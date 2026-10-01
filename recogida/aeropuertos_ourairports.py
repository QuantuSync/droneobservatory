"""Genera los aeropuertos europeos y sus pistas para el tráfico aéreo medido desde OurAirports.

De https://ourairports.com/data/ (dominio público): los aeropuertos grandes y medianos de
Europa (continente EU de OurAirports), Turquía y Chipre, con código OACI, salvo Rusia y
Bielorrusia (sin incidentes y casi sin receptores de adsb.lol). Cada uno lleva su punto de
referencia, su elevación, si tiene tráfico regular (`scheduled_service`) y los umbrales de
sus pistas con su rumbo verdadero, calculado de un umbral al otro, como hace la biblioteca
«traffic» (MIT). Los de Ucrania figuran aunque no tengan vuelos regulares desde 2022.

Uso: python -m recogida.aeropuertos_ourairports [--aeropuertos airports.csv]
    [--pistas runways.csv]
"""

import argparse
import csv
import io
import json
import math
import re
import sys
import unicodedata
from pathlib import Path
from typing import Any

from recogida.descarga import AGENTE_EODI, Descargador

AEROPUERTOS = "https://davidmegginson.github.io/ourairports-data/airports.csv"
PISTAS = "https://davidmegginson.github.io/ourairports-data/runways.csv"
DESTINO = Path(__file__).resolve().parent.parent / "configuracion" / "aeropuertos_trafico.json"
TIPOS = frozenset({"large_airport", "medium_airport"})
PAISES_FUERA_DE_EU = frozenset({"TR", "CY"})
EXCLUIDOS = frozenset({"RU", "BY"})
OACI = re.compile(r"^[A-Z]{4}$")
PIES_A_M = 0.3048


def _real(texto: str) -> float | None:
    try:
        return float(texto)
    except ValueError:
        return None


def ascii_(texto: str) -> str:
    """El nombre sin diacríticos: solo sirve para leer el fichero, y así el
    control de términos del repositorio no ve palabras partidas por letras no ASCII."""
    return unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")


def rumbo(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Rumbo inicial verdadero del primer punto al segundo, en grados (0, 360]."""
    f1, f2 = math.radians(lat1), math.radians(lat2)
    dl = math.radians(lon2 - lon1)
    x = math.sin(dl) * math.cos(f2)
    y = math.cos(f1) * math.sin(f2) - math.sin(f1) * math.cos(f2) * math.cos(dl)
    grados = math.degrees(math.atan2(x, y)) % 360
    return round(grados if grados > 0 else 360.0, 1)


def _umbrales(fila: dict[str, str]) -> list[dict[str, Any]]:
    """Los dos umbrales de una pista con coordenadas, cada uno con el rumbo hacia el otro."""
    puntos = {}
    for extremo in ("le", "he"):
        lat, lon = _real(fila[f"{extremo}_latitude_deg"]), _real(fila[f"{extremo}_longitude_deg"])
        if lat is None or lon is None:
            return []
        puntos[extremo] = (
            lat,
            lon,
            fila[f"{extremo}_ident"],
            _real(fila[f"{extremo}_elevation_ft"]),
        )
    (la1, lo1, id1, el1), (la2, lo2, id2, el2) = puntos["le"], puntos["he"]
    if (la1, lo1) == (la2, lo2):
        return []
    return [
        {"id": id1, "lat": round(la1, 5), "lon": round(lo1, 5), "rumbo": rumbo(la1, lo1, la2, lo2)}
        | ({"elev_ft": round(el1)} if el1 is not None else {}),
        {"id": id2, "lat": round(la2, 5), "lon": round(lo2, 5), "rumbo": rumbo(la2, lo2, la1, lo1)}
        | ({"elev_ft": round(el2)} if el2 is not None else {}),
    ]


def generar(aeropuertos: str, pistas: str) -> list[dict[str, Any]]:
    por_ref: dict[str, list[dict[str, Any]]] = {}
    for fila in csv.DictReader(io.StringIO(pistas)):
        if fila["closed"] == "1":
            continue
        por_ref.setdefault(fila["airport_ref"], []).extend(_umbrales(fila))
    resultado = []
    for fila in csv.DictReader(io.StringIO(aeropuertos)):
        pais = fila["iso_country"]
        europeo = fila["continent"] == "EU" or pais in PAISES_FUERA_DE_EU
        if fila["type"] not in TIPOS or not europeo or pais in EXCLUIDOS:
            continue
        oaci = fila["icao_code"] or fila["ident"]
        lat, lon = _real(fila["latitude_deg"]), _real(fila["longitude_deg"])
        if not OACI.match(oaci) or lat is None or lon is None:
            continue
        elevacion = _real(fila["elevation_ft"])
        resultado.append(
            {
                "oaci": oaci,
                "nombre": ascii_(fila["name"]),
                "pais": pais,
                "lat": round(lat, 5),
                "lon": round(lon, 5),
                "elev_ft": round(elevacion) if elevacion is not None else 0,
                "grande": fila["type"] == "large_airport",
                "regular": fila["scheduled_service"] == "yes",
                "pistas": sorted(por_ref.get(fila["id"], []), key=lambda p: str(p["id"])),
            }
        )
    return sorted(resultado, key=lambda a: str(a["oaci"]))


def principal(argumentos: list[str] | None = None) -> int:
    opciones = argparse.ArgumentParser(description=__doc__)
    opciones.add_argument("--aeropuertos", type=Path)
    opciones.add_argument("--pistas", type=Path)
    args = opciones.parse_args(argumentos)
    descarga = Descargador(agente=AGENTE_EODI)

    def leer(ruta: Path | None, url: str) -> str:
        if ruta is not None:
            return ruta.read_text(encoding="utf-8")
        return descarga.contenido(url, lambda c: c.startswith(b'"id",')).decode("utf-8")

    datos = generar(leer(args.aeropuertos, AEROPUERTOS), leer(args.pistas, PISTAS))
    texto = json.dumps(
        {
            "fuente": "OurAirports (dominio público), https://ourairports.com/data/",
            "aeropuertos": datos,
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )
    DESTINO.write_text(texto + "\n", encoding="utf-8", newline="\n")
    print(f"{len(datos)} aeropuertos, {sum(len(a['pistas']) for a in datos)} umbrales")
    return 0


if __name__ == "__main__":
    sys.exit(principal())
