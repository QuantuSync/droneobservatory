"""Paquete trimestral de los datos abiertos para Discuss Data (repositorio de datos de
investigación sobre Europa del Este de la Universidad de Bremen y la Biblioteca de Gotinga, que da
DOI y admite versiones).

Funciones puras: reciben los ficheros de la descarga abierta de la web (los mismos bytes que
sirve /datos/) y la página de metodología en inglés, y devuelven el .zip fechado
(`eodi-incidentes-AAAA-MM-DD.zip`). Lo baja, lo guarda y avisa recogida/discuss_data.py.

Contenido del paquete (en inglés, porque es para una comunidad internacional):

- data/incidents.csv, data/incidents.geojson y data/incidents_approximate_location.json: el
  conjunto de incidentes tal como lo publica la web (CSV y GeoJSON de los que tienen punto y el
  JSON de los que solo tienen un lugar aproximado), con una sola diferencia: el bloque
  `trafico_aereo`, que deriva del archivo de adsb.lol (ODbL 1.0), sale de los dos JSON;
- data/air_traffic_odbl.json: ese bloque, aparte, con su licencia ODbL 1.0 y su atribución;
- README.md: qué es el observatorio, qué contiene el paquete, fecha de corte, cifras, cada campo,
  los estados y la presencia del dron, la regla de la declaración oficial, enlaces, avisos,
  licencias y cita;
- METHODOLOGY.md: la página de metodología en inglés de la web (/en/methodology), convertida;
- LICENSE.md (CC BY 4.0 y la excepción ODbL), CITATION.cff y CHANGELOG.md (cambios respecto a la
  versión anterior del paquete, o «First version»).

Las coordenadas que salen de los nomenclátores de OpenStreetMap (configuracion/lugares_europa.json
e instalaciones_europa.json) son resultados de geocodificación sueltos, uno por incidente: según la
guía de geocodificación de la OSMF son extractos no sustanciales que pueden ir con otros datos y
otra licencia, con la atribución a OpenStreetMap (va en el README y en LICENSE.md). Las de GeoNames
son CC BY 4.0, compatibles, también con su atribución.

La salida es determinista: los mismos ficheros de entrada y la misma fecha dan el mismo .zip,
byte a byte.
"""

from __future__ import annotations

import csv
import html
import io
import json
import re
import zipfile
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from html.parser import HTMLParser
from typing import Any, ClassVar

SITIO = "https://droneobservatory.eu"
METODOLOGIA_EN = f"{SITIO}/en/methodology"
DATOS_ABIERTOS_EN = f"{SITIO}/en/methodology#datos-abiertos"
AVISOS_EN = f"{SITIO}/en/alerts"
PREFIJO_NOMBRE = "eodi-incidentes-"

# Ficheros de la descarga abierta que entran en el paquete, con su nombre dentro del .zip.
FICHEROS = {
    "incidentes.csv": "data/incidents.csv",
    "incidentes.geojson": "data/incidents.geojson",
    "incidentes_sin_ubicacion.json": "data/incidents_approximate_location.json",
}
RESUMEN = "resumen.json"
TRAFICO = "data/air_traffic_odbl.json"
BLOQUE_ODBL = "trafico_aereo"


class PaqueteInvalido(ValueError):
    pass


def nombre_paquete(fecha: date) -> str:
    return f"{PREFIJO_NOMBRE}{fecha.isoformat()}.zip"


def fecha_de_nombre(nombre: str) -> date | None:
    m = re.fullmatch(rf"(?:.*/)?{PREFIJO_NOMBRE}(\d{{4}}-\d{{2}}-\d{{2}})\.zip", nombre)
    return date.fromisoformat(m[1]) if m else None


def trimestre(fecha: date) -> str:
    """El trimestre de una fecha: «2026-T4». Hay un paquete por trimestre."""
    return f"{fecha.year}-T{(fecha.month - 1) // 3 + 1}"


# --- Los incidentes ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Incidentes:
    """Los incidentes del paquete: los del mapa (GeoJSON) y los de lugar aproximado."""

    mapa: dict[str, Any]
    aproximados: dict[str, Any]

    def propiedades(self) -> list[dict[str, Any]]:
        con_punto = [f["properties"] for f in self.mapa["features"]]
        return con_punto + [i.get("properties", i) for i in self.aproximados["incidentes"]]


def leer_incidentes(ficheros: dict[str, bytes]) -> Incidentes:
    mapa = json.loads(ficheros["incidentes.geojson"])
    aproximados = json.loads(ficheros["incidentes_sin_ubicacion.json"])
    if not isinstance(mapa.get("features"), list) or not isinstance(
        aproximados.get("incidentes"), list
    ):
        raise PaqueteInvalido("los ficheros de incidentes no tienen la forma esperada")
    return Incidentes(mapa, aproximados)


def _identificador(documento: dict[str, Any]) -> str:
    return str(documento.get("id") or documento.get("properties", {}).get("id"))


def separar_trafico(documentos: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Quita el bloque ODbL de cada incidente (en su sitio) y lo devuelve aparte, por código."""
    aparte: dict[str, Any] = {}
    for documento in documentos:
        propiedades = documento.get("properties", documento)
        if BLOQUE_ODBL in propiedades:
            aparte[_identificador(documento)] = propiedades.pop(BLOQUE_ODBL)
    return dict(sorted(aparte.items()))


def _json(datos: Any) -> bytes:
    """Como los escribe la web (compactos, sin salto final): sin el bloque ODbL, un fichero queda
    igual byte a byte que el de la descarga abierta."""
    return json.dumps(datos, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


# --- Metodología: de la página HTML a Markdown --------------------------------------------------


class _AMarkdown(HTMLParser):
    """Convierte el <main> de una página de texto de la web en Markdown sencillo."""

    BLOQUES: ClassVar[set[str]] = {
        "p",
        "dd",
        "li",
        "h1",
        "h2",
        "h3",
        "h4",
        "dt",
        "figcaption",
        "caption",
    }

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.dentro = 0
        self.saltar = 0
        self.lineas: list[str] = []
        self.actual: list[str] = []
        self.prefijo = ""
        self.enlace: str | None = None

    def handle_starttag(self, etiqueta: str, atributos: list[tuple[str, str | None]]) -> None:
        if etiqueta == "main":
            self.dentro += 1
            return
        if not self.dentro:
            return
        if etiqueta in {"nav", "script", "style", "svg", "button", "form"}:
            self.saltar += 1
        if self.saltar:
            return
        if etiqueta in self.BLOQUES:
            self._cerrar()
            self.prefijo = {
                "h1": "# ", "h2": "## ", "h3": "### ", "h4": "#### ", "li": "- ", "dt": "**",
            }.get(etiqueta, "")  # fmt: skip
        elif etiqueta == "br":
            self.actual.append(" ")
        elif etiqueta == "a":
            destino = dict(atributos).get("href") or ""
            if destino.startswith("/"):
                destino = SITIO + destino
            elif destino.startswith("#"):
                destino = METODOLOGIA_EN + destino
            self.enlace = destino or None
            self.actual.append("[")

    def handle_endtag(self, etiqueta: str) -> None:
        if etiqueta == "main":
            self._cerrar()
            self.dentro = max(0, self.dentro - 1)
            return
        if not self.dentro:
            return
        if etiqueta in {"nav", "script", "style", "svg", "button", "form"}:
            self.saltar = max(0, self.saltar - 1)
            return
        if self.saltar:
            return
        if etiqueta == "a":
            self.actual.append(f"]({self.enlace})" if self.enlace else "]")
            self.enlace = None
        elif etiqueta in self.BLOQUES:
            if etiqueta == "dt":
                self.actual.append("**")
            self._cerrar()

    def handle_data(self, texto: str) -> None:
        if self.dentro and not self.saltar:
            self.actual.append(texto)

    def _cerrar(self) -> None:
        texto = re.sub(r"\s+", " ", "".join(self.actual)).strip()
        texto = texto.replace("[ ", "[").replace(" ]", "]")
        if texto and texto not in {"**", "****"}:
            self.lineas.append(self.prefijo + texto)
        self.actual = []
        self.prefijo = ""


def metodologia_markdown(pagina: str) -> str:
    """La metodología en inglés, en Markdown, desde el HTML de /en/methodology."""
    conversor = _AMarkdown()
    conversor.feed(pagina)
    conversor.close()
    lineas = conversor.lineas
    if len(lineas) < 20 or not lineas[0].startswith("# "):
        raise PaqueteInvalido("la página de metodología no tiene el texto esperado")
    salida: list[str] = []
    for linea in lineas:
        es_lista = linea.startswith("- ")
        if salida and not (es_lista and salida[-1].startswith("- ")):
            salida.append("")
        salida.append(html.unescape(linea))
    cabecera = f"<!-- Exported from {METODOLOGIA_EN} when this package was generated. -->\n\n"
    return cabecera + "\n".join(salida) + "\n"


# --- Avisos -------------------------------------------------------------------------------------


def lineas_avisos(avisos: dict[str, Any], paises: Iterable[str]) -> list[str]:
    """Cómo suscribirse a los avisos: el canal de Europa y el de cada país del paquete."""
    servidor = avisos["servidor"]
    lineas = [
        f"- Server: {servidor} (ntfy, free and open source; apps for Android and iOS at "
        "https://ntfy.sh, or any ntfy client).",
        f"- All of Europe: topic `{avisos['general']['tema']}` "
        f"({servidor}/{avisos['general']['tema']}).",
        "- One country: topic `drones-<country>`, with the country's English name in lower case "
        "and hyphens. Countries with incidents in this package:",
    ]
    for codigo in sorted(set(paises)):
        pais = avisos["paises"].get(codigo)
        if pais:
            lineas.append(f"  - {pais['en']} ({codigo}): `{pais['tema']}`")
    return lineas


# --- Cambios respecto a la versión anterior ----------------------------------------------------


def _resumen_incidentes(incidentes: Incidentes) -> dict[str, tuple[str, str]]:
    return {
        str(p["id"]): (str(p["estado"]["actual"]), str(p.get("presencia_dron")))
        for p in incidentes.propiedades()
    }


def registro_de_cambios(
    fecha: date, actuales: Incidentes, anterior: tuple[date, Incidentes] | None
) -> str:
    cabecera = "# Changelog\n\n"
    if anterior is None:
        return (
            cabecera
            + f"## {fecha.isoformat()}\n\nFirst version of this package. It contains every "
            "incident published by the observatory up to the cut-off date stated in README.md.\n"
        )
    fecha_anterior, previos = anterior
    ahora = _resumen_incidentes(actuales)
    antes = _resumen_incidentes(previos)
    unidos: dict[str, str] = actuales.mapa.get("unidos") or {}
    nuevos = sorted(set(ahora) - set(antes))
    fuera = sorted(set(antes) - set(ahora))
    estados = sorted(c for c in set(ahora) & set(antes) if ahora[c][0] != antes[c][0])
    presencia = sorted(c for c in set(ahora) & set(antes) if ahora[c][1] != antes[c][1])
    partes = [
        cabecera,
        f"## {fecha.isoformat()}\n\n",
        f"Changes since the previous version ({fecha_anterior.isoformat()}): "
        f"{len(antes)} → {len(ahora)} incidents.\n\n",
        f"### New incidents ({len(nuevos)})\n\n",
        *(f"- {c}\n" for c in nuevos),
        "\n" if nuevos else "None.\n\n",
        f"### No longer listed ({len(fuera)})\n\n",
        "Nothing is deleted: an incident leaves the list only when it is merged into another "
        "record of the same event (its link redirects there) or withdrawn after review.\n\n",
        *(
            f"- {c}" + (f": merged into {unidos[c]}" if c in unidos else ": withdrawn") + "\n"
            for c in fuera
        ),
        "\n" if fuera else "None.\n\n",
        f"### Status changes ({len(estados)})\n\n",
        *(f"- {c}: {antes[c][0]} → {ahora[c][0]}\n" for c in estados),
        "\n" if estados else "None.\n\n",
        f"### Drone presence changes ({len(presencia)})\n\n",
        *(f"- {c}: {antes[c][1]} → {ahora[c][1]}\n" for c in presencia),
        "" if presencia else "None.\n",
    ]
    return "".join(partes)


# --- README, licencia y cita -------------------------------------------------------------------

CAMPOS_CSV = {
    "id": "Stable identifier of the incident (EODI-YYYY-NNNNN). Its page is `enlace`.",
    "tipo": "Type: `sobrevuelo` (overflight of a facility or area), `incursion` (entry into a "
    "country's airspace from outside) or `interrupcion_aeroportuaria` (airport disruption).",
    "estado": "Event status: `notificado`, `confirmado`, `atribuido` or `desmentido` (see "
    "«Statuses»).",
    "presencia_dron": "Drone presence: `confirmada`, `no_confirmada`, `no_acreditada` or "
    "`descartada` (see «Drone presence»).",
    "titulo_es / titulo_en": "Headline of the record, in Spanish and English, written by the "
    "observatory.",
    "inicio": "Start of the event, ISO 8601 in UTC (`YYYY-MM-DDTHH:MMZ`).",
    "inicio_precision": "Precision of `inicio`: `minuto`, `hora`, `dia` or `aproximada`.",
    "fin": "End of the event, if known (UTC).",
    "duracion_min": "Duration in minutes, if a source gives it.",
    "latitud / longitud": "Point of the incident (WGS 84). It is the centre of an area, not an "
    "exact position.",
    "radio_km": "Radius of that area in kilometres.",
    "pais": "Country where the event happened (ISO 3166-1 alpha-2). Overseas territories count "
    "as their country.",
    "localidad": "Locality named by the sources, if any.",
    "objetivo_categoria": "Category of the affected site: `aeropuerto`, `base_militar`, "
    "`puerto`, `energia`, `presa`, `estadio`, `industrial`, `gubernamental` or `otra`.",
    "objetivo_nombre": "Name of the affected site as the sources give it.",
    "objetivo_oaci": "ICAO code of the airport or aerodrome, if any.",
    "drones_min / drones_max": "Number of drones reported (a range); empty if unknown.",
    "cierre": "Whether the airport or airspace was closed: `si`, `no` or `desconocido`.",
    "medidas": "Response measures, separated by `|`: `patrulla`, `cazas` (fighter jets), "
    "`derribo` (shoot-down), `cierre_espacio_aereo`, `inhibicion` (jamming).",
    "atribucion_actor / atribucion_autoridad": "For attributed incidents only: who the "
    "authority holds responsible, and the authority that says so, in its own words.",
    "episodio": "Identifier of the episode (several incidents of the same night or wave), if any.",
    "fuentes": "Number of sources behind the record.",
    "ultima_actualizacion": "Last change of the record (UTC).",
    "enlace": "Page of the incident on droneobservatory.eu, with every source, quote and the "
    "full history.",
    "lugar_es / lugar_en": "Place name shown on the website, in Spanish and English.",
    "objetivo_es / objetivo_en": "Name of the affected site shown on the website, in Spanish and "
    "English.",
    "presencia_historial": "Changes of the drone presence, `date:value` separated by `|` "
    "(`:parcial` marks a partial official correction that does not change the value); empty if "
    "never rectified.",
}

ESTADOS = [
    ("notificado (reported)", "The news reports it. Initial status of every incident."),
    (
        "confirmado (confirmed)",
        "An official authority states that the incident happened. It means an authority has "
        "stated it, not that public physical evidence exists.",
    ),
    (
        "atribuido (attributed)",
        "A confirmed incident for which a competent authority (government, ministry, armed "
        "forces, prosecutor or police) expressly states, in its own words, who is responsible: a "
        "State or a person. A news report saying so, an investigation under way or a suspicion "
        "is not enough.",
    ),
    (
        "desmentido (denied)",
        "An authority denies the incident. It stays published, with the reason. Only another "
        "authority of equal or higher reliability can return it to confirmed.",
    ),
]

PRESENCIAS = [
    (
        "confirmada (confirmed)",
        "The competent authority (airport operator, air navigation service provider, police, "
        "armed forces, ministry, prosecutor or civil aviation authority) acts or states that the "
        "event was caused by a drone.",
    ),
    (
        "no_confirmada (not confirmed)",
        "The authority leaves it open («possible drone», «unidentified object») or only the "
        "press or witnesses report it.",
    ),
    (
        "no_acreditada (not substantiated)",
        "An official authority closed its investigation without evidence of the drone, or "
        "withdrew its statement without saying it was something else. It is not a denial.",
    ),
    (
        "descartada (ruled out)",
        "An authority says it was something else (a plane, a helicopter). It denies the drone, "
        "not the incident: if an airport closed, it closed.",
    ),
]


@dataclass(frozen=True)
class Cifras:
    incidentes: int
    con_punto: int
    aproximados: int
    paises: dict[str, int]
    estados: dict[str, int]
    presencias: dict[str, int]
    con_trafico: int


def cifras(incidentes: Incidentes, con_trafico: int) -> Cifras:
    propiedades = incidentes.propiedades()
    return Cifras(
        incidentes=len(propiedades),
        con_punto=len(incidentes.mapa["features"]),
        aproximados=len(incidentes.aproximados["incidentes"]),
        paises=dict(sorted(Counter(str(p["lugar"]["pais"]) for p in propiedades).items())),
        estados=dict(Counter(str(p["estado"]["actual"]) for p in propiedades).most_common()),
        presencias=dict(Counter(str(p.get("presencia_dron")) for p in propiedades).most_common()),
        con_trafico=con_trafico,
    )


def _tabla(filas: Iterable[tuple[str, str]], cabecera: tuple[str, str]) -> list[str]:
    lineas = [f"| {cabecera[0]} | {cabecera[1]} |", "| --- | --- |"]
    for a, b in filas:
        lineas.append("| " + a.replace("|", r"\|") + " | " + b.replace("|", r"\|") + " |")
    return lineas


def readme(
    fecha: date,
    corte: str,
    numeros: Cifras,
    licencia: dict[str, Any],
    avisos: dict[str, Any],
    nombres_pais: dict[str, str],
) -> str:
    autor = licencia["autor"]
    cita = licencia["cita"]["en"].format(anio=fecha.year, version=fecha.isoformat())
    paises = ", ".join(f"{nombres_pais.get(c, c)} ({n})" for c, n in numeros.paises.items())
    lineas = [
        f"# {licencia['titular']} (EODI): incidents, version {fecha.isoformat()}",
        "",
        "The European Observatory of Drone Incidents is a public register of drone incidents in "
        "Europe: unmanned aircraft that fly over a facility, enter a country's airspace from "
        "outside or disrupt the operation of an airport. Each incident keeps its sources, a short "
        "literal quote of each in its own language, its level of confirmation by official "
        "authorities and the full history of its changes. It covers all European soil, including "
        "overseas territories, and is updated every hour.",
        "",
        f"- Website: {SITIO}",
        f"- Original dataset and open download (always the latest data): {DATOS_ABIERTOS_EN}",
        f"- Methodology: {METODOLOGIA_EN} (copy in `METHODOLOGY.md`)",
        f"- Author: {autor['firma']['en']}, ORCID {autor['orcid']}",
        "",
        "## This version",
        "",
        f"- Package date: {fecha.isoformat()}. A new dated version is published every three "
        "months (January, April, July and October).",
        f"- Cut-off: data as published on {corte} (UTC).",
        f"- Incidents: {numeros.incidentes} ({numeros.con_punto} with a point on the map and "
        f"{numeros.aproximados} with an approximate location only).",
        f"- Countries: {len(numeros.paises)}: {paises}.",
        "- Event status: " + ", ".join(f"{k} {v}" for k, v in numeros.estados.items()) + ".",
        "- Drone presence: " + ", ".join(f"{k} {v}" for k, v in numeros.presencias.items()) + ".",
        "",
        "## Files",
        "",
        *_tabla(
            [
                (
                    "`data/incidents.csv`",
                    "Incidents with a point, one row per incident (UTF-8, "
                    "RFC 4180, CRLF). Same file as the website's CSV download.",
                ),
                (
                    "`data/incidents.geojson`",
                    "The same incidents as GeoJSON points, with every "
                    "public field: sources, quotes with translations, history, related records "
                    "and `unidos` (merged identifiers and the record they now point to). Same "
                    "file as the website's GeoJSON download, without the `trafico_aereo` block.",
                ),
                (
                    "`data/incidents_approximate_location.json`",
                    "Incidents placed only at country, region or sea level, with the same "
                    "fields. Same file as the website's download, without the `trafico_aereo` "
                    "block.",
                ),
                (
                    f"`{TRAFICO}`",
                    f"Measured air traffic for {numeros.con_trafico} incidents "
                    "(closures, diversions, holdings), by incident identifier. Separate because it "
                    "is licensed under ODbL 1.0 (see «Licences»).",
                ),
                ("`METHODOLOGY.md`", "The observatory's methodology, in English."),
                ("`LICENSE.md`", "Licences and attributions."),
                ("`CITATION.cff`", "How to cite this version (Citation File Format)."),
                ("`CHANGELOG.md`", "Changes since the previous version of this package."),
            ],
            ("File", "Content"),
        ),
        "",
        "## Rule: a status changes only with an official statement",
        "",
        "Every incident starts as `notificado`. Its status changes only when an official "
        "authority states something: it is confirmed when an authority says it happened, "
        "attributed only when a competent authority expressly says who is responsible, in its own "
        "words, and denied when an authority denies it. The press, witnesses, experts or the "
        "observatory itself never change a status. Every change is recorded with its date, the "
        "authority, the source link, an archived copy and the literal quote. Nothing is deleted: "
        "corrections are added to the history.",
        "",
        "### Statuses (`estado`)",
        "",
        *_tabla(ESTADOS, ("Value", "Meaning")),
        "",
        "### Drone presence (`presencia_dron`)",
        "",
        "The event status says whether the incident happened; drone presence says whether the "
        "authority attributes it to a drone.",
        "",
        *_tabla(PRESENCIAS, ("Value", "Meaning")),
        "",
        "## Fields of `incidents.csv`",
        "",
        *_tabla(
            ((f"`{k}`".replace(" / ", "` / `"), v) for k, v in CAMPOS_CSV.items()),
            ("Column", "Description"),
        ),
        "",
        "The GeoJSON files carry, in `properties`, the same data with its full structure: "
        "`fuentes` (each source with link, outlet, date, Admiralty reliability code and archived "
        "copy), `afirmaciones_publicas` (each fact by source, with the literal quote and its "
        "translations), `estado.historial`, `presencia_historial`, `objetivo`, `respuesta`, "
        "`relacionados`, `zona` (border or interior) and the other blocks described in "
        "`METHODOLOGY.md`. The JSON Schema of the records is in the observatory's code "
        "repository (`esquema/`).",
        "",
        "## Immediate alerts by country",
        "",
        "The observatory sends an immediate alert for each new incident in Europe that an "
        "authority confirms or attributes, or that an official source reports, and for airport "
        "closures caused by drones. Alerts are sent with ntfy, without registration:",
        "",
        *lineas_avisos(avisos, numeros.paises),
        "",
        f"Step-by-step instructions for phones and computers: {AVISOS_EN}",
        "",
        "## Licences",
        "",
        f"- The observatory's compilation (incidents, statuses, classifications and figures) is "
        f"published under {licencia['nombre']} ({licencia['url']}). Quoted sentences remain "
        "their authors' and are reproduced as short quotations with their source and link.",
        f"- `{TRAFICO}` is derived from the adsb.lol archive (© adsb.lol contributors) and is "
        "offered under the Open Database License 1.0 "
        "(https://opendatacommons.org/licenses/odbl/1-0/). It has been removed from the other "
        "files so that they carry only CC BY 4.0 data.",
        "- Some incident points were geocoded with gazetteers built from OpenStreetMap "
        "(© OpenStreetMap contributors, ODbL 1.0, https://www.openstreetmap.org/copyright): one "
        "coordinate per incident, an insubstantial extract under the OSMF Geocoding Guideline. "
        "Others come from GeoNames (CC BY 4.0, https://www.geonames.org) and OurAirports (public "
        "domain).",
        "- Thermal hotspots (`foco_termico`): we acknowledge the use of data from NASA's Fire "
        "Information for Resource Management System (FIRMS), part of NASA's ESDIS.",
        "",
        "## How to cite",
        "",
        cita,
        "",
        "Please cite the DOI of this version when available. The code of the observatory is "
        "open source under Apache-2.0.",
        "",
    ]
    return "\n".join(lineas)


def licencia_md(licencia: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Licences",
            "",
            f"## Data: {licencia['nombre']}",
            "",
            licencia["alcance"]["en"],
            "",
            f"Summary: {licencia['url']}  ",
            "Legal code: https://creativecommons.org/licenses/by/4.0/legalcode",
            "",
            f"Attribution: {licencia['titular']}, {licencia['autor']['firma']['en']} "
            f"({licencia['autor']['orcid']}), {licencia['fuente']}",
            "",
            f"## `{TRAFICO}`: ODbL 1.0",
            "",
            "Derived from the daily archive of adsb.lol (© adsb.lol contributors), distributed "
            "under the Open Database License 1.0. This file is a derivative database offered "
            "under the same licence: https://opendatacommons.org/licenses/odbl/1-0/",
            "",
            "## Third-party attributions",
            "",
            "- Places: © OpenStreetMap contributors (ODbL 1.0), "
            "https://www.openstreetmap.org/copyright; GeoNames (CC BY 4.0); OurAirports (public "
            "domain).",
            "- Thermal hotspots: NASA FIRMS (https://www.earthdata.nasa.gov/firms).",
            "- Quoted sentences belong to their authors and are used as short quotations.",
            "",
        ]
    )


def citation_cff(fecha: date, licencia: dict[str, Any], repositorio_cff: str) -> str:
    """El CITATION.cff del paquete: el del repositorio con la versión y la fecha del paquete."""
    cita = licencia["cita"]["en"].format(anio=fecha.year, version=fecha.isoformat())
    salida: list[str] = []
    saltar = False
    for linea in repositorio_cff.splitlines():
        if saltar and linea.startswith("  "):
            continue
        saltar = False
        if linea.startswith("#"):
            continue
        if linea.startswith("message:"):
            salida += ["message: >-", f"  If you use this data, please cite it as: {cita}"]
            saltar = True
        elif linea.startswith("title:"):
            salida.append(f'title: "{licencia["titular"]}: incidents (Discuss Data package)"')
        elif linea.startswith("version:"):
            salida.append(f'version: "{fecha.isoformat()}"')
        elif linea.startswith("date-released:"):
            salida.append(f'date-released: "{fecha.isoformat()}"')
        elif linea.startswith("repository-artifact:"):
            continue
        elif linea.startswith("abstract:"):
            salida += [
                "abstract: >-",
                "  Public register of drone incidents in Europe, each with its sources, literal",
                "  quotes and its level of confirmation by official authorities. A status changes",
                "  only with an official statement. Quarterly dated version of the open data of",
                f"  {SITIO} (CC BY 4.0; the measured air traffic file, ODbL 1.0).",
            ]
            saltar = True
        else:
            salida.append(linea)
    return "\n".join(salida) + "\n"


# --- El paquete ---------------------------------------------------------------------------------


def construir(
    ficheros: dict[str, bytes],
    pagina_metodologia: str,
    fecha: date,
    licencia: dict[str, Any],
    avisos: dict[str, Any],
    nombres_pais: dict[str, str],
    repositorio_cff: str,
    anterior: tuple[date, Incidentes] | None = None,
) -> tuple[bytes, dict[str, Any]]:
    """El .zip y su resumen (incidentes, países, ficheros con su huella)."""
    for nombre in [*FICHEROS, RESUMEN]:
        if not ficheros.get(nombre):
            raise PaqueteInvalido(f"falta {nombre}")
    corte = json.loads(ficheros[RESUMEN]).get("actualizado")
    if not corte:
        raise PaqueteInvalido("resumen.json sin fecha de actualización")
    incidentes = leer_incidentes(ficheros)
    numero_csv = sum(1 for _ in csv.DictReader(io.StringIO(ficheros["incidentes.csv"].decode())))
    if numero_csv != len(incidentes.mapa["features"]):
        raise PaqueteInvalido(
            f"el CSV tiene {numero_csv} filas y el GeoJSON {len(incidentes.mapa['features'])}"
        )
    trafico = separar_trafico([*incidentes.mapa["features"], *incidentes.aproximados["incidentes"]])
    numeros = cifras(incidentes, len(trafico))
    contenido: dict[str, bytes] = {
        "README.md": readme(fecha, corte, numeros, licencia, avisos, nombres_pais).encode(),
        "METHODOLOGY.md": metodologia_markdown(pagina_metodologia).encode(),
        "LICENSE.md": licencia_md(licencia).encode(),
        "CITATION.cff": citation_cff(fecha, licencia, repositorio_cff).encode(),
        "CHANGELOG.md": registro_de_cambios(fecha, incidentes, anterior).encode(),
        FICHEROS["incidentes.csv"]: ficheros["incidentes.csv"],
        FICHEROS["incidentes.geojson"]: _json(incidentes.mapa),
        FICHEROS["incidentes_sin_ubicacion.json"]: _json(incidentes.aproximados),
        TRAFICO: _json(
            {
                "licencia": {
                    "nombre": "ODbL 1.0",
                    "url": "https://opendatacommons.org/licenses/odbl/1-0/",
                    "atribucion": "© adsb.lol contributors (https://adsb.lol)",
                },
                "trafico_aereo": trafico,
            }
        ),
    }
    carpeta = nombre_paquete(fecha).removesuffix(".zip")
    salida = io.BytesIO()
    momento = (fecha.year, fecha.month, fecha.day, 0, 0, 0)
    with zipfile.ZipFile(salida, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as paquete:
        for nombre in sorted(contenido):
            info = zipfile.ZipInfo(f"{carpeta}/{nombre}", date_time=momento)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            paquete.writestr(info, contenido[nombre])
    resumen = {
        "nombre": nombre_paquete(fecha),
        "fecha": fecha.isoformat(),
        "corte": corte,
        "incidentes": numeros.incidentes,
        "paises": len(numeros.paises),
        "con_trafico_odbl": numeros.con_trafico,
        "ficheros": sorted(contenido),
    }
    return salida.getvalue(), resumen


def leer_paquete(datos: bytes) -> Incidentes:
    """Los incidentes de un paquete ya generado (para el registro de cambios del siguiente)."""
    with zipfile.ZipFile(io.BytesIO(datos)) as paquete:
        nombres = {n.split("/", 1)[1]: n for n in paquete.namelist() if "/" in n}
        mapa = json.loads(paquete.read(nombres[FICHEROS["incidentes.geojson"]]))
        aproximados = json.loads(paquete.read(nombres[FICHEROS["incidentes_sin_ubicacion.json"]]))
    return Incidentes(mapa, aproximados)
