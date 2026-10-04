"""Captura del seguimiento en directo de amenazas aéreas sobre Ucrania: solo escuchar y guardar.

Dos fuentes, cada una en su archivo, tal como llegan y sin transformar:

- **NEPTUN** (https://neptun.in.ua/developers): agregador ucraniano de terceros que da solo el
  estado en vivo, sin historia. Se escucha su flujo WebSocket (`wss://neptun.in.ua/api/v1/stream`)
  y se guarda cada mensaje recibido, entero, con la hora UTC de recepción: snapshot, upsert,
  remove, heartbeat, alerts y cualquier otro tipo. Si el flujo se corta, reconecta con espera
  creciente y anota el hueco (desde la última recepción hasta la primera tras reconectar); si el
  corte dura más de 30 s, consulta mientras tanto el REST (`threats` y `alerts`) como respaldo.
  Cada dos minutos guarda lo que devuelve `/api/v1/messages` (mensajes de texto de canales de
  Telegram que el flujo no trae), solo si ha cambiado. Ninguna petición REST a NEPTUN sale antes de
  10 s de la anterior (la fuente pide no bajar de 5 s).
- **Fuerza Aérea de Ucrania** (vista pública web de t.me/kpszsu): cada minuto, la página más
  reciente del canal; se guarda el bloque HTML de cada publicación nueva o cambiada (ediciones),
  con su identificador y su hora de publicación. Si entre dos lecturas se han publicado más de
  las que caben en una página, se leen las anteriores hasta enlazar; cada 10 minutos se relee
  además la página anterior para ver las ediciones de lo que ya no está en la primera.

Nada se procesa, se clasifica ni se publica: el archivo es privado y lo usará más adelante la
reconstrucción de rutas. Ficheros por hora UTC de recepción, en JSON por líneas
(`<datos>/<fuente>/<AAAA>/<MM>/<fuente>-<AAAA-MM-DD>T<HH>.jsonl`); los comprime, indexa y copia
`recogida/seguimiento_archivo.py`, fuera de este proceso. Nada se borra ni se reescribe.

Líneas del archivo de NEPTUN (`recibido` es la hora UTC de recepción, con microsegundos):

    {"recibido", "via": "ws", "crudo": <texto del mensaje, tal cual>}
    {"recibido", "via": "rest" | "mensajes", "url", "http": <código>, "crudo": <cuerpo, tal cual>}
    {"recibido", "evento": "conectado" | "desconectado" | "arranque" | "parada", ...}
    {"recibido", "evento": "hueco", "desde", "hasta", "segundos", "motivo", "respaldo_rest"}
    {"recibido", "evento": "hueco_mensajes", "desde", "hasta"}

Líneas del archivo de la Fuerza Aérea:

    {"recibido", "via": "telegram_web", "url", "id", "fecha", "version", "crudo": <bloque HTML>}
    {"recibido", "evento": "hueco", "desde", "hasta", "segundos", "motivo"}
    {"recibido", "evento": "ids_sin_enlazar", "desde_id", "hasta_id"}

El registro (`/home/eodi/.eodi/seguimiento.json`) lleva la última recepción, el último heartbeat,
la vía en uso y el último hueco de más de 10 minutos: de él sale `seguimiento` en estado.json.

El servicio lo lanza la unidad eodi-seguimiento (servidor/seguimiento.sh), siempre en marcha.
Sale solo cuando cambia su propio código en el clon (no con cada publicación de datos) y systemd
lo vuelve a lanzar.

Uso: python -m recogida.seguimiento servir [--datos <dir>] [--registro <json>]
"""

import argparse
import asyncio
import contextlib
import hashlib
import json
import logging
import os
import re
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import IO, Any, Protocol

from recogida.telegram import leer_pagina

registro_log = logging.getLogger("seguimiento")

RAIZ = Path(__file__).resolve().parent.parent
# Identificación propia: nombra el observatorio y su web, para que la fuente pueda contactar.
AGENTE = "EODI-bot/1.0 (European Observatory of Drone Incidents; +https://droneobservatory.eu)"

NEPTUN = "neptun"
NEPTUN_FLUJO = "wss://neptun.in.ua/api/v1/stream"
NEPTUN_REST = "https://neptun.in.ua/api/v1/"
RESPALDO = ("threats", "alerts")
MENSAJES = "messages"
KPSZSU = "kpszsu"
KPSZSU_URL = "https://t.me/s/kpszsu"

# NEPTUN pide no consultar el REST más de una vez cada 5 s: con margen, una cada 10 s entre todas
# las consultas REST (respaldo y mensajes).
INTERVALO_REST_S = 10.0
INTERVALO_MENSAJES_S = 120.0
# El flujo manda un heartbeat cada 15 s: un minuto sin nada es una conexión muerta.
SILENCIO_S = 60.0
# Respaldo REST solo si el flujo lleva caído más de esto (una reconexión normal tarda segundos).
RESPALDO_TRAS_S = 30.0
ESPERA_INICIAL_S = 2.0
ESPERA_MAXIMA_S = 300.0
# Una conexión que ha durado esto vuelve a empezar la espera creciente desde el principio.
CONEXION_ESTABLE_S = 60.0
# Un mensaje del flujo cabe de sobra: un snapshot de una noche grande son unos cientos de KB.
TAMANO_MAXIMO = 16 * 1024 * 1024
TOPE_HTTP_S = 30.0

# Telegram: la página más reciente cada minuto, una petición cada 3 s como mucho al enlazar.
INTERVALO_KPSZSU_S = 60.0
PAUSA_PAGINAS_S = 3.0
REPASO_KPSZSU_S = 600.0
PAGINAS_ENLACE_MAXIMAS = 10
VISTOS_MAXIMOS = 600

REGISTRO_CADA_S = 30.0
RESUMEN_CADA_S = 600.0
REVISION_CODIGO_S = 300.0
HUECO_LARGO = timedelta(minutes=10)
# El código propio: si cambia en el clon, el servicio sale y systemd lo relanza con el nuevo.
CODIGO = (
    "recogida/seguimiento.py",
    "recogida/telegram.py",
    "servidor/seguimiento.sh",
    "requirements.txt",
)

Ahora = Callable[[], datetime]
Reloj = Callable[[], float]
Dormir = Callable[[float], Awaitable[None]]


def instante(momento: datetime) -> str:
    """Hora UTC con microsegundos y Z."""
    return momento.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def leer_instante(texto: object) -> datetime | None:
    if not isinstance(texto, str) or not texto:
        return None
    try:
        return datetime.fromisoformat(texto.replace("Z", "+00:00")).astimezone(UTC)
    except ValueError:
        return None


def directorio_datos() -> Path:
    return Path(os.environ.get("EODI_SEGUIMIENTO_DATOS", RAIZ / "data" / "seguimiento"))


def ruta_hora(datos: Path, fuente: str, momento: datetime) -> Path:
    m = momento.astimezone(UTC)
    return datos / fuente / f"{m:%Y}" / f"{m:%m}" / f"{fuente}-{m:%Y-%m-%dT%H}.jsonl"


class Archivo:
    """Fichero por hora UTC de recepción de una fuente, en JSON por líneas, solo añadiendo.

    Cada línea se escribe y se vuelca al sistema al momento; al cambiar de hora se cierra el
    fichero anterior y se abre el nuevo. Nunca se trunca ni se reescribe nada."""

    def __init__(self, datos: Path, fuente: str) -> None:
        self.datos = datos
        self.fuente = fuente
        self._ruta: Path | None = None
        self._fichero: IO[str] | None = None
        self.lineas = 0

    def escribir(self, registro: dict[str, Any], momento: datetime) -> Path:
        ruta = ruta_hora(self.datos, self.fuente, momento)
        if ruta != self._ruta:
            self.cerrar()
            ruta.parent.mkdir(parents=True, exist_ok=True)
            self._fichero = ruta.open("a", encoding="utf-8", newline="\n")
            self._ruta = ruta
        assert self._fichero is not None
        linea = json.dumps(
            {"recibido": instante(momento), **registro}, ensure_ascii=False, separators=(",", ":")
        )
        self._fichero.write(linea + "\n")
        self._fichero.flush()
        self.lineas += 1
        return ruta

    def cerrar(self) -> None:
        if self._fichero is not None:
            self._fichero.flush()
            with contextlib.suppress(OSError):
                os.fsync(self._fichero.fileno())
            self._fichero.close()
        self._fichero = None
        self._ruta = None


class Ritmo:
    """Una petición cada `intervalo` segundos como mucho entre todos los que la comparten."""

    def __init__(self, intervalo: float, reloj: Reloj, dormir: Dormir) -> None:
        self.intervalo = intervalo
        self._reloj = reloj
        self._dormir = dormir
        self._ultima: float | None = None
        self._cerrojo = asyncio.Lock()

    async def turno(self) -> None:
        async with self._cerrojo:
            if self._ultima is not None:
                espera = self._ultima + self.intervalo - self._reloj()
                if espera > 0:
                    await self._dormir(espera)
            self._ultima = self._reloj()


@dataclass(frozen=True)
class Respuesta:
    estado: int
    cuerpo: str


def pedir_http(url: str) -> Respuesta:
    """GET con la identificación del observatorio. Un código HTTP de error no lanza."""
    peticion = urllib.request.Request(
        url, headers={"User-Agent": AGENTE, "Accept-Encoding": "identity"}
    )
    try:
        with urllib.request.urlopen(peticion, timeout=TOPE_HTTP_S) as respuesta:
            cuerpo: bytes = respuesta.read()
            return Respuesta(respuesta.status, cuerpo.decode("utf-8", errors="replace"))
    except urllib.error.HTTPError as error:
        return Respuesta(error.code, error.read().decode("utf-8", errors="replace"))


class Conexion(Protocol):
    async def recv(self) -> str | bytes: ...


Conectar = Callable[[], contextlib.AbstractAsyncContextManager[Conexion]]


def conectar_neptun() -> contextlib.AbstractAsyncContextManager[Conexion]:
    from websockets.asyncio.client import connect

    conexion: contextlib.AbstractAsyncContextManager[Conexion] = connect(
        NEPTUN_FLUJO,
        user_agent_header=AGENTE,
        max_size=TAMANO_MAXIMO,
        open_timeout=20,
        ping_interval=20,
        ping_timeout=20,
        close_timeout=5,
    )
    return conexion


@dataclass
class Bloque:
    """Una publicación de la vista web del canal: su bloque HTML entero, tal cual."""

    id: int
    fecha: str
    huella: str
    crudo: str


_INICIO_BLOQUE = '<div class="tgme_widget_message_wrap'
_POST = re.compile(r'data-post="([A-Za-z0-9_]+)/(\d+)"')


def bloques_pagina(html: str, canal: str = KPSZSU) -> list[Bloque]:
    """Cada publicación de la página con su bloque HTML sin tocar.

    La huella, para saber si una publicación ha cambiado, sale del texto y de la marca de
    edición, no del bloque: el bloque cambia en cada lectura (contador de vistas, enlaces
    firmados de las imágenes)."""
    textos = {p.id: p for p in leer_pagina(html).publicaciones}
    trozos = html.split(_INICIO_BLOQUE)[1:]
    bloques: list[Bloque] = []
    for trozo in trozos:
        crudo = _INICIO_BLOQUE + trozo
        # El último bloque arrastra el final de la página: se corta donde acaba la sección.
        fin = crudo.find('<div class="tgme_widget_message_centered')
        if fin < 0:
            fin = crudo.find("</section>")
        if fin > 0:
            crudo = crudo[:fin]
        encontrado = _POST.search(crudo)
        if encontrado is None or encontrado.group(1).lower() != canal.lower():
            continue
        numero = int(encontrado.group(2))
        publicacion = textos.get(numero)
        texto = publicacion.texto if publicacion else ""
        fecha = instante(publicacion.fecha) if publicacion else ""
        editado = _editado(crudo)
        huella = hashlib.sha256(f"{texto}\x00{editado}".encode()).hexdigest()[:24]
        bloques.append(Bloque(numero, fecha, huella, crudo))
    return bloques


def _editado(crudo: str) -> bool:
    """La vista web pone «edited» junto a la hora de una publicación editada."""
    inicio = crudo.find("tgme_widget_message_meta")
    if inicio < 0:
        return False
    fin = crudo.find("</time>", inicio)
    return "edited" in crudo[inicio : fin if fin > 0 else inicio + 1000]


@dataclass
class Hueco:
    desde: datetime
    motivo: str
    respaldo: int = 0


@dataclass
class Contadores:
    por_tipo: dict[str, int] = field(default_factory=dict)
    rest: int = 0
    mensajes: int = 0
    kpszsu: int = 0
    huecos: int = 0


def tipo_mensaje(crudo: str | bytes) -> str:
    if isinstance(crudo, bytes):
        return "binario"
    try:
        datos = json.loads(crudo)
    except ValueError:
        return "no_json"
    tipo = datos.get("type") if isinstance(datos, dict) else None
    return tipo if isinstance(tipo, str) else "sin_tipo"


class Servicio:
    def __init__(
        self,
        datos: Path,
        registro: Path | None,
        conectar: Conectar = conectar_neptun,
        pedir: Callable[[str], Respuesta] = pedir_http,
        ahora: Ahora = lambda: datetime.now(UTC),
        reloj: Reloj = time.monotonic,
        dormir: Dormir = asyncio.sleep,
        clon: Path | None = None,
    ) -> None:
        self.datos = datos
        self.registro = registro
        self._conectar = conectar
        self._pedir = pedir
        self.ahora = ahora
        self.reloj = reloj
        self._dormir = dormir
        self.clon = clon
        self.neptun = Archivo(datos, NEPTUN)
        self.kpszsu = Archivo(datos, KPSZSU)
        self.ritmo_rest = Ritmo(INTERVALO_REST_S, reloj, dormir)
        self.ritmo_telegram = Ritmo(PAUSA_PAGINAS_S, reloj, dormir)
        self.parar = asyncio.Event()
        self.contadores = Contadores()
        self.inicio = ahora()
        self.conectado = False
        self.via: str | None = None
        self.ultima_recepcion: datetime | None = None
        self.ultimo_latido: datetime | None = None
        self.ultima_ws: datetime | None = None
        self.ultimo_hueco_largo: dict[str, Any] | None = None
        self.hueco: Hueco | None = None
        self.caido_desde_reloj: float | None = None
        self.ultimo_mensajes: str | None = None
        self.mensajes_hasta: str | None = None
        self.kpszsu_ultima: datetime | None = None
        self.kpszsu_hueco: Hueco | None = None
        self.kpszsu_vistos: dict[int, tuple[str, int]] = {}
        self.kpszsu_ultimo_id: int | None = None
        self.codigo = huella_codigo(clon) if clon else ""
        self._retomar()

    # --- Estado guardado ----------------------------------------------------------------
    def _ruta_vistos(self) -> Path:
        return self.datos / KPSZSU / "vistos.json"

    def _retomar(self) -> None:
        """Lo que dejó la ejecución anterior: el hueco desde su última recepción y las
        publicaciones del canal ya guardadas (para no repetirlas)."""
        anterior = _leer_json(self.registro) if self.registro else None
        if anterior:
            self.ultimo_hueco_largo = anterior.get("ultimo_hueco_largo")
            ultima = leer_instante(anterior.get("ultima_ws") or anterior.get("ultima_recepcion"))
            if ultima is not None:
                self.hueco = Hueco(ultima, "servicio parado o reiniciado")
            kultima = leer_instante(anterior.get("kpszsu_ultima_lectura"))
            if kultima is not None:
                self.kpszsu_hueco = Hueco(kultima, "servicio parado o reiniciado")
        vistos = _leer_json(self._ruta_vistos())
        if vistos:
            for clave, (huella, version) in vistos.get("vistos", {}).items():
                self.kpszsu_vistos[int(clave)] = (str(huella), int(version))
            ultimo = vistos.get("ultimo_id")
            self.kpszsu_ultimo_id = int(ultimo) if isinstance(ultimo, int) else None

    def documento_registro(self) -> dict[str, Any]:
        return {
            "actualizado": instante(self.ahora()),
            "inicio": instante(self.inicio),
            "conectado": self.conectado,
            "via": self.via,
            "ultima_recepcion": _o_nulo(self.ultima_recepcion),
            "ultima_ws": _o_nulo(self.ultima_ws),
            "ultimo_latido": _o_nulo(self.ultimo_latido),
            "ultimo_hueco_largo": self.ultimo_hueco_largo,
            "kpszsu_ultima_lectura": _o_nulo(self.kpszsu_ultima),
            "kpszsu_ultimo_id": self.kpszsu_ultimo_id,
            "codigo": self.codigo,
            "contadores": {
                "por_tipo": dict(sorted(self.contadores.por_tipo.items())),
                "rest": self.contadores.rest,
                "mensajes": self.contadores.mensajes,
                "kpszsu": self.contadores.kpszsu,
                "huecos": self.contadores.huecos,
            },
        }

    def guardar_registro(self) -> None:
        if self.registro is not None:
            _escribir_json(self.registro, self.documento_registro())
        recientes = sorted(self.kpszsu_vistos)[-VISTOS_MAXIMOS:]
        self.kpszsu_vistos = {i: self.kpszsu_vistos[i] for i in recientes}
        _escribir_json(
            self._ruta_vistos(),
            {
                "ultimo_id": self.kpszsu_ultimo_id,
                "vistos": {str(i): list(v) for i, v in self.kpszsu_vistos.items()},
            },
        )

    # --- NEPTUN: flujo -------------------------------------------------------------------
    def recibido_flujo(self, crudo: str | bytes) -> None:
        momento = self.ahora()
        self._cerrar_hueco(momento)
        tipo = tipo_mensaje(crudo)
        if isinstance(crudo, bytes):
            import base64

            registro: dict[str, Any] = {
                "via": "ws",
                "binario": True,
                "crudo": base64.b64encode(crudo).decode("ascii"),
            }
        else:
            registro = {"via": "ws", "crudo": crudo}
        self.neptun.escribir(registro, momento)
        self.contadores.por_tipo[tipo] = self.contadores.por_tipo.get(tipo, 0) + 1
        self.ultima_recepcion = self.ultima_ws = momento
        self.via = "ws"
        if tipo == "heartbeat":
            self.ultimo_latido = momento

    def _cerrar_hueco(self, momento: datetime) -> None:
        if self.hueco is None:
            return
        hueco, self.hueco = self.hueco, None
        self.caido_desde_reloj = None
        segundos = round((momento - hueco.desde).total_seconds(), 3)
        nota = {
            "evento": "hueco",
            "desde": instante(hueco.desde),
            "hasta": instante(momento),
            "segundos": segundos,
            "motivo": hueco.motivo,
            "respaldo_rest": hueco.respaldo,
        }
        self.neptun.escribir(nota, momento)
        _anadir_linea(self.datos / "huecos.jsonl", {"fuente": NEPTUN, **nota})
        self.contadores.huecos += 1
        if momento - hueco.desde > HUECO_LARGO:
            self.ultimo_hueco_largo = {
                "desde": nota["desde"],
                "hasta": nota["hasta"],
                "motivo": hueco.motivo,
            }
        registro_log.info("hueco del flujo cerrado: %.0f s (%s)", segundos, hueco.motivo)

    def desconectado(self, motivo: str) -> None:
        momento = self.ahora()
        self.conectado = False
        if self.hueco is None:
            self.hueco = Hueco(self.ultima_ws or momento, motivo)
        if self.caido_desde_reloj is None:
            self.caido_desde_reloj = self.reloj()
        self.neptun.escribir({"evento": "desconectado", "motivo": motivo}, momento)
        registro_log.warning("flujo cortado: %s", motivo)

    async def flujo(self) -> None:
        espera = ESPERA_INICIAL_S
        while not self.parar.is_set():
            empezo = self.reloj()
            motivo = "conexión cerrada"
            try:
                async with self._conectar() as conexion:
                    self.conectado = True
                    self.neptun.escribir({"evento": "conectado"}, self.ahora())
                    while not self.parar.is_set():
                        crudo = await asyncio.wait_for(conexion.recv(), SILENCIO_S)
                        self.recibido_flujo(crudo)
            except asyncio.CancelledError:
                raise
            except TimeoutError:
                motivo = f"sin mensajes en {SILENCIO_S:.0f} s"
            except Exception as error:
                motivo = f"{type(error).__name__}: {error}"[:300]
            if self.parar.is_set():
                break
            self.desconectado(motivo)
            if self.reloj() - empezo >= CONEXION_ESTABLE_S:
                espera = ESPERA_INICIAL_S
            await self._esperar(espera)
            espera = min(espera * 2, ESPERA_MAXIMA_S)

    # --- NEPTUN: respaldo REST y mensajes -------------------------------------------------
    async def _rest(self, nombre: str, via: str) -> Respuesta | None:
        await self.ritmo_rest.turno()
        url = NEPTUN_REST + nombre
        try:
            respuesta = await asyncio.to_thread(self._pedir, url)
        except Exception as error:
            registro_log.warning("%s no responde: %s", url, error)
            return None
        momento = self.ahora()
        self.neptun.escribir(
            {"via": via, "url": url, "http": respuesta.estado, "crudo": respuesta.cuerpo}, momento
        )
        if via == "rest":
            self.contadores.rest += 1
            if 200 <= respuesta.estado < 300:
                self.ultima_recepcion = momento
                if self.via != "ws" or not self.conectado:
                    self.via = "rest"
        return respuesta

    def en_respaldo(self) -> bool:
        return (
            not self.conectado
            and self.caido_desde_reloj is not None
            and self.reloj() - self.caido_desde_reloj >= RESPALDO_TRAS_S
        )

    async def respaldo(self) -> None:
        vuelta = 0
        while not self.parar.is_set():
            if not self.en_respaldo():
                await self._esperar(5.0)
                continue
            respuesta = await self._rest(RESPALDO[vuelta % len(RESPALDO)], "rest")
            vuelta += 1
            if respuesta is not None and self.hueco is not None:
                self.hueco.respaldo += 1

    async def mensajes(self) -> None:
        while not self.parar.is_set():
            await self._mensajes_una_vez()
            await self._esperar(INTERVALO_MENSAJES_S)

    async def _mensajes_una_vez(self) -> None:
        await self.ritmo_rest.turno()
        url = NEPTUN_REST + MENSAJES
        try:
            respuesta = await asyncio.to_thread(self._pedir, url)
        except Exception as error:
            registro_log.warning("%s no responde: %s", url, error)
            return
        if respuesta.cuerpo == self.ultimo_mensajes:
            return
        momento = self.ahora()
        self.neptun.escribir(
            {"via": "mensajes", "url": url, "http": respuesta.estado, "crudo": respuesta.cuerpo},
            momento,
        )
        self.contadores.mensajes += 1
        if not 200 <= respuesta.estado < 300:
            return
        self.ultimo_mensajes = respuesta.cuerpo
        fechas = _fechas_mensajes(respuesta.cuerpo)
        if not fechas:
            return
        # Si el más antiguo de ahora es posterior al más nuevo de antes, falta lo de en medio.
        if self.mensajes_hasta is not None and min(fechas) > self.mensajes_hasta:
            self.neptun.escribir(
                {"evento": "hueco_mensajes", "desde": self.mensajes_hasta, "hasta": min(fechas)},
                momento,
            )
        self.mensajes_hasta = max(fechas)

    # --- Fuerza Aérea (t.me/kpszsu) ---------------------------------------------------------
    async def _pagina(self, antes: int | None) -> list[Bloque] | None:
        await self.ritmo_telegram.turno()
        url = KPSZSU_URL + (f"?before={antes}" if antes is not None else "")
        try:
            respuesta = await asyncio.to_thread(self._pedir, url)
        except Exception as error:
            registro_log.warning("t.me/s/kpszsu no responde: %s", error)
            return None
        if respuesta.estado != 200 or "tgme_channel_info" not in respuesta.cuerpo:
            registro_log.warning("t.me/s/kpszsu responde %s sin la página", respuesta.estado)
            return None
        return bloques_pagina(respuesta.cuerpo)

    def _guardar_bloques(self, bloques: list[Bloque], url: str) -> int:
        momento = self.ahora()
        nuevos = 0
        for bloque in sorted(bloques, key=lambda b: b.id):
            visto = self.kpszsu_vistos.get(bloque.id)
            if visto is not None and visto[0] == bloque.huella:
                continue
            version = 0 if visto is None else visto[1] + 1
            self.kpszsu.escribir(
                {
                    "via": "telegram_web",
                    "url": url,
                    "id": bloque.id,
                    "fecha": bloque.fecha,
                    "version": version,
                    "crudo": bloque.crudo,
                },
                momento,
            )
            self.kpszsu_vistos[bloque.id] = (bloque.huella, version)
            self.contadores.kpszsu += 1
            nuevos += 1
        return nuevos

    async def kpszsu_una_vez(self, repasar: bool) -> None:
        bloques = await self._pagina(None)
        if bloques is None:
            if self.kpszsu_hueco is None and self.kpszsu_ultima is not None:
                self.kpszsu_hueco = Hueco(self.kpszsu_ultima, "t.me/s/kpszsu no responde")
            return
        momento = self.ahora()
        if self.kpszsu_hueco is not None:
            hueco, self.kpszsu_hueco = self.kpszsu_hueco, None
            if momento - hueco.desde > timedelta(seconds=2 * INTERVALO_KPSZSU_S):
                nota = {
                    "evento": "hueco",
                    "desde": instante(hueco.desde),
                    "hasta": instante(momento),
                    "segundos": round((momento - hueco.desde).total_seconds(), 3),
                    "motivo": hueco.motivo,
                }
                self.kpszsu.escribir(nota, momento)
                _anadir_linea(self.datos / "huecos.jsonl", {"fuente": KPSZSU, **nota})
        self.kpszsu_ultima = momento
        todos = list(bloques)
        # Enlazar con lo ya visto: si la página empieza después del último id guardado, se leen
        # las anteriores (como mucho PAGINAS_ENLACE_MAXIMAS).
        if bloques and self.kpszsu_ultimo_id is not None:
            menor = min(b.id for b in bloques)
            paginas = 0
            while menor > self.kpszsu_ultimo_id + 1 and paginas < PAGINAS_ENLACE_MAXIMAS:
                anteriores = await self._pagina(menor)
                paginas += 1
                # Sin publicaciones más antiguas que las que ya había, no se avanza: se deja.
                if not anteriores or min(b.id for b in anteriores) >= menor:
                    break
                todos.extend(anteriores)
                menor = min(b.id for b in anteriores)
            if menor > self.kpszsu_ultimo_id + 1:
                self.kpszsu.escribir(
                    {
                        "evento": "ids_sin_enlazar",
                        "desde_id": self.kpszsu_ultimo_id + 1,
                        "hasta_id": menor - 1,
                    },
                    self.ahora(),
                )
        elif bloques and repasar:
            anteriores = await self._pagina(min(b.id for b in bloques))
            if anteriores:
                todos.extend(anteriores)
        self._guardar_bloques(todos, KPSZSU_URL)
        if todos:
            self.kpszsu_ultimo_id = max(self.kpszsu_ultimo_id or 0, *(b.id for b in todos))

    async def canal_kpszsu(self) -> None:
        ultimo_repaso = self.reloj()
        while not self.parar.is_set():
            repasar = self.reloj() - ultimo_repaso >= REPASO_KPSZSU_S
            if repasar:
                ultimo_repaso = self.reloj()
            await self.kpszsu_una_vez(repasar)
            await self._esperar(INTERVALO_KPSZSU_S)

    # --- Vigilancia propia ------------------------------------------------------------------
    async def vigilar(self) -> None:
        ultima_revision = ultimo_resumen = self.reloj()
        while not self.parar.is_set():
            self.guardar_registro()
            if self.reloj() - ultimo_resumen >= RESUMEN_CADA_S:
                ultimo_resumen = self.reloj()
                registro_log.info(
                    "en marcha por %s: %s, rest %d, mensajes %d, kpszsu %d, huecos %d",
                    self.via, self.contadores.por_tipo, self.contadores.rest,
                    self.contadores.mensajes, self.contadores.kpszsu, self.contadores.huecos,
                )  # fmt: skip
            if self.clon and self.reloj() - ultima_revision >= REVISION_CODIGO_S:
                ultima_revision = self.reloj()
                nuevo = huella_codigo(self.clon)
                if nuevo and self.codigo and nuevo != self.codigo:
                    registro_log.info("código nuevo en el clon: el servicio sale para tomarlo")
                    self.parar.set()
                    break
            await self._esperar(REGISTRO_CADA_S)

    async def _esperar(self, segundos: float) -> None:
        """Duerme, pero despierta en cuanto se pide parar."""
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(self.parar.wait(), segundos)

    async def servir(self) -> None:
        self.neptun.escribir({"evento": "arranque", "agente": AGENTE}, self.ahora())
        tareas = [
            asyncio.create_task(c())
            for c in (self.flujo, self.respaldo, self.mensajes, self.canal_kpszsu, self.vigilar)
        ]
        try:
            await self.parar.wait()
        finally:
            for tarea in tareas:
                tarea.cancel()
            await asyncio.gather(*tareas, return_exceptions=True)
            self.neptun.escribir({"evento": "parada"}, self.ahora())
            self.guardar_registro()
            self.neptun.cerrar()
            self.kpszsu.cerrar()


def _fechas_mensajes(cuerpo: str) -> list[str]:
    try:
        datos = json.loads(cuerpo)
    except ValueError:
        return []
    lista = datos.get("messages") if isinstance(datos, dict) else None
    if not isinstance(lista, list):
        return []
    return [m["date"] for m in lista if isinstance(m, dict) and isinstance(m.get("date"), str)]


def _o_nulo(momento: datetime | None) -> str | None:
    return instante(momento) if momento is not None else None


def _leer_json(ruta: Path) -> dict[str, Any] | None:
    try:
        datos = json.loads(ruta.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return datos if isinstance(datos, dict) else None


def _escribir_json(ruta: Path, datos: dict[str, Any]) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    temporal = ruta.with_name(ruta.name + ".tmp")
    with temporal.open("w", encoding="utf-8", newline="\n") as fichero:
        json.dump(datos, fichero, ensure_ascii=False)
        fichero.write("\n")
    temporal.replace(ruta)


def _anadir_linea(ruta: Path, datos: dict[str, Any]) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with ruta.open("a", encoding="utf-8", newline="\n") as fichero:
        fichero.write(json.dumps(datos, ensure_ascii=False) + "\n")


def huella_codigo(clon: Path) -> str:
    """Huella del código propio en el clon (los blobs de HEAD), o vacío si no se puede leer."""
    try:
        salida = subprocess.run(
            ["git", "-C", str(clon), "rev-parse", *(f"HEAD:{c}" for c in CODIGO)],
            capture_output=True, text=True, timeout=10, check=False,
        )  # fmt: skip
    except (OSError, subprocess.SubprocessError):
        return ""
    return salida.stdout.strip() if salida.returncode == 0 else ""


def servir(args: argparse.Namespace) -> int:
    datos: Path = args.datos or directorio_datos()
    registro: Path | None = args.registro
    if registro is None and os.environ.get("EODI_SEGUIMIENTO_REGISTRO"):
        registro = Path(os.environ["EODI_SEGUIMIENTO_REGISTRO"])
    clon = RAIZ if (RAIZ / ".git").exists() else None

    async def principal_async() -> None:
        servicio = Servicio(datos, registro, clon=clon)
        bucle = asyncio.get_running_loop()
        for senal in (signal.SIGTERM, signal.SIGINT):
            with contextlib.suppress(NotImplementedError, AttributeError, ValueError):
                bucle.add_signal_handler(senal, servicio.parar.set)
        await servicio.servir()

    asyncio.run(principal_async())
    return 0


def principal(argumentos: list[str] | None = None) -> int:
    opciones = argparse.ArgumentParser(description=__doc__)
    sub = opciones.add_subparsers(dest="orden", required=True)
    s = sub.add_parser("servir")
    s.add_argument("--datos", type=Path)
    s.add_argument("--registro", type=Path)
    args = opciones.parse_args(argumentos)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    return servir(args)


if __name__ == "__main__":
    sys.exit(principal())
