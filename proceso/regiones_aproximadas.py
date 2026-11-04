"""El centro de la región que nombra la fuente de un incidente sin punto.

Un incidente que solo se sabe a nivel de región (o de una localidad que no se pudo situar) se
publica sin punto, en incidentes_sin_ubicacion.json, y la web lo pinta con un marcador
aproximado (web/src/datos/lugarAproximado.ts). Ese marcador va en el centro de la región que da
la ficha: el punto de etiqueta de Natural Earth de sus regiones de primer nivel (los județe
rumanos, los raioane moldavos, los voivodatos polacos…), en configuracion/regiones_aproximadas.json
(recogida/regiones_natural_earth.py). Se busca por el nombre normalizado, sin acentos y sin las
palabras de clase de región: «județul Iași», «Iasi», «Яссы» y «Iași County» son la misma.

No es un dato de la fuente: el punto solo sirve para que el incidente se vea cerca de donde
fue, y la ficha dice que el lugar es aproximado y a qué nivel. Desde el 2 de noviembre de 2026:
EODI-2026-00725 (Frătăuți y Horodnic, Suceava) caía en el centro de Rumanía, a 250 km.
"""

import json
from functools import cache
from pathlib import Path
from typing import Any

from recogida.regiones_natural_earth import normalizar, sin_genericos

TABLA = Path(__file__).resolve().parent.parent / "configuracion" / "regiones_aproximadas.json"


@cache
def _filas() -> dict[tuple[str, str], tuple[float, float, dict[str, str]]]:
    """(país, nombre normalizado) → (longitud, latitud, nombre escrito en español e inglés)."""
    datos: dict[str, Any] = json.loads(TABLA.read_text(encoding="utf-8"))
    indice: dict[tuple[str, str], tuple[float, float, dict[str, str]]] = {}
    for pais, lon, lat, nombres, escrito_ in datos["regiones"]:
        for nombre in nombres:
            indice.setdefault((pais, nombre), (float(lon), float(lat), escrito_))
    return indice


def _fila(pais: str | None, region: str | None) -> tuple[float, float, dict[str, str]] | None:
    if not pais or not region:
        return None
    normal = normalizar(region)
    indice = _filas()
    for forma in (normal, sin_genericos(normal)):
        fila = indice.get((pais, forma))
        if fila is not None:
            return fila
    return None


def centro(pais: str | None, region: str | None) -> tuple[float, float] | None:
    """(longitud, latitud) del centro de la región del país con ese nombre, o None si no está
    o no se sabe cuál es."""
    fila = _fila(pais, region)
    return None if fila is None else (fila[0], fila[1])


def escrito(pais: str | None, region: str | None) -> dict[str, str] | None:
    """El nombre de la región en español y en inglés (Natural Earth), sea cual sea la lengua en
    que la nombra la ficha: «Dolna Saksonia», «Niedersachsen» y «Lower Saxony» son «Baja Sajonia»
    y «Lower Saxony». None si la región no está en la tabla."""
    fila = _fila(pais, region)
    return None if fila is None else dict(fila[2])


def con_centro(lugar: dict[str, Any]) -> dict[str, Any]:
    """El lugar publicado de un incidente sin punto con el centro de su región
    (`centro_region`), si la región se conoce. Uno de nivel país no lo lleva."""
    if lugar.get("nivel", "pais") == "pais" or "punto" in lugar:
        return lugar
    punto = centro(lugar.get("pais"), lugar.get("region"))
    if punto is None:
        return lugar
    return {**lugar, "centro_region": {"lon": punto[0], "lat": punto[1]}}
