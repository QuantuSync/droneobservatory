"""Correcciones revisadas a mano de incidentes concretos (configuracion/incidentes_revisados.json).

- **Unir**: registros del mismo suceso que las reglas de fusión no juntan, porque las noticias
  que vuelven sobre él semanas después quedan fechadas por su publicación. Se funden en el que
  elige la regla de siempre (`proceso/incidentes.destino_de`), con la fusión anotada y su motivo;
  `incidentes.revisar_fusiones` no las deshace. Si el que queda tiene un inicio posterior a su
  primera noticia, toma el de un registro unido con la fecha escrita por una fuente; si no sabe
  el cierre, toma el del registro que lo sabe.
- **Volver a extraer**: un incidente cuya ficha mezcló dos sucesos. Su candidato se extrae otra
  vez, una sola vez (cursor `revisados:<incidente>`), con una llamada directa dentro del tope de
  la revisión. Si la ficha nueva vuelve a dar el lugar o la fecha del otro suceso, el incidente
  se retira con el motivo.
"""

import copy
import json
import logging
from datetime import datetime
from functools import cache
from pathlib import Path
from typing import Any

from almacen.base import Almacen
from esquema import Documento
from proceso import extraccion, incidentes

registro = logging.getLogger(__name__)
RUTA = Path(__file__).resolve().parent.parent / "configuracion" / "incidentes_revisados.json"
CURSOR = "revisados:"


@cache
def cargar(ruta: Path = RUTA) -> dict[str, Any]:
    datos: dict[str, Any] = json.loads(ruta.read_text(encoding="utf-8"))
    return datos


def _vivo(almacen: Almacen, id_: str) -> Documento | None:
    """El registro, o aquel en que está fundido."""
    vistos = set()
    documento = almacen.incidente(id_)
    while documento is not None and "fusionado_en" in documento and id_ not in vistos:
        vistos.add(id_)
        id_ = documento["fusionado_en"]
        documento = almacen.incidente(id_)
    if documento is None or "retirado" in documento:
        return None
    return documento


def _primera_noticia(documento: Documento) -> str:
    return min(str(f["fecha"]["valor"]) for f in documento["fuentes"])


def _sin_cierre(documento: Documento) -> bool:
    return documento.get("consecuencias", {}).get("cierre", {}).get("valor") in (
        None,
        "desconocido",
    )


def completar(destino: Documento, unidos: list[Documento]) -> Documento:
    """El inicio y el cierre que le faltan al que queda y saben los registros unidos."""
    resultado = copy.deepcopy(destino)
    primera = _primera_noticia(resultado)
    if resultado["tiempo"]["inicio"]["valor"] > primera:
        escritos = sorted(
            (u for u in unidos
             if incidentes.fecha_verificada(u) and u["tiempo"]["inicio"]["valor"] <= primera),
            key=lambda u: (u["tiempo"]["inicio"]["valor"], u["id"]),
        )  # fmt: skip
        if escritos:
            resultado["tiempo"] = copy.deepcopy(escritos[0]["tiempo"])
    if _sin_cierre(resultado):
        con_cierre = [u for u in unidos if not _sin_cierre(u)]
        if con_cierre:
            resultado.setdefault("consecuencias", {})["cierre"] = copy.deepcopy(
                con_cierre[0]["consecuencias"]["cierre"]
            )
    return resultado


def unir(almacen: Almacen, ahora: datetime, modelos: frozenset[str]) -> int:
    """Funde cada grupo revisado en uno. Devuelve cuántos registros funde."""
    hechas = 0
    for grupo in cargar()["unir"]:
        vivos: dict[str, Documento] = {}
        for id_ in grupo["registros"]:
            documento = _vivo(almacen, id_)
            if documento is not None:
                vivos[documento["id"]] = documento
        if len(vivos) < 2:
            continue
        publicados = frozenset(vivos)
        destino = next(iter(vivos.values()))
        for otro in list(vivos.values())[1:]:
            destino = incidentes.destino_de(destino, otro, publicados)[0]
        unidos = [d for d in vivos.values() if d["id"] != destino["id"]]
        nuevo = destino
        fundidos = []
        for absorbido in unidos:
            nuevo, aportadas = incidentes.absorber(nuevo, absorbido, ahora)
            fundido = {**copy.deepcopy(absorbido), "fusionado_en": destino["id"]}
            fundido.pop("episodio", None)
            fundidos.append((fundido, aportadas))
        nuevo = completar(nuevo, unidos)
        almacen.guardar_incidente(nuevo, ahora, modelos)
        for fundido, aportadas in fundidos:
            almacen.guardar_incidente(fundido, ahora, modelos)
            almacen.registrar_fusion(
                ahora.strftime("%Y-%m-%dT%H:%MZ"), fundido["id"], destino["id"],
                incidentes.PREFIJO_REVISADA + grupo["motivo"], aportadas,
            )  # fmt: skip
            hechas += 1
    return hechas


def _mezcla(documento: Documento, revision: Documento) -> bool:
    """La ficha nueva vuelve a dar el lugar o la fecha del otro suceso."""
    lugar = json.dumps(documento.get("lugar", {}), ensure_ascii=False)
    return revision["no_lugar"].lower() in lugar.lower() or (
        documento["tiempo"]["inicio"]["valor"][:10] < revision["no_antes_de"]
    )


def _extraer(almacen: Almacen, cliente: Any, candidato: Documento, ahora: datetime) -> int:
    """Una llamada directa para el candidato, con la hora de la ejecución (la misma con que se
    valida lo publicado) y dentro del tope de la revisión. Devuelve cuántas llamadas hace."""
    from modelo import coste
    from recogida.descarga import Descargador
    from recogida.extractor import modelos_base, preparar_todas

    peticiones = preparar_todas(almacen, [candidato], Descargador)
    extraidas = extraccion.extraer(
        almacen, cliente, peticiones, ahora, coste.Modo.REVISION, modelos_base()
    )
    return len(extraidas.incidentes)


def reextraer(
    almacen: Almacen, cliente: Any, ahora: datetime, modelos: frozenset[str]
) -> list[str]:
    """Vuelve a extraer, una vez, el candidato de cada incidente revisado. Devuelve los
    incidentes hechos."""
    hechos = []
    candidatos = {c["id"]: c for c in almacen.candidatos()}
    for revision in cargar()["reextraer"]:
        clave = CURSOR + revision["incidente"]
        if almacen.cursor(clave) is not None or revision["candidato"] not in candidatos:
            continue
        llamadas = _extraer(almacen, cliente, candidatos[revision["candidato"]], ahora)
        if llamadas != 1:
            registro.warning("%s sin volver a extraer", revision["incidente"])
            continue
        id_ = extraccion.incidente_del_candidato(almacen, revision["candidato"])
        documento = almacen.incidente(id_) if id_ else None
        if documento is not None and incidentes.activo(documento) and _mezcla(documento, revision):
            extraccion.retirar(
                almacen, documento["id"],
                f"{revision['motivo']}; la ficha vuelta a extraer sigue mezclándolos",
                ahora, modelos,
            )  # fmt: skip
        almacen.guardar_cursor(clave, {"fecha": ahora.strftime("%Y-%m-%dT%H:%MZ"), "llamadas": 1})
        hechos.append(revision["incidente"])
    return hechos
