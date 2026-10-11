"""La cita tiene que respaldar el titular.

Un incidente se publica con sus citas guardadas (la frase de cada fuente y las de sus
afirmaciones). Si ninguna nombra el lugar, el país o lo propio del hecho que afirma el titular
(un nombre propio: «Borcea», «Schiphol», «Wunstorf»), el titular afirma algo que su fuente no
cuenta. Fue el caso de las altas «Drones del ataque ruso contra Ucrania cruzan a Rumanía», cuya
cita era el arranque del parte ucraniano («У ніч на … противник атакував …»).

`respalda` es la comprobación y `publicable` la barrera: un incidente cuyas citas públicas no
respaldan el titular no se publica (exportacion/geojson.publicables), salvo que esté revisado a
mano y justificado en configuracion/incidentes_revisados.json («titular_justificado», con su
motivo). La comprobación lee las citas en su escritura y también pasadas al alfabeto latino
(«София» casa con «Sofía») y con los nombres equivalentes de configuracion/nombres_equivalentes.json
(«Схипхол» es Schiphol), y la prueba fija de la integración continua la pasa por los ficheros
publicados (tests/test_cita_titular.py; docs/informe_revision_contenido.md, bloque 1).

Desde el 11 de octubre de 2026 también respalda el titular el titular del propio artículo de una
de sus fuentes, tal como está guardado en la base (tabla `articulos`): nunca un texto del
extractor ni el titular de un artículo que no es fuente del incidente. La recogida horaria lo
guarda entonces como cita del incidente (recogida/barrera.py), y la ficha muestra la frase que
respalda el titular. La primera frase del artículo no cuenta: la base no guarda el texto de los
artículos. Lo que siga retenido 6 horas se resuelve solo (recogida/barrera.py): a nivel de país
si algún texto de sus fuentes respalda el país, o descartado como no verificable si ninguno lo
hace.
"""

import json
import re
from functools import cache
from pathlib import Path

from esquema import Documento
from proceso.fronteras import nombres_del_pais
from proceso.noticias import normalizar
from proceso.validacion_ficha import nombrado_en

CONFIGURACION = Path(__file__).resolve().parent.parent / "configuracion"
EQUIVALENTES = CONFIGURACION / "nombres_equivalentes.json"
REVISADOS = CONFIGURACION / "incidentes_revisados.json"
REGIONES = CONFIGURACION / "regiones_localidades.json"
# El final que añaden las páginas a sus titulares («… ᐉ Новини от Fakti.bg - България»,
# «… | Diario X»): no es del titular. Tras un guion solo si nombra al medio («… - NRK»): «Tok fem
# ulovlige droner ved Leknes lufthavn – avslørte ulovlige sjåfører» es un titular entero.
_SUFIJO_PAGINA = re.compile(r"\s+(?:ᐉ|\|)\s.*$")
_SUFIJO_GUION = re.compile(r"\s+[-–—]\s+([^-–—]{2,40})$")
# Partes de guerra: la Fuerza Aérea de Ucrania y el Ministerio de Defensa ruso.
PARTES_DE_GUERRA = re.compile(r"^(?:kpszsu|mod_russia)-")
MIN_LETRAS = 4
# Palabras con mayúscula del titular que no son el nombre de un lugar o de un hecho concreto.
GENERICAS = frozenset({
    "dron", "drones", "drone", "uav", "uas", "rpas", "otan", "nato", "ejército", "army",
    "fuerza", "fuerzas", "aérea", "air", "force", "ministerio", "ministry", "defensa", "defence",
    "defense", "policía", "police", "gobierno", "government", "aeropuerto", "airport", "base",
    "militar", "military", "rusia", "russia", "ruso", "rusos", "rusa", "russian", "ucrania",
    "ukraine", "ucraniano", "ukrainian", "shahed", "geran", "gerbera", "europa", "europe",
})  # fmt: skip
# Cirílico y griego al alfabeto latino, letra a letra: basta para que un nombre casi siempre
# empiece igual («София» → «sofija», «Бургас» → «burgas», «Αιγαίο» → «aigaio»). Lo que no casa
# así va en nombres_equivalentes.json.
_LATINO = str.maketrans({
    "а": "a", "б": "b", "в": "v", "г": "g", "ґ": "g", "д": "d", "е": "e", "є": "je", "ё": "e",
    "ж": "zh", "з": "z", "и": "i", "і": "i", "ї": "ji", "й": "j", "к": "k", "л": "l", "м": "m",
    "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u", "ф": "f", "х": "h",
    "ц": "c", "ч": "ch", "ш": "sh", "щ": "sht", "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "ju",
    "я": "ja", "ј": "j", "љ": "lj", "њ": "nj", "ћ": "c", "ђ": "dj", "џ": "dz",
    "α": "a", "ά": "a", "β": "v", "γ": "g", "δ": "d", "ε": "e", "έ": "e", "ζ": "z", "η": "i",
    "ή": "i", "θ": "th", "ι": "i", "ί": "i", "ϊ": "i", "ΐ": "i", "κ": "k", "λ": "l", "μ": "m",
    "ν": "n", "ξ": "x", "ο": "o", "ό": "o", "π": "p", "ρ": "r", "σ": "s", "ς": "s", "τ": "t",
    "υ": "y", "ύ": "y", "ϋ": "y", "φ": "f", "χ": "ch", "ψ": "ps", "ω": "o", "ώ": "o",
})  # fmt: skip


def citas(incidente: Documento) -> list[str]:
    """Las frases guardadas que se publican como cita del incidente."""
    resultado = [f.get("frase_origen", "") for f in incidente.get("fuentes", [])]
    resultado += [a.get("cita", "") for a in incidente.get("afirmaciones_publicas", [])]
    resultado += [a.get("frase", "") for a in incidente.get("afirmaciones", [])]
    return [c for c in resultado if c]


def latino(texto: str) -> str:
    """El texto con el cirílico y el griego pasados al alfabeto latino."""
    return texto.lower().translate(_LATINO)


@cache
def equivalentes(ruta: Path = EQUIVALENTES) -> tuple[tuple[str, tuple[str, ...]], ...]:
    """Cada nombre con las formas en que lo escriben las fuentes en otra lengua o escritura."""
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    return tuple((e["nombre"], tuple(e["formas"])) for e in datos["nombres"])


@cache
def justificados(ruta: Path = REVISADOS) -> dict[str, str]:
    """Los incidentes revisados a mano cuyo titular es correcto aunque la comprobación no lo
    vea, con el motivo."""
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    return {e["incidente"]: e["motivo"]["es"] for e in datos.get("titular_justificado", [])}


@cache
def regiones_del_pais(ruta: Path = REGIONES) -> dict[str, tuple[str, ...]]:
    """Los nombres normalizados de las regiones de primer nivel de cada país (GeoNames)."""
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    resultado: dict[str, list[str]] = {}
    for region in datos["regiones"].values():
        resultado.setdefault(region["pais"], []).extend(region["nombres"])
    return {pais: tuple(dict.fromkeys(nombres)) for pais, nombres in resultado.items()}


def titular_limpio(titular: str, medio: str = "") -> str:
    """El titular del artículo sin el nombre del medio que le añade la página."""
    limpio = _SUFIJO_PAGINA.sub("", " ".join(titular.split()))
    nombre = medio.lower().removeprefix("www.").split(".")[0]
    final = _SUFIJO_GUION.search(limpio)
    if final and len(nombre) >= 2 and nombre in final[1].lower().replace(" ", ""):
        limpio = limpio[: final.start()]
    return limpio


def _palabras(nombre: str) -> list[str]:
    return [p for p in re.findall(r"[^\W\d_]+", nombre) if len(p) >= MIN_LETRAS]


def nombres_del_lugar(incidente: Documento) -> list[str]:
    lugar = incidente.get("lugar", {})
    nombres = [lugar.get(c) for c in ("suceso", "localidad", "region")]
    return [p for n in nombres if isinstance(n, str) for p in _palabras(n)]


def propios_del_titular(incidente: Documento) -> list[str]:
    """Los nombres propios del titular, sin la primera palabra ni las genéricas."""
    propios = []
    for titulo in incidente.get("titulo", {}).values():
        palabras = re.findall(r"[^\W\d_]+", titulo)
        for palabra in palabras[1:]:
            if (
                palabra[0].isupper()
                and len(palabra) >= MIN_LETRAS
                and palabra.lower() not in GENERICAS
            ):
                propios.append(palabra)
    return propios


def _formas(nombres: list[str]) -> list[str]:
    """Los nombres y sus formas equivalentes en otra lengua o escritura."""
    resultado = list(nombres)
    for nombre, formas in equivalentes():
        if any(nombrado_en(n, nombre) or nombrado_en(nombre, n) for n in nombres):
            resultado += formas
    return resultado


def _con_latino(textos: list[str]) -> list[str]:
    return [*textos, *(latino(t) for t in textos if not t.isascii())]


def nombra(textos: list[str], nombres: list[str]) -> bool:
    """Algún texto nombra alguno de los nombres (o una de sus formas en otra lengua)."""
    escritos = _con_latino([t for t in textos if t])
    formas = _formas(nombres)
    return any(nombrado_en(nombre, texto) for nombre in formas for texto in escritos)


def nombra_region(textos: list[str], pais: str) -> bool:
    """Algún texto nombra una región de primer nivel del país, con las palabras enteras: sin
    declinación, porque un nombre corto casaría con otra palabra («Ruse», provincia búlgara,
    con «руски»)."""
    escritos = [f" {normalizar(t)} " for t in _con_latino([t for t in textos if t])]
    return any(
        f" {region} " in texto
        for region in regiones_del_pais().get(pais, ())
        if len(region) >= MIN_LETRAS
        for texto in escritos
    )


def nombra_el_pais(textos: list[str], pais: str) -> bool:
    """Algún texto nombra el país o una de sus regiones: lo sitúa en ese país."""
    return bool(pais) and (
        nombra(textos, list(nombres_del_pais(pais))) or nombra_region(textos, pais)
    )


def respalda(incidente: Documento, otros: list[str] | None = None) -> bool:
    """Alguna cita (u otro texto de sus fuentes, como el titular del artículo) nombra el país,
    el lugar o un nombre propio del titular. Si el incidente solo se sitúa en su país, también
    vale una región del país: el titular no afirma más."""
    textos = [*citas(incidente), *(otros or [])]
    if not textos:
        return False
    lugar = incidente.get("lugar", {})
    pais = lugar.get("pais", "")
    nombres = [*nombres_del_pais(pais), *nombres_del_lugar(incidente),
               *propios_del_titular(incidente)]  # fmt: skip
    return nombra(textos, nombres) or (lugar.get("nivel") == "pais" and nombra_region(textos, pais))


def titular_que_respalda(incidente: Documento, titulares: dict[str, str]) -> tuple[str, str] | None:
    """(enlace, titular) del primer artículo fuente del incidente cuyo titular respalda el del
    incidente. `titulares`: enlace -> titular guardado en la base; solo cuentan los de sus
    propias fuentes públicas, nunca los de otro artículo."""
    propias = {f["enlace"]: f.get("medio", "") for f in incidente.get("fuentes", [])
               if f.get("enlace")}  # fmt: skip
    for enlace, medio in propias.items():
        titular = titular_limpio(titulares.get(enlace, ""), medio)
        if titular and respalda({**incidente, "fuentes": [], "afirmaciones_publicas": [],
                                 "afirmaciones": []}, [titular]):  # fmt: skip
            return enlace, titular
    return None


def respalda_el_pais(incidente: Documento, otros: list[str]) -> bool:
    """Algún texto de sus fuentes (citas o titulares de sus artículos) nombra el país del
    suceso o una de sus regiones, aunque no nombre el lugar concreto."""
    return nombra_el_pais([*citas(incidente), *otros], incidente.get("lugar", {}).get("pais", ""))


def publicable(incidente: Documento) -> bool:
    """Su cita respalda el titular, o está revisado a mano y justificado."""
    return incidente["id"] in justificados() or respalda(incidente)


def solo_partes_de_guerra(incidente: Documento) -> bool:
    fuentes = incidente.get("fuentes", [])
    return bool(fuentes) and all(PARTES_DE_GUERRA.match(f.get("id", "")) for f in fuentes)


def sin_respaldo(incidentes: list[Documento]) -> list[str]:
    """Los identificadores de los incidentes publicados cuya cita no respalda el titular."""
    return sorted(
        i["id"] for i in incidentes
        if "retirado" not in i and "fusionado_en" not in i and not respalda(i)
    )  # fmt: skip
