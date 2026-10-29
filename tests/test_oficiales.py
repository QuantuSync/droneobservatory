"""Fuentes oficiales sin red: RSS, robots.txt y enlace al incidente."""

from collections import Counter
from datetime import UTC, datetime, timedelta
from unicodedata import normalize

import pytest

from almacen.base import Almacen
from proceso.noticias import lugar, lugar_del_suceso, nomenclator
from recogida import oficiales
from recogida.descarga import AGENTE_EODI, Descargador, Respuesta
from recogida.plazo import Plazo
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


def test_sin_tiempo_las_fuentes_quedan_sin_leer(monkeypatch: pytest.MonkeyPatch) -> None:
    dos = (FUENTE, FUENTE)
    monkeypatch.setattr(oficiales, "fuentes", lambda: dos)
    sitio = Sitio("")
    descargador = Descargador(sitio, dormir=lambda _: None, pausa_minima_s=0)
    almacen = Almacen.abrir()
    recuentos = oficiales.ejecutar(almacen, AHORA, MODELOS, descargador, Plazo(0.0))
    assert (recuentos.notas, recuentos.sin_leer) == (0, len(dos))
    assert sitio.pedidas == []
    # Con tiempo se leen todas: dos notas por fuente, una de ellas sobre drones.
    recuentos = oficiales.ejecutar(almacen, AHORA, MODELOS, descargador, Plazo(oficiales.TOPE_S))
    assert (recuentos.notas, recuentos.relevantes, recuentos.sin_leer) == (4, 2, 0)


def test_una_nota_con_fecha_futura_no_es_el_ultimo_dato(monkeypatch: pytest.MonkeyPatch) -> None:
    # A las 06:30 del 23 de septiembre, la nota de las 07:00 está mal fechada: la última es la
    # de las 06:00.
    monkeypatch.setattr(oficiales, "fuentes", lambda: (FUENTE,))
    descargador = Descargador(Sitio(""), dormir=lambda _: None, pausa_minima_s=0)
    ahora = datetime(2025, 9, 23, 6, 30, tzinfo=UTC)
    recuentos = oficiales.ejecutar(Almacen.abrir(), ahora, MODELOS, descargador)
    assert recuentos.notas == 2
    assert recuentos.ultima == datetime(2025, 9, 23, 6, tzinfo=UTC)


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


# --- Una fuente caída no estropea la recogida ---------------------------------------------
CAIDA = {**FUENTE, "id": "caida", "url": "https://caida.ejemplo/rss"}
SANA = {**FUENTE, "id": "sana", "url": "https://sana.ejemplo/rss"}


class Reloj:
    """Reloj falso: dormir y las peticiones colgadas avanzan el tiempo sin esperar."""

    def __init__(self) -> None:
        self.ahora = 0.0

    def __call__(self) -> float:
        return self.ahora

    def dormir(self, segundos: float) -> None:
        self.ahora += segundos


class Sitios:
    """La fuente caída se cuelga (o responde `codigo`); la sana devuelve el canal."""

    def __init__(self, reloj: Reloj, codigo: int | None = None) -> None:
        self.reloj = reloj
        self.codigo = codigo
        self.pedidas: list[str] = []

    def __call__(self, url: str, cabeceras: dict[str, str], limite_s: float) -> Respuesta:
        self.pedidas.append(url)
        if "caida" in url:
            if self.codigo is not None:
                return self.codigo, {}, b""
            self.reloj.ahora += limite_s
            raise TimeoutError("sin respuesta")
        if url.endswith("/robots.txt"):
            return 200, {}, b""
        return 200, {}, RSS.encode()


def _descargador(sitios: Sitios, reloj: Reloj) -> Descargador:
    return Descargador(sitios, reloj.dormir, reloj, pausa_minima_s=0)


def test_una_fuente_que_se_cuelga_no_impide_leer_las_demas(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setattr(oficiales, "fuentes", lambda: (CAIDA, SANA))
    reloj = Reloj()
    sitios = Sitios(reloj)
    recuentos = oficiales.ejecutar(
        Almacen.abrir(), AHORA, MODELOS, _descargador(sitios, reloj),
        Plazo(oficiales.TOPE_S, reloj), reloj=reloj,
    )  # fmt: skip
    # La caída se corta en su tope y la sana se lee entera.
    assert reloj.ahora <= oficiales.TOPE_FUENTE_S + 1
    assert (recuentos.notas, recuentos.sin_leer, recuentos.bloqueadas) == (2, 0, 1)
    assert list(recuentos.fallidas) == ["caida"]
    assert "oficiales: fuente caida falló: cortada al agotar su tope de 45 s" in caplog.text


def test_tres_fallos_seguidos_ponen_la_fuente_en_pausa_y_a_las_6_horas_se_prueba(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setattr(oficiales, "fuentes", lambda: (CAIDA, SANA))
    almacen = Almacen.abrir()
    reloj = Reloj()
    sitios = Sitios(reloj, codigo=403)

    def pasada(ahora: datetime) -> oficiales.Recuentos:
        return oficiales.ejecutar(
            almacen, ahora, MODELOS, _descargador(sitios, reloj), Plazo(oficiales.TOPE_S, reloj),
            reloj=reloj,
        )  # fmt: skip

    for hora in range(3):
        recuentos = pasada(AHORA + timedelta(hours=hora))
        assert recuentos.fallidas.keys() == {"caida"}
        assert recuentos.en_pausa == []
    estado = oficiales.pausas(almacen)["caida"]
    assert estado["fallos_seguidos"] == 3
    assert estado["pausa_hasta"] == "2025-09-24T20:00:00Z"
    assert "en pausa 6 h" in caplog.text
    # En pausa no se pide nada, no es un fallo y la sana se lee.
    sitios.pedidas.clear()
    recuentos = pasada(AHORA + timedelta(hours=5))
    assert recuentos.en_pausa == ["caida"]
    assert (recuentos.sin_leer, recuentos.bloqueadas, recuentos.notas) == (0, 0, 2)
    assert not [u for u in sitios.pedidas if "caida" in u]
    # Pasadas las 6 horas se vuelve a probar: si falla, otras 6 horas.
    recuentos = pasada(AHORA + timedelta(hours=8))
    assert recuentos.fallidas.keys() == {"caida"}
    assert oficiales.pausas(almacen)["caida"]["pausa_hasta"] == "2025-09-25T02:00:00Z"
    # Si responde, sale de la pausa y empieza de cero.
    monkeypatch.setattr(oficiales, "fuentes", lambda: ({**SANA, "id": "caida"}, SANA))
    recuentos = pasada(AHORA + timedelta(hours=15))
    assert recuentos.fallidas == {}
    assert oficiales.pausas(almacen) == {}


def test_una_fuente_en_pausa_7_dias_se_avisa_una_sola_vez(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(oficiales, "fuentes", lambda: (CAIDA,))
    almacen = Almacen.abrir()
    reloj = Reloj()
    sitios = Sitios(reloj, codigo=403)
    avisos: list[str] = []
    ahora = AHORA
    for _ in range(40):
        oficiales.ejecutar(
            almacen, ahora, MODELOS, _descargador(sitios, reloj), avisar=avisos.append,
            reloj=reloj,
        )  # fmt: skip
        ahora += timedelta(hours=6, minutes=1)
    # La pausa empezó en la tercera pasada; 7 días son 28 pausas de 6 horas.
    assert len(avisos) == 1
    assert avisos[0].startswith("La fuente oficial caida lleva en pausa desde el 2025-09-25")


def test_una_fuente_en_pausa_no_es_un_aviso_de_la_recogida(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Lo que mira la recogida horaria para el código 2 y el estado de las oficiales.
    monkeypatch.setattr(oficiales, "fuentes", lambda: (CAIDA, SANA))
    almacen = Almacen.abrir()
    hasta = (AHORA + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    almacen.guardar_cursor(
        oficiales.CURSOR_PAUSAS,
        {"fuentes": {"caida": {"fallos_seguidos": 3, "pausa_hasta": hasta, "motivo": "x"}}},
    )
    reloj = Reloj()
    recuentos = oficiales.ejecutar(
        almacen, AHORA, MODELOS, _descargador(Sitios(reloj), reloj), reloj=reloj
    )
    assert recuentos.en_pausa == ["caida"]
    assert (recuentos.sin_leer, recuentos.bloqueadas) == (0, 0)


# --- Notas de un suceso con ficha sin punto, con varias posibles o sin ficha ---------------
NOTA_PAIS = """<rss version="2.0"><channel><title>Politi</title>
<item><title>Politiet bekræfter droner over Københavns Lufthavn</title>
<link>https://via.ejemplo/pressemeddelelse/3/droner?lang=da#sm-31</link>
<description>Droner blev observeret over lufthavnen mandag aften.</description>
<pubDate>Tue, 23 Sep 2025 06:00:00 GMT</pubDate></item>
<item><title>Prezes w debacie otwarcia Drone Summit</title>
<link>https://via.ejemplo/pressemeddelelse/4/summit?lang=da#sm-41</link>
<description>Rozmowa o przyszłości dronów w lotnictwie.</description>
<pubDate>Tue, 23 Sep 2025 07:00:00 GMT</pubDate></item>
</channel></rss>"""
# Solo la segunda nota: habla de drones, pero no cuenta un suceso.
SOLO_CUMBRE = NOTA_PAIS[: NOTA_PAIS.index("<item>")] + NOTA_PAIS[NOTA_PAIS.index("</item>") + 7 :]


def _sin_punto(almacen: Almacen, id_: str, nuevo: str | None = None) -> str:
    """Una copia de la ficha con el lugar solo a nivel de país (como EODI-2026-00603)."""
    incidente = almacen.incidente(id_)
    assert incidente is not None
    copia = {**incidente, "id": nuevo or id_}
    copia["lugar"] = {"pais": "DK", "nivel": "pais"}
    copia.pop("objetivo", None)
    almacen.guardar_incidente(copia, AHORA, MODELOS)
    return str(copia["id"])


def test_la_nota_se_enlaza_a_la_ficha_que_solo_tiene_el_pais() -> None:
    almacen = Almacen.abrir()
    id_ = _sin_punto(almacen, str(extraer_ejemplo(almacen)))
    (nota, _) = oficiales.leer_rss(NOTA_PAIS, FUENTE)
    # Mismo país, la víspera de la nota y un aeropuerto en las dos: es su ficha.
    assert [i["id"] for i in oficiales.posibles(almacen, nota)] == [id_]
    assert oficiales.enlazar(almacen, nota, AHORA, MODELOS) == id_
    incidente = almacen.incidente(id_)
    assert incidente is not None
    assert incidente["fuentes"][-1]["es_autoridad"] is True
    assert incidente["estado"]["actual"] == "confirmado"


def test_la_nota_con_el_dia_escrito_casa_con_la_ficha_de_ese_dia() -> None:
    almacen = Almacen.abrir()
    incidente = almacen.incidente(_sin_punto(almacen, str(extraer_ejemplo(almacen))))
    assert incidente is not None
    (nota, _) = oficiales.leer_rss(NOTA_PAIS, FUENTE)
    # Publicada días después, pero escribe el día del suceso (Alūksne: el 24/10 sobre el 18).
    tarde = datetime(2025, 9, 27, 6, tzinfo=UTC)
    con_dia = oficiales.Nota(
        nota.fuente, nota.id, nota.titulo, nota.enlace, tarde, "Droner den 22. september."
    )
    sin_dia = oficiales.Nota(nota.fuente, nota.id, nota.titulo, nota.enlace, tarde, "Droner.")
    assert oficiales.mismo_dia(incidente, con_dia)
    assert not oficiales.mismo_dia(incidente, sin_dia)


def test_con_varias_fichas_posibles_entra_por_el_filtro_y_despues_se_enlaza() -> None:
    almacen = Almacen.abrir()
    id_ = _sin_punto(almacen, str(extraer_ejemplo(almacen)))
    otra = _sin_punto(almacen, id_, "EODI-2025-00002")
    (nota, _) = oficiales.leer_rss(NOTA_PAIS, FUENTE)
    assert {i["id"] for i in oficiales.posibles(almacen, nota)} == {id_, otra}
    assert oficiales.enlazar(almacen, nota, AHORA, MODELOS) is None
    # Entra como artículo para que el experto (filtro de entrada) diga de cuál es.
    assert oficiales.a_entrada(almacen, nota, AHORA)
    # Cuando el filtro la ha unido a una, esa la tiene entre sus fuentes y la nota se enlaza.
    incidente = almacen.incidente(otra)
    assert incidente is not None
    articulo = {**incidente["fuentes"][0], "id": "gdelt-nota", "enlace": nota.enlace}
    incidente["fuentes"] = [*incidente["fuentes"], articulo]
    almacen.guardar_incidente(incidente, AHORA, MODELOS)
    assert oficiales.enlazar(almacen, nota, AHORA, MODELOS) == otra
    enlazada = almacen.incidente(otra)
    assert enlazada is not None
    # La fuente que entró como artículo es ahora la de la autoridad, sin repetirse.
    de_la_nota = [f for f in enlazada["fuentes"] if f.get("enlace") == nota.enlace]
    assert [(f["id"], f["es_autoridad"]) for f in de_la_nota] == [(nota.id, True)]


def test_la_nota_sin_ficha_entra_una_vez_como_candidato_prioritario() -> None:
    from recogida import extractor

    almacen = Almacen.abrir()
    (nota, _) = oficiales.leer_rss(NOTA_PAIS, FUENTE)
    assert oficiales.posibles(almacen, nota) == []
    assert oficiales.suceso(nota)
    assert oficiales.a_entrada(almacen, nota, AHORA)
    assert not oficiales.a_entrada(almacen, nota, AHORA)
    candidatos = oficiales.candidatos(almacen)
    assert len(candidatos) == 1
    (candidato,) = [c for c in almacen.candidatos() if c["id"] in candidatos]
    assert nota.enlace in candidato["articulos"]
    assert [a["medio"] for a in almacen.articulos_de([nota.enlace])] == ["Københavns Politi"]
    # El extractor lo lleva por delante; su ficha pasará por el filtro de entrada.
    assert [c["id"] for c in extractor.prioritarios(almacen)][:1] == [candidato["id"]]


def test_la_nota_que_no_cuenta_un_suceso_no_crea_nada() -> None:
    almacen = Almacen.abrir()

    def servir(url: str, cabeceras: dict[str, str], limite_s: float) -> Respuesta:
        if url.endswith("/robots.txt"):
            return 200, {}, b""
        return 200, {}, SOLO_CUMBRE.encode()

    recuentos = oficiales.Recuentos()
    reloj = Reloj()
    descargador = Descargador(servir, reloj.dormir, reloj, pausa_minima_s=0)
    assert (
        oficiales.recoger(almacen, descargador, FUENTE, AHORA, MODELOS, recuentos, Counter())
        is None
    )
    assert (recuentos.relevantes, recuentos.enlazadas, recuentos.a_entrada) == (1, 0, 0)
    assert almacen.candidatos() == []
    assert almacen.cursor(oficiales.CURSOR_SIN_FICHA) is None
