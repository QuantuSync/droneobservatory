"""Anomalías térmicas de NASA FIRMS (Fire Information for Resource Management System).

Cada foco es un píxel que un satélite vio más caliente que su entorno al pasar: VIIRS en
Suomi NPP, NOAA-20 y NOAA-21 (píxel de 375 m) y MODIS en Terra y Aqua (1 km). Se descargan
con la API de área (https://firms.modaps.eosdis.nasa.gov/api/area/) para un rectángulo que
cubre Ucrania, Moldavia, Crimea y la Rusia europea hasta los Urales, y se guardan como CSV
diarios comprimidos en el disco del servidor (`EODI_FIRMS_DATOS`, por defecto
`~/datos/firms`), fuera del repositorio y fuera de la base: la base se sube cifrada cada hora
y no debe crecer con los focos agrícolas. Con ellos se cruzan los impactos
(`proceso/focos_termicos.py`).

- **Recogida horaria.** Dentro de la ejecución horaria, solo si han pasado 3 horas o más
  desde la última descarga correcta: los dos últimos días de los productos NRT. Un fallo
  no para la recogida: queda en el registro y la siguiente ejecución vuelve a intentarlo.
- **Histórico.** `python -m recogida.firms historico`: una sola vez, desde octubre de 2022,
  con los productos SP (procesado estándar) y NRT donde SP no llega, en llamadas de 5 días,
  con pausas para no pasar de 5000 transacciones cada 10 minutos. Reanudable: lo ya
  descargado no se vuelve a pedir.

La clave (`EODI_FIRMS_MAP_KEY`) va dentro de la URL: ninguna URL ni mensaje de error sale
al registro sin cambiarla antes por «***» (`redactar`).

Uso: python -m recogida.firms historico [--tope-s N] [--datos DIR]
     python -m recogida.firms resumen [--datos DIR]
"""

import argparse
import csv
import gzip
import io
import json
import logging
import os
import sys
import time
from collections import OrderedDict
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

from proceso.focos_termicos import Caja, Foco
from recogida.descarga import AGENTE_EODI, Descargador, DescargaFallida
from recogida.plazo import Plazo, TiempoAgotado

registro = logging.getLogger("recogida.firms")

FUENTE_ID = "firms"
API = "https://firms.modaps.eosdis.nasa.gov/api"
VARIABLE_CLAVE = "EODI_FIRMS_MAP_KEY"
VARIABLE_DATOS = "EODI_FIRMS_DATOS"
# Solo en local y fuera de cualquier repositorio.
RUTA_CLAVE_LOCAL = Path.home() / ".eodi" / "firms_map_key.txt"
DATOS = Path.home() / "datos" / "firms"
CONTROL = "control.json"

# Oeste, sur, este, norte. De 22° E (frontera occidental de Ucrania) a 60° E (los Urales,
# con Perm, Ufá y Oremburgo dentro) y de 43° N (Crimea, Tuapse, Novorossiysk y la costa
# búlgara de Varna) a 61° N (Primorsk, Ust-Luga y Kirishi). Cubre también Moldavia, el este
# de Rumanía y de Polonia, los países bálticos y el sur de Finlandia, donde han caído drones
# de la guerra. tests/test_firms.py comprueba que todos los objetivos citados caen dentro.
CAJA = Caja(oeste=22.0, sur=43.0, este=60.0, norte=61.0)

# Productos: VIIRS en tres satélites y MODIS (Terra y Aqua en el mismo producto). Para cada
# uno, NRT (casi tiempo real, los últimos meses) y SP (procesado estándar, el histórico,
# con unos meses de retraso). NOAA-21 no tiene SP todavía (comprobado el 1 de octubre de
# 2026 con /api/data_availability/: SP hasta el 30 de junio de 2026, NRT desde el 1 de julio;
# NOAA-21 NRT desde el 17 de enero de 2024).
PRODUCTOS = ("VIIRS_SNPP", "VIIRS_NOAA20", "VIIRS_NOAA21", "MODIS")
NRT, SP = "NRT", "SP"
FUENTES_NRT = tuple(f"{p}_{NRT}" for p in PRODUCTOS)
SATELITE = {"VIIRS_SNPP": "Suomi NPP", "VIIRS_NOAA20": "NOAA-20", "VIIRS_NOAA21": "NOAA-21"}
SATELITE_MODIS = {"T": "Terra", "TERRA": "Terra", "A": "Aqua", "AQUA": "Aqua"}

# Cada 3 horas pasa al menos un satélite por la zona y FIRMS publica el NRT unas 3 horas
# después del paso: descargar más a menudo no trae nada nuevo y gasta transacciones.
INTERVALO = timedelta(hours=3)
# Los dos últimos días (ayer y hoy, UTC): lo que FIRMS aún completa con pasos tardíos.
DIAS_RECIENTES = 2
# La API admite de 1 a 5 días por llamada.
DIAS_POR_LLAMADA = 5
# Desde el otoño de 2022, cuando empiezan los ataques masivos con Shahed contra Ucrania.
INICIO_HISTORICO = date(2022, 10, 1)
# Tope de la recogida horaria: cuatro llamadas de un segundo o dos. Con un reintento corto
# y 30 s por petición, un FIRMS caído cuesta como mucho un par de minutos.
TOPE_S = 150.0
REINTENTOS = 1
ESPERA_REINTENTO_S = 5.0
# 5000 transacciones cada 10 minutos por clave; una llamada grande puede contar varias. El
# histórico hace una llamada cada 2 s (unas 300 cada 10 minutos) y cada 50 mira el
# contador: por encima de 4000, espera a que se vacíe.
PAUSA_HISTORICO_S = 2.0
CONSULTA_CONTADOR = 50
LIMITE_TRANSACCIONES = 4000
ESPERA_LIMITE_S = 600.0
CABECERA_CSV = b"latitude,longitude,"
# Días leídos que se guardan en memoria durante el cruce: la base y la ventana de un impacto
# son 33 días; los impactos se evalúan por fecha, así que los vecinos aprovechan los mismos.
DIAS_EN_MEMORIA = 40
# Margen alrededor de cada impacto al leer: 0,2° de latitud son 22 km y el doble de
# longitud, más de 15 km hasta los 61° N; el radio de búsqueda es de 10 km como mucho.
MARGEN_GRADOS = 0.2


class FirmsNoDisponible(RuntimeError):
    """FIRMS no se pudo leer: sin clave, sin red, respuesta inesperada o tiempo agotado."""


def redactar(texto: str, clave: str | None) -> str:
    """El texto sin la clave: «***» en su lugar."""
    return texto.replace(clave, "***") if clave else texto


def clave_desde_entorno() -> str | None:
    clave = os.environ.get(VARIABLE_CLAVE, "").strip()
    return clave or None


def cargar_clave_local(ruta: Path = RUTA_CLAVE_LOCAL) -> None:
    """Para ejecuciones en local: lleva la clave del fichero a la variable si falta."""
    if not os.environ.get(VARIABLE_CLAVE) and ruta.exists():
        os.environ[VARIABLE_CLAVE] = ruta.read_text(encoding="utf-8").strip()


def directorio_datos() -> Path:
    return Path(os.environ.get(VARIABLE_DATOS) or DATOS)


def descargador(plazo: Plazo | None = None, reintentos: int = REINTENTOS) -> Descargador:
    return Descargador(
        agente=AGENTE_EODI,
        reintentos=reintentos,
        espera_inicial_s=ESPERA_REINTENTO_S,
        pausa_minima_s=0.0,
        plazo=plazo,
    )


def url_area(clave: str, fuente: str, desde: date, dias: int) -> str:
    caja = f"{CAJA.oeste:g},{CAJA.sur:g},{CAJA.este:g},{CAJA.norte:g}"
    return f"{API}/area/csv/{clave}/{fuente}/{caja}/{dias}/{desde.isoformat()}"


def producto(fuente: str) -> str:
    return fuente.rsplit("_", 1)[0]


# --- Lectura de los CSV ---------------------------------------------------------------


def _instante(fila: dict[str, str]) -> datetime:
    hora = fila["acq_time"].strip().zfill(4)
    dia = date.fromisoformat(fila["acq_date"].strip())
    return datetime(dia.year, dia.month, dia.day, int(hora[:2]), int(hora[2:]), tzinfo=UTC)


def _satelite(fuente: str, fila: dict[str, str]) -> str:
    if producto(fuente) == "MODIS":
        return SATELITE_MODIS.get(fila.get("satellite", "").strip().upper(), "Terra")
    return SATELITE[producto(fuente)]


Cerca = Callable[[float, float], bool]


def leer_csv(contenido: bytes, fuente: str, cerca: Cerca | None = None) -> list[Foco]:
    """Focos de un CSV de FIRMS, VIIRS o MODIS. Las filas que no se entienden se saltan.
    Un día de verano trae decenas de miles de focos agrícolas por producto: se lee con
    csv.reader y los nombres de columna resueltos una sola vez."""
    lector = csv.reader(io.StringIO(contenido.decode("utf-8", errors="replace")))
    cabecera = next(lector, None)
    if cabecera is None:
        return []
    instrumento = "MODIS" if producto(fuente) == "MODIS" else "VIIRS"
    columnas = {nombre.strip(): n for n, nombre in enumerate(cabecera)}
    focos = []
    for valores in lector:
        try:
            fila = {nombre: valores[n] for nombre, n in columnas.items()}
            lat, lon = float(fila["latitude"]), float(fila["longitude"])
            if cerca is not None and not cerca(lat, lon):
                continue
            frp = fila.get("frp", "").strip()
            focos.append(
                Foco(
                    lat=lat,
                    lon=lon,
                    instante=_instante(fila),
                    satelite=_satelite(fuente, fila),
                    instrumento=instrumento,
                    confianza=fila["confidence"].strip().lower(),
                    frp=float(frp) if frp else 0.0,
                    fuente=fuente,
                )
            )
        except (KeyError, IndexError, ValueError, AttributeError):
            continue
    return focos


def _por_dia(contenido: bytes) -> tuple[bytes, dict[date, list[str]]]:
    """Cabecera y filas de cada día (acq_date) de una respuesta de varios días."""
    lineas = contenido.decode("utf-8", errors="replace").splitlines()
    cabecera, filas = lineas[0], lineas[1:]
    columna = cabecera.split(",").index("acq_date")
    dias: dict[date, list[str]] = {}
    for fila in filas:
        if not fila.strip():
            continue
        try:
            dia = date.fromisoformat(fila.split(",")[columna])
        except (IndexError, ValueError):
            continue
        dias.setdefault(dia, []).append(fila)
    return (cabecera + "\n").encode(), dias


# --- Ficheros en disco ----------------------------------------------------------------


@dataclass
class Datos:
    """Los CSV diarios de FIRMS en disco: <directorio>/<fuente>/<año>/<AAAA-MM-DD>.csv.gz."""

    directorio: Path
    # Si se da, solo se leen los focos a menos de MARGEN_GRADOS de alguno de estos puntos
    # (lat, lon): el cruce solo mira alrededor de los impactos.
    zonas: list[tuple[float, float]] | None = None
    _cache: OrderedDict[date, list[Foco] | None] = field(default_factory=OrderedDict)

    def ruta(self, fuente: str, dia: date) -> Path:
        return self.directorio / fuente / f"{dia.year:04d}" / f"{dia.isoformat()}.csv.gz"

    def guardar(self, fuente: str, dia: date, contenido: bytes) -> None:
        ruta = self.ruta(fuente, dia)
        ruta.parent.mkdir(parents=True, exist_ok=True)
        temporal = ruta.with_suffix(".tmp")
        temporal.write_bytes(gzip.compress(contenido, 6, mtime=0))
        temporal.replace(ruta)
        self._cache.pop(dia, None)

    def tiene(self, fuente: str, dia: date) -> bool:
        return self.ruta(fuente, dia).exists()

    def guardar_respuesta(self, fuente: str, desde: date, dias: int, contenido: bytes) -> int:
        """Reparte la respuesta en un fichero por día, también los días sin focos. Devuelve
        el número de focos."""
        cabecera, filas = _por_dia(contenido)
        for n in range(dias):
            dia = desde + timedelta(days=n)
            lineas = filas.get(dia, [])
            self.guardar(fuente, dia, cabecera + "".join(f"{x}\n" for x in lineas).encode())
        return sum(len(v) for v in filas.values())

    def focos(self, dia: date) -> list[Foco] | None:
        """Focos del día de todos los productos, o None si no hay ningún fichero del día. De
        cada producto vale el SP si existe (procesado definitivo) y si no, el NRT."""
        if dia in self._cache:
            self._cache.move_to_end(dia)
            return self._cache[dia]
        hallados: list[Foco] | None = None
        for prod in PRODUCTOS:
            for fuente in (f"{prod}_{SP}", f"{prod}_{NRT}"):
                ruta = self.ruta(fuente, dia)
                if ruta.exists():
                    contenido = gzip.decompress(ruta.read_bytes())
                    hallados = (hallados or []) + leer_csv(contenido, fuente, self._cerca())
                    break
        self._cache[dia] = hallados
        # Los días de un impacto (su base y su ventana) caben de sobra; más días en memoria
        # serían cientos de megas de focos agrícolas.
        while len(self._cache) > DIAS_EN_MEMORIA:
            self._cache.popitem(last=False)
        return hallados

    def _cerca(self) -> Cerca | None:
        if self.zonas is None:
            return None
        zonas = self.zonas

        def cerca(lat: float, lon: float) -> bool:
            return any(
                abs(lat - z_lat) <= MARGEN_GRADOS and abs(lon - z_lon) <= 2 * MARGEN_GRADOS
                for z_lat, z_lon in zonas
            )

        return cerca

    def control(self) -> dict[str, Any]:
        ruta = self.directorio / CONTROL
        if not ruta.exists():
            return {}
        try:
            datos: dict[str, Any] = json.loads(ruta.read_text(encoding="utf-8"))
        except ValueError:
            return {}
        return datos

    def guardar_control(self, control: dict[str, Any]) -> None:
        self.directorio.mkdir(parents=True, exist_ok=True)
        ruta = self.directorio / CONTROL
        temporal = ruta.with_suffix(".tmp")
        temporal.write_text(
            json.dumps(control, ensure_ascii=False, sort_keys=True, indent=1) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        temporal.replace(ruta)


def _leer_instante(texto: str | None) -> datetime | None:
    return datetime.fromisoformat(texto.replace("Z", "+00:00")) if texto else None


def _escribir_instante(momento: datetime) -> str:
    return momento.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


# --- Descarga ---------------------------------------------------------------------------


def _es_csv(contenido: bytes) -> bool:
    return contenido.startswith(CABECERA_CSV)


def descargar(clave: str, fuente: str, desde: date, dias: int, descarga: Descargador) -> bytes:
    """CSV de una llamada de área. Cualquier fallo sale como FirmsNoDisponible, con la clave
    cambiada por «***» y sin encadenar la excepción original (que lleva la URL)."""
    url = url_area(clave, fuente, desde, dias)
    try:
        return descarga.contenido(url, _es_csv)
    except DescargaFallida as error:
        mensaje = redactar(str(error), clave)
    except TiempoAgotado as error:
        mensaje = f"{fuente}: {error}"
    raise FirmsNoDisponible(mensaje)


@dataclass(frozen=True)
class Lectura:
    """Cómo fue FIRMS en una ejecución horaria."""

    descargada: bool
    ultima_correcta: datetime | None
    ultimo_dato: datetime | None
    focos: int = 0


def toca_descargar(datos: Datos, ahora: datetime) -> bool:
    ultima = _leer_instante(datos.control().get("ultima_correcta"))
    return ultima is None or ahora - ultima >= INTERVALO


def recoger(datos: Datos, ahora: datetime, clave: str | None, descarga: Descargador) -> Lectura:
    """Los dos últimos días NRT si han pasado 3 horas desde la última descarga correcta.
    Lanza FirmsNoDisponible si falta la clave o alguna llamada falla; lo descargado antes del
    fallo se queda y la siguiente ejecución vuelve a pedirlo todo."""
    control = datos.control()
    ultima = _leer_instante(control.get("ultima_correcta"))
    ultimo_dato = _leer_instante(control.get("ultimo_dato"))
    if not toca_descargar(datos, ahora):
        return Lectura(False, ultima, ultimo_dato)
    if not clave:
        raise FirmsNoDisponible(f"falta la variable de entorno {VARIABLE_CLAVE}")
    desde = ahora.date() - timedelta(days=DIAS_RECIENTES - 1)
    fallos: list[str] = []
    focos = 0
    for fuente in FUENTES_NRT:
        try:
            contenido = descargar(clave, fuente, desde, DIAS_RECIENTES, descarga)
        except FirmsNoDisponible as error:
            fallos.append(str(error))
            continue
        focos += datos.guardar_respuesta(fuente, desde, DIAS_RECIENTES, contenido)
        for foco in leer_csv(contenido, fuente):
            if ultimo_dato is None or foco.instante > ultimo_dato:
                ultimo_dato = foco.instante
    if fallos:
        raise FirmsNoDisponible("; ".join(fallos))
    control.update(ultima_correcta=_escribir_instante(ahora))
    if ultimo_dato is not None:
        control["ultimo_dato"] = _escribir_instante(ultimo_dato)
    datos.guardar_control(control)
    return Lectura(True, ahora, ultimo_dato, focos)


def lectura_sin_descarga(datos: Datos) -> Lectura:
    control = datos.control()
    return Lectura(
        False,
        _leer_instante(control.get("ultima_correcta")),
        _leer_instante(control.get("ultimo_dato")),
    )


# --- Histórico ------------------------------------------------------------------------


@dataclass(frozen=True)
class Tramo:
    fuente: str
    desde: date
    dias: int


def disponibilidad(clave: str, descarga: Descargador) -> dict[str, tuple[date, date]]:
    """Fechas que cubre cada producto según /api/data_availability/."""
    url = f"{API}/data_availability/csv/{clave}/ALL"
    try:
        texto = descarga.texto(url, lambda t: t.startswith("data_id"))
    except DescargaFallida as error:
        raise FirmsNoDisponible(redactar(str(error), clave)) from None
    cubiertas = {}
    for fila in csv.DictReader(io.StringIO(texto)):
        try:
            cubiertas[fila["data_id"]] = (
                date.fromisoformat(fila["min_date"]),
                date.fromisoformat(fila["max_date"]),
            )
        except (KeyError, ValueError):
            continue
    return cubiertas


def plan(cubiertas: dict[str, tuple[date, date]], inicio: date = INICIO_HISTORICO) -> list[Tramo]:
    """Tramos de 5 días de cada producto desde `inicio`: SP mientras lo haya y NRT desde el
    día siguiente al último SP (o desde el primero si el producto no tiene SP)."""
    tramos = []
    for prod in PRODUCTOS:
        siguiente = inicio
        for tipo in (SP, NRT):
            fuente = f"{prod}_{tipo}"
            if fuente not in cubiertas:
                continue
            primero, ultimo = cubiertas[fuente]
            dia = max(siguiente, primero)
            while dia <= ultimo:
                dias = min(DIAS_POR_LLAMADA, (ultimo - dia).days + 1)
                tramos.append(Tramo(fuente, dia, dias))
                dia += timedelta(days=dias)
            siguiente = max(siguiente, ultimo + timedelta(days=1))
    return tramos


def _dias(tramo: Tramo) -> Iterator[date]:
    for n in range(tramo.dias):
        yield tramo.desde + timedelta(days=n)


def pendientes(datos: Datos, tramos: list[Tramo], hoy: date) -> list[Tramo]:
    """Los tramos con algún día sin fichero. Los de los dos últimos días se dejan a la
    recogida horaria, que los vuelve a pedir cada 3 horas."""
    limite = hoy - timedelta(days=DIAS_RECIENTES - 1)
    return [t for t in tramos if any(not datos.tiene(t.fuente, d) for d in _dias(t) if d < limite)]


def transacciones(clave: str, descarga: Descargador) -> int | None:
    url = f"{API.removesuffix('/api')}/mapserver/mapkey_status/?MAP_KEY={clave}"
    try:
        texto = descarga.texto(url, lambda t: "current_transactions" in t)
        valor = json.loads(texto).get("current_transactions")
    except (DescargaFallida, ValueError):
        return None
    return int(valor) if isinstance(valor, int | float) else None


def historico(
    datos: Datos,
    clave: str,
    descarga: Descargador,
    ahora: datetime,
    tope_s: float | None = None,
    dormir: Callable[[float], None] = time.sleep,
    reloj: Callable[[], float] = time.monotonic,
) -> tuple[int, int]:
    """Descarga los tramos pendientes hasta terminar o hasta agotar `tope_s`. Devuelve
    (tramos descargados, tramos que quedan). Un tramo que falla queda pendiente."""
    tramos = pendientes(datos, plan(disponibilidad(clave, descarga)), ahora.date())
    fin = reloj() + tope_s if tope_s is not None else None
    hechos = 0
    for n, tramo in enumerate(tramos):
        if fin is not None and reloj() >= fin:
            break
        if n and n % CONSULTA_CONTADOR == 0:
            usadas = transacciones(clave, descarga)
            if usadas is not None and usadas > LIMITE_TRANSACCIONES:
                if fin is not None and reloj() + ESPERA_LIMITE_S >= fin:
                    break
                registro.info("%d transacciones en 10 minutos: se espera", usadas)
                dormir(ESPERA_LIMITE_S)
        try:
            contenido = descargar(clave, tramo.fuente, tramo.desde, tramo.dias, descarga)
        except FirmsNoDisponible as error:
            registro.warning("tramo %s %s no descargado: %s", tramo.fuente, tramo.desde, error)
            dormir(PAUSA_HISTORICO_S)
            continue
        datos.guardar_respuesta(tramo.fuente, tramo.desde, tramo.dias, contenido)
        hechos += 1
        if hechos % 25 == 0:
            registro.info("histórico: %d de %d tramos", hechos, len(tramos))
        dormir(PAUSA_HISTORICO_S)
    quedan = len(pendientes(datos, plan(disponibilidad(clave, descarga)), ahora.date()))
    control = datos.control()
    control["historico"] = {
        "actualizado": _escribir_instante(datetime.now(UTC)),
        "tramos_pendientes": quedan,
        "terminado": quedan == 0,
    }
    datos.guardar_control(control)
    return hechos, quedan


def resumen(datos: Datos) -> dict[str, Any]:
    """Ficheros, días y tamaño por fuente: nada de la clave ni del contenido."""
    fuentes: dict[str, Any] = {}
    if datos.directorio.exists():
        for carpeta in sorted(p for p in datos.directorio.iterdir() if p.is_dir()):
            ficheros = sorted(carpeta.glob("*/*.csv.gz"))
            if not ficheros:
                continue
            fuentes[carpeta.name] = {
                "dias": len(ficheros),
                "primero": ficheros[0].name.removesuffix(".csv.gz"),
                "ultimo": ficheros[-1].name.removesuffix(".csv.gz"),
                "megabytes": round(sum(f.stat().st_size for f in ficheros) / 1e6, 1),
            }
    return {"fuentes": fuentes, "control": datos.control()}


def principal(argumentos: list[str] | None = None) -> int:
    opciones = argparse.ArgumentParser(description=__doc__)
    opciones.add_argument("orden", choices=("historico", "resumen"))
    opciones.add_argument("--datos", type=Path, help="carpeta de los CSV (EODI_FIRMS_DATOS)")
    opciones.add_argument("--tope-s", type=float, help="tiempo máximo de esta tanda")
    args = opciones.parse_args(argumentos)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    datos = Datos(args.datos or directorio_datos())
    if args.orden == "resumen":
        print(json.dumps(resumen(datos), ensure_ascii=False, indent=1))
        return 0
    cargar_clave_local()
    clave = clave_desde_entorno()
    if not clave:
        registro.error("falta la variable de entorno %s", VARIABLE_CLAVE)
        return 1
    try:
        plazo = Plazo(args.tope_s) if args.tope_s is not None else None
        descarga = descargador(plazo, reintentos=3)
        hechos, quedan = historico(datos, clave, descarga, datetime.now(UTC), args.tope_s)
    except FirmsNoDisponible as error:
        registro.error("FIRMS no disponible: %s", redactar(str(error), clave))
        return 1
    registro.info("histórico: %d tramos descargados, %d pendientes", hechos, quedan)
    return 0 if quedan == 0 else 3


if __name__ == "__main__":
    sys.exit(principal())
