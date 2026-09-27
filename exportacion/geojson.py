"""Genera incidentes.geojson para la web a partir de la lista cerrada de campos."""

import copy
import json
from collections.abc import Iterable, Iterator
from datetime import datetime
from pathlib import Path
from typing import Any

from esquema import Documento
from exportacion.campos import CAMPOS_PUBLICOS_INCIDENTE
from proceso.validaciones import Error, fiabilidad_interna, validar_incidente


class ExportacionInvalida(ValueError):
    pass


def fuente_publica(fuente: Documento) -> bool:
    """Una fuente sale a la web solo si está marcada pública y no es interna por regla."""
    return (
        fuente.get("publica") is True
        and not fiabilidad_interna(fuente["fiabilidad"])
        and not fuente.get("interna_fuera_de_ucrania", False)
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


def campos_fuera_de_lista(coleccion: Documento) -> list[str]:
    return sorted(
        {
            ruta
            for feature in coleccion["features"]
            for ruta in rutas(feature["properties"])
            if ruta not in CAMPOS_PUBLICOS_INCIDENTE
        }
    )


def feature(incidente: Documento) -> Documento | None:
    """Feature pública del incidente, o None si ninguna de sus fuentes es pública."""
    documento = copy.deepcopy(incidente)
    documento["fuentes"] = [f for f in documento["fuentes"] if fuente_publica(f)]
    if not documento["fuentes"]:
        return None
    publicas = {f["id"] for f in documento["fuentes"]}
    for paso in documento["estado"]["historial"]:
        if paso["fuente_id"] not in publicas:
            del paso["fuente_id"]
    punto = documento["lugar"].pop("punto")
    return {
        "type": "Feature",
        "id": documento["id"],
        "geometry": {"type": "Point", "coordinates": [punto["lon"], punto["lat"]]},
        "properties": proyectar(documento, CAMPOS_PUBLICOS_INCIDENTE),
    }


def exportar(
    incidentes: Iterable[Documento], ahora: datetime, vocabulario_modelos: frozenset[str]
) -> Documento:
    features = []
    for incidente in incidentes:
        errores: list[Error] = validar_incidente(incidente, ahora, vocabulario_modelos)
        if errores:
            raise ExportacionInvalida(f"{incidente.get('id')}: {errores[0].mensaje}")
        publicado = feature(incidente)
        if publicado is not None:
            features.append(publicado)
    coleccion: Documento = {
        "type": "FeatureCollection",
        "features": sorted(features, key=lambda f: str(f["id"])),
    }
    # Segunda barrera: la proyección ya filtra, pero se comprueba el resultado.
    sobrantes = campos_fuera_de_lista(coleccion)
    if sobrantes:
        raise ExportacionInvalida(f"campos fuera de la lista: {sobrantes}")
    return coleccion


def escribir(coleccion: Documento, ruta: Path) -> None:
    texto = json.dumps(coleccion, ensure_ascii=False, sort_keys=True, indent=1)
    ruta.write_text(texto + "\n", encoding="utf-8")
