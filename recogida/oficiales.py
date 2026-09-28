"""Fuentes oficiales que confirman incidentes (fiabilidad A, autoridad).

Cada fuente de `configuracion/fuentes_oficiales.json` se lee respetando su
robots.txt y con la identificación del observatorio: las de tipo rss por su
canal y las de tipo pagina por su página de noticias (`paginas_oficiales`).
Una nota que habla de drones se enlaza al incidente que le
corresponde con la regla de fusión (mismo sitio y misma ventana); si encaja con
uno solo, entra como fuente de autoridad y el incidente pasa a confirmado: la
autoridad dice que ocurrió. presencia_dron solo cambia si la nota lo dice sin
reservas («bekræfter», sin «mulige» ni «formodede»). Si no encaja con ninguno o
encaja con varios, no se enlaza.

El registro solo lleva recuentos.
"""

import contextlib
import copy
import json
import logging
import re
import xml.etree.ElementTree as ET
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from functools import cache
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

from almacen.base import Almacen, DocumentoInvalido
from esquema import Documento
from proceso import incidentes
from proceso.credibilidad import Credibilidad
from proceso.estados import Estado, TransicionNoPermitida, transitar
from proceso.noticias import filtro, lugar, lugares_articulo, nomenclator
from recogida import paginas_oficiales
from recogida.descarga import AGENTE_EODI, Descargador, DescargaFallida

registro = logging.getLogger(__name__)

DIRECTORIO = Path(__file__).resolve().parent.parent / "configuracion"
MAX_PALABRAS_FRASE = 25
_FORMATOS = {"minuto": "%Y-%m-%dT%H:%MZ", "dia": "%Y-%m-%d"}
# Afirmación expresa de que había drones, sin reservas.
_AFIRMA = re.compile(r"bekræft|bestätig|confirm|potwierdz|confirmă", re.IGNORECASE)
_RESERVA = re.compile(
    r"\bmulig|formod|muligvis|mistanke|possibl|suspect|mutmaß|mögliche|podejrzan|posibil",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Nota:
    fuente: Documento
    id: str
    titulo: str
    enlace: str
    fecha: datetime
    texto: str
    precision: str = "minuto"


@dataclass
class Recuentos:
    notas: int = 0
    relevantes: int = 0
    enlazadas: int = 0
    confirmadas: int = 0
    bloqueadas: int = 0

    def resumen(self) -> str:
        return (
            f"notas={self.notas} relevantes={self.relevantes} enlazadas={self.enlazadas} "
            f"confirmadas={self.confirmadas} bloqueadas={self.bloqueadas}"
        )


@cache
def fuentes(ruta: Path = DIRECTORIO / "fuentes_oficiales.json") -> tuple[Documento, ...]:
    datos: dict[str, Any] = json.loads(ruta.read_text(encoding="utf-8"))
    return tuple(datos["fuentes"])


def robots(descargador: Descargador, url: str) -> RobotFileParser:
    partes = urlsplit(url)
    lector = RobotFileParser()
    try:
        texto = descargador.texto(f"{partes.scheme}://{partes.netloc}/robots.txt", lambda _: True)
    except DescargaFallida:
        texto = ""
    lector.parse(texto.splitlines())
    return lector


def leer_rss(texto: str, fuente: Documento) -> list[Nota]:
    notas = []
    for item in ET.fromstring(texto).iter("item"):
        enlace = (item.findtext("link") or "").strip()
        fecha = item.findtext("pubDate")
        if not enlace or not fecha:
            continue
        # Las actualizaciones de una misma nota comparten página: las distingue el fragmento.
        partes = urlsplit(enlace)
        identificador = re.sub(r"\W+", "-", partes.fragment or partes.path.rstrip("/")).strip("-")
        notas.append(
            Nota(
                fuente=fuente,
                id=f"{fuente['id']}-{identificador}".strip("-"),
                titulo=" ".join((item.findtext("title") or "").split()),
                enlace=enlace,
                fecha=parsedate_to_datetime(fecha).astimezone(UTC),
                texto=" ".join((item.findtext("description") or "").split()),
            )
        )
    return notas


def fuente_oficial(nota: Nota) -> Documento:
    return {
        "id": nota.id,
        "enlace": nota.enlace,
        "medio": nota.fuente["medio"],
        "fecha": {
            "valor": nota.fecha.strftime(_FORMATOS[nota.precision]),
            "precision": nota.precision,
        },
        "idioma": nota.fuente["idioma"],
        "fiabilidad": "A",
        "credibilidad": int(Credibilidad.CONFIRMADO),
        "frase_origen": " ".join(nota.titulo.split()[:MAX_PALABRAS_FRASE]),
        "replicas": 0,
        "campos_respaldados": ["estado"],
        "es_autoridad": True,
        "interna_fuera_de_ucrania": False,
        "publica": True,
    }


def _punto(nota: Nota) -> Documento | None:
    """El sitio de la nota como documento mínimo para la regla de fusión."""
    ids = lugares_articulo(f"{nota.titulo}. {nota.texto}", nomenclator(), filtro())
    if len(ids) != 1:
        return None
    sitio = lugar(ids[0], nomenclator())
    return {
        "id": nota.id,
        "lugar": {"punto": {"lat": sitio.lat, "lon": sitio.lon}, "radio_km": sitio.radio_km,
                  "pais": sitio.pais},
        "objetivo": {"nombre": sitio.nombre},
        "tiempo": {"inicio": {"valor": nota.fecha.strftime("%Y-%m-%dT%H:%MZ"),
                              "precision": "dia"}},
        "fuentes": [],
    }  # fmt: skip


def enlazar(almacen: Almacen, nota: Nota, ahora: datetime, modelos: frozenset[str]) -> str | None:
    """Añade la nota al único incidente que le corresponde. Devuelve su identificador."""
    punto = _punto(nota)
    if punto is None:
        return None
    encajan = [
        i
        for i in almacen.incidentes()
        if "fusionado_en" not in i and i["lugar"]["pais"] == nota.fuente["pais"]
        and incidentes.encajan(i, punto)
    ]  # fmt: skip
    if len(encajan) != 1:
        return None
    incidente = copy.deepcopy(encajan[0])
    if any(f["id"] == nota.id for f in incidente["fuentes"]):
        return str(incidente["id"])
    fuente = fuente_oficial(nota)
    incidente["fuentes"] = [*incidente["fuentes"], fuente]
    for otra in incidente["fuentes"]:
        otra["credibilidad"] = int(Credibilidad.CONFIRMADO)
    if incidente["estado"]["actual"] != Estado.CONFIRMADO:
        # Un desmentido de una autoridad más fiable no se revierte con esta nota.
        with contextlib.suppress(TransicionNoPermitida):
            incidente["estado"] = transitar(
                incidente["estado"], Estado.CONFIRMADO, fuente["fecha"], fuente["id"],
                {f["id"]: f for f in incidente["fuentes"]},
            )  # fmt: skip
    texto = f"{nota.titulo}. {nota.texto}"
    if _AFIRMA.search(texto) and not _RESERVA.search(texto):
        incidente["presencia_dron"] = "confirmada"
    incidente["control"]["ultima_actualizacion"] = {
        "valor": ahora.strftime("%Y-%m-%dT%H:%MZ"),
        "precision": "minuto",
    }
    try:
        almacen.guardar_incidente(incidente, ahora, modelos)
    except DocumentoInvalido:
        return None
    return str(incidente["id"])


def leer_pagina(descargador: Descargador, lector: RobotFileParser, fuente: Documento) -> list[Nota]:
    """Las notas de la página de noticias que pueden hablar de drones."""
    html = descargador.texto(fuente["url"], lambda t: "<" in t)
    candidatas = [
        (direccion, titulo)
        for direccion, titulo in paginas_oficiales.enlaces(html, fuente)
        if paginas_oficiales.interesa(titulo, fuente, filtro().dron)
        and lector.can_fetch(AGENTE_EODI, direccion)
    ][: paginas_oficiales.MAX_NOTAS_POR_FUENTE]
    notas = []
    for direccion, titulo in candidatas:
        try:
            articulo = descargador.texto(direccion, lambda t: "<" in t)
        except DescargaFallida:
            continue
        leido = paginas_oficiales.contenido(articulo, fuente, titulo)
        if leido is None:
            continue
        fecha, precision, texto = leido
        id_ = paginas_oficiales.identificador(fuente, direccion)
        notas.append(Nota(fuente, id_, titulo, direccion, fecha, texto, precision))
    return notas


def ejecutar(
    almacen: Almacen,
    ahora: datetime,
    modelos: frozenset[str],
    descargador: Descargador | None = None,
) -> Recuentos:
    recuentos = Recuentos()
    descargador = descargador or Descargador(agente=AGENTE_EODI)
    motivos: Counter[str] = Counter()
    for fuente in fuentes():
        lector = robots(descargador, fuente["url"])
        if not lector.can_fetch(AGENTE_EODI, fuente["url"]):
            recuentos.bloqueadas += 1
            motivos["robots"] += 1
            continue
        try:
            if fuente["tipo"] == "pagina":
                notas = leer_pagina(descargador, lector, fuente)
            else:
                notas = leer_rss(
                    descargador.texto(fuente["url"], lambda t: "<rss" in t[:200]), fuente
                )
        except (DescargaFallida, ET.ParseError):
            recuentos.bloqueadas += 1
            motivos["descarga"] += 1
            continue
        for nota in notas:
            recuentos.notas += 1
            if not filtro().dron.search(f"{nota.titulo} {nota.texto}"):
                continue
            recuentos.relevantes += 1
            antes = almacen.incidentes()
            id_ = enlazar(almacen, nota, ahora, modelos)
            if id_ is not None:
                recuentos.enlazadas += 1
                previo = next((i for i in antes if i["id"] == id_), None)
                if previo is not None and previo["estado"]["actual"] != Estado.CONFIRMADO:
                    recuentos.confirmadas += 1
    registro.info("oficiales %s motivos=%s", recuentos.resumen(), dict(motivos))
    return recuentos
