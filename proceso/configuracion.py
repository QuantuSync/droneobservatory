"""Lectura de la configuración versionada: fuentes con su fiabilidad y vocabulario de modelos."""

import json
from pathlib import Path

from esquema import VERSION, Documento, Esquema, validador

DIRECTORIO = Path(__file__).resolve().parent.parent / "configuracion"


class ConfiguracionInvalida(ValueError):
    pass


def _leer(ruta: Path) -> Documento:
    contenido: Documento = json.loads(ruta.read_text(encoding="utf-8"))
    if contenido.get("version_esquema") != VERSION:
        raise ConfiguracionInvalida(f"{ruta.name}: versión distinta de {VERSION}")
    return contenido


def cargar_fuentes(ruta: Path = DIRECTORIO / "fuentes.json") -> list[Documento]:
    contenido = _leer(ruta)
    validador(Esquema.CONFIGURACION_FUENTES).validate(contenido)
    fuentes: list[Documento] = contenido["fuentes"]
    return fuentes


def cargar_vocabulario_modelos(ruta: Path = DIRECTORIO / "modelos_dron.json") -> frozenset[str]:
    modelos = _leer(ruta).get("modelos")
    if not isinstance(modelos, list) or not all(isinstance(m, str) and m for m in modelos):
        raise ConfiguracionInvalida(f"{ruta.name}: 'modelos' debe ser una lista de textos")
    return frozenset(modelos)
