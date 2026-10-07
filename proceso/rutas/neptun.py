"""Pistas de NEPTUN (neptun.in.ua) leídas del archivo del seguimiento en directo.

NEPTUN agrega informes (canales de Telegram, avisos oficiales) y da para cada amenaza su posición
estimada, su rumbo, su velocidad si la calcula, cuántos aparatos, el tipo y la confianza, con un
radio de incertidumbre. Son estimaciones a partir de informes, no un radar, y así se tratan.

Del archivo (recogida/seguimiento.py: una línea por mensaje del flujo, con el texto tal como
llegó) se sacan, por amenaza (`id`), sus puntos en el tiempo: los de cada `upsert` y los de su
rastro (`trail`), sin repetir instantes. Una amenaza con un solo punto no es una pista.
"""

import gzip
import json
from collections import defaultdict
from collections.abc import Iterable, Iterator
from datetime import datetime
from pathlib import Path
from typing import Any

VERSION = "neptun-1.0.0"
ATRIBUCION = {
    "texto": "Дані: Карта повітряних тривог — NEPTUN",
    "enlace": "https://neptun.in.ua/",
}
TIPOS_DRON = ("uav",)


def lineas(ruta: Path) -> Iterator[dict[str, Any]]:
    abrir = gzip.open if ruta.suffix == ".gz" else open
    with abrir(ruta, "rt", encoding="utf-8") as f:
        for linea in f:
            linea = linea.strip()
            if linea:
                yield json.loads(linea)


def mensajes(rutas: Iterable[Path]) -> Iterator[dict[str, Any]]:
    """Los mensajes del flujo (los `crudo` del WebSocket y del respaldo REST), descodificados."""
    for ruta in rutas:
        for linea in lineas(ruta):
            if linea.get("via") not in ("ws", "rest") or "crudo" not in linea:
                continue
            try:
                mensaje = json.loads(linea["crudo"])
            except (TypeError, ValueError):
                continue
            if isinstance(mensaje, dict):
                yield mensaje


def _punto(t: Any, lat: Any, lon: Any, extra: dict[str, Any]) -> dict[str, Any] | None:
    if (
        not isinstance(t, str)
        or not isinstance(lat, int | float)
        or not isinstance(lon, int | float)
    ):
        return None
    return {
        "t": t[:19] + "Z",
        "lat": round(float(lat), 4),
        "lon": round(float(lon), 4),
        **extra,
    }


def _amenazas(mensaje: dict[str, Any]) -> list[dict[str, Any]]:
    tipo = mensaje.get("type")
    datos = mensaje.get("data")
    if tipo == "upsert" and isinstance(datos, dict):
        return [datos]
    if tipo == "snapshot" and isinstance(datos, dict):
        return [a for a in datos.get("threats", []) if isinstance(a, dict)]
    return []


def pistas(
    mensajes_: Iterable[dict[str, Any]], tipos: tuple[str, ...] = TIPOS_DRON
) -> list[dict[str, Any]]:
    """Una pista por amenaza de los tipos pedidos, con sus puntos en orden de tiempo."""
    puntos: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    datos: dict[str, dict[str, Any]] = {}
    for mensaje in mensajes_:
        for amenaza in _amenazas(mensaje):
            if amenaza.get("type") not in tipos or not amenaza.get("id"):
                continue
            id_ = str(amenaza["id"])
            velocidad = amenaza.get("velocity") or {}
            extra = {
                k: v
                for k, v in {
                    "rumbo": amenaza.get("heading"),
                    "kmh": velocidad.get("speedKmh") if isinstance(velocidad, dict) else None,
                    "numero": amenaza.get("count"),
                    "incertidumbre_km": amenaza.get("uncertaintyKm"),
                    "confianza": amenaza.get("confidenceLevel"),
                }.items()
                if v is not None
            }
            punto = _punto(amenaza.get("updatedAt"), amenaza.get("lat"), amenaza.get("lon"), extra)
            if punto is not None:
                puntos[id_][punto["t"]] = punto
            for paso in amenaza.get("trail") or []:
                if isinstance(paso, dict):
                    previo = _punto(paso.get("t"), paso.get("lat"), paso.get("lon"), {})
                    if previo is not None and previo["t"] not in puntos[id_]:
                        puntos[id_][previo["t"]] = previo
            datos[id_] = {
                "id": id_,
                "tipo": amenaza.get("type"),
                "titulo": amenaza.get("title"),
            }
    salida = []
    for id_, por_t in puntos.items():
        lista = [por_t[t] for t in sorted(por_t)]
        if len(lista) >= 2:
            salida.append({**datos[id_], "puntos": lista})
    return sorted(salida, key=lambda p: (p["puntos"][0]["t"], p["id"]))


def instante(texto: str) -> datetime:
    return datetime.fromisoformat(texto.replace("Z", "+00:00"))
