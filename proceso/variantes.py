"""Formas declinadas y compuestas del nombre de la ciudad de una instalación.

Los titulares nombran un aeropuerto con la ciudad declinada o como adjetivo:
«Düsseldorfer Flughafen», «lotnisko w Rzeszowie», «Palangos oro uostas», «Liepājas
lidosta», «Rovaniemen lentoasema», «Göteborgs flygplats». El nomenclátor casa una ciudad
de instalación solo si el titular nombra además el tipo de lugar, así que basta con añadir
a las ciudades de cada instalación sus formas en el idioma del país. Se generan por regla,
por la terminación del nombre; una forma que no existe no hace daño (no casa con nada) y
una que sale de dos instalaciones queda ambigua y no sitúa nada.

Las formas van normalizadas (minúsculas y sin acentos), como el índice del nomenclátor.
"""

from collections.abc import Callable

Regla = Callable[[str], set[str]]
VOCALES = "aeiouy"


def _aleman(n: str) -> set[str]:
    """Adjetivo de ciudad en -er: Düsseldorfer, Frankfurter, Bremer, Münchner."""
    formas = {n + "er"}
    if n.endswith("en"):
        formas |= {n[:-2] + "er", n[:-2] + "ner"}
    if n.endswith("e"):
        formas.add(n[:-1] + "er")
    return formas


def _polaco(n: str) -> set[str]:
    """Genitivo y locativo: Rzeszowa, w Rzeszowie, w Gdańsku, Warszawy, w Warszawie."""
    if n.endswith("a"):
        raiz = n[:-1]
        return {raiz + "y", raiz + "i", raiz + "ie"}
    if n[-1] in VOCALES:
        return set()
    formas = {n + "a", n + "u", n + "ie"}
    if n.endswith(("k", "g", "ch")):
        formas.discard(n + "ie")
    if n.endswith("n"):
        formas.add(n + "iu")
    return formas


def _lituano(n: str) -> set[str]:
    """Genitivo: Kaunas → Kauno, Vilnius → Vilniaus, Palanga → Palangos, Šiauliai → Šiaulių."""
    for final, genitivos in (
        ("iai", ("iu",)),
        ("as", ("o",)),
        ("is", ("io", "ies")),
        ("us", ("aus",)),
        ("a", ("os",)),
        ("e", ("es",)),
    ):
        if n.endswith(final):
            return {n[: -len(final)] + g for g in genitivos}
    return set()


def _leton(n: str) -> set[str]:
    """Genitivo: Rīga → Rīgas, Liepāja → Liepājas, Jelgava → Jelgavas, Cēsis → Cēsu."""
    if n.endswith(("a", "e")):
        return {n + "s"}
    if n.endswith("is"):
        return {n[:-2] + "u"}
    return set()


def _estonio(n: str) -> set[str]:
    """Genitivo: Tallinn → Tallinna; los acabados en vocal no cambian (Tartu, Pärnu)."""
    return set() if n[-1] in VOCALES else {n + "a"}


def _fines(n: str) -> set[str]:
    """Genitivo: Oulu → Oulun, Rovaniemi → Rovaniemen, Turku → Turun, Helsinki → Helsingin."""
    formas = {n + "n"} if n[-1] in VOCALES else {n + "in"}
    if n.endswith("i"):
        formas.add(n[:-1] + "en")
    if n.endswith("nki"):
        formas.add(n[:-3] + "ngin")
    if n.endswith("rku"):
        formas.add(n[:-3] + "run")
    return formas


def _escandinavo(n: str) -> set[str]:
    """Genitivo en -s: Göteborgs, Aalborgs, Trondheims; sin cambio si ya acaba en s."""
    return set() if n.endswith(("s", "x", "z")) else {n + "s"}


REGLAS: dict[str, Regla] = {
    "DE": _aleman, "AT": _aleman, "CH": _aleman, "LI": _aleman, "LU": _aleman,
    "PL": _polaco,
    "LT": _lituano,
    "LV": _leton,
    "EE": _estonio,
    "FI": _fines,
    "SE": _escandinavo, "DK": _escandinavo, "NO": _escandinavo,
}  # fmt: skip
# Una forma más corta que esto casaría con palabras sueltas cualesquiera.
MIN_LETRAS = 4


def variantes(normal: str, pais: str) -> set[str]:
    """Las formas declinadas del nombre normalizado de una ciudad de una palabra."""
    regla = REGLAS.get(pais)
    if regla is None or " " in normal or len(normal) < MIN_LETRAS:
        return set()
    return {f for f in regla(normal) if len(f) >= MIN_LETRAS and f != normal}
