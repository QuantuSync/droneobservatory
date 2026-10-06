"""Reproducción de días pasados con la detección en directo, para ajustar y validar umbrales.

Cada día procesado del archivo de adsb.lol guarda sus trazas filtradas (`trazas.txt.gz`: los
puntos en tierra o por debajo de 10 000 pies a 40 km o menos de un aeropuerto con tráfico
regular, uno cada 20 s), que son justo las posiciones que la detección en directo guarda de
cada consulta. Aquí se reparten en consultas de un ciclo (80 s: la última posición de cada
aeronave en cada ciclo, como la daría la consulta en tiempo real), se pasan por
`proceso/directo.py` ciclo a ciclo y se anotan los avisos, con las líneas base del archivo,
los METAR guardados del día y las esperas y desvíos del archivo como evidencia.

Uso (en el servidor, como eodi):
    python -m recogida.directo_reproduccion AAAA-MM-DD [AAAA-MM-DD ...] [--datos DIR]
        [--salida fichero.jsonl] [--aeropuertos EKCH,EDDM]
"""

import argparse
import gzip
import itertools
import json
import logging
import sys
import time
from collections.abc import Iterator
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

from proceso import directo, metar, trafico, vuelos
from recogida import referencia
from recogida import trafico as procesado
from recogida.directo import aeropuertos_con_cierre
from recogida.mediciones import Metares

registro = logging.getLogger("recogida.directo")

# Horas del día anterior que se leen para tener la línea previa al día reproducido.
HORAS_ANTES = 4
# Horas del día siguiente que se reproducen para ver la reanudación.
HORAS_DESPUES = 8
# Umbrales holgados con que se anotan los episodios de señal: con ellos se prueban después
# umbrales más estrictos sin repetir la reproducción (`ajustar`).
HOLGADOS = directo.Umbrales(
    esperados_minimos=4.0,
    fraccion_vistos=0.2,
    persistencia_s=0,
    factor_minimo=0.5,
    esperados_previos_minimos=6.0,
)


class Episodios:
    """Los tramos seguidos de ciclos con señal holgada de cada aeropuerto: por ciclo, el
    comienzo del hueco, los vistos, los esperados, el factor y los esperados previos; y al
    cerrarse, lo que dicen los METAR desde una hora antes del comienzo."""

    def __init__(self, bases: directo.Bases, metares: directo.Metares) -> None:
        self.bases = bases
        self.metares = metares
        self.abiertos: dict[str, list[list[float]]] = {}
        self.cerrados: list[dict[str, Any]] = []

    def anotar(self, oaci: str, ahora: float, movimientos: list[float], actividad: bool) -> None:
        s, _ = directo.senal(oaci, ahora, movimientos, self.bases, HOLGADOS)
        if s is not None:
            self.abiertos.setdefault(oaci, []).append(
                [ahora, s.comienzo, s.vistos, round(s.esperados, 2), round(s.factor, 3),
                 round(s.previos, 1), int(actividad)]
            )  # fmt: skip
        elif oaci in self.abiertos:
            self.cerrar(oaci)

    def cerrar(self, oaci: str) -> None:
        minutos = self.abiertos.pop(oaci)
        desde = min(m[1] for m in minutos) - directo.MARGEN_METAR_S
        hasta = minutos[-1][0]
        motivos = metar.explica(
            self.metares(oaci, desde, hasta),
            datetime.fromtimestamp(desde, UTC),
            datetime.fromtimestamp(hasta, UTC),
        )
        self.cerrados.append({"oaci": oaci, "minutos": minutos, "metar": motivos})

    def cerrar_todos(self) -> None:
        for oaci in list(self.abiertos):
            self.cerrar(oaci)


def posiciones_dia(
    datos: Path, dia: date, desde: float, hasta: float
) -> Iterator[directo.Posicion]:
    """Las posiciones de las trazas filtradas de un día entre `desde` y `hasta`."""
    ruta = procesado.directorio_dia(datos, dia) / "trazas.txt.gz"
    if not ruta.exists():
        return
    with gzip.open(ruta, "rt", encoding="utf-8") as lineas:
        yield from _posiciones(procesado.leer_trazas(lineas), desde, hasta)


def _posiciones(
    trazas: Iterator[tuple[str, list[list[Any]]]], desde: float, hasta: float
) -> Iterator[directo.Posicion]:
    for cabecera, puntos in trazas:
        icao, tipo, marcas, categoria = [*cabecera.split(","), "", "", "", ""][:4]
        for v in puntos:
            t = float(v[0])
            if not desde <= t < hasta:
                continue
            suelo = v[3] == "S"
            yield directo.Posicion(
                icao=icao,
                t=t,
                lat=v[1] / 1e4,
                lon=v[2] / 1e4,
                alt=None if suelo or v[3] is None else float(v[3]) * 25,
                suelo=suelo,
                gs=None if v[4] is None else float(v[4]),
                rumbo=None if v[5] is None else float(v[5]),
                vz=None if v[6] is None else float(v[6]),
                tipo=tipo or None,
                categoria=categoria or None,
                marcas=int(marcas or 0),
            )


def consultas(posiciones: Iterator[directo.Posicion]) -> dict[int, list[directo.Posicion]]:
    """Por ciclo, la última posición de cada aeronave en él: lo que daría la consulta."""
    por_minuto: dict[int, dict[str, directo.Posicion]] = {}
    for p in posiciones:
        minuto = int(p.t // directo.PASO_S) + 1
        cubo = por_minuto.setdefault(minuto, {})
        anterior = cubo.get(p.icao)
        if anterior is None or p.t > anterior.t:
            cubo[p.icao] = p
    return {m: list(c.values()) for m, c in por_minuto.items()}


class Entorno:
    """Lo que la detección necesita del archivo: días, coberturas, líneas base y METAR."""

    def __init__(self, datos: Path) -> None:
        self.datos = datos
        self.dias = procesado.Dias(datos)
        self.referencias = referencia.Referencias(datos)
        self.metares = Metares(datos)
        self.aeropuertos = vuelos.cargar_aeropuertos()
        self._niveles: dict[tuple[str, date], str | None] = {}
        self.bases = directo.Bases(self._base)

    def nivel(self, oaci: str, dia: date) -> str | None:
        clave = (oaci, dia)
        if clave not in self._niveles:
            c = trafico.cobertura(oaci, dia, self.dias, self.referencias)
            self._niveles[clave] = None if c is None else c.nivel
        return self._niveles[clave]

    def _base(self, oaci: str, dia: date) -> directo.BaseDia | None:
        def valido(d: date) -> bool:
            return self.nivel(oaci, d) in (trafico.ALTA, trafico.MEDIA)

        return directo.base_dia(oaci, dia, self.dias, valido)

    def vigilados(self, dia: date) -> list[str]:
        regulares = [a.oaci for a in self.aeropuertos if a.regular]
        return directo.vigilables(dia, regulares, self.nivel, self.bases, aeropuertos_con_cierre())

    def filas(self, ahora: float) -> list[list[Any]]:
        """Esperas, desvíos y aterrizajes del archivo hasta `ahora` (de ese día y el anterior)."""
        dia = datetime.fromtimestamp(ahora, UTC).date()
        filas: list[list[Any]] = []
        for d in (dia - timedelta(days=1), dia):
            datos = self.dias(d)
            if datos is None:
                continue
            for grupo in datos.movimientos.values():
                filas += [f for f in grupo if f[1] in "HVL" and float(f[2]) <= ahora]
        return filas


def reproducir(
    entorno: Entorno, dia: date, solo: list[str] | None = None
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    inicio_reloj = time.monotonic()
    cero = trafico.inicio_dia(dia)
    vigilados = solo or entorno.vigilados(dia)
    siguiente = dia + timedelta(days=1)
    hasta = (
        cero
        + 86400
        + (HORAS_DESPUES * 3600 if procesado.procesado(entorno.datos, siguiente) else 0)
    )
    # En flujo: solo se guarda la última posición de cada aeronave en cada ciclo.
    por_minuto = consultas(
        itertools.chain(
            posiciones_dia(entorno.datos, dia - timedelta(days=1), cero - HORAS_ANTES * 3600, cero),
            posiciones_dia(entorno.datos, dia, cero, cero + 86400),
            posiciones_dia(entorno.datos, siguiente, cero + 86400, hasta),
        )
    )
    vivos = directo.Vivos(entorno.aeropuertos)
    detector = directo.Detector(entorno.bases, entorno.metares, evidencia=entorno.filas)
    episodios = Episodios(entorno.bases, entorno.metares)
    todos: dict[str, directo.Aviso] = {}
    minuto = int((cero - HORAS_ANTES * 3600) // directo.PASO_S)
    ultimo = int(hasta // directo.PASO_S)
    motivos: dict[str, int] = {}
    vistos: dict[str, int] = {}
    while minuto <= ultimo:
        ahora = float(minuto * directo.PASO_S)
        vivos.anadir(por_minuto.get(minuto, []))
        antes = len(vivos.filas)
        vivos.actualizar(ahora)
        for f in vivos.filas[antes:]:
            if f[1] in "LD" and f[6] and cero <= f[2] < cero + 86400:
                vistos[f[0]] = vistos.get(f[0], 0) + 1
        if ahora >= cero:
            # Solo se abren avisos durante el día reproducido; los abiertos se siguen después.
            lista = vigilados if ahora < cero + 86400 else [a.oaci for a in detector.avisos]
            for aviso in detector.evaluar(lista, ahora, vivos, "reproduccion"):
                todos[aviso.id] = aviso
            if ahora < cero + 86400:
                actividad = vivos.actividad(ahora)
                for oaci in vigilados:
                    episodios.anotar(oaci, ahora, vivos.movimientos(oaci), oaci in actividad)
        minuto += 1
    episodios.cerrar_todos()
    for oaci, motivo in detector.motivos.items():
        del oaci
        motivos[motivo] = motivos.get(motivo, 0) + 1
    resultado = [a.documento() for a in todos.values()]
    resumen = {
        "dia": dia.isoformat(),
        "vigilados": len(vigilados),
        "avisos": len(resultado),
        "duracion_s": round(time.monotonic() - inicio_reloj),
        "proporcion_vista": comparar(entorno, dia, vigilados, vistos),
        "motivos": motivos,
        "episodios": episodios.cerrados,
    }
    return resultado, resumen


# La reproducción es un trabajo de sesión: corre a cualquier hora, también durante la recogida
# horaria, con las normas de docs/servidor.md («Trabajos de las sesiones en el servidor»): tope de
# memoria, prioridad baja y uno por sesión, que se ponen al lanzarla con systemd-run.


def comparar(
    entorno: Entorno, dia: date, vigilados: list[str], vivos_por: dict[str, int]
) -> dict[str, float]:
    """Proporción vista en directo de los aterrizajes y despegues del archivo, por aeropuerto."""
    datos = entorno.dias(dia)
    resultado: dict[str, float] = {}
    if datos is None:
        return resultado
    for oaci in vigilados:
        archivo = len(trafico.movimientos_ifr(datos.movimientos.get(oaci, [])))
        if archivo:
            resultado[oaci] = round(vivos_por.get(oaci, 0) / archivo, 3)
    return resultado


def principal(argumentos: list[str] | None = None) -> int:
    opciones = argparse.ArgumentParser(description=__doc__)
    opciones.add_argument("dias", type=date.fromisoformat, nargs="+")
    opciones.add_argument("--datos", type=Path, default=procesado.directorio_datos())
    opciones.add_argument("--salida", type=Path)
    opciones.add_argument("--aeropuertos")
    args = opciones.parse_args(argumentos)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
    entorno = Entorno(args.datos)
    solo = args.aeropuertos.split(",") if args.aeropuertos else None
    for dia in args.dias:
        avisos, resumen = reproducir(entorno, dia, solo)
        registro.info(
            "%s",
            json.dumps({k: v for k, v in resumen.items() if k != "episodios"}, ensure_ascii=False),
        )
        for aviso in avisos:
            registro.info("  aviso %s", json.dumps(aviso, ensure_ascii=False))
        if args.salida:
            with args.salida.open("a", encoding="utf-8") as salida:
                salida.write(json.dumps({**resumen, "lista": avisos}, ensure_ascii=False) + "\n")
        entorno.bases.olvidar_antes(dia)
    return 0


if __name__ == "__main__":
    sys.exit(principal())
