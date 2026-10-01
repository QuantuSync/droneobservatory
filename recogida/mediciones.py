"""Paso de las mediciones en la recogida horaria: tráfico aéreo medido y condiciones medidas.

Corre dentro de la recogida horaria, que ya tiene el cerrojo y la base abierta, y solo lee lo
que el procesado pesado (`recogida/trafico.py`, con su propio cerrojo) dejó en el disco del
servidor: escribe en la base en segundos (`proceso/mediciones.py`). También deja en
`<datos>/zonas.json` los incidentes que el procesado necesita, y pide a Open-Meteo y al IEM lo
que falta de las condiciones, con su cupo por ejecución.

Nada de lo que falle aquí cambia el resultado de la recogida: queda en el registro y en
estado.json (fuentes `trafico_aereo` y `condiciones`), y la ejecución siguiente vuelve a
intentarlo.

- `trafico_aereo`: leída si el paso termina y el último día procesado se procesó en las
  últimas 48 horas; con aviso si el procesado lleva más de 48 horas sin terminar un día (el
  diario debería procesar uno cada día); su último dato es la hora del último día procesado.
- `condiciones`: leída si Open-Meteo y el IEM responden (o no hacía falta pedir nada); su
  último dato es la hora de la última petición correcta.
"""

import logging
from datetime import UTC, date, datetime, timedelta
from functools import cache
from pathlib import Path
from typing import Any

from almacen.base import Almacen
from proceso import mediciones, metar, trafico, vuelos
from recogida import metar as metar_iem
from recogida import meteo, referencia
from recogida import trafico as procesado
from recogida.estado import CON_AVISO, LEIDA, NO_LEIDA, EstadoFuente
from recogida.plazo import Plazo

registro = logging.getLogger("recogida.mediciones")

FUENTE_TRAFICO = "trafico_aereo"
FUENTE_CONDICIONES = "condiciones"
# Tope del paso dentro de la recogida horaria: unos segundos con todo al día; el histórico
# entra por tandas de este tamaño.
TOPE_TRAFICO_S = 150.0
TOPE_CONDICIONES_S = meteo.TOPE_S
SIN_PROCESAR_AVISO = timedelta(hours=48)


def _instante(texto: str | None) -> datetime | None:
    return datetime.fromisoformat(texto.replace("Z", "+00:00")) if texto else None


class Metares:
    """METAR de los días procesados (los baja el procesado pesado), leídos y en caché."""

    def __init__(self, datos: Path) -> None:
        self._datos = datos
        self._dias: dict[date, dict[str, list[metar.Metar]]] = {}

    def dia(self, dia: date) -> dict[str, list[metar.Metar]]:
        if dia not in self._dias:
            crudos = metar_iem.leer(self._datos, dia)
            self._dias[dia] = {
                e: [metar.leer(h, t) for h, t in lista] for e, lista in crudos.items()
            }
            if len(self._dias) > procesado.DIAS_EN_MEMORIA:
                self._dias.pop(next(iter(self._dias)))
        return self._dias[dia]

    def __call__(self, oaci: str, desde: float, hasta: float) -> list[metar.Metar]:
        resultado: list[metar.Metar] = []
        dia = datetime.fromtimestamp(desde, UTC).date()
        while trafico.inicio_dia(dia) <= hasta:
            resultado += [
                m for m in self.dia(dia).get(oaci, []) if desde <= m.hora.timestamp() <= hasta
            ]
            dia += timedelta(days=1)
        return resultado


@cache
def aeropuertos() -> dict[str, vuelos.Aeropuerto]:
    return {a.oaci: a for a in vuelos.cargar_aeropuertos()}


def entorno(datos: Path) -> tuple[mediciones.Entorno, procesado.Dias]:
    dias = procesado.Dias(datos)
    return mediciones.Entorno(
        lector=dias,
        procesados=dias.procesados(),
        perdidos=dias.perdidos,
        referencias=referencia.Referencias(datos),
        metares=Metares(datos),
        resumen=dias.resumen,
        aeropuertos=aeropuertos(),
    ), dias


def paso_trafico(almacen: Almacen, ahora: datetime, datos: Path | None = None) -> EstadoFuente:
    datos = datos or procesado.directorio_datos()
    control = procesado.leer_json(datos / procesado.CONTROL) or {}
    ultimo = _instante(control.get("ultimo_correcto"))
    try:
        datos.mkdir(parents=True, exist_ok=True)
        procesado.escribir_json(
            datos / procesado.ZONAS, mediciones.zonas(almacen.incidentes(), aeropuertos())
        )
        contexto, _ = entorno(datos)
        resumen = mediciones.evaluar_trafico(almacen, contexto, ahora, Plazo(TOPE_TRAFICO_S))
        registro.info("tráfico aéreo: %s", resumen.texto())
        cursor = almacen.cursor(FUENTE_TRAFICO) or {}
        almacen.guardar_cursor(
            FUENTE_TRAFICO, {**cursor, "ultima_lectura": ahora.strftime("%Y-%m-%dT%H:%MZ")}
        )
    except Exception as error:
        registro.warning("tráfico aéreo no se incorpora: %s", error)
        return EstadoFuente(NO_LEIDA, ultimo)
    if ultimo is None or ahora - ultimo > SIN_PROCESAR_AVISO:
        return EstadoFuente(CON_AVISO, ultimo)
    return EstadoFuente(LEIDA, ultimo)


class MetarEstacion:
    """METAR de una estación y un día: del fichero del procesado si está, si no del IEM."""

    def __init__(self, datos_trafico: Path, datos_meteo: Path, metares: Metares) -> None:
        self._trafico = datos_trafico
        self._meteo = datos_meteo
        self._metares = metares
        self.peticiones = 0

    def __call__(self, estacion: str, dia: date) -> list[metar.Metar]:
        del_dia = self._metares.dia(dia)
        if del_dia:
            return del_dia.get(estacion, [])
        carpeta = self._meteo / "metar_estacion" / estacion
        if not metar_iem.ruta(carpeta, dia).exists():
            metar_iem.descargar(carpeta, dia, [estacion], metar_iem.descargador())
            self.peticiones += 1
        crudos = metar_iem.leer(carpeta, dia)
        return [metar.leer(h, t) for h, t in crudos.get(estacion, [])]


def paso_condiciones(
    almacen: Almacen,
    ahora: datetime,
    datos_trafico: Path | None = None,
    datos_meteo: Path | None = None,
    cliente: Any = None,
) -> EstadoFuente:
    datos_trafico = datos_trafico or procesado.directorio_datos()
    datos_meteo = datos_meteo or meteo.directorio_datos()
    cursor = almacen.cursor(FUENTE_CONDICIONES) or {}
    ultima = _instante(cursor.get("ultima_peticion"))
    plazo = Plazo(TOPE_CONDICIONES_S)
    try:
        cliente = cliente or meteo.Cliente(datos_meteo, meteo.descargador(plazo))
        variables = {"incidente": meteo.SUPERFICIE + meteo.PRESION, "guerra": meteo.VIENTO}

        def pedir(puntos: list[tuple[float, float]], dia: date, clave: str) -> list[Any]:
            return list(cliente.horas(puntos, dia, variables[clave], clave))

        metares = MetarEstacion(datos_trafico, datos_meteo, Metares(datos_trafico))
        resumen = mediciones.evaluar_condiciones(
            almacen, aeropuertos(), pedir, metares, ahora, plazo
        )
        registro.info("condiciones: %s", resumen.texto())
        if cliente.gastadas or metares.peticiones:
            ultima = ahora
            almacen.guardar_cursor(
                FUENTE_CONDICIONES, {**cursor, "ultima_peticion": ahora.strftime("%Y-%m-%dT%H:%MZ")}
            )
    except Exception as error:
        registro.warning("condiciones no se leen: %s", error)
        return EstadoFuente(NO_LEIDA, ultima)
    return EstadoFuente(LEIDA, ultima)
