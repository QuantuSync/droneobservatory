"""Mensajes de seguimiento de la Fuerza Aérea de Ucrania (t.me/kpszsu), leídos por código.

Cada línea de un mensaje de seguimiento dice dónde está un dron o un grupo y hacia dónde va:

- «🛵 БпЛА на півночі Сумщини, курс - південно-західний.»
- «🛵 Група БпЛА з Чорного моря ➡️ на Одещину.»
- «🛵 Сумщина: БпЛА повз Білопілля ➡️ курсом на захід.»
- «🏍 Реактивний БпЛА на Велику Димерку/Київ.»

De cada línea sale un aviso: el tipo (de ataque, a reacción, de reconocimiento), si es un grupo
y cuántos si lo dice, la zona (una localidad con su radio, una parte de una región, una región
entera o el mar Negro), el rumbo (de las palabras de dirección: «курс - південний», «з півночі» es
rumbo sur) y el destino («курсом на Конотоп», «в напрямку Сум»). Son zonas y direcciones, no
puntos: cada zona lleva su radio. Las líneas de misiles, aviones y bombas guiadas no son drones y
no dan avisos. Lo que la línea no dice queda vacío.
"""

import json
import math
import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from functools import cache
from typing import Any

from proceso import lugares_guerra
from recogida import parte

VERSION = "seguimiento-kpszsu-1.0.0"

# Rumbos: hacia dónde (grados desde el norte).
_DIRECCIONES = (
    ("північно-східн", 45.0),
    ("північно-західн", 315.0),
    ("південно-східн", 135.0),
    ("південно-західн", 225.0),
    ("північн", 0.0),
    ("південн", 180.0),
    ("східн", 90.0),
    ("західн", 270.0),
)
# «з півночі», «з північного сходу», «зі сходу»: de dónde viene (el rumbo es el contrario).
_DESDE = re.compile(
    r"\bз[іи]?\s+(північного\s+сходу|північного\s+заходу|південного\s+сходу|"
    r"південного\s+заходу|півночі|півдня|сходу|заходу)(?!\s+[А-ЯІЇЄҐ])"
)
_DESDE_GRADOS = {
    "північного сходу": 45.0,
    "північного заходу": 315.0,
    "південного сходу": 135.0,
    "південного заходу": 225.0,
    "півночі": 0.0,
    "півдня": 180.0,
    "сходу": 90.0,
    "заходу": 270.0,
}
# «курсом на захід», «курс - південний», «у північному напрямку», «змінюючи курс на схід»,
# «північним курсом», «курсом на північний захід».
_CURSO_PALABRA = re.compile(
    r"(?:курс\w*\s*(?:[-–—:]\s*)?(?:на\s+)?|в\s+|у\s+)"
    r"(північно-східн\w*|північно-західн\w*|південно-східн\w*|південно-західн\w*|"
    r"(?:північн|південн)\w*\s+(?:схід|захід)|північн\w*|південн\w*|східн\w*|західн\w*|"
    r"північ|південь|схід|захід)(?:\s+напрям\w*)?"
    r"|(північно-східн|північно-західн|південно-східн|південно-західн|північн|південн|східн|"
    r"західн)\w*\s+курсом"
)
_PUNTOS = {"північ": 0.0, "південь": 180.0, "схід": 90.0, "захід": 270.0}
# Parte de una región: «на півночі Сумщини», «на північному сході Дніпропетровщини».
_PARTE = re.compile(
    r"(?:на|у|в)\s+(північному\s+сході|північному\s+заході|південному\s+сході|"
    r"південному\s+заході|півночі|півдні|сході|заході|центрі)\s+([А-ЯІЇЄҐ][\w'’-]+)"
)
_PARTE_GRADOS = {
    "північному сході": 45.0,
    "північному заході": 315.0,
    "південному сході": 135.0,
    "південному заході": 225.0,
    "півночі": 0.0,
    "півдні": 180.0,
    "сході": 90.0,
    "заході": 270.0,
    "центрі": None,
}
# Nombre de lugar tras una preposición (con «м.», «н.п.» o «смт» delante, si los lleva).
_NOMBRE_UA = r"(?:м\.\s*|н\.п\.\s*|смт\s+)?([А-ЯІЇЄҐ][\w'’-]+(?:[ -][А-ЯІЇЄҐ][\w'’-]+)?)"
# Destino: «курсом на Конотоп», «в напрямку Сум», «вектором на Черкаси», «до Києва».
_DESTINO = re.compile(
    r"(?:курсом\s+на|курс\s+на|в\s+напрямку|у\s+напрямку|напрямок\s+на|вектором\s+на|"
    r"вектор\s*[-–]\s*|вектор\s+руху|➡️\s*(?:на|в\s+напрямку|у\s+напрямку)?|"
    r"наближа\w+\s+до|до|БпЛА\s+на|БпЛА\s+на/повз)\s+" + _NOMBRE_UA
)
# Posición en una localidad: «повз Хотінь», «над Павлоградом», «в районі Сум», «біля …».
_POSICION = re.compile(
    r"(?:на/повз|повз|над|біля|в\s+районі|у\s+районі|в\s+р-ні|у\s+р-ні|поблизу|східніше|"
    r"західніше|північніше|південніше)\s+" + _NOMBRE_UA
)
_MAR = re.compile(r"чорн\w+\s+мор|акваторі\w+|азовськ\w+\s+мор")
_NO_DRON = re.compile(r"ракет|\bкр\b|балістик|авіабомб|\bкаб\b|винищувач|\bміг\b|літак|🚀")
_DRON = re.compile(r"бпла|безпілотн|шахед|дрон|🛵|🏍|🛸")
_REACCION = re.compile(r"реактивн|🏍")
_RECONOCIMIENTO = re.compile(r"розвідувальн|🛸(?!.*🛵)")
_GRUPO = re.compile(r"груп|декілька|кілька")
_NUMERO = re.compile(r"(\d{1,3})\s*(?:х\s*)?(?:ударн\w+\s+)?(?:бпла|дрон|шахед)")
_LOCATIVO = re.compile(r"(?:щині|ині|ії|ні)$")
_LINEAS = re.compile(r"\n+|;\s*(?=\S)")
# Radio de una región entera y de una parte de región, y el del mar.
RADIO_PARTE_KM = 60.0
MAR_NEGRO = {"lat": 45.8, "lon": 31.2, "radio_km": 90.0}


@dataclass
class Zona:
    lat: float
    lon: float
    radio_km: float
    nivel: str  # localidad | parte | region | mar
    texto: str
    region: str | None = None

    def documento(self) -> dict[str, Any]:
        return {
            "lat": round(self.lat, 4),
            "lon": round(self.lon, 4),
            "radio_km": round(self.radio_km, 1),
            "nivel": self.nivel,
            "texto": self.texto,
            **({"region": self.region} if self.region else {}),
        }


@dataclass
class Aviso:
    """Lo que dice una línea de un mensaje de seguimiento."""

    texto: str
    tipo: str  # ataque | reaccion | reconocimiento
    grupo: bool
    numero: tuple[int, int] | None = None
    zona: Zona | None = None
    rumbo: float | None = None
    destino: Zona | None = None
    regiones: list[str] = field(default_factory=list)

    def documento(self) -> dict[str, Any]:
        documento: dict[str, Any] = {"texto": self.texto, "tipo": self.tipo, "grupo": self.grupo}
        if self.numero is not None:
            documento["numero"] = {"min": self.numero[0], "max": self.numero[1]}
        if self.zona is not None:
            documento["zona"] = self.zona.documento()
        if self.rumbo is not None:
            documento["rumbo"] = self.rumbo
        if self.destino is not None:
            documento["destino"] = self.destino.documento()
        if self.regiones:
            documento["regiones"] = self.regiones
        return documento


@cache
def _nomenclator() -> lugares_guerra.Nomenclator:
    return lugares_guerra.cargar()


@cache
def _vocabulario() -> parte.Vocabulario:
    return parte.vocabulario()


@cache
def _regiones() -> dict[str, dict[str, float]]:
    """Centro y caja de cada óblast (de sus contornos), para las zonas de región y de parte."""
    datos = json.loads(lugares_guerra.CONTORNOS_UA.read_text(encoding="utf-8"))
    cajas: dict[str, list[float]] = {}
    for rasgo in datos["features"]:
        geometria = rasgo["geometry"]
        poligonos = (
            [geometria["coordinates"]]
            if geometria["type"] == "Polygon"
            else geometria["coordinates"]
        )
        caja = cajas.setdefault(rasgo["properties"]["iso"], [90.0, 180.0, -90.0, -180.0])
        for poligono in poligonos:
            for lon, lat in poligono[0]:
                caja[0], caja[1] = min(caja[0], lat), min(caja[1], lon)
                caja[2], caja[3] = max(caja[2], lat), max(caja[3], lon)
    salida = {}
    for iso, (s, o, n, e) in cajas.items():
        alto = (n - s) * 111.0
        ancho = (e - o) * 111.0 * math.cos(math.radians((n + s) / 2))
        salida[iso] = {
            "lat": (n + s) / 2,
            "lon": (o + e) / 2,
            "sur": s,
            "oeste": o,
            "norte": n,
            "este": e,
            "radio_km": max(alto, ancho) / 2,
        }
    return salida


def zona_de_region(iso: str, parte_grados: float | None = None, texto: str = "") -> Zona | None:
    caja = _regiones().get(iso)
    if caja is None:
        return None
    if parte_grados is None:
        return Zona(caja["lat"], caja["lon"], caja["radio_km"], "region", texto, iso)
    # A dos tercios del centro hacia el borde en esa dirección.
    medio_lat = (caja["norte"] - caja["sur"]) / 2
    medio_lon = (caja["este"] - caja["oeste"]) / 2
    rad = math.radians(parte_grados)
    lat = caja["lat"] + math.cos(rad) * medio_lat * 2 / 3
    lon = caja["lon"] + math.sin(rad) * medio_lon * 2 / 3
    return Zona(lat, lon, min(RADIO_PARTE_KM, caja["radio_km"]), "parte", texto, iso)


def _grados(palabra: str) -> float | None:
    partes = palabra.split()
    if len(partes) == 2 and partes[1] in ("схід", "захід"):
        palabra = ("північно-" if partes[0].startswith("північн") else "південно-") + (
            "східн" if partes[1] == "схід" else "західн"
        )
    for raiz, grados in _DIRECCIONES:
        if palabra.startswith(raiz):
            return grados
    return _PUNTOS.get(palabra)


# Kiev ciudad y su óblast se nombran igual («Київ», «Київщина»): se buscan juntos.
_VECINAS = {"UA-30": "UA-32", "UA-32": "UA-30", "UA-40": "UA-43", "UA-43": "UA-40"}


def _localidad(nombre: str, regiones: list[str], contexto: str) -> Zona | None:
    """La localidad nombrada, primero en las regiones de la línea y si no en cualquiera (si no
    es ambigua)."""
    conjunto = set(regiones) | {_VECINAS[r] for r in regiones if r in _VECINAS}
    for filtro in ([frozenset(conjunto)] if conjunto else []) + [None]:
        for h in _nomenclator().localidades_en(nombre, filtro, contexto):
            if h.lugar is not None and h.lugar.pais == "UA":
                radio = max(h.lugar.radio_km, 5.0)
                return Zona(h.lugar.lat, h.lugar.lon, radio, "localidad", nombre, h.lugar.region)
    return None


def _regiones_de(texto: str) -> list[str]:
    return [c for c in parte.regiones_en(texto, _vocabulario()) if c.startswith("UA-")]


def leer_linea(linea: str, contexto: str) -> Aviso | None:
    bajo = linea.lower()
    if not _DRON.search(bajo) or _NO_DRON.search(bajo):
        return None
    tipo = (
        "reaccion"
        if _REACCION.search(bajo)
        else "reconocimiento"
        if _RECONOCIMIENTO.search(bajo) and "ударн" not in bajo
        else "ataque"
    )
    regiones = _regiones_de(linea)
    numero = None
    if m := _NUMERO.search(bajo):
        n = int(m.group(1))
        numero = (n, n)
    aviso = Aviso(linea.strip(), tipo, bool(_GRUPO.search(bajo)), numero, regiones=regiones)
    # Rumbo: dirección escrita, o el contrario de «de dónde viene».
    if m := _CURSO_PALABRA.search(bajo):
        aviso.rumbo = _grados(m.group(1) or m.group(2))
    m = _DESDE.search(bajo)
    if m is not None and linea[m.end() :].strip()[:1].isupper():
        m = None  # «з півночі Дніпропетровщини»: de qué parte, no de qué dirección
    if aviso.rumbo is None and m is not None:
        desde = _DESDE_GRADOS.get(" ".join(m.group(1).split()))
        if desde is not None:
            aviso.rumbo = (desde + 180.0) % 360.0
    # Destino: la primera localidad tras «курсом на», «в напрямку»…
    for m in _DESTINO.finditer(linea):
        nombre = m.group(1)
        if _grados(nombre.lower()) is not None:
            continue
        destinos = _regiones_de(nombre)
        if destinos and _LOCATIVO.search(nombre):
            # «на Харківщині»: dónde está, no adónde va.
            continue
        if destinos:
            aviso.destino = zona_de_region(destinos[0], texto=nombre)
        else:
            aviso.destino = _localidad(nombre, regiones, contexto)
        if aviso.destino is not None:
            break
    # Zona: una localidad nombrada como posición, una parte de región, el mar o la región.
    if m := _POSICION.search(linea):
        aviso.zona = _localidad(m.group(1), regiones, contexto)
    if aviso.zona is None and (m := _PARTE.search(linea)):
        en = _regiones_de(m.group(2))
        if en:
            aviso.zona = zona_de_region(
                en[0], _PARTE_GRADOS.get(" ".join(m.group(1).split())), m.group(0)
            )
    if (
        aviso.zona is None
        and _MAR.search(bajo)
        and re.search(r"\bз[іи]?\s+\S*\s*(?:чорн|акват)", bajo)
    ):
        aviso.zona = Zona(
            MAR_NEGRO["lat"], MAR_NEGRO["lon"], MAR_NEGRO["radio_km"], "mar", "Чорне море"
        )
    if aviso.zona is None and regiones:
        # La primera región que no es el destino: donde está ahora.
        destino_region = aviso.destino.region if aviso.destino else None
        for iso in regiones:
            if iso != destino_region or len(regiones) == 1:
                aviso.zona = zona_de_region(iso, texto=iso)
                break
    if aviso.zona is None and aviso.destino is None:
        return None
    return aviso


def leer(texto: str) -> list[Aviso]:
    """Los avisos de un mensaje: uno por línea que habla de drones con lugar."""
    lineas = [x for x in _LINEAS.split(texto) if x.strip()]
    avisos = []
    for linea in lineas:
        aviso = leer_linea(linea, texto)
        if aviso is not None:
            avisos.append(aviso)
    return avisos


def es_seguimiento(texto: str) -> bool:
    """Un mensaje de seguimiento corto (no un parte de la mañana con sus cifras)."""
    return len(texto) < 700 and not parte.es_parte(texto) and bool(_DRON.search(texto.lower()))


def leer_mensajes(mensajes: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """(id, fecha, texto) → los mensajes de seguimiento con sus avisos."""
    salida = []
    for m in mensajes:
        if not es_seguimiento(m["texto"]):
            continue
        avisos = leer(m["texto"])
        if avisos:
            salida.append(
                {"id": m["id"], "fecha": m["fecha"], "avisos": [a.documento() for a in avisos]}
            )
    return salida
