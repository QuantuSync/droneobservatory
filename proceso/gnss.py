"""Interferencia GNSS: proporción de aeronaves con calidad de posición degradada por celda.

Cada posición ADS-B lleva su integridad (NIC) y su precisión (NACp). Una aeronave tiene la
posición degradada en una celda y una hora si alguna de sus posiciones ADS-B allí trae NIC
menor que 7 o NACp menor que 8: son los mínimos que exige la norma de ADS-B Out de la FAA
(14 CFR 91.227: NACp ≥ 8, NIC ≥ 7), el umbral NIC < 7 del estudio de Liu, Lo y Walter
(ION ITM 2022) y el que usa el mapa de gods-eye-view. Solo cuentan posiciones ADS-B de
versión 1 o posterior (la versión 0 no transmite NACp y su NIC sale de otra escala) en el
aire.

Las celdas son hexágonos H3 de resolución 4 (unos 1770 km², 22 km de lado): la misma rejilla
que gpsjam.org, para que los resultados sean comparables. Como en gpsjam.org, se cuenta por
aeronave, no por posición, y se resta una aeronave degradada para que una sola con el equipo
averiado no tiña una celda: proporción = (degradadas − 1) / aeronaves, con 0 como mínimo.

Una celda solo cuenta con un mínimo de aeronaves: 5 en una hora y 20 en un día. Por debajo, su
proporción no se interpreta (queda vacía). Colores de gpsjam.org, que se usan como niveles:
menos del 2 % sin interferencia, del 2 al 10 % media y más del 10 % alta.
"""

from collections import Counter
from dataclasses import dataclass

import h3

from proceso.vuelos import Traza

RESOLUCION = 4
NIC_MINIMO = 7
NACP_MINIMO = 8
VERSION_MINIMA = 1
MINIMO_HORA = 5
MINIMO_DIA = 20
NIVEL_MEDIO = 0.02
NIVEL_ALTO = 0.10
# Una celda de 0,05° (unos 5 km) usa la misma celda H3 para todos sus puntos: el lado de una
# celda de resolución 4 es de 22 km, así que solo cambia algún punto pegado a un borde.
CACHE_GRADOS = 20


@dataclass(frozen=True)
class Caja:
    oeste: float
    sur: float
    este: float
    norte: float

    def contiene(self, lat: float, lon: float) -> bool:
        return self.sur <= lat <= self.norte and self.oeste <= lon <= self.este


class Celdas:
    """Celda H3 de cada punto, con caché por celdas de 0,05°."""

    def __init__(self) -> None:
        self._cache: dict[tuple[int, int], str] = {}

    def de(self, lat: float, lon: float) -> str:
        clave = (round(lat * CACHE_GRADOS), round(lon * CACHE_GRADOS))
        celda = self._cache.get(clave)
        if celda is None:
            celda = h3.latlng_to_cell(clave[0] / CACHE_GRADOS, clave[1] / CACHE_GRADOS, RESOLUCION)
            self._cache[clave] = celda
        return celda


def degradada(nic: int | None, nacp: int | None) -> bool:
    return (nic is not None and nic < NIC_MINIMO) or (nacp is not None and nacp < NACP_MINIMO)


def celdas_hora(traza: Traza, caja: Caja, celdas: Celdas) -> dict[tuple[int, str], bool]:
    """Por (hora desde 1970, celda), si la aeronave tuvo allí alguna posición degradada."""
    resultado: dict[tuple[int, str], bool] = {}
    for i in range(len(traza)):
        if traza.suelo[i] or not traza.adsb[i]:
            continue
        version, nic, nacp = traza.version[i], traza.nic[i], traza.nacp[i]
        if version is None or version < VERSION_MINIMA or nic is None or nacp is None:
            continue
        lat, lon = traza.lat[i], traza.lon[i]
        if not caja.contiene(lat, lon):
            continue
        clave = (int(traza.t[i] // 3600), celdas.de(lat, lon))
        mala = degradada(nic, nacp)
        if mala or clave not in resultado:
            resultado[clave] = resultado.get(clave, False) or mala
    return resultado


class Recuento:
    """Aeronaves distintas y degradadas por (hora, celda) y por celda en el día."""

    def __init__(self) -> None:
        self.aeronaves: Counter[tuple[int, str]] = Counter()
        self.degradadas: Counter[tuple[int, str]] = Counter()
        self.aeronaves_dia: Counter[str] = Counter()
        self.degradadas_dia: Counter[str] = Counter()

    def sumar(self, por_celda: dict[tuple[int, str], bool]) -> None:
        dia: dict[str, bool] = {}
        for clave, mala in por_celda.items():
            self.aeronaves[clave] += 1
            if mala:
                self.degradadas[clave] += 1
            dia[clave[1]] = dia.get(clave[1], False) or mala
        for celda, mala in dia.items():
            self.aeronaves_dia[celda] += 1
            if mala:
                self.degradadas_dia[celda] += 1

    def filas(self) -> list[tuple[int, str, int, int]]:
        return sorted((h, c, n, self.degradadas[(h, c)]) for (h, c), n in self.aeronaves.items())

    def filas_dia(self) -> list[tuple[str, int, int]]:
        return sorted((c, n, self.degradadas_dia[c]) for c, n in self.aeronaves_dia.items())


def proporcion(aeronaves: int, degradadas: int) -> float:
    if aeronaves <= 0:
        return 0.0
    return max(0, degradadas - 1) / aeronaves


def nivel(aeronaves: int, degradadas: int, minimo: int) -> str:
    if aeronaves < minimo:
        return "cobertura_insuficiente"
    p = proporcion(aeronaves, degradadas)
    return "alta" if p > NIVEL_ALTO else "media" if p >= NIVEL_MEDIO else "sin_interferencia"


def vecinas(celda: str) -> list[str]:
    return sorted(h3.grid_disk(celda, 1))


def celda_de(lat: float, lon: float) -> str:
    return str(h3.latlng_to_cell(lat, lon, RESOLUCION))
