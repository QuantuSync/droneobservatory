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

import json
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any

from proceso.fronteras import dentro_del_pais
from proceso.noticias import (
    GKG,
    RADIO_GKG_KM,
    Lugar,
    Nomenclator,
    localidades_declinadas,
    lugares_en,
    normalizar,
)
from proceso.validacion_ficha import MIN_LETRAS_PALABRA, Validada, nombrado_en
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
    ficha: Validada, pais: str, nombre: str, nivel: str, pistas: Pistas, nom: Nomenclator
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
    for buscado, nivel_buscado in _intentos(ficha):
        for origen, sitio in _hallados(ficha, pais, buscado, nivel_buscado, pistas, nom):
            if sitio.pais != pais or sitio.radio_km > RADIO_MAX_KM:
                continue
            if otra_region(sitio, region):
                fuera.append(f"{sitio.nombre} ({origen}) es de otra región que {region}")
                continue
            if not dentro_del_pais(pais, sitio.lat, sitio.lon):
                fuera.append(f"{sitio.nombre} ({origen}) fuera de {pais}")
                continue
            nivel_punto = "localidad" if origen in {"localidad", "gkg"} else nivel_buscado
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
