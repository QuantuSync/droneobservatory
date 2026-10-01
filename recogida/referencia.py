"""Referencia de movimientos por aeropuerto y día: el «Airport traffic» de EUROCONTROL.

EUROCONTROL publica en su Aviation Intelligence Portal los vuelos IFR diarios de llegada y
salida de unos 330 aeropuertos europeos, según el Network Manager
(https://www.eurocontrol.int/performance/data/download/csv/airport_traffic_<año>.csv, columna
FLT_TOT_1 = salidas + llegadas). Se actualiza cada mes, unas tres semanas después de que
termine. Sus condiciones permiten copiarlo con mención de EUROCONTROL y sin fines comerciales,
y no modificarlo: aquí solo se usa para calcular la cobertura de adsb.lol, no se publica
ninguna cifra suya, y figura en los créditos.

Los ficheros se guardan comprimidos en el disco del servidor (`<datos>/referencia/`) y se
vuelven a descargar si tienen más de una semana (los de años cerrados, una vez).

Para un día que EUROCONTROL aún no ha publicado, la referencia es la mediana del mismo día de
la semana en las cuatro últimas semanas publicadas de ese aeropuerto
(`eurocontrol_estimada`).
"""

import csv
import gzip
import io
import statistics
import time
from datetime import date, timedelta
from pathlib import Path

from proceso.trafico import Referencia
from recogida.descarga import AGENTE_EODI, Descargador

URL = "https://www.eurocontrol.int/performance/data/download/csv/airport_traffic_{anio}.csv"
CABECERA = b"YEAR,MONTH_NUM"
CADUCIDAD_S = 7 * 86400
PRIMER_ANIO = 2024
SEMANAS_ESTIMACION = 4


def ruta(datos: Path, anio: int) -> Path:
    return datos / "referencia" / f"airport_traffic_{anio}.csv.gz"


def actualizar(datos: Path, hoy: date, descarga: Descargador | None = None) -> list[int]:
    """Descarga los años que faltan o han caducado. Devuelve los años descargados."""
    descarga = descarga or Descargador(agente=AGENTE_EODI, reintentos=2)
    hechos = []
    for anio in range(PRIMER_ANIO, hoy.year + 1):
        destino = ruta(datos, anio)
        cerrado = (
            anio < hoy.year
            and destino.exists()
            and time.gmtime(destino.stat().st_mtime).tm_year > anio
        )
        if cerrado or (destino.exists() and time.time() - destino.stat().st_mtime < CADUCIDAD_S):
            continue
        cuerpo = descarga.contenido(URL.format(anio=anio), lambda c: c.startswith(CABECERA))
        destino.parent.mkdir(parents=True, exist_ok=True)
        temporal = destino.with_suffix(".tmp")
        temporal.write_bytes(gzip.compress(cuerpo, mtime=0))
        temporal.replace(destino)
        hechos.append(anio)
    return hechos


class Referencias:
    """Movimientos IFR de referencia por aeropuerto y día."""

    def __init__(self, datos: Path) -> None:
        self._dias: dict[str, dict[date, float]] = {}
        for fichero in sorted((datos / "referencia").glob("airport_traffic_*.csv.gz")):
            texto = gzip.decompress(fichero.read_bytes()).decode("utf-8", errors="replace")
            for fila in csv.DictReader(io.StringIO(texto)):
                try:
                    dia = date.fromisoformat(fila["FLT_DATE"][:10])
                    total = float(fila["FLT_TOT_1"])
                except (KeyError, ValueError):
                    continue
                self._dias.setdefault(fila["APT_ICAO"], {})[dia] = total
        self.ultimo = max((max(d) for d in self._dias.values() if d), default=None)

    def __call__(self, oaci: str, dia: date) -> Referencia | None:
        serie = self._dias.get(oaci)
        if not serie:
            return None
        if dia in serie:
            return Referencia(serie[dia], "eurocontrol")
        ultimo = max(serie)
        if dia < ultimo:
            return None  # un hueco en la serie: no se estima hacia atrás
        # El mismo día de la semana de las cuatro últimas semanas publicadas.
        candidato = ultimo - timedelta(days=(ultimo.weekday() - dia.weekday()) % 7)
        valores = [
            serie[d]
            for k in range(SEMANAS_ESTIMACION)
            if (d := candidato - timedelta(weeks=k)) in serie
        ]
        if len(valores) < 2:
            return None
        return Referencia(float(statistics.median(valores)), "eurocontrol_estimada")
