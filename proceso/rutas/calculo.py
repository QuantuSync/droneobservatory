"""Rutas publicables de cada noche, su comprobación y sus estadísticas.

1. **Comprobación** (solo en las noches con NEPTUN casi completo, 20 horas o más): se reconstruye
   la noche solo con los avisos de la Fuerza Aérea y se mide, para cada punto de las pistas de
   NEPTUN, la distancia a la línea central del tramo más cercano activo a esa hora (con 45 minutos
   de margen); y lo mismo con la línea recta de la zona de lanzamiento más cercana a cada impacto
   de la noche (la referencia). Pasa si la mediana de la reconstrucción es un 20 % menor o más que
   la de la recta en el conjunto y menor en cada noche, con 2 noches como mínimo.
2. **Qué se publica de cada noche**, cuando la noche ha terminado (ver `cerrada`): si tiene NEPTUN
   (20 horas o más), las pistas de NEPTUN; si no, la reconstrucción con la Fuerza Aérea, y solo
   si la comprobación pasa. Cada tramo lleva su franja (el contorno de sus dos zonas con su
   radio), su grupo, su fuente, los mensajes o la pista de que sale y su precisión.
3. **Estadísticas de grupos** de cada noche (tamaño, velocidad, divisiones y uniones) para la
   exportación semanal.
"""

import math
import statistics
from collections.abc import Callable, Sequence
from datetime import datetime, timedelta
from typing import Any

from proceso.rutas import geometria, neptun, noches, reconstruccion

VERSION = "rutas-publicacion-1.0.0"
HORAS_NEPTUN_MIN = 20
MARGEN_HORA = timedelta(minutes=45)
MEJORA_MINIMA = 0.2
NOCHES_MINIMAS = 2
# Una noche ha terminado cuando ha pasado su ventana (12:00 UTC del día siguiente) y dos horas
# desde su último aviso o punto de NEPTUN: nunca se publica una ruta de un ataque en curso.
ESPERA_TRAS_ULTIMO = timedelta(hours=2)

Frontera = Callable[[float, float], float]


def ultimo_mensaje(noche: dict[str, Any]) -> datetime | None:
    instantes = [neptun.instante(m["fecha"]) for m in noche["kpszsu"]]
    instantes += [
        neptun.instante(p["t"]) for pista in noche["neptun"]["pistas"] for p in pista["puntos"]
    ]
    return max(instantes) if instantes else None


def cerrada(noche: dict[str, Any], ahora: datetime) -> bool:
    _, fin = noches.ventana(noche["noche"])
    ultimo = ultimo_mensaje(noche)
    return ahora >= fin and (ultimo is None or ahora - ultimo >= ESPERA_TRAS_ULTIMO)


def con_neptun(noche: dict[str, Any]) -> bool:
    return int(noche["neptun"]["horas_con_datos"]) >= HORAS_NEPTUN_MIN and bool(
        noche["neptun"]["pistas"]
    )


# --- Comprobación -----------------------------------------------------------------------------


def _linea(t: dict[str, Any]) -> geometria.Tramo:
    return geometria.Tramo(
        t["desde"]["lat"], t["desde"]["lon"], 0.0, t["hasta"]["lat"], t["hasta"]["lon"], 0.0
    )


def _activo(t: dict[str, Any], momento: datetime) -> bool:
    if "t" not in t["desde"]:
        return False
    inicio = neptun.instante(t["desde"]["t"])
    fin = neptun.instante(t["hasta"]["t"]) if "t" in t["hasta"] else inicio + timedelta(hours=2)
    return inicio - MARGEN_HORA <= momento <= fin + MARGEN_HORA


def rectas(ataque: dict[str, Any]) -> list[geometria.Tramo]:
    """La referencia: la línea recta de la zona de lanzamiento más cercana a cada impacto."""
    zonas = reconstruccion._zonas_lanzamiento(ataque.get("zonas", []))
    lineas = []
    for lat, lon in ataque.get("impactos", []):
        if not zonas:
            break
        z = min(zonas, key=lambda z: geometria.distancia_km(z["lat"], z["lon"], lat, lon))
        lineas.append(geometria.Tramo(z["lat"], z["lon"], 0.0, lat, lon, 0.0))
    return lineas


def comprobar_noche(
    noche: dict[str, Any], ataque: dict[str, Any], frontera: Frontera
) -> dict[str, Any] | None:
    """Distancias de los puntos de NEPTUN a la reconstrucción y a la recta."""
    referencia = rectas(ataque)
    if not con_neptun(noche) or not referencia:
        return None
    tramos = reconstruccion.tramos_fuerza_aerea(noche, ataque.get("zonas", []), frontera)
    lineas = [(t, _linea(t)) for t in tramos]
    d_rec, d_recta = [], []
    for pista in noche["neptun"]["pistas"]:
        for p in pista["puntos"]:
            momento = neptun.instante(p["t"])
            activos = [linea for t, linea in lineas if _activo(t, momento)]
            if not activos:
                continue
            d_rec.append(min(x.distancia(p["lat"], p["lon"]) for x in activos))
            d_recta.append(min(x.distancia(p["lat"], p["lon"]) for x in referencia))
    if len(d_rec) < 50:
        return None
    return {
        "noche": noche["noche"],
        "puntos": len(d_rec),
        "puntos_sin_tramo_activo": sum(len(p["puntos"]) for p in noche["neptun"]["pistas"])
        - len(d_rec),
        "mediana_reconstruccion_km": round(statistics.median(d_rec), 1),
        "mediana_recta_km": round(statistics.median(d_recta), 1),
        "cuartil3_reconstruccion_km": round(statistics.quantiles(d_rec, n=4)[2], 1),
        "cuartil3_recta_km": round(statistics.quantiles(d_recta, n=4)[2], 1),
        "tramos": len(tramos),
        "rectas": len(referencia),
        "distancias": [round(x, 1) for x in d_rec],
        "distancias_recta": [round(x, 1) for x in d_recta],
    }


def resumen_comprobacion(noches_: Sequence[dict[str, Any]]) -> dict[str, Any]:
    validas = [n for n in noches_ if n is not None]
    todas_rec = [d for n in validas for d in n["distancias"]]
    todas_recta = [d for n in validas for d in n["distancias_recta"]]
    mediana_rec = statistics.median(todas_rec) if todas_rec else math.nan
    mediana_recta = statistics.median(todas_recta) if todas_recta else math.nan
    cada_noche = all(n["mediana_reconstruccion_km"] < n["mediana_recta_km"] for n in validas)
    pasa = bool(
        len(validas) >= NOCHES_MINIMAS
        and cada_noche
        and mediana_rec <= (1 - MEJORA_MINIMA) * mediana_recta
    )
    return {
        "version": VERSION,
        "noches": [{k: v for k, v in n.items() if not k.startswith("distancias")} for n in validas],
        "puntos": len(todas_rec),
        "mediana_reconstruccion_km": None if math.isnan(mediana_rec) else round(mediana_rec, 1),
        "mediana_recta_km": None if math.isnan(mediana_recta) else round(mediana_recta, 1),
        "mejor_en_cada_noche": cada_noche,
        "pasa": pasa,
        "criterio": (
            f"mediana un {round(MEJORA_MINIMA * 100)} % menor o más que la de la recta, menor en "
            f"cada noche y {NOCHES_MINIMAS} noches con NEPTUN como mínimo"
        ),
    }


# --- Publicación --------------------------------------------------------------------------------


def _clave(punto: dict[str, Any]) -> tuple[float, float, float]:
    return (round(punto["lat"], 2), round(punto["lon"], 2), round(punto["radio_km"]))


def unir_repetidos(tramos: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    """Los tramos de la Fuerza Aérea entre las mismas dos zonas, uno solo con todos sus
    mensajes y su primera y última hora."""
    por_clave: dict[tuple[Any, ...], dict[str, Any]] = {}
    for t in tramos:
        clave = (t["clase"], t["tipo"], _clave(t["desde"]), _clave(t["hasta"]))
        if clave not in por_clave:
            por_clave[clave] = {**t, "mensajes": list(t.get("mensajes", [])), "veces": 1}
            continue
        actual = por_clave[clave]
        actual["mensajes"] = sorted(set(actual["mensajes"]) | set(t.get("mensajes", [])))
        actual["veces"] += 1
        actual["division"] = actual["division"] or t["division"]
        actual["union"] = actual["union"] or t["union"]
    return list(por_clave.values())


def grupos_de(tramos: list[dict[str, Any]]) -> list[int]:
    """El grupo de cada tramo: los tramos que se tocan por sus extremos (misma zona) van en el
    mismo grupo; en NEPTUN, la pista."""
    padre = list(range(len(tramos)))

    def raiz(i: int) -> int:
        while padre[i] != i:
            padre[i] = padre[padre[i]]
            i = padre[i]
        return i

    por_extremo: dict[tuple[Any, ...], int] = {}
    for i, t in enumerate(tramos):
        claves = (
            [("pista", t["pista"])] if "pista" in t else [_clave(t["desde"]), _clave(t["hasta"])]
        )
        for clave in claves:
            if clave in por_extremo:
                padre[raiz(i)] = raiz(por_extremo[clave])
            else:
                por_extremo[clave] = i
    raices: dict[int, int] = {}
    return [raices.setdefault(raiz(i), len(raices) + 1) for i in range(len(tramos))]


def _publico(t: dict[str, Any], grupo: int, fuente: str) -> dict[str, Any]:
    geo = geometria.Tramo(
        t["desde"]["lat"],
        t["desde"]["lon"],
        t["desde"]["radio_km"],
        t["hasta"]["lat"],
        t["hasta"]["lon"],
        t["hasta"]["radio_km"],
    )
    salida: dict[str, Any] = {
        "grupo": grupo,
        "clase": t["clase"],
        "tipo": t["tipo"],
        "desde": {k: (round(v, 4) if isinstance(v, float) else v) for k, v in t["desde"].items()},
        "hasta": {k: (round(v, 4) if isinstance(v, float) else v) for k, v in t["hasta"].items()},
        "precision_km": round(max(t["desde"]["radio_km"], t["hasta"]["radio_km"]), 1),
        "franja": [[x, y] for x, y in geometria.poligono(geo, 10)],
    }
    numero = t.get("numero")
    if isinstance(numero, dict):
        salida["numero"] = numero
    elif isinstance(numero, int):
        salida["numero"] = {"min": numero, "max": numero}
    if t.get("kmh"):
        salida["kmh"] = round(float(t["kmh"]))
    if fuente == "neptun":
        salida["pista"] = t["pista"]
        if t.get("confianza"):
            salida["confianza"] = t["confianza"]
    else:
        salida["mensajes"] = t.get("mensajes", [])
        salida["division"] = bool(t.get("division"))
        salida["union"] = bool(t.get("union"))
    return salida


def estadisticas(
    tramos: Sequence[dict[str, Any]], grupos: Sequence[int], fuente: str
) -> list[dict[str, Any]]:
    """Por grupo: tramos, aparatos si constan, velocidad mediana si consta, divisiones y uniones."""
    por_grupo: dict[int, list[dict[str, Any]]] = {}
    for t, g in zip(tramos, grupos, strict=True):
        por_grupo.setdefault(g, []).append(t)
    salida = []
    for g, lista in sorted(por_grupo.items()):
        numeros = [t["numero"]["max"] for t in lista if isinstance(t.get("numero"), dict)]
        numeros += [t["numero"] for t in lista if isinstance(t.get("numero"), int)]
        velocidades = [float(t["kmh"]) for t in lista if t.get("kmh")]
        salida.append(
            {
                "grupo": g,
                "fuente": fuente,
                "tramos": len(lista),
                "aparatos_max": max(numeros) if numeros else None,
                "kmh_mediana": round(statistics.median(velocidades)) if velocidades else None,
                "divisiones": sum(1 for t in lista if t.get("division")),
                "uniones": sum(1 for t in lista if t.get("union")),
            }
        )
    return salida


def noche_publica(
    noche: dict[str, Any], ataque: dict[str, Any], frontera: Frontera, pasa: bool
) -> dict[str, Any] | None:
    """Lo publicable de una noche cerrada, o None si no hay rutas que publicar."""
    if con_neptun(noche):
        fuente = "neptun"
        tramos = reconstruccion.tramos_neptun(noche)
    elif pasa:
        fuente = "fuerza_aerea"
        tramos = unir_repetidos(
            reconstruccion.tramos_fuerza_aerea(noche, ataque.get("zonas", []), frontera)
        )
    else:
        return None
    if not tramos:
        return None
    grupos = grupos_de(tramos)
    documento: dict[str, Any] = {
        "version": VERSION,
        "noche": noche["noche"],
        "fuente": fuente,
        "ataques": ataque.get("ataques", []),
        "tramos": [_publico(t, g, fuente) for t, g in zip(tramos, grupos, strict=True)],
        "grupos": estadisticas(tramos, grupos, fuente),
    }
    if fuente == "neptun":
        documento["atribucion"] = dict(neptun.ATRIBUCION)
    enlazados = incidentes_enlazados(tramos, ataque.get("incidentes", []))
    if enlazados:
        documento["incidentes"] = enlazados
    return documento


ENLACE_INCIDENTE_KM = 50.0


def incidentes_enlazados(
    tramos: Sequence[dict[str, Any]], incidentes: Sequence[dict[str, Any]]
) -> list[str]:
    """Los incidentes europeos de la noche en los que acaba (o por los que pasa) una ruta: a 50 km
    o menos, más la precisión, de un extremo de un tramo. Se enlazan; no se crean incidentes."""
    enlazados = []
    for incidente in incidentes:
        for t in tramos:
            extremo = min(
                (t["desde"], t["hasta"]),
                key=lambda e: geometria.distancia_km(
                    e["lat"], e["lon"], incidente["lat"], incidente["lon"]
                ),
            )
            d = geometria.distancia_km(
                extremo["lat"], extremo["lon"], incidente["lat"], incidente["lon"]
            )
            if d <= ENLACE_INCIDENTE_KM + float(extremo["radio_km"]):
                enlazados.append(str(incidente["id"]))
                break
    return sorted(set(enlazados))


def resumen_noche(documento: dict[str, Any], ataque: dict[str, Any]) -> dict[str, Any]:
    return {
        "noche": documento["noche"],
        "fuente": documento["fuente"],
        "ataques": documento["ataques"],
        "lanzados": ataque.get("lanzados"),
        "tramos": len(documento["tramos"]),
        "grupos": len(documento["grupos"]),
    }
