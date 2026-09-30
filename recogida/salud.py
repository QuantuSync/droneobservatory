"""Salud de la recogida horaria: cuánto hace de su última ejecución correcta.

GitHub retrasa o se salta ejecuciones programadas sin avisar, y una recogida que
no se lanza no deja ningún fallo a la vista. El workflow de tests pasa aquí las
últimas ejecuciones correctas de recogida.yml y este módulo dice, en el resumen
del trabajo, si la última tiene más de seis horas. Solo señala: ni lanza la
recogida ni hace fallar los tests.

Uso:
    gh run list --workflow recogida.yml --status success --limit 1 --json updatedAt \\
        | python -m recogida.salud
"""

import json
import os
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

# La recogida es horaria: seis horas sin una ejecución correcta son ya varias perdidas
# seguidas, y es el mismo margen que se le da a una caída del extractor.
MAX_SIN_RECOGIDA = timedelta(hours=6)
HORA = timedelta(hours=1)
# Fichero del resumen del trabajo en GitHub Actions.
VARIABLE_RESUMEN = "GITHUB_STEP_SUMMARY"
# Prefijo con el que GitHub Actions convierte una línea del registro en una anotación.
ANOTACION_AVISO = "::warning::"
TITULO = "### Salud de la recogida horaria"


def ultima_correcta(texto: str) -> datetime | None:
    """Fin de la ejecución correcta más reciente, o None si no hay ninguna o no se sabe."""
    try:
        ejecuciones = json.loads(texto)
        fechas = [datetime.fromisoformat(e["updatedAt"]) for e in ejecuciones]
    except (ValueError, KeyError, TypeError):
        return None
    return max(fechas, default=None)


def estado(ultima: datetime | None, ahora: datetime) -> tuple[bool, str]:
    """Si la recogida está al día y la frase que lo cuenta."""
    if ultima is None:
        return False, "No se ha podido saber cuándo fue la última ejecución correcta."
    horas = (ahora - ultima) / HORA
    cuando = f"{ultima:%Y-%m-%d %H:%M} UTC, hace {horas:.1f} h"
    if ahora - ultima > MAX_SIN_RECOGIDA:
        limite = MAX_SIN_RECOGIDA / HORA
        return False, f"La última ejecución correcta terminó el {cuando}: más de {limite:.0f} h."
    return True, f"La última ejecución correcta terminó el {cuando}."


def principal(entrada: str, ahora: datetime) -> int:
    al_dia, frase = estado(ultima_correcta(entrada), ahora)
    print(frase if al_dia else f"{ANOTACION_AVISO}{frase}")
    resumen = os.environ.get(VARIABLE_RESUMEN)
    if resumen:
        marca = "✅" if al_dia else "⚠️"
        with Path(resumen).open("a", encoding="utf-8") as fichero:
            fichero.write(f"{TITULO}\n\n{marca} {frase}\n")
    return 0


if __name__ == "__main__":
    sys.exit(principal(sys.stdin.read(), datetime.now(UTC)))
