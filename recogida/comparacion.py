"""Cobertura frente a una lista de referencia de sucesos (la de Wikipedia de 2025).

Un suceso está cubierto si hay un incidente publicado (o, en su defecto, un
candidato) en su aeropuerto o base, o a menos de 20 km de su sitio, con inicio
del día anterior a tres días después: la fecha de la lista es la del suceso y la
de un candidato, la de su primer artículo.

Uso: python -m recogida.comparacion [--candidatos]
"""

import argparse
import json
import math
import sys
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory

from almacen import remoto
from almacen.base import Almacen
from almacen.cifrado import abrir_cifrada, cargar_clave_local
from esquema import Documento
from proceso.noticias import lugar, nomenclator

REFERENCIA = (
    Path(__file__).resolve().parent.parent / "configuracion" / "referencia_wikipedia_2025.json"
)
# Una base o un aeropuerto grande y su entorno: dos radios del nomenclátor.
DISTANCIA_KM = 20.0
DIAS_ANTES = timedelta(days=1)
# Las noticias de investigación salen días después: la de los drones de Dublín del 1 de
# diciembre de 2025 se publicó el 4.
DIAS_DESPUES = timedelta(days=3)
RADIO_TIERRA_KM = 6371.0


@dataclass(frozen=True)
class Suceso:
    fecha: date
    pais: str
    lugar: str
    lat: float
    lon: float
    oaci: str | None


def referencia(ruta: Path = REFERENCIA) -> list[Suceso]:
    nom = nomenclator()
    sucesos = []
    for s in json.loads(ruta.read_text(encoding="utf-8"))["sucesos"]:
        oaci = s.get("oaci")
        sitio = nom.lugares.get(oaci) if oaci else None
        lat = sitio.lat if sitio else s["lat"]
        lon = sitio.lon if sitio else s["lon"]
        sucesos.append(
            Suceso(date.fromisoformat(s["fecha"]), s["pais"], s["lugar"], lat, lon, oaci)
        )
    return sucesos


def _km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    f1, f2 = math.radians(lat1), math.radians(lat2)
    df, dl = f2 - f1, math.radians(lon2 - lon1)
    h = math.sin(df / 2) ** 2 + math.cos(f1) * math.cos(f2) * math.sin(dl / 2) ** 2
    return 2 * RADIO_TIERRA_KM * math.asin(math.sqrt(h))


@dataclass(frozen=True)
class Punto:
    id: str
    fecha: date
    lat: float
    lon: float
    sitio: str | None


def de_incidente(incidente: Documento) -> Punto:
    punto = incidente["lugar"]["punto"]
    return Punto(
        incidente["id"],
        date.fromisoformat(incidente["tiempo"]["inicio"]["valor"][:10]),
        punto["lat"],
        punto["lon"],
        incidente.get("objetivo", {}).get("oaci"),
    )


def de_candidato(candidato: Documento) -> Punto | None:
    try:
        sitio = lugar(candidato["lugar"], nomenclator())
    except KeyError:
        return None
    return Punto(
        candidato["id"],
        date.fromisoformat(candidato["inicio"][:10]),
        sitio.lat,
        sitio.lon,
        sitio.id,
    )


def cubre(suceso: Suceso, punto: Punto) -> bool:
    if not suceso.fecha - DIAS_ANTES <= punto.fecha <= suceso.fecha + DIAS_DESPUES:
        return False
    if suceso.oaci and punto.sitio == suceso.oaci:
        return True
    return _km(suceso.lat, suceso.lon, punto.lat, punto.lon) <= DISTANCIA_KM


def comparar(sucesos: list[Suceso], puntos: list[Punto]) -> list[tuple[Suceso, list[str]]]:
    return [(s, sorted(p.id for p in puntos if cubre(s, p))) for s in sucesos]


def tabla(resultado: list[tuple[Suceso, list[str]]]) -> str:
    lineas = ["| Fecha | País | Lugar | Encontrado |", "| --- | --- | --- | --- |"]
    for suceso, ids in resultado:
        encontrado = ", ".join(ids) if ids else "falta"
        lineas.append(f"| {suceso.fecha} | {suceso.pais} | {suceso.lugar} | {encontrado} |")
    cubiertos = sum(1 for _, ids in resultado if ids)
    lineas.append(f"\n{cubiertos} de {len(resultado)} sucesos encontrados.")
    return "\n".join(lineas) + "\n"


def principal(argumentos: list[str] | None = None) -> int:
    opciones = argparse.ArgumentParser(description=__doc__)
    opciones.add_argument("--candidatos", action="store_true", help="compara con los candidatos")
    opciones.add_argument("--base", type=Path, help="base cifrada local en vez de la rama estado")
    args = opciones.parse_args(argumentos)
    cargar_clave_local()
    with TemporaryDirectory() as temporal:
        ruta = args.base or Path(temporal) / remoto.FICHERO
        if args.base is None and not remoto.descargar(ruta):
            return 1
        almacen = Almacen(abrir_cifrada(ruta))
        if args.candidatos:
            puntos = [p for c in almacen.candidatos() if (p := de_candidato(c)) is not None]
        else:
            activos = [i for i in almacen.incidentes() if "fusionado_en" not in i]
            puntos = [de_incidente(i) for i in activos]
        sys.stdout.write(tabla(comparar(referencia(), puntos)))
    return 0


if __name__ == "__main__":
    sys.exit(principal())
