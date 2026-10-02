"""Relieve de Copernicus DEM GLO-90 para el horizonte de radar del motor de deducción.

Teselas de 1° × 1° del archivo público de AWS (`copernicus-dem-90m`, GeoTIFF optimizado para
la nube, sin clave), comprobado el 2 de octubre de 2026: unos 2 MB cada una, en coma flotante
de 32 bits, comprimidas con DEFLATE y el predictor de coma flotante. Licencia: GLO-90 es gratuito
para el público general; lo que se distribuye derivado de él lleva «produced using Copernicus
WorldDEM-90 © DLR e.V. 2010-2014 and © Airbus Defence and Space GmbH 2014-2018 provided under
COPERNICUS by the European Union and ESA; all rights reserved» (ATRIBUCION).

Solo se descargan las teselas que tocan los incidentes que se evalúan, y se guardan ya
descomprimidas (`<datos>/dem/N55E012.f32`, con su cabecera en `.json`) en el disco del
servidor: nunca en el repositorio ni en la base. Una tesela que no existe (mar abierto) se
anota para no volver a pedirla.
"""

import json
import math
import struct
import zlib
from array import array
from collections.abc import Callable
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

URL = (
    "https://copernicus-dem-90m.s3.amazonaws.com/Copernicus_DSM_COG_30_{nombre}_DEM/"
    "Copernicus_DSM_COG_30_{nombre}_DEM.tif"
)
ATRIBUCION = (
    "produced using Copernicus WorldDEM-90 © DLR e.V. 2010-2014 and © Airbus Defence and Space "
    "GmbH 2014-2018 provided under COPERNICUS by the European Union and ESA; all rights reserved"
)
SIN_TESELA = "sin_tesela.json"

Descarga = Callable[[str], bytes | None]


class TiffInvalido(ValueError):
    pass


@dataclass(frozen=True)
class Tesela:
    ancho: int
    alto: int
    lon0: float  # esquina noroeste (centro del primer píxel)
    lat0: float
    paso_lon: float
    paso_lat: float
    valores: array  # type: ignore[type-arg]

    def elevacion(self, lat: float, lon: float) -> float | None:
        """Interpolación bilineal; None fuera de la tesela o sin dato."""
        x = (lon - self.lon0) / self.paso_lon
        y = (self.lat0 - lat) / self.paso_lat
        if x < 0 or y < 0 or x > self.ancho - 1 or y > self.alto - 1:
            return None
        x0, y0 = min(int(x), self.ancho - 2), min(int(y), self.alto - 2)
        fx, fy = x - x0, y - y0
        v = self.valores
        a = v[y0 * self.ancho + x0]
        b = v[y0 * self.ancho + x0 + 1]
        c = v[(y0 + 1) * self.ancho + x0]
        d = v[(y0 + 1) * self.ancho + x0 + 1]
        if any(math.isnan(z) or z < -1000 for z in (a, b, c, d)):
            return None
        return float(a * (1 - fx) * (1 - fy) + b * fx * (1 - fy) + c * (1 - fx) * fy + d * fx * fy)


def nombre(lat: float, lon: float) -> str:
    """Nombre de la tesela que contiene el punto («N55_00_E012_00»)."""
    fila, columna = math.floor(lat), math.floor(lon)
    ns = f"N{fila:02d}" if fila >= 0 else f"S{-fila:02d}"
    eo = f"E{columna:03d}" if columna >= 0 else f"W{-columna:03d}"
    return f"{ns}_00_{eo}_00"


def _deshacer_predictor_flotante(datos: bytes, ancho: int, alto: int) -> bytes:
    """Predictor 3 de TIFF: por fila, diferencias horizontales de bytes y los bytes de cada
    valor separados en planos (el más significativo primero)."""
    salida = bytearray(len(datos))
    fila_bytes = ancho * 4
    for f in range(alto):
        fila = bytearray(datos[f * fila_bytes : (f + 1) * fila_bytes])
        acumulado = 0
        for i in range(fila_bytes):
            acumulado = (acumulado + fila[i]) & 0xFF
            fila[i] = acumulado
        base = f * fila_bytes
        for i in range(ancho):
            # Planos: byte más significativo en fila[i], luego fila[ancho + i]...
            salida[base + 4 * i] = fila[3 * ancho + i]
            salida[base + 4 * i + 1] = fila[2 * ancho + i]
            salida[base + 4 * i + 2] = fila[ancho + i]
            salida[base + 4 * i + 3] = fila[i]
    return bytes(salida)


def leer_tiff(datos: bytes) -> Tesela:
    """Lee la imagen completa (primer IFD) de un GeoTIFF de Copernicus DEM."""
    if datos[:4] != b"II*\x00":
        raise TiffInvalido("no es un TIFF little-endian")
    tamanos = {1: 1, 2: 1, 3: 2, 4: 4, 5: 8, 11: 4, 12: 8, 16: 8}
    formatos = {1: "B", 2: "c", 3: "H", 4: "I", 11: "f", 12: "d", 16: "Q"}
    desplazamiento = struct.unpack_from("<I", datos, 4)[0]
    n = struct.unpack_from("<H", datos, desplazamiento)[0]
    etiquetas: dict[int, tuple[int | float, ...]] = {}
    for i in range(n):
        pos = desplazamiento + 2 + 12 * i
        etiqueta, tipo, cuenta = struct.unpack_from("<HHI", datos, pos)
        if tipo not in formatos:
            continue
        tamano = tamanos[tipo] * cuenta
        origen = pos + 8 if tamano <= 4 else struct.unpack_from("<I", datos, pos + 8)[0]
        if tipo == 2:
            continue
        etiquetas[etiqueta] = struct.unpack_from(f"<{cuenta}{formatos[tipo]}", datos, origen)
    ancho, alto = int(etiquetas[256][0]), int(etiquetas[257][0])
    if etiquetas.get(258, (32,))[0] != 32 or etiquetas.get(339, (3,))[0] != 3:
        raise TiffInvalido("se esperaba coma flotante de 32 bits")
    compresion = int(etiquetas.get(259, (1,))[0])
    predictor = int(etiquetas.get(317, (1,))[0])
    if compresion not in (1, 8, 32946):
        raise TiffInvalido(f"compresión {compresion} no admitida")
    if 322 in etiquetas:
        tw, th = int(etiquetas[322][0]), int(etiquetas[323][0])
        offsets, cuentas = etiquetas[324], etiquetas[325]
    else:
        tw, th = ancho, int(etiquetas.get(278, (alto,))[0])
        offsets, cuentas = etiquetas[273], etiquetas[279]
    por_fila = math.ceil(ancho / tw)
    valores = array("f", bytes(4 * ancho * alto))
    for k, (o, c) in enumerate(zip(offsets, cuentas, strict=True)):
        crudo = datos[int(o) : int(o) + int(c)]
        bloque = zlib.decompress(crudo) if compresion != 1 else crudo
        if predictor == 3:
            bloque = _deshacer_predictor_flotante(bloque, tw, len(bloque) // (4 * tw))
        elif predictor != 1:
            raise TiffInvalido(f"predictor {predictor} no admitido")
        trozo = array("f")
        trozo.frombytes(bloque[: 4 * tw * (len(bloque) // (4 * tw))])
        fila0, col0 = (k // por_fila) * th, (k % por_fila) * tw
        filas = len(trozo) // tw
        for f in range(filas):
            y = fila0 + f
            if y >= alto:
                break
            n_col = min(tw, ancho - col0)
            valores[y * ancho + col0 : y * ancho + col0 + n_col] = trozo[f * tw : f * tw + n_col]
    escala = etiquetas[33550]
    punto = etiquetas[33922]
    # Punto de enlace: píxel (i, j) → (lon, lat). Píxel como área: el centro está medio paso
    # más allá de la esquina.
    paso_lon, paso_lat = float(escala[0]), float(escala[1])
    lon0 = float(punto[3]) - float(punto[0]) * paso_lon + paso_lon / 2
    lat0 = float(punto[4]) + float(punto[1]) * paso_lat - paso_lat / 2
    return Tesela(ancho, alto, lon0, lat0, paso_lon, paso_lat, valores)


class Relieve:
    """Elevaciones con las teselas en caché en disco y en memoria (las últimas)."""

    def __init__(self, directorio: Path, descargar: Descarga, maximo_descargas: int = 400):
        self.directorio = directorio
        self.descargar = descargar
        self.descargas = 0
        self.maximo_descargas = maximo_descargas
        self._cargar = lru_cache(maxsize=12)(self._tesela)

    def _sin_tesela(self) -> set[str]:
        ruta = self.directorio / SIN_TESELA
        return set(json.loads(ruta.read_text())) if ruta.exists() else set()

    def _tesela(self, clave: str) -> Tesela | None:
        cuerpo = self.directorio / f"{clave}.f32"
        cabecera = self.directorio / f"{clave}.json"
        if cuerpo.exists() and cabecera.exists():
            meta = json.loads(cabecera.read_text())
            valores = array("f")
            valores.frombytes(cuerpo.read_bytes())
            return Tesela(
                meta["ancho"],
                meta["alto"],
                meta["lon0"],
                meta["lat0"],
                meta["paso_lon"],
                meta["paso_lat"],
                valores,
            )
        if clave in self._sin_tesela() or self.descargas >= self.maximo_descargas:
            return None
        self.descargas += 1
        datos = self.descargar(URL.format(nombre=clave))
        self.directorio.mkdir(parents=True, exist_ok=True)
        if datos is None:
            (self.directorio / SIN_TESELA).write_text(
                json.dumps(sorted(self._sin_tesela() | {clave}))
            )
            return None
        tesela = leer_tiff(datos)
        cuerpo.write_bytes(tesela.valores.tobytes())
        cabecera.write_text(
            json.dumps(
                {
                    "ancho": tesela.ancho,
                    "alto": tesela.alto,
                    "lon0": tesela.lon0,
                    "lat0": tesela.lat0,
                    "paso_lon": tesela.paso_lon,
                    "paso_lat": tesela.paso_lat,
                }
            )
        )
        return tesela

    def __call__(self, lat: float, lon: float) -> float | None:
        tesela = self._cargar(nombre(lat, lon))
        return None if tesela is None else tesela.elevacion(lat, lon)

    def disco_mb(self) -> float:
        if not self.directorio.exists():
            return 0.0
        return sum(p.stat().st_size for p in self.directorio.iterdir()) / 1e6
