"""Salud de la recogida horaria: cuándo se actualizó por última vez la rama estado.

La recogida la lanza cada hora un servidor propio (servidor/), fuera de GitHub, y una
recogida que no se lanza no deja ningún fallo a la vista. Lo que sí deja cada recogida
es la base subida a la rama estado del repositorio de datos: el workflow de tests pasa
aquí la fecha del último commit de esa rama y este módulo dice en el resumen del
trabajo si tiene más de dos horas.

Solo señala: ni lanza nada ni hace fallar los tests.

Uso:
    git -C <clon de la rama estado> log -1 --format=%cI > estado.txt
    python -m recogida.salud --estado estado.txt
"""

import argparse
import os
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

# La recogida es horaria y sube la base en cada ejecución: dos horas sin commit nuevo
# son ya dos recogidas seguidas que no han llegado a subirla.
MAX_SIN_ESTADO = timedelta(hours=2)
HORA = timedelta(hours=1)
# Fichero del resumen del trabajo en GitHub Actions.
VARIABLE_RESUMEN = "GITHUB_STEP_SUMMARY"
# Prefijo con el que GitHub Actions convierte una línea del registro en una anotación.
ANOTACION_AVISO = "::warning::"
TITULO = "### Salud de la recogida horaria"

Estado = tuple[bool, str]


def ultimo_estado(texto: str) -> datetime | None:
    """Fecha del último commit de la rama estado, o None si no se sabe."""
    try:
        fecha = datetime.fromisoformat(texto.strip())
    except ValueError:
        return None
    # Una fecha sin zona no se puede comparar con la hora actual.
    return fecha.astimezone(UTC) if fecha.tzinfo else None


def estado(ultimo: datetime | None, ahora: datetime) -> Estado:
    """Si la recogida está al día y la frase que lo cuenta."""
    if ultimo is None:
        return False, "No se ha podido saber cuándo se actualizó por última vez la rama estado."
    horas = (ahora - ultimo) / HORA
    frase = f"La rama estado se actualizó por última vez el {ultimo:%Y-%m-%d %H:%M} UTC"
    frase = f"{frase}, hace {horas:.1f} h"
    if ahora - ultimo > MAX_SIN_ESTADO:
        return False, f"{frase}: más de {MAX_SIN_ESTADO / HORA:.0f} h."
    return True, f"{frase}."


def informar(resultado: Estado) -> None:
    """La frase en el registro y en el resumen del trabajo."""
    al_dia, frase = resultado
    print(frase if al_dia else f"{ANOTACION_AVISO}{frase}")
    resumen = os.environ.get(VARIABLE_RESUMEN)
    if resumen:
        with Path(resumen).open("a", encoding="utf-8") as fichero:
            fichero.write(f"{TITULO}\n\n{'✅' if al_dia else '⚠️'} {frase}\n")


def leer(ruta: Path) -> str:
    """El fichero de la consulta; vacío si la consulta falló y no lo dejó."""
    return ruta.read_text(encoding="utf-8") if ruta.exists() else ""


def principal(argumentos: list[str] | None = None, ahora: datetime | None = None) -> int:
    opciones = argparse.ArgumentParser(description=__doc__)
    opciones.add_argument("--estado", type=Path, required=True)
    args = opciones.parse_args(argumentos)
    informar(estado(ultimo_estado(leer(args.estado)), ahora or datetime.now(UTC)))
    return 0


if __name__ == "__main__":
    sys.exit(principal())
