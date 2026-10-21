"""Los nombres de lugar de todos los incidentes publicados, en español y en inglés.

Corre en la integración continua sobre los datos publicados de verdad (el trabajo
«datos-publicados», con EODI_PUBLICACION) y, en el resto de trabajos, sobre los datos de ejemplo.
Revisa lo que la ficha enseña de cada incidente (proceso/nombres_lugar.problemas): el titular, el
lugar, la localidad, el objetivo, la región y los demás lugares, sin otro alfabeto, sin palabras
de otro idioma, sin la forma de la otra versión («Paphos» en la española) y sin «Lugar» con el
país a secas cuando se conoce la localidad. Con datos publicados antes de que existiera el campo
`nombres`, comprueba lo que la regla daría al publicarlos."""

import json
import os
from pathlib import Path

import pytest

from esquema import Documento
from proceso import coherencia, nombres_lugar

CARPETA = Path(
    os.environ.get("EODI_PUBLICACION")
    or Path(__file__).resolve().parent / "fixtures" / "publicacion"
)


def publicados() -> list[Documento]:
    incidentes: list[Documento] = []
    mapa = CARPETA / "incidentes.geojson"
    if mapa.exists():
        for feature in json.loads(mapa.read_text(encoding="utf-8"))["features"]:
            propiedades = json.loads(json.dumps(feature["properties"]))
            lon, lat = feature["geometry"]["coordinates"]
            propiedades["lugar"]["punto"] = {"lon": lon, "lat": lat}
            incidentes.append(propiedades)
    sin_punto = CARPETA / "incidentes_sin_ubicacion.json"
    if sin_punto.exists():
        incidentes += json.loads(sin_punto.read_text(encoding="utf-8"))["incidentes"]
    return incidentes


def con_nombres(propiedades: Documento) -> Documento:
    if "nombres" in propiedades:
        # El titular como lo publica el código de ahora (exportacion/geojson.py): una forma que
        # una regla nueva corrige («Alexandrópolis», EODI-2026-00050) sale bien en la próxima
        # publicación; con lo ya corregido no cambia nada.
        return {**propiedades, "titulo": nombres_lugar.titulo_corregido(propiedades)}
    return {
        **propiedades,
        "titulo": nombres_lugar.titulo_corregido(propiedades),
        "nombres": nombres_lugar.nombres_publicos(propiedades),
    }


INCIDENTES = publicados()


def test_hay_incidentes() -> None:
    assert INCIDENTES


def test_ningun_nombre_mal_escrito_en_ninguna_version() -> None:
    malos = {
        p["id"]: problemas
        for p in INCIDENTES
        if (problemas := nombres_lugar.problemas(con_nombres(p)))
    }
    assert malos == {}


def test_ninguna_fecha_contradictoria() -> None:
    """El historial en orden, el estado actual como último paso, el fin después del inicio y el
    primer aviso no antes del suceso (proceso/coherencia.py)."""
    malos = {
        p["id"]: problemas
        for p in INCIDENTES
        if (problemas := coherencia.contradicciones(coherencia.coherente(p)))
    }
    assert malos == {}


@pytest.mark.parametrize(
    ("id_", "objetivo", "lugar"),
    [
        (
            "EODI-2026-00002",
            {"es": "Aeropuerto de Pafos", "en": "Paphos International Airport"},
            {"es": "Pafos, Chipre", "en": "Paphos, Cyprus"},
        ),
        (
            "EODI-2025-00057",
            {"es": "Aeropuerto de Lárnaca", "en": "Larnaca International Airport"},
            {"es": "Lárnaca, Chipre", "en": "Larnaca, Cyprus"},
        ),
        (
            "EODI-2026-00268",
            {"es": "RAF Akrotiri", "en": "RAF Akrotiri"},
            {
                "es": "RAF Akrotiri (base británica), Chipre",
                "en": "RAF Akrotiri (British base), Cyprus",
            },
        ),
    ],
)
def test_los_de_chipre(id_: str, objetivo: Documento, lugar: Documento) -> None:
    propiedades = next((p for p in INCIDENTES if p["id"] == id_), None)
    if propiedades is None:
        pytest.skip(f"{id_} no está en estos datos")
    nombres = con_nombres(propiedades)["nombres"]
    assert nombres["objetivo"] == objetivo
    assert nombres["lugar"] == lugar
