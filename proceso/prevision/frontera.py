"""Esta noche en la frontera: probabilidad de que un dron de la guerra cruce o caiga en un país.

El suceso de una noche es que el país tenga al menos un incidente del grupo «frontera»
(proceso/zona.py) en esa noche. La probabilidad se calcula antes de la noche, solo con lo que
ya se sabe a esa hora:

- los drones lanzados contra Ucrania de media en las tres últimas noches (partes de la Fuerza
  Aérea de Ucrania);
- cuántas de las siete últimas noches salieron drones desde Crimea, el camino del sur;
- los incidentes de frontera del propio país en los siete días anteriores (vienen en rachas).

Comprobación con el pasado (hacia delante, sin datos futuros): desde el 1 de julio de 2025,
para cada noche se ajusta el método solo con las noches que acabaron dos días antes o más
(se reajusta el día 1 de cada mes) y se compara su probabilidad con lo que pasó. Se publica en
un país solo si mejora a las dos referencias, la frecuencia de siempre del país y «mañana igual
que hoy», en un 5 % de Brier como mínimo, y si la mejora sobre la frecuencia se sostiene al
remuestrear semanas (percentil 10 por encima de cero), con 20 noches con suceso como mínimo.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from itertools import pairwise

from esquema import Documento
from proceso.prevision import metodos
from proceso.prevision.datos import Datos, log1p

VERSION = "frontera-1.0.0"
PAISES = ("RO", "MD", "PL", "LT", "LV", "EE", "FI", "BG", "HU", "SK")
ENTRENAR_DESDE = date(2025, 1, 1)
COMPROBAR_DESDE = date(2025, 7, 1)
MEJORA_MINIMA = 0.05
NOCHES_CON_SUCESO_MINIMAS = 20
# Tramos de probabilidad del historial de aciertos.
TRAMOS = (0.0, 0.05, 0.1, 0.2, 0.4, 1.0001)
# Las de más riesgo: el cuarto de noches con la probabilidad más alta.
FRACCION_ALTO = 0.25
NOCHES_EN_LISTA = 30


@dataclass(frozen=True)
class Serie:
    """Suceso por noche (1 si hubo incidente de frontera en el país) y lo que se sabía antes."""

    pais: str
    sucesos: frozenset[date]
    datos: Datos

    def suceso(self, noche: date) -> int:
        return int(noche in self.sucesos)

    def lanzados(self, noche: date) -> float:
        hallada = self.datos.noches.get(noche)
        return hallada.lanzados if hallada else 0.0

    def factores(self, noche: date) -> dict[str, float]:
        """Lo que se sabe antes de la noche que acaba el día `noche`."""
        anoche = noche - timedelta(days=1)
        tres = [self.lanzados(anoche - timedelta(days=k)) for k in range(3)]
        crimea = sum(
            1
            for k in range(1, 8)
            if (n := self.datos.noches.get(noche - timedelta(days=k))) and n.desde_crimea
        )
        recientes = sum(1 for k in range(1, 8) if self.suceso(noche - timedelta(days=k)))
        return {
            "lanzados_anoche": self.lanzados(anoche),
            "lanzados_tres_noches": sum(tres) / 3,
            "noches_desde_crimea": float(crimea),
            "incidentes_siete_dias": float(recientes),
        }

    def x(self, noche: date) -> list[float]:
        f = self.factores(noche)
        return [
            log1p(f["lanzados_tres_noches"]),
            f["noches_desde_crimea"] / 7,
            min(f["incidentes_siete_dias"], 3.0) / 3,
        ]


def serie(datos: Datos, pais: str) -> Serie:
    sucesos = frozenset(
        i.noche for i in datos.incidentes if i.pais == pais and i.grupo == "frontera"
    )
    return Serie(pais, sucesos, datos)


def _noches(desde: date, hasta: date) -> list[date]:
    return [desde + timedelta(days=k) for k in range((hasta - desde).days + 1)]


@dataclass
class Ajuste:
    pesos: list[float]
    # Valor habitual (mediana) de cada factor en las noches del ajuste.
    habituales: list[float]
    frecuencia: float
    tras_suceso: float
    tras_nada: float


def ajustar(s: Serie, hasta: date) -> Ajuste:
    """Ajuste con las noches de ENTRENAR_DESDE a `hasta` (incluida)."""
    noches = _noches(ENTRENAR_DESDE, hasta)
    y = [s.suceso(n) for n in noches]
    x = [s.x(n) for n in noches]
    pesos = metodos.ajustar_logistica(x, y)
    habituales = [sorted(columna)[len(columna) // 2] for columna in zip(*x, strict=True)]
    tras = [(s.suceso(n - timedelta(days=1)), s.suceso(n)) for n in noches[1:]]
    con = [b for a, b in tras if a]
    sin = [b for a, b in tras if not a]
    return Ajuste(
        pesos,
        habituales,
        sum(y) / len(y),
        (sum(con) + 1) / (len(con) + 2),
        (sum(sin) + 1) / (len(sin) + 2),
    )


@dataclass(frozen=True)
class Comprobacion:
    pais: str
    noches: list[date]
    p: list[float]
    frecuencia: list[float]
    persistencia: list[float]
    y: list[int]

    def resumen(self) -> Documento:
        semanas = [n.isocalendar()[0] * 100 + n.isocalendar()[1] for n in self.noches]
        relativa_f, sostenida_f = metodos.mejora_brier(self.p, self.frecuencia, self.y, semanas)
        relativa_p, _ = metodos.mejora_brier(self.p, self.persistencia, self.y, semanas)
        auc = metodos.area_bajo_curva(self.p, self.y)
        con_suceso = sum(self.y)
        corte = sorted(self.p, reverse=True)[max(0, int(len(self.p) * FRACCION_ALTO) - 1)]
        capturadas = sum(1 for p, y in zip(self.p, self.y, strict=True) if y and p >= corte)
        tramos = []
        for inferior, superior in pairwise(TRAMOS):
            dentro = [
                (p, y) for p, y in zip(self.p, self.y, strict=True) if inferior <= p < superior
            ]
            if dentro:
                tramos.append({
                    "desde": inferior, "hasta": min(1.0, superior), "noches": len(dentro),
                    "con_dron": sum(y for _, y in dentro),
                    "prevista_media": round(sum(p for p, _ in dentro) / len(dentro), 3),
                })  # fmt: skip
        publicable = (
            con_suceso >= NOCHES_CON_SUCESO_MINIMAS
            and relativa_f >= MEJORA_MINIMA
            and relativa_p >= MEJORA_MINIMA
            and sostenida_f.sostenida
        )
        return {
            "pais": self.pais,
            "desde": self.noches[0].isoformat() if self.noches else None,
            "noches": len(self.noches),
            "noches_con_dron": con_suceso,
            "area_bajo_curva": None if auc is None else round(auc, 3),
            "mejora_sobre_frecuencia": round(relativa_f, 3),
            "mejora_sobre_persistencia": round(relativa_p, 3),
            "mejora_cota": round(sostenida_f.cota, 5),
            "con_dron_en_riesgo_alto": capturadas,
            "tramos": tramos,
            "publicable": publicable,
        }


def comprobar(s: Serie, hasta: date) -> Comprobacion:
    """Comprobación hacia delante de COMPROBAR_DESDE a `hasta` (la última noche cuyo resultado
    ya se conoce)."""
    noches, p, frecuencia, persistencia, y = [], [], [], [], []
    ajuste: Ajuste | None = None
    for noche in _noches(COMPROBAR_DESDE, hasta):
        if ajuste is None or noche.day == 1:
            ajuste = ajustar(s, noche - timedelta(days=2))
        noches.append(noche)
        p.append(metodos.probabilidad(ajuste.pesos, s.x(noche)))
        frecuencia.append(ajuste.frecuencia)
        ayer = s.suceso(noche - timedelta(days=1))
        persistencia.append(ajuste.tras_suceso if ayer else ajuste.tras_nada)
        y.append(s.suceso(noche))
    return Comprobacion(s.pais, noches, p, frecuencia, persistencia, y)


def de_cada_10(p: float) -> int:
    return max(0, min(10, round(p * 10)))


def calcular(
    datos: Datos, noche: date, conocida_hasta: date, paises: Sequence[str] = PAISES
) -> dict[str, Documento]:
    """Por país: la comprobación y, si es publicable, la probabilidad de la noche que acaba el
    día `noche` con lo que la explica. `conocida_hasta`: la última noche con resultado ya
    conocido (las noticias de un dron caído llegan con días de retraso)."""
    resultado: dict[str, Documento] = {}
    for pais in paises:
        s = serie(datos, pais)
        comprobacion = comprobar(s, conocida_hasta)
        resumen = comprobacion.resumen()
        documento: Documento = {"comprobacion": resumen}
        if resumen["publicable"]:
            ajuste = ajustar(s, noche - timedelta(days=2))
            p = metodos.probabilidad(ajuste.pesos, s.x(noche))
            documento |= {
                "probabilidad": round(p, 3),
                "de_cada_10": de_cada_10(p),
                "frecuencia_de_siempre": round(ajuste.frecuencia, 3),
                "factores": {k: round(v, 1) for k, v in s.factores(noche).items()},
                "efectos": _efectos(ajuste, s.x(noche)),
                "ultimas": [
                    {"noche": n.isoformat(), "probabilidad": round(q, 3), "con_dron": bool(o)}
                    for n, q, o in list(
                        zip(comprobacion.noches, comprobacion.p, comprobacion.y, strict=True)
                    )[-NOCHES_EN_LISTA:]
                ],
            }
        resultado[pais] = documento
    return resultado


NOMBRES_FACTORES = (
    "lanzados_tres_noches",
    "noches_desde_crimea",
    "incidentes_siete_dias",
)


def _efectos(ajuste: Ajuste, x: Sequence[float]) -> dict[str, str]:
    """Si cada factor sube o baja hoy el riesgo frente a su valor habitual: «sube», «baja» o
    «nada» (si cambia la probabilidad en menos de un 10 % relativo)."""
    efectos = {}
    for nombre, peso, valor, habitual in zip(
        NOMBRES_FACTORES, ajuste.pesos[1:], x, ajuste.habituales, strict=True
    ):
        aporte = peso * (valor - habitual)
        efectos[nombre] = "sube" if aporte > 0.1 else "baja" if aporte < -0.1 else "nada"
    return efectos


def resultado_noche(datos: Datos, pais: str, noche: date) -> int:
    return int(
        any(i.noche == noche and i.pais == pais and i.grupo == "frontera" for i in datos.incidentes)
    )
