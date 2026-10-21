"""Los nombres de lugar que la auditoría G encontraba mal (proceso/auditoria_fichas.py) y las
localidades homónimas: una prueba por causa, con los datos de la ficha real."""

import json
from typing import Any

import pytest

from proceso import nombres_lugar, referencia, ubicacion
from proceso.noticias import nomenclator


def _gotemburgo() -> dict[str, Any]:
    # EODI-2025-00235: el punto se afinó del centro de Gotemburgo al aeropuerto de Landvetter y
    # el anterior se guardó sin nombre.
    return {
        "id": "EODI-2025-00235",
        "titulo": {
            "es": "Dron avistado en el aeropuerto de Gotemburgo obliga a cerrar el espacio aéreo",
            "en": "Drone sighted at Gothenburg airport forces airspace closure",
        },
        "lugar": {
            "pais": "SE", "nivel": "instalacion", "suceso": "Göteborg",
            "punto": {"lat": 57.66303, "lon": 12.28449}, "radio_km": 5.0,
            "historial": [{"anterior": {"punto": {"lat": 57.70716, "lon": 11.96679},
                                        "radio_km": 10.0}}],
        },
    }  # fmt: skip


def test_un_punto_anterior_sin_nombre_toma_el_de_la_localidad_mas_cercana() -> None:
    nombres = nombres_lugar.nombres_publicos(_gotemburgo())
    assert nombres["anteriores"] == [{"es": "Gotemburgo", "en": "Gothenburg"}]
    # Un punto anterior lejos de cualquier localidad sigue sin nombre.
    lejos = {"punto": {"lat": 57.0, "lon": 19.5}, "radio_km": 1.0}
    assert nombres_lugar.anterior(lejos, "SE") is None


def test_el_titular_con_una_forma_hibrida_de_alejandropolis() -> None:
    # EODI-2026-00050: «Alexandrópolis» no es la forma española (Alejandrópolis) ni la inglesa.
    titulo = "Dron interceptado cerca del aeropuerto de Alexandrópolis por cazas griegos"
    assert nombres_lugar.formas_ajenas(titulo, "es", "GR") == ["Alexandrópolis"]
    ficha = {"titulo": {"es": titulo, "en": "Drone near Alexandroupolis airport"},
             "lugar": {"pais": "GR", "localidad": "Alexandroupoli"}}  # fmt: skip
    assert "Alejandrópolis" in nombres_lugar.titulo_corregido(ficha)["es"]


def test_la_etiqueta_en_minuscula_de_wikidata_sale_con_mayuscula(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # EODI-2025-00206: la etiqueta española de Wikidata es «île Longue».
    guardado = {"FR:ile longue": {"es": "île Longue", "en": "Île Longue", "nombre": "Île Longue"}}
    monkeypatch.setattr(nombres_lugar, "_cache", lambda: guardado)
    assert nombres_lugar.lugar("Île Longue", "FR") == {"es": "Île Longue", "en": "Île Longue"}


def test_entre_homonimos_decide_el_municipio_que_escribe_la_fuente() -> None:
    # EODI-2026-00648: «w Józefowie w gminie Nieporęt»; el nomenclátor guarda el Józefów de
    # junto a Otwock (el más poblado) y la ficha salió allí.
    ruta = referencia.DIRECTORIO / "fichas" / "EODI-2026-00648.json"
    ficha = json.loads(ruta.read_text(encoding="utf-8"))
    ficha["lugar"] = {
        "pais": "PL", "nivel": "localidad", "suceso": "Józefów", "region": "mazowieckie",
        "geocodificacion": "localidad", "punto": {"lat": 52.13707, "lon": 21.23589},
        "radio_km": 5.0,
    }  # fmt: skip
    lugar = ubicacion.lugar_del_homonimo(ficha, nomenclator())
    assert lugar is not None
    assert lugar["punto"] == {"lat": 52.38377, "lon": 21.00517}
    assert lugar["geocodificacion"] == "localidad_pequena"
    # Ya en el pueblo de Nieporęt, no cambia.
    assert ubicacion.lugar_del_homonimo({**ficha, "lugar": lugar}, nomenclator()) is None
    # Sin municipio en la frase, nada decide.
    texto = ("Dron spadł na działkę w Józefowie.",)
    assert ubicacion.homonimo_de_la_fuente("Józefów", "PL", texto, nomenclator()) is None
