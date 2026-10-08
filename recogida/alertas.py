"""Archivo de las alertas aéreas de Ucrania que reparte alerts.in.ua: solo consultar y guardar.

alerts.in.ua (https://devs.alerts.in.ua/) es un servicio voluntario ucraniano que reparte las
alertas que declaran las autoridades de cada región, recogidas de la aplicación oficial de alerta
y de los canales oficiales locales. Su API, con token, da las alertas activas y el histórico del
último mes por región; el histórico no va más atrás: lo que no se archiva se pierde. Atribución de
todo lo archivado: «alerts.in.ua»; en cualquier uso futuro, «alerta declarada por las autoridades
ucranianas, recogida por alerts.in.ua».

Lo que hace el servicio, siempre en marcha (unidad eodi-alertas):

- **Activas**, cada minuto: `/v1/alerts/active.json`, con `If-Modified-Since` (la hora
  `Last-Modified` de la respuesta anterior). Un 304 no se guarda; una respuesta cuyo cuerpo cambia
  se guarda entera, tal cual.
- **Histórico**, una vez al día (y en el primer arranque): `/v1/regions/<uid>/alerts/month_ago.json`
  de las 27 regiones, una consulta por minuto como mucho (el límite del histórico es 2 por minuto),
  también con `If-Modified-Since` por región. Rellena lo que la captura no viera (un corte, un
  reinicio) y trae la hora de fin de cada alerta. El histórico de una región trae sus distritos,
  municipios y ciudades, con el nivel, pero no la lista de amenazas: esa solo está en las activas.
- **Límites.** Ninguna consulta sale antes de 20 s de la anterior (como mucho 3 por minuto entre
  todas; la API admite 8 a 10). Un fallo de red o un 5xx espera 1, 2, 4… hasta 15 minutos; un 429
  para todo 5 minutos; un 401 o 403 (token no válido o IP bloqueada) se anota para la vigilancia y
  se reintenta cada 10 minutos.

Dos archivos, en ficheros por hora UTC de recepción (`<datos>/<fuente>/<AAAA>/<MM>/
<fuente>-<AAAA-MM-DD>T<HH>.jsonl`, como el del seguimiento en directo; los comprime, indexa y
copia `recogida/seguimiento_archivo.py`):

- `alertas`, en crudo, cada respuesta que cambia:
      {"recibido", "via": "activas" | "historico", "fuente": "alerts.in.ua", "url", "region",
       "http", "last_modified", "crudo": <cuerpo, tal cual>}
      {"recibido", "evento": "arranque" | "parada" | "error", ...}
- `alertas_tabla`, la tabla de alertas, que solo se amplía: una línea por versión de cada alerta.
  La primera vez que se ve una alerta, versión 0; si cambia lo que da una vía (las activas o el
  histórico: cada una se compara con lo último que dio ella misma, porque el histórico no lleva
  las amenazas), una versión nueva, sin tocar las anteriores. Cuando una alerta deja de estar
  entre las activas, una versión con `cambio: "sale_de_activas"`: su fin, al minuto, hasta que el
  histórico traiga el `finished_at` oficial.
      {"recibido", "id", "version", "via", "cambio": "nueva" | "cambia" | "sale_de_activas",
       "fuente": "alerts.in.ua", "huella", "utc": {inicio, fin, actualizada, amenazas},
       "alerta": <la alerta tal como llegó>}
  Las horas de la API vienen en UTC (ISO 8601 con «Z»); `utc` las repite normalizadas
  (`AAAA-MM-DDTHH:MM:SS.mmmZ`) y `alerta` guarda el valor original.

Lo que hace falta para seguir sin repetir (la última huella por alerta y vía, las activas de la
última respuesta, los Last-Modified y la última pasada del histórico) está en
`<datos>/alertas_tabla/estado.json`; si falta, se rehace con la tabla de los últimos 40 días.

El registro (`/home/eodi/.eodi/alertas.json`) lleva la última respuesta correcta (200 o 304), el
último cambio, el último error de autorización y la última pasada del histórico: lo mira la
vigilancia (recogida/vigilancia.py).

El token (`/home/eodi/.eodi/alerts_in_ua_token`, solo legible por el usuario del servicio) va en la
cabecera `Authorization` y nunca en una dirección, un registro ni un fichero del archivo.

Uso: python -m recogida.alertas servir [--datos <dir>] [--registro <json>]
     python -m recogida.alertas tabla-desde-crudo [--datos <dir>]   (añade a la tabla lo que haya
         en el archivo en crudo y no esté ya; repetible)
"""

import argparse
import contextlib
import gzip
import hashlib
import json
import logging
import os
import signal
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from recogida.seguimiento import (
    AGENTE,
    Archivo,
    directorio_datos,
    huella_codigo,
    instante,
    leer_instante,
)

registro_log = logging.getLogger("alertas")

RAIZ = Path(__file__).resolve().parent.parent
FUENTE = "alerts.in.ua"
CRUDO = "alertas"
TABLA = "alertas_tabla"
API = "https://api.alerts.in.ua"
ACTIVAS = "/v1/alerts/active.json"
HISTORICO = "/v1/regions/{uid}/alerts/month_ago.json"
# Las 27 regiones (oblasts, Kyiv y Sevastopol) de la documentación de la API. El histórico de una
# región trae también sus distritos, municipios y ciudades; con un distrito responde 404.
REGIONES = (
    3, 4, 5, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29,
    30, 31,
)  # fmt: skip

# Límites de la API: 8 a 10 consultas por minuto por IP (12 como máximo) y 2 por minuto el
# histórico. Aquí, holgadamente por debajo: una consulta cada 20 s como mucho entre todas, las
# activas cada minuto y el histórico una región por minuto.
PAUSA_MINIMA_S = 20.0
INTERVALO_ACTIVAS_S = 60.0
INTERVALO_HISTORICO_S = 60.0
HISTORICO_CADA = timedelta(hours=24)
ESPERA_INICIAL_S = 60.0
ESPERA_MAXIMA_S = 900.0
ESPERA_429_S = 300.0
ESPERA_AUTORIZACION_S = 600.0
TOPE_HTTP_S = 60.0
# Lo que se recuerda de cada alerta para no repetirla: lo visto en los últimos 40 días (el
# histórico cubre 30).
MEMORIA = timedelta(days=40)
REGISTRO_CADA_S = 30.0
RESUMEN_CADA_S = 600.0
REVISION_CODIGO_S = 300.0
CODIGO = ("recogida/alertas.py", "recogida/seguimiento.py", "servidor/alertas.sh")

TOKEN_VARIABLE = "EODI_ALERTAS_TOKEN_FICHERO"


@dataclass(frozen=True)
class Respuesta:
    http: int
    cuerpo: str
    last_modified: str | None


Pedir = Callable[[str, dict[str, str]], Respuesta]


def pedir_http(token: str) -> Pedir:
    def pedir(ruta: str, cabeceras: dict[str, str]) -> Respuesta:
        peticion = urllib.request.Request(
            API + ruta,
            headers={"Authorization": f"Bearer {token}", "User-Agent": AGENTE, **cabeceras},
        )
        try:
            with urllib.request.urlopen(peticion, timeout=TOPE_HTTP_S) as r:
                return Respuesta(
                    r.status, r.read().decode("utf-8", "replace"), r.headers.get("Last-Modified")
                )
        except urllib.error.HTTPError as error:
            return Respuesta(
                error.code, error.read().decode("utf-8", "replace"),
                error.headers.get("Last-Modified"),
            )  # fmt: skip
        except (OSError, ValueError) as error:
            return Respuesta(0, f"{type(error).__name__}: {error}", None)

    return pedir


# --- Tabla de alertas -------------------------------------------------------------------------
def _utc(texto: object) -> str | None:
    momento = leer_instante(texto)
    if momento is None:
        return None
    return momento.strftime("%Y-%m-%dT%H:%M:%S.") + f"{momento.microsecond // 1000:03d}Z"


def huella_alerta(alerta: dict[str, Any]) -> str:
    texto = json.dumps(alerta, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()[:24]


def fila(
    alerta: dict[str, Any], version: int, via: str, cambio: str, momento: datetime
) -> dict[str, Any]:
    lista = alerta.get("threats")
    amenazas: list[Any] = lista if isinstance(lista, list) else []
    return {
        "id": alerta.get("id"),
        "version": version,
        "via": via,
        "cambio": cambio,
        "fuente": FUENTE,
        "huella": huella_alerta(alerta),
        "utc": {
            "inicio": _utc(alerta.get("started_at")),
            "fin": _utc(alerta.get("finished_at")),
            "actualizada": _utc(alerta.get("updated_at")),
            "amenazas": [_utc(a.get("started_at")) for a in amenazas if isinstance(a, dict)],
        },
        "alerta": alerta,
    }


def alertas_de(cuerpo: str) -> list[dict[str, Any]] | None:
    """Las alertas de una respuesta, o None si no es la forma esperada."""
    try:
        datos = json.loads(cuerpo)
    except ValueError:
        return None
    alertas = datos.get("alerts") if isinstance(datos, dict) else None
    if not isinstance(alertas, list):
        return None
    return [a for a in alertas if isinstance(a, dict) and a.get("id") is not None]


class Tabla:
    """Lo último visto de cada alerta, por vía, para escribir solo versiones nuevas."""

    def __init__(self, datos: Path, archivo: Archivo) -> None:
        self.datos = datos
        self.archivo = archivo
        self.alertas: dict[str, dict[str, Any]] = {}
        self.activas: list[str] = []
        self.last_modified: dict[str, str] = {}
        self.ultima_pasada_historico: str | None = None
        self.historico_pendiente: list[int] = []

    @property
    def ruta_estado(self) -> Path:
        return self.datos / TABLA / "estado.json"

    def cargar(self, ahora: datetime) -> None:
        try:
            estado = json.loads(self.ruta_estado.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            estado = None
        if isinstance(estado, dict):
            self.alertas = estado.get("alertas", {})
            self.activas = [str(i) for i in estado.get("activas", [])]
            self.last_modified = estado.get("last_modified", {})
            self.ultima_pasada_historico = estado.get("ultima_pasada_historico")
            self.historico_pendiente = [int(u) for u in estado.get("historico_pendiente", [])]
            return
        self.rehacer(ahora)

    def rehacer(self, ahora: datetime) -> None:
        """Lo último de cada alerta, leyendo la tabla de los últimos 40 días."""
        desde = ahora - MEMORIA
        for linea in lineas_tabla(self.datos, desde):
            self._anotar(linea)
        registro_log.info("estado de la tabla rehecho: %d alertas", len(self.alertas))

    def _anotar(self, linea: dict[str, Any]) -> None:
        clave = str(linea.get("id"))
        previa = self.alertas.get(clave, {"version": -1, "vias": {}})
        previa["version"] = max(int(previa["version"]), int(linea.get("version", 0)))
        if linea.get("cambio") != "sale_de_activas":
            previa["vias"][str(linea.get("via"))] = linea.get("huella")
        previa["fuera"] = linea.get("cambio") == "sale_de_activas"
        previa["visto"] = linea.get("recibido")
        self.alertas[clave] = previa

    def guardar(self, ahora: datetime) -> None:
        limite = instante(ahora - MEMORIA)
        self.alertas = {
            k: v for k, v in self.alertas.items() if str(v.get("visto", "")) >= limite
        }  # fmt: skip
        estado = {
            "actualizado": instante(ahora),
            "alertas": self.alertas,
            "activas": self.activas,
            "last_modified": self.last_modified,
            "ultima_pasada_historico": self.ultima_pasada_historico,
            "historico_pendiente": self.historico_pendiente,
        }
        self.ruta_estado.parent.mkdir(parents=True, exist_ok=True)
        temporal = self.ruta_estado.with_name(self.ruta_estado.name + ".tmp")
        temporal.write_text(
            json.dumps(estado, ensure_ascii=False, separators=(",", ":")) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        os.replace(temporal, self.ruta_estado)

    def _escribir(self, linea: dict[str, Any], momento: datetime) -> None:
        self.archivo.escribir(linea, momento)
        self._anotar({**linea, "recibido": instante(momento)})

    def incorporar(
        self, alertas: list[dict[str, Any]], via: str, momento: datetime
    ) -> dict[str, int]:
        """Escribe las versiones nuevas; con las activas, también las que han dejado de estarlo."""
        cuenta = {"nuevas": 0, "cambian": 0, "salen": 0}
        for alerta in alertas:
            clave = str(alerta["id"])
            huella = huella_alerta(alerta)
            previa = self.alertas.get(clave)
            if previa is None:
                self._escribir(fila(alerta, 0, via, "nueva", momento), momento)
                cuenta["nuevas"] += 1
                continue
            if previa["vias"].get(via) == huella and not (via == "activas" and previa.get("fuera")):
                previa["visto"] = instante(momento)
                continue
            version = int(previa["version"]) + 1
            self._escribir(fila(alerta, version, via, "cambia", momento), momento)
            cuenta["cambian"] += 1
        if via == "activas":
            ahora_activas = [str(a["id"]) for a in alertas]
            conjunto = set(ahora_activas)
            for clave in self.activas:
                previa = self.alertas.get(clave)
                if clave in conjunto or previa is None or previa.get("fuera"):
                    continue
                linea = {
                    "id": _id(clave),
                    "version": int(previa["version"]) + 1,
                    "via": "activas",
                    "cambio": "sale_de_activas",
                    "fuente": FUENTE,
                }
                self._escribir(linea, momento)
                cuenta["salen"] += 1
            self.activas = ahora_activas
        return cuenta


def _id(clave: str) -> int | str:
    return int(clave) if clave.isdigit() else clave


def _lineas_fichero(ruta: Path) -> Iterator[dict[str, Any]]:
    abrir = gzip.open if ruta.name.endswith(".gz") else open
    with abrir(ruta, "rt", encoding="utf-8") as fichero:
        for texto in fichero:
            if texto.strip():
                with contextlib.suppress(ValueError):
                    yield json.loads(texto)


def ficheros(datos: Path, fuente: str, desde: datetime | None = None) -> list[Path]:
    rutas = sorted((datos / fuente).glob("*/*/*.jsonl*"))
    if desde is None:
        return rutas
    corte = f"{fuente}-{desde:%Y-%m-%dT%H}"
    return [r for r in rutas if r.name.split(".", 1)[0] >= corte]


def lineas_tabla(datos: Path, desde: datetime | None = None) -> Iterator[dict[str, Any]]:
    for ruta in ficheros(datos, TABLA, desde):
        yield from _lineas_fichero(ruta)


# --- Servicio -----------------------------------------------------------------------------------
class Servicio:
    def __init__(
        self,
        datos: Path,
        registro: Path | None,
        pedir: Pedir,
        reloj: Callable[[], float] = time.monotonic,
        ahora: Callable[[], datetime] = lambda: datetime.now(UTC),
        clon: Path | None = None,
    ) -> None:
        self.datos = datos
        self.registro = registro
        self.pedir = pedir
        self.reloj = reloj
        self.ahora = ahora
        self.clon = clon
        self.codigo = huella_codigo(clon) if clon else ""
        self.crudo = Archivo(datos, CRUDO)
        self.tabla = Tabla(datos, Archivo(datos, TABLA))
        self.parar = False
        self.ultima_peticion: float | None = None
        self.proxima_activas = 0.0
        self.proxima_historico = 0.0
        self.esperas = {"activas": 0.0, "historico": 0.0}
        self.estado: dict[str, Any] = {}
        self.cuentas = {"peticiones": 0, "guardadas": 0, "no_modificadas": 0, "errores": 0}

    # Registro para la vigilancia.
    def documento_registro(self) -> dict[str, Any]:
        return {
            "fuente": FUENTE,
            "actualizado": instante(self.ahora()),
            **self.estado,
            "ultima_pasada_historico": self.tabla.ultima_pasada_historico,
            "historico_pendiente": len(self.tabla.historico_pendiente),
            "alertas_activas": len(self.tabla.activas),
        }

    def guardar_registro(self) -> None:
        if self.registro is None:
            return
        temporal = self.registro.with_name(self.registro.name + ".tmp")
        temporal.write_text(
            json.dumps(self.documento_registro(), ensure_ascii=False, indent=1) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        os.replace(temporal, self.registro)

    def evento(self, nombre: str, **extra: Any) -> None:
        self.crudo.escribir({"evento": nombre, "fuente": FUENTE, **extra}, self.ahora())

    # Consultas.
    def _consultar(self, via: str, ruta: str, region: int | None) -> Respuesta:
        cabeceras = {}
        if ruta in self.tabla.last_modified:
            cabeceras["If-Modified-Since"] = self.tabla.last_modified[ruta]
        self.ultima_peticion = self.reloj()
        self.cuentas["peticiones"] += 1
        respuesta = self.pedir(ruta, cabeceras)
        momento = self.ahora()
        marca = instante(momento)
        if respuesta.http in (200, 304):
            self.estado["ultima_respuesta"] = marca
            self.estado.pop("error_autorizacion", None)
            self.esperas[via] = 0.0
            if respuesta.last_modified:
                self.tabla.last_modified[ruta] = respuesta.last_modified
        if respuesta.http == 304:
            self.cuentas["no_modificadas"] += 1
            return respuesta
        if respuesta.http == 200:
            alertas = alertas_de(respuesta.cuerpo)
            huella = hashlib.sha256(respuesta.cuerpo.encode("utf-8")).hexdigest()
            if alertas is None:
                self._error(via, ruta, region, respuesta, "respuesta sin la lista de alertas")
                return respuesta
            if self.estado.get(f"huella:{ruta}") != huella:
                self.crudo.escribir(
                    {
                        "via": via, "fuente": FUENTE, "url": ruta, "region": region,
                        "http": respuesta.http, "last_modified": respuesta.last_modified,
                        "crudo": respuesta.cuerpo,
                    },
                    momento,
                )  # fmt: skip
                self.estado[f"huella:{ruta}"] = huella
                self.estado["ultimo_cambio"] = marca
                self.cuentas["guardadas"] += 1
                cuenta = self.tabla.incorporar(alertas, via, momento)
                if any(cuenta.values()):
                    registro_log.info("%s %s: %s", via, region or "", cuenta)
                self.tabla.guardar(momento)
            return respuesta
        self._error(via, ruta, region, respuesta, "")
        return respuesta

    def _error(
        self, via: str, ruta: str, region: int | None, respuesta: Respuesta, motivo: str
    ) -> None:
        self.cuentas["errores"] += 1
        marca = instante(self.ahora())
        detalle = (motivo or respuesta.cuerpo)[:300]
        # El cuerpo de un error de la API es un mensaje corto; nunca lleva el token.
        self.evento("error", via=via, url=ruta, region=region, http=respuesta.http, motivo=detalle)
        self.estado["ultimo_error"] = {"momento": marca, "http": respuesta.http, "url": ruta}
        if respuesta.http in (401, 403):
            self.estado["error_autorizacion"] = {"momento": marca, "http": respuesta.http}
            espera = ESPERA_AUTORIZACION_S
        elif respuesta.http == 429:
            espera = ESPERA_429_S
        else:
            previa = self.esperas[via]
            espera = min(ESPERA_MAXIMA_S, previa * 2 if previa else ESPERA_INICIAL_S)
        self.esperas[via] = espera
        registro_log.warning("%s %s: HTTP %s %s; espera %.0f s", via, ruta, respuesta.http,
                             detalle[:120], espera)  # fmt: skip
        siguiente = self.reloj() + espera
        if via == "activas" or respuesta.http in (401, 403, 429):
            self.proxima_activas = max(self.proxima_activas, siguiente)
        if via == "historico" or respuesta.http in (401, 403, 429):
            self.proxima_historico = max(self.proxima_historico, siguiente)

    def toca_historico(self) -> None:
        """Pone en cola las 27 regiones si la última pasada completa tiene más de un día."""
        if self.tabla.historico_pendiente:
            return
        ultima = leer_instante(self.tabla.ultima_pasada_historico)
        if ultima is None or self.ahora() - ultima >= HISTORICO_CADA:
            self.tabla.historico_pendiente = list(REGIONES)
            registro_log.info("pasada del histórico: %d regiones", len(REGIONES))

    def paso(self) -> float:
        """Hace la consulta que toque, si toca; devuelve cuánto esperar hasta la siguiente."""
        ahora = self.reloj()
        if self.ultima_peticion is not None and ahora - self.ultima_peticion < PAUSA_MINIMA_S:
            return self.ultima_peticion + PAUSA_MINIMA_S - ahora
        if ahora >= self.proxima_activas:
            self.proxima_activas = ahora + INTERVALO_ACTIVAS_S
            self._consultar("activas", ACTIVAS, None)
            return 1.0
        self.toca_historico()
        if self.tabla.historico_pendiente and ahora >= self.proxima_historico:
            uid = self.tabla.historico_pendiente[0]
            self.proxima_historico = ahora + INTERVALO_HISTORICO_S
            respuesta = self._consultar("historico", HISTORICO.format(uid=uid), uid)
            # Un 404 no se repite (la región no existe para la API); lo demás, sí.
            if respuesta.http in (200, 304, 404):
                self.tabla.historico_pendiente.pop(0)
                if not self.tabla.historico_pendiente:
                    self.tabla.ultima_pasada_historico = instante(self.ahora())
                    registro_log.info("pasada del histórico terminada")
                self.tabla.guardar(self.ahora())
            return 1.0
        siguientes = [self.proxima_activas]
        if self.tabla.historico_pendiente:
            siguientes.append(self.proxima_historico)
        return max(0.5, min(siguientes) - ahora)

    def servir(self, dormir: Callable[[float], None] = time.sleep) -> None:
        self.tabla.cargar(self.ahora())
        self.evento("arranque")
        ultimo_registro = ultimo_resumen = ultima_revision = self.reloj()
        self.guardar_registro()
        try:
            while not self.parar:
                espera = self.paso()
                ahora = self.reloj()
                if ahora - ultimo_registro >= REGISTRO_CADA_S:
                    self.guardar_registro()
                    ultimo_registro = ahora
                if ahora - ultimo_resumen >= RESUMEN_CADA_S:
                    registro_log.info("en 10 min: %s; activas %d", self.cuentas,
                                      len(self.tabla.activas))  # fmt: skip
                    self.cuentas = dict.fromkeys(self.cuentas, 0)
                    ultimo_resumen = ahora
                if self.clon and ahora - ultima_revision >= REVISION_CODIGO_S:
                    ultima_revision = ahora
                    if (nuevo := huella_codigo(self.clon)) and nuevo != self.codigo:
                        registro_log.info("el código ha cambiado: el servicio sale para relanzarse")
                        break
                dormir(min(espera, 5.0))
        finally:
            self.evento("parada")
            self.tabla.guardar(self.ahora())
            self.guardar_registro()
            self.crudo.cerrar()
            self.tabla.archivo.cerrar()


def leer_token() -> str:
    ruta = os.environ.get(TOKEN_VARIABLE)
    if not ruta:
        raise SystemExit(f"falta {TOKEN_VARIABLE}")
    token = Path(ruta).read_text(encoding="utf-8").strip()
    if not token:
        raise SystemExit("el fichero del token está vacío")
    return token


# --- Tabla desde el crudo ---------------------------------------------------------------------
def tabla_desde_crudo(datos: Path, ahora: datetime) -> dict[str, int]:
    """Pasa por la tabla cada respuesta del archivo en crudo, en orden; lo ya anotado no se
    repite. Las líneas nuevas llevan la hora de recepción de la respuesta."""
    archivo = Archivo(datos, TABLA)
    tabla = Tabla(datos, archivo)
    tabla.cargar(ahora)
    total = {"respuestas": 0, "nuevas": 0, "cambian": 0, "salen": 0}
    try:
        for ruta in ficheros(datos, CRUDO):
            for linea in _lineas_fichero(ruta):
                if linea.get("http") != 200 or linea.get("via") not in ("activas", "historico"):
                    continue
                alertas = alertas_de(str(linea.get("crudo", "")))
                momento = leer_instante(linea.get("recibido"))
                if alertas is None or momento is None:
                    continue
                total["respuestas"] += 1
                for clave, valor in tabla.incorporar(alertas, str(linea["via"]), momento).items():
                    total[clave] += valor
    finally:
        archivo.cerrar()
        tabla.guardar(ahora)
    return total


def principal(argumentos: list[str] | None = None) -> int:
    opciones = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = opciones.add_subparsers(dest="orden", required=True)
    s = sub.add_parser("servir")
    s.add_argument("--datos", type=Path)
    s.add_argument("--registro", type=Path)
    t = sub.add_parser("tabla-desde-crudo")
    t.add_argument("--datos", type=Path)
    args = opciones.parse_args(argumentos)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    datos: Path = args.datos or directorio_datos()
    if args.orden == "tabla-desde-crudo":
        print(json.dumps(tabla_desde_crudo(datos, datetime.now(UTC))))
        return 0
    registro: Path | None = args.registro
    if registro is None and os.environ.get("EODI_ALERTAS_REGISTRO"):
        registro = Path(os.environ["EODI_ALERTAS_REGISTRO"])
    clon = RAIZ if (RAIZ / ".git").exists() else None
    servicio = Servicio(datos, registro, pedir_http(leer_token()), clon=clon)

    def parar(*_: object) -> None:
        servicio.parar = True

    signal.signal(signal.SIGTERM, parar)
    signal.signal(signal.SIGINT, parar)
    servicio.servir()
    return 0


if __name__ == "__main__":
    sys.exit(principal())
