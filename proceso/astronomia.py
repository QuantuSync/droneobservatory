"""Sol y luna en un lugar y una hora, calculados en local sin servicios externos.

- **Sol**: posición con las fórmulas de la NOAA (Solar Calculator, a partir de Meeus,
  «Astronomical Algorithms»), con un error de unas centésimas de grado: elevación sobre el
  horizonte sin refracción y luz: día con el sol por encima de −0,833° (el borde superior del
  disco con la refracción media), crepúsculo hasta −12° (civil y náutico, cuando aún se
  distinguen siluetas contra el cielo) y noche por debajo.
- **Luna**: posición con la teoría abreviada de Meeus (capítulo 47, términos principales),
  con un error de unas décimas de grado, más que suficiente para saber si estaba sobre el
  horizonte, y fracción iluminada por el ángulo de fase (capítulo 48).
"""

import math
from datetime import UTC, datetime

GRADO = math.pi / 180
HORIZONTE_SOL = -0.833
CREPUSCULO = -12.0


def _dia_juliano(momento: datetime) -> float:
    return momento.astimezone(UTC).timestamp() / 86400.0 + 2440587.5


def _siglos(momento: datetime) -> float:
    return (_dia_juliano(momento) - 2451545.0) / 36525.0


def _oblicuidad(t: float) -> float:
    segundos = 21.448 - t * (46.815 + t * (0.00059 - t * 0.001813))
    media = 23.0 + (26.0 + segundos / 60.0) / 60.0
    return media + 0.00256 * math.cos((125.04 - 1934.136 * t) * GRADO)


def _sideral_local(momento: datetime, lon: float) -> float:
    """Tiempo sideral local en grados."""
    d = _dia_juliano(momento) - 2451545.0
    t = d / 36525.0
    gmst = 280.46061837 + 360.98564736629 * d + 0.000387933 * t * t - t**3 / 38710000.0
    return (gmst + lon) % 360.0


def _altura(ar: float, dec: float, lat: float, lon: float, momento: datetime) -> float:
    """Altura sobre el horizonte (grados) de un astro de ascensión recta y declinación dadas."""
    horario = (_sideral_local(momento, lon) - ar) * GRADO
    seno = math.sin(lat * GRADO) * math.sin(dec * GRADO) + math.cos(lat * GRADO) * math.cos(
        dec * GRADO
    ) * math.cos(horario)
    return math.asin(max(-1.0, min(1.0, seno))) / GRADO


def _ecuatoriales(longitud: float, latitud: float, oblicuidad: float) -> tuple[float, float]:
    lam, beta, eps = longitud * GRADO, latitud * GRADO, oblicuidad * GRADO
    ar = math.atan2(math.sin(lam) * math.cos(eps) - math.tan(beta) * math.sin(eps), math.cos(lam))
    dec = math.asin(math.sin(beta) * math.cos(eps) + math.cos(beta) * math.sin(eps) * math.sin(lam))
    return (ar / GRADO) % 360.0, dec / GRADO


def longitud_sol(t: float) -> float:
    """Longitud eclíptica aparente del sol (grados)."""
    media = (280.46646 + t * (36000.76983 + 0.0003032 * t)) % 360.0
    anomalia = (357.52911 + t * (35999.05029 - 0.0001537 * t)) * GRADO
    centro = (
        math.sin(anomalia) * (1.914602 - t * (0.004817 + 0.000014 * t))
        + math.sin(2 * anomalia) * (0.019993 - 0.000101 * t)
        + math.sin(3 * anomalia) * 0.000289
    )
    return media + centro - 0.00569 - 0.00478 * math.sin((125.04 - 1934.136 * t) * GRADO)


def elevacion_sol(lat: float, lon: float, momento: datetime) -> float:
    t = _siglos(momento)
    ar, dec = _ecuatoriales(longitud_sol(t), 0.0, _oblicuidad(t))
    return _altura(ar, dec, lat, lon, momento)


def luz(elevacion: float) -> str:
    if elevacion > HORIZONTE_SOL:
        return "dia"
    return "crepusculo" if elevacion >= CREPUSCULO else "noche"


def _luna_ecliptica(t: float) -> tuple[float, float]:
    """Longitud y latitud eclípticas geocéntricas de la luna (grados), términos principales."""
    lp = 218.3164477 + 481267.88123421 * t
    d = (297.8501921 + 445267.1114034 * t) * GRADO
    m = (357.5291092 + 35999.0502909 * t) * GRADO
    mp = (134.9633964 + 477198.8675055 * t) * GRADO
    f = (93.2720950 + 483202.0175233 * t) * GRADO
    longitud = lp + (
        6.288774 * math.sin(mp)
        + 1.274027 * math.sin(2 * d - mp)
        + 0.658314 * math.sin(2 * d)
        + 0.213618 * math.sin(2 * mp)
        - 0.185116 * math.sin(m)
        - 0.114332 * math.sin(2 * f)
        + 0.058793 * math.sin(2 * d - 2 * mp)
        + 0.057066 * math.sin(2 * d - m - mp)
        + 0.053322 * math.sin(2 * d + mp)
        + 0.045758 * math.sin(2 * d - m)
        - 0.040923 * math.sin(m - mp)
        - 0.034720 * math.sin(d)
        - 0.030383 * math.sin(m + mp)
    )
    latitud = (
        5.128122 * math.sin(f)
        + 0.280602 * math.sin(mp + f)
        + 0.277693 * math.sin(mp - f)
        + 0.173237 * math.sin(2 * d - f)
        + 0.055413 * math.sin(2 * d - mp + f)
        + 0.046271 * math.sin(2 * d - mp - f)
    )
    return longitud % 360.0, latitud


def luna(lat: float, lon: float, momento: datetime) -> tuple[float, float]:
    """Altura de la luna sobre el horizonte (grados, geocéntrica) y fracción iluminada (0-1)."""
    t = _siglos(momento)
    longitud, latitud = _luna_ecliptica(t)
    ar, dec = _ecuatoriales(longitud, latitud, _oblicuidad(t))
    altura = _altura(ar, dec, lat, lon, momento)
    # Elongación respecto del sol y ángulo de fase (luna a 385 000 km, sol a 1 UA).
    sol = longitud_sol(t) * GRADO
    elong = math.acos(math.cos(latitud * GRADO) * math.cos(longitud * GRADO - sol))
    fase = math.atan2(149597870.0 * math.sin(elong), 385000.0 - 149597870.0 * math.cos(elong))
    return altura, (1 + math.cos(fase)) / 2


def condiciones(lat: float, lon: float, momento: datetime) -> dict[str, object]:
    elevacion = elevacion_sol(lat, lon, momento)
    altura_luna, fraccion = luna(lat, lon, momento)
    return {
        "elevacion_sol": round(elevacion, 1),
        "luz": luz(elevacion),
        "altura_luna": round(altura_luna, 1),
        "luna_iluminada": round(fraccion, 2),
    }
