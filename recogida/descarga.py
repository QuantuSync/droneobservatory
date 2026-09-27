"""Descarga educada y robusta.

Pausa mínima entre peticiones al mismo sitio, identificación de un navegador
real, reintentos con espera creciente y comprobación de que la respuesta es
contenido real y no una página de bloqueo servida con código 200.
"""

import time
import urllib.error
import urllib.request
from collections import Counter
from collections.abc import Callable
from urllib.parse import urlsplit

# Navegador de escritorio real y reciente: algunos sitios sirven otra página a
# clientes que no se identifican como navegador.
NAVEGADOR = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
)
CABECERAS = {
    "User-Agent": NAVEGADOR,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "uk,en;q=0.8",
}

# 3 s entre peticiones al mismo sitio: unas 20 por minuto, el ritmo de una
# persona que pasa páginas deprisa. El histórico (unas 4000 páginas) cabe en
# pocas horas y una ejecución horaria pide dos o tres páginas.
PAUSA_MINIMA_S = 3.0
# 4 reintentos con espera doble cada vez (5, 10, 20 y 40 s): 75 s en total,
# suficiente para superar un corte breve sin alargar una ejecución fallida.
REINTENTOS = 4
ESPERA_INICIAL_S = 5.0
# Tope a lo que pida el servidor en Retry-After, para no quedar colgados.
ESPERA_MAXIMA_S = 300.0
TIEMPO_LIMITE_S = 30.0
CODIGOS_REINTENTABLES = frozenset({429, 500, 502, 503, 504})
HTTP_NO_ENCONTRADO = 404

Respuesta = tuple[int, dict[str, str], bytes]
Transporte = Callable[[str, dict[str, str], float], Respuesta]
Validador = Callable[[str], bool]


class DescargaFallida(RuntimeError):
    pass


class PaginaBloqueada(DescargaFallida):
    """El servidor respondió, pero no con el contenido esperado."""


class NoEncontrado(DescargaFallida):
    """Código 404: el recurso no existe (aún)."""


def transporte_urllib(url: str, cabeceras: dict[str, str], limite_s: float) -> Respuesta:
    peticion = urllib.request.Request(url, headers=cabeceras)
    try:
        with urllib.request.urlopen(peticion, timeout=limite_s) as respuesta:
            return respuesta.status, dict(respuesta.headers), respuesta.read()
    except urllib.error.HTTPError as error:
        return error.code, dict(error.headers or {}), b""


def _retry_after(cabeceras: dict[str, str]) -> float | None:
    valor = {k.lower(): v for k, v in cabeceras.items()}.get("retry-after")
    if valor is None or not valor.strip().isdigit():
        return None
    return min(float(valor), ESPERA_MAXIMA_S)


class Descargador:
    def __init__(
        self,
        transporte: Transporte = transporte_urllib,
        dormir: Callable[[float], None] = time.sleep,
        reloj: Callable[[], float] = time.monotonic,
        pausa_minima_s: float = PAUSA_MINIMA_S,
        pausas_por_sitio: dict[str, float] | None = None,
        reintentos: int = REINTENTOS,
        espera_inicial_s: float = ESPERA_INICIAL_S,
    ) -> None:
        self._reintentos = reintentos
        self._espera_inicial_s = espera_inicial_s
        self._transporte = transporte
        self._dormir = dormir
        self._reloj = reloj
        self._pausa_minima_s = pausa_minima_s
        # Sitios que piden otra pausa (la API de GDELT, una petición cada 5 s).
        self._pausas = pausas_por_sitio or {}
        self._ultima: dict[str, float] = {}
        self.recuentos: Counter[str] = Counter()

    def _esperar_turno(self, sitio: str) -> None:
        ultima = self._ultima.get(sitio)
        if ultima is not None:
            pausa = self._pausas.get(sitio, self._pausa_minima_s)
            falta = pausa - (self._reloj() - ultima)
            if falta > 0:
                self._dormir(falta)
        self._ultima[sitio] = self._reloj()

    def texto(self, url: str, valido: Validador) -> str:
        """Descarga una página y comprueba con `valido` que es el contenido esperado."""
        cuerpo = self.contenido(url, lambda c: valido(c.decode("utf-8", errors="replace")))
        return cuerpo.decode("utf-8", errors="replace")

    def contenido(self, url: str, valido: Callable[[bytes], bool]) -> bytes:
        """Descarga en bruto y comprueba con `valido` que es el contenido esperado."""
        sitio = urlsplit(url).netloc
        motivo = ""
        for intento in range(self._reintentos + 1):
            if intento:
                self.recuentos["reintentos"] += 1
            self._esperar_turno(sitio)
            self.recuentos["peticiones"] += 1
            espera = self._espera_inicial_s * 2**intento
            try:
                codigo, cabeceras, cuerpo = self._transporte(url, CABECERAS, TIEMPO_LIMITE_S)
            except (OSError, TimeoutError) as error:
                motivo = f"error de red: {type(error).__name__}"
            else:
                if codigo == 200:
                    if valido(cuerpo):
                        return cuerpo
                    self.recuentos["bloqueos"] += 1
                    motivo = "contenido inesperado con código 200"
                elif codigo in CODIGOS_REINTENTABLES:
                    motivo = f"código {codigo}"
                    espera = max(espera, _retry_after(cabeceras) or 0)
                elif codigo == HTTP_NO_ENCONTRADO:
                    raise NoEncontrado(f"{url}: código {codigo}")
                else:
                    raise DescargaFallida(f"{url}: código {codigo}")
            if intento < self._reintentos:
                self._dormir(espera)
        self.recuentos["fallos"] += 1
        tipo = PaginaBloqueada if motivo.startswith("contenido") else DescargaFallida
        raise tipo(f"{url}: {motivo} tras {self._reintentos} reintentos")
