"""Recorrido hacia atrás de un canal de Telegram, página a página, con caché."""

import json
import logging
import time
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from recogida.cache import CachePaginas
from recogida.descarga import Descargador
from recogida.telegram import Pagina, Publicacion, es_pagina_de_canal, leer_pagina, url_pagina

registro = logging.getLogger(__name__)

# Una línea de avance cada 100 páginas: unas 40 en todo el histórico.
AVISO_CADA_PAGINAS = 100
# Hasta 10 intentos separados 0,5 s: 5 s bastan para que acabe una lectura ajena.
REINTENTOS_GUARDAR = 10
PAUSA_GUARDAR_S = 0.5


def clave_pagina(canal: str, antes: int) -> str:
    return f"{canal}/antes-{antes}"


def pagina(
    descargador: Descargador,
    cache: CachePaginas,
    canal: str,
    antes: int | None,
    usar_cache: bool,
) -> Pagina:
    """Página del canal. La primera (sin before) cambia siempre y nunca sale de la caché."""
    if antes is not None and usar_cache:
        guardada = cache.leer(clave_pagina(canal, antes))
        if guardada is not None:
            return leer_pagina(guardada)
    html = descargador.texto(url_pagina(canal, antes), es_pagina_de_canal)
    if antes is not None:
        cache.guardar(clave_pagina(canal, antes), html)
    return leer_pagina(html)


def siguiente(pagina_leida: Pagina) -> int | None:
    """Identificador desde el que pedir la página anterior, o None si no hay más."""
    if not pagina_leida.publicaciones:
        return None
    return min(p.id for p in pagina_leida.publicaciones)


@dataclass
class Progreso:
    """Estado del recorrido del histórico, para reanudarlo si se corta."""

    inicio: int
    siguiente: int | None
    paginas: int = 0

    @classmethod
    def leer(cls, ruta: Path) -> "Progreso | None":
        if not ruta.exists():
            return None
        datos = json.loads(ruta.read_text(encoding="utf-8"))
        return cls(datos["inicio"], datos["siguiente"], datos["paginas"])

    def guardar(self, ruta: Path) -> None:
        ruta.parent.mkdir(parents=True, exist_ok=True)
        datos = {"inicio": self.inicio, "siguiente": self.siguiente, "paginas": self.paginas}
        temporal = ruta.with_suffix(".tmp")
        temporal.write_text(json.dumps(datos), encoding="utf-8")
        for intento in range(REINTENTOS_GUARDAR):
            try:
                temporal.replace(ruta)
                return
            except PermissionError:
                # En Windows otro proceso que está leyendo el fichero bloquea el
                # reemplazo un instante.
                if intento == REINTENTOS_GUARDAR - 1:
                    raise
                time.sleep(PAUSA_GUARDAR_S)


def recorrer_historico(
    descargador: Descargador,
    cache: CachePaginas,
    canal: str,
    desde: datetime,
    ruta_progreso: Path,
) -> Progreso:
    """Baja hasta la primera página anterior a `desde`, guardando el avance tras cada página."""
    progreso = Progreso.leer(ruta_progreso)
    if progreso is None:
        portada = pagina(descargador, cache, canal, None, usar_cache=False)
        inicio = max(p.id for p in portada.publicaciones) + 1
        progreso = Progreso(inicio=inicio, siguiente=inicio)
        progreso.guardar(ruta_progreso)
    while progreso.siguiente is not None:
        leida = pagina(descargador, cache, canal, progreso.siguiente, usar_cache=True)
        progreso.paginas += 1
        antigua = min((p.fecha for p in leida.publicaciones), default=None)
        progreso.siguiente = None if antigua is None or antigua < desde else siguiente(leida)
        progreso.guardar(ruta_progreso)
        if progreso.paginas % AVISO_CADA_PAGINAS == 0:
            registro.info("páginas recorridas: %d", progreso.paginas)
    return progreso


def publicaciones_en_cache(
    cache: CachePaginas, canal: str, inicio: int, desde: datetime
) -> Iterator[Publicacion]:
    """Reproduce desde la caché la cadena de páginas que empezó en `inicio`."""
    antes: int | None = inicio
    while antes is not None:
        html = cache.leer(clave_pagina(canal, antes))
        if html is None:
            raise FileNotFoundError(f"falta en la caché la página {clave_pagina(canal, antes)}")
        leida = leer_pagina(html)
        yield from (p for p in leida.publicaciones if p.fecha >= desde)
        antigua = min((p.fecha for p in leida.publicaciones), default=None)
        antes = None if antigua is None or antigua < desde else siguiente(leida)
