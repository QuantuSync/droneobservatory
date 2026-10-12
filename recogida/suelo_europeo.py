"""Los incidentes ya guardados, con el país del suelo europeo de fuera del continente.

Desde el 12 de octubre de 2026 cada territorio cuenta como su país (configuracion/territorios.json):
Gibraltar es Reino Unido (antes «GI», que ya no es un país de las fronteras) y el suelo de las
bases soberanas de Akrotiri y Dhekelia también (antes caía en Chipre). En cada recogida horaria se
corrigen los incidentes guardados con el país de antes: un territorio pasa a su país padre y un
punto que ya no cae en su país pero sí en el de un soberano dentro de él (Reino Unido en Chipre)
pasa a ese país. Sin esto, dejarían de publicarse (el punto fuera de su país). Ya aplicado, no
cambia nada. Cada cambio queda en el historial con su motivo.
"""

import logging
from datetime import UTC, datetime

from almacen.base import Almacen, DocumentoInvalido
from esquema import Documento
from proceso.fronteras import dentro_del_pais, paises
from proceso.territorios import pais_padre, soberanos_dentro

registro = logging.getLogger("recogida")

TABLA = "incidentes"
MOTIVO = (
    "suelo europeo fuera del continente: el territorio cuenta como el país del que depende "
    "(configuracion/territorios.json)"
)


def pais_corregido(lugar: Documento) -> str | None:
    """El país que le toca al lugar ahora, o None si el que tiene ya vale."""
    pais = str(lugar.get("pais") or "")
    nuevo = pais_padre(pais)
    punto = lugar.get("punto")
    if isinstance(punto, dict) and nuevo in paises():
        lat, lon = float(punto["lat"]), float(punto["lon"])
        if not dentro_del_pais(nuevo, lat, lon):
            for soberano in soberanos_dentro(nuevo):
                if dentro_del_pais(soberano, lat, lon):
                    nuevo = soberano
                    break
    return nuevo if nuevo != pais else None


def paso_horario(almacen: Almacen, ahora: datetime, modelos: frozenset[str]) -> int:
    """Corrige el país de los incidentes guardados; devuelve cuántos cambian."""
    cambiados = 0
    for documento in almacen.incidentes():
        lugar = documento.get("lugar") or {}
        nuevo_pais = pais_corregido(lugar)
        if nuevo_pais is None:
            continue
        control = {
            **documento["control"],
            "ultima_actualizacion": {
                "valor": ahora.astimezone(UTC).strftime("%Y-%m-%dT%H:%MZ"),
                "precision": "minuto",
            },
        }
        nuevo = {**documento, "lugar": {**lugar, "pais": nuevo_pais}, "control": control}
        try:
            almacen.guardar_incidente(nuevo, ahora, modelos)
        except DocumentoInvalido as error:
            registro.warning("país sin corregir en %s: %s", documento["id"], str(error)[:300])
            continue
        almacen.anotar_motivo(
            TABLA, documento["id"], {"lugar": lugar}, {"lugar": nuevo["lugar"]}, MOTIVO
        )
        registro.info("%s: país %s → %s (%s)", documento["id"], lugar.get("pais"), nuevo_pais,
                      MOTIVO)  # fmt: skip
        cambiados += 1
    return cambiados
