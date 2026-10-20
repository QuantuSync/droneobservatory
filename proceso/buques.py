"""Sucesos en el mar y objetos alcanzados: el nombre de un buque nunca es un lugar.

El 20 de octubre de 2026 la ficha del buque Chelsea 3, alcanzado por un dron frente a la costa
búlgara, salió como «Chelsea 3, Bulgaria»: el nombre del barco como lugar, «sobrevuelo» como tipo
e «interior» como zona. Reglas, con el texto de la ficha (titular y frases de sus fuentes):

- **Nombres de buques** (y de vehículos o aeronaves): lo que sigue a «buque», «vessel»,
  «tanker», «MV»… es un nombre, no un lugar. Si el lugar del suceso es ese nombre, el lugar es la
  zona marítima que nombran las fuentes (el mar Negro, la zona económica exclusiva de un país) o,
  si no nombran ninguna, el mar.
- **En el mar**: el texto habla de un buque en el mar, de aguas territoriales o de una zona
  económica exclusiva. Un suceso en el mar de un país con costa en el mar Negro es de la costa del
  mar Negro (proceso/zona.py), nunca del interior.
- **Alcanzado**: un buque o una instalación alcanzados por un dron (impacto, explosión, restos a
  bordo) no son un sobrevuelo: el dron de un ataque así es militar y, en el mar, llegó desde
  fuera (proceso/incidentes.aplicar_reglas lo clasifica como incursión, como los buques del 13 de
  octubre de 2026, EODI-2026-00513 y 00514).
"""

import re
from collections.abc import Iterable

from proceso.noticias import normalizar

# Palabras que nombran un buque, en los idiomas de las fuentes (normalizadas: minúsculas y sin
# acentos).
_PALABRAS_BUQUE = (
    r"buque|barco|carguero|petrolero|granelero|mercante|navio|"
    r"vessel|ship|tanker|freighter|bulk carrier|cargo ship|merchant vessel|boat|"
    r"schiff|frachter|schip|vrachtschip|navire|petrolier|"
    r"nava|navei|petrolierul|vasul|statek|masowiec|tankowiec|"
    r"кораб|кораба|корабът|танкер|судно|судна|плавзасіб"
)
BUQUE = re.compile(rf"\b(?:{_PALABRAS_BUQUE})\b")
# El nombre tras la palabra (en el texto original, con mayúsculas): «vessel Chelsea 3», «buque
# «Chelsea 3»», «MV Chelsea 3», «tanker Kairos».
_NOMBRE = re.compile(
    r"(?:\b(?:MV|M/V|MT|M/T)\s+|"
    rf"(?i:\b(?:{_PALABRAS_BUQUE})\s+(?:named\s+|llamado\s+)?))"
    r"[«\"“'‘]?((?:[A-Z][\w-]*|\d+)(?:\s+(?:[A-Z][\w-]*|\d+)){0,3})[»\"”'’]?"
)
_ARTICULOS = frozenset({"the", "a", "el", "la", "un", "una", "der", "die", "das", "le", "de",
                        "in", "en", "at", "on", "off", "near", "frente", "was", "is", "fue",
                        "que"})  # fmt: skip
# El mar: un buque, aguas territoriales, una zona económica exclusiva, alta mar.
MAR = re.compile(
    r"\b(?:mar negro|black sea|marea neagra|черно море|чорне море|черное море|schwarzes meer|"
    r"mar baltico|baltic sea|ostsee|mar del norte|north sea|nordsee|noordzee|"
    r"zona economica exclusiva|exclusive economic zone|eez|zee|aguas territoriales|"
    r"territorial waters|aguas bulgaras|bulgarian waters|apele teritoriale|"
    r"alta mar|high seas|in the sea|en el mar|at sea|offshore|frente a la costa|off the coast)\b"
)
# La zona marítima que nombra el texto, por orden de detalle (es, en).
ZONAS = (
    (re.compile(r"\b(?:zona economica exclusiva|exclusive economic zone|eez)\b.{0,40}"
                r"\b(?:bulgar|bulgaria)"), ("mar Negro, zona económica exclusiva de Bulgaria",
                                            "Black Sea, Bulgarian exclusive economic zone")),
    (re.compile(r"\b(?:bulgar\w*|bulgaria)\b.{0,40}\b(?:zona economica exclusiva|exclusive "
                r"economic zone|eez)\b"), ("mar Negro, zona económica exclusiva de Bulgaria",
                                           "Black Sea, Bulgarian exclusive economic zone")),
    (re.compile(r"\b(?:mar negro|black sea|marea neagra|черно море|чорне море|черное море|"
                r"schwarzes meer)\b"), ("mar Negro", "Black Sea")),
    (re.compile(r"\b(?:mar baltico|baltic sea|ostsee)\b"), ("mar Báltico", "Baltic Sea")),
    (re.compile(r"\b(?:mar del norte|north sea|nordsee|noordzee)\b"), ("mar del Norte",
                                                                       "North Sea")),
)  # fmt: skip
# Un objeto alcanzado: impacto, explosión, ataque o restos a bordo.
ALCANZADO = re.compile(
    r"\b(?:alcanzad\w*|impactad\w*|impacto|golpead\w*|golpe[ao]n?|atacad\w*|explosion|"
    r"explot\w*|restos a bordo|struck|hit|attacked|exploded|debris (?:found )?(?:aboard|on board)|"
    r"drone-struck|getroffen|angegriffen|explosie|lovit\w*|atacat\w*|"
    r"ударен\w*|атакуван\w*|поразен\w*|уцелен\w*)\b"
)


def _plano(texto: str) -> str:
    return normalizar(texto)


def nombres_de_buques(textos: Iterable[str]) -> set[str]:
    """Los nombres de buques que dan los textos (en minúsculas y sin acentos)."""
    nombres: set[str] = set()
    for texto in textos:
        for hallado in _NOMBRE.finditer(str(texto)):
            palabras = hallado.group(1).split()
            while palabras and palabras[0].lower() in _ARTICULOS:
                palabras = palabras[1:]
            while palabras and palabras[-1].lower() in _ARTICULOS:
                palabras = palabras[:-1]
            if not palabras or not palabras[0][0].isupper():
                continue
            nombre = _plano(" ".join(palabras))
            if len(nombre) >= 3 and not BUQUE.fullmatch(nombre):
                nombres.add(nombre)
    return nombres


def es_nombre_de_buque(nombre: str | None, textos: Iterable[str]) -> bool:
    """El nombre (de un lugar) es el de un buque que nombran los textos, solo o seguido del país
    («Chelsea 3», «Chelsea 3, Bulgaria»)."""
    if not nombre:
        return False
    plano = _plano(str(nombre).split(",")[0]).strip()
    return bool(plano) and any(
        plano == buque or plano.startswith(buque + " ") or buque.startswith(plano + " ")
        for buque in nombres_de_buques(textos)
    )


def en_el_mar(textos: Iterable[str]) -> bool:
    """Los textos sitúan el suceso en el mar: un buque y el mar o una zona marítima."""
    planos = [_plano(str(t)) for t in textos]
    return any(MAR.search(t) for t in planos) and any(BUQUE.search(t) for t in planos)


def zona_maritima(textos: Iterable[str]) -> tuple[str, str] | None:
    """La zona marítima más detallada que nombran los textos, en español y en inglés."""
    planos = [_plano(str(t)) for t in textos]
    for patron, nombres in ZONAS:
        if any(patron.search(t) for t in planos):
            return nombres
    return None


def alcanzado(textos: Iterable[str]) -> bool:
    """Un buque alcanzado por un dron: los textos hablan de un buque y de un impacto, un ataque,
    una explosión o restos a bordo."""
    planos = [_plano(str(t)) for t in textos]
    return any(BUQUE.search(t) for t in planos) and any(ALCANZADO.search(t) for t in planos)


def textos_de(incidente: dict) -> list[str]:  # type: ignore[type-arg]
    """El titular y las frases de las fuentes de un incidente."""
    textos = [str(t) for t in (incidente.get("titulo") or {}).values()]
    for fuente in incidente.get("fuentes", []):
        for campo in ("frase_origen", "titular"):
            if fuente.get(campo):
                textos.append(str(fuente[campo]))
    return textos
