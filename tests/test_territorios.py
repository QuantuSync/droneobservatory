"""Suelo europeo fuera del continente: país padre, hora local y soberanías."""

from datetime import UTC, datetime

import pytest

from modelo import ficha
from proceso import fechas, territorios


@pytest.mark.parametrize(
    ("codigo", "padre"),
    [("GI", "GB"), ("gl", "DK"), ("SJ", "NO"), ("RE", "FR"), ("YT", "FR"), ("GF", "FR"),
     ("GP", "FR"), ("MQ", "FR"), ("MF", "FR"), ("IC", "ES"), ("EA", "ES"), ("ES", "ES"),
     ("CY", "CY")],
)  # fmt: skip
def test_pais_padre(codigo: str, padre: str) -> None:
    assert territorios.pais_padre(codigo) == padre


def test_la_ficha_lee_un_territorio_como_su_pais() -> None:
    assert ficha.interpretar("pais", "RE") == "FR"
    assert ficha.interpretar("lugar_suceso", "Nuuk; localidad; GL; Sermersooq")["pais"] == "DK"


@pytest.mark.parametrize(
    ("lat", "lon", "zona"),
    [(28.1, -15.42, "Atlantic/Canary"), (37.74, -25.67, "Atlantic/Azores"),
     (5.16, -52.65, "America/Cayenne"), (-20.88, 55.45, "Indian/Reunion"),
     (-12.78, 45.23, "Indian/Mayotte"), (16.24, -61.53, "America/Guadeloupe"),
     (14.6, -61.07, "America/Martinique"), (34.59, 32.99, "Asia/Nicosia"),
     (64.18, -51.72, "America/Nuuk"), (76.53, -68.7, "America/Thule"),
     (78.22, 15.65, "Arctic/Longyearbyen")],
)  # fmt: skip
def test_hora_local_del_territorio(lat: float, lon: float, zona: str) -> None:
    hallada = territorios.zona_del_punto(lat, lon)
    assert hallada is not None and hallada.key == zona


def test_en_el_continente_manda_el_pais() -> None:
    assert territorios.zona_del_punto(40.4, -3.7) is None
    madrid = fechas.zona("ES", 40.4, -3.7)
    canarias = fechas.zona("ES", 28.1, -15.42)
    assert madrid is not None and canarias is not None
    verano = datetime(2026, 7, 1, 12, tzinfo=UTC)
    assert madrid.utcoffset(verano) != canarias.utcoffset(verano)


def test_reino_unido_tiene_suelo_en_chipre() -> None:
    assert territorios.soberanos_dentro("CY") == ("GB",)
    assert territorios.soberanos_dentro("ES") == ()
