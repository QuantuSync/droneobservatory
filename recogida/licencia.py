"""La licencia y los créditos de los datos abiertos (configuracion/licencia_datos.json): CC BY 4.0
para la compilación del observatorio, con qué cubre, quién es el autor (con su ORCID), cómo se
cita y su dirección.

La llevan dentro los ficheros públicos del almacén (recogida/publicacion.py: miembro `licencia`
al principio del JSON, como los que se descargan de la web, y `x-amz-meta-licencia`,
`x-amz-meta-autor` y `x-amz-meta-orcid` en el objeto) y la exportación semanal
(exportacion/semanal.py). Así los créditos viajan con los datos cuando alguien los integra en otro
sistema.
"""

import json
import os
from datetime import UTC, datetime
from functools import cache
from pathlib import Path
from typing import Any

RUTA = Path(__file__).resolve().parent.parent / "configuracion" / "licencia_datos.json"
# El correo de contacto del autor no está en el repositorio: lo da esta variable (en el servidor, su
# configuración). Sin ella, el autor va sin correo (y la exportación para AEGIS, que lo exige,
# falla).
VARIABLE_CORREO = "EODI_CORREO_AUTOR"


@cache
def cargar(ruta: Path = RUTA) -> dict[str, Any]:
    datos: dict[str, Any] = json.loads(ruta.read_text(encoding="utf-8"))
    return datos


ARCHIVADAS = RUTA.parent / "versiones_archivadas.json"


def doi_archivado() -> str:
    """El DOI de la versión archivada más reciente (la primera de
    configuracion/versiones_archivadas.json): la única forma de citar los datos desde que se
    retiraron las versiones mensuales (3 de noviembre de 2026)."""
    versiones: list[dict[str, Any]] = json.loads(ARCHIVADAS.read_text(encoding="utf-8"))[
        "versiones"
    ]
    return str(versiones[0]["doi"])


def cita(actualizado: datetime | None = None) -> dict[str, str]:
    """La cita de los datos vivos (del año de `actualizado`, ahora si no se da), en español y en
    inglés: son los datos vivos a la fecha de actualización del fichero y, para citarlos, se usa
    el DOI de la versión archivada más reciente. Sin la fecha dentro: un fichero que no cambia
    tiene la misma huella y no se vuelve a subir (recogida/publicacion.py)."""
    momento = (actualizado or datetime.now(UTC)).astimezone(UTC)
    plantilla: dict[str, str] = cargar()["cita"]
    return {i: plantilla[i].format(anio=momento.year, doi=doi_archivado()) for i in ("es", "en")}


def autor() -> dict[str, Any]:
    """El autor: nombre, cómo firma en cada idioma, ORCID y correo."""
    datos: dict[str, Any] = cargar()["autor"]
    resultado = {c: datos[c] for c in ("nombre", "firma", "orcid")}
    correo = os.environ.get(VARIABLE_CORREO, "").strip()
    if correo:
        resultado["correo"] = correo
    return resultado


def miembro(actualizado: datetime | None = None) -> dict[str, Any]:
    """El miembro `licencia` de un fichero JSON publicado (el mismo que pone la web)."""
    datos = cargar()
    return {
        **{c: datos[c] for c in ("nombre", "url", "titular")},
        "autor": autor(),
        "fuente": datos["fuente"],
        "alcance": datos["alcance"],
        "cita": cita(actualizado),
    }


def creditos(actualizado: datetime) -> dict[str, Any]:
    """Los créditos de un conjunto de datos (exportación semanal): autor, licencia, cita y
    dirección."""
    datos = cargar()
    return {
        "titulo": datos["titular"],
        "autor": autor(),
        "licencia": {"nombre": datos["nombre"], "url": datos["url"]},
        "cita": cita(actualizado),
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


def con_licencia(datos: bytes, actualizado: datetime | None = None) -> bytes:
    """El JSON con la licencia como primer miembro del objeto raíz (en un GeoJSON, un miembro
    ajeno que el estándar permite). Si ya la traía, se sustituye; el resto no cambia."""
    documento = json.loads(datos)
    nuevo = {
        "licencia": miembro(actualizado),
        **{k: v for k, v in documento.items() if k != "licencia"},
    }
    return (json.dumps(nuevo, ensure_ascii=False, indent=1) + "\n").encode("utf-8")
