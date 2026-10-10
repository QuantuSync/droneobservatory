"""IndexNow: avisa a Bing y a los demás buscadores que lo usan de las páginas nuevas o cambiadas
(docs/posicionamiento.md).

Corre al final de cada recogida que publica bien (servidor/recogida.sh). La lista de páginas sale
del sitemap de la web en vivo, con la fecha de modificación de cada una: así solo se avisa de lo
que ya está publicado (un incidente nuevo entra en el sitemap cuando la web se ha reconstruido, y
se avisa en la recogida siguiente) y de nada que no haya cambiado.

- La primera vez (sin estado), se envían todas las direcciones del sitemap, una sola vez.
- Después, solo las páginas de incidentes (en español y en inglés) nuevas o con otra fecha de
  modificación que la ya enviada.
- Por lotes (`lote` de configuracion/indexnow.json, como mucho 10 000 por petición, el límite de
  IndexNow); lo enviado queda anotado, dirección y fecha, en $INDEXNOW_DATOS/indexnow.json y no se
  repite. Un lote que falla se reintenta en la recogida siguiente.
- Antes de enviar, comprueba que la web sirve el fichero de la clave (/<clave>.txt): sin él, los
  buscadores rechazarían el envío.

Un fallo no cambia el código de la recogida.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
import urllib.error
import urllib.request
from collections.abc import Callable, Iterable, Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

registro = logging.getLogger("indexnow")

RAIZ = Path(__file__).resolve().parent.parent
CONFIGURACION = RAIZ / "configuracion" / "indexnow.json"
ESTADO = "indexnow.json"
TIEMPO_ESPERA_S = 30
LOTE_MAXIMO = 10_000
AGENTE = "EODI-bot/1.0 (+https://droneobservatory.eu)"
ESPACIO_SITEMAP = "{http://www.sitemaps.org/schemas/sitemap/0.9}"
PATRON_INCIDENTE = re.compile(r"/(?:en/)?EODI-\d{4}-\d{5}$")
RESPUESTAS_BUENAS = (200, 202)

Documento = dict[str, Any]
Descargar = Callable[[str], str]
Publicar = Callable[[Documento], int]


def configuracion(ruta: Path = CONFIGURACION) -> Documento:
    datos: Documento = json.loads(ruta.read_text(encoding="utf-8"))
    return datos


def descargar(url: str) -> str:
    peticion = urllib.request.Request(url, headers={"User-Agent": AGENTE})
    with urllib.request.urlopen(peticion, timeout=TIEMPO_ESPERA_S) as respuesta:
        texto: str = respuesta.read().decode("utf-8")
        return texto


def publicador(punto: str) -> Publicar:
    """Envía un lote a IndexNow (POST en JSON) y devuelve el código de la respuesta."""

    def publicar(cuerpo: Documento) -> int:
        peticion = urllib.request.Request(
            punto,
            data=json.dumps(cuerpo).encode("utf-8"),
            headers={"Content-Type": "application/json; charset=utf-8", "User-Agent": AGENTE},
            method="POST",
        )
        try:
            with urllib.request.urlopen(peticion, timeout=TIEMPO_ESPERA_S) as respuesta:
                codigo: int = respuesta.status
                return codigo
        except urllib.error.HTTPError as error:
            return error.code

    return publicar


# --- Qué se envía ----------------------------------------------------------------------------
def leer_sitemap(texto: str) -> dict[str, str]:
    """Dirección → fecha de modificación («» si no la trae) de cada página del sitemap."""
    raiz = ElementTree.fromstring(texto)
    paginas: dict[str, str] = {}
    for url in raiz.iter(f"{ESPACIO_SITEMAP}url"):
        loc = (url.findtext(f"{ESPACIO_SITEMAP}loc") or "").strip()
        if loc:
            paginas[loc] = (url.findtext(f"{ESPACIO_SITEMAP}lastmod") or "").strip()
    return paginas


def pendientes(sitemap: dict[str, str], enviados: dict[str, str] | None) -> list[str]:
    """La primera vez (sin nada enviado), todo; después, los incidentes nuevos o cambiados."""
    if enviados is None:
        return sorted(sitemap)
    return sorted(
        url
        for url, fecha in sitemap.items()
        if PATRON_INCIDENTE.search(url) and enviados.get(url) != fecha
    )


def lotes(urls: Iterable[str], tamano: int) -> Iterator[list[str]]:
    lista = list(dict.fromkeys(urls))  # sin repetir, en orden
    paso = max(1, min(tamano, LOTE_MAXIMO))
    for i in range(0, len(lista), paso):
        yield lista[i : i + paso]


def cuerpo(config: Documento, urls: list[str]) -> Documento:
    sitio = config["sitio"].rstrip("/")
    return {
        "host": sitio.split("://", 1)[1],
        "key": config["clave"],
        "keyLocation": f"{sitio}/{config['clave']}.txt",
        "urlList": urls,
    }


# --- Estado ----------------------------------------------------------------------------------
def leer_estado(ruta: Path) -> Documento | None:
    if not ruta.exists():
        return None
    datos: Documento = json.loads(ruta.read_text(encoding="utf-8"))
    return datos


def guardar_estado(ruta: Path, estado: Documento) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    temporal = ruta.with_name(ruta.name + ".tmp")
    temporal.write_text(
        json.dumps(estado, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8"
    )
    os.replace(temporal, ruta)


def pasar(
    config: Documento,
    estado_ruta: Path,
    bajar: Descargar,
    publicar: Publicar | None,
    ahora: datetime,
) -> tuple[int, int]:
    """Una pasada: (enviadas, fallidas). Con `publicar` None, ensayo: no envía ni anota."""
    sitio = config["sitio"].rstrip("/")
    sitemap = leer_sitemap(bajar(f"{sitio}/sitemap.xml"))
    anterior = leer_estado(estado_ruta)
    enviados: dict[str, str] | None = None if anterior is None else dict(anterior["enviados"])
    lista = pendientes(sitemap, enviados)
    if publicar is None:
        registro.info("ensayo: %d direcciones se enviarían", len(lista))
        return len(lista), 0
    if not lista:
        return 0, 0
    if bajar(f"{sitio}/{config['clave']}.txt").strip() != config["clave"]:
        raise ValueError("la web no sirve el fichero de la clave de IndexNow")
    nuevos = dict(enviados or {})
    hechas = fallidas = 0
    for lote in lotes(lista, int(config.get("lote", LOTE_MAXIMO))):
        codigo = publicar(cuerpo(config, lote))
        if codigo not in RESPUESTAS_BUENAS:
            fallidas += len(lote)
            registro.warning("IndexNow respondió %d a un lote de %d direcciones", codigo, len(lote))
            continue
        hechas += len(lote)
        nuevos.update({url: sitemap[url] for url in lote})
    if hechas:
        guardar_estado(
            estado_ruta,
            {"enviados": nuevos, "ultima": ahora.strftime("%Y-%m-%dT%H:%M:%SZ")},
        )
    return hechas, fallidas


def principal(argumentos: list[str] | None = None, ahora: datetime | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    analizador = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    analizador.add_argument("orden", choices=("enviar", "ensayo"))
    analizador.add_argument("--datos", type=Path, required=True, help="carpeta de indexnow.json")
    args = analizador.parse_args(argumentos)
    config = configuracion()
    estado = args.datos / ESTADO
    publicar = None if args.orden == "ensayo" else publicador(config["punto"])
    try:
        hechas, fallidas = pasar(config, estado, descargar, publicar, ahora or datetime.now(UTC))
    except (urllib.error.URLError, OSError, ValueError, ElementTree.ParseError) as error:
        print(f"indexnow: sin enviar ({type(error).__name__}: {error})")
        return 1
    if args.orden == "ensayo":
        print(f"indexnow: ensayo, {hechas} direcciones se enviarían")
        return 0
    print(f"indexnow: {hechas} direcciones enviadas, {fallidas} sin enviar")
    return 1 if fallidas else 0


if __name__ == "__main__":
    sys.exit(principal())
