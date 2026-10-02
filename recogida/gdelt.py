"""Fuente: noticias europeas sobre drones en los ficheros GKG 2.0 de GDELT (fiabilidad C3).

GDELT publica cada 15 minutos dos ficheros GKG: el de las noticias en inglés y
el de las traducidas. Cada ejecución procesa todas las franjas pendientes
desde la última procesada, hasta la última que anuncian los índices de última
actualización. Los ficheros se leen en memoria, fila a fila, y no se guardan.

De cada fila solo se toma lo necesario: URL, fecha, medio, idioma de origen,
temas, lugares y el titular de la página, que va en los campos extra. Pasa si
el titular nombra un dron y el medio es europeo o el artículo sitúa algo en un
país europeo. Después se aplican el filtro, el deduplicado (misma URL canónica
o titular casi idéntico) y la agrupación en candidatos provisionales.
"""

import html
import io
import json
import logging
import re
import zipfile
from collections import Counter
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from functools import cache
from pathlib import Path
from typing import Any

from almacen.base import Almacen
from esquema import Documento
from proceso.noticias import (
    DIRECTORIO,
    GKG,
    LOCALIDAD,
    RADIO_GKG_KM,
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
    id_gkg,
    lugar,
    lugares_articulo,
    nomenclator,
    titular_normalizado,
    url_canonica,
)
from recogida.descarga import Descargador, DescargaFallida, NoEncontrado
from recogida.plazo import Plazo, TiempoAgotado

registro = logging.getLogger(__name__)

FUENTE_ID = "gdelt"
BASE = "https://data.gdeltproject.org/gdeltv2/"
# Flujo: (índice de última actualización, sufijo del fichero GKG).
FLUJOS = {
    "ingles": (BASE + "lastupdate.txt", ".gkg.csv.zip"),
    "traducido": (BASE + "lastupdate-translation.txt", ".translation.gkg.csv.zip"),
}
FRANJA = timedelta(minutes=15)
# Son ficheros estáticos, no una API: medio segundo entre peticiones basta para no
# encadenarlas. Medido: cada fichero tarda de 0,6 a 1,1 s en bajar.
PAUSAS = {"data.gdeltproject.org": 0.5}
# Sin cursor, la primera ejecución empieza un día atrás.
PRIMERA_VENTANA = timedelta(days=1)
# Tope por ejecución: 192 franjas son 48 horas. Si hay más pendientes, la siguiente
# ejecución sigue donde lo dejó esta.
MAX_FRANJAS_POR_EJECUCION = 192
# Tope de tiempo por ejecución. Medido del 28 al 30 de septiembre de 2026: 1,3 s por
# franja con sus dos ficheros (29 franjas en 37 s), así que las 192 del tope son unos
# 250 s. 360 s las cubren con margen; con GDELT lento se leen las que quepan y el cursor,
# que avanza franja a franja, deja el resto para la ejecución siguiente.
TOPE_S = 360.0
# El índice anuncia ficheros que aún no se pueden descargar (404): el 27 de septiembre
# de 2026 el traducido iba más de una hora por detrás de su índice. Si un fichero sigue
# faltando seis horas después de la última franja anunciada, se da por perdido (GDELT
# tiene franjas sin fichero); hasta entonces, la ejecución se para en él y lo reintenta.
ESPERA_AUSENTE = timedelta(hours=6)
# Con más de un día pendiente tras la ejecución, queda en rojo.
HUECO_TOLERADO = timedelta(days=1)
# Temas que se guardan: los propios de GDELT, sin las taxonomías largas (TAX_, WB_,
# UNGP_...), que no ayudan a clasificar el incidente y engordan la base.
_TAXONOMIAS = ("TAX_", "WB_", "UNGP_", "EPU_", "CRISISLEX_", "SOC_", "USPEC_", "ECON_")
MAX_TEMAS = 20
_FORMATO_FRANJA = "%Y%m%d%H%M%S"

# Columnas del GKG 2.1 que se usan.
COL_FECHA = 1
COL_MEDIO = 3
COL_URL = 4
COL_TEMAS = 7
COL_LUGARES = 9
COL_TRADUCCION = 25
COL_EXTRAS = 26
NUM_COLUMNAS = 27
# Un lugar del GKG: tipo#nombre#país#región#lat#lon#id.
GKG_CAMPOS_LUGAR = 6
_TITULO = re.compile(r"<PAGE_TITLE>(.*?)</PAGE_TITLE>", re.DOTALL)
_IDIOMA_ORIGEN = re.compile(r"srclc:(\w+)")


class GdeltNoDisponible(RuntimeError):
    pass


@dataclass
class Recuentos:
    franjas: int = 0
    ausentes: int = 0
    filas: int = 0
    recibidos: int = 0
    ya_vistos: int = 0
    descartados: int = 0
    replicas: int = 0
    nuevos: int = 0
    agrupados: int = 0
    candidatos_nuevos: int = 0
    motivos: Counter[str] = field(default_factory=Counter)

    def sumar(self, otros: "Recuentos") -> None:
        for nombre, valor in vars(otros).items():
            if isinstance(valor, int):
                setattr(self, nombre, getattr(self, nombre) + valor)
        self.motivos.update(otros.motivos)

    def resumen(self) -> str:
        return (
            f"franjas={self.franjas} ausentes={self.ausentes} filas={self.filas} "
            f"recibidos={self.recibidos} ya_vistos={self.ya_vistos} "
            f"descartados={self.descartados} replicas={self.replicas} nuevos={self.nuevos} "
            f"agrupados={self.agrupados} candidatos_nuevos={self.candidatos_nuevos}"
        )


def descargador(plazo: Plazo | None = None) -> Descargador:
    return Descargador(pausas_por_sitio=PAUSAS, plazo=plazo)


# --- Medios europeos -----------------------------------------------------------


@dataclass(frozen=True)
class Medios:
    fips: dict[str, str]
    tld: dict[str, str]
    dominios: dict[str, str]

    def pais(self, medio: str) -> str | None:
        """País del medio: por su dominio o el de un dominio padre, o por el sufijo."""
        dominio = medio.lower().strip().removeprefix("www.")
        etiquetas = dominio.split(".")
        for i in range(len(etiquetas) - 1):
            if pais := self.dominios.get(".".join(etiquetas[i:])):
                return pais
        return self.tld.get(etiquetas[-1])

    def ubicacion(self, lugares: str) -> tuple[str, ...]:
        """El lugar geolocalizado más preciso del GKG en un país europeo: una ciudad o un
        lugar con nombre (tipos 3 y 4); si no, una región (tipos 2 y 5)."""
        por_tipo: dict[str, tuple[str, ...]] = {}
        for entrada in lugares.split(";"):
            campos = entrada.split("#")
            if len(campos) < GKG_CAMPOS_LUGAR or campos[0] not in RADIO_GKG_KM:
                continue
            pais = self.fips.get(campos[2])
            try:
                lat, lon = float(campos[4]), float(campos[5])
            except ValueError:
                continue
            if pais is not None:
                nombre = campos[1].split(",")[0]
                por_tipo.setdefault(campos[0], (id_gkg(campos[0], nombre, pais, lat, lon),))
        return next((por_tipo[t] for t in ("4", "3", "5", "2") if t in por_tipo), ())

    def paises_lugares(self, lugares: str) -> set[str]:
        """Países europeos de los lugares del GKG («1#Spain#SP#SP#40#-4#SP;...»)."""
        paises = set()
        for entrada in lugares.split(";"):
            campos = entrada.split("#")
            if len(campos) > 2 and (pais := self.fips.get(campos[2])):
                paises.add(pais)
        return paises


@cache
def medios(ruta: Path = DIRECTORIO / "medios_europa.json") -> Medios:
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    return Medios(fips=datos["fips"], tld=datos["tld"], dominios=datos["dominios"])


# --- Ficheros GKG ----------------------------------------------------------------


def franja_de(momento: datetime) -> datetime:
    """La franja de 15 minutos que contiene el momento."""
    momento = momento.astimezone(UTC).replace(second=0, microsecond=0)
    return momento.replace(minute=momento.minute - momento.minute % 15)


def url_fichero(franja: datetime, flujo: str) -> str:
    return BASE + franja.strftime(_FORMATO_FRANJA) + FLUJOS[flujo][1]


def ultima_anunciada(descargador: Descargador) -> datetime:
    """La franja más reciente que anuncian los dos índices (la menor de las dos)."""
    ultimas = []
    for indice, sufijo in FLUJOS.values():
        texto = descargador.texto(indice, lambda t: "gdeltv2/" in t)
        m = re.search(r"/(\d{14})" + re.escape(sufijo), texto)
        if m is None:
            raise DescargaFallida(f"{indice}: el índice no anuncia el fichero GKG")
        ultimas.append(datetime.strptime(m[1], _FORMATO_FRANJA).replace(tzinfo=UTC))
    return min(ultimas)


def es_zip(contenido: bytes) -> bool:
    return contenido[:2] == b"PK"


def filas(contenido: bytes) -> Iterator[list[str]]:
    """Filas del fichero GKG comprimido, leídas en memoria sin guardarlo."""
    with zipfile.ZipFile(io.BytesIO(contenido)) as comprimido:
        for nombre in comprimido.namelist():
            with comprimido.open(nombre) as fichero:
                texto = io.TextIOWrapper(fichero, encoding="utf-8", errors="replace", newline="\n")
                for linea in texto:
                    campos = linea.rstrip("\r\n").split("\t")
                    if len(campos) >= NUM_COLUMNAS:
                        yield campos


def titular(extras: str) -> str:
    m = _TITULO.search(extras)
    return " ".join(html.unescape(m[1]).split()) if m else ""


def idioma(traduccion: str, config: dict[str, Any]) -> str | None:
    """Idioma de origen del flujo traducido («srclc:deu;eng:...»); sin él, inglés."""
    m = _IDIOMA_ORIGEN.match(traduccion)
    return config["idiomas"].get(m[1]) if m else "en"


def temas(v1: str) -> tuple[str, ...]:
    propios = {t for t in v1.split(";") if t and not t.startswith(_TAXONOMIAS)}
    return tuple(sorted(propios)[:MAX_TEMAS])


def articulo(
    campos: list[str], filtro_: Filtro, nom: Nomenclator, med: Medios, config: dict[str, Any]
) -> Articulo | None:
    """El artículo de la fila si su titular nombra un dron y tiene que ver con Europa."""
    texto = titular(campos[COL_EXTRAS])
    if not texto or not filtro_.dron.search(texto):
        return None
    pais = med.pais(campos[COL_MEDIO])
    if pais is None and not med.paises_lugares(campos[COL_LUGARES]):
        return None
    return Articulo(
        url=url_canonica(campos[COL_URL]),
        medio=campos[COL_MEDIO],
        fecha=datetime.strptime(campos[COL_FECHA][:14], _FORMATO_FRANJA).replace(tzinfo=UTC),
        titular=texto,
        idioma=idioma(campos[COL_TRADUCCION], config),
        pais=pais,
        temas=temas(campos[COL_TEMAS]),
        lugares=lugares_articulo(texto, nom, filtro_, med.ubicacion(campos[COL_LUGARES])),
    )


def articulos(
    contenido: bytes, recuentos: Recuentos, filtro_: Filtro, nom: Nomenclator, med: Medios,
    config: dict[str, Any],
) -> list[Articulo]:  # fmt: skip
    encontrados = []
    for campos in filas(contenido):
        recuentos.filas += 1
        if (a := articulo(campos, filtro_, nom, med, config)) is not None:
            encontrados.append(a)
    return encontrados


# --- Base ------------------------------------------------------------------------


def _fecha(momento: datetime) -> str:
    return momento.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def documento_articulo(a: Articulo) -> Documento:
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


def articulo_de_documento(documento: Documento) -> Articulo:
    return Articulo(
        url=documento["url"],
        medio=documento["medio"],
        fecha=datetime.fromisoformat(documento["fecha"]),
        titular=documento["titular"],
        idioma=documento.get("idioma"),
        pais=documento.get("pais"),
        temas=tuple(documento.get("temas", [])),
        lugares=tuple(documento.get("lugares", [])),
    )


def _documento_candidato(c: Candidato) -> Documento:
    documento: Documento = {
        "id": c.id,
        "tipo": c.tipo,
        "lugar": c.lugar.id,
        "inicio": _fecha(c.inicio),
        "ultimo": _fecha(c.ultimo),
        "precision": c.precision,
        "articulos": c.articulos,
    }
    # Registro interno de dónde sale el sitio cuando no es una instalación.
    if c.lugar.tipo in {LOCALIDAD, GKG}:
        documento["ubicacion"] = c.lugar.tipo
    if c.separado_de:
        documento["separado_de"] = c.separado_de
    return documento


def _candidato(documento: Documento, nom: Nomenclator) -> Candidato:
    return Candidato(
        id=documento["id"],
        tipo=documento["tipo"],
        lugar=lugar(documento["lugar"], nom),
        inicio=datetime.fromisoformat(documento["inicio"]),
        ultimo=datetime.fromisoformat(documento["ultimo"]),
        precision=documento["precision"],
        articulos=list(documento["articulos"]),
        separado_de=documento.get("separado_de"),
    )


def incorporar(
    almacen: Almacen,
    recibidos_: list[Articulo],
    filtro_: Filtro | None = None,
    nom: Nomenclator | None = None,
) -> Recuentos:
    """Filtra, deduplica, guarda y agrupa los artículos recibidos."""
    filtro_, nom = filtro_ or filtro(), nom or nomenclator()
    recuentos = Recuentos(recibidos=len(recibidos_))
    recibidos = sorted(recibidos_, key=lambda x: (x.fecha, x.url))
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
        almacen.guardar_articulo(documento_articulo(a))
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


class FranjaPendiente(RuntimeError):
    """El fichero aún no se puede descargar: se reintenta en la siguiente ejecución."""


def leer_franja(
    descargador: Descargador, franja: datetime, ultima: datetime
) -> tuple[list[Articulo], Recuentos]:
    """Artículos de los dos flujos de una franja. Un fichero que falta pasadas seis horas
    de la última franja anunciada se da por perdido; antes, la franja queda pendiente."""
    config, filtro_, nom, med = configuracion(), filtro(), nomenclator(), medios()
    lectura = Recuentos(franjas=1)
    encontrados: list[Articulo] = []
    for flujo in FLUJOS:
        try:
            contenido = descargador.contenido(url_fichero(franja, flujo), es_zip)
        except NoEncontrado as error:
            if ultima - franja < ESPERA_AUSENTE:
                raise FranjaPendiente(str(error)) from error
            lectura.ausentes += 1
            continue
        encontrados += articulos(contenido, lectura, filtro_, nom, med, config)
    return encontrados, lectura


def recoger_franja(
    almacen: Almacen, descargador: Descargador, franja: datetime, ultima: datetime
) -> Recuentos:
    """Lee una franja e incorpora sus artículos a la base."""
    encontrados, lectura = leer_franja(descargador, franja, ultima)
    recuentos = incorporar(almacen, encontrados)
    recuentos.franjas, recuentos.ausentes, recuentos.filas = 1, lectura.ausentes, lectura.filas
    return recuentos


def recorrer(
    almacen: Almacen,
    descargador: Descargador,
    desde: datetime,
    hasta: datetime,
    ultima: datetime,
    guardar: Callable[[datetime], None],
) -> tuple[datetime | None, Recuentos]:
    """Procesa las franjas de `desde` a `hasta` (incluida). Devuelve la última procesada.

    `guardar(franja)` se llama tras cada franja para dejar el avance en la base.
    """
    recuentos = Recuentos()
    procesada: datetime | None = None
    franja = desde
    while franja <= hasta:
        try:
            recuentos.sumar(recoger_franja(almacen, descargador, franja, ultima))
        except (FranjaPendiente, DescargaFallida, TiempoAgotado) as error:
            registro.warning("franja %s sin leer: %s", _fecha(franja), type(error).__name__)
            break
        procesada = franja
        guardar(franja)
        franja += FRANJA
    return procesada, recuentos


def ejecutar(
    almacen: Almacen,
    descargador: Descargador,
    ahora: datetime,
    max_franjas: int = MAX_FRANJAS_POR_EJECUCION,
) -> Recuentos:
    """Una ejecución: todas las franjas pendientes desde el cursor, con un tope."""
    cursor = almacen.cursor(FUENTE_ID)
    if cursor and "franja" in cursor:
        hecha = datetime.fromisoformat(cursor["franja"])
    elif cursor:
        # Cursor de la antigua API DOC: sigue desde donde se quedó.
        hecha = franja_de(datetime.fromisoformat(cursor["hasta"])) - FRANJA
    else:
        hecha = franja_de(ahora - PRIMERA_VENTANA) - FRANJA
    inicio = cursor.get("inicio", _fecha(hecha + FRANJA)) if cursor else _fecha(hecha + FRANJA)

    def guardar(franja: datetime) -> None:
        almacen.guardar_cursor(FUENTE_ID, {"franja": _fecha(franja), "inicio": inicio})

    try:
        ultima = ultima_anunciada(descargador)
        hasta = min(ultima, hecha + FRANJA * max_franjas)
        procesada, recuentos = recorrer(
            almacen, descargador, hecha + FRANJA, hasta, ultima, guardar
        )
    except (DescargaFallida, TiempoAgotado) as error:
        registro.warning("gdelt sin índice: %s", type(error).__name__)
        procesada, recuentos = None, Recuentos()
    hecha = procesada or hecha
    registro.info("gdelt hasta %s %s", _fecha(hecha), recuentos.resumen())
    if ahora - hecha > HUECO_TOLERADO:
        raise GdeltNoDisponible(f"franjas pendientes desde {_fecha(hecha)}")
    return recuentos
