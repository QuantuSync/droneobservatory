"""Lo que no es un suceso no es ficha (proceso/no_es_suceso.py). El caso: la EODI-2026-00539,
un reportaje de contenido de socio de delfi.lt (sección «Pulsas / Poveikis») sobre la defensa
aérea de la OTAN, sin ningún suceso concreto (retirada a mano en el PR #242)."""

from dataclasses import replace
from typing import Any

import pytest

from almacen.base import Almacen
from modelo import coste, ficha, paginas
from proceso import extraccion, no_es_suceso
from tests.test_extraccion import AHORA, MODELOS, campo, ficha_ejemplo
from tests.test_modelos import BASE, EXPERTO, Cliente, _peticion
from tests.test_nada_se_retira import POLICIA, _publicada, _respuesta_base, _sigue_publicada

DELFI_00539 = (
    "https://delfi.lt/projektai/pulsas/poveikis/"
    "nato-kariai-pasakoja-kaip-elgiasi-i-sali-iskridus-dronui-120318834"
)
TITULAR_00539 = "NATO kariai pasakoja, kaip elgiasi į šalį įskridus dronui"
# Las marcas que daba la página de la 00539 (modelo/paginas.marcas, 15 de octubre de 2026).
MARCAS_00539 = (
    "keywords=koviniai dronai, #PulsEurope, Oro pavojus", "og:type=article",
    "article:section=Delfi, Pulsas, Poveikis", "ld:@type=NewsArticle", "ld:articleSection=Poveikis",
)  # fmt: skip
# Una página de delfi.lt: el menú de todas sus páginas lleva «Reklama» y «Užsakomasis turinys».
PAGINA_CON_MENU = """<html><head>
<meta property="og:type" content="article">
<meta property="article:section" content="Lietuvoje">
<script type="application/ld+json">{"@context":"https://schema.org","@type":"NewsArticle",
"articleSection":"Lietuvoje"}</script></head>
<body class="page"><nav><a href="/apie/reklama/">Reklama</a>
<a href="/uzsakomasis-turinys/">Užsakomasis turinys</a></nav>
<article class="article"><p>Virš Vilniaus oro uosto pastebėtas dronas, skrydžiai sustabdyti dviem
valandoms, pranešė oro uosto atstovai.</p></article></body></html>"""
PAGINA_OPINION = """<html><head>
<meta property="article:section" content="Opinion">
<script type="application/ld+json">{"@graph":[{"@type":"OpinionNewsArticle"}]}</script>
</head><body class="single sponsored-off"><p>x</p></body></html>"""


def _fuentes_00539(peticion: extraccion.Peticion) -> extraccion.Peticion:
    """La petición con la fuente de la 00539: dirección y marcas de su página."""
    fuentes = [
        no_es_suceso.con_aviso(replace(f, titular=TITULAR_00539, url=DELFI_00539,
                                       marcas=MARCAS_00539, medio="delfi.lt"))
        for f in peticion.fuentes
    ]  # fmt: skip
    return replace(peticion, fuentes=fuentes)


def _opinion(peticion: extraccion.Peticion) -> extraccion.Peticion:
    fuentes = [
        no_es_suceso.con_aviso(replace(f, titular=f"Kommentar: {f.titular}",
                                       url="https://example.de/meinung/drohnen-1"))
        for f in peticion.fuentes
    ]  # fmt: skip
    return replace(peticion, fuentes=fuentes)


@pytest.fixture(autouse=True)
def dos_modelos(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EODI_MODELO_BASE", BASE)
    monkeypatch.setenv("EODI_MODELO_EXPERTO", EXPERTO)


@pytest.fixture
def almacen() -> Any:
    a = Almacen.abrir()
    yield a
    a.cerrar()


NO_ES = {"es_incidente": campo(False, "Københavns Lufthavn", 0.9)}


# --- Señales ----------------------------------------------------------------------------------


def test_la_00539_es_contenido_de_socio() -> None:
    veredicto = no_es_suceso.de_fuente(TITULAR_00539, DELFI_00539, MARCAS_00539, "delfi.lt")
    assert veredicto is not None and veredicto.categoria == "patrocinado" and veredicto.segura
    assert "No es un suceso" in veredicto.motivo() and "Not an event" in veredicto.motivo_en()


@pytest.mark.parametrize(
    ("titular", "url", "marcas", "categoria"),
    [
        ("Drones over the base", "https://x.eu/a", ("article:section=Sponsored",), "patrocinado"),
        ("Drohnen", "https://x.de/a", ("article:tag=Anzeige",), "patrocinado"),
        ("Drohnen", "https://x.de/a", ("keywords=Partnerinhalt, Drohnen",), "patrocinado"),
        ("Drones", "https://x.es/a", ("article:section=Contenido patrocinado",), "patrocinado"),
        ("Dronai", "https://x.lt/a", ("article:section=Turinio partneris",), "patrocinado"),
        ("Drones", "https://x.com/a", ("ld:@type=AdvertiserContentArticle",), "patrocinado"),
        ("Drones", "https://x.com/advertorial/drones-1", (), "patrocinado"),
        ("Drony", "https://x.pl/a", ("article:section=Artykuł sponsorowany",), "patrocinado"),
        ("Opinión: el muro de drones", "https://x.es/a", (), "opinion"),
        ("Op-ed | Europe needs a drone wall", "https://x.com/a", (), "opinion"),
        ("Drohnen über dem Flughafen", "https://x.de/kommentar/a", (), "opinion"),
        ("Drones", "https://x.com/a", ("ld:@type=OpinionNewsArticle",), "opinion"),
        ("Cómo funciona la defensa antidrones de la OTAN", "https://x.es/a", (), "explicativo"),
        ("How the drone wall works", "https://x.com/a", (), "explicativo"),
        ("Interview: General über Drohnenabwehr", "https://x.de/a", (), "entrevista"),
        ("Analysis: what the drone incursions mean", "https://x.com/a", (), "analisis"),
    ],
)
def test_senales_en_varios_idiomas(
    titular: str, url: str, marcas: tuple[str, ...], categoria: str
) -> None:
    veredicto = no_es_suceso.de_fuente(titular, url, marcas)
    assert veredicto is not None and veredicto.categoria == categoria


@pytest.mark.parametrize(
    "titular",
    [
        "Drohnen über dem Flughafen München gesichtet",
        "Copenhagen Airport closed after drone sightings",
        "Lotnisko w Rzeszowie zamknięte z powodu drona",
        "Police: drones seen over the base, an interview with the commander follows",
    ],
)
def test_una_noticia_de_un_suceso_no_tiene_senal(titular: str) -> None:
    assert no_es_suceso.de_fuente(titular, "https://x.eu/news/1", ("og:type=article",)) is None


# Del repaso de las fichas publicadas del 15 de octubre de 2026: noticias de sucesos que no deben
# quedar marcadas.
@pytest.mark.parametrize(
    ("titular", "url", "marcas"),
    [
        # EODI-2026-00043 y 00080: ladepeche.fr pone «article:opinion=false» en todas sus noticias.
        ("Un drone aperçu au-dessus de l'aéroport Toulouse-Blagnac",
         "https://ladepeche.fr/2026/02/27/un-drone-apercu-13247992.php",
         ("og:type=article", "article:opinion=false", "ld:articleSection=Faits divers")),
        # EODI-2025-00281: lo mismo en dailymail.co.uk.
        ("British Airways plane near miss with drone", "https://dailymail.co.uk/news/article-1.html",
         ("article:section=News", "article:opinion=false", "ld:@type=NewsArticle")),
        # EODI-2025-00199: un directo de nieuwsblad.be que cuenta el cierre de Bruselas.
        ("LIVE. Luchtverkeer op Brussels Airport kort stilgelegd na dronemelding",
         "https://nieuwsblad.be/binnenland/live.-luchtverkeer-op-brussels-airport/1.html", ()),
    ],
)  # fmt: skip
def test_lo_que_marcaba_de_mas_el_repaso(titular: str, url: str, marcas: tuple[str, ...]) -> None:
    assert no_es_suceso.de_fuente(titular, url, marcas) is None
    assert no_es_suceso.de_fuente("x", url, ("article:opinion=true",)) is not None


def test_las_marcas_no_salen_del_menu() -> None:
    marcas = paginas.marcas(PAGINA_CON_MENU)
    assert "article:section=Lietuvoje" in marcas
    assert no_es_suceso.de_fuente("Virš oro uosto dronas", "https://delfi.lt/a", marcas) is None


def test_las_marcas_de_la_pagina_y_de_sus_datos_estructurados() -> None:
    marcas = paginas.marcas(PAGINA_OPINION)
    assert "article:section=Opinion" in marcas and "ld:@type=OpinionNewsArticle" in marcas
    assert not any(m.startswith("clase") for m in marcas)
    veredicto = no_es_suceso.de_fuente("Drones", "https://x.com/a", marcas)
    assert veredicto is not None and veredicto.categoria == "opinion"


def test_basta_una_fuente_que_cuente_el_suceso() -> None:
    patrocinada = ficha.FuenteTexto("delfi.lt", "", "lt", TITULAR_00539, "", DELFI_00539,
                                    MARCAS_00539)  # fmt: skip
    noticia = ficha.FuenteTexto("lrt.lt", "", "lt", "Dronas virš Vilniaus oro uosto", "",
                                "https://lrt.lt/naujienos/1")  # fmt: skip
    assert no_es_suceso.de_fuentes([patrocinada, noticia]) is None
    veredicto = no_es_suceso.de_fuentes([patrocinada])
    assert veredicto is not None and veredicto.segura


def test_el_modelo_ve_lo_que_dice_la_pagina() -> None:
    fuente = no_es_suceso.con_aviso(
        ficha.FuenteTexto("delfi.lt", "", "lt", TITULAR_00539, "x", DELFI_00539, MARCAS_00539)
    )
    assert "La página lo marca como contenido patrocinado o de socio." in fuente.bloque(1)


# --- Una ficha nueva --------------------------------------------------------------------------


def test_la_00539_no_se_publica_y_no_gasta_en_el_experto(almacen: Almacen) -> None:
    peticion = _fuentes_00539(_peticion(almacen))
    # El base la da por suceso, como pasó el 14 de octubre de 2026.
    cliente = Cliente(
        ficha_ejemplo(declaraciones=[POLICIA]), ficha_ejemplo(declaraciones=[POLICIA])
    )
    hechas = extraccion.extraer(almacen, cliente, [peticion], AHORA, coste.Modo.HORARIO, MODELOS)
    assert cliente.pedidas == [BASE]
    assert hechas.incidentes == [None] and not almacen.incidentes()
    (extraida,) = almacen.extracciones(peticion.candidato["id"])
    assert extraida["no_es_suceso"]["categoria"] == "patrocinado"
    assert any(m.startswith("no_es_suceso: patrocinado") for m in extraida["motivos"])


def test_con_duda_decide_el_experto(almacen: Almacen) -> None:
    peticion = _opinion(_peticion(almacen))
    cliente = Cliente(ficha_ejemplo(), ficha_ejemplo(**NO_ES))
    hechas = extraccion.extraer(almacen, cliente, [peticion], AHORA, coste.Modo.HORARIO, MODELOS)
    assert cliente.pedidas == [BASE, EXPERTO]
    assert hechas.incidentes == [None]
    (extraida,) = almacen.extracciones(peticion.candidato["id"])
    assert any(m.startswith("no_es_suceso: opinion") for m in extraida["escalado"])


def test_si_el_experto_ve_un_suceso_se_publica(almacen: Almacen) -> None:
    peticion = _opinion(_peticion(almacen))
    cliente = Cliente(
        ficha_ejemplo(declaraciones=[POLICIA]), ficha_ejemplo(declaraciones=[POLICIA])
    )
    hechas = extraccion.extraer(almacen, cliente, [peticion], AHORA, coste.Modo.HORARIO, MODELOS)
    assert cliente.pedidas == [BASE, EXPERTO] and hechas.incidentes[0] is not None


# --- Una ficha publicada: nada se retira sin el experto ---------------------------------------


def test_una_publicada_que_no_es_suceso_la_retira_el_experto_en_dos_idiomas(
    almacen: Almacen,
) -> None:
    peticion, id_ = _publicada(almacen)
    peticion = _fuentes_00539(peticion)
    # El base sigue diciendo que es un suceso: se escala por la página.
    cliente = Cliente(ficha_ejemplo(), ficha_ejemplo(**NO_ES))
    extraccion.extraer(almacen, cliente, [peticion], AHORA, coste.Modo.HORARIO, MODELOS)
    assert cliente.pedidas == [BASE, EXPERTO]
    incidente = almacen.incidente(id_)
    assert incidente is not None
    retirado = incidente["retirado"]
    assert retirado["motivo"].startswith("No es un suceso: la fuente es contenido patrocinado")
    assert retirado["motivo_en"].startswith("Not an event: the source is sponsored")


def test_sin_el_experto_la_publicada_se_queda(almacen: Almacen) -> None:
    peticion, id_ = _publicada(almacen)
    peticion = _fuentes_00539(peticion)
    # Una respuesta del base sin escalar (un lote): no retira, el candidato espera al experto.
    respuesta = _respuesta_base(ficha_ejemplo())
    extraccion.procesar_respuesta(almacen, peticion, respuesta, AHORA, coste.Modo.HISTORICO, True,
                                  MODELOS)  # fmt: skip
    _sigue_publicada(almacen, id_)
    espera = extraccion.esperan_experto(almacen)[peticion.candidato["id"]]
    assert espera["revision"]
    assert any("no_es_suceso: patrocinado" in m for m in espera["motivos"])


# --- El control de las fichas publicadas ------------------------------------------------------


def _ficha_00539(fiabilidad: str = "C") -> dict[str, Any]:
    return {
        "id": "EODI-2026-00539", "control": {"candidato": "CAND-00539"},
        "fuentes": [{"id": "f1", "medio": "delfi.lt", "enlace": DELFI_00539,
                     "fiabilidad": fiabilidad, "publica": True}],
    }  # fmt: skip


def test_el_control_manda_al_experto_una_publicada_que_no_es_suceso(almacen: Almacen) -> None:
    from types import SimpleNamespace

    from recogida import control_fichas

    leidas = {DELFI_00539: paginas.Pagina("x", MARCAS_00539)}
    veredicto = control_fichas.no_es_suceso_de(almacen, _ficha_00539(), leidas)
    assert veredicto is not None and veredicto.categoria == "patrocinado"
    # Con una fuente oficial, o sin haber leído todas las fuentes, nunca.
    assert control_fichas.no_es_suceso_de(almacen, _ficha_00539("B"), leidas) is None
    assert control_fichas.no_es_suceso_de(almacen, _ficha_00539(), {}) is None
    ctx: Any = SimpleNamespace(almacen=almacen, ahora=AHORA)
    assert control_fichas.senalar_no_suceso(ctx, _ficha_00539(), veredicto)
    espera = extraccion.esperan_experto(almacen)["CAND-00539"]
    assert espera["revision"] and espera["motivos"][0].startswith("no_es_suceso: patrocinado")
    # Una vez anotada no se vuelve a anotar.
    assert not control_fichas.senalar_no_suceso(ctx, _ficha_00539(), veredicto)


def test_lo_que_el_experto_mantuvo_no_se_le_vuelve_a_mandar(almacen: Almacen) -> None:
    from types import SimpleNamespace

    from recogida import control_fichas

    peticion, id_ = _publicada(almacen)
    peticion = _opinion(peticion)
    # El experto la ve con el motivo de la página y la mantiene.
    cliente = Cliente(
        ficha_ejemplo(declaraciones=[POLICIA]), ficha_ejemplo(declaraciones=[POLICIA])
    )
    extraccion.extraer(almacen, cliente, [peticion], AHORA, coste.Modo.HORARIO, MODELOS)
    assert cliente.pedidas == [BASE, EXPERTO]
    _sigue_publicada(almacen, id_)
    incidente = almacen.incidente(id_)
    assert incidente is not None
    veredicto = no_es_suceso.de_fuentes(peticion.fuentes)
    assert veredicto is not None
    ctx: Any = SimpleNamespace(almacen=almacen, ahora=AHORA)
    assert not control_fichas.senalar_no_suceso(ctx, incidente, veredicto)
