"""Qué se ataca y cuándo: lo que ha cambiado de verdad en los últimos meses frente a lo habitual.

Se mira la **proporción** de cada clase, no su número: el número de impactos o de incidentes
de un mes depende de cuántas fuentes se leen y de cómo escriben, y una proporción dentro de las
mismas fuentes no. Dos ámbitos:

- **Ucrania, tipo de objetivo**: la proporción de cada tipo (residencial, energía, combustible,
  industria, ferrocarril, puerto) entre los impactos con objetivo conocido, solo de los canales
  oficiales que dan impactos en todos los trimestres desde enero de 2025 (un canal que empieza o
  deja de nombrar lugares a mitad no cambia la mezcla). Por región no: cada región la cuenta un
  solo canal y los partes nacionales dejaron de listar regiones a mitad de 2025, así que un cambio
  regional no se distingue de un cambio de cobertura.
- **Europa, tipo de incidente**: incursión, sobrevuelo o interrupción de un aeropuerto, entre todos
  los incidentes (cada uno una vez, en la fecha del suceso).

Lo reciente son los tres últimos meses cerrados; lo habitual, los doce anteriores. Ha cambiado si
lo reciente queda fuera de lo que lo habitual da 1 de cada 20 veces (binomial) y la diferencia es
de 3 puntos o más, con 30 casos recientes y 60 habituales como mínimo. Comprobación hacia delante
(desde septiembre de 2025): tras marcar un cambio, ¿el mes siguiente se parece más a lo reciente
que a lo habitual? Un ámbito se publica si, con 10 casos o más, la mejora se sostiene al
remuestrear meses.
"""

import math
from collections import Counter
from collections.abc import Iterable
from datetime import date

from esquema import Documento
from proceso.prevision import metodos
from proceso.prevision.datos import Datos

VERSION = "cambios-1.0.0"
RECIENTE = 3
HABITUAL = 12
HABITUAL_MINIMO = 9
UMBRAL = 0.05
DIFERENCIA_MINIMA = 0.03
RECIENTES_MINIMOS = 30
HABITUALES_MINIMOS = 60
CLASE_MINIMA = 5
COMPROBAR_DESDE = "2025-09"
CASOS_MINIMOS = 10
PRIMER_MES = "2025-01"
IMPACTOS_POR_TRIMESTRE = 5
TOTAL = "__total__"
Serie = dict[str, Counter[str]]


def _mes(dia: date) -> str:
    return dia.isoformat()[:7]


def meses_entre(desde: str, hasta: str) -> list[str]:
    anio, mes = int(desde[:4]), int(desde[5:7])
    resultado = []
    while f"{anio:04d}-{mes:02d}" <= hasta:
        resultado.append(f"{anio:04d}-{mes:02d}")
        mes += 1
        if mes > 12:
            anio, mes = anio + 1, 1
    return resultado


def _ultimo_cerrado(hasta: date) -> str:
    anio, mes = hasta.year, hasta.month - 1
    if mes == 0:
        anio, mes = anio - 1, 12
    return f"{anio:04d}-{mes:02d}"


def _anadir(serie: Serie, mes: str, claves: Iterable[str]) -> None:
    contador = serie.setdefault(mes, Counter())
    contador[TOTAL] += 1
    for clave in set(claves):
        contador[clave] += 1


def canales_estables(datos: Datos) -> set[str]:
    """Canales con impactos en todos los trimestres cerrados desde enero de 2025."""
    ultimo = _ultimo_cerrado(datos.hasta)
    # Trimestres completos (numerados desde enero de 2025) hasta el último mes cerrado.
    trimestre_ultimo = (int(ultimo[:4]) - 2025) * 4 + (int(ultimo[5:7]) - 1) // 3
    if int(ultimo[5:7]) % 3 != 0:
        trimestre_ultimo -= 1
    completos = set(range(trimestre_ultimo + 1))
    por_canal: dict[str, Counter[int]] = {}
    for impacto in datos.impactos:
        m = _mes(impacto.dia)
        trimestre = (int(m[:4]) - 2025) * 4 + (int(m[5:7]) - 1) // 3
        for canal in impacto.canales:
            por_canal.setdefault(canal, Counter())[trimestre] += 1
    return {
        canal for canal, cuenta in por_canal.items()
        if completos and all(cuenta.get(q, 0) >= IMPACTOS_POR_TRIMESTRE for q in completos)
    }  # fmt: skip


def series(datos: Datos) -> dict[str, Serie]:
    estables = canales_estables(datos)
    objetivo: Serie = {}
    for impacto in datos.impactos:
        if impacto.categorias and set(impacto.canales) & estables:
            _anadir(objetivo, _mes(impacto.dia), impacto.categorias)
    tipo: Serie = {}
    for incidente in datos.incidentes:
        _anadir(tipo, _mes(incidente.dia), [incidente.tipo])
    return {"ucrania_objetivo": objetivo, "europa_tipo": tipo}


def _log_binomial(k: int, n: int, p: float) -> float:
    p = min(max(p, 1e-4), 1 - 1e-4)
    return (
        math.lgamma(n + 1) - math.lgamma(k + 1) - math.lgamma(n - k + 1)
        + k * math.log(p) + (n - k) * math.log(1 - p)
    )  # fmt: skip


def _cola(k: int, n: int, p: float, arriba: bool) -> float:
    probabilidades = [math.exp(_log_binomial(j, n, p)) for j in range(n + 1)]
    return sum(probabilidades[k:]) if arriba else sum(probabilidades[: k + 1])


def cambios(serie: Serie, meses: list[str], t: int) -> list[Documento]:
    """Los cambios marcados con los meses hasta el índice t (incluido)."""
    recientes = meses[t - RECIENTE + 1 : t + 1]
    habituales = meses[max(0, t - RECIENTE + 1 - HABITUAL) : t - RECIENTE + 1]
    if len(habituales) < HABITUAL_MINIMO:
        return []
    vacio: Counter[str] = Counter()
    n = sum(serie.get(m, vacio)[TOTAL] for m in recientes)
    nh = sum(serie.get(m, vacio)[TOTAL] for m in habituales)
    if n < RECIENTES_MINIMOS or nh < HABITUALES_MINIMOS:
        return []
    claves = {c for m in recientes + habituales for c in serie.get(m, vacio) if c != TOTAL}
    resultado = []
    for clave in sorted(claves):
        k = sum(serie.get(m, vacio)[clave] for m in recientes)
        kh = sum(serie.get(m, vacio)[clave] for m in habituales)
        if k < CLASE_MINIMA and kh < CLASE_MINIMA:
            continue
        habitual = (kh + 0.5) / (nh + 1)
        reciente = k / n
        arriba = reciente > habitual
        if abs(reciente - habitual) >= DIFERENCIA_MINIMA and _cola(k, n, habitual, arriba) < UMBRAL:
            resultado.append({
                "clave": clave, "sentido": "sube" if arriba else "baja",
                "reciente": round(reciente, 3), "habitual": round(kh / nh, 3),
                "casos": k, "de": n, "casos_habituales": kh, "de_habituales": nh,
            })  # fmt: skip
    return resultado


def comprobar(serie: Serie, meses: list[str]) -> Documento:
    diferencias, bloques = [], []
    casos = sostenidos = 0
    vacio: Counter[str] = Counter()
    for t in range(len(meses) - 1):
        if meses[t] < COMPROBAR_DESDE:
            continue
        siguiente = serie.get(meses[t + 1], vacio)
        n1 = siguiente[TOTAL]
        if n1 < 10:
            continue
        for cambio in cambios(serie, meses, t):
            k1 = siguiente[cambio["clave"]]
            reciente = cambio["reciente"]
            habitual = (cambio["casos_habituales"] + 0.5) / (cambio["de_habituales"] + 1)
            diferencias.append(_log_binomial(k1, n1, reciente) - _log_binomial(k1, n1, habitual))
            bloques.append(t)
            casos += 1
            sostenidos += int((k1 / n1 > habitual) == (cambio["sentido"] == "sube"))
    mejora = metodos.mejora_remuestreada(diferencias, bloques)
    return {
        "casos": casos,
        "sostenidos": sostenidos,
        "mejora_sobre_habitual": round(mejora.media, 3),
        "mejora_cota": round(mejora.cota, 4),
        "publicable": casos >= CASOS_MINIMOS and mejora.sostenida,
    }


def calcular(datos: Datos) -> Documento | None:
    ultimo = _ultimo_cerrado(datos.hasta)
    meses = meses_entre(PRIMER_MES, ultimo)
    ambitos = []
    for ambito, serie in series(datos).items():
        comprobacion = comprobar(serie, meses)
        if not comprobacion["publicable"]:
            continue
        ambitos.append({
            "ambito": ambito, "comprobacion": comprobacion,
            "cambios": cambios(serie, meses, len(meses) - 1),
        })  # fmt: skip
    if not ambitos:
        return None
    return {
        "version": VERSION,
        "recientes": {"desde": meses[-RECIENTE], "hasta": meses[-1]},
        "ambitos": ambitos,
    }
