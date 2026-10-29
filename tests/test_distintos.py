"""Una decisión de «sucesos distintos» de una revisión o del experto no la deshace ninguna unión
automática (docs/sucesos_mezclados.md, «Dos fichas distintas sin nada que repartir»): el 29 de
octubre de 2026 la regla unió EODI-2026-00538 (un blanco aéreo) en EODI-2026-00541 (el petrolero),
que una revisión había dado por distintos."""

from typing import Any

import pytest

from proceso import auditoria_fichas, incidentes
from proceso import control_fichas as reglas
from recogida import control_fichas, revisados
from tests.ejemplos import VOCABULARIO_MODELOS
from tests.test_control_fichas import AHORA, _base, _nuremberg_alemana, _nuremberg_griega

VIEJO, NUEVO = "EODI-2026-09515", "EODI-2026-09516"
PAR = frozenset((VIEJO, NUEVO))
MOTIVO = {"es": "Dos sucesos distintos.", "en": "Two different events."}


@pytest.fixture
def revisados_distintos(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(incidentes, "pares_distintos", lambda: frozenset({PAR}))
    configuracion: dict[str, Any] = {
        "separar": [],
        "distintos": [{"incidentes": [VIEJO, NUEVO], "separado_de": VIEJO, "motivo": MOTIVO}],
    }
    monkeypatch.setattr(revisados, "cargar", lambda: configuracion)


def _decision_par(almacen: Any, decision: str, escalado: bool) -> None:
    documento: dict[str, Any] = {
        "decision": decision, "huella": "x", "fecha": "2026-10-13T05:00:00Z",
        "motivo_es": "días distintos",
    }  # fmt: skip
    if escalado:
        documento["escalado"] = ["dudoso"]
    almacen.guardar_controles({f"par:{VIEJO}|{NUEVO}": documento}, "2026-10-13T05:00:00Z")


def test_una_revision_de_distintos_impide_la_union_y_la_deja_como_propuesta(
    revisados_distintos: None,
) -> None:
    almacen = _base(_nuremberg_alemana(), _nuremberg_griega())
    viejo, nuevo = almacen.incidente(VIEJO), almacen.incidente(NUEVO)
    assert viejo is not None and nuevo is not None
    assert (
        control_fichas.unir(almacen, viejo, nuevo, "el mismo", AHORA, VOCABULARIO_MODELOS) is None
    )
    assert "fusionado_en" not in (almacen.incidente(NUEVO) or {})
    propuestas = almacen.cursor(control_fichas.CURSOR_PROPUESTAS) or {}
    assert propuestas[f"par:{VIEJO}|{NUEVO}"]["une"] == NUEVO


def test_la_revision_vale_para_el_control_el_filtro_y_la_segunda_lectura(
    revisados_distintos: None,
) -> None:
    viejo, nuevo = _nuremberg_alemana(), _nuremberg_griega()
    assert reglas.separados(viejo, nuevo)
    assert not reglas.candidatos(viejo, nuevo)
    assert not incidentes.encajan(viejo, nuevo)


def test_el_experto_que_dio_distintos_impide_la_union() -> None:
    almacen = _base(_nuremberg_alemana(), _nuremberg_griega())
    _decision_par(almacen, "distinto", escalado=True)
    assert incidentes.distintos_del_experto(almacen) == frozenset({PAR})
    viejo, nuevo = almacen.incidente(VIEJO), almacen.incidente(NUEVO)
    assert viejo is not None and nuevo is not None
    assert (
        control_fichas.unir(almacen, viejo, nuevo, "el mismo", AHORA, VOCABULARIO_MODELOS) is None
    )
    assert almacen.cursor(control_fichas.CURSOR_PROPUESTAS)


def test_el_distinto_del_modelo_base_o_del_plazo_no_impide_la_union() -> None:
    almacen = _base(_nuremberg_alemana(), _nuremberg_griega())
    _decision_par(almacen, "distinto", escalado=False)
    assert incidentes.distintos_del_experto(almacen) == frozenset()
    viejo, nuevo = almacen.incidente(VIEJO), almacen.incidente(NUEVO)
    assert viejo is not None and nuevo is not None
    assert control_fichas.unir(almacen, viejo, nuevo, "el mismo", AHORA, VOCABULARIO_MODELOS)
    assert (almacen.incidente(NUEVO) or {}).get("fusionado_en") == VIEJO


def test_el_control_no_vuelve_a_comparar_lo_que_el_experto_dio_por_distinto() -> None:
    almacen = _base(_nuremberg_alemana(), _nuremberg_griega())
    _decision_par(almacen, "distinto", escalado=True)
    ctx = control_fichas.Contexto(almacen, AHORA, VOCABULARIO_MODELOS, None, None, None, None,  # type: ignore[arg-type]
                                  decisiones=almacen.controles())  # fmt: skip
    assert ctx.del_experto == frozenset({PAR})
    assert control_fichas.pares_por_decidir(ctx, {VIEJO, NUEVO}) == []


def test_la_union_hecha_se_deshace_y_quedan_relacionadas(revisados_distintos: None) -> None:
    almacen = _base(_nuremberg_alemana(), _nuremberg_griega())
    viejo, nuevo = almacen.incidente(VIEJO), almacen.incidente(NUEVO)
    assert viejo is not None and nuevo is not None
    # Como la regla de fusión a las 00:17 del 29 de octubre de 2026.
    hecho, aportadas = incidentes.absorber(viejo, nuevo, AHORA)
    almacen.guardar_incidente(hecho, AHORA, VOCABULARIO_MODELOS)
    almacen.guardar_incidente({**nuevo, "fusionado_en": VIEJO}, AHORA, VOCABULARIO_MODELOS)
    almacen.registrar_fusion("2026-10-13T14:17Z", NUEVO, VIEJO, "mismo sitio y misma ventana",
                             aportadas)  # fmt: skip
    assert auditoria_fichas.uniones_marcadas(almacen.incidentes()) == [f"{NUEVO}→{VIEJO}"]
    revisados.separar(almacen, AHORA, VOCABULARIO_MODELOS)
    a, b = almacen.incidente(VIEJO), almacen.incidente(NUEVO)
    assert a is not None and b is not None and "fusionado_en" not in b
    assert {f["id"] for f in b["fuentes"]} & set(aportadas)
    assert not {f["id"] for f in a["fuentes"]} & (
        set(aportadas) - {f["id"] for f in viejo["fuentes"]}
    )
    assert [r["id"] for r in a["relacionados"]] == [NUEVO]
    assert [r["id"] for r in b["relacionados"]] == [VIEJO]
    assert b["relacionados"][0]["nota"] == MOTIVO
    assert auditoria_fichas.uniones_marcadas(almacen.incidentes()) == []


def test_la_auditoria_v_ve_la_union_sobre_un_distinto_del_experto() -> None:
    viejo, nuevo = _nuremberg_alemana(), _nuremberg_griega()
    unido = {**nuevo, "fusionado_en": VIEJO}
    assert auditoria_fichas.uniones_marcadas([viejo, unido], frozenset({PAR})) == [
        f"{NUEVO}→{VIEJO}"
    ]
    assert auditoria_fichas.uniones_marcadas([viejo, unido]) == []
    assert auditoria_fichas.auditar([viejo, unido], del_experto=frozenset({PAR}))["V"]


def test_la_configuracion_de_sulina() -> None:
    assert frozenset(("EODI-2026-00538", "EODI-2026-00541")) in incidentes.pares_distintos()
    for par in revisados.cargar()["distintos"]:
        assert len(par["incidentes"]) == 2 and par["separado_de"] in par["incidentes"]
        assert par["motivo"]["es"] and par["motivo"]["en"]
