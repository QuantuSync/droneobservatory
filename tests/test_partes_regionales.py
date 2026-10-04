"""Partes de las administraciones regionales que no nombran pueblos: comunidades («громада»)
como lugar, líneas por lugar con varias armas, el parte de la frontera de Sumy y el histórico
que el lector añade después (docs/informe_errores_datos.md, bloque 2)."""

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from almacen.base import Almacen
from proceso import impactos_guerra
from proceso.lugares_guerra import base_unidad
from proceso.mensajes_guerra import analizar
from recogida import guerra as paso
from recogida.canales_guerra import Canal, Datos
from tests.nomenclator_falso import nomenclator

N = nomenclator()
PUBLICADO = datetime(2026, 10, 1, 6, 0, tzinfo=UTC)
JARKOV = frozenset({"UA-63"})


def test_base_de_la_comunidad_igual_en_todos_sus_casos() -> None:
    assert base_unidad("Краснопільській") == base_unidad("Краснопільська") == "краснопіль"
    assert base_unidad("Нікопольщині") == base_unidad("Нікопольський") == "нікополь"


def test_la_comunidad_es_el_lugar_con_su_centro_y_su_alcance() -> None:
    # Como el parte de Dnipró: «По Синельниківському, а саме Межівській громаді, росіяни
    # вдарили БпЛА» (t.me/adm_dp/32676), con la comunidad del nomenclátor de prueba.
    leido = analizar(
        "По Чугуївському району, а саме Малинівській громаді, росіяни вдарили БпЛА. "
        "Загорілися 2 авто.",
        PUBLICADO, N, JARKOV,
    )  # fmt: skip
    assert [(i.lugar.nombre, i.lugar.nivel) for i in leido.impactos] == [
        ("Малинівська громада", "comunidad")
    ]
    lugar = leido.impactos[0].lugar
    assert lugar.id.endswith(":comunidad")
    assert lugar.documento()["nivel"] == "comunidad"


def test_la_localidad_que_nombra_el_mensaje_gana_a_su_comunidad() -> None:
    leido = analizar(
        "Ворог атакував Чугуївську громаду безпілотниками. У Чугуєві пошкоджено будинок.",
        PUBLICADO, N, JARKOV,
    )  # fmt: skip
    assert [i.lugar.nombre for i in leido.impactos] == ["Чугуїв"]


def test_linea_por_lugar_con_varias_armas() -> None:
    # Parte de la frontera de Sumy (t.me/Sumy_news_ODA/34444), con la comunidad de prueba.
    texto = (
        "‼️⚫Малинівська громада: ворог здійснив обстріли БпЛА (3 вибухи), пуски КАБів (33 вибухи)."
    )
    leido = analizar(texto, PUBLICADO, N, JARKOV)
    assert [i.lugar.nombre for i in leido.impactos] == ["Малинівська громада"]
    # Sin el dron en la línea, no.
    leido = analizar(
        "Ворог атакував безпілотниками область. Малинівська громада: мінометний обстріл (5 "
        "вибухів).", PUBLICADO, N, JARKOV,
    )  # fmt: skip
    assert leido.impactos == []


def test_el_parte_de_la_frontera_es_un_parte_diario() -> None:
    texto = (
        "⚡Сумщина\nСитуація на прикордонні станом на 21.00\n10 березня 2025\n\n💥Протягом дня "
        "росіяни здійснили 116 обстрілів.\n\n‼️⚫Малинівська громада: удари FPV-дронами (2 "
        "вибухи)."
    )
    leido = analizar(texto, PUBLICADO, N, JARKOV)
    assert leido.parte_diario
    assert [i.lugar.nombre for i in leido.impactos] == ["Малинівська громада"]


def test_compuesto_con_guion_no_es_la_localidad_de_su_primera_palabra() -> None:
    hallados = N.localidades_en("Чугуїв-Малинівська громада", JARKOV)
    assert all(h.texto != "Чугуїв" for h in hallados)


# --- Histórico añadido después y relectura con otra versión -------------------------------

OVA = Canal(
    id="ova_kharkiv", canal="kharkivoda", grupo="ova_ua", pais="UA", region="UA-63",
    sentido="RU_UA", idioma="uk", titulo="kharkivoda", insignia=False, descripcion_enlaza=(),
    web_oficial=None, web_enlaza=None, web_desde_servidor=False, fiabilidad="B",
    origen="oficial", medio="Харківська ОВА", autoridad_ocupacion=False,
    identificado={"fecha": "2026-10-01"}, institucion="ova_kharkiv",
)  # fmt: skip
AHORA = datetime(2026, 10, 4, 9, 0, tzinfo=UTC)


@pytest.fixture(autouse=True)
def canales_de_prueba(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(impactos_guerra, "_canales", lambda: {"kharkivoda": OVA})


def _escribir(tmp_path: Path, publicaciones: list[tuple[int, str, str]]) -> None:
    ruta = tmp_path / "canales" / "kharkivoda" / "2025-03.jsonl"
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with ruta.open("a", encoding="utf-8") as fichero:
        for id_, fecha, texto in publicaciones:
            fichero.write(json.dumps({"id": id_, "fecha": fecha, "texto": texto},
                                     ensure_ascii=False) + "\n")  # fmt: skip


def test_el_historico_que_llega_despues_se_lee_en_la_hora_siguiente(tmp_path: Path) -> None:
    almacen = Almacen.abrir()
    _escribir(tmp_path, [(500, "2026-10-04T08:00:00Z", "Вночі ворог вдарив дроном по Чугуєву.")])
    paso.procesar(almacen, Datos(tmp_path), [OVA], N, AHORA)
    assert almacen.cursor("guerra:ova_kharkiv") == {"ultimo_id": 500}
    # El lector recorre el histórico hacia atrás y deja una publicación antigua (por debajo
    # del cursor y de hace meses): antes no se leía nunca.
    _escribir(tmp_path, [(100, "2025-03-01T08:00:00Z", "Вночі ворог вдарив дроном по Харкову.")])
    resumen = paso.procesar(almacen, Datos(tmp_path), [OVA], N, AHORA)
    assert resumen.con_impactos == 1
    assert sorted(d["lugar"]["nombre"] for d in impactos_guerra.vigentes(almacen)) == [
        "Харків", "Чугуїв",
    ]  # fmt: skip
    # Ya leídas con esta versión, no se vuelven a leer.
    assert paso.procesar(almacen, Datos(tmp_path), [OVA], N, AHORA).mensajes == 0


def test_una_version_nueva_del_analizador_se_aplica_a_lo_antiguo(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    almacen = Almacen.abrir()
    _escribir(tmp_path, [(100, "2025-03-01T08:00:00Z", "Вночі ворог вдарив дроном по Харкову.")])
    paso.procesar(almacen, Datos(tmp_path), [OVA], N, AHORA)
    monkeypatch.setattr(paso, "VERSION", "mensajes-guerra/prueba")
    assert paso.procesar(almacen, Datos(tmp_path), [OVA], N, AHORA).mensajes == 1
