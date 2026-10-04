"""Focos de calor en vivo: los focos de NASA FIRMS de las últimas 24 horas sobre Ucrania y la
Rusia europea, para la capa de guerra de la web.

Sale de los CSV que la recogida horaria descarga de FIRMS cada 3 horas (`datos/firms`,
recogida/firms.py): no se pide nada a FIRMS. Cada foco de las últimas 24 horas (contadas desde
la ejecución) dentro de Ucrania (con lo ocupado) o de una región de la Rusia europea (los
polígonos de las regiones que dibuja la web) pasa por los mismos filtros que el cruce con los
impactos (proceso/focos_termicos.py):

- **Confianza**: fuera VIIRS «l» y MODIS por debajo de 30.
- **Fuentes de calor habituales**: fuera el foco que cae a menos de DISTANCIA_HABITUAL_KM de
  un foco de los 30 días anteriores sin pasar de FACTOR_FRP veces su potencia (las antorchas de
  una refinería, una planta), y el que cae en un emplazamiento con FOCOS_EMPLAZAMIENTO o más
  focos en el año anterior sin pasar de FACTOR_FRP veces su percentil 90 (antorchas
  estacionales, como la de Kirishi).
- **Fuego frecuente**: fuera el foco cuyo entorno (RADIO_FRECUENTE_KM) ardió
  DIAS_FUEGO_FRECUENTE días o más de los 30 anteriores repartido en CELDAS_FUEGO_FRECUENTE celdas o
  más (las ciudades del frente y las zonas de quemas).

Un foco **coincide con un impacto declarado** si cae en el radio de búsqueda de un impacto con
lugar publicado (`publicacion/ucrania.json`, sin los partes diarios ni los FPV del frente, como
en el cruce) y su hora está entre 36 horas antes y 36 horas después de la publicación del
impacto.

El año de referencia de los emplazamientos se resume una vez al día por celdas de 0,01° (`<datos>/
emplazamientos-<AAAA-MM-DD>.json.gz`, `EODI_FOCOS_VIVO_DATOS`). El fichero público, pequeño,
va al almacén público (`focos/ultimas24h.json`, caché de 5 minutos) y la web lo lee
directamente; lleva la hora del último foco.

Lo lanza `servidor/focos_vivo.sh` con su propio temporizador y cerrojo, cada hora: sale nuevo
tras cada descarga de FIRMS y la ventana de 24 horas avanza. No toca la base ni el clon.
"""

import argparse
import gzip
import json
import logging
import math
import os
import sys
import time
from collections import defaultdict
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from esquema import Documento
from proceso import fronteras, impactos_guerra
from proceso.focos_termicos import (
    CELDAS_FUEGO_FRECUENTE,
    DIAS_FUEGO_FRECUENTE,
    DISTANCIA_HABITUAL_KM,
    FACTOR_FRP,
    FOCOS_EMPLAZAMIENTO,
    PERCENTIL_EMPLAZAMIENTO,
    Foco,
    distancia_km,
    radio_busqueda,
)
from recogida import firms

registro = logging.getLogger("recogida.focos_vivo")

RAIZ = Path(__file__).resolve().parent.parent
PUBLICACION = RAIZ / "publicacion" / "ucrania.json"
# Ucrania (con lo ocupado) y las regiones de la Rusia europea que dibuja la web.
REGIONES = (
    RAIZ / "web" / "public" / "mapa" / "ucrania-regiones.geojson",
    RAIZ / "web" / "public" / "mapa" / "rusia-regiones.geojson",
)
VARIABLE_DATOS = "EODI_FOCOS_VIVO_DATOS"
DATOS = Path.home() / "datos" / "focos_vivo"
OBJETO = "focos/ultimas24h.json"
CACHE = "public, max-age=300"
HORAS = 24
DIAS_BASE = 30
DIAS_ANIO = 365
RADIO_FRECUENTE_KM = 5.0
VENTANA_IMPACTO = timedelta(hours=36)
CELDA = 0.01
REJILLA = 0.1  # celdas del índice espacial para buscar vecinos


def _es_baja(foco: Foco) -> bool:
    return foco.baja_confianza()


class Indice:
    """Focos por celdas de REJILLA grados, para buscar los de alrededor de un punto."""

    def __init__(self, focos: Iterable[Foco]) -> None:
        self._celdas: dict[tuple[int, int], list[Foco]] = defaultdict(list)
        for foco in focos:
            self._celdas[self._celda(foco.lat, foco.lon)].append(foco)

    @staticmethod
    def _celda(lat: float, lon: float) -> tuple[int, int]:
        return math.floor(lat / REJILLA), math.floor(lon / REJILLA)

    def cerca(self, lat: float, lon: float, radio_km: float) -> list[Foco]:
        pasos_lat = math.ceil(radio_km / 111.0 / REJILLA)
        pasos_lon = math.ceil(radio_km / (111.0 * max(0.2, math.cos(math.radians(lat)))) / REJILLA)
        fila, columna = self._celda(lat, lon)
        resultado = []
        for df in range(-pasos_lat, pasos_lat + 1):
            for dc in range(-pasos_lon, pasos_lon + 1):
                for foco in self._celdas.get((fila + df, columna + dc), []):
                    if distancia_km(lat, lon, foco.lat, foco.lon) <= radio_km:
                        resultado.append(foco)
        return resultado


@dataclass(frozen=True)
class Emplazamiento:
    focos: int
    frp_p90: float


def _celda_emplazamiento(lat: float, lon: float) -> str:
    return f"{math.floor(lat / CELDA)},{math.floor(lon / CELDA)}"


def resumir_sitios(
    potencias: dict[str, dict[str, list[float]]],
) -> dict[str, dict[str, Emplazamiento]]:
    """Por celda de 0,01° y por instrumento, los focos del año y el percentil 90 de su
    potencia."""
    resultado: dict[str, dict[str, Emplazamiento]] = {}
    for celda, por_instrumento in potencias.items():
        resultado[celda] = {}
        for instrumento, lista in por_instrumento.items():
            ordenadas = sorted(lista)
            p90 = ordenadas[min(len(ordenadas) - 1, int(PERCENTIL_EMPLAZAMIENTO * len(ordenadas)))]
            resultado[celda][instrumento] = Emplazamiento(len(lista), p90)
    return resultado


def emplazamientos(focos: Iterable[Foco]) -> dict[str, dict[str, Emplazamiento]]:
    potencias: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    for foco in focos:
        potencias[_celda_emplazamiento(foco.lat, foco.lon)][foco.instrumento].append(foco.frp)
    return resumir_sitios(potencias)


def en_emplazamiento(foco: Foco, sitios: dict[str, dict[str, Emplazamiento]]) -> bool:
    """Como proceso.focos_termicos.cuenta_con_emplazamiento con las celdas del año: el foco cae en
    un sitio con FOCOS_EMPLAZAMIENTO o más focos (en su celda o en las vecinas, a la distancia
    de un sitio habitual) y su potencia no pasa de FACTOR_FRP veces el percentil 90 del sitio."""
    pasos = math.ceil(DISTANCIA_HABITUAL_KM[foco.instrumento] / 111.0 / CELDA)
    fila, columna = math.floor(foco.lat / CELDA), math.floor(foco.lon / CELDA)
    total = 0
    referencias: list[float] = []
    for df in range(-pasos, pasos + 1):
        for dc in range(-pasos * 2, pasos * 2 + 1):
            sitio = sitios.get(f"{fila + df},{columna + dc}")
            if sitio is None:
                continue
            for instrumento, datos in sitio.items():
                total += datos.focos
                if instrumento == foco.instrumento:
                    referencias.append(datos.frp_p90)
            if not any(i == foco.instrumento for i in sitio):
                referencias += [d.frp_p90 for d in sitio.values()]
    if total < FOCOS_EMPLAZAMIENTO:
        return False
    return foco.frp <= FACTOR_FRP * (max(referencias) if referencias else 0.0)


def habitual(foco: Foco, base: Indice) -> bool:
    """Como proceso.focos_termicos.cuenta: en un sitio que ya ardía en los 30 días anteriores
    y sin potencia anómala."""
    radio = max(DISTANCIA_HABITUAL_KM.values())
    cerca = [
        b
        for b in base.cerca(foco.lat, foco.lon, radio)
        if distancia_km(foco.lat, foco.lon, b.lat, b.lon)
        <= max(DISTANCIA_HABITUAL_KM[foco.instrumento], DISTANCIA_HABITUAL_KM[b.instrumento])
    ]
    if not cerca:
        return False
    mismo = [b.frp for b in cerca if b.instrumento == foco.instrumento]
    return foco.frp <= FACTOR_FRP * max(mismo or [b.frp for b in cerca])


def frecuente(foco: Foco, base: Indice) -> bool:
    """Como proceso.focos_termicos.fuego_frecuente alrededor del foco."""
    alrededor = [f for f in base.cerca(foco.lat, foco.lon, RADIO_FRECUENTE_KM) if not _es_baja(f)]
    dias = {f.instante.date() for f in alrededor}
    celdas = {(round(f.lat, 2), round(f.lon, 2)) for f in alrededor}
    return len(dias) >= DIAS_FUEGO_FRECUENTE and len(celdas) >= CELDAS_FUEGO_FRECUENTE


@dataclass(frozen=True)
class ImpactoCercano:
    id: str
    lat: float
    lon: float
    radio_km: float
    publicado: datetime


def impactos_recientes(publicacion: Documento, desde: datetime) -> list[ImpactoCercano]:
    """Impactos con lugar publicados desde `desde` que el cruce con FIRMS evalúa."""
    resultado = []
    for impacto in publicacion.get("impactos", []):
        if not impactos_guerra.con_firms(impacto):
            continue
        publicado = datetime.fromisoformat(impacto["fecha"]["valor"].replace("Z", "+00:00"))
        if publicado < desde:
            continue
        lugar = impacto["lugar"]
        resultado.append(
            ImpactoCercano(
                id=impacto["id"],
                lat=float(lugar["punto"]["lat"]),
                lon=float(lugar["punto"]["lon"]),
                radio_km=radio_busqueda(float(lugar["radio_km"])),
                publicado=publicado,
            )
        )
    return resultado


def coincide(foco: Foco, impactos: list[ImpactoCercano]) -> str | None:
    cercanos = [
        (distancia_km(foco.lat, foco.lon, i.lat, i.lon), i.id)
        for i in impactos
        if abs(foco.instante - i.publicado) <= VENTANA_IMPACTO
        and distancia_km(foco.lat, foco.lon, i.lat, i.lon) <= i.radio_km
    ]
    return min(cercanos)[1] if cercanos else None


@dataclass
class Resumen:
    leidos: int = 0
    baja_confianza: int = 0
    habituales: int = 0
    emplazamiento: int = 0
    frecuentes: int = 0
    publicados: int = 0
    coinciden: int = 0


def seleccionar(
    recientes: list[Foco],
    base: Indice,
    sitios: dict[str, dict[str, Emplazamiento]],
    impactos: list[ImpactoCercano],
) -> tuple[list[tuple[Foco, str | None]], Resumen]:
    resumen = Resumen(leidos=len(recientes))
    elegidos = []
    for foco in recientes:
        if _es_baja(foco):
            resumen.baja_confianza += 1
        elif habitual(foco, base):
            resumen.habituales += 1
        elif en_emplazamiento(foco, sitios):
            resumen.emplazamiento += 1
        elif frecuente(foco, base):
            resumen.frecuentes += 1
        else:
            impacto = coincide(foco, impactos)
            resumen.coinciden += impacto is not None
            elegidos.append((foco, impacto))
    resumen.publicados = len(elegidos)
    return elegidos, resumen


CODIGO_SATELITE = {"Suomi NPP": "N", "NOAA-20": "N20", "NOAA-21": "N21", "Terra": "T", "Aqua": "A"}


def documento(
    elegidos: list[tuple[Foco, str | None]], ahora: datetime, desde: datetime, resumen: Resumen
) -> Documento:
    """El fichero público: por foco [lon, lat, hora UTC «AAAA-MM-DDTHH:MMZ», satélite, impacto
    con el que coincide o null]."""
    ordenados = sorted(elegidos, key=lambda par: (par[0].instante, par[0].lat, par[0].lon))
    ultimo = max((f.instante for f, _ in elegidos), default=None)
    return {
        "generado": ahora.strftime("%Y-%m-%dT%H:%MZ"),
        "desde": desde.strftime("%Y-%m-%dT%H:%MZ"),
        "ultimo_foco": None if ultimo is None else ultimo.strftime("%Y-%m-%dT%H:%MZ"),
        "fuente": "NASA FIRMS (VIIRS y MODIS, tiempo casi real)",
        "atribucion": "NASA FIRMS (https://firms.modaps.eosdis.nasa.gov)",
        "zona": {
            "oeste": firms.CAJA.oeste,
            "sur": firms.CAJA.sur,
            "este": firms.CAJA.este,
            "norte": firms.CAJA.norte,
        },
        "descartados": {
            "baja_confianza": resumen.baja_confianza,
            "fuentes_habituales": resumen.habituales + resumen.emplazamiento,
            "fuego_frecuente": resumen.frecuentes,
        },
        "focos": [
            [
                round(f.lon, 3),
                round(f.lat, 3),
                f.instante.strftime("%Y-%m-%dT%H:%MZ"),
                CODIGO_SATELITE.get(f.satelite, f.satelite),
                impacto,
            ]
            for f, impacto in ordenados
        ],
    }


class Territorio:
    """Ucrania y la Rusia europea: los polígonos de las regiones de la web."""

    def __init__(self, rutas: Iterable[Path] = REGIONES) -> None:
        self.poligonos = [p for ruta in rutas for p in fronteras.poligonos_geojson(ruta)]

    def contiene(self, lat: float, lon: float) -> bool:
        return any(p.contiene(lon, lat) for p in self.poligonos)


def _focos_de_dias(datos: firms.Datos, dias: Iterable[date]) -> list[Foco]:
    resultado: list[Foco] = []
    for dia in dias:
        resultado += datos.focos(dia) or []
    return resultado


def _dias(desde: date, hasta: date) -> list[date]:
    return [desde + timedelta(days=k) for k in range((hasta - desde).days + 1)]


def cargar_emplazamientos(
    directorio: Path, datos_firms: firms.Datos, hoy: date
) -> dict[str, dict[str, Emplazamiento]]:
    """El resumen del año anterior a los 30 días de base, de la caché del día o calculándolo."""
    ruta = directorio / f"emplazamientos-{hoy.isoformat()}.json.gz"
    if ruta.exists():
        crudo: dict[str, dict[str, list[float]]] = json.loads(gzip.decompress(ruta.read_bytes()))
        return {
            c: {i: Emplazamiento(int(v[0]), float(v[1])) for i, v in s.items()}
            for c, s in crudo.items()
        }
    hasta = hoy - timedelta(days=DIAS_BASE + 1)
    desde = hoy - timedelta(days=DIAS_ANIO)
    # Día a día, sin guardar los focos: solo las potencias por celda.
    acumulado: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    anual = firms.Datos(datos_firms.directorio)
    for dia in _dias(desde, hasta):
        for foco in anual.focos(dia) or []:
            acumulado[_celda_emplazamiento(foco.lat, foco.lon)][foco.instrumento].append(foco.frp)
    sitios = resumir_sitios(acumulado)
    directorio.mkdir(parents=True, exist_ok=True)
    for viejo in directorio.glob("emplazamientos-*.json.gz"):
        viejo.unlink()
    crudo_salida = {c: {i: [e.focos, e.frp_p90] for i, e in s.items()} for c, s in sitios.items()}
    ruta.write_bytes(
        gzip.compress(json.dumps(crudo_salida, separators=(",", ":")).encode(), 6, mtime=0)
    )
    return sitios


Subir = Callable[[str, bytes, str, str], bool]


def generar(
    datos_firms: firms.Datos,
    directorio: Path,
    publicacion: Documento,
    ahora: datetime,
    territorio: Territorio | None = None,
) -> tuple[Documento, Resumen]:
    territorio = territorio or Territorio()
    desde = ahora - timedelta(hours=HORAS)
    recientes = [
        f
        for f in _focos_de_dias(datos_firms, _dias(desde.date(), ahora.date()))
        if desde <= f.instante <= ahora
        and firms.CAJA.contiene(f.lat, f.lon)
        and territorio.contiene(f.lat, f.lon)
    ]
    inicio_base = desde - timedelta(days=DIAS_BASE)
    base = Indice(
        f
        for f in _focos_de_dias(datos_firms, _dias(inicio_base.date(), desde.date()))
        if inicio_base <= f.instante < desde
    )
    sitios = cargar_emplazamientos(directorio, datos_firms, ahora.date())
    impactos = impactos_recientes(publicacion, desde - VENTANA_IMPACTO)
    elegidos, resumen = seleccionar(recientes, base, sitios, impactos)
    return documento(elegidos, ahora, desde, resumen), resumen


def principal(argumentos: list[str] | None = None) -> int:
    from recogida.satelite import subida_al_almacen

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    opciones = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    opciones.add_argument("orden", choices=["generar"])
    opciones.add_argument("--sin-subir", action="store_true")
    opciones.add_argument("--registro", type=Path)
    args = opciones.parse_args(argumentos)
    inicio = time.monotonic()
    ahora = datetime.now(UTC)
    directorio = Path(os.environ.get(VARIABLE_DATOS) or DATOS)
    directorio.mkdir(parents=True, exist_ok=True)
    datos_firms = firms.Datos(firms.directorio_datos())
    publicacion: Documento = (
        json.loads(PUBLICACION.read_text(encoding="utf-8")) if PUBLICACION.exists() else {}
    )
    publico, resumen = generar(datos_firms, directorio, publicacion, ahora)
    cuerpo = json.dumps(publico, ensure_ascii=False, separators=(",", ":")).encode()
    (directorio / "ultimas24h.json").write_bytes(cuerpo)
    subido = args.sin_subir or subida_al_almacen(os.environ)(
        OBJETO, cuerpo, "application/json", CACHE
    )
    duracion = time.monotonic() - inicio
    registro.info(
        "focos en vivo: %d leídos, %d publicados (%d coinciden con un impacto); fuera: %d de baja "
        "confianza, %d de fuentes habituales, %d de emplazamientos, %d de fuego frecuente; "
        "%d bytes; último foco %s; %.0f s",
        resumen.leidos,
        resumen.publicados,
        resumen.coinciden,
        resumen.baja_confianza,
        resumen.habituales,
        resumen.emplazamiento,
        resumen.frecuentes,
        len(cuerpo),
        publico["ultimo_foco"],
        duracion,
    )
    if args.registro is not None and subido:
        args.registro.write_text(
            json.dumps({"ultima": publico["generado"], "ultimo_foco": publico["ultimo_foco"]})
            + "\n",
            encoding="utf-8",
            newline="\n",
        )
    return 0 if subido else 1


if __name__ == "__main__":
    sys.exit(principal())
