"""Gordinești (Rezina, Moldavia), 5/11/2026: news.yam.md publicó primero «Un obiect suspect,
asemănător unei drone, descoperit în raionul Rezina» y después «Poliția precizează: Obiectul suspect
descoperit în raionul Rezina este o dronă de recunoaștere». Las fuentes elegidas eran una por
medio, así que la segunda nunca se mandó y el candidato se quedó en «no es incidente» aunque se
volvió a extraer al llegar ella. Ahora los huecos los llenan los artículos más recientes del mismo
medio, y un candidato que no es incidente se vuelve a extraer si no leyó un artículo que hoy se
mandaría."""

from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any

import pytest

from almacen.base import Almacen
from proceso import extraccion
from proceso.incidentes import huella

AHORA = datetime(2026, 11, 8, 12, tzinfo=UTC)
CANDIDATO = "CAND-20261105T1315-loc:617502-avistamiento"
PRIMERA = "https://news.yam.md/ro/story/82067602"
POLICIA = "https://news.yam.md/ro/story/82120923"


def _articulo(url: str, fecha: str, titular: str, medio: str = "news.yam.md") -> dict[str, Any]:
    return {"url": url, "medio": medio, "fecha": fecha, "idioma": "ro", "titular": titular,
            "replicas": 0}  # fmt: skip


ARTICULOS = [
    _articulo(PRIMERA, "2026-11-05T13:15:00Z",
              "Un obiect suspect, asemănător unei drone, descoperit în raionul Rezina"),
    _articulo(POLICIA, "2026-11-05T17:30:00Z", "Poliția precizează: Obiectul suspect descoperit "
              "în raionul Rezina este o dronă de recunoaștere"),
]  # fmt: skip


@pytest.fixture
def almacen() -> Iterator[Almacen]:
    a = Almacen.abrir()
    yield a
    a.cerrar()


def _preparar(
    almacen: Almacen, monkeypatch: pytest.MonkeyPatch, enviadas: list[str], incidente: str | None
) -> dict[str, Any]:
    candidato = {"id": CANDIDATO, "articulos": [PRIMERA, POLICIA], "lugar": "loc:617502"}
    extraccion_ = {
        "enviadas": enviadas, "incidente": incidente, "huella": huella([PRIMERA, POLICIA]),
        "campos": {"es_incidente": {"valor": incidente is not None}},
    }  # fmt: skip
    monkeypatch.setattr(almacen, "extracciones", lambda _c: [extraccion_])
    monkeypatch.setattr(almacen, "candidatos", lambda: [candidato])
    monkeypatch.setattr(almacen, "candidatos_extraidos_desde", lambda _d: [CANDIDATO])
    monkeypatch.setattr(extraccion, "_articulos", lambda _a, _c: ARTICULOS)
    return candidato


def test_la_noticia_siguiente_del_mismo_medio_se_manda() -> None:
    elegidas = [a["url"] for a in extraccion.elegir_fuentes(ARTICULOS)]
    assert elegidas == [PRIMERA, POLICIA]


def test_con_tres_medios_no_cambia_y_los_huecos_van_por_lo_mas_reciente() -> None:
    otros = [_articulo(f"https://m{n}.md/a", f"2026-11-05T1{n}:00:00Z", "t", f"m{n}.md")
             for n in (4, 6)]  # fmt: skip
    assert [a["url"] for a in extraccion.elegir_fuentes([*ARTICULOS, *otros])] == [
        PRIMERA, "https://m4.md/a", "https://m6.md/a",
    ]  # fmt: skip
    mas = [_articulo(f"https://news.yam.md/ro/story/{n}", f"2026-11-0{n}T10:00:00Z", "t")
           for n in (6, 7)]  # fmt: skip
    assert [a["url"] for a in extraccion.elegir_fuentes([*ARTICULOS, *mas])] == [
        PRIMERA, "https://news.yam.md/ro/story/7", "https://news.yam.md/ro/story/6",
    ]  # fmt: skip


def test_el_descartado_que_no_leyo_la_noticia_de_la_policia_se_vuelve_a_extraer(
    almacen: Almacen, monkeypatch: pytest.MonkeyPatch
) -> None:
    candidato = _preparar(almacen, monkeypatch, [PRIMERA], None)
    assert extraccion.fuentes_sin_leer(almacen, candidato)
    assert extraccion.necesita_extraccion(almacen, candidato)
    # La lista de los de antes de la ventana se hace una vez y lo lleva.
    assert extraccion.revisar_fuentes_sin_leer(almacen, AHORA) == {CANDIDATO}
    assert (almacen.cursor(extraccion.REVISION_FUENTES) or {}).get("marcados") == [CANDIDATO]


def test_ya_leida_o_ya_incidente_no_se_repite(
    almacen: Almacen, monkeypatch: pytest.MonkeyPatch
) -> None:
    candidato = _preparar(almacen, monkeypatch, [PRIMERA, POLICIA], None)
    assert not extraccion.fuentes_sin_leer(almacen, candidato)
    assert not extraccion.necesita_extraccion(almacen, candidato)
    candidato = _preparar(almacen, monkeypatch, [PRIMERA], "EODI-2026-00999")
    assert not extraccion.fuentes_sin_leer(almacen, candidato)
