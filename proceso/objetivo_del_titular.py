"""La instalación que nombran el titular y las fuentes cuando la ficha no la reconoció.

La auditoría de las fichas (proceso/auditoria_fichas.py, comprobación B) encontró titulares que
nombran una instalación («aeropuerto de Frankfurt», «base militar de Creil», «Portul Constanța»)
con el objetivo vacío o «otra». `objetivo_nombrado` la busca en el nomenclátor
(configuracion/lugares_europa.json e instalaciones_europa.json) con el mismo criterio que agrupa
las noticias (proceso/noticias.lugares_en: un alias completo, o la ciudad junto al tipo de lugar)
y solo la da si es una sola, del país de la ficha y, si la ficha tiene punto, a menos de su radio
más 10 km. Si no, nada: lo que no se puede decidir así va a mano con su cita
(configuracion/incidentes_revisados.json).
"""

import json
import math
import re
from functools import cache

from esquema import Documento
from proceso import noticias
from proceso.ubicacion import CATEGORIA_LUGAR

# Margen sobre el radio de la instalación: el punto de la ficha puede ser el del pueblo de al lado.
MARGEN_KM = 10.0
# Tipos del nomenclátor que son el objetivo de un suceso (no un estadio o una presa por su ciudad).
TIPOS = frozenset({"aeropuerto", "base", "puerto", "nuclear", "energia"})
# El titular de la ficha nombra una sola instalación («el aeropuerto de», «la base militar de»);
# con varias («los aeropuertos de París», «bases militares en Manching y Neuburg») no se elige.
_UNA_INSTALACION = re.compile(
    r"\b(?:aeropuerto|aeródromo|base(?: aérea| militar| naval| de la otan| otan)?|puerto|"
    r"central (?:nuclear|eléctrica|térmica))\b",
    re.IGNORECASE,
)
_VARIAS = re.compile(r"\b(?:aeropuertos|aeródromos|bases|puertos|centrales)\b", re.IGNORECASE)


def _km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radianes = math.pi / 180
    x = (lon2 - lon1) * radianes * math.cos((lat1 + lat2) * radianes / 2)
    y = (lat2 - lat1) * radianes
    return 6371.0 * math.hypot(x, y)


def _alias_completo(texto: str, sitio: noticias.Lugar) -> bool:
    normal = f" {noticias.normalizar(texto)} "
    return sitio.tipo not in noticias.nomenclator().cue and any(
        " " in noticias.normalizar(a) and f" {noticias.normalizar(a)} " in normal
        for a in sitio.alias
    )


def _textos(incidente: Documento) -> list[str]:
    """El titular de la ficha en sus idiomas y los titulares y frases de sus fuentes."""
    textos = [str(t) for t in (incidente.get("titulo") or {}).values()]
    for fuente in incidente.get("fuentes", []):
        textos += [str(fuente.get(c) or "") for c in ("titular", "frase_origen")]
    return [t for t in textos if t]


def objetivo_nombrado(incidente: Documento) -> Documento | None:
    """El objetivo que nombran el titular o las fuentes, si la ficha no tiene uno de verdad
    (vacío o «otra»), su titular nombra una sola instalación y una sola del nomenclátor casa en
    un texto que nombra también su tipo; si no, None."""
    actual = incidente.get("objetivo") or {}
    if actual.get("categoria") not in (None, "otra"):
        return None
    titulo = str((incidente.get("titulo") or {}).get("es") or "")
    if not _UNA_INSTALACION.search(titulo) or _VARIAS.search(titulo):
        return None
    lugar = incidente.get("lugar") or {}
    punto = lugar.get("punto")
    nomenclator = noticias.nomenclator()
    hallados: set[str] = set()
    for texto in _textos(incidente):
        for id_ in noticias.lugares_en(texto, nomenclator):
            sitio = nomenclator.lugares[id_]
            if sitio.tipo not in TIPOS or sitio.pais != lugar.get("pais"):
                continue
            # El mismo texto nombra el tipo de lugar: «Бяла» sola es el pueblo, no su aeródromo.
            # Un puerto o una central (sin palabra de tipo en el nomenclátor): con su nombre
            # completo de varias palabras («Portul Constanța»).
            if not noticias._nombra_tipo(texto, id_, nomenclator) and not _alias_completo(
                texto, sitio
            ):
                continue
            if (
                punto is not None
                and _km(punto["lat"], punto["lon"], sitio.lat, sitio.lon)
                > sitio.radio_km + MARGEN_KM
            ):
                continue
            hallados.add(id_)
    if len(hallados) != 1:
        return None
    sitio = nomenclator.lugares[hallados.pop()]
    oaci = _oaci().get(sitio.id)
    objetivo: Documento = {
        "categoria": "aeropuerto" if oaci else CATEGORIA_LUGAR[sitio.tipo],
        "nombre": sitio.nombre,
    }
    if oaci:
        objetivo["oaci"] = oaci
    return objetivo


@cache
def _oaci() -> dict[str, str]:
    """{id de la instalación: OACI} (los ficheros del nomenclátor lo guardan; su índice, no)."""
    resultado: dict[str, str] = {}
    for fichero in ("lugares_europa.json", "instalaciones_europa.json"):
        datos = json.loads((noticias.DIRECTORIO / fichero).read_text(encoding="utf-8"))
        for clave, valor in datos["lugares"].items():
            if valor.get("oaci"):
                resultado[clave] = str(valor["oaci"])
    return resultado
