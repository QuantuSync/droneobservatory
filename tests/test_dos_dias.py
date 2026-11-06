"""Una frase con dos días es dos sucesos (proceso/fechas.dias_distintos, auditoría AA): el caso de
Letonia, EODI-2026-00756 (5 de noviembre de 2026), y las frases que no lo son."""

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from proceso import auditoria_fichas, fechas

RIGA = ZoneInfo("Europe/Riga")
PUBLICACION = datetime(2026, 11, 5, 8, 15, tzinfo=UTC)


def _dias(frase: str, idioma: str) -> list[str]:
    return [str(d) for d in fechas.dias_distintos(frase, PUBLICACION, RIGA, idioma)]


def test_dos_dias_unidos_por_una_conjuncion() -> None:
    frase = "W łotewską przestrzeń powietrzną wkroczyły w niedzielę i wtorek dwa drony."
    assert _dias(frase, "pl") == ["2026-11-01", "2026-11-03"]
    assert _dias("Dos drones entraron el domingo y el martes", "es") == [
        "2026-11-01",
        "2026-11-03",
    ]


def test_lo_que_no_son_dos_sucesos() -> None:
    # Una noche que cruza la medianoche, un día con su fecha escrita, dos momentos de un suceso.
    assert _dias("W nocy z niedzieli na poniedziałek nad Łotwą przeleciał dron", "pl") == []
    assert _dias("Op donderdag 15 januari en vrijdag kwam een melding", "nl") == []
    assert (
        _dias(
            "Los Mossos le detuvieron el lunes en Masquefa y ha pasado a disposición judicial "
            "este miércoles.",
            "es",
        )
        == []
    )


def _ficha(frase: str) -> dict[str, object]:
    return {
        "id": "EODI-2026-09756",
        "lugar": {"pais": "LV", "nivel": "pais"},
        "fuentes": [
            {
                "id": "f1",
                "enlace": "https://wiadomosci.onet.pl/swiat/incydenty",
                "frase_origen": frase,
                "idioma": "pl",
                "fecha": {"valor": "2026-11-05T08:15Z", "precision": "aproximada"},
            }
        ],
    }


def test_la_auditoria_marca_la_ficha_sin_revisar() -> None:
    frase = "W łotewską przestrzeń powietrzną wkroczyły w niedzielę i wtorek dwa drony."
    assert auditoria_fichas.dos_dias_sin_revisar(_ficha(frase))
    assert not auditoria_fichas.dos_dias_sin_revisar(_ficha("W niedzielę wleciał dron."))
    # Una parte nacida de una separación (con «relacionados») ya está revisada.
    separada = {**_ficha(frase), "relacionados": [{"id": "EODI-2026-00746"}]}
    assert not auditoria_fichas.dos_dias_sin_revisar(separada)
