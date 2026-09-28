"""Sondeo de las fuentes oficiales candidatas: robots.txt, respuesta y tipo de contenido.

Para cada candidata de `configuracion/fuentes_oficiales_candidatas.json`: si
robots.txt deja leer la página al observatorio, el código de respuesta y si
es un canal (RSS o Atom) o una página HTML. Una sola petición por candidata,
identificándose como el observatorio. Escribe una línea por candidata con el
resultado, sin contenido.

Uso: python -m recogida.sondeo_oficiales
"""

import json
import re
import sys
from pathlib import Path
from typing import Any

from recogida.descarga import AGENTE_EODI, Descargador, DescargaFallida, NoEncontrado
from recogida.oficiales import robots

CANDIDATAS = (
    Path(__file__).resolve().parent.parent / "configuracion" / ("fuentes_oficiales_candidatas.json")
)
# Una sola petición por candidata, sin reintentos: el sondeo solo dice si se puede leer.
REINTENTOS = 0


def sondear(descargador: Descargador, candidata: dict[str, Any]) -> str:
    url = candidata["url"]
    if not robots(descargador, url).can_fetch(AGENTE_EODI, url):
        return "bloqueada_por_robots"
    try:
        texto = descargador.texto(url, lambda _: True)
    except NoEncontrado:
        return "no_encontrada"
    except DescargaFallida as error:
        codigo = re.search(r"código (\d{3})", str(error))
        return f"rechazada_{codigo[1]}" if codigo else "sin_respuesta"
    inicio = texto.lstrip()[:500].lower()
    if "<rss" in inicio or "<feed" in inicio:
        return "feed"
    if "<urlset" in inicio or "<sitemapindex" in inicio:
        return "sitemap"
    return "pagina" if "<html" in inicio or "<!doctype" in inicio else "otro"


def principal(argumentos: list[str] | None = None) -> int:
    candidatas = json.loads(CANDIDATAS.read_text(encoding="utf-8"))["candidatas"]
    descargador = Descargador(agente=AGENTE_EODI, reintentos=REINTENTOS)
    for candidata in candidatas:
        print(f"{candidata['id']} {sondear(descargador, candidata)}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(principal())
