"""La licencia y los créditos de los datos abiertos (configuracion/licencia_datos.json): CC BY 4.0
para la compilación del observatorio, con qué cubre, quién es el autor (con su ORCID), cómo se
cita y su dirección.

La llevan dentro los ficheros públicos del almacén (recogida/publicacion.py: miembro `licencia`
al principio del JSON, como los que se descargan de la web, y `x-amz-meta-licencia`,
`x-amz-meta-autor` y `x-amz-meta-orcid` en el objeto), las versiones citables
(recogida/versiones.py) y la exportación semanal (exportacion/semanal.py). Así los créditos viajan
con los datos cuando alguien los integra en otro sistema.
"""

import json
from datetime import UTC, datetime
from functools import cache
from pathlib import Path
from typing import Any

RUTA = Path(__file__).resolve().parent.parent / "configuracion" / "licencia_datos.json"


@cache
def cargar(ruta: Path = RUTA) -> dict[str, Any]:
    datos: dict[str, Any] = json.loads(ruta.read_text(encoding="utf-8"))
    return datos


def version_actual(momento: datetime | None = None) -> str:
    """La versión (AAAA-MM) que se cita para los datos vivos: el mes en curso, en UTC."""
    return f"{(momento or datetime.now(UTC)).astimezone(UTC):%Y-%m}"


def cita(version: str) -> dict[str, str]:
    """La cita recomendada de la versión AAAA-MM, en español y en inglés."""
    plantilla: dict[str, str] = cargar()["cita"]
    return {i: plantilla[i].format(anio=version[:4], version=version) for i in ("es", "en")}


def autor() -> dict[str, Any]:
    """El autor: nombre, cómo firma en cada idioma, ORCID y correo."""
    datos: dict[str, Any] = cargar()["autor"]
    return {c: datos[c] for c in ("nombre", "firma", "orcid", "correo")}


def miembro(version: str | None = None) -> dict[str, Any]:
    """El miembro `licencia` de un fichero JSON publicado (el mismo que pone la web)."""
    datos = cargar()
    return {
        **{c: datos[c] for c in ("nombre", "url", "titular")},
        "autor": autor(),
        "fuente": datos["fuente"],
        "alcance": datos["alcance"],
        "cita": cita(version or version_actual()),
    }


def de_version() -> dict[str, Any]:
    """La licencia del metadatos.json de una versión citable."""
    datos = cargar()
    return {c: datos[c] for c in ("nombre", "url", "titular", "alcance")}


def creditos(version: str) -> dict[str, Any]:
    """Los créditos de un conjunto de datos (exportación semanal): autor, licencia, cita y
    dirección."""
    datos = cargar()
    return {
        "titulo": datos["titular"],
        "autor": autor(),
        "licencia": {"nombre": datos["nombre"], "url": datos["url"]},
        "cita": cita(version),
        "direccion": datos["fuente"],
    }


def cabeceras() -> dict[str, str]:
    """Los metadatos del objeto en el almacén (solo ASCII, como piden las cabeceras HTTP)."""
    datos = cargar()
    return {
        "x-amz-meta-licencia": datos["nombre"],
        "x-amz-meta-licencia-url": datos["url"],
        "x-amz-meta-autor": datos["autor"]["nombre"],
        "x-amz-meta-orcid": datos["autor"]["orcid"],
    }


def con_licencia(datos: bytes, version: str | None = None) -> bytes:
    """El JSON con la licencia como primer miembro del objeto raíz (en un GeoJSON, un miembro
    ajeno que el estándar permite). Si ya la traía, se sustituye; el resto no cambia."""
    documento = json.loads(datos)
    nuevo = {
        "licencia": miembro(version),
        **{k: v for k, v in documento.items() if k != "licencia"},
    }
    return (json.dumps(nuevo, ensure_ascii=False, indent=1) + "\n").encode("utf-8")
