"""Notas de prensa de la Guardia Civil sobre drones (fuente oficial de detalle, fiabilidad A).

La Guardia Civil no ofrece un canal RSS o Atom que funcione: la página de canales
(https://web.guardiacivil.es/es/tramites/rss_list/) solo enlaza un Atom que responde 404
(comprobado el 4 de octubre de 2026). Se leen, como hace cualquier visitante:

- la lista de noticias (https://web.guardiacivil.es/es/destacados/noticias/), 10 por página,
  con su fecha, título y enlace;
- el buscador general (https://web.guardiacivil.es/es/buscador-general/) con cada palabra de
  dron («dron», «drones», «RPAS», «UAS», «aeronave no tripulada», «PEGASO», «antidron»);
- la nota completa de las que pasan el filtro de palabras, para localizar sus pasajes sobre
  drones (proceso/pasajes.py).

Qué se guarda: solo las notas de un incidente, es decir, un dron que sobrevuela o entra sin
permiso en una instalación (aeropuerto, base, cárcel, puerto, central, estadio, edificio
oficial, evento). Los drones sobre cárceles cuentan. Se descartan las redes de contrabando con
drones (narcodrones del Estrecho), el uso de drones por la propia Guardia Civil y las notas de
divulgación (proyectos, jornadas, despliegues de seguridad). De cada nota se guarda título,
fecha, enlace, atribución («Guardia Civil») y los pasajes sobre drones, nunca la nota entera.

Condiciones de reutilización: el aviso legal de web.guardiacivil.es
(https://web.guardiacivil.es/es/informacion-general/nota-legal/index.html, leído el 4 de
octubre de 2026) limita el uso a la descarga y el uso privado y pide autorización a la
Dirección General para cualquier otro; no cita la Ley 37/2007. Por eso solo se publica el
enlace a la nota, su atribución y una frase breve citada, como cualquier fuente; el texto no se
reproduce. Sin robots.txt (responde 404).

La recogida horaria extrae la nota con el extractor de las fuentes de detalle y la cruza con
los incidentes: si corresponde a uno que ya está por la prensa, se une a él y lo confirma; si
no, una nota de un incidente da de alta uno nuevo (como una respuesta parlamentaria).
"""

import html as html_
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import quote, urljoin, urlsplit

from esquema import Documento
from recogida import detalle
from recogida.descarga import Descargador, DescargaFallida
from recogida.investigaciones import (
    INICIO_HISTORICO,
    VENTANA_RECIENTE,
    Sitios,
    _es_html,
    _guardados,
    _guardar,
    _texto_html,
    documento,
    identificador,
)

WEB = "https://web.guardiacivil.es"
LISTA = WEB + "/es/destacados/noticias/index.html?reloaded&page={pagina}"
BUSCADOR = (
    WEB + "/es/buscador-general/index.html?reloaded&page={pagina}&searchaction=search"
    "&busqueda={termino}"
)
TERMINOS = ("dron", "drones", "RPAS", "UAS", "aeronave no tripulada", "PEGASO", "antidron")
MAX_PAGINAS_LISTA = 120
MAX_PAGINAS_BUSCADOR = 10
MESES = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6, "julio": 7,
    "agosto": 8, "septiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12,
}  # fmt: skip

DRON = re.compile(
    r"\bdron(?:es)?\b|\bRPAS\b|\bUAS\b|aeronaves?\s+no\s+tripulad\w+|"
    r"sistemas?\s+a[eé]reos?\s+no\s+tripulad\w+|\bPEGASO\b|antidron\w*|"
    r"anti-dron\w*|\bcontra\s?dron\w*",
    re.IGNORECASE,
)
INSTALACION = re.compile(
    r"aeropuerto|aeródromo|helipuerto|base\s+(?:aérea|militar|naval)|cuartel|acuartelamiento|"
    r"prisi[oó]n|c[aá]rcel|centro\s+penitenciario|penitenciari\w+|puerto\b|central\s+(?:nuclear|"
    r"térmica|eléctrica)|planta|refiner[ií]a|subestaci[oó]n|presa|embalse|estadio|campo\s+de\s+"
    r"f[uú]tbol|palacio|ministerio|edificio\s+(?:oficial|público)|parlamento|cumbre|concierto|"
    r"festival|procesi[oó]n|evento|recinto|zona\s+(?:restringida|prohibida)|espacio\s+a[eé]reo",
    re.IGNORECASE,
)
INTRUSION = re.compile(
    r"sobrevol\w*|sobrevuel\w*|intrus\w*|irrumpi\w*|invadi\w*|detect\w*|neutraliz\w*|"
    r"intercept\w*|inhibi\w*|derrib\w*|denunci\w*|sancion\w*|propuesta\s+de\s+sanci[oó]n|"
    r"piloto|identific\w*|sin\s+autorizaci[oó]n|no\s+autorizad\w*|il[ií]cit\w*|ilegal\w*|"
    r"introduc\w*\s+(?:droga|tel[eé]fono|m[oó]vil|hach[ií]s|sustancia)",
    re.IGNORECASE,
)
# Lo que no es un incidente: contrabando con drones, uso propio, divulgación.
CONTRABANDO = re.compile(
    r"narco\w*|hach[ií]s|coca[ií]na|estupefaciente\w*|droga\w*|tabaco|contrabando|"
    r"pateras?|narcolanchas?|vigilar\s+(?:los\s+)?movimientos|organizaci[oó]n\s+criminal|"
    r"red\s+criminal|blanqueo",
    re.IGNORECASE,
)
# Las cárceles son la excepción: un dron que introduce droga en una prisión es un incidente.
PRISION = re.compile(r"prisi[oó]n|c[aá]rcel|centro\s+penitenciario|penitenciari\w+", re.I)
USO_PROPIO = re.compile(
    r"(?:con|mediante|gracias\s+a|ayuda\s+de|empleo\s+de|uso\s+de)\s+(?:un\s+|los\s+|sus\s+)?"
    r"drones?\b|drones?\s+de\s+la\s+guardia\s+civil|unidad\s+(?:a[eé]rea|de\s+drones)|"
    r"equipos?\s+pegaso|desplegad\w+|despliegue|dispositivo\s+de\s+seguridad|"
    r"equipo\s+anti\s?-?drones?|incorpora\w*\s+drones?|adquisici[oó]n|formaci[oó]n\s+de\s+pilotos|"
    r"como\s+drones?|equipos?\s+de\s+drones|vigilancia\s+\(drones\)|medios\s+t[eé]cnicos|"
    r"apoyo\s+de\s+(?:\w+\s+){0,6}drones?|operativo\s+de\s+b[uú]squeda",
    re.IGNORECASE,
)
DIVULGACION = re.compile(
    r"jornadas?\b|curso\b|cursos\b|seminario|congreso|feria|exhibici[oó]n|charla|campaña|"
    r"consejos|recomendaciones|proyecto\s+europeo|proyecto\b|financiad\w+\s+por|ISFP|"
    r"premio|aniversario|visita\s+institucional",
    re.IGNORECASE,
)
_ITEM = re.compile(r'<li class="elementoListado.*?</li>', re.S)
_ENLACE = re.compile(r'<a href="([^"]+)" title="([^"]*)" class="enlace_elemento"')
_FECHA_LISTA = re.compile(r'class="fecha_elemento">\s*(\d{1,2})\s+(\w+)\s+(\d{4})')
_DESCRIPCION = re.compile(r'class="descripcion">(.*?)</div>', re.S)
_FECHA_NOTA = re.compile(r'class="fecha-publicacion">\s*(\d{2})/(\d{2})/(\d{2,4})')


def _limpio(texto: str) -> str:
    return " ".join(html_.unescape(re.sub(r"<[^>]+>", " ", texto)).split())


def entradas(html: str) -> list[Documento]:
    """Las noticias de una página de la lista o del buscador: enlace, título, fecha y entradilla."""
    resultado = []
    for item in _ITEM.findall(html):
        enlace = _ENLACE.search(item)
        fecha = _FECHA_LISTA.search(item)
        if enlace is None or fecha is None or fecha[2].lower() not in MESES:
            continue
        descripcion = _DESCRIPCION.search(item)
        resultado.append({
            "enlace": urljoin(WEB, enlace[1]),
            "titulo": _limpio(enlace[2]),
            "fecha": f"{fecha[3]}-{MESES[fecha[2].lower()]:02d}-{int(fecha[1]):02d}",
            "entradilla": _limpio(descripcion[1]) if descripcion else "",
        })  # fmt: skip
    return resultado


def fecha_nota(html: str) -> str | None:
    m = _FECHA_NOTA.search(html)
    if m is None:
        return None
    anio = int(m[3]) + (2000 if len(m[3]) == 2 else 0)
    return f"{anio}-{int(m[2]):02d}-{int(m[1]):02d}"


_FRASE = re.compile(r"[^.!?\n]+[.!?]?")


def es_incidente(texto: str) -> tuple[bool, str]:
    """Si la nota cuenta un dron que sobrevuela o entra en una instalación, y por qué no si no
    lo es: contrabando, uso propio de la Guardia Civil, divulgación o sin dron o sin lugar. Se
    mira frase a frase: una nota larga nombra drones, prisiones y despliegues en frases que no
    tienen nada que ver entre sí."""
    if not DRON.search(texto):
        return False, "sin_dron"
    motivo = "sin_instalacion"
    for m in _FRASE.finditer(texto):
        frase = m.group(0)
        if not DRON.search(frase):
            continue
        if CONTRABANDO.search(frase) and not PRISION.search(frase):
            motivo = "contrabando"
            continue
        if USO_PROPIO.search(frase):
            motivo = "uso_propio"
            continue
        if DIVULGACION.search(frase) and not INTRUSION.search(frase):
            motivo = "divulgacion"
            continue
        if INSTALACION.search(frase) and INTRUSION.search(frase):
            return True, "incidente"
    if DIVULGACION.search(texto):
        return False, "divulgacion"
    return False, motivo


def recolector_guardia_civil(
    fuente: Documento, raiz: Path, descargador: Descargador, ahora: datetime, historico: bool
) -> int:
    sitios = Sitios(descargador)
    guardados = set() if historico else _guardados(raiz, fuente["id"])
    desde = INICIO_HISTORICO if historico else (ahora - VENTANA_RECIENTE).date().isoformat()
    candidatas: dict[str, Documento] = {}
    for pagina in range(1, MAX_PAGINAS_LISTA + 1):
        lista = entradas(sitios.texto(LISTA.format(pagina=pagina), _es_html))
        for e in lista:
            if e["fecha"] >= desde and DRON.search(f"{e['titulo']} {e['entradilla']}"):
                candidatas.setdefault(e["enlace"], e)
        if not lista or min(e["fecha"] for e in lista) < desde:
            break
    for termino in TERMINOS:
        for pagina in range(1, MAX_PAGINAS_BUSCADOR + 1):
            url = BUSCADOR.format(pagina=pagina, termino=quote(termino))
            lista = entradas(sitios.texto(url, _es_html))
            for e in lista:
                if e["fecha"] >= desde:
                    candidatas.setdefault(e["enlace"], e)
            if len(lista) < 25:
                break
    nuevos = []
    for enlace, entrada in sorted(candidatas.items()):
        nativo = urlsplit(enlace).path.strip("/")
        if identificador(fuente["id"], nativo) in guardados:
            continue
        try:
            pagina_nota = sitios.texto(enlace, _es_html)
        except DescargaFallida:
            continue
        texto = "\n\n".join(x for x in (entrada["entradilla"], _texto_html(pagina_nota)) if x)
        incidente, _ = es_incidente(f"{entrada['titulo']}. {texto}")
        if not incidente:
            continue
        nuevos.append(documento(
            fuente, nativo, "nota_oficial", entrada["titulo"], enlace,
            fecha_nota(pagina_nota) or entrada["fecha"], texto,
        ))  # fmt: skip
    return _guardar(raiz, fuente, nuevos)


detalle.registrar_recolector("guardia_civil", recolector_guardia_civil)
