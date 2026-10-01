"""Circuitos de espera: el método de la biblioteca «traffic», reproducido sin dependencias.

    Adapted from "traffic" (https://github.com/xoolive/traffic, commit aee9ba0,
    src/traffic/algorithms/navigation/holding_pattern), MIT License,
    Copyright (c) 2018 Xavier Olive.

Ventanas de 6 minutos que avanzan de 2 en 2; se descartan las que duran menos de 5. Cada
ventana se remuestrea en 30 instantes equiespaciados con el punto real más cercano, se
desenvuelve el rumbo y la entrada es el cambio de rumbo acumulado desde el primer punto. Un
escalado y una red pequeña (lineal 30→8, convolución de 10 filtros de 3, máximo de 2,
lineales 30→8→4→1 y sigmoide) dan la probabilidad de espera; una ventana es de espera si
redondea a 1. Los pesos son los de la biblioteca, sin cambios
(configuracion/espera_traffic.json, con su licencia).

Las ventanas positivas seguidas se unen en una espera. A diferencia de la biblioteca, que
une la primera y la última ventana positivas aunque haya negativas entre medias, aquí una
ventana negativa cierra la espera: dos esperas separadas son dos.

Para no evaluar la red en todo el vuelo, antes se descartan las ventanas cuyo giro
acumulado no llega a 180°: la red da menos de 0,01 con un giro uniforme de 180° (y menos
cuanto menor es el giro), así que no cambia ningún resultado.
"""

import json
import math
from collections.abc import Sequence
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any

PESOS = Path(__file__).resolve().parent.parent / "configuracion" / "espera_traffic.json"
DURACION_S = 360.0
PASO_S = 120.0
DURACION_MINIMA_S = 300.0
MUESTRAS = 30
GIRO_MINIMO = 180.0


@dataclass(frozen=True)
class Espera:
    inicio: float
    fin: float
    indice_inicio: int
    indice_fin: int


@cache
def _pesos() -> dict[str, Any]:
    datos: dict[str, Any] = json.loads(PESOS.read_text(encoding="utf-8"))
    return datos


def _lineal(pesos: list[list[float]], sesgo: list[float], x: Sequence[float]) -> list[float]:
    return [
        sum(w * v for w, v in zip(fila, x, strict=True)) + b
        for fila, b in zip(pesos, sesgo, strict=True)
    ]


def probabilidad(giros: Sequence[float]) -> float:
    """Salida de la red para 30 cambios de rumbo acumulados (el primero, cero)."""
    p = _pesos()
    x = [g * m + s for g, m, s in zip(giros, p["escala_mul"], p["escala_suma"], strict=True)]
    h = _lineal(p["capa0_pesos"], p["capa0_sesgo"], x)
    mapas = []
    for filtro, sesgo in zip(p["conv_pesos"], p["conv_sesgo"], strict=True):
        conv = [max(0.0, sum(filtro[k] * h[i + k] for k in range(3)) + sesgo) for i in range(6)]
        mapas += [max(conv[i], conv[i + 1]) for i in range(0, 6, 2)]
    h = [max(0.0, v) for v in _lineal(p["capa6_pesos"], p["capa6_sesgo"], mapas)]
    h = [max(0.0, v) for v in _lineal(p["capa8_pesos"], p["capa8_sesgo"], h)]
    z = _lineal(p["capa10_pesos"], p["capa10_sesgo"], h)[0]
    return 1.0 / (1.0 + math.exp(-z)) if z > -700 else 0.0


def desenvolver(rumbos: Sequence[float]) -> list[float]:
    """Rumbo continuo, sin el salto de 359° a 0° (como numpy.unwrap en grados)."""
    resultado: list[float] = []
    for r in rumbos:
        if not resultado:
            resultado.append(r)
            continue
        anterior = resultado[-1]
        d = (r - anterior + 180.0) % 360.0 - 180.0
        resultado.append(anterior + d)
    return resultado


def _remuestrear(tiempos: Sequence[float], valores: Sequence[float], i: int, j: int) -> list[float]:
    """30 instantes equiespaciados entre tiempos[i] y tiempos[j], con el punto más cercano."""
    inicio, fin = tiempos[i], tiempos[j]
    resultado = []
    k = i
    for n in range(MUESTRAS):
        objetivo = inicio + (fin - inicio) * n / (MUESTRAS - 1)
        while k < j and abs(tiempos[k + 1] - objetivo) <= abs(tiempos[k] - objetivo):
            k += 1
        resultado.append(valores[k])
    return resultado


def detectar(tiempos: Sequence[float], rumbos: Sequence[float]) -> list[Espera]:
    """Esperas de un tramo de vuelo con rumbo en todos sus puntos, ordenado por tiempo."""
    if len(tiempos) < 2:
        return []
    continuo = desenvolver(rumbos)
    esperas: list[Espera] = []
    actual: list[float] | None = None
    indices: list[int] = []
    inicio_ventana = tiempos[0]
    i = 0
    n = len(tiempos)
    while inicio_ventana <= tiempos[-1]:
        while i < n and tiempos[i] < inicio_ventana:
            i += 1
        if i >= n:
            break
        j = i
        while j + 1 < n and tiempos[j + 1] < inicio_ventana + DURACION_S:
            j += 1
        positiva = False
        if tiempos[j] - tiempos[i] >= DURACION_MINIMA_S:
            tramo = continuo[i : j + 1]
            if max(tramo) - min(tramo) >= GIRO_MINIMO:
                muestras = _remuestrear(tiempos, continuo, i, j)
                giros = [m - muestras[0] for m in muestras]
                positiva = round(probabilidad(giros)) == 1
        if positiva:
            if actual is None:
                actual, indices = [tiempos[i], tiempos[j]], [i, j]
            else:
                actual[1], indices[1] = tiempos[j], j
        elif actual is not None:
            esperas.append(Espera(actual[0], actual[1], indices[0], indices[1]))
            actual = None
        inicio_ventana += PASO_S
    if actual is not None:
        esperas.append(Espera(actual[0], actual[1], indices[0], indices[1]))
    return esperas
