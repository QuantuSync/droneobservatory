"""Salud de la recogida horaria: su última ejecución correcta y el reloj que la lanza.

GitHub retrasa o se salta ejecuciones programadas sin avisar, y una recogida que
no se lanza no deja ningún fallo a la vista. El workflow de tests pasa aquí las
últimas ejecuciones correctas de recogida.yml y las últimas de reloj.yml, y este
módulo dice en el resumen del trabajo:

- si la última recogida correcta tiene más de seis horas;
- si no hay ningún reloj en marcha ni lo ha habido en las dos últimas horas.

Solo señala: ni lanza nada ni hace fallar los tests.

Uso:
    gh run list --workflow recogida.yml --status success --limit 1 --json updatedAt > r.json
    gh run list --workflow reloj.yml --limit 20 --json status,updatedAt > j.json
    python -m recogida.salud --recogida r.json --reloj j.json
"""

import argparse
import json
import os
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

from recogida.reloj import ESTADO_TERMINADA

# La recogida es horaria: seis horas sin una ejecución correcta son ya varias perdidas
# seguidas, y es el mismo margen que se le da a una caída del extractor.
MAX_SIN_RECOGIDA = timedelta(hours=6)
# Entre un turno del reloj y el siguiente pasan segundos, y el respaldo programado mira
# cada hora si hay que arrancar uno: dos horas sin reloj son dos respaldos fallidos.
MAX_SIN_RELOJ = timedelta(hours=2)
HORA = timedelta(hours=1)
# Fichero del resumen del trabajo en GitHub Actions.
VARIABLE_RESUMEN = "GITHUB_STEP_SUMMARY"
# Prefijo con el que GitHub Actions convierte una línea del registro en una anotación.
ANOTACION_AVISO = "::warning::"
TITULO = "### Salud de la recogida horaria"

Estado = tuple[bool, str]


def ultima_correcta(texto: str) -> datetime | None:
    """Fin de la ejecución correcta más reciente, o None si no hay ninguna o no se sabe."""
    try:
        ejecuciones = json.loads(texto)
        fechas = [datetime.fromisoformat(e["updatedAt"]) for e in ejecuciones]
    except (ValueError, KeyError, TypeError):
        return None
    return max(fechas, default=None)


def estado(ultima: datetime | None, ahora: datetime) -> Estado:
    """Si la recogida está al día y la frase que lo cuenta."""
    if ultima is None:
        return False, "No se ha podido saber cuándo fue la última ejecución correcta."
    horas = (ahora - ultima) / HORA
    cuando = f"{ultima:%Y-%m-%d %H:%M} UTC, hace {horas:.1f} h"
    if ahora - ultima > MAX_SIN_RECOGIDA:
        limite = MAX_SIN_RECOGIDA / HORA
        return False, f"La última ejecución correcta terminó el {cuando}: más de {limite:.0f} h."
    return True, f"La última ejecución correcta terminó el {cuando}."


def estado_reloj(texto: str, ahora: datetime) -> Estado:
    """Si hay un reloj en marcha, o lo ha habido hace poco, y la frase que lo cuenta."""
    try:
        ejecuciones = json.loads(texto)
        en_marcha = any(e["status"] != ESTADO_TERMINADA for e in ejecuciones)
        fechas = [datetime.fromisoformat(e["updatedAt"]) for e in ejecuciones]
    except (ValueError, KeyError, TypeError):
        return False, "No se ha podido saber si el reloj de la recogida está en marcha."
    if en_marcha:
        return True, "El reloj de la recogida está en marcha."
    if not fechas:
        return False, "El reloj de la recogida no está en marcha y no consta que lo haya estado."
    horas = (ahora - max(fechas)) / HORA
    frase = f"El reloj de la recogida no está en marcha; el último acabó hace {horas:.1f} h"
    if ahora - max(fechas) > MAX_SIN_RELOJ:
        return False, f"{frase}: más de {MAX_SIN_RELOJ / HORA:.0f} h."
    return True, f"{frase}."


def informar(estados: list[Estado]) -> None:
    """Una línea por comprobación en el registro y en el resumen del trabajo."""
    lineas = []
    for al_dia, frase in estados:
        print(frase if al_dia else f"{ANOTACION_AVISO}{frase}")
        lineas.append(f"{'✅' if al_dia else '⚠️'} {frase}")
    resumen = os.environ.get(VARIABLE_RESUMEN)
    if resumen:
        with Path(resumen).open("a", encoding="utf-8") as fichero:
            fichero.write(f"{TITULO}\n\n" + "\n\n".join(lineas) + "\n")


def leer(ruta: Path) -> str:
    """El fichero de una consulta; vacío si la consulta falló y no lo dejó."""
    return ruta.read_text(encoding="utf-8") if ruta.exists() else ""


def principal(argumentos: list[str] | None = None, ahora: datetime | None = None) -> int:
    opciones = argparse.ArgumentParser(description=__doc__)
    opciones.add_argument("--recogida", type=Path, required=True)
    opciones.add_argument("--reloj", type=Path, required=True)
    args = opciones.parse_args(argumentos)
    ahora = ahora or datetime.now(UTC)
    informar([
        estado(ultima_correcta(leer(args.recogida)), ahora),
        estado_reloj(leer(args.reloj), ahora),
    ])  # fmt: skip
    return 0


if __name__ == "__main__":
    sys.exit(principal())
