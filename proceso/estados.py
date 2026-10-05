"""Máquina de estados de incidentes y ataques. Nada se borra: cada cambio se añade al historial."""

import copy
import itertools
from collections.abc import Mapping
from enum import StrEnum

from esquema import Documento
from proceso.credibilidad import Fiabilidad


class Estado(StrEnum):
    NOTIFICADO = "notificado"
    CONFIRMADO = "confirmado"
    ATRIBUIDO = "atribuido"
    DESMENTIDO = "desmentido"


class Capa(StrEnum):
    GENERAL = "general"
    UCRANIA = "ucrania"


ESTADO_INICIAL = Estado.NOTIFICADO

# notificado → confirmado → atribuido, desde cualquiera → desmentido,
# y desmentido → confirmado como reversión condicionada.
TRANSICIONES: dict[Estado, frozenset[Estado]] = {
    Estado.NOTIFICADO: frozenset({Estado.CONFIRMADO, Estado.DESMENTIDO}),
    Estado.CONFIRMADO: frozenset({Estado.ATRIBUIDO, Estado.DESMENTIDO}),
    Estado.ATRIBUIDO: frozenset({Estado.DESMENTIDO}),
    Estado.DESMENTIDO: frozenset({Estado.CONFIRMADO}),
}

# Transiciones que además exigen que las provoque una autoridad con fiabilidad
# igual o mayor que la de la fuente que provocó el estado de origen.
REVERSIONES = frozenset({(Estado.DESMENTIDO, Estado.CONFIRMADO)})

# Retirada de una atribución que no se sostiene (proceso/atribucion.retirar), o de una
# confirmación que la autoridad no daba (la policía acude y no ve ningún dron; revisada a mano,
# recogida/revisados.py): vuelve al estado de antes y solo vale con su motivo en el paso del
# historial. No la provoca una fuente por sí sola.
RETIRADAS = frozenset(
    {
        (Estado.ATRIBUIDO, Estado.CONFIRMADO),
        (Estado.ATRIBUIDO, Estado.NOTIFICADO),
        (Estado.CONFIRMADO, Estado.NOTIFICADO),
    }
)

# En la capa de Ucrania la atribución no aplica.
EXCLUIDOS_POR_CAPA: dict[Capa, frozenset[Estado]] = {
    Capa.GENERAL: frozenset(),
    Capa.UCRANIA: frozenset({Estado.ATRIBUIDO}),
}


class TransicionNoPermitida(ValueError):
    pass


def permitida(origen: Estado, destino: Estado, capa: Capa = Capa.GENERAL) -> bool:
    """Permitida por la tabla; las reversiones se comprueban aparte con sus fuentes."""
    return destino in TRANSICIONES[origen] and destino not in EXCLUIDOS_POR_CAPA[capa]


def error_reversion(desmiente: Documento | None, revierte: Documento | None) -> str | None:
    """Motivo por el que una reversión no vale, o None si vale."""
    if desmiente is None or revierte is None:
        return "la reversión cita una fuente inexistente"
    if not revierte.get("es_autoridad"):
        return "revertir un desmentido exige una autoridad"
    if Fiabilidad(revierte["fiabilidad"]).rango > Fiabilidad(desmiente["fiabilidad"]).rango:
        return "revertir un desmentido exige fiabilidad igual o mayor que la de quien desmintió"
    return None


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
    fuentes: Mapping[str, Documento],
    capa: Capa = Capa.GENERAL,
) -> Documento:
    """Devuelve un estado nuevo con el cambio añadido; el original no se modifica."""
    origen = Estado(estado["actual"])
    if not permitida(origen, destino, capa):
        raise TransicionNoPermitida(f"{origen} → {destino} no permitida en la capa {capa}")
    if (origen, destino) in REVERSIONES:
        anterior = estado["historial"][-1]["fuente_id"]
        error = error_reversion(fuentes.get(anterior), fuentes.get(fuente_id))
        if error:
            raise TransicionNoPermitida(error)
    resultado = copy.deepcopy(estado)
    resultado["actual"] = destino.value
    resultado["historial"].append(
        {"estado": destino.value, "fecha": copy.deepcopy(fecha), "fuente_id": fuente_id}
    )
    return resultado


def errores_historial(
    estado: Documento, fuentes: Mapping[str, Documento], capa: Capa = Capa.GENERAL
) -> list[str]:
    """Comprueba que el historial sigue transiciones permitidas y acaba en el estado actual."""
    pasos = estado["historial"]
    historial = [Estado(paso["estado"]) for paso in pasos]
    errores: list[str] = []
    if not historial:
        return ["historial vacío"]
    if historial[0] is not ESTADO_INICIAL:
        errores.append(f"el historial empieza en {historial[0]}, no en {ESTADO_INICIAL}")
    for (origen, paso_origen), (destino, paso_destino) in itertools.pairwise(
        zip(historial, pasos, strict=True)
    ):
        if (origen, destino) in RETIRADAS:
            if not paso_destino.get("motivo"):
                errores.append(f"retirada sin motivo: {origen} → {destino}")
        elif not permitida(origen, destino, capa):
            errores.append(f"transición no permitida: {origen} → {destino}")
        elif (origen, destino) in REVERSIONES:
            error = error_reversion(
                fuentes.get(paso_origen["fuente_id"]), fuentes.get(paso_destino["fuente_id"])
            )
            if error:
                errores.append(error)
    if Estado(estado["actual"]) is not historial[-1]:
        errores.append(f"estado actual {estado['actual']} distinto del último del historial")
    return errores
