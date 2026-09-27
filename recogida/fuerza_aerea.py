"""Fuente: canal oficial de la Fuerza Aérea de Ucrania (vista pública web de t.me/kpszsu).

Antes de leer se comprueba que el canal sigue siendo el oficial. Si algo falla
la fuente no lee nada y el motivo queda en el registro.
"""

import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta

from recogida.cache import CachePaginas
from recogida.descarga import Descargador, DescargaFallida
from recogida.recorrido import pagina, siguiente
from recogida.telegram import Pagina, Publicacion

registro = logging.getLogger(__name__)

CANAL = "kpszsu"
FUENTE_ID = "fuerza_aerea_ua"
TITULO_OFICIAL = "Повітряні Сили"
# Enlace al canal dentro de la web oficial, también codificado en una redirección.
ENLACE_CANAL = re.compile(r"t\.me(?:/|%2F)kpszsu(?![A-Za-z0-9_])", re.IGNORECASE)
# Tope de páginas hacia atrás en una ejecución: 500 páginas son unas 10 000
# publicaciones, más de medio año al ritmo del canal (unas 50 al día). Si no
# basta para alcanzar el cursor, algo va mal y es mejor no leer que dejar un hueco.
MAX_PAGINAS_POR_EJECUCION = 500
# Cada ejecución vuelve a leer las publicaciones de las últimas 48 horas: el canal
# corrige partes a lo largo de la mañana y a veces al día siguiente. A unas 50
# publicaciones al día son unas cinco páginas más por ejecución.
RELECTURA = timedelta(hours=48)


class CanalNoVerificado(RuntimeError):
    pass


class HuecoDemasiadoGrande(RuntimeError):
    pass


@dataclass(frozen=True)
class Lectura:
    publicaciones: tuple[Publicacion, ...]
    paginas: int


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
    canal = portada.canal
    if canal is None:
        raise CanalNoVerificado("la página no trae la cabecera del canal")
    if not canal.verificado:
        raise CanalNoVerificado("falta la insignia de verificado")
    if TITULO_OFICIAL not in canal.titulo:
        raise CanalNoVerificado("el título no contiene el nombre oficial")
    web = web_oficial(portada)
    if web is None:
        raise CanalNoVerificado("la descripción no enlaza ninguna web oficial")
    try:
        html = descargador.texto(web, lambda texto: "<html" in texto.lower())
    except DescargaFallida as error:
        raise CanalNoVerificado(f"no se pudo leer la web oficial: {error}") from error
    if not ENLACE_CANAL.search(html):
        raise CanalNoVerificado("la web oficial ya no enlaza a t.me/kpszsu")


def leer_desde(
    descargador: Descargador,
    cache: CachePaginas,
    portada: Pagina,
    ultimo_id: int,
    releer_desde: datetime | None = None,
    max_paginas: int = MAX_PAGINAS_POR_EJECUCION,
    canal: str = CANAL,
) -> Lectura:
    """Publicaciones posteriores a `ultimo_id` o a `releer_desde`, de la más antigua a la
    más reciente. Las ya leídas desde `releer_desde` se vuelven a leer por si se editaron."""

    def falta(leida: Pagina) -> bool:
        antigua = min(leida.publicaciones, key=lambda p: p.id)
        return antigua.id > ultimo_id or (
            releer_desde is not None and antigua.fecha >= releer_desde
        )

    vistas = {p.id: p for p in portada.publicaciones}
    leida, paginas = portada, 1
    while leida.publicaciones and falta(leida):
        if paginas >= max_paginas:
            raise HuecoDemasiadoGrande(f"el cursor queda a más de {max_paginas} páginas")
        leida = pagina(descargador, cache, canal, siguiente(leida), usar_cache=False)
        paginas += 1
        vistas.update((p.id, p) for p in leida.publicaciones)
    elegidas = (
        p
        for p in vistas.values()
        if p.id > ultimo_id or (releer_desde is not None and p.fecha >= releer_desde)
    )
    return Lectura(tuple(sorted(elegidas, key=lambda p: p.id)), paginas)
