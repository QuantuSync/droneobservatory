"""Una revisión quita de una ficha una fuente que no es suya (sección `quitar_fuentes`): la que
añadió una cita revisada que ya salió de la configuración (EODI-2025-00051, la frase de Defensa
sobre los drones de Volkel, el 30 de octubre de 2026)."""

from typing import Any

import pytest

from recogida import revisados
from tests.ejemplos import VOCABULARIO_MODELOS
from tests.test_control_fichas import AHORA, _base, _nuremberg_alemana

AJENA = "gdelt-schwaebische"


def test_quita_la_fuente_y_lo_que_afirmaba() -> None:
    documento = _nuremberg_alemana()
    assert any(a.get("fuente_id") == AJENA for a in documento["afirmaciones"])
    nuevo = revisados.sin_fuentes(documento, set(), frozenset({AJENA}))
    assert nuevo is not None
    assert AJENA not in {f["id"] for f in nuevo["fuentes"]}
    assert not any(a.get("fuente_id") == AJENA for a in nuevo["afirmaciones"])
    assert AJENA in {f["id"] for f in documento["fuentes"]}


def test_no_deja_una_ficha_sin_fuentes() -> None:
    documento = _nuremberg_alemana()
    assert (
        revisados.sin_fuentes(documento, set(), frozenset(f["id"] for f in documento["fuentes"]))
        is None
    )


def test_la_recogida_la_quita_una_vez(monkeypatch: pytest.MonkeyPatch) -> None:
    documento = _nuremberg_alemana()
    configuracion: dict[str, Any] = {
        "quitar_fuentes": [
            {"incidente": documento["id"], "fuente": AJENA,
             "motivo": {"es": "No es suya.", "en": "Not its own."}},
        ],
    }  # fmt: skip
    monkeypatch.setattr(revisados, "cargar", lambda: configuracion)
    almacen = _base(documento)
    hechos = revisados.corregir(almacen, AHORA, VOCABULARIO_MODELOS)
    assert hechos.fuentes_quitadas == [documento["id"]]
    guardado = almacen.incidente(documento["id"])
    assert guardado is not None and AJENA not in {f["id"] for f in guardado["fuentes"]}
    assert revisados.corregir(almacen, AHORA, VOCABULARIO_MODELOS).fuentes_quitadas == []


def test_la_configuracion_de_eindhoven() -> None:
    entradas = revisados.cargar()["quitar_fuentes"]
    assert {
        "incidente": "EODI-2025-00051",
        "fuente": "revisada-534b7be4382f30fd-declaracion-1",
    } in [{"incidente": e["incidente"], "fuente": e["fuente"]} for e in entradas]
    for entrada in entradas:
        assert entrada["motivo"]["es"] and entrada["motivo"]["en"]
