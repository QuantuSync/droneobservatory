"""Nombres normalizados de las zonas de lanzamiento de los partes de la Fuerza Aérea de Ucrania.

La misma zona sale en los partes con varias grafías («Міллерово», «Міллєрово», «Мілерово»;
«Шаталово» y «Шаталове»; «Донецьк», «Донецьк - України» y «Донецької обл») y contaba como
zonas distintas. La tabla `configuracion/zonas_lanzamiento_nombres.json` da, para cada zona
del catálogo del motor de deducción (`configuracion/zonas_lanzamiento.json`), su nombre
normalizado, y las direcciones genéricas sin emplazamiento («Крим», «Курська область»).

Un nombre de los partes es de una zona si contiene una de sus raíces (las del catálogo y las
variantes de la tabla), comparando sin distinguir «є» de «е» ni el tipo de guion, y ninguna de
sus exclusiones. Un nombre puede dar dos zonas («Чауда Гвардійське», sin coma). Una dirección
genérica solo cuenta si el nombre no da ninguna zona concreta («Чауда – окупований Крим» es
Чауда). Lo que no es una zona (un misil, una ruta) se descarta y lo que no se reconoce va al
registro de revisión, nunca como zona nueva.
"""

import json
import re
from dataclasses import dataclass
from datetime import datetime
from functools import cache
from pathlib import Path
from typing import TYPE_CHECKING, Any

from esquema import Documento

if TYPE_CHECKING:
    from almacen.base import Almacen

CONFIGURACION = Path(__file__).resolve().parent.parent / "configuracion"
NOMBRES = CONFIGURACION / "zonas_lanzamiento_nombres.json"
CATALOGO = CONFIGURACION / "zonas_lanzamiento.json"


def plegar(texto: str) -> str:
    """Minúsculas, «є»/«ё» como «е», un solo tipo de guion y de apóstrofo, sin espacios
    alrededor del guion."""
    t = texto.lower().replace("є", "е").replace("ё", "е")
    t = re.sub(r"[’ʼ`]", "'", t)
    t = re.sub(r"\s*[-–—]\s*", "-", t)
    return " ".join(t.split())


@dataclass(frozen=True)
class Entrada:
    nombre: str
    raices: tuple[str, ...]
    excluir: tuple[str, ...]
    catalogo: tuple[str, ...] = ()
    region: str | None = None

    def posicion(self, plegado: str) -> int | None:
        """Dónde empieza la primera raíz en el nombre plegado, o None si no es de esta zona."""
        if any(e in plegado for e in self.excluir):
            return None
        posiciones = [plegado.find(r) for r in self.raices if r in plegado]
        return min(posiciones) if posiciones else None


@dataclass(frozen=True)
class Tabla:
    version: str
    zonas: tuple[Entrada, ...]
    direcciones: tuple[Entrada, ...]
    no_son_zonas: tuple[tuple[re.Pattern[str], str], ...]


@cache
def tabla(ruta: Path = NOMBRES, catalogo: Path = CATALOGO) -> Tabla:
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    zonas_catalogo = {z["id"]: z for z in json.loads(catalogo.read_text(encoding="utf-8"))["zonas"]}
    zonas = []
    for z in datos["zonas"]:
        raices = {plegar(v) for v in z["variantes"]}
        excluir: set[str] = set()
        for id_ in z["catalogo"]:
            raices |= {plegar(r) for r in zonas_catalogo[id_]["raices"]}
            excluir |= {plegar(e) for e in zonas_catalogo[id_].get("excluir") or []}
        # Si alguna zona del catálogo no excluye, la exclusión de otra no vale para todas.
        if any(not zonas_catalogo[i].get("excluir") for i in z["catalogo"]):
            excluir = set()
        zonas.append(Entrada(z["nombre"], tuple(sorted(raices)), tuple(sorted(excluir)),
                             tuple(z["catalogo"])))  # fmt: skip
    direcciones = tuple(
        Entrada(d["nombre"], tuple(plegar(v) for v in d["variantes"]), (), (), d["region"])
        for d in datos["direcciones"]
    )
    no_son = tuple(
        (re.compile(n["patron"], re.IGNORECASE), n["motivo"]) for n in datos["no_son_zonas"]
    )
    return Tabla(datos["version"], tuple(zonas), direcciones, no_son)


@dataclass(frozen=True)
class Normalizado:
    """Lo que da un nombre de un parte: sus zonas normalizadas (en el orden del texto), o el
    motivo por el que no es una zona, o nada (va al registro de revisión)."""

    zonas: tuple[str, ...] = ()
    descarte: str | None = None

    @property
    def reconocido(self) -> bool:
        return bool(self.zonas) or self.descarte is not None


def normalizar(nombre: str, t: Tabla | None = None) -> Normalizado:
    t = t or tabla()
    plegado = plegar(nombre)
    for patron, motivo in t.no_son_zonas:
        if patron.search(plegado):
            return Normalizado(descarte=motivo)
    for grupo in (t.zonas, t.direcciones):
        halladas = sorted(
            (pos, e.nombre) for e in grupo if (pos := e.posicion(plegado)) is not None
        )
        if halladas:
            return Normalizado(tuple(dict.fromkeys(n for _, n in halladas)))
    return Normalizado()


def normalizar_lista(nombres: list[str] | tuple[str, ...]) -> tuple[list[str], list[str]]:
    """(zonas normalizadas sin repetir, nombres que no se reconocen)."""
    zonas: list[str] = []
    sin_reconocer: list[str] = []
    for nombre in nombres:
        resultado = normalizar(nombre)
        for zona in resultado.zonas:
            if zona not in zonas:
                zonas.append(zona)
        if not resultado.reconocido:
            sin_reconocer.append(nombre)
    return zonas, sin_reconocer


# --- Corrección de los ataques guardados y registro de revisión --------------------------------

CURSOR = "zonas_lanzamiento"
CURSOR_REVISAR = "zonas_lanzamiento:revisar"
MOTIVO = (
    "zonas de lanzamiento con su nombre normalizado (configuracion/zonas_lanzamiento_nombres.json):"
    " una zona por lugar aunque el parte la escriba de otra forma"
)


def _citadas(ataque: Documento) -> list[str]:
    citadas = ataque.get("zonas_lanzamiento_citadas")
    if citadas is None:
        citadas = ataque.get("zonas_lanzamiento") or []
    return [str(x) for x in citadas]


def corregir(almacen: "Almacen", ahora: datetime) -> dict[str, Any]:
    """Normaliza las zonas de los ataques guardados (una vez por versión de la tabla: cursor
    CURSOR) y rehace en cada recogida el registro de revisión (CURSOR_REVISAR) con los nombres
    que la tabla no reconoce y los ataques que los citan. Lo escrito por el parte se conserva en
    zonas_lanzamiento_citadas. Devuelve el resumen."""
    version = tabla().version
    hecho = almacen.cursor(CURSOR) or {}
    resumen: dict[str, Any] = {}
    sin_reconocer: dict[str, list[str]] = {}
    for ataque in almacen.ataques_ucrania():
        citadas = _citadas(ataque)
        zonas, desconocidas = normalizar_lista(citadas)
        for nombre in desconocidas:
            sin_reconocer.setdefault(nombre, []).append(ataque["id"])
        if hecho.get("version") == version:
            continue
        if zonas == ataque.get("zonas_lanzamiento", []):
            continue
        nuevo = {**ataque, "zonas_lanzamiento": zonas, "zonas_lanzamiento_citadas": citadas}
        almacen.guardar_ataque_ucrania(nuevo, ahora)
        almacen.anotar_motivo(
            "ataques_ucrania", ataque["id"],
            {"zonas_lanzamiento": ataque.get("zonas_lanzamiento")},
            {"zonas_lanzamiento": zonas}, MOTIVO,
        )  # fmt: skip
        resumen["cambiados"] = resumen.get("cambiados", 0) + 1
    if hecho.get("version") != version:
        antes = {z for a in almacen.ataques_ucrania() for z in _citadas(a)}
        despues = {z for a in almacen.ataques_ucrania() for z in a.get("zonas_lanzamiento", [])}
        resumen.update(version=version, fecha=ahora.strftime("%Y-%m-%dT%H:%MZ"),
                       nombres_citados=len(antes), zonas_normalizadas=len(despues))  # fmt: skip
        resumen.setdefault("cambiados", 0)
        almacen.guardar_cursor(CURSOR, resumen)
    revisar = {
        "fecha": ahora.strftime("%Y-%m-%dT%H:%MZ"),
        "nombres": [
            {"nombre": n, "ataques": len(ids), "ejemplo": ids[0]}
            for n, ids in sorted(sin_reconocer.items())
        ],
    }
    anterior = almacen.cursor(CURSOR_REVISAR) or {}
    if anterior.get("nombres") != revisar["nombres"]:
        almacen.guardar_cursor(CURSOR_REVISAR, revisar)
    return resumen
