"""Respuestas de gobiernos a preguntas parlamentarias sobre drones (fuentes de detalle).

Tres parlamentos con acceso automático verificado el 1 de octubre de 2026:

- **Bundestag** (`bundestag_dip`): API de DIP (search.dip.bundestag.de/api/v1). Pide una clave
  pública que el Bundestag publica en su página de ayuda y cambia de vez en cuando: se lee en
  cada ejecución de su API de contenidos (content.dip.bundestag.de) y va solo en la cabecera
  Authorization; nunca se guarda ni sale en el registro. Se buscan los procedimientos con
  palabras de dron en el título o con el descriptor «Unbemanntes Fluggerät» y de cada uno se
  toma solo la respuesta del gobierno: la Drucksache de respuesta de una Kleine Anfrage (sin
  la exposición de los diputados ni las preguntas), el bloque de la pregunta en la Drucksache
  semanal de Schriftliche Fragen, o el de la Mündliche Frage en el anexo del Plenarprotokoll.
  Condiciones de uso de DIP (27-02-2023): uso libre citando «Deutscher Bundestag/Bundesrat –
  DIP» y el número de documento; los PDF no se modifican.
- **Tweede Kamer** (`tweede_kamer`): OData v4 del Gegevensmagazijn, sin clave. Documentos
  «Antwoord schriftelijke vragen» y «Brief regering» con «drone» en el asunto; el texto sale
  del PDF del documento. De las respuestas se guardan solo los bloques «Antwoord N». CC0 1.0.
- **Reino Unido** (`uk_parlamento`): API de Written Questions, sin clave. Preguntas con palabras
  de dron; se guardan las que relacionan drones con aeropuertos, bases o instalaciones
  militares, prisiones, infraestructura crítica, avistamientos o detección. La respuesta
  entera sale de /questions/{id}. Open Parliament Licence v3.0 («Contains Parliamentary
  information licensed under the Open Parliament Licence v3.0»).

El **Folketing** no se lee: su API (oda.ft.dk) da los metadatos de preguntas y respuestas,
pero los textos de las respuestas son PDF en www.ft.dk, que responde a cualquier petición
automática con una comprobación anti-robots de Cloudflare (403), también a robots.txt y a la
página de condiciones de uso. No se intenta esquivar.

Cada respuesta es un documento oficial (`respuesta_parlamentaria`, fiabilidad A1) con los
pasajes sobre drones de la respuesta del gobierno, nunca de la pregunta. Sin --historico solo
se mira la ventana reciente (60 días); con él, todo desde el 1 de enero de 2024. Lo ya guardado
no se vuelve a pedir salvo en el histórico.
"""

import html
import json
import logging
import re
from collections.abc import Callable, Iterator
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlencode, urlsplit
from urllib.robotparser import RobotFileParser

from esquema import Documento
from proceso.pasajes import localizar
from recogida import detalle
from recogida.descarga import AGENTE_EODI, Descargador, DescargaFallida

registro = logging.getLogger(__name__)

DESDE_HISTORICO = "2024-01-01"
VENTANA_RECIENTE = timedelta(days=60)
FIABILIDAD = "A"
CREDIBILIDAD = 1
TIPO = "respuesta_parlamentaria"

# --- Comunes -------------------------------------------------------------------------


def _derivado(
    base: Descargador, cabeceras: dict[str, str] | None = None, reintentos: int | None = None
) -> Descargador:
    """Otro descargador con el mismo transporte y las mismas esperas que `base`: con cabeceras
    propias (la clave de DIP) o sin reintentos (robots.txt)."""
    original = base._transporte
    transporte = original
    if cabeceras:
        extra = dict(cabeceras)

        def con_cabeceras(url: str, propias: dict[str, str], limite: float) -> Any:
            return original(url, {**propias, **extra}, limite)

        transporte = con_cabeceras
    return Descargador(
        transporte=transporte,
        dormir=base._dormir,
        reloj=base._reloj,
        agente=AGENTE_EODI,
        reintentos=base._reintentos if reintentos is None else reintentos,
    )


class Robots:
    """robots.txt de cada sitio, una vez por ejecución; sin fichero (404, 500), todo vale."""

    def __init__(self, descargador: Descargador) -> None:
        self._descargador = _derivado(descargador, reintentos=0)
        self._lectores: dict[str, RobotFileParser] = {}

    def permite(self, url: str) -> bool:
        partes = urlsplit(url)
        sitio = f"{partes.scheme}://{partes.netloc}"
        if sitio not in self._lectores:
            lector = RobotFileParser()
            try:
                texto = self._descargador.texto(f"{sitio}/robots.txt", lambda _: True)
            except DescargaFallida:
                texto = ""
            # Una página HTML en lugar del fichero (una aplicación web) no son reglas.
            lector.parse([] if "<html" in texto[:500].lower() else texto.splitlines())
            self._lectores[sitio] = lector
        return self._lectores[sitio].can_fetch(AGENTE_EODI, url)


def _es_json(cuerpo: bytes) -> bool:
    try:
        json.loads(cuerpo)
    except ValueError:
        return False
    return True


def _json(descargador: Descargador, url: str) -> Any:
    return json.loads(descargador.contenido(url, _es_json))


def guardados(raiz: Path, fuente_id: str) -> set[str]:
    ruta = detalle.ruta_documentos(raiz, fuente_id)
    if not ruta.exists():
        return set()
    return {d["id"] for d in json.loads(ruta.read_text(encoding="utf-8"))}


def documento(
    fuente_id: str,
    id_nativo: str,
    autoridad: str,
    pais: str,
    idioma: str,
    titulo: str,
    enlace: str,
    fecha: str,
    respuesta: str,
) -> Documento:
    """El documento recogido, con los pasajes sobre drones de la respuesta del gobierno."""
    pasajes = localizar(respuesta)
    id_ = f"{fuente_id}:" + re.sub(r"[^A-Za-z0-9_.:/-]", "_", id_nativo)
    return {
        "id": id_,
        "fuente_detalle": fuente_id,
        "tipo": TIPO,
        "autoridad": autoridad,
        "pais": pais,
        "idioma": idioma,
        "titulo": " ".join(titulo.split()),
        "enlace": enlace,
        "fecha": fecha[:10],
        "fiabilidad": FIABILIDAD,
        "credibilidad": CREDIBILIDAD,
        "pasajes": list(pasajes.textos),
        "huella": pasajes.huella,
    }


def _limpiar_html(texto: str) -> str:
    sin_etiquetas = re.sub(r"<\s*(br|/p|/li|/tr)\s*/?>", "\n\n", texto, flags=re.I)
    return html.unescape(re.sub(r"<[^>]+>", " ", sin_etiquetas))


# --- Bundestag: DIP -------------------------------------------------------------------

DIP = "https://search.dip.bundestag.de/api/v1/"
AYUDA_DIP = "https://content.dip.bundestag.de/content-api/v1/content/help-api"
TITULOS_DIP = (
    "Drohne",
    "Drohnen",
    "Drohnenabwehr",
    "Drohnenüberflüge",
    "Drohnenüberflug",
    "Drohnensichtungen",
    "Drohnenvorfälle",
    "Drohnenangriff",
    "unbemannte",
)
DESCRIPTOR_DIP = "Unbemanntes Fluggerät"
TIPOS_DIP = frozenset({"Kleine Anfrage", "Schriftliche Frage", "Mündliche Frage"})
MAX_PAGINAS_DIP = 50
_CLAVE_DIP = re.compile(r"API-Key\s+lautet:\s*(?:<br\s*/?>)?\s*([A-Za-z0-9]+\.[A-Za-z0-9]+)")


class SinClave(DescargaFallida):
    """La página de ayuda de DIP no trae la clave pública."""


def clave_dip(descargador: Descargador) -> str:
    """La clave pública vigente de la página de ayuda de DIP (cambia de vez en cuando)."""
    ayuda = _json(descargador, AYUDA_DIP)
    texto = " ".join(str(p) for p in ayuda.get("data", {}).get("content", []))
    m = _CLAVE_DIP.search(texto)
    if m is None:
        raise SinClave("la página de ayuda de DIP no trae la clave pública")
    return m[1]


def _dip(descargador: Descargador, recurso: str, parametros: list[tuple[str, str]]) -> Any:
    return _json(descargador, DIP + recurso + "?" + urlencode(parametros))


def procedimientos_dip(descargador: Descargador, filtro: tuple[str, str]) -> list[Documento]:
    """Los procedimientos de la búsqueda, con todas sus páginas (cursor)."""
    resultado: list[Documento] = []
    vistos: set[str] = set()
    for consulta in ([("f.titel", t) for t in TITULOS_DIP], [("f.deskriptor", DESCRIPTOR_DIP)]):
        cursor = None
        for _ in range(MAX_PAGINAS_DIP):
            parametros = [*consulta, filtro, ("f.zuordnung", "BT"), ("format", "json")]
            if cursor:
                parametros.append(("cursor", cursor))
            pagina = _dip(descargador, "vorgang", parametros)
            for vorgang in pagina.get("documents", []):
                if str(vorgang["id"]) not in vistos:
                    vistos.add(str(vorgang["id"]))
                    resultado.append(vorgang)
            if not pagina.get("documents") or pagina.get("cursor") in {None, cursor}:
                break
            cursor = pagina["cursor"]
    return resultado


def _espaciada(palabra: str) -> str:
    """Una palabra que la Drucksache puede escribir espaciada («V o r b e m e r k u n g»)."""
    return r"\s?".join(palabra)


# «Vorbemerkung der Bundesregierung», a veces con las letras espaciadas.
_VORBEMERKUNG = re.compile(
    r"\s+".join(_espaciada(p) for p in ("Vorbemerkung", "der", "Bundesregierung"))
)


# Una pregunta numerada acaba en «?» a final de línea; con tope, para no comerse una respuesta.
_PREGUNTA_KA = re.compile(r"(?m)^[ \t\u2002]*\d+\.[ \t\u2002].{0,1500}?\?[ \t]*$", re.S)


def respuesta_kleine_anfrage(texto: str) -> str:
    """La respuesta de la Bundesregierung sin la exposición de los diputados ni las preguntas:
    desde su «Vorbemerkung der Bundesregierung» (o desde la primera pregunta) y sin el texto de
    cada pregunta numerada."""
    vorbemerkung = _VORBEMERKUNG.search(texto)
    if vorbemerkung is not None:
        inicio = vorbemerkung.end()
    else:
        m = _PREGUNTA_KA.search(texto)
        inicio = m.start() if m else 0
    return _PREGUNTA_KA.sub("\n", texto[inicio:]).strip()


def respuesta_escrita(texto: str, numero: str) -> str | None:
    """El bloque «NN. Abgeordnete…» de la Drucksache semanal, solo desde «Antwort».."""
    inicio = re.search(rf"(?m)^[\s\u2002]*{re.escape(numero)}\.[\s\u2002]+Abgeordnete", texto)
    if inicio is None:
        return None
    siguiente = re.search(r"(?m)^[\s\u2002]*\d+\.[\s\u2002]+Abgeordnete", texto[inicio.end() :])
    bloque = texto[inicio.start() : inicio.end() + (siguiente.start() if siguiente else len(texto))]
    antwort = bloque.find("Antwort de")
    return bloque[antwort:].strip() if antwort >= 0 else None


def respuesta_oral(texto: str, numero: str) -> str | None:
    """La respuesta escrita a la Mündliche Frage en el anexo del Plenarprotokoll: el bloque
    «Frage NN» seguido de «Frage des/der Abgeordneten», desde «Antwort»."""
    for m in re.finditer(rf"(?m)^Frage {re.escape(numero)}\s*$", texto):
        if not texto[m.end() : m.end() + 200].lstrip().startswith("Frage de"):
            continue
        resto = texto[m.end() :]
        fin = re.search(r"(?m)^(Frage \d+|Anlage \d+)\s*$", resto)
        bloque = resto[: fin.start() if fin else len(resto)]
        antwort = bloque.find("Antwort de")
        return bloque[antwort:].strip() if antwort >= 0 else None
    return None


class LectorDip:
    """Textos de DIP de una ejecución, con caché: varias preguntas comparten Drucksache."""

    def __init__(self, descargador: Descargador) -> None:
        self.descargador = descargador
        self._textos: dict[tuple[str, str], str | None] = {}

    def texto(self, recurso: str, numero: str) -> str | None:
        if (recurso, numero) not in self._textos:
            pagina = _dip(
                self.descargador,
                recurso,
                [("f.dokumentnummer", numero), ("f.zuordnung", "BT"), ("format", "json")],
            )
            documentos = pagina.get("documents", [])
            self._textos[(recurso, numero)] = documentos[0].get("text") if documentos else None
        return self._textos[(recurso, numero)]

    def posiciones(self, vorgang_id: str) -> list[Documento]:
        pagina = _dip(
            self.descargador, "vorgangsposition", [("f.vorgang", vorgang_id), ("format", "json")]
        )
        return list(pagina.get("documents", []))

    def respuesta(self, vorgang: Documento) -> tuple[str, Documento] | None:
        """(texto de la respuesta, fundstelle) del procedimiento, o None si aún no la hay."""
        posiciones = self.posiciones(str(vorgang["id"]))
        tipo = vorgang.get("vorgangstyp")
        for posicion in posiciones:
            fundstelle = posicion.get("fundstelle", {})
            if tipo == "Kleine Anfrage" and fundstelle.get("drucksachetyp") == "Antwort":
                texto = self.texto("drucksache-text", fundstelle["dokumentnummer"])
                return (respuesta_kleine_anfrage(texto), fundstelle) if texto else None
            if (
                tipo == "Schriftliche Frage"
                and fundstelle.get("drucksachetyp") == "Schriftliche Fragen"
                and fundstelle.get("frage_nummer")
            ):
                texto = self.texto("drucksache-text", fundstelle["dokumentnummer"])
                bloque = (
                    respuesta_escrita(texto, str(fundstelle["frage_nummer"])) if texto else None
                )
                return (bloque, fundstelle) if bloque else None
        if tipo == "Mündliche Frage":
            numero = next(
                (
                    p["fundstelle"]["frage_nummer"]
                    for p in posiciones
                    if p.get("fundstelle", {}).get("frage_nummer")
                ),
                None,
            )
            protocolo = next(
                (
                    p["fundstelle"]
                    for p in posiciones
                    if p.get("fundstelle", {}).get("dokumentart") == "Plenarprotokoll"
                ),
                None,
            )
            if numero and protocolo:
                texto = self.texto("plenarprotokoll-text", protocolo["dokumentnummer"])
                bloque = respuesta_oral(texto, str(numero)) if texto else None
                return (bloque, protocolo) if bloque else None
        return None


def recolector_dip(
    fuente: Documento, raiz: Path, descargador: Descargador, ahora: datetime, historico: bool
) -> int:
    robots = Robots(descargador)
    if not robots.permite(AYUDA_DIP) or not robots.permite(DIP + "vorgang"):
        raise DescargaFallida("robots.txt no permite leer DIP")
    clave = clave_dip(descargador)
    lector = LectorDip(_derivado(descargador, {"Authorization": f"ApiKey {clave}"}))
    filtro = (
        ("f.datum.start", DESDE_HISTORICO)
        if historico
        else ("f.aktualisiert.start", (ahora - VENTANA_RECIENTE).strftime("%Y-%m-%dT%H:%M:%S"))
    )
    ya = set() if historico else guardados(raiz, fuente["id"])
    nuevos = []
    for vorgang in procedimientos_dip(lector.descargador, filtro):
        id_ = f"{fuente['id']}:{vorgang['id']}"
        if vorgang.get("vorgangstyp") not in TIPOS_DIP or id_ in ya:
            continue
        hallada = lector.respuesta(vorgang)
        if hallada is None:
            continue
        texto, fundstelle = hallada
        nuevos.append(
            documento(
                fuente["id"],
                str(vorgang["id"]),
                "Bundesregierung",
                "DE",
                "de",
                f"{vorgang['titel']} "
                f"({fundstelle.get('dokumentart', '')} {fundstelle['dokumentnummer']})",
                fundstelle.get("pdf_url") or f"https://dip.bundestag.de/vorgang/{vorgang['id']}",
                str(fundstelle.get("datum") or vorgang.get("datum")),
                texto,
            )
        )
    detalle.guardar_documentos(raiz, fuente["id"], nuevos)
    registro.info("bundestag_dip: %d respuestas nuevas", len(nuevos))
    return len(nuevos)


# --- Tweede Kamer -------------------------------------------------------------------------

TK = "https://gegevensmagazijn.tweedekamer.nl/OData/v4/2.0/"
SOORTEN_TK = ("Antwoord schriftelijke vragen", "Brief regering")
_PREGUNTA_TK = re.compile(r"(?m)^\s*Vraag \d+\s*$")
_RESPUESTA_TK = re.compile(r"(?m)^\s*Antwoord \d+\s*$")
_MINISTERIO_TK = re.compile(r"Antwoord van [^(]*\(([^)]+)\)")
_BRIEF_TK = re.compile(r"BRIEF VAN DE[^\n]*?(?:VAN|VOOR)\s+([A-Z][A-Z ,]+)")


def consulta_tk(desde: str) -> str:
    soorten = " or ".join(f"Soort eq '{s}'" for s in SOORTEN_TK)
    filtro = (
        f"({soorten}) and contains(tolower(Onderwerp),'drone') and Datum ge {desde} "
        "and Verwijderd eq false"
    )
    return (
        TK
        + "Document?"
        + urlencode(
            {
                "$filter": filtro,
                "$orderby": "Datum desc",
                "$select": "Id,Soort,DocumentNummer,Onderwerp,Datum,ContentType",
            },
            quote_via=quote,
        )
    )


def respuestas_tk(texto: str, soort: str) -> str:
    """De unas respuestas a preguntas escritas, solo los bloques «Antwoord N»; de una carta del
    gobierno, el texto entero."""
    if soort != "Antwoord schriftelijke vragen":
        return texto
    bloques = []
    for m in _RESPUESTA_TK.finditer(texto):
        resto = texto[m.end() :]
        fin = _PREGUNTA_TK.search(resto)
        bloques.append(resto[: fin.start() if fin else len(resto)].strip())
    return "\n\n".join(bloques)


def autoridad_tk(texto: str) -> str:
    if m := _MINISTERIO_TK.search(texto):
        return f"Rijksoverheid ({' '.join(m[1].split())})"
    if m := _BRIEF_TK.search(texto):
        return f"Rijksoverheid ({' '.join(m[1].split()).title()})"
    return "Rijksoverheid"


def _es_pdf(cuerpo: bytes) -> bool:
    return cuerpo[:5] == b"%PDF-"


def _texto_pdf(datos: bytes) -> str:
    from io import BytesIO

    from pypdf import PdfReader  # solo hace falta al leer documentos

    return "\n".join(p.extract_text() or "" for p in PdfReader(BytesIO(datos)).pages)


def _paginas_odata(descargador: Descargador, url: str) -> Iterator[Documento]:
    while url:
        pagina = _json(descargador, url)
        yield from pagina.get("value", [])
        url = pagina.get("@odata.nextLink", "")


def recolector_tk(
    fuente: Documento, raiz: Path, descargador: Descargador, ahora: datetime, historico: bool
) -> int:
    robots = Robots(descargador)
    desde = DESDE_HISTORICO if historico else (ahora - VENTANA_RECIENTE).strftime("%Y-%m-%d")
    url = consulta_tk(desde)
    if not robots.permite(url):
        raise DescargaFallida("robots.txt no permite leer el Gegevensmagazijn")
    ya = set() if historico else guardados(raiz, fuente["id"])
    nuevos = []
    for registro_tk in _paginas_odata(descargador, url):
        id_ = f"{fuente['id']}:{registro_tk['DocumentNummer']}"
        if id_ in ya or registro_tk.get("ContentType") != "application/pdf":
            continue
        enlace = f"{TK}Document({registro_tk['Id']})/resource"
        try:
            texto = _texto_pdf(descargador.contenido(enlace, _es_pdf))
        except (DescargaFallida, ValueError) as error:
            registro.warning("tweede_kamer: %s no se lee: %s", registro_tk["DocumentNummer"], error)
            continue
        nuevos.append(
            documento(
                fuente["id"],
                registro_tk["DocumentNummer"],
                autoridad_tk(texto),
                "NL",
                "nl",
                registro_tk["Onderwerp"],
                enlace,
                registro_tk["Datum"],
                respuestas_tk(texto, registro_tk["Soort"]),
            )
        )
    detalle.guardar_documentos(raiz, fuente["id"], nuevos)
    registro.info("tweede_kamer: %d documentos nuevos", len(nuevos))
    return len(nuevos)


# --- Reino Unido: Written Questions -----------------------------------------------------

UK = "https://questions-statements-api.parliament.uk/api/writtenquestions/questions"
PUBLICA_UK = "https://questions-statements.parliament.uk/written-questions/detail/{fecha}/{uin}"
TERMINOS_UK = ("drone", "drones", "unmanned aerial", "counter-drone")
TAMANO_PAGINA_UK = 100
MAX_PAGINAS_UK = 30
_DRON_UK = re.compile(r"\b(drones?|unmanned (aerial|air)|UAVs?|UAS|counter-drone)\b", re.I)
_CONTEXTO_UK = re.compile(
    r"\b(airports?|aerodromes?|airfields?|airspace|military|bases?|RAF|USAF|establishments?|"
    r"barracks|prisons?|critical (national )?infrastructure|nuclear|power stations?|ports?|"
    r"sightings?|detect\w*|incursions?|Lakenheath|Mildenhall|Feltwell|Akrotiri)\b",
    re.I,
)


def relevante_uk(pregunta: Documento) -> bool:
    texto = " ".join(str(pregunta.get(c) or "") for c in ("heading", "questionText", "answerText"))
    return bool(_DRON_UK.search(texto) and _CONTEXTO_UK.search(texto))


def busqueda_uk(termino: str, desde: str, salto: int) -> str:
    return (
        UK
        + "?"
        + urlencode(
            {
                "searchTerm": termino,
                "tabledWhenFrom": desde,
                "answered": "Answered",
                "take": TAMANO_PAGINA_UK,
                "skip": salto,
            }
        )
    )


def preguntas_uk(descargador: Descargador, desde: str) -> list[Documento]:
    """Las preguntas contestadas con palabras de dron, sin repetir. Una página que falla tras
    los reintentos (la API da 500 en las páginas profundas) corta solo ese término."""
    vistas: dict[int, Documento] = {}
    for termino in TERMINOS_UK:
        for pagina in range(MAX_PAGINAS_UK):
            try:
                datos = _json(descargador, busqueda_uk(termino, desde, pagina * TAMANO_PAGINA_UK))
            except DescargaFallida as error:
                registro.warning(
                    "uk_parlamento: «%s» cortado en la página %d: %s", termino, pagina, error
                )
                break
            resultados = [r["value"] for r in datos.get("results", [])]
            for pregunta in resultados:
                vistas.setdefault(int(pregunta["id"]), pregunta)
            if len(resultados) < TAMANO_PAGINA_UK:
                break
    return [vistas[k] for k in sorted(vistas)]


def recolector_uk(
    fuente: Documento, raiz: Path, descargador: Descargador, ahora: datetime, historico: bool
) -> int:
    robots = Robots(descargador)
    if not robots.permite(UK):
        raise DescargaFallida("robots.txt no permite leer la API de Written Questions")
    desde = DESDE_HISTORICO if historico else (ahora - VENTANA_RECIENTE).strftime("%Y-%m-%d")
    ya = set() if historico else guardados(raiz, fuente["id"])
    nuevos = []
    for resumen in preguntas_uk(descargador, desde):
        id_ = f"{fuente['id']}:{resumen['uin']}"
        if id_ in ya or not relevante_uk(resumen) or not resumen.get("dateAnswered"):
            continue
        pregunta = _json(descargador, f"{UK}/{resumen['id']}")["value"]
        if not relevante_uk(pregunta):
            continue
        respuesta = _limpiar_html(str(pregunta.get("answerText") or ""))
        enlace = PUBLICA_UK.format(fecha=str(pregunta["dateTabled"])[:10], uin=pregunta["uin"])
        nuevos.append(
            documento(
                fuente["id"],
                str(pregunta["uin"]),
                f"UK Government ({pregunta.get('answeringBodyName') or 'sin departamento'})",
                "GB",
                "en",
                str(pregunta.get("heading") or pregunta["uin"]),
                enlace,
                str(pregunta["dateAnswered"]),
                respuesta,
            )
        )
    detalle.guardar_documentos(raiz, fuente["id"], nuevos)
    registro.info("uk_parlamento: %d respuestas nuevas", len(nuevos))
    return len(nuevos)


RECOLECTORES: dict[str, Callable[[Documento, Path, Descargador, datetime, bool], int]] = {
    "bundestag_dip": recolector_dip,
    "tweede_kamer": recolector_tk,
    "uk_parlamento": recolector_uk,
}
for _tipo, _funcion in RECOLECTORES.items():
    detalle.registrar_recolector(_tipo, _funcion)
