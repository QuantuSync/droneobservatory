"""Fuentes oficiales sin red: RSS, robots.txt y enlace al incidente."""

from datetime import UTC, datetime
from unicodedata import normalize

from almacen.base import Almacen
from proceso.noticias import lugar, lugar_del_suceso, nomenclator
from recogida import oficiales
from recogida.descarga import AGENTE_EODI, Descargador, Respuesta
from tests.test_extraccion import MODELOS, extraer_ejemplo

AHORA = datetime(2025, 9, 24, 12, tzinfo=UTC)
FUENTE = {"id": "politi_kobenhavn", "medio": "Københavns Politi", "pais": "DK", "idioma": "da",
          "tipo": "rss", "url": "https://via.ejemplo/rss?p=1"}  # fmt: skip
RSS = """<rss version="2.0"><channel><title>Politi</title>
<item><title>Politiet bekræfter droner over Københavns Lufthavn</title>
<link>https://via.ejemplo/pressemeddelelse/1/droner?lang=da#sm-11</link>
<description>Lufthavnen blev lukket mandag aften.</description>
<pubDate>Tue, 23 Sep 2025 06:00:00 GMT</pubDate></item>
<item><title>14 cyklister fik bøde</title>
<link>https://via.ejemplo/pressemeddelelse/2/cykler?lang=da#sm-12</link>
<pubDate>Tue, 23 Sep 2025 07:00:00 GMT</pubDate></item>
</channel></rss>"""


def test_leer_rss() -> None:
    notas = oficiales.leer_rss(RSS, FUENTE)
    assert [n.id for n in notas] == ["politi_kobenhavn-sm-11", "politi_kobenhavn-sm-12"]
    assert notas[0].fecha == datetime(2025, 9, 23, 6, tzinfo=UTC)


def test_la_nota_confirma_el_incidente_que_le_corresponde() -> None:
    almacen = Almacen.abrir()
    id_ = extraer_ejemplo(almacen)
    (nota, _) = oficiales.leer_rss(RSS, FUENTE)
    assert oficiales.enlazar(almacen, nota, AHORA, MODELOS) == id_
    incidente = almacen.incidente(str(id_))
    assert incidente is not None
    assert incidente["estado"]["actual"] == "confirmado"
    assert incidente["presencia_dron"] == "confirmada"
    oficial = incidente["fuentes"][-1]
    assert (oficial["fiabilidad"], oficial["es_autoridad"], oficial["credibilidad"]) == (
        "A",
        True,
        1,
    )
    # Enlazar otra vez no la repite.
    assert oficiales.enlazar(almacen, nota, AHORA, MODELOS) == id_
    otra_vez = almacen.incidente(str(id_))
    assert otra_vez is not None
    assert len(otra_vez["fuentes"]) == len(incidente["fuentes"])


class Sitio:
    def __init__(self, robots: str) -> None:
        self.robots = robots
        self.pedidas: list[str] = []

    def __call__(self, url: str, cabeceras: dict[str, str], limite_s: float) -> Respuesta:
        self.pedidas.append(url)
        if url.endswith("/robots.txt"):
            return 200, {}, self.robots.encode()
        return 200, {}, RSS.encode()


def test_robots_que_bloquea_no_se_fuerza() -> None:
    sitio = Sitio("User-agent: *\nDisallow: /\n")
    descargador = Descargador(sitio, dormir=lambda _: None, pausa_minima_s=0)
    lector = oficiales.robots(descargador, FUENTE["url"])
    assert not lector.can_fetch(AGENTE_EODI, FUENTE["url"])


def test_el_lugar_del_suceso_manda_sobre_la_capital() -> None:
    # Defensa letona, 25 de marzo de 2026: la rueda de prensa es en Riga y el dron cayó en
    # Krāslava.
    titulo = "Aizsardzības ministrijā informēs par Krāslavas novadā nokritušo dronu"
    texto = "Preses konference notiks Rīgā, netālu no RIX Rīgas lidosta."
    nom = nomenclator()
    id_ = lugar_del_suceso(titulo, texto, nom)
    assert id_ is not None
    # Los nombres de GeoNames vienen descompuestos (NFD).
    assert normalize("NFC", lugar(id_, nom).nombre) == "Krāslava"
    # Sin lugar en el titular, el del texto.
    id_texto = lugar_del_suceso("Informācija presei", texto, nom)
    assert id_texto is not None
    assert "Rīg" in normalize("NFC", lugar(id_texto, nom).nombre)
