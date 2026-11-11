"""Una frase con dos días es dos sucesos (proceso/fechas.dias_distintos, auditoría AA): el caso de
Letonia, EODI-2026-00756 (5 de noviembre de 2026), y las frases que no lo son."""

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from proceso import fechas, suceso

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
    assert suceso.dos_dias_sin_revisar(_ficha(frase))
    assert not suceso.dos_dias_sin_revisar(_ficha("W niedzielę wleciał dron."))
    # Una parte nacida de una separación (con «relacionados») ya está revisada.
    separada = {**_ficha(frase), "relacionados": [{"id": "EODI-2026-00746"}]}
    assert not suceso.dos_dias_sin_revisar(separada)


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
    assert suceso.dos_dias_sin_revisar(ficha)


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


# La noche del martes al miércoles contada el martes por la noche (LRT, alertas aéreas de
# Lituania del 10 de noviembre de 2026): el miércoles aún no ha llegado. La ficha EODI-2026-00784
# del ensayo quedó retenida por «una frase da dos días (2026-11-04, 2026-11-10)».
VILNA = ZoneInfo("Europe/Vilnius")
MARTES_NOCHE = datetime(2026, 11, 10, 20, 56, tzinfo=UTC)
MIERCOLES = datetime(2026, 11, 11, 7, 18, tzinfo=UTC)


def test_la_noche_del_martes_al_miercoles_contada_el_martes_es_una_noche() -> None:
    frase = (
        "Naktį iš antradienio į trečiadienį šalies gyventojus vienas po kito pasiekė skirtingi "
        "oro pavojaus signalai dėl galimo drono Lietuvos teritorijoje."
    )
    for publicacion in (MARTES_NOCHE, MIERCOLES):
        assert fechas.dias_distintos(frase, publicacion, VILNA, "lt") == []
    ingles = "Air alerts were issued overnight from Tuesday into Wednesday and early Wednesday."
    assert fechas.dias_distintos(ingles, MARTES_NOCHE, VILNA, "en") == []
    # Sin la noche, dos días seguidos siguen siendo dos días, se cuente cuando se cuente.
    dos = "Dronai pastebėti antradienį ir trečiadienį."
    assert len(fechas.dias_distintos(dos, MARTES_NOCHE, VILNA, "lt")) == 2
    assert len(fechas.dias_distintos(dos, MIERCOLES, VILNA, "lt")) == 2


# «La noche hacia el 11» empieza el 10. La nota de las Fuerzas Armadas de Letonia sobre la noche
# del 10 al 11 de noviembre de 2026 («Naktī uz 11. novembri…») daba una ficha del 11
# (EODI-2026-00784), y las alertas de esa misma noche (EODI-2026-00777), otra del 10.
NOCHES_HACIA = {
    "lv": "Naktī uz 11. novembri Latvijas gaisa telpā ielidoja trīs bezpilota lidaparāti",
    "lt": "Naktį į lapkričio 11-ąją į Lietuvos oro erdvę įskrido dronas",
    "et": "Ööl vastu 11. novembrit sisenes Eesti õhuruumi droon",
    "de": "In der Nacht zum 11. November drang eine Drohne in den Luftraum ein",
    "en": "On the night into 11 November a drone entered the airspace",
}


def test_la_noche_hacia_una_fecha_escrita_empieza_la_vispera() -> None:
    publicada = datetime(2026, 11, 11, 7, 0, tzinfo=UTC)
    del_once = datetime(2026, 11, 11, tzinfo=UTC)
    for idioma, frase in NOCHES_HACIA.items():
        (lectura,) = fechas.leer(frase, publicada, RIGA, idioma)
        assert (str(lectura.dia), lectura.hacia) == ("2026-11-10", True), idioma
        # La ficha con el día 11 a secas pasa al 10.
        resuelto = fechas.resolver(del_once, "dia", [frase], publicada, RIGA, RIGA, idioma)
        assert (str(resuelto.valor.date()), resuelto.precision) == ("2026-11-10", "dia"), idioma
        # Con hora, la madrugada del 11 sigue siendo de esa noche: no se toca.
        madrugada = datetime(2026, 11, 11, 1, 18, tzinfo=UTC)
        con_hora = fechas.resolver(madrugada, "minuto", [frase], publicada, RIGA, RIGA, idioma)
        assert con_hora.valor == madrugada and not con_hora.corregido, idioma
    # Con el día de la semana, igual que antes: «la noche hacia el miércoles» es la del martes.
    for idioma, frase in (
        ("lv", "Naktī uz trešdienu Latvijas gaisa telpā ielidoja drons"),
        ("lt", "Naktį į trečiadienį į Lietuvos oro erdvę įskrido dronas"),
        ("et", "Ööl vastu kolmapäeva sisenes Eesti õhuruumi droon"),
    ):
        resuelto = fechas.resolver(del_once, "dia", [frase], publicada, RIGA, RIGA, idioma)
        assert str(resuelto.valor.date()) == "2026-11-10", idioma


def test_una_fecha_escrita_sin_la_noche_hacia_no_cambia() -> None:
    publicada = datetime(2026, 11, 11, 7, 0, tzinfo=UTC)
    del_once = datetime(2026, 11, 11, tzinfo=UTC)
    frase = (
        "Nacionālie bruņotie spēki informē, ka 11. novembrī no plkst. 00.23 Latvijas gaisa telpā"
    )
    (lectura,) = fechas.leer(frase, publicada, RIGA, "lv")
    assert (str(lectura.dia), lectura.hacia) == ("2026-11-11", False)
    resuelto = fechas.resolver(del_once, "dia", [frase], publicada, RIGA, RIGA, "lv")
    assert str(resuelto.valor.date()) == "2026-11-11" and not resuelto.corregido
    # La noche hacia el 11 lejos de la fecha (otra frase de la nota) tampoco: tiene que ir junto.
    lejos = "Naktī uz rītdienu gaidāms lietus, bet 11. novembrī ielidoja drons"
    assert not fechas.leer(lejos, publicada, RIGA, "lv")[0].hacia
