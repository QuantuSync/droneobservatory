"""Titulares coherentes con la presencia del dron.

El titular de un incidente y su campo presencia_dron dicen lo mismo:

- dron confirmado: el titular afirma el dron («Drones sobre el aeropuerto de Lieja interrumpen
  el tráfico aéreo»); un «posible dron» o un «objeto no identificado» se escriben como dron;
- dron no confirmado: el titular lo da como posible («Posibles drones sobre…», «Un posible dron
  obliga a…»); un titular que no nombra el dron («Cierre del aeropuerto de X») vale tal cual.

Los titulares los escribe el extractor; esta regla los ajusta al guardar el incidente y al
revisar los ya guardados. Solo cambia el calificativo del dron: el resto del titular queda igual.
"""

import re

from esquema import Documento

CONFIRMADA, NO_CONFIRMADA = "confirmada", "no_confirmada"

_DRON = {
    "es": re.compile(r"\b(drones|dron)\b", re.IGNORECASE),
    "en": re.compile(r"\b(drones|drone)\b", re.IGNORECASE),
}
_POSIBLE = {
    "es": re.compile(
        r"\b(?:posibles?|presuntos?|supuestos?|sospechosos?)\s+(?=(?:drones|dron)\b)",
        re.IGNORECASE,
    ),
    "en": re.compile(
        r"\b(?:possible|suspected|alleged|presumed|potential)\s+(?=(?:drones|drone)\b)",
        re.IGNORECASE,
    ),
}
_OBJETO = {
    "es": re.compile(
        r"\b(?P<obj>objetos?)\s+(?:volador(?:es)?\s+)?no\s+identificados?\b", re.IGNORECASE
    ),
    "en": re.compile(r"\bunidentified\s+(?:flying\s+)?(?P<obj>objects?)\b", re.IGNORECASE),
}

# El titular ya duda del dron con otra palabra («posiblemente», «sospecha de», «unidentified»):
# no hace falta añadir «posible», y si se añadió sobra.
_DUDA = {
    "es": re.compile(
        r"\b(?:posiblemente|probablemente|presunt\w*|supuest\w*|sospech\w*|no identificad\w*)",
        re.IGNORECASE,
    ),
    "en": re.compile(
        r"\b(?:possibly|probably|suspected|suspicious|alleged|presumed|unidentified)\b",
        re.IGNORECASE,
    ),
}
_AÑADIDO = {
    "es": re.compile(r"\bposibles?\s+(?=(?:drones|dron)\b)", re.IGNORECASE),
    "en": re.compile(r"\bpossible\s+(?=(?:drones|drone)\b)", re.IGNORECASE),
}
DISTANCIA_DUDA = 40


def _sin_doble(titulo: str, idioma: str) -> str:
    """Sin el «posible» que sobra tras otra palabra de duda («posiblemente un posible dron»)."""
    for duda in _DUDA[idioma].finditer(titulo):
        for m in _AÑADIDO[idioma].finditer(titulo):
            if 0 < m.start() - duda.end() <= DISTANCIA_DUDA:
                return titulo[: m.start()] + titulo[m.end() :]
    return titulo


def _mayuscula(texto: str, como: str) -> str:
    return texto[:1].upper() + texto[1:] if como[:1].isupper() else texto


def da_por_posible(titulo: str, idioma: str) -> bool:
    """El titular presenta el dron como posible u objeto no identificado."""
    return bool(_POSIBLE[idioma].search(titulo) or _OBJETO[idioma].search(titulo))


def afirma_dron(titulo: str, idioma: str) -> bool:
    """El titular nombra el dron sin presentarlo como posible."""
    return bool(_DRON[idioma].search(_POSIBLE[idioma].sub("", titulo))) and not da_por_posible(
        titulo, idioma
    )


def coherente(titulo: str, presencia: str | None, idioma: str) -> bool:
    if idioma in _DUDA and _sin_doble(titulo, idioma) != titulo:
        return False
    if presencia == CONFIRMADA:
        return not da_por_posible(titulo, idioma)
    if presencia == NO_CONFIRMADA:
        return not afirma_dron(titulo, idioma) or bool(_DUDA[idioma].search(titulo))
    return True


def _afirmar(titulo: str, idioma: str) -> str:
    resultado = _POSIBLE[idioma].sub("", titulo)

    def objeto(m: re.Match[str]) -> str:
        plural = m.group("obj").lower().endswith("s")
        palabra = (
            ("drones" if plural else "dron")
            if idioma == "es"
            else ("drones" if plural else "drone")
        )
        return _mayuscula(palabra, m.group(0))

    resultado = _OBJETO[idioma].sub(objeto, resultado)
    return _mayuscula(resultado, titulo)


def _como_posible(titulo: str, idioma: str) -> str:
    m = _DRON[idioma].search(titulo)
    if m is None:
        return titulo
    palabra = m.group(1)
    plural = palabra.lower().endswith("s") and palabra.lower() != "dron"
    calificativo = ("posibles" if plural else "posible") if idioma == "es" else "possible"
    al_inicio = m.start() == 0
    nuevo = f"{calificativo} {palabra.lower()}"
    resultado = titulo[: m.start()] + nuevo + titulo[m.end() :]
    return _mayuscula(resultado, titulo) if al_inicio else resultado


def ajustar(titulo: str, presencia: str | None, idioma: str) -> str:
    """El titular coherente con la presencia (el mismo si ya lo es)."""
    if idioma not in _DRON:
        return titulo
    titulo = _sin_doble(titulo, idioma)
    if coherente(titulo, presencia, idioma):
        return titulo
    if presencia == CONFIRMADA:
        return _afirmar(titulo, idioma)
    return _como_posible(titulo, idioma)


def ajustar_incidente(incidente: Documento) -> Documento:
    """El incidente con sus titulares coherentes con su presencia del dron."""
    titulo = dict(incidente.get("titulo") or {})
    presencia = incidente.get("presencia_dron")
    nuevo = {idioma: ajustar(texto, presencia, idioma) for idioma, texto in titulo.items()}
    if nuevo == titulo:
        return incidente
    return {**incidente, "titulo": nuevo}
