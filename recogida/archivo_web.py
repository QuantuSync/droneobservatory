"""Copias archivadas de las fuentes y comprobación de sus enlaces.

Las noticias desaparecen: un medio cierra (news.yam.md), cambia sus direcciones o borra el
artículo. Para cada enlace de las fuentes de los incidentes publicados se busca una copia en
Internet Archive (la más cercana a la fecha de la fuente, por su API de disponibilidad) y, si no
hay ninguna y el enlace sigue vivo, se pide que se archive (Save Page Now), con pausas y un tope
por ronda. Además se comprueba el propio enlace: un enlace solo se da por caído cuando falla dos
veces seguidas con al menos una hora entre medias (errores 404 y 410, 5xx, dominio que ya no
existe, sin respuesta o redirección a la portada). Un 401, 403 o 429 no dice nada del artículo
(muchos medios cierran el paso a los centros de datos) y no cuenta como caído.

Todo esto va aparte de la recogida: lo hace el servicio eodi-archivo (servidor/archivo.sh), que
lee los ficheros publicados y guarda lo que encuentra en su propio fichero de estado
(EODI_ARCHIVO_DATOS/enlaces.json). La recogida horaria solo lee ese fichero, apunta en la base los
cambios (tabla copias_archivadas, almacen/base.py) y publica el enlace archivado junto a cada
fuente. Si Internet Archive no responde, la ronda se corta y lo pendiente queda para la siguiente:
nunca para la recogida ni la publicación.

    python -m recogida.archivo_web ronda --publicacion DIR --datos DIR [--minutos 12] [--sin-pedir]
    python -m recogida.archivo_web resumen --datos DIR
"""

import argparse
import http.client
import json
import logging
import os
import socket
import ssl
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from collections.abc import Callable, Iterable, Iterator
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from recogida.descarga import AGENTE_EODI, CABECERAS

registro = logging.getLogger(__name__)

FICHERO_ESTADO = "enlaces.json"
FICHEROS_PUBLICADOS = ("incidentes.geojson", "incidentes_sin_ubicacion.json")

# Estados de una comprobación. «vivo»: responde con el artículo; «bloqueado»: el sitio no deja
# pasar (401, 403, 429, 451 o página de comprobación), no dice nada; «fallo»: error que, repetido,
# da el enlace por caído.
VIVO = "vivo"
BLOQUEADO = "bloqueado"
FALLO = "fallo"
# Motivos de fallo.
NO_ENCONTRADO = "no_encontrado"
ERROR_SERVIDOR = "error_servidor"
SIN_DOMINIO = "sin_dominio"
SIN_RESPUESTA = "sin_respuesta"
PORTADA = "portada"

CODIGOS_BLOQUEO = frozenset({401, 403, 405, 406, 429, 451})
# Dos fallos seguidos separados al menos por esto dan el enlace por caído.
SEPARACION_MINIMA = timedelta(hours=1)
# Cada enlace se vuelve a comprobar, y a buscar su copia si no la tiene, una vez por semana.
REVISION_SEMANAL = timedelta(days=7)
# Tras pedir que se archive, la copia se busca de nuevo pasado este tiempo.
ESPERA_TRAS_PEDIR = timedelta(hours=2)
# Una petición de archivo que falla se reintenta más tarde, como mucho estas veces por semana.
PEDIDOS_POR_SEMANA = 3
COMPROBACIONES_GUARDADAS = 4

DISPONIBILIDAD = "https://archive.org/wayback/available"
CDX = "https://web.archive.org/cdx/search/cdx"
GUARDAR = "https://web.archive.org/save/"
COPIA = "https://web.archive.org/web/{marca}/{enlace}"
# Internet Archive pide ritmo humano: una consulta por segundo como mucho y una petición de
# archivo cada 20 s sin cuenta (sus límites públicos para clientes anónimos).
PAUSA_CONSULTA_S = 1.0
PAUSA_PEDIDO_S = 20.0
# Tras un 429 o un corte, Internet Archive descansa este tiempo; tres seguidos cortan la ronda.
DESCANSO_S = 60.0
CORTES_PARA_PARAR = 3
LIMITE_S = 20.0
LIMITE_INDICE_S = 90.0
# Consultas a la vez (cada una tarda de 2 a 6 s; el ritmo de una por segundo se respeta igual).
HILOS_ARCHIVO = 4
LIMITE_PEDIDO_S = 30.0
# Por sitio, una comprobación cada 3 s, como el resto de la recogida (recogida/descarga.py).
PAUSA_SITIO_S = 3.0
HILOS_COMPROBACION = 32
LEER_COMO_MUCHO = 256 * 1024


def ahora_utc() -> datetime:
    return datetime.now(UTC).replace(microsecond=0)


def _instante(momento: datetime) -> str:
    return momento.strftime("%Y-%m-%dT%H:%M:%SZ")


def _leer_instante(texto: str) -> datetime:
    return datetime.fromisoformat(texto.replace("Z", "+00:00"))


def _marca(momento: datetime) -> str:
    return momento.strftime("%Y%m%d%H%M%S")


def _desde_marca(marca: str) -> str:
    return _instante(
        datetime.strptime(marca[:14].ljust(14, "0"), "%Y%m%d%H%M%S").replace(tzinfo=UTC)
    )


# --- Comprobación de un enlace -------------------------------------------------------------


@dataclass(frozen=True)
class Comprobacion:
    estado: str
    motivo: str = ""
    codigo: int | None = None

    def documento(self, momento: datetime) -> dict[str, Any]:
        doc: dict[str, Any] = {"instante": _instante(momento), "estado": self.estado}
        if self.motivo:
            doc["motivo"] = self.motivo
        if self.codigo is not None:
            doc["codigo"] = self.codigo
        return doc


def es_portada(original: str, destino: str) -> bool:
    """Una redirección de un artículo a la portada (o a la portada de un idioma) del sitio."""
    a, b = urllib.parse.urlsplit(original), urllib.parse.urlsplit(destino)
    ruta_a = a.path.strip("/")
    ruta_b = b.path.strip("/")
    if not ruta_a and not a.query:
        return False
    if ruta_b.lower() in {"", "index.html", "index.php", "home", "inicio", "start"}:
        return True
    # Portada de un idioma o de una sección: un único tramo corto («/ro/», «/en», «/news/»).
    if "/" not in ruta_b and len(ruta_b) <= 5 and ruta_b != ruta_a and not b.query:
        return True
    return any(
        p in b.path.lower() for p in ("/404", "not-found", "notfound", "pagina-no-encontrada")
    )


_BLOQUEO_EN_PAGINA = (
    b"cf-chl",
    b"challenge-platform",
    b"captcha",
    b"just a moment",
    b"access denied",
    b"are you a robot",
)


def comprobar_enlace(enlace: str, limite_s: float = LIMITE_S) -> Comprobacion:
    """Pide el enlace como un navegador y dice si sigue vivo."""
    peticion = urllib.request.Request(enlace, headers=CABECERAS)
    try:
        with urllib.request.urlopen(peticion, timeout=limite_s) as respuesta:
            destino = respuesta.geturl()
            cuerpo = respuesta.read(LEER_COMO_MUCHO)
            codigo = respuesta.status
    except urllib.error.HTTPError as error:
        codigo = error.code
        if codigo in (404, 410):
            return Comprobacion(FALLO, NO_ENCONTRADO, codigo)
        if codigo in CODIGOS_BLOQUEO:
            return Comprobacion(BLOQUEADO, "", codigo)
        if codigo >= 500:
            return Comprobacion(FALLO, ERROR_SERVIDOR, codigo)
        return Comprobacion(BLOQUEADO, "", codigo)
    except urllib.error.URLError as error:
        motivo = error.reason
        if isinstance(motivo, socket.gaierror) and motivo.errno in (
            socket.EAI_NONAME, getattr(socket, "EAI_NODATA", -5),
        ):  # fmt: skip
            return Comprobacion(FALLO, SIN_DOMINIO)
        if isinstance(motivo, ssl.SSLError):
            # Certificado caducado o mal puesto: el sitio existe, el artículo puede seguir ahí.
            return Comprobacion(BLOQUEADO, "certificado")
        return Comprobacion(FALLO, SIN_RESPUESTA)
    except (TimeoutError, OSError, http.client.HTTPException, ValueError):
        return Comprobacion(FALLO, SIN_RESPUESTA)
    if es_portada(enlace, destino):
        return Comprobacion(FALLO, PORTADA, codigo)
    if any(m in cuerpo[:20000].lower() for m in _BLOQUEO_EN_PAGINA) and len(cuerpo) < 30000:
        return Comprobacion(BLOQUEADO, "comprobacion", codigo)
    return Comprobacion(VIVO, "", codigo)


def caido(comprobaciones: list[dict[str, Any]]) -> bool:
    """Caído: las dos últimas comprobaciones fallan y entre ellas pasó al menos una hora."""
    if len(comprobaciones) < 2:
        return False
    penultima, ultima = comprobaciones[-2], comprobaciones[-1]
    if penultima["estado"] != FALLO or ultima["estado"] != FALLO:
        return False
    separacion = _leer_instante(ultima["instante"]) - _leer_instante(penultima["instante"])
    return separacion >= SEPARACION_MINIMA


# --- Internet Archive ----------------------------------------------------------------------


class ArchivoNoResponde(RuntimeError):
    """Internet Archive no responde o pide que se baje el ritmo: la ronda se corta."""


Transporte = Callable[[str, float], tuple[int, dict[str, str], bytes]]


def transporte_archivo(url: str, limite_s: float) -> tuple[int, dict[str, str], bytes]:
    peticion = urllib.request.Request(url, headers={"User-Agent": AGENTE_EODI})
    try:
        with urllib.request.urlopen(peticion, timeout=limite_s) as respuesta:
            cabeceras = dict(respuesta.headers)
            # Save Page Now redirige a la copia recién hecha: se apunta la dirección final.
            cabeceras["X-Destino"] = respuesta.geturl()
            return respuesta.status, cabeceras, respuesta.read()
    except urllib.error.HTTPError as error:
        return error.code, dict(error.headers or {}), b""


class InternetArchive:
    """Consultas y peticiones a Internet Archive con su ritmo y sus descansos."""

    def __init__(
        self,
        transporte: Transporte = transporte_archivo,
        dormir: Callable[[float], None] = time.sleep,
        reloj: Callable[[], float] = time.monotonic,
    ) -> None:
        self._transporte = transporte
        self._dormir = dormir
        self._reloj = reloj
        self._cerrojo = threading.Lock()
        self._ultima_consulta = -1e9
        self._ultimo_pedido = -1e9
        self._cortes = 0
        self.recuentos: Counter[str] = Counter()

    def _turno(self, ultima: str, pausa: float) -> None:
        with self._cerrojo:
            falta = pausa - (self._reloj() - getattr(self, ultima))
            if falta > 0:
                self._dormir(falta)
            setattr(self, ultima, self._reloj())

    def _pedir(
        self, url: str, limite_s: float, consulta: bool
    ) -> tuple[int, dict[str, str], bytes]:
        for _ in range(CORTES_PARA_PARAR):
            if consulta:
                self._turno("_ultima_consulta", PAUSA_CONSULTA_S)
            else:
                self._turno("_ultimo_pedido", PAUSA_PEDIDO_S)
            try:
                codigo, cabeceras, cuerpo = self._transporte(url, limite_s)
            except (OSError, TimeoutError, http.client.HTTPException):
                if not consulta:
                    # Save Page Now tarda más de un minuto en responder mientras hace la copia
                    # y la sigue haciendo aunque no se espere: el pedido vale y la copia se busca
                    # más tarde.
                    return 0, {}, b""
                codigo, cabeceras, cuerpo = 0, {}, b""
            if codigo == 429 or codigo == 0 or codigo >= 500:
                self._cortes += 1
                self.recuentos["cortes"] += 1
                if self._cortes >= CORTES_PARA_PARAR:
                    raise ArchivoNoResponde(f"Internet Archive: {codigo or 'sin respuesta'}")
                self._dormir(DESCANSO_S)
                continue
            self._cortes = 0
            return codigo, cabeceras, cuerpo
        raise ArchivoNoResponde("Internet Archive: sin respuesta")

    def copia_cercana(
        self, enlace: str, fecha: datetime, indice: bool = False
    ) -> dict[str, str] | None:
        """La copia con código 200 más cercana a la fecha, o None. Con `indice`, si la API de
        disponibilidad no da ninguna se pregunta además al índice CDX (lento: solo para los
        enlaces que fallan, donde la copia importa más)."""
        self.recuentos["busquedas"] += 1
        consulta = urllib.parse.urlencode({"url": enlace, "timestamp": _marca(fecha)})
        codigo, _, cuerpo = self._pedir(f"{DISPONIBILIDAD}?{consulta}", LIMITE_S, True)
        if codigo == 200:
            try:
                cercana = json.loads(cuerpo).get("archived_snapshots", {}).get("closest") or {}
            except (json.JSONDecodeError, AttributeError):
                cercana = {}
            if cercana.get("available") and str(cercana.get("status")) == "200":
                return self._copia(enlace, str(cercana["timestamp"]))
        if not indice:
            return None
        # La API de disponibilidad a veces no ve copias que sí están: se pregunta al índice.
        consulta = urllib.parse.urlencode({
            "url": enlace, "output": "json", "fl": "timestamp,statuscode",
            "filter": "statuscode:200", "closest": _marca(fecha), "sort": "closest", "limit": "1",
        })  # fmt: skip
        # El índice CDX se cae a menudo («Temporarily Offline») y tarda: su fallo deja esta búsqueda
        # sin copia (se repite la semana siguiente) pero no corta la ronda.
        self._turno("_ultima_consulta", PAUSA_CONSULTA_S)
        try:
            codigo, _, cuerpo = self._transporte(f"{CDX}?{consulta}", LIMITE_INDICE_S)
        except (OSError, TimeoutError, http.client.HTTPException):
            self.recuentos["indice_sin_respuesta"] += 1
            return None
        if codigo != 200:
            self.recuentos["indice_sin_respuesta"] += 1
            return None
        try:
            filas = json.loads(cuerpo) if cuerpo.strip() else []
        except json.JSONDecodeError:
            return None
        if len(filas) < 2 or not filas[1]:
            return None
        return self._copia(enlace, str(filas[1][0]))

    def _copia(self, enlace: str, marca: str) -> dict[str, str]:
        self.recuentos["copias"] += 1
        return {"enlace": COPIA.format(marca=marca, enlace=enlace), "fecha": _desde_marca(marca)}

    def pedir_archivo(self, enlace: str) -> dict[str, str] | None:
        """Pide a Save Page Now que archive el enlace; da la copia si responde con ella."""
        self.recuentos["pedidos"] += 1
        codigo, cabeceras, _ = self._pedir(GUARDAR + enlace, LIMITE_PEDIDO_S, False)
        if codigo == 0:
            self.recuentos["pedidos_en_curso"] += 1
            return None
        if codigo != 200:
            self.recuentos["pedidos_fallidos"] += 1
            return None
        minusculas = {k.lower(): v for k, v in cabeceras.items()}
        for ubicacion in (minusculas.get("content-location", ""), minusculas.get("x-destino", "")):
            ruta = urllib.parse.urlsplit(ubicacion).path if "://" in ubicacion else ubicacion
            partes = ruta.split("/")
            if len(partes) > 2 and partes[1] == "web" and partes[2][:14].isdigit():
                return self._copia(enlace, partes[2][:14])
        return None


# --- Estado -------------------------------------------------------------------------------


def leer_estado(datos: Path) -> dict[str, dict[str, Any]]:
    ruta = datos / FICHERO_ESTADO
    if not ruta.exists():
        return {}
    contenido: dict[str, dict[str, Any]] = json.loads(ruta.read_text(encoding="utf-8"))
    return contenido


def guardar_estado(datos: Path, estado: dict[str, dict[str, Any]]) -> None:
    datos.mkdir(parents=True, exist_ok=True)
    temporal = datos / (FICHERO_ESTADO + ".tmp")
    temporal.write_text(
        json.dumps(estado, ensure_ascii=False, sort_keys=True, indent=0),
        encoding="utf-8",
        newline="\n",
    )
    os.replace(temporal, datos / FICHERO_ESTADO)


def enlaces_publicados(publicacion: Path) -> dict[str, str]:
    """Enlace → fecha más antigua de sus fuentes, en los incidentes publicados."""
    enlaces: dict[str, str] = {}

    def fuentes(nodo: Any) -> Iterator[dict[str, Any]]:
        if isinstance(nodo, dict):
            for fuente in nodo.get("fuentes", []) if isinstance(nodo.get("fuentes"), list) else []:
                if isinstance(fuente, dict):
                    yield fuente
            for clave, valor in nodo.items():
                if clave != "fuentes":
                    yield from fuentes(valor)
        elif isinstance(nodo, list):
            for valor in nodo:
                yield from fuentes(valor)

    for nombre in FICHEROS_PUBLICADOS:
        ruta = publicacion / nombre
        if not ruta.exists():
            continue
        for fuente in fuentes(json.loads(ruta.read_text(encoding="utf-8"))):
            enlace = fuente.get("enlace")
            fecha = (fuente.get("fecha") or {}).get("valor")
            if not isinstance(enlace, str) or not enlace.startswith(("http://", "https://")):
                continue
            if not isinstance(fecha, str):
                fecha = "2025-01-01T00:00:00Z"
            if enlace not in enlaces or fecha < enlaces[enlace]:
                enlaces[enlace] = fecha
    return enlaces


def _fecha_fuente(texto: str) -> datetime:
    try:
        return _leer_instante(texto if "T" in texto else texto + "T12:00:00Z")
    except ValueError:
        return datetime(2025, 1, 1, tzinfo=UTC)


def resumen_enlace(entrada: dict[str, Any]) -> dict[str, Any]:
    """Lo que se publica de un enlace: la copia (si hay) y si el original está caído."""
    resumen: dict[str, Any] = {"caido": caido(entrada.get("comprobaciones", []))}
    if entrada.get("copia"):
        resumen["copia"] = entrada["copia"]
    return resumen


# --- Paso de la recogida horaria -----------------------------------------------------------

# En el servidor, la carpeta del servicio eodi-archivo (servidor/configuracion.sh). Sin la variable
# la recogida no apunta nada (pruebas y ensayos en local).
VARIABLE_DATOS = "EODI_ARCHIVO_DATOS"


def resultados_para_la_base(
    estado: dict[str, dict[str, Any]], vigentes: dict[str, dict[str, Any]]
) -> dict[str, dict[str, Any]]:
    """Lo que se apunta: enlaces con copia o caídos y los que ya tenían fila (por si cambian)."""
    resultados = {}
    for enlace, entrada in estado.items():
        documento = resumen_enlace(entrada)
        if documento.get("copia") or documento["caido"] or enlace in vigentes:
            resultados[enlace] = documento
    return resultados


def paso_horario(almacen: Any, ahora: datetime, datos: Path | None = None) -> int:
    """Lleva a la base lo que ha encontrado eodi-archivo desde la recogida anterior. Solo lee su
    fichero de estado: no pide nada a Internet Archive ni a los medios."""
    if datos is None:
        variable = os.environ.get(VARIABLE_DATOS)
        if not variable:
            return 0
        datos = Path(variable)
    try:
        estado = leer_estado(datos)
    except (OSError, json.JSONDecodeError) as error:
        registro.warning(
            "copias archivadas sin leer (%s): quedan las de la recogida anterior", error
        )
        return 0
    nuevas: int = almacen.guardar_copias_archivadas(
        resultados_para_la_base(estado, almacen.copias_archivadas()),
        _instante(ahora.replace(microsecond=0)),
    )
    if nuevas:
        registro.info("copias archivadas: %d enlaces con resultado nuevo", nuevas)
    return nuevas


def con_copias(
    fuentes: list[dict[str, Any]], copias: dict[str, dict[str, Any]]
) -> list[dict[str, Any]]:
    """Las fuentes con su copia archivada y, si el original está caído, la marca."""
    salida = []
    for fuente in fuentes:
        vigente = copias.get(fuente.get("enlace", ""))
        if vigente is None:
            salida.append(fuente)
            continue
        nueva = {k: v for k, v in fuente.items() if k not in ("copia_archivada", "enlace_caido")}
        if vigente.get("copia"):
            nueva["copia_archivada"] = vigente["copia"]
        if vigente.get("caido"):
            nueva["enlace_caido"] = True
        salida.append(nueva)
    return salida


def con_copias_archivadas(
    incidentes: list[dict[str, Any]], copias: dict[str, dict[str, Any]]
) -> list[dict[str, Any]]:
    """Cada incidente con la copia archivada de sus fuentes y la marca de enlace caído (la web y
    la exportación semanal)."""
    if not copias:
        return incidentes
    return [{**i, "fuentes": con_copias(i["fuentes"], copias)} for i in incidentes]


# --- Ronda -------------------------------------------------------------------------------


@dataclass
class Tareas:
    comprobar: list[str]
    buscar: list[str]
    pedir: list[str]


def tareas(estado: dict[str, dict[str, Any]], momento: datetime) -> Tareas:
    """Qué toca en esta ronda, lo nuevo primero."""
    comprobar: list[tuple[int, str, str]] = []
    buscar: list[tuple[int, str, str]] = []
    pedir: list[tuple[str, str]] = []
    for enlace, entrada in estado.items():
        comprobaciones = entrada.get("comprobaciones", [])
        ultima = comprobaciones[-1] if comprobaciones else None
        if ultima is None:
            comprobar.append((0, "", enlace))
        else:
            hace = momento - _leer_instante(ultima["instante"])
            repetir = (
                ultima["estado"] == FALLO
                and not caido(comprobaciones)
                and hace >= SEPARACION_MINIMA
            )
            if repetir:
                comprobar.append((1, ultima["instante"], enlace))
            elif hace >= REVISION_SEMANAL:
                comprobar.append((2, ultima["instante"], enlace))
        if entrada.get("copia"):
            continue
        busqueda = entrada.get("buscada")
        pedido = entrada.get("pedido")
        if busqueda is None:
            buscar.append((0, "", enlace))
        elif caido(comprobaciones) and not entrada.get("indice"):
            # Caído y buscado solo con la API de disponibilidad: se pregunta también al índice.
            buscar.append((1, busqueda, enlace))
        elif pedido and _leer_instante(pedido) > _leer_instante(busqueda):
            if momento - _leer_instante(pedido) >= ESPERA_TRAS_PEDIR:
                buscar.append((1, busqueda, enlace))
        elif momento - _leer_instante(busqueda) >= REVISION_SEMANAL:
            buscar.append((2, busqueda, enlace))
        elif ultima is not None and ultima["estado"] == VIVO and _puede_pedir(entrada, momento):
            pedir.append((entrada.get("fecha", ""), enlace))
    comprobar.sort()
    buscar.sort()
    # Se piden antes las fuentes más recientes: las viejas tienen más probabilidad de estar ya.
    pedir.sort(reverse=True)
    return Tareas([e for *_, e in comprobar], [e for *_, e in buscar], [e for _, e in pedir])


def _puede_pedir(entrada: dict[str, Any], momento: datetime) -> bool:
    pedidos = [
        p for p in entrada.get("pedidos", []) if momento - _leer_instante(p) < REVISION_SEMANAL
    ]
    if len(pedidos) >= PEDIDOS_POR_SEMANA:
        return False
    pedido = entrada.get("pedido")
    return pedido is None or momento - _leer_instante(pedido) >= ESPERA_TRAS_PEDIR


class _RitmoPorSitio:
    def __init__(self, pausa_s: float) -> None:
        self._pausa = pausa_s
        self._cerrojo = threading.Lock()
        self._siguiente: dict[str, float] = {}

    def esperar(self, sitio: str) -> None:
        with self._cerrojo:
            ahora = time.monotonic()
            turno = max(ahora, self._siguiente.get(sitio, 0.0))
            self._siguiente[sitio] = turno + self._pausa
        if turno > ahora:
            time.sleep(turno - ahora)


def _en_orden_de_sitios(enlaces: Iterable[str]) -> list[str]:
    """Reparte los enlaces alternando sitios, para que los hilos no esperen todos al mismo."""
    por_sitio: dict[str, list[str]] = {}
    for enlace in enlaces:
        por_sitio.setdefault(urllib.parse.urlsplit(enlace).hostname or "", []).append(enlace)
    colas = list(por_sitio.values())
    orden: list[str] = []
    while colas:
        orden.extend(cola.pop(0) for cola in colas)
        colas = [c for c in colas if c]
    return orden


def ronda(
    publicacion: Path,
    datos: Path,
    minutos: float,
    pedir: bool = True,
    archivo: InternetArchive | None = None,
    comprobador: Callable[[str], Comprobacion] = comprobar_enlace,
    reloj: Callable[[], datetime] = ahora_utc,
    tope_pedidos: int | None = None,
) -> Counter[str]:
    """Una ronda acotada en tiempo: comprueba, busca copias y pide archivos. Guarda a menudo."""
    fin = time.monotonic() + minutos * 60
    archivo = archivo or InternetArchive()
    estado = leer_estado(datos)
    publicados = enlaces_publicados(publicacion)
    recuento: Counter[str] = Counter()
    for enlace, fecha in publicados.items():
        entrada = estado.setdefault(enlace, {})
        if entrada.get("fecha") != fecha:
            entrada["fecha"] = fecha
            recuento["nuevos" if len(entrada) == 1 else "fecha_cambiada"] += 1
    # Un enlace que ya no se publica se deja de revisar, pero no se olvida.
    for enlace, entrada in estado.items():
        entrada["publicado"] = enlace in publicados
    activos = {e: v for e, v in estado.items() if v["publicado"]}
    momento = reloj()
    pendiente = tareas(activos, momento)
    guardado = [time.monotonic()]

    def guardar_a_menudo(forzar: bool = False) -> None:
        if forzar or time.monotonic() - guardado[0] > 60:
            guardar_estado(datos, estado)
            guardado[0] = time.monotonic()

    # 1. Comprobaciones, en paralelo entre sitios y con pausa en cada sitio.
    ritmo = _RitmoPorSitio(PAUSA_SITIO_S)
    cerrojo = threading.Lock()

    def una(enlace: str) -> None:
        if time.monotonic() > fin:
            return
        ritmo.esperar(urllib.parse.urlsplit(enlace).hostname or "")
        if time.monotonic() > fin:
            return
        resultado = comprobador(enlace)
        with cerrojo:
            lista = estado[enlace].setdefault("comprobaciones", [])
            lista.append(resultado.documento(reloj()))
            del lista[:-COMPROBACIONES_GUARDADAS]
            recuento[f"comprobado_{resultado.estado}"] += 1
            guardar_a_menudo()

    # 2. Copias en Internet Archive y 3. peticiones de archivo, a la vez que las comprobaciones
    # (son otro servidor) y hasta el tope de tiempo.
    def archivar() -> None:
        try:
            parar = threading.Event()

            def buscar(enlace: str) -> None:
                if time.monotonic() > fin or parar.is_set():
                    return
                with cerrojo:
                    entrada = estado[enlace]
                    fecha = _fecha_fuente(entrada["fecha"])
                    comprobaciones = entrada.get("comprobaciones", [])
                    falla = bool(comprobaciones) and comprobaciones[-1]["estado"] == FALLO
                try:
                    copia = archivo.copia_cercana(enlace, fecha, indice=falla)
                except ArchivoNoResponde:
                    parar.set()
                    raise
                with cerrojo:
                    entrada["buscada"] = _instante(reloj())
                    entrada["indice"] = falla
                    if copia:
                        entrada["copia"] = copia
                        recuento["copias_encontradas"] += 1
                    else:
                        recuento["sin_copia"] += 1
                    guardar_a_menudo()

            with ThreadPoolExecutor(HILOS_ARCHIVO) as consultas:
                for futuro in [consultas.submit(buscar, e) for e in pendiente.buscar]:
                    futuro.result()
            if not pedir:
                return
            # Los que se acaban de buscar sin copia y siguen vivos también se piden ya.
            with cerrojo:
                pedibles = tareas(
                    {e: v for e, v in estado.items() if v.get("publicado")}, reloj()
                ).pedir
            for hechos, enlace in enumerate(pedibles):
                if time.monotonic() > fin or (tope_pedidos is not None and hechos >= tope_pedidos):
                    break
                with cerrojo:
                    entrada = estado[enlace]
                    cuando = _instante(reloj())
                    entrada["pedido"] = cuando
                    entrada["pedidos"] = [
                        p for p in entrada.get("pedidos", [])
                        if reloj() - _leer_instante(p) < REVISION_SEMANAL
                    ] + [cuando]  # fmt: skip
                copia = archivo.pedir_archivo(enlace)
                with cerrojo:
                    if copia:
                        entrada["copia"] = copia
                        recuento["archivados"] += 1
                    else:
                        recuento["pedidos_sin_copia"] += 1
                    guardar_a_menudo()
        except ArchivoNoResponde as error:
            registro.warning("%s: lo pendiente queda para la ronda siguiente", error)
            recuento["archivo_no_responde"] += 1

    hilo_archivo = threading.Thread(target=archivar, name="archivo")
    hilo_archivo.start()
    with ThreadPoolExecutor(HILOS_COMPROBACION) as hilos:
        list(hilos.map(una, _en_orden_de_sitios(pendiente.comprobar)))
    hilo_archivo.join()
    with cerrojo:
        guardar_a_menudo(True)
    recuento.update({f"ia_{k}": v for k, v in archivo.recuentos.items()})
    return recuento


def resumen(datos: Path) -> dict[str, int]:
    estado = leer_estado(datos)
    publicados = [v for v in estado.values() if v.get("publicado", True)]
    caidos = [v for v in publicados if caido(v.get("comprobaciones", []))]
    return {
        "enlaces": len(publicados),
        "comprobados": sum(1 for v in publicados if v.get("comprobaciones")),
        "caidos": len(caidos),
        "caidos_con_copia": sum(1 for v in caidos if v.get("copia")),
        "caidos_sin_copia": sum(1 for v in caidos if not v.get("copia")),
        "con_copia": sum(1 for v in publicados if v.get("copia")),
        "sin_copia": sum(1 for v in publicados if not v.get("copia")),
        "sin_buscar": sum(1 for v in publicados if not v.get("buscada") and not v.get("copia")),
        "pendientes_de_repetir": sum(
            1 for v in publicados
            if v.get("comprobaciones") and v["comprobaciones"][-1]["estado"] == FALLO
            and not caido(v["comprobaciones"])
        ),
    }  # fmt: skip


def main(argumentos: list[str] | None = None) -> int:
    analizador = argparse.ArgumentParser(prog="python -m recogida.archivo_web")
    ordenes = analizador.add_subparsers(dest="orden", required=True)
    r = ordenes.add_parser("ronda", help="una ronda acotada en tiempo")
    r.add_argument("--publicacion", type=Path, required=True)
    r.add_argument("--datos", type=Path, required=True)
    r.add_argument("--minutos", type=float, default=12.0)
    r.add_argument("--sin-pedir", action="store_true", help="no pide archivos nuevos")
    r.add_argument("--tope-pedidos", type=int, default=None)
    s = ordenes.add_parser("resumen", help="recuento del estado")
    s.add_argument("--datos", type=Path, required=True)
    args = analizador.parse_args(argumentos)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    if args.orden == "resumen":
        print(json.dumps(resumen(args.datos), ensure_ascii=False, indent=1))
        return 0
    recuento = ronda(
        args.publicacion,
        args.datos,
        args.minutos,
        not args.sin_pedir,
        tope_pedidos=args.tope_pedidos,
    )
    print(json.dumps(dict(sorted(recuento.items())), ensure_ascii=False))
    print(json.dumps(resumen(args.datos), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
