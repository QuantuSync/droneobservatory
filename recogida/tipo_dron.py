"""Tipo de dron de cada incidente en la recogida horaria (proceso/tipo_dron).

Después de frontera o interior y antes de publicar: para cada incidente vigente, lo que identificó
la autoridad, los rasgos descritos y la clase probable; y la comprobación contra los casos de
respuesta conocida, que decide qué grupos se publican. Solo se guarda lo que cambia (tabla
tipos_dron, con historial). Lo que se publicaba y deja de publicarse se marca como retirado, con
su motivo en español y en inglés. Un fallo aquí no cambia el resultado de la recogida: queda la
última versión guardada.

Tarda unos segundos (medido con la base del 6 de octubre de 2026: 438 incidentes, 69 casos de
respuesta conocida, 11 s con la carga de la base).
"""

import logging
import time
from datetime import datetime
from typing import Any

from almacen.base import Almacen
from esquema import Documento
from exportacion import mejor_origen, procedencia, semanal
from proceso.deduccion import catalogo as catalogo_
from proceso.tipo_dron import calculo

registro = logging.getLogger(__name__)
CURSOR = "tipo_dron"
TOPE_S = 120
MOTIVO_RETIRADA = {
    "es": "El tipo deducido deja de publicarse: con los datos de ahora no hay base o su grupo "
    "ya no pasa la comprobación con casos de respuesta conocida.",
    "en": "The deduced type is no longer published: with current data there is no basis or "
    "its group no longer passes the check against cases with a known answer.",
}


def _instante(ahora: datetime) -> str:
    return ahora.strftime("%Y-%m-%dT%H:%MZ")


def entradas(almacen: Almacen) -> list[tuple[Documento, list[Any], Documento | None]]:
    """(incidente, frases de mejor origen, deducción) de cada incidente vigente."""
    deducciones = almacen.deducciones("incidente")
    incidentes = [
        d for d in almacen.incidentes() if "fusionado_en" not in d and "retirado" not in d
    ]
    contextos = semanal.contextos_mejor_origen(almacen, incidentes)
    return [
        (
            d,
            mejor_origen.frases(d, contextos[d["id"]], procedencia.origen_de_fuente),
            deducciones.get(d["id"]),
        )
        for d in incidentes
    ]


def _con_retirada(nuevo: Documento, anterior: Documento | None, ahora: datetime) -> Documento:
    if anterior is None or "publicado" not in anterior or "publicado" in nuevo:
        return nuevo
    if "identificado" in nuevo:
        return nuevo
    return {**nuevo, "retirado": {"fecha": _instante(ahora), "motivo": dict(MOTIVO_RETIRADA)}}


def actualizar(almacen: Almacen, ahora: datetime) -> dict[str, Any]:
    inicio = time.monotonic()
    catalogo = catalogo_.cargar_vivo(almacen.catalogo_vivo("catalogo").get("catalogo"))
    documentos, resumen = calculo.calcular(
        catalogo, entradas(almacen), almacen.encuentros(), almacen.episodios()
    )
    anteriores = almacen.tipos_dron()
    guardados = 0
    for id_, documento in sorted(documentos.items()):
        if time.monotonic() - inicio > TOPE_S:
            registro.warning("tipo de dron: tope de tiempo, el resto en la siguiente recogida")
            break
        if almacen.guardar_tipo_dron(id_, _con_retirada(documento, anteriores.get(id_), ahora)):
            guardados += 1
    cursor = {**resumen, "calculado": _instante(ahora), "recuento": calculo.recuento(documentos)}
    previo = almacen.cursor(CURSOR) or {}
    if {k: v for k, v in previo.items() if k != "calculado"} != {
        k: v for k, v in cursor.items() if k != "calculado"
    }:
        almacen.guardar_cursor(CURSOR, cursor)
    return {"guardados": guardados, **calculo.recuento(documentos),
            "grupos_publicados": resumen["grupos_publicados"], "pasa": resumen["pasa"]}  # fmt: skip


def paso_horario(almacen: Almacen, ahora: datetime) -> None:
    """En la recogida horaria: nada de lo que falle aquí sale de esta función."""
    try:
        registro.info("tipo de dron: %s", actualizar(almacen, ahora))
    except Exception as error:
        registro.warning("tipo de dron sin calcular: %s", str(error)[:300])
