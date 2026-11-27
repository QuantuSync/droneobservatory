"""Titulares coherentes con la presencia del dron.

El titular de un incidente y su campo presencia_dron dicen lo mismo:

- dron confirmado: el titular afirma el dron («Drones sobre el aeropuerto de Lieja interrumpen
  el tráfico aéreo»); un «posible dron» o un «objeto no identificado» se escriben como dron;
- dron no confirmado o no acreditado (una autoridad cerró la investigación sin pruebas del dron,
  proceso/rectificaciones.py): el titular lo da como posible («Posibles drones sobre…», «Un
  posible dron obliga a…»); un titular que no nombra el dron («Cierre del aeropuerto de X») vale
  tal cual;
- dron descartado (la autoridad dijo que era otra cosa): el titular no lo afirma; dice que no lo
  era («Falsa alarma de dron…») o lo da como posible.

La duda cuenta también lejos del dron, en la misma frase («por sospecha de dron», «Posible caída
de dron», «Suspected airspace violation by drones»), y «dron no identificado» afirma un dron. La
misma lectura (`postura`) decide la regla y la auditoría AJ (proceso/auditoria_fichas.py).

Los titulares los escribe el extractor; esta regla los ajusta al guardar el incidente y al
revisar los ya guardados (proceso/decidir.decidir_titulo, cada vez que se guarda la ficha, con la
presencia ya decidida). Solo cambia el calificativo del dron: el resto del titular queda igual.
"""

import re

from esquema import Documento

CONFIRMADA, NO_CONFIRMADA, NO_ACREDITADA = "confirmada", "no_confirmada", "no_acreditada"
DESCARTADA = "descartada"

_DRON = {
    "es": re.compile(r"\b(drones|dron)\b", re.IGNORECASE),
    "en": re.compile(r"\b(drones|drone)\b", re.IGNORECASE),
}
_POSIBLE = {
    "es": re.compile(
        r"\b(?:posibles?|presuntos?|supuestos?|sospechosos?)\s+(?=(?:drones|dron)\b)",
        re.IGNORECASE,
    ),
    # Con una palabra en medio en inglés: «Possible military drone discovered in Taraclia»
    # (EODI-2025-00278) se quedaba con «Possible» con el dron ya confirmado.
    "en": re.compile(
        r"\b(?:possible|suspected|alleged|presumed|potential)\s+"
        r"(?=(?:[a-z][\w-]*\s+)?(?:drones|drone)\b)",
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
        r"\b(?:posiblemente|probablemente|presunt\w*|supuest\w*|sospech\w*|"
        r"(?<!\bdron )(?<!\bdrones )no identificad\w*|posibles?\s+(?!(?:drones|dron)\b)\w+)",
        re.IGNORECASE,
    ),
    "en": re.compile(
        r"\b(?:possibly|probably|suspected|suspicious|alleged|presumed|"
        r"unidentified(?!\s+drones?\b)|possible\s+(?!(?:drones|drone)\b)\w+)\b",
        re.IGNORECASE,
    ),
}
_AÑADIDO = {
    "es": re.compile(r"\bposibles?\s+(?=(?:drones|dron)\b)", re.IGNORECASE),
    "en": re.compile(r"\bpossible\s+(?=(?:drones|drone)\b)", re.IGNORECASE),
}
DISTANCIA_DUDA = 40

# La duda sobre el dron que no va pegada a él, en la misma frase del titular y hasta
# `DISTANCIA_DUDA_LEJOS` caracteres antes: «Cierre del espacio aéreo de Aalborg por sospecha de
# dron» (EODI-2025-00095), «Posible caída de dron» (EODI-2025-00299), «Suspected airspace
# violation by drones» (EODI-2026-00903). La regla solo miraba el «posible» pegado al dron: el
# inglés perdía la duda con el dron confirmado y el español no, y la auditoría T no lo veía.
DISTANCIA_DUDA_LEJOS = 60
_DUDA_LEJOS = {
    "es": re.compile(
        r"\b(?P<duda>(?:posibles?|presunt[oa]s?|supuest[oa]s?)\s+|sospechas?\s+de\s+|"
        r"posiblemente\s+|probablemente\s+)"
        rf"(?P<medio>[^,;:.()«»\"“”]{{0,{DISTANCIA_DUDA_LEJOS}}}?)\b(?:drones|dron)\b",
        re.IGNORECASE,
    ),
    "en": re.compile(
        r"\b(?P<duda>(?:possible|suspected|alleged|presumed|potential|possibly|probably)\s+)"
        rf"(?P<medio>[^,;:.()\"“”]{{0,{DISTANCIA_DUDA_LEJOS}}}?)\b(?:drones|drone)\b",
        re.IGNORECASE,
    ),
}
# Lo que dice que no era un dron: con la presencia descartada, el titular que lo dice no duda del
# dron, lo niega («Falsa alarma de dron…», «…que la policía descarta», EODI-2025-00225 y
# EODI-2026-00064).
_DESCARTE = {
    "es": re.compile(r"\b(?:falsa alarma|descart\w*|no era un dron|resultó ser|era un globo)\b",
                     re.IGNORECASE),
    "en": re.compile(r"\b(?:false (?:drone )?alarm|ruled out|not a drone|turned out|"
                     r"was a balloon)\b", re.IGNORECASE),
}  # fmt: skip
AFIRMA, DUDA, NIEGA, NO_LO_NOMBRA = "afirma", "duda", "niega", "no_lo_nombra"


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
    """El titular presenta el dron como posible u objeto no identificado, con la duda pegada al
    dron o antes en la misma frase («por sospecha de dron», «Posible caída de dron»)."""
    return bool(
        _POSIBLE[idioma].search(titulo)
        or _OBJETO[idioma].search(titulo)
        or _DUDA_LEJOS[idioma].search(titulo)
    )


def postura(titulo: str, idioma: str) -> str:
    """Lo que el titular dice del dron: lo niega (`NIEGA`), duda de él (`DUDA`), lo afirma
    (`AFIRMA`) o no lo nombra (`NO_LO_NOMBRA`). La misma lectura para la regla que ajusta el
    titular al guardar (`coherente`) y para la auditoría AJ (proceso/auditoria_fichas.py)."""
    if idioma not in _DRON:
        return NO_LO_NOMBRA
    if _DESCARTE[idioma].search(titulo):
        return NIEGA
    # Solo la duda sobre el dron: «despiertan sospechas de espionaje» (EODI-2025-00388) o «with
    # owner unidentified» (EODI-2025-00034) no dudan de él.
    if da_por_posible(titulo, idioma):
        return DUDA
    if _DRON[idioma].search(titulo):
        return AFIRMA
    return NO_LO_NOMBRA


# Lo que puede decir del dron el titular según la presencia: confirmada, el dron (o nada);
# descartada, que no lo era, que es posible o nada; si no, que es posible o nada.
POSTURAS_VALIDAS = {
    CONFIRMADA: frozenset({AFIRMA, NO_LO_NOMBRA}),
    NO_CONFIRMADA: frozenset({DUDA, NO_LO_NOMBRA}),
    NO_ACREDITADA: frozenset({DUDA, NO_LO_NOMBRA}),
    DESCARTADA: frozenset({NIEGA, DUDA, NO_LO_NOMBRA}),
}


def afirma_dron(titulo: str, idioma: str) -> bool:
    """El titular nombra el dron sin presentarlo como posible."""
    return bool(_DRON[idioma].search(_POSIBLE[idioma].sub("", titulo))) and not da_por_posible(
        titulo, idioma
    )


def coherente(titulo: str, presencia: str | None, idioma: str) -> bool:
    """El titular dice del dron lo mismo que la presencia (`POSTURAS_VALIDAS`), sin un «posible»
    repetido."""
    if idioma in _DUDA and _sin_doble(titulo, idioma) != titulo:
        return False
    validas = POSTURAS_VALIDAS.get(str(presencia))
    return validas is None or postura(titulo, idioma) in validas


def _sin_duda_lejos(titulo: str, idioma: str) -> str:
    """El titular sin la duda que va antes del dron en la misma frase: «por sospecha de dron» →
    «por un dron», «por sospecha de actividad de drones» → «por actividad de drones», «Posible
    caída de dron» → «Caída de dron», «Suspected airspace violation by drones» → «Airspace
    violation by drones»."""

    def sin(m: re.Match[str]) -> str:
        duda, medio = m.group("duda"), m.group("medio")
        resto = m.group(0)[len(duda) :]
        if (
            duda.lower().startswith("sospecha")
            and not medio
            and not resto.lower().startswith("drones")
        ):
            resto = "un " + resto
        return _mayuscula(resto, duda) if m.start() == 0 else resto

    return _DUDA_LEJOS[idioma].sub(sin, titulo)


def _afirmar(titulo: str, idioma: str) -> str:
    resultado = _sin_duda_lejos(_POSIBLE[idioma].sub("", titulo), idioma)

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
_DESCONOCIDO_EN = re.compile(r"\b(?:unidentified|unknown)\s+$", re.IGNORECASE)
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
    # «over unidentified drone» → «over possible unidentified drone» (EODI-2026-00819).
    desconocido = _DESCONOCIDO_EN.search(titulo[:inicio])
    if desconocido is not None:
        inicio = desconocido.start()
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

# «Dron» es masculino: «Una dron entra en el espacio aéreo de Rumanía» (EODI-2026-00698) y «Una
# posible dron interrumpe…» (EODI-2026-00322, 28 de octubre de 2026) venían de traducir el rumano
# «o dronă» y el alemán «eine Drohne», femeninos. Las palabras que concuerdan con el dron, delante
# (con «posible» en medio o no) y detrás.
_MASCULINO_ANTES = {
    "una": "un", "la": "el", "de la": "del", "a la": "al", "esta": "este", "esa": "ese",
    "aquella": "aquel", "otra": "otro", "alguna": "algún", "ninguna": "ningún", "misma": "mismo",
    "nueva": "nuevo", "sola": "solo", "primera": "primer", "segunda": "segundo",
    "tercera": "tercer", "cierta": "cierto", "presunta": "presunto", "supuesta": "supuesto",
    "sospechosa": "sospechoso", "misteriosa": "misterioso", "pequeña": "pequeño",
    "unas": "unos", "las": "los", "estas": "estos", "esas": "esos", "aquellas": "aquellos",
    "otras": "otros", "algunas": "algunos", "varias": "varios", "nuevas": "nuevos",
    "mismas": "mismos", "muchas": "muchos", "pocas": "pocos", "ciertas": "ciertos",
    "presuntas": "presuntos", "supuestas": "supuestos", "sospechosas": "sospechosos",
    "misteriosas": "misteriosos", "pequeñas": "pequeños",
}  # fmt: skip
_FEMENINO_ANTES = re.compile(
    r"\b("
    + "|".join(sorted((re.escape(p) for p in _MASCULINO_ANTES), key=len, reverse=True))
    + r")(\s+(?:posibles?\s+)?)(?=(?:drones|dron)\b)",
    re.IGNORECASE,
)
_FEMENINO_DESPUES = re.compile(
    r"\b(drones|dron)(\s+)(rus|ucranian|bielorrus|armad|explosiv|cargad|"
    r"derribad|abatid|detectad|avistad|hallad|encontrad|estrellad|caíd|perdid|desviad|"
    r"misterios|pequeñ|sospechos|no identificad)(a)(s?)\b",
    re.IGNORECASE,
)


def concordar(titulo: str, idioma: str) -> str:
    """El titular con las palabras que acompañan al dron en masculino (solo en español)."""
    if idioma != "es":
        return titulo

    def antes(m: re.Match[str]) -> str:
        return _mayuscula(_MASCULINO_ANTES[m.group(1).lower()], m.group(1)) + m.group(2)

    def despues(m: re.Match[str]) -> str:
        return m.group(1) + m.group(2) + m.group(3) + "o" + m.group(5)

    return _FEMENINO_DESPUES.sub(despues, _FEMENINO_ANTES.sub(antes, titulo))


def concuerda(titulo: str, idioma: str) -> bool:
    return concordar(titulo, idioma) == titulo


# «Drone» es la palabra inglesa e italiana; en español es «dron»: «Drone agricola bloquea el
# aeropuerto de Cuneo-Levaldigi» (EODI-2026-00056) y «Drone interrumpe el tráfico en el aeropuerto
# de Larnaca» (EODI-2025-00057) copiaban la de la fuente. Sin «dron», el titular tampoco se leía
# como un dron y no llevaba el «posible» de su presencia, que sí llevaba el inglés.
_DRONE_ES = re.compile(r"\bdrone\b", re.IGNORECASE)


def en_castellano(titulo: str, idioma: str) -> str:
    """El titular en español con «dron» y no «drone»."""
    if idioma != "es":
        return titulo
    return _DRONE_ES.sub(lambda m: _mayuscula("dron", m.group(0)), titulo)


def ajustar(titulo: str, presencia: str | None, idioma: str) -> str:
    """El titular coherente con la presencia (el mismo si ya lo es)."""
    titulo = _POSIBLE_REPETIDO.sub(lambda m: m.group(0).split()[0], titulo)
    titulo = concordar(en_castellano(titulo, idioma), idioma)
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
