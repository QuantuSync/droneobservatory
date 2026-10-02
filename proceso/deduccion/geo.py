"""Geometría para el motor de deducción: distancias sobre la esfera, rumbos, puntos de destino y
distancias a la tierra extranjera, a la costa y a las aguas internacionales con los polígonos de
Natural Earth de `configuracion/fronteras_europa.json` (escala 1:10 millones).

Las distancias a fronteras y costas son cotas inferiores, como pide una regla que descarta: se
les resta el margen de la escala de los polígonos (2,5 km, el mismo de proceso/fronteras.py) y
las aguas internacionales empiezan, como pronto, 12 millas náuticas mar adentro de la costa
más cercana.
"""

import math
from dataclasses import dataclass
from functools import cache

from proceso import fronteras

RADIO_TIERRA_KM = 6371.0088
MARGEN_POLIGONO_KM = fronteras.MARGEN_FRONTERA_KM
MAR_TERRITORIAL_KM = fronteras.MARGEN_MAR_KM
# Hasta dónde se buscan fronteras y costas alrededor de un punto.
BUSQUEDA_KM = 600.0
# Prueba de si un tramo de un polígono es frontera terrestre o costa: un punto a esta distancia
# hacia fuera del tramo cae en tierra de otro país (frontera) o no (costa).
PASO_COSTA_KM = 1.0

Punto = tuple[float, float]  # lat, lon


def distancia_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distancia de círculo máximo (haversine)."""
    f1, f2 = math.radians(lat1), math.radians(lat2)
    df, dl = f2 - f1, math.radians(lon2 - lon1)
    a = math.sin(df / 2) ** 2 + math.cos(f1) * math.cos(f2) * math.sin(dl / 2) ** 2
    return 2 * RADIO_TIERRA_KM * math.asin(min(1.0, math.sqrt(a)))


def rumbo(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Rumbo inicial de 1 a 2, en grados desde el norte (0–360)."""
    f1, f2 = math.radians(lat1), math.radians(lat2)
    dl = math.radians(lon2 - lon1)
    x = math.sin(dl) * math.cos(f2)
    y = math.cos(f1) * math.sin(f2) - math.sin(f1) * math.cos(f2) * math.cos(dl)
    return (math.degrees(math.atan2(x, y)) + 360.0) % 360.0


def destino(lat: float, lon: float, rumbo_grados: float, km: float) -> Punto:
    """Punto a `km` de (lat, lon) con ese rumbo inicial."""
    d = km / RADIO_TIERRA_KM
    f1, l1, t = math.radians(lat), math.radians(lon), math.radians(rumbo_grados)
    f2 = math.asin(math.sin(f1) * math.cos(d) + math.cos(f1) * math.sin(d) * math.cos(t))
    l2 = l1 + math.atan2(
        math.sin(t) * math.sin(d) * math.cos(f1), math.cos(d) - math.sin(f1) * math.sin(f2)
    )
    return math.degrees(f2), (math.degrees(l2) + 540.0) % 360.0 - 180.0


def diferencia_angular(a: float, b: float) -> float:
    """Diferencia entre dos rumbos, de 0 a 180 grados."""
    d = abs(a - b) % 360.0
    return 360.0 - d if d > 180.0 else d


def a_local(lat0: float, lon0: float, lat: float, lon: float) -> tuple[float, float]:
    """(este, norte) en km en una proyección azimutal equidistante centrada en (lat0, lon0)."""
    d = distancia_km(lat0, lon0, lat, lon)
    if d == 0:
        return 0.0, 0.0
    r = math.radians(rumbo(lat0, lon0, lat, lon))
    return d * math.sin(r), d * math.cos(r)


def de_local(lat0: float, lon0: float, este: float, norte: float) -> Punto:
    d = math.hypot(este, norte)
    if d == 0:
        return lat0, lon0
    return destino(lat0, lon0, math.degrees(math.atan2(este, norte)), d)


@dataclass(frozen=True)
class Tramo:
    a: tuple[float, float]  # lon, lat
    b: tuple[float, float]
    pais: str
    costa: bool


def _todos_los_poligonos() -> dict[str, tuple[fronteras.Poligono, ...]]:
    datos = fronteras.fronteras()
    return {**datos.vecinos, **datos.paises}


@cache
def _contornos(pais: str) -> tuple[tuple[fronteras.Poligono, tuple[Tramo, ...]], ...]:
    """Los polígonos del país con sus tramos (sin saber aún si son costa)."""
    resultado = []
    for poligono in _todos_los_poligonos().get(pais, ()):
        lista: list[Tramo] = []
        for anillo in poligono.anillos:
            anterior = anillo[-1]
            for actual in anillo:
                if anterior != actual:
                    lista.append(Tramo(anterior, actual, pais, False))
                anterior = actual
        resultado.append((poligono, tuple(lista)))
    return tuple(resultado)


def tramos_cerca(pais: str, lat: float, lon: float, km: float) -> list[Tramo]:
    """Los tramos del contorno del país en polígonos a menos de `km` del punto."""
    margen = km / (fronteras.KM_POR_GRADO * max(math.cos(math.radians(lat)), 0.1))
    return [
        t
        for poligono, lista in _contornos(pais)
        if poligono.cerca(lon, lat, margen)
        for t in lista
        if _cerca(lat, lon, t, km)
    ]


def tramos(pais: str) -> tuple[Tramo, ...]:
    return tuple(t for _, lista in _contornos(pais) for t in lista)


@cache
def es_costa(pais: str, a: tuple[float, float], b: tuple[float, float]) -> bool:
    return _es_costa(pais, a, b)


def _es_costa(pais: str, a: tuple[float, float], b: tuple[float, float]) -> bool:
    lon_m, lat_m = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
    direccion = rumbo(a[1], a[0], b[1], b[0])
    for lado in (90.0, -90.0):
        lat_f, lon_f = destino(lat_m, lon_m, direccion + lado, PASO_COSTA_KM)
        if en_tierra_de(pais, lat_f, lon_f):
            continue
        return not fronteras.en_tierra_de_alguien(lat_f, lon_f)
    return False


def en_tierra_de(pais: str, lat: float, lon: float) -> bool:
    return any(p.contiene(lon, lat) for p in _todos_los_poligonos().get(pais, ()))


@cache
def _indice() -> dict[tuple[int, int], tuple[tuple[str, fronteras.Poligono], ...]]:
    """Polígonos por celda de 1° (por su caja): pais_en solo mira los de su celda."""
    celdas: dict[tuple[int, int], list[tuple[str, fronteras.Poligono]]] = {}
    for pais, poligonos in _todos_los_poligonos().items():
        for poligono in poligonos:
            lon_min, lat_min, lon_max, lat_max = poligono.caja
            for x in range(math.floor(lon_min), math.floor(lon_max) + 1):
                for y in range(math.floor(lat_min), math.floor(lat_max) + 1):
                    celdas.setdefault((x, y), []).append((pais, poligono))
    return {k: tuple(v) for k, v in celdas.items()}


def pais_en(lat: float, lon: float) -> str | None:
    """El país en cuya tierra cae el punto (de los de la recogida y sus vecinos), o None (mar)."""
    for pais, poligono in _indice().get((math.floor(lon), math.floor(lat)), ()):
        if poligono.contiene(lon, lat):
            return pais
    return None


def _distancia_tramo_km(lat: float, lon: float, tramo: Tramo) -> float:
    return fronteras._distancia_segmento_km(lat, lon, tramo.a, tramo.b)


def _cerca(lat: float, lon: float, tramo: Tramo, km: float) -> bool:
    margen = km / (fronteras.KM_POR_GRADO * max(math.cos(math.radians(lat)), 0.1))
    return (
        min(tramo.a[0], tramo.b[0]) - margen <= lon <= max(tramo.a[0], tramo.b[0]) + margen
        and min(tramo.a[1], tramo.b[1]) - margen <= lat <= max(tramo.a[1], tramo.b[1]) + margen
    )


@dataclass(frozen=True)
class Exterior:
    """Cotas inferiores de lo que separa un punto de donde pudo despegar fuera del país."""

    tierra_extranjera_km: float | None
    pais_extranjero: str | None
    costa_km: float | None
    aguas_internacionales_km: float | None

    @property
    def fuera_km(self) -> float | None:
        """Lo más cerca que empieza el exterior (tierra de otro país o aguas internacionales)."""
        valores = [
            v for v in (self.tierra_extranjera_km, self.aguas_internacionales_km) if v is not None
        ]
        return min(valores) if valores else None

    def documento(self) -> dict[str, float | str | None]:
        return {
            "tierra_extranjera_km": _redondo(self.tierra_extranjera_km),
            "pais_extranjero": self.pais_extranjero,
            "costa_km": _redondo(self.costa_km),
            "aguas_internacionales_km": _redondo(self.aguas_internacionales_km),
        }


def _redondo(valor: float | None) -> float | None:
    return None if valor is None else round(valor, 1)


def exterior(pais: str, lat: float, lon: float, hasta_km: float = BUSQUEDA_KM) -> Exterior:
    """Distancias (cotas inferiores) a la tierra de otro país, a la costa del país y a las aguas
    internacionales. None si no hay ninguna a menos de `hasta_km`."""
    mejor_tierra, pais_tierra = None, None
    for otro in _todos_los_poligonos():
        if otro == pais:
            continue
        for tramo in tramos_cerca(otro, lat, lon, hasta_km):
            d = _distancia_tramo_km(lat, lon, tramo)
            if d <= hasta_km and (mejor_tierra is None or d < mejor_tierra):
                mejor_tierra, pais_tierra = d, otro
    costa = None
    cercanos = sorted(
        ((_distancia_tramo_km(lat, lon, t), t) for t in tramos_cerca(pais, lat, lon, hasta_km)),
        key=lambda x: x[0],
    )
    # El tramo de costa más cercano: se miran por orden de distancia y se para en el primero.
    for d, tramo in cercanos:
        if d > hasta_km:
            break
        if es_costa(pais, tramo.a, tramo.b):
            costa = d
            break
    tierra = None if mejor_tierra is None else max(0.0, mejor_tierra - MARGEN_POLIGONO_KM)
    costa_inf = None if costa is None else max(0.0, costa - MARGEN_POLIGONO_KM)
    aguas = None if costa_inf is None else costa_inf + MAR_TERRITORIAL_KM
    return Exterior(tierra, pais_tierra, costa_inf, aguas)


def distancia_a_pais_km(pais: str, lat: float, lon: float, hasta_km: float = 3000.0) -> float:
    """Distancia del punto a la tierra del país (0 dentro), cota inferior con el margen de la
    escala de los polígonos."""
    if en_tierra_de(pais, lat, lon):
        return 0.0
    mejor = hasta_km
    for _, lista in _contornos(pais):
        for tramo in lista:
            mejor = min(mejor, _distancia_tramo_km(lat, lon, tramo))
    return max(0.0, mejor - MARGEN_POLIGONO_KM)


def punto_mas_cercano(pais: str, lat: float, lon: float) -> Punto | None:
    """El punto del contorno del país más cercano a (lat, lon)."""
    mejor, punto = math.inf, None
    for tramo in tramos(pais):
        d = _distancia_tramo_km(lat, lon, tramo)
        if d < mejor:
            mejor = d
            punto = _proyeccion(lat, lon, tramo)
    return punto


def _proyeccion(lat: float, lon: float, tramo: Tramo) -> Punto:
    escala = math.cos(math.radians(lat))
    ax, ay = (tramo.a[0] - lon) * escala, tramo.a[1] - lat
    bx, by = (tramo.b[0] - lon) * escala, tramo.b[1] - lat
    dx, dy = bx - ax, by - ay
    largo = dx * dx + dy * dy
    t = 0.0 if largo == 0 else max(0.0, min(1.0, -(ax * dx + ay * dy) / largo))
    return lat + ay + t * dy, lon + (ax + t * dx) / escala
