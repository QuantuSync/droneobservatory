"""Declaraciones oficiales citadas por la prensa: cómo cambian el incidente.

Las autoridades confirman los incidentes en declaraciones a la prensa, no en sus
webs. Cada declaración que el extractor encuentra en una noticia (con su frase
literal, que tiene que estar en el texto enviado) se registra como fuente
«declaración oficial citada», de fiabilidad B, con el enlace a la noticia. Reglas:

- incidente o drones: pasa a confirmado (la autoridad dice que ocurrió).
- drones: presencia_dron confirmada; solo si la frase no habla de avisos recibidos
  («la policía recibió avisos de drones» no confirma nada).
- sin_drones: presencia_dron descartada. niega_incidente: desmentido.
- autoria: atribuido, solo si quien atribuye es un gobierno.
"""

import contextlib
import copy
import re
from collections.abc import Sequence
from typing import Any

from esquema import Documento
from proceso.credibilidad import Credibilidad
from proceso.estados import Estado, TransicionNoPermitida, transitar

MAX_PALABRAS_FRASE = 25
FIABILIDAD = "B"
# Avisos o llamadas recibidos por la autoridad: no son una afirmación suya.
_AVISOS = re.compile(
    r"\b(avisos?|llamadas|report(s|ed)?|tips?|meldinger|henvendelser|anmeldelser|"
    r"Hinweise|Meldungen|Anrufe|zgłosze\w*|sesizări|meldingen)\b",
    re.IGNORECASE,
)
_CONFIRMAN = frozenset({"incidente", "drones"})


def _normal(texto: str) -> str:
    return " ".join(texto.lower().split())


def validas(declaraciones: Sequence[dict[str, Any]], textos: Sequence[str]) -> list[dict[str, Any]]:
    """Las declaraciones cuya frase está en el texto de su fuente, con la frase recortada."""
    resultado = []
    for declaracion in declaraciones:
        numero = declaracion.get("fuente")
        frase = str(declaracion.get("frase", ""))
        if not isinstance(numero, int) or not 1 <= numero <= len(textos) or not frase.strip():
            continue
        if _normal(frase) not in _normal(textos[numero - 1]):
            continue
        palabras = frase.split()[:MAX_PALABRAS_FRASE]
        resultado.append({**declaracion, "frase": " ".join(palabras)})
    return resultado


def cuenta(declaracion: dict[str, Any]) -> bool:
    """Si la declaración es una afirmación de la autoridad y no un aviso que recibió."""
    return not (declaracion["afirma"] in _CONFIRMAN and _AVISOS.search(declaracion["frase"]))


def fuente(declaracion: dict[str, Any], noticia: Documento, numero: int) -> Documento:
    resultado = copy.deepcopy(noticia)
    resultado.update({
        "id": f"{noticia['id']}-declaracion-{numero}",
        "medio": f"{declaracion['autoridad']} (declaración oficial citada en {noticia['medio']})",
        "fiabilidad": FIABILIDAD,
        "credibilidad": int(Credibilidad.CONFIRMADO),
        "frase_origen": declaracion["frase"],
        "replicas": 0,
        "campos_respaldados": ["estado", "presencia_dron"],
        "es_autoridad": True,
    })  # fmt: skip
    return resultado


def _transitar(incidente: Documento, destino: Estado, origen: Documento) -> None:
    if incidente["estado"]["actual"] == destino:
        return
    fuentes = {f["id"]: f for f in incidente["fuentes"]}
    # Un cambio que la máquina de estados no permite (revertir un desmentido de más
    # fiabilidad, atribuir sin confirmar) se deja sin hacer.
    with contextlib.suppress(TransicionNoPermitida):
        incidente["estado"] = transitar(
            incidente["estado"], destino, origen["fecha"], origen["id"], fuentes
        )


def aplicar(
    incidente: Documento, declaraciones: Sequence[dict[str, Any]], enviadas: Sequence[str]
) -> Documento:
    """El incidente con las declaraciones como fuentes y sus cambios de estado y presencia."""
    resultado = copy.deepcopy(incidente)
    por_enlace = {f["enlace"]: f for f in resultado["fuentes"]}
    nuevas: list[tuple[dict[str, Any], Documento]] = []
    for numero, declaracion in enumerate(declaraciones, 1):
        noticia = por_enlace.get(enviadas[declaracion["fuente"] - 1])
        if noticia is None or not cuenta(declaracion):
            continue
        nuevas.append((declaracion, fuente(declaracion, noticia, numero)))
    resultado["fuentes"] = [*resultado["fuentes"], *(f for _, f in nuevas)]
    # Primero lo que confirma y después lo que desmiente o atribuye.
    orden = {"incidente": 0, "drones": 0, "sin_drones": 1, "niega_incidente": 2, "autoria": 3}
    for declaracion, origen in sorted(nuevas, key=lambda n: orden[n[0]["afirma"]]):
        afirma = declaracion["afirma"]
        if afirma in _CONFIRMAN:
            _transitar(resultado, Estado.CONFIRMADO, origen)
        if afirma == "drones":
            resultado["presencia_dron"] = "confirmada"
        elif afirma == "sin_drones":
            resultado["presencia_dron"] = "descartada"
        elif afirma == "niega_incidente":
            _transitar(resultado, Estado.DESMENTIDO, origen)
            if resultado["estado"]["actual"] == Estado.DESMENTIDO:
                resultado["control"]["motivo_desmentido"] = (
                    f"{declaracion['autoridad']}: «{declaracion['frase']}»"
                )
        elif afirma == "autoria" and declaracion["categoria"] == "gobierno":
            actor = str(declaracion.get("autor", "")).strip()
            if actor and resultado["estado"]["actual"] == Estado.CONFIRMADO:
                _transitar(resultado, Estado.ATRIBUIDO, origen)
            if actor and resultado["estado"]["actual"] == Estado.ATRIBUIDO:
                resultado["atribucion"] = {
                    "actor": actor,
                    "autoridad": declaracion["autoridad"],
                    "fecha": origen["fecha"],
                }
    return resultado
