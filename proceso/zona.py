"""Frontera o interior: en qué grupo cae cada incidente europeo y por qué.

Son dos fenómenos distintos que el mapa enseñaba mezclados:

- **frontera**: drones de la guerra que cruzan o caen cerca de la frontera con Ucrania, Rusia
  (también Kaliningrado) o Bielorrusia, o en la costa del mar Negro;
- **interior**: drones sobre aeropuertos, bases e instalaciones del interior de Europa.

El criterio sale de los datos publicados el 6 de octubre de 2026 (docs/informe_prevision.md):
de los 322 incidentes con punto, 97 están a menos de 50 km de esa frontera, los demás de la
banda llegan hasta 144 km (incursiones de Polonia, Rumanía y Lituania) y el siguiente está a
191 km (el aeropuerto de Bucarest, cerrado por un dron sin relación con un ataque). El corte
va en ese hueco: 150 km. En la costa del mar Negro, 50 km (el puerto de Constanza está en la
costa; el siguiente punto, el aeropuerto de Sofía, a más de 200 km del mar).

En orden, la primera regla que se cumple:

1. enlazado con el ataque ruso contra Ucrania de esa noche (proceso/cruces.py): frontera;
2. con punto: frontera si está a 150 km o menos de la frontera terrestre con Ucrania, Rusia o
   Bielorrusia, o a 50 km o menos de la costa del mar Negro; si no, interior;
3. sin punto, con un lugar del nomenclátor de su país en su localidad, su región o su titular:
   la misma distancia desde ese lugar; un titular que lo sitúa en el mar Negro, frontera;
4. sin punto ni lugar: frontera si el dron entró desde fuera (incursión, entrada desde el
   exterior o dron de un Estado) en un país que tiene frontera con Ucrania, Rusia o
   Bielorrusia o costa en el mar Negro, o si el país entero cae
   dentro de la banda (Moldavia); si no, interior.

Se recalcula entero en cada recogida horaria, después de los cruces, y solo se guarda lo que
cambia, con su motivo en el historial.
"""

import copy
import json
import re
import unicodedata
from collections.abc import Iterable
from datetime import datetime
from functools import cache
from pathlib import Path
from typing import TYPE_CHECKING, Any

from esquema import Documento
from proceso.deduccion import geo

if TYPE_CHECKING:
    from almacen.base import Almacen

VERSION = "zona-1.0.0"
FRONTERA = "frontera"
INTERIOR = "interior"
GRUPOS = (FRONTERA, INTERIOR)
# Países del otro lado: Ucrania, Rusia (con Kaliningrado) y Bielorrusia.
LADO_DE_LA_GUERRA = ("UA", "RU", "BY")
BANDA_FRONTERA_KM = 150.0
BANDA_MAR_NEGRO_KM = 50.0
# Caja del mar Negro (sin el de Azov ni el Mármara): los tramos de costa dentro de ella.
CAJA_MAR_NEGRO = (27.3, 40.8, 41.9, 46.7)
PAISES_COSTA_MAR_NEGRO = ("RO", "BG", "TR", "UA", "RU", "GE")
# Un titular que sitúa el suceso en el mar Negro, sin lugar del nomenclátor.
MAR_NEGRO = re.compile(r"mar negro|black sea|marea neagr", re.IGNORECASE)
# Motivos, en el orden de las reglas. La web los dice con palabras (es/en).
MOTIVOS = (
    "ataque",
    "cerca_de_la_frontera",
    "costa_mar_negro",
    "lejos_de_la_frontera",
    "incursion_en_pais_fronterizo",
    "pais_dentro_de_la_banda",
    "sin_lugar",
)
MOTIVO_HISTORIAL = (
    "grupo frontera o interior recalculado (proceso/zona.py): distancia a la frontera con "
    "Ucrania, Rusia y Bielorrusia y a la costa del mar Negro, y enlace con el ataque de su noche"
)
CONFIGURACION = Path(__file__).resolve().parent.parent / "configuracion"
LUGARES = CONFIGURACION / "lugares_europa.json"
LOCALIDADES = CONFIGURACION / "localidades_europa.json"
EQUIVALENTES = CONFIGURACION / "nombres_equivalentes.json"


def _plano(texto: str) -> str:
    sin_tildes = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in sin_tildes if not unicodedata.combining(c)).casefold()


def _caja(punto: tuple[float, float]) -> bool:
    lon_min, lat_min, lon_max, lat_max = CAJA_MAR_NEGRO
    return lon_min <= punto[0] <= lon_max and lat_min <= punto[1] <= lat_max


@cache
def _costa_mar_negro() -> tuple[geo.Tramo, ...]:
    return tuple(
        t
        for pais in PAISES_COSTA_MAR_NEGRO
        for t in geo.tramos(pais)
        if _caja(t.a) and _caja(t.b) and geo.es_costa(pais, t.a, t.b)
    )


def distancia_frontera_km(lat: float, lon: float) -> float | None:
    """Distancia a la tierra de Ucrania, Rusia o Bielorrusia; None si pasa de 600 km."""
    mejor: float | None = None
    for pais in LADO_DE_LA_GUERRA:
        if geo.en_tierra_de(pais, lat, lon):
            return 0.0
        for tramo in geo.tramos_cerca(pais, lat, lon, geo.BUSQUEDA_KM):
            d = geo._distancia_tramo_km(lat, lon, tramo)
            if mejor is None or d < mejor:
                mejor = d
    return mejor


def distancia_mar_negro_km(lat: float, lon: float) -> float | None:
    """Distancia a la costa del mar Negro; None si pasa de 600 km."""
    if not (20 <= lon <= 50 and 36 <= lat <= 52):
        return None
    return min(geo._distancia_tramo_km(lat, lon, t) for t in _costa_mar_negro())


@cache
def _por_punto(lat: float, lon: float) -> tuple[str, str, float | None]:
    frontera = distancia_frontera_km(lat, lon)
    if frontera is not None and frontera <= BANDA_FRONTERA_KM:
        return FRONTERA, "cerca_de_la_frontera", frontera
    mar = distancia_mar_negro_km(lat, lon)
    if mar is not None and mar <= BANDA_MAR_NEGRO_KM:
        return FRONTERA, "costa_mar_negro", frontera
    return INTERIOR, "lejos_de_la_frontera", frontera


@cache
def _vertices(pais: str) -> tuple[tuple[float, float], ...]:
    return tuple({t.a for t in geo.tramos(pais)})


@cache
def pais_fronterizo(pais: str) -> bool:
    """Si alguna parte del país cae dentro de la banda (frontera o costa del mar Negro)."""
    return any(_por_punto(lat, lon)[0] == FRONTERA for lon, lat in _vertices(pais)[::7])


@cache
def pais_dentro_de_la_banda(pais: str) -> bool:
    """Si todo el país cae dentro de la banda de la frontera (Moldavia)."""
    vertices = _vertices(pais)
    return bool(vertices) and all(
        (d := distancia_frontera_km(lat, lon)) is not None and d <= BANDA_FRONTERA_KM
        for lon, lat in vertices[::5]
    )


@cache
def _nombres() -> dict[tuple[str, str], tuple[float, float, float]]:
    """(país, nombre sin tildes) -> (lat, lon, radio) de las localidades y lugares del
    nomenclátor, con las formas de configuracion/nombres_equivalentes.json («Constanza»)."""
    indice: dict[tuple[str, str], tuple[float, float, float]] = {}

    def poner(pais: str, nombre: str, lat: float, lon: float, radio: float) -> None:
        plano = " ".join(re.findall(r"\w+", _plano(nombre)))
        if len(plano) < 4:
            return
        anterior = indice.get((pais, plano))
        if anterior is None or radio > anterior[2]:
            indice[(pais, plano)] = (lat, lon, radio)

    localidades = json.loads(LOCALIDADES.read_text(encoding="utf-8"))["localidades"]
    for nombre, pais, lat, lon, radio, alias in localidades.values():
        for forma in (nombre, *alias):
            poner(pais, forma, lat, lon, radio)
    for lugar in json.loads(LUGARES.read_text(encoding="utf-8"))["lugares"].values():
        for forma in (lugar.get("nombre", ""), *lugar.get("alias", []), *lugar.get("ciudades", [])):
            poner(lugar["pais"], forma, lugar["lat"], lugar["lon"], lugar.get("radio_km", 5.0))
    equivalentes = json.loads(EQUIVALENTES.read_text(encoding="utf-8"))["nombres"]
    for entrada in equivalentes:
        for forma in entrada["formas"]:
            plano = " ".join(re.findall(r"\w+", _plano(forma)))
            for (pais, nombre), valor in list(indice.items()):
                if nombre == plano:
                    poner(pais, entrada["nombre"], *valor)
    return indice


def _lugar_nombrado(incidente: Documento) -> tuple[float, float] | None:
    """El lugar del nomenclátor de su país que nombran su localidad, su región o su titular
    (el de más radio si nombra varios en el mismo texto)."""
    lugar = incidente.get("lugar", {})
    pais = lugar.get("pais", "")
    titulo = incidente.get("titulo", {})
    indice = _nombres()
    for texto in (lugar.get("localidad"), lugar.get("region"), titulo.get("es"), titulo.get("en")):
        if not texto:
            continue
        palabras = re.findall(r"\w+", _plano(str(texto)))
        hallados = [
            indice[(pais, " ".join(palabras[i : i + n]))]
            for n in (3, 2, 1)
            for i in range(len(palabras) - n + 1)
            if (pais, " ".join(palabras[i : i + n])) in indice
        ]
        if hallados:
            lat, lon, _ = max(hallados, key=lambda h: h[2])
            return lat, lon
    return None


def clasificar(incidente: Documento) -> Documento:
    """{grupo, motivo, distancia_km?}: la distancia (a la frontera con Ucrania, Rusia o
    Bielorrusia, redondeada al km) solo cuando hay punto o lugar nombrado."""
    if "ataque" in incidente:
        return {"grupo": FRONTERA, "motivo": "ataque"}
    lugar = incidente.get("lugar", {})
    punto = lugar.get("punto")
    situado = (punto["lat"], punto["lon"]) if punto else _lugar_nombrado(incidente)
    if situado is not None:
        grupo, motivo, distancia = _por_punto(round(situado[0], 4), round(situado[1], 4))
        resultado: Documento = {"grupo": grupo, "motivo": motivo}
        if distancia is not None:
            resultado["distancia_km"] = round(distancia)
        return resultado
    pais = lugar.get("pais", "")
    titulos = " ".join(str(v) for v in incidente.get("titulo", {}).values())
    if pais in PAISES_COSTA_MAR_NEGRO and MAR_NEGRO.search(titulos):
        return {"grupo": FRONTERA, "motivo": "costa_mar_negro"}
    if pais_dentro_de_la_banda(pais):
        return {"grupo": FRONTERA, "motivo": "pais_dentro_de_la_banda"}
    pruebas = incidente.get("pruebas", {})
    de_fuera = (
        incidente.get("tipo") == "incursion"
        or pruebas.get("entrada_exterior") is True
        or pruebas.get("dron_estatal") is True
    )
    if de_fuera and pais_fronterizo(pais):
        return {"grupo": FRONTERA, "motivo": "incursion_en_pais_fronterizo"}
    return {"grupo": INTERIOR, "motivo": "sin_lugar"}


def con_zona(incidente: Documento) -> Documento:
    nuevo = copy.deepcopy(incidente)
    nuevo["zona"] = clasificar(incidente)
    return nuevo


def recuento(incidentes: Iterable[Documento]) -> dict[str, int]:
    resultado = dict.fromkeys(GRUPOS, 0)
    for incidente in incidentes:
        zona: dict[str, Any] = incidente.get("zona") or {}
        if zona.get("grupo") in resultado:
            resultado[zona["grupo"]] += 1
    return resultado


def clasificar_todos(
    almacen: "Almacen", ahora: datetime, modelos: frozenset[str]
) -> dict[str, int]:
    """Recalcula el grupo de cada incidente y guarda solo lo que cambia."""
    resumen = {"frontera": 0, "interior": 0, "cambiados": 0}
    for incidente in almacen.incidentes():
        if "fusionado_en" in incidente or "retirado" in incidente:
            continue
        zona = clasificar(incidente)
        resumen[zona["grupo"]] += 1
        if incidente.get("zona") == zona:
            continue
        nuevo = copy.deepcopy(incidente)
        nuevo["zona"] = zona
        almacen.guardar_incidente(nuevo, ahora, modelos)
        almacen.anotar_motivo(
            "incidentes", incidente["id"], {"zona": incidente.get("zona")}, {"zona": zona},
            MOTIVO_HISTORIAL,
        )  # fmt: skip
        resumen["cambiados"] += 1
    return resumen
