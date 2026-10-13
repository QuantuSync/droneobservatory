"""Fronteras y países con la posición de la Unión Europea (docs/metodología): un lugar del norte
de Chipre es Chipre, de Transnistria es Moldavia, de Abjasia y Osetia del Sur es Georgia y de
Crimea, Sebastopol y el Donbás ocupado es Ucrania; Kosovo, como en el resto del observatorio."""

import copy
import json
from pathlib import Path

import pytest

from proceso import fronteras
from recogida import fronteras_natural_earth

RAIZ = Path(__file__).resolve().parent.parent

LUGARES = {
    "Kyrenia (norte de Chipre)": (35.30, 33.35, "CY"),
    "Famagusta (norte de Chipre)": (35.12, 33.94, "CY"),
    "Nicosia norte": (35.20, 33.36, "CY"),
    "Tiraspol (Transnistria)": (46.84, 29.63, "MD"),
    "Bender (Transnistria)": (46.83, 29.48, "MD"),
    "Sujumi (Abjasia)": (43.00, 41.02, "GE"),
    "Tsjinvali (Osetia del Sur)": (42.23, 43.97, "GE"),
    "Simferópol (Crimea)": (44.95, 34.10, "UA"),
    "Sebastopol": (44.60, 33.52, "UA"),
    "Kerch (Crimea)": (45.35, 36.47, "UA"),
    "Donetsk": (48.00, 37.80, "UA"),
    "Lugansk": (48.57, 39.31, "UA"),
    "Mariúpol": (47.10, 37.55, "UA"),
    "Melitópol": (46.85, 35.37, "UA"),
    "Pristina": (42.66, 21.16, "XK"),
}


def _paises_del_punto(lat: float, lon: float) -> set[str]:
    datos = fronteras.fronteras()
    return {
        pais
        for grupo in (datos.paises, datos.vecinos)
        for pais, poligonos in grupo.items()
        if any(p.contiene(lon, lat) for p in poligonos)
    }


@pytest.mark.parametrize("nombre", sorted(LUGARES))
def test_cada_lugar_cae_en_el_pais_que_reconoce_la_union_europea(nombre: str) -> None:
    lat, lon, pais = LUGARES[nombre]
    assert _paises_del_punto(lat, lon) == {pais}, nombre


def test_las_entidades_no_reconocidas_no_son_paises() -> None:
    datos = json.loads((RAIZ / "configuracion" / "fronteras_europa.json").read_text("utf-8"))
    codigos = set(datos["paises"]) | set(datos["vecinos"])
    assert not codigos & {"Northern Cyprus", "N. Cyprus", "Transnistria", "Abkhazia",
                          "South Ossetia", "Crimea"}  # fmt: skip
    # Sus nombres no sitúan nada (no son una localidad) y no son nombres de Chipre.
    for nombre in ("northern cyprus", "kuzey kibris turk cumhuriyeti",
                   "republica turca del norte de chipre"):  # fmt: skip
        assert fronteras.es_nombre_de_pais(nombre)
        assert nombre not in datos["nombres_por_pais"]["CY"]


def test_el_generador_pasa_crimea_a_ucrania_una_sola_vez() -> None:
    crimea = [[[33.5, 44.6], [34.1, 44.95], [36.4, 45.3], [33.5, 44.6]]]
    rusia = [[[37.0, 55.0], [38.0, 56.0], [39.0, 55.0], [37.0, 55.0]]]
    ucrania = [[[30.0, 50.0], [31.0, 51.0], [32.0, 50.0], [30.0, 50.0]]]
    datos = {"paises": {"RO": []}, "vecinos": {"RU": [crimea, rusia], "UA": [ucrania]}}
    una = fronteras_natural_earth.segun_la_ue(copy.deepcopy(datos))
    assert una["vecinos"] == {"RU": [rusia], "UA": [ucrania, crimea]}
    assert fronteras_natural_earth.segun_la_ue(copy.deepcopy(una)) == una
