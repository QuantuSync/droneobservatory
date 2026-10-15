"""Nombres de los buckets privados.

Los buckets privados no llevan su nombre en configuracion/ (el repositorio es público): su
configuración dice en qué variable está (bucket_variable) y el valor sale del entorno o, si no
está, del fichero buckets.env de la carpeta de secretos (EODI_SECRETOS o ~/.eodi), con una línea
VARIABLE=nombre por bucket. Los públicos llevan el nombre en claro (bucket).
"""

import os
import sys
from pathlib import Path
from typing import Any

VARIABLE_SECRETOS = "EODI_SECRETOS"
FICHERO = "buckets.env"


def _casa() -> Path:
    if sys.platform != "win32":
        import pwd

        return Path(pwd.getpwuid(os.getuid()).pw_dir)
    return Path.home()


def variables() -> dict[str, str]:
    ruta = Path(os.environ.get(VARIABLE_SECRETOS) or _casa() / ".eodi") / FICHERO
    try:
        lineas = ruta.read_text(encoding="utf-8").splitlines()
    except OSError:
        return {}
    valores = {}
    for linea in lineas:
        nombre, igual, valor = linea.strip().partition("=")
        if igual and nombre and not nombre.startswith("#"):
            valores[nombre.strip()] = valor.strip().strip("\"'")
    return valores


def nombre(datos: dict[str, Any]) -> str:
    """El bucket de una configuración de configuracion/: en claro o por su variable."""
    if datos.get("bucket"):
        return str(datos["bucket"])
    variable = str(datos["bucket_variable"])
    valor = os.environ.get(variable) or variables().get(variable)
    if not valor:
        raise RuntimeError(f"falta el nombre del bucket: variable {variable} o {FICHERO}")
    return valor
