"""Cuándo una respuesta del modelo base se escala al modelo experto (docs/modelos.md).

Lo decide el código, con reglas fijas, mirando la respuesta del modelo base:

1. **poca_seguridad**: el modelo base da una confianza baja (menos de 0,7) a un dato clave.
2. **duplicado_dudoso**: en el control de duplicados, el modelo base no sabe si dos fichas son el
   mismo suceso, su decisión no casa con lo que él mismo dice del día y del sitio, o dice que son
   del mismo día y del mismo sitio y aun así las separa (porque una fuente de una de ellas cita
   otro suceso: en la prueba del 14 de octubre de 2026 separó así dos duplicados reales).
3. **contradiccion** y **sin_cita**: las fuentes se contradicen (una autoridad dice que hubo
   drones y otra que no; la verificación de una ficha publicada contradice un dato clave) o un
   dato clave no tiene una frase que esté, literal, en su fuente.
4. **critico**: el caso es de los que más importan: un dron confirmado, atribuido a un Estado,
   una incursión en un país de la OTAN o en Moldavia, o un cierre de aeropuerto.

Si se escala, vale la respuesta del experto. Las tareas mecánicas (traducir citas, sacar lugares
de los partes de Ucrania, clasificar frases del catálogo) nunca se escalan.
"""

import json
from functools import cache
from pathlib import Path
from typing import Any

from proceso.noticias import normalizar

UMBRAL_SEGURIDAD = 0.7
# Los datos de una ficha que deciden lo que se publica.
CLAVE_FICHA = (
    "es_incidente", "tipo", "pais", "lugar_suceso", "inicio", "presencia_dron", "drones",
    "cierre", "cierre_minutos", "dron_estatal",
)  # fmt: skip
# Moldavia cuenta como la OTAN para estas reglas (como en los avisos de alta prioridad).
PAISES_CRITICOS_EXTRA = frozenset({"MD"})
AFIRMAN_DRONES = frozenset({"incidente", "drones"})
NIEGAN_DRONES = frozenset({"sin_drones", "niega_incidente"})
RUTA_PAISES = Path(__file__).resolve().parent.parent / "configuracion" / "avisos.json"


@cache
def paises_otan() -> frozenset[str]:
    datos = json.loads(RUTA_PAISES.read_text(encoding="utf-8"))
    return frozenset(c for c, d in datos["paises"].items() if d.get("otan"))


def _valor(ficha: dict[str, Any], campo: str) -> Any:
    dato = ficha.get(campo)
    return dato.get("valor") if isinstance(dato, dict) else None


def _con_cita(dato: dict[str, Any], textos: tuple[str, ...]) -> bool:
    fuente, frase = dato.get("fuente"), dato.get("frase")
    if not isinstance(fuente, int) or not 1 <= fuente <= len(textos):
        return False
    if not isinstance(frase, str) or not frase.strip():
        return False
    return normalizar(frase) in normalizar(textos[fuente - 1])


def motivos_ficha(ficha: dict[str, Any], textos: tuple[str, ...]) -> list[str]:
    """Los motivos para escalar una ficha leída (modelo/ficha.leer_respuesta); vacía, ninguno.

    `textos`: el titular y el texto de cada fuente, en el orden en que se mandaron.
    """
    motivos: list[str] = []
    for campo in CLAVE_FICHA:
        dato = ficha.get(campo)
        if not isinstance(dato, dict):
            continue
        confianza = dato.get("confianza")
        if isinstance(confianza, int | float) and confianza < UMBRAL_SEGURIDAD:
            motivos.append(f"poca_seguridad: {campo}")
    if _valor(ficha, "es_incidente") is False and not motivos:
        # El modelo base está seguro de que no es un incidente: no hay nada que publicar.
        return []
    for campo in CLAVE_FICHA:
        dato = ficha.get(campo)
        if isinstance(dato, dict) and campo != "es_incidente" and not _con_cita(dato, textos):
            motivos.append(f"sin_cita: {campo}")
    afirma = {d.get("afirma") for d in ficha.get("declaraciones", []) if isinstance(d, dict)}
    presencia = _valor(ficha, "presencia_dron")
    if afirma & NIEGAN_DRONES and (afirma & AFIRMAN_DRONES or presencia == "confirmada"):
        motivos.append("contradiccion: unas fuentes dicen que hubo drones y otras que no")
    if presencia == "confirmada":
        motivos.append("critico: dron confirmado")
    if _valor(ficha, "dron_estatal") is True or "autoria" in afirma:
        motivos.append("critico: atribuido")
    pais = str(_valor(ficha, "pais") or "").upper()
    if _valor(ficha, "tipo") == "incursion" and (
        pais in paises_otan() or pais in PAISES_CRITICOS_EXTRA
    ):
        motivos.append(f"critico: incursión en {pais}")
    if _valor(ficha, "cierre") == "si":
        motivos.append("critico: cierre de aeropuerto")
    return motivos


def motivos_comparacion(decision: dict[str, Any]) -> list[str]:
    """Los motivos para escalar la comparación de dos fichas (modelo/control.py, «comparar»)."""
    valor = decision.get("decision")
    if valor == "dudoso":
        return ["duplicado_dudoso: el modelo base no lo sabe"]
    juntos = (
        decision.get("mismo_dia") is True
        and decision.get("mismo_sitio") is True
        and decision.get("varios_sucesos") is False
    )
    if (valor == "mismo") != juntos:
        return ["duplicado_dudoso: la decisión no casa con el día y el sitio"]
    if valor != "mismo" and decision.get("mismo_dia") is True and decision.get("mismo_sitio") is True:
        return ["duplicado_dudoso: mismo día y mismo sitio, pero separados"]
    return []


def motivos_verificacion(
    contradice: list[str], critico: bool, sin_cita: list[str] | None = None
) -> list[str]:
    """Los motivos para escalar la verificación de una ficha.

    `contradice`: los datos clave en que la verificación del modelo base contradice la ficha;
    `critico`: la ficha es de un caso crítico; `sin_cita`: datos que la verificación da sin una
    frase literal. Una verificación que confirma la ficha no se escala aunque sea crítica: la
    ficha de un caso crítico ya la decidió el experto.
    """
    motivos = [f"contradiccion: {c}" for c in contradice]
    if critico and motivos:
        motivos.append("critico")
    motivos += [f"sin_cita: {c}" for c in sin_cita or []]
    return motivos
