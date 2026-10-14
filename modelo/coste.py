"""Coste de cada llamada al extractor y límites de gasto duros.

Cada llamada se cobra con la tarifa del modelo que la hizo (modelo/modelos.py: el base, el
experto o el de antes), con su tramo de más de 100.000 tokens, sus precios de caché y el
descuento de los lotes.

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

- 0,15 dólares al día para el control de calidad de las fichas (modo «control», en la recogida
  horaria y en la revisión de madrugada: duplicados, respaldo de cada dato y traducción de las
  citas, recogida/control_fichas.py);
- 4 dólares, una sola vez, para el repaso de todo lo publicado con ese control (modo
  «control_repaso», `python -m recogida.control_fichas repaso`).
- 2 dólares, una sola vez, para traducir por lote las citas que quedaban sin traducir el 14 de
  octubre de 2026 (unas 8.600 de la capa de Ucrania y 440 de Europa) con el modelo base (modo
  «traducciones», `python -m recogida.control_fichas traducir-pendientes`).

El barrido del catálogo vivo (recogida/catalogo_vivo.py) lleva su propio registro de gasto
fuera de la base: 0,10 dólares al día y 3 dólares una vez para su primera pasada.

El modelo experto tiene además su propio tope diario, sumando todos los modos: 0,30 dólares
(LIMITE_EXPERTO_DIARIO_USD). Lo que gasta cuenta también en el modo de la llamada.

Antes de cada llamada se suma lo gastado y el peor caso de la llamada (sus
tokens de entrada estimados y el máximo de salida); si pasa del límite, no se
llama.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any

from modelo import modelos

DESCUENTO_LOTE = modelos.DESCUENTO_LOTE
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
LIMITE_CONTROL_DIARIO_USD = 0.15
# Repaso del control sobre todo lo publicado: 4 USD el 14 de octubre de 2026 de madrugada (se
# gastaron 3,46) y 6 USD más ese mismo día para las fichas que quedaron sin verificar.
LIMITE_CONTROL_REPASO_USD = 9.46
# Traducción de una sola vez de las citas atrasadas (14 de octubre de 2026), por lote.
LIMITE_TRADUCCIONES_USD = 2.00
# Tope diario del modelo experto, en todos los modos juntos.
LIMITE_EXPERTO_DIARIO_USD = 0.30
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
    CONTROL = "control"
    CONTROL_REPASO = "control_repaso"
    TRADUCCIONES = "traducciones"


class LimiteGasto(RuntimeError):
    pass


@dataclass(frozen=True)
class Uso:
    entrada: int
    salida: int
    escritura_cache: int = 0
    lectura_cache: int = 0
    # El modelo que hizo la llamada (el campo «model» de la respuesta); vacío, el base.
    modelo: str = ""

    @classmethod
    def de_respuesta(cls, usage: dict[str, Any], modelo: str | None = None) -> "Uso":
        return cls(
            entrada=int(usage.get("input_tokens", 0)),
            salida=int(usage.get("output_tokens", 0)),
            escritura_cache=int(usage.get("cache_creation_input_tokens") or 0),
            lectura_cache=int(usage.get("cache_read_input_tokens") or 0),
            modelo=modelo or "",
        )

    @classmethod
    def de_mensaje(cls, respuesta: dict[str, Any]) -> "Uso":
        """El uso de una respuesta del servicio, con el modelo que la dio."""
        return cls.de_respuesta(respuesta.get("usage", {}), respuesta.get("model"))

    def coste(self, lote: bool = False) -> float:
        return modelos.coste(
            self.modelo or None, self.entrada, self.salida, self.escritura_cache,
            self.lectura_cache, lote,
        )  # fmt: skip


def peor_caso(
    letras_entrada: int, max_salida: int, lote: bool = False, modelo: str | None = None,
    esfuerzo: str | None = None,
) -> float:  # fmt: skip
    """Coste máximo de una llamada: toda la entrada sin caché y toda la salida permitida, con el
    margen del razonamiento del modelo (el base si no se dice)."""
    nombre = modelo or modelos.base()
    salida = modelos.max_salida(nombre, max_salida, esfuerzo)
    return Uso(int(letras_entrada * TOKENS_POR_LETRA), salida, modelo=nombre).coste(lote)


def comprobar_experto(gastado_hoy: float, previsto: float) -> None:
    """Lanza LimiteGasto si el experto pasaría hoy de su tope diario."""
    if gastado_hoy + previsto > LIMITE_EXPERTO_DIARIO_USD:
        raise LimiteGasto(
            f"experto: gastado {gastado_hoy:.4f} + previsto {previsto:.4f} > "
            f"{LIMITE_EXPERTO_DIARIO_USD:.2f} USD"
        )


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
        Modo.CONTROL: LIMITE_CONTROL_DIARIO_USD,
        Modo.CONTROL_REPASO: LIMITE_CONTROL_REPASO_USD,
        Modo.TRADUCCIONES: LIMITE_TRADUCCIONES_USD,
    }[modo]


def diario(modo: Modo) -> bool:
    """Los modos con límite diario (lo gastado se cuenta solo en el día UTC)."""
    return modo in {Modo.HORARIO, Modo.GUERRA, Modo.CONTROL}


def comprobar(gastado: float, previsto: float, modo: Modo) -> None:
    """Lanza LimiteGasto si lo gastado más lo previsto pasa del límite del modo."""
    if gastado + previsto > limite(modo):
        raise LimiteGasto(
            f"{modo}: gastado {gastado:.4f} + previsto {previsto:.4f} > {limite(modo):.2f} USD"
        )


def dia(momento: datetime) -> str:
    return momento.strftime("%Y-%m-%d")
