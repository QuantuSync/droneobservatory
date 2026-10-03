"""Lectura de ventanas de un GeoTIFF optimizado para la nube (COG) por peticiones de rango.

Solo se descargan la cabecera y las teselas internas que tocan la ventana pedida: un recorte de
unos kilómetros de una escena de Sentinel-2 son dos o cuatro teselas de un megabyte, nunca la
escena entera (unos 200 MB por banda). Admite lo que usan las imágenes del archivo abierto de
Sentinel-2 en AWS: TIFF clásico en orden little-endian, teselas, DEFLATE con o sin el predictor
horizontal y muestras de 8 bits (color natural de tres bandas o la clasificación de escena de una).

El paso de latitud y longitud a la cuadrícula UTM de la escena va aquí también (fórmulas de
Krüger con el elipsoide WGS 84; error de milímetros a esta escala).
"""

import math
import struct
import zlib
from collections.abc import Callable
from dataclasses import dataclass

import numpy as np
import numpy.typing as npt

# Lee los bytes [inicio, fin) del fichero remoto.
LectorRango = Callable[[int, int], bytes]

CABECERA_BYTES = 1 << 16
TIPOS = {1: ("B", 1), 3: ("H", 2), 4: ("I", 4), 12: ("d", 8), 16: ("Q", 8)}
ETIQUETA_ANCHO, ETIQUETA_ALTO = 256, 257
ETIQUETA_BITS, ETIQUETA_COMPRESION = 258, 259
ETIQUETA_MUESTRAS, ETIQUETA_PLANAR, ETIQUETA_PREDICTOR = 277, 284, 317
ETIQUETA_ANCHO_TESELA, ETIQUETA_ALTO_TESELA = 322, 323
ETIQUETA_OFFSETS, ETIQUETA_CUENTAS = 324, 325
ETIQUETA_ESCALA, ETIQUETA_ENLACE = 33550, 33922
SIN_COMPRESION, DEFLATE, DEFLATE_ANTIGUO = 1, 8, 32946


class CogInvalido(ValueError):
    pass


@dataclass(frozen=True)
class Cabecera:
    ancho: int
    alto: int
    muestras: int
    tesela_ancho: int
    tesela_alto: int
    compresion: int
    predictor: int
    offsets: tuple[int, ...]
    cuentas: tuple[int, ...]
    # Coordenadas (x, y) de la esquina superior izquierda y tamaño del píxel, en metros.
    x0: float
    y0: float
    paso_x: float
    paso_y: float


def _valores(
    datos: bytes, lector: LectorRango, tipo: int, cuenta: int, campo: int
) -> tuple[int | float, ...]:
    """Los valores de una etiqueta: dentro de la entrada si caben en 4 bytes; si no, en su
    desplazamiento, que puede caer fuera de lo leído (se pide aparte)."""
    formato, tamano = TIPOS[tipo]
    total = tamano * cuenta
    if total <= 4:
        crudo = struct.pack("<I", campo)[:total]
    else:
        crudo = datos[campo : campo + total] if campo + total <= len(datos) else b""
        if len(crudo) < total:
            crudo = lector(campo, campo + total)
    return struct.unpack(f"<{cuenta}{formato}", crudo)


def leer_cabecera(lector: LectorRango) -> Cabecera:
    """La primera imagen del fichero (la de resolución completa)."""
    datos = lector(0, CABECERA_BYTES)
    if datos[:4] != b"II*\x00":
        raise CogInvalido("se esperaba un TIFF clásico little-endian")
    posicion = struct.unpack_from("<I", datos, 4)[0]
    if posicion + 2 > len(datos):
        raise CogInvalido("la primera imagen no está en la cabecera")
    n = struct.unpack_from("<H", datos, posicion)[0]
    etiquetas: dict[int, tuple[int | float, ...]] = {}
    for i in range(n):
        etiqueta, tipo, cuenta, campo = struct.unpack_from("<HHII", datos, posicion + 2 + 12 * i)
        if tipo in TIPOS:
            etiquetas[etiqueta] = _valores(datos, lector, tipo, cuenta, campo)

    def uno(etiqueta: int, defecto: int | None = None) -> int:
        if etiqueta in etiquetas:
            return int(etiquetas[etiqueta][0])
        if defecto is None:
            raise CogInvalido(f"falta la etiqueta {etiqueta}")
        return defecto

    if any(int(b) != 8 for b in etiquetas.get(ETIQUETA_BITS, (8,))):
        raise CogInvalido("solo muestras de 8 bits")
    if uno(ETIQUETA_PLANAR, 1) != 1:
        raise CogInvalido("solo muestras intercaladas")
    if ETIQUETA_ANCHO_TESELA not in etiquetas:
        raise CogInvalido("solo imágenes en teselas")
    compresion = uno(ETIQUETA_COMPRESION, SIN_COMPRESION)
    if compresion not in (SIN_COMPRESION, DEFLATE, DEFLATE_ANTIGUO):
        raise CogInvalido(f"compresión {compresion} no admitida")
    predictor = uno(ETIQUETA_PREDICTOR, 1)
    if predictor not in (1, 2):
        raise CogInvalido(f"predictor {predictor} no admitido")
    escala, enlace = etiquetas.get(ETIQUETA_ESCALA), etiquetas.get(ETIQUETA_ENLACE)
    if escala is None or enlace is None:
        raise CogInvalido("sin georreferencia")
    paso_x, paso_y = float(escala[0]), float(escala[1])
    return Cabecera(
        ancho=uno(ETIQUETA_ANCHO),
        alto=uno(ETIQUETA_ALTO),
        muestras=uno(ETIQUETA_MUESTRAS, 1),
        tesela_ancho=uno(ETIQUETA_ANCHO_TESELA),
        tesela_alto=uno(ETIQUETA_ALTO_TESELA),
        compresion=compresion,
        predictor=predictor,
        offsets=tuple(int(v) for v in etiquetas[ETIQUETA_OFFSETS]),
        cuentas=tuple(int(v) for v in etiquetas[ETIQUETA_CUENTAS]),
        x0=float(enlace[3]) - float(enlace[0]) * paso_x,
        y0=float(enlace[4]) + float(enlace[1]) * paso_y,
        paso_x=paso_x,
        paso_y=paso_y,
    )


def decodificar_tesela(crudo: bytes, cabecera: Cabecera) -> npt.NDArray[np.uint8]:
    """Una tesela como matriz (alto, ancho, muestras)."""
    datos = crudo if cabecera.compresion == SIN_COMPRESION else zlib.decompress(crudo)
    forma = (cabecera.tesela_alto, cabecera.tesela_ancho, cabecera.muestras)
    esperado = forma[0] * forma[1] * forma[2]
    if len(datos) < esperado:
        raise CogInvalido("tesela incompleta")
    tesela = np.frombuffer(datos[:esperado], dtype=np.uint8).reshape(forma)
    if cabecera.predictor == 2:
        # Diferencias horizontales por muestra: la suma acumulada en 8 bits las deshace.
        tesela = np.cumsum(tesela, axis=1, dtype=np.uint8)
    return tesela


def leer_ventana(
    lector: LectorRango, cabecera: Cabecera, columna: int, fila: int, ancho: int, alto: int
) -> npt.NDArray[np.uint8]:
    """La ventana pedida (alto, ancho, muestras); lo que cae fuera de la imagen sale a 0, el
    valor sin dato de estas imágenes."""
    salida = np.zeros((alto, ancho, cabecera.muestras), dtype=np.uint8)
    por_fila = math.ceil(cabecera.ancho / cabecera.tesela_ancho)
    filas_teselas = math.ceil(cabecera.alto / cabecera.tesela_alto)
    tw, th = cabecera.tesela_ancho, cabecera.tesela_alto
    for ty in range(max(0, fila // th), min(filas_teselas, (fila + alto - 1) // th + 1)):
        for tx in range(max(0, columna // tw), min(por_fila, (columna + ancho - 1) // tw + 1)):
            indice = ty * por_fila + tx
            cuenta = cabecera.cuentas[indice]
            if cuenta == 0:
                continue
            inicio = cabecera.offsets[indice]
            tesela = decodificar_tesela(lector(inicio, inicio + cuenta), cabecera)
            # Intersección de la tesela con la ventana, en coordenadas de la imagen.
            x_a, y_a = max(columna, tx * tw), max(fila, ty * th)
            x_b = min(columna + ancho, (tx + 1) * tw, cabecera.ancho)
            y_b = min(fila + alto, (ty + 1) * th, cabecera.alto)
            if x_a >= x_b or y_a >= y_b:
                continue
            salida[y_a - fila : y_b - fila, x_a - columna : x_b - columna] = tesela[
                y_a - ty * th : y_b - ty * th, x_a - tx * tw : x_b - tx * tw
            ]
    return salida


def ventana_de_caja(
    cabecera: Cabecera, x_min: float, y_min: float, x_max: float, y_max: float
) -> tuple[int, int, int, int]:
    """(columna, fila, ancho, alto) de la caja en metros de la proyección de la imagen."""
    columna = math.floor((x_min - cabecera.x0) / cabecera.paso_x)
    fila = math.floor((cabecera.y0 - y_max) / cabecera.paso_y)
    ancho = math.ceil((x_max - x_min) / cabecera.paso_x)
    alto = math.ceil((y_max - y_min) / cabecera.paso_y)
    return columna, fila, ancho, alto


# --- UTM (WGS 84) ------------------------------------------------------------------------

_A = 6378137.0
_F = 1 / 298.257223563
_K0 = 0.9996


def zona_utm(epsg: int) -> tuple[int, bool]:
    """(huso, hemisferio norte) de un código EPSG UTM WGS 84 (326xx norte, 327xx sur)."""
    if 32601 <= epsg <= 32660:
        return epsg - 32600, True
    if 32701 <= epsg <= 32760:
        return epsg - 32700, False
    raise ValueError(f"EPSG {epsg} no es UTM WGS 84")


def a_utm(lat: float, lon: float, huso: int, norte: bool = True) -> tuple[float, float]:
    """Latitud y longitud en grados a (x, y) en metros del huso dado (serie de Krüger)."""
    n = _F / (2 - _F)
    a_rect = _A / (1 + n) * (1 + n**2 / 4 + n**4 / 64)
    alfa = (
        n / 2 - 2 * n**2 / 3 + 5 * n**3 / 16,
        13 * n**2 / 48 - 3 * n**3 / 5,
        61 * n**3 / 240,
    )
    fi = math.radians(lat)
    lambda0 = math.radians((huso - 1) * 6 - 180 + 3)
    dl = math.radians(lon) - lambda0
    e = 2 * math.sqrt(n) / (1 + n)
    t = math.sinh(math.atanh(math.sin(fi)) - e * math.atanh(e * math.sin(fi)))
    xi = math.atan2(t, math.cos(dl))
    eta = math.atanh(math.sin(dl) / math.sqrt(1 + t * t))
    x_xi, x_eta = xi, eta
    for j, a_j in enumerate(alfa, start=1):
        x_xi += a_j * math.sin(2 * j * xi) * math.cosh(2 * j * eta)
        x_eta += a_j * math.cos(2 * j * xi) * math.sinh(2 * j * eta)
    x = 500000.0 + _K0 * a_rect * x_eta
    y = _K0 * a_rect * x_xi + (0.0 if norte else 10000000.0)
    return x, y
