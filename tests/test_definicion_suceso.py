"""La batería de casos reales de la definición de suceso (docs/definicion_suceso.md): las fichas
de la base de producción del 11 de noviembre de 2026 (tests/fixtures/definicion_suceso.json) y,
de cada caso, la decisión correcta según sus fuentes. La definición (proceso/suceso.py) tiene
que acertarlos todos."""

import copy
import json
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import pytest

from almacen.base import Almacen
from proceso import auditoria_fichas, incidentes, invariantes, suceso
from tests import ejemplos
from tests.ejemplos import VOCABULARIO_MODELOS

CASO = json.loads(
    (Path(__file__).resolve().parent / "fixtures" / "definicion_suceso.json").read_text(
        encoding="utf-8"
    )
)
DECIDIDAS: dict[str, dict[str, str]] = CASO["autoridades_decididas"]
DEL_EXPERTO = frozenset(frozenset(par) for par in CASO["distintos_del_experto"])
AHORA = datetime(2026, 11, 11, 16, 17, tzinfo=UTC)


def f(numero: str) -> dict[str, Any]:
    """La ficha real, por el final de su identificador («2026-00777»)."""
    ficha: dict[str, Any] = copy.deepcopy(CASO["fichas"][f"EODI-{numero}"])
    return ficha


def suelta(numero: str) -> dict[str, Any]:
    """La ficha como era antes de unirse o de retirarse."""
    return {k: v for k, v in f(numero).items() if k not in {"fusionado_en", "retirado"}}


def sin_revisar(numero: str, otro_id: str) -> dict[str, Any]:
    """La ficha como nació: con otro número (las revisiones a mano van por el número) y sin los
    enlaces que le puso una separación."""
    ficha = suelta(numero)
    ficha.pop("relacionados", None)
    return {**ficha, "id": otro_id}


def dicho(a: dict[str, Any], b: dict[str, Any], vigente: bool = False) -> suceso.Veredicto:
    return suceso.veredicto(
        a, b, DEL_EXPERTO, DECIDIDAS.get(a["id"]), DECIDIDAS.get(b["id"]), vigente
    )


def fusion(absorbido: str, destino: str) -> dict[str, Any]:
    """La unión vigente real de las dos fichas."""
    (unica,) = [
        u for u in CASO["fusiones"]
        if u["absorbido"] == f"EODI-{absorbido}" and u["destino"] == f"EODI-{destino}"
    ]  # fmt: skip
    return dict(unica)


def se_deshace(absorbido: str, destino: str) -> suceso.Veredicto | None:
    return incidentes.union_que_se_deshace(
        fusion(absorbido, destino), f(absorbido), f(destino), DECIDIDAS
    )


# --- Dos días distintos son dos sucesos -----------------------------------------------------


def test_letonia_el_domingo_y_el_martes_son_dos_sucesos() -> None:
    """EODI-2026-00756 (el dron del domingo 1 de noviembre, Krāslava y Ludza) y EODI-2026-00746
    (el del martes 3, caído cerca de Balvi). «W łotewską przestrzeń powietrzną wkroczyły w
    niedzielę i wtorek dwa drony» los juntó en una ficha del domingo."""
    domingo, martes = f("2026-00756"), f("2026-00746")
    assert dicho(domingo, martes).relacion == suceso.DISTINTOS
    # Sin la revisión tampoco se unen ni se preguntan: no son la misma jornada.
    assert dicho(sin_revisar("2026-00756", "EODI-2026-09756"), martes).relacion == suceso.AJENAS
    # La ficha que nació con los dos días se marca: cuenta dos sucesos.
    nacida = sin_revisar("2026-00756", "EODI-2026-09756")
    hallada = suceso.varios_dias(nacida)
    assert hallada is not None
    frase, dias = hallada
    assert "w niedzielę i wtorek" in frase
    assert dias == [date(2026, 11, 1), date(2026, 11, 3)]
    assert suceso.dos_dias_sin_revisar(nacida)
    # Ya separada por una revisión, no.
    assert not suceso.dos_dias_sin_revisar(domingo)


def test_letonia_la_ficha_del_martes_no_se_pierde() -> None:
    """EODI-2026-00760 nació al separar la 00756 y es el dron del martes: una revisión la unió a
    EODI-2026-00746, y ninguna regla deshace una unión hecha a mano."""
    assert f("2026-00760")["fusionado_en"] == "EODI-2026-00746"
    assert fusion("2026-00760", "2026-00746")["motivo"].startswith(suceso.PREFIJO_REVISADA)
    assert se_deshace("2026-00760", "2026-00746") is None


def test_leipzig_el_sabado_y_el_domingo_son_dos_sucesos() -> None:
    """EODI-2026-00770 (sábado 7 de noviembre, 19:20) y EODI-2026-00773 (domingo 8, 8:15): «Wie
    die Polizei mitteilte, wurde am Samstag und Sonntag jeweils eine der beiden Landebahnen
    kurzzeitig gesperrt»."""
    sabado, domingo = f("2026-00770"), f("2026-00773")
    assert dicho(sabado, domingo).relacion == suceso.DISTINTOS
    # Sin la revisión: el mismo sitio, pero ni la misma jornada ni una noche (13 horas después,
    # ya de día): no se unen ni se preguntan.
    a = sin_revisar("2026-00770", "EODI-2026-09770")
    b = sin_revisar("2026-00773", "EODI-2026-09773")
    assert suceso.mismo_sitio(a, b)
    assert dicho(a, b).relacion == suceso.AJENAS
    hallada = suceso.varios_dias(a)
    assert hallada is not None and hallada[1] == [date(2026, 11, 7), date(2026, 11, 8)]
    assert suceso.dos_dias_sin_revisar(a) and not suceso.dos_dias_sin_revisar(sabado)


def test_dos_dias_seguidos_sin_hora_no_se_unen_sin_preguntar() -> None:
    """El mismo sitio el sábado y el domingo, las dos fichas con el día a secas: puede ser una
    noche que cruza la medianoche o dos sucesos. La regla de fusión los unía; ahora lo decide
    quien lee las fuentes."""
    a = sin_revisar("2026-00770", "EODI-2026-09770")
    b = sin_revisar("2026-00773", "EODI-2026-09773")
    a["tiempo"] = {"inicio": ejemplos.instante("2026-11-07T00:00Z", "dia")}
    b["tiempo"] = {"inicio": ejemplos.instante("2026-11-08T00:00Z", "dia")}
    # Las dos cuentan un cierre de pista y sus noticias son del lunes 9: dos cierres de noches
    # distintas, dos sucesos (regla 5).
    assert suceso.cierres_de_noches_distintas(a, b)
    veredicto = dicho(a, b)
    assert (veredicto.relacion, veredicto.regla) == (suceso.DISTINTOS, suceso.REGLA_CIERRES)
    # Sin cierre no hay regla firme: ni se unen solas ni son distintas sin leer las fuentes.
    for ficha in (a, b):
        ficha.pop("consecuencias")
    assert dicho(a, b).relacion == suceso.EXPERTO
    assert not suceso.encajan(a, b)
    b["tiempo"] = {"inicio": ejemplos.instante("2026-11-07T00:00Z", "dia")}
    assert dicho(a, b).relacion == suceso.MISMO


def test_el_cierre_de_madrugada_es_de_la_noche_de_la_vispera() -> None:
    """EODI-2026-00779 (Lituania, la suspensión del aeropuerto de Kaunas, fechada el miércoles
    11 de noviembre por una nota de las 02:30 de ese día) y EODI-2026-00792 (las alertas desde
    las 23:00 del martes 10): la misma noche. Con la regla de antes eran «dos cierres de noches
    distintas» y nunca se habrían unido."""
    kaunas, lituania = suelta("2026-00779"), f("2026-00792")
    assert kaunas["tiempo"]["inicio"] == {"valor": "2026-11-11T00:00Z", "precision": "dia"}
    assert suceso.noches_del_cierre(kaunas) == {date(2026, 11, 10), date(2026, 11, 11)}
    assert suceso.noches_del_cierre(lituania) == {date(2026, 11, 10)}
    assert not suceso.cierres_de_noches_distintas(kaunas, lituania)
    # Sin la revisión que las une a mano (12 de noviembre), lo decide quien lee las fuentes.
    assert dicho({**kaunas, "id": "EODI-2026-09779"}, lituania).relacion == suceso.EXPERTO
    assert dicho(kaunas, lituania).regla == suceso.REGLA_REVISION
    assert dicho(kaunas, lituania).relacion == suceso.MISMO
    # El cierre del día siguiente por la tarde, con sus noticias de esa tarde, sí es otra noche.
    tarde = copy.deepcopy(kaunas)
    for fuente in tarde["fuentes"]:
        fuente["fecha"] = ejemplos.instante("2026-11-11T19:30Z")
    assert suceso.noches_del_cierre(tarde) == {date(2026, 11, 11)}
    assert suceso.cierres_de_noches_distintas(tarde, lituania)


def test_moldavia_una_noche_no_son_dos_dias() -> None:
    """EODI-2026-00566: «The five drones entered Moldovan airspace over a little more than 17
    hours on Thursday and Friday». La frase da dos días, pero las fuentes cuentan la noche del
    15 al 16 de octubre («în noaptea de 15 spre 16 octombrie») y el dron del viernes tiene ficha
    propia: su inicio está revisado con cita y la ficha no se marca."""
    ficha = f("2026-00566")
    assert ficha["tiempo"]["inicio"]["valor"].startswith("2026-10-15")
    assert suceso.varios_dias(ficha) is not None
    assert not suceso.dos_dias_sin_revisar(ficha)


def test_la_hague_y_flamanville_un_solo_suceso() -> None:
    """EODI-2026-00772: una sola comunicación de la prefectura, «durant le week-end du 1er
    novembre», sin día, hora ni drones por instalación. Nada la marca para separarla."""
    ficha = f("2026-00772")
    assert suceso.varios_dias(ficha) is None
    assert not suceso.dos_dias_sin_revisar(ficha)


# --- La jornada: una noche que cruza la medianoche es una sola --------------------------------


def test_nuremberg_la_madrugada_del_martes() -> None:
    """EODI-2026-00515: «in der Nacht auf Dienstag (13. Oktober)» (merkur.de), «Am Flughafen
    Nürnberg ist es am frühen Dienstagmorgen (13.…» (infranken.de), «in den frühen
    Morgenstunden» (schwaebische.de). El suceso empezó la madrugada del martes 13 de octubre de
    2026: ese es su día. Una ficha de esa misma noche fechada por la víspera no es otro
    suceso."""
    ficha = f("2026-00515")
    assert ficha["tiempo"]["inicio"] == {"valor": "2026-10-13T00:00Z", "precision": "dia"}
    assert any("frühen Morgenstunden" in str(n["frase_origen"]) for n in ficha["fuentes"])
    vispera = {**sin_revisar("2026-00515", "EODI-2026-09515")}
    vispera["tiempo"] = {
        "inicio": ejemplos.instante("2026-10-12T00:00Z", "dia"),
        "origen_inicio": {"tipo": "explicita", "motivo": "«nacht auf dienstag 13 oktober»"},
    }
    assert dicho(vispera, ficha).relacion == suceso.EXPERTO
    # Y al unirse, la que queda conserva su día: no toma el de la que llega.
    assert not suceso.toma_el_tiempo(ficha, vispera)


def test_hamburgo_la_tarde_de_la_vispera() -> None:
    """EODI-2026-00771: «Am Abend wurde an der Führungsakademie der Bundeswehr im Stadtteil
    Nienstedten eine Drohne entdeckt», en una nota del lunes 9 de noviembre a las 14:30: la
    tarde del domingo 8."""
    from zoneinfo import ZoneInfo

    from proceso import fechas

    ficha = f("2026-00771")
    assert ficha["tiempo"]["inicio"]["valor"].startswith("2026-11-08")
    (nota,) = ficha["fuentes"]
    publicacion = suceso.leer_instante(nota["fecha"])
    lecturas = fechas.leer(str(nota["frase_origen"]), publicacion, ZoneInfo("Europe/Berlin"), "de")
    assert [lectura.dia for lectura in lecturas] == [date(2026, 11, 8)]
    assert date(2026, 11, 9) not in lecturas[0].admitidos


# --- La nota de una noche y sus alertas ------------------------------------------------------


def test_letonia_la_nota_de_la_noche_y_sus_alertas_son_el_mismo_suceso() -> None:
    """EODI-2026-00777 (las alertas por municipios de la noche del 10 al 11 de noviembre) y
    EODI-2026-00784 (la nota de las Fuerzas Armadas: «Naktī uz 11. novembri Latvijas gaisa telpā
    ielidoja trīs bezpilota lidaparāti»). El experto las dio por distintas y salieron las dos."""
    alertas, nota = f("2026-00777"), suelta("2026-00784")
    assert frozenset({alertas["id"], nota["id"]}) in DEL_EXPERTO
    # Con sus números reales manda la revisión que las unió.
    assert dicho(alertas, nota).regla == suceso.REGLA_REVISION
    # Como nacieron: la regla 3, aunque el experto las diera por distintas.
    nacida = _nota_de_la_noche()
    del_experto = frozenset({frozenset({alertas["id"], nacida["id"]})})
    veredicto = suceso.veredicto(alertas, nacida, del_experto)
    assert (veredicto.relacion, veredicto.regla) == (suceso.MISMO, suceso.REGLA_RESUMEN)


def _nota_de_la_noche() -> dict[str, Any]:
    """EODI-2026-00784 como nació a las 09:17: con la nota de la noche y nada más (la alerta de
    Smiltene se le enlazó después)."""
    nota = sin_revisar("2026-00784", "EODI-2026-09784")
    nota["fuentes"] = [n for n in nota["fuentes"] if "Naktī uz 11." in str(n["frase_origen"])]
    assert len(nota["fuentes"]) == 4
    return nota


def test_letonia_la_nota_se_une_sola_y_queda_la_ficha_de_las_alertas() -> None:
    almacen = Almacen.abrir()
    alertas = {**_completa(f("2026-00777")), "id": "EODI-2026-09777"}
    for ficha in (alertas, _completa(_nota_de_la_noche())):
        almacen.guardar_incidente(ficha, AHORA, VOCABULARIO_MODELOS)
    assert incidentes.fusionar(almacen, AHORA, VOCABULARIO_MODELOS) == 1
    unida = almacen.incidente("EODI-2026-09784")
    assert unida is not None and unida["fusionado_en"] == "EODI-2026-09777"
    assert incidentes.revisar_fusiones(almacen, AHORA, VOCABULARIO_MODELOS) == []
    assert invariantes.uniones_de_sucesos_distintos(almacen) == []


# --- Países distintos son sucesos distintos ---------------------------------------------------


def test_el_resumen_de_letonia_y_lituania_no_es_ningun_suceso() -> None:
    """EODI-2026-00778: el resumen de la prensa británica «Latvia and Lithuania», con el lugar
    en Letonia. No es la alerta letona (el experto las dio por distintas) ni puede llevar dentro
    la ficha de Lituania."""
    resumen, letona = suelta("2026-00778"), f("2026-00777")
    assert (resumen["lugar"]["pais"], letona["lugar"]["pais"]) == ("LV", "LV")
    veredicto = dicho(resumen, letona)
    assert (veredicto.relacion, veredicto.regla) == (suceso.DISTINTOS, suceso.REGLA_EXPERTO)
    # El filtro no vuelve a compararla con la que el experto dio por distinta: sale o se retira,
    # nunca queda retenida sin salida.
    assert suceso.conjunto(resumen, [letona], DEL_EXPERTO) == []
    # Su país no es firme: las autoridades que cita son lituanas.
    assert not suceso.pais_firme(resumen, DECIDIDAS.get(resumen["id"]))


@pytest.mark.parametrize("lituana", ["00779", "00783", "00785", "00786", "00787"])
def test_las_fichas_de_lituania_no_van_dentro_de_una_de_letonia(lituana: str) -> None:
    """EODI-2026-00779, 00783, 00785, 00786 y 00787 (Lituania, con sus autoridades) quedaron
    unidas por el filtro a EODI-2026-00778 (lugar en Letonia): la definición las da por sucesos
    distintos y esas uniones se deshacen solas, aunque las hiciera quien leyó las fuentes."""
    ficha = suelta(f"2026-{lituana}")
    assert (ficha["lugar"]["pais"], f("2026-00778")["lugar"]["pais"]) == ("LT", "LV")
    assert suceso.pais_firme(ficha, DECIDIDAS.get(ficha["id"]))
    veredicto = dicho(ficha, suelta("2026-00778"))
    assert (veredicto.relacion, veredicto.regla) == (suceso.DISTINTOS, suceso.REGLA_PAISES)
    assert fusion(f"2026-{lituana}", "2026-00778")["motivo"].startswith(suceso.PREFIJO_CONTROL)
    deshecha = se_deshace(f"2026-{lituana}", "2026-00778")
    assert deshecha is not None and deshecha.regla == suceso.REGLA_PAISES


@pytest.mark.parametrize(
    "lituana", ["00779", "00783", "00785", "00786", "00787", "00788", "00789", "00790", "00791"]
)
def test_lituania_una_sola_ficha_de_esa_noche(lituana: str) -> None:
    """Las fichas lituanas de la noche del 10 al 11 de noviembre son el suceso de
    EODI-2026-00792: nada las da por distintas de ella y entran en su conjunto de comparación
    (las une la regla si dan el mismo sitio y la misma jornada; si no, quien lee las fuentes)."""
    ficha, lituania = suelta(f"2026-{lituana}"), f("2026-00792")
    veredicto = dicho(ficha, lituania)
    assert veredicto.relacion in (suceso.MISMO, suceso.EXPERTO), veredicto
    comparadas = suceso.conjunto(ficha, [lituania, f("2026-00777")], DEL_EXPERTO)
    assert "EODI-2026-00792" in [d["id"] for d in comparadas]
    # Y nunca es la de Letonia.
    assert dicho(ficha, f("2026-00777")).relacion == suceso.DISTINTOS


def test_el_dron_de_letonia_no_va_dentro_de_una_ficha_de_rumania() -> None:
    """EODI-2026-00218 (el dron derribado sobre Letonia el 14 de agosto de 2026, región de
    Balvi, con la declaración de las Fuerzas Armadas letonas) estaba unida desde el 13 de
    octubre a EODI-2026-00230 (Tulcea, Rumanía, 13 de agosto) por la regla de fusión, de cuando
    la 00218 aún tenía el lugar en Tulcea."""
    letona, rumana = f("2026-00218"), f("2026-00230")
    assert (letona["lugar"]["pais"], rumana["lugar"]["pais"]) == ("LV", "RO")
    assert fusion("2026-00218", "2026-00230")["motivo"] == suceso.MOTIVO_SITIO_Y_JORNADA
    deshecha = se_deshace("2026-00218", "2026-00230")
    assert deshecha is not None and deshecha.regla == suceso.REGLA_PAISES
    assert auditoria_fichas.uniones_marcadas([letona, rumana]) == [
        "EODI-2026-00218→EODI-2026-00230"
    ]
    # Su suceso ya tiene ficha: EODI-2026-00140, el derribo del 14 de agosto en Balvi. Suelta,
    # la 00218 es de su conjunto y nada las da por distintas.
    propia, derribo = suelta("2026-00218"), f("2026-00140")
    assert (derribo["lugar"]["pais"], derribo["tiempo"]["inicio"]["valor"][:10]) == (
        "LV", "2026-08-14",
    )  # fmt: skip
    assert dicho(propia, derribo).relacion in (suceso.MISMO, suceso.EXPERTO)
    assert derribo["id"] in [d["id"] for d in suceso.conjunto(propia, [derribo, rumana])]
    # La unión que una revisión hizo a mano dentro de ella sigue: EODI-2026-00310 es su suceso.
    assert se_deshace("2026-00310", "2026-00218") is None


def test_sin_autoridad_de_ninguno_de_los_dos_paises_decide_quien_lee_las_fuentes() -> None:
    """Estonia (EODI-2026-00801, dos noticias, ninguna autoridad) frente a Lituania
    (EODI-2026-00792, con las suyas): basta la de una para que sean sucesos distintos. Dos
    fichas de países vecinos sin autoridad de ninguno (un buque en el mar) no son firmes."""
    estonia, lituania = f("2026-00801"), f("2026-00792")
    assert not suceso.pais_firme(estonia) and suceso.pais_firme(lituania)
    assert dicho(estonia, lituania).regla == suceso.REGLA_PAISES
    sin_nadie = {**lituania, "fuentes": [n for n in lituania["fuentes"] if not n["es_autoridad"]]}
    letona = {**estonia, "id": "EODI-2026-09801", "lugar": {"pais": "LV", "nivel": "pais"}}
    assert suceso.veredicto(letona, sin_nadie).relacion == suceso.EXPERTO


# --- El episodio transfronterizo ----------------------------------------------------------------


def test_lituania_letonia_y_estonia_tres_sucesos_y_un_episodio() -> None:
    """La noche del 10 al 11 de noviembre de 2026 un dron cruzó Lituania (EODI-2026-00792: «the
    drones were not shot down and flew into Latvian airspace»; «Šiąnakt dronas perskrido Lietuvą,
    Latviją ir pasiekė Estiją»), Letonia (EODI-2026-00777) y llegó a Estonia (EODI-2026-00801).
    La restricción de Finlandia de esa noche (EODI-2026-00793) no la enlaza ninguna fuente."""
    lituania, letonia, estonia, finlandia = (
        f("2026-00792"), f("2026-00777"), f("2026-00801"), f("2026-00793"),
    )  # fmt: skip
    for a, b in ((lituania, letonia), (letonia, estonia), (lituania, estonia)):
        assert dicho(a, b).relacion == suceso.DISTINTOS
    assert suceso.mismo_episodio_transfronterizo(lituania, letonia)
    assert suceso.mismo_episodio_transfronterizo(letonia, estonia)
    assert not suceso.mismo_episodio_transfronterizo(estonia, finlandia)
    episodios = suceso.episodios_calculados([lituania, letonia, estonia, finlandia])
    assert [(noche, [m["id"] for m in miembros]) for noche, miembros in episodios] == [
        ("2026-11-10", ["EODI-2026-00777", "EODI-2026-00792", "EODI-2026-00801"])
    ]
    # Las unidas y las retiradas no entran en ningún episodio.
    con_mas = [lituania, letonia, estonia, f("2026-00778"), f("2026-00779"), f("2026-00784")]
    assert len(suceso.episodios_calculados(con_mas)[0][1]) == 3


# --- Una noticia sobre un suceso anterior ------------------------------------------------------


def test_otopeni_la_noticia_de_dos_dias_despues_es_el_mismo_suceso() -> None:
    """EODI-2025-00106 (dos noticias del expediente penal, del 30 de septiembre de 2025:
    «Echipajul unei aeronave a semnalat acum două zile…») es el dron de Otopeni del domingo 28
    (EODI-2025-00049). Una revisión las unió, y la que queda no toma el día de la que llega."""
    repetida, suceso_ = suelta("2025-00106"), f("2025-00049")
    assert dicho(repetida, suceso_).relacion == suceso.MISMO
    assert suceso_["tiempo"]["inicio"]["valor"].startswith("2025-09-28")
    # Como estaba la 00049 antes de la unión: con la hora de su primera noticia.
    antes = copy.deepcopy(suceso_)
    antes["tiempo"] = {
        "inicio": ejemplos.instante("2025-09-28T18:45Z", "aproximada"),
        "origen_inicio": {"tipo": "publicacion", "motivo": "fecha de publicación"},
    }
    escrita = copy.deepcopy(repetida)
    escrita["tiempo"] = {
        "inicio": ejemplos.instante("2025-09-30T00:00Z", "dia"),
        "origen_inicio": {"tipo": "relativa", "motivo": "«marti»"},
    }
    assert suceso.fecha_verificada(escrita) and not suceso.fecha_verificada(antes)
    assert not suceso.toma_el_tiempo(antes, escrita)
    # El día que da una fuente para esa misma jornada sí lo toma.
    escrita["tiempo"]["inicio"] = ejemplos.instante("2025-09-28T00:00Z", "dia")
    assert suceso.toma_el_tiempo(antes, escrita)


def test_leipzig_la_noticia_de_noviembre_es_del_suceso_de_agosto() -> None:
    """EODI-2026-00765 (la búsqueda de un sospechoso, 6 de noviembre de 2026: «Anschlagsversuch
    mit Drohne in Leipzig») cuenta el suceso del 4 de agosto (EODI-2026-00134). No es un suceso
    nuevo: el control la compara con las fichas anteriores de su sitio y se une a la suya o se
    retira; nada de la definición lo impide."""
    noticia, agosto = suelta("2026-00765"), f("2026-00134")
    assert suceso.mismo_sitio(noticia, agosto)
    assert suceso.fecha_aproximada(noticia)
    assert [d["id"] for d in suceso.previas_del_sitio(noticia, [agosto])] == ["EODI-2026-00134"]
    assert dicho(noticia, agosto).relacion != suceso.DISTINTOS
    assert "retirado" in f("2026-00765")


def test_iasi_la_revista_de_prensa_del_dia_siguiente() -> None:
    """EODI-2026-00739 (una revista de prensa del 1 de noviembre) cuenta la alerta RO-Alert del
    sábado 31 de octubre (EODI-2026-00719). La unió el control leyendo las fuentes: está en su
    conjunto de comparación y ninguna regla la deshace."""
    revista, alerta = suelta("2026-00739"), f("2026-00719")
    assert "EODI-2026-00719" in [d["id"] for d in suceso.conjunto(revista, [alerta])]
    assert dicho(revista, alerta).relacion != suceso.DISTINTOS
    assert se_deshace("2026-00739", "2026-00719") is None


# --- El mismo día y el mismo país no bastan: el episodio físico ---------------------------------


def test_moldavia_tres_drones_el_mismo_dia_son_tres_sucesos() -> None:
    """30 de septiembre de 2026: el dron de Hîrbovăț (05:43, EODI-2026-00263), el de Lunga
    (10:26, EODI-2026-00160) y el de Brănești (20:45, EODI-2026-00636). Una revisión los separó:
    no se unen ni se preguntan. Las fichas repetidas de cada uno sí son de su suceso."""
    hirbovat, lunga, branesti = f("2026-00263"), f("2026-00160"), f("2026-00636")
    for a, b in ((hirbovat, lunga), (hirbovat, branesti), (lunga, branesti)):
        assert suceso.separados(a, b)
        assert dicho(a, b).relacion in (suceso.DISTINTOS, suceso.AJENAS)
    assert se_deshace("2026-00262", "2026-00636") is None
    assert se_deshace("2026-00527", "2026-00263") is None


def test_sulina_tres_sucesos_la_misma_tarde_y_noche() -> None:
    """14 de octubre de 2026 frente a Sulina: el blanco aéreo de las 17:38 (EODI-2026-00538), el
    petrolero hacia las 20:00 (EODI-2026-00541) y el dron de la 01:34 (EODI-2026-00698, con
    EODI-2026-00544 unida). El mismo sitio y la misma jornada: los separó una revisión."""
    blanco, petrolero, dron = f("2026-00538"), f("2026-00541"), f("2026-00698")
    for a, b in ((blanco, petrolero), (petrolero, dron)):
        assert dicho(a, b).relacion == suceso.DISTINTOS
    assert se_deshace("2026-00544", "2026-00698") is None


# --- La batería entera sobre una base ----------------------------------------------------------


def _completa(ficha: dict[str, Any]) -> dict[str, Any]:
    """La ficha recortada con lo que pide el esquema para guardarla."""
    base = ejemplos.incidente_minimo()
    nueva = {**base, **{k: v for k, v in ficha.items() if k != "fuentes_en_la_base"}}
    primera = nueva["fuentes"][0]
    for fuente in nueva["fuentes"]:
        for clave, valor in base["fuentes"][0].items():
            fuente.setdefault(clave, valor)
    nueva["afirmaciones"] = []
    nueva["tipo"] = "sobrevuelo"
    nueva["estado"] = {
        "actual": "notificado",
        "historial": [
            {"estado": "notificado", "fecha": primera["fecha"], "fuente_id": primera["id"]}
        ],
    }
    for clave in ("respuesta", "drones", "pruebas", "atribucion", "presencia_dron"):
        nueva.pop(clave, None)
    origen = (nueva["tiempo"].get("origen_inicio") or {}).get("fuente_id")
    if origen and origen not in {n["id"] for n in nueva["fuentes"]}:
        nueva["tiempo"]["origen_inicio"].pop("fuente_id")
    return nueva


def test_la_union_de_otro_pais_se_deshace_sola_en_la_base() -> None:
    """EODI-2026-00218 dentro de EODI-2026-00230: `revisar_fusiones` la saca, la invariante I6
    queda a cero y, suelta, no vuelve a unirse a la ficha de Rumanía."""
    almacen = Almacen.abrir()
    # Con otros números: las revisiones a mano van por el número de la ficha.
    rumana = {**_completa(f("2026-00230")), "id": "EODI-2026-09230"}
    letona = {**_completa(suelta("2026-00218")), "id": "EODI-2026-09218"}
    rumana.pop("relacionados", None)
    solo_rumana = {
        **rumana,
        "fuentes": [n for n in rumana["fuentes"] if "lett" not in str(n["enlace"]).lower()],
    }
    almacen.guardar_incidente(solo_rumana, AHORA, VOCABULARIO_MODELOS)
    almacen.guardar_incidente(letona, AHORA, VOCABULARIO_MODELOS)
    nuevo, aportadas = incidentes.absorber(solo_rumana, letona, AHORA)
    almacen.guardar_incidente(nuevo, AHORA, VOCABULARIO_MODELOS)
    almacen.guardar_incidente(
        {**letona, "fusionado_en": "EODI-2026-09230"}, AHORA, VOCABULARIO_MODELOS
    )
    almacen.registrar_fusion(
        "2026-10-13T20:17Z", "EODI-2026-09218", "EODI-2026-09230",
        suceso.MOTIVO_SITIO_Y_JORNADA, aportadas,
        incidentes.instantanea(almacen, solo_rumana, letona),
    )  # fmt: skip
    assert invariantes.uniones_de_sucesos_distintos(almacen) == [
        "EODI-2026-09218→EODI-2026-09230 (paises_distintos)"
    ]
    assert incidentes.revisar_fusiones(almacen, AHORA, VOCABULARIO_MODELOS) == ["EODI-2026-09218"]
    vuelta, queda = almacen.incidente("EODI-2026-09218"), almacen.incidente("EODI-2026-09230")
    assert vuelta is not None and queda is not None
    assert "fusionado_en" not in vuelta and vuelta["lugar"]["pais"] == "LV"
    assert not {n["id"] for n in letona["fuentes"]} & {n["id"] for n in queda["fuentes"]}
    assert invariantes.uniones_de_sucesos_distintos(almacen) == []
    # Idempotente: otra pasada no hace nada, y la regla de fusión no las vuelve a juntar.
    assert incidentes.revisar_fusiones(almacen, AHORA, VOCABULARIO_MODELOS) == []
    assert incidentes.fusionar(almacen, AHORA, VOCABULARIO_MODELOS) == 0


# --- La ficha que queda -------------------------------------------------------------------------


def test_lituania_queda_la_ficha_publicada_no_la_de_numero_mas_bajo() -> None:
    """EODI-2026-00779 nunca salió en la web y EODI-2026-00792 es la ficha publicada de esa
    noche: al unirse queda la publicada. Con la regla de antes («la más antigua») la 00792, con
    sus avisos enviados y sus datos revisados, se habría fundido en la 00779."""
    kaunas, lituania = suelta("2026-00779"), f("2026-00792")
    conserva, une = suceso.queda(kaunas, lituania, {"EODI-2026-00792"}.__contains__)
    assert (conserva["id"], une["id"]) == ("EODI-2026-00792", "EODI-2026-00779")
    # Si salen las dos, o no se sabe, la más antigua.
    assert suceso.queda(kaunas, lituania)[0]["id"] == "EODI-2026-00779"
    assert suceso.queda(kaunas, lituania, lambda _: True)[0]["id"] == "EODI-2026-00779"


def test_la_ficha_de_lituania_sale_de_la_retirada_y_se_une_a_la_publicada() -> None:
    """El camino entero sobre una base: la ficha lituana está fundida por el control en el
    resumen con el lugar en Letonia (retirado); `revisar_fusiones` la saca, quien lee las
    fuentes la une a la ficha publicada de Lituania, y nada les da la vuelta después."""
    from exportacion import puerta
    from recogida import control_fichas as control

    almacen = Almacen.abrir()
    resumen = {**_completa(suelta("2026-00778")), "id": "EODI-2026-09778"}
    kaunas = {**_completa(suelta("2026-00779")), "id": "EODI-2026-09779"}
    lituania = {**_completa(f("2026-00792")), "id": "EODI-2026-09792"}
    for ficha in (resumen, kaunas, lituania):
        almacen.guardar_incidente(ficha, AHORA, VOCABULARIO_MODELOS)
    almacen.guardar_publicado(
        "EODI-2026-09792", puerta.PUBLICADA, "incidentes.geojson", {"id": "EODI-2026-09792"},
        {}, {}, "x",
    )  # fmt: skip
    almacen.guardar_controles(
        {"entrada:EODI-2026-09779": {"autoridades": DECIDIDAS["EODI-2026-00779"]}},
        "2026-11-11T03:17:00Z",
    )
    assert control.unir(almacen, resumen, kaunas, "x", AHORA, VOCABULARIO_MODELOS) is None
    # La unión del 11 de noviembre, hecha antes de la regla: se anota como estaba.
    nuevo, aportadas = incidentes.absorber(resumen, kaunas, AHORA)
    almacen.guardar_incidente(nuevo, AHORA, VOCABULARIO_MODELOS)
    almacen.guardar_incidente(
        {**kaunas, "fusionado_en": "EODI-2026-09778"}, AHORA, VOCABULARIO_MODELOS
    )
    almacen.registrar_fusion(
        "2026-11-11T03:17Z", "EODI-2026-09779", "EODI-2026-09778",
        suceso.PREFIJO_CONTROL + "filtro de entrada: Es la misma alerta", aportadas,
        incidentes.instantanea(almacen, resumen, kaunas),
    )  # fmt: skip

    assert incidentes.revisar_fusiones(almacen, AHORA, VOCABULARIO_MODELOS) == ["EODI-2026-09779"]
    vuelta = almacen.incidente("EODI-2026-09779")
    publicada = almacen.incidente("EODI-2026-09792")
    assert vuelta is not None and publicada is not None and "fusionado_en" not in vuelta
    conserva, une = suceso.queda(vuelta, publicada, almacen.sale_en_la_web)
    assert conserva["id"] == "EODI-2026-09792"
    assert control.unir(almacen, conserva, une, "la misma noche", AHORA, VOCABULARIO_MODELOS)
    queda = almacen.incidente("EODI-2026-09792")
    unida = almacen.incidente("EODI-2026-09779")
    assert queda is not None and unida is not None
    assert unida["fusionado_en"] == "EODI-2026-09792"
    assert {n["id"] for n in kaunas["fuentes"]} <= {n["id"] for n in queda["fuentes"]}
    # La renumeración de «la más antigua» no les da la vuelta, ni nada deshace la unión.
    decision = {
        "decision": "mismo", "conserva": "EODI-2026-09792", "une": "EODI-2026-09779",
        "motivo_es": "la misma noche",
    }  # fmt: skip
    par = suceso.clave_par("EODI-2026-09779", "EODI-2026-09792")
    assert (
        control.conservar_la_mas_antigua(almacen, {par: decision}, AHORA, VOCABULARIO_MODELOS) == {}
    )
    assert incidentes.revisar_fusiones(almacen, AHORA, VOCABULARIO_MODELOS) == []
    assert invariantes.uniones_de_sucesos_distintos(almacen) == []


def test_la_ficha_que_vuelve_de_una_union_deshecha_pasa_otra_vez_por_el_filtro() -> None:
    """EODI-2026-00779 tiene en el filtro la decisión «unida» (a EODI-2026-00778). Al deshacerse
    esa unión vuelve a estar activa con las mismas fuentes: tiene que pasar otra vez por el
    filtro, que es quien la une a la ficha de su suceso."""
    from recogida import entrada

    kaunas = suelta("2026-00779")
    decision = {
        "decision": entrada.UNIDA, "huella": entrada.huella(kaunas),
        "conserva": "EODI-2026-00778", "une": "EODI-2026-00779",
    }  # fmt: skip
    assert entrada.vigente(decision, kaunas)
    assert entrada.pendiente(decision, kaunas, AHORA)
    # Una que el filtro dejó publicar y no ha cambiado, no.
    assert not entrada.pendiente({**decision, "decision": entrada.PUBLICAR}, kaunas, AHORA)
