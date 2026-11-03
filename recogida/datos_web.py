"""Los ficheros de la descarga abierta de la web (droneobservatory.eu/datos/…), en una sola versión.

Los usa el paquete trimestral de Discuss Data (recogida/discuss_data.py): baja `resumen.json`, los
ficheros y otra vez `resumen.json`, y los da por buenos solo si las dos lecturas del resumen dan la
misma hora de actualización (si una recogida publica en medio, se repite, como mucho INTENTOS
veces, con un minuto de espera).
"""

import json
import logging
import urllib.request
from collections.abc import Callable, Iterable
from typing import Any

from recogida.descarga import AGENTE_EODI

registro = logging.getLogger("datos_web")

ORIGEN = "https://droneobservatory.eu"
RESUMEN = "resumen.json"
INTENTOS = 3
TOPE_S = 120.0

Leer = Callable[[str], bytes]


class DatosCambiantes(RuntimeError):
    """Los datos de la web cambiaron en cada intento mientras se bajaban."""


def leer_http(url: str) -> bytes:
    peticion = urllib.request.Request(
        url, headers={"User-Agent": AGENTE_EODI, "Cache-Control": "no-cache"}
    )
    with urllib.request.urlopen(peticion, timeout=TOPE_S) as respuesta:
        datos: bytes = respuesta.read()
        return datos


def bajar_version(
    leer: Leer,
    ficheros: Iterable[str],
    dormir: Callable[[float], None],
    origen: str = ORIGEN,
) -> tuple[dict[str, Any], dict[str, bytes]]:
    """El resumen y los ficheros de una misma versión de los datos de la web."""
    base = origen.rstrip("/") + "/datos/"
    nombres = list(ficheros)
    for intento in range(INTENTOS):
        if intento:
            dormir(60.0)
        antes = json.loads(leer(base + RESUMEN))
        bajados = {nombre: leer(base + nombre) for nombre in nombres}
        despues = json.loads(leer(base + RESUMEN))
        if antes.get("actualizado") == despues.get("actualizado"):
            return despues, bajados
        registro.info("los datos de la web cambiaron mientras se bajaban: se repite")
    raise DatosCambiantes("los datos de la web cambiaron en cada intento")
