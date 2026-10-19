"""El lugar más preciso que permite el titular de la ficha (docs/control_fichas.md, «Lugar»).

Si el titular de la ficha nombra una instalación del nomenclátor (un aeropuerto, una base, un
puerto, una central), el lugar del incidente es esa instalación, con su código OACI si lo tiene,
y el marcador va en ella: nunca el país a secas ni el punto genérico de su ciudad. Lo hace la
recogida horaria con lo guardado, sin llamar a nada. Lo que nombran las fuentes y no el titular
lo decide la verificación de la ficha (recogida/control_fichas.py), que lee el contexto.

El titular nombra la instalación sin duda si:

- nombra una sola del país del incidente con su tipo de lugar, por su nombre propio o por su
  ciudad («aeropuerto de Núremberg»); por la ciudad solo si ninguna otra instalación del mismo
  tipo lleva ese nombre («aeropuerto de Varsovia» puede ser Chopin o Modlin);
- no nombra otra localidad que no sea la de la instalación («cerca de Heathrow, sobre Marlow»
  es Marlow; «Manching y Neuburg» son dos sitios).

Se aplica a los incidentes sin punto (solo el país, la región o un lugar sin situar) y a los
que tienen el punto genérico de la misma ciudad de la instalación (Núremberg, el GKG): nunca
cambia un punto que da una autoridad, el de otra instalación ni el de otra localidad. Un punto
que cambia queda en `lugar.historial` con el motivo en español y en inglés.
"""

from datetime import datetime

from esquema import Documento
from proceso.focos_termicos import distancia_km
from proceso.fronteras import dentro_del_pais
from proceso.noticias import (
    Lugar,
    Nomenclator,
    _grupos,
    _nombra_tipo,
    localidades_declinadas,
    lugares_en,
    normalizar,
)
from proceso.territorios import soberanos_dentro
from proceso.ubicacion import CATEGORIA_LUGAR, DECIMALES, Objetivo, nombres_en_idiomas

# Tipos de lugar del nomenclátor que son una instalación (no un helipuerto ni una ciudad).
TIPOS_INSTALACION = frozenset(CATEGORIA_LUGAR)
CATEGORIAS_INSTALACION = frozenset(CATEGORIA_LUGAR.values())
# Puntos que se pueden afinar: los de una localidad o del GKG, no los de una instalación.
GEOCODIFICACION_GENERICA = frozenset({"localidad", "localidad_pequena", "gkg", "lugar_nuevo"})
ORIGEN = "frase_origen"
# Sin el nombre de la instalación: el titular lo da en su idioma y la nota se lee en es/en (el
# nombre traducido ya sale en la ficha).
MOTIVO = {
    "es": "Lugar más preciso: la instalación que nombra el titular.",
    "en": "More precise place: the facility named in the headline.",
}
# El lugar es la instalación afectada que identifica la ficha por su código OACI, aunque ninguna
# autoridad dé el punto exacto (EODI-2026-00146: el punto del candidato, en la ciudad de Melilla,
# a 2,2 km del aeropuerto).
MOTIVO_OBJETIVO = {
    "es": "Lugar más preciso: la instalación afectada que identifica la ficha.",
    "en": "More precise place: the affected facility identified in the record.",
}
# Por debajo de esta distancia el punto ya está en la instalación.
DISTANCIA_INSTALACION_KM = 1.0
# Las notas de antes llevaban el nombre del titular tal cual.
MOTIVO_ANTERIOR = "Lugar más preciso que da el titular:"


def _con_la_palabra(grupo: str, sitio: Lugar, nom: Nomenclator) -> list[str]:
    """Las otras instalaciones del mismo tipo y país cuyo nombre, alias o ciudad lleva esas
    palabras («Warsaw Chopin Airport» lleva «warsaw», como Modlin)."""
    buscado = f" {grupo} "
    return [
        otro.id
        for otro in nom.lugares.values()
        if otro.id != sitio.id
        and otro.tipo == sitio.tipo
        and otro.pais == sitio.pais
        and any(buscado in f" {normalizar(n)} " for n in (otro.nombre, *otro.alias, *otro.ciudades))
    ]


def _por_ciudad_ambigua(texto: str, sitio: Lugar, nom: Nomenclator) -> bool:
    """El titular nombra la instalación solo por una ciudad que lleva también otra del mismo
    tipo («aeropuerto de Varsovia» puede ser Chopin o Modlin)."""
    grupos = _grupos(normalizar(texto))
    if any(sitio.id in nom.alias.get(g, ()) for g in grupos):
        return False
    return any(
        sitio.id in nom.ciudades.get(grupo, ()) and _con_la_palabra(grupo, sitio, nom)
        for grupo in grupos
    )


def _otra_localidad(texto: str, sitio: Lugar, nom: Nomenclator) -> bool:
    """El titular nombra una localidad del país que no es la de la instalación."""
    propios = nombres_en_idiomas(sitio.id, nom)
    for id_ in localidades_declinadas(texto, nom):
        otra = nom.lugares.get(id_)
        if otra is None or otra.pais != sitio.pais:
            continue
        if not ({normalizar(n) for n in (otra.nombre, *otra.alias)} & propios):
            return True
    return False


def instalacion_del_titulo(incidente: Documento, nom: Nomenclator) -> Lugar | None:
    """La instalación que nombra sin duda el titular de la ficha (en español o en inglés)."""
    pais = str(incidente["lugar"]["pais"])
    paises = {pais, *soberanos_dentro(pais)}
    hallados: dict[str, Lugar] = {}
    for texto in (str(t) for t in (incidente.get("titulo") or {}).values()):
        for id_ in lugares_en(texto, nom):
            sitio = nom.lugares.get(id_)
            if (
                sitio is None
                or sitio.tipo not in TIPOS_INSTALACION
                or sitio.pais not in paises
                or not dentro_del_pais(sitio.pais, sitio.lat, sitio.lon)
            ):
                continue
            if (
                not _nombra_tipo(texto, sitio.id, nom)
                or _por_ciudad_ambigua(texto, sitio, nom)
                or _otra_localidad(texto, sitio, nom)
            ):
                return None
            hallados[sitio.id] = sitio
    return next(iter(hallados.values())) if len(hallados) == 1 else None


def _afinable(incidente: Documento, sitio: Lugar, nom: Nomenclator) -> bool:
    """Sin punto, o con el punto genérico de la ciudad de la instalación."""
    lugar = incidente["lugar"]
    if "punto" not in lugar:
        return True
    objetivo = incidente.get("objetivo") or {}
    if (
        lugar.get("geocodificacion") not in GEOCODIFICACION_GENERICA
        or objetivo.get("categoria") in CATEGORIAS_INSTALACION
    ):
        return False
    nombres = {
        normalizar(str(n))
        for n in (objetivo.get("nombre"), lugar.get("localidad"), lugar.get("suceso"))
        if n
    }
    return bool(nombres) and nombres <= nombres_en_idiomas(sitio.id, nom)


def instalacion_del_objetivo(incidente: Documento, nom: Nomenclator) -> Lugar | None:
    """La instalación del nomenclátor que identifica el objetivo de la ficha por su código OACI,
    si el punto está a más de DISTANCIA_INSTALACION_KM de ella y no lo da una autoridad."""
    lugar = incidente["lugar"]
    oaci = (incidente.get("objetivo") or {}).get("oaci")
    if (
        not oaci
        or "punto" not in lugar
        or lugar.get("fuente_punto")
        or lugar.get("geocodificacion") == "oficial"
    ):
        return None
    sitio = nom.lugares.get(str(oaci))
    pais = str(lugar["pais"])
    if (
        sitio is None
        or sitio.tipo not in TIPOS_INSTALACION
        or sitio.pais not in {pais, *soberanos_dentro(pais)}
        or not dentro_del_pais(sitio.pais, sitio.lat, sitio.lon)
    ):
        return None
    punto = lugar["punto"]
    if distancia_km(punto["lat"], punto["lon"], sitio.lat, sitio.lon) <= DISTANCIA_INSTALACION_KM:
        return None
    return sitio


def _nota_antigua(entrada: Documento) -> bool:
    return str((entrada.get("motivo") or {}).get("es", "")).startswith(MOTIVO_ANTERIOR)


def nota_sin_nombre(incidente: Documento) -> Documento | None:
    """El incidente con las notas antiguas del lugar sin el nombre del titular, o None."""
    historial = (incidente.get("lugar") or {}).get("historial") or []
    if not any(_nota_antigua(h) for h in historial):
        return None
    nuevo = [{**h, "motivo": dict(MOTIVO)} if _nota_antigua(h) else h for h in historial]
    return {**incidente, "lugar": {**incidente["lugar"], "historial": nuevo}}


def precisar(incidente: Documento, nom: Nomenclator, ahora: datetime) -> Documento | None:
    """El incidente con el lugar en la instalación que nombra el titular o que identifica su
    objetivo, o None si no cambia."""
    sitio = instalacion_del_titulo(incidente, nom)
    motivo, del_objetivo = MOTIVO, False
    if sitio is None or not _afinable(incidente, sitio, nom):
        sitio, motivo, del_objetivo = (
            instalacion_del_objetivo(incidente, nom),
            MOTIVO_OBJETIVO,
            True,
        )
        if sitio is None:
            return None
    antes = incidente["lugar"]
    punto = {"lat": round(sitio.lat, DECIMALES), "lon": round(sitio.lon, DECIMALES)}
    nuevo: Documento = {
        k: v for k, v in antes.items() if k in {"localidad", "region", "historial", "otros_lugares"}
    }
    nuevo.update(
        pais=sitio.pais,
        nivel="instalacion",
        punto=punto,
        radio_km=sitio.radio_km,
        geocodificacion=ORIGEN,
        suceso=sitio.nombre,
    )
    if "punto" in antes and antes["punto"] != punto:
        anterior: Documento = {"punto": antes["punto"], "radio_km": antes["radio_km"]}
        if "localidad" in antes:
            anterior["localidad"] = antes["localidad"]
        nuevo["historial"] = [
            *antes.get("historial", []),
            {
                "fecha": {"valor": ahora.strftime("%Y-%m-%dT%H:%MZ"), "precision": "minuto"},
                "anterior": anterior,
                "motivo": dict(motivo),
            },
        ]
    if del_objetivo:
        # El punto es el del nomenclátor; el objetivo ya es la instalación (puede venir de una
        # revisión) y no se toca.
        resultado = {**incidente, "lugar": {**nuevo, "geocodificacion": "nomenclator"}}
        return None if resultado == incidente else resultado
    objetivo = Objetivo.de_lugar(sitio)
    datos_objetivo: Documento = {
        **{k: v for k, v in (incidente.get("objetivo") or {}).items() if k == "uso"},
        "categoria": objetivo.categoria,
        "nombre": objetivo.nombre,
    }
    if objetivo.oaci and objetivo.categoria == "aeropuerto":
        datos_objetivo["oaci"] = objetivo.oaci
    resultado = {**incidente, "lugar": nuevo, "objetivo": datos_objetivo}
    return None if resultado == incidente else resultado
