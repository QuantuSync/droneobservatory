"""Fuentes oficiales que confirman incidentes (fiabilidad A, autoridad).

Cada fuente de `configuracion/fuentes_oficiales.json` se lee respetando su
robots.txt y con la identificación del observatorio: las de tipo rss por su
canal y las de tipo pagina por su página de noticias (`paginas_oficiales`).
Una nota que habla de drones se enlaza al incidente que le
corresponde: con la regla de fusión (mismo sitio y misma ventana) o, si la ficha
solo tiene el país o la región (sin punto), o la nota no nombra un sitio que se
sepa situar, con el mismo país, el mismo día (el de la nota o la víspera, o el
día que la nota escribe) y un tipo de suceso compatible. Si encaja con uno
solo, entra como fuente de autoridad y el incidente pasa a confirmado: la
autoridad dice que ocurrió. presencia_dron solo cambia si la nota lo dice sin
reservas («bekræfter», sin «mulige» ni «formodede»).

Una nota que cuenta un suceso (SUCESO) y no encaja con ninguna ficha, o con
varias, no se pierde: entra una vez como artículo de su lugar en un candidato
(como los artículos dirigidos), el extractor lo lleva delante de todos y la
ficha que salga pasa por el filtro de entrada (recogida/entrada.py), donde el
experto la compara con todo y decide si es nueva o la de una ficha existente.
En la recogida siguiente la nota se enlaza a esa ficha como fuente de
autoridad. Una nota que no cuenta un suceso (una cumbre, un informe anual, un
ejercicio) no crea nada.

Cada fuente tiene su propio tiempo (TOPE_FUENTE_S) dentro del tope de todas (TOPE_S), y cada
petición el suyo (LIMITE_PETICION_S) dentro del de la fuente, con reintentos que caben en él: una
petición colgada no agota el tope de su fuente. Los tres se pueden cambiar por fuente en la
configuración (`tope_s`, `limite_s`, `reintentos`). Una fuente lenta o caída se corta, se apunta
en el registro con su id y el motivo del último intento (un tiempo de espera, un código, otro
contenido), y se pasa a la siguiente.

Ninguna fuente deja de leerse por haber fallado: es de donde llegan las alertas. La que falla en
FALLOS_PARA_BREVE recogidas seguidas se sigue probando en cada recogida, pero después de las
demás y con un solo intento breve por petición (LIMITE_BREVE_S, sin reintentos), para que una
fuente caída no quite tiempo a las que responden; en cuanto responde se lee entera y empieza de
cero. Hasta el 12 de noviembre de 2026 se saltaba 6 horas: la navegación aérea de Letonia (lgs)
estuvo así dos veces en dos días por cortes sueltos. Si una fuente lleva AVISO_SIN_LEER sin
leerse, se avisa al responsable, una vez por racha. El estado de las que fallan va en el cursor
CURSOR_FALLOS de la base, como el de los demás pasos de la recogida.

Las fuentes con "delegada": true no dejan entrar a la dirección del servidor: se descargan a
través del lector delegado de la web (recogida/lector_delegado.py), con el mismo descargador, la
misma pausa y los mismos reintentos. Si el lector falla, la fuente falla como cualquier otra.
"""

import contextlib
import copy
import json
import logging
import math
import os
import re
import time
import unicodedata
import xml.etree.ElementTree as ET
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime
from functools import cache
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlsplit
from urllib.robotparser import RobotFileParser

from almacen.base import Almacen, DocumentoInvalido
from esquema import Documento
from proceso import fechas, incidentes
from proceso import suceso as definicion
from proceso.credibilidad import Credibilidad
from proceso.estados import Estado, TransicionNoPermitida, transitar
from proceso.noticias import (
    filtro,
    localidades_declinadas,
    lugar,
    lugar_del_suceso,
    lugares_en,
    nomenclator,
    titular_normalizado,
)
from recogida import lector_delegado, navegador, paginas_oficiales
from recogida.descarga import AGENTE_EODI, Descargador, DescargaFallida
from recogida.plazo import Plazo, TiempoAgotado

registro = logging.getLogger(__name__)

DIRECTORIO = Path(__file__).resolve().parent.parent / "configuracion"
# Carpeta de datos de las fuentes de detalle en el servidor (servidor/configuracion.sh).
VARIABLE_DATOS_DETALLE = "EODI_DETALLE_DATOS"
MAX_PALABRAS_FRASE = 25
# Tope de tiempo por ejecución. Leer las 32 fuentes y enlazar sus notas tarda de 170 a 190 s
# (medido del 15 al 16 de octubre de 2026); 300 s dejan sitio para dos fuentes cortadas por su
# tope. Las notas se leen enteras en cada ejecución: una fuente que queda sin leer no pierde
# nada, la lee la siguiente.
TOPE_S = 300.0
# Tope de cada fuente dentro del de todas. Las más lentas tardan 18 s (mapn y lfv, siete
# peticiones con la pausa de 3 s entre peticiones al mismo sitio; medido en el servidor el 16 de
# octubre de 2026); 45 s son dos veces y media. Una fuente caída con sus reintentos llegaba a
# 80 s y dejaba otras sin leer.
TOPE_FUENTE_S = 45.0
# Tope de cada petición y reintentos (con 5 y 10 s de espera) dentro del de la fuente:
# 12 + 5 + 12 + 10 = 39 s. Con el límite general del descargador (30 s, y 5, 10, 20 y 40 s de
# espera) una sola petición colgada agotaba los 45 s de la fuente sin llegar al segundo intento,
# y en el registro solo quedaba «cortada al agotar su tope» (los 19 cortes del 9 al 12 de
# noviembre de 2026: lgs, mod_lv, mil_lv, dfs y valenciaport, que al probarlas a mano respondían
# en menos de medio segundo).
LIMITE_PETICION_S = 12.0
REINTENTOS_PETICION = 2
# Una fuente que falla en estas recogidas seguidas se sigue probando en cada una, la última y
# con un solo intento breve por petición.
FALLOS_PARA_BREVE = 3
LIMITE_BREVE_S = 10.0
# Una fuente que lleva este tiempo sin leerse se avisa al responsable, una vez por racha.
AVISO_SIN_LEER = timedelta(hours=3)
# El nombre del cursor es el de cuando las fuentes se pausaban.
CURSOR_FALLOS = "oficiales_pausas"
# El día va a las 00:00, como en el resto de las fichas: «2026-10-24» a secas no cumple el
# esquema, y hasta el 29 de octubre de 2026 la ficha no se guardaba y la nota de una página con
# solo el día (mapn, mil_lv, mod_lv) no se enlazaba nunca.
_FORMATOS = {"minuto": "%Y-%m-%dT%H:%MZ", "dia": "%Y-%m-%dT00:00Z"}
# Afirmación expresa de que había drones, sin reservas.
_AFIRMA = re.compile(r"bekræft|bestätig|confirm|potwierdz|confirmă", re.IGNORECASE)
_RESERVA = re.compile(
    r"\bmulig|formod|muligvis|mistanke|possibl|suspect|mutmaß|mögliche|podejrzan|posibil",
    re.IGNORECASE,
)
# Lo que dice que la nota cuenta un suceso concreto (un dron que entra, se ve, se detecta, se
# derriba, cae o se halla; una alerta aérea), en las lenguas de las fuentes. Sin ello, la nota
# habla de drones sin un suceso (una cumbre, un informe anual, un ejercicio, la normativa del
# espacio aéreo: medido sobre las notas de las fuentes oficiales del 20 de agosto al 29 de octubre
# de 2026). «Espacio aéreo» a secas no basta: lo dicen también las notas de normativa (LVNL).
SUCESO = re.compile(
    r"violat|incursion|intrusion|shot down|crash|wreck|debris|sighted|sighting|spotted|"
    r"\bfound\b|detected|"
    r"apdraudēj|atrast|nokrit|ielid|pārkāp|"
    r"ținte aeriene|ţinte aeriene|ținta aeriană|ţinta aeriană|a pătruns|au pătruns|doborât|"
    r"prăbuș|a detectat|au decolat|"
    r"naruszeni|zestrzel|szczątk|wtargn|"
    r"abgeschossen|gesichtet|trümmer|absturz|eingedrungen|"
    r"observeret|observert|observerad|nedskudt|krænk|kränk|"
    r"avistamiento|avistad|derribad|"
    r"survol|abattu|débris|"
    r"neergehaald|waargenomen|gespot|binnengedrongen|"
    r"pažeid|įskrid|numuš|nukrit|oro pavoj|air alert|air raid|"
    r"loukka",
    re.IGNORECASE,
)
# Las notas más antiguas que esto no entran como candidatas: las páginas de algunas fuentes
# guardan notas de meses atrás, y lo de entonces ya lo trajeron las noticias.
DIAS_ENTRADA = 30
# Una nota de un aeropuerto es de una interrupción aeroportuaria: sin sitio común no se enlaza a
# una incursión o un sobrevuelo del mismo día (ni al revés).
_AEROPUERTO = re.compile(
    r"airport|aeropuert|aéroport|aeroport|flughafen|lufthavn|lufthamn|lotnisk|lidost|luchthaven",
    re.IGNORECASE,
)
INTERRUPCION = "interrupcion_aeroportuaria"
# Notas de un suceso que no encajaron con una sola ficha y entraron como artículo.
CURSOR_SIN_FICHA = "oficiales_sin_ficha"
MOTIVO_SIN_FICHA = (
    "nota oficial sin ficha: entra como artículo de su lugar para que el extractor y el filtro "
    "de entrada decidan si es un suceso nuevo o el de una ficha existente"
)


@dataclass(frozen=True)
class Nota:
    fuente: Documento
    id: str
    titulo: str
    enlace: str
    fecha: datetime
    texto: str
    precision: str = "minuto"


@dataclass
class Recuentos:
    notas: int = 0
    relevantes: int = 0
    enlazadas: int = 0
    confirmadas: int = 0
    # Notas de un suceso sin ficha que entraron como artículo para el filtro de entrada.
    a_entrada: int = 0
    bloqueadas: int = 0
    # Fuentes que no dio tiempo a leer en esta ejecución (el tope de todas se agotó).
    sin_leer: int = 0
    # La nota más reciente leída en esta pasada, de cualquier fuente: el último dato de las
    # oficiales. Si la pasada se corta, puede ser anterior a la publicada, que no se rebaja
    # (recogida/estado.py).
    ultima: datetime | None = None
    # Las fuentes que fallaron en esta pasada, con el motivo, y las que se probaron con un solo
    # intento breve por venir fallando.
    fallidas: dict[str, str] = field(default_factory=dict)
    en_breve: list[str] = field(default_factory=list)
    # Lo que tardó cada fuente, en segundos.
    tiempos: dict[str, float] = field(default_factory=dict)

    def resumen(self) -> str:
        return (
            f"notas={self.notas} relevantes={self.relevantes} enlazadas={self.enlazadas} "
            f"confirmadas={self.confirmadas} a_entrada={self.a_entrada} "
            f"bloqueadas={self.bloqueadas} "
            f"sin_leer={self.sin_leer} en_breve={len(self.en_breve)}"
        )


def carpeta_renders() -> Path:
    """Donde deja el temporizador de las fuentes de detalle las listas renderizadas."""
    return Path(os.environ.get(VARIABLE_DATOS_DETALLE, "data/detalle")) / "paginas_js"


@cache
def fuentes(ruta: Path = DIRECTORIO / "fuentes_oficiales.json") -> tuple[Documento, ...]:
    datos: dict[str, Any] = json.loads(ruta.read_text(encoding="utf-8"))
    return tuple(datos["fuentes"])


def robots(descargador: Descargador, url: str) -> RobotFileParser:
    """El robots.txt del sitio, con un solo intento: si no llega, no se gasta en él el tiempo de
    la fuente (se sigue como si no lo hubiera, como hasta ahora)."""
    partes = urlsplit(url)
    lector = RobotFileParser()
    unico = descargador.con_limites(0, descargador.limite_s)
    try:
        texto = unico.texto(f"{partes.scheme}://{partes.netloc}/robots.txt", lambda _: True)
    except DescargaFallida:
        texto = ""
    finally:
        descargador.ultimo_fallo = unico.ultimo_fallo or descargador.ultimo_fallo
    lector.parse(texto.splitlines())
    return lector


ATOM = "{http://www.w3.org/2005/Atom}"


def _entradas(raiz: ET.Element) -> list[tuple[str, str | None, str, str, bool]]:
    """(enlace, fecha, título, texto, es_atom) de cada entrada de un canal RSS o Atom."""
    entradas: list[tuple[str, str | None, str, str, bool]] = []
    for item in raiz.iter("item"):
        entradas.append((
            (item.findtext("link") or "").strip(), item.findtext("pubDate"),
            item.findtext("title") or "", item.findtext("description") or "", False,
        ))  # fmt: skip
    for entrada in raiz.iter(f"{ATOM}entry"):
        enlace = entrada.find(f"{ATOM}link")
        entradas.append((
            (enlace.get("href", "") if enlace is not None else "").strip(),
            entrada.findtext(f"{ATOM}published") or entrada.findtext(f"{ATOM}updated"),
            entrada.findtext(f"{ATOM}title") or "",
            entrada.findtext(f"{ATOM}summary") or entrada.findtext(f"{ATOM}content") or "", True,
        ))  # fmt: skip
    return entradas


def _fecha_canal(texto: str, atom: bool) -> datetime:
    if atom:
        return datetime.fromisoformat(texto.strip().replace("Z", "+00:00")).astimezone(UTC)
    return parsedate_to_datetime(texto).astimezone(UTC)


def es_canal(texto: str) -> bool:
    """Un canal RSS o Atom (no una página de error o de comprobación)."""
    cabeza = texto[:300]
    return "<rss" in cabeza or "<feed" in cabeza


def leer_rss(texto: str, fuente: Documento) -> list[Nota]:
    """Las notas de un canal RSS o Atom. Un enlace relativo se resuelve con la dirección del
    canal (el Atom del Ministerio de Defensa los da relativos)."""
    notas = []
    for enlace, fecha, titulo, descripcion, atom in _entradas(ET.fromstring(texto)):
        enlace = urljoin(fuente["url"], enlace) if enlace else enlace
        if not enlace or not fecha:
            continue
        try:
            momento = _fecha_canal(fecha, atom)
        except (TypeError, ValueError):
            continue
        # Las actualizaciones de una misma nota comparten página: las distingue el fragmento.
        partes = urlsplit(enlace)
        identificador = re.sub(r"\W+", "-", partes.fragment or partes.path.rstrip("/")).strip("-")
        notas.append(
            Nota(
                fuente=fuente,
                id=f"{fuente['id']}-{identificador}".strip("-"),
                titulo=" ".join(titulo.split()),
                enlace=enlace,
                fecha=momento,
                texto=" ".join(re.sub(r"<[^>]+>", " ", descripcion).split()),
            )
        )
    return notas


def fuente_oficial(nota: Nota) -> Documento:
    return {
        "id": nota.id,
        "enlace": nota.enlace,
        "medio": nota.fuente["medio"],
        "fecha": {
            "valor": nota.fecha.strftime(_FORMATOS[nota.precision]),
            "precision": nota.precision,
        },
        "idioma": nota.fuente["idioma"],
        "fiabilidad": "A",
        "credibilidad": int(Credibilidad.CONFIRMADO),
        "frase_origen": " ".join(nota.titulo.split()[:MAX_PALABRAS_FRASE]),
        "replicas": 0,
        "campos_respaldados": ["estado"],
        "es_autoridad": True,
        "interna_fuera_de_ucrania": False,
        "publica": True,
    }


def _punto(nota: Nota) -> Documento | None:
    """El sitio de la nota como documento mínimo para la regla de fusión."""
    id_ = lugar_del_suceso(nota.titulo, nota.texto, nomenclator())
    if id_ is None:
        return None
    sitio = lugar(id_, nomenclator())
    return {
        "id": nota.id,
        "lugar": {"punto": {"lat": sitio.lat, "lon": sitio.lon}, "radio_km": sitio.radio_km,
                  "pais": sitio.pais},
        "objetivo": {"nombre": sitio.nombre},
        # La fecha de la nota es la de publicación: el suceso es de ese día o del anterior.
        "tiempo": {"inicio": {"valor": nota.fecha.strftime("%Y-%m-%dT%H:%MZ"),
                              "precision": "aproximada"}},
        "fuentes": [],
    }  # fmt: skip


def suceso(nota: Nota) -> bool:
    """La nota cuenta un suceso concreto (SUCESO), no solo habla de drones."""
    return SUCESO.search(f"{nota.titulo}. {nota.texto}") is not None


def tipo_compatible(incidente: Documento, nota: Nota) -> bool:
    """Una nota de un aeropuerto, con una interrupción aeroportuaria; las demás, con una
    incursión o un sobrevuelo."""
    de_aeropuerto = _AEROPUERTO.search(f"{nota.titulo}. {nota.texto}") is not None
    return bool(incidente["tipo"] == INTERRUPCION) == de_aeropuerto


def mismo_dia(incidente: Documento, nota: Nota) -> bool:
    """El suceso es del día de la nota o de la víspera (la regla de fusión con la fecha de
    publicación), o la nota escribe su día («nokritis 18. oktobrī», publicada el 24)."""
    de_la_nota: Documento = {
        "id": nota.id,
        "lugar": {"pais": nota.fuente["pais"], "radio_km": 0.0},
        "tiempo": {"inicio": {"valor": nota.fecha.strftime("%Y-%m-%dT%H:%MZ"),
                              "precision": "aproximada"}},
        "fuentes": [],
    }  # fmt: skip
    primero, segundo = sorted(
        (incidente, de_la_nota), key=lambda d: (d["tiempo"]["inicio"]["valor"], d["id"])
    )
    with contextlib.suppress(KeyError, ValueError):
        if definicion.misma_ventana(primero, segundo):
            return True
    fecha = nota.fecha if nota.fecha.tzinfo else nota.fecha.replace(tzinfo=UTC)
    return fechas.dia_escrito(
        str(incidente["tiempo"]["inicio"]["valor"]), f"{nota.titulo}. {nota.texto}", fecha
    )


def _normal(texto: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", texto.casefold()) if not unicodedata.combining(c)
    )


def nombra_la_ficha(incidente: Documento, nota: Nota) -> bool:
    """La nota nombra la localidad de la ficha, o la ficha ya tiene otra nota de la misma
    autoridad (la primera nota y su actualización). Las del MApN del 17 de octubre de 2026: el
    sitio que lee la regla es la base de Borcea, de donde despegaron los F-16, a 200 km de la
    ficha de Sulina (EODI-2026-00582); la actualización escribe «la sud-est de Sulina»."""
    localidad = str(incidente["lugar"].get("localidad") or "").strip()
    if localidad and re.search(
        rf"\b{re.escape(_normal(localidad))}\b", _normal(f"{nota.titulo}. {nota.texto}")
    ):
        return True
    prefijo = f"{nota.fuente['id']}-"
    return any(
        str(f.get("id", "")).startswith(prefijo) and f.get("es_autoridad")
        for f in incidente["fuentes"]
    )


def posibles(almacen: Almacen, nota: Nota) -> list[Documento]:
    """Las fichas activas del país de la nota que pueden ser su suceso: las que encajan con su
    sitio por la regla de fusión y, del mismo día y un tipo compatible, las que no tienen punto
    (solo el país o la región), las que la nota nombra (`nombra_la_ficha`) y, si la nota no
    nombra un sitio que se sepa situar, todas. Las alertas que una autoridad va dando por
    zonas en una misma noche son el mismo suceso (docs/definicion_suceso.md): la nota de otra
    zona y otra hora va a la ficha que ya tiene las de esa noche."""
    punto = _punto(nota)
    resultado: list[Documento] = []
    for incidente in almacen.incidentes():
        if not incidentes.activo(incidente) or incidente["lugar"]["pais"] != nota.fuente["pais"]:
            continue
        por_sitio = punto is not None and definicion.encajan(incidente, punto)
        por_dia = (
            (
                punto is None
                or not definicion.con_punto(incidente)
                or nombra_la_ficha(incidente, nota)
            )
            and tipo_compatible(incidente, nota)
            and mismo_dia(incidente, nota)
        )
        if por_sitio or por_dia:
            resultado.append(incidente)
    return resultado


def elegida(nota: Nota, candidatas: list[Documento]) -> Documento | None:
    """La ficha de la nota: la única posible o, si hay varias, la que ya la tiene entre sus
    fuentes (la nota entró como artículo y el filtro de entrada decidió de qué ficha era)."""
    if len(candidatas) == 1:
        return candidatas[0]
    con_ella = [
        i for i in candidatas if any(f.get("enlace") == nota.enlace for f in i["fuentes"])
    ]  # fmt: skip
    return con_ella[0] if len(con_ella) == 1 else None


def enlazar(almacen: Almacen, nota: Nota, ahora: datetime, modelos: frozenset[str]) -> str | None:
    """Añade la nota al único incidente que le corresponde. Devuelve su identificador."""
    suya = elegida(nota, posibles(almacen, nota))
    if suya is None:
        return None
    incidente = copy.deepcopy(suya)
    if any(f["id"] == nota.id for f in incidente["fuentes"]):
        return str(incidente["id"])
    fuente = fuente_oficial(nota)
    # Si entró antes como artículo (nota sin ficha), esa fuente pasa a ser la de la autoridad:
    # lo que la citaba (pasos del estado, afirmaciones, origen de la fecha) cita ahora la nota.
    # Las declaraciones que el extractor sacó de ella siguen. EODI-2026-00704 (29 de octubre de
    # 2026): sin cambiar las citas, la ficha no cumplía el esquema y la nota no se guardaba.
    previa = next(
        (f for f in incidente["fuentes"]
         if f.get("enlace") == nota.enlace and not f.get("es_autoridad")),
        None,
    )  # fmt: skip
    if previa is not None:
        if previa.get("campos_respaldados"):
            fuente["campos_respaldados"] = sorted({*previa["campos_respaldados"], "estado"})
        sin_ella = [f for f in incidente["fuentes"] if f is not previa]
        incidente = json.loads(
            json.dumps({**incidente, "fuentes": sin_ella}, ensure_ascii=False).replace(
                json.dumps(previa["id"]), json.dumps(nota.id)
            )
        )
    incidente["fuentes"] = [
        *(
            f
            for f in incidente["fuentes"]
            if f.get("enlace") != nota.enlace or f.get("es_autoridad")
        ),
        fuente,
    ]
    for otra in incidente["fuentes"]:
        otra["credibilidad"] = int(Credibilidad.CONFIRMADO)
    if incidente["estado"]["actual"] != Estado.CONFIRMADO:
        # Un desmentido de una autoridad más fiable no se revierte con esta nota.
        with contextlib.suppress(TransicionNoPermitida):
            incidente["estado"] = transitar(
                incidente["estado"], Estado.CONFIRMADO, fuente["fecha"], fuente["id"],
                {f["id"]: f for f in incidente["fuentes"]},
            )  # fmt: skip
    texto = f"{nota.titulo}. {nota.texto}"
    if _AFIRMA.search(texto) and not _RESERVA.search(texto):
        incidente["presencia_dron"] = "confirmada"
    # La confirmación puede cambiar el tipo y la presencia del dron (proceso/incidentes.py).
    incidente = incidentes.aplicar_reglas(incidente)
    incidente["control"]["ultima_actualizacion"] = {
        "valor": ahora.strftime("%Y-%m-%dT%H:%MZ"),
        "precision": "minuto",
    }
    try:
        almacen.guardar_incidente(incidente, ahora, modelos)
    except DocumentoInvalido as error:
        registro.warning("oficiales: la nota %s no cabe en %s: %s", nota.id, incidente["id"], error)
        return None
    return str(incidente["id"])


def leer_pagina(
    descargador: Descargador, lector: RobotFileParser, fuente: Documento, html: str | None = None
) -> list[Nota]:
    """Las notas de la página de noticias que pueden hablar de drones. Con `html`, la lista ya
    renderizada (fuentes que la cargan con JavaScript, recogida/navegador.py)."""
    if html is None:
        html = descargador.texto(fuente["url"], lambda t: "<" in t)
    candidatas = [
        (direccion, titulo)
        for direccion, titulo in paginas_oficiales.enlaces(html, fuente)
        if paginas_oficiales.interesa(titulo, fuente, filtro().dron)
        and lector.can_fetch(AGENTE_EODI, direccion)
    ][: int(fuente.get("max_notas", paginas_oficiales.MAX_NOTAS_POR_FUENTE))]
    notas = []
    for direccion, titulo in candidatas:
        try:
            articulo = descargador.texto(direccion, lambda t: "<" in t)
        except (DescargaFallida, ValueError):
            continue
        leido = paginas_oficiales.contenido(articulo, fuente, titulo)
        if leido is None:
            continue
        fecha, precision, texto = leido
        if fuente.get("titulo_nota"):
            # La lista no trae el título («Läs mer»): se toma el de la propia nota.
            titulo = paginas_oficiales.leer(articulo).meta.get("og:title") or titulo
        id_ = paginas_oficiales.identificador(fuente, direccion)
        notas.append(Nota(fuente, id_, titulo, direccion, fecha, texto, precision))
    return notas


def recoger(
    almacen: Almacen,
    descargador: Descargador,
    fuente: Documento,
    ahora: datetime,
    modelos: frozenset[str],
    recuentos: Recuentos,
    motivos: Counter[str],
) -> str | None:
    """Lee una fuente y enlaza sus notas relevantes con los incidentes. Devuelve el motivo si la
    fuente falló (no se pudo leer por ella misma)."""
    lector = robots(descargador, fuente["url"])
    if not lector.can_fetch(AGENTE_EODI, fuente["url"]):
        recuentos.bloqueadas += 1
        motivos["robots"] += 1
        return "su robots.txt no deja leerla"
    try:
        if fuente["tipo"] == "pagina":
            notas = leer_pagina(descargador, lector, fuente)
        elif fuente["tipo"] == navegador.TIPO:
            # La lista la renderiza el temporizador de las fuentes de detalle; si no hay un
            # render reciente, la fuente queda sin leer en esta ejecución.
            html = navegador.guardado(fuente, carpeta_renders(), ahora)
            if html is None:
                # No es un fallo de la fuente: depende del temporizador de las de detalle.
                recuentos.bloqueadas += 1
                motivos["sin_render"] += 1
                return None
            notas = leer_pagina(descargador, lector, fuente, html)
        else:
            notas = leer_rss(descargador.texto(fuente["url"], es_canal), fuente)
    except (DescargaFallida, ET.ParseError, ValueError) as error:
        recuentos.bloqueadas += 1
        motivos["descarga"] += 1
        return f"{type(error).__name__}: {str(error)[:200]}"
    for nota in notas:
        recuentos.notas += 1
        fecha = nota.fecha if nota.fecha.tzinfo else nota.fecha.replace(tzinfo=UTC)
        if fecha > ahora:
            # Mal fechada (zona u hora de la página): no cuenta como el último dato.
            registro.info("oficiales: nota con fecha futura %s: %s", fecha.isoformat(), nota.enlace)
        else:
            recuentos.ultima = max(recuentos.ultima or fecha, fecha)
        if not filtro().dron.search(f"{nota.titulo} {nota.texto}"):
            continue
        recuentos.relevantes += 1
        antes = almacen.incidentes()
        id_ = enlazar(almacen, nota, ahora, modelos)
        if id_ is not None:
            recuentos.enlazadas += 1
            previo = next((i for i in antes if i["id"] == id_), None)
            if previo is not None and previo["estado"]["actual"] != Estado.CONFIRMADO:
                recuentos.confirmadas += 1
        elif (
            suceso(nota)
            and fecha >= ahora - timedelta(days=DIAS_ENTRADA)
            and a_entrada(almacen, nota, ahora)
        ):
            recuentos.a_entrada += 1
    return None


def candidatos(almacen: Almacen) -> set[str]:
    """Los candidatos donde entraron notas oficiales sin ficha (el extractor los lleva delante)."""
    cursor = almacen.cursor(CURSOR_SIN_FICHA) or {}
    return {c for entrada in cursor.values() if isinstance(entrada, dict)
            for c in entrada.get("candidatos", [])}  # fmt: skip


@cache
def _mayor_localidad(pais: str) -> str | None:
    """La localidad de mayor radio del país (casi siempre, la capital)."""
    del_pais = [
        (sitio.radio_km, id_) for id_, sitio in nomenclator().lugares.items()
        if sitio.pais == pais and sitio.tipo == "localidad"
    ]  # fmt: skip
    return max(del_pais)[1] if del_pais else None


def lugar_de_candidato(nota: Nota) -> str | None:
    """Dónde entra la nota sin ficha: el lugar del suceso; si nombra varios, el primero del país
    de la fuente (la alerta letona «Krāslavas un Rēzeknes novadā»); si ninguno, la localidad
    mayor del país. Ese lugar solo agrupa: el de la ficha lo saca el extractor de la nota."""
    nom = nomenclator()
    id_ = lugar_del_suceso(nota.titulo, nota.texto, nom)
    if id_ is not None and id_ in nom.lugares:
        return id_
    for parte in (nota.titulo, f"{nota.titulo}. {nota.texto}"):
        for hallados in (lugares_en(parte, nom), localidades_declinadas(parte, nom)):
            pais = nota.fuente["pais"]
            del_pais = [h for h in hallados if h in nom.lugares and nom.lugares[h].pais == pais]
            if del_pais:
                return del_pais[0]
    return _mayor_localidad(str(nota.fuente["pais"]))


def a_entrada(almacen: Almacen, nota: Nota, ahora: datetime) -> bool:
    """La nota sin ficha entra, una sola vez, como artículo de su lugar en un candidato. True si
    ha entrado ahora."""
    from recogida.calidad import situar_en_candidatos

    cursor: dict[str, Any] = dict(almacen.cursor(CURSOR_SIN_FICHA) or {})
    if nota.enlace in cursor:
        return False
    sitio = lugar_de_candidato(nota)
    if sitio is None:
        registro.warning("oficiales: nota sin ficha y sin lugar: %s", nota.enlace)
        return False
    fecha = nota.fecha if nota.fecha.tzinfo else nota.fecha.replace(tzinfo=UTC)
    documento: Documento = {
        "url": nota.enlace, "medio": nota.fuente["medio"],
        "fecha": fecha.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "idioma": nota.fuente["idioma"], "pais": nota.fuente["pais"], "titular": nota.titulo,
        "titular_normalizado": titular_normalizado(nota.titulo), "temas": [], "lugares": [sitio],
    }  # fmt: skip
    if not almacen.guardar_articulo(documento):
        existente = almacen.articulos_de([nota.enlace])
        if existente:
            documento = {**existente[0], "lugares": [sitio]}
    tocados = situar_en_candidatos(almacen, [(documento, [sitio])], MOTIVO_SIN_FICHA)
    cursor[nota.enlace] = {
        "entrado": ahora.strftime("%Y-%m-%dT%H:%MZ"), "fuente": nota.fuente["id"],
        "candidatos": tocados,
    }  # fmt: skip
    almacen.guardar_cursor(CURSOR_SIN_FICHA, cursor)
    registro.info(
        "oficiales: nota sin ficha a la entrada (%s): %s", ", ".join(tocados), nota.enlace
    )
    return True


def _instante(texto: Any) -> datetime | None:
    try:
        return datetime.fromisoformat(str(texto).replace("Z", "+00:00")) if texto else None
    except ValueError:
        return None


def _iso(momento: datetime) -> str:
    return momento.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def fallos(almacen: Almacen) -> dict[str, dict[str, Any]]:
    """El estado de cada fuente que viene fallando: fallos seguidos, desde cuándo, el último
    motivo y si se avisó."""
    guardado = (almacen.cursor(CURSOR_FALLOS) or {}).get("fuentes") or {}
    return {k: dict(v) for k, v in guardado.items() if isinstance(v, dict)}


def en_breve(estado: dict[str, Any]) -> bool:
    """La fuente viene fallando: se prueba la última y con un solo intento breve por petición."""
    return int(estado.get("fallos_seguidos") or 0) >= FALLOS_PARA_BREVE


def anotar_fallo(estado: dict[str, Any], motivo: str, ahora: datetime) -> None:
    """Anota un fallo de la fuente y desde cuándo falla."""
    estado["fallos_seguidos"] = int(estado.get("fallos_seguidos") or 0) + 1
    estado["motivo"] = motivo
    # Una racha que viene de antes de este campo empieza a contar en su último fallo anotado.
    estado.setdefault("primer_fallo", estado.get("ultimo_fallo") or _iso(ahora))
    estado["ultimo_fallo"] = _iso(ahora)
    for viejo in ("pausa_hasta", "en_pausa_desde"):
        estado.pop(viejo, None)


def limites(fuente: Documento, breve: bool) -> tuple[float, float, int]:
    """(tope de la fuente, límite de cada petición, reintentos): los suyos si la configuración
    los da (`tope_s`, `limite_s`, `reintentos`); con la fuente fallando, un intento breve."""
    tope = float(fuente.get("tope_s", TOPE_FUENTE_S))
    limite = float(fuente.get("limite_s", LIMITE_PETICION_S))
    if breve:
        return tope, min(limite, LIMITE_BREVE_S), 0
    return tope, limite, int(fuente.get("reintentos", REINTENTOS_PETICION))


Avisar = Callable[[str], None]


def texto_sin_leer(id_: str, nombre: str, estado: dict[str, Any], ahora: datetime) -> str:
    """El aviso de una fuente que lleva AVISO_SIN_LEER sin leerse."""
    desde = _instante(estado.get("primer_fallo")) or ahora
    horas = (ahora - desde).total_seconds() / 3600
    return (
        f"{nombre} ({id_}) no se lee desde hace más de {AVISO_SIN_LEER.total_seconds() / 3600:.0f} "
        f"horas: falla desde el {desde:%Y-%m-%d %H:%M} UTC ({horas:.0f} h, "
        f"{estado.get('fallos_seguidos', 0)} recogidas seguidas). Último motivo: "
        f"{estado.get('motivo', 'sin motivo')}. Se sigue probando en cada recogida."
    )


def avisar_sin_leer(
    estados: dict[str, dict[str, Any]], ahora: datetime, avisar: Avisar | None,
    nombres: dict[str, str] | None = None, que: str = "La fuente oficial",
) -> list[str]:  # fmt: skip
    """Avisa, una vez por racha, de las fuentes que llevan AVISO_SIN_LEER fallando en todas las
    recogidas: la última lectura buena fue antes de su primer fallo. Devuelve las avisadas. Sin
    quien avise (un ensayo, las pruebas, fuera del servidor) no se da por avisada."""
    avisadas = []
    for id_, estado in sorted(estados.items()):
        desde = _instante(estado.get("primer_fallo"))
        if desde is None or estado.get("avisada") or ahora - desde < AVISO_SIN_LEER:
            continue
        registro.warning(
            "fuente %s sin leer desde hace más de %.0f horas (falla desde %s)",
            id_, AVISO_SIN_LEER.total_seconds() / 3600, estado["primer_fallo"],
        )  # fmt: skip
        if avisar is None:
            continue
        nombre = f"{que} {(nombres or {}).get(id_, id_)}"
        try:
            avisar(texto_sin_leer(id_, nombre, estado, ahora))
        except OSError as error:
            # Se reintenta en la recogida siguiente.
            registro.warning("el aviso de la fuente %s no salió: %s", id_, error)
            continue
        estado["avisada"] = _iso(ahora)
        avisadas.append(id_)
    return avisadas


def ejecutar(
    almacen: Almacen,
    ahora: datetime,
    modelos: frozenset[str],
    descargador: Descargador | None = None,
    plazo: Plazo | None = None,
    avisar: Avisar | None = None,
    reloj: Callable[[], float] = time.monotonic,
) -> Recuentos:
    """Lee las fuentes oficiales hasta agotar el plazo, si lo hay, cada una con su tope: primero
    las que vienen respondiendo y al final, con un intento breve, las que vienen fallando.

    `avisar` manda al responsable el aviso de una fuente que lleva AVISO_SIN_LEER sin leerse (no
    se pasa en los ensayos ni en las pruebas)."""
    recuentos = Recuentos()
    descargador = descargador or Descargador(agente=AGENTE_EODI)
    motivos: Counter[str] = Counter()
    # Una fuente quitada de la configuración deja de tener estado.
    ids = {f["id"] for f in fuentes()}
    estados = {k: v for k, v in fallos(almacen).items() if k in ids}
    antes = json.dumps(estados, sort_keys=True)
    # Las que vienen fallando, al final: no quitan tiempo a las que responden.
    orden = sorted(fuentes(), key=lambda f: en_breve(estados.get(f["id"], {})))
    for leidas, fuente in enumerate(orden):
        breve = en_breve(estados.get(fuente["id"], {}))
        if breve:
            recuentos.en_breve.append(fuente["id"])
        tope, limite, reintentos = limites(fuente, breve)
        # El tope de la fuente, sin pasar del que queda para todas.
        restante = math.inf if plazo is None else plazo.restante()
        propio = restante > tope
        de_la_fuente = descargador.con_limites(reintentos, limite)
        de_la_fuente.plazo = Plazo(min(tope, restante), reloj)
        if fuente.get("delegada"):
            de_la_fuente = de_la_fuente.con_transporte(
                lector_delegado.transporte_delegado(fuente["id"], descargador.transporte)
            )
        inicio = reloj()
        try:
            motivo = recoger(almacen, de_la_fuente, fuente, ahora, modelos, recuentos, motivos)
        except TiempoAgotado as error:
            if not propio:
                recuentos.sin_leer = len(orden) - leidas
                registro.warning("oficiales: %s; fuentes sin leer: %d", error, recuentos.sin_leer)
                break
            recuentos.bloqueadas += 1
            motivos["tiempo"] += 1
            motivo = f"cortada al agotar su tope de {tope:.0f} s"
            if de_la_fuente.ultimo_fallo:
                motivo += f" (último intento: {de_la_fuente.ultimo_fallo[:160]})"
        recuentos.tiempos[fuente["id"]] = round(reloj() - inicio, 1)
        if motivo is None:
            estados.pop(fuente["id"], None)
            continue
        recuentos.fallidas[fuente["id"]] = motivo
        anotar_fallo(estados.setdefault(fuente["id"], {}), motivo, ahora)
        # Con las recogidas seguidas que lleva fallando: el resumen diario privado las cuenta
        # (recogida/visitas.py) desde el segundo fallo.
        registro.warning(
            "oficiales: fuente %s falló: %s (%d recogidas seguidas)%s", fuente["id"], motivo,
            estados[fuente["id"]]["fallos_seguidos"],
            "; se sigue probando con un intento breve" if en_breve(estados[fuente["id"]]) else "",
        )  # fmt: skip
    nombres = {str(f["id"]): f"{f['medio']} ({f['pais']})" for f in fuentes()}
    avisar_sin_leer(estados, ahora, avisar, nombres)
    # Sin fallos ni cambios no se escribe: una recogida sin nada nuevo no cambia la base.
    if json.dumps(estados, sort_keys=True) != antes:
        almacen.guardar_cursor(CURSOR_FALLOS, {"fuentes": estados})
    lentas = sorted(recuentos.tiempos.items(), key=lambda par: -par[1])[:6]
    registro.info(
        "oficiales %s motivos=%s; las más lentas (s): %s", recuentos.resumen(), dict(motivos),
        ", ".join(f"{id_}={tiempo:.1f}" for id_, tiempo in lentas),
    )  # fmt: skip
    return recuentos
