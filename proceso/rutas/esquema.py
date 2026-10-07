"""Esquemas de los ficheros publicados de las rutas (esquema/rutas/1.1.0)."""

import json
from functools import cache
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

DIRECTORIO = Path(__file__).resolve().parent.parent.parent / "esquema" / "rutas" / "1.1.0"


class RutaInvalida(ValueError):
    pass


@cache
def validador(nombre: str) -> Draft202012Validator:
    esquema = json.loads((DIRECTORIO / f"{nombre}.schema.json").read_text(encoding="utf-8"))
    return Draft202012Validator(esquema)


def validar(nombre: str, documento: Any) -> None:
    errores = sorted(validador(nombre).iter_errors(documento), key=str)
    if errores:
        raise RutaInvalida(f"{nombre}: {errores[0].message} en {list(errores[0].absolute_path)}")
