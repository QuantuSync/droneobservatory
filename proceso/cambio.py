"""Cambio visible entre la imagen de antes y la de después de un impacto (Sentinel-2).

Una pareja de antes y después solo se publica si en ella se ve el daño. Las dos imágenes se
llevan a una misma rejilla de 10 m centrada en el recorte (norte arriba) y se miden dos cosas:

- **Quemado.** La diferencia del índice normalizado de quemado, NBR = (B8A − B12) / (B8A + B12),
  entre antes y después (dNBR; positivo, quemado). La medida habitual de lo quemado.
- **Visible.** La distancia entre los colores de antes y de después (el color natural, TCI), para
  daños que no son incendio: un depósito que desaparece, un tejado hundido.

Lo que no es daño se descarta: los píxeles que la clasificación de escena (SCL) da por nube,
sombra de nube, cirro, nieve, agua o sin dato en cualquiera de las dos fechas; y el cambio de
estación o de cultivo, restando a cada medida su mediana fuera de la zona del impacto (lo que
cambia todo el recorte por igual no es el ataque).

Solo cuenta el cambio localizado donde fue el ataque: dentro de RADIO_ZONA_M del punto del
impacto (o de sus focos), y por encima de lo que cambia, en proporción, el resto del recorte.
"""

from collections import deque
from dataclasses import dataclass

import numpy as np
import numpy.typing as npt

# Píxel de la rejilla común: el del color natural.
PASO_M = 10.0
HECTAREAS_POR_PIXEL = PASO_M * PASO_M / 10_000
# Clases de la SCL que valen: zonas oscuras (2, donde caen también las quemadas), vegetación (4),
# suelo desnudo (5) y sin clasificar (7).
SCL_VALIDAS = (2, 4, 5, 7)
# Reflectancia de las bandas de 16 bits del archivo (escala y desplazamiento del catálogo).
ESCALA, DESPLAZAMIENTO = 0.0001, -0.1
# Zona del impacto: un círculo alrededor del punto del impacto o del centro de sus focos.
RADIO_ZONA_M = 800.0
# Umbrales por píxel (ya restada la mediana del resto del recorte): como mínimo un dNBR de
# quemado bajo y un oscurecimiento de 20 en la escala de 0 a 255; y, en cada pareja, por encima
# de lo que cambia el PERCENTIL_FONDO del resto del recorte.
UMBRAL_DNBR = 0.1
UMBRAL_OSCURECE = 20.0
PERCENTIL_FONDO = 97.0
# «Sombra de nube» (3) después del ataque con un NBR de quemado: es lo quemado.
SCL_SOMBRA = 3
NBR_QUEMADO = 0.0
# Un cambio de menos píxeles juntos es ruido.
PIXELES_MINIMOS = 6
# Una pareja se publica si la mancha principal que toca la zona del impacto llega a estas
# hectáreas. Fijado mirando las 33 primeras parejas una a una: las 4 con daño visible (quemado)
# dan de 11,8 a 120,8 ha; las 29 sin él, 7,4 como mucho (docs/informe_guerra_satelite.md).
UMBRAL_PRINCIPAL_HA = 10.0
# Reencuadre de una pareja que pasa: si la mancha queda lejos del centro o pequeña en el recorte,
# el recorte se centra en ella con este margen (lado = MARGEN_REENCUADRE × su extensión).
MARGEN_REENCUADRE = 2.5
LADO_MINIMO_M = 1500


@dataclass(frozen=True)
class Bandas:
    """Una fecha en la rejilla común: SCL, B8A, B12 (16 bits) y color natural (alto, ancho, 3)."""

    scl: npt.NDArray[np.uint8]
    b8a: npt.NDArray[np.uint16]
    b12: npt.NDArray[np.uint16]
    rgb: npt.NDArray[np.uint8]


@dataclass(frozen=True)
class Cambio:
    # Hectáreas que cambian dentro de la zona y las que cabría esperar por lo que cambia el
    # resto del recorte; su diferencia es el cambio del ataque.
    hectareas: float
    esperadas: float
    # Proporción de píxeles que cambian dentro de la zona y fuera.
    dentro: float
    fuera: float
    # Parte de la zona que se ve en las dos fechas.
    valida: float
    # Píxeles (fila, columna) de la zona cambiada principal, para su contorno.
    pixeles: tuple[tuple[int, int], ...]
    lado: int
    # Hectáreas del mayor grupo de píxeles cambiados que toca la zona.
    principal: float = 0.0

    @property
    def exceso(self) -> float:
        return round(self.hectareas - self.esperadas, 2)

    @property
    def pasa(self) -> bool:
        return self.principal >= UMBRAL_PRINCIPAL_HA

    @property
    def zona_hectareas(self) -> float:
        """Hectáreas de la zona marcada (los grupos que tocan la zona del impacto)."""
        return round(len(self.pixeles) * HECTAREAS_POR_PIXEL, 1)

    def contorno(self) -> list[tuple[float, float]]:
        """La envolvente de la zona marcada en fracciones de la imagen: (x, y) de 0 a 1 desde
        la esquina superior izquierda."""
        return [
            (round(c / self.lado, 4), round(f / self.lado, 4)) for f, c in envolvente(self.pixeles)
        ]

    def reencuadre(self) -> tuple[float, float, float] | None:
        """(fila, columna, lado en píxeles) del recorte centrado en la mancha si la actual queda
        lejos del centro (más de un sexto del lado) o pequeña (menos de un quinto); None si el
        encuadre ya vale."""
        if not self.pixeles:
            return None
        filas = [f for f, _ in self.pixeles]
        columnas = [c for _, c in self.pixeles]
        fila, columna = (min(filas) + max(filas) + 1) / 2, (min(columnas) + max(columnas) + 1) / 2
        extension = max(max(filas) - min(filas), max(columnas) - min(columnas)) + 1
        lejos = (
            (fila - self.lado / 2) ** 2 + (columna - self.lado / 2) ** 2
        ) ** 0.5 > self.lado / 6
        if not lejos and extension >= self.lado / 5:
            return None
        lado = max(LADO_MINIMO_M / PASO_M, min(float(self.lado), extension * MARGEN_REENCUADRE))
        return fila, columna, lado


def nbr(b8a: npt.NDArray[np.uint16], b12: npt.NDArray[np.uint16]) -> npt.NDArray[np.float64]:
    nir = b8a.astype(np.float64) * ESCALA + DESPLAZAMIENTO
    swir = b12.astype(np.float64) * ESCALA + DESPLAZAMIENTO
    suma = nir + swir
    resultado: npt.NDArray[np.float64] = np.where(
        np.abs(suma) > 1e-6, (nir - swir) / np.where(suma == 0, 1, suma), 0.0
    )
    return resultado


def validos(scl: npt.NDArray[np.uint8]) -> npt.NDArray[np.bool_]:
    resultado: npt.NDArray[np.bool_] = np.isin(scl, SCL_VALIDAS)
    return resultado


def zona(lado: int, fila: float, columna: float, radio_px: float) -> npt.NDArray[np.bool_]:
    filas, columnas = np.mgrid[0:lado, 0:lado]
    resultado: npt.NDArray[np.bool_] = (filas + 0.5 - fila) ** 2 + (
        columnas + 0.5 - columna
    ) ** 2 <= radio_px**2
    return resultado


def _abrir(mascara: npt.NDArray[np.bool_]) -> npt.NDArray[np.bool_]:
    """Quita los píxeles sueltos: queda un píxel cambiado si al menos 3 de sus 8 vecinos lo
    están también."""
    relleno = np.pad(mascara, 1).astype(np.int8)
    vecinos = sum(
        relleno[1 + dy : relleno.shape[0] - 1 + dy, 1 + dx : relleno.shape[1] - 1 + dx]
        for dy in (-1, 0, 1)
        for dx in (-1, 0, 1)
        if dy or dx
    )
    resultado: npt.NDArray[np.bool_] = mascara & (vecinos >= 3)
    return resultado


def componentes(mascara: npt.NDArray[np.bool_]) -> list[list[tuple[int, int]]]:
    """Grupos de píxeles cambiados contiguos (8 vecinos), del mayor al menor."""
    vistos = np.zeros_like(mascara)
    grupos: list[list[tuple[int, int]]] = []
    alto, ancho = mascara.shape
    for f0, c0 in zip(*np.nonzero(mascara), strict=True):
        if vistos[f0, c0]:
            continue
        grupo: list[tuple[int, int]] = []
        cola = deque([(int(f0), int(c0))])
        vistos[f0, c0] = True
        while cola:
            f, c = cola.popleft()
            grupo.append((f, c))
            for df in (-1, 0, 1):
                for dc in (-1, 0, 1):
                    nf, nc = f + df, c + dc
                    if (
                        0 <= nf < alto
                        and 0 <= nc < ancho
                        and mascara[nf, nc]
                        and not vistos[nf, nc]
                    ):
                        vistos[nf, nc] = True
                        cola.append((nf, nc))
        grupos.append(grupo)
    return sorted(grupos, key=len, reverse=True)


def luminancia(rgb: npt.NDArray[np.uint8]) -> npt.NDArray[np.float64]:
    color = rgb.astype(np.float64)
    resultado: npt.NDArray[np.float64] = (
        0.299 * color[:, :, 0] + 0.587 * color[:, :, 1] + 0.114 * color[:, :, 2]
    )
    return resultado


def medir(antes: Bandas, despues: Bandas, centro: tuple[float, float]) -> Cambio:
    """El cambio entre las dos fechas. `centro` es (fila, columna) del impacto en la rejilla."""
    lado = antes.scl.shape[0]
    nbr_antes = nbr(antes.b8a, antes.b12)
    nbr_despues = nbr(despues.b8a, despues.b12)
    # Lo quemado sale a veces como «sombra de nube» en la clasificación de después: vale si su
    # índice de quemado lo dice.
    quemado_oscuro = (despues.scl == SCL_SOMBRA) & (nbr_despues < NBR_QUEMADO)
    valido = validos(antes.scl) & (validos(despues.scl) | quemado_oscuro)
    en_zona = zona(lado, centro[0], centro[1], RADIO_ZONA_M / PASO_M)
    fuera = valido & ~en_zona
    dentro = valido & en_zona
    if np.count_nonzero(fuera) < 100 or not dentro.any():
        return Cambio(0.0, 0.0, 0.0, 0.0, 0.0, (), lado)
    # Cada medida, menos lo que cambia el resto del recorte (estación, cultivo, luz).
    dnbr_crudo = nbr_antes - nbr_despues
    dnbr = dnbr_crudo - float(np.median(dnbr_crudo[fuera]))
    oscurece = luminancia(antes.rgb) - luminancia(despues.rgb)
    oscurece = oscurece - float(np.median(oscurece[fuera]))
    # Solo lo que cambia más que casi todo el resto del recorte.
    umbral_dnbr = max(UMBRAL_DNBR, float(np.percentile(dnbr[fuera], PERCENTIL_FONDO)))
    umbral_luz = max(UMBRAL_OSCURECE, float(np.percentile(oscurece[fuera], PERCENTIL_FONDO)))
    cambiado = _abrir(valido & ((dnbr > umbral_dnbr) | (oscurece > umbral_luz)))
    n_dentro = int(np.count_nonzero(cambiado & dentro))
    proporcion_fuera = float(np.count_nonzero(cambiado & fuera)) / int(np.count_nonzero(fuera))
    # La zona cambiada principal: los grupos que tocan la zona del impacto.
    grupos = [
        g
        for g in componentes(cambiado)
        if len(g) >= PIXELES_MINIMOS and any(en_zona[f, c] for f, c in g)
    ]
    pixeles = tuple(p for g in grupos[:3] for p in g)
    return Cambio(
        hectareas=round(n_dentro * HECTAREAS_POR_PIXEL, 2),
        esperadas=round(proporcion_fuera * int(np.count_nonzero(dentro)) * HECTAREAS_POR_PIXEL, 2),
        dentro=round(n_dentro / int(np.count_nonzero(dentro)), 4),
        fuera=round(proporcion_fuera, 4),
        valida=round(int(np.count_nonzero(dentro)) / int(np.count_nonzero(en_zona)), 3),
        pixeles=pixeles,
        lado=lado,
        principal=round(len(grupos[0]) * HECTAREAS_POR_PIXEL, 2) if grupos else 0.0,
    )


def envolvente(pixeles: tuple[tuple[int, int], ...]) -> list[tuple[int, int]]:
    """Envolvente convexa (fila, columna) de las esquinas de los píxeles, en sentido horario."""
    puntos = sorted(
        {(f + df, c + dc) for f, c in pixeles for df in (0, 1) for dc in (0, 1)},
        key=lambda p: (p[1], p[0]),
    )
    if len(puntos) < 3:
        return puntos

    def giro(o: tuple[int, int], a: tuple[int, int], b: tuple[int, int]) -> int:
        return (a[1] - o[1]) * (b[0] - o[0]) - (a[0] - o[0]) * (b[1] - o[1])

    abajo: list[tuple[int, int]] = []
    for p in puntos:
        while len(abajo) >= 2 and giro(abajo[-2], abajo[-1], p) <= 0:
            abajo.pop()
        abajo.append(p)
    arriba: list[tuple[int, int]] = []
    for p in reversed(puntos):
        while len(arriba) >= 2 and giro(arriba[-2], arriba[-1], p) <= 0:
            arriba.pop()
        arriba.append(p)
    return abajo[:-1] + arriba[:-1]
