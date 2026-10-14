"""Las autoridades y fuentes oficiales escritas en español y en inglés, con la misma regla que la
web (web/src/i18n/autoridades.ts): primero la tabla revisada (configuracion/autoridades.json:
«el Gobierno federal alemán (Bundesregierung)»); después la traducción que viaja con la ficha
publicada (`autoridades`, exportacion/citas.con_autoridades); si no hay, «una autoridad» / «an
authority». Nunca un nombre en otra lengua. La usan los avisos de ntfy y el resumen diario."""

import json
import re
import unicodedata
from functools import cache
from pathlib import Path
from typing import Any

TABLA = Path(__file__).resolve().parent.parent / "configuracion" / "autoridades.json"
SIN_NOMBRE = {"es": "una autoridad", "en": "an authority"}
DECLARACION = re.compile(r"^(.+) \(declaración oficial citada en .+\)$")
# En un texto solo se buscan nombres de autoridad con al menos estas letras: uno más corto
# («MoD», «ISW») se confunde con otras palabras.
MIN_LETRAS_EN_TEXTO = 6


@cache
def tabla() -> dict[str, Any]:
    return dict(json.loads(TABLA.read_text(encoding="utf-8"))["autoridades"])


Traducidas = dict[str, Any]


def _traducida(original: str, idioma: str, traducidas: Traducidas | None) -> str | None:
    """La traducción que viaja con la ficha publicada (nombre -> {es, en}), en forma compuesta."""
    nombre = unicodedata.normalize("NFC", original)
    for clave, traduccion in (traducidas or {}).items():
        if unicodedata.normalize("NFC", clave) != nombre or not isinstance(traduccion, dict):
            continue
        es, en = str(traduccion.get("es") or "").strip(), str(traduccion.get("en") or "").strip()
        if es and en:
            return es if idioma == "es" else en
    return None


def _de_tabla(original: str, idioma: str) -> str | None:
    nombre = unicodedata.normalize("NFC", original)
    conocida = next((v for k, v in tabla().items() if unicodedata.normalize("NFC", k) == nombre),
                    None)  # fmt: skip
    if conocida is None:
        return None
    texto = str(conocida[idioma])
    return f"{texto} ({original})" if conocida.get("original") else texto


def conocida(original: str, traducidas: Traducidas | None = None) -> bool:
    """Si la autoridad se sabe escribir en el idioma del texto (tabla o traducción)."""
    de_tabla = _de_tabla(original, "es")
    return de_tabla is not None or _traducida(original, "es", traducidas) is not None


def escrita(original: str, idioma: str, traducidas: Traducidas | None = None) -> str:
    """La autoridad en el idioma del texto: la tabla, la traducción de la ficha o «una
    autoridad»."""
    if not any(c.isalpha() for c in original):
        return original
    return (
        _de_tabla(original, idioma)
        or _traducida(original, idioma, traducidas)
        or SIN_NOMBRE[idioma]
    )


def de_la_fuente(medio: str, idioma: str, traducidas: Traducidas | None = None) -> str:
    """Quién da la fuente: de una declaración citada, la autoridad; si no, el medio. Un medio
    con dominio (un periódico: «novinite.com») sale tal cual, como en la web."""
    declaracion = DECLARACION.match(medio)
    if declaracion:
        return escrita(declaracion.group(1), idioma, traducidas)
    if "." in medio and not conocida(medio, traducidas):
        return medio
    return escrita(medio, idioma, traducidas)


def en_texto(texto: str, idioma: str, traducidas: Traducidas | None = None) -> str:
    """Un texto generado (un titular) con cada autoridad de la tabla o de la ficha que aparezca
    con su nombre original escrita en el idioma del texto."""
    nombres = {**dict.fromkeys(tabla()), **dict.fromkeys(traducidas or {})}
    for nombre in sorted(nombres, key=len, reverse=True):
        if len(nombre) < MIN_LETRAS_EN_TEXTO or nombre not in texto:
            continue
        escrito = escrita(nombre, idioma, traducidas)
        if escrito != nombre and escrito not in texto:
            patron = rf"(?<!\w){re.escape(nombre)}(?!\w)"
            # El nombre escrito va literal: sus barras no son referencias del patrón.
            texto = re.sub(patron, escrito.replace("\\", r"\\"), texto)
    return texto


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
