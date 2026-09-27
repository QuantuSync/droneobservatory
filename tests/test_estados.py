import itertools

import pytest

from proceso.estados import (
    Capa,
    Estado,
    TransicionNoPermitida,
    errores_historial,
    nuevo_estado,
    permitida,
    transitar,
)
from tests.ejemplos import instante

PERMITIDAS = {
    (Estado.NOTIFICADO, Estado.CONFIRMADO),
    (Estado.CONFIRMADO, Estado.ATRIBUIDO),
    (Estado.NOTIFICADO, Estado.DESMENTIDO),
    (Estado.CONFIRMADO, Estado.DESMENTIDO),
    (Estado.ATRIBUIDO, Estado.DESMENTIDO),
}


@pytest.mark.parametrize(("origen", "destino"), list(itertools.product(Estado, Estado)))
def test_tabla_completa_de_transiciones(origen: Estado, destino: Estado) -> None:
    assert permitida(origen, destino) == ((origen, destino) in PERMITIDAS)


def test_ucrania_no_admite_atribucion() -> None:
    assert not permitida(Estado.CONFIRMADO, Estado.ATRIBUIDO, Capa.UCRANIA)
    assert permitida(Estado.NOTIFICADO, Estado.CONFIRMADO, Capa.UCRANIA)
    assert permitida(Estado.CONFIRMADO, Estado.DESMENTIDO, Capa.UCRANIA)


def test_transitar_anade_al_historial_sin_modificar_el_original() -> None:
    inicial = nuevo_estado(instante("2025-10-01T21:00Z"), "F1")
    confirmado = transitar(inicial, Estado.CONFIRMADO, instante("2025-10-01T22:00Z"), "F2")
    assert inicial["actual"] == "notificado"
    assert len(inicial["historial"]) == 1
    assert confirmado["actual"] == "confirmado"
    assert [p["fuente_id"] for p in confirmado["historial"]] == ["F1", "F2"]


def test_desmentido_conserva_todo_el_historial() -> None:
    estado = nuevo_estado(instante("2025-10-01T21:00Z"), "F1")
    estado = transitar(estado, Estado.CONFIRMADO, instante("2025-10-01T22:00Z"), "F2")
    estado = transitar(estado, Estado.DESMENTIDO, instante("2025-10-02T09:00Z"), "F3")
    assert [p["estado"] for p in estado["historial"]] == ["notificado", "confirmado", "desmentido"]
    assert errores_historial(estado) == []


def test_atribuido_sin_confirmado_no_permitido() -> None:
    estado = nuevo_estado(instante("2025-10-01T21:00Z"), "F1")
    with pytest.raises(TransicionNoPermitida):
        transitar(estado, Estado.ATRIBUIDO, instante("2025-10-01T22:00Z"), "F2")


def test_desmentido_es_final() -> None:
    estado = nuevo_estado(instante("2025-10-01T21:00Z"), "F1")
    estado = transitar(estado, Estado.DESMENTIDO, instante("2025-10-01T22:00Z"), "F2")
    with pytest.raises(TransicionNoPermitida):
        transitar(estado, Estado.CONFIRMADO, instante("2025-10-01T23:00Z"), "F3")


def test_errores_historial_detecta_salto_y_desajuste() -> None:
    fecha = instante("2025-10-01T21:00Z")
    estado = {
        "actual": "confirmado",
        "historial": [
            {"estado": "notificado", "fecha": fecha, "fuente_id": "F1"},
            {"estado": "atribuido", "fecha": fecha, "fuente_id": "F1"},
        ],
    }
    errores = errores_historial(estado)
    assert any("notificado → atribuido" in e for e in errores)
    assert any("distinto del último" in e for e in errores)


def test_errores_historial_exige_inicio_notificado() -> None:
    fecha = instante("2025-10-01T21:00Z")
    estado = {
        "actual": "confirmado",
        "historial": [{"estado": "confirmado", "fecha": fecha, "fuente_id": "F1"}],
    }
    assert any("empieza en" in e for e in errores_historial(estado))
