"""Apagones vistos desde el espacio: brillo nocturno de ciudades y regiones antes y después de un
ataque contra la red eléctrica. Regla por código, sin modelo.

**Medida de una noche.** La radiancia de la banda día-noche (DNB) de VIIRS del gránulo SDR de esa
noche (`recogida/luces.py`). Para cada ciudad, los píxeles a menos de su radio (el del
nomenclátor, entre RADIO_MIN_KM y RADIO_MAX_KM) con calidad buena y el fondo, la mediana del
anillo de FONDO_KM alrededor. El brillo es la media del exceso sobre el fondo (los valores por
debajo del fondo cuentan como cero), en nW/(cm²·sr). Restar el fondo del mismo paso quita la luz
de la Luna reflejada por el suelo y el resplandor del aire, que son casi iguales dentro y fuera
de la ciudad: es la corrección por Luna de esta medida. De los pasos de la noche se queda el de
menor ángulo cenital del satélite.

**Noche válida** (`valida`): ángulo cenital del satélite de SATELITE_MAX_GRADOS o menos (más
oblicuo, la ciudad se ve por el lado y más pequeña), el Sol al menos SOL_MIN_GRADOS del cénit,
al menos COBERTURA_MINIMA del círculo de la ciudad visto con calidad buena o pobre (CALIDAD_MAXIMA),
nubosidad medida en la ciudad a la hora del paso de NUBES_MAX_PCT o menos (Open-Meteo: con nubes,
las luces se apagan o se difuminan y la Luna ilumina las nubes) y fondo por debajo de
FONDO_MAX (un fondo alto es niebla o nubes iluminadas que el modelo no ve).

**Ataque.** Referencia: la mediana del brillo de las noches válidas de las DIAS_REFERENCIA
anteriores a la noche del ataque, con al menos NOCHES_REFERENCIA_MIN. Después: las noches
válidas desde la del ataque hasta DIAS_DESPUES después de la de su fin. La pérdida de una
noche es 1 − brillo / referencia. Hay pérdida de luz si alguna noche posterior pierde
UMBRAL_PERDIDA o más y la referencia es de BRILLO_REFERENCIA_MIN o más (por debajo, una ciudad ya
apagada, el ruido de la medida es del orden de la señal). Los umbrales salen de la validación
con apagones documentados y noches de control (docs/informe_guerra_satelite.md).

**Región.** La suma del brillo de sus ciudades medidas las mismas noches, con la misma regla.

Solo sale a la web la pérdida de luz (`perdida_luz`), con su origen «medido».
"""

import math
import statistics
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

import numpy as np
import numpy.typing as npt

from esquema import Documento

VERSION = "luces/1"
RADIO_MIN_KM = 3.0
RADIO_MAX_KM = 15.0
FONDO_KM = (10.0, 25.0)  # anillo del fondo, más allá del radio de la ciudad
SATELITE_MAX_GRADOS = 55.0
# Con el Sol a menos de 12° bajo el horizonte (noches cortas del verano), el crepúsculo ilumina
# el fondo de forma desigual.
SOL_MIN_GRADOS = 102.0
# Parte del círculo de la ciudad que tiene que verse con calidad buena: menos es una ciudad
# cortada por el borde del gránulo o tapada por píxeles sin calibrar. Un píxel de la banda
# día-noche mide unos 0,56 km² (medido en la vertical; crece poco hacia el borde).
COBERTURA_MINIMA = 0.6
PIXEL_KM2 = 0.56
# Calidad del SDR (bits 0-1 de QF1): 0 buena, 1 pobre (la corrección de luz parásita de las
# noches cortas la marca así en casi todo el gránulo), 2 y 3 sin calibrar. Los bits altos
# (saturación, datos perdidos) también descartan el píxel.
CALIDAD_MAXIMA = 1
NUBES_MAX_PCT = 30.0
FONDO_MAX = 4.0
DIAS_REFERENCIA = 21
NOCHES_REFERENCIA_MIN = 3
DIAS_DESPUES = 7
UMBRAL_PERDIDA = 0.5
BRILLO_REFERENCIA_MIN = 1.0
RADIO_TIERRA_KM = 6371.0088
# Radiancia del SDR en W/(cm²·sr); la medida va en nW/(cm²·sr).
NANO = 1e9
VALOR_RELLENO = -999.0


@dataclass(frozen=True)
class Ciudad:
    id: str
    nombre: str
    region: str
    lat: float
    lon: float
    radio_km: float


def ciudad_de(documento: Mapping[str, Any]) -> Ciudad:
    return Ciudad(
        id=str(documento["id"]),
        nombre=str(documento["nombre"]),
        region=str(documento["region"]),
        lat=float(documento["lat"]),
        lon=float(documento["lon"]),
        radio_km=min(
            max(float(documento.get("radio_km", RADIO_MIN_KM)), RADIO_MIN_KM), RADIO_MAX_KM
        ),
    )


def distancias_km(
    lat: npt.NDArray[np.float32], lon: npt.NDArray[np.float32], ciudad: Ciudad
) -> npt.NDArray[np.float64]:
    """Distancia aproximada (equirrectangular, error < 0,1 % a 50 km) de cada píxel a la ciudad."""
    coseno = math.cos(math.radians(ciudad.lat))
    dy = (lat.astype(np.float64) - ciudad.lat) * (math.pi / 180) * RADIO_TIERRA_KM
    dx = (lon.astype(np.float64) - ciudad.lon) * (math.pi / 180) * RADIO_TIERRA_KM * coseno
    resultado: npt.NDArray[np.float64] = np.hypot(dx, dy)
    return resultado


def medir_ciudad(
    ciudad: Ciudad,
    lat: npt.NDArray[np.float32],
    lon: npt.NDArray[np.float32],
    radiancia: npt.NDArray[np.float32],
    calidad: npt.NDArray[np.uint8],
    cenit_satelite: npt.NDArray[np.float32],
    cenit_luna: npt.NDArray[np.float32],
    cenit_sol: npt.NDArray[np.float32],
) -> Documento | None:
    """La medida de la ciudad en un gránulo, o None si la ciudad no cae en él."""
    # Recorte grueso antes de calcular distancias en todo el gránulo.
    margen = (ciudad.radio_km + FONDO_KM[1]) / 111.0
    caja = (np.abs(lat - ciudad.lat) <= margen) & (
        np.abs(lon - ciudad.lon) <= margen / max(0.2, math.cos(math.radians(ciudad.lat)))
    )
    if not caja.any():
        return None
    filas, columnas = np.nonzero(caja)
    f0, f1, c0, c1 = filas.min(), filas.max() + 1, columnas.min(), columnas.max() + 1
    la, lo = lat[f0:f1, c0:c1], lon[f0:f1, c0:c1]
    rad = radiancia[f0:f1, c0:c1].astype(np.float64) * NANO
    buena = (calidad[f0:f1, c0:c1] <= CALIDAD_MAXIMA) & (radiancia[f0:f1, c0:c1] > VALOR_RELLENO)
    d = distancias_km(la, lo, ciudad)
    dentro = (d <= ciudad.radio_km) & buena
    anillo = (d >= ciudad.radio_km + FONDO_KM[0]) & (d <= ciudad.radio_km + FONDO_KM[1]) & buena
    n = int(np.count_nonzero(dentro))
    if n == 0 or not anillo.any():
        return None
    # La ciudad tiene que caer entera en el gránulo: si el borde la corta, no vale.
    todos = d <= ciudad.radio_km
    if int(np.count_nonzero(todos)) and (
        (f0 == 0 and todos[0].any())
        or (f1 == lat.shape[0] and todos[-1].any())
        or (c0 == 0 and todos[:, 0].any())
        or (c1 == lat.shape[1] and todos[:, -1].any())
    ):
        return None
    fondo = float(np.median(rad[anillo]))
    exceso = np.clip(rad[dentro] - fondo, 0.0, None)
    # Otras dos lecturas de la misma ciudad: la media sin recortar en cero (sin el sesgo que el
    # ruido de los píxeles oscuros da al recorte) y el núcleo iluminado (el décimo más brillante).
    sin_recorte = rad[dentro] - fondo
    nucleo = np.sort(sin_recorte)[-max(1, n // 10) :]
    return {
        "brillo": round(float(exceso.mean()), 4),
        "brillo_medio": round(float(sin_recorte.mean()), 4),
        "brillo_nucleo": round(float(nucleo.mean()), 4),
        "fondo": round(fondo, 4),
        "pixeles": n,
        "cobertura": round(n / (math.pi * ciudad.radio_km**2 / PIXEL_KM2), 3),
        "cenit_satelite": round(float(cenit_satelite[f0:f1, c0:c1][dentro].mean()), 1),
        "cenit_luna": round(float(cenit_luna[f0:f1, c0:c1][dentro].mean()), 1),
        "cenit_sol": round(float(cenit_sol[f0:f1, c0:c1][dentro].mean()), 1),
    }


def mejor(medidas: Iterable[Documento]) -> Documento | None:
    """De los pasos de una noche, el de menor ángulo cenital del satélite."""
    return min(medidas, key=lambda m: float(m["cenit_satelite"]), default=None)


def valida(medida: Documento | None) -> bool:
    if medida is None:
        return False
    nubes = medida.get("nubes_pct")
    return (
        float(medida["cenit_satelite"]) <= SATELITE_MAX_GRADOS
        and float(medida.get("cenit_sol", 180.0)) >= SOL_MIN_GRADOS
        and float(medida.get("cobertura", 0.0)) >= COBERTURA_MINIMA
        and nubes is not None
        and float(nubes) <= NUBES_MAX_PCT
        and float(medida["fondo"]) <= FONDO_MAX
    )


# --- Regla del ataque -----------------------------------------------------------------------

# Brillo por noche (fecha de la tarde, en UTC) de una ciudad o región: None si no es válida.
Serie = Mapping[date, float | None]


@dataclass(frozen=True)
class Resultado:
    referencia: float | None
    noches_referencia: int
    perdidas: dict[date, float]

    @property
    def maxima(self) -> tuple[date, float] | None:
        if not self.perdidas:
            return None
        return max(self.perdidas.items(), key=lambda par: (par[1], -par[0].toordinal()))

    @property
    def perdida_luz(self) -> bool:
        maxima = self.maxima
        return (
            self.referencia is not None
            and self.referencia >= BRILLO_REFERENCIA_MIN
            and maxima is not None
            and maxima[1] >= UMBRAL_PERDIDA
        )

    def noches_con_perdida(self) -> list[date]:
        return sorted(d for d, p in self.perdidas.items() if p >= UMBRAL_PERDIDA)


def noches_referencia(inicio: date) -> list[date]:
    """Noches de la referencia: de DIAS_REFERENCIA noches antes a la víspera de la noche del
    ataque. Una noche lleva la fecha de su tarde (UTC): el paso, hacia la 01:30 hora local, es de
    madrugada del día siguiente."""
    return [inicio - timedelta(days=k) for k in range(DIAS_REFERENCIA, 0, -1)]


def noches_despues(inicio: date, fin: date) -> list[date]:
    """Noches del ataque y posteriores: la del inicio (un ataque de tarde apaga esa misma noche;
    si el paso es anterior a los impactos, esa noche no pierde nada), las que dure el ataque y
    las DIAS_DESPUES siguientes a la de su fin."""
    return [inicio + timedelta(days=k) for k in range((fin - inicio).days + DIAS_DESPUES + 1)]


def evaluar(serie: Serie, inicio: date, fin: date) -> Resultado:
    referencia = [v for d in noches_referencia(inicio) if (v := serie.get(d)) is not None]
    if len(referencia) < NOCHES_REFERENCIA_MIN:
        return Resultado(None, len(referencia), {})
    valor = statistics.median(referencia)
    perdidas = {}
    for noche in noches_despues(inicio, fin):
        brillo = serie.get(noche)
        if brillo is not None and valor > 0:
            perdidas[noche] = round(1 - brillo / valor, 4)
    return Resultado(valor, len(referencia), perdidas)


def serie_de_region(
    series: Mapping[str, Serie], ciudades: Iterable[str], noches: Iterable[date]
) -> dict[date, float | None]:
    """Suma del brillo de las ciudades de la región. Una noche solo cuenta si están todas las
    ciudades que se miden en la región (si no, la suma bajaría por faltar una)."""
    lista = list(ciudades)
    resultado: dict[date, float | None] = {}
    for noche in noches:
        valores = [series.get(c, {}).get(noche) for c in lista]
        resultado[noche] = (
            None if any(v is None for v in valores) else sum(v for v in valores if v is not None)
        )
    return resultado


def ciudades_con_serie(
    series: Mapping[str, Serie], ciudades: Iterable[str], inicio: date
) -> list[str]:
    """Las ciudades de la región con referencia suficiente: las demás no entran en la suma."""
    return [
        c
        for c in ciudades
        if sum(1 for d in noches_referencia(inicio) if series.get(c, {}).get(d) is not None)
        >= NOCHES_REFERENCIA_MIN
    ]


def documento(zona: Documento, resultado: Resultado, inicio: date, fin: date) -> Documento | None:
    """La pérdida de luz tal como se guarda y se publica, o None si no la hay."""
    if not resultado.perdida_luz:
        return None
    maxima = resultado.maxima
    assert maxima is not None and resultado.referencia is not None
    noches = resultado.noches_con_perdida()
    referencia = noches_referencia(inicio)
    return {
        **zona,
        "perdida_pct": round(100 * maxima[1]),
        "noche": maxima[0].isoformat(),
        "noches": [d.isoformat() for d in noches],
        "referencia": {
            "desde": referencia[0].isoformat(),
            "hasta": referencia[-1].isoformat(),
            "noches": resultado.noches_referencia,
            "brillo": round(resultado.referencia, 2),
        },
        "brillo": round(resultado.referencia * (1 - maxima[1]), 2),
        "origen": "medido",
    }


def con_luces(
    ataques: Iterable[Documento], luces_por_ataque: Mapping[str, Documento]
) -> list[Documento]:
    """Copias de los ataques con su pérdida de luz (`perdida_luz`), si la tienen. Los documentos
    guardados no la llevan: vive en su propia tabla."""
    resultado = []
    for ataque in ataques:
        perdidas = luces_por_ataque.get(ataque.get("id", ""), {}).get("perdidas", [])
        resultado.append({**ataque, "perdida_luz": perdidas} if perdidas else ataque)
    return resultado
