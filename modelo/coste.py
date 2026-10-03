"""Coste de cada llamada al extractor y límites de gasto duros.

Las tarifas son las del modelo configurado en el secreto EODI_EXTRACTOR_MODELO
en septiembre de 2026, en dólares por millón de tokens. Si cambia el modelo,
hay que cambiarlas aquí.

Límites, compartidos por todo lo que llama al extractor:
- 5 dólares para todo el histórico (modo «historico»);
- 0,30 dólares al día para la recogida horaria (modo «horario»);
- 5 dólares para la revisión de todo lo publicado con las reglas de calidad de los
  datos (modo «revision», `python -m recogida.extractor revision`);
- 3 dólares para el histórico de las fuentes oficiales de detalle (modo «detalle»,
  `python -m recogida.detalle historico`), por lotes.
- 0,20 dólares al día para los mensajes de la capa de guerra que el código no resuelve
  (modo «guerra», en la recogida horaria), aparte del límite horario;
- 5 dólares para el histórico de esos mensajes desde el 1 de enero de 2025 (modo
  «guerra_historico», `python -m proceso.extraccion_guerra lote`);
- 2 dólares, una sola vez, para la tercera revisión de la calidad de los datos (modo
  «calidad», `python -m recogida.calidad`): candidatos separados por suceso, artículos que
  ahora se sitúan, candidatos de la búsqueda dirigida y los prioritarios nunca extraídos.
- 3 dólares, una sola vez, para el barrido dirigido desde enero de 2025 (modo «dirigida»,
  `python -m recogida.barrido_dirigido incorporar`): incidentes en España y en puertos y presas.

El barrido del catálogo vivo (recogida/catalogo_vivo.py) lleva su propio registro de gasto
fuera de la base: 0,10 dólares al día y 3 dólares una vez para su primera pasada.

Antes de cada llamada se suma lo gastado y el peor caso de la llamada (sus
tokens de entrada estimados y el máximo de salida); si pasa del límite, no se
llama.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any

MILLON = 1_000_000
PRECIO_ENTRADA = 1.00
PRECIO_SALIDA = 5.00
# La escritura en caché cuesta 1,25 veces la entrada y la lectura, 0,1 veces.
PRECIO_ESCRITURA_CACHE = 1.25
PRECIO_LECTURA_CACHE = 0.10
# Los lotes cuestan la mitad.
DESCUENTO_LOTE = 0.5
LIMITE_HISTORICO_USD = 5.00
LIMITE_DIARIO_USD = 0.30
LIMITE_REVISION_USD = 5.00
# Histórico de las fuentes oficiales de detalle (respuestas parlamentarias, informes de
# investigación, sentencias), procesado una sola vez por lotes: presupuesto propio, aparte del
# límite diario. Lo nuevo de cada día entra en el límite diario de la recogida horaria.
LIMITE_DETALLE_USD = 3.00
LIMITE_GUERRA_DIARIO_USD = 0.20
LIMITE_GUERRA_HISTORICO_USD = 5.00
LIMITE_CALIDAD_USD = 2.00
LIMITE_DIRIGIDA_USD = 3.00
# Una letra son unos 0,3 tokens en los idiomas europeos; se estima por lo alto con 0,5
# para que el peor caso no se quede corto.
TOKENS_POR_LETRA = 0.5


class Modo(StrEnum):
    HORARIO = "horario"
    HISTORICO = "historico"
    REVISION = "revision"
    DETALLE = "detalle"
    GUERRA = "guerra"
    GUERRA_HISTORICO = "guerra_historico"
    CALIDAD = "calidad"
    DIRIGIDA = "dirigida"


class LimiteGasto(RuntimeError):
    pass


@dataclass(frozen=True)
class Uso:
    entrada: int
    salida: int
    escritura_cache: int = 0
    lectura_cache: int = 0

    @classmethod
    def de_respuesta(cls, usage: dict[str, Any]) -> "Uso":
        return cls(
            entrada=int(usage.get("input_tokens", 0)),
            salida=int(usage.get("output_tokens", 0)),
            escritura_cache=int(usage.get("cache_creation_input_tokens") or 0),
            lectura_cache=int(usage.get("cache_read_input_tokens") or 0),
        )

    def coste(self, lote: bool = False) -> float:
        dolares = (
            self.entrada * PRECIO_ENTRADA
            + self.salida * PRECIO_SALIDA
            + self.escritura_cache * PRECIO_ENTRADA * PRECIO_ESCRITURA_CACHE
            + self.lectura_cache * PRECIO_ENTRADA * PRECIO_LECTURA_CACHE
        ) / MILLON
        return dolares * (DESCUENTO_LOTE if lote else 1)


def peor_caso(letras_entrada: int, max_salida: int, lote: bool = False) -> float:
    """Coste máximo de una llamada: toda la entrada sin caché y toda la salida permitida."""
    return Uso(int(letras_entrada * TOKENS_POR_LETRA), max_salida).coste(lote)


def limite(modo: Modo) -> float:
    return {
        Modo.HORARIO: LIMITE_DIARIO_USD,
        Modo.HISTORICO: LIMITE_HISTORICO_USD,
        Modo.REVISION: LIMITE_REVISION_USD,
        Modo.DETALLE: LIMITE_DETALLE_USD,
        Modo.GUERRA: LIMITE_GUERRA_DIARIO_USD,
        Modo.GUERRA_HISTORICO: LIMITE_GUERRA_HISTORICO_USD,
        Modo.CALIDAD: LIMITE_CALIDAD_USD,
        Modo.DIRIGIDA: LIMITE_DIRIGIDA_USD,
    }[modo]


def diario(modo: Modo) -> bool:
    """Los modos con límite diario (lo gastado se cuenta solo en el día UTC)."""
    return modo in {Modo.HORARIO, Modo.GUERRA}


def comprobar(gastado: float, previsto: float, modo: Modo) -> None:
    """Lanza LimiteGasto si lo gastado más lo previsto pasa del límite del modo."""
    if gastado + previsto > limite(modo):
        raise LimiteGasto(
            f"{modo}: gastado {gastado:.4f} + previsto {previsto:.4f} > {limite(modo):.2f} USD"
        )


def dia(momento: datetime) -> str:
    return momento.strftime("%Y-%m-%d")
