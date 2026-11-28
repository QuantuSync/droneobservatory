"""Límite propio de cada descarga (28 de noviembre de 2026): ninguna dirección gasta más de su
`tope_s` entre peticiones, reintentos y esperas, y el fallo dice si es transitorio."""

import pytest

from recogida.descarga import Descargador, DescargaFallida, NoEncontrado, Respuesta
from tests.test_descarga import VALIDA, Reloj, Transporte, descargador, es_valida


def test_un_retry_after_que_no_cabe_en_el_limite_no_se_duerme() -> None:
    # 28/11/2026, 01:17-07:17 UTC: un 429 que pedía esperar 300 s se dormía entero dentro del
    # tope de 420 s del extractor horario. Con el límite de la página, falla en el acto.
    reloj = Reloj()
    d = descargador([(429, {"Retry-After": "600"}, b"")], reloj)
    with pytest.raises(DescargaFallida) as error:
        d.texto("https://www.newsmonkey.be/x", es_valida, tope_s=45)
    assert reloj.esperas == []
    assert error.value.transitoria
    assert "pide esperar 300 s" in str(error.value)
    assert "no cabe en el límite de la página" in str(error.value)


def test_los_reintentos_y_esperas_no_pasan_del_limite_de_la_descarga() -> None:
    reloj = Reloj()
    respuestas: list[Respuesta | Exception] = [TimeoutError("timed out")] * 5
    t = Transporte(respuestas)
    limites: list[float] = []

    def anotar(url: str, cabeceras: dict[str, str], limite_s: float) -> Respuesta:
        limites.append(limite_s)
        reloj.ahora += limite_s  # la petición agota su tiempo de espera
        return t(url, cabeceras, limite_s)

    d = Descargador(anotar, reloj.dormir, reloj, pausa_minima_s=0, limite_s=30)
    with pytest.raises(DescargaFallida) as error:
        d.texto("https://lenta.example/x", es_valida, tope_s=45)
    # 30 s de la primera petición, 5 de espera y lo que queda (10 s) para la segunda; la espera
    # siguiente (10 s) ya no cabe.
    assert limites == [30, 10]
    assert reloj.ahora <= 45
    assert error.value.transitoria


def test_un_404_o_un_403_no_son_transitorios() -> None:
    reloj = Reloj()
    with pytest.raises(NoEncontrado) as no_esta:
        descargador([(404, {}, b"")], reloj).texto("https://a.example/x", es_valida, tope_s=45)
    with pytest.raises(DescargaFallida) as prohibido:
        descargador([(403, {}, b"")], reloj).texto("https://a.example/x", es_valida, tope_s=45)
    assert not no_esta.value.transitoria
    assert not prohibido.value.transitoria


def test_sin_limite_propio_el_retry_after_se_respeta_como_siempre() -> None:
    reloj = Reloj()
    d = descargador([(429, {"Retry-After": "120"}, b""), (200, {}, VALIDA.encode())], reloj)
    assert d.texto("https://a.example/x", es_valida) == VALIDA
    assert reloj.esperas == [120]
