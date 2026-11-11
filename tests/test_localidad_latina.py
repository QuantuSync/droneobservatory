"""La localidad de una instalación de la capa de guerra sale de la recogida con su nombre en
alfabeto latino (docs/ciclo_de_vida.md): la web no enseña el cirílico, y sin él cada localidad
nueva había que añadirla a mano a una tabla («Заводське», 10 de noviembre de 2026)."""

from exportacion.campos import CAMPOS_PUBLICOS_IMPACTO
from proceso.lugares_guerra import Lugar, _con_localidad


def _lugar(id_: str, nombre: str, nivel: str, categoria: str, latino: str | None = None) -> Lugar:
    return Lugar(
        id=id_, nombre=nombre, nivel=nivel, pais="UA", region="UA-12", lat=48.5, lon=34.6,
        radio_km=3.0, categoria=categoria, nombre_latino=latino,
    )  # fmt: skip


def test_la_instalacion_lleva_el_nombre_latino_de_su_localidad() -> None:
    planta = _lugar("osm:1", "Завод", "instalacion", "industrial")
    localidad = _lugar("katotth:UA12", "Заводське", "localidad", "ciudad", "Zavodske")
    documento = _con_localidad(planta, localidad).documento()
    assert documento["localidad"] == "Заводське"
    assert documento["localidad_latino"] == "Zavodske"
    assert "lugar.localidad_latino" in CAMPOS_PUBLICOS_IMPACTO


def test_sin_nombre_latino_en_el_nomenclator_no_se_inventa() -> None:
    planta = _lugar("osm:1", "Завод", "instalacion", "industrial")
    localidad = _lugar("katotth:UA12", "Заводське", "localidad", "ciudad")
    documento = _con_localidad(planta, localidad).documento()
    assert documento["localidad"] == "Заводське" and "localidad_latino" not in documento
    assert "localidad_latino" not in _con_localidad(planta, None).documento()
