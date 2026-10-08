"""La licencia de los datos abiertos (configuracion/licencia_datos.json): CC BY 4.0 para la
compilación del observatorio, con qué cubre y cómo se cita.

La llevan dentro los ficheros públicos del almacén (recogida/publicacion.py: miembro `licencia`
al principio del JSON, como los que se descargan de la web, y `x-amz-meta-licencia` en el objeto)
y las versiones citables (recogida/versiones.py).
"""

import json
from functools import cache
from pathlib import Path
from typing import Any

RUTA = Path(__file__).resolve().parent.parent / "configuracion" / "licencia_datos.json"


@cache
def cargar(ruta: Path = RUTA) -> dict[str, Any]:
    datos: dict[str, Any] = json.loads(ruta.read_text(encoding="utf-8"))
    return datos


def miembro() -> dict[str, Any]:
    """El miembro `licencia` de un fichero JSON publicado (el mismo que pone la web)."""
    datos = cargar()
    return {c: datos[c] for c in ("nombre", "url", "titular", "fuente", "alcance", "cita")}


def de_version() -> dict[str, Any]:
    """La licencia del metadatos.json de una versión citable."""
    datos = cargar()
    return {c: datos[c] for c in ("nombre", "url", "titular", "alcance")}


def cabeceras() -> dict[str, str]:
    """Los metadatos del objeto en el almacén (solo ASCII, como piden las cabeceras HTTP)."""
    datos = cargar()
    return {"x-amz-meta-licencia": datos["nombre"], "x-amz-meta-licencia-url": datos["url"]}


def con_licencia(datos: bytes) -> bytes:
    """El JSON con la licencia como primer miembro del objeto raíz (en un GeoJSON, un miembro
    ajeno que el estándar permite). Si ya la traía, se sustituye; el resto no cambia."""
    documento = json.loads(datos)
    nuevo = {"licencia": miembro(), **{k: v for k, v in documento.items() if k != "licencia"}}
    return (json.dumps(nuevo, ensure_ascii=False, indent=1) + "\n").encode("utf-8")
