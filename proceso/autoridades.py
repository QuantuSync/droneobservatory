"""Las autoridades y fuentes oficiales escritas en español y en inglés
(configuracion/autoridades.json), como en la web (web/src/i18n/autoridades.ts): «el Gobierno
federal alemán (Bundesregierung)». Una que no está en la tabla sale tal cual si va en alfabeto
latino y, en otra escritura, «una autoridad»: nunca otro alfabeto."""

import json
import re
import unicodedata
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


# Una autoridad que no está en la tabla se traduce como las citas (recogida/control_fichas.py),
# con esta marca delante para que el modelo la escriba como nombre, con su artículo; la
# traducción se guarda con la huella del nombre sin la marca.
MARCA = "[autoridad] "


def en_tabla(nombre: str) -> bool:
    return unicodedata.normalize("NFC", nombre) in tabla_nfc()


@cache
def tabla_nfc() -> frozenset[str]:
    return frozenset(unicodedata.normalize("NFC", n) for n in tabla())


def nombres(documento: dict[str, Any]) -> list[tuple[str, str]]:
    """Las autoridades que enseña la web de un incidente, un ataque o un impacto, con el idioma
    de su fuente: la de cada declaración citada, el nombre de cada fuente que no es un medio con
    dominio (un canal oficial, un ministerio), la que atribuye y las que investigan."""
    fuentes = [f for f in documento.get("fuentes", []) or [] if isinstance(f, dict)]
    idiomas = {str(f.get("id")): str(f.get("idioma") or "") for f in fuentes}
    salida: dict[str, str] = {}
    for fuente in fuentes:
        medio = str(fuente.get("medio") or "").strip()
        declaracion = DECLARACION.match(medio)
        nombre = declaracion.group(1) if declaracion else ("" if "." in medio else medio)
        if nombre:
            salida.setdefault(nombre, idiomas[str(fuente.get("id"))])
    atribuye = (documento.get("atribucion") or {}).get("autoridad")
    if atribuye:
        salida.setdefault(str(atribuye), "")
    for entrada in documento.get("investigacion", []) or []:
        if entrada.get("autoridad"):
            idioma = idiomas.get(str(entrada.get("fuente_id")), "")
            salida.setdefault(str(entrada["autoridad"]), idioma)
    return [(n, i) for n, i in salida.items() if any(c.isalpha() for c in n)]


def por_traducir(documento: dict[str, Any]) -> list[tuple[str, str]]:
    """Las autoridades del documento que no están en la tabla: (nombre, idioma)."""
    return [(n, i) for n, i in nombres(documento) if not en_tabla(n)]
