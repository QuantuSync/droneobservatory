"""Meteorología medida de Open-Meteo para cada incidente y para cada ataque de la capa de guerra.

Se usa la Historical Forecast API (https://historical-forecast-api.open-meteo.com/v1/forecast),
uso no comercial sin clave, datos con licencia CC BY 4.0 («Weather data by Open-Meteo.com»).
Comprobado el 1 de octubre de 2026: es la única de Open-Meteo que da los niveles de presión en
el histórico (la Historical Weather API de ERA5 los devuelve vacíos) y llega hasta el día
anterior; su modelo por defecto (`best_match`, que en Europa combina ICON, ECMWF IFS, GFS y
los modelos regionales) trae viento, temperatura y humedad en 1000, 925, 850 y 700 hPa desde
el 1 de enero de 2025 en todos los incidentes probados. Sus series empiezan entre marzo de
2021 (GFS) y noviembre de 2022 (ICON, ECMWF IFS 0,4°); lo que no tenga dato llega como null y
se guarda como vacío, nunca se rellena.

Límites del servicio gratuito: 600 llamadas por minuto, 5000 por hora y 10 000 por día; una
petición de más de 10 variables o más de 14 días cuenta como varias. Aquí cada petición es de
un día y un lugar (o varios lugares de un mismo ataque) y se guarda en caché en el disco del
servidor (`<datos>/openmeteo/AAAA-MM-DD/<lat>_<lon>.json`, `EODI_METEO_DATOS`, por defecto
`~/datos/meteo`): un mismo lugar y día no se vuelve a pedir. Cada ejecución horaria pide como
mucho TOPE_LLAMADAS.
"""

import json
import os
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

from recogida.descarga import AGENTE_EODI, Descargador
from recogida.plazo import Plazo

URL = "https://historical-forecast-api.open-meteo.com/v1/forecast"
VARIABLE_DATOS = "EODI_METEO_DATOS"
DATOS = Path.home() / "datos" / "meteo"
NIVELES = (1000, 925, 850, 700)
SUPERFICIE = (
    "temperature_2m",
    "relative_humidity_2m",
    "precipitation",
    "cloud_cover",
    "wind_speed_10m",
    "wind_direction_10m",
    "wind_gusts_10m",
    "wind_speed_100m",
    "wind_direction_100m",
)
PRESION = tuple(
    f"{v}_{n}hPa" for n in NIVELES for v in ("wind_speed", "wind_direction", "temperature")
)
# Para la capa de guerra basta el viento: 10 variables, una llamada por lugar y día.
VIENTO = (
    "wind_speed_10m",
    "wind_direction_10m",
    "wind_speed_100m",
    "wind_direction_100m",
    *(f"{v}_{n}hPa" for n in (925, 850, 700) for v in ("wind_speed", "wind_direction")),
)
ATRIBUCION = "Weather data by Open-Meteo.com (CC BY 4.0)"
# 300 llamadas por ejecución horaria: unas 7000 al día, por debajo del límite de 10 000.
TOPE_LLAMADAS = 300
TOPE_S = 120.0
PAUSA_S = 0.2


def directorio_datos() -> Path:
    return Path(os.environ.get(VARIABLE_DATOS) or DATOS)


def descargador(plazo: Plazo | None = None) -> Descargador:
    return Descargador(agente=AGENTE_EODI, pausa_minima_s=PAUSA_S, reintentos=2, plazo=plazo)


def url(puntos: list[tuple[float, float]], dia: date, variables: tuple[str, ...]) -> str:
    parametros = {
        "latitude": ",".join(f"{lat:.3f}" for lat, _ in puntos),
        "longitude": ",".join(f"{lon:.3f}" for _, lon in puntos),
        "start_date": dia.isoformat(),
        "end_date": dia.isoformat(),
        "hourly": ",".join(variables),
        "wind_speed_unit": "ms",
        "timezone": "GMT",
    }
    return f"{URL}?{urlencode(parametros)}"


def unidades(variables: tuple[str, ...], lugares: int) -> float:
    """Llamadas que cuenta Open-Meteo: una por lugar y por cada 10 variables (un día)."""
    return lugares * max(1.0, len(variables) / 10)


@dataclass
class Cliente:
    datos: Path
    descarga: Descargador
    tope: float = TOPE_LLAMADAS
    gastadas: float = 0.0

    def _ruta(self, lat: float, lon: float, dia: date, clave: str) -> Path:
        return self.datos / "openmeteo" / dia.isoformat() / f"{clave}_{lat:.3f}_{lon:.3f}.json"

    def horas(
        self, puntos: list[tuple[float, float]], dia: date, variables: tuple[str, ...], clave: str
    ) -> list[dict[str, list[Any]] | None]:
        """Series horarias de cada punto ese día (de la caché o pidiéndolas). None en un punto
        si no queda cupo en esta ejecución."""
        resultado: list[dict[str, list[Any]] | None] = []
        faltan: list[tuple[int, tuple[float, float]]] = []
        for k, (lat, lon) in enumerate(puntos):
            ruta = self._ruta(lat, lon, dia, clave)
            if ruta.exists():
                resultado.append(json.loads(ruta.read_text(encoding="utf-8")))
            else:
                resultado.append(None)
                faltan.append((k, (lat, lon)))
        if not faltan:
            return resultado
        coste = unidades(variables, len(faltan))
        if self.gastadas + coste > self.tope:
            return resultado
        cuerpo = self.descarga.contenido(
            url([p for _, p in faltan], dia, variables), lambda c: c.lstrip()[:1] in (b"{", b"[")
        )
        self.gastadas += coste
        respuesta = json.loads(cuerpo)
        lista = respuesta if isinstance(respuesta, list) else [respuesta]
        for (k, (lat, lon)), datos in zip(faltan, lista, strict=True):
            horario: dict[str, list[Any]] = datos.get("hourly", {})
            ruta = self._ruta(lat, lon, dia, clave)
            ruta.parent.mkdir(parents=True, exist_ok=True)
            ruta.write_text(
                json.dumps(horario, separators=(",", ":")), encoding="utf-8", newline="\n"
            )
            resultado[k] = horario
        return resultado


def valor(horario: dict[str, list[Any]], variable: str, hora: int) -> float | None:
    serie = horario.get(variable) or []
    if 0 <= hora < len(serie) and isinstance(serie[hora], int | float):
        return float(serie[hora])
    return None


def rango(horario: dict[str, list[Any]], variable: str) -> tuple[float, float] | None:
    serie = [float(v) for v in horario.get(variable) or [] if isinstance(v, int | float)]
    return (min(serie), max(serie)) if serie else None


Pedidor = Callable[
    [list[tuple[float, float]], date, tuple[str, ...], str], list[dict[str, list[Any]] | None]
]
