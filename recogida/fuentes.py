"""Fuentes de partes que se recogen, en el orden en que se leen."""

from recogida import fuerza_aerea
from recogida.fuente import Fuente

FUENTES: tuple[Fuente, ...] = (fuerza_aerea.FUENTE,)
POR_ID = {fuente.id: fuente for fuente in FUENTES}
