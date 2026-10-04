"""Tipo de actor y país de las atribuciones ya guardadas (una vez, dentro de la recogida
horaria).

Desde el esquema 1.10.0 cada atribución dice si se atribuye a un Estado o a una persona y su
país (proceso/atribucion.py). Las guardadas antes no lo traen: se clasifican leyendo la frase
guardada de la autoridad que atribuye. Si la frase no nombra a quien se atribuye (el extractor
puso el nombre de quien habla como autor), el incidente vuelve al estado que tenía antes de la
atribución. La base es de solo añadir: cada cambio es una versión nueva del incidente y deja su
motivo en el historial. También los fundidos en otro, que salen en la exportación semanal.

Se ejecuta una vez por versión (el cursor CURSOR guarda la aplicada); después la regla se
aplica al construir cada incidente (proceso/declaraciones.py) y la validación la exige.
"""

import logging
from datetime import UTC, datetime
from typing import Any

from almacen.base import Almacen, DocumentoInvalido
from esquema import Documento
from proceso import atribucion
from proceso.presencia import TABLA_MOTIVOS

registro = logging.getLogger(__name__)

CURSOR = "tipo_atribucion"
VERSION = "atribucion/1"
MOTIVO_TIPO = (
    "tipo de actor (Estado o persona) y país de la atribución, leídos de la frase guardada de "
    "la autoridad que atribuye"
)
MOTIVO_SIN_ATRIBUCION = (
    "la frase de la autoridad no nombra a quien se atribuye (el autor guardado era quien "
    "habla): sin atribución, vuelve al estado anterior"
)


def aplicar(almacen: Almacen, ahora: datetime, modelos: frozenset[str]) -> dict[str, Any]:
    """Clasifica las atribuciones guardadas si no se ha hecho ya. Devuelve el resumen (vacío si
    no hace nada)."""
    hecho = almacen.cursor(CURSOR) or {}
    if hecho.get("version") == VERSION:
        return {}
    instante = {"valor": ahora.astimezone(UTC).strftime("%Y-%m-%dT%H:%MZ"), "precision": "minuto"}
    clasificados: list[str] = []
    retirados: list[str] = []
    fallidos: list[str] = []
    for incidente in almacen.incidentes():
        nuevo = atribucion.corregir(incidente)
        if nuevo is incidente:
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
        sigue = "atribucion" in documento
        campos = ("atribucion", "estado")
        antes = {c: incidente.get(c) for c in campos if incidente.get(c) != documento.get(c)}
        despues = {c: documento.get(c) for c in antes}
        motivo = MOTIVO_TIPO if sigue else MOTIVO_SIN_ATRIBUCION
        almacen.anotar_motivo(TABLA_MOTIVOS, documento["id"], antes, despues, motivo)
        (clasificados if sigue else retirados).append(documento["id"])
    resumen: dict[str, Any] = {
        "version": VERSION,
        "fecha": ahora.strftime("%Y-%m-%dT%H:%MZ"),
        "clasificados": clasificados,
        "sin_atribucion": retirados,
        "sin_guardar": fallidos,
    }
    # Con incidentes sin guardar no se da por hecha: se vuelve a intentar en la siguiente.
    if not fallidos:
        almacen.guardar_cursor(CURSOR, resumen)
    registro.info(
        "atribuciones clasificadas: %d; sin atribución: %d; sin guardar: %d",
        len(clasificados), len(retirados), len(fallidos),
    )  # fmt: skip
    return resumen
