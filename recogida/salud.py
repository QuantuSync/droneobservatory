"""Salud de la recogida horaria: cuándo terminó bien por última vez, según estado.json.

La recogida la lanza cada hora un servidor propio (servidor/), fuera de GitHub. Al salir,
cada recogida sube estado.json al bucket de las teselas (recogida/estado.py) con la hora de
la última recogida correcta. Esa hora avanza con cada recogida correcta, traiga o no datos
nuevos; la fecha de la rama estado, en cambio, no avanza cuando la base no cambia, y daba
avisos falsos.

Hay problema si la última recogida correcta tiene más de dos horas o si el fichero no
responde en tres intentos espaciados. Una recogida fallida o con avisos no es problema
mientras haya una correcta reciente.

Lo usan el workflow de tests, que lo deja en su resumen, y el workflow vigia-recogida, que
abre o cierra la incidencia con lo que escribe en su salida (`problema` y `mensaje`).

Uso: python -m recogida.salud [--url <estado.json>]
"""

import argparse
import json
import os
import sys
import time
import urllib.request
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from recogida.descarga import AGENTE_EODI

URL = "https://tiles.droneobservatory.eu/estado.json"
# La recogida es horaria: dos horas sin una correcta son dos recogidas seguidas que no lo
# han sido (o que no se han lanzado).
MAX_SIN_CORRECTA = timedelta(hours=2)
HORA = timedelta(hours=1)
# Tres intentos con un minuto entre ellos: un fallo de red o del bucket de unos segundos no
# es una caída del servidor.
INTENTOS = 3
PAUSA_S = 60.0
TOPE_S = 30.0
VARIABLE_RESUMEN = "GITHUB_STEP_SUMMARY"
VARIABLE_SALIDA = "GITHUB_OUTPUT"
ANOTACION_AVISO = "::warning::"
TITULO = "### Salud de la recogida horaria"

Estado = tuple[bool, str]
Lector = Callable[[str], bytes]


def _descargar(url: str) -> bytes:
    # Con la identificación del observatorio: al agente por defecto de Python, Cloudflare le
    # responde 403.
    cabeceras = {"Cache-Control": "no-cache", "User-Agent": AGENTE_EODI}
    peticion = urllib.request.Request(url, headers=cabeceras)
    with urllib.request.urlopen(peticion, timeout=TOPE_S) as respuesta:
        datos: bytes = respuesta.read()
        return datos


def leer_estado(
    url: str = URL,
    leer: Lector = _descargar,
    dormir: Callable[[float], None] = time.sleep,
    intentos: int = INTENTOS,
) -> dict[str, Any] | None:
    """El estado publicado, o None si no responde con un JSON en ninguno de los intentos."""
    for intento in range(intentos):
        if intento:
            dormir(PAUSA_S)
        try:
            datos = json.loads(leer(url))
        except (OSError, ValueError):
            continue
        if isinstance(datos, dict):
            return datos
    return None


def _instante(texto: Any) -> datetime | None:
    if not isinstance(texto, str):
        return None
    try:
        return datetime.fromisoformat(texto.replace("Z", "+00:00")).astimezone(UTC)
    except ValueError:
        return None


def diagnostico(estado: dict[str, Any] | None, ahora: datetime) -> Estado:
    """Si la recogida está al día y la frase que lo cuenta."""
    if estado is None:
        return False, f"estado.json no responde tras {INTENTOS} intentos espaciados."
    ultima = _instante(estado.get("ultima_correcta"))
    ultima_frase = f"La última recogida ({estado.get('resultado')}) terminó el {estado.get('fin')}"
    if ultima is None:
        return False, f"{ultima_frase} y no consta ninguna recogida correcta."
    horas = (ahora - ultima) / HORA
    frase = (
        f"{ultima_frase}; la última correcta, el {ultima:%Y-%m-%d %H:%M} UTC, hace {horas:.1f} h"
    )
    if ahora - ultima > MAX_SIN_CORRECTA:
        return False, f"{frase}: más de {MAX_SIN_CORRECTA / HORA:.0f} h."
    return True, f"{frase}."


def informar(resultado: Estado) -> None:
    """La frase en el registro, en el resumen del trabajo y en su salida."""
    al_dia, frase = resultado
    print(frase if al_dia else f"{ANOTACION_AVISO}{frase}")
    resumen = os.environ.get(VARIABLE_RESUMEN)
    if resumen:
        with Path(resumen).open("a", encoding="utf-8") as fichero:
            fichero.write(f"{TITULO}\n\n{'✅' if al_dia else '⚠️'} {frase}\n")
    salida = os.environ.get(VARIABLE_SALIDA)
    if salida:
        with Path(salida).open("a", encoding="utf-8") as fichero:
            fichero.write(f"problema={'false' if al_dia else 'true'}\nmensaje={frase}\n")


def principal(
    argumentos: list[str] | None = None,
    ahora: datetime | None = None,
    leer: Lector = _descargar,
    dormir: Callable[[float], None] = time.sleep,
) -> int:
    opciones = argparse.ArgumentParser(description=__doc__)
    opciones.add_argument("--url", default=URL)
    args = opciones.parse_args(argumentos)
    estado = leer_estado(args.url, leer, dormir)
    informar(diagnostico(estado, ahora or datetime.now(UTC)))
    return 0


if __name__ == "__main__":
    sys.exit(principal())
