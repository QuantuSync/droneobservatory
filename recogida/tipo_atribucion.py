"""Atribuciones ya guardadas, con la regla estricta (una vez, dentro de la recogida horaria).

Cada atribución guardada se vuelve a decidir con proceso/atribucion.py leyendo la frase guardada
de la autoridad que atribuye. Las guardadas no dicen si la frase son palabras literales de la
autoridad (lo pide la ficha del extractor desde esta regla): ninguna se sostiene. Cada una se
retira con un paso nuevo en el historial que vuelve al estado anterior a la atribución, con su
motivo (el revisado a mano en configuracion/atribuciones_revisadas.json o, si no lo hay, el de la
regla), lo que la autoridad investiga como investigación en curso y el titular sin lo que solo
decía la atribución. La base es de solo añadir: cada cambio es una versión nueva del incidente y
deja su motivo en el historial. También los fundidos en otro, que salen en la exportación
semanal.

Se ejecuta una vez por versión (el cursor CURSOR guarda la aplicada); después la regla se
aplica al construir cada incidente (proceso/declaraciones.py) y la validación la exige.
"""

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from almacen.base import Almacen, DocumentoInvalido
from esquema import Documento
from proceso import atribucion
from proceso.atribucion import Motivo
from proceso.presencia import TABLA_MOTIVOS

registro = logging.getLogger(__name__)

CURSOR = "tipo_atribucion"
VERSION = "atribucion/2"
RUTA_REVISADAS = Path(__file__).parents[1] / "configuracion" / "atribuciones_revisadas.json"
MOTIVO_TIPO = (
    "tipo de actor (Estado o persona) y país de la atribución, leídos de la frase guardada de "
    "la autoridad que atribuye"
)


def _por_regla(ruta: Path = RUTA_REVISADAS) -> dict[Motivo, dict[str, str]]:
    datos = json.loads(ruta.read_text(encoding="utf-8"))["por_regla"]
    return {Motivo(codigo): textos for codigo, textos in datos.items()}


# El motivo de la regla, para el historial de la ficha, cuando no hay uno revisado.
MOTIVOS: dict[Motivo, dict[str, str]] = _por_regla()


def revisadas(ruta: Path = RUTA_REVISADAS) -> dict[str, dict[str, str]]:
    datos: dict[str, dict[str, str]] = json.loads(ruta.read_text(encoding="utf-8"))["motivos"]
    return datos


def decidir(incidente: Documento) -> atribucion.Decision | None:
    """La regla sobre la atribución guardada de un incidente (None si no tiene)."""
    datos = incidente.get("atribucion")
    fuente = atribucion.fuente_de_atribucion(incidente)
    if datos is None or fuente is None:
        return None
    return atribucion.evaluar(
        str(datos["actor"]),
        str(fuente.get("frase_origen", "")),
        datos.get("tipo"),
        datos.get("pais"),
        # Lo guardado no dice si la frase es literal.
        literal=None,
        declarantes=[str(datos["autoridad"]), atribucion.autoridad_de_fuente(fuente)],
    )


def atribucion_borrada(almacen: Almacen, incidente: Documento) -> Documento | None:
    """Un incidente al que la primera versión de esta corrección (atribucion/1) quitó el paso a
    atribuido sin dejar rastro en su historial: el mismo con ese paso y su atribución de vuelta,
    sacados de su versión anterior guardada, para retirarla ahora con su motivo. None si no es
    el caso."""
    if "atribucion" in incidente or any("motivo" in p for p in incidente["estado"]["historial"]):
        return None
    for cambio in reversed(almacen.historial(incidente["id"])):
        anterior = cambio["anterior"]
        if cambio["tabla"] != "incidentes" or not isinstance(anterior, dict):
            continue
        if anterior.get("estado", {}).get("actual") != atribucion.ESTADO_ATRIBUIDO:
            continue
        if "atribucion" not in anterior:
            return None
        paso = anterior["estado"]["historial"][-1]
        historial = [*incidente["estado"]["historial"], paso]
        return {
            **incidente,
            "estado": {"actual": atribucion.ESTADO_ATRIBUIDO, "historial": historial},
            "atribucion": anterior["atribucion"],
        }
    return None


def aplicar(almacen: Almacen, ahora: datetime, modelos: frozenset[str]) -> dict[str, Any]:
    """Decide de nuevo las atribuciones guardadas si no se ha hecho ya. Devuelve el resumen
    (vacío si no hace nada)."""
    hecho = almacen.cursor(CURSOR) or {}
    if hecho.get("version") == VERSION:
        return {}
    instante = {"valor": ahora.astimezone(UTC).strftime("%Y-%m-%dT%H:%MZ"), "precision": "minuto"}
    motivos_revisados = revisadas()
    clasificados: list[str] = []
    retirados: dict[str, str] = {}
    fallidos: list[str] = []
    for guardado in almacen.incidentes():
        incidente = guardado
        if guardado["id"] in motivos_revisados:
            incidente = atribucion_borrada(almacen, guardado) or guardado
        decision = decidir(incidente)
        if decision is None:
            continue
        if decision.clase is not None:
            datos = {k: v for k, v in incidente["atribucion"].items() if k not in ("tipo", "pais")}
            nuevo = {**incidente, "atribucion": datos | decision.clase}
            texto = MOTIVO_TIPO
        else:
            motivo = (
                motivos_revisados.get(incidente["id"])
                or MOTIVOS[decision.motivo or Motivo.NO_LITERAL]
            )
            nuevo = atribucion.retirar(incidente, motivo, instante)
            texto = motivo["es"]
        if nuevo == guardado:
            continue
        documento: Documento = {
            **nuevo, "control": {**nuevo["control"], "ultima_actualizacion": instante},
        }  # fmt: skip
        try:
            almacen.guardar_incidente(documento, ahora, modelos)
        except DocumentoInvalido as error:
            registro.warning("atribución sin guardar en %s: %s", incidente["id"], error)
            fallidos.append(incidente["id"])
            continue
        campos = ("atribucion", "estado", "titulo", "investigacion")
        antes = {c: guardado.get(c) for c in campos if guardado.get(c) != documento.get(c)}
        despues = {c: documento.get(c) for c in antes}
        almacen.anotar_motivo(TABLA_MOTIVOS, documento["id"], antes, despues, texto)
        if decision.clase is not None:
            clasificados.append(documento["id"])
        else:
            retirados[documento["id"]] = (decision.motivo or Motivo.NO_LITERAL).value
    resumen: dict[str, Any] = {
        "version": VERSION,
        "fecha": ahora.strftime("%Y-%m-%dT%H:%MZ"),
        "clasificados": clasificados,
        "retirados": retirados,
        "sin_guardar": fallidos,
    }
    # Con incidentes sin guardar no se da por hecha: se vuelve a intentar en la siguiente.
    if not fallidos:
        almacen.guardar_cursor(CURSOR, resumen)
    registro.info(
        "atribuciones clasificadas: %d; retiradas: %d; sin guardar: %d",
        len(clasificados), len(retirados), len(fallidos),
    )  # fmt: skip
    return resumen
