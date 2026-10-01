"""Lectura de la vista pública web de un canal de Telegram (t.me/s/<canal>).

Cada página trae la cabecera del canal y unas 20 publicaciones; el enlace
"más" indica el identificador desde el que seguir hacia atrás con ?before=.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from html.parser import HTMLParser

BASE = "https://t.me"


@dataclass(frozen=True)
class Publicacion:
    canal: str
    id: int
    fecha: datetime
    texto: str
    # Publicación a la que responde (Rosaviatsia levanta así cada restricción).
    responde_a: int | None = None

    @property
    def enlace(self) -> str:
        return f"{BASE}/{self.canal}/{self.id}"


@dataclass(frozen=True)
class Canal:
    titulo: str
    verificado: bool
    enlaces_descripcion: tuple[str, ...]


@dataclass(frozen=True)
class Pagina:
    canal: Canal | None
    publicaciones: tuple[Publicacion, ...]
    anterior: int | None


def url_pagina(canal: str, antes: int | None = None) -> str:
    return f"{BASE}/s/{canal}" + (f"?before={antes}" if antes is not None else "")


def es_pagina_de_canal(html: str) -> bool:
    """Contenido real: la cabecera del canal está presente."""
    return "tgme_channel_info_header_title" in html


@dataclass
class _Mensaje:
    post: str
    fecha: str = ""
    partes: list[str] = field(default_factory=list)
    responde_a: int | None = None


class _Lector(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        # Clases de los div abiertos: el HTML de Telegram cierra bien sus div.
        self.pila: list[str] = []
        self.mensajes: list[_Mensaje] = []
        self.titulo: list[str] = []
        self.verificado = False
        self.enlaces: list[str] = []
        self.anterior: int | None = None
        self._texto_en: int | None = None
        self._en_fecha = False

    def _dentro(self, clase: str) -> bool:
        return any(clase in c.split() for c in self.pila)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        atributos = {k: v or "" for k, v in attrs}
        clase = atributos.get("class", "")
        clases = clase.split()
        if tag == "div":
            self.pila.append(clase)
            if "data-post" in atributos:
                self.mensajes.append(_Mensaje(atributos["data-post"]))
            elif "js-message_text" in clases and self.mensajes and self._texto_en is None:
                self._texto_en = len(self.pila)
        elif tag == "br" and self._texto_en is not None:
            self.mensajes[-1].partes.append("\n")
        elif tag == "a":
            if "tgme_widget_message_reply" in clases and self.mensajes:
                numero = atributos.get("href", "").rstrip("/").rpartition("/")[2]
                if numero.isdigit():
                    self.mensajes[-1].responde_a = int(numero)
            if "tgme_widget_message_date" in clases:
                self._en_fecha = True
            elif "tme_messages_more" in clases and atributos.get("data-before", "").isdigit():
                self.anterior = int(atributos["data-before"])
            elif self._dentro("tgme_channel_info_description") and atributos.get("href"):
                self.enlaces.append(atributos["href"])
        elif tag == "time" and self._en_fecha and self.mensajes:
            self.mensajes[-1].fecha = atributos.get("datetime", "")
        elif tag == "i" and "verified-icon" in clases and self._dentro("tgme_channel_info_header"):
            self.verificado = True

    def handle_endtag(self, tag: str) -> None:
        if tag == "div" and self.pila:
            if self._texto_en == len(self.pila):
                self._texto_en = None
            self.pila.pop()
        elif tag == "a":
            self._en_fecha = False

    def handle_data(self, data: str) -> None:
        if self._texto_en is not None:
            self.mensajes[-1].partes.append(data)
        elif self._dentro("tgme_channel_info_header_title"):
            self.titulo.append(data)


def leer_pagina(html: str) -> Pagina:
    lector = _Lector()
    lector.feed(html)
    lector.close()
    canal = None
    if es_pagina_de_canal(html):
        canal = Canal(
            titulo="".join(lector.titulo).strip(),
            verificado=lector.verificado,
            enlaces_descripcion=tuple(lector.enlaces),
        )
    publicaciones = []
    for mensaje in lector.mensajes:
        nombre, _, numero = mensaje.post.partition("/")
        if not numero.isdigit() or not mensaje.fecha:
            continue
        publicaciones.append(
            Publicacion(
                canal=nombre,
                id=int(numero),
                fecha=datetime.fromisoformat(mensaje.fecha).astimezone(UTC),
                texto="".join(mensaje.partes).strip(),
                responde_a=mensaje.responde_a,
            )
        )
    return Pagina(canal, tuple(publicaciones), lector.anterior)
