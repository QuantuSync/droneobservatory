"""Noticias europeas sobre drones: filtro sin modelo, réplicas y agrupación provisional.

No se publica nada: los candidatos son la entrada del extractor del siguiente PR.
Del artículo solo se guardan sus datos (URL, medio, fecha, idioma, país,
titular, temas y lugares), nunca el texto.

Agrupación con la regla de fusión del diseño: mismo objetivo o puntos a menos
de la suma de radios más 10 km; con precisión de hora, inicios a menos de 6
horas; con precisión de día, el mismo día o el siguiente; más de 12 horas sin
actividad es un incidente nuevo. Una agrupación dudosa no se hace.
"""

import json
import math
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from functools import cache
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

DIRECTORIO = Path(__file__).resolve().parent.parent / "configuracion"
# Regla de fusión del diseño.
MARGEN_FUSION_KM = 10.0
INICIOS_HORA = timedelta(hours=6)
SIN_ACTIVIDAD = timedelta(hours=12)
# Las réplicas de una nota de agencia salen en uno o dos días: se buscan en 72 horas.
VENTANA_REPLICAS = timedelta(hours=72)
# «Casi idéntico»: comparten al menos el 85 % de las palabras (índice de Jaccard), lo
# que deja pasar un signo, un artículo o el nombre del medio y no dos noticias que
# solo comparten el lugar. Con titulares de menos de 6 palabras se exige igualdad.
PARECIDO_TITULARES = 0.85
MIN_PALABRAS_PARECIDO = 6
RADIO_TIERRA_KM = 6371.0
# Parámetros de seguimiento que no cambian la página.
_SEGUIMIENTO = re.compile(r"^(?:utm_\w+|fbclid|gclid|ocid|cmpid|at_\w+|mc_\w+|ref|src)$", re.I)
# « - Medio», « | Medio» al final del titular.
_SUFIJO_MEDIO = re.compile(r"\s+[-|–—]\s+[^-|–—]{2,40}$")


@dataclass(frozen=True)
class Articulo:
    url: str
    medio: str
    fecha: datetime
    titular: str
    idioma: str | None = None
    pais: str | None = None
    temas: tuple[str, ...] = ()
    lugares: tuple[str, ...] = ()


@dataclass(frozen=True)
class Lugar:
    id: str
    tipo: str
    nombre: str
    lat: float
    lon: float
    radio_km: float
    pais: str
    alias: tuple[str, ...]
    ciudades: tuple[str, ...]


@dataclass
class Candidato:
    id: str
    tipo: str
    lugar: Lugar
    inicio: datetime
    ultimo: datetime
    precision: str
    articulos: list[str] = field(default_factory=list)


# --- Normalización ---------------------------------------------------------------


def url_canonica(url: str) -> str:
    """Esquema https, sin «www.», sin fragmento, sin parámetros de seguimiento ni barra final."""
    partes = urlsplit(url.strip())
    anfitrion = partes.netloc.lower().removeprefix("www.")
    consulta = urlencode(
        sorted((k, v) for k, v in parse_qsl(partes.query) if not _SEGUIMIENTO.match(k))
    )
    ruta = partes.path.rstrip("/") or "/"
    return urlunsplit(("https", anfitrion, ruta, consulta, ""))


def sin_acentos(texto: str) -> str:
    descompuesto = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in descompuesto if not unicodedata.combining(c))


def normalizar(texto: str) -> str:
    """Minúsculas, sin acentos, sin puntuación y con los espacios simples."""
    limpio = re.sub(r"[^\w\s]", " ", sin_acentos(texto).lower())
    return " ".join(limpio.split())


def titular_normalizado(titular: str) -> str:
    return normalizar(_SUFIJO_MEDIO.sub("", titular.strip()))


def casi_iguales(a: str, b: str) -> bool:
    """Titulares normalizados iguales o casi: réplicas de la misma nota."""
    if a == b:
        return True
    pa, pb = set(a.split()), set(b.split())
    if min(len(pa), len(pb)) < MIN_PALABRAS_PARECIDO:
        return False
    return len(pa & pb) / len(pa | pb) >= PARECIDO_TITULARES


# --- Filtro ------------------------------------------------------------------------


@dataclass(frozen=True)
class Filtro:
    dron: re.Pattern[str]
    excluir: re.Pattern[str]
    senales: re.Pattern[str]
    tipos: tuple[tuple[str, re.Pattern[str]], ...]

    def pasa(self, titular: str, lugares: tuple[str, ...]) -> bool:
        """Menciona drones, no es ocio ni comercio y trae una señal de incidente o un lugar."""
        return bool(
            self.dron.search(titular)
            and not self.excluir.search(titular)
            and (self.senales.search(titular) or lugares)
        )

    def tipo(self, titular: str, lugar: Lugar | None) -> str:
        """Tipo aparente: el de la instalación reconocida o el de la primera señal que casa."""
        if lugar is not None and lugar.tipo in TIPO_APARENTE:
            return TIPO_APARENTE[lugar.tipo]
        return next((tipo for tipo, patron in self.tipos if patron.search(titular)), "otro")


def _alternativas(palabras: list[str], prefijo: bool) -> str:
    cola = r"\w*" if prefijo else ""
    return "|".join(re.escape(p) + cola for p in sorted(palabras, key=len, reverse=True))


@cache
def configuracion(ruta: Path = DIRECTORIO / "gdelt.json") -> dict[str, Any]:
    datos: dict[str, Any] = json.loads(ruta.read_text(encoding="utf-8"))
    return datos


def filtro(config: dict[str, Any] | None = None) -> Filtro:
    config = config or configuracion()
    palabras = [p for lista in config["palabras_dron"].values() for p in lista]
    frontera = r"(?<![\w])(?:"
    return Filtro(
        dron=re.compile(frontera + _alternativas(palabras, prefijo=True) + ")", re.IGNORECASE),
        excluir=re.compile(frontera + _alternativas(config["excluir"], True) + ")", re.IGNORECASE),
        senales=re.compile(
            frontera
            + _alternativas([s for g in config["senales"].values() for s in g], True)
            + ")",
            re.IGNORECASE,
        ),
        tipos=tuple(
            (tipo, re.compile(frontera + _alternativas(lista, True) + ")", re.IGNORECASE))
            for tipo, lista in config["senales"].items()
        ),
    )


# --- Lugares -----------------------------------------------------------------------

# Longitud mínima de un alias para buscarlo en un titular: con menos, siglas como «CPH»
# casan con cualquier cosa.
MIN_LETRAS_ALIAS = 4
# Los alias se buscan por grupos de palabras seguidas del titular: hasta 8 palabras cubre
# los nombres largos («Aeropuerto Adolfo Suárez Madrid-Barajas»).
MAX_PALABRAS_ALIAS = 8
# Tipo de lugar a tipo aparente del incidente.
TIPO_APARENTE = {
    "aeropuerto": "aeropuerto", "helipuerto": "aeropuerto", "base": "militar",
    "nuclear": "infraestructura", "energia": "infraestructura",
    "subestacion": "infraestructura", "presa": "infraestructura", "puerto": "infraestructura",
    "estadio": "infraestructura",
}  # fmt: skip
LOCALIDAD = "localidad"
GKG = "gkg"
# Coordenadas del propio GKG cuando nada casa: una ciudad o un lugar con nombre (tipos 3 y 4
# del GKG) con 10 km de radio; una región (tipos 2 y 5), con 50 km, el máximo del esquema.
# Un país entero no sitúa nada.
RADIO_GKG_KM = {"3": 10.0, "4": 10.0, "2": 50.0, "5": 50.0}


@dataclass(frozen=True)
class Nomenclator:
    lugares: dict[str, Lugar]
    # Alias normalizado de una instalación: casa solo.
    alias: dict[str, tuple[str, ...]]
    # Ciudad normalizada de una instalación: solo casa si el titular nombra además el tipo.
    ciudades: dict[str, tuple[str, ...]]
    # Localidad normalizada: solo si no casa ninguna instalación y hay señal de incidente.
    localidades: dict[str, tuple[str, ...]]
    cue: dict[str, re.Pattern[str]]


def _indice(pares: list[tuple[str, str]]) -> dict[str, tuple[str, ...]]:
    indice: dict[str, list[str]] = {}
    for clave, id_ in pares:
        if id_ not in indice.setdefault(clave, []):
            indice[clave].append(id_)
    return {k: tuple(v) for k, v in indice.items()}


def _leer_lugares(ruta: Path) -> dict[str, Lugar]:
    if not ruta.exists():
        return {}
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    return {
        id_: Lugar(
            id=id_,
            tipo=v["tipo"],
            nombre=v["nombre"],
            lat=v["lat"],
            lon=v["lon"],
            radio_km=v["radio_km"],
            pais=v["pais"],
            alias=tuple(v["alias"]),
            ciudades=tuple(v["ciudades"]),
        )
        for id_, v in datos["lugares"].items()
    }


def _leer_localidades(ruta: Path) -> dict[str, Lugar]:
    if not ruta.exists():
        return {}
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    return {
        id_: Lugar(id_, LOCALIDAD, nombre, lat, lon, radio, pais, tuple(alias), ())
        for id_, (nombre, pais, lat, lon, radio, alias) in datos["localidades"].items()
    }


@cache
def nomenclator(
    ruta: Path = DIRECTORIO / "lugares_europa.json",
    instalaciones: Path = DIRECTORIO / "instalaciones_europa.json",
    localidades: Path = DIRECTORIO / "localidades_europa.json",
) -> Nomenclator:
    """Instalaciones del nomenclátor inicial y del ampliado, y localidades."""
    lugares = {**_leer_lugares(instalaciones), **_leer_lugares(ruta)}
    pueblos = _leer_localidades(localidades)
    cue = {
        tipo: re.compile(r"(?<!\w)(?:" + _alternativas(palabras, True) + ")", re.IGNORECASE)
        for tipo, palabras in configuracion()["tipo_de_lugar"].items()
    }

    def propio(nombre: str) -> bool:
        """Tiene alguna palabra que no es el tipo de lugar: «Lentokenttäalue» no nombra nada."""
        return len(nombre) >= MIN_LETRAS_ALIAS and any(
            not any(p.match(palabra) for p in cue.values()) for palabra in nombre.split()
        )

    alias = [
        (normalizar(a), sitio.id)
        for sitio in lugares.values()
        for a in sitio.alias
        if propio(normalizar(a)) and len(normalizar(a).split()) <= MAX_PALABRAS_ALIAS
    ]
    # Una «ciudad» que es una palabra de tipo de lugar («militar», «wojskowa») no nombra nada:
    # casaría con cualquier titular que hable de militares.
    ciudades = [
        (normalizar(c), sitio.id)
        for sitio in lugares.values()
        for c in sitio.ciudades
        # El nomenclátor está en forma descompuesta: se compara también sin acentos.
        if not any(p.search(c) or p.search(normalizar(c)) for p in cue.values())
    ]
    nombres_pueblos = [
        (normalizar(a), sitio.id)
        for sitio in pueblos.values()
        for a in sitio.alias
        if len(normalizar(a)) >= MIN_LETRAS_ALIAS
        and len(normalizar(a).split()) <= MAX_PALABRAS_ALIAS
    ]
    return Nomenclator(
        {**pueblos, **lugares}, _indice(alias), _indice(ciudades), _indice(nombres_pueblos), cue
    )


def _grupos(normal: str) -> list[str]:
    """Grupos de palabras seguidas del texto normalizado, en orden de aparición."""
    palabras = normal.split()
    return [
        " ".join(palabras[i : i + n])
        for i in range(len(palabras))
        for n in range(1, min(MAX_PALABRAS_ALIAS, len(palabras) - i) + 1)
    ]


def _buscar(indice: dict[str, tuple[str, ...]], grupos: list[str]) -> list[str]:
    return [id_ for grupo in grupos for id_ in indice.get(grupo, ())]


def lugares_en(titular: str, nom: Nomenclator) -> tuple[str, ...]:
    """Instalaciones del nomenclátor que nombra el titular, sin repetir.

    Un alias completo casa solo; una ciudad, solo si el titular nombra además el
    tipo de lugar («Flughafen», «air base», «centrale nucléaire»).
    """
    grupos = _grupos(normalizar(titular))
    # Un alias de una sola palabra tiene que ir con mayúscula: «camp» en «military camp» no
    # es el campo irlandés que se llama «Camp».
    mayusculas = _mayusculas(titular)
    hallados = _buscar(nom.alias, [g for g in grupos if " " in g or g in mayusculas])
    if not hallados:
        hallados = [
            id_
            for id_ in _buscar(nom.ciudades, [g for g in grupos if " " in g or g in mayusculas])
            if (cue := nom.cue.get(nom.lugares[id_].tipo)) is not None and cue.search(titular)
        ]
    return tuple(dict.fromkeys(hallados))


def _mayusculas(titular: str) -> set[str]:
    """Palabras del titular escritas con mayúscula, normalizadas («Helsinki-Vantaan» da
    «helsinki» y «vantaan»)."""
    palabras = [p for p in re.findall(r"[^\W\d_][\w'’-]*", titular) if p[0].isupper()]
    return {parte for p in palabras for parte in normalizar(p).split()}


def localidades_en(titular: str, nom: Nomenclator) -> tuple[str, ...]:
    """Localidades que nombra el titular con mayúscula («Police» en un titular sobre la
    policía no es la ciudad polaca)."""
    mayusculas = _mayusculas(titular)
    grupos = [g for g in _grupos(normalizar(titular)) if g.split()[0] in mayusculas]
    return tuple(dict.fromkeys(_buscar(nom.localidades, grupos)))


def id_gkg(tipo: str, nombre: str, pais: str, lat: float, lon: float) -> str:
    """Identificador de un lugar geolocalizado por el GKG: lleva todo lo necesario."""
    limpio = re.sub(r"[:|]", " ", nombre).strip()
    return f"{GKG}:{tipo}:{lat:.4f}:{lon:.4f}:{pais}:{limpio}"


def lugar(id_: str, nom: Nomenclator) -> Lugar:
    """El lugar del nomenclátor o, si es un lugar del GKG, el que describe su identificador."""
    if not id_.startswith(GKG + ":"):
        return nom.lugares[id_]
    _, tipo, lat, lon, pais, nombre = id_.split(":", 5)
    return Lugar(id_, GKG, nombre, float(lat), float(lon), RADIO_GKG_KM[tipo], pais, (), ())


def lugares_articulo(
    titular: str, nom: Nomenclator, filtro_: "Filtro", gkg: tuple[str, ...] = ()
) -> tuple[str, ...]:
    """Dónde sitúa el artículo: la instalación que nombra; si no nombra ninguna y trae señal
    de incidente, la localidad; y si tampoco, el lugar que geolocaliza el GKG."""
    instalaciones = lugares_en(titular, nom)
    if instalaciones or not filtro_.senales.search(titular):
        return instalaciones
    return localidades_en(titular, nom) or gkg


# --- Agrupación --------------------------------------------------------------------


def distancia_km(a: Lugar, b: Lugar) -> float:
    """Distancia de círculo máximo (fórmula del haverseno)."""
    f1, f2 = math.radians(a.lat), math.radians(b.lat)
    df, dl = f2 - f1, math.radians(b.lon - a.lon)
    h = math.sin(df / 2) ** 2 + math.cos(f1) * math.cos(f2) * math.sin(dl / 2) ** 2
    return 2 * RADIO_TIERRA_KM * math.asin(math.sqrt(h))


def mismo_sitio(a: Lugar, b: Lugar) -> bool:
    return a.id == b.id or distancia_km(a, b) < a.radio_km + b.radio_km + MARGEN_FUSION_KM


def misma_ventana(candidato: Candidato, fecha: datetime, precision: str) -> bool:
    if fecha - candidato.ultimo > SIN_ACTIVIDAD:
        return False
    if precision == "hora" and candidato.precision == "hora":
        return abs(fecha - candidato.inicio) < INICIOS_HORA
    return fecha.date() in {candidato.inicio.date(), candidato.inicio.date() + timedelta(days=1)}


@dataclass
class Agrupacion:
    candidatos: list[Candidato] = field(default_factory=list)
    sin_lugar: int = 0
    dudosos: int = 0

    def abiertos(self, fecha: datetime) -> list[Candidato]:
        return [c for c in self.candidatos if fecha - c.ultimo <= SIN_ACTIVIDAD]


def agrupar(
    articulos: list[Articulo],
    filtro_: Filtro,
    nom: Nomenclator,
    agrupacion: Agrupacion | None = None,
    precision: str = "dia",
) -> Agrupacion:
    """Agrupa en orden de fecha. La fecha de un artículo es la de publicación, no la del
    suceso: por eso la precisión es de día."""
    resultado = agrupacion or Agrupacion()
    for articulo in sorted(articulos, key=lambda a: (a.fecha, a.url)):
        if len(articulo.lugares) != 1:
            # Sin lugar o con varios: agruparlo sería dudoso.
            if articulo.lugares:
                resultado.dudosos += 1
            else:
                resultado.sin_lugar += 1
            continue
        sitio = lugar(articulo.lugares[0], nom)
        tipo = filtro_.tipo(articulo.titular, sitio)
        encajan = [
            c
            for c in resultado.abiertos(articulo.fecha)
            if c.tipo == tipo
            and mismo_sitio(c.lugar, sitio)
            and misma_ventana(c, articulo.fecha, precision)
        ]
        if len(encajan) > 1:
            resultado.dudosos += 1
            continue
        if encajan:
            candidato = encajan[0]
            candidato.articulos.append(articulo.url)
            candidato.ultimo = max(candidato.ultimo, articulo.fecha)
            continue
        resultado.candidatos.append(
            Candidato(
                # Inicio y lugar: dos candidatos no empiezan en el mismo minuto en el mismo sitio
                # sin fundirse, salvo que sean de tipo distinto.
                id=f"CAND-{articulo.fecha:%Y%m%dT%H%M}-{sitio.id}-{tipo}",
                tipo=tipo,
                lugar=sitio,
                inicio=articulo.fecha,
                ultimo=articulo.fecha,
                precision=precision,
                articulos=[articulo.url],
            )
        )
    return resultado
