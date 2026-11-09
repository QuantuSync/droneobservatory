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


# Dos días seguidos (EODI-2026-00770, Leipzig/Halle, sábado 7 y domingo 8 de noviembre de 2026):
# antes contaban como una noche y la ficha juntó los dos cierres de pista.
LUNES = datetime(2026, 11, 9, 12, 15, tzinfo=UTC)
BERLIN = ZoneInfo("Europe/Berlin")
FIN_DE_SEMANA = ["2026-11-07", "2026-11-08"]


def _dias_lunes(frase: str, idioma: str) -> list[str]:
    return [str(d) for d in fechas.dias_distintos(frase, LUNES, BERLIN, idioma)]


def test_leipzig_sabado_y_domingo_son_dos_dias() -> None:
    frase = (
        "Wie die Polizei mitteilte, wurde am Samstag und Sonntag jeweils eine der beiden "
        "Landebahnen kurzzeitig gesperrt."
    )
    assert _dias_lunes(frase, "de") == FIN_DE_SEMANA


def test_dos_dias_seguidos_en_cada_idioma() -> None:
    frases = {
        "de": "Am Samstag sowie am Sonntag wurden Drohnen über dem Flughafen gesichtet.",
        "pl": "Drony zauważono nad lotniskiem w sobotę i w niedzielę.",
        "ro": "Drone au fost observate deasupra aeroportului sâmbătă și duminică.",
        "en": "Drones were spotted over the airport on Saturday and Sunday.",
        "fr": "Des drones ont été aperçus au-dessus de l'aéroport samedi et dimanche.",
        "nl": "Op zaterdag en zondag werden drones boven het vliegveld gezien.",
        "sv": "Drönare sågs över flygplatsen på lördag och söndag.",
        "da": "Der blev set droner over lufthavnen lørdag og søndag.",
        "no": "Det ble observert droner over flyplassen lørdag og søndag.",
        "fi": "Lentokentän yllä havaittiin drooneja lauantaina ja sunnuntaina.",
        "lt": "Dronai virš oro uosto pastebėti šeštadienį ir sekmadienį.",
        "hu": "Drónokat észleltek a repülőtér felett szombaton és vasárnap.",
        "sq": "Dronë u panë mbi aeroport të shtunën dhe të dielën.",
    }
    for idioma, frase in frases.items():
        assert _dias_lunes(frase, idioma) == FIN_DE_SEMANA, idioma


def test_una_noche_entre_dos_dias_no_son_dos_sucesos() -> None:
    noches = {
        "en": "Drones were seen late Saturday and early Sunday near the base.",
        "de": "Am Samstagabend und Sonntag früh wurden Drohnen gemeldet.",
        "pl": "Drony latały w sobotę wieczorem i w niedzielę nad ranem.",
        "ro": "Drone au survolat zona sâmbătă seara și duminică dimineața.",
        "fr": "Des drones ont survolé la base samedi soir et dimanche matin.",
        "nl": "Zaterdagavond en zondag werden drones gezien.",
        "sv": "Drönare sågs under natten mellan lördag och söndag.",
    }
    for idioma, frase in noches.items():
        assert _dias_lunes(frase, idioma) == [], idioma


def test_la_auditoria_marca_leipzig() -> None:
    ficha = {
        "id": "EODI-2026-09770",
        "lugar": {"pais": "DE", "nivel": "instalacion"},
        "fuentes": [
            {
                "id": "f1",
                "enlace": "https://welt.de/regionales/sachsen/drohnen-behindern-betrieb.html",
                "frase_origen": "Wie die Polizei mitteilte, wurde am Samstag und Sonntag jeweils "
                "eine der beiden Landebahnen kurzzeitig gesperrt.",
                "idioma": "de",
                "fecha": {"valor": "2026-11-09T12:15Z", "precision": "aproximada"},
            }
        ],
    }
    assert auditoria_fichas.dos_dias_sin_revisar(ficha)


def test_la_retencion_por_dos_dias_se_revisa_al_enlazar_la_parte() -> None:
    # La parte del domingo de una separación nace con la frase de los dos días; si la retuvo el
    # filtro de entrada antes de llevar «relacionados», al enlazarla vuelve a pasar por él.
    from recogida import entrada

    frase = (
        "Wie die Polizei mitteilte, wurde am Samstag und Sonntag jeweils eine der beiden "
        "Landebahnen kurzzeitig gesperrt."
    )
    ficha = {
        "id": "EODI-2026-09771",
        "lugar": {"pais": "DE", "nivel": "instalacion"},
        "tiempo": {"inicio": {"valor": "2026-11-08T00:00Z", "precision": "dia"}},
        "fuentes": [
            {
                "id": "f1",
                "enlace": "https://welt.de/regionales/sachsen/drohnen-behindern-betrieb.html",
                "frase_origen": frase,
                "idioma": "de",
                "fecha": {"valor": "2026-11-09T12:15Z", "precision": "aproximada"},
            }
        ],
    }
    decision = {
        "huella": entrada.huella(ficha),
        "decision": entrada.RETENER,
        "dos_dias": True,
        "motivo": "una frase da dos días",
    }
    assert not entrada.pendiente(decision, ficha, LUNES)
    enlazada = {**ficha, "relacionados": [{"id": "EODI-2026-00770"}]}
    assert entrada.pendiente(decision, enlazada, LUNES)
