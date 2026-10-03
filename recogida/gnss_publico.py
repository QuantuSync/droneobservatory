"""Mapa diario de interferencia GPS: ficheros públicos en el almacén, uno por día y por mes.

Sale de lo que guarda el procesado diario del archivo de adsb.lol (`gnss_dia.csv.gz`:
aeronaves distintas y aeronaves con la posición degradada por celda H3 de resolución 4,
`proceso/gnss.py`). Por celda: proporción = (degradadas − 1) / aeronaves, como gpsjam.org;
solo las celdas con 20 aeronaves o más en el día; nivel «sin» por debajo del 2 %, «media» del
2 al 10 % y «alta» por encima. Cada celda lleva su contorno (seis vértices, longitud y
latitud con 3 decimales) para que la web la dibuje sin calcular H3. En el fichero de un mes,
aeronaves y degradadas son la suma de sus días (aeronaves-día) y la proporción se recalcula
igual. El resumen da el número de celdas por nivel, la proporción de toda Europa y el nivel del
periodo: el de la celda del percentil 90 por proporción (el que alcanza una de cada diez).

Objetos (`configuracion/almacen_publico.json`, `objetos.gnss`): `gnss/indice.json` (días y
meses publicados), `gnss/dia/AAAA-MM-DD.json` y `gnss/mes/AAAA-MM.json`, con compresión gzip
(`Content-Encoding: gzip`). Los campos son los de la lista cerrada
`exportacion/campos.CAMPOS_PUBLICOS_GNSS`.

Lo publica el servicio de detección en directo (`recogida/directo.py`) en cada ciclo, unos
pocos días cada vez (los nuevos primero, después el histórico), y anota lo publicado en
`<datos del directo>/gnss.json`.
"""

import gzip
import json
import logging
from collections.abc import Callable
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import h3

from exportacion.campos import CAMPOS_PUBLICOS_GNSS
from exportacion.proyeccion import fuera_de_lista
from proceso import gnss
from recogida import trafico as procesado

registro = logging.getLogger("recogida.directo")

VERSION = 1
# Versión del cálculo: al cambiar, se vuelve a publicar todo (el nivel del resumen pasó de la
# media de Europa al percentil 90 de las celdas).
CALCULO = 2
CONTROL = "gnss.json"
CACHE_DIA = "public, max-age=86400"
CACHE_INDICE = "public, max-age=300"
NIVELES = {"sin_interferencia": "sin", "media": "media", "alta": "alta"}

Subir = Callable[[str, bytes, str, str | None, str | None], bool]


def nivel(aeronaves: int, degradadas: int) -> str:
    p = gnss.proporcion(aeronaves, degradadas)
    return "alta" if p > gnss.NIVEL_ALTO else "media" if p >= gnss.NIVEL_MEDIO else "sin"


def nivel_resumen(celdas: list[dict[str, Any]]) -> str:
    """El nivel del periodo: el de la celda del percentil 90 por proporción (el que alcanza una
    de cada diez celdas). La media de toda Europa queda casi siempre por debajo del 2 % aunque
    haya cientos de celdas con interferencia alta."""
    if not celdas:
        return "sin"
    proporciones = sorted(c["proporcion"] for c in celdas)
    p = proporciones[min(len(proporciones) - 1, int(0.9 * len(proporciones)))]
    return "alta" if p > gnss.NIVEL_ALTO else "media" if p >= gnss.NIVEL_MEDIO else "sin"


def contorno(celda: str) -> list[list[float]]:
    return [[round(lon, 3), round(lat, 3)] for lat, lon in h3.cell_to_boundary(celda)]


def documento(periodo: str, dias: int, filas: dict[str, tuple[int, int]]) -> dict[str, Any]:
    """El fichero público de un día o de un mes con sus celdas (aeronaves, degradadas)."""
    minimo = gnss.MINIMO_DIA * dias
    celdas: list[dict[str, Any]] = []
    for celda, (n, malas) in sorted(filas.items()):
        if n < minimo:
            continue
        celdas.append(
            {
                "h3": celda,
                "aeronaves": n,
                "degradadas": malas,
                "proporcion": round(gnss.proporcion(n, malas), 4),
                "nivel": nivel(n, malas),
                "contorno": contorno(celda),
            }
        )
    total = sum(c["aeronaves"] for c in celdas)
    malas_total = sum(max(0, c["degradadas"] - 1) for c in celdas)
    proporcion = malas_total / total if total else 0.0
    return {
        "version": VERSION,
        "periodo": periodo,
        "dias": dias,
        "resolucion_h3": gnss.RESOLUCION,
        "resumen": {
            "celdas": len(celdas),
            "celdas_media": sum(1 for c in celdas if c["nivel"] == "media"),
            "celdas_alta": sum(1 for c in celdas if c["nivel"] == "alta"),
            "aeronaves": total,
            "degradadas": sum(c["degradadas"] for c in celdas),
            "proporcion": round(proporcion, 4),
            "nivel": nivel_resumen(celdas),
        },
        "celdas": celdas,
    }


def leer_dia(datos_trafico: Path, dia: date) -> dict[str, tuple[int, int]] | None:
    carpeta = procesado.directorio_dia(datos_trafico, dia)
    if not (carpeta / procesado.RESUMEN).exists():
        return None
    filas = procesado._detalle(carpeta, "gnss_dia")
    return {c: (n, m) for c, n, m in filas}


def comprimir(contenido: dict[str, Any]) -> bytes:
    texto = json.dumps(contenido, ensure_ascii=False, separators=(",", ":"))
    return gzip.compress(texto.encode("utf-8"), compresslevel=9, mtime=0)


class Publicador:
    def __init__(self, datos_trafico: Path, datos: Path, subir: Subir | None) -> None:
        self.datos_trafico = datos_trafico
        self.datos = datos
        self.subir = subir
        self.ruta_control = datos / CONTROL

    def _control(self) -> dict[str, Any]:
        """Lo publicado: `dias` y `meses` (todo lo que hay en el almacén, con el cálculo que sea,
        para que el índice no pierda días mientras se vuelve a publicar) y `al_dia`, los días
        publicados con el cálculo actual."""
        try:
            contenido: dict[str, Any] = json.loads(self.ruta_control.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            contenido = {}
        if contenido.get("calculo") != CALCULO:
            contenido["al_dia"] = []
            contenido["calculo"] = CALCULO
        contenido.setdefault("dias", [])
        contenido.setdefault("meses", [])
        contenido.setdefault("al_dia", [])
        return contenido

    def _guardar(self, control: dict[str, Any]) -> None:
        self.ruta_control.parent.mkdir(parents=True, exist_ok=True)
        temporal = self.ruta_control.with_suffix(".tmp")
        temporal.write_text(json.dumps(control, indent=1) + "\n", encoding="utf-8", newline="\n")
        temporal.replace(self.ruta_control)

    def _subir(self, objeto: str, contenido: dict[str, Any], cache: str) -> bool:
        if fuera_de_lista([contenido], CAMPOS_PUBLICOS_GNSS):
            raise ValueError(f"{objeto}: campos fuera de la lista cerrada")
        if self.subir is None:
            return False
        return self.subir(f"gnss/{objeto}", comprimir(contenido), "application/json", cache, "gzip")

    def pendientes(self) -> list[date]:
        hechos = set(self._control()["al_dia"])
        dias = procesado.Dias(self.datos_trafico).procesados()
        return sorted((d for d in dias if d.isoformat() not in hechos), reverse=True)

    def publicar_pendientes(self, tope: int = 2) -> int:
        """Publica hasta `tope` días nuevos, sus meses y el índice. Devuelve cuántos días."""
        if self.subir is None:
            return 0
        control = self._control()
        hechos = 0
        meses: set[str] = set()
        for dia in self.pendientes()[:tope]:
            filas = leer_dia(self.datos_trafico, dia)
            if filas is None:
                continue
            if not self._subir(
                f"dia/{dia.isoformat()}.json", documento(dia.isoformat(), 1, filas), CACHE_DIA
            ):
                break
            control["dias"] = sorted(set(control["dias"]) | {dia.isoformat()})
            control["al_dia"] = sorted(set(control["al_dia"]) | {dia.isoformat()})
            meses.add(dia.isoformat()[:7])
            hechos += 1
        for mes in sorted(meses):
            dias = [d for d in control["al_dia"] if d.startswith(mes)]
            suma: dict[str, tuple[int, int]] = {}
            for d in dias:
                for celda, (n, m) in (
                    leer_dia(self.datos_trafico, date.fromisoformat(d)) or {}
                ).items():
                    viejo = suma.get(celda, (0, 0))
                    suma[celda] = (viejo[0] + n, viejo[1] + m)
            if self._subir(f"mes/{mes}.json", documento(mes, len(dias), suma), CACHE_DIA):
                control["meses"] = sorted(set(control.get("meses", [])) | {mes})
        if hechos:
            indice = {
                "version": VERSION,
                "generado": datetime.now(UTC).strftime("%Y-%m-%dT%H:%MZ"),
                "dias": control["dias"],
                "meses": control.get("meses", []),
            }
            if self._subir("indice.json", indice, CACHE_INDICE):
                self._guardar(control)
                registro.info("interferencia GPS publicada: %d días nuevos", hechos)
        return hechos
