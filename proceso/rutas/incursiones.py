"""Recorrido de las incursiones en Rumanía, Moldavia y Polonia según la autoridad, y velocidad
entre avistamientos encadenados.

**Recorrido.** De las frases de origen oficial del incidente (la autoridad o su declaración
citada) se leen los lugares por los que dice que pasó el dron, en orden, y sus horas:

- «din direcția localității Lesnaia (Ucraina) spre localitatea Săiți»;
- «pe direcția Stanislavka (regiunea Odesa) - Vărăncău»;
- «de la NE de Chilia Veche spre SV de Izmail, și a părăsit spațiul aerian național în dreptul
  localității Pardina»;
- «intrând în țară prin localitatea Valea Perjei»; «z kierunku …», «w rejonie …».

Cada lugar se sitúa con las localidades de GeoNames y del nomenclátor de Ucrania, y solo si está a
80 km o menos del punto del incidente (así un homónimo lejano no cuela). Con dos lugares o más,
el recorrido se dibuja como franja (cada lugar con su radio). Sin dos lugares, no hay recorrido.

**Velocidad entre avistamientos encadenados.** Si dos lugares del mismo recorrido, o dos
incidentes del mismo episodio, llevan hora, la velocidad necesaria entre ellos va de (distancia −
radios) / (tiempo más el margen de las horas) a (distancia + radios) / (tiempo menos ese margen);
el margen es de 2 minutos con hora al minuto y de 30 con hora en punto. Es la velocidad mínima
con que tuvo que volar: si pasa de 300 km/h en todo el margen, solo un dron a reacción llega
(restricción «reacción» para el tipo de dron). Una velocidad necesaria baja no dice hélice (un
dron rápido también puede tardar más, dando vueltas): no decide. Si el tiempo puede ser de menos
de 5 minutos (el margen lo cubre), no se usa: pueden ser dos drones.
"""

import gzip
import itertools
import json
import re
import unicodedata
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any

from proceso import lugares_guerra
from proceso.rutas import geometria

VERSION = "recorridos-1.0.0"
CONFIGURACION = Path(__file__).resolve().parent.parent.parent / "configuracion"
PAISES = ("RO", "MD", "PL")
VECINOS = ("RO", "MD", "PL", "UA", "BY", "RU")
CERCA_KM = 80.0
RADIO_LUGAR_KM = 4.0
ORIGENES = ("oficial", "oficial_citado")
HELICE_MAX_KMH = 230.0
REACCION_MIN_KMH = 300.0
TIEMPO_MINIMO_MIN = 5.0
MARGEN_MIN = 2.0

_MAYUSCULA = "A-ZĂÂÎȘŞȚŢŁŚŻŹĆŃÓĘĄ"
_LETRAS = r"\wăâîșşțţłśżźćńóęą'’-"
_NOMBRE = rf"([{_MAYUSCULA}][{_LETRAS}]+(?:[ -][{_MAYUSCULA}][{_LETRAS}]+){{0,2}})"
_LUGARES = re.compile(
    r"(?:din\s+direcți[ae]\s+(?:localității\s+|satului\s+|loc\.\s*|orașului\s+)?|"
    r"pe\s+direcți[ae]\s+(?:satului\s+|localității\s+)?|spre\s+(?:localitatea\s+|orașul\s+|satul\s+)?|"
    r"prin\s+(?:zona\s+|localitatea\s+)?|în\s+dreptul\s+localității\s+|de\s+la\s+[NSEV]{1,2}\s+de\s+|"
    r"spre\s+[NSEV]{1,2}\s+de\s+|localitatea\s+|în\s+direcția\s+(?:localității\s+)?|"
    r"z\s+kierunku\s+|w\s+rejonie\s+|w\s+okolicach\s+|nad\s+|przez\s+|\s[-–]\s)" + _NOMBRE
)
_HORA = re.compile(r"(?:la\s+ora|ora|o\s+godz\.?|godz\.?|около|at)\s+(\d{1,2})[.:](\d{2})")
_NO_LUGAR = frozenset(
    {
        "Ucraina",
        "Ucrainei",
        "România",
        "României",
        "Republica",
        "Moldova",
        "Ukrainy",
        "Polski",
        "Polska",
        "Federației",
        "Rusiei",
        "Unitatea",
        "UTAG",
        "Odesa",
        "Reni",
        "Găgăuzia",
    }
)


def plano(texto: str) -> str:
    base = unicodedata.normalize("NFKD", texto.lower())
    return "".join(c for c in base if not unicodedata.combining(c)).replace("ł", "l")


@cache
def _indice() -> dict[str, list[tuple[str, float, float]]]:
    """Nombre plano → (país, lat, lon) de GeoNames (Europa) y del nomenclátor de Ucrania."""
    indice: dict[str, list[tuple[str, float, float]]] = {}

    def anadir(nombre: str, pais: str, lat: float, lon: float) -> None:
        if pais in VECINOS:
            indice.setdefault(plano(nombre), []).append((pais, lat, lon))

    datos = json.loads((CONFIGURACION / "localidades_europa.json").read_text(encoding="utf-8"))
    for fila in (
        datos["localidades"].values()
        if isinstance(datos["localidades"], dict)
        else datos["localidades"]
    ):
        nombre, pais, lat, lon = fila[0], fila[1], fila[2], fila[3]
        for alias in [nombre, *(fila[5] if len(fila) > 5 and isinstance(fila[5], list) else [])]:
            anadir(str(alias), pais, lat, lon)
    from proceso import ubicacion

    _, filas = ubicacion.localidades_pequenas()
    for fila in filas.values():
        for alias in [fila[0], *fila[5]]:
            anadir(str(alias), fila[1], fila[2], fila[3])
    crudo = json.loads(gzip.decompress(lugares_guerra.NOMENCLATOR.read_bytes()))
    for e in crudo["localidades"]:
        for alias in [e["nombre"], *e.get("nombres", {}).get("la", [])]:
            anadir(alias, "UA", e["lat"], e["lon"])
    return indice


def situar(nombre: str, lat0: float, lon0: float) -> tuple[float, float] | None:
    """El lugar con ese nombre más cercano al incidente, si está a 80 km o menos."""
    candidatos = _indice().get(plano(nombre), [])
    cerca = [(geometria.distancia_km(lat, lon, lat0, lon0), lat, lon) for _, lat, lon in candidatos]
    cerca = [c for c in cerca if c[0] <= CERCA_KM]
    if not cerca:
        return None
    _, lat, lon = min(cerca)
    return lat, lon


@dataclass
class Lugar:
    nombre: str
    lat: float
    lon: float
    hora: str | None
    cita: str
    fuente: str


def lugares_de_frase(texto: str, lat0: float, lon0: float, fuente: str) -> list[Lugar]:
    hallados: list[Lugar] = []
    hora = None
    if m := _HORA.search(texto):
        hora = f"{int(m.group(1)):02d}:{m.group(2)}"
    for m in _LUGARES.finditer(texto):
        nombre = m.group(1).strip()
        if nombre.split()[0] in _NO_LUGAR:
            continue
        punto = situar(nombre, lat0, lon0)
        if punto is None and " " in nombre:
            punto = situar(nombre.split()[0], lat0, lon0)
        if punto is None:
            continue
        if any(plano(h.nombre) == plano(nombre) for h in hallados):
            continue
        hallados.append(Lugar(nombre, punto[0], punto[1], hora, texto, fuente))
    return hallados


def recorrido(
    incidente: dict[str, Any], frases: list[tuple[str, str, str, str | None]]
) -> dict[str, Any] | None:
    """El recorrido que da la autoridad, o None si no da dos lugares."""
    lugar = incidente.get("lugar") or {}
    punto = lugar.get("punto")
    if lugar.get("pais") not in PAISES or not punto:
        return None
    for origen, fuente, texto, _ in frases:
        if origen not in ORIGENES:
            continue
        lugares = lugares_de_frase(texto, punto["lat"], punto["lon"], fuente)
        if len(lugares) >= 2:
            return {
                "version": VERSION,
                "fuente": fuente,
                "cita": texto,
                "puntos": [
                    {
                        "nombre": x.nombre,
                        "lat": round(x.lat, 4),
                        "lon": round(x.lon, 4),
                        "radio_km": RADIO_LUGAR_KM,
                        **({"hora": x.hora} if x.hora else {}),
                    }
                    for x in lugares
                ],
                "franja": [
                    [
                        [a, b]
                        for a, b in geometria.poligono(
                            geometria.Tramo(
                                x.lat, x.lon, RADIO_LUGAR_KM, y.lat, y.lon, RADIO_LUGAR_KM
                            ),
                            10,
                        )
                    ]
                    for x, y in itertools.pairwise(lugares)
                ],
            }
    return None


MARGEN_HORA_EN_PUNTO_MIN = 30.0


def velocidad_entre(a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any] | None:
    """Velocidad necesaria entre dos avistamientos {lat, lon, radio_km, minuto (desde una época),
    margen_min}; None si el tiempo puede ser casi nulo."""
    minutos = abs(float(b["minuto"]) - float(a["minuto"]))
    margen = float(a["margen_min"]) + float(b["margen_min"])
    if minutos - margen < TIEMPO_MINIMO_MIN:
        return None
    d = geometria.distancia_km(a["lat"], a["lon"], b["lat"], b["lon"])
    radios = float(a["radio_km"]) + float(b["radio_km"])
    minima = max(0.0, d - radios) / ((minutos + margen) / 60)
    maxima = (d + radios) / ((minutos - margen) / 60)
    return {
        "min_kmh": round(minima),
        "max_kmh": round(maxima),
        "minutos": round(minutos),
        "distancia_km": round(d, 1),
        "decide": "reaccion" if minima > REACCION_MIN_KMH else None,
    }


def velocidad(puntos: list[dict[str, Any]]) -> dict[str, Any] | None:
    """La velocidad necesaria entre los dos primeros lugares del recorrido con hora distinta."""
    con_hora = [p for p in puntos if p.get("hora")]
    for a, b in itertools.pairwise(con_hora):
        if a["hora"] == b["hora"]:
            continue
        pares = []
        for p in (a, b):
            h, m = (int(x) for x in p["hora"].split(":"))
            pares.append({**p, "minuto": h * 60 + m, "margen_min": MARGEN_MIN})
        if pares[1]["minuto"] < pares[0]["minuto"]:
            pares[1]["minuto"] += 24 * 60
        resultado = velocidad_entre(pares[0], pares[1])
        if resultado is not None:
            return {**resultado, "desde": a["nombre"], "hasta": b["nombre"]}
    return None


def avistamiento(incidente: dict[str, Any]) -> dict[str, Any] | None:
    """El incidente como avistamiento para la velocidad: punto, radio y hora con su margen."""
    from datetime import datetime

    lugar = incidente.get("lugar") or {}
    inicio = (incidente.get("tiempo") or {}).get("inicio") or {}
    margen = {"minuto": MARGEN_MIN, "hora": MARGEN_HORA_EN_PUNTO_MIN}.get(
        inicio.get("precision", "")
    )
    if not lugar.get("punto") or margen is None:
        return None
    momento = datetime.fromisoformat(str(inicio["valor"]).replace("Z", "+00:00"))
    return {
        "id": incidente["id"],
        "lat": lugar["punto"]["lat"],
        "lon": lugar["punto"]["lon"],
        "radio_km": float(lugar.get("radio_km") or RADIO_LUGAR_KM),
        "minuto": momento.timestamp() / 60.0,
        "margen_min": margen,
    }


def velocidades_de_episodio(incidentes: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Por incidente del episodio, la velocidad necesaria desde el avistamiento anterior, cuando
    decide algo."""
    puntos = sorted((a for a in map(avistamiento, incidentes) if a), key=lambda a: a["minuto"])
    salida = {}
    for a, b in itertools.pairwise(puntos):
        resultado = velocidad_entre(a, b)
        if resultado is not None:
            salida[b["id"]] = {**resultado, "desde": a["id"]}
            salida.setdefault(a["id"], {**resultado, "hasta": b["id"]})
    return salida
