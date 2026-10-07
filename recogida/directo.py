"""Servicio de detección en directo de cierres de aeropuerto (`proceso/directo.py`).

**Fuente.** Las posiciones en tiempo real de adsb.lol (`/v2/point/<lat>/<lon>/<radio>`, sin
clave, datos con licencia ODbL 1.0, «© adsb.lol contributors»), la misma red de receptores
que el archivo diario con que se calculan las líneas base. Respaldo automático: adsb.fi
(`/api/v3/lat/<lat>/lon/<lon>/dist/<radio>`, mismo formato readsb, una petición por segundo
como mucho, uso no comercial citando adsb.fi con enlace a su web). Las dos limitan el radio
a 250 millas náuticas; aquí se piden círculos de 250 que cubren todos los aeropuertos
vigilados con su zona de 40 km (`circulos`), unos dieciséis, una vez por ciclo, con
compresión gzip.

**Ritmo y errores.** Un ciclo dura 80 s y sus peticiones se reparten en sus primeros 75 s,
con 5 s entre una y otra como mínimo (12 por minuto: medido el 3 de octubre de 2026,
adsb.lol responde 429 hacia la décima petición seguida a 3 s, y a 4 o 5 s casi nunca); una
respuesta 429 alarga esa pausa un 25 % (hasta 6 s) y respeta Retry-After, y cada ciclo sin 429 la
vuelve a acercar a la de partida. Un fallo se repite
con 2 y 4 s de espera, con el tope diario de reintentos por sitio que comparten todas las
unidades (`recogida/reintentos.py`). Si en un ciclo falla la mitad o más de los círculos de la
fuente principal, ese ciclo se pide al respaldo (si fallan menos, solo esos círculos); tras
tres ciclos seguidos así, el servicio sigue con el respaldo y vuelve a probar la principal
cada 10 minutos con una sola petición. Un aeropuerto sin datos de ninguna de las dos durante
más de 5 minutos tiene un hueco de la fuente, y un hueco de la fuente nunca abre un aviso.

**Cada ciclo** (80 s): pide las posiciones, reconstruye los movimientos, evalúa los
aeropuertos vigilados, aplica las confirmaciones que deja la recogida horaria
(`confirmaciones.json`), publica `directo.json` en el almacén público y guarda su estado
(`estado.json`) y el registro para `estado.json` de la web (`/home/eodi/.eodi/directo.json`).
Un aviso nuevo lanza la búsqueda dirigida de noticias (`recogida/busqueda_dirigida.py
directo`), con su propio cerrojo. Cada día, al aparecer un día nuevo procesado del archivo,
recalcula los aeropuertos vigilados y sus líneas base, y publica el mapa diario de
interferencia GPS (`recogida/gnss_publico.py`).

Lo lanza `servidor/directo.sh` (unidad `eodi-directo`, siempre en marcha, con su propio
cerrojo `directo.lock`), nunca la recogida horaria.

Uso: python -m recogida.directo servir [--datos DIR] [--trafico DIR] [--sin-subir]
     python -m recogida.directo circulos
"""

import argparse
import gzip
import json
import logging
import math
import os
import pickle
import signal
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

from proceso import directo, metar, trafico, vuelos
from recogida import almacen_publico, gnss_publico, referencia, reintentos
from recogida import metar as metar_iem
from recogida import trafico as procesado
from recogida.descarga import AGENTE_EODI

registro = logging.getLogger("recogida.directo")

VARIABLE_DATOS = "EODI_DIRECTO_DATOS"
DATOS = Path.home() / "datos" / "directo"
REGISTRO = Path.home() / ".eodi" / "directo.json"
ESTADO = "estado.json"
AVISOS = "avisos.json"
HISTORIAL = "avisos_historial.jsonl"
CONFIRMACIONES = "confirmaciones.json"

FUENTES: dict[str, dict[str, Any]] = {
    "adsb_lol": {
        "url": "https://api.adsb.lol/v2/point/{lat:.3f}/{lon:.3f}/{radio}",
        "sitio": "api.adsb.lol",
        "pausa_s": 5.0,
    },
    "adsb_fi": {
        "url": "https://opendata.adsb.fi/api/v3/lat/{lat:.3f}/lon/{lon:.3f}/dist/{radio}",
        "sitio": "opendata.adsb.fi",
        "pausa_s": 5.0,
    },
}
PRINCIPAL, RESPALDO = "adsb_lol", "adsb_fi"
RADIO_NM = 250
RADIO_MAXIMO_NM = 250
MARGEN_NM = 25.0
KM_POR_NM = 1.852
TIEMPO_LIMITE_S = 20.0
ESPERAS_REINTENTO_S = (2.0, 4.0)
FALLOS_PARA_RESPALDO = 3
# Ritmo: las peticiones de un ciclo se reparten en sus primeros 75 s, con la pausa de cada
# fuente como mínimo. Una respuesta 429 (demasiadas peticiones) alarga la pausa un 25 %, hasta
# 6 s, y respeta Retry-After (hasta 30 s); cada ciclo sin 429 la acerca de nuevo a la de
# partida. adsb.lol da algún 429 suelto según su carga: se repite esa petición con espera.
REPARTO_S = 75.0
PAUSA_MAXIMA_S = 6.0
RETRY_AFTER_MAXIMO_S = 30.0
PRUEBA_PRINCIPAL_S = 600
# Una posición de hace más de un minuto ya no es la de ahora (seen_pos de readsb).
ANTIGUEDAD_MAXIMA_S = 60.0
# Si más de una cuarta parte de los aeropuertos vigilados da señal a la vez, el fallo es de
# la fuente, no de los aeropuertos.
FRACCION_SENALES_FUENTE = 0.25
CACHE_METAR_S = 600
BUSQUEDA_CADA_S = 1800
CACHE_PUBLICO = "public, max-age=30"
CICLO_CORRECTO_AVISO_S = 600
VIVOS = "vivos.pickle"
# Un hueco de la fuente de hasta 5 minutos no corta las trazas (el análisis de movimientos
# admite esos saltos); uno mayor deja fuera la señal que lo toca.
HUECO_TOLERADO_S = 300
# Las trazas guardadas valen al reiniciar si tienen menos de 15 minutos.
MEMORIA_RECUPERABLE_S = 900
GUARDAR_VIVOS_S = 600


# La carpeta de los datos publicados (exportacion/publicar.py: en el servidor, fuera del clon).
PUBLICACION = Path(
    os.environ.get("EODI_PUBLICACION_DIRECTORIO")
    or Path(__file__).resolve().parent.parent / "publicacion"
)


def aeropuertos_con_cierre(directorio: Path = PUBLICACION) -> set[str]:
    """Aeropuertos con un incidente publicado de cierre (interrupción del aeropuerto o cierre
    declarado): se vigilan aunque su cobertura sea media (proceso/directo.vigilables)."""
    resultado: set[str] = set()
    for nombre, clave in (("incidentes.geojson", "features"),
                          ("incidentes_sin_ubicacion.json", "incidentes")):  # fmt: skip
        documento = leer_json(directorio / nombre) or {}
        for elemento in documento.get(clave, []):
            propiedades = elemento.get("properties", elemento)
            oaci = (propiedades.get("objetivo") or {}).get("oaci")
            cierre = (propiedades.get("consecuencias") or {}).get("cierre") or {}
            if oaci and (
                propiedades.get("tipo") == "interrupcion_aeroportuaria"
                or cierre.get("valor") == "si"
            ):
                resultado.add(str(oaci))
    return resultado


def directorio_datos() -> Path:
    return Path(os.environ.get(VARIABLE_DATOS) or DATOS)


# --- Círculos ------------------------------------------------------------------------------


@dataclass(frozen=True)
class Circulo:
    lat: float
    lon: float
    radio_nm: int
    aeropuertos: tuple[str, ...]


def circulos(aeropuertos: Iterable[vuelos.Aeropuerto], radio_nm: int = RADIO_NM) -> list[Circulo]:
    """Círculos que cubren cada aeropuerto con su zona de 40 km (con margen): uno voraz, que
    centra cada círculo en el aeropuerto que deja más aeropuertos cubiertos y lo recentra en
    el punto medio de los que cubre."""
    alcance_km = (radio_nm - MARGEN_NM) * KM_POR_NM
    pendientes = {a.oaci: a for a in aeropuertos}
    resultado = []
    while pendientes:
        mejor: tuple[int, vuelos.Aeropuerto, list[vuelos.Aeropuerto]] | None = None
        for a in pendientes.values():
            dentro = [
                b
                for b in pendientes.values()
                if vuelos.distancia_km(a.lat, a.lon, b.lat, b.lon) <= alcance_km
            ]
            if mejor is None or len(dentro) > mejor[0]:
                mejor = (len(dentro), a, dentro)
        assert mejor is not None
        _, centro, dentro = mejor
        lat = (min(b.lat for b in dentro) + max(b.lat for b in dentro)) / 2
        lon = (min(b.lon for b in dentro) + max(b.lon for b in dentro)) / 2
        if any(vuelos.distancia_km(lat, lon, b.lat, b.lon) > alcance_km for b in dentro):
            lat, lon = centro.lat, centro.lon
        cubiertos = [
            b
            for b in pendientes.values()
            if vuelos.distancia_km(lat, lon, b.lat, b.lon) <= alcance_km
        ]
        resultado.append(
            Circulo(
                round(lat, 3), round(lon, 3), radio_nm, tuple(sorted(b.oaci for b in cubiertos))
            )
        )
        for b in cubiertos:
            del pendientes[b.oaci]
    return resultado


# --- Lectura de una fuente -----------------------------------------------------------------


def posicion(ac: dict[str, Any], ahora: float) -> directo.Posicion | None:
    """Una aeronave del formato readsb (`ac` de la respuesta) como posición; None sin
    posición reciente."""
    icao = str(ac.get("hex", "")).lower()
    if not icao or icao.startswith("~"):
        return None
    lat, lon = ac.get("lat"), ac.get("lon")
    visto = ac.get("seen_pos")
    if not isinstance(lat, int | float) or not isinstance(lon, int | float):
        return None
    if not isinstance(visto, int | float) or visto > ANTIGUEDAD_MAXIMA_S:
        return None
    alt = ac.get("alt_baro")
    suelo = alt == "ground"
    vz = ac.get("baro_rate", ac.get("geom_rate"))
    indicativo = str(ac.get("flight") or "").strip() or None

    def numero(valor: Any) -> float | None:
        return float(valor) if isinstance(valor, int | float) else None

    return directo.Posicion(
        icao=icao,
        t=ahora - float(visto),
        lat=float(lat),
        lon=float(lon),
        alt=None if suelo else numero(alt),
        suelo=suelo,
        gs=numero(ac.get("gs")),
        rumbo=numero(ac.get("track")),
        vz=numero(vz),
        indicativo=indicativo,
        tipo=ac.get("t") or None,
        categoria=ac.get("category") or None,
        marcas=int(ac.get("dbFlags") or 0),
    )


def leer_respuesta(cuerpo: bytes) -> tuple[float, list[dict[str, Any]]]:
    """El instante de la respuesta (s) y sus aeronaves."""
    if cuerpo[:2] == b"\x1f\x8b":
        cuerpo = gzip.decompress(cuerpo)
    datos = json.loads(cuerpo)
    ahora = float(datos.get("now") or time.time())
    if ahora > 1e11:  # en milisegundos
        ahora /= 1000
    lista = datos.get("ac", datos.get("aircraft")) or []
    return ahora, [a for a in lista if isinstance(a, dict)]


Pedir = Callable[[str], bytes]


def pedir_urllib(url: str) -> bytes:
    peticion = urllib.request.Request(
        url, headers={"User-Agent": AGENTE_EODI, "Accept-Encoding": "gzip"}
    )
    with urllib.request.urlopen(peticion, timeout=TIEMPO_LIMITE_S) as respuesta:
        cuerpo: bytes = respuesta.read()
        return cuerpo


@dataclass
class Lectura:
    fuente: str
    posiciones: list[directo.Posicion] = field(default_factory=list)
    fallidos: list[Circulo] = field(default_factory=list)
    peticiones: int = 0
    bytes: int = 0
    # Círculos que dio el respaldo porque la principal no los dio en este ciclo.
    respaldados: int = 0


class Lector:
    """Pide los círculos a la fuente principal o al respaldo, con espera creciente y el tope
    diario de reintentos."""

    def __init__(
        self,
        pedir: Pedir = pedir_urllib,
        dormir: Callable[[float], None] = time.sleep,
        tope: reintentos.TopeDiario | None = None,
        detenido: Callable[[], bool] = lambda: False,
        reloj: Callable[[], float] = time.monotonic,
    ) -> None:
        self.reloj = reloj
        self.pedir = pedir
        self.dormir = dormir
        self.tope = tope
        self.detenido = detenido
        self.fallos_seguidos = 0
        self.en_respaldo = False
        self.ultima_prueba = 0.0
        self.pausas = {f: float(d["pausa_s"]) for f, d in FUENTES.items()}
        self._limitado = False

    def _uno(self, fuente: str, c: Circulo, lectura: Lectura) -> bool:
        datos = FUENTES[fuente]
        url = datos["url"].format(lat=c.lat, lon=c.lon, radio=min(c.radio_nm, RADIO_MAXIMO_NM))
        for intento in range(len(ESPERAS_REINTENTO_S) + 1):
            if intento:
                if self.tope is not None and not self.tope.permite(datos["sitio"]):
                    return False
                if self.tope is not None:
                    self.tope.anotar(datos["sitio"])
                self.dormir(ESPERAS_REINTENTO_S[intento - 1])
            lectura.peticiones += 1
            try:
                cuerpo = self.pedir(url)
                ahora, lista = leer_respuesta(cuerpo)
            except urllib.error.HTTPError as error:
                registro.info("%s %s: HTTP %s", fuente, c.aeropuertos[:3], error.code)
                if error.code in (400, 401, 403, 404):
                    return False
                if error.code == 429:
                    self._limitado = True
                    self.pausas[fuente] = min(PAUSA_MAXIMA_S, self.pausas[fuente] * 1.25)
                    try:
                        espera = float(error.headers.get("Retry-After") or 0)
                    except (TypeError, ValueError):
                        espera = 0.0
                    if espera > 0:
                        self.dormir(min(espera, RETRY_AFTER_MAXIMO_S))
                continue
            except (OSError, ValueError) as error:
                registro.info("%s %s: %s", fuente, c.aeropuertos[:3], type(error).__name__)
                continue
            lectura.bytes += len(cuerpo)
            lectura.posiciones += [p for a in lista if (p := posicion(a, ahora)) is not None]
            return True
        return False

    def _ronda(self, fuente: str, lista: list[Circulo], reparto: float = REPARTO_S) -> Lectura:
        lectura = Lectura(fuente)
        self._limitado = False
        inicio = self.reloj()
        for n, c in enumerate(lista):
            # Cada petición sale a su hora dentro del ciclo, cuente lo que haya tardado la
            # anterior: la pausa se mide entre salidas, no entre una respuesta y la salida
            # siguiente.
            espera = inicio + n * max(self.pausas[fuente], reparto / len(lista)) - self.reloj()
            if n and espera > 0:
                self.dormir(espera)
            if self.detenido():
                lectura.fallidos += lista[n:]
                break
            if not self._uno(fuente, c, lectura):
                lectura.fallidos.append(c)
        if not self._limitado:
            base = float(FUENTES[fuente]["pausa_s"])
            self.pausas[fuente] = max(base, self.pausas[fuente] * 0.9)
        return lectura

    def leer(self, lista: list[Circulo], ahora: float) -> Lectura:
        if self.en_respaldo and ahora - self.ultima_prueba >= PRUEBA_PRINCIPAL_S and lista:
            self.ultima_prueba = ahora
            prueba = Lectura(PRINCIPAL)
            if self._uno(PRINCIPAL, lista[0], prueba):
                registro.info("la fuente principal vuelve a responder")
                self.en_respaldo, self.fallos_seguidos = False, 0
        if not self.en_respaldo:
            lectura = self._ronda(PRINCIPAL, lista)
            if len(lectura.fallidos) * 2 < max(1, len(lista)):
                self.fallos_seguidos = 0
                if lectura.fallidos and not self.detenido():
                    # Los círculos que la principal no dio en este ciclo, al respaldo.
                    complemento = self._ronda(RESPALDO, lectura.fallidos, reparto=0.0)
                    lectura.posiciones += complemento.posiciones
                    lectura.peticiones += complemento.peticiones
                    lectura.bytes += complemento.bytes
                    lectura.respaldados = len(lectura.fallidos) - len(complemento.fallidos)
                    lectura.fallidos = complemento.fallidos
                return lectura
            self.fallos_seguidos += 1
            if self.fallos_seguidos >= FALLOS_PARA_RESPALDO:
                registro.warning("la fuente principal falla: se sigue con el respaldo")
                self.en_respaldo, self.ultima_prueba = True, ahora
        return self._ronda(RESPALDO, lista)


# --- METAR del momento ------------------------------------------------------------------------


class MetaresVivos:
    """METAR del día de un aeropuerto pedidos al IEM cuando hacen falta, con caché de 10
    minutos (solo se piden para un aeropuerto con señal)."""

    def __init__(self, pedir: Pedir = pedir_urllib) -> None:
        self.pedir = pedir
        self._cache: dict[tuple[str, date], tuple[float, list[metar.Metar]]] = {}

    def _dia(self, oaci: str, dia: date) -> list[metar.Metar]:
        clave = (oaci, dia)
        guardado = self._cache.get(clave)
        if guardado is not None and time.time() - guardado[0] < CACHE_METAR_S:
            return guardado[1]
        lista: list[metar.Metar] = []
        try:
            texto = self.pedir(metar_iem.url([oaci], dia)).decode("utf-8", errors="replace")
            for linea in texto.splitlines()[1:]:
                partes = linea.split(",", 2)
                if len(partes) == 3:
                    hora = datetime.strptime(partes[1], "%Y-%m-%d %H:%M").replace(tzinfo=UTC)
                    lista.append(metar.leer(hora, partes[2]))
        except (OSError, ValueError) as error:
            registro.info("metar de %s no se lee: %s", oaci, type(error).__name__)
        self._cache[clave] = (time.time(), lista)
        return lista

    def __call__(self, oaci: str, desde: float, hasta: float) -> list[metar.Metar]:
        dias = {datetime.fromtimestamp(t, UTC).date() for t in (desde, hasta)}
        return [
            m
            for d in sorted(dias)
            for m in self._dia(oaci, d)
            if desde <= m.hora.timestamp() <= hasta
        ]


# --- Estado, publicación y servicio -------------------------------------------------------------


def escribir_json(ruta: Path, contenido: Any) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    temporal = ruta.with_suffix(ruta.suffix + ".tmp")
    temporal.write_text(
        json.dumps(contenido, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n"
    )
    temporal.replace(ruta)


def leer_json(ruta: Path) -> Any:
    try:
        return json.loads(ruta.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def documento_publico(
    detector: directo.Detector,
    aeropuertos: dict[str, vuelos.Aeropuerto],
    ahora: float,
    fuente: str,
    vigilados: int,
) -> dict[str, Any]:
    """directo.json: lo que lee la web. Solo los campos de la lista cerrada
    (`exportacion/campos.py`, CAMPOS_PUBLICOS_DIRECTO)."""
    from exportacion.campos import CAMPOS_PUBLICOS_AVISO_DIRECTO
    from exportacion.proyeccion import proyectar

    avisos = []
    for a in sorted(detector.avisos, key=lambda x: x.detectado, reverse=True):
        aeropuerto = aeropuertos.get(a.oaci)
        documento = {
            **a.documento(),
            "nombre": aeropuerto.nombre if aeropuerto else a.oaci,
            "pais": aeropuerto.pais if aeropuerto else None,
            "lat": round(aeropuerto.lat, 4) if aeropuerto else None,
            "lon": round(aeropuerto.lon, 4) if aeropuerto else None,
        }
        avisos.append(proyectar(documento, CAMPOS_PUBLICOS_AVISO_DIRECTO))
    return {
        "version": 1,
        "generado": directo.instante(ahora),
        "fuente": fuente,
        "ciclo_s": directo.PASO_S,
        "aeropuertos_vigilados": vigilados,
        "avisos": avisos,
    }


class Servicio:
    def __init__(
        self,
        datos: Path,
        datos_trafico: Path,
        subir: Callable[[str, bytes, str, str | None, str | None], bool] | None,
        lector: Lector | None = None,
        metares: directo.Metares | None = None,
        lanzar_busqueda: Callable[[], None] | None = None,
        registro_ruta: Path = REGISTRO,
    ) -> None:
        self.datos = datos
        self.datos_trafico = datos_trafico
        self.subir = subir
        self.lector = lector or Lector(tope=reintentos.TopeDiario.desde_entorno())
        self.lanzar_busqueda = lanzar_busqueda
        self.registro_ruta = registro_ruta
        self.aeropuertos = vuelos.cargar_aeropuertos()
        self.por_oaci = {a.oaci: a for a in self.aeropuertos}
        self.dias = procesado.Dias(datos_trafico)
        self.referencias = referencia.Referencias(datos_trafico)
        self._niveles: dict[tuple[str, date], str | None] = {}
        self.bases = directo.Bases(self._base)
        self.detector = directo.Detector(
            self.bases,
            metares if metares is not None else MetaresVivos(),
            hueco_fuente=self._hueco,
        )
        self.vivos = directo.Vivos(self.aeropuertos)
        self.recuperado = self._cargar_vivos()
        self.vigilados: list[str] = []
        self.circulos: list[Circulo] = []
        self.dia_vigilados: date | None = None
        # Intervalos sin datos de cada aeropuerto (su círculo falló, o el servicio estuvo
        # parado): (desde, hasta).
        self.huecos: dict[str, list[tuple[float, float]]] = {}
        self.ultimo_ciclo: dict[str, float] = {}
        self.ultimo_correcto: float | None = None
        self.ultima_busqueda = 0.0
        self._cargar_estado()

    # -- Archivo y vigilados --

    def _nivel(self, oaci: str, dia: date) -> str | None:
        clave = (oaci, dia)
        if clave not in self._niveles:
            c = trafico.cobertura(oaci, dia, self.dias, self.referencias)
            self._niveles[clave] = None if c is None else c.nivel
        return self._niveles[clave]

    def _base(self, oaci: str, dia: date) -> directo.BaseDia | None:
        def valido(d: date) -> bool:
            return self._nivel(oaci, d) in (trafico.ALTA, trafico.MEDIA)

        return directo.base_dia(oaci, dia, self.dias, valido)

    def preparar_dia(self, hoy: date) -> None:
        if self.dia_vigilados == hoy:
            return
        self.bases.olvidar_antes(hoy - timedelta(days=1))
        self._niveles = {k: v for k, v in self._niveles.items() if k[1] >= hoy - timedelta(days=35)}
        regulares = [a.oaci for a in self.aeropuertos if a.regular]
        self.vigilados = directo.vigilables(
            hoy, regulares, self._nivel, self.bases, aeropuertos_con_cierre()
        )
        self.circulos = circulos([self.por_oaci[o] for o in self.vigilados])
        self.dia_vigilados = hoy
        # Las líneas base de hoy y de mañana (una ventana que pasa de medianoche) se calculan
        # ya; después, los días del archivo leídos (unos 40 MB cada uno) no hacen falta.
        for oaci in self.vigilados:
            self.bases(oaci, hoy)
            self.bases(oaci, hoy + timedelta(days=1))
        self.dias = procesado.Dias(self.datos_trafico)
        registro.info(
            "%s: %d aeropuertos vigilados en %d círculos",
            hoy,
            len(self.vigilados),
            len(self.circulos),
        )

    # -- Estado --

    def _cargar_estado(self) -> None:
        estado = leer_json(self.datos / ESTADO) or {}
        self.detector.avisos = [directo.Aviso.de_documento(a) for a in estado.get("avisos", [])]
        valor = estado.get("ultimo_correcto")
        self.ultimo_correcto = directo.segundos(valor) if valor else None

    def _guardar_estado(self, ahora: float) -> None:
        escribir_json(
            self.datos / ESTADO,
            {
                "version": 1,
                "ahora": directo.instante(ahora),
                "ultimo_correcto": (
                    directo.instante(self.ultimo_correcto) if self.ultimo_correcto else None
                ),
                "fuente": RESPALDO if self.lector.en_respaldo else PRINCIPAL,
                "vigilados": self.vigilados,
                "senales": {o: directo.instante(t) for o, t in self.detector.senales.items()},
                "avisos": [a.documento() for a in self.detector.avisos],
            },
        )
        escribir_json(
            self.datos / AVISOS,
            {"avisos": [{**a.documento(), "directo": True} for a in self.detector.avisos]},
        )
        if self.ultimo_correcto is not None:
            escribir_json(
                self.registro_ruta,
                {
                    "ultimo_ciclo_correcto": directo.instante(self.ultimo_correcto),
                    "fuente": RESPALDO if self.lector.en_respaldo else PRINCIPAL,
                    "vigilados": len(self.vigilados),
                    "avisos_activos": sum(
                        1 for a in self.detector.avisos if a.estado != directo.REANUDADA
                    ),
                },
            )

    def _historial(self, aviso: directo.Aviso, ahora: float) -> None:
        with (self.datos / HISTORIAL).open("a", encoding="utf-8", newline="\n") as salida:
            salida.write(
                json.dumps({"momento": directo.instante(ahora), **aviso.documento()}) + "\n"
            )

    def _confirmaciones(self) -> None:
        contenido = leer_json(self.datos / CONFIRMACIONES) or {}
        for aviso in self.detector.avisos:
            dato = contenido.get("avisos", {}).get(aviso.id)
            if not dato or aviso.confirmacion == dato.get("confirmacion"):
                continue
            aviso.confirmacion = dato.get("confirmacion")
            if dato.get("primera_noticia"):
                aviso.primera_noticia = directo.segundos(dato["primera_noticia"])
            if aviso.estado == directo.POSIBLE and aviso.confirmacion:
                aviso.estado = directo.CONFIRMADO

    # -- Ciclo --

    def _hueco(self, oaci: str, desde: float, hasta: float) -> bool:
        return any(h0 < hasta and h1 > desde for h0, h1 in self.huecos.get(oaci, []))

    def _anotar_datos(self, oaci: str, ahora: float) -> None:
        """Un ciclo con datos del aeropuerto: si el anterior fue hace más de HUECO_TOLERADO_S,
        el tiempo entre los dos es un hueco de la fuente."""
        anterior = self.ultimo_ciclo.get(oaci, self.inicio_datos)
        if ahora - anterior > HUECO_TOLERADO_S:
            self.huecos.setdefault(oaci, []).append((anterior, ahora))
        self.ultimo_ciclo[oaci] = ahora

    # -- Trazas en disco (para no perderlas al reiniciar el servicio) --

    def _cargar_vivos(self) -> bool:
        ruta = self.datos / VIVOS
        self.inicio_datos = 0.0
        try:
            with ruta.open("rb") as entrada:
                guardado = pickle.load(entrada)
        except (OSError, ValueError, EOFError, pickle.UnpicklingError, AttributeError):
            return False
        if time.time() - float(guardado.get("ahora", 0)) > MEMORIA_RECUPERABLE_S:
            return False
        for nombre in ("aeronaves", "asentados", "filas", "esperas", "_por_aeropuerto"):
            setattr(self.vivos, nombre, guardado[nombre])
        self.ultimo_ciclo = guardado.get("ultimo_ciclo", {})
        self.huecos = guardado.get("huecos", {})
        self.inicio_datos = float(guardado.get("inicio_datos", 0.0))
        return True

    def guardar_vivos(self, ahora: float) -> None:
        ruta = self.datos / VIVOS
        ruta.parent.mkdir(parents=True, exist_ok=True)
        temporal = ruta.with_suffix(".tmp")
        with temporal.open("wb") as salida:
            pickle.dump(
                {
                    "ahora": ahora,
                    "aeronaves": self.vivos.aeronaves,
                    "asentados": self.vivos.asentados,
                    "filas": self.vivos.filas,
                    "esperas": self.vivos.esperas,
                    "_por_aeropuerto": self.vivos._por_aeropuerto,
                    "ultimo_ciclo": self.ultimo_ciclo,
                    "huecos": self.huecos,
                    "inicio_datos": self.inicio_datos,
                },
                salida,
            )
        temporal.replace(ruta)

    def ciclo(self, ahora: float) -> dict[str, Any]:
        self.preparar_dia(datetime.fromtimestamp(ahora, UTC).date())
        if not self.inicio_datos:
            # Sin trazas guardadas: lo anterior a este momento es hueco para todos.
            self.inicio_datos = ahora
            for oaci in self.vigilados:
                self.huecos.setdefault(oaci, []).append((0.0, ahora))
        lectura = self.lector.leer(self.circulos, ahora)
        fallidos = {o for c in lectura.fallidos for o in c.aeropuertos}
        for c in self.circulos:
            for oaci in c.aeropuertos:
                if oaci not in fallidos:
                    self._anotar_datos(oaci, ahora)
        limite = ahora - directo.MEMORIA_S - directo.HUECO_MAXIMO_S
        for oaci in list(self.huecos):
            self.huecos[oaci] = [h for h in self.huecos[oaci] if h[1] >= limite]
        self.vivos.anadir(lectura.posiciones)
        self.vivos.actualizar(ahora)
        correcto = len(lectura.fallidos) * 2 < max(1, len(self.circulos))
        evaluables = list(self.vigilados)
        activos_antes = {a.id for a in self.detector.avisos}
        nuevos = self.detector.evaluar(evaluables, ahora, self.vivos, lectura.fuente)
        if len(self.detector.senales) > FRACCION_SENALES_FUENTE * max(1, len(evaluables)):
            registro.warning(
                "señal en %d aeropuertos a la vez: fallo de la fuente", len(self.detector.senales)
            )
            self.detector.avisos = [a for a in self.detector.avisos if a not in nuevos]
            self.detector.senales.clear()
            nuevos = []
        # Los avisos abiertos se siguen aunque el aeropuerto no sea evaluable en este ciclo.
        self._confirmaciones()
        for aviso in nuevos:
            registro.info("aviso nuevo: %s", json.dumps(aviso.documento(), ensure_ascii=False))
            self._historial(aviso, ahora)
        if nuevos or (
            any(a.estado != directo.REANUDADA for a in self.detector.avisos)
            and ahora - self.ultima_busqueda >= BUSQUEDA_CADA_S
        ):
            self.ultima_busqueda = ahora
            if self.lanzar_busqueda is not None:
                self.lanzar_busqueda()
        for aviso in self.detector.avisos:
            recien = (
                aviso.id in activos_antes
                and aviso.estado == directo.REANUDADA
                and aviso.reanudado is not None
                and abs(aviso.reanudado - ahora) < 2 * directo.RETRASO_S + directo.PASO_S
            )
            if recien:
                self._historial(aviso, ahora)
        if correcto:
            self.ultimo_correcto = ahora
        publico = documento_publico(
            self.detector, self.por_oaci, ahora, lectura.fuente, len(self.vigilados)
        )
        subido = None
        if self.subir is not None:
            cuerpo = json.dumps(publico, ensure_ascii=False, separators=(",", ":")).encode()
            subido = self.subir("directo.json", cuerpo, "application/json", CACHE_PUBLICO, None)
        self._guardar_estado(ahora)
        return {
            "fuente": lectura.fuente,
            "peticiones": lectura.peticiones,
            "kb": round(lectura.bytes / 1024),
            "posiciones": len(lectura.posiciones),
            "fallidos": len(lectura.fallidos),
            "respaldados": lectura.respaldados,
            "evaluables": len(evaluables),
            "senales": len(self.detector.senales),
            "avisos": len(self.detector.avisos),
            "subido": subido,
        }


def subidor(
    almacen: almacen_publico.Almacen,
) -> Callable[[str, bytes, str, str | None, str | None], bool] | None:
    clave_id = os.environ.get(almacen_publico.VARIABLE_ID, "")
    secreto = os.environ.get(almacen_publico.VARIABLE_SECRETO, "")
    if not clave_id or not secreto:
        return None

    def subir(
        objeto: str, cuerpo: bytes, tipo: str, cache: str | None, codificacion: str | None
    ) -> bool:
        correcto, motivo = almacen_publico.subir(
            almacen, objeto, cuerpo, clave_id, secreto, tipo, cache, codificacion=codificacion
        )
        if not correcto:
            registro.warning("%s no se sube: %s", objeto, motivo)
        return correcto

    return subir


def lanzador_busqueda(clon: Path, cerrojo: Path) -> Callable[[], None]:
    """Lanza la búsqueda dirigida de los avisos en directo en segundo plano, con el cerrojo
    de la búsqueda (si ya hay una en marcha, no se lanza otra)."""

    def lanzar() -> None:
        orden = [
            "flock", "--nonblock", str(cerrojo), sys.executable, "-m",
            "recogida.busqueda_dirigida", "directo", "--tope-min", "15",
        ]  # fmt: skip
        try:
            subprocess.Popen(
                orden, cwd=clon, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                start_new_session=True,
            )  # fmt: skip
        except OSError as error:
            registro.warning("la búsqueda dirigida no se lanza: %s", error)

    return lanzar


def servir(args: argparse.Namespace) -> int:
    datos = args.datos or directorio_datos()
    trafico_datos = args.trafico or procesado.directorio_datos()
    almacen = almacen_publico.cargar()
    subir = None if args.sin_subir else subidor(almacen)
    if subir is None and not args.sin_subir:
        registro.warning("sin credenciales del almacén: directo.json no se publica")
    cerrojo_busqueda = Path(
        os.environ.get("EODI_CERROJO_BUSQUEDA", Path.home() / ".eodi" / "busqueda.lock")
    )
    parada = threading.Event()

    def dormir(segundos: float) -> None:
        parada.wait(segundos)

    lector = Lector(
        tope=reintentos.TopeDiario.desde_entorno(), dormir=dormir, detenido=parada.is_set
    )
    servicio = Servicio(
        datos,
        trafico_datos,
        subir,
        lector=lector,
        lanzar_busqueda=lanzador_busqueda(Path.cwd(), cerrojo_busqueda),
    )
    gnss = gnss_publico.Publicador(trafico_datos, datos, subir)
    version = version_clon(Path.cwd())
    ultimo_guardado = time.time()

    def al_parar(*_: Any) -> None:
        parada.set()

    signal.signal(signal.SIGTERM, al_parar)
    signal.signal(signal.SIGINT, al_parar)
    while not parada.is_set():
        comienzo = time.time()
        ahora = math.floor(comienzo / directo.PASO_S) * directo.PASO_S
        try:
            resumen = servicio.ciclo(comienzo)
            registro.info("ciclo %s: %s", directo.instante(ahora), json.dumps(resumen))
        except Exception:
            registro.exception("el ciclo ha fallado; sigue el siguiente")
        try:
            gnss.publicar_pendientes(tope=2)
        except Exception:
            registro.exception("el mapa de interferencia GPS no se publica en este ciclo")
        if comienzo - ultimo_guardado >= GUARDAR_VIVOS_S:
            servicio.guardar_vivos(comienzo)
            ultimo_guardado = comienzo
            nueva = version_clon(Path.cwd())
            if nueva and nueva != version:
                # Código nuevo en el clon (lo pone al día la recogida horaria): se guarda y se
                # sale; systemd vuelve a lanzar el servicio con el código nuevo y las trazas.
                registro.info("código nuevo en el clon: el servicio se reinicia")
                break
        parada.wait(max(0.0, directo.PASO_S - (time.time() - comienzo)))
    servicio.guardar_vivos(time.time())
    registro.info("servicio parado")
    return 0


# Lo que el servicio ejecuta: un cambio aquí lo reinicia; los commits de datos publicados
# (`publicacion/`, cada hora) no.
CODIGO = ("almacen", "configuracion", "esquema", "exportacion", "modelo", "proceso", "recogida")


def version_clon(clon: Path) -> str:
    """La huella del código del clon (los árboles de git de sus carpetas de código), vacía si no
    se puede leer."""
    try:
        salida = subprocess.run(
            ["git", "-C", str(clon), "rev-parse", *(f"HEAD:{c}" for c in CODIGO)],
            capture_output=True, text=True, timeout=10, check=False,
        )  # fmt: skip
    except (OSError, subprocess.SubprocessError):
        return ""
    return salida.stdout.strip() if salida.returncode == 0 else ""


def principal(argumentos: list[str] | None = None) -> int:
    opciones = argparse.ArgumentParser(description=__doc__)
    sub = opciones.add_subparsers(dest="orden", required=True)
    s = sub.add_parser("servir")
    s.add_argument("--datos", type=Path)
    s.add_argument("--trafico", type=Path)
    s.add_argument("--sin-subir", action="store_true")
    c = sub.add_parser("circulos")
    c.add_argument("--trafico", type=Path)
    args = opciones.parse_args(argumentos)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    if args.orden == "circulos":
        trafico_datos = args.trafico or procesado.directorio_datos()
        servicio = Servicio(Path("/tmp/directo-circulos"), trafico_datos, None)
        hoy = datetime.now(UTC).date()
        servicio.preparar_dia(hoy)
        for circulo in servicio.circulos:
            print(json.dumps(circulo.__dict__, ensure_ascii=False))
        return 0
    return servir(args)


if __name__ == "__main__":
    sys.exit(principal())
