import itertools

import pytest

from esquema import Documento
from proceso.estados import (
    Capa,
    Estado,
    TransicionNoPermitida,
    errores_historial,
    nuevo_estado,
    permitida,
    transitar,
)
from tests.ejemplos import fuente, instante

PERMITIDAS = {
    (Estado.NOTIFICADO, Estado.CONFIRMADO),
    (Estado.CONFIRMADO, Estado.ATRIBUIDO),
    (Estado.NOTIFICADO, Estado.DESMENTIDO),
    (Estado.CONFIRMADO, Estado.DESMENTIDO),
    (Estado.ATRIBUIDO, Estado.DESMENTIDO),
    (Estado.DESMENTIDO, Estado.CONFIRMADO),
}

# D desmiente: una autoridad B (más fiable) o D (igual) puede revertir; una C que no es
# autoridad o una autoridad E (menos fiable) no.
FUENTES: dict[str, Documento] = {
    "F1": fuente("F1", "B"),
    "F2": fuente("F2", "A", es_autoridad=True),
    "DESMIENTE": fuente("DESMIENTE", "D", es_autoridad=True),
    "AUTORIDAD_B": fuente("AUTORIDAD_B", "B", es_autoridad=True),
    "AUTORIDAD_D": fuente("AUTORIDAD_D", "D", es_autoridad=True),
    "AUTORIDAD_E": fuente("AUTORIDAD_E", "E", publica=False, es_autoridad=True),
    "MEDIO_C": fuente("MEDIO_C", "C"),
}


def desmentido() -> Documento:
    estado = nuevo_estado(instante("2025-10-01T21:00Z"), "F1")
    estado = transitar(estado, Estado.CONFIRMADO, instante("2025-10-01T22:00Z"), "F2", FUENTES)
    return transitar(estado, Estado.DESMENTIDO, instante("2025-10-02T09:00Z"), "DESMIENTE", FUENTES)


@pytest.mark.parametrize(("origen", "destino"), list(itertools.product(Estado, Estado)))
def test_tabla_completa_de_transiciones(origen: Estado, destino: Estado) -> None:
    assert permitida(origen, destino) == ((origen, destino) in PERMITIDAS)


def test_ucrania_no_admite_atribucion() -> None:
    assert not permitida(Estado.CONFIRMADO, Estado.ATRIBUIDO, Capa.UCRANIA)
    assert permitida(Estado.NOTIFICADO, Estado.CONFIRMADO, Capa.UCRANIA)
    assert permitida(Estado.CONFIRMADO, Estado.DESMENTIDO, Capa.UCRANIA)


def test_transitar_anade_al_historial_sin_modificar_el_original() -> None:
    inicial = nuevo_estado(instante("2025-10-01T21:00Z"), "F1")
    confirmado = transitar(inicial, Estado.CONFIRMADO, instante("2025-10-01T22:00Z"), "F2", FUENTES)
    assert inicial["actual"] == "notificado"
    assert len(inicial["historial"]) == 1
    assert confirmado["actual"] == "confirmado"
    assert [p["fuente_id"] for p in confirmado["historial"]] == ["F1", "F2"]


def test_desmentido_conserva_todo_el_historial() -> None:
    estado = desmentido()
    assert [p["estado"] for p in estado["historial"]] == ["notificado", "confirmado", "desmentido"]
    assert errores_historial(estado, FUENTES) == []


def test_atribuido_sin_confirmado_no_permitido() -> None:
    estado = nuevo_estado(instante("2025-10-01T21:00Z"), "F1")
    with pytest.raises(TransicionNoPermitida):
        transitar(estado, Estado.ATRIBUIDO, instante("2025-10-01T22:00Z"), "F2", FUENTES)


@pytest.mark.parametrize("revierte", ["AUTORIDAD_B", "AUTORIDAD_D"])
def test_reversion_permitida_y_registrada(revierte: str) -> None:
    anterior = desmentido()
    estado = transitar(
        anterior, Estado.CONFIRMADO, instante("2025-10-03T09:00Z"), revierte, FUENTES
    )
    assert estado["actual"] == "confirmado"
    assert [p["estado"] for p in estado["historial"]] == [
        "notificado",
        "confirmado",
        "desmentido",
        "confirmado",
    ]
    assert estado["historial"][-1]["fuente_id"] == revierte
    assert errores_historial(estado, FUENTES) == []
    assert anterior["actual"] == "desmentido"


@pytest.mark.parametrize(
    ("revierte", "motivo"),
    [
        ("MEDIO_C", "exige una autoridad"),
        ("AUTORIDAD_E", "fiabilidad igual o mayor"),
        ("NO_EXISTE", "fuente inexistente"),
    ],
)
def test_reversion_rechazada(revierte: str, motivo: str) -> None:
    with pytest.raises(TransicionNoPermitida, match=motivo):
        transitar(desmentido(), Estado.CONFIRMADO, instante("2025-10-03T09:00Z"), revierte, FUENTES)


def test_desmentido_solo_revierte_a_confirmado() -> None:
    for destino in (Estado.NOTIFICADO, Estado.ATRIBUIDO, Estado.DESMENTIDO):
        with pytest.raises(TransicionNoPermitida):
            transitar(desmentido(), destino, instante("2025-10-03T09:00Z"), "AUTORIDAD_B", FUENTES)


def test_errores_historial_detecta_reversion_invalida() -> None:
    estado = desmentido()
    estado["historial"].append(
        {"estado": "confirmado", "fecha": instante("2025-10-03T09:00Z"), "fuente_id": "MEDIO_C"}
    )
    estado["actual"] = "confirmado"
    assert any("exige una autoridad" in e for e in errores_historial(estado, FUENTES))


def test_errores_historial_detecta_salto_y_desajuste() -> None:
    fecha = instante("2025-10-01T21:00Z")
    estado = {
        "actual": "confirmado",
        "historial": [
            {"estado": "notificado", "fecha": fecha, "fuente_id": "F1"},
            {"estado": "atribuido", "fecha": fecha, "fuente_id": "F1"},
        ],
    }
    errores = errores_historial(estado, FUENTES)
    assert any("notificado → atribuido" in e for e in errores)
    assert any("distinto del último" in e for e in errores)


def test_errores_historial_exige_inicio_notificado() -> None:
    fecha = instante("2025-10-01T21:00Z")
    estado = {
        "actual": "confirmado",
        "historial": [{"estado": "confirmado", "fecha": fecha, "fuente_id": "F1"}],
    }
    assert any("empieza en" in e for e in errores_historial(estado, FUENTES))
