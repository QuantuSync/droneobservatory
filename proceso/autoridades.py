"""Las autoridades y fuentes oficiales escritas en español y en inglés
(configuracion/autoridades.json), como en la web (web/src/i18n/autoridades.ts): «el Gobierno
federal alemán (Bundesregierung)». Una que no está en la tabla sale tal cual si va en alfabeto
latino y, en otra escritura, «una autoridad»: nunca otro alfabeto."""

import json
import re
from functools import cache
from pathlib import Path
from typing import Any

from proceso.nombres_lugar import latino_puro

TABLA = Path(__file__).resolve().parent.parent / "configuracion" / "autoridades.json"
SIN_NOMBRE = {"es": "una autoridad", "en": "an authority"}
DECLARACION = re.compile(r"^(.+) \(declaración oficial citada en .+\)$")


@cache
def tabla() -> dict[str, Any]:
    return dict(json.loads(TABLA.read_text(encoding="utf-8"))["autoridades"])


def escrita(original: str, idioma: str) -> str:
    conocida = tabla().get(original)
    if conocida is None:
        letras = [c for c in original if c.isalpha()]
        return original if not letras or latino_puro(original) else SIN_NOMBRE[idioma]
    texto = str(conocida[idioma])
    return f"{texto} ({original})" if conocida.get("original") else texto


def de_la_fuente(medio: str, idioma: str) -> str:
    """Quién da la fuente: de una declaración citada, la autoridad; si no, el medio."""
    declaracion = DECLARACION.match(medio)
    return escrita(declaracion.group(1) if declaracion else medio, idioma)
