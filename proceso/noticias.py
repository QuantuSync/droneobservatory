"""Noticias europeas sobre drones: filtro sin modelo, réplicas y agrupación provisional.

No se publica nada: los candidatos son la entrada del extractor del siguiente PR.
Del artículo solo se guardan sus datos (URL, medio, fecha, idioma, país,
titular, temas y lugares), nunca el texto.

Agrupación con la regla de fusión del diseño: mismo objetivo o puntos a menos
de la suma de radios más 10 km; con precisión de hora, inicios a menos de 6
horas; con precisión de día, el mismo día o el siguiente; más de 12 horas sin
actividad es un incidente nuevo. Una agrupación dudosa no se hace.

Las noticias de un cierre se siguen publicando todo el día siguiente, así que un
segundo suceso en el mismo sitio a la noche siguiente caería en el mismo candidato.
Un titular que dice que se repite («erneut», «again», «de nuevo») 18 horas o más
después del inicio del candidato abre otro, que recibe desde entonces las noticias
del sitio: un candidato por objetivo y suceso.
"""

import json
import math
import re
import unicodedata
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta
from functools import cache
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from proceso.fronteras import es_nombre_de_pais
from proceso.variantes import variantes

DIRECTORIO = Path(__file__).resolve().parent.parent / "configuracion"
# Regla de fusión del diseño.
MARGEN_FUSION_KM = 10.0
INICIOS_HORA = timedelta(hours=6)
SIN_ACTIVIDAD = timedelta(hours=12)
# Un titular que dice que el suceso se repite abre otro candidato si llega 18 horas o más
# después del inicio del que tiene el sitio. Antes habla del mismo suceso: otra oleada de
# la misma noche o la crónica de la mañana siguiente («reabre tras cerrar de nuevo»), que
# llega de 10 a 16 horas después; un suceso de la noche siguiente llega a las 18 a 26 horas
# (Múnich, 2 y 3 de octubre de 2025: 19 h 45 min).
REPETICION_MIN = timedelta(hours=18)
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
    # Candidato del mismo sitio del que se separó por un titular de repetición.
    separado_de: str | None = None
    # Inicio del suceso, cuando su incidente lo sabe (no se guarda: sale del incidente). La
    # repetición se mide desde él: las primeras noticias pueden salir horas después del suceso.
    suceso: datetime | None = None


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


# Letras que la descomposición Unicode no separa de su base: «Sønderborg» se escribe
# «Sonderborg» en los titulares de fuera de Dinamarca, «Łódź» «Lodz», «Straße» «Strasse».
_PLEGADO = str.maketrans({
    "ø": "o", "æ": "ae", "œ": "oe", "ß": "ss", "ł": "l", "đ": "d", "ð": "d", "þ": "th",
    "ı": "i", "ŀ": "l",
})  # fmt: skip


def plegar(normal: str) -> str:
    """Un texto ya normalizado (en minúsculas) con esas letras como en su forma latina simple.
    Para los índices que se guardaron normalizados antes de este pliegue."""
    return normal.translate(_PLEGADO)


def normalizar(texto: str) -> str:
    """Minúsculas, sin acentos (también ø, æ, ß, ł…), sin puntuación y con los espacios
    simples."""
    limpio = re.sub(r"[^\w\s]", " ", plegar(sin_acentos(texto).lower()))
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
    repeticion: re.Pattern[str] = re.compile(r"(?!)")

    def repite(self, titular: str) -> bool:
        """El titular dice que el suceso se repite («erneut gesperrt», «closes again»)."""
        return bool(self.repeticion.search(titular))

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
        repeticion=re.compile(
            frontera
            + _alternativas(
                [p for lista in config.get("repeticion", {}).values() for p in lista], False
            )
            + r")(?!\w)",
            re.IGNORECASE,
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
# Un titular que nombra más de cinco instalaciones es un resumen, no un suceso.
MAX_OBJETIVOS_ARTICULO = 5


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

    # El nombre de un país no nombra un lugar: GeoNames da «Ukraine» como nombre alternativo
    # de Fuentes de Andalucía y «Moldova» como el de Fundu Moldovei (Rumanía).
    alias = [
        (normalizar(a), sitio.id)
        for sitio in lugares.values()
        for a in sitio.alias
        if propio(normalizar(a))
        and len(normalizar(a).split()) <= MAX_PALABRAS_ALIAS
        and not es_nombre_de_pais(normalizar(a))
    ]
    # Una «ciudad» que es una palabra de tipo de lugar («militar», «wojskowa») no nombra nada:
    # casaría con cualquier titular que hable de militares.
    # Con sus formas declinadas en el idioma del país («Düsseldorfer», «Rzeszowie»).
    ciudades = [
        (forma, sitio.id)
        for sitio in lugares.values()
        for c in sitio.ciudades
        # El nomenclátor está en forma descompuesta: se compara también sin acentos.
        if not any(p.search(c) or p.search(normalizar(c)) for p in cue.values())
        for forma in (normalizar(c), *sorted(variantes(normalizar(c), sitio.pais)))
    ]
    nombres_pueblos = [
        (normalizar(a), sitio.id)
        for sitio in pueblos.values()
        for a in sitio.alias
        if len(normalizar(a)) >= MIN_LETRAS_ALIAS
        and len(normalizar(a).split()) <= MAX_PALABRAS_ALIAS
        and not es_nombre_de_pais(normalizar(a))
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
    """Lugares de los grupos que nombran uno solo: un nombre de varios lugares («Leipzig»,
    de Leipzig/Halle y de Leipzig-Altenburg) es ambiguo y no sitúa nada."""
    return [indice[g][0] for g in grupos if len(indice.get(g, ())) == 1]


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
        # Una ciudad de varias instalaciones («Düsseldorf», del aeropuerto y de un helipuerto)
        # vale si el titular nombra el tipo de una sola de ellas («Düsseldorfer Flughafen»).
        hallados = []
        for grupo in grupos:
            if " " in grupo or grupo in mayusculas:
                con_tipo = [i for i in nom.ciudades.get(grupo, ()) if _nombra_tipo(titular, i, nom)]
                if len(con_tipo) > 1:
                    # Entre varias, la que solo lleva el nombre de una ciudad: «Düsseldorf» es
                    # el aeropuerto de Düsseldorf, no el de Düsseldorf Mönchengladbach.
                    con_tipo = [i for i in con_tipo if _ciudades_sueltas(nom.lugares[i]) == 1]
                if len(con_tipo) == 1:
                    hallados.append(con_tipo[0])
    return tuple(dict.fromkeys(hallados))


def _ciudades_sueltas(sitio: Lugar) -> int:
    """Cuántas ciudades de una sola palabra lleva la instalación."""
    return len({normalizar(c) for c in sitio.ciudades if " " not in normalizar(c)})


def _nombra_tipo(titular: str, id_: str, nom: Nomenclator) -> bool:
    """El titular nombra el tipo de lugar de la instalación («Flughafen», «air base»)."""
    cue = nom.cue.get(nom.lugares[id_].tipo)
    return cue is not None and cue.search(titular) is not None


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


# Nombre más largo que una terminación de caso: las que quedan tras quitarla («Krāslavas» da
# «kraslava»; «Rīgas», «riga»). Genitivos letón y lituano en -s y -as.
MIN_LETRAS_DECLINADA = 5


def localidades_declinadas(titular: str, nom: Nomenclator) -> tuple[str, ...]:
    """Localidades del titular, también las declinadas («Krāslavas novadā» es Krāslava)."""
    mayusculas = _mayusculas(titular)
    sueltas = [g for g in _grupos(normalizar(titular)) if " " not in g and g in mayusculas]
    raices = [
        g[:-corte] for g in sueltas if g.endswith("s") and len(g) > MIN_LETRAS_DECLINADA
        for corte in (1, 2)
    ]  # fmt: skip
    return tuple(dict.fromkeys([*localidades_en(titular, nom), *_buscar(nom.localidades, raices)]))


def lugar_del_suceso(titulo: str, texto: str, nom: Nomenclator) -> str | None:
    """El lugar donde ocurre lo que cuenta una nota, o None si no se sabe.

    El titular nombra el lugar del suceso: lo que nombra manda sobre lo que el texto nombra
    de pasada (la capital donde se da una rueda de prensa). Dentro de cada parte, una
    instalación, que es más concreta, antes que una localidad; si hay varias del mismo
    tipo, no se elige ninguna.
    """
    for parte in (titulo, f"{titulo}. {texto}"):
        for hallados in (lugares_en(parte, nom), localidades_declinadas(parte, nom)):
            if len(hallados) == 1:
                return hallados[0]
            if hallados:
                return None
    return None


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
        sitios = [lugar(id_, nom) for id_ in articulo.lugares]
        # Varias instalaciones de un mismo país en un titular («drones over Esbjerg, Sønderborg
        # and Skrydstrup») son varios objetivos de una misma noche: el artículo va a cada uno.
        # Varios lugares de otra clase, o de varios países, serían una agrupación dudosa.
        varios_objetivos = (
            1 < len(sitios) <= MAX_OBJETIVOS_ARTICULO
            and all(s.tipo in TIPO_APARENTE for s in sitios)
            and len({s.pais for s in sitios}) == 1
        )
        if not sitios:
            resultado.sin_lugar += 1
            continue
        if len(sitios) > 1 and not varios_objetivos:
            resultado.dudosos += 1
            continue
        for sitio in sitios:
            _agrupar_en(resultado, articulo, sitio, filtro_, precision)
    return resultado


def _agrupar_en(
    resultado: Agrupacion, articulo: Articulo, sitio: Lugar, filtro_: Filtro, precision: str
) -> None:
    tipo = filtro_.tipo(articulo.titular, sitio)
    encajan = [
        c
        for c in resultado.abiertos(articulo.fecha)
        if c.tipo == tipo
        and mismo_sitio(c.lugar, sitio)
        and misma_ventana(c, articulo.fecha, precision)
    ]
    if len(encajan) > 1 and len({(c.lugar.id, c.tipo) for c in encajan}) == 1:
        # Un sitio con varios candidatos abiertos solo los tiene por una repetición: lo nuevo
        # es del suceso más reciente.
        encajan = [max(encajan, key=lambda c: c.inicio)]
    if len(encajan) > 1:
        resultado.dudosos += 1
        return
    if encajan:
        candidato = encajan[0]
        if not repeticion(candidato, articulo, filtro_):
            if articulo.url not in candidato.articulos:
                candidato.articulos.append(articulo.url)
            candidato.ultimo = max(candidato.ultimo, articulo.fecha)
            return
        resultado.candidatos.append(nuevo_candidato(articulo, sitio, tipo, precision, candidato.id))
        return
    resultado.candidatos.append(nuevo_candidato(articulo, sitio, tipo, precision))


def repeticion(candidato: Candidato, articulo: Articulo, filtro_: Filtro) -> bool:
    """El artículo cuenta que el suceso del candidato se ha repetido: abre otro. Las horas se
    cuentan desde el suceso si se sabe (Lieja: el cierre del sábado por la noche sale en las
    noticias del domingo por la mañana y el «opnieuw» del domingo por la noche es otro)."""
    referencia = min(candidato.inicio, candidato.suceso) if candidato.suceso else candidato.inicio
    return (
        filtro_.repite(articulo.titular)
        and articulo.fecha - referencia >= REPETICION_MIN
        and articulo.url not in candidato.articulos
    )


def nuevo_candidato(
    articulo: Articulo, sitio: Lugar, tipo: str, precision: str, separado_de: str | None = None
) -> Candidato:
    return Candidato(
        # Inicio y lugar: dos candidatos no empiezan en el mismo minuto en el mismo sitio
        # sin fundirse, salvo que sean de tipo distinto.
        id=f"CAND-{articulo.fecha:%Y%m%dT%H%M}-{sitio.id}-{tipo}",
        tipo=tipo,
        lugar=sitio,
        inicio=articulo.fecha,
        ultimo=articulo.fecha,
        precision=precision,
        articulos=[articulo.url],
        separado_de=separado_de,
    )


def separar(candidato: Candidato, articulos: list[Articulo], filtro_: Filtro) -> list[Candidato]:
    """El candidato repasado con la regla de repetición, para los que se agruparon antes de
    ella: el primero conserva su identificador y los artículos hasta la primera repetición;
    cada repetición abre otro con los que siguen. Repasar uno ya separado no cambia nada."""
    grupos = [replace(candidato, articulos=[], ultimo=candidato.inicio)]
    for articulo in sorted(articulos, key=lambda a: (a.fecha, a.url)):
        actual = grupos[-1]
        if actual.articulos and repeticion(actual, articulo, filtro_):
            nuevo = nuevo_candidato(
                articulo, candidato.lugar, candidato.tipo, candidato.precision, actual.id
            )
            if nuevo.id != actual.id:
                grupos.append(nuevo)
                continue
        actual.articulos.append(articulo.url)
        actual.ultimo = max(actual.ultimo, articulo.fecha)
    return grupos
