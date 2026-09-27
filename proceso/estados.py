"""Máquina de estados de incidentes y ataques. Nada se borra: cada cambio se añade al historial."""

import copy
import itertools
from enum import StrEnum

from esquema import Documento


class Estado(StrEnum):
    NOTIFICADO = "notificado"
    CONFIRMADO = "confirmado"
    ATRIBUIDO = "atribuido"
    DESMENTIDO = "desmentido"


class Capa(StrEnum):
    GENERAL = "general"
    UCRANIA = "ucrania"


ESTADO_INICIAL = Estado.NOTIFICADO

# notificado → confirmado → atribuido, y desde cualquiera → desmentido.
TRANSICIONES: dict[Estado, frozenset[Estado]] = {
    Estado.NOTIFICADO: frozenset({Estado.CONFIRMADO, Estado.DESMENTIDO}),
    Estado.CONFIRMADO: frozenset({Estado.ATRIBUIDO, Estado.DESMENTIDO}),
    Estado.ATRIBUIDO: frozenset({Estado.DESMENTIDO}),
    Estado.DESMENTIDO: frozenset(),
}

# En la capa de Ucrania la atribución no aplica.
EXCLUIDOS_POR_CAPA: dict[Capa, frozenset[Estado]] = {
    Capa.GENERAL: frozenset(),
    Capa.UCRANIA: frozenset({Estado.ATRIBUIDO}),
}


class TransicionNoPermitida(ValueError):
    pass


def permitida(origen: Estado, destino: Estado, capa: Capa = Capa.GENERAL) -> bool:
    return destino in TRANSICIONES[origen] and destino not in EXCLUIDOS_POR_CAPA[capa]


def nuevo_estado(fecha: Documento, fuente_id: str) -> Documento:
    return {
        "actual": ESTADO_INICIAL.value,
        "historial": [{"estado": ESTADO_INICIAL.value, "fecha": fecha, "fuente_id": fuente_id}],
    }


def transitar(
    estado: Documento,
    destino: Estado,
    fecha: Documento,
    fuente_id: str,
    capa: Capa = Capa.GENERAL,
) -> Documento:
    """Devuelve un estado nuevo con el cambio añadido; el original no se modifica."""
    origen = Estado(estado["actual"])
    if not permitida(origen, destino, capa):
        raise TransicionNoPermitida(f"{origen} → {destino} no permitida en la capa {capa}")
    resultado = copy.deepcopy(estado)
    resultado["actual"] = destino.value
    resultado["historial"].append(
        {"estado": destino.value, "fecha": copy.deepcopy(fecha), "fuente_id": fuente_id}
    )
    return resultado


def errores_historial(estado: Documento, capa: Capa = Capa.GENERAL) -> list[str]:
    """Comprueba que el historial sigue transiciones permitidas y acaba en el estado actual."""
    historial = [Estado(paso["estado"]) for paso in estado["historial"]]
    errores: list[str] = []
    if not historial:
        return ["historial vacío"]
    if historial[0] is not ESTADO_INICIAL:
        errores.append(f"el historial empieza en {historial[0]}, no en {ESTADO_INICIAL}")
    for origen, destino in itertools.pairwise(historial):
        if not permitida(origen, destino, capa):
            errores.append(f"transición no permitida: {origen} → {destino}")
    if Estado(estado["actual"]) is not historial[-1]:
        errores.append(f"estado actual {estado['actual']} distinto del último del historial")
    return errores
