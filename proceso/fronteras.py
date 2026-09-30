"""Si un punto cae dentro del país del incidente, con las fronteras de Natural Earth.

Un punto vale si está dentro de algún polígono del país. Fuera de él, dos márgenes
por la escala de los polígonos (1:10 millones), medidos sobre las 20 174
instalaciones del nomenclátor, de las que 751 caen fuera del polígono de su país:

- en el mar, hasta 12 millas náuticas de la costa del país (su mar territorial):
  puertos, aeropuertos ganados al mar y plataformas;
- en tierra de otro país, hasta 2,5 km de la frontera: presas de ríos fronterizos
  y pasos de frontera. De las 164 instalaciones que caen en tierra de otro país,
  113 están a menos de 2,5 km y solo 6 más entre 2,5 y 5 km; las demás, a decenas o
  cientos de km, son errores del nomenclátor (una central rusa marcada como
  finlandesa) o territorios de ultramar.

Un punto más lejos no vale nunca.

Los polígonos salen de `configuracion/fronteras_europa.json`, generado con
`python -m recogida.fronteras_natural_earth`.
"""

import json
import math
from dataclasses import dataclass
from functools import cache
from pathlib import Path

DIRECTORIO = Path(__file__).resolve().parent.parent / "configuracion"
# Mar territorial (Convención de las Naciones Unidas sobre el Derecho del Mar): 12 millas
# náuticas de 1,852 km.
MILLAS_MAR_TERRITORIAL = 12
KM_POR_MILLA = 1.852
MARGEN_MAR_KM = MILLAS_MAR_TERRITORIAL * KM_POR_MILLA
# Tierra de otro país junto a la frontera (medida en la cabecera).
MARGEN_FRONTERA_KM = 2.5
KM_POR_GRADO = 111.2

Anillo = tuple[tuple[float, float], ...]


@dataclass(frozen=True)
class Poligono:
    # lon mínima, lat mínima, lon máxima, lat máxima.
    caja: tuple[float, float, float, float]
    # El primero es el exterior; los demás, huecos.
    anillos: tuple[Anillo, ...]

    def cerca(self, lon: float, lat: float, margen: float = 0.0) -> bool:
        lon_min, lat_min, lon_max, lat_max = self.caja
        return (
            lon_min - margen <= lon <= lon_max + margen
            and lat_min - margen <= lat <= lat_max + margen
        )

    def contiene(self, lon: float, lat: float) -> bool:
        if not self.cerca(lon, lat):
            return False
        exterior, *huecos = self.anillos
        return _en_anillo(lon, lat, exterior) and not any(_en_anillo(lon, lat, h) for h in huecos)


def _en_anillo(lon: float, lat: float, anillo: Anillo) -> bool:
    """Regla de la semirrecta: cuántas aristas cruza una semirrecta hacia el este."""
    dentro = False
    anterior = anillo[-1]
    for actual in anillo:
        (x1, y1), (x2, y2) = anterior, actual
        if (y1 > lat) != (y2 > lat) and lon < (x2 - x1) * (lat - y1) / (y2 - y1) + x1:
            dentro = not dentro
        anterior = actual
    return dentro


def _poligono(crudo: list[list[list[float]]]) -> Poligono:
    anillos = tuple(tuple((x, y) for x, y in anillo) for anillo in crudo)
    xs = [x for x, _ in anillos[0]]
    ys = [y for _, y in anillos[0]]
    return Poligono((min(xs), min(ys), max(xs), max(ys)), anillos)


@dataclass(frozen=True)
class Fronteras:
    paises: dict[str, tuple[Poligono, ...]]
    vecinos: dict[str, tuple[Poligono, ...]]
    nombres_paises: frozenset[str]
    nombres_por_pais: dict[str, tuple[str, ...]]


@cache
def fronteras(ruta: Path = DIRECTORIO / "fronteras_europa.json") -> Fronteras:
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    return Fronteras(
        paises={p: tuple(_poligono(c) for c in v) for p, v in datos["paises"].items()},
        vecinos={p: tuple(_poligono(c) for c in v) for p, v in datos["vecinos"].items()},
        nombres_paises=frozenset(datos["nombres_paises"]),
        # El generador lee el fichero anterior, que puede no traerlos todavía.
        nombres_por_pais={p: tuple(n) for p, n in datos.get("nombres_por_pais", {}).items()},
    )


def paises() -> frozenset[str]:
    return frozenset(fronteras().paises)


def en_tierra(pais: str, lat: float, lon: float) -> bool:
    return any(p.contiene(lon, lat) for p in fronteras().paises.get(pais, ()))


def en_tierra_de_alguien(lat: float, lon: float) -> bool:
    datos = fronteras()
    return any(
        p.contiene(lon, lat) for grupo in (datos.paises, datos.vecinos) for pais in grupo.values()
        for p in pais
    )  # fmt: skip


def _distancia_segmento_km(
    lat: float, lon: float, a: tuple[float, float], b: tuple[float, float]
) -> float:
    """Distancia a un segmento en una proyección local (equirrectangular): basta a pocos km."""
    escala = math.cos(math.radians(lat))
    ax, ay = (a[0] - lon) * escala, a[1] - lat
    bx, by = (b[0] - lon) * escala, b[1] - lat
    dx, dy = bx - ax, by - ay
    largo = dx * dx + dy * dy
    t = 0.0 if largo == 0 else max(0.0, min(1.0, -(ax * dx + ay * dy) / largo))
    return math.hypot(ax + t * dx, ay + t * dy) * KM_POR_GRADO


def distancia_borde_km(pais: str, lat: float, lon: float, hasta_km: float) -> float:
    """Distancia al borde del país, o `hasta_km` si está más lejos (solo mira hasta ahí)."""
    margen = hasta_km / (KM_POR_GRADO * max(math.cos(math.radians(lat)), 0.1))
    mejor = hasta_km
    for poligono in fronteras().paises.get(pais, ()):
        if not poligono.cerca(lon, lat, margen):
            continue
        for anillo in poligono.anillos:
            anterior = anillo[-1]
            for actual in anillo:
                mejor = min(mejor, _distancia_segmento_km(lat, lon, anterior, actual))
                anterior = actual
    return mejor


def dentro_del_pais(pais: str, lat: float, lon: float) -> bool:
    """En tierra del país, en su mar territorial o en el margen de su frontera."""
    if en_tierra(pais, lat, lon):
        return True
    if pais not in fronteras().paises:
        return False
    margen = MARGEN_FRONTERA_KM if en_tierra_de_alguien(lat, lon) else MARGEN_MAR_KM
    return distancia_borde_km(pais, lat, lon, margen) < margen


def es_nombre_de_pais(normal: str) -> bool:
    """El texto normalizado es el nombre de un país en algún idioma («ukraine», «moldova»)."""
    return normal in fronteras().nombres_paises


def nombres_del_pais(pais: str) -> tuple[str, ...]:
    """Los nombres normalizados del país en los idiomas de Natural Earth."""
    return fronteras().nombres_por_pais.get(pais, ())
