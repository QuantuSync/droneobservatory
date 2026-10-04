"""Imagen de satélite de antes y después de cada instalación alcanzada (Sentinel-2).

Para cada impacto con lugar de la capa de guerra con foco térmico detectado y para cada impacto
en una instalación, la última imagen óptica de Sentinel-2 sin nubes anterior al ataque y la
primera sin nubes posterior, recortadas sobre el sitio, en color natural.

**Acceso, sin cuenta.** El catálogo STAC público de Earth Search (Element 84,
`earth-search.aws.element84.com/v1`, colección `sentinel-2-l2a`) da las escenas del nivel 2A y
la dirección de cada banda en el archivo abierto de Sentinel-2 en AWS (`sentinel-cogs`, GeoTIFF
optimizado para la nube). Se lee solo la ventana del recorte de cada banda
(`recogida/cog.py`): la clasificación de escena (SCL, 20 m) y el color natural (TCI, 10 m).
Comprobado el 3 de octubre de 2026. Los datos de Copernicus Sentinel son de acceso libre y
gratuito; lo que se publica derivado de ellos lleva «Contains modified Copernicus Sentinel data
<año>» (ATRIBUCION).

**Selección por nubes sobre el recorte.** De cada escena candidata se lee primero la SCL de la
ventana del recorte; la escena vale si en el recorte hay como mucho un 2 % de píxeles sin dato y
como mucho un 3 % de nube (probabilidad media o alta), cirro o sombra de nube. La cobertura de
nubes de la escena entera no decide nada: una escena muy nublada puede tener el recorte limpio.
La imagen de antes es la más reciente que vale entre 180 días antes y el inicio del ataque; la
de después, la primera que vale desde la publicación del impacto. Si aún no hay ninguna
posterior, la pareja queda a medias y cada ejecución busca solo en las escenas nuevas.

**Imagen.** El color natural (TCI) ya viene con el ajuste fijo de la ESA; a las dos imágenes de
una pareja (y a todas) se les aplica además la misma curva fija (AJUSTE_GAMMA), que aclara los
tonos medios sin tocar los extremos. JPEG de calidad 85 sin metadatos, a 10 m por píxel.

**Salida.** Las imágenes, en el almacén público (`satelite/<impacto>/<antes|despues>-<fecha>-
<escena>.jpg`, inmutables), y el índice `satelite/parejas.json` con, por impacto, el centro y el
lado del recorte y de cada imagen la fecha, la escena, el objeto y las nubes medidas en el
recorte; la web lo lee al abrir la ficha de un impacto. En `<datos>/` (`EODI_SATELITE_DATOS`),
`control.json` (lo buscado) y una copia del índice.

Lo lanza `servidor/satelite.sh` con su propio temporizador y cerrojo; lee la base de la rama
estado sin tomar el cerrojo de la recogida horaria, como el motor de deducción.
"""

import argparse
import io
import json
import logging
import math
import os
import sys
import time
import urllib.request
from collections.abc import Callable, Iterable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

import numpy as np
import numpy.typing as npt
from PIL import Image

from almacen import cifrado, remoto
from almacen.base import Almacen
from esquema import Documento
from proceso import cambio
from proceso.focos_termicos import distancia_km
from recogida import almacen_publico, cog
from recogida.descarga import AGENTE_EODI
from recogida.rango import Lector, LecturaFallida

registro = logging.getLogger("recogida.satelite")

STAC = "https://earth-search.aws.element84.com/v1/search"
COLECCION = "sentinel-2-l2a"
ATRIBUCION = "Contains modified Copernicus Sentinel data {anios}"
VARIABLE_DATOS = "EODI_SATELITE_DATOS"
DATOS = Path.home() / "datos" / "satelite"
CONTROL = "control.json"
PREFIJO = "satelite"
INDICE = f"{PREFIJO}/parejas.json"
CACHE_IMAGEN = "public, max-age=31536000, immutable"
CACHE_INDICE = "public, max-age=300"

# Clases de la SCL de Sentinel-2 L2A que tapan el suelo o no tienen dato.
SIN_DATO = 0
DEFECTUOSO = 1
SOMBRA_NUBE = 3
NUBE_MEDIA, NUBE_ALTA, CIRRO = 8, 9, 10
CLASES_NUBE = frozenset({SOMBRA_NUBE, NUBE_MEDIA, NUBE_ALTA, CIRRO})
MAXIMO_NUBE = 0.03
MAXIMO_SIN_DATO = 0.02
# Cuánto se busca hacia atrás la imagen de antes y cuántas escenas se miran por búsqueda.
DIAS_ANTES = 180
# Plazo para hallar, después del ataque, una imagen despejada en la que se vea el cambio (el humo
# o una nube fina pueden taparlo el primer día).
PLAZO_CAMBIO_DIAS = 15
CANDIDATAS = 40
# Escenas enteramente cubiertas no se miran: ni un píxel útil.
NUBES_ESCENA_MAXIMA = 99.5
CALIDAD_JPEG = 85
AJUSTE_GAMMA = 1.25
# Lado del recorte por tipo de instalación, en metros: que entre la instalación entera.
LADO_M = {
    "refineria": 4000,
    "puerto": 4000,
    "aerodromo": 4000,
    "deposito_combustible": 2500,
    "industrial": 2500,
    "central": 2500,
    "subestacion": 1500,
    "ferrocarril": 2000,
    "militar": 3000,
}
LADO_DEFECTO_M = 3000
LADO_MAXIMO_M = 6000
# Margen alrededor de la instalación y de sus focos cuando no coinciden.
MARGEN_FOCOS_M = 2000
# Tope de tiempo por ejecución: lo que no cabe sigue en la siguiente.
TOPE_S = 40 * 60

Buscador = Callable[[Documento], Documento]


# --- Selección ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Medida:
    nubes: float
    sin_dato: float

    @property
    def despejada(self) -> bool:
        return self.nubes <= MAXIMO_NUBE and self.sin_dato <= MAXIMO_SIN_DATO


def medir_nubes(scl: npt.NDArray[np.uint8]) -> Medida:
    """Fracción de nube (y sombra, cirro) y de píxeles sin dato en el recorte de la SCL."""
    total = scl.size
    if total == 0:
        return Medida(1.0, 1.0)
    sin_dato = int(np.count_nonzero((scl == SIN_DATO) | (scl == DEFECTUOSO)))
    nubes = int(np.count_nonzero(np.isin(scl, list(CLASES_NUBE))))
    return Medida(nubes / total, sin_dato / total)


def ajustar(tci: npt.NDArray[np.uint8]) -> npt.NDArray[np.uint8]:
    """La misma curva fija para todas las imágenes: aclara los tonos medios."""
    tabla = np.array(
        [round(255 * (v / 255) ** (1 / AJUSTE_GAMMA)) for v in range(256)], dtype=np.uint8
    )
    return tabla[tci]


def jpeg(rgb: npt.NDArray[np.uint8]) -> bytes:
    salida = io.BytesIO()
    Image.fromarray(rgb, "RGB").save(
        salida, "JPEG", quality=CALIDAD_JPEG, optimize=True, progressive=True
    )
    return salida.getvalue()


# --- Escenas -----------------------------------------------------------------------------


@dataclass(frozen=True)
class Escena:
    id: str
    fecha: datetime
    epsg: int
    tci: str
    scl: str
    nubes_escena: float
    # Infrarrojo cercano estrecho (B8A) y de onda corta (B12), 20 m: el índice de quemado.
    b8a: str = ""
    b12: str = ""


def _instante(texto: str) -> datetime:
    return datetime.fromisoformat(texto.replace("Z", "+00:00")).astimezone(UTC)


def _texto(momento: datetime) -> str:
    return momento.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def escena_de_item(item: Documento) -> Escena | None:
    propiedades = item.get("properties", {})
    activos = item.get("assets", {})
    codigo = propiedades.get("proj:epsg") or str(propiedades.get("proj:code", "")).split(":")[-1]
    try:
        epsg = int(codigo)
        return Escena(
            id=str(item["id"]),
            fecha=_instante(str(propiedades["datetime"])),
            epsg=epsg,
            tci=str(activos["visual"]["href"]),
            scl=str(activos["scl"]["href"]),
            nubes_escena=float(propiedades.get("eo:cloud_cover", 0.0)),
            b8a=str(activos.get("nir08", {}).get("href", "")),
            b12=str(activos.get("swir22", {}).get("href", "")),
        )
    except (KeyError, ValueError, TypeError):
        return None


def consulta(
    lat: float, lon: float, desde: datetime, hasta: datetime, recientes: bool
) -> Documento:
    return {
        "collections": [COLECCION],
        "intersects": {"type": "Point", "coordinates": [lon, lat]},
        "datetime": f"{_texto(desde)}/{_texto(hasta)}",
        "limit": CANDIDATAS,
        "sortby": [{"field": "properties.datetime", "direction": "desc" if recientes else "asc"}],
        "query": {"eo:cloud_cover": {"lt": NUBES_ESCENA_MAXIMA}},
    }


def buscador_http(lector: Lector) -> Buscador:
    """POST al catálogo STAC (con la identificación del observatorio)."""

    def buscar(cuerpo: Documento) -> Documento:
        datos = json.dumps(cuerpo).encode()
        espera = 2.0
        for intento in range(3):
            if intento:
                time.sleep(espera)
                espera *= 2
            peticion = urllib.request.Request(
                STAC,
                data=datos,
                method="POST",
                headers={"Content-Type": "application/json", "User-Agent": AGENTE_EODI},
            )
            try:
                with urllib.request.urlopen(peticion, timeout=60) as respuesta:
                    contenido = respuesta.read()
                    lector.bytes += len(contenido)
                    resultado: Documento = json.loads(contenido)
                    return resultado
            except (OSError, ValueError):
                continue
        raise LecturaFallida("catálogo STAC sin respuesta")

    return buscar


def escenas(buscar: Buscador, cuerpo: Documento) -> list[Escena]:
    """Escenas de la búsqueda, sin repetir fecha y tesela (el catálogo da a veces dos
    procesados de la misma toma)."""
    vistas: set[str] = set()
    resultado = []
    for item in buscar(cuerpo).get("features", []):
        escena = escena_de_item(item)
        if escena is None:
            continue
        clave = escena.id.rsplit("_", 2)[0]
        if clave in vistas:
            continue
        vistas.add(clave)
        resultado.append(escena)
    return resultado


# --- Recortes ----------------------------------------------------------------------------


@dataclass(frozen=True)
class Recorte:
    lat: float
    lon: float
    lado_m: int

    def caja(self, epsg: int) -> tuple[float, float, float, float]:
        huso, norte = cog.zona_utm(epsg)
        x, y = cog.a_utm(self.lat, self.lon, huso, norte)
        medio = self.lado_m / 2
        return x - medio, y - medio, x + medio, y + medio


def leer_banda(lector: Lector, url: str, recorte: Recorte, epsg: int) -> npt.NDArray[np.uint8]:
    leer = lector.rango(url)
    cabecera = cog.leer_cabecera(leer)
    columna, fila, ancho, alto = cog.ventana_de_caja(cabecera, *recorte.caja(epsg))
    return cog.leer_ventana(leer, cabecera, columna, fila, ancho, alto)


def rejilla(recorte: Recorte, paso_m: float) -> tuple[npt.NDArray[np.float64], ...]:
    """Latitudes y longitudes de los centros de una rejilla norte arriba de `paso_m` metros que
    cubre el recorte (aproximación local; error de centímetros en unos kilómetros)."""
    n = round(recorte.lado_m / paso_m)
    desplazamientos = (np.arange(n) + 0.5) * paso_m - recorte.lado_m / 2
    norte, este = np.meshgrid(-desplazamientos, desplazamientos, indexing="ij")
    metros_por_grado = 111_320.0
    lat = recorte.lat + norte / metros_por_grado
    lon = recorte.lon + este / (metros_por_grado * math.cos(math.radians(recorte.lat)))
    return lat, lon


def en_rejilla(
    lector: Lector, url: str, recorte: Recorte, epsg: int, paso_m: float = 10.0
) -> npt.NDArray[Any]:
    """La banda de una escena llevada a la rejilla común del recorte (vecino más cercano): así
    se comparan dos fechas aunque sus escenas estén en husos UTM distintos."""
    lat, lon = rejilla(recorte, paso_m)
    huso_utm, norte = cog.zona_utm(epsg)
    x, y = cog.a_utm_matriz(lat, lon, huso_utm, norte)
    leer = lector.rango(url)
    cabecera = cog.leer_cabecera(leer)
    margen = 2 * max(cabecera.paso_x, cabecera.paso_y)
    columna, fila, ancho, alto = cog.ventana_de_caja(
        cabecera,
        float(x.min()) - margen,
        float(y.min()) - margen,
        float(x.max()) + margen,
        float(y.max()) + margen,
    )
    ventana = cog.leer_ventana(leer, cabecera, columna, fila, ancho, alto)
    columnas = np.clip(((x - cabecera.x0) / cabecera.paso_x).astype(int) - columna, 0, ancho - 1)
    filas = np.clip(((cabecera.y0 - y) / cabecera.paso_y).astype(int) - fila, 0, alto - 1)
    resultado: npt.NDArray[Any] = ventana[filas, columnas]
    return resultado


def huso(escena: str) -> str:
    """Huso UTM de una escena por su tesela MGRS («S2C_37TDJ_…» → «37»)."""
    partes = escena.split("_")
    return partes[1][:2] if len(partes) > 1 else ""


def mismo_huso_primero(candidatas: list[Escena], antes: str) -> list[Escena]:
    """Una misma toma puede caer en teselas de dos husos UTM; de las de un mismo día va primero
    la del huso de la imagen de antes, para que las dos no queden giradas entre sí."""
    preferido = huso(antes)
    # Las candidatas de la imagen de después van de la más antigua a la más reciente.
    return sorted(candidatas, key=lambda e: (e.fecha.date(), huso(e.id) != preferido))


def primera_despejada(
    lector: Lector, candidatas: Iterable[Escena], recorte: Recorte
) -> tuple[Escena, Medida] | None:
    for escena in candidatas:
        try:
            scl = leer_banda(lector, escena.scl, recorte, escena.epsg)[:, :, 0]
        except (LecturaFallida, cog.CogInvalido) as error:
            registro.info("%s: SCL no legible (%s)", escena.id, error)
            continue
        medida = medir_nubes(scl)
        if medida.despejada:
            return escena, medida
    return None


# --- Impactos ----------------------------------------------------------------------------


@dataclass(frozen=True)
class Objetivo:
    """Un impacto con su recorte y las fechas de su búsqueda."""

    id: str
    recorte: Recorte
    antes_hasta: datetime
    despues_desde: datetime
    foco: bool
    # Nombre del lugar alcanzado, para la lista de la web.
    lugar: str = ""


def _centroide(focos: list[Documento]) -> tuple[float, float]:
    return (
        sum(float(f["lat"]) for f in focos) / len(focos),
        sum(float(f["lon"]) for f in focos) / len(focos),
    )


def objetivo_de_impacto(
    impacto: Documento,
    periodo: tuple[datetime, datetime],
    detectado: bool,
    focos: list[Documento],
) -> Objetivo | None:
    """El impacto como objetivo si tiene foco detectado o está en una instalación. El recorte se
    centra en los focos que contaron (lo que ardió) o, sin foco, en la instalación. `periodo` es
    la ventana del impacto que usa también el cruce con FIRMS
    (proceso.impactos_guerra.periodo_del_impacto): la imagen de antes es anterior a su inicio y
    la de después, posterior a su fin y a la publicación."""
    lugar = impacto["lugar"]
    instalacion = lugar.get("nivel") == "instalacion"
    if not detectado and not instalacion:
        return None
    punto = lugar["punto"]
    lat, lon = float(punto["lat"]), float(punto["lon"])
    lado = LADO_M.get(str(lugar.get("categoria")), LADO_DEFECTO_M) if instalacion else 3000
    if detectado and focos:
        lat_f, lon_f = _centroide(focos)
        if instalacion:
            # Que se vean la instalación y lo que ardió: el punto medio, con lado de sobra.
            separacion = distancia_km(lat, lon, lat_f, lon_f) * 1000
            lat, lon = (lat + lat_f) / 2, (lon + lon_f) / 2
            lado = max(lado, round(separacion) + MARGEN_FOCOS_M)
        else:
            lat, lon = lat_f, lon_f
    lado = min(lado, LADO_MAXIMO_M)
    inicio, fin = periodo
    publicado = _instante(impacto["fecha"]["valor"])
    return Objetivo(
        id=str(impacto["id"]),
        recorte=Recorte(round(lat, 5), round(lon, 5), lado),
        antes_hasta=inicio,
        despues_desde=max(fin, publicado),
        foco=detectado,
        lugar=str(lugar.get("nombre") or ""),
    )


def ordenar(objetivos: Iterable[Objetivo]) -> list[Objetivo]:
    """Primero los que tienen foco detectado, después el resto de instalaciones; dentro, del
    más reciente al más antiguo."""
    return sorted(objetivos, key=lambda o: (not o.foco, -o.despues_desde.timestamp(), o.id))


# --- Ejecución ---------------------------------------------------------------------------


def _imagen(escena: Escena, medida: Medida) -> Documento:
    return {
        "fecha": _texto(escena.fecha),
        "escena": escena.id,
        "nubes_recorte": round(medida.nubes, 4),
    }


@dataclass
class Resumen:
    publicadas: int = 0
    sin_cambio: int = 0
    buscando: int = 0
    sin_antes: int = 0
    nuevas: int = 0
    retiradas: int = 0
    pendientes: int = 0

    def texto(self) -> str:
        return (
            f"{self.publicadas} parejas con cambio publicadas, {self.sin_cambio} sin cambio "
            f"visible, {self.buscando} buscando aún la imagen posterior con cambio, "
            f"{self.sin_antes} sin imagen anterior despejada, {self.nuevas} publicadas en esta "
            f"ejecución, {self.retiradas} imágenes retiradas, {self.pendientes} impactos para la "
            "ejecución siguiente"
        )


Subir = Callable[[str, bytes, str, str], bool]
Borrar = Callable[[str], bool]


def escena_por_id(buscar: Buscador, id_: str) -> Escena | None:
    hallada = escenas(buscar, {"collections": [COLECCION], "ids": [id_], "limit": 1})
    return hallada[0] if hallada else None


def bandas(lector: Lector, escena: Escena, recorte: Recorte) -> cambio.Bandas:
    """Una fecha en la rejilla común del recorte: SCL, B8A, B12 y color natural."""

    def leer(url: str) -> npt.NDArray[Any]:
        return en_rejilla(lector, url, recorte, escena.epsg, cambio.PASO_M)

    return cambio.Bandas(
        scl=leer(escena.scl)[:, :, 0],
        b8a=leer(escena.b8a)[:, :, 0],
        b12=leer(escena.b12)[:, :, 0],
        rgb=leer(escena.tci)[:, :, :3],
    )


def medir_cambio(
    lector: Lector, antes: Escena, despues: Escena, recorte: Recorte
) -> tuple[cambio.Cambio, cambio.Bandas, cambio.Bandas]:
    a, d = bandas(lector, antes, recorte), bandas(lector, despues, recorte)
    lado = a.scl.shape[0]
    return cambio.medir(a, d, (lado / 2, lado / 2)), a, d


def reencuadrado(recorte: Recorte, medida: cambio.Cambio) -> Recorte:
    """El recorte centrado en la mancha, si hace falta (cambio.Cambio.reencuadre)."""
    nuevo = medida.reencuadre()
    if nuevo is None:
        return recorte
    fila, columna, lado_px = nuevo
    medio = medida.lado / 2
    metros_por_grado = 111_320.0
    lat = recorte.lat + (medio - fila) * cambio.PASO_M / metros_por_grado
    lon = recorte.lon + (columna - medio) * cambio.PASO_M / (
        metros_por_grado * math.cos(math.radians(recorte.lat))
    )
    lado_m = int(round(lado_px * cambio.PASO_M / 100) * 100)
    return Recorte(round(lat, 5), round(lon, 5), lado_m)


def _objetos(entrada: Documento) -> list[str]:
    return [
        str(entrada[lado]["objeto"])
        for lado in ("antes", "despues")
        if isinstance(entrada.get(lado), dict) and entrada[lado].get("objeto")
    ]


def procesar(
    objetivo: Objetivo,
    control: Documento,
    buscar: Buscador,
    lector: Lector,
    subir: Subir,
    ahora: datetime,
    borrar: Borrar | None = None,
) -> Documento:
    """Completa la pareja de un impacto y devuelve su entrada de control. La imagen de antes es
    la última despejada anterior al ataque; la de después, la primera despejada posterior en la
    que se ve un cambio en la zona del impacto (proceso/cambio.py), buscada durante
    PLAZO_CAMBIO_DIAS. Solo una pareja con cambio se sube al almacén, en la rejilla común (las
    dos imágenes alineadas) y reencuadrada en la mancha si hace falta; lo publicado antes de
    una pareja sin cambio se retira."""
    entrada: Documento = dict(control)
    recorte = objetivo.recorte
    actual = {"lat": recorte.lat, "lon": recorte.lon, "lado_m": recorte.lado_m}
    if entrada.get("recorte") != actual:
        entrada = {}
    entrada["recorte"] = actual
    entrada["foco"] = objetivo.foco
    if objetivo.lugar:
        entrada["lugar"] = objetivo.lugar
    if entrada.get("cambio") or entrada.get("sin_cambio"):
        return entrada
    # Lo publicado sin medir (las primeras parejas) se mide como una escena más de después.
    retirar = _objetos(entrada)
    previa = entrada.get("despues")
    if isinstance(previa, dict):
        entrada.pop("despues", None)
        if isinstance(entrada.get("antes"), dict):
            entrada["antes"].pop("objeto", None)
    if entrada.get("antes") is None and not entrada.get("antes_buscado"):
        cuerpo = consulta(
            recorte.lat,
            recorte.lon,
            objetivo.antes_hasta - timedelta(days=DIAS_ANTES),
            objetivo.antes_hasta,
            recientes=True,
        )
        hallada = primera_despejada(lector, escenas(buscar, cuerpo), recorte)
        entrada["antes_buscado"] = True
        if hallada is not None:
            entrada["antes"] = _imagen(*hallada)
    antes_doc = entrada.get("antes")
    if not isinstance(antes_doc, dict):
        return entrada
    antes = escena_por_id(buscar, str(antes_doc["escena"]))
    if antes is None:
        return entrada
    limite = objetivo.despues_desde + timedelta(days=PLAZO_CAMBIO_DIAS)
    desde = objetivo.despues_desde
    if entrada.get("despues_buscado_hasta"):
        desde = max(desde, _instante(str(entrada["despues_buscado_hasta"])))
    revisadas = set(entrada.get("revisadas", []))
    candidatas: list[Escena] = []
    if isinstance(previa, dict) and str(previa["escena"]) not in revisadas:
        escena_previa = escena_por_id(buscar, str(previa["escena"]))
        if escena_previa is not None:
            candidatas.append(escena_previa)
    hasta = min(ahora, limite)
    if desde < hasta:
        candidatas += mismo_huso_primero(
            escenas(buscar, consulta(recorte.lat, recorte.lon, desde, hasta, recientes=False)),
            antes.id,
        )
    for escena in candidatas:
        if escena.id in revisadas:
            continue
        hallada = primera_despejada(lector, [escena], recorte)
        if hallada is None:
            continue
        revisadas.add(escena.id)
        medida, _, _ = medir_cambio(lector, antes, escena, recorte)
        entrada["medida"] = {
            "escena": escena.id,
            "principal": medida.principal,
            "dentro": medida.dentro,
            "fuera": medida.fuera,
        }
        if not medida.pasa:
            continue
        # Encuadre en la mancha y las dos imágenes en la rejilla común.
        final = reencuadrado(recorte, medida)
        if final != recorte:
            medida, _, _ = medir_cambio(lector, antes, escena, final)
        a = bandas(lector, antes, final)
        d = bandas(lector, escena, final)
        subidas = {}
        for lado, imagen, bandas_lado in (("antes", antes, a), ("despues", escena, d)):
            objeto = (
                f"{PREFIJO}/{objetivo.id}/{lado}-{imagen.fecha:%Y%m%d}-{imagen.id}-"
                f"{final.lado_m}.jpg"
            )
            if not subir(objeto, jpeg(ajustar(bandas_lado.rgb)), "image/jpeg", CACHE_IMAGEN):
                return entrada
            subidas[lado] = objeto
        entrada["antes"] = {**antes_doc, "objeto": subidas["antes"]}
        entrada["despues"] = {**_imagen(escena, hallada[1]), "objeto": subidas["despues"]}
        entrada["cambio"] = {
            "hectareas": medida.zona_hectareas,
            "principal": medida.principal,
            "contorno": [list(p) for p in medida.contorno()],
            "recorte": {"lat": final.lat, "lon": final.lon, "lado_m": final.lado_m},
        }
        break
    entrada["revisadas"] = sorted(revisadas)
    if not entrada.get("cambio"):
        ultima = candidatas[-1].fecha if len(candidatas) >= CANDIDATAS else hasta
        entrada["despues_buscado_hasta"] = _texto(max(desde, ultima))
        if ahora >= limite:
            entrada["sin_cambio"] = True
    if borrar is not None:
        publicados = set(_objetos(entrada)) if entrada.get("cambio") else set()
        pendientes = []
        for objeto in retirar:
            if objeto not in publicados and not borrar(objeto):
                pendientes.append(objeto)
        if pendientes:
            entrada["retirar"] = pendientes
    return entrada


def indice(control: dict[str, Documento], ahora: datetime) -> Documento:
    """El índice público: solo las parejas en las que se ve un cambio, con su contorno."""
    parejas = {}
    for impacto, entrada in sorted(control.items()):
        hecho = entrada.get("cambio")
        if not hecho or not entrada.get("antes") or not entrada.get("despues"):
            continue
        parejas[impacto] = {
            "recorte": hecho["recorte"],
            "antes": entrada["antes"],
            "despues": entrada["despues"],
            "cambio": {"hectareas": hecho["hectareas"], "contorno": hecho["contorno"]},
            **({"lugar": entrada["lugar"]} if entrada.get("lugar") else {}),
        }
    anios = sorted(
        {img["fecha"][:4] for p in parejas.values() for img in (p["antes"], p["despues"])}
    )
    return {
        "generado": ahora.strftime("%Y-%m-%dT%H:%MZ"),
        "fuente": "Copernicus Sentinel-2 L2A (Earth Search, archivo abierto de AWS)",
        "atribucion": ATRIBUCION.format(anios="-".join(dict.fromkeys([anios[0], anios[-1]])))
        if anios
        else ATRIBUCION.format(anios=ahora.year),
        "parejas": parejas,
    }


def resumir(control: dict[str, Documento], resumen: Resumen) -> Resumen:
    for entrada in control.values():
        if entrada.get("cambio"):
            resumen.publicadas += 1
        elif entrada.get("sin_cambio"):
            resumen.sin_cambio += 1
        elif entrada.get("antes"):
            resumen.buscando += 1
        else:
            resumen.sin_antes += 1
    return resumen


def actualizar(
    objetivos: list[Objetivo],
    control: dict[str, Documento],
    buscar: Buscador,
    lector: Lector,
    subir: Subir,
    ahora: datetime,
    tope_s: float = TOPE_S,
    reloj: Callable[[], float] = time.monotonic,
    borrar: Borrar | None = None,
) -> Resumen:
    """Recorre los objetivos (los de foco primero) hasta el tope de tiempo. Lo que quedó por
    retirar del almacén se vuelve a intentar."""
    inicio = reloj()
    resumen = Resumen()
    for objetivo in ordenar(objetivos):
        anterior = control.get(objetivo.id, {})
        if objetivo.lugar and anterior and anterior.get("lugar") != objetivo.lugar:
            anterior = control[objetivo.id] = {**anterior, "lugar": objetivo.lugar}
        if borrar is not None and anterior.get("retirar"):
            quedan = [o for o in anterior["retirar"] if not borrar(o)]
            resumen.retiradas += len(anterior["retirar"]) - len(quedan)
            anterior = control[objetivo.id] = {**anterior, "retirar": quedan}
        if anterior.get("cambio") or anterior.get("sin_cambio"):
            continue
        if reloj() - inicio > tope_s:
            resumen.pendientes += 1
            continue
        try:
            entrada = procesar(objetivo, anterior, buscar, lector, subir, ahora, borrar)
        except (LecturaFallida, cog.CogInvalido) as error:
            registro.warning("%s: %s", objetivo.id, error)
            resumen.pendientes += 1
            continue
        if entrada.get("cambio") and not anterior.get("cambio"):
            resumen.nuevas += 1
        resumen.retiradas += len(_objetos(anterior)) - len(entrada.get("retirar", []))
        control[objetivo.id] = entrada
    return resumir(control, resumen)


# --- Objetivos desde la base ---------------------------------------------------------------


def objetivos_de_base(almacen: Almacen) -> list[Objetivo]:
    """Los impactos públicos con foco detectado o en una instalación, como los publica la web
    (exportacion.ucrania.impacto_publico): los retirados, unidos a otro o sin fuente pública no
    entran."""
    from exportacion.ucrania import impacto_publico
    from proceso import impactos_guerra
    from proceso.focos_termicos import DETECTADO

    focos = almacen.focos_termicos()
    ataques = {a["id"]: a for a in almacen.ataques_ucrania()}
    resultado = []
    for documento in almacen.impactos_guerra():
        detectado = focos.get(documento["id"], {}).get(
            "resultado"
        ) == DETECTADO and impactos_guerra.con_firms(documento)
        con_foco = {**documento, "foco_termico": focos[documento["id"]]} if detectado else documento
        if impacto_publico(con_foco) is None:
            continue
        casados = almacen.focos_casados(documento["id"]) if detectado else []
        objetivo = objetivo_de_impacto(
            documento, impactos_guerra.periodo_del_impacto(documento, ataques), detectado, casados
        )
        if objetivo is not None:
            resultado.append(objetivo)
    return resultado


OBJETIVOS = "objetivos.json"


def documento_de_objetivo(objetivo: Objetivo) -> Documento:
    return {
        "id": objetivo.id,
        "recorte": {
            "lat": objetivo.recorte.lat,
            "lon": objetivo.recorte.lon,
            "lado_m": objetivo.recorte.lado_m,
        },
        "antes_hasta": objetivo.antes_hasta.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "despues_desde": objetivo.despues_desde.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "foco": objetivo.foco,
        "lugar": objetivo.lugar,
    }


def objetivo_de_documento(documento: Documento) -> Objetivo:
    recorte = documento["recorte"]
    return Objetivo(
        id=str(documento["id"]),
        recorte=Recorte(float(recorte["lat"]), float(recorte["lon"]), int(recorte["lado_m"])),
        antes_hasta=_instante(str(documento["antes_hasta"])),
        despues_desde=_instante(str(documento["despues_desde"])),
        foco=bool(documento["foco"]),
        lugar=str(documento.get("lugar") or ""),
    )


def directorio_datos() -> Path:
    return Path(os.environ.get(VARIABLE_DATOS, DATOS))


def paso_horario(almacen: Almacen) -> None:
    """En la recogida horaria, que ya tiene la base abierta: deja los objetivos en
    `objetivos.json` para el temporizador de las imágenes, que así no carga la base (unos 640 MB
    descifrada). Nada de lo que falle aquí sale de esta función."""
    try:
        objetivos = objetivos_de_base(almacen)
        datos = directorio_datos()
        datos.mkdir(parents=True, exist_ok=True)
        _escribir(
            datos / OBJETIVOS,
            {
                "generado": datetime.now(UTC).strftime("%Y-%m-%dT%H:%MZ"),
                "objetivos": [documento_de_objetivo(o) for o in objetivos],
            },
        )
        registro.info("satélite: %d objetivos para las imágenes", len(objetivos))
    except Exception as error:
        registro.warning("objetivos de satélite no guardados: %s", str(error)[:300])


def cargar_objetivos(ruta: Path) -> list[Objetivo] | None:
    if not ruta.exists():
        return None
    documento = json.loads(ruta.read_text(encoding="utf-8"))
    return [objetivo_de_documento(d) for d in documento.get("objetivos", [])]


def _cargar_control(ruta: Path) -> dict[str, Documento]:
    if not ruta.exists():
        return {}
    datos: dict[str, Documento] = json.loads(ruta.read_text(encoding="utf-8"))
    return datos


def _escribir(ruta: Path, documento: Any) -> None:
    temporal = ruta.with_suffix(".tmp")
    with open(temporal, "w", encoding="utf-8", newline="\n") as fichero:
        json.dump(documento, fichero, ensure_ascii=False, indent=1, sort_keys=True)
    temporal.replace(ruta)


def subida_al_almacen(entorno: dict[str, str] | os._Environ[str]) -> Subir:
    almacen = almacen_publico.cargar()
    clave_id = entorno.get(almacen_publico.VARIABLE_ID, "")
    secreto = entorno.get(almacen_publico.VARIABLE_SECRETO, "")

    def subir(objeto: str, cuerpo: bytes, tipo: str, cache: str) -> bool:
        if not clave_id or not secreto:
            registro.warning("sin credenciales del almacén: no se sube %s", objeto)
            return False
        correcto, motivo = almacen_publico.subir(
            almacen, objeto, cuerpo, clave_id, secreto, tipo, cache
        )
        if not correcto:
            registro.warning("%s: %s", objeto, motivo)
        return correcto

    return subir


def borrado_del_almacen(entorno: dict[str, str] | os._Environ[str]) -> Borrar:
    almacen = almacen_publico.cargar()
    clave_id = entorno.get(almacen_publico.VARIABLE_ID, "")
    secreto = entorno.get(almacen_publico.VARIABLE_SECRETO, "")

    def borrar(objeto: str) -> bool:
        if not clave_id or not secreto:
            return False
        correcto, motivo = almacen_publico.borrar(almacen, objeto, clave_id, secreto)
        if not correcto:
            registro.warning("%s no retirado: %s", objeto, motivo)
        return correcto

    return borrar


@contextmanager
def _base(repositorio: str | None, local: Path | None) -> Iterator[Almacen]:
    """La base de la rama estado (o un db.age local), solo para leerla."""
    with TemporaryDirectory() as temporal:
        ruta = local
        if ruta is None:
            ruta = Path(temporal) / "db.age"
            if not remoto.descargar(ruta, repositorio or remoto.REPOSITORIO):
                raise SystemExit("no hay base en la rama estado")
        conexion = cifrado.abrir_cifrada(ruta)
        try:
            yield Almacen(conexion)
        finally:
            conexion.close()


def principal(argumentos: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    opciones = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    opciones.add_argument("orden", choices=["actualizar"])
    opciones.add_argument(
        "--repositorio", help="leer los objetivos de la base del repositorio (rama estado)"
    )
    opciones.add_argument("--base", type=Path, help="leer los objetivos de un db.age local")
    opciones.add_argument("--tope-min", type=float, default=TOPE_S / 60)
    opciones.add_argument("--registro", type=Path, help="fichero con la última ejecución correcta")
    args = opciones.parse_args(argumentos)
    datos = directorio_datos()
    datos.mkdir(parents=True, exist_ok=True)
    ruta_control = datos / CONTROL
    control = _cargar_control(ruta_control)
    inicio = time.monotonic()
    ahora = datetime.now(UTC)
    lector = Lector()
    subir = subida_al_almacen(os.environ)
    if args.repositorio is None and args.base is None:
        # Lo normal en el servidor: los objetivos que deja la recogida horaria.
        cargados = cargar_objetivos(datos / OBJETIVOS)
        if cargados is None:
            registro.warning("sin %s: la recogida horaria aún no los ha dejado", OBJETIVOS)
            return 1
        objetivos = cargados
    else:
        with _base(args.repositorio, args.base) as almacen:
            objetivos = objetivos_de_base(almacen)
    resumen = actualizar(
        objetivos,
        control,
        buscador_http(lector),
        lector,
        subir,
        ahora,
        args.tope_min * 60,
        borrar=borrado_del_almacen(os.environ),
    )
    _escribir(ruta_control, control)
    publico = indice(control, ahora)
    _escribir(datos / "parejas.json", publico)
    cuerpo = json.dumps(publico, ensure_ascii=False, separators=(",", ":")).encode()
    subido = subir(INDICE, cuerpo, "application/json", CACHE_INDICE)
    duracion = time.monotonic() - inicio
    registro.info(
        "satélite: %d objetivos; %s; %.1f MB leídos en %d peticiones; %.0f s",
        len(objetivos),
        resumen.texto(),
        lector.bytes / 1e6,
        lector.peticiones,
        duracion,
    )
    if args.registro is not None and subido:
        _escribir(
            args.registro,
            {"ultima": ahora.strftime("%Y-%m-%dT%H:%MZ"), "duracion_s": round(duracion)},
        )
    return 0 if subido else 1


if __name__ == "__main__":
    sys.exit(principal())
