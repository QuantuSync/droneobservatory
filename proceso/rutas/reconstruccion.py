"""Rutas de una noche reconstruidas con los avisos de la Fuerza Aérea, y con las pistas de NEPTUN.

**Con la Fuerza Aérea.** Cada aviso con zona es un nodo (hora, zona con radio, rumbo, destino),
salvo si la zona es una región entera (más de 90 km de radio): eso no sitúa el dron.
Un nodo se enlaza con el siguiente aviso, dentro de las tres horas siguientes, que:

- cabe en el tiempo: la distancia entre las zonas, menos sus radios, se recorre a 250 km/h como
  mucho (450 km/h los de reacción), y
- sigue la dirección: está hacia el rumbo del primero (60° como mucho), o más cerca de su
  destino, o las dos zonas se tocan; sin rumbo ni destino, a 150 km como mucho.

Se toma el más temprano; si otro aviso igual de temprano (10 minutos) cumple y está en otro sitio,
el grupo se divide (dos sucesores); si dos nodos llevan al mismo, se unen. No se asigna identidad
por el texto: un tramo es un enlace entre dos avisos, nada más. Cada tramo guarda los mensajes de
los que sale. El último nodo con destino declarado se alarga hasta él (tramo «hacia destino»), y
el primero, si está a 200 km o menos de la frontera rusa o del mar y la noche tiene zonas de
lanzamiento, se alarga desde la más cercana de ellas (tramo «desde lanzamiento»).

**Con NEPTUN.** Cada pista (una amenaza con sus puntos) da tramos entre puntos seguidos, con el
radio de incertidumbre que da NEPTUN (5 km si no lo da).
"""

import itertools
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any

from proceso.rutas import geometria
from proceso.rutas.neptun import instante

VERSION = "rutas-1.0.0"
VENTANA = timedelta(hours=3)
SIMULTANEO = timedelta(minutes=10)
VELOCIDAD_MAX_KMH = {"ataque": 250.0, "reaccion": 450.0, "reconocimiento": 250.0}
ANGULO_MAX = 60.0
SIN_DIRECCION_KM = 150.0
LANZAMIENTO_KM = 200.0
RADIO_NEPTUN_KM = 5.0
RADIO_LANZAMIENTO_KM = 30.0
# Una zona más ancha que esto (una región entera) no sitúa el dron: no entra en la ruta. Las
# partes de región (60 km), las localidades y el mar (90 km) sí.
PRECISION_MAX_KM = 90.0


@dataclass
class Nodo:
    indice: int
    mensaje: int
    t: Any
    lat: float
    lon: float
    radio: float
    tipo: str
    rumbo: float | None
    destino: dict[str, Any] | None
    numero: dict[str, int] | None
    texto: str
    sucesores: list[int] = field(default_factory=list)
    predecesores: list[int] = field(default_factory=list)


def nodos(noche: dict[str, Any]) -> list[Nodo]:
    lista: list[Nodo] = []
    for mensaje in noche["kpszsu"]:
        t = instante(mensaje["fecha"])
        for aviso in mensaje["avisos"]:
            zona = aviso.get("zona")
            if zona is None or aviso["tipo"] == "reconocimiento":
                continue
            if zona["radio_km"] > PRECISION_MAX_KM:
                continue
            lista.append(
                Nodo(
                    len(lista),
                    mensaje["id"],
                    t,
                    zona["lat"],
                    zona["lon"],
                    zona["radio_km"],
                    aviso["tipo"],
                    aviso.get("rumbo"),
                    aviso.get("destino"),
                    aviso.get("numero"),
                    aviso["texto"],
                )
            )
    return lista


def _cabe(a: Nodo, b: Nodo) -> bool:
    horas = (b.t - a.t).total_seconds() / 3600.0
    d = geometria.distancia_km(a.lat, a.lon, b.lat, b.lon)
    if d - a.radio - b.radio > VELOCIDAD_MAX_KMH.get(a.tipo, 250.0) * horas:
        return False
    if d <= a.radio + b.radio:
        return True
    hacia = geometria.rumbo(a.lat, a.lon, b.lat, b.lon)
    if a.rumbo is not None:
        return geometria.diferencia_angular(hacia, a.rumbo) <= ANGULO_MAX
    if a.destino is not None:
        antes = geometria.distancia_km(a.lat, a.lon, a.destino["lat"], a.destino["lon"])
        despues = geometria.distancia_km(b.lat, b.lon, a.destino["lat"], a.destino["lon"])
        return despues < antes
    return d <= SIN_DIRECCION_KM


def enlazar(lista: list[Nodo]) -> None:
    orden = sorted(lista, key=lambda n: n.t)
    for i, a in enumerate(orden):
        candidatos = [
            b
            for b in orden[i + 1 :]
            if timedelta(0) < b.t - a.t <= VENTANA
            and (a.tipo == "reaccion") == (b.tipo == "reaccion")
            and _cabe(a, b)
        ]
        if not candidatos:
            continue
        primero = candidatos[0]
        elegidos = [primero]
        for b in candidatos[1:]:
            if b.t - primero.t > SIMULTANEO:
                break
            if (
                geometria.distancia_km(b.lat, b.lon, primero.lat, primero.lon)
                > b.radio + primero.radio
            ):
                elegidos.append(b)
                break
        for b in elegidos:
            a.sucesores.append(b.indice)
            b.predecesores.append(a.indice)


def _zonas_lanzamiento(nombres: Sequence[str]) -> list[dict[str, Any]]:
    from proceso.deduccion import catalogo

    zonas = catalogo.cargar().zonas
    salida = []
    for nombre in nombres:
        for zona in zonas:
            if zona.lat is not None and zona.lon is not None and zona.nombra(nombre):
                salida.append({"nombre": nombre, "lat": zona.lat, "lon": zona.lon})
                break
    return salida


def _tramo(a: tuple[float, float, float], b: tuple[float, float, float]) -> geometria.Tramo:
    return geometria.Tramo(a[0], a[1], a[2], b[0], b[1], b[2])


def tramos_fuerza_aerea(
    noche: dict[str, Any], lanzamiento: Sequence[str] = (), frontera_km: Any = None
) -> list[dict[str, Any]]:
    """Los tramos de la noche con la Fuerza Aérea: enlaces entre avisos, alargados hasta el
    destino declarado y desde la zona de lanzamiento de la noche."""
    lista = nodos(noche)
    enlazar(lista)
    tramos: list[dict[str, Any]] = []
    for a in lista:
        for j in a.sucesores:
            b = lista[j]
            tramos.append(
                {
                    "clase": "enlace",
                    "tipo": a.tipo,
                    "desde": {
                        "t": a.t.strftime("%Y-%m-%dT%H:%MZ"),
                        "lat": a.lat,
                        "lon": a.lon,
                        "radio_km": a.radio,
                    },
                    "hasta": {
                        "t": b.t.strftime("%Y-%m-%dT%H:%MZ"),
                        "lat": b.lat,
                        "lon": b.lon,
                        "radio_km": b.radio,
                    },
                    "mensajes": sorted({a.mensaje, b.mensaje}),
                    "division": len(a.sucesores) > 1,
                    "union": len(b.predecesores) > 1,
                    "numero": a.numero or b.numero,
                }
            )
        if not a.sucesores and a.destino is not None and a.destino["radio_km"] <= PRECISION_MAX_KM:
            tramos.append(
                {
                    "clase": "hacia_destino",
                    "tipo": a.tipo,
                    "desde": {
                        "t": a.t.strftime("%Y-%m-%dT%H:%MZ"),
                        "lat": a.lat,
                        "lon": a.lon,
                        "radio_km": a.radio,
                    },
                    "hasta": {
                        "lat": a.destino["lat"],
                        "lon": a.destino["lon"],
                        "radio_km": a.destino["radio_km"],
                    },
                    "mensajes": [a.mensaje],
                    "division": False,
                    "union": False,
                    "numero": a.numero,
                }
            )
    zonas = _zonas_lanzamiento(lanzamiento)
    if zonas and frontera_km is not None:
        for a in lista:
            if a.predecesores or a.tipo == "reconocimiento":
                continue
            if frontera_km(a.lat, a.lon) > LANZAMIENTO_KM:
                continue
            cerca = min(
                zonas, key=lambda z: geometria.distancia_km(z["lat"], z["lon"], a.lat, a.lon)
            )
            tramos.append(
                {
                    "clase": "desde_lanzamiento",
                    "tipo": a.tipo,
                    "desde": {
                        "lat": cerca["lat"],
                        "lon": cerca["lon"],
                        "radio_km": RADIO_LANZAMIENTO_KM,
                        "zona": cerca["nombre"],
                    },
                    "hasta": {
                        "t": a.t.strftime("%Y-%m-%dT%H:%MZ"),
                        "lat": a.lat,
                        "lon": a.lon,
                        "radio_km": a.radio,
                    },
                    "mensajes": [a.mensaje],
                    "division": False,
                    "union": False,
                    "numero": a.numero,
                }
            )
    return tramos


def tramos_neptun(noche: dict[str, Any]) -> list[dict[str, Any]]:
    tramos = []
    for pista in noche["neptun"]["pistas"]:
        puntos = pista["puntos"]
        for a, b in itertools.pairwise(puntos):
            if a["lat"] == b["lat"] and a["lon"] == b["lon"]:
                continue
            ra = float(a.get("incertidumbre_km") or RADIO_NEPTUN_KM)
            rb = float(b.get("incertidumbre_km") or RADIO_NEPTUN_KM)
            tramos.append(
                {
                    "clase": "neptun",
                    "pista": pista["id"],
                    "tipo": "ataque",
                    "desde": {"t": a["t"], "lat": a["lat"], "lon": a["lon"], "radio_km": ra},
                    "hasta": {"t": b["t"], "lat": b["lat"], "lon": b["lon"], "radio_km": rb},
                    "numero": b.get("numero") or a.get("numero"),
                    "kmh": b.get("kmh") or a.get("kmh"),
                    "confianza": b.get("confianza") or a.get("confianza"),
                }
            )
    return tramos


def a_geometria(tramos: Sequence[dict[str, Any]]) -> list[geometria.Tramo]:
    return [
        _tramo(
            (t["desde"]["lat"], t["desde"]["lon"], t["desde"]["radio_km"]),
            (t["hasta"]["lat"], t["hasta"]["lon"], t["hasta"]["radio_km"]),
        )
        for t in tramos
    ]
