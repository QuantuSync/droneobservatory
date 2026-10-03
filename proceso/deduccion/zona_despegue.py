"""Zona de despegue posible de cada clase compatible con un incidente.

Triángulo de velocidades sobre el viento medido: un dron con velocidad propia V (su máxima) y
tiempo de vuelo t, con el aire moviéndose a W, avanza sobre el suelo t·(V·u + W) para un rumbo
u cualquiera. Los puntos desde los que llega al incidente P en un tiempo t forman el círculo de
centro P − t·W y radio t·V; la unión para t entre 0 y T (su tiempo máximo, limitado por su
alcance en aire en calma: V·T no pasa del alcance) es la envolvente convexa de P y del círculo
de t = T, porque los círculos intermedios son homotéticos desde P. Es una cota superior: la
zona real es menor (el dron no vuela todo el tiempo a la máxima ni en línea recta).

El polígono se simplifica a 24 vértices y se cruza con tierra y mar por muestreo: una rejilla de
puntos dentro del polígono, cada uno clasificado con los polígonos de Natural Earth (tierra del
país del incidente, de otro país o mar). Las fracciones son de área.
"""

import math
from dataclasses import dataclass
from typing import Any

from proceso.deduccion import capacidades, geo
from proceso.deduccion.catalogo import Catalogo

VERSION = ("zona_despegue", "1.0.0")
VERTICES_CIRCULO = 24
MUESTRAS_LADO = 24
# Por encima de este radio la zona no dice nada útil de un incidente concreto: se da el radio y
# no se calcula el polígono (drones de largo alcance).
RADIO_MAXIMO_KM = 400.0


@dataclass(frozen=True)
class Zona:
    clase: str
    poligono: list[tuple[float, float]]  # lat, lon
    radio_km: float
    desplazamiento_km: float
    fracciones: dict[str, float]
    paises: dict[str, float]

    def documento(self) -> dict[str, Any]:
        return {
            "clase": self.clase,
            "poligono": [[round(a, 4), round(b, 4)] for a, b in self.poligono],
            "radio_km": round(self.radio_km, 1),
            "desplazamiento_viento_km": round(self.desplazamiento_km, 1),
            "fracciones": {k: round(v, 3) for k, v in self.fracciones.items()},
            "paises": {k: round(v, 3) for k, v in sorted(self.paises.items())},
        }


def _envolvente(puntos: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """Envolvente convexa (cadena monótona), en coordenadas planas."""
    lista = sorted(set(puntos))
    if len(lista) <= 2:
        return lista

    def giro(o: tuple[float, float], a: tuple[float, float], b: tuple[float, float]) -> float:
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    abajo: list[tuple[float, float]] = []
    for p in lista:
        while len(abajo) >= 2 and giro(abajo[-2], abajo[-1], p) <= 0:
            abajo.pop()
        abajo.append(p)
    arriba: list[tuple[float, float]] = []
    for p in reversed(lista):
        while len(arriba) >= 2 and giro(arriba[-2], arriba[-1], p) <= 0:
            arriba.pop()
        arriba.append(p)
    return abajo[:-1] + arriba[:-1]


def dentro(x: float, y: float, poligono: list[tuple[float, float]]) -> bool:
    dentro = False
    anterior = poligono[-1]
    for actual in poligono:
        (x1, y1), (x2, y2) = anterior, actual
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            dentro = not dentro
        anterior = actual
    return dentro


def poligono_local(
    velocidad_ms: float, tiempo_min: float, viento: tuple[float, float]
) -> list[tuple[float, float]]:
    """Polígono (este, norte) en km respecto al incidente."""
    t_h = tiempo_min / 60.0
    radio = velocidad_ms * 3.6 * t_h
    centro = (-viento[0] * 3.6 * t_h, -viento[1] * 3.6 * t_h)
    circulo = [
        (
            centro[0] + radio * math.sin(2 * math.pi * i / VERTICES_CIRCULO),
            centro[1] + radio * math.cos(2 * math.pi * i / VERTICES_CIRCULO),
        )
        for i in range(VERTICES_CIRCULO)
    ]
    return _envolvente([(0.0, 0.0), *circulo])


def calcular(
    catalogo: Catalogo,
    clase: str,
    pais: str,
    lat: float,
    lon: float,
    viento_ms: tuple[float, float],
) -> Zona | dict[str, Any] | None:
    """La zona de una clase, o un documento con el motivo si no se calcula, o None sin datos."""
    velocidad = capacidades.de_clase(catalogo, clase, capacidades.velocidad_max_ms)
    tiempo = capacidades.de_clase(catalogo, clase, capacidades.tiempo_max_min)
    alcance = capacidades.de_clase(catalogo, clase, capacidades.alcance_aire_km)
    # La zona es una cota superior: hace falta la de todos los modelos de la clase.
    if not velocidad.sirve or not tiempo.sirve or velocidad.valor is None or tiempo.valor is None:
        return None
    t = tiempo.valor
    if alcance.sirve and alcance.valor is not None and velocidad.valor > 0:
        t = min(t, alcance.valor * 1000.0 / velocidad.valor / 60.0)
    radio = velocidad.valor * 3.6 * t / 60.0
    if radio > RADIO_MAXIMO_KM:
        return {"clase": clase, "radio_km": round(radio, 1), "motivo": "radio_demasiado_grande"}
    local = poligono_local(velocidad.valor, t, viento_ms)
    poligono = [geo.de_local(lat, lon, x, y) for x, y in local]
    fracciones, paises = _cruzar(local, lat, lon, pais)
    desplazamiento = math.hypot(*viento_ms) * 3.6 * t / 60.0
    return Zona(clase, poligono, radio, desplazamiento, fracciones, paises)


def _cruzar(
    local: list[tuple[float, float]], lat: float, lon: float, pais: str
) -> tuple[dict[str, float], dict[str, float]]:
    xs = [p[0] for p in local]
    ys = [p[1] for p in local]
    cuentas: dict[str, int] = {"pais": 0, "otros_paises": 0, "mar": 0}
    por_pais: dict[str, int] = {}
    total = 0
    for i in range(MUESTRAS_LADO):
        for j in range(MUESTRAS_LADO):
            x = min(xs) + (max(xs) - min(xs)) * (i + 0.5) / MUESTRAS_LADO
            y = min(ys) + (max(ys) - min(ys)) * (j + 0.5) / MUESTRAS_LADO
            if not dentro(x, y, local):
                continue
            total += 1
            plat, plon = geo.de_local(lat, lon, x, y)
            donde = geo.pais_en(plat, plon)
            if donde is None:
                cuentas["mar"] += 1
            elif donde == pais:
                cuentas["pais"] += 1
            else:
                cuentas["otros_paises"] += 1
                por_pais[donde] = por_pais.get(donde, 0) + 1
    if total == 0:
        return {}, {}
    return ({k: v / total for k, v in cuentas.items()}, {k: v / total for k, v in por_pais.items()})
