"""Descarga a través del lector delegado de la web (api/lector.ts, docs/lector_delegado.md).

Algunas fuentes oficiales no dejan entrar a la dirección del servidor de la recogida. Las marcadas
con "delegada": true en configuracion/fuentes_oficiales.json se piden al lector de la web, que las
descarga desde Vercel y devuelve la página tal cual, con el código de la fuente. Es solo otro
transporte del descargador: la pausa por sitio, los reintentos, el tope diario y la comprobación
de que la página es la esperada son los mismos de siempre (recogida/descarga.py).

Las respuestas del lector llevan X-Lector: «origen» (lo que dio la fuente) o «propio» (el lector
no la pudo pedir). Un «propio» de red (504) o una respuesta sin esa cabecera cuentan como un error
de red, que se reintenta; uno de rechazo (400, 403) es un fallo de la fuente; el 429 del tope por
minuto se reintenta como cualquier 429.
"""

import os
from urllib.parse import urlencode

from recogida.descarga import Respuesta, Transporte, transporte_urllib

LECTOR = "https://droneobservatory.eu/api/lector"
# Otra dirección del lector (una vista previa, en un ensayo) y la clave de acceso de las vistas
# previas protegidas, si hace falta. En producción no se usa ninguna de las dos.
ENTORNO_URL = "EODI_LECTOR_URL"
ENTORNO_CLAVE = "EODI_LECTOR_BYPASS"
CODIGOS_DE_RED = frozenset({502, 504})


class LectorSinRespuesta(OSError):
    """El lector delegado no llegó a la fuente o no respondió como lector."""


def transporte_delegado(
    fuente: str,
    transporte: Transporte = transporte_urllib,
    lector: str | None = None,
    clave: str | None = None,
) -> Transporte:
    """Un transporte que pide cada dirección de `fuente` al lector delegado."""
    base = lector or os.environ.get(ENTORNO_URL) or LECTOR
    clave = clave if clave is not None else os.environ.get(ENTORNO_CLAVE, "")

    def pedir(url: str, cabeceras: dict[str, str], limite_s: float) -> Respuesta:
        propias = dict(cabeceras)
        if clave:
            propias["x-vercel-protection-bypass"] = clave
        direccion = f"{base}?{urlencode({'fuente': fuente, 'url': url})}"
        codigo, respuesta, cuerpo = transporte(direccion, propias, limite_s)
        lector_dice = {k.lower(): v for k, v in respuesta.items()}.get("x-lector")
        if lector_dice == "origen":
            return codigo, respuesta, cuerpo
        if lector_dice is None or codigo in CODIGOS_DE_RED:
            raise LectorSinRespuesta(f"lector delegado: código {codigo}")
        return codigo, respuesta, cuerpo

    return pedir
