"""Viento y temperatura medidos (Open-Meteo, bloque `condiciones` de cada incidente o ataque) a
la altura de vuelo de cada clase.

Las alturas de los niveles de presión son las de la atmósfera estándar de la OACI (Doc 7488):
1000 hPa a unos 111 m, 925 hPa a 762 m, 850 hPa a 1457 m y 700 hPa a 3012 m sobre el nivel del
mar. Es una aproximación (la altura real del nivel cambia con el tiempo), así que solo sirve
para elegir qué niveles caen en la banda de vuelo de una clase; el viento sale tal cual.

Con solo el día (`rango_dia`), cada valor es el mínimo y el máximo del día y no hay dirección:
para descartar se usa el mínimo del día (lo más favorable al dron).
"""

import math
from dataclasses import dataclass
from typing import Any

ALTURA_NIVEL_M = {"1000": 111.0, "925": 762.0, "850": 1457.0, "700": 3012.0}


@dataclass(frozen=True)
class Lectura:
    """Viento a una altura: velocidad en m/s (la más baja del día con rango_dia) y de dónde
    sopla, en grados (None si no se sabe)."""

    altura_m: float
    nombre: str
    velocidad_ms: float
    direccion: float | None


def _numero(valor: Any, mas_bajo: bool = True) -> float | None:
    if isinstance(valor, int | float):
        return float(valor)
    if (
        isinstance(valor, list)
        and len(valor) == 2
        and all(isinstance(v, int | float) for v in valor)
    ):
        return float(min(valor) if mas_bajo else max(valor))
    return None


def lecturas(lugar: dict[str, Any] | None) -> list[Lectura]:
    """Todas las lecturas de viento del lugar, de la más baja a la más alta."""
    if not lugar:
        return []
    resultado = []
    superficie = lugar.get("superficie") or {}
    for nombre, altura, velocidad, direccion in (
        ("10m", 10.0, "viento_10m_ms", "direccion_10m"),
        ("100m", 100.0, "viento_100m_ms", "direccion_100m"),
    ):
        v = _numero(superficie.get(velocidad))
        if v is not None:
            resultado.append(Lectura(altura, nombre, v, _numero(superficie.get(direccion))))
    for nivel, datos in sorted((lugar.get("niveles") or {}).items(), key=lambda x: -int(x[0])):
        v = _numero((datos or {}).get("viento_ms"))
        if v is not None and nivel in ALTURA_NIVEL_M:
            resultado.append(
                Lectura(
                    ALTURA_NIVEL_M[nivel], f"{nivel}hPa", v, _numero((datos or {}).get("direccion"))
                )
            )
    return sorted(resultado, key=lambda x: x.altura_m)


def en_banda(lista: list[Lectura], desde_m: float | None, hasta_m: float | None) -> list[Lectura]:
    """Las lecturas entre dos alturas; si ninguna cae dentro, la más cercana por cada lado
    (el viento de la banda está entre ellas)."""
    bajo = 0.0 if desde_m is None else desde_m
    alto = math.inf if hasta_m is None else hasta_m
    dentro = [x for x in lista if bajo <= x.altura_m <= alto]
    if dentro:
        return dentro
    debajo = [x for x in lista if x.altura_m < bajo]
    encima = [x for x in lista if x.altura_m > alto]
    return ([debajo[-1]] if debajo else []) + ([encima[0]] if encima else [])


def racha(lugar: dict[str, Any] | None) -> float | None:
    if not lugar:
        return None
    return _numero((lugar.get("superficie") or {}).get("racha_10m_ms"), mas_bajo=False)


def temperatura(lugar: dict[str, Any] | None) -> tuple[float, float] | None:
    """Temperatura en superficie: (la más baja, la más alta) del momento o del día."""
    if not lugar:
        return None
    valor = (lugar.get("superficie") or {}).get("temperatura_c")
    if isinstance(valor, int | float):
        return float(valor), float(valor)
    if isinstance(valor, list) and len(valor) == 2:
        return float(min(valor)), float(max(valor))
    return None


def precipitacion(lugar: dict[str, Any] | None) -> float | None:
    if not lugar:
        return None
    return _numero((lugar.get("superficie") or {}).get("precipitacion_mm"), mas_bajo=False)


def vector(velocidad_ms: float, direccion: float) -> tuple[float, float]:
    """(este, norte) en m/s hacia donde va el aire: la dirección meteorológica es de dónde sopla."""
    hacia = math.radians((direccion + 180.0) % 360.0)
    return velocidad_ms * math.sin(hacia), velocidad_ms * math.cos(hacia)


def medio(lista: list[Lectura]) -> tuple[float, float] | None:
    """Vector medio de las lecturas con dirección, o None si ninguna la tiene."""
    vectores = [vector(x.velocidad_ms, x.direccion) for x in lista if x.direccion is not None]
    if not vectores:
        return None
    return (
        sum(v[0] for v in vectores) / len(vectores),
        sum(v[1] for v in vectores) / len(vectores),
    )
