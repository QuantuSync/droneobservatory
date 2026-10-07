"""El archivo del seguimiento, ordenado por noches: mensajes de la Fuerza Aérea con sus avisos y
pistas de NEPTUN.

Una noche va de las 12:00 UTC de su día a las 12:00 UTC del siguiente (las oleadas salen por la
tarde y acaban por la mañana; así una oleada no se parte en dos). Se lee del archivo:

- `kpszsu/AAAA/MM/kpszsu-AAAA-MM-DDTHH.jsonl(.gz)`: lo capturado en directo desde el 4 de octubre
  de 2026 (bloque HTML de cada publicación, con sus versiones; vale la última);
- `kpszsu/historico/kpszsu-historico-AAAA-MM.jsonl.gz`: los mensajes del canal desde 2022, sacados
  de las páginas que ya estaban descargadas (recogida/rutas.py importar-historico);
- `neptun/AAAA/MM/neptun-AAAA-MM-DDTHH.jsonl(.gz)`: el flujo de NEPTUN.

Una noche se estructura sola, con sus ficheros, y no carga el resto del archivo.
"""

import re
from collections.abc import Iterator
from datetime import UTC, date, datetime, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Any

from proceso.rutas import mensajes, neptun
from recogida.telegram import leer_pagina

VERSION = "noches-1.0.0"
HORA_CORTE = 12


def noche_de(momento: datetime) -> str:
    """El día de la noche a que pertenece un instante UTC."""
    dia = momento.date() if momento.hour >= HORA_CORTE else momento.date() - timedelta(days=1)
    return dia.isoformat()


def ventana(noche: str) -> tuple[datetime, datetime]:
    inicio = datetime.combine(date.fromisoformat(noche), datetime.min.time(), UTC).replace(
        hour=HORA_CORTE
    )
    return inicio, inicio + timedelta(days=1)


def _horas(noche: str) -> list[datetime]:
    inicio, fin = ventana(noche)
    horas = []
    momento = inicio
    while momento < fin:
        horas.append(momento)
        momento += timedelta(hours=1)
    return horas


def ficheros_hora(datos: Path, fuente: str, momento: datetime) -> list[Path]:
    carpeta = datos / fuente / f"{momento:%Y}" / f"{momento:%m}"
    base = f"{fuente}-{momento:%Y-%m-%dT%H}"
    if not carpeta.exists():
        return []
    return sorted(p for p in carpeta.glob(f"{base}*") if p.name.endswith((".jsonl", ".jsonl.gz")))


def historico(datos: Path, noche: str) -> Path:
    mes = noche[:7]
    return datos / "kpszsu" / "historico" / f"kpszsu-historico-{mes}.jsonl.gz"


_HTML = re.compile(r"<[^>]+>")


def _texto_bloque(crudo: str) -> str:
    pagina = leer_pagina(f"<section>{crudo}</section>")
    return pagina.publicaciones[0].texto if pagina.publicaciones else _HTML.sub(" ", crudo)


@lru_cache(maxsize=3)
def _historico_mes(ruta: Path) -> tuple[dict[str, Any], ...]:
    """Las publicaciones de un mes del histórico, sin el bloque HTML (ya traen su texto): al
    estructurar noche a noche, el mes se lee una vez."""
    return tuple({k: v for k, v in linea.items() if k != "crudo"} for linea in neptun.lineas(ruta))


def mensajes_kpszsu(datos: Path, noche: str) -> list[dict[str, Any]]:
    """(id, fecha, texto) de las publicaciones del canal de la noche: la última versión de cada
    una, del archivo en directo y del histórico."""
    inicio, fin = ventana(noche)
    por_id: dict[int, dict[str, Any]] = {}
    rutas: list[Path] = []
    for hora in [*_horas(noche), fin, fin + timedelta(hours=1)]:
        rutas += ficheros_hora(datos, "kpszsu", hora)
    for mes in sorted({noche[:7], fin.strftime("%Y-%m")}):
        ruta = datos / "kpszsu" / "historico" / f"kpszsu-historico-{mes}.jsonl.gz"
        if ruta.exists():
            rutas.append(ruta)
    for ruta in rutas:
        lineas_ = _historico_mes(ruta) if "historico" in ruta.name else neptun.lineas(ruta)
        for linea in lineas_:
            if "id" not in linea or "fecha" not in linea:
                continue
            fecha = neptun.instante(str(linea["fecha"]))
            if not inicio <= fecha < fin:
                continue
            texto = linea.get("texto")
            if texto is None and linea.get("crudo"):
                texto = _texto_bloque(str(linea["crudo"]))
            version = int(linea.get("version", 0))
            previo = por_id.get(int(linea["id"]))
            if previo is None or version >= previo["version"]:
                por_id[int(linea["id"])] = {
                    "id": int(linea["id"]),
                    "fecha": fecha.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "texto": texto or "",
                    "version": version,
                }
    return [por_id[i] for i in sorted(por_id)]


def pistas_neptun(datos: Path, noche: str) -> tuple[list[dict[str, Any]], int]:
    """Pistas de drones de la noche y cuántas horas de la noche tienen fichero de NEPTUN."""
    rutas: list[Path] = []
    horas_con_datos = 0
    for hora in _horas(noche):
        encontradas = ficheros_hora(datos, "neptun", hora)
        horas_con_datos += bool(encontradas)
        rutas += encontradas
    inicio, fin = ventana(noche)
    lista = []
    for pista in neptun.pistas(neptun.mensajes(rutas)):
        puntos = [p for p in pista["puntos"] if inicio <= neptun.instante(p["t"]) < fin]
        if len(puntos) >= 2:
            lista.append({**pista, "puntos": puntos})
    return lista, horas_con_datos


def estructurar(datos: Path, noche: str) -> dict[str, Any]:
    """La noche estructurada: avisos de la Fuerza Aérea y pistas de NEPTUN."""
    kpszsu = mensajes.leer_mensajes(mensajes_kpszsu(datos, noche))
    pistas, horas = pistas_neptun(datos, noche)
    return {
        "version": VERSION,
        "version_kpszsu": mensajes.VERSION,
        "version_neptun": neptun.VERSION,
        "noche": noche,
        "kpszsu": kpszsu,
        "neptun": {"horas_con_datos": horas, "pistas": pistas},
    }


def noches_del_archivo(datos: Path) -> Iterator[str]:
    """Las noches con algún mensaje en el archivo (histórico o en directo)."""
    vistas: set[str] = set()
    for ruta in sorted((datos / "kpszsu" / "historico").glob("kpszsu-historico-*.jsonl.gz")):
        for linea in neptun.lineas(ruta):
            if "fecha" in linea:
                vistas.add(noche_de(neptun.instante(str(linea["fecha"]))))
    for fuente in ("kpszsu", "neptun"):
        for ruta in (datos / fuente).glob("*/*/*.jsonl*"):
            m = re.search(r"(\d{4}-\d{2}-\d{2})T(\d{2})", ruta.name)
            if m:
                momento = datetime.fromisoformat(f"{m.group(1)}T{m.group(2)}:00+00:00")
                vistas.add(noche_de(momento))
    yield from sorted(vistas)
