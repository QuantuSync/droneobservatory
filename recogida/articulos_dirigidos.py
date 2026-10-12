"""Artículos dirigidos: noticias concretas que se hacen entrar por el flujo normal.

Para un incidente que GDELT no trajo (un medio que no indexa, un territorio de fuera del
continente, una noticia sin la señal que pide el filtro general), se apuntan sus fuentes en
configuracion/articulos_dirigidos.json: dirección, medio, fecha de publicación, idioma, país del
medio, titular literal y el lugar del nomenclátor donde ocurre. En cada recogida horaria, los que
aún no están entran como artículos de ese lugar y se agrupan en su candidato (o abren uno), como
los de la búsqueda dirigida; el extractor los lleva delante de todos (recogida/extractor.py,
`prioritarios`) y la ficha, la validación, la barrera y la publicación son las de siempre: el
estado (notificado, confirmado, atribuido) lo dan solo las fuentes oficiales que cite la ficha. Un
incidente antiguo no se avisa por ntfy (la regla de las 72 horas de recogida/avisos.py).

Cada artículo entra una sola vez (cursor `articulos_dirigidos` de la base, con sus candidatos).
"""

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from almacen.base import Almacen
from esquema import Documento
from proceso.noticias import nomenclator, titular_normalizado

registro = logging.getLogger("recogida")

RUTA = Path(__file__).resolve().parent.parent / "configuracion" / "articulos_dirigidos.json"
FUENTE_ID = "articulos_dirigidos"
MOTIVO = "artículo dirigido: fuente apuntada a mano para un incidente que no trajo GDELT"
CAMPOS = ("url", "medio", "fecha", "idioma", "pais", "titular", "lugar")


def cargar(ruta: Path = RUTA) -> list[dict[str, Any]]:
    if not ruta.exists():
        return []
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    return list(datos.get("articulos", []))


def _fecha(texto: str) -> str:
    momento = datetime.fromisoformat(texto.replace("Z", "+00:00")).astimezone(UTC)
    return momento.strftime("%Y-%m-%dT%H:%M:%SZ")


def candidatos(almacen: Almacen) -> set[str]:
    """Los candidatos donde entraron artículos dirigidos."""
    cursor = almacen.cursor(FUENTE_ID) or {}
    return {c for entrada in cursor.values() if isinstance(entrada, dict)
            for c in entrada.get("candidatos", [])}  # fmt: skip


def paso_horario(almacen: Almacen, ahora: datetime, ruta: Path = RUTA) -> int:
    """Incorpora los artículos dirigidos que aún no están. Devuelve cuántos entraron."""
    from recogida.calidad import situar_en_candidatos

    cursor: dict[str, Any] = dict(almacen.cursor(FUENTE_ID) or {})
    nom = nomenclator()
    entraron = 0
    for articulo in cargar(ruta):
        url = articulo["url"]
        if url in cursor:
            continue
        faltan = [c for c in CAMPOS if not articulo.get(c)]
        if faltan or articulo["lugar"] not in nom.lugares:
            motivo = f"faltan {', '.join(faltan)}" if faltan else "lugar desconocido"
            registro.warning("artículo dirigido %s sin entrar: %s", url, motivo)
            continue
        documento: Documento = {
            "url": url, "medio": articulo["medio"], "fecha": _fecha(articulo["fecha"]),
            "idioma": articulo["idioma"], "pais": articulo["pais"], "titular": articulo["titular"],
            "titular_normalizado": titular_normalizado(articulo["titular"]), "temas": [],
            "lugares": [articulo["lugar"]],
        }  # fmt: skip
        if not almacen.guardar_articulo(documento):
            existente = almacen.articulos_de([url])
            if existente:
                documento = {**existente[0], "lugares": [articulo["lugar"]]}
        tocados = situar_en_candidatos(almacen, [(documento, [articulo["lugar"]])], MOTIVO)
        cursor[url] = {"entrado": ahora.strftime("%Y-%m-%dT%H:%MZ"), "candidatos": tocados}
        entraron += 1
        registro.info("artículo dirigido %s en %s", url, ", ".join(tocados))
    if entraron:
        almacen.guardar_cursor(FUENTE_ID, cursor)
    return entraron
