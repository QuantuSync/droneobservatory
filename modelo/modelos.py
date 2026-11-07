"""El modelo del servicio: desde el 7 de noviembre de 2026, uno solo para todo.

Configuración (variables de entorno, secretos en el servidor; docs/modelos.md):

- EODI_MODELO: el modelo único de todas las llamadas (Sonnet 5.5). Manda sobre las dos de abajo:
  con él, el base y el experto son el mismo modelo y nada se escala (escala()).
- EODI_MODELO_BASE y EODI_MODELO_EXPERTO: los dos modelos del 14 de octubre al 7 de noviembre de
  2026 (Haiku 5.5 para todo y Sonnet 5.5 para los casos que escalaba proceso/escalado.py). Sin
  EODI_MODELO, el base es EODI_MODELO_BASE (o EODI_EXTRACTOR_MODELO, el de antes del 14 de
  octubre) y el experto, EODI_MODELO_EXPERTO.
- EODI_EXTRACCION_HAIKU=1 (interruptor de vuelta atrás, en la configuración del servidor): solo la
  extracción de las fichas vuelve al modelo de EODI_MODELO_BASE (Haiku 5.5), con su escalado de
  antes al modelo único. Todo lo demás sigue con el modelo único.

Cada modelo tiene su tarifa (dólares por millón de tokens) y lo que admite la petición. Los
modelos nuevos no admiten temperatura ni muestreo (darían un error 400), razonan antes de
contestar y gradúan ese razonamiento con el esfuerzo; el modelo de antes admite temperatura y
no admite esfuerzo. Las peticiones se escriben una vez, con temperatura y esfuerzo, y
`adaptar` deja en cada una lo que su modelo admite.
"""

import copy
import os
from dataclasses import dataclass
from typing import Any

MILLON = 1_000_000
# La escritura en la caché cuesta 1,25 veces la entrada y la lectura, 0,1 veces, en todos.
FACTOR_ESCRITURA_CACHE = 1.25
FACTOR_LECTURA_CACHE = 0.10
# Los lotes cuestan la mitad.
DESCUENTO_LOTE = 0.5
ESFUERZOS = ("low", "medium", "high")
MUESTREO = ("temperature", "top_p", "top_k")
BASE = "base"
EXPERTO = "experto"


@dataclass(frozen=True)
class Modelo:
    """Tarifa y capacidades de un modelo, reconocido por una parte de su identificador (la
    familia y la versión: el identificador completo solo está en los secretos)."""

    prefijo: str
    entrada: float
    salida: float
    # Con más de `umbral_largo` tokens de entrada, toda la petición va a la tarifa larga.
    umbral_largo: int | None = None
    entrada_larga: float = 0.0
    salida_larga: float = 0.0
    muestreo: bool = False
    esfuerzo: bool = True
    # Segundos que se espera cada respuesta como mucho (el razonamiento alarga las respuestas).
    espera_s: float = 90.0
    # Tokens de razonamiento que se suman al máximo de salida de cada petición, por esfuerzo
    # (bajo, medio, alto): el razonamiento cuenta en el máximo y, sin este margen, la respuesta
    # se cortaría. Medido el 14 de octubre de 2026 con fichas reales: el base razona de 1.100 a
    # 4.800 tokens con esfuerzo medio; el experto, casi nada.
    margen: tuple[int, int, int] = (0, 0, 0)
    # Marcar las instrucciones para la caché del servicio. Escribirla cuesta 1,25 veces la
    # entrada y dura 5 minutos; leerla, 0,1. Compensa en los dos modelos: el base hace varias
    # llamadas seguidas con las mismas instrucciones y el experto, desde el 19 de octubre de
    # 2026, también (de 7.950 tokens de entrada, 7.460 son instrucciones fijas, y más de la
    # mitad de sus llamadas llegan a menos de 5 minutos de otra del mismo tipo).
    cache: bool = True

    def tarifa(self, tokens_entrada: int) -> tuple[float, float]:
        if self.umbral_largo is not None and tokens_entrada > self.umbral_largo:
            return self.entrada_larga, self.salida_larga
        return self.entrada, self.salida


# Tarifas de octubre de 2026 (docs/modelos.md). Un modelo que no está en la lista se trata como
# el de antes (tarifa y petición), que es lo que hacía todo el código hasta ahora.
MODELOS = (
    Modelo("haiku-4-5", 1.00, 5.00, muestreo=True, esfuerzo=False, espera_s=60.0),
    Modelo(
        "haiku-5-5",
        0.10,
        0.50,
        umbral_largo=100_000,
        entrada_larga=0.50,
        salida_larga=2.50,
        espera_s=120.0,
        margen=(3000, 8000, 12000),
    ),
    Modelo("sonnet-5-5", 2.00, 10.00, espera_s=150.0, margen=(2000, 4000, 6000)),
)
RESERVA = Modelo("", 1.00, 5.00, muestreo=True, esfuerzo=False, espera_s=60.0)


def de(identificador: str | None) -> Modelo:
    """El modelo por su identificador (vale con fecha al final); el de reserva si no se conoce."""
    texto = (identificador or "").strip()
    for modelo in MODELOS:
        if modelo.prefijo and modelo.prefijo in texto:
            return modelo
    return RESERVA


VARIABLE_UNICO = "EODI_MODELO"
VARIABLE_INTERRUPTOR = "EODI_EXTRACCION_HAIKU"


def unico() -> str:
    """El modelo único (EODI_MODELO), o vacío si no está configurado."""
    return os.environ.get(VARIABLE_UNICO, "").strip()


def base() -> str:
    """El modelo de las llamadas: el único si está; si no, el base de antes."""
    return (
        unico() or os.environ.get("EODI_MODELO_BASE") or os.environ.get("EODI_EXTRACTOR_MODELO", "")
    )


def experto() -> str:
    """El modelo que decide los casos difíciles: el único si está (el mismo que el base); si no,
    el experto de antes, o vacío."""
    return unico() or os.environ.get("EODI_MODELO_EXPERTO", "").strip()


def extraccion() -> str:
    """El modelo de la extracción de las fichas: el base, salvo con el interruptor de vuelta atrás
    (EODI_EXTRACCION_HAIKU=1), que la devuelve al modelo de EODI_MODELO_BASE."""
    if os.environ.get(VARIABLE_INTERRUPTOR, "").strip() == "1":
        return os.environ.get("EODI_MODELO_BASE", "").strip() or base()
    return base()


def familia(identificador: str | None) -> str:
    """La familia y versión de un modelo (su prefijo conocido), o el identificador tal cual."""
    texto = (identificador or "").strip()
    conocido = de(texto)
    return conocido.prefijo or texto


def escala(modelo_respuesta: str | None) -> bool:
    """Si una respuesta de `modelo_respuesta` se puede escalar: solo si hay experto y es otro
    modelo. Con un modelo único nada se escala (repetir la llamada con el mismo modelo solo
    gastaría el doble)."""
    otro = experto()
    if not otro:
        return False
    return familia(modelo_respuesta or base()) != familia(otro)


def coste(
    modelo: str | None, entrada: int, salida: int, escritura_cache: int = 0,
    lectura_cache: int = 0, lote: bool = False,
) -> float:  # fmt: skip
    """Dólares de una llamada con la tarifa del modelo que la hizo."""
    m = de(modelo or base())
    precio_entrada, precio_salida = m.tarifa(entrada + escritura_cache + lectura_cache)
    dolares = (
        entrada * precio_entrada
        + salida * precio_salida
        + escritura_cache * precio_entrada * FACTOR_ESCRITURA_CACHE
        + lectura_cache * precio_entrada * FACTOR_LECTURA_CACHE
    ) / MILLON
    return dolares * (DESCUENTO_LOTE if lote else 1)


def max_salida(modelo: str | None, base_tokens: int, esfuerzo: str | None) -> int:
    """El máximo de salida que se pide: el de la respuesta más el margen del razonamiento."""
    m = de(modelo or base())
    if not m.esfuerzo:
        return base_tokens
    esfuerzo = esfuerzo or "medium"
    nivel = ESFUERZOS.index(esfuerzo) if esfuerzo in ESFUERZOS else len(ESFUERZOS) - 1
    return base_tokens + m.margen[nivel]


def adaptar(cuerpo: dict[str, Any], modelo: str) -> dict[str, Any]:
    """La petición con lo que admite su modelo (una copia; la original no cambia).

    - Sin temperatura ni muestreo en los modelos que no lo admiten.
    - El esfuerzo (output_config.effort) solo en los que lo admiten; en los demás se quita.
    - En los que razonan, el máximo de salida lleva el margen del razonamiento.
    - Sin marcas de caché en los que no la usan.
    """
    m = de(modelo)
    nuevo = copy.deepcopy(cuerpo)
    salida = nuevo.get("output_config")
    esfuerzo = salida.get("effort") if isinstance(salida, dict) else None
    if not m.muestreo:
        for clave in MUESTREO:
            nuevo.pop(clave, None)
    if not m.esfuerzo:
        if isinstance(salida, dict):
            salida.pop("effort", None)
    elif isinstance(salida, dict) and esfuerzo is None:
        salida["effort"] = "medium"
    if not m.cache and isinstance(nuevo.get("system"), list):
        for bloque in nuevo["system"]:
            if isinstance(bloque, dict):
                bloque.pop("cache_control", None)
    if "max_tokens" in nuevo:
        nuevo["max_tokens"] = max_salida(modelo, int(nuevo["max_tokens"]), esfuerzo)
    return {"model": modelo, **nuevo}
