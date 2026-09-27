"""Fuente: noticias europeas sobre drones en la API DOC 2.0 de GDELT (fiabilidad C3).

Modo artlist en JSON, hasta 250 artículos por llamada, con los filtros dentro
del parámetro query: palabras de dron en los idiomas europeos y medios de
países europeos. Una ventana que llega a 250 se parte en dos hasta que cabe.

Los artículos pasan un filtro sin modelo, se deduplican (misma URL canónica o
titular casi idéntico) y se agrupan en candidatos provisionales. No se publica
nada: el extractor que convierte candidatos en incidentes va en el siguiente PR.
"""

import json
import logging
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlencode

from almacen.base import Almacen
from esquema import Documento
from proceso.noticias import (
    VENTANA_REPLICAS,
    Agrupacion,
    Articulo,
    Candidato,
    Filtro,
    Nomenclator,
    agrupar,
    casi_iguales,
    configuracion,
    filtro,
    lugares_en,
    nomenclator,
    titular_normalizado,
    url_canonica,
)
from recogida.descarga import Descargador, DescargaFallida

registro = logging.getLogger(__name__)

API = "https://api.gdeltproject.org/api/v2/doc/doc"
FUENTE_ID = "gdelt"
MAX_RESULTADOS = 250
# La API pide una petición cada 5 segundos como mucho (lo dice su propia respuesta
# 429): 6 s dejan un margen para el reloj y la latencia.
PAUSA_S = 6.0
PAUSAS = {"api.gdeltproject.org": PAUSA_S}
# Desde un runner de GitHub, 38 de 45 peticiones espaciadas dieron 429 (84 %). Con 6
# reintentos y esperas de 10 s dobladas (de 10 s a 320 s, 10,5 minutos como mucho),
# una consulta sale adelante en el 79 % de las ejecuciones (1 - 0,84^7); si no, el
# cursor espera a la siguiente hora.
REINTENTOS = 6
ESPERA_INICIAL_S = 10.0


def descargador() -> Descargador:
    return Descargador(
        pausas_por_sitio=PAUSAS, reintentos=REINTENTOS, espera_inicial_s=ESPERA_INICIAL_S
    )


# La API indexa cada 15 minutos: una ventana más corta no se puede partir.
VENTANA_MINIMA = timedelta(minutes=15)
# Cada ejecución vuelve a pedir la última hora ya leída: la API tarda en indexar
# algunos artículos y aparecen con fecha anterior a la última consulta.
SOLAPE = timedelta(hours=1)
# Sin cursor, la primera ejecución empieza un día atrás.
PRIMERA_VENTANA = timedelta(days=1)
# Países por consulta: 21, dos consultas por ventana. Menos consultas es menos
# peticiones bajo el límite de la API, y una consulta de 21 países (unos 600
# caracteres) queda lejos de los 2000 de una URL segura.
PAISES_POR_CONSULTA = 21
# Si la API no responde, el cursor no avanza y la siguiente ejecución recupera el
# hueco. Solo cuando el hueco pasa de un día la ejecución queda en rojo.
HUECO_TOLERADO = timedelta(days=1)
_FORMATO = "%Y%m%d%H%M%S"


class GdeltNoDisponible(RuntimeError):
    pass


@dataclass
class Recuentos:
    recibidos: int = 0
    ya_vistos: int = 0
    descartados: int = 0
    replicas: int = 0
    nuevos: int = 0
    agrupados: int = 0
    candidatos_nuevos: int = 0
    motivos: Counter[str] = field(default_factory=Counter)

    def resumen(self) -> str:
        return (
            f"recibidos={self.recibidos} ya_vistos={self.ya_vistos} "
            f"descartados={self.descartados} replicas={self.replicas} nuevos={self.nuevos} "
            f"agrupados={self.agrupados} candidatos_nuevos={self.candidatos_nuevos}"
        )


# --- Consulta ----------------------------------------------------------------------


def _termino(palabra: str) -> str:
    return f'"{palabra}"' if " " in palabra else palabra


def consultas(config: dict[str, Any] | None = None) -> list[str]:
    """Una consulta por grupo de países con las palabras de la consulta (en inglés)."""
    config = config or configuracion()
    drones = "(" + " OR ".join(_termino(p) for p in config["consulta"]) + ")"
    paises = sorted(config["paises"])
    grupos = [
        paises[i : i + PAISES_POR_CONSULTA] for i in range(0, len(paises), PAISES_POR_CONSULTA)
    ]
    return [drones + " (" + " OR ".join(f"sourcecountry:{p}" for p in g) + ")" for g in grupos]


def url_consulta(consulta: str, inicio: datetime, fin: datetime) -> str:
    parametros = {
        "query": consulta,
        "mode": "artlist",
        "format": "json",
        "maxrecords": str(MAX_RESULTADOS),
        "sort": "dateasc",
        "startdatetime": inicio.astimezone(UTC).strftime(_FORMATO),
        "enddatetime": fin.astimezone(UTC).strftime(_FORMATO),
    }
    return f"{API}?{urlencode(parametros)}"


def es_json(texto: str) -> bool:
    """La API responde 200 con un texto de error si la consulta no le gusta."""
    return texto.lstrip()[:1] == "{"


def pedir(
    descargador: Descargador, consulta: str, inicio: datetime, fin: datetime
) -> list[dict[str, Any]]:
    """Artículos de la ventana. Si llega a 250, parte la ventana en dos."""
    texto = descargador.texto(url_consulta(consulta, inicio, fin), es_json)
    articulos: list[dict[str, Any]] = json.loads(texto).get("articles", [])
    if len(articulos) < MAX_RESULTADOS or fin - inicio <= VENTANA_MINIMA:
        return articulos
    mitad = inicio + (fin - inicio) / 2
    return pedir(descargador, consulta, inicio, mitad) + pedir(descargador, consulta, mitad, fin)


# --- Artículos ---------------------------------------------------------------------


def _clave(nombre: str) -> str:
    return "".join(nombre.lower().split())


def articulo(bruto: dict[str, Any], config: dict[str, Any], nom: Nomenclator) -> Articulo:
    titular = " ".join(str(bruto.get("title", "")).split())
    paises = config["paises"]
    return Articulo(
        url=url_canonica(bruto["url"]),
        medio=str(bruto.get("domain") or ""),
        fecha=datetime.strptime(bruto["seendate"], "%Y%m%dT%H%M%SZ").replace(tzinfo=UTC),
        titular=titular,
        idioma=config["idiomas"].get(bruto.get("language", "")),
        pais=paises.get(_clave(str(bruto.get("sourcecountry", "")))),
        lugares=lugares_en(titular, nom),
    )


def _fecha(momento: datetime) -> str:
    return momento.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _documento_articulo(a: Articulo) -> Documento:
    return {
        "url": a.url,
        "medio": a.medio,
        "fecha": _fecha(a.fecha),
        "idioma": a.idioma,
        "pais": a.pais,
        "titular": a.titular,
        "titular_normalizado": titular_normalizado(a.titular),
        "temas": list(a.temas),
        "lugares": list(a.lugares),
    }


def _documento_candidato(c: Candidato) -> Documento:
    return {
        "id": c.id,
        "tipo": c.tipo,
        "lugar": c.lugar.id,
        "inicio": _fecha(c.inicio),
        "ultimo": _fecha(c.ultimo),
        "precision": c.precision,
        "articulos": c.articulos,
    }


def _candidato(documento: Documento, nom: Nomenclator) -> Candidato:
    return Candidato(
        id=documento["id"],
        tipo=documento["tipo"],
        lugar=nom.lugares[documento["lugar"]],
        inicio=datetime.fromisoformat(documento["inicio"]),
        ultimo=datetime.fromisoformat(documento["ultimo"]),
        precision=documento["precision"],
        articulos=list(documento["articulos"]),
    )


def incorporar(
    almacen: Almacen,
    brutos: list[dict[str, Any]],
    filtro_: Filtro | None = None,
    nom: Nomenclator | None = None,
    config: dict[str, Any] | None = None,
) -> Recuentos:
    """Filtra, deduplica, guarda y agrupa los artículos recibidos."""
    filtro_, nom, config = filtro_ or filtro(), nom or nomenclator(), config or configuracion()
    recuentos = Recuentos(recibidos=len(brutos))
    recibidos = sorted((articulo(b, config, nom) for b in brutos), key=lambda x: (x.fecha, x.url))
    if not recibidos:
        return recuentos
    # Titulares ya guardados en la ventana de réplicas, con su fecha, más los que entran ahora.
    titulares = [
        (datetime.fromisoformat(f), url, t)
        for url, t, f in almacen.titulares_desde(_fecha(recibidos[0].fecha - VENTANA_REPLICAS))
    ]
    vistos: set[str] = set()
    nuevos: list[Articulo] = []
    for a in recibidos:
        if a.url in vistos or almacen.existe_articulo(a.url):
            recuentos.ya_vistos += 1
            continue
        vistos.add(a.url)
        if not filtro_.pasa(a.titular, a.lugares):
            recuentos.descartados += 1
            continue
        normal = titular_normalizado(a.titular)
        limite = a.fecha - VENTANA_REPLICAS
        original = next(
            (url for f, url, otro in titulares if f >= limite and casi_iguales(normal, otro)),
            None,
        )
        if original is not None:
            almacen.sumar_replica(original)
            recuentos.replicas += 1
            continue
        almacen.guardar_articulo(_documento_articulo(a))
        titulares.append((a.fecha, a.url, normal))
        nuevos.append(a)
    recuentos.nuevos = len(nuevos)
    if not nuevos:
        return recuentos
    desde = _fecha(nuevos[0].fecha - timedelta(hours=12))
    previos = [_candidato(d, nom) for d in almacen.candidatos_desde(desde)]
    conocidos = {c.id for c in previos}
    agrupacion = agrupar(nuevos, filtro_, nom, Agrupacion(candidatos=previos))
    for candidato in agrupacion.candidatos:
        almacen.guardar_candidato(_documento_candidato(candidato))
        recuentos.candidatos_nuevos += candidato.id not in conocidos
        for url in candidato.articulos:
            almacen.asignar_candidato(url, candidato.id)
    recuentos.agrupados = sum(
        1 for a in nuevos for c in agrupacion.candidatos if a.url in c.articulos
    )
    return recuentos


# --- Ejecución ---------------------------------------------------------------------


def recoger(
    almacen: Almacen, descargador: Descargador, inicio: datetime, fin: datetime
) -> Recuentos:
    """Pide todos los grupos de países de la ventana y los incorpora juntos."""
    brutos: list[dict[str, Any]] = []
    for consulta in consultas():
        brutos += pedir(descargador, consulta, inicio, fin)
    return incorporar(almacen, brutos)


def ejecutar(almacen: Almacen, descargador: Descargador, ahora: datetime) -> Recuentos:
    """Una ejecución: desde el cursor (con una hora de solape) hasta ahora."""
    cursor = almacen.cursor(FUENTE_ID)
    hasta = datetime.fromisoformat(cursor["hasta"]) if cursor else ahora - PRIMERA_VENTANA
    inicio = hasta - SOLAPE if cursor else hasta
    try:
        recuentos = recoger(almacen, descargador, inicio, ahora)
    except DescargaFallida as error:
        hueco = ahora - hasta
        registro.warning("gdelt sin respuesta, hueco pendiente de %s: %s", hueco, error)
        if hueco > HUECO_TOLERADO:
            raise GdeltNoDisponible(f"sin respuesta desde {cursor}") from error
        return Recuentos()
    # «inicio» es donde empezó la recogida horaria: el histórico llega hasta ahí.
    primera = cursor["inicio"] if cursor else _fecha(inicio)
    almacen.guardar_cursor(FUENTE_ID, {"hasta": _fecha(ahora), "inicio": primera})
    registro.info("gdelt %s", recuentos.resumen())
    return recuentos
