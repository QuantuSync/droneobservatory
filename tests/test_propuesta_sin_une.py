"""Una retrospectiva que el experto da por el mismo suceso que otra ficha y que no se puede unir
(el par no se junta: partes de una separación, distintos revisados) se guarda como propuesta:
«mismo», con «conserva» y sin «une» (recogida/control_fichas.retrospectivas). Los dos pasos que
recorren las uniones hechas leían «une» de toda decisión «mismo» y lanzaban KeyError: el control
entero se paraba en cada pasada, también en las siguientes, y las fichas nuevas de esas horas se
publicaban sin su filtro de entrada. Visto al leer el código el 10 de noviembre de 2026; en la
base no había ninguna decisión así."""

from datetime import UTC, datetime
from typing import Any

from almacen.base import Almacen
from recogida import control_fichas as control
from tests.ejemplos import VOCABULARIO_MODELOS

AHORA = datetime(2026, 11, 10, 10, 17, tzinfo=UTC)
PROPUESTA: dict[str, dict[str, Any]] = {
    "retrospectiva:EODI-2026-00900": {
        "decision": "mismo",
        "conserva": "EODI-2026-00134",
        "motivo_es": "la nota cuenta el suceso de agosto",
        "propuesta": True,
    }
}
UNION: dict[str, dict[str, Any]] = {
    "par:EODI-2026-00001|EODI-2026-00002": {
        "decision": "mismo",
        "conserva": "EODI-2026-00001",
        "une": "EODI-2026-00002",
        "motivo_es": "el mismo suceso",
    }
}


def test_una_propuesta_no_es_una_union() -> None:
    assert not control.una_union(PROPUESTA["retrospectiva:EODI-2026-00900"])
    assert control.una_union(UNION["par:EODI-2026-00001|EODI-2026-00002"])
    assert not control.una_union({"decision": "distinto"})


def test_la_propuesta_no_para_los_pasos_de_las_uniones() -> None:
    almacen = Almacen.abrir(":memory:")
    decisiones = {**PROPUESTA, **UNION}
    # Las fichas de la unión no están en la base: los dos pasos las saltan, sin tocar nada.
    assert control.conservar_la_mas_antigua(almacen, decisiones, AHORA, VOCABULARIO_MODELOS) == {}
    assert control.reaplicar_uniones(almacen, decisiones, AHORA, VOCABULARIO_MODELOS) == 0
