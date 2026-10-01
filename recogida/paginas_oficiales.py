"""Lectores de las páginas de noticias de las fuentes oficiales sin canal RSS.

La página de noticias da los enlaces a las notas (los que casan con el patrón
`enlace` de la fuente) y su título. Solo se abren las notas cuyo título habla
de drones o es uno de los títulos genéricos de la fuente («Informație de
presă»), como mucho MAX_NOTAS_POR_FUENTE por ejecución. De cada nota se toma la
fecha y los primeros párrafos. La fecha sale del patrón `fecha` de la fuente si
lo tiene y, si no, de los metadatos de publicación de la página.
"""

import re
from datetime import UTC, datetime
from html.parser import HTMLParser
from urllib.parse import quote, urljoin, urlsplit
from zoneinfo import ZoneInfo

from esquema import Documento

MAX_NOTAS_POR_FUENTE = 5
MAX_PARRAFOS = 6
MAX_CARACTERES_TEXTO = 2000
MAX_CARACTERES_ID = 90
# Los párrafos más cortos suelen ser menús, pies y avisos, no el cuerpo de la nota.
MIN_CARACTERES_PARRAFO = 80
# Caracteres que se dejan tal cual al codificar una dirección (los reservados y %).
_SEGUROS_URL = ":/?#[]@!$&'()*+,;=%~"
_AVISOS = re.compile(r"cookie", re.IGNORECASE)
_OMITIDAS = frozenset({"script", "style", "noscript", "template"})
_MESES = {m: i for i, m in enumerate(
    ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"), 1
)} | {"maj": 5, "okt": 10}  # fmt: skip
_ISO = re.compile(r"(\d{4})-(\d{2})-(\d{2})(?:[T ](\d{2}):(\d{2})(?::\d{2}(?:\.\d+)?)?"
                  r"(Z|[+-]\d{2}:?\d{2})?)?")  # fmt: skip
_NUMERICA = re.compile(r"(\d{1,2})[./-](\d{1,2})[./-](\d{4})")
_CON_MES = re.compile(r"(\d{1,2})\.?\s+([^\W\d_]{3,})\.?,?\s+(\d{4})")
# Nombres completos de los meses en los idiomas de las fuentes con fecha en texto (sueco,
# danés y noruego, italiano, español, estonio, neerlandés, alemán): con solo las tres primeras
# letras, «juuni» y «juuli» serían el mismo mes.
_NOMBRES_MES = (
    ("januari", "januar", "gennaio", "enero", "jaanuar", "january"),
    ("februari", "februar", "febbraio", "febrero", "veebruar", "february"),
    ("mars", "marts", "marzo", "märts", "maart", "märz", "march"),
    ("april", "aprile", "abril", "aprill"),
    ("maj", "mai", "maggio", "mayo", "mei", "may"),
    ("juni", "giugno", "junio", "juuni", "june"),
    ("juli", "luglio", "julio", "juuli", "july"),
    ("augusti", "august", "agosto", "augustus"),
    ("september", "settembre", "septiembre", "septembre"),
    ("oktober", "ottobre", "octubre", "oktoober", "october"),
    ("november", "novembre", "noviembre"),
    ("december", "dicembre", "diciembre", "detsember", "dezember"),
)
_MESES_COMPLETOS = {nombre: i for i, nombres in enumerate(_NOMBRES_MES, 1) for nombre in nombres}
_LD_FECHA = re.compile(r'"datePublished"\s*:\s*"([^"]+)"')


class _Lector(HTMLParser):
    """Enlaces, párrafos, metadatos y texto plano de una página."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.enlaces: list[tuple[str, str]] = []
        self.parrafos: list[str] = []
        self.meta: dict[str, str] = {}
        self.tiempos: list[str] = []
        self.datos_ld: list[str] = []
        self.partes: list[str] = []
        self._omitir = 0
        self._enlace: tuple[str, list[str]] | None = None
        self._parrafo: list[str] | None = None
        self._ld: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        atributos = {k: v or "" for k, v in attrs}
        if tag in _OMITIDAS:
            self._omitir += 1
            if atributos.get("type") == "application/ld+json":
                self._ld = []
            return
        clave = atributos.get("property") or atributos.get("name") or atributos.get("itemprop")
        if tag == "a":
            self._enlace = (atributos.get("href", ""), [])
        elif tag == "p":
            self._parrafo = []
        elif tag == "meta" and clave and atributos.get("content"):
            self.meta[clave.lower()] = atributos["content"]
        elif tag == "time" and atributos.get("datetime"):
            self.tiempos.append(atributos["datetime"])
        self.partes.append(" ")

    def handle_endtag(self, tag: str) -> None:
        if tag in _OMITIDAS:
            self._omitir = max(0, self._omitir - 1)
            if self._ld is not None:
                self.datos_ld.append("".join(self._ld))
                self._ld = None
            return
        if tag == "a" and self._enlace is not None:
            self.enlaces.append((self._enlace[0], " ".join("".join(self._enlace[1]).split())))
            self._enlace = None
        elif tag == "p" and self._parrafo is not None:
            parrafo = " ".join("".join(self._parrafo).split())
            if parrafo:
                self.parrafos.append(parrafo)
            self._parrafo = None
        self.partes.append(" ")

    def handle_data(self, data: str) -> None:
        if self._ld is not None:
            self._ld.append(data)
        if self._omitir:
            return
        self.partes.append(data)
        if self._enlace is not None:
            self._enlace[1].append(data)
        if self._parrafo is not None:
            self._parrafo.append(data)

    def texto(self) -> str:
        return " ".join("".join(self.partes).split())


def leer(html: str) -> _Lector:
    lector = _Lector()
    lector.feed(html)
    lector.close()
    return lector


def enlaces(html: str, fuente: Documento) -> list[tuple[str, str]]:
    """Enlaces a notas de la página de noticias, sin repetir: (dirección, título)."""
    patron = re.compile(fuente["enlace"])
    vistos: dict[str, str] = {}
    for href, texto in leer(html).enlaces:
        # Las fechas del enlace sobran en el título: la nota trae la suya.
        titulo = re.sub(fuente.get("sobra_titulo", r"$^"), "", _NUMERICA.sub("", texto))
        titulo = " ".join(titulo.split()).strip(" ,-")
        # Las direcciones con letras no ASCII (MApN) se piden codificadas.
        direccion = quote(urljoin(fuente["url"], href).split("#")[0], safe=_SEGUROS_URL)
        if patron.search(direccion) and titulo and len(titulo) > len(vistos.get(direccion, "")):
            vistos[direccion] = titulo
    return list(vistos.items())


def interesa(titulo: str, fuente: Documento, dron: re.Pattern[str]) -> bool:
    generico = fuente.get("titulos_genericos")
    return bool(dron.search(titulo) or (generico and re.search(generico, titulo)))


def _desde_iso(valor: str, zona: ZoneInfo) -> tuple[datetime, str] | None:
    m = _ISO.match(valor.strip())
    if m is None:
        return None
    anio, mes, dia, hora, minuto, desfase = m.groups()
    if hora is None:
        return datetime(int(anio), int(mes), int(dia), tzinfo=UTC), "dia"
    instante = datetime(int(anio), int(mes), int(dia), int(hora), int(minuto))
    if (instante.hour, instante.minute) == (0, 0):
        # Medianoche local: la fuente solo da el día.
        return datetime(int(anio), int(mes), int(dia), tzinfo=UTC), "dia"
    if desfase is None:
        return instante.replace(tzinfo=zona).astimezone(UTC), "minuto"
    iso = f"{instante.isoformat()}{'+00:00' if desfase == 'Z' else desfase}"
    return datetime.fromisoformat(iso).astimezone(UTC), "minuto"


def dia_de_texto(valor: str) -> datetime | None:
    """El día que dice un texto («15-08-2024», «18. August 2025», «16 mai 2017»), o None."""
    return _desde_texto(valor)


def _desde_texto(valor: str) -> datetime | None:
    if m := _NUMERICA.search(valor):
        return datetime(int(m[3]), int(m[2]), int(m[1]), tzinfo=UTC)
    for m in _CON_MES.finditer(valor):
        nombre = m[2].lower()
        mes = _MESES_COMPLETOS.get(nombre) or _MESES.get(nombre[:3])
        if mes is not None:
            return datetime(int(m[3]), mes, int(m[1]), tzinfo=UTC)
    return None


def fecha(pagina: _Lector, fuente: Documento) -> tuple[datetime, str] | None:
    """Fecha de publicación de la nota y su precisión (minuto o dia)."""
    zona = ZoneInfo(fuente["zona"])
    if patron := fuente.get("fecha"):
        m = re.search(patron, pagina.texto())
        dia = _desde_texto(m[1]) if m else None
        return (dia, "dia") if dia else None
    candidatos = [
        pagina.meta.get("article:published_time"),
        *(m[1] for d in pagina.datos_ld for m in _LD_FECHA.finditer(d)),
        pagina.meta.get("datepublished"),
        *pagina.tiempos,
    ]
    for valor in candidatos:
        if valor and (resultado := _desde_iso(valor, zona)):
            return resultado
    return None


def identificador(fuente: Documento, direccion: str) -> str:
    ruta = urlsplit(direccion)
    marca = re.sub(r"\W+", "-", f"{ruta.path}{ruta.query}").strip("-")[-MAX_CARACTERES_ID:]
    return f"{fuente['id']}-{marca}".strip("-")


def contenido(html: str, fuente: Documento, titulo: str) -> tuple[datetime, str, str] | None:
    """Fecha, precisión y primeros párrafos de una nota; None si no se encuentra su fecha."""
    pagina = leer(html)
    publicada = fecha(pagina, fuente)
    if publicada is None:
        return None
    cuerpo = [
        p for p in pagina.parrafos
        if len(p) >= MIN_CARACTERES_PARRAFO and p != titulo and not _AVISOS.search(p)
    ]  # fmt: skip
    texto = " ".join(cuerpo[:MAX_PARRAFOS])
    return publicada[0], publicada[1], texto[:MAX_CARACTERES_TEXTO]
