"""Suelo europeo fuera del continente: territorios con su país padre, soberanías dentro de otro
país y hora local por territorio (configuracion/territorios.json)."""

import json
from functools import cache
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

RUTA = Path(__file__).resolve().parent.parent / "configuracion" / "territorios.json"


@cache
def configuracion() -> dict[str, Any]:
    datos: dict[str, Any] = json.loads(RUTA.read_text(encoding="utf-8"))
    return datos


def pais_padre(codigo: str) -> str:
    """El país del que depende un territorio («GI» → «GB», «RE» → «FR»); cualquier otro código,
    tal cual."""
    return str(configuracion()["padres"].get(codigo.strip().upper(), codigo))


def soberanos_dentro(pais: str) -> tuple[str, ...]:
    """Países con suelo dentro de `pais` (Reino Unido en Chipre)."""
    return tuple(configuracion()["soberanias"].get(pais, ()))


def zona_del_punto(lat: float | None, lon: float | None) -> ZoneInfo | None:
    """La hora local del territorio en que cae el punto, o None si no cae en ninguno."""
    if lat is None or lon is None:
        return None
    for entrada in configuracion()["zonas"]:
        oeste, sur, este, norte = entrada["caja"]
        if oeste <= lon <= este and sur <= lat <= norte:
            return ZoneInfo(entrada["zona"])
    return None
