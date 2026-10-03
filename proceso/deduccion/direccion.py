"""Dirección de entrada de los drones de un incidente: declarada por una autoridad o deducida.

- Declarada: una autoridad (nota oficial o declaración citada) dice desde qué país entró el dron
  («entered from Belarus»): la dirección es la del punto de ese país más cercano al incidente.
  Lleva el origen y la fuente de la frase.
- Deducida: con el viento medido, la zona de despegue posible de las clases de corto alcance
  compatibles (proceso/deduccion/zona_despegue.py) queda desplazada a barlovento. La dirección es
  la de la tierra de esas zonas vista desde el incidente: por sectores de 30°, la fracción de la
  tierra desde la que pudo despegar (del mar no se despega), su dirección media y su
  concentración (0, repartida por igual alrededor; 1, toda en una dirección). Sin viento medido
  la zona está centrada en el incidente y no se deduce ninguna dirección.

`desde_grados` es el acimut, desde el incidente, de donde vino el dron (0 norte, 90 este).
"""

import math
from typing import Any

from proceso.deduccion import geo, zona_despegue
from proceso.deduccion.catalogo import Catalogo

VERSION = ("direccion_entrada", "1.0.0")
SECTORES = 12
ANCHO = 360.0 / SECTORES
# Por debajo de esta concentración la tierra posible está repartida alrededor: no hay dirección.
CONCENTRACION_MINIMA = 0.2


def declarada(
    lat: float, lon: float, pais: str, origen: str, fuente: str, frase: str
) -> dict[str, Any] | None:
    punto = geo.punto_mas_cercano(pais, lat, lon)
    if punto is None:
        return None
    return {
        "regla": VERSION[0],
        "version": VERSION[1],
        "tipo": "declarada",
        "desde_grados": round(geo.rumbo(lat, lon, punto[0], punto[1]), 1),
        "pais": pais,
        "distancia_km": round(geo.distancia_km(lat, lon, punto[0], punto[1]), 1),
        "origen": origen,
        "fuente": fuente,
        "frase": frase[:300],
    }


def _sector(azimut: float) -> int:
    return int(((azimut + ANCHO / 2) % 360.0) // ANCHO)


def deducida(
    catalogo: Catalogo, lat: float, lon: float, zonas: list[dict[str, Any]]
) -> dict[str, Any] | None:
    """Con las zonas de despegue de las clases compatibles calculadas con viento medido."""
    pesos = [0.0] * SECTORES
    clases = []
    for zona in zonas:
        clase = catalogo.clases.get(zona.get("clase", ""))
        if (
            clase is None
            or not clase.corto_alcance
            or not zona.get("viento_medido")
            or not zona.get("poligono")
            or not zona.get("desplazamiento_viento_km")
        ):
            continue
        local = [geo.a_local(lat, lon, a, b) for a, b in zona["poligono"]]
        xs, ys = [p[0] for p in local], [p[1] for p in local]
        cuenta = [0] * SECTORES
        n = zona_despegue.MUESTRAS_LADO
        for i in range(n):
            for j in range(n):
                x = min(xs) + (max(xs) - min(xs)) * (i + 0.5) / n
                y = min(ys) + (max(ys) - min(ys)) * (j + 0.5) / n
                if (x == 0 and y == 0) or not zona_despegue.dentro(x, y, local):
                    continue
                plat, plon = geo.de_local(lat, lon, x, y)
                if geo.pais_en(plat, plon) is None:
                    continue
                cuenta[_sector(math.degrees(math.atan2(x, y)) % 360.0)] += 1
        total = sum(cuenta)
        if total == 0:
            continue
        clases.append(clase.id)
        for k in range(SECTORES):
            pesos[k] += cuenta[k] / total
    if not clases:
        return None
    suma = sum(pesos)
    fracciones = [p / suma for p in pesos]
    este = sum(f * math.sin(math.radians(k * ANCHO)) for k, f in enumerate(fracciones))
    norte = sum(f * math.cos(math.radians(k * ANCHO)) for k, f in enumerate(fracciones))
    concentracion = math.hypot(este, norte)
    resultado: dict[str, Any] = {
        "regla": VERSION[0],
        "version": VERSION[1],
        "tipo": "deducida",
        "origen": "deducido",
        "sectores": [round(f, 3) for f in fracciones],
        "concentracion": round(concentracion, 3),
        "clases": clases,
    }
    if concentracion >= CONCENTRACION_MINIMA:
        resultado["desde_grados"] = round(math.degrees(math.atan2(este, norte)) % 360.0, 1)
    return resultado
