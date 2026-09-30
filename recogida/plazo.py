"""Tope de tiempo de un paso de la ejecución horaria.

Cada fuente y el extractor reciben un plazo propio. El paso que lo agota se corta
y deja lo que le falta para la ejecución siguiente, sin quitar tiempo a los demás.
"""

import time
from collections.abc import Callable


class TiempoAgotado(RuntimeError):
    pass


class Plazo:
    def __init__(self, segundos: float, reloj: Callable[[], float] = time.monotonic) -> None:
        self.segundos = segundos
        self._reloj = reloj
        self._fin = reloj() + segundos

    def restante(self) -> float:
        return self._fin - self._reloj()

    def agotado(self) -> bool:
        return self.restante() <= 0

    def comprobar(self, espera_s: float = 0.0) -> None:
        """Lanza TiempoAgotado si el plazo ha pasado o pasaría durante una espera."""
        if self.restante() <= espera_s:
            raise TiempoAgotado(f"tope de {self.segundos:.0f} s agotado")
