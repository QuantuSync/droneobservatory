import pytest

from recogida.descarga import (
    ESPERA_INICIAL_S,
    ESPERA_MAXIMA_S,
    PAUSA_MINIMA_S,
    REINTENTOS,
    Descargador,
    DescargaFallida,
    NoEncontrado,
    PaginaBloqueada,
    Respuesta,
)
from recogida.plazo import Plazo, TiempoAgotado

VALIDA = "<html>contenido real</html>"


class Reloj:
    """Reloj falso: dormir avanza el tiempo sin esperar de verdad."""

    def __init__(self) -> None:
        self.ahora = 0.0
        self.esperas: list[float] = []

    def __call__(self) -> float:
        return self.ahora

    def dormir(self, segundos: float) -> None:
        self.esperas.append(segundos)
        self.ahora += segundos


class Transporte:
    """Transporte falso que devuelve respuestas preparadas y anota lo pedido."""

    def __init__(self, respuestas: list[Respuesta | Exception]) -> None:
        self.pendientes = list(respuestas)
        self.pedidas: list[tuple[str, dict[str, str]]] = []

    def __call__(self, url: str, cabeceras: dict[str, str], limite_s: float) -> Respuesta:
        self.pedidas.append((url, cabeceras))
        siguiente = self.pendientes.pop(0)
        if isinstance(siguiente, Exception):
            raise siguiente
        return siguiente


def es_valida(texto: str) -> bool:
    return "contenido real" in texto


def descargador(respuestas: list[Respuesta | Exception], reloj: Reloj) -> Descargador:
    return Descargador(Transporte(respuestas), reloj.dormir, reloj, pausa_minima_s=3.0)


def test_devuelve_el_texto_y_se_identifica_como_navegador() -> None:
    reloj = Reloj()
    t = Transporte([(200, {}, VALIDA.encode())])
    d = Descargador(t, reloj.dormir, reloj)
    assert d.texto("https://t.me/s/kpszsu", es_valida) == VALIDA
    ((_, cabeceras),) = t.pedidas
    assert cabeceras["User-Agent"].startswith("Mozilla/5.0")
    assert d.recuentos["peticiones"] == 1


def test_pausa_minima_entre_peticiones_al_mismo_sitio() -> None:
    reloj = Reloj()
    d = descargador([(200, {}, VALIDA.encode())] * 3, reloj)
    d.texto("https://t.me/a", es_valida)
    reloj.ahora += 1.0
    d.texto("https://t.me/b", es_valida)
    d.texto("https://otro.org/c", es_valida)
    # Solo espera lo que falta hasta 3 s y solo en el mismo sitio.
    assert reloj.esperas == [2.0]


def test_reintenta_con_espera_creciente() -> None:
    reloj = Reloj()
    d = descargador([(503, {}, b""), OSError("red"), (200, {}, VALIDA.encode())], reloj)
    assert d.texto("https://t.me/a", es_valida) == VALIDA
    esperas_reintento = [e for e in reloj.esperas if e >= ESPERA_INICIAL_S]
    assert esperas_reintento == [ESPERA_INICIAL_S, ESPERA_INICIAL_S * 2]
    assert d.recuentos["reintentos"] == 2


def test_respeta_retry_after_con_tope() -> None:
    reloj = Reloj()
    d = descargador([(429, {"Retry-After": "9999"}, b""), (200, {}, VALIDA.encode())], reloj)
    d.texto("https://t.me/a", es_valida)
    assert ESPERA_MAXIMA_S in reloj.esperas


def test_pagina_de_bloqueo_con_codigo_200() -> None:
    reloj = Reloj()
    bloqueo: Respuesta = (200, {}, b"<html>Please complete the captcha</html>")
    d = descargador([bloqueo] * (REINTENTOS + 1), reloj)
    with pytest.raises(PaginaBloqueada):
        d.texto("https://t.me/a", es_valida)
    assert d.recuentos["bloqueos"] == REINTENTOS + 1


def test_codigo_no_reintentable_falla_enseguida() -> None:
    reloj = Reloj()
    d = descargador([(404, {}, b"")], reloj)
    with pytest.raises(DescargaFallida):
        d.texto("https://t.me/a", es_valida)
    assert d.recuentos["peticiones"] == 1


def test_agota_los_reintentos() -> None:
    reloj = Reloj()
    d = descargador([OSError("red")] * (REINTENTOS + 1), reloj)
    with pytest.raises(DescargaFallida, match="error de red"):
        d.texto("https://t.me/a", es_valida)
    assert d.recuentos["fallos"] == 1


def test_con_el_plazo_agotado_no_se_pide_nada() -> None:
    reloj = Reloj()
    transporte = Transporte([(200, {}, VALIDA.encode())])
    d = Descargador(transporte, reloj.dormir, reloj, plazo=Plazo(0.0, reloj))
    with pytest.raises(TiempoAgotado):
        d.texto("https://t.me/a", es_valida)
    assert transporte.pedidas == []


def test_no_empieza_una_espera_de_reintento_que_no_cabe_en_el_plazo() -> None:
    reloj = Reloj()
    plazo = Plazo(ESPERA_INICIAL_S / 2, reloj)
    d = Descargador(Transporte([(503, {}, b"")]), reloj.dormir, reloj, plazo=plazo)
    with pytest.raises(TiempoAgotado):
        d.texto("https://t.me/a", es_valida)
    assert reloj.esperas == []
    assert d.recuentos["peticiones"] == 1


def test_la_pausa_entre_peticiones_tambien_cuenta_en_el_plazo() -> None:
    reloj = Reloj()
    d = descargador([(200, {}, VALIDA.encode())] * 2, reloj)
    d.plazo = Plazo(PAUSA_MINIMA_S / 2, reloj)
    d.texto("https://t.me/a", es_valida)
    with pytest.raises(TiempoAgotado):
        d.texto("https://t.me/b", es_valida)
    assert reloj.esperas == []
    assert d.recuentos["peticiones"] == 1


def test_una_peticion_no_pasa_del_plazo() -> None:
    limites: list[float] = []

    def transporte(url: str, cabeceras: dict[str, str], limite_s: float) -> Respuesta:
        limites.append(limite_s)
        return 200, {}, VALIDA.encode()

    reloj = Reloj()
    d = Descargador(transporte, reloj.dormir, reloj, plazo=Plazo(12.0, reloj))
    d.texto("https://t.me/a", es_valida)
    d.plazo = None
    d.texto("https://t.me/b", es_valida)
    assert limites == [12.0, 30.0]


def test_el_tiempo_agotado_no_es_un_fallo_de_descarga() -> None:
    # Quien atrapa DescargaFallida para seguir con lo siguiente no se traga el tope.
    assert not issubclass(TiempoAgotado, DescargaFallida)


def test_contenido_en_bruto_y_404_sin_reintentos() -> None:
    reloj = Reloj()
    transporte = Transporte([(200, {}, b"PK"), (404, {}, b"")])
    d = Descargador(transporte, dormir=reloj.dormir, reloj=reloj)
    assert d.contenido("https://ejemplo.org/a.zip", lambda c: c[:2] == b"PK") == b"PK"
    with pytest.raises(NoEncontrado):
        d.contenido("https://ejemplo.org/b.zip", lambda c: True)
    assert len(transporte.pedidas) == 2


def test_el_ultimo_fallo_dice_que_paso_en_el_ultimo_intento() -> None:
    # Quien corta un paso por su tope puede decir por qué no llegó la página.
    def colgado(url: str, cabeceras: dict[str, str], limite_s: float) -> Respuesta:
        raise TimeoutError("sin respuesta")

    descargador = Descargador(colgado, dormir=lambda _s: None, pausa_minima_s=0, reintentos=1)
    assert descargador.ultimo_fallo == ""
    with pytest.raises(DescargaFallida):
        descargador.texto("https://lento.ejemplo/canal", lambda _t: True)
    assert descargador.ultimo_fallo == (
        "https://lento.ejemplo/canal: error de red: TimeoutError (sin respuesta en 30 s)"
    )

    def con_503(url: str, cabeceras: dict[str, str], limite_s: float) -> Respuesta:
        return 503, {}, b""

    otro = Descargador(con_503, dormir=lambda _s: None, pausa_minima_s=0, reintentos=0)
    with pytest.raises(DescargaFallida):
        otro.texto("https://lento.ejemplo/canal", lambda _t: True)
    assert otro.ultimo_fallo == "https://lento.ejemplo/canal: código 503"


def test_con_otros_limites_es_el_mismo_visitante() -> None:
    # La pausa entre peticiones al mismo sitio y los recuentos se comparten.
    dormidas: list[float] = []
    pedidas: list[float] = []

    def sitio(url: str, cabeceras: dict[str, str], limite_s: float) -> Respuesta:
        pedidas.append(limite_s)
        return 200, {}, b"<p>hola</p>"

    descargador = Descargador(sitio, dormir=dormidas.append, reloj=lambda: 0.0, pausa_minima_s=3)
    breve = descargador.con_limites(0, 10.0)
    assert (breve.reintentos, breve.limite_s) == (0, 10.0)
    descargador.texto("https://sitio.ejemplo/a", lambda _t: True)
    breve.texto("https://sitio.ejemplo/b", lambda _t: True)
    assert dormidas == [3] and pedidas == [30.0, 10.0]
    assert descargador.recuentos["peticiones"] == 2
