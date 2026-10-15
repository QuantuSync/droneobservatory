"""Primeras frases de una noticia, sacadas en memoria. La página nunca se guarda.

Solo se leen los párrafos (<p>) fuera de scripts, estilos, menús, cabeceras y
pies; los de menos de 40 letras o 6 palabras suelen ser firmas, fechas o
avisos y se saltan. Se toman las primeras frases hasta 600 letras: bastan
para lugar, hora, cierre y cifras, que las noticias dan al principio. Si la
descarga falla, el extractor recibe solo el titular.
"""

import json
import re
from dataclasses import dataclass
from html.parser import HTMLParser

from recogida.descarga import Descargador, DescargaFallida

MIN_LETRAS_PARRAFO = 40
MIN_PALABRAS_PARRAFO = 6
MAX_LETRAS = 600
_IGNORAR = frozenset({"script", "style", "noscript", "nav", "header", "footer", "aside", "form"})
_FRASE = re.compile(r"(?<=[.!?])\s+")


class _Parrafos(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parrafos: list[str] = []
        self._ignorar = 0
        self._actual: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in _IGNORAR:
            self._ignorar += 1
        elif tag == "p" and not self._ignorar:
            self._actual = []

    def handle_endtag(self, tag: str) -> None:
        if tag in _IGNORAR and self._ignorar:
            self._ignorar -= 1
        elif tag == "p" and self._actual is not None:
            self.parrafos.append(" ".join("".join(self._actual).split()))
            self._actual = None

    def handle_data(self, data: str) -> None:
        if self._actual is not None and not self._ignorar:
            self._actual.append(data)


def primeras_frases(html: str, max_letras: int = MAX_LETRAS) -> str:
    lector = _Parrafos()
    lector.feed(html)
    utiles = [
        p
        for p in lector.parrafos
        if len(p) >= MIN_LETRAS_PARRAFO and len(p.split()) >= MIN_PALABRAS_PARRAFO
    ]
    texto = ""
    for frase in (f for p in utiles for f in _FRASE.split(p)):
        if texto and len(texto) + len(frase) + 1 > max_letras:
            break
        texto = f"{texto} {frase}".strip()
    return texto[:max_letras]


def es_html(texto: str) -> bool:
    return "<p" in texto.lower()


# Las marcas que la propia página pone al artículo: tipo, sección y etiquetas (meta) y el tipo y
# la sección de sus datos estructurados (JSON-LD). Nunca los menús («Reklama» o «Užsakomasis
# turinys» están en el menú de todas las páginas de delfi.lt) ni las clases de estilo
# («sponsored-off» no dice que lo sea).
_META = frozenset({
    "og:type", "article:section", "article:tag", "article:opinion", "article:content_tier",
    "keywords", "news_keywords", "parsely-section", "parsely-tags", "sailthru.tags", "dc.type",
    "section", "category", "sponsor", "article:sponsor",
})  # fmt: skip
_CLAVES_LD = ("@type", "articleSection", "genre")
MAX_MARCAS = 24
MAX_LETRAS_MARCA = 160


class _Marcas(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.marcas: list[str] = []
        self._ld: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        atributos = {k.lower(): v or "" for k, v in attrs}
        if tag == "meta":
            nombre = (atributos.get("property") or atributos.get("name") or "").lower()
            if nombre in _META and atributos.get("content"):
                self.marcas.append(f"{nombre}={atributos['content']}")
        elif tag == "script" and atributos.get("type", "").lower() == "application/ld+json":
            self._ld = []

    def handle_endtag(self, tag: str) -> None:
        if tag == "script" and self._ld is not None:
            self._datos_estructurados("".join(self._ld))
            self._ld = None

    def handle_data(self, data: str) -> None:
        if self._ld is not None:
            self._ld.append(data)

    def _datos_estructurados(self, texto: str) -> None:
        try:
            datos = json.loads(texto)
        except ValueError:
            return
        pendientes = [datos]
        while pendientes:
            dato = pendientes.pop()
            if isinstance(dato, list):
                pendientes.extend(dato)
            elif isinstance(dato, dict):
                pendientes.extend(dato.get("@graph") or [])
                for clave in _CLAVES_LD:
                    valor = dato.get(clave)
                    valores = valor if isinstance(valor, list) else [valor]
                    self.marcas += [f"ld:{clave}={v}" for v in valores if isinstance(v, str) and v]
                if dato.get("sponsor"):
                    self.marcas.append("ld:sponsor")


def marcas(html: str) -> tuple[str, ...]:
    """Las marcas de la página, sin repetir y recortadas."""
    lector = _Marcas()
    lector.feed(html)
    unicas = dict.fromkeys(" ".join(m.split())[:MAX_LETRAS_MARCA] for m in lector.marcas)
    return tuple(unicas)[:MAX_MARCAS]


@dataclass(frozen=True)
class Pagina:
    texto: str
    marcas: tuple[str, ...] = ()


def leer_pagina(descargador: Descargador, url: str) -> Pagina:
    """Primeras frases y marcas de la noticia; vacías si no se puede descargar."""
    try:
        html = descargador.texto(url, es_html)
    except DescargaFallida:
        return Pagina("")
    return Pagina(primeras_frases(html), marcas(html))


def leer(descargador: Descargador, url: str) -> str:
    """Primeras frases de la noticia, o texto vacío si no se puede descargar."""
    return leer_pagina(descargador, url).texto
