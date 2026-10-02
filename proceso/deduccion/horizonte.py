"""Horizonte de radar y línea de visión con el relieve (Copernicus DEM).

Para un radar en el aeropuerto o la instalación afectada, por sectores de 10°, la altura sobre
el terreno por debajo de la cual un dron queda oculto a una distancia dada: tapado por el
relieve que hay entre el radar y él o por debajo del horizonte de la Tierra.

- Refracción normal: radio terrestre efectivo de 4/3 del real (8495 km), el modelo habitual de
  propagación de radar.
- El radar está en el punto del lugar, con la antena a ALTURA_ANTENA_M sobre el suelo. Es un
  supuesto del motor (no hay datos públicos de la altura de cada antena): el resultado lo lleva.
- Perfil cada PASO_M metros hasta ALCANCE_KM; el ángulo de elevación del horizonte en cada
  distancia es el mayor de los del relieve más cercano. Un dron a altitud h y distancia d se
  ve si su ángulo supera ese horizonte.
- Las elevaciones del DEM son de superficie (incluyen edificios y árboles en parte): el
  resultado es el de esa superficie.
"""

import math
from collections.abc import Callable
from typing import Any

from proceso.deduccion import geo

VERSION = ("horizonte_radar", "1.0.0")
RADIO_EFECTIVO_KM = geo.RADIO_TIERRA_KM * 4.0 / 3.0
ALTURA_ANTENA_M = 15.0
SECTORES = 36
PASO_M = 250.0
ALCANCE_KM = 30.0
DISTANCIAS_KM = (1.0, 2.0, 5.0, 10.0, 20.0, 30.0)

Elevacion = Callable[[float, float], float | None]


def caida_m(distancia_m: float) -> float:
    """Lo que baja la superficie de la Tierra (con refracción) a esa distancia."""
    return distancia_m * distancia_m / (2.0 * RADIO_EFECTIVO_KM * 1000.0)


def perfil_sector(
    elevacion: Elevacion, lat: float, lon: float, azimut: float, suelo_radar: float
) -> list[dict[str, float]] | None:
    """Altura de ocultación sobre el terreno en cada distancia de DISTANCIAS_KM, o None si falta
    relieve en el camino."""
    antena = suelo_radar + ALTURA_ANTENA_M
    horizonte = -math.inf
    resultado = []
    objetivos = list(DISTANCIAS_KM)
    pasos = int(ALCANCE_KM * 1000.0 / PASO_M)
    for i in range(1, pasos + 1):
        d = i * PASO_M
        plat, plon = geo.destino(lat, lon, azimut, d / 1000.0)
        z = elevacion(plat, plon)
        if z is None:
            return None
        cota = z - caida_m(d) - antena
        if objetivos and d >= objetivos[0] * 1000.0 - 1e-6:
            # Altitud (sobre el nivel del mar) por debajo de la cual queda oculto.
            oculta = (
                antena + caida_m(d) + d * math.tan(horizonte)
                if horizonte > -math.inf
                else -math.inf
            )
            sobre_terreno = max(0.0, oculta - z) if oculta > -math.inf else 0.0
            resultado.append(
                {"distancia_km": objetivos.pop(0), "oculto_bajo_m": round(sobre_terreno, 1)}
            )
        horizonte = max(horizonte, math.atan2(cota, d))
    return resultado


def calcular(elevacion: Elevacion, lat: float, lon: float) -> dict[str, Any] | None:
    """Horizonte del radar del lugar por sectores. None si no hay relieve del punto."""
    suelo = elevacion(lat, lon)
    if suelo is None:
        return None
    sectores = []
    for s in range(SECTORES):
        azimut = s * 360.0 / SECTORES
        perfil = perfil_sector(elevacion, lat, lon, azimut, suelo)
        sectores.append({"azimut": azimut, "perfil": perfil})
    con_datos = [x for x in sectores if x["perfil"] is not None]
    if not con_datos:
        return None
    return {
        "regla": VERSION[0],
        "version": VERSION[1],
        "antena_sobre_suelo_m": ALTURA_ANTENA_M,
        "antena_supuesta": True,
        "suelo_radar_m": round(suelo, 1),
        "radio_efectivo_km": round(RADIO_EFECTIVO_KM, 1),
        "sectores": sectores,
    }
