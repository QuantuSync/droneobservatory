"""METAR históricos de los aeropuertos, del archivo del Iowa Environmental Mesonet (IEM).

https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py devuelve los METAR de las
estaciones pedidas entre dos fechas (`data=metar`, rutinarios y especiales: `report_type` 3 y
4), también de Europa (comprobado con EKCH el 22 de septiembre de 2025: un METAR cada 30
minutos). Dominio público; el IEM agradece la atribución. Pide no pasar de una petición por
segundo y por dirección, y no más de unos 1000 años-estación por petición: aquí se piden los
aeropuertos de un día en tandas de 60, con una pausa de 2 s.

Se guardan en el disco del servidor, un fichero por día (`<datos>/metar/AAAA/AAAA-MM-DD.csv.gz`,
columnas estación, hora UTC y METAR), y se leen con `leer` y `proceso/metar.py`.
"""

import csv
import gzip
import io
from collections.abc import Iterable
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from urllib.parse import urlencode

from recogida.descarga import AGENTE_EODI, Descargador

URL = "https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py"
TANDA = 60
PAUSA_S = 2.0
CABECERA = b"station,valid,metar"


def url(estaciones: Iterable[str], dia: date) -> str:
    fin = dia + timedelta(days=1)
    parametros = [("station", e) for e in estaciones] + [
        ("data", "metar"),
        ("year1", str(dia.year)),
        ("month1", str(dia.month)),
        ("day1", str(dia.day)),
        ("year2", str(fin.year)),
        ("month2", str(fin.month)),
        ("day2", str(fin.day)),
        ("tz", "Etc/UTC"),
        ("format", "onlycomma"),
        ("latlon", "no"),
        ("missing", "M"),
        ("trace", "T"),
        ("direct", "no"),
        ("report_type", "3"),
        ("report_type", "4"),
    ]
    return f"{URL}?{urlencode(parametros)}"


def descargador() -> Descargador:
    return Descargador(agente=AGENTE_EODI, pausa_minima_s=PAUSA_S, reintentos=3)


def ruta(directorio: Path, dia: date) -> Path:
    return directorio / "metar" / f"{dia.year}" / f"{dia.isoformat()}.csv.gz"


def descargar(directorio: Path, dia: date, estaciones: list[str], descarga: Descargador) -> Path:
    """Descarga los METAR del día de todas las estaciones y los guarda. Devuelve la ruta."""
    filas: list[str] = []
    for i in range(0, len(estaciones), TANDA):
        cuerpo = descarga.contenido(
            url(estaciones[i : i + TANDA], dia), lambda c: c.startswith(CABECERA)
        )
        filas += cuerpo.decode("utf-8", errors="replace").splitlines()[1:]
    destino = ruta(directorio, dia)
    destino.parent.mkdir(parents=True, exist_ok=True)
    temporal = destino.with_suffix(".tmp")
    texto = "station,valid,metar\n" + "".join(f"{f}\n" for f in sorted(set(filas)) if f)
    temporal.write_bytes(gzip.compress(texto.encode("utf-8"), mtime=0))
    temporal.replace(destino)
    return destino


def leer(directorio: Path, dia: date) -> dict[str, list[tuple[datetime, str]]]:
    """Por estación, sus METAR del día (hora UTC y texto), en orden. Vacío si no se bajaron."""
    fichero = ruta(directorio, dia)
    if not fichero.exists():
        return {}
    resultado: dict[str, list[tuple[datetime, str]]] = {}
    texto = gzip.decompress(fichero.read_bytes()).decode("utf-8")
    for fila in csv.DictReader(io.StringIO(texto)):
        try:
            hora = datetime.strptime(fila["valid"], "%Y-%m-%d %H:%M").replace(tzinfo=UTC)
        except (KeyError, ValueError):
            continue
        resultado.setdefault(fila["station"], []).append((hora, fila["metar"]))
    for lista in resultado.values():
        lista.sort()
    return resultado
