"""Carga de los JSON Schema versionados y lectura de sus marcas de visibilidad."""

import json
from collections.abc import Iterator
from enum import StrEnum
from functools import cache
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012

VERSION = "1.16.0"
DIRECTORIO = Path(__file__).parent / VERSION
PREFIJO_ID = f"urn:eodi:esquema:{VERSION}:"
MARCA = "x-visibilidad"

Documento = dict[str, Any]


def compatible(version: object) -> bool:
    """Una versión anterior con la misma mayor es compatible: los cambios menores solo añaden
    campos opcionales, así que lo escrito con ella sigue siendo válido."""
    if not isinstance(version, str) or version.count(".") != 2:
        return False
    try:
        partes = tuple(int(x) for x in version.split("."))
    except ValueError:
        return False
    actual = tuple(int(x) for x in VERSION.split("."))
    return partes[0] == actual[0] and partes <= actual


class Visibilidad(StrEnum):
    PUBLICO = "publico"
    INTERNO = "interno"


class Esquema(StrEnum):
    COMUN = "comun"
    INCIDENTE = "incidente"
    AFIRMACION = "afirmacion"
    FUENTE = "fuente"
    EPISODIO = "episodio"
    ATAQUE_UCRANIA = "ataque_ucrania"
    REGION_UCRANIA = "region_ucrania"
    IMPACTO_GUERRA = "impacto_guerra"
    RESTRICCION_AEROPUERTO = "restriccion_aeropuerto"
    CONFIGURACION_FUENTES = "configuracion_fuentes"
    ENCUENTRO = "encuentro"
    ESTADISTICA_OFICIAL = "estadistica_oficial"
    DOCUMENTO_OFICIAL = "documento_oficial"


@cache
def cargar(esquema: Esquema) -> Documento:
    ruta = DIRECTORIO / f"{esquema.value}.schema.json"
    contenido: Documento = json.loads(ruta.read_text(encoding="utf-8"))
    return contenido


@cache
def registro() -> Registry[Any]:
    recursos = [
        (PREFIJO_ID + e.value, Resource.from_contents(cargar(e), default_specification=DRAFT202012))
        for e in Esquema
    ]
    vacio: Registry[Any] = Registry()
    return vacio.with_resources(recursos)


def validador(esquema: Esquema) -> Draft202012Validator:
    return Draft202012Validator(cargar(esquema), registry=registro())


def validador_definicion(nombre: str) -> Draft202012Validator:
    """Validador de una definición común (comun.schema.json#/$defs/<nombre>)."""
    return Draft202012Validator(
        {"$ref": f"{PREFIJO_ID}{Esquema.COMUN.value}#/$defs/{nombre}"}, registry=registro()
    )


def _recorrer(
    nodo: Documento,
    ruta: str,
    interno: bool,
    resolver: Any,
    visitados: frozenset[str],
) -> Iterator[tuple[str, Visibilidad | None, bool]]:
    """Genera (ruta, marca propia, efectivamente interno) para cada propiedad."""
    if "$ref" in nodo:
        referencia = nodo["$ref"]
        if referencia in visitados:
            return
        resuelto = resolver.lookup(referencia)
        yield from _recorrer(
            resuelto.contents, ruta, interno, resuelto.resolver, visitados | {referencia}
        )
    for clave, hijo in nodo.get("properties", {}).items():
        sub = f"{ruta}.{clave}" if ruta else clave
        marca_cruda = hijo.get(MARCA)
        marca = Visibilidad(marca_cruda) if marca_cruda is not None else None
        interno_hijo = interno or marca is Visibilidad.INTERNO
        yield sub, marca, interno_hijo
        yield from _recorrer(hijo, sub, interno_hijo, resolver, visitados)
    if isinstance(nodo.get("items"), dict):
        yield from _recorrer(nodo["items"], f"{ruta}[]", interno, resolver, visitados)
    for combinador in ("oneOf", "anyOf", "allOf"):
        for rama in nodo.get(combinador, []):
            yield from _recorrer(rama, ruta, interno, resolver, visitados)


def recorrer(esquema: Esquema) -> Iterator[tuple[str, Visibilidad | None, bool]]:
    raiz = cargar(esquema)
    resolver = registro().resolver(base_uri=raiz["$id"])
    yield from _recorrer(raiz, "", False, resolver, frozenset())


def rutas_por_visibilidad(esquema: Esquema) -> dict[Visibilidad, frozenset[str]]:
    """Rutas de campos agrupadas por visibilidad efectiva (la más restrictiva de la cadena)."""
    publicas: set[str] = set()
    internas: set[str] = set()
    for ruta, _marca, interno in recorrer(esquema):
        (internas if interno else publicas).add(ruta)
    # Una ruta alcanzada por varias ramas es interna si alguna lo es.
    return {
        Visibilidad.PUBLICO: frozenset(publicas - internas),
        Visibilidad.INTERNO: frozenset(internas),
    }
