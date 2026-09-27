"""Piezas comunes de las exportaciones públicas: proyección sobre una lista cerrada y fuentes."""

import copy
import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from esquema import Documento
from proceso.estados import Capa
from proceso.validaciones import fiabilidad_interna


class ExportacionInvalida(ValueError):
    pass


def fuente_publica(fuente: Documento, capa: Capa) -> bool:
    """Una fuente sale a la web solo si está marcada pública y no es interna por regla."""
    interna_en_esta_capa = capa is Capa.GENERAL and fuente.get("interna_fuera_de_ucrania", False)
    return (
        fuente.get("publica") is True
        and not fiabilidad_interna(fuente["fiabilidad"])
        and not interna_en_esta_capa
    )


def rutas(valor: Any, ruta: str = "") -> Iterator[str]:
    """Todas las rutas de claves de un documento, con "[]" para elementos de lista."""
    if isinstance(valor, dict):
        for clave, hijo in valor.items():
            sub = f"{ruta}.{clave}" if ruta else clave
            yield sub
            yield from rutas(hijo, sub)
    elif isinstance(valor, list):
        for hijo in valor:
            yield from rutas(hijo, f"{ruta}[]")


def proyectar(valor: Any, permitidos: frozenset[str], ruta: str = "") -> Any:
    """Copia solo las claves cuya ruta está en la lista."""
    if isinstance(valor, dict):
        resultado = {}
        for clave, hijo in valor.items():
            sub = f"{ruta}.{clave}" if ruta else clave
            if sub in permitidos:
                resultado[clave] = proyectar(hijo, permitidos, sub)
        return resultado
    if isinstance(valor, list):
        return [proyectar(hijo, permitidos, f"{ruta}[]") for hijo in valor]
    return valor


def fuera_de_lista(documentos: list[Documento], permitidos: frozenset[str]) -> list[str]:
    return sorted({r for d in documentos for r in rutas(d) if r not in permitidos})


def solo_fuentes_publicas(documento: Documento, capa: Capa) -> Documento | None:
    """Copia sin fuentes internas y sin citarlas en el historial; None si no queda ninguna."""
    copia = copy.deepcopy(documento)
    copia["fuentes"] = [f for f in copia["fuentes"] if fuente_publica(f, capa)]
    if not copia["fuentes"]:
        return None
    publicas = {f["id"] for f in copia["fuentes"]}
    for paso in copia["estado"]["historial"]:
        if paso["fuente_id"] not in publicas:
            del paso["fuente_id"]
    return copia


def escribir(documento: Documento, ruta: Path) -> None:
    texto = json.dumps(documento, ensure_ascii=False, sort_keys=True, indent=1)
    ruta.write_text(texto + "\n", encoding="utf-8", newline="\n")
