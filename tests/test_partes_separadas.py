"""Las partes de una separación revisada son sucesos distintos desde que nace la ficha de cada
una, con el identificador que tenga, aunque la separación no lleve la marca «distintos» y antes de
enlazarse como relacionadas. El 30 de octubre de 2026 la parte del 29/10 de EODI-2025-00178 nació
como EODI-2025-00472 y la regla «mismo sitio y misma ventana» la volvió a fundir en 00178 en la
misma recogida (fusión 2438)."""

import json
from pathlib import Path
from typing import Any

import pytest

from proceso import auditoria_fichas, incidentes
from recogida import revisados
from tests.ejemplos import VOCABULARIO_MODELOS
from tests.test_control_fichas import AHORA, _base, _nuremberg_alemana, _nuremberg_griega

VIEJO, NUEVO = "EODI-2026-09515", "EODI-2026-09516"
NOTA = {"es": "Juntaba dos sucesos.", "en": "It merged two events."}


def _separacion(ruta: Path, distintos: bool = False) -> dict[str, Any]:
    """Como la separación de EODI-2025-00178: dos partes, sin «distintos»."""
    revision: dict[str, Any] = {
        "incidente": VIEJO,
        "motivo": NOTA,
        "partes": [
            {"es_suceso": True, "fecha": "2026-10-13", "pais": "DE", "coincide_con": None,
             "fuentes": ["gdelt-infranken", "gdelt-infranken-declaracion-1",
                         "gdelt-schwaebische"]},
            {"es_suceso": True, "fecha": "2026-10-13", "pais": "DE", "coincide_con": None,
             "fuentes": ["gdelt-dnews"]},
        ],
    }  # fmt: skip
    if distintos:
        revision["distintos"] = True
    configuracion = {"separar": [revision], "distintos": []}
    ruta.write_text(json.dumps(configuracion), encoding="utf-8")
    return configuracion


@pytest.fixture
def separada(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> dict[str, Any]:
    configuracion = _separacion(tmp_path / "revisados.json")
    mapa = incidentes.partes_por_articulo(tmp_path / "revisados.json")
    monkeypatch.setattr(incidentes, "partes_por_articulo", lambda: mapa)
    monkeypatch.setattr(incidentes, "separaciones_distintas", lambda: frozenset())
    monkeypatch.setattr(incidentes, "pares_distintos", lambda: frozenset())
    monkeypatch.setattr(revisados, "cargar", lambda: configuracion)
    return configuracion


def _alemana() -> dict[str, Any]:
    """La alemana en el mismo sitio y a la misma hora que la griega: la regla las junta."""
    documento = _nuremberg_alemana()
    griega = _nuremberg_griega()
    documento["lugar"] = griega["lugar"]
    documento["tiempo"] = griega["tiempo"]
    return documento


def _relacionadas(a: dict[str, Any], b: dict[str, Any]) -> None:
    a["relacionados"] = [{"id": b["id"], "separado_de": VIEJO, "nota": NOTA}]
    b["relacionados"] = [{"id": a["id"], "separado_de": VIEJO, "nota": NOTA}]


def _fundir(almacen: Any, motivo: str = "mismo sitio y misma ventana") -> None:
    viejo, nuevo = almacen.incidente(VIEJO), almacen.incidente(NUEVO)
    hecho, aportadas = incidentes.absorber(viejo, nuevo, AHORA)
    almacen.guardar_incidente(hecho, AHORA, VOCABULARIO_MODELOS)
    almacen.guardar_incidente({**nuevo, "fusionado_en": VIEJO}, AHORA, VOCABULARIO_MODELOS)
    almacen.registrar_fusion("2026-10-30T01:17Z", NUEVO, VIEJO, motivo, aportadas)


def test_sin_separacion_la_regla_las_junta() -> None:
    assert incidentes.encajan(_alemana(), _nuremberg_griega())


def test_las_partes_relacionadas_sin_la_marca_no_se_juntan(separada: dict[str, Any]) -> None:
    # Lo de EODI-2025-00178 y EODI-2025-00472: relacionadas por la separación, que no lleva
    # «distintos». Antes del arreglo, la regla las fundía.
    viejo, nuevo = _alemana(), _nuremberg_griega()
    _relacionadas(viejo, nuevo)
    assert incidentes.de_partes_separadas(viejo, nuevo)
    assert not incidentes.encajan(viejo, nuevo)
    almacen = _base(viejo, nuevo)
    assert incidentes.fusionar(almacen, AHORA, VOCABULARIO_MODELOS) == 0
    assert "fusionado_en" not in (almacen.incidente(NUEVO) or {})


def test_la_parte_recien_nacida_no_se_junta_antes_de_enlazarse(separada: dict[str, Any]) -> None:
    # La parte nueva nace en el extractor con otro identificador y sin relacionados: la regla
    # corre antes de la siguiente pasada de la separación.
    almacen = _base(_alemana(), _nuremberg_griega())
    assert incidentes.fusionar(almacen, AHORA, VOCABULARIO_MODELOS) == 0


def test_dos_registros_de_la_misma_parte_si_se_juntan(separada: dict[str, Any]) -> None:
    otro = _nuremberg_griega()
    otro["fuentes"] = [{**otro["fuentes"][0], "id": "gdelt-schwaebische"}]
    assert not incidentes.de_partes_separadas(_alemana(), otro)
    assert incidentes.encajan(_alemana(), otro)


def test_un_articulo_de_las_dos_partes_no_separa(tmp_path: Path) -> None:
    configuracion = _separacion(tmp_path / "r.json")
    configuracion["separar"][0]["partes"][1]["fuentes"].append("gdelt-infranken-declaracion-2")
    (tmp_path / "r.json").write_text(json.dumps(configuracion), encoding="utf-8")
    mapa = incidentes.partes_por_articulo(tmp_path / "r.json")
    assert "gdelt-infranken" not in mapa
    assert mapa["gdelt-dnews"] == frozenset({(VIEJO, 1)})


def test_la_union_de_la_regla_la_ve_la_auditoria_y_se_deshace(separada: dict[str, Any]) -> None:
    almacen = _base(_alemana(), _nuremberg_griega())
    _fundir(almacen)
    assert auditoria_fichas.uniones_marcadas(almacen.incidentes()) == [f"{NUEVO}→{VIEJO}"]
    assert incidentes.revisar_fusiones(almacen, AHORA, VOCABULARIO_MODELOS) == [NUEVO]
    assert "fusionado_en" not in (almacen.incidente(NUEVO) or {})
    assert auditoria_fichas.uniones_marcadas(almacen.incidentes()) == []


def test_la_separacion_deshace_la_union_y_las_enlaza(separada: dict[str, Any]) -> None:
    almacen = _base(_alemana(), _nuremberg_griega())
    _fundir(almacen)
    revisados._deshacer_entre_partes(almacen, [[VIEJO], [NUEVO]], AHORA, VOCABULARIO_MODELOS)
    assert "fusionado_en" not in (almacen.incidente(NUEVO) or {})


def test_la_union_revisada_a_mano_no_se_deshace(separada: dict[str, Any]) -> None:
    almacen = _base(_alemana(), _nuremberg_griega())
    _fundir(almacen, incidentes.PREFIJO_REVISADA + "el mismo suceso")
    revisados._deshacer_entre_partes(almacen, [[VIEJO], [NUEVO]], AHORA, VOCABULARIO_MODELOS)
    assert incidentes.revisar_fusiones(almacen, AHORA, VOCABULARIO_MODELOS) == []
    assert (almacen.incidente(NUEVO) or {}).get("fusionado_en") == VIEJO


def test_la_configuracion_de_vilna() -> None:
    mapa = incidentes.partes_por_articulo()
    assert mapa["gdelt-8f443417cf9ade19"] == frozenset({("EODI-2025-00178", 0)})
    assert mapa["gdelt-16109fdf16777cbb"] == frozenset({("EODI-2025-00178", 1)})
    assert frozenset(("EODI-2025-00178", "EODI-2025-00472")) in incidentes.pares_distintos()


def test_una_ficha_que_aun_junta_varias_partes_no_bloquea(separada: dict[str, Any]) -> None:
    # Como las uniones del 4/10/2026 en EODI-2025-00154: el absorbido es de una parte y el
    # destino lleva esa parte y otras; comparten la parte, así que no se deshace por esto.
    mezclada = _alemana()
    mezclada["fuentes"] = [*mezclada["fuentes"], *_nuremberg_griega()["fuentes"]]
    registro = _nuremberg_griega()
    registro["id"] = "EODI-2026-09517"
    registro["fuentes"] = [{**_alemana()["fuentes"][0], "id": "gdelt-infranken-declaracion-1"}]
    assert not incidentes.de_partes_separadas(mezclada, registro)
    assert incidentes.de_partes_separadas(_alemana(), _nuremberg_griega())
