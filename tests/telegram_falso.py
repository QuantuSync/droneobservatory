"""Canal de Telegram falso para los tests: genera páginas t.me/s sin red."""

from dataclasses import dataclass, field
from datetime import datetime
from urllib.parse import parse_qs, urlsplit

from recogida.descarga import Descargador, Respuesta

POR_PAGINA = 3
WEB_OFICIAL = "https://sitio.oficial/fuerza-aerea"
CABECERA = """<div class="tgme_channel_info"><div class="tgme_channel_info_header">
<div class="tgme_channel_info_header_title"><span>{titulo}</span></div>
<div class="tgme_channel_info_header_labels">{insignia}</div></div>
<div class="tgme_channel_info_description">Канали: <a href="{web}">{web}</a></div></div>"""
MENSAJE = """<div class="tgme_widget_message" data-post="kpszsu/{id}">
<div class="tgme_widget_message_text js-message_text">{texto}</div>
<a class="tgme_widget_message_date" href="https://t.me/kpszsu/{id}">
<time datetime="{fecha}" class="time"></time></a></div>"""


@dataclass
class CanalFalso:
    """Publicaciones por id; sirve la portada, las páginas ?before= y la web oficial."""

    publicaciones: dict[int, tuple[datetime, str]]
    titulo: str = "Повітряні Сили ЗС України"
    verificado: bool = True
    web: str = WEB_OFICIAL
    web_enlaza: str = '<html><a href="https://t.me/kpszsu">Telegram</a></html>'
    pedidas: list[str] = field(default_factory=list)

    def html(self, antes: int | None) -> str:
        ids = sorted(i for i in self.publicaciones if antes is None or i < antes)[-POR_PAGINA:]
        insignia = '<i class="verified-icon">✔</i>' if self.verificado else ""
        partes = [CABECERA.format(titulo=self.titulo, insignia=insignia, web=self.web)]
        if ids:
            partes.append(f'<a class="tme_messages_more" data-before="{ids[0]}"></a>')
        for i in ids:
            fecha, texto = self.publicaciones[i]
            partes.append(MENSAJE.format(id=i, texto=texto, fecha=fecha.isoformat()))
        return "<html><body>" + "\n".join(partes) + "</body></html>"

    def __call__(self, url: str, cabeceras: dict[str, str], limite_s: float) -> Respuesta:
        self.pedidas.append(url)
        if url == self.web:
            return 200, {}, self.web_enlaza.encode()
        antes = parse_qs(urlsplit(url).query).get("before")
        return 200, {}, self.html(int(antes[0]) if antes else None).encode()


def descargador(canal: CanalFalso) -> Descargador:
    return Descargador(canal, dormir=lambda _: None, pausa_minima_s=0)
