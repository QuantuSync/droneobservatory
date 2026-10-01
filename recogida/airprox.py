"""UK Airprox Board: encuentros de drones, aeromodelos y objetos desconocidos con aeronaves.

La UK Airprox Board (UKAB) publica:

- en su página de drones, un Excel histórico de los Airprox con drones, globos, aeromodelos y
  objetos desconocidos («UA and Other Airprox Count»), uno por fila desde 2010 y al día (número,
  fecha, aeronave, objeto según la UKAB, posición, altitud, lugar notificado y riesgo). Es el
  índice: dice qué Airprox interesan y su clasificación tal cual;
- cada año, una página con el informe en PDF de cada Airprox y, desde 2010, un catálogo en
  Excel con los campos fijos de todos: hora UTC, posición en grados, minutos y segundos,
  altitud, categoría de riesgo y tipo, categoría y espacio aéreo de cada aeronave. El del año
  en curso se publica al cerrarlo;
- desde 2016, los encuentros con drones, globos, aeromodelos y objetos van en una hoja
  consolidada por reunión, una tabla con una fila por encuentro: número, fecha, hora,
  aeronave, objeto, posición y punto de referencia, altitud, espacio aéreo, informe del
  piloto, separación y riesgo notificados, opinión de la junta y categoría de riesgo. Antes, un
  informe por Airprox.

Todo se lee con código: los Excel con la biblioteca estándar (un .xlsx es un zip de XML) y los
PDF con pypdf, por expresiones regulares sobre los campos fijos. No pasa nada por el
extractor. Lo que el informe no dice queda sin poner. Los globos no son drones ni objetos
desconocidos: no se guardan.

Condiciones: el sitio no tiene robots.txt (responde 404) y no publica con una licencia abierta.
Su página de copyright dice que los derechos son de la CAA y de la MAA a través de la UKAB, y
permite descargar y copiar las publicaciones para mejorar la seguridad aérea, para investigación
y para uso personal o educativo, no con fines comerciales sin acuerdo previo con la UKAB, citando
siempre a la UKAB como procedencia. Los informes van marcados «OFFICIAL - Public. This information
has been cleared for unrestricted distribution.». Los datos se guardan como registros internos con
esa condición en su campo de licencia, y en lo público solo va el enlace al informe y una frase
breve, citando a la UKAB.

En disco (fuera de la base, que no debe crecer con texto): por informe, su texto extraído
comprimido, el Excel histórico y el catálogo de cada año. Uso, para leer en local una carpeta
de datos:

    python -m recogida.airprox <carpeta> [--desde 2010] [--hasta 2026]
"""

import argparse
import gzip
import hashlib
import io
import json
import logging
import re
import sys
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from esquema import Documento
from recogida.descarga import AGENTE_EODI, Descargador, DescargaFallida

registro = logging.getLogger(__name__)

BASE = "https://www.airproxboard.org.uk"
LISTA = BASE + "/reports-and-analysis/individual-airprox-reports/{anio}/"
DRONES = BASE + "/topical-issues-and-themes/drones/"
PRIMER_ANIO = 2010
AUTORIDAD = "UK Airprox Board"
COPYRIGHT = BASE + "/learn-more-about-airprox/copyright/"
LICENCIA = (
    "© CAA y MAA a través de la UKAB: uso para investigación, uso personal o educativo; no "
    "comercial sin acuerdo previo con la UKAB; citar a la UKAB (" + COPYRIGHT + ")"
)
ATRIBUCION = "Fuente: UK Airprox Board (airproxboard.org.uk)."
VERSION = "airprox/1"
# Fiabilidad del organismo y credibilidad de lo que publica: A2. La junta evalúa lo que
# notifica el piloto y lo cruza con el radar, pero la posición y la separación son
# estimaciones que ella misma declara como tales.
FIABILIDAD = "A"
CREDIBILIDAD = 2
PAIS = "GB"
MAX_PALABRAS = 25
PIE_A_M = 0.3048
MILLA_NAUTICA_M = 1852.0
YARDA_M = 0.9144
DECIMALES = 5

# --- Página de cada año -------------------------------------------------------------

_ENLACE = re.compile(
    r'href="(?P<href>/Documents/Download/[^"]+)"[^>]*>\s*<span>(?P<texto>[^<]+)</span>', re.I
)
_INFORME = re.compile(r"Airprox Report (\d{7})")


@dataclass(frozen=True)
class PaginaAnio:
    catalogo: str | None
    informes: dict[str, str]


def leer_pagina_anio(html: str) -> PaginaAnio:
    """El catálogo en Excel y el PDF de cada Airprox de la página de un año."""
    catalogo = None
    informes: dict[str, str] = {}
    for m in _ENLACE.finditer(html):
        texto, url = m["texto"], BASE + m["href"]
        if "Catalogue" in texto and "XLS" in texto.upper():
            catalogo = url
        elif (n := _INFORME.search(texto)) and "PDF" in texto:
            informes[n[1]] = url
    return PaginaAnio(catalogo, informes)


# --- Catálogo en Excel ----------------------------------------------------------------

_NS = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
_COLUMNA = re.compile(r"([A-Z]+)")
EPOCA_EXCEL = datetime(1899, 12, 30, tzinfo=UTC)


def _indice_columna(referencia: str) -> int:
    letras = _COLUMNA.match(referencia)
    numero = 0
    for letra in letras[1] if letras else "A":
        numero = numero * 26 + ord(letra) - ord("A") + 1
    return numero - 1


_REL = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
_PAQUETE = {"r": "http://schemas.openxmlformats.org/package/2006/relationships"}


def _ruta_hoja(libro: zipfile.ZipFile, nombre: str | None) -> str:
    """El fichero de la hoja con ese nombre (workbook.xml y sus relaciones); sin nombre, la
    primera."""
    hojas = sorted(n for n in libro.namelist() if re.match(r"xl/worksheets/sheet\d+\.xml$", n))
    if nombre is None:
        return hojas[0]
    raiz = ET.fromstring(libro.read("xl/workbook.xml"))
    relaciones = ET.fromstring(libro.read("xl/_rels/workbook.xml.rels"))
    destinos = {
        r.get("Id"): r.get("Target", "") for r in relaciones.findall("r:Relationship", _PAQUETE)
    }
    for hoja in raiz.iter(f"{{{_NS['x']}}}sheet"):
        if hoja.get("name") == nombre:
            destino = destinos.get(hoja.get(_REL), "").lstrip("/")
            return destino if destino.startswith("xl/") else f"xl/{destino}"
    raise KeyError(f"el libro no tiene la hoja {nombre}")


def filas_xlsx(datos: bytes, hoja: str | None = None) -> list[list[Any]]:
    """Las filas de una hoja (por defecto, la primera), como listas de celdas. Los números van
    como float y los textos como str, sin interpretar fechas (eso depende de la columna)."""
    with zipfile.ZipFile(io.BytesIO(datos)) as libro:
        compartidas: list[str] = []
        if "xl/sharedStrings.xml" in libro.namelist():
            raiz = ET.fromstring(libro.read("xl/sharedStrings.xml"))
            for si in raiz.findall("x:si", _NS):
                compartidas.append("".join(t.text or "" for t in si.iter(f"{{{_NS['x']}}}t")))
        raiz = ET.fromstring(libro.read(_ruta_hoja(libro, hoja)))
    filas: list[list[Any]] = []
    for fila in raiz.iter(f"{{{_NS['x']}}}row"):
        valores: dict[int, Any] = {}
        for celda in fila.findall("x:c", _NS):
            tipo = celda.get("t")
            v = celda.find("x:v", _NS)
            if tipo == "inlineStr":
                valor: Any = "".join(t.text or "" for t in celda.iter(f"{{{_NS['x']}}}t"))
            elif v is None or v.text is None:
                continue
            elif tipo == "s":
                valor = compartidas[int(v.text)]
            elif tipo in {"str", "e"}:
                valor = v.text
            elif tipo == "b":
                valor = v.text == "1"
            else:
                valor = float(v.text)
            valores[_indice_columna(celda.get("r", "A"))] = valor
        if valores:
            filas.append([valores.get(i) for i in range(max(valores) + 1)])
    return filas


def fecha_xlsx(datos: bytes) -> str | None:
    """Día de la última modificación del libro (docProps/core.xml), AAAA-MM-DD."""
    with zipfile.ZipFile(io.BytesIO(datos)) as libro:
        if "docProps/core.xml" not in libro.namelist():
            return None
        texto = libro.read("docProps/core.xml").decode("utf-8", errors="replace")
    m = re.search(r"<dcterms:modified[^>]*>(\d{4}-\d{2}-\d{2})", texto)
    return m[1] if m else None


def leer_xlsx(datos: bytes) -> list[dict[str, Any]]:
    """Las filas de la primera hoja como diccionarios por cabecera."""
    filas = filas_xlsx(datos)
    if not filas:
        return []
    cabecera = [str(c).strip() if c is not None else "" for c in filas[0]]
    return [
        {cabecera[i]: fila[i] for i in range(min(len(cabecera), len(fila))) if cabecera[i]}
        for fila in filas[1:]
        if any(c is not None for c in fila)
    ]


def _texto(valor: Any) -> str | None:
    if valor is None:
        return None
    texto = " ".join(str(valor).split())
    return texto or None


def _fecha_excel(valor: Any) -> datetime | None:
    if isinstance(valor, float):
        return EPOCA_EXCEL + timedelta(days=int(valor))
    if isinstance(valor, str):
        for formato in ("%Y-%m-%d", "%d/%m/%Y", "%d %b %Y"):
            try:
                return datetime.strptime(valor.strip()[:10], formato).replace(tzinfo=UTC)
            except ValueError:
                continue
    return None


def _hora_excel(valor: Any) -> tuple[int, int] | None:
    """Fracción de día (0,5 = 12:00) o texto «1215» / «12:15»."""
    if isinstance(valor, float):
        minutos = round(valor % 1 * 24 * 60)
        return divmod(minutos, 60) if minutos < 24 * 60 else None
    if isinstance(valor, str) and (m := re.match(r"^\s*(\d{1,2}):?(\d{2})", valor)):
        hora, minuto = int(m[1]), int(m[2])
        return (hora, minuto) if hora < 24 and minuto < 60 else None
    return None


_GMS = re.compile(r"^\s*(\d{1,3}):(\d{2}):(\d{2})\s*([NSEW])\s*$")


def _coordenada_excel(valor: Any) -> float | None:
    """«51:53:00 N», «002:10:00 W»."""
    m = _GMS.match(str(valor or ""))
    if m is None:
        return None
    grados = int(m[1]) + int(m[2]) / 60 + int(m[3]) / 3600
    return round(-grados if m[4] in "SW" else grados, DECIMALES)


# Lo que interesa: drones (RPAS, UAS), aeromodelos y objetos desconocidos. Los globos, los
# parapentes o las aves no son drones ni objetos desconocidos.
_DRON = re.compile(r"RPAS|UAS\b|\bUAV\b|drone|model", re.I)
_DESCONOCIDO = re.compile(r"unknown\W+object|\(object\)|unk\.? obj", re.I)
_NO_DRON = re.compile(r"balloon|lighter-than-air|paraglider|kite|bird|lantern", re.I)


def lado_objeto(fila: dict[str, Any]) -> int | None:
    """1 o 2: qué aeronave del catálogo es el dron u objeto; None si ninguna lo es."""
    for lado in (2, 1):
        categoria = _texto(fila.get(f"Aircraft {lado} Category")) or ""
        tipo = _texto(fila.get(f"Aircraft {lado} Type")) or ""
        texto = f"{categoria} {tipo}"
        if _NO_DRON.search(categoria):
            continue
        if _DRON.search(texto) or _DESCONOCIDO.search(tipo):
            return lado
    return None


# --- Informes en PDF ------------------------------------------------------------------


def texto_pdf(datos: bytes) -> str:
    """El texto de un PDF, página a página. Lanza ValueError si no se puede leer."""
    from pypdf import PdfReader  # solo hace falta al leer informes
    from pypdf.errors import PyPdfError

    # Avisos de pypdf sobre fuentes tipográficas: no dicen nada del contenido.
    logging.getLogger("pypdf").setLevel(logging.ERROR)
    try:
        lector = PdfReader(io.BytesIO(datos))
        return "\n".join(pagina.extract_text() or "" for pagina in lector.pages)
    except (PyPdfError, KeyError, TypeError) as error:
        raise ValueError(f"PDF ilegible: {type(error).__name__}") from error


_MESES = {m: i for i, m in enumerate(
    ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"), 1
)}  # fmt: skip
_CABECERA_FILA = re.compile(
    r"^(?P<num>20\d{5})\s+(?P<dia>\d{1,2})\s+(?P<mes>[A-Za-z]{3})\w*\s+(?P<anio>\d{2,4})\s*$",
    re.M,
)
_POSICION = re.compile(r"^(?P<objeto>.*?)\s*(?P<lat>\d{4}\s?[NS])\s+(?P<lon>\d{5}\s?[EW])\s*$")
_HORA = re.compile(r"^\s*(\d{2})(\d{2})\s*Z?\s*$")
_SEPARACION = re.compile(r"Reported\s+Separation\s*:\s*(?P<sep>[^\n]+)", re.I)
_SEPARACION_INDIVIDUAL = re.compile(r"Separation\s*\n?\s*Reported\s+(?P<sep>[^\n]+)", re.I)
_RIESGO_NOTIFICADO = re.compile(r"Reported\s+Risk\s+of\s+Collision\s*:\s*(?P<r>[A-Za-z/]+)", re.I)
_OPINION = re.compile(
    r"((?:In the Board[’'`]s opinion|The Board agreed that the (?:pilot|reported|description))"
    r".*?\.)(?=\s|$)",
    re.S,
)
_REUNION = re.compile(r"UKAB Meeting on (\d{1,2})\w{0,2} (\w+) (\d{4})")
_RIESGO_FINAL = re.compile(r"(?:^|\s)([A-E])\s*$")
_RIESGO_DECLARADO = re.compile(r"\bRisk:\s.*?\.\s+([A-E])(?=\s|$)", re.S)
# Palabras con que el piloto describe el aspecto del objeto.
_ASPECTO = re.compile(
    r"\b(black|white|grey|gray|red|blue|green|yellow|orange|silver|dark|bright|colou?r\w*|"
    r"quad-?copter|multi-?rotor|fixed[- ]wing|shaped|size|sized|diameter|large|small|lights?|"
    r"\d+(?:\.\d+)?\s?(?:m|cm|ft)\b)",
    re.I,
)
# Líneas que repiten las páginas y la cabecera de la tabla.
_RUIDO = re.compile(
    r"^\s*(OFFICIAL.*|Airprox|Number|Date|Time|\(UTC\)|Aircraft|\(Operator\) Object|Object|"
    r"Location1?|Description|Altitude|Airspace|\(Class\)|Pilot/Controller Report|"
    r"Reported Separation|Reported Risk|(Comments|Cause)/Risk Statement ICAO|ICAO|Risk|"
    r"\d+\s*Latitude and Longitude.*|Because such reported times.*|\d{1,2})\s*$"
)
_PALABRAS_OBJETO = re.compile(
    r"\b(drones?|UAS|UAV|RPAS|quad-?copter|multi-?rotor|hexa-?copter|octo-?copter|object|"
    r"model aircraft)\b",
    re.I,
)
_PILOTO = re.compile(r"\b(pilot|controller|crew|operator)\b[^.]{0,60}\breports?\b", re.I)


@dataclass
class Bloque:
    """Lo que dice el informe de un Airprox, con los textos tal como salen del PDF."""

    numero: str
    fecha: datetime | None = None
    hora: tuple[int, int] | None = None
    aeronave: str | None = None
    operador: str | None = None
    objeto: str | None = None
    lat: float | None = None
    lon: float | None = None
    ubicacion: str | None = None
    altitud: str | None = None
    espacio: str | None = None
    clase_espacio: str | None = None
    cuerpo: str = ""
    separacion: str | None = None
    riesgo_notificado: str | None = None
    opinion: str | None = None
    riesgo: str | None = None
    reunion: datetime | None = None
    extra: dict[str, str] = field(default_factory=dict)


def _limpiar(texto: str) -> str:
    return "\n".join(linea for linea in texto.splitlines() if not _RUIDO.match(linea))


def _gms_pdf(texto: str) -> float:
    """«5205N» → 52,0833; «00113W» → −1,2167 (grados y minutos)."""
    limpio = texto.replace(" ", "")
    cifras, hemisferio = limpio[:-1], limpio[-1]
    grados, minutos = int(cifras[:-2]), int(cifras[-2:])
    valor = grados + minutos / 60
    return round(-valor if hemisferio in "SW" else valor, DECIMALES)


def _fecha_texto(dia: str, mes: str, anio: str) -> datetime | None:
    numero = _MESES.get(mes[:3].lower())
    if numero is None:
        return None
    anio_completo = int(anio) + (2000 if len(anio) == 2 else 0)
    try:
        return datetime(anio_completo, numero, int(dia), tzinfo=UTC)
    except ValueError:
        return None


def _reunion(texto: str) -> datetime | None:
    m = _REUNION.search(texto)
    return _fecha_texto(m[1], m[2], m[3]) if m else None


def _frase(texto: str) -> str:
    return " ".join(texto.split()[:MAX_PALABRAS])


def _opinion(cuerpo: str) -> str | None:
    m = _OPINION.search(cuerpo)
    return _frase(m[1]) if m else None


def bloques_consolidados(texto: str) -> dict[str, Bloque]:
    """Las filas de una hoja consolidada (drones, globos, aeromodelos y objetos)."""
    reunion = _reunion(texto)
    limpio = _limpiar(texto)
    cabeceras = list(_CABECERA_FILA.finditer(limpio))
    resultado: dict[str, Bloque] = {}
    for i, m in enumerate(cabeceras):
        fin = cabeceras[i + 1].start() if i + 1 < len(cabeceras) else len(limpio)
        lineas = [x.strip() for x in limpio[m.end() : fin].splitlines()]
        lineas = [x for x in lineas if x]
        bloque = Bloque(numero=m["num"], fecha=_fecha_texto(m["dia"], m["mes"], m["anio"]),
                        reunion=reunion)  # fmt: skip
        posicion = next((j for j, x in enumerate(lineas) if _POSICION.match(x)), None)
        if posicion is None:
            continue
        if lineas and (h := _HORA.match(lineas[0])):
            bloque.hora = (int(h[1]), int(h[2]))
        cabeza = lineas[1:posicion] if bloque.hora else lineas[:posicion]
        # Aeronave, su operador entre paréntesis y el objeto, que a veces ocupa dos líneas
        # («Unk» y «Obj») antes de la posición.
        operador = next(
            (j for j, x in enumerate(cabeza) if x.startswith("(") and x.endswith(")")), None
        )
        aeronaves = cabeza if operador is None else cabeza[:operador]
        bloque.aeronave = " ".join(aeronaves) or None
        bloque.operador = cabeza[operador].strip("()") if operador is not None else None
        p = _POSICION.match(lineas[posicion])
        assert p is not None
        antes = cabeza[operador + 1 :] if operador is not None else []
        bloque.objeto = " ".join([*antes, p["objeto"].strip()]).strip() or None
        bloque.lat, bloque.lon = _gms_pdf(p["lat"]), _gms_pdf(p["lon"])
        resto = lineas[posicion + 1 :]
        # Punto de referencia, altitud, espacio aéreo y su clase, en ese orden.
        if resto:
            bloque.ubicacion = resto.pop(0)
        if resto and re.search(r"\d\s*ft|FL\s?\d|\bft\b", resto[0], re.I):
            bloque.altitud = resto.pop(0)
        if resto and not resto[0].startswith("("):
            bloque.espacio = resto.pop(0)
        if resto and re.fullmatch(r"\(([A-G](?:/[A-G])?|Other)\)", resto[0]):
            bloque.clase_espacio = resto.pop(0).strip("()")
        cuerpo = "\n".join(resto)
        if (r := _RIESGO_FINAL.search(cuerpo)) is not None:
            bloque.riesgo = r[1]
            cuerpo = cuerpo[: r.start(1)]
        elif (r := _RIESGO_DECLARADO.search(cuerpo)) is not None:
            bloque.riesgo = r[1]
        bloque.cuerpo = cuerpo
        if s := _SEPARACION.search(cuerpo):
            bloque.separacion = " ".join(s["sep"].split())
        if r2 := _RIESGO_NOTIFICADO.search(cuerpo):
            bloque.riesgo_notificado = r2["r"]
        bloque.opinion = _opinion(cuerpo)
        resultado[bloque.numero] = bloque
    return resultado


_INDIVIDUAL = re.compile(
    r"AIRPROX\s+REPORT\s+No\.?\s*(?P<num>20\d{5}).*?Date:?\s*(?P<dia>\d{1,2})\s+(?P<mes>[A-Za-z]{3})\w*"
    r"\s+(?P<anio>\d{4})\s+Time:?\s*(?P<hora>\d{4})\s*Z.*?Position:?\s*(?P<lat>\d{4}\s?[NS])\s+"
    r"(?P<lon>\d{5}\s?[EW])(?:\s+Location:?\s*(?P<ubicacion>[^\n(]+))?",
    re.S,
)


def bloque_individual(texto: str) -> Bloque | None:
    """El informe individual de los años anteriores a las hojas consolidadas."""
    m = _INDIVIDUAL.search(texto)
    if m is None:
        return None
    bloque = Bloque(
        numero=m["num"],
        fecha=_fecha_texto(m["dia"], m["mes"], m["anio"]),
        hora=(int(m["hora"][:2]), int(m["hora"][2:])),
        lat=_gms_pdf(m["lat"]),
        lon=_gms_pdf(m["lon"]),
        ubicacion=_texto(m["ubicacion"]),
    )
    if s := _SEPARACION_INDIVIDUAL.search(texto):
        bloque.separacion = " ".join(s["sep"].split())
    bloque.cuerpo = texto[m.end() :]
    if r := re.search(r"PART C.*?Risk\s*:?\s*([A-E])\b", texto, re.S | re.I):
        bloque.riesgo = r[1]
    bloque.opinion = _opinion(bloque.cuerpo)
    return bloque


def bloques(texto: str) -> dict[str, Bloque]:
    if "Consolidated" in texto[:400]:
        return bloques_consolidados(texto)
    individual = bloque_individual(texto)
    return {individual.numero: individual} if individual else {}


# --- Valores -------------------------------------------------------------------------

_MEDIDA = re.compile(
    r"(?P<a>\d+(?:\.\d+)?)\s*(?:-|–|to)?\s*(?P<b>\d+(?:\.\d+)?)?\s*(?P<u>ft|feet|m|metres?|"
    r"meters?|nm|yds?|yards?|km)?",
    re.I,
)
_UNIDADES = {"ft": PIE_A_M, "feet": PIE_A_M, "m": 1.0, "metre": 1.0, "metres": 1.0,
             "meter": 1.0, "meters": 1.0, "nm": MILLA_NAUTICA_M, "yd": YARDA_M, "yds": YARDA_M,
             "yard": YARDA_M, "yards": YARDA_M, "km": 1000.0}  # fmt: skip


def _distancia(parte: str, unidad_por_defecto: str | None) -> dict[str, float] | None:
    """«50ft», «50-100ft», «0.25NM», «Nil» (0) en metros; None si no se entiende."""
    limpio = parte.strip().strip("~≈c.").strip()
    if re.fullmatch(r"(nil|0)", limpio, re.I):
        return {"min": 0.0, "max": 0.0}
    m = _MEDIDA.match(limpio)
    if m is None or not m["a"]:
        return None
    unidad = (m["u"] or unidad_por_defecto or "").lower()
    if unidad not in _UNIDADES:
        return None
    factor = _UNIDADES[unidad]
    minimo = float(m["a"]) * factor
    maximo = float(m["b"]) * factor if m["b"] else minimo
    if maximo < minimo:
        return None
    return {"min": round(minimo, 2), "max": round(maximo, 2)}


def separacion(texto: str) -> Documento:
    """«50ft V/0m H», «300ftV/ 0M H», «0ft V/50-100ft H», «NK» → vertical y horizontal."""
    resultado: Documento = {"texto": " ".join(texto.split())}
    m = re.match(r"^(?P<v>.*?)\s*V\s*/\s*(?P<h>.*?)\s*H\b", resultado["texto"], re.I)
    if m is None:
        return resultado
    vertical = _distancia(m["v"], "ft")
    horizontal = _distancia(m["h"], None)
    if vertical is not None:
        resultado["vertical_m"] = vertical
    if horizontal is not None:
        resultado["horizontal_m"] = horizontal
    return resultado


def altitud(valor: Any) -> Documento | None:
    """Altitud de la aeronave: número del catálogo o texto del informe («375ft», «310ft agl»,
    «FL078»)."""
    if isinstance(valor, float):
        return {"pies": int(valor), "texto": f"{int(valor)}ft", "referencia": "sin_referencia"}
    texto = _texto(valor)
    if texto is None:
        return None
    if m := re.search(r"FL\s?(\d{2,3})", texto, re.I):
        return {"pies": int(m[1]) * 100, "texto": texto, "referencia": "nivel_vuelo"}
    if m := re.search(r"(\d[\d,]*)\s*ft", texto, re.I):
        pies = int(m[1].replace(",", ""))
        referencia = "agl" if re.search(r"\bagl\b", texto, re.I) else "sin_referencia"
        return {"pies": pies, "texto": texto, "referencia": referencia}
    return None


_MULTIRROTOR = re.compile(r"quad-?copter|multi-?rotor|hexa-?copter|octo-?copter|rotors|"
                          r"\bDJI\b|mavic|phantom|propellers", re.I)  # fmt: skip
_ALA_FIJA = re.compile(r"fixed[- ]wing|delta[- ]wing|\bwings?\b|plane-like|model aircraft", re.I)


def clase(texto: str) -> str:
    """Clase del objeto por las palabras con que lo describe el informe."""
    multirrotor, ala = bool(_MULTIRROTOR.search(texto)), bool(_ALA_FIJA.search(texto))
    if multirrotor and not ala:
        return "multirrotor_pequeno"
    if ala and not multirrotor:
        return "ala_fija"
    return "desconocido"


def descripcion(cuerpo: str) -> str | None:
    """La frase del informe del piloto que describe el objeto, literal y con 25 palabras como
    mucho: la primera que lo nombra dentro del informe del piloto o, si no, del texto."""
    texto = " ".join(cuerpo.split())
    inicio = _PILOTO.search(texto)
    frases = [
        f for f in re.split(r"(?<=[.!?])\s+", texto[inicio.start() :] if inicio else texto)
        if _PALABRAS_OBJETO.search(f)
        and not f.startswith(("In the Board", "The Board", "Reported", "Risk:", "Cause:"))
    ]  # fmt: skip
    # La que describe su aspecto (color, forma, tamaño); si ninguna, la primera que lo nombra.
    elegida = next((f for f in frases if _ASPECTO.search(f)), frases[0] if frases else None)
    return _frase(elegida) if elegida else None


def _altura_objeto(alt: Documento | None, sep: Documento) -> dict[str, float] | None:
    """La altitud de la aeronave más o menos la separación vertical notificada."""
    if alt is None or "vertical_m" not in sep:
        return None
    base = alt["pies"] * PIE_A_M
    vertical = sep["vertical_m"]
    return {
        "min": round(max(0.0, base - vertical["max"]), 2),
        "max": round(base + vertical["max"], 2),
    }


# --- Índice: el Excel histórico de drones y objetos -----------------------------------

_EXCEL_INDICE = re.compile(r'href="(?P<href>/media/[^"]+\.xlsx)"', re.I)
# Columnas del Excel histórico.
INDICE_NUMERO, INDICE_FECHA, INDICE_AERONAVE = "Airprox No", "Date", "Aircraft"
INDICE_OBJETO, INDICE_LAT, INDICE_LON = "Object", "Latitude", "Longitude"
INDICE_ALTITUD, INDICE_LUGAR = "Alt", "Reported Location"


def enlace_indice(html: str) -> str | None:
    m = _EXCEL_INDICE.search(html)
    return BASE + m["href"] if m else None


def _riesgo_indice(fila: dict[str, Any]) -> str | None:
    """La columna del riesgo lleva en el Excel un nombre roto («Risk+J:K»)."""
    for clave, valor in fila.items():
        if clave.startswith("Risk") and (texto := _texto(valor)) in RIESGOS:
            return texto
    return None


def indice(filas: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Por número, las filas del Excel histórico que no son globos."""
    resultado = {}
    for fila in filas:
        numero = _numero(fila.get(INDICE_NUMERO))
        objeto = _texto(fila.get(INDICE_OBJETO))
        if numero and objeto and not _NO_DRON.search(objeto):
            resultado[numero] = fila
    return resultado


# --- Encuentros -----------------------------------------------------------------------

RIESGOS = frozenset({"A", "B", "C", "D", "E"})


def _instante(momento: datetime, precision: str = "minuto") -> Documento:
    return {"valor": momento.strftime("%Y-%m-%dT%H:%MZ"), "precision": precision}


def _gms_indice(valor: Any) -> float | None:
    texto = _texto(valor)
    if texto is None or not re.fullmatch(r"\d{4,5}\s?[NSEW]", texto):
        return None
    return _gms_pdf(texto)


def _posicion(
    fila: dict[str, Any] | None, indice_fila: dict[str, Any] | None, bloque: Bloque | None
) -> Documento:
    lat = _coordenada_excel(fila.get("Latitude")) if fila else None
    lon = _coordenada_excel(fila.get("Longitude")) if fila else None
    if (lat is None or lon is None) and indice_fila:
        lat, lon = (
            _gms_indice(indice_fila.get(INDICE_LAT)),
            _gms_indice(indice_fila.get(INDICE_LON)),
        )
    if (lat is None or lon is None) and bloque:
        lat, lon = bloque.lat, bloque.lon
    posicion: Documento = {}
    if lat is not None and lon is not None:
        posicion["punto"] = {"lat": lat, "lon": lon}
    lugar = (bloque.ubicacion if bloque else None) or (
        _texto(indice_fila.get(INDICE_LUGAR)) if indice_fila else None
    )
    if lugar:
        posicion["descripcion"] = lugar
    return posicion


def _altitud(
    fila: dict[str, Any] | None, indice_fila: dict[str, Any] | None, bloque: Bloque | None
) -> Documento | None:
    alt = None
    for valor in (
        fila.get("Altitude (ft)") if fila else None,
        indice_fila.get(INDICE_ALTITUD) if indice_fila else None,
    ):
        if valor is not None and alt is None:
            alt = altitud(valor)
    # El informe dice si es sobre el terreno o un nivel de vuelo; el catálogo, solo los pies.
    if bloque and bloque.altitud and (alt is None or alt["referencia"] == "sin_referencia"):
        alt = altitud(bloque.altitud) or alt
    return alt


def _aeronave(
    fila: dict[str, Any] | None,
    otro: int,
    indice_fila: dict[str, Any] | None,
    bloque: Bloque | None,
) -> tuple[Documento, Documento]:
    """La aeronave afectada y su espacio aéreo."""
    espacio: Documento = {}
    if fila and (clase_ := _texto(fila.get(f"Aircraft {otro} Airspace"))):
        espacio["clase"] = clase_
    elif bloque and bloque.clase_espacio:
        espacio["clase"] = bloque.clase_espacio
    if fila and (nombre := _texto(fila.get(f"Aircraft {otro} Airspace Name"))):
        espacio["nombre"] = nombre
    elif bloque and bloque.espacio:
        espacio["nombre"] = bloque.espacio
    aeronave: Documento = {}
    if fila:
        for clave, columna in (("tipo", "Type"), ("categoria", "Category"),
                               ("clasificacion_vuelo", "Flight Classification"),
                               ("servicio", "ATS"), ("reglas", "Flight Rules")):  # fmt: skip
            if valor := _texto(fila.get(f"Aircraft {otro} {columna}")):
                aeronave[clave] = valor
    if "tipo" not in aeronave:
        tipo = (_texto(indice_fila.get(INDICE_AERONAVE)) if indice_fila else None) or (
            bloque.aeronave if bloque else None
        )
        if tipo:
            aeronave["tipo"] = tipo
    if bloque and bloque.operador:
        aeronave["operador"] = bloque.operador
    return aeronave, espacio


def encuentro(
    numero: str,
    indice_fila: dict[str, Any] | None,
    fila: dict[str, Any] | None,
    bloque: Bloque | None,
    enlace: str,
    catalogo: str | None,
    alta: datetime,
) -> Documento | None:
    """El encuentro con los campos del Excel histórico, del catálogo del año y del informe. El
    catálogo manda en la hora, la posición y la aeronave; el Excel histórico, en la
    clasificación del objeto; el informe añade lo que no tienen. None si no hay fecha o si el
    objeto es un globo."""
    lado = lado_objeto(fila) if fila else None
    otro = 1 if lado == 2 else 2
    fecha = (
        (_fecha_excel(fila.get("Date")) if fila else None)
        or (_fecha_excel(indice_fila.get(INDICE_FECHA)) if indice_fila else None)
        or (bloque.fecha if bloque else None)
    )
    hora = (_hora_excel(fila.get("Time (UTC)")) if fila else None) or (
        bloque.hora if bloque else None
    )
    categoria = _texto(fila.get(f"Aircraft {lado} Category")) if fila and lado else None
    tipo = _texto(fila.get(f"Aircraft {lado} Type")) if fila and lado else None
    clasificacion = (
        (_texto(indice_fila.get(INDICE_OBJETO)) if indice_fila else None)
        or (bloque.objeto if bloque else None)
        or tipo
        or categoria
    )
    if fecha is None or clasificacion is None or _NO_DRON.search(clasificacion):
        return None
    id_ = f"UKAB-{numero}"
    parser = {"origen": "oficial", "metodo": "parser", "fuentes": [id_]}
    regla = {"origen": "oficial", "metodo": "regla", "fuentes": [id_]}
    instante = (
        _instante(fecha.replace(hour=hora[0], minute=hora[1])) if hora else _instante(fecha, "dia")
    )
    procedencia: Documento = {"instante": parser, "pais": regla}
    documento: Documento = {
        "id": id_, "autoridad": AUTORIDAD, "numero": numero, "enlace": enlace,
        "instante": instante, "pais": PAIS,
    }  # fmt: skip
    if catalogo:
        documento["catalogo"] = catalogo
    if bloque and bloque.reunion:
        documento["reunion"] = bloque.reunion.strftime("%Y-%m-%d")
    if fila and (luz := _texto(fila.get("Day/Night"))):
        documento["luz"] = luz
        procedencia["luz"] = parser
    if posicion := _posicion(fila, indice_fila, bloque):
        documento["posicion"] = posicion
        procedencia["posicion"] = parser
    alt = _altitud(fila, indice_fila, bloque)
    if alt is not None:
        documento["altitud"] = alt
        procedencia["altitud"] = parser
    aeronave, espacio = _aeronave(fila, otro, indice_fila, bloque)
    if espacio:
        documento["espacio_aereo"] = espacio
        procedencia["espacio_aereo"] = parser
    if aeronave:
        documento["aeronave"] = aeronave
        procedencia["aeronave"] = parser
    objeto: Documento = {"clasificacion": clasificacion}
    if categoria:
        objeto["categoria_catalogo"] = categoria
    if tipo:
        objeto["tipo_catalogo"] = tipo
    procedencia["objeto.clasificacion"] = parser
    sep: Documento = separacion(bloque.separacion) if bloque and bloque.separacion else {}
    if bloque:
        if bloque.opinion:
            objeto["opinion_junta"] = bloque.opinion
            procedencia["objeto.opinion_junta"] = parser
        if texto := descripcion(bloque.cuerpo):
            objeto["descripcion"] = texto
            procedencia["objeto.descripcion"] = parser
            objeto["clase"] = clase(texto)
            procedencia["objeto.clase"] = regla
    if (altura := _altura_objeto(alt, sep)) is not None:
        objeto["altura_m"] = altura
        procedencia["objeto.altura_m"] = regla
    documento["objeto"] = objeto
    if sep:
        documento["separacion"] = sep
        procedencia["separacion"] = parser
    if bloque and bloque.riesgo_notificado:
        documento["riesgo_notificado"] = bloque.riesgo_notificado
        procedencia["riesgo_notificado"] = parser
    riesgos = (
        _texto(fila.get("Risk Category")) if fila else None,
        _riesgo_indice(indice_fila) if indice_fila else None,
        bloque.riesgo if bloque else None,
    )
    if (riesgo := next((r for r in riesgos if r in RIESGOS), None)) is not None:
        documento["categoria_riesgo"] = riesgo
        procedencia["categoria_riesgo"] = parser
    documento["fuente"] = {
        "medio": AUTORIDAD, "fiabilidad": FIABILIDAD, "credibilidad": CREDIBILIDAD,
        "licencia": LICENCIA,
    }  # fmt: skip
    documento["procedencia"] = dict(sorted(procedencia.items()))
    documento["control"] = {"alta": _instante(alta), "lector": VERSION}
    return documento


# --- Datos en disco y recogida ---------------------------------------------------------


def _huella(texto: str) -> str:
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()[:20]


class Datos:
    """Carpeta de datos de la UKAB: Excel histórico, catálogos, textos de informes e índice."""

    def __init__(self, raiz: Path) -> None:
        self.raiz = raiz
        self.textos = raiz / "textos"
        self.catalogos = raiz / "catalogos"
        self.indice_ruta = raiz / "indice.json"
        self.historico_ruta = raiz / "ua_other.xlsx"

    def indice(self) -> dict[str, Any]:
        if not self.indice_ruta.exists():
            return {"anios": {}}
        datos: dict[str, Any] = json.loads(self.indice_ruta.read_text(encoding="utf-8"))
        return datos

    def guardar_indice(self, indice_: dict[str, Any]) -> None:
        self.raiz.mkdir(parents=True, exist_ok=True)
        temporal = self.indice_ruta.with_suffix(".tmp")
        temporal.write_text(json.dumps(indice_, ensure_ascii=False, sort_keys=True, indent=1),
                            encoding="utf-8", newline="\n")  # fmt: skip
        temporal.replace(self.indice_ruta)

    def historico(self) -> dict[str, dict[str, Any]]:
        if not self.historico_ruta.exists():
            return {}
        return indice(leer_xlsx(self.historico_ruta.read_bytes()))

    def texto(self, url: str) -> str | None:
        ruta = self.textos / f"{_huella(url)}.txt.gz"
        return gzip.decompress(ruta.read_bytes()).decode("utf-8") if ruta.exists() else None

    def guardar_texto(self, url: str, texto: str) -> None:
        self.textos.mkdir(parents=True, exist_ok=True)
        ruta = self.textos / f"{_huella(url)}.txt.gz"
        ruta.write_bytes(gzip.compress(texto.encode("utf-8"), mtime=0))

    def catalogo(self, anio: int) -> bytes | None:
        ruta = self.catalogos / f"{anio}.xlsx"
        return ruta.read_bytes() if ruta.exists() else None

    def guardar_catalogo(self, anio: int, datos: bytes) -> None:
        self.catalogos.mkdir(parents=True, exist_ok=True)
        (self.catalogos / f"{anio}.xlsx").write_bytes(datos)


def _es_pdf(datos: bytes) -> bool:
    return datos[:5] == b"%PDF-"


def _es_xlsx(datos: bytes) -> bool:
    return datos[:2] == b"PK"


@dataclass
class Recuentos:
    anios: int = 0
    informes_nuevos: int = 0
    fallidos: int = 0
    encuentros: int = 0

    def texto(self) -> str:
        return (
            f"años={self.anios} informes_nuevos={self.informes_nuevos} "
            f"fallidos={self.fallidos} encuentros={self.encuentros}"
        )


def _numero(valor: Any) -> str | None:
    if isinstance(valor, float):
        return f"{int(valor):07d}"
    texto = _texto(valor)
    return texto if texto and re.fullmatch(r"\d{7}", texto) else None


def _es_pagina(texto: str) -> bool:
    return "Airprox" in texto and "<html" in texto


def recoger(
    datos: Datos,
    descargador: Descargador,
    anios: list[int],
    actualizar: frozenset[int] = frozenset(),
) -> Recuentos:
    """Descarga lo que falta: el Excel histórico (siempre: es el índice al día), y de cada año
    pedido con algún encuentro su página, su catálogo (si se publicó y es un año a actualizar
    o aún no se tiene) y el informe de cada encuentro. Lo ya descargado no se vuelve a pedir."""
    recuentos = Recuentos()
    enlace = enlace_indice(descargador.texto(DRONES, _es_pagina))
    if enlace is None:
        raise DescargaFallida("la página de drones de la UKAB no enlaza el Excel histórico")
    datos.raiz.mkdir(parents=True, exist_ok=True)
    datos.historico_ruta.write_bytes(descargador.contenido(enlace, _es_xlsx))
    por_anio: dict[int, list[str]] = {}
    for numero in datos.historico():
        por_anio.setdefault(int(numero[:4]), []).append(numero)
    registro_ = datos.indice()
    registro_["historico"] = enlace
    for anio in anios:
        if anio not in por_anio:
            continue
        pagina = leer_pagina_anio(descargador.texto(LISTA.format(anio=anio), _es_pagina))
        recuentos.anios += 1
        entrada = registro_["anios"].setdefault(str(anio), {})
        entrada["informes"] = pagina.informes
        entrada["catalogo"] = pagina.catalogo
        if pagina.catalogo and (datos.catalogo(anio) is None or anio in actualizar):
            datos.guardar_catalogo(anio, descargador.contenido(pagina.catalogo, _es_xlsx))
        for numero in sorted(por_anio[anio]):
            url = pagina.informes.get(numero)
            if url is None or datos.texto(url) is not None:
                continue
            try:
                texto = texto_pdf(descargador.contenido(url, _es_pdf))
            except (DescargaFallida, ValueError) as error:
                registro.warning("airprox: %s no se lee: %s", numero, error)
                recuentos.fallidos += 1
                continue
            datos.guardar_texto(url, texto)
            recuentos.informes_nuevos += 1
        datos.guardar_indice(registro_)
    datos.guardar_indice(registro_)
    return recuentos


def encuentros(datos: Datos, alta: datetime) -> list[Documento]:
    """Todos los encuentros que dan los datos descargados, en orden de número."""
    buscados = datos.historico()
    registro_ = datos.indice()
    resultado: dict[str, Documento] = {}
    for anio, entrada in sorted(registro_["anios"].items()):
        informes: dict[str, str] = entrada.get("informes", {})
        contenido = datos.catalogo(int(anio)) if entrada.get("catalogo") else None
        filas = {
            n: f for f in (leer_xlsx(contenido) if contenido else [])
            if (n := _numero(f.get("Airprox No")))
        }  # fmt: skip
        leidos: dict[str, Bloque] = {}
        for url in sorted(set(informes.values())):
            texto = datos.texto(url)
            if texto:
                for numero, bloque in bloques(texto).items():
                    leidos.setdefault(numero, bloque)
        for numero in sorted(n for n in buscados if n[:4] == anio):
            enlace = informes.get(numero)
            if enlace is None:
                continue
            documento = encuentro(numero, buscados[numero], filas.get(numero), leidos.get(numero),
                                  enlace, entrada.get("catalogo"), alta)  # fmt: skip
            if documento is not None:
                resultado[documento["id"]] = documento
    return [resultado[k] for k in sorted(resultado)]


def principal(argumentos: list[str] | None = None) -> int:
    opciones = argparse.ArgumentParser(description=__doc__)
    opciones.add_argument("carpeta", type=Path)
    opciones.add_argument("--desde", type=int, default=PRIMER_ANIO)
    opciones.add_argument("--hasta", type=int, default=datetime.now(UTC).year)
    args = opciones.parse_args(argumentos)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    datos = Datos(args.carpeta)
    anios = list(range(args.desde, args.hasta + 1))
    recuentos = recoger(datos, Descargador(agente=AGENTE_EODI), anios, frozenset(anios[-2:]))
    recuentos.encuentros = len(encuentros(datos, datetime.now(UTC)))
    registro.info("airprox %s", recuentos.texto())
    return 0


if __name__ == "__main__":
    sys.exit(principal())
