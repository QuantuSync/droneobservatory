"""Informes de investigación, cierres de investigaciones policiales y sentencias sobre drones.

Lectores de las fuentes de detalle del grupo «investigaciones» (configuracion/fuentes_detalle.json),
uno por fuente, registrados en recogida/detalle.py. Cada uno deja en la carpeta de datos los
documentos que hablan de drones, con sus pasajes ya localizados (proceso/pasajes.py); el
extractor y el cruce con los incidentes los hace después la recogida horaria.

- aaib: API de búsqueda y de contenido de GOV.UK (informes de la AAIB de la categoría
  «unmanned-aircraft-systems» y los que nombran drones) y el PDF de cada informe;
- havarikommissionen: sitemap.xml, la página de cada caso de aviación y su «statement»;
- ovv: búsqueda del sitio (drone, onbemand, RPAS, UAS) restringida a investigaciones;
- nsia: lista paginada de informes publicados de aviación;
- pkbwl: el registro entero en JSON (API pública del sitio);
- politi_dk: lista de noticias de politi.dk por fecha y distrito (la que monta la propia web);
- rechtspraak: datos abiertos de rechtspraak.nl, resúmenes por fecha de modificación (o de
  sentencia, en el histórico) y el texto de las que nombran drones;
- domsdatabasen: API JSON de búsqueda de Domsdatabasen.

Reglas comunes: identificación del observatorio, robots.txt de cada sitio, la pausa del
descargador (3 s por sitio) y comprobación de que lo descargado es lo esperado. Lo ya leído no
se vuelve a pedir: los documentos guardados y las páginas ya vistas que no eran de drones se
saltan, salvo en el histórico.
"""

import contextlib
import html as html_
import io
import json
import re
import xml.etree.ElementTree as ET
from collections.abc import Callable
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import quote, urljoin, urlsplit
from urllib.robotparser import RobotFileParser

from esquema import Documento
from proceso import pasajes
from recogida import detalle, oficiales, paginas_oficiales
from recogida.descarga import AGENTE_EODI, Descargador, DescargaFallida, NoEncontrado

FIABILIDAD = "A"
CREDIBILIDAD = 1
# Lo que mira una recogida que no es la del histórico.
VENTANA_RECIENTE = timedelta(days=60)
MAX_PAGINAS_PDF = 20
MAX_PAGINAS_LISTA = 40
INICIO_HISTORICO = "2024-01-01"
_ID = re.compile(r"[^A-Za-z0-9_.:/-]+")
# Siglas y palabras de dron que el filtro general no tiene en neerlandés, noruego y polaco.
_DRON_EXTRA = re.compile(
    r"\b(onbemand\w*\s+luchtvaartu\w*|onbemande\s+luchtvaartu\w*|ubemann\w*|"
    r"bezza[lł]ogow\w*|BSP|DJI|mavic|matrice|multikopter\w*|modellfly\w*|modellseil\w*)",
    re.IGNORECASE,
)


def habla_de_drones(texto: str) -> bool:
    return pasajes.habla_de_drones(texto) or bool(_DRON_EXTRA.search(texto))


# --- Piezas comunes ---------------------------------------------------------------------


class Sitios:
    """robots.txt de cada sitio, leído una vez por recogida."""

    def __init__(self, descargador: Descargador) -> None:
        self.descargador = descargador
        self._lectores: dict[str, RobotFileParser] = {}

    def permitido(self, url: str) -> bool:
        sitio = urlsplit(url).netloc
        if sitio not in self._lectores:
            self._lectores[sitio] = oficiales.robots(self.descargador, url)
        return self._lectores[sitio].can_fetch(AGENTE_EODI, url)

    def texto(self, url: str, valido: Callable[[str], bool]) -> str:
        if not self.permitido(url):
            raise DescargaFallida(f"{url}: robots.txt no lo permite")
        return self.descargador.texto(url, valido)

    def contenido(self, url: str, valido: Callable[[bytes], bool]) -> bytes:
        if not self.permitido(url):
            raise DescargaFallida(f"{url}: robots.txt no lo permite")
        return self.descargador.contenido(url, valido)


def _es_html(texto: str) -> bool:
    return "<html" in texto[:2000].lower() or "<!doctype html" in texto[:200].lower()


def _es_json(texto: str) -> bool:
    try:
        json.loads(texto)
    except ValueError:
        return False
    return True


def _es_xml(texto: str) -> bool:
    return texto.lstrip("﻿ \n").startswith("<")


def _es_pdf(datos: bytes) -> bool:
    return datos[:5] == b"%PDF-"


def identificador(fuente_id: str, nativo: str) -> str:
    return f"{fuente_id}:{_ID.sub('-', nativo).strip('-')}"


def documento(
    fuente: Documento, nativo: str, tipo: str, titulo: str, enlace: str, fecha: str, texto: str,
    autoridad: str | None = None,
) -> Documento:  # fmt: skip
    """El documento recogido, con los pasajes que hablan de drones."""
    hallados = pasajes.localizar(texto)
    return {
        "id": identificador(fuente["id"], nativo),
        "fuente_detalle": fuente["id"],
        "tipo": tipo,
        "autoridad": autoridad or fuente["autoridad"],
        "pais": fuente["pais"],
        "idioma": fuente["idioma"],
        "titulo": " ".join(titulo.split()) or nativo,
        "enlace": enlace,
        "fecha": fecha,
        "fiabilidad": fuente.get("fiabilidad", FIABILIDAD),
        "credibilidad": fuente.get("credibilidad", CREDIBILIDAD),
        "pasajes": list(hallados.textos),
        "huella": hallados.huella,
    }


def _guardados(raiz: Path, fuente_id: str) -> set[str]:
    ruta = detalle.ruta_documentos(raiz, fuente_id)
    if not ruta.exists():
        return set()
    return {d["id"] for d in json.loads(ruta.read_text(encoding="utf-8"))}


def _ruta_vistos(raiz: Path, fuente_id: str) -> Path:
    return raiz / "investigaciones" / f"{fuente_id}.vistos.json"


def _vistos(raiz: Path, fuente_id: str) -> set[str]:
    ruta = _ruta_vistos(raiz, fuente_id)
    return set(json.loads(ruta.read_text(encoding="utf-8"))) if ruta.exists() else set()


def _guardar_vistos(raiz: Path, fuente_id: str, vistos: set[str]) -> None:
    ruta = _ruta_vistos(raiz, fuente_id)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(json.dumps(sorted(vistos), ensure_ascii=False), encoding="utf-8", newline="\n")


def _texto_html(html: str) -> str:
    """Los párrafos de una página, separados por línea en blanco."""
    return "\n\n".join(paginas_oficiales.leer(html).parrafos)


def _plano(html: str) -> str:
    sin_codigo = re.sub(r"<(script|style)\b.*?</\1>", " ", html, flags=re.S | re.I)
    return " ".join(html_.unescape(re.sub(r"<[^>]+>", " ", sin_codigo)).split())


def texto_pdf(datos: bytes, paginas: int = MAX_PAGINAS_PDF) -> str:
    from pypdf import PdfReader

    lector = PdfReader(io.BytesIO(datos))
    return "\n".join((p.extract_text() or "") for p in lector.pages[:paginas])


def _guardar(raiz: Path, fuente: Documento, documentos: list[Documento]) -> int:
    if documentos:
        detalle.guardar_documentos(raiz, fuente["id"], documentos)
    return len(documentos)


# --- AAIB (Reino Unido) -----------------------------------------------------------------

GOVUK = "https://www.gov.uk"
_CAMPOS_AAIB = "title,link,public_timestamp,description,date_of_occurrence"


def busquedas_aaib(historico: bool, inicio: int = 0) -> list[str]:
    cuantos = 100 if historico else 20
    base = (
        f"{GOVUK}/api/search.json?filter_format=aaib_report&count={cuantos}&start={inicio}"
        f"&order=-public_timestamp&fields={_CAMPOS_AAIB}"
    )
    return [f"{base}&filter_aircraft_category=unmanned-aircraft-systems", f"{base}&q=drone"]


def resultados_aaib(texto: str) -> list[Documento]:
    """Los informes de una respuesta de búsqueda que tratan de drones."""
    datos = json.loads(texto)
    return [
        r for r in datos.get("results", [])
        if r.get("link", "").startswith("/aaib-reports/")
        and habla_de_drones(f"{r.get('title', '')} {r.get('description', '')}")
    ]  # fmt: skip


def pdf_aaib(contenido: Documento) -> str | None:
    """El PDF del informe entre los adjuntos (no el glosario de abreviaturas)."""
    for adjunto in contenido.get("details", {}).get("attachments", []):
        if (
            adjunto.get("content_type") == "application/pdf"
            and "glossary" not in str(adjunto.get("title", "")).lower()
        ):
            return str(adjunto["url"])
    return None


def documento_aaib(
    fuente: Documento, resultado: Documento, contenido: Documento, pdf: str
) -> Documento:
    cuerpo = _texto_html(str(contenido.get("details", {}).get("body", "")))
    texto = "\n\n".join(x for x in (str(resultado.get("description", "")), cuerpo, pdf) if x)
    return documento(
        fuente, resultado["link"].removeprefix("/"), "informe_investigacion",
        str(resultado.get("title", "")), GOVUK + resultado["link"],
        str(resultado["public_timestamp"])[:10], texto,
    )  # fmt: skip


def recolector_aaib(
    fuente: Documento, raiz: Path, descargador: Descargador, ahora: datetime, historico: bool
) -> int:
    sitios = Sitios(descargador)
    guardados = set() if historico else _guardados(raiz, fuente["id"])
    hallados: dict[str, Documento] = {}
    for busqueda in busquedas_aaib(historico):
        inicio = 0
        while True:
            url = busqueda.replace("&start=0", f"&start={inicio}")
            texto = sitios.texto(url, _es_json)
            for r in resultados_aaib(texto):
                hallados.setdefault(r["link"], r)
            total = int(json.loads(texto).get("total", 0))
            inicio += 100
            if not historico or inicio >= total:
                break
    nuevos = []
    for link, resultado in sorted(hallados.items()):
        if identificador(fuente["id"], link.removeprefix("/")) in guardados:
            continue
        contenido = json.loads(sitios.texto(f"{GOVUK}/api/content{quote(link)}", _es_json))
        enlace_pdf = pdf_aaib(contenido)
        texto = texto_pdf(sitios.contenido(enlace_pdf, _es_pdf)) if enlace_pdf else ""
        nuevos.append(documento_aaib(fuente, resultado, contenido, texto))
    return _guardar(raiz, fuente, nuevos)


# --- Havarikommissionen (Dinamarca) ----------------------------------------------------

HCL = "https://havarikommissionen.dk"
_CASO_HCL = re.compile(r"/undersoegelsesresultater/soeg-i-luftfart/\d{4}/(\d{4}-\d+)$")
_FECHA_GUION = re.compile(r"\b(\d{2})-(\d{2})-(\d{4})\b")


def casos_hcl(sitemap: str, desde: str | None) -> list[str]:
    """Las páginas de casos de aviación del sitemap; con `desde`, solo las cambiadas después."""
    casos = []
    for bloque in re.findall(r"<url>(.*?)</url>", sitemap, re.S):
        loc = re.search(r"<loc>([^<]+)</loc>", bloque)
        if loc is None or not _CASO_HCL.search(loc[1]):
            continue
        cambio = re.search(r"<lastmod>([^<]+)</lastmod>", bloque)
        if desde and cambio and cambio[1][:10] < desde:
            continue
        casos.append(loc[1].strip())
    return sorted(set(casos))


def _fecha_tras(texto: str, titulo: str) -> str | None:
    """La fecha de publicación del caso: la que va justo después del título en la página (el
    título lleva la del suceso); si no, la primera que no es la del título."""
    if titulo and (m := re.search(re.escape(titulo) + r"\s+(\d{2})-(\d{2})-(\d{4})\b", texto)):
        return f"{m[3]}-{m[2]}-{m[1]}"
    del_titulo = set(_FECHA_GUION.findall(titulo))
    m = next((f for f in _FECHA_GUION.finditer(texto) if f.groups() not in del_titulo), None)
    return f"{m[3]}-{m[2]}-{m[1]}" if m else None


def caso_hcl(html: str) -> Documento:
    """Título, descripción, si es de drones, fecha y enlace al statement de una página de caso."""
    pagina = paginas_oficiales.leer(html)
    titulo = " ".join(pagina.meta.get("og:title", "").split())
    descripcion = pagina.meta.get("description", "")
    plano = _plano(html)
    statement = re.search(r'href="([^"]*/statement-[^"]+)"', html)
    return {
        "titulo": titulo,
        "descripcion": descripcion,
        "drones": "Drone - UAS" in plano or habla_de_drones(f"{titulo} {descripcion}"),
        "fecha": _fecha_tras(plano, titulo),
        "statement": urljoin(HCL, statement[1]) if statement else None,
        "texto": _texto_html(html),
    }


def recolector_havarikommissionen(
    fuente: Documento, raiz: Path, descargador: Descargador, ahora: datetime, historico: bool
) -> int:
    sitios = Sitios(descargador)
    vistos = set() if historico else _vistos(raiz, fuente["id"])
    desde = None if historico else (ahora - VENTANA_RECIENTE).date().isoformat()
    sitemap = sitios.texto(f"{HCL}/sitemap.xml", lambda t: "<urlset" in t)
    nuevos = []
    for url in casos_hcl(sitemap, desde):
        if url in vistos:
            continue
        caso = caso_hcl(sitios.texto(url, _es_html))
        vistos.add(url)
        if not caso["drones"] or caso["fecha"] is None:
            continue
        texto = caso["texto"]
        if caso["statement"]:
            with contextlib.suppress(DescargaFallida):
                texto = _texto_html(sitios.texto(caso["statement"], _es_html)) or texto
        nativo = _CASO_HCL.search(url)
        assert nativo is not None
        texto = "\n\n".join(x for x in (caso["descripcion"], texto) if x)
        nuevos.append(documento(fuente, nativo[1], "informe_investigacion", caso["titulo"],
                                caso["statement"] or url, caso["fecha"], texto))  # fmt: skip
    _guardar_vistos(raiz, fuente["id"], vistos)
    return _guardar(raiz, fuente, nuevos)


# --- Onderzoeksraad voor Veiligheid (Países Bajos) --------------------------------------

OVV = "https://onderzoeksraad.nl"
TERMINOS_OVV = ("drone", "onbemand", "RPAS", "UAS")
_ITEM_OVV = re.compile(
    r'<time datetime="(?P<fecha>\d{4}-\d{2}-\d{2})[^"]*">.*?'
    r'<a href="(?P<url>https://onderzoeksraad\.nl/onderzoek/[^"]+)">(?P<titulo>.*?)</a>'
    r'(?:.*?c-result__content__description">(?P<descripcion>.*?)</p>)?',
    re.S,
)


def busqueda_ovv(termino: str, pagina: int) -> str:
    return f"{OVV}/?s={quote(termino)}&post_type%5B0%5D=investigation&paged={pagina}"


def resultados_ovv(html: str) -> list[Documento]:
    resultado = []
    for item in re.split(r'<li class="c-result__list__item">', html)[1:]:
        m = _ITEM_OVV.search(item)
        if m is None:
            continue
        titulo = _plano(m["titulo"])
        descripcion = _plano(m["descripcion"] or "")
        resultado.append({"url": m["url"], "fecha": m["fecha"], "titulo": titulo,
                          "descripcion": descripcion,
                          "drones": habla_de_drones(f"{titulo} {descripcion}")})  # fmt: skip
    return resultado


def recolector_ovv(
    fuente: Documento, raiz: Path, descargador: Descargador, ahora: datetime, historico: bool
) -> int:
    sitios = Sitios(descargador)
    guardados = set() if historico else _guardados(raiz, fuente["id"])
    hallados: dict[str, Documento] = {}
    for termino in TERMINOS_OVV if historico else TERMINOS_OVV[:1]:
        for pagina in range(1, MAX_PAGINAS_LISTA + 1):
            try:
                items = resultados_ovv(sitios.texto(busqueda_ovv(termino, pagina), _es_html))
            except NoEncontrado:
                # Pasada la última página, la búsqueda responde 404.
                break
            for item in items:
                if item["drones"]:
                    hallados.setdefault(item["url"], item)
            if not items or not historico:
                break
    nuevos = []
    for url, item in sorted(hallados.items()):
        nativo = url.rstrip("/").rsplit("/", 1)[-1]
        if identificador(fuente["id"], nativo) in guardados:
            continue
        texto = _texto_html(sitios.texto(url, _es_html))
        texto = "\n\n".join(x for x in (item["descripcion"], texto) if x)
        nuevos.append(documento(fuente, nativo, "informe_investigacion", item["titulo"], url,
                                item["fecha"], texto))  # fmt: skip
    return _guardar(raiz, fuente, nuevos)


# --- NSIA (Noruega) -------------------------------------------------------------------

NSIA = "https://nsia.no"
LISTA_NSIA = NSIA + "/Aviation/Aviation/Published-reports?page={pagina}"
_FILA_NSIA = re.compile(r"<tr>(.*?)</tr>", re.S)
_PUBLICADO_NSIA = re.compile(r"Published (\d{2})\.(\d{2})\.(\d{4})")


def filas_nsia(html: str) -> list[Documento]:
    """Las filas de la tabla de informes: enlace y celdas (número, aeronave, matrícula, fecha
    del suceso, lugar...)."""
    resultado = []
    for fila in _FILA_NSIA.findall(html):
        enlace = re.search(r'href="(/Aviation/Aviation/Published-reports/[^"?]+)"', fila)
        if enlace is None:
            continue
        celdas = [_plano(c) for c in re.findall(r"<td[^>]*>(.*?)</td>", fila, re.S)]
        resultado.append({"url": NSIA + enlace[1], "celdas": [c for c in celdas if c],
                          "drones": habla_de_drones(" ".join(celdas))})  # fmt: skip
    return resultado


def informe_nsia(html: str) -> tuple[str | None, str, str]:
    """Fecha de publicación, título y texto de la página de un informe."""
    plano = _plano(html)
    m = _PUBLICADO_NSIA.search(plano)
    fecha = f"{m[3]}-{m[2]}-{m[1]}" if m else None
    titulo = re.search(r"Print (Report on .*?)(?: Aviation report| Luftfartsrapport|$)", plano)
    return fecha, titulo[1] if titulo else "", _texto_html(html) or plano


def recolector_nsia(
    fuente: Documento, raiz: Path, descargador: Descargador, ahora: datetime, historico: bool
) -> int:
    sitios = Sitios(descargador)
    guardados = set() if historico else _guardados(raiz, fuente["id"])
    hallados: dict[str, Documento] = {}
    for pagina in range(MAX_PAGINAS_LISTA if historico else 1):
        try:
            filas = filas_nsia(sitios.texto(LISTA_NSIA.format(pagina=pagina), _es_html))
        except NoEncontrado:
            break
        if not filas:
            break
        hallados.update({f["url"]: f for f in filas if f["drones"]})
    nuevos = []
    for url, fila in sorted(hallados.items()):
        nativo = url.rsplit("/", 1)[-1]
        if identificador(fuente["id"], nativo) in guardados:
            continue
        fecha, titulo, texto = informe_nsia(sitios.texto(url, _es_html))
        if fecha is None:
            continue
        titulo = titulo or " ".join(fila["celdas"][:3])
        nuevos.append(documento(fuente, nativo, "informe_investigacion", titulo, url, fecha, texto))
    return _guardar(raiz, fuente, nuevos)


# --- PKBWL (Polonia) ------------------------------------------------------------------

PKBWL = "https://pkbwl.gov.pl/api/pkbwl_reports/v1/reports"
_ETIQUETAS_PKBWL = (
    ("nr_pkbwl", "Nr PKBWL"), ("data_zdarzenia", "Data zdarzenia"),
    ("kategoria_statku_powietrznego", "Kategoria statku powietrznego"),
    ("typ_statku_powietrznego", "Typ statku powietrznego"),
    ("klasyfikacja_zdarzenia", "Klasyfikacja zdarzenia"),
    ("miejsce_zdarzenia", "Miejsce zdarzenia"),
    ("data_zakonczenia_badania", "Data zakończenia badania"),
)  # fmt: skip
_FECHA_ISO = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def registros_pkbwl(texto: str) -> list[Documento]:
    """Los sucesos del registro con un dron (categoría «dron», «BSP» o un modelo de dron)."""
    return [
        r for r in json.loads(texto)
        if habla_de_drones(f"{r.get('kategoria_statku_powietrznego', '')} "
                           f"{r.get('typ_statku_powietrznego', '')}")
    ]  # fmt: skip


def documento_pkbwl(fuente: Documento, registro: Documento) -> Documento:
    """El registro es una ficha de campos fijos: su texto son esos campos, con su etiqueta."""
    texto = "\n".join(
        f"{etiqueta}: {registro[clave]}" for clave, etiqueta in _ETIQUETAS_PKBWL
        if registro.get(clave)
    )  # fmt: skip
    final = str(registro.get("data_zakonczenia_badania", ""))
    fecha = final if _FECHA_ISO.match(final) else str(registro["data_zdarzenia"])
    titulo = ", ".join(
        str(registro[c]) for c in ("klasyfikacja_zdarzenia", "typ_statku_powietrznego",
                                   "miejsce_zdarzenia") if registro.get(c)
    )  # fmt: skip
    return documento(fuente, str(registro["nr_pkbwl"]), "informe_investigacion", titulo,
                     str(registro["permalink"]), fecha, texto)  # fmt: skip


def recolector_pkbwl(
    fuente: Documento, raiz: Path, descargador: Descargador, ahora: datetime, historico: bool
) -> int:
    sitios = Sitios(descargador)
    corte = "" if historico else (ahora - VENTANA_RECIENTE).date().isoformat()
    nuevos = [
        documento_pkbwl(fuente, r) for r in registros_pkbwl(sitios.texto(PKBWL, _es_json))
        if _FECHA_ISO.match(str(r.get("data_zdarzenia", ""))) and str(r["data_zdarzenia"]) >= corte
    ]  # fmt: skip
    return _guardar(raiz, fuente, nuevos)


# --- Policía danesa (politi.dk) --------------------------------------------------------

POLITI = "https://politi.dk"
_INIT = re.compile(r'ng-init="init\((.*?)\)"', re.S)
_CIERRE = re.compile(
    r"efterforskning\w*\s.{0,80}?\b(?:indstillet|afsluttet|lukket)\b|"
    r"\b(?:indstille[rt]?|afslutte[rt]?)\s+efterforskning",
    re.IGNORECASE | re.S,
)
POR_PAGINA = 10


def lista_politi(desde: str, hasta: str, distritos: list[str], pagina: int) -> str:
    a, b = (x.replace("-0", "-").replace("-", "/") for x in (desde, hasta))
    return (
        f"{POLITI}/nyhedsliste?fromDate={a}&toDate={b}&district={','.join(distritos)}&page={pagina}"
    )


def noticias_politi(html: str) -> tuple[int, list[Documento]]:
    """El total y las noticias de una página de la lista (van en los datos de arranque)."""
    m = _INIT.search(html)
    if m is None:
        raise DescargaFallida("la lista de politi.dk no trae sus datos")
    datos = json.loads(html_.unescape(m[1]))
    noticias = datos["AllNews"]
    return int(noticias.get("TotalNumberOfNews", 0)), list(noticias.get("NewsList") or [])


# En danés: «drone», «droner», «droneobservationer»... El filtro general casa con «dron» y
# daría también «Dronninglund» o «dronning».
_DRON_DANES = re.compile(r"\b(drone\w*|droner\w*|UAS|UAV|RPAS)\b", re.IGNORECASE)


def de_drones_politi(texto: str) -> bool:
    return bool(_DRON_DANES.search(texto))


def tipo_politi(texto: str) -> str:
    return "cierre_investigacion" if _CIERRE.search(texto) else "nota_oficial"


def _meses(desde: str, hasta: str) -> list[tuple[str, str]]:
    """Tramos de un mes de `desde` a `hasta` (AAAA-MM-DD)."""
    tramos = []
    inicio = datetime.fromisoformat(desde)
    fin = datetime.fromisoformat(hasta)
    while inicio <= fin:
        siguiente = (inicio.replace(day=1) + timedelta(days=32)).replace(day=1)
        ultimo = min(siguiente - timedelta(days=1), fin)
        tramos.append((inicio.date().isoformat(), ultimo.date().isoformat()))
        inicio = siguiente
    return tramos


def recolector_politi_dk(
    fuente: Documento, raiz: Path, descargador: Descargador, ahora: datetime, historico: bool
) -> int:
    sitios = Sitios(descargador)
    guardados = set() if historico else _guardados(raiz, fuente["id"])
    hoy = ahora.date().isoformat()
    desde = INICIO_HISTORICO if historico else (ahora - VENTANA_RECIENTE).date().isoformat()
    tramos = _meses(desde, hoy) if historico else [(desde, hoy)]
    hallados: dict[str, Documento] = {}
    for inicio, fin in tramos:
        for pagina in range(1, MAX_PAGINAS_LISTA + 1):
            url = lista_politi(inicio, fin, fuente["distritos"], pagina)
            total, noticias = noticias_politi(sitios.texto(url, _es_html))
            for n in noticias:
                if de_drones_politi(f"{n.get('Headline', '')} {n.get('Manchet', '')}"):
                    hallados.setdefault(str(n["Link"]), n)
            if pagina * POR_PAGINA >= total or not noticias:
                break
    nuevos = []
    for enlace, noticia in sorted(hallados.items()):
        nativo = urlsplit(enlace).path.removeprefix("/")
        if identificador(fuente["id"], nativo) in guardados:
            continue
        texto = _texto_html(sitios.texto(enlace, _es_html))
        titulo = str(noticia.get("Headline", ""))
        texto = "\n\n".join(x for x in (str(noticia.get("Manchet") or ""), texto) if x)
        nuevos.append(documento(
            fuente, nativo, tipo_politi(f"{titulo}. {texto}"), titulo, enlace,
            str(noticia["ListDate"])[:10], texto, autoridad=str(noticia.get("DistrictName") or ""),
        ))  # fmt: skip
    return _guardar(raiz, fuente, nuevos)


# --- rechtspraak.nl (Países Bajos) ------------------------------------------------------

RECHTSPRAAK = "https://data.rechtspraak.nl/uitspraken"
POR_CONSULTA = 1000
_SEGUNDOS = "%Y-%m-%dT%H:%M:%S"
_ATOM = "{http://www.w3.org/2005/Atom}"
_RESUMEN_DRON = re.compile(
    r"\b(drone\w*|onbemand\w*\s+luchtvaartu\w*|UAS|RPAS|quadcopter\w*)\b",
    re.IGNORECASE,
)


def consulta_rechtspraak(campo: str, desde: str, hasta: str, inicio: int) -> str:
    return (
        f"{RECHTSPRAAK}/zoeken?type=Uitspraak&{campo}={desde}&{campo}={hasta}"
        f"&max={POR_CONSULTA}&from={inicio}&return=DOC"
    )


def entradas_rechtspraak(texto: str) -> tuple[int, list[Documento]]:
    """Total y entradas (ECLI, título, resumen) de una respuesta de búsqueda."""
    raiz = ET.fromstring(texto.lstrip("﻿"))
    total = re.search(r"(\d+)", raiz.findtext(f"{_ATOM}subtitle") or "")
    entradas = [
        {"ecli": e.findtext(f"{_ATOM}id") or "", "titulo": e.findtext(f"{_ATOM}title") or "",
         "resumen": e.findtext(f"{_ATOM}summary") or ""}
        for e in raiz.iter(f"{_ATOM}entry")
    ]  # fmt: skip
    return (int(total[1]) if total else len(entradas)), entradas


def de_drones_rechtspraak(entrada: Documento) -> bool:
    """Nombra drones y es de un tribunal europeo (no de los del Caribe neerlandés)."""
    return bool(_RESUMEN_DRON.search(f"{entrada['titulo']} {entrada['resumen']}")) and not entrada[
        "ecli"
    ].startswith("ECLI:NL:OG")


def sentencia_rechtspraak(xml: str) -> tuple[str | None, str, str]:
    """Fecha de publicación, tribunal y texto (resumen y sentencia) de una resolución."""
    raiz = ET.fromstring(xml.lstrip("﻿"))
    fecha = autoridad = None
    for elemento in raiz.iter():
        nombre = elemento.tag.rsplit("}", 1)[-1]
        if nombre == "issued" and fecha is None and elemento.text:
            fecha = elemento.text.strip()[:10]
        if nombre == "creator" and autoridad is None and elemento.text:
            autoridad = elemento.text.strip()
    bloques = []
    for elemento in raiz.iter():
        if elemento.tag.rsplit("}", 1)[-1] in {"inhoudsindicatie", "uitspraak"}:
            for parrafo in elemento.iter():
                if parrafo.tag.rsplit("}", 1)[-1] in {"para", "title"}:
                    texto = " ".join("".join(parrafo.itertext()).split())
                    if texto:
                        bloques.append(texto)
    return fecha, autoridad or "Rechtspraak", "\n\n".join(bloques)


def _ruta_control_rechtspraak(raiz: Path) -> Path:
    return raiz / "investigaciones" / "rechtspraak.control.json"


def recolector_rechtspraak(
    fuente: Documento, raiz: Path, descargador: Descargador, ahora: datetime, historico: bool
) -> int:
    """En el histórico, todas las resoluciones por fecha de sentencia desde 2024 (unas 70 000 al
    año, 1000 por consulta); si no, las modificadas desde la última recogida. La API no busca
    por texto: se miran los resúmenes y solo de las que nombran drones se pide el texto."""
    sitios = Sitios(descargador)
    guardados = set() if historico else _guardados(raiz, fuente["id"])
    control = _ruta_control_rechtspraak(raiz)
    previo = json.loads(control.read_text(encoding="utf-8")) if control.exists() else {}
    hoy = ahora.date().isoformat()
    if historico:
        tramos = [("date", f"{a}-01-01", f"{a}-12-31")
                  for a in range(int(INICIO_HISTORICO[:4]), ahora.year + 1)]  # fmt: skip
    else:
        semana = (ahora - timedelta(days=7)).strftime(_SEGUNDOS)
        tramos = [
            ("modified", previo.get("modificadas_hasta") or semana, ahora.strftime(_SEGUNDOS))
        ]
    hallados: dict[str, Documento] = {}
    for campo, desde_, hasta in tramos:
        inicio = 0
        while True:
            total, entradas = entradas_rechtspraak(
                sitios.texto(consulta_rechtspraak(campo, desde_, hasta, inicio), _es_xml)
            )
            hallados.update({e["ecli"]: e for e in entradas if de_drones_rechtspraak(e)})
            inicio += POR_CONSULTA
            if inicio >= total or not entradas:
                break
    nuevos = []
    for ecli, entrada in sorted(hallados.items()):
        if identificador(fuente["id"], ecli) in guardados:
            continue
        enlace = f"{RECHTSPRAAK}/content?id={ecli}"
        fecha, autoridad, texto = sentencia_rechtspraak(sitios.texto(enlace, _es_xml))
        if fecha is None:
            continue
        nuevos.append(documento(
            fuente, ecli, "sentencia", entrada["titulo"],
            f"https://uitspraken.rechtspraak.nl/details?id={ecli}", fecha,
            "\n\n".join(x for x in (entrada["resumen"], texto) if x), autoridad=autoridad,
        ))  # fmt: skip
    control.parent.mkdir(parents=True, exist_ok=True)
    control.write_text(
        json.dumps({**previo, "modificadas_hasta": ahora.strftime(_SEGUNDOS),
                    "ultima": hoy}),
        encoding="utf-8", newline="\n",
    )  # fmt: skip
    return _guardar(raiz, fuente, nuevos)


# --- Domsdatabasen (Dinamarca) ---------------------------------------------------------

DOMSDATABASEN = "https://www.domsdatabasen.dk"
TERMINOS_DOMS = ("drone", "droneflyvning")


def busqueda_doms(termino: str, pagina: int) -> str:
    return (
        f"{DOMSDATABASEN}/webapi/api/Case/search?query={quote(termino)}&sorting=0"
        f"&page={pagina}&pageSize=50"
    )


def casos_doms(texto: str) -> list[Documento]:
    """Los casos cuyo titular habla de drones (la búsqueda del sitio es aproximada)."""
    casos = json.loads(texto).get("cases", [])
    return [c for c in casos if habla_de_drones(str(c.get("headline", "")))]


def documento_doms(fuente: Documento, caso: Documento) -> Documento | None:
    documentos = caso.get("documents", [])
    fechas = [str(d["verdictDateTime"])[:10] for d in documentos if d.get("verdictDateTime")]
    if not fechas:
        return None
    materias = ", ".join(str(m.get("displayText", "")) for m in caso.get("caseSubjects", []))
    texto = "\n\n".join(x for x in (str(caso.get("headline", "")), materias) if x)
    return documento(
        fuente, str(caso["id"]), "sentencia", str(caso.get("headline", "")),
        f"{DOMSDATABASEN}/#sag/{caso['id']}", max(fechas), texto,
        autoridad=str(caso.get("officeName") or fuente["autoridad"]),
    )  # fmt: skip


def recolector_domsdatabasen(
    fuente: Documento, raiz: Path, descargador: Descargador, ahora: datetime, historico: bool
) -> int:
    sitios = Sitios(descargador)
    nuevos: dict[str, Documento] = {}
    for termino in TERMINOS_DOMS:
        texto = sitios.texto(busqueda_doms(termino, 1), _es_json)
        for caso in casos_doms(texto):
            if (doc := documento_doms(fuente, caso)) is not None:
                nuevos[doc["id"]] = doc
    return _guardar(raiz, fuente, [nuevos[k] for k in sorted(nuevos)])


RECOLECTORES: dict[str, detalle.Recolector] = {
    "aaib": recolector_aaib,
    "havarikommissionen": recolector_havarikommissionen,
    "ovv": recolector_ovv,
    "nsia": recolector_nsia,
    "pkbwl": recolector_pkbwl,
    "politi_dk": recolector_politi_dk,
    "rechtspraak": recolector_rechtspraak,
    "domsdatabasen": recolector_domsdatabasen,
}
for _tipo, _funcion in RECOLECTORES.items():
    detalle.registrar_recolector(_tipo, _funcion)
