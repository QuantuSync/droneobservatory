"""Condiciones medidas de cada incidente y de cada ataque de la capa de guerra.

**Incidente europeo.** En su punto (o, sin punto, en su aeropuerto) y a su hora:
meteorología de Open-Meteo (superficie y niveles de presión de 1000, 925, 850 y 700 hPa), el
METAR más cercano en el tiempo (como mucho una hora antes o después) de su aeropuerto o del
aeropuerto más cercano a 50 km o menos, y el sol y la luna (`proceso/astronomia.py`). Con solo
el día, cada valor es el mínimo y el máximo del día UTC, el METAR es el de peor visibilidad
del día, y en lugar del sol se dan las horas de luz; el bloque lo declara con `rango_dia`.

**Ataque de la capa de guerra.** Viento a 10 m, a 100 m y en 925, 850 y 700 hPa en cada zona
de lanzamiento que nombra el parte (a la hora de inicio del periodo) y en cada región del
ataque (a la mitad del periodo), con su capital como punto
(`configuracion/lugares_meteo_ucrania.json`). Un nombre de región o de mar como zona de
lanzamiento no tiene punto.

Lo que Open-Meteo no da llega como null y se guarda vacío; nunca se rellena.
"""

import json
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from functools import cache
from pathlib import Path
from typing import Any

from esquema import Documento
from proceso import astronomia, metar, vuelos

LUGARES = Path(__file__).resolve().parent.parent / "configuracion" / "lugares_meteo_ucrania.json"
VERSION_REGLA = "1.0.0"
RADIO_METAR_KM = 50.0
MARGEN_METAR = timedelta(hours=1)
MAXIMO_LANZAMIENTO = 6
MAXIMO_IMPACTO = 8

SUPERFICIE = {
    "temperatura_c": "temperature_2m",
    "humedad_pct": "relative_humidity_2m",
    "precipitacion_mm": "precipitation",
    "nubosidad_pct": "cloud_cover",
    "viento_10m_ms": "wind_speed_10m",
    "direccion_10m": "wind_direction_10m",
    "racha_10m_ms": "wind_gusts_10m",
    "viento_100m_ms": "wind_speed_100m",
    "direccion_100m": "wind_direction_100m",
}
NIVELES = (1000, 925, 850, 700)
EN_NIVEL = {
    "viento_ms": "wind_speed",
    "direccion": "wind_direction",
    "temperatura_c": "temperature",
}
DIRECCIONES = frozenset({"direccion_10m", "direccion_100m", "direccion"})

# Series horarias de un día en un punto: variable de Open-Meteo → 24 valores (o None).
Horario = dict[str, list[Any]]


def _valor(horario: Horario, variable: str, hora: int) -> float | None:
    serie = horario.get(variable) or []
    if 0 <= hora < len(serie) and isinstance(serie[hora], int | float):
        return round(float(serie[hora]), 1)
    return None


def _rango(horario: Horario, variable: str) -> list[float] | None:
    serie = [float(v) for v in horario.get(variable) or [] if isinstance(v, int | float)]
    return [round(min(serie), 1), round(max(serie), 1)] if serie else None


def meteorologia(horario: Horario, hora: int | None) -> tuple[Documento, Documento]:
    """Superficie y niveles a una hora (o el rango del día si `hora` es None)."""

    def leer(nombre: str, variable: str) -> Any:
        if hora is not None:
            return _valor(horario, variable, hora)
        return None if nombre in DIRECCIONES else _rango(horario, variable)

    superficie = {nombre: leer(nombre, variable) for nombre, variable in SUPERFICIE.items()}
    niveles = {
        str(n): {nombre: leer(nombre, f"{v}_{n}hPa") for nombre, v in EN_NIVEL.items()}
        for n in NIVELES
    }
    return superficie, niveles


def viento(horario: Horario, hora: int) -> tuple[Documento, Documento]:
    """Solo el viento (capa de guerra): 10 y 100 m y 925, 850 y 700 hPa."""
    superficie = {
        "viento_10m_ms": _valor(horario, "wind_speed_10m", hora),
        "direccion_10m": _valor(horario, "wind_direction_10m", hora),
        "viento_100m_ms": _valor(horario, "wind_speed_100m", hora),
        "direccion_100m": _valor(horario, "wind_direction_100m", hora),
    }
    niveles = {
        str(n): {
            "viento_ms": _valor(horario, f"wind_speed_{n}hPa", hora),
            "direccion": _valor(horario, f"wind_direction_{n}hPa", hora),
        }
        for n in (925, 850, 700)
    }
    return superficie, niveles


def estacion_metar(
    lat: float, lon: float, oaci: str | None, aeropuertos: dict[str, vuelos.Aeropuerto]
) -> tuple[str, float] | None:
    """El aeropuerto del incidente o el más cercano a 50 km o menos, con su distancia."""
    if oaci and oaci in aeropuertos:
        a = aeropuertos[oaci]
        return oaci, round(vuelos.distancia_km(lat, lon, a.lat, a.lon), 1)
    cercanos = sorted(
        (vuelos.distancia_km(lat, lon, a.lat, a.lon), a.oaci)
        for a in aeropuertos.values()
        if abs(a.lat - lat) < 1 and abs(a.lon - lon) < 1.5
    )
    if cercanos and cercanos[0][0] <= RADIO_METAR_KM:
        return cercanos[0][1], round(cercanos[0][0], 1)
    return None


def metar_doc(m: metar.Metar, estacion: str, distancia: float) -> Documento:
    return {
        "estacion": estacion,
        "distancia_km": distancia,
        "hora": {"valor": m.hora.strftime("%Y-%m-%dT%H:%MZ"), "precision": "minuto"},
        "texto": m.texto,
        "visibilidad_m": m.visibilidad_m,
        "techo_ft": m.techo_ft,
        "fenomenos": m.fenomenos,
        "viento_kt": m.viento_kt,
        "racha_kt": m.racha_kt,
        "viento_dir": m.viento_dir,
    }


def elegir_metar(metares: list[metar.Metar], momento: datetime | None) -> metar.Metar | None:
    if not metares:
        return None
    if momento is None:  # solo el día: el de peor visibilidad (y, a igualdad, más viento)
        return min(
            metares,
            key=lambda m: (
                m.visibilidad_m if m.visibilidad_m is not None else 99999,
                -(m.viento_kt or 0),
            ),
        )
    cercano = min(metares, key=lambda m: abs((m.hora - momento).total_seconds()))
    return cercano if abs(cercano.hora - momento) <= MARGEN_METAR else None


def astronomia_doc(lat: float, lon: float, momento: datetime | None, dia: date) -> Documento:
    if momento is not None:
        return dict(astronomia.condiciones(lat, lon, momento))
    horas = sum(
        1
        for h in range(24)
        if astronomia.elevacion_sol(
            lat, lon, datetime(dia.year, dia.month, dia.day, h, 30, tzinfo=UTC)
        )
        > astronomia.HORIZONTE_SOL
    )
    _, fraccion = astronomia.luna(lat, lon, datetime(dia.year, dia.month, dia.day, 12, tzinfo=UTC))
    return {"horas_de_luz": float(horas), "luna_iluminada": round(fraccion, 2)}


def lugar_incidente(
    nombre: str | None,
    lat: float,
    lon: float,
    momento: datetime | None,
    dia: date,
    horario: Horario,
    metares: list[metar.Metar],
    estacion: tuple[str, float] | None,
) -> Documento:
    hora = None if momento is None else momento.hour
    superficie, niveles = meteorologia(horario, hora)
    # Los valores son los de la hora en punto que contiene el momento del incidente.
    referencia = (
        momento.replace(minute=0, second=0, microsecond=0)
        if momento is not None
        else datetime(dia.year, dia.month, dia.day, tzinfo=UTC)
    )
    documento: Documento = {
        "lat": round(lat, 4),
        "lon": round(lon, 4),
        "momento": {
            "valor": referencia.strftime("%Y-%m-%dT%H:%MZ"),
            "precision": "hora" if momento is not None else "dia",
        },
        "rango_dia": momento is None,
        "superficie": superficie,
        "niveles": niveles,
        "astronomia": astronomia_doc(lat, lon, momento, dia),
    }
    if nombre:
        documento["nombre"] = nombre
    if estacion is not None:
        elegido = elegir_metar(metares, momento)
        if elegido is not None:
            documento["metar"] = metar_doc(elegido, estacion[0], estacion[1])
    return documento


@cache
def lugares_ucrania() -> dict[str, Any]:
    datos: dict[str, Any] = json.loads(LUGARES.read_text(encoding="utf-8"))
    return datos


def punto_lanzamiento(nombre: str) -> tuple[str, float, float] | None:
    texto = " ".join(nombre.lower().split())
    for zona in lugares_ucrania()["lanzamiento"]:
        if any(r in texto for r in zona["raices"]) and not any(
            e in texto for e in zona.get("excluir", [])
        ):
            return zona["nombre"], zona["lat"], zona["lon"]
    return None


def puntos_ataque(
    ataque: Documento,
) -> tuple[list[tuple[str, float, float]], list[tuple[str, float, float]]]:
    """Puntos de lanzamiento y de impacto de un ataque RU→UA, sin repetir."""
    lanzamiento: list[tuple[str, float, float]] = []
    for nombre in ataque.get("zonas_lanzamiento") or []:
        punto = punto_lanzamiento(nombre)
        if punto is not None and punto not in lanzamiento:
            lanzamiento.append(punto)
    regiones = lugares_ucrania()["regiones"]
    impacto: list[tuple[str, float, float]] = []
    for region in ataque.get("regiones") or []:
        r = regiones.get(region.get("region"))
        punto = (r["nombre"], r["lat"], r["lon"]) if r else None
        if punto is not None and punto not in impacto:
            impacto.append(punto)
    return lanzamiento[:MAXIMO_LANZAMIENTO], impacto[:MAXIMO_IMPACTO]


def lugar_viento(
    nombre: str, lat: float, lon: float, momento: datetime, horario: Horario
) -> Documento:
    superficie, niveles = viento(horario, momento.hour)
    return {
        "nombre": nombre,
        "lat": lat,
        "lon": lon,
        "momento": {"valor": momento.strftime("%Y-%m-%dT%H:00Z"), "precision": "hora"},
        "rango_dia": False,
        "superficie": superficie,
        "niveles": niveles,
    }


PedirHorario = Callable[[list[tuple[float, float]], date, str], list[Horario | None]]
