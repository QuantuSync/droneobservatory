"""La semana que viene y las rachas por país, con incidentes por semana (lunes a domingo).

Cada incidente cuenta una vez, en la semana del suceso (no la de la noticia). La serie de un
país puede ser la de todos sus incidentes o la de un grupo (frontera o interior,
proceso/zona.py).

**La semana que viene.** Lo esperado es la media de las semanas anteriores con un peso que se
reduce a la mitad cada cuatro semanas; el margen, del 10 al 90 % de una binomial negativa con la
dispersión del propio país (8 de cada 10 semanas deberían caer dentro). Se compara, semana a
semana desde julio de 2025 y solo con lo anterior, con la frecuencia de siempre del país (la
media de todas sus semanas anteriores) y con «la semana que viene igual que esta», por el
logaritmo de la probabilidad que dio cada método a lo que pasó. Se publica en un país si mejora
a las dos y la mejora sobre la frecuencia se sostiene al remuestrear semanas.

**Rachas.** Lo normal de una serie es la media de sus semanas del último año sin las cuatro
últimas. Hay racha cuando las cuatro últimas semanas suman más de lo que lo normal da 1 de cada
20 veces (binomial negativa con su dispersión), con 3 incidentes como mínimo en 2 días
distintos o más (un mismo suceso contado varias veces no hace racha). Una serie con menos de 5
incidentes en su año normal no tiene racha: con tan pocos no se puede decir qué es normal. La
racha se comprueba igual que la previsión: tras marcarla, ¿la semana siguiente se parece más a
la racha que a lo normal?
"""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, timedelta

from esquema import Documento
from proceso.prevision import metodos
from proceso.prevision.datos import Datos, Incidente

VERSION = "semana-1.0.0"
PRIMERA_SEMANA = date(2025, 1, 6)
COMPROBAR_DESDE = date(2025, 6, 30)
SEMIVIDA = 4.0
SEMANAS_MINIMAS = 20
INCIDENTES_MINIMOS = 15
MEJORA_MINIMA = 0.02  # en logaritmo natural por semana
CUANTIL_BAJO = 0.10
CUANTIL_ALTO = 0.90
SEMANAS_EN_MARCADOR = 12
# Rachas.
VENTANA_RACHA = 4
NORMAL_SEMANAS = 52
NORMAL_INCIDENTES_MINIMOS = 5
UMBRAL_RACHA = 0.05
RACHA_INCIDENTES_MINIMOS = 3
RACHA_DIAS_MINIMOS = 2
TERMINADAS_SEMANAS = 6
SEMANAS_EN_GRAFICA = 26
GRUPOS = ("todo", "frontera", "interior")


def lunes(dia: date) -> date:
    return dia - timedelta(days=dia.weekday())


@dataclass(frozen=True)
class Serie:
    pais: str
    grupo: str
    semanas: list[date]
    cuentas: list[int]
    dias: dict[date, set[date]]

    def hasta(self, k: int) -> list[int]:
        return self.cuentas[:k]


def semanas_cerradas(datos: Datos) -> list[date]:
    """Semanas completas hasta la anterior a la del día de cálculo."""
    ultima = lunes(datos.hasta) - timedelta(days=7)
    resultado = []
    actual = PRIMERA_SEMANA
    while actual <= ultima:
        resultado.append(actual)
        actual += timedelta(days=7)
    return resultado


def series(datos: Datos) -> dict[tuple[str, str], Serie]:
    semanas = semanas_cerradas(datos)
    indice = {s: k for k, s in enumerate(semanas)}
    resultado: dict[tuple[str, str], Serie] = {}
    for incidente in datos.incidentes:
        semana = lunes(incidente.dia)
        if semana not in indice:
            continue
        for grupo in ("todo", incidente.grupo):
            clave = (incidente.pais, grupo)
            if clave not in resultado:
                resultado[clave] = Serie(incidente.pais, grupo, semanas, [0] * len(semanas), {})
            serie = resultado[clave]
            serie.cuentas[indice[semana]] += 1
            serie.dias.setdefault(semana, set()).add(incidente.dia)
    return resultado


# --- La semana que viene ---------------------------------------------------------------------


def prevision(cuentas: list[int]) -> tuple[float, int, int, float | None]:
    """Lo esperado, el margen (10 % y 90 %) y la dispersión, con las semanas dadas."""
    media = max(metodos.MEDIA_MINIMA, metodos.ewma([float(c) for c in cuentas], SEMIVIDA))
    r = metodos.dispersion([float(c) for c in cuentas])
    return (
        media,
        metodos.cuantil(CUANTIL_BAJO, media, r),
        metodos.cuantil(CUANTIL_ALTO, media, r),
        r,
    )


@dataclass(frozen=True)
class Reconstruida:
    semana: date
    esperado: float
    minimo: int
    maximo: int
    real: int


def comprobar_semana(serie: Serie) -> tuple[Documento, list[Reconstruida]]:
    diferencias_f, diferencias_p, bloques = [], [], []
    reconstruidas = []
    for k, semana in enumerate(serie.semanas):
        if semana < COMPROBAR_DESDE:
            continue
        anteriores = serie.hasta(k)
        if len(anteriores) < SEMANAS_MINIMAS or sum(anteriores) < INCIDENTES_MINIMOS:
            continue
        real = serie.cuentas[k]
        media, minimo, maximo, r = prevision(anteriores)
        frecuencia = max(metodos.MEDIA_MINIMA, sum(anteriores) / len(anteriores))
        persistencia = max(metodos.MEDIA_MINIMA, float(anteriores[-1]))
        metodo = metodos.log_probabilidad(real, media, r)
        diferencias_f.append(metodo - metodos.log_probabilidad(real, frecuencia, r))
        diferencias_p.append(metodo - metodos.log_probabilidad(real, persistencia, r))
        bloques.append(k)
        reconstruidas.append(Reconstruida(semana, media, minimo, maximo, real))
    sobre_f = metodos.mejora_remuestreada(diferencias_f, bloques)
    sobre_p = metodos.mejora_remuestreada(diferencias_p, bloques)
    dentro = sum(1 for r in reconstruidas if r.minimo <= r.real <= r.maximo)
    publicable = (
        sobre_f.casos > 0
        and sobre_f.media >= MEJORA_MINIMA
        and sobre_p.media >= MEJORA_MINIMA
        and sobre_f.sostenida
    )
    resumen = {
        "pais": serie.pais,
        "grupo": serie.grupo,
        "semanas": sobre_f.casos,
        "mejora_sobre_frecuencia": round(sobre_f.media, 3),
        "mejora_sobre_persistencia": round(sobre_p.media, 3),
        "mejora_cota": round(sobre_f.cota, 4),
        "dentro_del_margen": dentro,
        "publicable": publicable,
    }
    return resumen, reconstruidas


# --- Rachas ----------------------------------------------------------------------------------


@dataclass(frozen=True)
class Normal:
    media: float
    r: float | None
    incidentes: int


def normal(serie: Serie, k: int) -> Normal | None:
    """Lo normal antes de la ventana que acaba en la semana k (incluida)."""
    inicio = max(0, k - VENTANA_RACHA + 1 - NORMAL_SEMANAS)
    base = serie.cuentas[inicio : k - VENTANA_RACHA + 1]
    if len(base) < SEMANAS_MINIMAS or sum(base) < NORMAL_INCIDENTES_MINIMOS:
        return None
    return Normal(sum(base) / len(base), metodos.dispersion([float(c) for c in base]), sum(base))


def en_racha(serie: Serie, k: int) -> bool:
    lo_normal = normal(serie, k)
    if lo_normal is None:
        return False
    ventana = serie.cuentas[k - VENTANA_RACHA + 1 : k + 1]
    total = sum(ventana)
    dias = set().union(
        *(serie.dias.get(s, set()) for s in serie.semanas[k - VENTANA_RACHA + 1 : k + 1])
    )
    if total < RACHA_INCIDENTES_MINIMOS or len(dias) < RACHA_DIAS_MINIMOS:
        return False
    r = None if lo_normal.r is None else lo_normal.r * VENTANA_RACHA
    return metodos.cola_superior(total, lo_normal.media * VENTANA_RACHA, r) < UMBRAL_RACHA


def comprobar_rachas(todas: Iterable[Serie]) -> Documento:
    """Tras marcar una racha, la semana siguiente: ¿se parece más a la racha (la media móvil)
    que a lo normal?"""
    diferencias, bloques = [], []
    siguientes, normales = 0, 0.0
    for serie in todas:
        for k in range(len(serie.semanas) - 1):
            if serie.semanas[k] < COMPROBAR_DESDE or not en_racha(serie, k):
                continue
            lo_normal = normal(serie, k)
            assert lo_normal is not None
            real = serie.cuentas[k + 1]
            media = max(
                metodos.MEDIA_MINIMA,
                metodos.ewma([float(c) for c in serie.cuentas[: k + 1]], SEMIVIDA),
            )
            r = lo_normal.r
            diferencias.append(
                metodos.log_probabilidad(real, media, r)
                - metodos.log_probabilidad(real, lo_normal.media, r)
            )
            bloques.append(k)
            siguientes += real
            normales += lo_normal.media
    mejora = metodos.mejora_remuestreada(diferencias, bloques)
    return {
        "semanas_en_racha": mejora.casos,
        "incidentes_semana_siguiente": siguientes,
        "normal_semana_siguiente": round(normales, 1),
        "mejora_sobre_normal": round(mejora.media, 3),
        "mejora_cota": round(mejora.cota, 4),
        "publicable": mejora.casos >= 10 and mejora.media >= MEJORA_MINIMA and mejora.sostenida,
    }


def racha_actual(serie: Serie) -> Documento | None:
    """La racha en curso que acaba en la última semana cerrada, si la hay."""
    k = len(serie.semanas) - 1
    if k < 0 or not en_racha(serie, k):
        return None
    inicio = k
    while inicio - 1 >= 0 and en_racha(serie, inicio - 1):
        inicio -= 1
    # Desde la primera semana con incidentes de la primera ventana marcada.
    primera = max(0, inicio - VENTANA_RACHA + 1)
    while primera < k and serie.cuentas[primera] == 0:
        primera += 1
    lo_normal = normal(serie, inicio)
    assert lo_normal is not None
    semanas = k - primera + 1
    incidentes = sum(serie.cuentas[primera : k + 1])
    ultimas = sum(serie.cuentas[k - 1 : k + 1])
    previas = sum(serie.cuentas[max(0, k - 3) : k - 1])
    if ultimas >= previas + 2 and ultimas >= 1.5 * max(previas, 1):
        tendencia = "crece"
    elif previas >= ultimas + 2 and ultimas <= previas / 1.5:
        tendencia = "se_apaga"
    else:
        tendencia = "estable"
    return {
        "pais": serie.pais,
        "grupo": serie.grupo,
        "desde": serie.semanas[primera].isoformat(),
        "hasta": (serie.semanas[k] + timedelta(days=6)).isoformat(),
        "semanas": semanas,
        "incidentes": incidentes,
        "habitual": round(lo_normal.media * semanas, 1),
        "veces": round(incidentes / max(lo_normal.media * semanas, 0.1), 1),
        "tendencia": tendencia,
    }


def racha_terminada(serie: Serie) -> Documento | None:
    """La racha que acabó en las últimas semanas (ya no está por encima de lo normal)."""
    k = len(serie.semanas) - 1
    if k < 0 or en_racha(serie, k):
        return None
    for atras in range(1, TERMINADAS_SEMANAS + 1):
        j = k - atras
        if j >= 0 and en_racha(serie, j):
            return {
                "pais": serie.pais,
                "grupo": serie.grupo,
                "hasta": (serie.semanas[j] + timedelta(days=6)).isoformat(),
            }
    return None


def grafica(serie: Serie) -> Documento | None:
    """Incidentes por semana de las últimas semanas y la banda de lo normal (del 10 al 90 %)."""
    k = len(serie.semanas) - 1
    lo_normal = normal(serie, k)
    if lo_normal is None:
        return None
    desde = max(0, k - SEMANAS_EN_GRAFICA + 1)
    return {
        "semanas": [s.isoformat() for s in serie.semanas[desde : k + 1]],
        "incidentes": serie.cuentas[desde : k + 1],
        "normal": round(lo_normal.media, 2),
        "banda": [
            metodos.cuantil(CUANTIL_BAJO, lo_normal.media, lo_normal.r),
            metodos.cuantil(CUANTIL_ALTO, lo_normal.media, lo_normal.r),
        ],
    }


def incidentes_de_semana(incidentes: Iterable[Incidente], pais: str, semana: date) -> int:
    fin = semana + timedelta(days=6)
    return sum(1 for i in incidentes if i.pais == pais and semana <= i.dia <= fin)
