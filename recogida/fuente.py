"""Fuente de partes en un canal de Telegram: verificación, detector, parser y lectura común.

Cada fuente (Fuerza Aérea de Ucrania, Ministerio de Defensa ruso) se describe
con una instancia de `Fuente`. La lectura desde el cursor, la relectura de las
últimas 48 horas y la comprobación básica del canal son iguales para todas.
"""

import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta

from proceso.ataques import Perfil
from recogida.cache import CachePaginas
from recogida.descarga import Descargador
from recogida.parte import ParteLeido
from recogida.recorrido import pagina, siguiente
from recogida.telegram import Pagina, Publicacion

# Tope de páginas hacia atrás en una ejecución: 500 páginas son unas 10 000
# publicaciones, unos tres meses al ritmo medio de la Fuerza Aérea en 2026 (unas 110 al día). Si
# no basta para alcanzar el cursor, algo va mal y es mejor no leer que dejar un hueco.
MAX_PAGINAS_POR_EJECUCION = 500
# Cada ejecución vuelve a leer las publicaciones de las últimas 48 horas: los canales
# corrigen partes a lo largo de la mañana y a veces al día siguiente. Medido: en 48 horas
# la Fuerza Aérea llega a publicar unas 570 (29 páginas, 90 s a 3 s por página).
RELECTURA = timedelta(hours=48)


class CanalNoVerificado(RuntimeError):
    pass


class HuecoDemasiadoGrande(RuntimeError):
    pass


@dataclass(frozen=True)
class Fuente:
    id: str
    canal: str
    perfil: Perfil
    verificar: Callable[[Descargador, Pagina], None]
    es_parte: Callable[[str], bool]
    leer: Callable[[str, datetime], ParteLeido]
    # Para la auditoría de cobertura: qué publicaciones mencionan drones y por qué una
    # de ellas no es parte (None si no se sabe).
    palabras_dron: re.Pattern[str]
    explicar: Callable[[str], str | None]
    # Tope de tiempo de la fuente en una ejecución horaria, en segundos.
    tope_s: float


@dataclass(frozen=True)
class Lectura:
    publicaciones: tuple[Publicacion, ...]
    paginas: int


def verificar_cabecera(portada: Pagina, titulo_oficial: str) -> None:
    """Cabecera del canal, insignia de verificado y título oficial."""
    canal = portada.canal
    if canal is None:
        raise CanalNoVerificado("la página no trae la cabecera del canal")
    if not canal.verificado:
        raise CanalNoVerificado("falta la insignia de verificado")
    if titulo_oficial not in canal.titulo:
        raise CanalNoVerificado("el título no contiene el nombre oficial")


def leer_desde(
    descargador: Descargador,
    cache: CachePaginas,
    portada: Pagina,
    canal: str,
    ultimo_id: int,
    releer_desde: datetime | None = None,
    max_paginas: int = MAX_PAGINAS_POR_EJECUCION,
) -> Lectura:
    """Publicaciones posteriores a `ultimo_id` o a `releer_desde`, de la más antigua a la
    más reciente. Las ya leídas desde `releer_desde` se vuelven a leer por si se editaron."""

    def elegida(publicacion: Publicacion) -> bool:
        return publicacion.id > ultimo_id or (
            releer_desde is not None and publicacion.fecha >= releer_desde
        )

    vistas = {p.id: p for p in portada.publicaciones}
    leida, paginas = portada, 1
    while leida.publicaciones and elegida(min(leida.publicaciones, key=lambda p: p.id)):
        if paginas >= max_paginas:
            raise HuecoDemasiadoGrande(f"el cursor queda a más de {max_paginas} páginas")
        leida = pagina(descargador, cache, canal, siguiente(leida), usar_cache=False)
        paginas += 1
        vistas.update((p.id, p) for p in leida.publicaciones)
    return Lectura(tuple(sorted(filter(elegida, vistas.values()), key=lambda p: p.id)), paginas)
