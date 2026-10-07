"""Geometría de las franjas de ruta: un tramo es un segmento entre dos zonas con radio, y la
franja es el conjunto de puntos a menos del radio (interpolado a lo largo del tramo) del segmento.
Distancias en km sobre una proyección local equirrectangular (errores de menos del 1 % a la
escala de Ucrania)."""

import math
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

RADIO_TIERRA_KM = 6371.0


def distancia_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * RADIO_TIERRA_KM * math.asin(min(1.0, math.sqrt(a)))


def rumbo(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dl = math.radians(lon2 - lon1)
    x = math.sin(dl) * math.cos(p2)
    y = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dl)
    return (math.degrees(math.atan2(x, y)) + 360.0) % 360.0


def diferencia_angular(a: float, b: float) -> float:
    d = abs(a - b) % 360.0
    return min(d, 360.0 - d)


@dataclass(frozen=True)
class Tramo:
    lat1: float
    lon1: float
    radio1: float
    lat2: float
    lon2: float
    radio2: float

    def contiene(self, lat: float, lon: float) -> bool:
        return self.distancia(lat, lon) <= 0.0

    def distancia(self, lat: float, lon: float) -> float:
        """Distancia del punto al borde de la franja (negativa dentro)."""
        lat0 = math.radians((self.lat1 + self.lat2 + lat) / 3)
        kx = 111.32 * math.cos(lat0)
        ky = 110.57
        ax, ay = self.lon1 * kx, self.lat1 * ky
        bx, by = self.lon2 * kx, self.lat2 * ky
        px, py = lon * kx, lat * ky
        dx, dy = bx - ax, by - ay
        largo2 = dx * dx + dy * dy
        t = 0.0 if largo2 == 0 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / largo2))
        cx, cy = ax + t * dx, ay + t * dy
        radio = self.radio1 + t * (self.radio2 - self.radio1)
        return math.hypot(px - cx, py - cy) - radio


def dentro(tramos: Sequence[Tramo], lat: float, lon: float) -> bool:
    return any(t.contiene(lat, lon) for t in tramos)


# Rejilla para medir áreas: Ucrania y su entorno, cada 0,1°.
CAJA = (43.5, 21.5, 53.5, 41.0)
PASO = 0.1


def area_km2(tramos: Sequence[Tramo], caja: tuple[float, float, float, float] = CAJA) -> float:
    """Área de la unión de las franjas, contando celdas de la rejilla."""
    if not tramos:
        return 0.0
    sur, oeste, norte, este = caja
    total = 0.0
    lat = sur + PASO / 2
    while lat < norte:
        celda = (PASO * 110.57) * (PASO * 111.32 * math.cos(math.radians(lat)))
        lon = oeste + PASO / 2
        cerca = [
            t
            for t in tramos
            if min(t.lat1, t.lat2) - (max(t.radio1, t.radio2) / 110.0) - PASO
            <= lat
            <= max(t.lat1, t.lat2) + (max(t.radio1, t.radio2) / 110.0) + PASO
        ]
        if cerca:
            while lon < este:
                if dentro(cerca, lat, lon):
                    total += celda
                lon += PASO
        lat += PASO
    return total


def con_anchura(lineas: Iterable[tuple[float, float, float, float]], radio: float) -> list[Tramo]:
    return [Tramo(a, b, radio, c, d, radio) for a, b, c, d in lineas]


def poligono(tramo: Tramo, lados: int = 12) -> list[tuple[float, float]]:
    """Contorno (lon, lat) de la franja de un tramo: los dos círculos y sus tangentes, como la
    envolvente convexa de los dos círculos muestreados."""
    puntos = []
    for lat, lon, radio in (
        (tramo.lat1, tramo.lon1, tramo.radio1),
        (tramo.lat2, tramo.lon2, tramo.radio2),
    ):
        for i in range(lados):
            angulo = 2 * math.pi * i / lados
            dlat = radio * math.cos(angulo) / 110.57
            dlon = radio * math.sin(angulo) / (111.32 * math.cos(math.radians(lat)))
            puntos.append((round(lon + dlon, 4), round(lat + dlat, 4)))
    return _envolvente(puntos)


def _envolvente(puntos: list[tuple[float, float]]) -> list[tuple[float, float]]:
    unicos = sorted(set(puntos))
    if len(unicos) <= 2:
        return unicos

    def cruz(o: tuple[float, float], a: tuple[float, float], b: tuple[float, float]) -> float:
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    abajo: list[tuple[float, float]] = []
    for p in unicos:
        while len(abajo) >= 2 and cruz(abajo[-2], abajo[-1], p) <= 0:
            abajo.pop()
        abajo.append(p)
    arriba: list[tuple[float, float]] = []
    for p in reversed(unicos):
        while len(arriba) >= 2 and cruz(arriba[-2], arriba[-1], p) <= 0:
            arriba.pop()
        arriba.append(p)
    contorno = abajo[:-1] + arriba[:-1]
    return [*contorno, contorno[0]]
