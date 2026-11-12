"""Lo que se lee de una noticia, sacado en memoria. La página nunca se guarda.

Solo se leen los párrafos (<p>) fuera de scripts, estilos, menús, cabeceras y
pies; los de menos de 40 letras o 6 palabras suelen ser firmas, fechas o
avisos y se saltan. Se toman las frases seguidas, desde el principio, hasta
3.000 letras (MAX_LETRAS): la nota entera en dos de cada tres noticias (la
mediana de las fuentes de las fichas publicadas es de 2.000 letras). Si la
descarga falla, el extractor recibe solo el titular.

Hasta el 12 de noviembre de 2026 se tomaban las 600 primeras letras («bastan
para lugar, hora, cierre y cifras, que las noticias dan al principio»). No
bastaban: la nota de LRT de la noche del 10 al 11 de noviembre
(EODI-2026-00792, 9.000 letras) cuenta el dron que entró desde Bielorrusia en
la letra 1.100 y el cierre de los aeropuertos de Vilna y Kaunas en la 2.000, y
ninguna extracción los recogió; medido ese día, 358 de las 399 fichas
publicadas tenían alguna fuente cortada. Se lee seguido y no eligiendo frases
sueltas de más abajo: probado en una reproducción de tres días, una frase
suelta sin las de su alrededor se lee mal (los restos hallados un sábado en
Liepna, Letonia, salieron como un suceso nuevo de ese sábado; cinco frases
después la nota dice que son del objeto que cayó el 18 de octubre).

Lo que solo necesita el principio (comparar dos fichas, el filtro de entrada)
sigue recibiendo las 600 primeras letras (`principio`).
"""

import json
import re
from dataclasses import dataclass
from html.parser import HTMLParser

from recogida.descarga import Descargador, DescargaFallida

MIN_LETRAS_PARRAFO = 40
MIN_PALABRAS_PARRAFO = 6
MAX_LETRAS = 3000
# El principio de la nota: lo que se leía antes y lo que sigue bastando para comparar fichas.
MAX_LETRAS_PRINCIPIO = 600
_IGNORAR = frozenset({"script", "style", "noscript", "nav", "header", "footer", "aside", "form"})
_FRASE = re.compile(r"(?<=[.!?])\s+")


# Un párrafo que es casi todo él un enlace no es texto de la nota: es el titular de otra noticia
# (las listas de «más noticias» que algunos medios meten como párrafos dentro del artículo). Con
# 600 letras apenas entraban; con 3.000, la página de b92.net de la noche del 10 al 11 de
# noviembre de 2026 (EODI-2026-00782) era su primera frase y una ristra de titulares de otras
# noticias, y la ficha salió con el lugar y la presencia de uno de ellos.
PARTE_ENLACE = 0.8


def _letras(texto: str) -> int:
    return len("".join(texto.split()))


class _Parrafos(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parrafos: list[str] = []
        self._ignorar = 0
        self._actual: list[str] | None = None
        self._en_enlace = False
        self._letras_enlace = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in _IGNORAR:
            self._ignorar += 1
        elif tag == "a":
            self._en_enlace = True
        elif tag == "p" and not self._ignorar:
            self._actual = []
            self._letras_enlace = 0

    def handle_endtag(self, tag: str) -> None:
        if tag in _IGNORAR and self._ignorar:
            self._ignorar -= 1
        elif tag == "a":
            self._en_enlace = False
        elif tag == "p" and self._actual is not None:
            texto = " ".join("".join(self._actual).split())
            if self._letras_enlace < PARTE_ENLACE * _letras(texto):
                self.parrafos.append(texto)
            self._actual = None

    def handle_data(self, data: str) -> None:
        if self._actual is not None and not self._ignorar:
            self._actual.append(data)
            if self._en_enlace:
                self._letras_enlace += _letras(data)


def _hasta(frases: list[str], max_letras: int) -> str:
    """Las frases seguidas, desde la primera, que caben en `max_letras`."""
    texto = ""
    for frase in frases:
        if texto and len(texto) + len(frase) + 1 > max_letras:
            break
        texto = f"{texto} {frase}".strip()
    return texto[:max_letras]


def primeras_frases(html: str, max_letras: int = MAX_LETRAS) -> str:
    """Las frases de los párrafos útiles de la página, seguidas, hasta `max_letras`."""
    lector = _Parrafos()
    lector.feed(html)
    utiles = [
        p
        for p in lector.parrafos
        if len(p) >= MIN_LETRAS_PARRAFO and len(p.split()) >= MIN_PALABRAS_PARRAFO
    ]
    return _hasta([f for p in utiles for f in _FRASE.split(p)], max_letras)


def principio(texto: str, max_letras: int = MAX_LETRAS_PRINCIPIO) -> str:
    """El principio de lo leído de una nota (`primeras_frases`): sus primeras frases hasta
    `max_letras`, lo mismo que se leía cuando el tope de la nota era ese."""
    return _hasta(_FRASE.split(texto), max_letras) if len(texto) > max_letras else texto


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
