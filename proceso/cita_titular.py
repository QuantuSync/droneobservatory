"""La cita tiene que respaldar el titular.

Un incidente se publica con sus citas guardadas (la frase de cada fuente y las de sus
afirmaciones). Si ninguna nombra el lugar, el país o lo propio del hecho que afirma el titular
(un nombre propio: «Borcea», «Schiphol», «Wunstorf»), el titular afirma algo que su fuente no
cuenta. Fue el caso de las altas «Drones del ataque ruso contra Ucrania cruzan a Rumanía», cuya
cita era el arranque del parte ucraniano («У ніч на … противник атакував …»).

`respalda` es la comprobación; `sin_respaldo` la aplica a una lista de incidentes. Hoy deja sin
publicar los incidentes cuyas fuentes son solo partes de guerra (exportacion/geojson.publicables);
para el resto se mide y se informa (docs/informe_errores_datos.md).
"""

import re

from esquema import Documento
from proceso.fronteras import nombres_del_pais
from proceso.validacion_ficha import nombrado_en

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


def citas(incidente: Documento) -> list[str]:
    """Las frases guardadas que se publican como cita del incidente."""
    resultado = [f.get("frase_origen", "") for f in incidente.get("fuentes", [])]
    resultado += [a.get("cita", "") for a in incidente.get("afirmaciones_publicas", [])]
    resultado += [a.get("frase", "") for a in incidente.get("afirmaciones", [])]
    return [c for c in resultado if c]


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


def respalda(incidente: Documento) -> bool:
    """Alguna cita nombra el país, el lugar o un nombre propio del titular."""
    textos = citas(incidente)
    if not textos:
        return False
    nombres = [
        *nombres_del_pais(incidente.get("lugar", {}).get("pais", "")),
        *nombres_del_lugar(incidente),
        *propios_del_titular(incidente),
    ]
    return any(nombrado_en(nombre, texto) for nombre in nombres for texto in textos)


def solo_partes_de_guerra(incidente: Documento) -> bool:
    fuentes = incidente.get("fuentes", [])
    return bool(fuentes) and all(PARTES_DE_GUERRA.match(f.get("id", "")) for f in fuentes)


def sin_respaldo(incidentes: list[Documento]) -> list[str]:
    """Los identificadores de los incidentes publicados cuya cita no respalda el titular."""
    return sorted(
        i["id"] for i in incidentes
        if "retirado" not in i and "fusionado_en" not in i and not respalda(i)
    )  # fmt: skip
