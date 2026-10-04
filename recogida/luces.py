"""Apagones vistos desde el espacio: medida de la luz nocturna en el servidor (regla en
proceso/luces.py).

**Datos, sin cuenta.** Los gránulos SDR de la banda día-noche de VIIRS de NOAA-20 en el archivo
abierto de NOAA en AWS (`noaa-nesdis-n20-pds`, carpetas `VIIRS-DNB-SDR` con la radiancia
calibrada y su calidad y `VIIRS-DNB-GEO` con la posición de cada píxel y los ángulos del satélite
y de la Luna), en HDF5, comprobado el 3 de octubre de 2026: sin registro ni clave, con datos
desde antes de 2024. Cada gránulo cubre unos 86 s de órbita (unos 560 km por 3000 km); Ucrania y
el oeste de Rusia caen en dos a cuatro gránulos por noche (el paso descendente, hacia la 01:30
hora solar). Se leen por rangos (`recogida/rango.py`) solo las variables que hacen falta, unos
50 MB por gránulo, y no se guarda ningún gránulo: solo la medida de cada ciudad.

**Qué gránulos.** Los de la noche (salida entre las 21:50 y las 00:50 UTC) cuya huella (el
contorno `G-Ring` de sus metadatos, unos 150 kB por gránulo) toca CAJA: se mira uno de cada tres
y después los vecinos de los que la tocan. Las huellas se guardan por noche (`anillos/`) y no se
vuelven a pedir.

**Nubes.** La nubosidad total de Open-Meteo (Historical Forecast API, la misma de
recogida/meteo.py, CC BY 4.0) en cada ciudad a la hora del paso, pedida por meses
(`nubes/<ciudad>/<AAAA-MM>.json`), con un tope de llamadas por ejecución.

**Qué ataques.** Los ataques de la capa de guerra con objetivos de energía: los que tienen un
impacto con lugar de categoría energía, y aquellos durante cuyo periodo (o en las 18 horas
siguientes) el canal oficial de una región publicó un mensaje sobre drones que nombra la red
eléctrica (las mismas palabras de energía de proceso/mensajes_guerra.py), con esa región como
afectada. Se leen de `publicacion/ucrania.json` del clon (lo que publica la recogida) y de los
mensajes guardados por el lector de canales (`datos/guerra/canales`).

**Ciudades con alumbrado reducido de forma permanente.** Con todas las noches medidas, las
ciudades cuyo brillo se queda de forma sostenida por debajo de la referencia mínima de la regla
(proceso/luces.py, `alumbrado_reducido`): con esa luz, un apagón no se ve desde el satélite.
Van a `alumbrado.json` y al almacén público (`luces/alumbrado.json`), que lee la web.

**Salida**, en `<datos>/` (`EODI_LUCES_DATOS`): `noches/<AAAA-MM-DD>.json` (la medida de cada
ciudad esa noche), `resultados.json` (por ataque, las pérdidas de luz de sus regiones y
ciudades), `alumbrado.json`, `validacion.json` y `control.json`. La recogida horaria guarda los
resultados en la base (`incorporar`, tabla `luces_nocturnas`) y la publicación los añade a cada
ataque.

Lo lanza `servidor/luces.sh` con su propio temporizador y cerrojo; nunca toca la base ni el clon.
"""

import argparse
import gzip
import json
import logging
import multiprocessing
import os
import re
import sys
import time
import urllib.parse
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol

import numpy as np

from esquema import Documento
from proceso import luces
from proceso.focos_termicos import distancia_km
from recogida.rango import FicheroRemoto, Lector, LecturaFallida

if TYPE_CHECKING:
    from almacen.base import Almacen

registro = logging.getLogger("recogida.luces")

RAIZ = Path(__file__).resolve().parent.parent
CIUDADES = RAIZ / "configuracion" / "ciudades_luces.json"
VALIDACION = RAIZ / "configuracion" / "validacion_luces.json"
PUBLICACION = RAIZ / "publicacion" / "ucrania.json"
CANALES = RAIZ / "configuracion" / "canales_guerra.json"
VARIABLE_DATOS = "EODI_LUCES_DATOS"
DATOS = Path.home() / "datos" / "luces"
GUERRA = Path.home() / "datos" / "guerra" / "canales"
VARIABLE_GUERRA = "EODI_GUERRA_DATOS"
CONTROL = "control.json"
RESULTADOS = "resultados.json"
ALUMBRADO = "alumbrado.json"
OBJETO_ALUMBRADO = "luces/alumbrado.json"
CACHE_ALUMBRADO = "public, max-age=3600"
FICHERO_VALIDACION = "validacion.json"
FUENTE_ID = "luces_nocturnas"

BUCKET = "https://noaa-nesdis-n20-pds.s3.amazonaws.com"
SATELITE = "NOAA-20"
GEO, SDR = "VIIRS-DNB-GEO", "VIIRS-DNB-SDR"
# Oeste, sur, este, norte: Ucrania, Crimea y el oeste de Rusia hasta Moscú y Rostov.
CAJA = (21.0, 43.5, 42.0, 57.0)
# Salidas de los gránulos de la noche del día D: de las 21:50 de D a las 00:50 de D+1 (UTC). El
# paso descendente de NOAA-20 cruza Ucrania hacia la 01:30 hora solar (las 23:30 UTC a 30° E),
# con los pasos vecinos a unos 100 minutos.
DESDE_HORA, HASTA_HORA = (21, 50), (0, 50)
# Huellas leídas en la primera vuelta: una de cada tantos gránulos.
PASO_ANILLOS = 3
PRIMERA_NOCHE = date(2024, 1, 1)
# Una noche no se mide hasta pasadas estas horas desde su paso (el archivo tarda en llenarse).
ESPERA_NOCHE = timedelta(hours=8)
BLOQUE = 1 << 22
PROCESOS_ANILLOS = 6
# Gránulos en que se mide cada ciudad cada noche (el borde de uno puede cortarla).
GRANULOS_POR_CIUDAD = 2
# Noches que se miden a la vez (sus huellas y sus gránulos van al mismo grupo de procesos).
NOCHES_POR_LOTE = int(os.environ.get("EODI_LUCES_NOCHES_POR_LOTE", "4"))
# Gránulos medidos a la vez: cada uno ocupa unos 400 MB mientras se lee.
PROCESOS_MEDIDA = int(os.environ.get("EODI_LUCES_PROCESOS", "2"))
# Tiempo de mensajes de un ataque: su periodo y las 18 horas siguientes (el balance de la
# mañana y los cortes que anuncia la compañía eléctrica).
MENSAJES_TRAS_FIN = timedelta(hours=18)

OPEN_METEO = "https://historical-forecast-api.open-meteo.com/v1/forecast"
TOPE_NUBES = 300.0  # unidades de Open-Meteo por ejecución (un mes de un lugar son 3)
TOPE_S = 45 * 60
# Cada cuántas noches empieza una ventana de control automático.
PASO_CONTROL_DIAS = 7

PATRON_GRANULO = re.compile(r"_d(\d{8})_t(\d{6})\d_e\d+_b\d+")


# --- Archivo de NOAA ----------------------------------------------------------------------


@dataclass(frozen=True)
class Granulo:
    clave: str  # «_dAAAAMMDD_tHHMMSS…_b…», común al SDR y al GEO
    geo: str
    sdr: str
    tam_geo: int
    tam_sdr: int
    inicio: datetime


def listar(lector: Lector, prefijo: str) -> dict[str, tuple[str, int]]:
    """Claves .h5 del prefijo, con su tamaño, por clave de gránulo."""
    resultado: dict[str, tuple[str, int]] = {}
    token: str | None = None
    while True:
        url = f"{BUCKET}/?list-type=2&prefix={urllib.parse.quote(prefijo)}"
        if token:
            url += "&continuation-token=" + urllib.parse.quote(token)
        texto = lector.obtener(url).decode()
        for clave, tamano in re.findall(
            r"<Key>([^<]*\.h5)</Key>.*?<Size>(\d+)</Size>", texto, flags=re.S
        ):
            m = PATRON_GRANULO.search(clave)
            if m:
                resultado[m.group(0)] = (clave, int(tamano))
        siguiente = re.search(r"<NextContinuationToken>([^<]*)<", texto)
        if not siguiente:
            return resultado
        token = siguiente.group(1)


def granulos_de_noche(lector: Lector, noche: date) -> list[Granulo]:
    """Gránulos de NOAA-20 que salen durante la noche (sin mirar aún dónde caen)."""
    resultado = []
    for dia in (noche, noche + timedelta(days=1)):
        prefijo = f"{dia:%Y/%m/%d}/"
        geos = listar(lector, f"{GEO}/{prefijo}")
        sdrs = listar(lector, f"{SDR}/{prefijo}")
        for clave, (geo, tam_geo) in geos.items():
            if clave not in sdrs:
                continue
            m = PATRON_GRANULO.search(clave)
            assert m is not None
            inicio = datetime.strptime(m.group(1) + m.group(2), "%Y%m%d%H%M%S").replace(tzinfo=UTC)
            desde = datetime.combine(noche, datetime.min.time(), UTC) + timedelta(
                hours=DESDE_HORA[0], minutes=DESDE_HORA[1]
            )
            hasta = datetime.combine(
                noche + timedelta(days=1), datetime.min.time(), UTC
            ) + timedelta(hours=HASTA_HORA[0], minutes=HASTA_HORA[1])
            if desde <= inicio <= hasta:
                sdr, tam_sdr = sdrs[clave]
                resultado.append(Granulo(clave, geo, sdr, tam_geo, tam_sdr, inicio))
    return sorted(resultado, key=lambda g: g.inicio)


def _abrir(lector: Lector, clave: str, tamano: int) -> Any:
    import h5py

    return h5py.File(FicheroRemoto(lector.rango(f"{BUCKET}/{clave}"), tamano, BLOQUE), "r")


def anillo(geo: str, tamano: int) -> list[list[float]]:
    """Contorno del gránulo (latitudes y longitudes del G-Ring)."""
    import h5py

    lector = Lector()
    fichero = FicheroRemoto(lector.rango(f"{BUCKET}/{geo}"), tamano, 1 << 16)
    with h5py.File(fichero, "r") as h:
        grupo = h["Data_Products/VIIRS-DNB-GEO/VIIRS-DNB-GEO_Gran_0"]
        lat = [float(v) for v in np.asarray(grupo.attrs["G-Ring_Latitude"]).ravel()]
        lon = [float(v) for v in np.asarray(grupo.attrs["G-Ring_Longitude"]).ravel()]
    return [lat, lon]


def _anillo_seguro(argumentos: tuple[str, int]) -> list[list[float]] | None:
    try:
        return anillo(*argumentos)
    except Exception:
        return None


def toca_caja(contorno: list[list[float]]) -> bool:
    lat, lon = contorno
    if not lat or max(lon) - min(lon) > 180:
        return False
    oeste, sur, este, norte = CAJA
    return min(lat) <= norte and max(lat) >= sur and min(lon) <= este and max(lon) >= oeste


class Grupo:
    """Procesos para leer HDF5 en paralelo (la biblioteca no deja hacerlo con hilos dentro de un
    proceso), creados una vez por ejecución y no una vez por noche."""

    def __init__(self, procesos: int) -> None:
        self.procesos = procesos
        self._grupo: Any = None

    def map(self, funcion: Callable[[Any], Any], tareas: list[Any]) -> list[Any]:
        if not tareas:
            return []
        if self._grupo is None:
            self._grupo = multiprocessing.get_context("spawn").Pool(self.procesos)
        resultado: list[Any] = self._grupo.map(funcion, tareas)
        return resultado

    def cerrar(self) -> None:
        if self._grupo is not None:
            self._grupo.close()
            self._grupo.join()
            self._grupo = None


def _leer_anillos(granulos: list[Granulo], grupo: Grupo) -> list[list[list[float]] | None]:
    return grupo.map(_anillo_seguro, [(g.geo, g.tam_geo) for g in granulos])


def a_leer(
    granulos: list[Granulo], conocidos: dict[str, list[list[float]]], paso: int = PASO_ANILLOS
) -> list[int]:
    """Índices de los gránulos cuya huella falta. Primero uno de cada `paso` (un paso por la zona
    ocupa al menos `paso` gránulos seguidos, así que ninguno se escapa); después, solo los
    vecinos de los que tocan la zona."""
    if not conocidos:
        return [i for i in range(len(granulos)) if i % paso == 0]
    tocan = [
        i for i, g in enumerate(granulos) if g.clave in conocidos and toca_caja(conocidos[g.clave])
    ]
    vecinos = {j for i in tocan for j in range(i - paso + 1, i + paso)}
    return sorted(
        j for j in vecinos if 0 <= j < len(granulos) and granulos[j].clave not in conocidos
    )


def anillos_de_noches(
    datos: Path, noches: dict[date, list[Granulo]], grupo: Grupo
) -> dict[date, dict[str, list[list[float]]]]:
    """Contornos de los gránulos de cada noche que pueden tocar la zona, de la caché o
    pidiéndolos en paralelo, todas las noches a la vez."""
    resultado: dict[date, dict[str, list[list[float]]]] = {}
    abiertas: dict[date, set[int]] = {}
    for noche in noches:
        ruta = datos / "anillos" / f"{noche.isoformat()}.json"
        if ruta.exists():
            resultado[noche] = json.loads(ruta.read_text(encoding="utf-8"))
        else:
            resultado[noche] = {}
            abiertas[noche] = set()
    while True:
        tareas: list[tuple[date, int]] = []
        for noche, leidos in abiertas.items():
            nuevos = [i for i in a_leer(noches[noche], resultado[noche]) if i not in leidos]
            leidos.update(nuevos)
            tareas += [(noche, i) for i in nuevos]
        if not tareas:
            break
        contornos = _leer_anillos([noches[n][i] for n, i in tareas], grupo)
        for (noche, i), contorno in zip(tareas, contornos, strict=True):
            if contorno is not None:
                resultado[noche][noches[noche][i].clave] = contorno
    for noche in abiertas:
        _escribir(datos / "anillos" / f"{noche.isoformat()}.json", resultado[noche])
    return resultado


def anillos(
    datos: Path, noche: date, granulos: list[Granulo], grupo: Grupo | None = None
) -> dict[str, list[list[float]]]:
    """Los contornos de una sola noche."""
    propio = grupo or Grupo(PROCESOS_ANILLOS)
    try:
        return anillos_de_noches(datos, {noche: granulos}, propio)[noche]
    finally:
        if grupo is None:
            propio.cerrar()


def medir_granulo(
    lector: Lector, granulo: Granulo, ciudades: list[luces.Ciudad]
) -> tuple[dict[str, Documento], float]:
    """Medida de cada ciudad que cae en el gránulo, y la fracción iluminada de la Luna."""
    with _abrir(lector, granulo.geo, granulo.tam_geo) as h:
        g = h["All_Data/VIIRS-DNB-GEO_All"]
        lat = g["Latitude"][:]
        lon = g["Longitude"][:]
        cenit_satelite = g["SatelliteZenithAngle"][:]
        cenit_luna = g["LunarZenithAngle"][:]
        cenit_sol = g["SolarZenithAngle"][:]
        fraccion_luna = float(np.asarray(g["MoonIllumFraction"]).ravel()[0])
    with _abrir(lector, granulo.sdr, granulo.tam_sdr) as h:
        s = h["All_Data/VIIRS-DNB-SDR_All"]
        radiancia = s["Radiance"][:]
        calidad = s["QF1_VIIRSDNBSDR"][:]
    medidas = {}
    for ciudad in ciudades:
        medida = luces.medir_ciudad(
            ciudad, lat, lon, radiancia, calidad, cenit_satelite, cenit_luna, cenit_sol
        )
        if medida is not None:
            medida["hora"] = granulo.inicio.strftime("%Y-%m-%dT%H:%MZ")
            medida["luna_pct"] = round(fraccion_luna, 1)
            medidas[ciudad.id] = medida
    return medidas, fraccion_luna


def dentro(contorno: list[list[float]], lat: float, lon: float) -> bool:
    """Si el punto cae dentro del contorno del gránulo (rayo horizontal)."""
    lats, lons = contorno
    resultado = False
    j = len(lats) - 1
    for i in range(len(lats)):
        if (lats[i] > lat) != (lats[j] > lat):
            corte = lons[i] + (lat - lats[i]) * (lons[j] - lons[i]) / (lats[j] - lats[i])
            if lon < corte:
                resultado = not resultado
        j = i
    return resultado


def elegir_granulos(
    contornos: dict[str, list[list[float]]], ciudades: list[luces.Ciudad]
) -> dict[str, list[luces.Ciudad]]:
    """Para cada ciudad, los GRANULOS_POR_CIUDAD gránulos que la contienen con su centro más
    cerca (los más cercanos a la vertical del satélite y lejos de sus bordes); por gránulo, las
    ciudades que mide."""
    asignadas: dict[str, list[luces.Ciudad]] = {}
    for ciudad in ciudades:
        candidatos = []
        for clave, contorno in contornos.items():
            if not toca_caja(contorno) or not dentro(contorno, ciudad.lat, ciudad.lon):
                continue
            lat_c = sum(contorno[0]) / len(contorno[0])
            lon_c = sum(contorno[1]) / len(contorno[1])
            candidatos.append((distancia_km(ciudad.lat, ciudad.lon, lat_c, lon_c), clave))
        # Los dos más centrados: si el borde de uno corta la ciudad, vale el otro.
        for _, clave in sorted(candidatos)[:GRANULOS_POR_CIUDAD]:
            asignadas.setdefault(clave, []).append(ciudad)
    return asignadas


def _medir_en_proceso(argumentos: tuple[Granulo, list[luces.Ciudad]]) -> dict[str, Documento]:
    granulo, ciudades = argumentos
    lector = Lector()
    medidas, _ = medir_granulo(lector, granulo, ciudades)
    medidas["__bytes__"] = {"bytes": lector.bytes}
    return medidas


def medir_noches(
    lector: Lector,
    datos: Path,
    pedidas: dict[date, list[luces.Ciudad]],
    grupo: Grupo,
) -> dict[date, Documento]:
    """Medida de las ciudades pedidas en cada noche, cada una en el gránulo que la ve más de
    frente. Las huellas y los gránulos de todas las noches se leen en paralelo."""
    granulos = {noche: granulos_de_noche(lector, noche) for noche in pedidas}
    contornos = anillos_de_noches(datos, granulos, grupo)
    tareas: list[tuple[date, Granulo, list[luces.Ciudad]]] = []
    asignadas_por_noche: dict[date, dict[str, list[luces.Ciudad]]] = {}
    for noche, ciudades in pedidas.items():
        por_clave = {g.clave: g for g in granulos[noche]}
        asignadas = elegir_granulos(
            {c: v for c, v in contornos[noche].items() if c in por_clave}, ciudades
        )
        asignadas_por_noche[noche] = asignadas
        tareas += [(noche, por_clave[clave], lista) for clave, lista in sorted(asignadas.items())]
    elegidas: dict[date, dict[str, Documento]] = {noche: {} for noche in pedidas}
    medidas = grupo.map(_medir_en_proceso, [(g, lista) for _, g, lista in tareas])
    for (noche, _, _), medida in zip(tareas, medidas, strict=True):
        lector.bytes += int(medida.pop("__bytes__")["bytes"])
        for ciudad_id, documento in medida.items():
            previa = elegidas[noche].get(ciudad_id)
            # De los gránulos que la ven entera, el más vertical.
            elegidas[noche][ciudad_id] = luces.mejor([d for d in (previa, documento) if d])  # type: ignore[assignment]
    return {
        noche: {
            "noche": noche.isoformat(),
            "satelite": SATELITE,
            "granulos": sorted(asignadas_por_noche[noche]),
            "version": luces.VERSION,
            # Las ciudades que se pidieron medir (algunas pueden no verse esa noche).
            "pedidas": sorted(c.id for c in ciudades),
            "ciudades": dict(sorted(elegidas[noche].items())),
        }
        for noche, ciudades in pedidas.items()
    }


def medir_noche(
    lector: Lector, datos: Path, noche: date, ciudades: list[luces.Ciudad]
) -> Documento:
    """Medida de las ciudades en una sola noche."""
    grupo = Grupo(PROCESOS_MEDIDA)
    try:
        return medir_noches(lector, datos, {noche: ciudades}, grupo)[noche]
    finally:
        grupo.cerrar()


def _noche_guardada(datos: Path, noche: date) -> Documento | None:
    ruta = datos / "noches" / f"{noche.isoformat()}.json"
    if not ruta.exists():
        return None
    documento: Documento = json.loads(ruta.read_text(encoding="utf-8"))
    return documento


def faltan_en(documento: Documento | None, ciudades: Iterable[str]) -> set[str]:
    """Ciudades que aún no se han pedido en esa noche (todas si la noche no está medida)."""
    if documento is None:
        return set(ciudades)
    pedidas = set(documento.get("pedidas") or documento.get("ciudades") or {})
    return set(ciudades) - pedidas


def unir(anterior: Documento | None, nuevo: Documento) -> Documento:
    """Una noche medida en dos veces (primero unas ciudades, después otras)."""
    if anterior is None:
        return nuevo
    return {
        **nuevo,
        "granulos": sorted(set(anterior.get("granulos", [])) | set(nuevo["granulos"])),
        "pedidas": sorted(set(anterior.get("pedidas", [])) | set(nuevo["pedidas"])),
        "ciudades": dict(sorted({**anterior.get("ciudades", {}), **nuevo["ciudades"]}.items())),
    }


# --- Nubes -------------------------------------------------------------------------------


class Nubes:
    """Nubosidad horaria de Open-Meteo por ciudad y mes, con caché y tope por ejecución."""

    def __init__(
        self,
        datos: Path,
        obtener: Callable[[str], bytes] | None = None,
        tope: float = TOPE_NUBES,
        hoy: date | None = None,
    ) -> None:
        self.datos = datos / "nubes"
        self.tope = tope
        self.gastadas = 0.0
        self.hoy = hoy or datetime.now(UTC).date()
        self._obtener = obtener or self._http
        self._memoria: dict[tuple[str, str], dict[str, float] | None] = {}

    @staticmethod
    def _http(url: str) -> bytes:
        return Lector().obtener(url)

    def _mes(self, ciudad: luces.Ciudad, mes: date) -> dict[str, float] | None:
        clave = (ciudad.id, f"{mes:%Y-%m}")
        if clave in self._memoria:
            return self._memoria[clave]
        ruta = self.datos / ciudad.id.replace(":", "_") / f"{mes:%Y-%m}.json"
        fin = (mes.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
        completo = fin < self.hoy - timedelta(days=1)
        if ruta.exists():
            guardado = json.loads(ruta.read_text(encoding="utf-8"))
            if guardado.get("completo") or guardado.get("pedido") == self.hoy.isoformat():
                self._memoria[clave] = guardado["horas"]
                return self._memoria[clave]
        hasta = min(fin, self.hoy - timedelta(days=1))
        if hasta < mes:
            return None
        coste = 3.0
        if self.gastadas + coste > self.tope:
            return None
        parametros = {
            "latitude": f"{ciudad.lat:.3f}",
            "longitude": f"{ciudad.lon:.3f}",
            "start_date": mes.isoformat(),
            "end_date": hasta.isoformat(),
            "hourly": "cloud_cover",
            "timezone": "GMT",
        }
        self.gastadas += coste
        try:
            respuesta = json.loads(
                self._obtener(f"{OPEN_METEO}?{urllib.parse.urlencode(parametros)}")
            )
        except (LecturaFallida, ValueError) as error:
            registro.warning("nubes de %s %s: %s", ciudad.nombre, f"{mes:%Y-%m}", error)
            return None
        horario = respuesta.get("hourly", {})
        horas = {
            t: float(v)
            for t, v in zip(horario.get("time", []), horario.get("cloud_cover", []), strict=False)
            if isinstance(v, int | float)
        }
        _escribir(ruta, {"completo": completo, "pedido": self.hoy.isoformat(), "horas": horas})
        self._memoria[clave] = horas
        return horas

    def en(self, ciudad: luces.Ciudad, hora: str) -> float | None:
        """Nubosidad (%) a la hora en punto más cercana a `hora` («AAAA-MM-DDTHH:MMZ»)."""
        momento = datetime.strptime(hora, "%Y-%m-%dT%H:%MZ") + timedelta(minutes=30)
        momento = momento.replace(minute=0)
        horas = self._mes(ciudad, momento.date().replace(day=1))
        if horas is None:
            return None
        return horas.get(momento.strftime("%Y-%m-%dT%H:00"))


# --- Ataques contra la energía -----------------------------------------------------------


@dataclass(frozen=True)
class AtaqueEnergia:
    id: str
    sentido: str
    inicio: datetime
    fin: datetime
    regiones: tuple[str, ...]


def _instante(texto: str) -> datetime:
    return datetime.fromisoformat(texto.replace("Z", "+00:00")).astimezone(UTC)


def mensajes_de_energia(guerra: Path, canales: list[Documento]) -> list[tuple[str, datetime]]:
    """(región, hora) de cada mensaje guardado de un canal regional que nombra la red eléctrica."""
    from proceso.mensajes_guerra import categorias

    resultado = []
    for canal in canales:
        region = canal.get("region")
        carpeta = guerra / str(canal["canal"])
        if not region or not carpeta.is_dir():
            continue
        for fichero in sorted(carpeta.glob("*.jsonl*")):
            abrir = gzip.open if fichero.suffix == ".gz" else open
            with abrir(fichero, "rt", encoding="utf-8") as lineas:
                for linea in lineas:
                    try:
                        mensaje = json.loads(linea)
                    except ValueError:
                        continue
                    texto = str(mensaje.get("texto") or "")
                    if "energia" in categorias(texto):
                        resultado.append((str(region), _instante(str(mensaje["fecha"]))))
    return resultado


def _solape_con_el_dia(inicio: datetime, fin: datetime, dia: date) -> timedelta:
    comienzo = datetime.combine(dia, datetime.min.time(), UTC)
    return min(fin, comienzo + timedelta(days=1)) - max(inicio, comienzo)


def ataques_de_energia(
    publicacion: Documento,
    mensajes: Iterable[tuple[str, datetime]],
    apagones: Iterable[tuple[date, str]] = (),
) -> list[AtaqueEnergia]:
    """Ataques con objetivos de energía y sus regiones afectadas. Además de los impactos y los
    mensajes, los apagones documentados de la validación (día y región de cada ciudad): cuentan
    para el ataque contra Ucrania en curso ese día (el que más horas tiene en él)."""
    ataques = {a["id"]: a for a in publicacion.get("ataques", [])}
    regiones: dict[str, set[str]] = {}
    for impacto in publicacion.get("impactos", []):
        if "energia" in impacto.get("categorias_objetivo", []) and impacto.get("ataque") in ataques:
            regiones.setdefault(impacto["ataque"], set()).add(impacto["region"])
    por_sentido: dict[str, list[tuple[datetime, datetime, str]]] = {}
    for ataque in ataques.values():
        if "incluido_en" in ataque:
            continue
        por_sentido.setdefault(ataque["sentido"], []).append(
            (
                _instante(ataque["periodo"]["inicio"]["valor"]),
                _instante(ataque["periodo"]["fin"]["valor"]),
                ataque["id"],
            )
        )
    for lista in por_sentido.values():
        lista.sort()
    for region, momento in mensajes:
        sentido = "RU_UA" if region.startswith("UA-") else "UA_RU"
        # El ataque más reciente que empezó antes del mensaje y cuyo tiempo lo incluye.
        candidatos = [
            (inicio, id_)
            for inicio, fin, id_ in por_sentido.get(sentido, [])
            if inicio <= momento <= fin + MENSAJES_TRAS_FIN
        ]
        if candidatos:
            regiones.setdefault(max(candidatos)[1], set()).add(region)
    for dia, region in apagones:
        solapes = [
            (_solape_con_el_dia(inicio, fin, dia), id_)
            for inicio, fin, id_ in por_sentido.get("RU_UA", [])
        ]
        positivos = [s for s in solapes if s[0] > timedelta(0)]
        if positivos:
            regiones.setdefault(max(positivos)[1], set()).add(region)
    resultado = []
    for id_, conjunto in regiones.items():
        ataque = ataques[id_]
        resultado.append(
            AtaqueEnergia(
                id=id_,
                sentido=ataque["sentido"],
                inicio=_instante(ataque["periodo"]["inicio"]["valor"]),
                fin=_instante(ataque["periodo"]["fin"]["valor"]),
                regiones=tuple(sorted(conjunto)),
            )
        )
    return sorted(resultado, key=lambda a: (a.inicio, a.id))


def noches_de(inicio: date, fin: date) -> list[date]:
    return luces.noches_referencia(inicio) + luces.noches_despues(inicio, fin)


class FuenteNubes(Protocol):
    """Lo que la evaluación necesita de las nubes: la nubosidad de una ciudad a una hora."""

    def en(self, ciudad: luces.Ciudad, hora: str) -> float | None: ...


# --- Evaluación --------------------------------------------------------------------------


def cargar_ciudades(ruta: Path = CIUDADES) -> list[luces.Ciudad]:
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    return [luces.ciudad_de(c) for c in datos["ciudades"]]


def series(
    datos: Path, noches: Iterable[date], ciudades: list[luces.Ciudad], nubes: FuenteNubes
) -> dict[str, dict[date, float | None]]:
    """Brillo válido de cada ciudad por noche (None si la noche no vale o no se midió)."""
    por_id = {c.id: c for c in ciudades}
    resultado: dict[str, dict[date, float | None]] = {c.id: {} for c in ciudades}
    for noche in sorted(set(noches)):
        ruta = datos / "noches" / f"{noche.isoformat()}.json"
        if not ruta.exists():
            continue
        medidas = json.loads(ruta.read_text(encoding="utf-8")).get("ciudades", {})
        for ciudad_id, medida in medidas.items():
            ciudad = por_id.get(ciudad_id)
            if ciudad is None:
                continue
            medida = {**medida, "nubes_pct": nubes.en(ciudad, medida["hora"])}
            resultado[ciudad_id][noche] = float(medida["brillo"]) if luces.valida(medida) else None
    return resultado


def evaluar_ataque(
    ataque: AtaqueEnergia,
    ciudades: list[luces.Ciudad],
    serie: dict[str, dict[date, float | None]],
) -> list[Documento]:
    """Las pérdidas de luz de las regiones afectadas y de sus ciudades."""
    inicio, fin = ataque.inicio.date(), ataque.fin.date()
    noches = noches_de(inicio, fin)
    documentos = []
    for region in ataque.regiones:
        de_region = [c for c in ciudades if c.region == region]
        for ciudad in de_region:
            resultado = luces.evaluar(serie.get(ciudad.id, {}), inicio, fin)
            zona = {
                "zona": "ciudad",
                "region": region,
                "ciudad": {
                    "id": ciudad.id,
                    "nombre": ciudad.nombre,
                    "punto": {"lat": ciudad.lat, "lon": ciudad.lon},
                },
            }
            if (doc := luces.documento(zona, resultado, inicio, fin)) is not None:
                documentos.append(doc)
        medidas = luces.ciudades_con_serie(serie, [c.id for c in de_region], inicio)
        if medidas:
            suma = luces.serie_de_region(serie, medidas, noches)
            resultado = luces.evaluar(suma, inicio, fin)
            zona = {"zona": "region", "region": region}
            if (doc := luces.documento(zona, resultado, inicio, fin)) is not None:
                documentos.append(doc)
    return documentos


# --- Ficheros ----------------------------------------------------------------------------


def _escribir(ruta: Path, documento: Any) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    temporal = ruta.with_suffix(ruta.suffix + ".tmp")
    with open(temporal, "w", encoding="utf-8", newline="\n") as fichero:
        json.dump(documento, fichero, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    temporal.replace(ruta)


def directorio_datos() -> Path:
    return Path(os.environ.get(VARIABLE_DATOS) or DATOS)


def noches_pendientes(
    datos: Path,
    necesarias: Iterable[date],
    ahora: datetime,
    ciudades: Iterable[str] | None = None,
) -> list[date]:
    """Noches necesarias aún sin medir (o sin alguna de `ciudades`), de la más reciente a la
    más antigua. La de ayer y las anteriores, pasada la espera del archivo."""
    ultima = (ahora - ESPERA_NOCHE - timedelta(hours=24)).date()
    ids = list(ciudades or [])
    return sorted(
        (
            n
            for n in set(necesarias)
            if PRIMERA_NOCHE <= n <= ultima
            and (
                not (datos / "noches" / f"{n.isoformat()}.json").exists()
                or (ids and faltan_en(_noche_guardada(datos, n), ids))
            )
        ),
        reverse=True,
    )


def casos_validacion(ruta: Path = VALIDACION) -> list[Documento]:
    datos: list[Documento] = json.loads(ruta.read_text(encoding="utf-8"))["casos"]
    return datos


def apagones_documentados(
    casos: list[Documento], ciudades: list[luces.Ciudad]
) -> list[tuple[date, str]]:
    """Día y región de cada ciudad de los apagones documentados de la validación."""
    region = {c.id: c.region for c in ciudades}
    return [
        (date.fromisoformat(caso["inicio"]), region[ciudad_id])
        for caso in casos
        if caso["tipo"] == "apagon"
        for ciudad_id in caso["ciudades"]
        if ciudad_id in region
    ]


def noches_medidas(datos: Path) -> list[date]:
    """Todas las noches con alguna medida guardada."""
    carpeta = datos / "noches"
    if not carpeta.is_dir():
        return []
    return sorted(date.fromisoformat(r.stem) for r in carpeta.glob("????-??-??.json"))


def alumbrado(
    ciudades: list[luces.Ciudad], serie: dict[str, dict[date, float | None]]
) -> list[Documento]:
    """Las ciudades con alumbrado reducido de forma permanente, de norte a sur."""
    resultado = []
    for ciudad in sorted(ciudades, key=lambda c: (-c.lat, c.id)):
        encontrado = luces.alumbrado_reducido(serie.get(ciudad.id, {}))
        if encontrado is not None:
            resultado.append(luces.documento_alumbrado(ciudad, encontrado))
    return resultado


def noches_validacion(casos: list[Documento]) -> list[date]:
    resultado = []
    for caso in casos:
        inicio, fin = date.fromisoformat(caso["inicio"]), date.fromisoformat(caso["fin"])
        resultado += noches_de(inicio, fin)
    return resultado


def controles_automaticos(
    ciudades: list[luces.Ciudad],
    serie: dict[str, dict[date, float | None]],
    ataques: list[AtaqueEnergia],
    paso_dias: int = PASO_CONTROL_DIAS,
) -> list[luces.Resultado]:
    """La regla en cada ciudad en ventanas sin ningún ataque contra la energía de su
    región: una ventana empieza cada `paso_dias` noches medidas y no puede tener un ataque de su
    región desde DIAS_REFERENCIA noches antes hasta DIAS_DESPUES después. Lo que pierda una
    ciudad ahí es el ruido de la medida (nubes que el modelo no ve, cortes programados)."""
    perdidas: list[luces.Resultado] = []
    for ciudad in ciudades:
        noches = sorted(n for n, v in serie.get(ciudad.id, {}).items() if v is not None)
        if not noches:
            continue
        de_region = [a for a in ataques if ciudad.region in a.regiones]
        inicio = noches[0] + timedelta(days=luces.DIAS_REFERENCIA)
        while inicio <= noches[-1]:
            libre = all(
                not (
                    inicio - timedelta(days=luces.DIAS_REFERENCIA + luces.DIAS_DESPUES)
                    <= a.inicio.date()
                    <= inicio + timedelta(days=luces.DIAS_DESPUES + 1)
                )
                for a in de_region
            )
            if libre:
                resultado = luces.evaluar(serie[ciudad.id], inicio, inicio + timedelta(days=1))
                if (
                    resultado.maxima is not None
                    and resultado.referencia is not None
                    and resultado.referencia >= luces.BRILLO_REFERENCIA_MIN
                ):
                    perdidas.append(resultado)
            inicio += timedelta(days=paso_dias)
    return perdidas


def _cuantil(valores: list[float], q: float) -> float | None:
    if not valores:
        return None
    ordenados = sorted(valores)
    return round(ordenados[min(len(ordenados) - 1, int(q * len(ordenados)))], 3)


def validar(
    casos: list[Documento],
    ciudades: list[luces.Ciudad],
    serie: dict[str, dict[date, float | None]],
    ataques: list[AtaqueEnergia] | None = None,
) -> Documento:
    """Cada caso documentado (y cada control) con lo que da la regla para sus ciudades, y los
    controles automáticos."""
    filas = []
    for caso in casos:
        inicio, fin = date.fromisoformat(caso["inicio"]), date.fromisoformat(caso["fin"])
        for ciudad_id in caso["ciudades"]:
            resultado = luces.evaluar(serie.get(ciudad_id, {}), inicio, fin)
            maxima = resultado.maxima
            filas.append(
                {
                    "caso": caso["id"],
                    "tipo": caso["tipo"],
                    "ciudad": ciudad_id,
                    "nombre": next((c.nombre for c in ciudades if c.id == ciudad_id), ciudad_id),
                    "referencia": None
                    if resultado.referencia is None
                    else round(resultado.referencia, 2),
                    "noches_referencia": resultado.noches_referencia,
                    "noches_despues": len(resultado.perdidas),
                    "perdida_maxima": None if maxima is None else maxima[1],
                    "noche": None if maxima is None else maxima[0].isoformat(),
                    "perdidas": {d.isoformat(): v for d, v in sorted(resultado.perdidas.items())},
                    "perdida_luz": resultado.perdida_luz,
                }
            )
    apagones = [f for f in filas if f["tipo"] == "apagon"]
    controles = [f for f in filas if f["tipo"] == "control"]
    automaticos = controles_automaticos(ciudades, serie, ataques or [])
    maximas = [r.maxima[1] for r in automaticos if r.maxima is not None]
    return {
        "version": luces.VERSION,
        "umbral": luces.UMBRAL_PERDIDA,
        "noches_con_perdida_min": luces.NOCHES_CON_PERDIDA_MIN,
        "apagones": {
            "evaluables": sum(1 for f in apagones if f["perdida_maxima"] is not None),
            "detectados": sum(1 for f in apagones if f["perdida_luz"]),
            "total": len(apagones),
        },
        "controles": {
            "evaluables": sum(1 for f in controles if f["perdida_maxima"] is not None),
            "falsos_positivos": sum(1 for f in controles if f["perdida_luz"]),
            "total": len(controles),
        },
        "controles_automaticos": {
            "ventanas": len(automaticos),
            "falsos_positivos": sum(1 for r in automaticos if r.perdida_luz),
            "perdida_p50": _cuantil(maximas, 0.5),
            "perdida_p90": _cuantil(maximas, 0.9),
            "perdida_p95": _cuantil(maximas, 0.95),
            "perdida_p99": _cuantil(maximas, 0.99),
        },
        "filas": filas,
    }


# --- Órdenes -----------------------------------------------------------------------------


def calcular(
    datos: Path,
    guerra: Path,
    ahora: datetime,
    tope_s: float = TOPE_S,
    lector: Lector | None = None,
    reloj: Callable[[], float] = time.monotonic,
    solo_validacion: bool = False,
) -> Documento:
    inicio_reloj = reloj()
    lector = lector or Lector()
    ciudades = cargar_ciudades()
    casos = casos_validacion()
    publicacion = (
        json.loads(PUBLICACION.read_text(encoding="utf-8")) if PUBLICACION.exists() else {}
    )
    canales = json.loads(CANALES.read_text(encoding="utf-8"))["canales"]
    ataques = (
        []
        if solo_validacion
        else ataques_de_energia(
            publicacion,
            mensajes_de_energia(guerra, canales),
            apagones_documentados(casos, ciudades),
        )
    )
    necesarias = noches_validacion(casos) + [
        n for a in ataques for n in noches_de(a.inicio.date(), a.fin.date())
    ]
    # La noche más reciente también, aunque no sea de ningún ataque: así la siguiente referencia
    # ya está medida.
    necesarias.append((ahora - ESPERA_NOCHE - timedelta(hours=24)).date())
    # Con --solo-validacion se miden solo las ciudades de los casos; el servicio completa
    # después esas noches con las demás.
    ids_validacion = {c for caso in casos for c in caso["ciudades"]}
    a_medir = [c for c in ciudades if c.id in ids_validacion] if solo_validacion else ciudades
    pendientes = noches_pendientes(datos, necesarias, ahora, [c.id for c in a_medir])
    # Primero las de la validación, después las demás de la más reciente a la más antigua.
    de_validacion = set(noches_validacion(casos))
    pendientes.sort(key=lambda n: (n not in de_validacion, -n.toordinal()))
    medidas = fallidas = 0
    grupo = Grupo(PROCESOS_MEDIDA)
    try:
        for inicio_lote in range(0, len(pendientes), NOCHES_POR_LOTE):
            if reloj() - inicio_reloj > tope_s:
                break
            lote = pendientes[inicio_lote : inicio_lote + NOCHES_POR_LOTE]
            anteriores = {noche: _noche_guardada(datos, noche) for noche in lote}
            pedidas = {
                noche: [
                    c
                    for c in a_medir
                    if c.id in faltan_en(anteriores[noche], [x.id for x in a_medir])
                ]
                for noche in lote
            }
            try:
                documentos = medir_noches(lector, datos, pedidas, grupo)
            except (LecturaFallida, OSError, KeyError) as error:
                registro.warning("noches %s no medidas: %s", lote, str(error)[:200])
                fallidas += len(lote)
                continue
            for noche, documento in documentos.items():
                _escribir(
                    datos / "noches" / f"{noche.isoformat()}.json",
                    unir(anteriores[noche], documento),
                )
                medidas += 1
    finally:
        grupo.cerrar()
    nubes = Nubes(datos)
    serie = series(datos, necesarias, ciudades, nubes)
    resultados = {}
    for ataque in ataques:
        perdidas = evaluar_ataque(ataque, ciudades, serie)
        if perdidas:
            resultados[ataque.id] = perdidas
    validacion = validar(casos, ciudades, serie, ataques)
    reducidas = alumbrado(ciudades, series(datos, noches_medidas(datos), ciudades, nubes))
    _escribir(
        datos / RESULTADOS,
        {"version": luces.VERSION, "generado": _hora(ahora), "ataques": resultados},
    )
    _escribir(datos / ALUMBRADO, documento_de_alumbrado(reducidas, ahora))
    _escribir(datos / FICHERO_VALIDACION, validacion)
    restantes = len(noches_pendientes(datos, necesarias, ahora, [c.id for c in a_medir]))
    control = {
        "ultima": _hora(ahora),
        "noches_medidas": medidas,
        "noches_fallidas": fallidas,
        "noches_pendientes": restantes,
        "ataques_energia": len(ataques),
        "ataques_con_perdida": len(resultados),
        "alumbrado_reducido": len(reducidas),
        "nubes_llamadas": nubes.gastadas,
        "megabytes": round(lector.bytes / 1e6, 1),
        "duracion_s": round(reloj() - inicio_reloj),
        "validacion": {
            k: validacion[k] for k in ("apagones", "controles", "controles_automaticos")
        },
    }
    _escribir(datos / CONTROL, control)
    return control


def _hora(momento: datetime) -> str:
    return momento.astimezone(UTC).strftime("%Y-%m-%dT%H:%MZ")


def documento_de_alumbrado(ciudades: list[Documento], ahora: datetime) -> Documento:
    """El fichero público de las ciudades con alumbrado reducido."""
    return {
        "version": luces.VERSION,
        "generado": _hora(ahora),
        "referencia_minima": luces.BRILLO_REFERENCIA_MIN,
        "satelite": "NOAA-20",
        "ciudades": ciudades,
    }


def subir_alumbrado(datos: Path, subir: Callable[[str, bytes, str, str], bool]) -> bool:
    """Sube alumbrado.json al almacén público (si existe)."""
    ruta = datos / ALUMBRADO
    if not ruta.exists():
        return False
    return subir(OBJETO_ALUMBRADO, ruta.read_bytes(), "application/json", CACHE_ALUMBRADO)


def incorporar(almacen: "Almacen", datos: Path | None = None) -> int:
    """En la recogida horaria: guarda en la base las pérdidas de luz de cada ataque."""
    ruta = (datos or directorio_datos()) / RESULTADOS
    if not ruta.exists():
        return 0
    resultados = json.loads(ruta.read_text(encoding="utf-8"))
    cambiados = 0
    vigentes = resultados.get("ataques", {})
    for ataque_id, documentos in vigentes.items():
        cambiados += almacen.guardar_luces_nocturnas(
            ataque_id, {"version": resultados["version"], "perdidas": documentos}
        )
    # Un ataque que ya no tiene pérdida (otra versión de la regla) se queda sin ninguna.
    for ataque_id in set(almacen.luces_nocturnas()) - set(vigentes):
        cambiados += almacen.guardar_luces_nocturnas(
            ataque_id, {"version": resultados["version"], "perdidas": []}
        )
    return cambiados


def paso_horario(almacen: "Almacen") -> None:
    """En la recogida horaria: nada de lo que falle aquí sale de esta función."""
    try:
        registro.info("luces nocturnas incorporadas: %d cambiadas", incorporar(almacen))
    except Exception as error:
        registro.warning("luces nocturnas no incorporadas: %s", str(error)[:300])


def principal(argumentos: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    opciones = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    opciones.add_argument("orden", choices=["calcular"])
    opciones.add_argument("--tope-min", type=float, default=TOPE_S / 60)
    opciones.add_argument("--solo-validacion", action="store_true")
    opciones.add_argument("--sin-subir", action="store_true")
    opciones.add_argument("--registro", type=Path)
    args = opciones.parse_args(argumentos)
    datos = directorio_datos()
    guerra = Path(os.environ.get(VARIABLE_GUERRA) or GUERRA.parent) / "canales"
    ahora = datetime.now(UTC)
    control = calcular(
        datos, guerra, ahora, args.tope_min * 60, solo_validacion=args.solo_validacion
    )
    registro.info("luces: %s", json.dumps(control, ensure_ascii=False))
    if not args.sin_subir and not args.solo_validacion:
        from recogida.satelite import subida_al_almacen

        subido = subir_alumbrado(datos, subida_al_almacen(os.environ))
        registro.info("alumbrado reducido %s", "subido" if subido else "no subido")
    if args.registro is not None:
        _escribir(args.registro, {"ultima": control["ultima"], "duracion_s": control["duracion_s"]})
    return 0


if __name__ == "__main__":
    sys.exit(principal())
