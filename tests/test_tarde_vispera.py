"""Una tarde no pasa de la medianoche. EODI-2026-00771: bild.de publicó el 9 de noviembre de 2026
a las 14:30 (hora de Alemania) «Am Abend wurde an der Führungsakademie der Bundeswehr im Stadtteil
Nienstedten eine Drohne entdeckt.» A esa hora la tarde del 9 no había llegado: es la del 8. La
lectura admitía también el día siguiente, como en una noche, y la ficha se publicó con el 9."""

from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

import pytest

from proceso import fechas

BERLIN = ZoneInfo("Europe/Berlin")
FRASE = (
    "Am Abend wurde an der Führungsakademie der Bundeswehr im Stadtteil Nienstedten eine Drohne "
    "entdeckt."
)
PUBLICADA = datetime(2026, 11, 9, 13, 30, tzinfo=UTC)


def test_la_tarde_de_una_nota_de_mediodia_es_la_de_la_vispera() -> None:
    (lectura,) = fechas.leer(FRASE, PUBLICADA, BERLIN, "de")
    assert lectura.dia == date(2026, 11, 8)
    assert lectura.admitidos == frozenset({date(2026, 11, 8)})


def test_la_ficha_con_el_dia_de_la_nota_se_corrige_a_la_vispera() -> None:
    resolucion = fechas.resolver(
        datetime(2026, 11, 9, tzinfo=UTC), "dia", [FRASE], PUBLICADA, BERLIN, BERLIN, "de"
    )
    assert resolucion.corregido
    assert resolucion.valor.date() == date(2026, 11, 8)
    assert resolucion.origen == fechas.RELATIVA


def test_la_ficha_con_la_vispera_se_queda() -> None:
    resolucion = fechas.resolver(
        datetime(2026, 11, 8, tzinfo=UTC), "dia", [FRASE], PUBLICADA, BERLIN, BERLIN, "de"
    )
    assert not resolucion.corregido
    assert resolucion.valor.date() == date(2026, 11, 8)


def test_la_tarde_de_una_nota_de_la_noche_es_la_de_ese_dia() -> None:
    noche = datetime(2026, 11, 9, 20, 0, tzinfo=UTC)
    (lectura,) = fechas.leer(FRASE, noche, BERLIN, "de")
    assert lectura.admitidos == frozenset({date(2026, 11, 9)})


@pytest.mark.parametrize(
    ("frase", "idioma", "zona"),
    [
        ("Un drone a été aperçu dans la soirée au-dessus du site.", "fr", "Europe/Paris"),
        ("Un drone è stato avvistato in serata sopra l'aeroporto.", "it", "Europe/Rome"),
        ("Am späten Abend wurde eine Drohne über dem Gelände gesichtet.", "de", "Europe/Berlin"),
    ],
)
def test_las_tardes_de_otros_idiomas(frase: str, idioma: str, zona: str) -> None:
    (lectura,) = fechas.leer(frase, PUBLICADA, ZoneInfo(zona), idioma)
    assert lectura.admitidos == frozenset({date(2026, 11, 8)})


def test_una_noche_sigue_admitiendo_la_madrugada_siguiente() -> None:
    frase = "In der Nacht wurde eine Drohne über dem Flughafen gesichtet."
    (lectura,) = fechas.leer(frase, PUBLICADA, BERLIN, "de")
    assert lectura.admitidos == frozenset({date(2026, 11, 8), date(2026, 11, 9)})


def test_cada_tarde_esta_entre_las_noches_de_su_idioma() -> None:
    for idioma, datos in fechas.configuracion()["idiomas"].items():
        assert set(datos.get("tardes", [])) <= set(datos["noches"]), idioma


def test_la_ficha_de_hamburgo_lleva_la_tarde_del_domingo() -> None:
    """La regla no alcanza a la ficha ya guardada (su día lo protege el cerrojo): va por revisión,
    con la frase de la nota."""
    from recogida import revisados

    (revision,) = [
        d for d in revisados.cargar()["datos"]
        if d["incidente"] == "EODI-2026-00771" and d["campo"] == "inicio"
    ]  # fmt: skip
    assert revision["valor"] == "2026-11-08"
    assert revision["cita"] == FRASE
