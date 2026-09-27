"""Fuente: canal oficial de la Fuerza Aérea de Ucrania (vista pública web de t.me/kpszsu).

Antes de leer se comprueba que el canal sigue siendo el oficial. Si algo falla
la fuente no lee nada y el motivo queda en el registro.
"""

import re

from proceso.ataques import SENTIDO_RU_UA, Perfil
from recogida import parte
from recogida.descarga import Descargador, DescargaFallida
from recogida.fuente import CanalNoVerificado, Fuente, verificar_cabecera
from recogida.telegram import Pagina

CANAL = "kpszsu"
FUENTE_ID = "fuerza_aerea_ua"
TITULO_OFICIAL = "Повітряні Сили"
# Enlace al canal dentro de la web oficial, también codificado en una redirección.
ENLACE_CANAL = re.compile(r"t\.me(?:/|%2F)kpszsu(?![A-Za-z0-9_])", re.IGNORECASE)


def web_oficial(portada: Pagina) -> str | None:
    """Primera web externa enlazada en la descripción del canal."""
    if portada.canal is None:
        return None
    for enlace in portada.canal.enlaces_descripcion:
        if enlace.startswith("http") and "t.me/" not in enlace:
            return enlace
    return None


def verificar(descargador: Descargador, portada: Pagina) -> None:
    """Comprueba insignia, título y que la web oficial enlaza al canal."""
    verificar_cabecera(portada, TITULO_OFICIAL)
    web = web_oficial(portada)
    if web is None:
        raise CanalNoVerificado("la descripción no enlaza ninguna web oficial")
    try:
        html = descargador.texto(web, lambda texto: "<html" in texto.lower())
    except DescargaFallida as error:
        raise CanalNoVerificado(f"no se pudo leer la web oficial: {error}") from error
    if not ENLACE_CANAL.search(html):
        raise CanalNoVerificado("la web oficial ya no enlaza a t.me/kpszsu")


FUENTE = Fuente(
    id=FUENTE_ID,
    canal=CANAL,
    perfil=Perfil(
        sentido=SENTIDO_RU_UA,
        idioma="uk",
        zona=parte.KYIV,
        version_parser=parte.VERSION_PARSER,
        # La Fuerza Aérea también es parte en la guerra: sus cifras se publican marcadas.
        reivindicacion=True,
    ),
    verificar=verificar,
    es_parte=parte.es_parte,
    leer=parte.leer,
    palabras_dron=parte.PALABRAS_DRON,
    explicar=parte.motivo_no_parte,
)
