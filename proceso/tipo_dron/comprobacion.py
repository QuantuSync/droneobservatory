"""Comprobación de la clase probable contra los casos de respuesta conocida.

Cada caso se calcula sin él: la frecuencia de partida sale de los demás casos y sus frases van con
los nombres de modelo tapados. Se mide por grupo (las clases que ve el usuario):

- acierto: el grupo más probable es el de la respuesta;
- entre los dos primeros: el de la respuesta está entre los dos más probables;
- logaritmo de la probabilidad dada a la respuesta (más alto es mejor) y Brier;
- calibración: por tramos de la probabilidad del grupo más probable, cuántas veces acertó.

Referencia: decir siempre el grupo más frecuente de los demás casos, con la frecuencia de cada
grupo como probabilidad. Se publica si el método la mejora claramente: más aciertos y más
logaritmo por caso (la mejora mínima de configuracion/tipo_dron.json), y el percentil 10 de la
mejora al remuestrear los casos con reemplazo por encima de cero. Por grupo, se publica si tiene
los casos mínimos y su acierto mínimo. Se mide además, solo para informar, frente a «el grupo
más frecuente de su zona».
"""

import math
import random
from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

from proceso.deduccion.catalogo import Catalogo
from proceso.tipo_dron import modelo
from proceso.tipo_dron.casos import Conocido

TRAMOS = ((0.0, 0.4), (0.4, 0.6), (0.6, 0.8), (0.8, 1.01))
EPSILON = 1e-6


@dataclass
class Evaluado:
    caso: Conocido
    con_base: bool
    metodo: dict[str, float]
    referencia: dict[str, float]
    zona: dict[str, float]


def _frecuencia_grupos(casos: Sequence[Conocido], zona: str | None = None) -> dict[str, float]:
    ids = [g["id"] for g in modelo.grupos()]
    cuenta = dict.fromkeys(ids, 0.0)
    elegidos = [k for k in casos if zona is None or k.entrada.zona == zona] or list(casos)
    for k in elegidos:
        grupos = k.grupos
        for g in grupos:
            cuenta[g] += 1.0 / len(grupos)
    total = sum(cuenta.values()) or 1.0
    # Un grupo que nunca sale recibe una probabilidad mínima: la referencia no puede dar cero.
    return {g: max(v / total, EPSILON) for g, v in cuenta.items()}


def evaluar(catalogo: Catalogo, casos: Sequence[Conocido]) -> list[Evaluado]:
    evaluados = []
    for i, caso in enumerate(casos):
        resto = [k for j, k in enumerate(casos) if j != i]
        previa = [(k.entrada.zona, k.respuesta) for k in resto]
        resultado = modelo.calcular(catalogo, caso.entrada, previa)
        evaluados.append(
            Evaluado(
                caso,
                modelo.con_base(caso.entrada, resultado),
                resultado.por_grupo,
                _frecuencia_grupos(resto),
                _frecuencia_grupos(resto, caso.entrada.zona),
            )
        )
    return evaluados


def _metricas(probabilidades: dict[str, float], respuesta: set[str]) -> dict[str, float]:
    orden = sorted(probabilidades, key=lambda g: (-probabilidades[g], g))
    masa = sum(probabilidades[g] for g in respuesta)
    brier = sum(
        (probabilidades[g] - (1.0 / len(respuesta) if g in respuesta else 0.0)) ** 2
        for g in probabilidades
    )
    return {
        "acierto": 1.0 if orden[0] in respuesta else 0.0,
        "dos_primeros": 1.0 if set(orden[:2]) & respuesta else 0.0,
        "log": math.log(max(masa, EPSILON)),
        "brier": brier,
        "p_primero": probabilidades[orden[0]],
    }


def _sumario(filas: list[dict[str, float]]) -> dict[str, float]:
    n = len(filas)
    if not n:
        return {"casos": 0}
    return {
        "casos": n,
        "aciertos": int(sum(f["acierto"] for f in filas)),
        "acierto": round(sum(f["acierto"] for f in filas) / n, 3),
        "dos_primeros": round(sum(f["dos_primeros"] for f in filas) / n, 3),
        "log_por_caso": round(sum(f["log"] for f in filas) / n, 4),
        "brier": round(sum(f["brier"] for f in filas) / n, 4),
    }


def _remuestreo(diferencias: list[float], veces: int, semilla: int) -> float:
    """Percentil 10 de la media de las diferencias al remuestrear con reemplazo."""
    if not diferencias:
        return float("nan")
    azar = random.Random(semilla)
    medias = sorted(
        sum(azar.choice(diferencias) for _ in diferencias) / len(diferencias) for _ in range(veces)
    )
    return medias[int(0.1 * veces)]


def _error_calibracion(filas: list[tuple[str | None, float, float]]) -> float:
    """Error de calibración de un grupo: en cada zona (frontera, interior), la diferencia entre
    la probabilidad media que el método da al grupo y la parte de los casos que lo eran, pesada
    por los casos de la zona. No se parte por tramos de probabilidad: al dejar fuera un caso, la
    frecuencia de partida de su grupo baja un poco (0,47 frente a 0,51 en la frontera) y unos
    tramos separarían los casos de un grupo de los del otro sin que la probabilidad esté mal."""
    if not filas:
        return 1.0
    total = 0.0
    for zona in sorted({z or "" for z, _, _ in filas}):
        dentro = [(p, y) for z, p, y in filas if (z or "") == zona]
        media_p = sum(p for p, _ in dentro) / len(dentro)
        media_y = sum(y for _, y in dentro) / len(dentro)
        total += len(dentro) * abs(media_p - media_y)
    return total / len(filas)


def _calibracion(filas: list[tuple[float, float]]) -> list[dict[str, Any]]:
    tabla = []
    for bajo, alto in TRAMOS:
        dentro = [(p, a) for p, a in filas if bajo <= p < alto]
        if not dentro:
            continue
        tabla.append(
            {
                "desde": bajo,
                "hasta": min(alto, 1.0),
                "casos": len(dentro),
                "probabilidad_media": round(sum(p for p, _ in dentro) / len(dentro), 3),
                "aciertos": int(sum(a for _, a in dentro)),
                "acierto": round(sum(a for _, a in dentro) / len(dentro), 3),
            }
        )
    return tabla


def resumen(evaluados: list[Evaluado], solo_con_base: bool = True) -> dict[str, Any]:
    """Métricas del método, de la referencia y de la referencia por zona; por grupo y por
    procedencia de la respuesta; calibración; y qué se publica."""
    conf = modelo.configuracion()["publicar"]
    lista = [e for e in evaluados if e.con_base or not solo_con_base]
    metodo = [_metricas(e.metodo, e.caso.grupos) for e in lista]
    referencia = [_metricas(e.referencia, e.caso.grupos) for e in lista]
    por_zona = [_metricas(e.zona, e.caso.grupos) for e in lista]
    diferencias = [m["log"] - r["log"] for m, r in zip(metodo, referencia, strict=True)]
    p10 = _remuestreo(diferencias, int(conf["remuestreos"]), int(conf["semilla"]))
    s_metodo, s_ref = _sumario(metodo), _sumario(referencia)
    mejora_log = (
        s_metodo.get("log_por_caso", 0.0) - s_ref.get("log_por_caso", 0.0) if lista else 0.0
    )
    pasa = bool(
        lista
        and s_metodo["acierto"] > s_ref["acierto"]
        and mejora_log >= float(conf["mejora_minima_log"])
        and p10 > 0
    )
    # Por grupo de la respuesta.
    grupos: dict[str, Any] = {}
    for g in [x["id"] for x in modelo.grupos()]:
        # Solo los casos cuya respuesta es ese grupo y ningún otro: un multirrotor sin más (la
        # UKAB no dice si comercial, FPV o grande) no comprueba ninguno de los tres.
        de_g = [(e, m) for e, m in zip(lista, metodo, strict=True) if e.caso.grupos == {g}]
        aciertos = sum(1 for e, m in de_g if m["acierto"])
        # Precisión: de las veces que el método dijo este grupo, cuántas era.
        dichos = [
            (e, m)
            for e, m in zip(lista, metodo, strict=True)
            if max(e.metodo, key=lambda x: (e.metodo[x], x)) == g
        ]
        correctos = sum(1 for e, _ in dichos if g in e.caso.grupos)
        n = len(de_g)
        acierto = aciertos / n if n else 0.0
        precision = correctos / len(dichos) if dichos else 0.0
        # Lo que el método da a este grupo en sus casos, frente a la referencia.
        log_g = [m["log"] for e, m in de_g]
        log_ref = [r["log"] for e, r in zip(lista, referencia, strict=True) if e.caso.grupos == {g}]
        mejora_g = (sum(log_g) - sum(log_ref)) / n if n else 0.0
        error = _error_calibracion(
            [(e.caso.entrada.zona, e.metodo[g],
              (1.0 / len(e.caso.grupos)) if g in e.caso.grupos else 0.0)
             for e in lista]
        )  # fmt: skip
        publica = (
            pasa
            and n >= int(conf["minimo_casos_por_grupo"])
            and mejora_g > 0
            and error <= float(conf["error_calibracion_maximo"])
        )
        grupos[g] = {
            "casos": n,
            "aciertos": aciertos,
            "acierto": round(acierto, 3),
            "dicho": len(dichos),
            "precision": round(precision, 3),
            "mejora_log": round(mejora_g, 3),
            "error_calibracion": round(error, 3),
            "publica": publica,
        }
    procedencias = Counter(e.caso.fuente_respuesta for e in lista)
    pares = list(zip(lista, metodo, referencia, strict=True))
    por_procedencia = {
        p: {
            "metodo": _sumario([m for e, m, _ in pares if e.caso.fuente_respuesta == p]),
            "referencia": _sumario([r for e, _, r in pares if e.caso.fuente_respuesta == p]),
        }
        for p in sorted(procedencias)
    }
    return {
        "version": modelo.version(),
        "casos_conocidos": len(evaluados),
        "casos_con_base": len(lista),
        "metodo": s_metodo,
        "referencia": s_ref,
        "referencia_por_zona": _sumario(por_zona),
        "mejora_log_por_caso": round(mejora_log, 4),
        "mejora_log_p10": round(p10, 4) if not math.isnan(p10) else None,
        "pasa": pasa,
        "grupos": grupos,
        "grupos_publicados": sorted(g for g, d in grupos.items() if d["publica"]),
        "por_procedencia": por_procedencia,
        "calibracion": _calibracion([(m["p_primero"], m["acierto"]) for m in metodo]),
        "calibracion_referencia": _calibracion(
            [(r["p_primero"], r["acierto"]) for r in referencia]
        ),
    }


def tabla_de_casos(
    evaluados: list[Evaluado], nombre: Callable[[str], str] = str
) -> list[dict[str, Any]]:
    """Una fila por caso, para el informe y para mirar los fallos."""
    filas = []
    for e in evaluados:
        orden = sorted(e.metodo.items(), key=lambda x: (-x[1], x[0]))
        filas.append(
            {
                "id": e.caso.id,
                "procedencia": e.caso.fuente_respuesta,
                "respuesta": sorted(e.caso.grupos),
                "con_base": e.con_base,
                "zona": e.caso.entrada.zona,
                "primero": nombre(orden[0][0]),
                "p_primero": round(orden[0][1], 3),
                "segundo": nombre(orden[1][0]),
                "p_segundo": round(orden[1][1], 3),
                "acierto": orden[0][0] in e.caso.grupos,
                "rasgos": sorted(
                    f"{r['rasgo']}:{r['valor']}"
                    for r in e.caso.entrada.rasgos
                    if isinstance(r["valor"], str)
                ),
            }
        )
    return filas
