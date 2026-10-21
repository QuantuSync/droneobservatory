"""Dónde ocurrió un incidente: el lugar del suceso que da la ficha, situado con código.

El punto de un incidente es el del lugar donde ocurrió el suceso que describe la
ficha (donde se vio, cayó, explotó o fue derribado el dron), nunca el de otro sitio
que nombre la noticia. El candidato se agrupa por el primer lugar que casa en el
titular, que puede ser otro («la Guardia Civil» casa con el aeródromo de La Guardia,
en Toledo): su objetivo solo vale si su nombre es el del lugar del suceso.

Orden en que se busca el punto del lugar del suceso, siempre en su país:

1. una instalación del nomenclátor con ese nombre, si el suceso es en una instalación;
2. el objetivo del candidato, si su nombre es el del lugar del suceso;
3. un lugar del vocabulario que ha crecido con el uso, con ese nombre;
4. una localidad del nomenclátor con ese nombre;
5. el lugar nuevo que propone la ficha, con ese nombre;
6. el lugar que geolocaliza el GKG, si es una ciudad o un lugar con nombre (sus tipos 3
   y 4) y lleva ese nombre. Nunca uno de nivel de país o de región (tipos 1, 2 y 5), que
   son el centro del país o de la región.

Un suceso que solo se sabe a nivel de país o de región no tiene punto: nunca se usa el
centro de un país o de una región. Tampoco lo tiene un lugar que no se encuentra ni uno
de más de 50 km de radio. Esos incidentes se publican aparte, sin mapa.

Un punto hallado que cae fuera del país del incidente (`proceso/fronteras.py`) no vale;
si ninguno vale y alguno se halló, el incidente no se publica.
"""

import gzip
import json
import math
import re
from collections import defaultdict
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any

from proceso.fronteras import dentro_del_pais, nombres_del_pais, paises
from proceso.noticias import (
    GKG,
    RADIO_GKG_KM,
    Lugar,
    Nomenclator,
    distancia_km,
    localidades_declinadas,
    lugares_en,
    normalizar,
    plegar,
)
from proceso.territorios import soberanos_dentro
from proceso.validacion_ficha import (
    MIN_LETRAS_PALABRA,
    Validada,
    nombrado_en,
    propias_en_fuentes,
)
from recogida.lugares_osm import RADIO_KM

DIRECTORIO = Path(__file__).resolve().parent.parent / "configuracion"
# Radio máximo del esquema: un lugar más grande no es un punto.
RADIO_MAX_KM = 50.0
LONGITUD_OACI = 4
CATEGORIA_LUGAR = {
    "aeropuerto": "aeropuerto", "base": "base_militar", "nuclear": "energia",
    "energia": "energia", "subestacion": "energia", "presa": "presa", "puerto": "puerto",
    "estadio": "estadio",
}  # fmt: skip
# Tipos de lugar del GKG que son una ciudad o un lugar con nombre.
TIPOS_GKG_PUNTUALES = frozenset({"3", "4"})
SIN_PUNTO = frozenset({"region", "pais"})


@dataclass(frozen=True)
class Objetivo:
    """Un sitio con punto: del nomenclátor, del vocabulario o nuevo de la ficha."""

    id: str
    categoria: str
    nombre: str
    pais: str
    lat: float
    lon: float
    radio_km: float
    oaci: str | None = None

    @classmethod
    def de_lugar(cls, lugar: Lugar) -> "Objetivo":
        oaci = lugar.id if lugar.tipo == "aeropuerto" and len(lugar.id) == LONGITUD_OACI else None
        return cls(
            id=lugar.id,
            # Helipuertos, localidades y lugares del GKG: «otra».
            categoria=CATEGORIA_LUGAR.get(lugar.tipo, "otra"),
            nombre=lugar.nombre,
            pais=lugar.pais,
            lat=lugar.lat,
            lon=lugar.lon,
            radio_km=lugar.radio_km,
            oaci=oaci,
        )


@dataclass(frozen=True)
class Ubicacion:
    """El lugar del incidente: con punto (`sitio`) o solo con país y, si se sabe, región."""

    pais: str
    nivel: str
    sitio: Objetivo | None = None
    # De dónde sale el punto: nomenclator, candidato, vocabulario, localidad, lugar_nuevo, gkg.
    origen: str | None = None
    nombre: str | None = None
    region: str | None = None
    # Por qué no tiene punto, o por qué no vale.
    motivo: str | None = None
    # False si el único punto hallado cae fuera del país: el incidente no se publica.
    valida: bool = True


def _propias(nombre: str, genericos: tuple[str, ...]) -> set[str]:
    return {
        p
        for p in normalizar(nombre).split()
        if len(p) >= MIN_LETRAS_PALABRA and not p.startswith(genericos)
    }


def mismo_nombre(nombres: tuple[str, ...], suceso: str, genericos: tuple[str, ...]) -> bool:
    """Alguno de los nombres comparte una palabra propia (no de tipo de lugar) con el del
    suceso, entera o declinada: «Københavns Lufthavn» y «Copenhagen Airport, Kastrup» no,
    «Aeroport d'Eivissa» e «Ibiza» tampoco; «Anenii Noi» y «raionul Anenii Noi», sí."""
    propias_suceso = " ".join(_propias(suceso, genericos))
    if not propias_suceso:
        return False
    return any(
        palabra and nombrado_en(palabra, propias_suceso)
        for nombre in nombres
        for palabra in _propias(nombre, genericos)
    )


@dataclass(frozen=True)
class Pistas:
    """Lo que se sabe del candidato además de la ficha."""

    # Identificador del lugar del candidato: del nomenclátor, del vocabulario o del GKG.
    lugar_candidato: str
    objetivo_candidato: Objetivo | None
    nombres_candidato: tuple[str, ...]
    vocabulario: dict[str, Any]
    genericos: tuple[str, ...]


def _unico(ids: tuple[str, ...], pais: str, nom: Nomenclator) -> Lugar | None:
    del_pais = [nom.lugares[i] for i in ids if i in nom.lugares and nom.lugares[i].pais == pais]
    return del_pais[0] if len(del_pais) == 1 else None


def _hallados(
    ficha: Validada,
    pais: str,
    nombre: str,
    nivel: str,
    pistas: Pistas,
    nom: Nomenclator,
    region: str | None = None,
) -> list[tuple[str, Objetivo]]:
    """Sitios con el nombre del lugar del suceso, en orden de preferencia."""
    hallados: list[tuple[str, Objetivo]] = []
    if nivel == "instalacion" and (sitio := _unico(lugares_en(nombre, nom), pais, nom)):
        hallados.append(("nomenclator", Objetivo.de_lugar(sitio)))
    candidato = pistas.objetivo_candidato
    if (
        candidato is not None
        and not pistas.lugar_candidato.startswith(GKG + ":")
        and mismo_nombre(pistas.nombres_candidato, nombre, pistas.genericos)
    ):
        hallados.append(("candidato", candidato))
    for datos in pistas.vocabulario.values():
        if datos["pais"] == pais and mismo_nombre((datos["nombre"],), nombre, pistas.genericos):
            hallados.append(("vocabulario", Objetivo(**datos)))
    if sitio := _unico(localidades_declinadas(nombre, nom), pais, nom):
        hallados.append(("localidad", Objetivo.de_lugar(sitio)))
    if pequena := localidad_pequena(nombre, pais, region):
        hallados.append(("localidad_pequena", pequena))
    nuevo = ficha.valor("lugar_nuevo")
    if nuevo and mismo_nombre((nuevo["nombre"],), nombre, pistas.genericos):
        hallados.append(("lugar_nuevo", _objetivo_nuevo(nuevo)))
    if pistas.lugar_candidato.startswith(GKG + ":"):
        _, tipo, lat, lon, pais_gkg, nombre_gkg = pistas.lugar_candidato.split(":", 5)
        if tipo in TIPOS_GKG_PUNTUALES and nombrado_en(nombre_gkg, nombre):
            sitio_gkg = Objetivo(
                pistas.lugar_candidato, "otra", nombre_gkg, pais_gkg, float(lat), float(lon),
                RADIO_GKG_KM[tipo],
            )  # fmt: skip
            hallados.append(("gkg", sitio_gkg))
    return hallados


# Categoría del objetivo a tipo de lugar del nomenclátor, para el radio de un lugar nuevo.
TIPO_LUGAR = {"aeropuerto": "aeropuerto", "base_militar": "base", "energia": "nuclear"}
DECIMALES = 5


def _objetivo_nuevo(nuevo: dict[str, Any]) -> Objetivo:
    return Objetivo(
        id=f"{nuevo['pais']}-{normalizar(nuevo['nombre']).replace(' ', '_')}",
        categoria=nuevo["categoria"],
        nombre=str(nuevo["nombre"]).strip(),
        pais=nuevo["pais"],
        lat=round(float(nuevo["lat"]), DECIMALES),
        lon=round(float(nuevo["lon"]), DECIMALES),
        # El radio que da el nomenclátor a su tipo de lugar; a lo demás, el de una base.
        radio_km=RADIO_KM.get(TIPO_LUGAR.get(nuevo["categoria"], "base"), RADIO_KM["base"]),
    )


# Palabras que acompañan al nombre de una región en GeoNames o en las fuentes y no la
# identifican («Tulcea County», «județul Tulcea», «raionul Anenii Noi»).
GENERICOS_REGION = (
    "county", "region", "province", "provincia", "district", "municipality", "oblast",
    "voivodeship", "raion", "judet", "departement", "department", "canton", "kanton",
    "governorate", "autonomous", "community", "comunidad", "autonoma", "state", "land",
)  # fmt: skip


@cache
def regiones(ruta: Path = DIRECTORIO / "regiones_localidades.json") -> dict[str, Any]:
    datos: dict[str, Any] = json.loads(ruta.read_text(encoding="utf-8"))
    return datos


def regiones_con_nombre(pais: str, nombre: str) -> set[str]:
    """Las regiones del país que se llaman así («Tulcea» es la de Tulcea County)."""
    return {
        numero
        for numero, region in regiones()["regiones"].items()
        if region["pais"] == pais
        and mismo_nombre(tuple(region["nombres"]), nombre, GENERICOS_REGION)
    }


# El radio de un pueblo en el nomenclátor de localidades (recogida/localidades_geonames.RADIOS).
RADIO_PEQUENA_KM = 3.0


@cache
def localidades_pequenas(
    ruta: Path = DIRECTORIO / "localidades_pequenas.json.gz",
) -> tuple[dict[str, tuple[str, ...]], dict[str, list[Any]]]:
    """Índice de nombre normalizado a localidades pequeñas, y sus filas
    ([nombre, país, lat, lon, región, nombres]). Solo se carga si hace falta."""
    filas: dict[str, list[Any]] = json.loads(gzip.decompress(ruta.read_bytes()))["localidades"]
    indice: dict[str, list[str]] = defaultdict(list)
    for id_, fila in filas.items():
        # Los nombres se guardaron normalizados antes de plegar «ø», «ł»…: se pliegan aquí.
        for nombre in dict.fromkeys(plegar(n) for n in fila[5]):
            indice[nombre].append(id_)
    return {k: tuple(v) for k, v in indice.items()}, filas


def localidad_pequena(nombre: str, pais: str, region: str | None) -> Objetivo | None:
    """La localidad pequeña del país con ese nombre, si es una sola; con varias, la región
    que da la ficha tiene que dejar una sola."""
    indice, filas = localidades_pequenas()
    ids = [i for i in indice.get(normalizar(nombre), ()) if filas[i][1] == pais]
    if region and ids:
        casan = regiones_con_nombre(pais, region)
        if casan:
            ids = [i for i in ids if filas[i][4] in casan]
    if len(ids) != 1:
        return None
    fila = filas[ids[0]]
    return Objetivo(ids[0], "otra", fila[0], pais, fila[2], fila[3], RADIO_PEQUENA_KM)


# El municipio (gmina, comuna, Gemeinde…) que la fuente escribe junto a la localidad: «w
# Józefowie w gminie Nieporęt» (EODI-2026-00648).
_MUNICIPIO = re.compile(
    r"(?<!\w)(?:gmin(?:ie|a|y)|comun(?:a|ei)|gemeinde|municipality of|municipio de|"
    r"t[eé]rmino municipal de|commune de|kommune|kunta|obec|op[cć]ina|općini|obcina|"
    r"savivaldyb[eė]s?|novad[aā]?|vald)\s+(\w[\w-]*)(?:\s+(\w[\w-]*))?",
    re.IGNORECASE,
)
# Lo más lejos que está la localidad de la sede del municipio que la nombra.
RADIO_MUNICIPIO_KM = 12.0


def _con_ese_nombre(nombre: str, pais: str, nom: Nomenclator) -> list[Objetivo]:
    """Todas las localidades del país con ese nombre: la del nomenclátor (la más poblada) y
    las homónimas pequeñas (configuracion/localidades_pequenas.json.gz)."""
    normal = normalizar(nombre)
    salida = [
        Objetivo.de_lugar(nom.lugares[i]) for i in localidades_declinadas(nombre, nom)
        if nom.lugares[i].pais == pais and normalizar(nom.lugares[i].nombre) == normal
    ]  # fmt: skip
    indice, filas = localidades_pequenas()
    for id_ in indice.get(normal, ()):
        fila = filas[id_]
        if fila[1] == pais:
            salida.append(Objetivo(id_, "otra", fila[0], pais, fila[2], fila[3], RADIO_PEQUENA_KM))
    return salida


def _km(a: Objetivo, b: Objetivo) -> float:
    f1, f2 = math.radians(a.lat), math.radians(b.lat)
    h = (
        math.sin((f2 - f1) / 2) ** 2
        + math.cos(f1) * math.cos(f2) * math.sin(math.radians(b.lon - a.lon) / 2) ** 2
    )
    return 2 * 6371.0 * math.asin(math.sqrt(h))


def homonimo_de_la_fuente(
    nombre: str, pais: str, textos: tuple[str, ...], nom: Nomenclator
) -> Objetivo | None:
    """Con varias localidades del país que se llaman así, la que está junto al municipio que la
    fuente escribe con ella («Józefów w gminie Nieporęt»: el pueblo de Nieporęt, no la ciudad
    de junto a Otwock, que es la que guarda el nomenclátor por ser la más poblada). None si
    no hay homónimas o ninguna frase lo decide."""
    candidatos = _con_ese_nombre(nombre, pais, nom)
    if len(candidatos) < 2:
        return None
    raiz = normalizar(nombre)[: max(4, len(normalizar(nombre)) - 2)]
    for texto in textos:
        if raiz not in normalizar(texto):
            continue
        for encontrado in _MUNICIPIO.finditer(texto):
            palabras = [encontrado.group(1)]
            if encontrado.group(2) and encontrado.group(2)[:1].isupper():
                palabras.append(f"{encontrado.group(1)} {encontrado.group(2)}")
            for municipio in reversed(palabras):
                if normalizar(municipio) == normalizar(nombre):
                    continue
                sedes = _con_ese_nombre(municipio, pais, nom)
                pares = [(_km(c, s), c) for c in candidatos for s in sedes]
                if pares:
                    distancia, elegido = min(pares, key=lambda p: p[0])
                    if distancia <= RADIO_MUNICIPIO_KM:
                        return elegido
    return None


def lugar_del_homonimo(incidente: dict[str, Any], nom: Nomenclator) -> dict[str, Any] | None:
    """El lugar de una ficha guardada que situó una localidad por su nombre en la homónima que
    no es: el de la que deciden sus fuentes (homonimo_de_la_fuente), o None si ya era esa."""
    lugar = incidente.get("lugar") or {}
    nombre = lugar.get("localidad") or lugar.get("suceso")
    punto = lugar.get("punto")
    if not nombre or not punto or lugar.get("geocodificacion") not in {
        "localidad", "localidad_pequena",
    }:  # fmt: skip
        return None
    textos = tuple(
        str(f.get(c) or "")
        for f in incidente.get("fuentes", [])
        for c in ("frase_origen", "titular")
    )
    elegido = homonimo_de_la_fuente(str(nombre), str(lugar.get("pais")), textos, nom)
    if elegido is None:
        return None
    actual = Objetivo(
        "", "otra", str(nombre), str(lugar.get("pais")), punto["lat"], punto["lon"], 0
    )
    if _km(actual, elegido) < 1:
        return None
    return {
        **lugar,
        "punto": {"lat": round(elegido.lat, DECIMALES), "lon": round(elegido.lon, DECIMALES)},
        "radio_km": elegido.radio_km,
        "geocodificacion": "localidad_pequena"
        if elegido.id in localidades_pequenas()[1]
        else "localidad",
    }


def otra_region(sitio: Objetivo, region: str | None) -> bool:
    """La ficha dice en qué región ocurrió y la localidad hallada es de otra."""
    if not region:
        return False
    codigo = regiones()["localidades"].get(sitio.id)
    casan = regiones_con_nombre(sitio.pais, region)
    return codigo is not None and bool(casan) and codigo not in casan


def _intentos(ficha: Validada) -> list[tuple[str, str]]:
    """(nombre, nivel) que se buscan, en orden: el lugar del suceso; si no se encuentra o
    la ficha no lo da, la instalación afectada que nombra la ficha, y la localidad donde
    ocurrió. Todos son del suceso según la ficha y están validados en su frase."""
    suceso = ficha.valor("lugar_suceso")
    intentos = [(str(suceso["nombre"]), str(suceso["nivel"]))] if suceso else []
    instalacion = ficha.valor("objetivo_nombre")
    if not suceso and instalacion:
        intentos.append((str(instalacion), "instalacion"))
    localidad = ficha.valor("localidad")
    if localidad and all(normalizar(localidad) != normalizar(n) for n, _ in intentos):
        intentos.append((str(localidad), "localidad"))
    return intentos


def ubicar(ficha: Validada, pistas: Pistas, nom: Nomenclator) -> Ubicacion:
    """El lugar del incidente según el lugar del suceso de la ficha. La ficha es publicable:
    su país se sabe."""
    pais = ficha.pais or ""
    suceso = ficha.valor("lugar_suceso")
    nombre = str(suceso["nombre"]) if suceso else None
    nivel = str(suceso["nivel"]) if suceso else "localidad"
    region = (str(suceso.get("region") or "") if suceso else "") or (
        nombre if nivel == "region" else None
    )
    if nivel in SIN_PUNTO:
        return Ubicacion(pais, nivel, nombre=nombre, region=region,
                         motivo=f"solo se sabe a nivel de {nivel}")  # fmt: skip
    fuera: list[str] = []
    # Un lugar de otro país con suelo dentro de este (RAF Akrotiri, británica, en Chipre) vale
    # con el país del lugar si su punto cae en ese suelo (configuracion/territorios.json).
    soberanos = soberanos_dentro(pais)
    for buscado, nivel_buscado in _intentos(ficha):
        for soberano in soberanos:
            for origen, sitio in _hallados(
                ficha, soberano, buscado, nivel_buscado, pistas, nom, None
            ):
                if (
                    sitio.pais == soberano
                    and sitio.radio_km <= RADIO_MAX_KM
                    and dentro_del_pais(soberano, sitio.lat, sitio.lon)
                    and not dentro_del_pais(pais, sitio.lat, sitio.lon)
                ):
                    return Ubicacion(
                        soberano, nivel_buscado, sitio, origen, nombre or buscado, region
                    )
        for origen, sitio in _hallados(ficha, pais, buscado, nivel_buscado, pistas, nom, region):
            if sitio.pais != pais or sitio.radio_km > RADIO_MAX_KM:
                continue
            if otra_region(sitio, region):
                fuera.append(f"{sitio.nombre} ({origen}) es de otra región que {region}")
                continue
            if not dentro_del_pais(pais, sitio.lat, sitio.lon):
                fuera.append(f"{sitio.nombre} ({origen}) fuera de {pais}")
                continue
            nivel_punto = (
                "localidad"
                if origen in {"localidad", "localidad_pequena", "gkg"}
                else nivel_buscado
            )
            return Ubicacion(pais, nivel_punto, sitio, origen, nombre or buscado, region)
    # Sin lugar del suceso no se toma el objetivo del candidato aunque la ficha diga que es
    # el conocido: «la Guardia Civil» en la frase casaba con el aeródromo de La Guardia.
    if nombre is None and not fuera:
        return Ubicacion(pais, "pais", motivo="la ficha no dice dónde ocurrió")
    if fuera and all("fuera de" in f for f in fuera):
        return Ubicacion(pais, nivel, nombre=nombre, region=region,
                         motivo="; ".join(fuera), valida=False)  # fmt: skip
    return Ubicacion(pais, nivel, nombre=nombre, region=region,
                     motivo="; ".join(fuera) or "lugar del suceso sin situar")  # fmt: skip


# --- Afinado de un lugar que solo se sabe a nivel de región -----------------------------


# Una instalación es de la región de su ciudad: una localidad con ese nombre a 30 km o menos.
RADIO_CIUDAD_KM = 30.0


def region_del_sitio(sitio: Lugar, nom: Nomenclator) -> str | None:
    """Código de la región de primer nivel de una localidad o, para una instalación, de su
    ciudad."""
    datos = regiones()["localidades"]
    if sitio.id in datos:
        return str(datos[sitio.id])
    for ciudad in sitio.ciudades:
        for id_ in nom.localidades.get(normalizar(ciudad), ()):
            otra = nom.lugares[id_]
            if otra.pais == sitio.pais and distancia_km(sitio, otra) <= RADIO_CIUDAD_KM:
                codigo = datos.get(id_)
                if codigo is not None:
                    return str(codigo)
    return None


def nombres_en_idiomas(id_: str, nom: Nomenclator) -> set[str]:
    """Los nombres normalizados de una instalación y de su ciudad en todos sus idiomas: los de
    las localidades del nomenclátor que se llaman como una de sus ciudades, del mismo país y a
    30 km o menos («Lüttich», «Luik», «Lieja» para el aeropuerto de Lieja). Sin siglas: «NATO»
    es una ciudad de la base de Geilenkirchen en OpenStreetMap y no la nombra."""
    sitio = nom.lugares.get(id_)
    if sitio is None:
        return set()
    ciudades = [c for c in sitio.ciudades if not c.isupper()]
    propios = {normalizar(n) for n in (sitio.nombre, *sitio.alias, *ciudades)}
    for ciudad in ciudades:
        for otro_id in nom.localidades.get(normalizar(ciudad), ()):
            otro = nom.lugares[otro_id]
            if otro.pais == sitio.pais and distancia_km(sitio, otro) <= RADIO_CIUDAD_KM:
                propios |= {normalizar(n) for n in (otro.nombre, *otro.alias)}
    return {n for n in propios if len(n) >= MIN_LETRAS_PALABRA}


def afinar(ubicacion: Ubicacion, textos: tuple[str, ...], nom: Nomenclator) -> Ubicacion:
    """Un suceso que la ficha solo sitúa en una región gana el punto de la única instalación
    (o, si no hay ninguna, de la única localidad) de esa región que nombran las frases de la
    ficha y los titulares de sus fuentes: «Drohnen über Schleswig-Holstein» con «Drohnensich-
    tungen über Kraftwerk, Klinik und Werft in Kiel». Solo si la región se reconoce y el sitio
    está en ella; con dos sitios distintos no se elige ninguno. La localidad que se llama como
    la región no cuenta («Tulcea» es casi siempre la provincia). Un suceso de nivel país no se
    afina: la capital donde habla un ministro no es el lugar del suceso."""
    if ubicacion.sitio is not None or ubicacion.nivel != "region" or not ubicacion.region:
        return ubicacion
    if not regiones_con_nombre(ubicacion.pais, ubicacion.region):
        return ubicacion
    for buscar, origen_nivel in (
        (lugares_en, "instalacion"),
        (localidades_declinadas, "localidad"),
    ):
        sitios: dict[str, Lugar] = {}
        for texto in textos:
            for id_ in buscar(texto, nom):
                sitio = nom.lugares.get(id_)
                if sitio is None or sitio.pais != ubicacion.pais:
                    continue
                if mismo_nombre((sitio.nombre,), ubicacion.region, GENERICOS_REGION):
                    # «Tulcea» en el titular es, casi siempre, la provincia de Tulcea.
                    continue
                codigo = region_del_sitio(sitio, nom)
                dentro = codigo in regiones_con_nombre(ubicacion.pais, ubicacion.region)
                if dentro and dentro_del_pais(sitio.pais, sitio.lat, sitio.lon):
                    sitios[id_] = sitio
        if len(sitios) == 1:
            sitio = next(iter(sitios.values()))
            return Ubicacion(
                ubicacion.pais, origen_nivel, Objetivo.de_lugar(sitio), "frase_origen",
                ubicacion.nombre, ubicacion.region,
            )  # fmt: skip
        if sitios:
            return ubicacion
    return ubicacion


# --- País deducido del lugar del suceso ------------------------------------------------

CAMPOS_LUGAR = ("lugar_suceso", "objetivo_nombre", "localidad")


def _paises_del_nombre(nombre: str, nivel: str, nom: Nomenclator) -> set[str]:
    """Los países donde el nomenclátor tiene un lugar con ese nombre: las instalaciones, si
    alguna se llama así; si no, todas las localidades, grandes y pequeñas, homónimas
    incluidas (el nomenclátor grande solo guarda la más poblada de cada nombre: hay un
    Neudorf en Eslovaquia y muchos en Alemania y Austria). Si el suceso es de nivel país,
    los países que se llaman así."""
    normal = normalizar(nombre)
    if nivel == "pais":
        return {p for p in paises() if normal in nombres_del_pais(p)}
    instalaciones = {nom.lugares[i].pais for i in lugares_en(nombre, nom)}
    if instalaciones:
        return instalaciones
    indice, filas = localidades_pequenas()
    grandes = {nom.lugares[i].pais for i in localidades_declinadas(nombre, nom)}
    return grandes | {filas[i][1] for i in indice.get(normal, ())}


def pais_del_suceso(
    ficha: dict[str, Any], textos: tuple[str, ...], genericos: tuple[str, ...], nom: Nomenclator
) -> tuple[str, str, dict[str, Any]] | None:
    """El país que se deduce sin ambigüedad del lugar del suceso que da la ficha en bruto:
    su nombre, citado en su frase o en las fuentes, es de lugares de un solo país. Nunca el
    país del medio. Si la ficha declara un país (aunque no valide), el deducido tiene que ser
    ese: un suceso en El Paso (EE. UU.) no es de la aldea canaria que se llama igual.
    Devuelve (país, campo del que sale, ese campo)."""
    declarados = _paises_declarados(ficha)
    for nombre_campo in CAMPOS_LUGAR:
        campo = ficha.get(nombre_campo)
        if not isinstance(campo, dict) or campo.get("valor") is None:
            continue
        valor = campo["valor"]
        suceso = nombre_campo == "lugar_suceso"
        if suceso and not isinstance(valor, dict):
            continue
        nombre = str(valor["nombre"] if suceso else valor)
        nivel = str(valor.get("nivel", "localidad")) if suceso else "localidad"
        frase = str(campo.get("frase", ""))
        if not (
            nombrado_en(nombre, frase) or propias_en_fuentes(nombre, (frase, *textos), genericos)
        ):
            continue
        if nivel == "region":
            continue
        encontrados = _paises_del_nombre(nombre, nivel, nom)
        if len(encontrados) == 1 and (not declarados or encontrados <= declarados):
            return encontrados.pop(), nombre_campo, campo
        if encontrados:
            return None
    return None


def _paises_declarados(ficha: dict[str, Any]) -> set[str]:
    """Los códigos de país que da la ficha en bruto, en el país y en el lugar del suceso."""
    pais = (ficha.get("pais") or {}).get("valor")
    suceso = (ficha.get("lugar_suceso") or {}).get("valor")
    valores = [pais, suceso.get("pais") if isinstance(suceso, dict) else None]
    return {str(v).strip().upper() for v in valores if isinstance(v, str) and v.strip()}
