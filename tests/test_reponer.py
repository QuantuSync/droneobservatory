"""Las fichas retiradas porque no se sabía la fecha del suceso, cuya fecha da después otra fuente
con una frase (configuracion/incidentes_revisados.json, «reponer» y «datos»): vuelven una vez y
como nuevas, así que el control las retiene hasta que pasen el filtro de entrada."""

from datetime import UTC, datetime
from typing import Any

import pytest

from almacen.base import Almacen
from recogida import control_fichas, revisados
from tests import ejemplos
from tests.ejemplos import VOCABULARIO_MODELOS

AHORA = datetime(2026, 10, 29, 11, 17, tzinfo=UTC)


def _retirada(motivo: str) -> dict[str, Any]:
    return {
        "fecha": {"valor": "2026-10-28T10:00Z", "precision": "minuto"},
        "motivo": motivo,
        "motivo_en": motivo,
    }


def test_la_retirada_por_fecha_desconocida_vuelve_una_vez_como_nueva(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    almacen = Almacen.abrir()
    incidente = ejemplos.incidente_minimo()
    id_ = incidente["id"]
    retirado = {**incidente, "retirado": _retirada("Fecha del suceso desconocida")}
    almacen.guardar_incidente(retirado, AHORA, VOCABULARIO_MODELOS)
    almacen.guardar_cursor(control_fichas.CURSOR, {"vistos": {id_: "2026-10-01T00:00:00Z"}})
    configuracion = {
        **revisados.cargar(),
        "reponer": [{"incidente": id_, "motivo": {"es": "La fecha.", "en": "The date."}}],
    }
    monkeypatch.setattr(revisados, "cargar", lambda: configuracion)

    hechos = revisados.corregir(almacen, AHORA, VOCABULARIO_MODELOS)
    assert hechos.repuestos == [id_]
    assert "retirado" not in (almacen.incidente(id_) or {})
    # Como una ficha nueva: fuera de las ya publicadas, el control la retiene hasta el filtro.
    assert id_ not in (almacen.cursor(control_fichas.CURSOR) or {})["vistos"]

    # Una sola vez: si después se vuelve a retirar, no vuelve sola.
    actual = almacen.incidente(id_)
    assert actual is not None
    almacen.guardar_incidente({**actual, "retirado": _retirada("otra")}, AHORA, VOCABULARIO_MODELOS)
    assert revisados.corregir(almacen, AHORA, VOCABULARIO_MODELOS).repuestos == []


def test_las_repuestas_tienen_su_fecha_con_cita() -> None:
    configuracion = revisados.cargar()
    inicios = {d["incidente"]: d for d in configuracion["datos"] if d["campo"] == "inicio"}
    for entrada in configuracion["reponer"]:
        revision = inicios[entrada["incidente"]]
        assert revision["cita"] and revision["enlace"] and revision["valor"][:4].isdigit()
        assert entrada["motivo"]["es"] and entrada["motivo"]["en"]


def test_la_repuesta_sigue_en_retirar_y_no_se_vuelve_a_retirar(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Las repuestas siguen en «retirar»: la recogida siguiente a la que las repuso las retiraba
    otra vez (EODI-2025-00312 y EODI-2026-00056, 29 de octubre de 2026). La retirada así hecha
    se deshace una vez más; otra retirada se queda."""
    almacen = Almacen.abrir()
    incidente = ejemplos.incidente_minimo()
    id_ = incidente["id"]
    motivo = {"es": "Fecha del suceso desconocida.", "en": "Unknown date."}
    retirado = {**incidente, "retirado": _retirada(motivo["es"])}
    almacen.guardar_incidente(retirado, AHORA, VOCABULARIO_MODELOS)
    configuracion = {
        **revisados.cargar(),
        "retirar": [{"incidente": id_, "motivo": motivo}],
        "reponer": [{"incidente": id_, "motivo": {"es": "La fecha.", "en": "The date."}}],
    }
    monkeypatch.setattr(revisados, "cargar", lambda: configuracion)

    assert revisados.corregir(almacen, AHORA, VOCABULARIO_MODELOS).repuestos == [id_]
    despues = datetime(2026, 10, 29, 12, 17, tzinfo=UTC)
    hechos = revisados.corregir(almacen, despues, VOCABULARIO_MODELOS)
    assert hechos.retirados == [] and hechos.repuestos == []
    assert "retirado" not in (almacen.incidente(id_) or {})

    # Retirada otra vez por «retirar» (el código anterior): vuelve.
    actual = almacen.incidente(id_)
    assert actual is not None
    retirada = {
        "fecha": {"valor": "2026-10-29T12:17Z", "precision": "minuto"},
        "motivo": motivo["es"],
        "motivo_en": motivo["en"],
    }
    almacen.guardar_incidente({**actual, "retirado": retirada}, despues, VOCABULARIO_MODELOS)
    luego = datetime(2026, 10, 29, 14, 17, tzinfo=UTC)
    assert revisados.corregir(almacen, luego, VOCABULARIO_MODELOS).repuestos == [id_]
    assert "retirado" not in (almacen.incidente(id_) or {})
