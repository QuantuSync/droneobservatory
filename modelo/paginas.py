"""Primeras frases de una noticia, sacadas en memoria. La página nunca se guarda.

Solo se leen los párrafos (<p>) fuera de scripts, estilos, menús, cabeceras y
pies; los de menos de 40 letras o 6 palabras suelen ser firmas, fechas o
avisos y se saltan. Se toman las primeras frases hasta 600 letras: bastan
para lugar, hora, cierre y cifras, que las noticias dan al principio. Si la
descarga falla, el extractor recibe solo el titular.
"""

import re
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


def leer(descargador: Descargador, url: str) -> str:
    """Primeras frases de la noticia, o texto vacío si no se puede descargar."""
    try:
        return primeras_frases(descargador.texto(url, es_html))
    except DescargaFallida:
        return ""
