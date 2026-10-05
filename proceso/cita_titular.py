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
"""

import json
import re
from functools import cache
from pathlib import Path

from esquema import Documento
from proceso.fronteras import nombres_del_pais
from proceso.validacion_ficha import nombrado_en

CONFIGURACION = Path(__file__).resolve().parent.parent / "configuracion"
EQUIVALENTES = CONFIGURACION / "nombres_equivalentes.json"
REVISADOS = CONFIGURACION / "incidentes_revisados.json"
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


def respalda(incidente: Documento) -> bool:
    """Alguna cita nombra el país, el lugar o un nombre propio del titular."""
    textos = citas(incidente)
    if not textos:
        return False
    textos += [latino(t) for t in textos if not t.isascii()]
    nombres = _formas([
        *nombres_del_pais(incidente.get("lugar", {}).get("pais", "")),
        *nombres_del_lugar(incidente),
        *propios_del_titular(incidente),
    ])  # fmt: skip
    return any(nombrado_en(nombre, texto) for nombre in nombres for texto in textos)


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
