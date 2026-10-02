"""Reintentos por fuente que duran entre ejecuciones: tope diario y espera creciente.

Dentro de una ejecución, el descargador ya espera el doble en cada reintento
(recogida/descarga.py). Esto cubre lo que pasa entre ejecuciones, que en el servidor son
cada hora o menos:

- **Tope diario de reintentos por sitio.** Cada reintento a un sitio queda anotado en un
  fichero por sitio y día; pasado el tope, ese día cada petición a ese sitio se hace una
  sola vez. Un sitio caído o que rechaza al servidor recibe así como mucho
  TOPE_DIARIO_REINTENTOS reintentos al día entre todas las unidades.
- **Espera creciente tras fallos seguidos** (`siguiente_intento`): 1, 2, 4, 8 y 16 horas y
  después una vez al día; un rechazo (403 y parecidos, o una página de bloqueo) espera ya el
  día entero. La usan las comprobaciones que se repetían en cada ejecución
  (recogida/canales_guerra.py, la web oficial de cada canal).

El fichero de cada sitio está en el directorio de EODI_REINTENTOS_DATOS (en el servidor,
/home/eodi/datos/reintentos). Sin esa variable no hay tope entre ejecuciones (local, tests).
Si el fichero no se puede leer o escribir, la descarga sigue: el tope nunca para la recogida.
"""

import json
import os
import re
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

VARIABLE = "EODI_REINTENTOS_DATOS"
# Un sitio sano no necesita reintentos; 40 al día cubren cortes breves de una fuente que se
# lee cada hora (dos por hora) sin dejar que un sitio caído reciba cientos.
TOPE_DIARIO_REINTENTOS = 40
ESPERA_PRIMER_FALLO = timedelta(hours=1)
ESPERA_MAXIMA = timedelta(hours=24)
_NO_PERMITIDO = re.compile(r"[^A-Za-z0-9._-]")


def espera_tras_fallos(fallos_seguidos: int, rechazo: bool = False) -> timedelta:
    """Cuánto esperar antes del siguiente intento tras `fallos_seguidos` fallos."""
    if fallos_seguidos <= 0:
        return timedelta(0)
    if rechazo:
        return ESPERA_MAXIMA
    espera: timedelta = ESPERA_PRIMER_FALLO * 2 ** (fallos_seguidos - 1)
    return min(espera, ESPERA_MAXIMA)


def siguiente_intento(ahora: datetime, fallos_seguidos: int, rechazo: bool = False) -> datetime:
    return ahora + espera_tras_fallos(fallos_seguidos, rechazo)


class TopeDiario:
    """Reintentos de cada sitio en el día (UTC), anotados en un fichero por sitio."""

    def __init__(
        self,
        directorio: Path,
        tope: int = TOPE_DIARIO_REINTENTOS,
        hoy: Callable[[], date] = lambda: datetime.now(UTC).date(),
    ) -> None:
        self.directorio = directorio
        self.tope = tope
        self._hoy = hoy

    @classmethod
    def desde_entorno(cls) -> "TopeDiario | None":
        directorio = os.environ.get(VARIABLE)
        return cls(Path(directorio)) if directorio else None

    def _dia(self) -> str:
        return self._hoy().isoformat()

    def _fichero(self, sitio: str) -> Path:
        return self.directorio / f"{_NO_PERMITIDO.sub('_', sitio) or 'sitio'}.json"

    def _leer(self, sitio: str) -> dict[str, int]:
        try:
            datos = json.loads(self._fichero(sitio).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}
        if not isinstance(datos, dict):
            return {}
        return {k: v for k, v in datos.items() if isinstance(v, int)}

    def usados(self, sitio: str) -> int:
        return self._leer(sitio).get(self._dia(), 0)

    def permite(self, sitio: str) -> bool:
        return self.usados(sitio) < self.tope

    def anotar(self, sitio: str) -> None:
        """Un reintento más hoy. Solo se guarda el día en curso."""
        dia = self._dia()
        cuenta = {dia: self._leer(sitio).get(dia, 0) + 1}
        try:
            self.directorio.mkdir(parents=True, exist_ok=True)
            fichero = self._fichero(sitio)
            temporal = fichero.with_suffix(f".{os.getpid()}.tmp")
            temporal.write_text(json.dumps(cuenta), encoding="utf-8", newline="\n")
            temporal.replace(fichero)
        except OSError:
            return
