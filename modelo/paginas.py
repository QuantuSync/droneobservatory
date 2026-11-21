"""Primeras frases de una noticia, sacadas en memoria. La página nunca se guarda.

Solo se leen los párrafos (<p>) fuera de scripts, estilos, menús, cabeceras y
pies; los de menos de 40 letras o 6 palabras suelen ser firmas, fechas o
avisos y se saltan. Se toman las primeras frases hasta 600 letras: de ahí
saca el extractor si es un incidente, qué pasó, dónde, en qué país y qué día
(el paso 1). Si la descarga falla, el extractor recibe solo el titular.

La nota (desde el 21 de noviembre de 2026): las frases seguidas, desde el
principio, hasta 3.000 letras (MAX_LETRAS_NOTA), sin los párrafos que son casi
todo un enlace (el titular de otra noticia). De ahí saca el paso 2 los detalles
de ese mismo suceso que las noticias dan más abajo: el cierre, los vuelos, la
hora, el número de drones y lo que dicen las autoridades (modelo/detalles.py).
El 12 de noviembre de 2026, 358 de las 399 fichas publicadas tenían alguna
fuente cortada: la nota de LRT de EODI-2026-00792 cuenta el cierre de Vilna y
Kaunas en la letra 2.000. Leer la nota entera de una vez (PR #470) colaba
lugares y datos de otras noticias de la página; por eso el lugar, el país y el
día salen solo del principio.
"""

import json
import re
from dataclasses import dataclass
from html.parser import HTMLParser

from recogida.descarga import Descargador, DescargaFallida

MIN_LETRAS_PARRAFO = 40
MIN_PALABRAS_PARRAFO = 6
MAX_LETRAS = 600
MAX_LETRAS_NOTA = 3000
# Un párrafo que es casi todo él un enlace no es texto de la nota: es el titular de otra noticia
# (las listas de «más noticias» que algunos medios meten como párrafos dentro del artículo). Medido
# el 12 de noviembre de 2026: 31 de 116 páginas los tenían; en rnz.de, 21.000 letras.
PARTE_ENLACE = 0.8
_IGNORAR = frozenset({"script", "style", "noscript", "nav", "header", "footer", "aside", "form"})
_FRASE = re.compile(r"(?<=[.!?])\s+")


def _letras(texto: str) -> int:
    return len("".join(texto.split()))


class _Parrafos(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parrafos: list[str] = []
        # Por cada párrafo, si es casi todo él un enlace.
        self.enlaces: list[bool] = []
        self._ignorar = 0
        self._actual: list[str] | None = None
        self._en_enlace = 0
        self._letras_enlace = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in _IGNORAR:
            self._ignorar += 1
        elif tag == "a":
            self._en_enlace += 1
        elif tag == "p" and not self._ignorar:
            self._actual = []
            self._letras_enlace = 0

    def handle_endtag(self, tag: str) -> None:
        if tag in _IGNORAR and self._ignorar:
            self._ignorar -= 1
        elif tag == "a" and self._en_enlace:
            self._en_enlace -= 1
        elif tag == "p" and self._actual is not None:
            texto = " ".join("".join(self._actual).split())
            self.parrafos.append(texto)
            self.enlaces.append(self._letras_enlace >= PARTE_ENLACE * max(_letras(texto), 1))
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


def _utiles(html: str, sin_enlaces: bool) -> list[str]:
    lector = _Parrafos()
    lector.feed(html)
    return [
        p
        for p, enlace in zip(lector.parrafos, lector.enlaces, strict=True)
        if len(p) >= MIN_LETRAS_PARRAFO and len(p.split()) >= MIN_PALABRAS_PARRAFO
        and not (sin_enlaces and enlace)
    ]  # fmt: skip


def primeras_frases(html: str, max_letras: int = MAX_LETRAS) -> str:
    """El principio de la noticia: lo que lee el paso 1, como siempre."""
    return _hasta([f for p in _utiles(html, False) for f in _FRASE.split(p)], max_letras)


def nota(html: str, max_letras: int = MAX_LETRAS_NOTA) -> str:
    """La nota seguida, desde el principio, sin los párrafos que son el titular de otra noticia:
    lo que lee el paso 2 (modelo/detalles.py)."""
    return _hasta([f for p in _utiles(html, True) for f in _FRASE.split(p)], max_letras)


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
    # La nota hasta 3.000 letras (para el paso 2); vacía si no se pidió.
    nota: str = ""


def leer_pagina(descargador: Descargador, url: str, con_nota: bool = False) -> Pagina:
    """Primeras frases y marcas de la noticia (y, con `con_nota`, la nota); vacías si no se
    puede descargar."""
    try:
        html = descargador.texto(url, es_html)
    except DescargaFallida:
        return Pagina("")
    return Pagina(primeras_frases(html), marcas(html), nota(html) if con_nota else "")


def leer_con_nota(descargador: Descargador, url: str) -> tuple[str, str]:
    """El principio (paso 1) y la nota (paso 2) de la noticia, vacíos si no se puede descargar."""
    pagina = leer_pagina(descargador, url, con_nota=True)
    return pagina.texto, pagina.nota


def leer(descargador: Descargador, url: str) -> str:
    """Primeras frases de la noticia, o texto vacío si no se puede descargar."""
    return leer_pagina(descargador, url).texto
