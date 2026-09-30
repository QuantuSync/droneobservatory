"""Reloj propio de la recogida horaria.

GitHub se salta la mayoría de las ejecuciones programadas (del 28 al 30 de
septiembre de 2026 lanzó 10 de 62), pero las lanzadas a demanda no se pierden.
El workflow reloj.yml mantiene un trabajo en marcha que espera al minuto 17 de
cada hora y lanza recogida.yml a demanda. Un trabajo no puede durar más de seis
horas, así que el reloj va por turnos: el turno hace sus lanzamientos y, justo
después del último, lanza el turno siguiente y termina.

- `guardia` decide si la ejecución arranca un turno. Lanzada a demanda (a mano
  o como relevo de otro turno), sí; la programada de respaldo, solo si no hay
  ningún otro reloj en marcha o en cola.
- `turno` espera y lanza. Antes de cada lanzamiento comprueba que no haya ya
  una recogida en cola o en marcha; si la hay, no lanza otra.

Uso:
    python -m recogida.reloj guardia --evento <schedule|workflow_dispatch>
    python -m recogida.reloj turno
"""

import argparse
import json
import logging
import os
import subprocess
import sys
import time
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path

registro = logging.getLogger("reloj")

RECOGIDA = "recogida.yml"
RELOJ = "reloj.yml"
RAMA = "main"
# El minuto de la recogida: el mismo que su programación, lejos del pico de las horas en
# punto.
MINUTO_LANZAMIENTO = 17
ENTRE_LANZAMIENTOS = timedelta(hours=1)
# Un trabajo alojado por GitHub se corta a las seis horas. Cinco y media dejan margen
# para el arranque y para el relevo, y el workflow pone su propio tope algo por encima.
DURACION_TURNO = timedelta(hours=5, minutes=30)
ESTADO_TERMINADA = "completed"
EVENTO_PROGRAMADO = "schedule"
# Ejecuciones recientes que se miran para saber si hay alguna sin terminar: las que no
# han terminado son siempre las últimas, y de un workflow no hay más de dos o tres a la vez.
MAX_EJECUCIONES = 20
# Una orden que falla se repite dos veces más, con 10 s entre intentos: basta para un
# tropiezo de la API y no retrasa el lanzamiento más de medio minuto.
INTENTOS = 3
ESPERA_ENTRE_INTENTOS_S = 10.0
# Variables que pone GitHub Actions: la ejecución en curso y el fichero de salidas del paso.
VARIABLE_EJECUCION = "GITHUB_RUN_ID"
VARIABLE_SALIDAS = "GITHUB_OUTPUT"
SALIDA_ARRANCAR = "arrancar"

Orden = Callable[[list[str]], str]


class OrdenFallida(RuntimeError):
    pass


def gh(argumentos: list[str]) -> str:
    """Ejecuta la herramienta de línea de órdenes de GitHub y devuelve su salida."""
    resultado = subprocess.run(["gh", *argumentos], capture_output=True, text=True, check=False)
    if resultado.returncode != 0:
        motivo = (resultado.stderr.strip().splitlines() or ["sin mensaje"])[0]
        raise OrdenFallida(f"gh {argumentos[0]} {argumentos[1]}: {motivo}")
    return resultado.stdout


class Actions:
    """Lo que el reloj necesita de GitHub Actions: qué hay sin terminar y lanzar."""

    def __init__(
        self,
        orden: Orden = gh,
        dormir: Callable[[float], None] = time.sleep,
        propia: str | None = None,
    ) -> None:
        self._orden = orden
        self._dormir = dormir
        # La ejecución que pregunta no cuenta como «otra en marcha».
        self._propia = propia

    def _insistir(self, argumentos: list[str]) -> str:
        for _ in range(INTENTOS - 1):
            try:
                return self._orden(argumentos)
            except OrdenFallida:
                self._dormir(ESPERA_ENTRE_INTENTOS_S)
        return self._orden(argumentos)

    def sin_terminar(self, workflow: str) -> int:
        """Ejecuciones del workflow en cola o en marcha, sin contar la propia."""
        limite = str(MAX_EJECUCIONES)
        salida = self._insistir(
            [
                "run",
                "list",
                "--workflow",
                workflow,
                "--limit",
                limite,
                "--json",
                "databaseId,status",
            ]
        )
        return sum(
            1
            for ejecucion in json.loads(salida)
            if ejecucion["status"] != ESTADO_TERMINADA
            and str(ejecucion["databaseId"]) != self._propia
        )

    def lanzar(self, workflow: str) -> None:
        self._insistir(["workflow", "run", workflow, "--ref", RAMA])


def lanzamientos(inicio: datetime, duracion: timedelta = DURACION_TURNO) -> list[datetime]:
    """Las horas de lanzamiento de un turno que empieza en `inicio`."""
    hora = inicio.replace(minute=MINUTO_LANZAMIENTO, second=0, microsecond=0)
    if hora < inicio:
        hora += ENTRE_LANZAMIENTOS
    horas = []
    while hora <= inicio + duracion:
        horas.append(hora)
        hora += ENTRE_LANZAMIENTOS
    return horas


def guardia(actions: Actions, evento: str) -> bool:
    """Si esta ejecución del reloj tiene que arrancar un turno."""
    if evento != EVENTO_PROGRAMADO:
        return True
    try:
        otros = actions.sin_terminar(RELOJ)
    except OrdenFallida as error:
        # Sin saber si hay otro reloj no se arranca: la siguiente hora lo vuelve a mirar.
        registro.warning("no se sabe si hay otro reloj: %s", error)
        return False
    registro.info("relojes en marcha o en cola: %d", otros)
    return otros == 0


def lanzar_recogida(actions: Actions) -> bool:
    """Lanza la recogida si no hay ya una en cola o en marcha. True si la lanza."""
    try:
        if actions.sin_terminar(RECOGIDA):
            registro.info("ya hay una recogida en cola o en marcha: no se lanza otra")
            return False
    except OrdenFallida as error:
        # Si hubiera una en marcha, el grupo de concurrencia de la recogida pone esta a la cola.
        registro.warning("no se sabe si hay una recogida en marcha, se lanza: %s", error)
    try:
        actions.lanzar(RECOGIDA)
    except OrdenFallida as error:
        registro.warning("recogida sin lanzar: %s", error)
        return False
    registro.info("recogida lanzada")
    return True


def turno(
    actions: Actions,
    reloj: Callable[[], datetime] = lambda: datetime.now(UTC),
    dormir: Callable[[float], None] = time.sleep,
    duracion: timedelta = DURACION_TURNO,
) -> int:
    """Un turno: los lanzamientos de sus horas y, tras el último, el relevo.

    El relevo sale justo después de un lanzamiento, así el turno siguiente tiene casi
    una hora para arrancar antes de su primera recogida y no se pierde ninguna.
    """
    horas = lanzamientos(reloj(), duracion)
    registro.info("turno con lanzamientos a las %s", ", ".join(f"{h:%H:%M}" for h in horas))
    for hora in horas:
        while (falta := (hora - reloj()).total_seconds()) > 0:
            dormir(falta)
        lanzar_recogida(actions)
    try:
        actions.lanzar(RELOJ)
    except OrdenFallida as error:
        # Sin relevo no hay reloj hasta que lo arranque la programación de respaldo.
        registro.error("relevo sin lanzar: %s", error)
        return 1
    registro.info("relevo lanzado")
    return 0


def principal(argumentos: list[str] | None = None) -> int:
    opciones = argparse.ArgumentParser(description=__doc__)
    ordenes = opciones.add_subparsers(dest="orden", required=True)
    o_guardia = ordenes.add_parser("guardia")
    o_guardia.add_argument("--evento", required=True, help="evento que lanzó la ejecución")
    ordenes.add_parser("turno")
    args = opciones.parse_args(argumentos)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
    actions = Actions(propia=os.environ.get(VARIABLE_EJECUCION))
    if args.orden == "turno":
        return turno(actions)
    arrancar = "true" if guardia(actions, args.evento) else "false"
    registro.info("%s=%s", SALIDA_ARRANCAR, arrancar)
    salidas = os.environ.get(VARIABLE_SALIDAS)
    if salidas:
        with Path(salidas).open("a", encoding="utf-8") as fichero:
            fichero.write(f"{SALIDA_ARRANCAR}={arrancar}\n")
    return 0


if __name__ == "__main__":
    sys.exit(principal())
