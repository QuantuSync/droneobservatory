"""Lectura por rangos de bytes de ficheros públicos grandes (imágenes de satélite en AWS).

Las imágenes de Sentinel-2 y los gránulos de VIIRS del archivo abierto se leen a trozos con
la cabecera `Range` de HTTP: solo lo que hace falta del fichero. Cada petición lleva la
identificación del observatorio, tiene un tope de tiempo y se repite dos veces con espera
creciente si falla por la red o por un error temporal del servidor (429 o 5xx). Un 403 o un
404 no se repiten.

`FicheroRemoto` presenta un fichero remoto como un fichero de Python (lectura y
posicionamiento) con una caché de bloques, para la biblioteca de HDF5, que pide la cabecera,
los índices y los datos de cada variable a trozos.
"""

import io
import time
import urllib.error
import urllib.request
from collections import OrderedDict
from collections.abc import Callable

from recogida.descarga import AGENTE_EODI

INTENTOS = 3
ESPERA_INICIAL_S = 2.0
TOPE_PETICION_S = 60.0
CODIGOS_TEMPORALES = frozenset({429, 500, 502, 503, 504})

# Hace la petición GET con las cabeceras dadas y devuelve (código, cuerpo).
Transporte = Callable[[str, dict[str, str], float], tuple[int, bytes]]


class LecturaFallida(RuntimeError):
    pass


def transporte_urllib(url: str, cabeceras: dict[str, str], tope_s: float) -> tuple[int, bytes]:
    peticion = urllib.request.Request(url, headers=cabeceras)
    try:
        with urllib.request.urlopen(peticion, timeout=tope_s) as respuesta:
            return int(respuesta.status), respuesta.read()
    except urllib.error.HTTPError as error:
        return int(error.code), b""


class Lector:
    """Peticiones GET (enteras o por rango) con reintentos; cuenta los bytes recibidos."""

    def __init__(
        self,
        transporte: Transporte = transporte_urllib,
        dormir: Callable[[float], None] = time.sleep,
    ) -> None:
        self.transporte = transporte
        self.dormir = dormir
        self.bytes = 0
        self.peticiones = 0

    def obtener(self, url: str, inicio: int | None = None, fin: int | None = None) -> bytes:
        """El fichero entero o los bytes [inicio, fin)."""
        cabeceras = {"User-Agent": AGENTE_EODI}
        if inicio is not None and fin is not None:
            cabeceras["Range"] = f"bytes={inicio}-{fin - 1}"
        espera = ESPERA_INICIAL_S
        motivo = ""
        for intento in range(INTENTOS):
            if intento:
                self.dormir(espera)
                espera *= 2
            self.peticiones += 1
            try:
                codigo, cuerpo = self.transporte(url, cabeceras, TOPE_PETICION_S)
            except (OSError, ValueError) as error:
                motivo = type(error).__name__
                continue
            if codigo in (200, 206):
                self.bytes += len(cuerpo)
                return cuerpo
            motivo = f"HTTP {codigo}"
            if codigo not in CODIGOS_TEMPORALES:
                break
        raise LecturaFallida(f"{url.split('?')[0]}: {motivo}")

    def rango(self, url: str) -> Callable[[int, int], bytes]:
        return lambda inicio, fin: self.obtener(url, inicio, fin)


class FicheroRemoto(io.RawIOBase):
    """Fichero remoto de tamaño conocido leído por bloques, con los últimos en memoria."""

    def __init__(
        self,
        leer: Callable[[int, int], bytes],
        tamano: int,
        bloque: int = 1 << 20,
        bloques_en_memoria: int = 64,
    ) -> None:
        super().__init__()
        self._leer = leer
        self.tamano = tamano
        self.bloque = bloque
        self._maximo = bloques_en_memoria
        self._cache: OrderedDict[int, bytes] = OrderedDict()
        self._posicion = 0

    def readable(self) -> bool:
        return True

    def seekable(self) -> bool:
        return True

    def tell(self) -> int:
        return self._posicion

    def seek(self, desplazamiento: int, desde: int = io.SEEK_SET) -> int:
        base = {io.SEEK_SET: 0, io.SEEK_CUR: self._posicion, io.SEEK_END: self.tamano}[desde]
        self._posicion = max(0, base + desplazamiento)
        return self._posicion

    def _de_bloque(self, indice: int) -> bytes:
        if indice in self._cache:
            self._cache.move_to_end(indice)
            return self._cache[indice]
        inicio = indice * self.bloque
        datos = self._leer(inicio, min(self.tamano, inicio + self.bloque))
        self._cache[indice] = datos
        if len(self._cache) > self._maximo:
            self._cache.popitem(last=False)
        return datos

    def readinto(self, destino: bytearray | memoryview) -> int:  # type: ignore[override]
        vista = memoryview(destino).cast("B")
        pedidos = min(len(vista), max(0, self.tamano - self._posicion))
        hechos = 0
        while hechos < pedidos:
            indice = (self._posicion + hechos) // self.bloque
            datos = self._de_bloque(indice)
            desplazamiento = self._posicion + hechos - indice * self.bloque
            trozo = datos[desplazamiento : desplazamiento + pedidos - hechos]
            if not trozo:
                break
            vista[hechos : hechos + len(trozo)] = trozo
            hechos += len(trozo)
        self._posicion += hechos
        return hechos
