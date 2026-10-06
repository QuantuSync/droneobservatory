"""Lugares concretos de la capa de guerra: localidades e instalaciones de Ucrania y de la
Rusia europea en el texto de un mensaje.

El nomenclátor (`configuracion/nomenclator_guerra.json.gz`, generado por
`recogida/nomenclator_guerra.py`) da cada localidad con sus nombres en ucraniano, ruso y
latino, su región ISO 3166-2, su distrito y su comunidad, y cada instalación con su
categoría. Aquí se buscan en el texto con todas sus formas declinadas
(`proceso/declinacion.py`) y se resuelven con estas reglas, que salen de los errores del
nomenclátor europeo («La Guardia», «Ucrania», «Moldova»):

1. Ningún nombre que coincida con un país, una región o una institución.
2. El nombre tiene que empezar por mayúscula en el texto. Si además es una palabra
   corriente (sale en minúscula en los mensajes: «мирне», «перемога», «дружба»), tiene que
   ir precedido de su tipo de lugar («село», «смт», «с.», «селище», «місто», «м.»,
   «поселок», «пос.», «хутор»…).
3. Solo se buscan localidades de la región del mensaje: la del canal (una administración
   regional, un gobernador) o, en los canales de todo el país, la región que el propio
   mensaje nombra en la misma frase. Una localidad de otra región no sale.
4. Un nombre que llevan varias localidades de esa región se resuelve con el distrito
   («Чугуївський район») o la comunidad («Куп'янська громада») que nombre el mensaje; si
   no, con la única ciudad frente a aldeas homónimas («Запоріжжя»); si siguen siendo
   varias, queda sin resolver.
5. Una palabra seguida de «район», «громада», «область» u «округ» es una unidad
   administrativa, no la localidad.

Una instalación se reconoce por su tipo en el texto («НПЗ», «нафтобаза», «підстанція»,
«ТЕЦ», «аеродром»…) con su nombre entre comillas («НПЗ «Новокуйбышевский»»), con la
localidad en la misma frase o con el adjetivo de la localidad («Рязанский НПЗ»): si hay
una sola instalación de ese tipo en esa localidad, el lugar es la instalación; si no, la
localidad.
"""

import gzip
import json
import math
import os
import re
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field, replace
from functools import cache
from pathlib import Path
from typing import Any

from proceso.declinacion import formas
from proceso.noticias import sin_acentos

RAIZ = Path(__file__).resolve().parent.parent
NOMENCLATOR = RAIZ / "configuracion" / "nomenclator_guerra.json.gz"
COMUNES = RAIZ / "configuracion" / "palabras_comunes_guerra.json"
CONTORNOS_UA = RAIZ / "web" / "public" / "mapa" / "ucrania-regiones.geojson"
KM_POR_GRADO = 111.2
# El contorno público de los óblasts está simplificado: hasta 10 km fuera se da por dentro.
MARGEN_CONTORNO_KM = 10.0
# Radio del lugar por tipo de instalación: lo que ocupa (una refinería, unos 3 km de lado; un
# depósito o una estación, uno o dos; una subestación, unos cientos de metros).
CATEGORIAS_INSTALACION: dict[str, float] = {
    "refineria": 3.0, "deposito_combustible": 1.5, "central": 2.0, "subestacion": 1.0,
    "aerodromo": 4.0, "puerto": 3.0, "militar": 3.0, "ferrocarril": 1.5, "industrial": 2.0,
}  # fmt: skip
# Distancia máxima de una instalación a la localidad con que se nombra («НПЗ в Рязани»):
# las refinerías y los aeródromos suelen estar a las afueras.
DISTANCIA_INSTALACION_KM = 20.0
# Máximo de palabras de un nombre de lugar.
MAX_PALABRAS = 4

# Países, regiones e instituciones: nunca son el nombre de una localidad. Se comparan
# normalizados (PROHIBIDOS).
NOMBRES_PROHIBIDOS = frozenset(
    {
        "україна", "украина", "ukraine", "ukraina", "росія", "россия", "russia", "рф",
        "молдова", "молдавия", "moldova", "білорусь", "беларусь", "белоруссия", "польща",
        "польша", "румунія", "румыния", "угорщина", "венгрия", "словаччина", "словакия",
        "грузія", "грузия", "європа", "европа", "крим", "крым", "донбас", "донбасс",
        "сили оборони", "зсу", "всу", "ппо", "пво", "дснс", "мчс", "сбу", "фсб", "укренерго",
        "нафтогаз", "укрзалізниця", "ржд", "газпром", "роснефть", "лукоил", "транснефть",
        "нато", "оон", "ес", "сша", "америка", "москва-сити",
    }
)  # fmt: skip
# Tipos de lugar que preceden al nombre: con ellos una palabra corriente vale.
_TIPO_LUGAR = (
    r"(?:село|селі|села|селище|селищі|смт|с|м|місто|місті|міста|сел|"
    r"поселок|поселке|посёлок|посёлке|пос|п|хутор|хуторе|хутір|деревня|деревне|станица|"
    r"станице|ст|город|городе|г|рабочий поселок|рп|пгт|н\.п|нп|населений пункт)"
)
TIPO_LUGAR = re.compile(r"(?:^|[\s(«\"])" + _TIPO_LUGAR + r"\.?\s*$", re.IGNORECASE)
# Un nombre de persona tras su cargo («Голова Одеської ОДА Олег Кіпер»: Олег también es una
# aldea): el cargo poco antes y un apellido con mayúscula justo después.
_CARGO = re.compile(
    r"(?:голова|голови|начальник\w*|очільник\w*|губернатор\w*|заступник\w*|керівник\w*|"
    r"міністр\w*|президент\w*|глава|главы|мер|мера|мером|мэр\w*)\b[^.!?\n]{0,50}$",
    re.IGNORECASE,
)
_APELLIDO = re.compile(r"^\s+[А-ЯІЇЄҐЁ][а-яіїєґё'’ʼ]+")
# La palabra siguiente dice que es una unidad administrativa.
_ADMINISTRATIVA = re.compile(
    r"^\s*(?:район|районі|району|районе|районом|районов|районах|районів|громад|тг\b|"
    r"тергромад|територіальн\w*\s+громад|област|"
    r"обл\b|обл\.|округ|муніципальн|муниципальн|городск\w+ округ|міськ\w+ громад|"
    r"сільськ\w+ громад|селищн\w+ громад)",
    re.IGNORECASE,
)
# Un adjetivo de distrito en una lista: «Новоспасского и Сенгилеевского районов».
_ADJETIVO_DISTRITO = re.compile(r"(?:ськ|цьк|зьк|ск|цк)\w*$", re.IGNORECASE)
_LISTA_DISTRITOS = re.compile(
    r"^(?:\s*(?:,|и|та|і|й)\s*[^\W\d_]+(?:ськ|цьк|зьк|ск|цк)\w*)+\s*(?:район|р-н)",
    re.IGNORECASE,
)
_PALABRA = re.compile(r"[^\W\d_]+(?:['’ʼ][^\W\d_]+)*")
_RAION = re.compile(
    r"(?<![\w'])([^\W\d_]+?)(?:ськ|цьк|зьк|ск|цк)\w*\s+(?:район|р-н|р-ну|р-ні|районі|району|районе|района)",
    re.IGNORECASE,
)
_HROMADA = re.compile(
    r"(?<![\w'])([^\W\d_]+?)(?:ськ|цьк|зьк|ськ|івськ|инськ)?\w*\s+"
    r"(?:громад|тг\b|ОТГ|тергромад|територіальн\w*\s+громад)",
    re.IGNORECASE,
)
# Comunidades y distritos como lugar: una lista de adjetivos con mayúscula delante de
# «громада» o «район» («Марганецькій, Покровській та Мирівській громадам», «по Одеському
# району»), o el distrito en «-щина» («на Нікопольщині»).
_ADJ_UNIDAD = r"[А-ЯІЇЄҐ][\w'’-]*?(?:ськ|цьк|зьк)\w*"
_ADJETIVO_UNIDAD = re.compile(_ADJ_UNIDAD)
_LISTA_UNIDADES = r"(" + _ADJ_UNIDAD + r"(?:\s*(?:,|та|і|й|и)\s*" + _ADJ_UNIDAD + r")*)"
_LISTA_HROMADAS = re.compile(
    _LISTA_UNIDADES
    + r"\s+(?:(?:сільськ|селищн|міськ)\w*\s+)?"
    # «Бобрицькій тергромаді», «Канівській територіальній громаді» (Черкащина, Вінниччина).
    + r"(?:громад\w*|ТГ\b|ОТГ\b|тергромад\w*|територіальн\w*\s+громад\w*)"
)
_LISTA_RAIONES = re.compile(_LISTA_UNIDADES + r"\s+(?:район\w*|р-н\w*)")
_SHCHYNA = re.compile(r"(?<![\w'’-])[А-ЯІЇЄҐ][\w'’-]+щин(?:а|і|у|ою|и)\b")
# Una comunidad más ancha que esto no es un lugar concreto. Los distritos no tienen tope: si el
# mensaje solo nombra el distrito («в Одеському районі», «Ізмаїльський район»), el lugar es el
# distrito con su radio real (los de 2020 miden de 30 a más de 100 km), con nivel «distrito»
# para que nadie lo lea como una localidad.
RADIO_MAX_UNIDAD_KM = 50.0

# Tipo de instalación en el texto → categoría del nomenclátor.
TIPOS_INSTALACION: tuple[tuple[re.Pattern[str], str], ...] = tuple(
    (re.compile(patron, re.IGNORECASE), categoria)
    for patron, categoria in (
        (r"\bНПЗ\b|нафтопереробн\w*|нефтеперерабат\w*|нафтоперероб\w*", "refineria"),
        (r"нафтобаз\w*|нефтебаз\w*|паливн\w+\s+(?:склад|баз)\w*|\bПММ\b|\bГСМ\b|\bЛПДС\b|"
         r"\bНПС\b|нафтоналивн\w*|нефтеналивн\w*|нафтотермінал\w*|нефтетерминал\w*",
         "deposito_combustible"),
        (r"\bТЕС\b|\bТЕЦ\b|\bГЕС\b|\bТЭЦ\b|\bГРЭС\b|\bТЭС\b|\bГЭС\b|\bАЕС\b|\bАЭС\b|"
         r"електростанц\w*|электростанц\w*", "central"),
        (r"підстанці\w*|подстанци\w*", "subestacion"),
        (r"аеродром\w*|аэродром\w*|аеропорт\w*|аэропорт\w*|авіабаз\w*|авиабаз\w*", "aerodromo"),
        (r"\bпорт(?:у|і|ом|а|е)?\b|морськ\w+\s+порт\w*|морск\w+\s+порт\w*|термінал\w*|"
         r"терминал\w*", "puerto"),
        (r"залізничн\w+\s+(?:станц|вузл)\w*|\bж/д\s+станц\w*|железнодорожн\w+\s+(?:станц|узл)\w*|"
         r"\bдепо\b|вокзал\w*", "ferrocarril"),
        (r"\bзавод\w*|комбінат\w*|комбинат\w*", "industrial"),
    )
)  # fmt: skip


def normalizar(texto: str) -> str:
    """Minúsculas, sin acentos, sin apóstrofos ni puntuación y con los espacios simples: «й»
    queda «и», «ї» queda «і», «ё» queda «е»."""
    limpio = re.sub(r"[^\w\s]", " ", sin_acentos(texto).lower())
    return " ".join(limpio.split())


PROHIBIDOS = frozenset(normalizar(n) for n in NOMBRES_PROHIBIDOS)


def radio_localidad(categoria: str, poblacion: int) -> float:
    """Radio del lugar: lo que ocupa la localidad, por su población o su categoría."""
    if poblacion >= 1_000_000:
        return 15.0
    if poblacion >= 300_000:
        return 10.0
    if poblacion >= 100_000:
        return 7.0
    if poblacion >= 50_000:
        return 5.0
    if poblacion >= 10_000 or categoria == "ciudad":
        return 4.0
    if categoria == "asentamiento":
        return 2.5
    return 1.5


# --- Contornos de los óblasts -----------------------------------------------------------


def _distancia_segmento_km(
    lat: float, lon: float, a: tuple[float, float], b: tuple[float, float]
) -> float:
    escala = math.cos(math.radians(lat))
    ax, ay = (a[0] - lon) * escala, a[1] - lat
    bx, by = (b[0] - lon) * escala, b[1] - lat
    dx, dy = bx - ax, by - ay
    largo = dx * dx + dy * dy
    t = 0.0 if largo == 0 else max(0.0, min(1.0, -(ax * dx + ay * dy) / largo))
    return math.hypot(ax + t * dx, ay + t * dy) * KM_POR_GRADO


def _en_anillo(lon: float, lat: float, anillo: list[list[float]]) -> bool:
    dentro = False
    anterior = anillo[-1]
    for actual in anillo:
        (x1, y1), (x2, y2) = anterior[:2], actual[:2]
        if (y1 > lat) != (y2 > lat) and lon < (x2 - x1) * (lat - y1) / (y2 - y1) + x1:
            dentro = not dentro
        anterior = actual
    return dentro


@dataclass(frozen=True)
class Contornos:
    """Contornos de los óblasts de Ucrania (con Crimea y Sebastopol), por código ISO."""

    poligonos: dict[str, tuple[list[list[list[float]]], ...]]

    @classmethod
    def cargar(cls, ruta: Path = CONTORNOS_UA) -> "Contornos":
        datos = json.loads(ruta.read_text(encoding="utf-8"))
        poligonos: dict[str, list[list[list[list[float]]]]] = defaultdict(list)
        for rasgo in datos["features"]:
            geometria = rasgo["geometry"]
            lista = (
                [geometria["coordinates"]] if geometria["type"] == "Polygon"
                else geometria["coordinates"]
            )  # fmt: skip
            poligonos[rasgo["properties"]["iso"]] += lista
        return cls({k: tuple(v) for k, v in poligonos.items()})

    def _contiene(self, region: str, lat: float, lon: float) -> bool:
        return any(
            _en_anillo(lon, lat, p[0]) and not any(_en_anillo(lon, lat, h) for h in p[1:])
            for p in self.poligonos.get(region, ())
        )

    def distancia_km(self, region: str, lat: float, lon: float) -> float:
        """0 dentro del contorno; fuera, la distancia a su borde."""
        if self._contiene(region, lat, lon):
            return 0.0
        mejor = math.inf
        for poligono in self.poligonos.get(region, ()):
            for anillo in poligono:
                anterior = anillo[-1]
                for actual in anillo:
                    mejor = min(
                        mejor,
                        _distancia_segmento_km(
                            lat, lon, (anterior[0], anterior[1]), (actual[0], actual[1])
                        ),
                    )
                    anterior = actual
        return mejor

    def dentro(self, region: str, lat: float, lon: float) -> bool:
        """El punto cae en el óblast (con el margen del contorno simplificado). De una región
        que no es de Ucrania no hay contorno: no se comprueba aquí."""
        if region not in self.poligonos:
            return True
        return self.distancia_km(region, lat, lon) <= MARGEN_CONTORNO_KM

    def region_de(self, lat: float, lon: float, pais: str) -> str | None:
        """La región de Ucrania que contiene el punto, o None si no cae en ninguna."""
        if pais != "UA":
            return None
        for region in self.poligonos:
            if self._contiene(region, lat, lon):
                return region
        return None


# --- Nomenclátor --------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Lugar:
    id: str
    nombre: str
    nivel: str  # localidad o instalacion
    pais: str
    region: str
    lat: float
    lon: float
    radio_km: float
    categoria: str
    nombre_latino: str | None = None
    raion: str | None = None
    hromada: str | None = None
    # La localidad con que se nombró la instalación, si fue así.
    localidad: str | None = None
    oaci: str | None = None

    def documento(self) -> dict[str, Any]:
        documento: dict[str, Any] = {
            "id": self.id,
            "nombre": self.nombre,
            "nivel": self.nivel,
            "punto": {"lat": self.lat, "lon": self.lon},
            "radio_km": self.radio_km,
        }
        if self.nombre_latino:
            documento["nombre_latino"] = self.nombre_latino
        if self.nivel == "instalacion":
            documento["categoria"] = self.categoria
            if self.localidad:
                documento["localidad"] = self.localidad
        return documento


@dataclass(frozen=True)
class Hallazgo:
    """Un lugar del texto: resuelto (lugar) o no (candidatos y motivo)."""

    texto: str
    inicio: int
    fin: int
    lugar: Lugar | None
    motivo: str | None = None
    candidatos: tuple[str, ...] = ()


@dataclass
class Nomenclator:
    localidades: dict[str, Lugar]
    instalaciones: dict[str, Lugar]
    # Forma normalizada → posición (o posiciones) en `lista` de las localidades que la llevan.
    # Enteros y tuplas, no conjuntos de cadenas: con casi dos millones de formas, la diferencia
    # son cientos de megas en la recogida horaria.
    lista: list[Lugar] = field(default_factory=list)
    indice: dict[str, int | tuple[int, ...]] = field(default_factory=dict)
    # Nombre normalizado de instalación → ids.
    indice_instalaciones: dict[str, set[str]] = field(default_factory=lambda: defaultdict(set))
    nombres_instalacion: dict[str, list[str]] = field(default_factory=dict)
    comunes: frozenset[str] = frozenset()
    # Raíz del distrito o la comunidad, normalizada → ids de localidad.
    por_raion: dict[str, set[str]] = field(default_factory=lambda: defaultdict(set))
    por_hromada: dict[str, set[str]] = field(default_factory=lambda: defaultdict(set))
    # Raíz del distrito urbano → (región, id de la ciudad).
    distritos: dict[str, set[tuple[str, str]]] = field(default_factory=lambda: defaultdict(set))
    _ciudades: list[tuple[Lugar, tuple[str, ...]]] = field(default_factory=list)
    # (tipo, base del nombre) → comunidades o distritos con su centro (se calcula una vez).
    _unidades: dict[tuple[str, str], list[Lugar]] = field(default_factory=lambda: defaultdict(list))

    @classmethod
    def desde_datos(cls, datos: dict[str, Any], comunes: Iterable[str] = ()) -> "Nomenclator":
        nomenclator = cls({}, {}, comunes=frozenset(comunes))
        for entrada in datos["localidades"]:
            nomenclator._anadir_localidad(entrada)
        for entrada in datos.get("instalaciones", []):
            nomenclator._anadir_instalacion(entrada)
        for distrito in datos.get("distritos_urbanos", []):
            if distrito["ciudad"] in nomenclator.localidades:
                nomenclator.distritos[raiz_administrativa(distrito["nombre"])].add(
                    (distrito["region"], distrito["ciudad"])
                )
        return nomenclator

    def _anadir_localidad(self, e: dict[str, Any]) -> None:
        nombres: dict[str, list[str]] = e["nombres"]
        lugar = Lugar(
            id=e["id"], nombre=e["nombre"], nivel="localidad", pais=e["pais"],
            region=e["region"], lat=e["lat"], lon=e["lon"], radio_km=e["radio_km"],
            categoria=e["categoria"], nombre_latino=_primero(nombres.get("la")),
            raion=e.get("raion"), hromada=e.get("hromada"),
        )  # fmt: skip
        self.localidades[lugar.id] = lugar
        posicion = len(self.lista)
        self.lista.append(lugar)
        todas: set[str] = set()
        for idioma, lista in nombres.items():
            # De las aldeas rusas, solo los nombres rusos: las variantes en otras lenguas
            # (bielorruso, ucraniano) solo las tienen las ciudades que alguien escribe así.
            if lugar.pais == "RU" and lugar.categoria != "ciudad" and idioma == "uk":
                continue
            for nombre in lista:
                if idioma == "la":
                    todas.add(nombre.lower())
                elif idioma == "cy":
                    todas |= formas(nombre, "ru")
                    if lugar.pais == "UA":
                        todas |= formas(nombre, "uk")
                else:
                    todas |= formas(nombre, idioma)
        for forma in todas:
            normal = normalizar(forma)
            if normal and normal not in PROHIBIDOS and len(normal) >= 3:
                previo = self.indice.get(normal)
                if previo is None:
                    self.indice[normal] = posicion
                elif isinstance(previo, int):
                    if previo != posicion:
                        self.indice[normal] = (previo, posicion)
                elif posicion not in previo:
                    self.indice[normal] = (*previo, posicion)
        for clave, destino in ((e.get("raion"), self.por_raion), (e.get("hromada"),
                                                                   self.por_hromada)):  # fmt: skip
            if clave:
                destino[raiz_administrativa(clave)].add(lugar.id)

    def _anadir_instalacion(self, e: dict[str, Any]) -> None:
        nombres: dict[str, list[str]] = e["nombres"]
        principal = (nombres.get("uk") or nombres.get("ru") or nombres.get("cy")
                     or nombres.get("la") or [e["osm"]])[0]  # fmt: skip
        lugar = Lugar(
            id=f"osm:{e['osm']}", nombre=principal, nivel="instalacion", pais=e["pais"],
            region=e["region"], lat=e["lat"], lon=e["lon"], radio_km=e["radio_km"],
            categoria=e["categoria"], nombre_latino=_primero(nombres.get("la")),
            oaci=e.get("oaci"),
        )  # fmt: skip
        self.instalaciones[lugar.id] = lugar
        normales = sorted({normalizar(n) for lista in nombres.values() for n in lista})
        self.nombres_instalacion[lugar.id] = normales
        for nombre in normales:
            self.indice_instalaciones[nombre].add(lugar.id)

    # --- Búsqueda --------------------------------------------------------------------

    def localidades_en(
        self, texto: str, regiones: frozenset[str] | None, contexto: str | None = None
    ) -> list[Hallazgo]:
        """Las localidades que nombra el texto, de las regiones dadas (None: cualquiera). Los
        distritos y comunidades que deshacen homónimos se toman del texto y de `contexto` (el
        mensaje entero), también el distrito en «-щина» («в Пушкарях на Новгород-Сіверщині»)."""
        palabras = [(m.start(), m.end(), m.group(0)) for m in _PALABRA.finditer(texto)]
        normales = [normalizar(p) for _, _, p in palabras]
        pistas = texto if contexto is None else texto + "\n" + contexto
        raiones = {raiz_administrativa(m.group(0).split()[0]) for m in _RAION.finditer(pistas)}
        raiones |= {raiz_administrativa(m.group(0)) for m in _SHCHYNA.finditer(pistas)}
        hromadas = {raiz_administrativa(m.group(0).split()[0]) for m in _HROMADA.finditer(pistas)}
        hallazgos: list[Hallazgo] = self._distritos_en(texto, regiones)
        i = 0
        while i < len(palabras):
            encontrado = None
            for largo in range(min(MAX_PALABRAS, len(palabras) - i), 0, -1):
                forma = " ".join(normales[i : i + largo])
                posiciones = self.indice.get(forma)
                if posiciones is not None:
                    encontrado = (
                        largo, forma,
                        (posiciones,) if isinstance(posiciones, int) else posiciones,
                    )  # fmt: skip
                    break
            if encontrado is None:
                i += 1
                continue
            largo, forma, ids = encontrado
            inicio, fin = palabras[i][0], palabras[i + largo - 1][1]
            i += largo
            original = texto[inicio:fin]
            if not original[:1].isupper():
                continue
            # Parte de un nombre compuesto que no es este lugar («Хутір-Михайлівська громада»).
            if texto[fin : fin + 1] == "-" or texto[max(0, inicio - 1) : inicio] == "-":
                continue
            if _ADMINISTRATIVA.match(texto[fin:]):
                continue
            if _ADJETIVO_DISTRITO.search(original) and _LISTA_DISTRITOS.match(texto[fin:]):
                continue
            if forma in self.comunes and not TIPO_LUGAR.search(texto[max(0, inicio - 25) : inicio]):
                continue
            if _CARGO.search(texto[max(0, inicio - 60) : inicio]) and _APELLIDO.match(texto[fin:]):
                continue
            candidatos = sorted((self.lista[x] for x in ids), key=lambda c: c.id)
            if regiones is not None:
                candidatos = [c for c in candidatos if c.region in regiones]
            if not candidatos:
                continue
            if len(candidatos) > 1:
                candidatos = _desambiguar(candidatos, raiones, hromadas, self)
            if len(candidatos) == 1:
                hallazgos.append(Hallazgo(original, inicio, fin, candidatos[0]))
            else:
                hallazgos.append(
                    Hallazgo(
                        original, inicio, fin, None, "ambiguo", tuple(c.id for c in candidatos)
                    )
                )
        return hallazgos

    def _distritos_en(self, texto: str, regiones: frozenset[str] | None) -> list[Hallazgo]:
        """«У Київському районі» en un mensaje de Járkov: la ciudad cuyo distrito urbano lleva
        ese nombre, si es una sola en las regiones y ningún distrito rural se llama así."""
        hallazgos = []
        for m in _RAION.finditer(texto):
            adjetivo = m.group(0).split()[0]
            raiz = raiz_administrativa(adjetivo)
            ciudades = {
                c for r, c in self.distritos.get(raiz, set()) if regiones is None or r in regiones
            }
            rurales = [
                x for x in self.por_raion.get(raiz, set())
                if regiones is None or self.localidades[x].region in regiones
            ]  # fmt: skip
            if len(ciudades) == 1 and not rurales and adjetivo[:1].isupper():
                ciudad = self.localidades[next(iter(ciudades))]
                hallazgos.append(Hallazgo(m.group(0), m.start(), m.end(), ciudad))
        return hallazgos

    def instalacion(
        self,
        categoria: str,
        regiones: frozenset[str] | None,
        cerca_de: Lugar | None = None,
        nombre: str | None = None,
    ) -> Lugar | None:
        """La única instalación de esa categoría con ese nombre (entre comillas en el texto) o
        a menos de DISTANCIA_INSTALACION_KM de la localidad; None si no hay una sola."""
        candidatos = [
            i for i in self.instalaciones.values()
            if i.categoria == categoria and (regiones is None or i.region in regiones)
        ]  # fmt: skip
        if nombre:
            raices = [p[:5] for p in normalizar(nombre).split() if len(p) >= 4]
            if raices:
                por_nombre = [
                    c for c in candidatos
                    if any(all(r in n for r in raices) for n in self._nombres_de(c.id))
                ]  # fmt: skip
                if cerca_de is not None:
                    por_nombre = [
                        c for c in por_nombre if _km(c, cerca_de) <= DISTANCIA_INSTALACION_KM
                    ]
                if len(por_nombre) == 1:
                    return _con_localidad(por_nombre[0], cerca_de)
                if por_nombre:
                    return None
        if cerca_de is None:
            return None
        cerca = [c for c in candidatos if _km(c, cerca_de) <= DISTANCIA_INSTALACION_KM]
        return _con_localidad(cerca[0], cerca_de) if len(cerca) == 1 else None

    def _nombres_de(self, id_: str) -> list[str]:
        return self.nombres_instalacion.get(id_, [])

    def localidad_por_adjetivo(
        self, adjetivo: str, regiones: frozenset[str] | None
    ) -> Lugar | None:
        """«Рязанский», «Саратовського», «Новокуйбышевский» → la ciudad (una sola en las
        regiones) cuyo nombre empieza por la raíz del adjetivo. La raíz con el signo blando del
        adjetivo vale también sin él: «Ізмаїльського» → Ізмаїл."""
        raiz = raiz_adjetivo(adjetivo)
        if len(raiz) < 4:
            return None
        raices = {raiz, raiz.removesuffix("ь")}
        ciudades = {
            c.id: c for c, nombres in self._nombres_ciudades()
            if (regiones is None or c.region in regiones)
            and any(n.startswith(r) or n == r for n in nombres for r in raices)
        }  # fmt: skip
        return next(iter(ciudades.values())) if len(ciudades) == 1 else None

    # --- Comunidades y distritos ------------------------------------------------------

    def unidades_en(
        self, texto: str, regiones: frozenset[str] | None, contexto: str | None = None
    ) -> list[Hallazgo]:
        """Las comunidades («Марганецькій, Покровській громадам», «Краснопільська громада»)
        y los distritos rurales («по Одеському району», «Нікопольщина») que nombra el texto,
        como lugar de nivel comunidad o distrito: su centro y el radio que abarca. Solo en
        Ucrania (las localidades rusas no traen distrito). Una comunidad que abarca más de
        RADIO_MAX_UNIDAD_KM, o el distrito en «-щина» que lleva el nombre de la capital del
        óblast («Сумщина», «Одещина» son el óblast), no sale. `contexto` (el mensaje) da los
        distritos que deshacen dos comunidades del mismo nombre."""
        hallazgos: list[Hallazgo] = []
        # Distritos que nombra el texto: deshacen dos comunidades del mismo nombre.
        todo = contexto or texto
        pistas = {base_unidad(a.group(0)) for m in _LISTA_RAIONES.finditer(todo)
                  for a in _ADJETIVO_UNIDAD.finditer(m.group(1))}  # fmt: skip
        pistas |= {base_unidad(m.group(0)) for m in _SHCHYNA.finditer(todo)}
        for patron, tipo in ((_LISTA_HROMADAS, "comunidad"), (_LISTA_RAIONES, "distrito")):
            for m in patron.finditer(texto):
                for a in _ADJETIVO_UNIDAD.finditer(m.group(1)):
                    if tipo == "distrito" and self._es_distrito_urbano(a.group(0), regiones):
                        continue
                    lugar = self.unidad(tipo, base_unidad(a.group(0)), regiones, pistas)
                    inicio = m.start(1) + a.start()
                    if lugar is not None:
                        hallazgos.append(Hallazgo(a.group(0), inicio, inicio + len(a.group(0)),
                                                  lugar))  # fmt: skip
        for m in _SHCHYNA.finditer(texto):
            lugar = self.unidad("distrito", base_unidad(m.group(0)), regiones)
            if lugar is not None and not self._es_capital(lugar, regiones):
                hallazgos.append(Hallazgo(m.group(0), m.start(), m.end(), lugar))
        return hallazgos

    def _es_distrito_urbano(self, adjetivo: str, regiones: frozenset[str] | None) -> bool:
        return any(
            regiones is None or r in regiones
            for r, _ in self.distritos.get(raiz_administrativa(adjetivo), set())
        )

    def _es_capital(self, unidad: Lugar, regiones: frozenset[str] | None) -> bool:
        """El distrito cuyo centro es la mayor ciudad del óblast: «Сумщина» es el óblast."""
        ciudades = [
            c for c in self.localidades.values()
            if c.region == unidad.region and c.categoria == "ciudad"
        ]  # fmt: skip
        mayor = max(ciudades, key=lambda c: (c.radio_km, c.id), default=None)
        return mayor is not None and unidad.id == f"{mayor.id}:distrito"

    def unidad(
        self, tipo: str, base: str, regiones: frozenset[str] | None,
        distritos: set[str] | frozenset[str] = frozenset(),
    ) -> Lugar | None:  # fmt: skip
        """La comunidad o el distrito de esa base en las regiones (uno solo), con su centro:
        la localidad que lleva su nombre («Краснопільська громада» → Краснопілля)."""
        if len(base) < 3:
            return None
        if not self._unidades:
            self._indexar_unidades()
        candidatas = [
            u for u in self._unidades.get((tipo, base), [])
            if regiones is None or u.region in regiones
        ]  # fmt: skip
        if len(candidatas) > 1 and distritos:
            candidatas = [u for u in candidatas if u.raion and base_unidad(u.raion) in distritos]
        return candidatas[0] if len(candidatas) == 1 else None

    def _indexar_unidades(self) -> None:
        grupos: dict[tuple[str, str, str, str], list[Lugar]] = defaultdict(list)
        for lugar in self.localidades.values():
            if lugar.pais != "UA":
                continue
            if lugar.hromada:
                grupos[("comunidad", lugar.region, lugar.raion or "", lugar.hromada)].append(lugar)
            if lugar.raion:
                grupos[("distrito", lugar.region, "", lugar.raion)].append(lugar)
        for (tipo, region, _, nombre), miembros in grupos.items():
            base = base_unidad(nombre)
            centro = _centro(base, miembros)
            if centro is None:
                continue
            alcance = max(_km(centro, m) + m.radio_km for m in miembros)
            if tipo == "comunidad" and alcance > RADIO_MAX_UNIDAD_KM:
                continue
            sufijo = "громада" if tipo == "comunidad" else "район"
            latino = f"{centro.nombre_latino} {'hromada' if tipo == 'comunidad' else 'raion'}"
            self._unidades[(tipo, base)].append(
                Lugar(
                    id=f"{centro.id}:{tipo}",
                    nombre=f"{nombre} {sufijo}",
                    nivel=tipo,
                    pais="UA",
                    region=region,
                    lat=centro.lat,
                    lon=centro.lon,
                    radio_km=round(max(alcance, centro.radio_km), 1),
                    categoria=tipo,
                    nombre_latino=latino if centro.nombre_latino else None,
                    raion=centro.raion,
                    hromada=centro.hromada if tipo == "comunidad" else None,
                )
            )

    def _nombres_ciudades(self) -> list[tuple[Lugar, tuple[str, ...]]]:
        """Las ciudades con sus nombres normalizados de una palabra (se calcula una vez)."""
        if not self._ciudades:
            nombres: dict[int, set[str]] = defaultdict(set)
            for forma, posiciones in self.indice.items():
                if " " in forma:
                    continue
                for x in (posiciones,) if isinstance(posiciones, int) else posiciones:
                    if self.lista[x].categoria == "ciudad":
                        nombres[x].add(forma)
            self._ciudades.extend((self.lista[x], tuple(sorted(n))) for x, n in nombres.items())
        return self._ciudades


def _primero(lista: list[str] | None) -> str | None:
    return lista[0] if lista else None


def _km(a: Lugar, b: Lugar) -> float:
    f1, f2 = math.radians(a.lat), math.radians(b.lat)
    df, dl = f2 - f1, math.radians(b.lon - a.lon)
    h = math.sin(df / 2) ** 2 + math.cos(f1) * math.cos(f2) * math.sin(dl / 2) ** 2
    return 2 * 6371.0088 * math.asin(math.sqrt(h))


def _con_localidad(instalacion: Lugar, localidad: Lugar | None) -> Lugar:
    if localidad is None:
        return instalacion
    return replace(instalacion, localidad=localidad.nombre)


def raiz_administrativa(nombre: str) -> str:
    """Raíz de un distrito o una comunidad para compararla con lo que dice el mensaje: las
    seis primeras letras normalizadas («Чугуївський», «Чугуївського» → «чугуїв»)."""
    return normalizar(nombre).replace(" ", "")[:6]


_FINALES_ADJETIVO = re.compile(
    r"(?:ськ|цьк|зьк|ск|цк)(?:ий|ого|ому|им|ім|ой|ая|ую|ій|ої|ом|ыи|ии|ои|их|ых|ому)?$"
)


def raiz_adjetivo(adjetivo: str) -> str:
    """«рязанский» → «рязан»; «саратовського» → «саратов»."""
    normal = normalizar(adjetivo)
    return _FINALES_ADJETIVO.sub("", normal)


def base_unidad(nombre: str) -> str:
    """Base del nombre de una comunidad o un distrito, igual en todos sus casos y en su forma
    en «-щина»: «Краснопільській» y «Краснопільська» → «краснопіль»; «Нікопольщині» y
    «Нікопольський» → «нікополь»."""
    normal = normalizar(nombre).replace(" ", "")
    return re.sub(r"(?:(?:ськ|цьк|зьк)\w*|щин\w*)$", "", normal)


# La vocal del nombre cambia en el adjetivo («Межова» → «Межівська», «Мирове» → «Мирівська»).
_VOCALES_ALTERNAN = str.maketrans({"і": "о", "е": "о", "а": "о"})


def _centro(base: str, miembros: list[Lugar]) -> Lugar | None:
    """La localidad de la unidad que lleva su nombre: la de prefijo común más largo con la
    base (al menos la base sin sus dos últimas letras), y entre iguales la de más categoría."""
    rango = {"ciudad": 2, "asentamiento": 1}
    mejor: tuple[int, int, float] | None = None
    elegido = None
    plegada = base.translate(_VOCALES_ALTERNAN)
    for m in miembros:
        nombre = normalizar(m.nombre).replace(" ", "").translate(_VOCALES_ALTERNAN)
        comun = len(os.path.commonprefix([nombre, plegada]))
        if comun < max(3, len(base) - 2):
            continue
        clave = (comun, rango.get(m.categoria, 0), m.radio_km)
        if mejor is None or clave > mejor:
            mejor, elegido = clave, m
    return elegido


def _desambiguar(
    candidatos: list[Lugar], raiones: set[str], hromadas: set[str], nomenclator: Nomenclator
) -> list[Lugar]:
    """Los candidatos del distrito o la comunidad que nombra el mensaje, si los nombra; si no,
    la única ciudad frente a aldeas homónimas («Запоріжжя», la capital del óblast, frente a la
    aldea del mismo nombre)."""
    elegidos = _por_unidad(candidatos, raiones, hromadas)
    if len(elegidos) > 1:
        ciudades = [c for c in elegidos if c.categoria == "ciudad"]
        # Homónimas de verdad (el mismo nombre oficial): no una ciudad que lleva el nombre de
        # la aldea entre sus nombres antiguos («Приморськ», antes «Приморське»).
        if len(ciudades) == 1 and all(
            c.categoria == "aldea" and normalizar(c.nombre) == normalizar(ciudades[0].nombre)
            for c in elegidos
            if c is not ciudades[0]
        ):
            return ciudades
    return elegidos


def _por_unidad(candidatos: list[Lugar], raiones: set[str], hromadas: set[str]) -> list[Lugar]:
    if hromadas:
        de_comunidad = [
            c for c in candidatos if c.hromada and raiz_administrativa(c.hromada) in hromadas
        ]
        if de_comunidad:
            return de_comunidad
    if raiones:
        de_distrito = [c for c in candidatos if c.raion and _raion_casa(c.raion, raiones)]
        if de_distrito:
            return de_distrito
    return candidatos


def _raion_casa(raion: str, raices: set[str]) -> bool:
    """El distrito del codificador («Чугуївський») o de GeoNames («Belgorodskiy Rayon»)
    casa con una raíz del mensaje («чугуїв», «белгор»)."""
    propia = raiz_administrativa(raion)
    if propia in raices:
        return True
    latina = normalizar(raion).replace(" ", "")
    return any(transliterar(r)[:5] and latina.startswith(transliterar(r)[:5]) for r in raices)


_TRANSLITERACION = str.maketrans({
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ж": "zh", "з": "z",
    "и": "i", "к": "k", "л": "l", "м": "m", "н": "n", "о": "o", "п": "p", "р": "r",
    "с": "s", "т": "t", "у": "u", "ф": "f", "х": "kh", "ц": "ts", "ч": "ch", "ш": "sh",
    "щ": "shch", "ы": "y", "э": "e", "ю": "yu", "я": "ya", "і": "i", "є": "ye", "ґ": "g",
    "ь": "", "ъ": "", "й": "y", "ї": "yi",
})  # fmt: skip


def transliterar(texto: str) -> str:
    """Transliteración latina aproximada (la de GeoNames para los distritos rusos)."""
    return texto.translate(_TRANSLITERACION)


@cache
def cargar(ruta: Path = NOMENCLATOR, comunes: Path = COMUNES) -> Nomenclator:
    datos = json.loads(gzip.decompress(ruta.read_bytes()))
    lista = json.loads(comunes.read_text(encoding="utf-8"))["palabras"] if comunes.exists() else []
    return Nomenclator.desde_datos(datos, lista)


@cache
def contornos() -> Contornos:
    return Contornos.cargar()
