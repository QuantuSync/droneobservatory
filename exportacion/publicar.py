"""Escribe los ficheros públicos (ucrania.json e incidentes.geojson) a partir de la base."""

from datetime import datetime
from pathlib import Path

from almacen.base import Almacen
from exportacion.geojson import exportar
from exportacion.proyeccion import escribir
from exportacion.ucrania import exportar_ucrania
from proceso.configuracion import cargar_vocabulario_modelos

DIRECTORIO = Path(__file__).resolve().parent.parent / "publicacion"
UCRANIA = "ucrania.json"
INCIDENTES = "incidentes.geojson"


def modelos(almacen: Almacen) -> frozenset[str]:
    """El vocabulario de modelos de la configuración más el que ha crecido con el uso."""
    return cargar_vocabulario_modelos() | frozenset(almacen.vocabulario("modelo_dron"))


def publicar(almacen: Almacen, ahora: datetime, directorio: Path = DIRECTORIO) -> list[Path]:
    """Regenera los dos ficheros y devuelve los que han cambiado."""
    directorio.mkdir(parents=True, exist_ok=True)
    documentos = {
        UCRANIA: exportar_ucrania(almacen.ataques_ucrania(), ahora),
        INCIDENTES: exportar(almacen.incidentes(), ahora, modelos(almacen)),
    }
    cambiados = []
    for nombre, documento in documentos.items():
        ruta = directorio / nombre
        anterior = ruta.read_bytes() if ruta.exists() else None
        escribir(documento, ruta)
        if ruta.read_bytes() != anterior:
            cambiados.append(ruta)
    return cambiados
