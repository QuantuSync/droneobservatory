"""El dron que identificó la autoridad, y los nombres de modelo que se tapan al comprobar.

Un incidente tiene el dron identificado por la autoridad cuando una frase de origen oficial (la
autoridad misma o su declaración citada) nombra un modelo o una familia del catálogo sin
expresión de duda («de tip Gerbera», «the Russian-provenance Geran-2 drone»). «Asemănător unei
drone de tip Shahed» (parecido a), «ar fi» (sería) o «possibly a Shahed» no identifican: lo dicen
las expresiones de duda de configuracion/expresiones_duda.json y las de parecido de aquí.
"""

import re
from collections.abc import Iterable
from typing import Any

from proceso import atribucion
from proceso.tipo_dron import modelo
from proceso.tipo_dron.rasgos import Frase, plano

ORIGENES_OFICIALES = ("oficial", "oficial_citado", "medido")

# (expresión sin acentos, clase del catálogo). La primera que casa decide; las más concretas,
# antes (Geran-3 antes que Geran).
FAMILIAS: tuple[tuple[str, str], ...] = (
    (r"geran[- ]?[345]|герань[- ]?[345]|shahed[- ]?238|шахед[- ]?238|tu-141|ту-141",
     "ataque_reaccion"),
    (r"gerbera\w*|гербер\w*|parodiya|пароди\w*|\bmaya\b|майя", "senuelo_largo_alcance"),
    (r"shahed\w*|шахед\w*|шахід\w*|geran\w*|герань\w*|герані|liutyi|лютий|fp-1|"
     r"\bbober\b|бобер|uj-2[26]", "ataque_largo_alcance_piston"),
    (r"orlan\w*|орлан\w*|forpost\w*|форпост\w*|orion|орион|akinci",
     "ala_fija_reconocimiento_combustion"),
    (r"lancet\w*|ланцет\w*|kub-bla|куб-бла|italmas|molniya|молния", "municion_merodeadora"),
    (r"\bdji\b|mavic\w*|phantom|matrice|autel|skydio|\bmini [234]\b|\bair 3s?\b",
     "multirrotor_consumo"),
    (r"\bfpv\b", "fpv"),
)  # fmt: skip
_FAMILIAS_RE = [(re.compile(e), c) for e, c in FAMILIAS]
# Parecido, no identificación.
PARECIDO = re.compile(
    r"asemanat\w*|similar\w*|resembl\w*|like a|looked like|ahnlich\w*|podobn\w*|похож\w*|"
    r"схож\w*|semblable\w*|parecid\w*|simil\w*|als ob|wie ein|type of|zoals"
)
# Clase de un modelo de la clase «multirrotor_consumo» nombrado por su familia (DJI sin modelo):
# las tres de consumo y profesionales caben.
CLASES_FAMILIA = {
    "multirrotor_consumo": ("multirrotor_consumo_sub250", "multirrotor_consumo",
                            "multirrotor_profesional"),
}  # fmt: skip


def familias_en(texto: str) -> list[tuple[str, str]]:
    """(palabra tal como sale, clase) de cada familia que nombra el texto."""
    normal = plano(texto)
    hallados = []
    for expresion, clase in _FAMILIAS_RE:
        m = expresion.search(normal)
        if m:
            # Con su número, si lo lleva: «Shahed 138», «Geran-2».
            numero = _NUMERO.match(normal, m.end())
            fin = numero.end() if numero else m.end()
            hallados.append((texto[m.start() : fin], clase))
            normal = normal[: m.start()] + " " * (fin - m.start()) + normal[fin:]
    return hallados


_NUMERO = re.compile(r"[- ]?\d{1,3}(?![\d.,])")


def tapar_modelos(texto: str) -> str:
    """El texto con los nombres de modelo y familia tapados: para comprobar sin que el nombre
    que dio la autoridad decida por sí solo."""
    normal = plano(texto)
    letras = list(texto)
    for expresion, _ in _FAMILIAS_RE:
        for m in expresion.finditer(normal):
            for i in range(m.start(), m.end()):
                letras[i] = "·"
    return "".join(letras)


def clases_de(clase: str) -> tuple[str, ...]:
    return CLASES_FAMILIA.get(clase, (clase,))


def identificado(frases: Iterable[Frase]) -> dict[str, Any] | None:
    """El dron que nombra la autoridad, con su frase y su fuente, o None. Si dos frases
    oficiales nombran familias distintas, no hay una identificación sola: None."""
    hallados: list[dict[str, Any]] = []
    for frase in frases:
        if frase.origen not in ORIGENES_OFICIALES:
            continue
        if atribucion.expresion_de_duda(frase.texto) is not None:
            continue
        if PARECIDO.search(plano(frase.texto)):
            continue
        for palabra, clase in familias_en(frase.texto):
            hallados.append(
                {
                    "modelo": palabra,
                    "clases": list(clases_de(clase)),
                    "grupo": modelo.grupo_de_clase()[clase],
                    "cita": frase.texto,
                    "fuente": frase.fuente,
                    "origen": frase.origen,
                }
            )
    if not hallados:
        return None
    grupos = {h["grupo"] for h in hallados}
    if len(grupos) > 1:
        return None
    return hallados[0]
