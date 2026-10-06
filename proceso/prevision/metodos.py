"""Métodos de la previsión y de su comprobación con el pasado.

Todo es deliberadamente sencillo y determinista (sin azar sin semilla):

- regresión logística con una penalización pequeña, para una probabilidad diaria;
- media móvil con peso que se reduce a la mitad cada cuatro semanas y una binomial negativa
  con la dispersión del propio país, para un número semanal con su margen;
- las referencias simples con que se compara: la frecuencia de siempre (todo lo anterior) y
  «mañana igual que hoy»;
- las puntuaciones: Brier (probabilidades), logaritmo de la probabilidad del resultado
  (números) y su mejora sobre la referencia, con un remuestreo por semanas para saber si la
  mejora se sostiene o es suerte.
"""

import math
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

# Remuestreo de semanas con semilla fija: la misma comprobación da siempre el mismo resultado.
SEMILLA = 20261006
REMUESTREOS = 1000
# Cota inferior con que tiene que sostenerse la mejora: el percentil 10 del remuestreo.
PERCENTIL_COTA = 10
MEDIA_MINIMA = 0.05


def ajustar_logistica(
    x: Sequence[Sequence[float]], y: Sequence[int], penalizacion: float = 1.0
) -> list[float]:
    """Pesos (el primero, el término independiente) por Newton con penalización L2."""
    matriz = np.hstack([np.ones((len(x), 1)), np.asarray(x, dtype=float)])
    objetivo = np.asarray(y, dtype=float)
    pesos = np.zeros(matriz.shape[1])
    identidad = np.diag(np.r_[0.0, np.ones(matriz.shape[1] - 1)])
    for _ in range(40):
        p = 1.0 / (1.0 + np.exp(-(matriz @ pesos)))
        gradiente = matriz.T @ (p - objetivo) + penalizacion * (identidad @ pesos)
        hessiana = (matriz.T * (p * (1 - p))) @ matriz + penalizacion * identidad
        paso = np.linalg.solve(hessiana, gradiente)
        pesos -= paso
        if float(np.max(np.abs(paso))) < 1e-8:
            break
    return [float(v) for v in pesos]


def probabilidad(pesos: Sequence[float], x: Sequence[float]) -> float:
    z = pesos[0] + sum(p * v for p, v in zip(pesos[1:], x, strict=True))
    return 1.0 / (1.0 + math.exp(-max(-30.0, min(30.0, z))))


def brier(p: Sequence[float], y: Sequence[int]) -> float:
    return float(np.mean((np.asarray(p, dtype=float) - np.asarray(y, dtype=float)) ** 2))


def area_bajo_curva(p: Sequence[float], y: Sequence[int]) -> float | None:
    """Probabilidad de que una noche con suceso tenga más riesgo que una sin él."""
    positivos = [a for a, b in zip(p, y, strict=True) if b]
    negativos = [a for a, b in zip(p, y, strict=True) if not b]
    if not positivos or not negativos:
        return None
    orden = np.argsort(np.asarray(list(p), dtype=float), kind="mergesort")
    valores = np.asarray(list(p), dtype=float)[orden]
    rangos = np.empty(len(valores))
    i = 0
    while i < len(valores):
        j = i
        while j + 1 < len(valores) and valores[j + 1] == valores[i]:
            j += 1
        rangos[i : j + 1] = (i + j) / 2 + 1
        i = j + 1
    rango_de = np.empty(len(valores))
    rango_de[orden] = rangos
    suma = float(sum(rango_de[k] for k, b in enumerate(y) if b))
    n1, n0 = len(positivos), len(negativos)
    return (suma - n1 * (n1 + 1) / 2) / (n1 * n0)


def ewma(serie: Sequence[float], semivida: float) -> float:
    """Media con pesos que se reducen a la mitad cada `semivida` pasos hacia atrás."""
    if not serie:
        return 0.0
    n = len(serie)
    pesos = [float(0.5 ** ((n - 1 - k) / semivida)) for k in range(n)]
    return float(sum(p * v for p, v in zip(pesos, serie, strict=True)) / sum(pesos))


def dispersion(serie: Sequence[float]) -> float | None:
    """Parámetro r de la binomial negativa por momentos; None si no hay más varianza que en
    una Poisson."""
    if len(serie) < 2:
        return None
    media = float(np.mean(serie))
    varianza = float(np.var(serie, ddof=1))
    if media <= 0 or varianza <= media * 1.05:
        return None
    return media * media / (varianza - media)


def log_probabilidad(k: int, media: float, r: float | None) -> float:
    media = max(MEDIA_MINIMA, media)
    if r is None:
        return k * math.log(media) - media - math.lgamma(k + 1)
    p = r / (r + media)
    return (
        math.lgamma(k + r) - math.lgamma(r) - math.lgamma(k + 1)
        + r * math.log(p) + k * math.log(1 - p)
    )  # fmt: skip


def cola_superior(k: int, media: float, r: float | None) -> float:
    """P(X ≥ k)."""
    if k <= 0:
        return 1.0
    acumulada = sum(math.exp(log_probabilidad(i, media, r)) for i in range(k))
    return max(0.0, 1.0 - acumulada)


def cuantil(q: float, media: float, r: float | None) -> int:
    acumulada = 0.0
    for k in range(10000):
        acumulada += math.exp(log_probabilidad(k, media, r))
        if acumulada >= q:
            return k
    return 10000


@dataclass(frozen=True)
class Mejora:
    """Mejora de un método sobre su referencia en una puntuación en la que más es mejor."""

    media: float
    cota: float
    casos: int

    @property
    def sostenida(self) -> bool:
        return self.cota > 0


def mejora_remuestreada(diferencias: Sequence[float], bloques: Sequence[int]) -> Mejora:
    """Media de las diferencias (método menos referencia, por caso) y su percentil 10 al
    remuestrear bloques enteros (semanas) con reemplazo."""
    if not diferencias:
        return Mejora(0.0, 0.0, 0)
    valores = np.asarray(diferencias, dtype=float)
    etiquetas = np.asarray(bloques)
    unicos = sorted(set(int(b) for b in bloques))
    por_bloque = [valores[etiquetas == b] for b in unicos]
    sumas = np.array([float(v.sum()) for v in por_bloque])
    tamanos = np.array([len(v) for v in por_bloque])
    generador = np.random.default_rng(SEMILLA)
    medias = []
    for _ in range(REMUESTREOS):
        elegidos = generador.integers(0, len(unicos), len(unicos))
        medias.append(float(sumas[elegidos].sum() / max(1, tamanos[elegidos].sum())))
    return Mejora(float(valores.mean()), float(np.percentile(medias, PERCENTIL_COTA)), len(valores))


def mejora_brier(
    p: Sequence[float], referencia: Sequence[float], y: Sequence[int], bloques: Sequence[int]
) -> tuple[float, Mejora]:
    """Mejora relativa de Brier (1 − Brier del método / Brier de la referencia) y la mejora
    absoluta por caso, remuestreada."""
    b_metodo = brier(p, y)
    b_referencia = brier(referencia, y)
    relativa = 1 - b_metodo / b_referencia if b_referencia > 0 else 0.0
    diferencias = [(r - o) ** 2 - (m - o) ** 2 for m, r, o in zip(p, referencia, y, strict=True)]
    return relativa, mejora_remuestreada(diferencias, bloques)
