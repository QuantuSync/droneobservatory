"""Fuentes oficiales que confirman incidentes (fiabilidad A, autoridad).

Cada fuente de `configuracion/fuentes_oficiales.json` se lee respetando su
robots.txt y con la identificación del observatorio: las de tipo rss por su
canal y las de tipo pagina por su página de noticias (`paginas_oficiales`).
Una nota que habla de drones se enlaza al incidente que le
corresponde con la regla de fusión (mismo sitio y misma ventana); si encaja con
uno solo, entra como fuente de autoridad y el incidente pasa a confirmado: la
autoridad dice que ocurrió. presencia_dron solo cambia si la nota lo dice sin
reservas («bekræfter», sin «mulige» ni «formodede»). Si no encaja con ninguno o
encaja con varios, no se enlaza.

Cada fuente tiene su propio tiempo (TOPE_FUENTE_S) dentro del tope de todas (TOPE_S): una
fuente lenta o caída se corta, se apunta en el registro con su id y el motivo, y se pasa a la
siguiente. Una fuente que falla en FALLOS_PARA_PAUSA recogidas seguidas se salta durante PAUSA y
después se vuelve a probar; si falla otra vez, otra PAUSA. Una fuente en pausa no es un fallo de
la recogida: sale en el registro y en el resumen diario, y solo se avisa al responsable, una vez
por fuente, si lleva AVISO_PAUSA seguido en pausa. El estado de las pausas va en el cursor
CURSOR_PAUSAS de la base, como el de los demás pasos de la recogida.
"""

import contextlib
import copy
import json
import logging
import math
import os
import re
import time
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
from proceso import incidentes
from proceso.credibilidad import Credibilidad
from proceso.estados import Estado, TransicionNoPermitida, transitar
from proceso.noticias import filtro, lugar, lugar_del_suceso, nomenclator
from recogida import navegador, paginas_oficiales
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
# Pausa automática de una fuente que falla en varias recogidas seguidas.
FALLOS_PARA_PAUSA = 3
PAUSA = timedelta(hours=6)
# Una fuente que lleva este tiempo seguido en pausa se avisa al responsable, una sola vez.
AVISO_PAUSA = timedelta(days=7)
CURSOR_PAUSAS = "oficiales_pausas"
_FORMATOS = {"minuto": "%Y-%m-%dT%H:%MZ", "dia": "%Y-%m-%d"}
# Afirmación expresa de que había drones, sin reservas.
_AFIRMA = re.compile(r"bekræft|bestätig|confirm|potwierdz|confirmă", re.IGNORECASE)
_RESERVA = re.compile(
    r"\bmulig|formod|muligvis|mistanke|possibl|suspect|mutmaß|mögliche|podejrzan|posibil",
    re.IGNORECASE,
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
    bloqueadas: int = 0
    # Fuentes que no dio tiempo a leer en esta ejecución (el tope de todas se agotó).
    sin_leer: int = 0
    # La nota más reciente leída en esta pasada, de cualquier fuente: el último dato de las
    # oficiales. Si la pasada se corta, puede ser anterior a la publicada, que no se rebaja
    # (recogida/estado.py).
    ultima: datetime | None = None
    # Las fuentes que fallaron en esta pasada, con el motivo, y las que se saltaron por estar en
    # pausa (no son un fallo).
    fallidas: dict[str, str] = field(default_factory=dict)
    en_pausa: list[str] = field(default_factory=list)

    def resumen(self) -> str:
        return (
            f"notas={self.notas} relevantes={self.relevantes} enlazadas={self.enlazadas} "
            f"confirmadas={self.confirmadas} bloqueadas={self.bloqueadas} "
            f"sin_leer={self.sin_leer} en_pausa={len(self.en_pausa)}"
        )


def carpeta_renders() -> Path:
    """Donde deja el temporizador de las fuentes de detalle las listas renderizadas."""
    return Path(os.environ.get(VARIABLE_DATOS_DETALLE, "data/detalle")) / "paginas_js"


@cache
def fuentes(ruta: Path = DIRECTORIO / "fuentes_oficiales.json") -> tuple[Documento, ...]:
    datos: dict[str, Any] = json.loads(ruta.read_text(encoding="utf-8"))
    return tuple(datos["fuentes"])


def robots(descargador: Descargador, url: str) -> RobotFileParser:
    partes = urlsplit(url)
    lector = RobotFileParser()
    try:
        texto = descargador.texto(f"{partes.scheme}://{partes.netloc}/robots.txt", lambda _: True)
    except DescargaFallida:
        texto = ""
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


def enlazar(almacen: Almacen, nota: Nota, ahora: datetime, modelos: frozenset[str]) -> str | None:
    """Añade la nota al único incidente que le corresponde. Devuelve su identificador."""
    punto = _punto(nota)
    if punto is None:
        return None
    encajan = [
        i
        for i in almacen.incidentes()
        if incidentes.activo(i) and i["lugar"]["pais"] == nota.fuente["pais"]
        and incidentes.encajan(i, punto)
    ]  # fmt: skip
    if len(encajan) != 1:
        return None
    incidente = copy.deepcopy(encajan[0])
    if any(f["id"] == nota.id for f in incidente["fuentes"]):
        return str(incidente["id"])
    fuente = fuente_oficial(nota)
    incidente["fuentes"] = [*incidente["fuentes"], fuente]
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
    except DocumentoInvalido:
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
    ][: paginas_oficiales.MAX_NOTAS_POR_FUENTE]
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
    return None


def _instante(texto: Any) -> datetime | None:
    try:
        return datetime.fromisoformat(str(texto).replace("Z", "+00:00")) if texto else None
    except ValueError:
        return None


def _iso(momento: datetime) -> str:
    return momento.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def pausas(almacen: Almacen) -> dict[str, dict[str, Any]]:
    """El estado de cada fuente que ha fallado: fallos seguidos, pausa y si se avisó."""
    guardado = (almacen.cursor(CURSOR_PAUSAS) or {}).get("fuentes") or {}
    return {k: dict(v) for k, v in guardado.items() if isinstance(v, dict)}


def en_pausa(estado: dict[str, Any], ahora: datetime) -> bool:
    hasta = _instante(estado.get("pausa_hasta"))
    return hasta is not None and ahora < hasta


def anotar_fallo(estado: dict[str, Any], motivo: str, ahora: datetime) -> bool:
    """Anota un fallo de la fuente; devuelve si entra en pausa."""
    estado["fallos_seguidos"] = int(estado.get("fallos_seguidos") or 0) + 1
    estado["motivo"] = motivo
    estado["ultimo_fallo"] = _iso(ahora)
    if estado["fallos_seguidos"] < FALLOS_PARA_PAUSA:
        return False
    # La tercera vez seguida, y cada vez que falla al volver a probarla, otra pausa.
    estado["pausa_hasta"] = _iso(ahora + PAUSA)
    estado.setdefault("en_pausa_desde", _iso(ahora))
    return True


Avisar = Callable[[str], None]


def avisar_pausas_largas(
    estados: dict[str, dict[str, Any]], ahora: datetime, avisar: Avisar | None
) -> None:
    """Avisa, una vez por fuente, de las que llevan AVISO_PAUSA seguido en pausa."""
    for id_, estado in sorted(estados.items()):
        desde = _instante(estado.get("en_pausa_desde"))
        if desde is None or estado.get("avisada") or ahora - desde < AVISO_PAUSA:
            continue
        texto = (
            f"La fuente oficial {id_} lleva en pausa desde el {desde:%Y-%m-%d %H:%M} UTC "
            f"({(ahora - desde).days} días): falla cada vez que se vuelve a probar. Último "
            f"motivo: {estado.get('motivo', 'sin motivo')}. Revisar su dirección en "
            "configuracion/fuentes_oficiales.json."
        )
        registro.warning(
            "oficiales: fuente %s en pausa %d días seguidos", id_, (ahora - desde).days
        )
        if avisar is None:
            continue
        try:
            avisar(texto)
        except OSError as error:
            # Se reintenta en la recogida siguiente.
            registro.warning("oficiales: el aviso de la fuente %s no salió: %s", id_, error)
            continue
        estado["avisada"] = _iso(ahora)


def ejecutar(
    almacen: Almacen,
    ahora: datetime,
    modelos: frozenset[str],
    descargador: Descargador | None = None,
    plazo: Plazo | None = None,
    avisar: Avisar | None = None,
    reloj: Callable[[], float] = time.monotonic,
) -> Recuentos:
    """Lee las fuentes oficiales hasta agotar el plazo, si lo hay, cada una con su tope.

    `avisar` manda al responsable el aviso de una fuente que lleva AVISO_PAUSA en pausa (no se
    pasa en los ensayos ni en las pruebas)."""
    recuentos = Recuentos()
    descargador = descargador or Descargador(agente=AGENTE_EODI)
    motivos: Counter[str] = Counter()
    # Una fuente quitada de la configuración deja de tener estado.
    ids = {f["id"] for f in fuentes()}
    estados = {k: v for k, v in pausas(almacen).items() if k in ids}
    activas = []
    for fuente in fuentes():
        estado = estados.get(fuente["id"], {})
        if en_pausa(estado, ahora):
            recuentos.en_pausa.append(fuente["id"])
            registro.warning(
                "oficiales: fuente %s en pausa hasta %s (falló %d recogidas seguidas: %s)",
                fuente["id"], estado["pausa_hasta"], estado.get("fallos_seguidos", 0),
                estado.get("motivo"),
            )  # fmt: skip
        else:
            activas.append(fuente)
    for leidas, fuente in enumerate(activas):
        # El tope de la fuente, sin pasar del que queda para todas.
        restante = math.inf if plazo is None else plazo.restante()
        propio = restante > TOPE_FUENTE_S
        descargador.plazo = Plazo(min(TOPE_FUENTE_S, restante), reloj)
        try:
            motivo = recoger(almacen, descargador, fuente, ahora, modelos, recuentos, motivos)
        except TiempoAgotado as error:
            if not propio:
                recuentos.sin_leer = len(activas) - leidas
                registro.warning("oficiales: %s; fuentes sin leer: %d", error, recuentos.sin_leer)
                break
            recuentos.bloqueadas += 1
            motivos["tiempo"] += 1
            motivo = f"cortada al agotar su tope de {TOPE_FUENTE_S:.0f} s"
        if motivo is None:
            estados.pop(fuente["id"], None)
            continue
        recuentos.fallidas[fuente["id"]] = motivo
        pausa = anotar_fallo(estados.setdefault(fuente["id"], {}), motivo, ahora)
        # Con las recogidas seguidas que lleva fallando: el resumen diario privado las cuenta
        # (recogida/visitas.py) desde el segundo fallo, sin esperar al aviso de los 7 días.
        registro.warning(
            "oficiales: fuente %s falló: %s (%d recogidas seguidas)%s", fuente["id"], motivo,
            estados[fuente["id"]]["fallos_seguidos"],
            f"; en pausa {PAUSA.total_seconds() / 3600:.0f} h" if pausa else "",
        )  # fmt: skip
    descargador.plazo = None
    avisar_pausas_largas(estados, ahora, avisar)
    almacen.guardar_cursor(CURSOR_PAUSAS, {"fuentes": estados})
    registro.info("oficiales %s motivos=%s", recuentos.resumen(), dict(motivos))
    return recuentos
