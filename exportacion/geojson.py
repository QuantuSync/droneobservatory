"""Genera incidentes.geojson para la web a partir de la lista cerrada de campos."""

from collections.abc import Iterable
from datetime import datetime

from esquema import Documento
from exportacion.campos import CAMPOS_PUBLICOS_INCIDENTE
from exportacion.proyeccion import (
    ExportacionInvalida,
    fuera_de_lista,
    proyectar,
    solo_fuentes_publicas,
)
from proceso.estados import Capa
from proceso.validaciones import validar_incidente


def campos_fuera_de_lista(coleccion: Documento) -> list[str]:
    return fuera_de_lista(
        [f["properties"] for f in coleccion["features"]], CAMPOS_PUBLICOS_INCIDENTE
    )


def feature(incidente: Documento) -> Documento | None:
    """Feature pública del incidente, o None si ninguna de sus fuentes es pública."""
    documento = solo_fuentes_publicas(incidente, Capa.GENERAL)
    if documento is None:
        return None
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
        errores = validar_incidente(incidente, ahora, vocabulario_modelos)
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
