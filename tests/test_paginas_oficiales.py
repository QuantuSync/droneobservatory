"""Lectores de las páginas oficiales sin red: una página y una nota por fuente."""

from datetime import UTC, datetime
from typing import Any

import pytest

from almacen.base import Almacen
from proceso.noticias import filtro
from recogida import oficiales, paginas_oficiales
from recogida.descarga import Descargador, Respuesta
from tests.test_extraccion import MODELOS, extraer_ejemplo

PARRAFO = "Texto de la nota con el detalle de lo ocurrido, lo bastante largo para no ser un menú."


def fuente(id_: str) -> dict[str, Any]:
    return next(f for f in oficiales.fuentes() if f["id"] == id_)


# Por fuente: página de noticias, dirección y título esperados, nota y fecha esperada.
CASOS = [
    (
        "mapn",
        '<a href="https://www.mapn.ro/cpresa/19397_fragmente-de-drona">Fragmente de dronă'
        ', neutralizate , din 10.09.2026</a><a href="https://www.mapn.ro/tabara/">Tabăra</a>',
        "https://www.mapn.ro/cpresa/19397_fragmente-de-drona",
        "Fragmente de dronă, neutralizate",
        "<div>28.09.2026</div><div>Nr. 289 10.09.2026 Print</div>",
        (datetime(2026, 9, 10, tzinfo=UTC), "dia"),
    ),
    (
        "dfs",
        '<a href="https://www.dfs.de/homepage/de/medien/presse/2026/22-09-2026-drohne/">'
        "09/22/2026 Drohne am Flughafen Frankfurt09/22/2026Mehr</a>",
        "https://www.dfs.de/homepage/de/medien/presse/2026/22-09-2026-drohne/",
        "Drohne am Flughafen Frankfurt",
        '<script type="application/ld+json">{"datePublished":"2026-09-22T14:30:00+02:00'
        '[Europe/Berlin]"}</script>',
        (datetime(2026, 9, 22, 12, 30, tzinfo=UTC), "minuto"),
    ),
    (
        "mod_lv",
        '<a href="/lv/zinas/drons-virs-lielvardes-bazes">Drons virs Lielvārdes bāzes</a>',
        "https://www.mod.gov.lv/lv/zinas/drons-virs-lielvardes-bazes",
        "Drons virs Lielvārdes bāzes",
        "<h1>Drons virs Lielvārdes bāzes</h1><span>28.09.2026</span>",
        (datetime(2026, 9, 28, tzinfo=UTC), "dia"),
    ),
    (
        "mod_md",
        '<a href="/ro/comunicate-de-presa/drona-cazuta-in-raionul-cahul">Dronă căzută în '
        "raionul Cahul</a>",
        "https://www.army.md/ro/comunicate-de-presa/drona-cazuta-in-raionul-cahul",
        "Dronă căzută în raionul Cahul",
        "<span>27 Sep 2026</span> <span>28</span> <span>1 min</span>",
        (datetime(2026, 9, 27, tzinfo=UTC), "dia"),
    ),
    (
        "riga_airport",
        '<a href="/en/news/drone-sighting-near-riga-airport">22/09/2026 Drone sighting near '
        "Riga Airport</a>",
        "https://www.riga-airport.com/en/news/drone-sighting-near-riga-airport",
        "Drone sighting near Riga Airport",
        "<div>Home / Drone sighting near Riga Airport 22/09/2026</div>",
        (datetime(2026, 9, 22, tzinfo=UTC), "dia"),
    ),
    (
        "finavia",
        '<a href="/fi/uutishuone/2026/drooni-helsinki-vantaalla?x=1">Drooni Helsinki-Vantaalla</a>',
        "https://www.finavia.fi/fi/uutishuone/2026/drooni-helsinki-vantaalla?x=1",
        "Drooni Helsinki-Vantaalla",
        '<script type="application/ld+json">{"datePublished": "2026-09-18T12:07:49+0300"}</script>',
        (datetime(2026, 9, 18, 9, 7, tzinfo=UTC), "minuto"),
    ),
    (
        "austrocontrol",
        '<a href="/unternehmen/medien/presse__news/detail/drohne_wien">Drohne über '
        "Flughafen Wien</a>",
        "https://www.austrocontrol.at/unternehmen/medien/presse__news/detail/drohne_wien",
        "Drohne über Flughafen Wien",
        "<div>So 06.09.2026 zurück zur Liste</div>",
        (datetime(2026, 9, 6, tzinfo=UTC), "dia"),
    ),
    (
        "muc",
        '<a href="/presse-drohne-legt-flugbetrieb-lahm-43059920">03.10.2025 Presse: Drohne '
        "legt Flugbetrieb lahm</a>",
        "https://www.munich-airport.de/presse-drohne-legt-flugbetrieb-lahm-43059920",
        "Drohne legt Flugbetrieb lahm",
        "<div>3.10.2025 Drohne legt Flugbetrieb lahm</div><div>Weitere Themen 01.10.2025</div>",
        (datetime(2025, 10, 3, tzinfo=UTC), "dia"),
    ),
    (
        "mod_se",
        '<a href="/pressmeddelanden/2025/09/dronare-over-karlskrona/">Drönare över Karlskrona</a>',
        "https://www.regeringen.se/pressmeddelanden/2025/09/dronare-over-karlskrona/",
        "Drönare över Karlskrona",
        '<script type="application/ld+json">{"datePublished":"2025-09-16T14:00:23.0000000'
        '+02:00"}</script><time datetime="2025-08-29"></time>',
        (datetime(2025, 9, 16, 12, 0, tzinfo=UTC), "minuto"),
    ),
]


@pytest.mark.parametrize(("id_", "pagina", "direccion", "titulo", "cabecera", "fecha"), CASOS)
def test_lector_de_cada_fuente(
    id_: str,
    pagina: str,
    direccion: str,
    titulo: str,
    cabecera: str,
    fecha: tuple[datetime, str],
) -> None:
    datos = fuente(id_)
    assert paginas_oficiales.enlaces(f"<html><body>{pagina}</body></html>", datos) == [
        (direccion, titulo)
    ]
    articulo = f"<html><head></head><body>{cabecera}<p>Menú</p><p>{PARRAFO}</p></body></html>"
    assert paginas_oficiales.contenido(articulo, datos, titulo) == (*fecha, PARRAFO)


def test_direcciones_con_letras_no_ascii_se_codifican() -> None:
    pagina = '<a href="/cpresa/19397_Fragmente-de-dronă">Fragmente de dronă</a>'
    ((direccion, _),) = paginas_oficiales.enlaces(pagina, fuente("mapn"))
    assert direccion == "https://www.mapn.ro/cpresa/19397_Fragmente-de-dron%C4%83"


def test_fecha_con_el_mes_en_danes() -> None:
    danesa = {"zona": "Europe/Copenhagen", "fecha": r"(\d{1,2}\. (?:maj|oktober) \d{4})"}
    articulo = f"<div>26-10-2025</div><div>3. oktober 2025</div><p>{PARRAFO}</p>"
    assert paginas_oficiales.contenido(articulo, danesa, "x") == (
        datetime(2025, 10, 3, tzinfo=UTC),
        "dia",
        PARRAFO,
    )


def test_sin_fecha_no_hay_nota() -> None:
    assert paginas_oficiales.contenido(f"<p>{PARRAFO}</p>", fuente("mapn"), "x") is None


def test_titulos_genericos_se_abren() -> None:
    mapn = fuente("mapn")
    dron = filtro().dron
    assert paginas_oficiales.interesa("Informație de presă", mapn, dron)
    assert not paginas_oficiales.interesa("Ziua Crucii, marcată pe Vârful Caraiman", mapn, dron)


def test_rss_de_la_defensa_belga() -> None:
    rss = """<rss version="2.0"><channel><item><title>Drones boven Kleine-Brogel</title>
    <link>https://www.mil.be/nl/news/drones-boven-kleine-brogel/</link>
    <pubDate>Mon, 03 Nov 2025 10:00:00 GMT</pubDate></item></channel></rss>"""
    (nota,) = oficiales.leer_rss(rss, fuente("mod_be"))
    assert nota.id == "mod_be-nl-news-drones-boven-kleine-brogel"


AHORA = datetime(2025, 9, 24, 12, tzinfo=UTC)
PAGINA_DK = {"id": "forsvar_ejemplo", "medio": "Forsvaret", "pais": "DK", "idioma": "da",
             "tipo": "pagina", "zona": "Europe/Copenhagen", "url": "https://forsvar.ejemplo/nyt/",
             "enlace": r"/nyt/\d+-"}  # fmt: skip
LISTA_DK = '<a href="/nyt/7-droner">Mulige droner over Københavns Lufthavn</a><a href="/om">Om</a>'
NOTA_DK = (
    '<meta property="article:published_time" content="2025-09-23T08:00:00+02:00">'
    "<p>Politiet undersøger observationer af mulige droner over Københavns Lufthavn mandag.</p>"
)


class Sitio:
    def __init__(self) -> None:
        self.pedidas: list[str] = []

    def __call__(self, url: str, cabeceras: dict[str, str], limite_s: float) -> Respuesta:
        self.pedidas.append(url)
        if url.endswith("/robots.txt"):
            return 200, {}, b"User-agent: *\nDisallow: /om\n"
        return 200, {}, (NOTA_DK if "/nyt/7" in url else LISTA_DK).encode()


def test_la_nota_de_una_pagina_confirma_sin_tocar_la_presencia() -> None:
    almacen = Almacen.abrir()
    id_ = extraer_ejemplo(almacen)
    sitio = Sitio()
    descargador = Descargador(sitio, dormir=lambda _: None, pausa_minima_s=0)
    lector = oficiales.robots(descargador, PAGINA_DK["url"])
    (nota,) = oficiales.leer_pagina(descargador, lector, PAGINA_DK)
    assert (nota.fecha, nota.precision) == (datetime(2025, 9, 23, 6, tzinfo=UTC), "minuto")
    assert oficiales.enlazar(almacen, nota, AHORA, MODELOS) == id_
    incidente = almacen.incidente(str(id_))
    assert incidente is not None
    assert incidente["estado"]["actual"] == "confirmado"
    # «mulige droner»: la autoridad no afirma que hubiera drones.
    assert incidente["presencia_dron"] == "no_confirmada"
    assert "https://forsvar.ejemplo/om" not in sitio.pedidas
