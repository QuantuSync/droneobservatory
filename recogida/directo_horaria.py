"""Confirmación de los avisos de la detección en directo, en la recogida horaria.

El servicio en directo (`recogida/directo.py`) no abre la base: deja sus avisos en
`<datos>/avisos.json`. La recogida horaria, que la tiene abierta, busca para cada aviso un
incidente de la base en ese aeropuerto y en su ventana (`proceso/directo.confirmar`): con
él, el aviso pasa a «cierre confirmado» (oficial si alguna fuente del incidente es oficial) y
guarda la hora de la primera noticia. Lo deja en `<datos>/confirmaciones.json`, que el
servicio aplica en su ciclo siguiente. El incidente entra en la base por el flujo normal (la
búsqueda dirigida que lanza el aviso, el extractor) y su cierre medido llega con el archivo
diario de adsb.lol, con origen «medido».

Un fallo aquí no cambia el resultado de la recogida.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from almacen.base import Almacen
from proceso import directo
from recogida.directo import AVISOS, CONFIRMACIONES, directorio_datos, escribir_json

registro = logging.getLogger("recogida")


def confirmaciones(
    avisos: list[dict[str, Any]], incidentes: list[dict[str, Any]]
) -> dict[str, Any]:
    resultado: dict[str, Any] = {}
    for documento in avisos:
        aviso = directo.Aviso.de_documento(documento)
        if directo.confirmar(aviso, incidentes):
            resultado[aviso.id] = {
                "confirmacion": aviso.confirmacion,
                "primera_noticia": (
                    None
                    if aviso.primera_noticia is None
                    else directo.instante(aviso.primera_noticia)
                ),
            }
    return resultado


def paso_horario(almacen: Almacen, ahora: datetime, datos: Path | None = None) -> int:
    datos = datos or directorio_datos()
    try:
        avisos = json.loads((datos / AVISOS).read_text(encoding="utf-8")).get("avisos", [])
    except (OSError, ValueError):
        return 0
    if not avisos:
        return 0
    hallados = confirmaciones(avisos, almacen.incidentes())
    escribir_json(
        datos / CONFIRMACIONES,
        {"generado": ahora.strftime("%Y-%m-%dT%H:%MZ"), "avisos": hallados},
    )
    return len(hallados)
