"""Código del Almirantazgo: credibilidad de un dato a partir de quién lo respalda o lo contradice.

Función pura: el resultado depende solo de las declaraciones, no de su orden.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from enum import IntEnum, StrEnum


class Fiabilidad(StrEnum):
    """Fiabilidad fija de la fuente, de A (más fiable) a F."""

    A = "A"
    B = "B"
    C = "C"
    D = "D"
    E = "E"
    F = "F"

    @property
    def rango(self) -> int:
        # Menor rango, mayor fiabilidad.
        return list(Fiabilidad).index(self)


class Credibilidad(IntEnum):
    CONFIRMADO = 1
    PROBABLE = 2
    POSIBLE = 3
    DUDOSO = 4
    IMPROBABLE = 5
    SIN_BASE = 6


class Postura(StrEnum):
    RESPALDA = "respalda"
    CONTRADICE = "contradice"


FIABILIDAD_ALTA = frozenset({Fiabilidad.A, Fiabilidad.B})
FIABILIDAD_INTERNA = frozenset({Fiabilidad.E, Fiabilidad.F})
FIABILIDAD_MEDIA_RANGOS = frozenset({Fiabilidad.C.rango, Fiabilidad.D.rango})
FUENTES_INDEPENDIENTES_PARA_CONFIRMAR = 2


@dataclass(frozen=True)
class Declaracion:
    """Lo que dice una fuente sobre un dato.

    nota identifica la nota original: las réplicas de una misma nota comparten
    nota y no cuentan como fuentes independientes.
    """

    nota: str
    fiabilidad: Fiabilidad
    es_autoridad: bool
    postura: Postura


def credibilidad(declaraciones: Iterable[Declaracion]) -> Credibilidad:
    lista = list(declaraciones)
    respaldos = [t for t in lista if t.postura is Postura.RESPALDA]
    contras = [t for t in lista if t.postura is Postura.CONTRADICE]

    # 5: lo contradice una autoridad.
    if any(t.es_autoridad for t in contras):
        return Credibilidad.IMPROBABLE
    if not respaldos:
        return Credibilidad.SIN_BASE

    # 4: lo contradice una fuente de fiabilidad igual o mayor que la mejor que lo respalda.
    mejor = min(t.fiabilidad.rango for t in respaldos)
    if any(t.fiabilidad.rango <= mejor for t in contras):
        return Credibilidad.DUDOSO

    # 1: lo confirma una autoridad o dos fuentes A o B independientes.
    notas_altas = {t.nota for t in respaldos if t.fiabilidad in FIABILIDAD_ALTA}
    if any(t.es_autoridad for t in respaldos):
        return Credibilidad.CONFIRMADO
    if len(notas_altas) >= FUENTES_INDEPENDIENTES_PARA_CONFIRMAR:
        return Credibilidad.CONFIRMADO

    # 2: una fuente A o B coherente con el resto (nadie la contradice).
    if notas_altas and not contras:
        return Credibilidad.PROBABLE

    # 3: una fuente C o D, o una A o B contradicha por otra de menor fiabilidad.
    # Llegados aquí, cualquier contradicción viene de una fuente menos fiable.
    if notas_altas or mejor in FIABILIDAD_MEDIA_RANGOS:
        return Credibilidad.POSIBLE

    # 6: solo fuentes E o F.
    return Credibilidad.SIN_BASE
