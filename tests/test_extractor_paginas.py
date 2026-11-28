"""Páginas que fallan en la ejecución horaria del extractor (28 de noviembre de 2026).

Del 28/11 de 01:17 a 07:17 UTC una página de newsmonkey.be contestaba con un 429 que pedía
esperar; el descargador dormía 300 s, el tope de 420 s del paso se agotaba y el TiempoAgotado de
esa página tiraba la preparación entera: ningún candidato llegaba al modelo y el registro no decía
nada de la página. Ahora cada página tiene su límite, la que falla aparta solo a su candidato (que
se reintenta en la recogida siguiente) y los demás llegan al modelo.
"""

import logging
import threading
from dataclasses import replace
from datetime import timedelta
from typing import Any

import pytest

from almacen.base import Almacen
from modelo import ficha, paginas
from proceso import extraccion
from recogida import extractor
from recogida.descarga import Descargador, Respuesta
from recogida.plazo import Plazo, TiempoAgotado
from tests import test_extraccion
from tests.test_descarga import Reloj
from tests.test_extraccion import (
    AHORA,
    PENDIENTES,
    TEXTO,
    bien,
    candidato_con_articulos,
    paso_horario,
)

# Las mismas bases de prueba que tests/test_extraccion.py.
almacen = test_extraccion.almacen
candidato_pendiente = test_extraccion.candidato_pendiente

HTML = f"<html><p>{TEXTO}</p></html>".encode()
LENTA = "https://www.newsmonkey.be/"


def _peticiones(almacen: Almacen, monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    """Tres candidatos con sus fuentes: el segundo, con una página de newsmonkey.be."""
    base = candidato_con_articulos(almacen, horas=2)
    original = extraccion.preparar(almacen, base, None)
    candidatos = [{**base, "id": f"CAND-{i}"} for i in range(3)]

    def preparar(_a: Almacen, candidato: dict[str, Any], _d: object) -> extraccion.Peticion:
        n = int(candidato["id"][-1])
        urls = [f"{LENTA}{n}" if n == 1 else f"https://bien{n}.example/{j}"
                for j in range(len(original.enviadas))]  # fmt: skip
        fuentes = [replace(f, url=u) for f, u in zip(original.fuentes, urls, strict=True)]
        return replace(original, candidato=candidato, enviadas=urls, fuentes=fuentes)

    monkeypatch.setattr(extraccion, "preparar", preparar)
    return candidatos


class Web:
    """newsmonkey.be pide esperar con un 429; las demás contestan bien. Con un reloj falso por
    hilo, nada espera de verdad."""

    def __init__(self) -> None:
        self.pedidas: list[str] = []
        self._cerrojo = threading.Lock()

    def __call__(self, url: str, cabeceras: dict[str, str], limite_s: float) -> Respuesta:
        with self._cerrojo:
            self.pedidas.append(url)
        if url.startswith(LENTA):
            return 429, {"Retry-After": "300"}, b""
        return 200, {}, HTML


def _fabrica(web: Web, esperas: list[float]) -> Any:
    def nuevo() -> Descargador:
        reloj = Reloj()

        def dormir(segundos: float) -> None:
            esperas.append(segundos)
            reloj.dormir(segundos)

        return Descargador(web, dormir, reloj, pausa_minima_s=0)

    return nuevo


def test_una_pagina_que_pide_esperar_aparta_solo_su_candidato(
    almacen: Almacen, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO, logger="recogida")
    candidatos = _peticiones(almacen, monkeypatch)
    web, esperas = Web(), list[float]()
    informe = extractor.Preparacion()
    hechas = extractor.preparar_todas(almacen, candidatos, _fabrica(web, esperas), AHORA, informe)
    assert [p.candidato["id"] for p in hechas] == ["CAND-0", "CAND-2"]
    assert all(f.texto for p in hechas for f in p.fuentes)
    assert list(informe.apartados) == ["CAND-1"]
    assert max(esperas, default=0) < 300  # la espera de 300 s no se duerme
    mensajes = [r.getMessage() for r in caplog.records]
    # Cada página que falla, con su dirección y lo que tardó; y el candidato apartado.
    assert any(m.startswith("página sin leer en ") and LENTA in m and "429" in m for m in mensajes)
    assert any("CAND-1 apartado en esta recogida" in m and "vez 1 de 2" in m for m in mensajes)


def test_la_pagina_apartada_se_reintenta_y_despues_va_con_el_titular(
    almacen: Almacen, monkeypatch: pytest.MonkeyPatch
) -> None:
    candidatos = _peticiones(almacen, monkeypatch)
    web, esperas = Web(), list[float]()
    ids = []
    for hora in range(3):
        informe = extractor.Preparacion()
        hechas = extractor.preparar_todas(
            almacen, candidatos, _fabrica(web, esperas), AHORA + timedelta(hours=hora), informe
        )
        ids.append([p.candidato["id"] for p in hechas])
    # Dos recogidas apartado; en la tercera va con el titular de esa fuente.
    assert ids == [["CAND-0", "CAND-2"], ["CAND-0", "CAND-2"], ["CAND-0", "CAND-1", "CAND-2"]]
    assert sum(u.startswith(LENTA) for u in web.pedidas) == 3 * len(candidatos[0]["articulos"])


def test_sin_tiempo_de_preparacion_los_preparados_siguen(
    almacen: Almacen, monkeypatch: pytest.MonkeyPatch
) -> None:
    candidatos = _peticiones(almacen, monkeypatch)
    original = paginas.leer_pagina

    def leer(descargador: Descargador, url: str, **opciones: Any) -> paginas.Pagina:
        if url.startswith(LENTA):
            raise TiempoAgotado("tope de 180 s agotado")
        return original(descargador, url, **opciones)

    monkeypatch.setattr(paginas, "leer_pagina", leer)
    informe = extractor.Preparacion()
    hechas = extractor.preparar_todas(almacen, candidatos, _fabrica(Web(), []), AHORA, informe)
    assert [p.candidato["id"] for p in hechas] == ["CAND-0", "CAND-2"]
    assert informe.sin_tiempo == ["CAND-1"]
    # Sin informe (el histórico), el tiempo agotado sale como siempre.
    with pytest.raises(TiempoAgotado):
        extractor.preparar_todas(almacen, candidatos, _fabrica(Web(), []), AHORA)


def test_la_preparacion_deja_siempre_tiempo_para_las_llamadas() -> None:
    plazo = extractor.plazo_de_preparacion(Plazo(extractor.TOPE_S))
    assert plazo is not None
    assert plazo.segundos == extractor.TOPE_PREPARACION_S
    assert extractor.TOPE_S - plazo.segundos >= extractor.RESERVA_LLAMADAS_S
    corto = extractor.plazo_de_preparacion(Plazo(200))
    assert corto is not None and corto.segundos <= 200 - extractor.RESERVA_LLAMADAS_S
    assert extractor.plazo_de_preparacion(None) is None


def test_con_una_web_que_falla_el_extractor_llama_con_los_demas(
    almacen: Almacen,
    candidato_pendiente: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    # La ejecución horaria entera: uno de los tres candidatos tiene una página que falla con un
    # fallo transitorio; los otros dos llegan al modelo y el primero queda pendiente.
    caplog.set_level(logging.INFO, logger="recogida")
    vistos: list[object] = []
    cerrojo = threading.Lock()
    monkeypatch.setattr(extractor, "Descargador", lambda **_: object())

    def leer(descargador: object, url: str, **_: Any) -> paginas.Pagina:
        with cerrojo:
            if descargador not in vistos:
                vistos.append(descargador)
            primero = descargador is vistos[0]
        if primero:
            return paginas.Pagina("", fallo=f"{url}: código 429, pide esperar 300 s",
                                  transitorio=True)  # fmt: skip
        return paginas.Pagina(TEXTO)

    monkeypatch.setattr(paginas, "leer_pagina", leer)
    resultado, _servicio = paso_horario(almacen, [bien(), bien()], plazo=Plazo(extractor.TOPE_S))
    assert resultado.candidatos == PENDIENTES
    assert resultado.llamadas == PENDIENTES - 1
    assert resultado.pendientes == 1
    mensajes = [r.getMessage() for r in caplog.records]
    assert any("apartado en esta recogida" in m for m in mensajes)
    assert any(m.startswith("extractor: 3 candidatos elegidos") for m in mensajes)


def test_sin_llamadas_el_registro_dice_por_que(
    almacen: Almacen,
    candidato_pendiente: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.WARNING, logger="recogida")

    def falla(_d: object, url: str, **_: Any) -> paginas.Pagina:
        return paginas.Pagina("", fallo=f"{url}: error de red: TimeoutError", transitorio=True)

    monkeypatch.setattr(paginas, "leer_pagina", falla)
    resultado, servicio = paso_horario(almacen, [], plazo=Plazo(extractor.TOPE_S))
    assert (resultado.llamadas, servicio.pedidas) == (0, [])
    (motivo,) = [r.getMessage() for r in caplog.records if "sin llamadas" in r.getMessage()]
    assert "apartados por una página que falló" in motivo
    assert "TimeoutError" in motivo


def test_peticion_sin_fuentes_no_rompe_la_preparacion(almacen: Almacen) -> None:
    # Las fuentes de la petición se reconstruyen con su texto: la misma forma que antes.
    candidato = candidato_con_articulos(almacen, horas=2)
    informe = extractor.Preparacion()
    hechas = extractor.preparar_todas(almacen, [candidato], _fabrica(Web(), []), AHORA, informe)
    assert len(hechas) == 1
    assert all(isinstance(f, ficha.FuenteTexto) for f in hechas[0].fuentes)
    assert informe.paginas == len(hechas[0].enviadas)
