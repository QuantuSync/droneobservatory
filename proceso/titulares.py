"""Titulares coherentes con la presencia del dron.

El titular de un incidente y su campo presencia_dron dicen lo mismo:

- dron confirmado: el titular afirma el dron («Drones sobre el aeropuerto de Lieja interrumpen
  el tráfico aéreo»); un «posible dron» o un «objeto no identificado» se escriben como dron;
- dron no confirmado o no acreditado (una autoridad cerró la investigación sin pruebas del dron,
  proceso/rectificaciones.py): el titular lo da como posible («Posibles drones sobre…», «Un
  posible dron obliga a…»); un titular que no nombra el dron («Cierre del aeropuerto de X») vale
  tal cual.

Los titulares los escribe el extractor; esta regla los ajusta al guardar el incidente y al
revisar los ya guardados. Solo cambia el calificativo del dron: el resto del titular queda igual.
"""

import re

from esquema import Documento

CONFIRMADA, NO_CONFIRMADA, NO_ACREDITADA = "confirmada", "no_confirmada", "no_acreditada"

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

# El titular ya duda del dron con otra palabra («posiblemente», «sospecha de», «unidentified», «un
# posible avistamiento»): no hace falta añadir «posible», y si se añadió sobra («Posible
# avistamiento de posible dron», EODI-2026-00515).
_DUDA = {
    "es": re.compile(
        r"\b(?:posiblemente|probablemente|presunt\w*|supuest\w*|sospech\w*|no identificad\w*|"
        r"posibles?\s+(?!(?:drones|dron)\b)\w+)",
        re.IGNORECASE,
    ),
    "en": re.compile(
        r"\b(?:possibly|probably|suspected|suspicious|alleged|presumed|unidentified|"
        r"possible\s+(?!(?:drones|drone)\b)\w+)\b",
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
    if presencia in (NO_CONFIRMADA, NO_ACREDITADA):
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


# En inglés el calificativo va delante de todo el grupo del dron: «Mystery drones» → «Possible
# mystery drones», «Narco-drones» → «Possible narco-drones» (no «Mystery possible drones» ni
# «Narco-possible drones», 20 de octubre de 2026). No se salta un determinante, un número ni una
# preposición.
_COMPUESTO_EN = re.compile(r"(?:[\w’']+-)+$")
_PALABRA_ANTES_EN = re.compile(r"([A-Za-z][\w’']*)\s+$")
_GENTILICIOS_EN = ("ian", "ish", "ese", "an", "ch", "i")
_NO_MODIFICA_EN = frozenset({
    "a", "an", "the", "of", "over", "at", "near", "by", "with", "and", "after", "for", "from",
    "in", "on", "into", "above", "around", "two", "three", "four", "five", "several", "multiple",
    "many", "more", "some", "other", "unknown", "than", "dozen", "numerous", "six", "seven",
    "eight", "nine", "ten", "eleven", "twelve", "dozens", "hundreds",
})  # fmt: skip


def _inicio_del_grupo(titulo: str, inicio: int) -> int:
    """Dónde empieza en inglés el grupo nominal que acaba en «drone(s)».

    Solo se salta una palabra suelta cuando abre el titular («Mystery drones…», «Explosive
    drone…»): en medio puede ser un verbo o una preposición («closed following drone…», «due to
    drone…», «Pilot reports drone…»).
    """
    compuesto = _COMPUESTO_EN.search(titulo[:inicio])
    if compuesto is not None:
        inicio = compuesto.start()
    anterior = _PALABRA_ANTES_EN.search(titulo[:inicio])
    if (
        anterior is not None
        and anterior.start(1) == 0
        and anterior.group(1).lower() not in _NO_MODIFICA_EN
    ):
        inicio = 0
    return inicio


def _como_posible(titulo: str, idioma: str) -> str:
    m = _DRON[idioma].search(titulo)
    if m is None:
        return titulo
    palabra = m.group(1)
    plural = palabra.lower().endswith("s") and palabra.lower() != "dron"
    calificativo = ("posibles" if plural else "posible") if idioma == "es" else "possible"
    inicio = _inicio_del_grupo(titulo, m.start()) if idioma == "en" else m.start()
    grupo = titulo[inicio : m.start()] + palabra.lower()
    primera = grupo.split()[0].split("-")[0]
    if (
        inicio == 0
        and titulo[m.end() + 1 : m.end() + 2].islower()
        and not primera.lower().endswith(_GENTILICIOS_EN)
    ):
        # Al principio de un titular en minúsculas: «Mystery drones spotted» → «Possible
        # mystery drones spotted» (pero «Possible Russian drones»).
        grupo = grupo[:1].lower() + grupo[1:]
    resultado = titulo[:inicio] + f"{calificativo} {grupo}" + titulo[m.end() :]
    return _mayuscula(resultado, titulo) if inicio == 0 else resultado


# «Possible possible drone», «posible posible dron»: el calificativo repetido (2025-00299).
_POSIBLE_REPETIDO = re.compile(r"\b(possible|posibles?)\s+\1\b", re.IGNORECASE)


def ajustar(titulo: str, presencia: str | None, idioma: str) -> str:
    """El titular coherente con la presencia (el mismo si ya lo es)."""
    titulo = _POSIBLE_REPETIDO.sub(lambda m: m.group(0).split()[0], titulo)
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
