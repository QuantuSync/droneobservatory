"""Salud de la recogida horaria: cuándo terminó bien por última vez, según estado.json.

La recogida la lanza cada hora un servidor propio (servidor/), fuera de GitHub. Al salir,
cada recogida sube estado.json al almacén público (recogida/estado.py) con la hora de
la última recogida correcta. Esa hora avanza con cada recogida correcta, traiga o no datos
nuevos; la fecha de la rama estado, en cambio, no avanza cuando la base no cambia, y daba
avisos falsos.

Hay problema si la última recogida correcta tiene más de dos horas o si el fichero no
responde en tres intentos espaciados. Una recogida fallida o con avisos no es problema
mientras haya una correcta reciente.

Aparte, la exportación semanal para AEGIS: hay problema si la última correcta
(ultima_exportacion) tiene más de 8 días o no consta ninguna. Si estado.json no responde o
aún no trae el campo, eso lo cuenta la comprobación de la recogida y aquí no se avisa.

Y la detección en directo de cierres (recogida/directo.py), que publica directo.json cada
minuto: hay problema si su última publicación tiene más de media hora o si no responde.

Y la captura del seguimiento en directo (recogida/seguimiento.py), por `seguimiento` de
estado.json: hay problema si no está en marcha (más de 10 minutos sin un heartbeat del flujo de
NEPTUN cuando se compuso el estado) o si en las dos últimas horas ha habido un hueco de más de 10
minutos (el servicio lo anota al reconectar, también tras estar parado). Si estado.json no
responde o aún no trae el campo, aquí no se avisa.

Lo usan el workflow de tests, que lo deja en su resumen, y el workflow vigia-recogida, que
abre o cierra las incidencias con lo que escribe en su salida (`problema` y `mensaje` de la
recogida; `problema_exportacion` y `mensaje_exportacion` de la exportación;
`problema_directo` y `mensaje_directo` de la detección en directo; `problema_seguimiento` y
`mensaje_seguimiento` de la captura del seguimiento).

Uso: python -m recogida.salud [--url <estado.json>] [--url-directo <directo.json>]
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

from recogida import almacen_publico
from recogida.descarga import AGENTE_EODI

# La dirección pública de estado.json sale de configuracion/almacen_publico.json.
_ALMACEN = almacen_publico.cargar()
URL = _ALMACEN.url_publica(_ALMACEN.objetos["estado"])
URL_DIRECTO = _ALMACEN.url_publica(_ALMACEN.objetos["directo"])
# La detección en directo publica directo.json cada minuto: media hora sin publicar es que el
# servicio se ha parado (systemd lo relanza a los 30 s si se cae).
MAX_SIN_DIRECTO = timedelta(minutes=30)
TITULO_DIRECTO = "### Detección en directo"
TITULO_SEGUIMIENTO = "### Captura del seguimiento en directo"
# Un hueco largo cuenta como problema durante dos horas: lo ve al menos una pasada del vigía
# (minuto 41) con el estado de la recogida siguiente (hacia el minuto 33).
HUECO_RECIENTE = timedelta(hours=2)
# La recogida es horaria: dos horas sin una correcta son dos recogidas seguidas que no lo
# han sido (o que no se han lanzado).
MAX_SIN_CORRECTA = timedelta(hours=2)
# La exportación es semanal: ocho días dan un día de margen sobre el lunes siguiente.
MAX_SIN_EXPORTACION = timedelta(days=8)
DIA = timedelta(days=1)
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
TITULO_EXPORTACION = "### Exportación semanal"

Estado = tuple[bool, str]
Lector = Callable[[str], bytes]


def _descargar(url: str) -> bytes:
    # Con la identificación del observatorio, como todos los lectores.
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


def diagnostico_exportacion(estado: dict[str, Any] | None, ahora: datetime) -> Estado:
    """Si la exportación semanal está al día y la frase que lo cuenta."""
    if estado is None or "ultima_exportacion" not in estado:
        return True, "estado.json no informa de la exportación semanal: no se comprueba."
    ultima = _instante(estado.get("ultima_exportacion"))
    if ultima is None:
        return False, "No consta ninguna exportación semanal correcta."
    dias = (ahora - ultima) / DIA
    frase = (
        f"La última exportación semanal correcta terminó el {ultima:%Y-%m-%d %H:%M} UTC, "
        f"hace {dias:.1f} días"
    )
    if ahora - ultima > MAX_SIN_EXPORTACION:
        return False, f"{frase}: más de {MAX_SIN_EXPORTACION / DIA:.0f} días."
    return True, f"{frase}."


def diagnostico_directo(directo: dict[str, Any] | None, ahora: datetime) -> Estado:
    """Si la detección en directo publica (directo.json reciente) y la frase que lo cuenta."""
    if directo is None:
        return False, f"directo.json no responde tras {INTENTOS} intentos espaciados."
    generado = _instante(directo.get("generado"))
    if generado is None:
        return False, "directo.json no dice cuándo se generó."
    minutos = (ahora - generado).total_seconds() / 60
    frase = (
        f"La detección en directo publicó por última vez el {generado:%Y-%m-%d %H:%M} UTC, "
        f"hace {minutos:.0f} min, con {directo.get('fuente')}"
    )
    if ahora - generado > MAX_SIN_DIRECTO:
        return False, f"{frase}: más de {MAX_SIN_DIRECTO.total_seconds() / 60:.0f} min."
    return True, f"{frase}."


def diagnostico_seguimiento(estado: dict[str, Any] | None, ahora: datetime) -> Estado:
    """Si la captura del seguimiento recibe el flujo y la frase que lo cuenta."""
    if estado is None or not isinstance(estado.get("seguimiento"), dict):
        return True, "estado.json no informa de la captura del seguimiento: no se comprueba."
    seguimiento: dict[str, Any] = estado["seguimiento"]
    situacion = seguimiento.get("estado")
    latido = _instante(seguimiento.get("ultimo_latido"))
    como = str(situacion).replace("_", " ")
    frase = f"La captura del seguimiento estaba {como} el {estado.get('fin')}"
    frase += f"; último heartbeat el {latido:%Y-%m-%d %H:%M} UTC" if latido else "; sin heartbeat"
    hueco = seguimiento.get("ultimo_hueco_largo")
    hasta = _instante(hueco.get("hasta")) if isinstance(hueco, dict) else None
    if situacion != "en_marcha":
        return False, f"{frase}: más de 10 minutos sin heartbeat del flujo de NEPTUN."
    if hasta is not None and ahora - hasta <= HUECO_RECIENTE:
        assert isinstance(hueco, dict)
        return False, (
            f"{frase}, pero estuvo sin datos del flujo de {hueco.get('desde')} a "
            f"{hueco.get('hasta')}: más de 10 minutos."
        )
    return True, f"{frase}."


def informar(resultado: Estado, titulo: str = TITULO, sufijo: str = "") -> None:
    """La frase en el registro, en el resumen del trabajo y en su salida."""
    al_dia, frase = resultado
    print(frase if al_dia else f"{ANOTACION_AVISO}{frase}")
    resumen = os.environ.get(VARIABLE_RESUMEN)
    if resumen:
        with Path(resumen).open("a", encoding="utf-8") as fichero:
            fichero.write(f"{titulo}\n\n{'✅' if al_dia else '⚠️'} {frase}\n")
    salida = os.environ.get(VARIABLE_SALIDA)
    if salida:
        with Path(salida).open("a", encoding="utf-8") as fichero:
            problema = "false" if al_dia else "true"
            fichero.write(f"problema{sufijo}={problema}\nmensaje{sufijo}={frase}\n")


def principal(
    argumentos: list[str] | None = None,
    ahora: datetime | None = None,
    leer: Lector = _descargar,
    dormir: Callable[[float], None] = time.sleep,
) -> int:
    opciones = argparse.ArgumentParser(description=__doc__)
    opciones.add_argument("--url", default=URL)
    opciones.add_argument("--url-directo", default=URL_DIRECTO)
    args = opciones.parse_args(argumentos)
    estado = leer_estado(args.url, leer, dormir)
    momento = ahora or datetime.now(UTC)
    informar(diagnostico(estado, momento))
    informar(diagnostico_exportacion(estado, momento), TITULO_EXPORTACION, "_exportacion")
    directo = leer_estado(args.url_directo, leer, dormir)
    informar(diagnostico_directo(directo, momento), TITULO_DIRECTO, "_directo")
    informar(diagnostico_seguimiento(estado, momento), TITULO_SEGUIMIENTO, "_seguimiento")
    return 0


if __name__ == "__main__":
    sys.exit(principal())
