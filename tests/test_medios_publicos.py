"""Medios públicos leídos directamente: LRT (Lituania), con sus listas y sus notas de la noche
del 10 al 11 de noviembre de 2026, leídas desde el servidor el 11 y recortadas a lo que usa el
lector. Y el canal de las Fuerzas de Defensa de Estonia, de ese mismo día."""

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from almacen.base import Almacen
from proceso import autoridades
from proceso.noticias import filtro
from recogida import extractor, medios_publicos, oficiales, paginas_oficiales
from recogida.descarga import Descargador, Respuesta

FIXTURES = Path(__file__).resolve().parent / "fixtures"
AHORA = datetime(2026, 11, 11, 8, 17, tzinfo=UTC)
ALERTAS = "https://www.lrt.lt/en/news-in-english/19/3111025/drone-incursions-trigger-air-alerts-across-lithuania-nato-jets-scrambled"
ANULADA = "https://www.lrt.lt/en/news-in-english/19/3110468/lithuania-calls-off-air-alert-warning-in-vilnius-and-utena-regions"
VUELOS = "https://www.lrt.lt/en/news-in-english/19/3111061/airspace-restrictions-disrupt-three-flights-carrying-465-passengers-at-vilnius-airport"
NOCHE = "https://www.lrt.lt/naujienos/lietuvoje/2/3111046/neramiausia-naktis-naikintuvai-drona-bande-numusti-du-kartus-taciau-nepavyko"
PAGINAS = {
    "https://www.lrt.lt/en/news-in-english": "lista_en.html",
    "https://www.lrt.lt/naujienos/lietuvoje": "lista_lt.html",
    ALERTAS: "3111025.html",
    ANULADA: "3110468.html",
    VUELOS: "3111061.html",
    NOCHE: "3111046.html",
}


def _medio(id_: str) -> dict[str, Any]:
    return next(m for m in medios_publicos.medios() if m["id"] == id_)


class _Sitio:
    def __init__(self, robots: str = "") -> None:
        self.pedidas: list[str] = []
        self.robots = robots

    def __call__(self, url: str, cabeceras: dict[str, str], limite_s: float) -> Respuesta:
        self.pedidas.append(url)
        if url.endswith("/robots.txt"):
            return 200, {}, self.robots.encode()
        if url not in PAGINAS:
            return 404, {}, b""
        return 200, {}, (FIXTURES / "lrt" / PAGINAS[url]).read_bytes()


def _descargador(sitio: _Sitio) -> Descargador:
    return Descargador(transporte=sitio, dormir=lambda _s: None, pausa_minima_s=0.0, reintentos=0)


def test_los_dos_medios_de_lrt() -> None:
    assert [m["id"] for m in medios_publicos.medios()] == ["lrt_en", "lrt_lt"]
    for medio in medios_publicos.medios():
        assert (medio["medio"], medio["pais"], medio["tipo"]) == ("lrt.lt", "LT", "pagina")
        assert medio["url"].startswith("https://www.lrt.lt/")
    # No son fuentes oficiales: ni están en su lista ni cuentan como medio de una autoridad.
    assert not {m["id"] for m in medios_publicos.medios()} & {f["id"] for f in oficiales.fuentes()}
    assert "lrt.lt" not in autoridades._paises_oficiales()


def test_las_listas_dan_las_notas_de_la_alerta() -> None:
    dron = filtro().dron
    interesan = {}
    for id_, lista in (("lrt_en", "lista_en.html"), ("lrt_lt", "lista_lt.html")):
        pagina = (FIXTURES / "lrt" / lista).read_text(encoding="utf-8")
        enlaces = paginas_oficiales.enlaces(pagina, _medio(id_))
        assert len(enlaces) >= 15
        interesan[id_] = [d for d, t in enlaces if paginas_oficiales.interesa(t, _medio(id_), dron)]
    # «air alert» y «Airspace» no dicen «drone»: se abren por los títulos genéricos.
    assert set(interesan["lrt_en"]) == {ALERTAS, ANULADA, VUELOS}
    # La lista lituana enlaza además una nota antigua de otra alerta (3007328).
    assert NOCHE in interesan["lrt_lt"] and len(interesan["lrt_lt"]) == 2


def test_las_notas_de_la_noche_entran_como_articulos_y_solo_una_vez() -> None:
    almacen = Almacen.abrir()
    sitio = _Sitio()
    assert medios_publicos.paso_horario(almacen, AHORA, _descargador(sitio)) == 4
    cursor = almacen.cursor(medios_publicos.CURSOR) or {}
    # También la de los vuelos retrasados: cuenta el cierre de los aeropuertos por la alerta.
    assert all(cursor[u]["candidatos"] for u in (ALERTAS, ANULADA, VUELOS, NOCHE))
    # La nota antigua que la lista lituana aún enlaza ya no existe: no se vuelve a pedir.
    (antigua,) = [u for u in cursor if "/3007328/" in u]
    assert cursor[antigua]["descartada"] == "no existe"
    articulos = {a["url"]: a for a in almacen.articulos_de([ALERTAS, ANULADA, NOCHE])}
    assert {a["medio"] for a in articulos.values()} == {"lrt.lt"}
    assert articulos[ALERTAS]["fecha"] == "2026-11-11T05:31:00Z"
    assert articulos[ANULADA]["fecha"] == "2026-11-10T20:59:00Z"
    assert (articulos[NOCHE]["idioma"], articulos[NOCHE]["pais"]) == ("lt", "LT")
    assert articulos[ALERTAS]["titular"].startswith("Drone incursions trigger air alerts")
    # Sus candidatos van delante en el extractor, como los de un artículo dirigido.
    candidatos = medios_publicos.candidatos(almacen)
    assert candidatos and candidatos <= {c["id"] for c in almacen.candidatos()}
    assert {c["id"] for c in extractor.prioritarios(almacen)} >= candidatos
    # Ninguna ficha, ninguna fuente de autoridad: solo artículos.
    assert almacen.incidentes() == []
    # En la recogida siguiente no se vuelve a abrir ninguna nota: solo las dos listas.
    sitio.pedidas.clear()
    assert medios_publicos.paso_horario(almacen, AHORA, _descargador(sitio)) == 0
    assert [u for u in sitio.pedidas if not u.endswith("/robots.txt")] == [
        "https://www.lrt.lt/en/news-in-english", "https://www.lrt.lt/naujienos/lietuvoje",
    ]  # fmt: skip


def test_una_nota_antigua_no_entra() -> None:
    almacen = Almacen.abrir()
    tarde = datetime(2026, 11, 20, 8, 17, tzinfo=UTC)
    assert medios_publicos.paso_horario(almacen, tarde, _descargador(_Sitio())) == 0
    cursor = almacen.cursor(medios_publicos.CURSOR) or {}
    assert cursor[ALERTAS]["descartada"] == "de hace más de 3 días"


def test_el_robots_del_medio_se_respeta_y_un_medio_caido_no_corta_el_otro() -> None:
    almacen = Almacen.abrir()
    vetado = _Sitio("User-agent: *\nDisallow: /en/\n")
    assert medios_publicos.paso_horario(almacen, AHORA, _descargador(vetado)) == 1
    assert not [u for u in vetado.pedidas if "/en/news-in-english" in u]

    class _SinIngles(_Sitio):
        def __call__(self, url: str, cabeceras: dict[str, str], limite_s: float) -> Respuesta:
            if url == "https://www.lrt.lt/en/news-in-english":
                return 503, {}, b""
            return super().__call__(url, cabeceras, limite_s)

    otro = Almacen.abrir()
    assert medios_publicos.paso_horario(otro, AHORA, _descargador(_SinIngles())) == 1


def test_el_canal_de_las_fuerzas_de_defensa_de_estonia() -> None:
    fuente = next(f for f in oficiales.fuentes() if f["id"] == "mil_ee")
    assert (fuente["medio"], fuente["pais"], fuente["idioma"], fuente["tipo"]) == (
        "Kaitsevägi", "EE", "et", "rss",
    )  # fmt: skip
    canal = (FIXTURES / "mil_ee" / "feed.xml").read_text(encoding="utf-8")
    assert oficiales.es_canal(canal)
    notas = oficiales.leer_rss(canal, fuente)
    assert len(notas) == 10
    assert notas[0].id == "mil_ee-uudised-teenistuskoerad-ja-nende-juhid-said-lennukogemuse"
    assert notas[0].fecha == datetime(2026, 11, 10, 12, 32, 7, tzinfo=UTC)
    # Ese día no había ninguna de drones: nada entra ni se enlaza.
    dron = filtro().dron
    assert not [n for n in notas if dron.search(f"{n.titulo} {n.texto}")]
    assert dron.search("Eesti õhuruumi sisenes droon")
    kaitsevagi = autoridades.tabla()["Kaitsevägi"]
    assert kaitsevagi["es"] == "las Fuerzas de Defensa de Estonia"
    assert kaitsevagi["en"] == "the Estonian Defence Forces"
