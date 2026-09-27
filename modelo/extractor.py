"""Extractor: convierte el texto de una nota en afirmaciones sobre campos del incidente.

La interfaz registra los tokens de entrada y salida de cada llamada. Hay una
implementación nula para tests, un envoltorio con caché en disco y la
implementación remota queda como interfaz sin implementar.
"""

import hashlib
import json
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class AfirmacionExtraida:
    campo: str
    valor: Any
    confianza: float


@dataclass(frozen=True)
class ResultadoExtraccion:
    afirmaciones: tuple[AfirmacionExtraida, ...]
    tokens_entrada: int
    tokens_salida: int


@dataclass
class RegistroTokens:
    """Consumo acumulado. Los aciertos de caché no consumen tokens."""

    llamadas: int = 0
    tokens_entrada: int = 0
    tokens_salida: int = 0
    aciertos_cache: int = 0

    def anotar(self, resultado: ResultadoExtraccion) -> None:
        self.llamadas += 1
        self.tokens_entrada += resultado.tokens_entrada
        self.tokens_salida += resultado.tokens_salida


class Extractor(ABC):
    def __init__(self) -> None:
        self.registro = RegistroTokens()

    @property
    @abstractmethod
    def version(self) -> str:
        """Versión de la lógica de extracción; forma parte de la clave de caché."""

    @abstractmethod
    def _extraer(self, texto: str) -> ResultadoExtraccion: ...

    def extraer(self, texto: str) -> ResultadoExtraccion:
        resultado = self._extraer(texto)
        self.registro.anotar(resultado)
        return resultado


class ExtractorNulo(Extractor):
    """No extrae nada. Para tests."""

    @property
    def version(self) -> str:
        return "nulo"

    def _extraer(self, texto: str) -> ResultadoExtraccion:
        return ResultadoExtraccion(afirmaciones=(), tokens_entrada=0, tokens_salida=0)


class ExtractorRemoto(Extractor):
    """Extractor real basado en un modelo de lenguaje. Pendiente de implementar."""

    def __init__(self, version: str) -> None:
        super().__init__()
        self._version = version

    @property
    def version(self) -> str:
        return self._version

    def _extraer(self, texto: str) -> ResultadoExtraccion:
        raise NotImplementedError("el extractor remoto aún no está implementado")


def huella(texto: str) -> str:
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


def clave_cache(texto: str, version: str) -> str:
    return huella(f"{version}\n{huella(texto)}")


class ExtractorConCache(Extractor):
    """Envuelve otro extractor y guarda cada resultado en disco.

    La clave combina la huella del texto de entrada y la versión de la lógica:
    cambiar la versión invalida la caché sin borrarla.
    """

    def __init__(self, interno: Extractor, directorio: Path) -> None:
        super().__init__()
        self.interno = interno
        self.directorio = directorio

    @property
    def version(self) -> str:
        return self.interno.version

    def _ruta(self, texto: str) -> Path:
        return self.directorio / f"{clave_cache(texto, self.version)}.json"

    def _extraer(self, texto: str) -> ResultadoExtraccion:
        return self.interno.extraer(texto)

    def extraer(self, texto: str) -> ResultadoExtraccion:
        ruta = self._ruta(texto)
        if ruta.exists():
            self.registro.aciertos_cache += 1
            return _leer(ruta)
        resultado = super().extraer(texto)
        self.directorio.mkdir(parents=True, exist_ok=True)
        ruta.write_text(json.dumps(asdict(resultado), ensure_ascii=False), encoding="utf-8")
        return resultado


def _leer(ruta: Path) -> ResultadoExtraccion:
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    return ResultadoExtraccion(
        afirmaciones=tuple(AfirmacionExtraida(**a) for a in datos["afirmaciones"]),
        tokens_entrada=datos["tokens_entrada"],
        tokens_salida=datos["tokens_salida"],
    )
