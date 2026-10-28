"""Las fuentes delegadas se descargan por el lector de la web (recogida/lector_delegado.py)."""

from urllib.parse import parse_qs, urlsplit

import pytest

from almacen.base import Almacen
from recogida import lector_delegado, oficiales
from recogida.descarga import Descargador, DescargaFallida, Respuesta, Transporte
from recogida.plazo import Plazo
from tests.test_extraccion import MODELOS
from tests.test_oficiales import AHORA, RSS, SANA, Reloj

LECTOR = "https://lector.ejemplo/api/lector"
URL_DELEGADA = "https://bloquea.ejemplo/rss"
DELEGADA = {**SANA, "id": "delegada", "url": URL_DELEGADA, "delegada": True}
ORIGEN = {"X-Lector": "origen", "X-Lector-Url-Final": "https://bloquea.ejemplo/rss"}


class Lector:
    """El lector de la web (y el sitio directo de las no delegadas), sin red."""

    def __init__(self, codigo: int = 200, cabeceras: dict[str, str] | None = None) -> None:
        self.codigo = codigo
        self.cabeceras = ORIGEN if cabeceras is None else cabeceras
        self.pedidas: list[str] = []
        self.claves: list[str | None] = []

    def __call__(self, url: str, cabeceras: dict[str, str], limite_s: float) -> Respuesta:
        self.pedidas.append(url)
        self.claves.append(cabeceras.get("x-vercel-protection-bypass"))
        if not url.startswith(LECTOR):
            return 200, {}, b"" if url.endswith("/robots.txt") else RSS.encode()
        pedida = parse_qs(urlsplit(url).query)["url"][0]
        if self.codigo != 200:
            return self.codigo, self.cabeceras, b""
        return 200, self.cabeceras, b"" if pedida.endswith("/robots.txt") else RSS.encode()


def _transporte(lector: Lector, clave: str = "") -> Transporte:
    return lector_delegado.transporte_delegado("delegada", lector, LECTOR, clave)


def _descargador(transporte: Transporte, reloj: Reloj | None = None) -> Descargador:
    reloj = reloj or Reloj()
    return Descargador(transporte, reloj.dormir, reloj, pausa_minima_s=0, tope_diario=None)


def test_pide_la_direccion_al_lector_con_su_fuente() -> None:
    lector = Lector()
    texto = _descargador(_transporte(lector)).texto(URL_DELEGADA, oficiales.es_canal)
    assert "Politiet" in texto
    (pedida,) = lector.pedidas
    assert pedida.startswith(f"{LECTOR}?")
    assert parse_qs(urlsplit(pedida).query) == {"fuente": ["delegada"], "url": [URL_DELEGADA]}
    # Sin clave de vistas previas, ninguna cabecera de acceso.
    assert lector.claves == [None]


def test_la_clave_de_las_vistas_previas_solo_si_se_da() -> None:
    lector = Lector()
    _descargador(_transporte(lector, "clave-de-prueba")).texto(URL_DELEGADA, oficiales.es_canal)
    assert lector.claves == ["clave-de-prueba"]


def test_el_codigo_de_la_fuente_pasa_tal_cual() -> None:
    lector = Lector(403, ORIGEN)
    with pytest.raises(DescargaFallida, match="código 403"):
        _descargador(_transporte(lector)).texto(URL_DELEGADA, oficiales.es_canal)
    # Un 403 no se reintenta, igual que si viniera de la fuente directamente.
    assert len(lector.pedidas) == 1


def test_si_el_lector_no_llega_a_la_fuente_se_reintenta_como_un_error_de_red() -> None:
    lector = Lector(504, {"X-Lector": "propio"})
    with pytest.raises(DescargaFallida, match="error de red"):
        _descargador(_transporte(lector)).texto(URL_DELEGADA, oficiales.es_canal)
    assert len(lector.pedidas) == 5
    # Una respuesta sin la cabecera del lector (la web caída, otra página) también.
    sin_lector = Lector(200, {})
    with pytest.raises(DescargaFallida, match="error de red"):
        _descargador(_transporte(sin_lector)).texto(URL_DELEGADA, oficiales.es_canal)


def test_una_direccion_que_el_lector_rechaza_es_un_fallo_sin_reintentos() -> None:
    lector = Lector(400, {"X-Lector": "propio"})
    with pytest.raises(DescargaFallida, match="código 400"):
        _descargador(_transporte(lector)).texto(URL_DELEGADA, oficiales.es_canal)
    assert len(lector.pedidas) == 1


def test_la_recogida_lee_por_el_lector_solo_las_delegadas(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(oficiales, "fuentes", lambda: (DELEGADA, SANA))
    monkeypatch.setenv(lector_delegado.ENTORNO_URL, LECTOR)
    lector = Lector()
    reloj = Reloj()
    recuentos = oficiales.ejecutar(
        Almacen.abrir(), AHORA, MODELOS, _descargador(lector, reloj),
        Plazo(oficiales.TOPE_S, reloj), reloj=reloj,
    )  # fmt: skip
    assert recuentos.fallidas == {}
    assert recuentos.notas == 4
    por_lector = [u for u in lector.pedidas if u.startswith(LECTOR)]
    directas = [u for u in lector.pedidas if not u.startswith(LECTOR)]
    # La delegada, su robots.txt y su canal, por el lector; la otra, directa.
    assert [parse_qs(urlsplit(u).query)["url"][0] for u in por_lector] == [
        "https://bloquea.ejemplo/robots.txt",
        URL_DELEGADA,
    ]
    assert directas == ["https://sana.ejemplo/robots.txt", SANA["url"]]


def test_si_el_lector_falla_la_fuente_falla_sin_tumbar_la_recogida(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setattr(oficiales, "fuentes", lambda: (DELEGADA, SANA))
    monkeypatch.setenv(lector_delegado.ENTORNO_URL, LECTOR)
    lector = Lector(403, ORIGEN)
    reloj = Reloj()
    recuentos = oficiales.ejecutar(
        Almacen.abrir(), AHORA, MODELOS, _descargador(lector, reloj),
        Plazo(oficiales.TOPE_S, reloj), reloj=reloj,
    )  # fmt: skip
    assert list(recuentos.fallidas) == ["delegada"]
    assert recuentos.notas == 2
    assert "oficiales: fuente delegada falló" in caplog.text


def test_en_la_configuracion_el_csn_va_delegado_y_mod_lv_vuelve_directa() -> None:
    fuentes = {f["id"]: f for f in oficiales.fuentes()}
    assert fuentes["csn_sucesos"]["delegada"] is True
    assert "mod_lv" in fuentes
    assert [f for f in fuentes if fuentes[f].get("delegada")] == ["csn_sucesos"]
