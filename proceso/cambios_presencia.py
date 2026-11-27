"""El historial público de la presencia del dron: cada cambio de valor de una ficha (confirmada, no
confirmada, no acreditada, descartada), con su fecha, de qué valor a qué valor, el motivo en
español y en inglés y, si la hay, la frase de origen que lo sostiene con su fuente y su enlace.

Desde el 27 de noviembre de 2026 (EODI-2026-01008, Ludza: pasó de «no confirmada» a «confirmada»
a las 07:32 UTC con la nota ampliada del ejército letón, y la web solo enseñaba el historial del
estado). Cada cambio se guarda al guardar la ficha (`Almacen.guardar_incidente`) en la tabla
`presencia_cambios`, con la regla de proceso/decidir.py que lo decide y la fuente en que se apoya.
Los cambios anteriores se rellenan una vez desde el historial de la base (`rellenar`): la versión
de antes y la de después de cada cambio están guardadas; la regla y la fuente se leen con las
reglas de hoy sobre la versión de después y, si no dan ese valor, el cambio sale sin motivo
(«motivo no guardado»): no se inventa ninguno. Lo que no consta no se enseña.

Solo se publica lo que ya es público: el motivo escrito para la web (nunca el motivo interno del
historial), la frase de origen de una fuente pública (recortada) y su medio y su enlace. Se publican
los cambios desde que la ficha salió en la web, uno por hora como mucho (lo que va y vuelve dentro
de la misma hora nunca se vio publicado): `pasos_publicos`.
"""

import logging
import re
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from esquema import Documento

registro = logging.getLogger(__name__)

# El cursor que dice que los cambios anteriores a la tabla ya se rellenaron desde el historial.
CURSOR_RELLENO = "presencia_cambios:relleno"
# Largo máximo de la frase publicada (la «frase breve de origen» de las fuentes).
MAX_FRASE = 300
VALORES = ("confirmada", "no_confirmada", "no_acreditada", "descartada")

# El motivo público de cada regla (proceso/decidir.py), en español y en inglés.
MOTIVOS: dict[str, tuple[str, str]] = {
    "autoridad_atribuye": (
        "una autoridad afirma que hubo un dron",
        "an authority states there was a drone",
    ),
    "documento_oficial": (
        "la autoridad lo dice en su propio comunicado",
        "the authority says so in its own statement",
    ),
    "pruebas_fisicas": (
        "hay pruebas físicas del dron (restos, derribo o captura) y el suceso está confirmado",
        "there is physical evidence of the drone (debris, downing or capture) and the event is "
        "confirmed",
    ),
    "rectificacion": (
        "rectificación oficial de la autoridad",
        "official correction by the authority",
    ),
    "revision": (
        "revisión a mano contra la fuente citada",
        "manual review against the cited source",
    ),
    "descartada": (
        "una fuente dice que era otra cosa",
        "a source says it was something else",
    ),
    "sin_autoridad": (
        "ninguna autoridad afirma que hubiera un dron: solo hay avisos, sospechas o lo que cuenta "
        "la prensa",
        "no authority states there was a drone: there are only reports, suspicions or press "
        "accounts",
    ),
    "sin_suceso_confirmado": (
        "ninguna autoridad confirma el suceso",
        "no authority confirms the event",
    ),
    "actuacion": (
        "la autoridad actúa por un dron (un cierre o una intervención) y lo cuenta la fuente",
        "the authority acts because of a drone (a closure or an intervention) and the source "
        "reports it",
    ),
    "abierta": (
        "una fuente cuenta que el dron no se encontró o lo pone en duda",
        "a source reports that the drone was not found or casts doubt on it",
    ),
    "experto": (
        "revisión del experto contra las fuentes de la ficha",
        "expert review against the record's sources",
    ),
    "deshecho": (
        "se deshace el cambio anterior: la unión con otra ficha que lo traía no se hizo",
        "the previous change is undone: the merge with another record that brought it was not made",
    ),
    "sin_motivo": (
        "cambio anterior al registro de sus motivos: el motivo no se guardó",
        "change made before reasons were recorded: the reason was not saved",
    ),
}
# Lo que se añade al motivo de una bajada cuando la frase es la que la sostenía antes.
ANTES_SE_APOYABA = (
    "antes se apoyaba en esta frase",
    "it previously relied on this sentence",
)


@dataclass(frozen=True)
class Cambio:
    """Un cambio de presencia tal como se guarda en la tabla `presencia_cambios`."""

    incidente: str
    fecha: str
    de: str
    a: str
    regla: str
    fuente_id: str | None = None
    frase: str | None = None
    enlace: str | None = None
    medio: str | None = None
    anterior: bool = False


def _fuente(documento: Documento, fuente_id: str | None) -> Documento | None:
    if not fuente_id:
        return None
    for fuente in documento.get("fuentes", []):
        if fuente.get("id") == fuente_id:
            return dict(fuente)
    return None


def _publicable(fuente: Documento | None) -> bool:
    if fuente is None or not str(fuente.get("frase_origen") or "").strip():
        return False
    from exportacion.proyeccion import fuente_publica
    from proceso.estados import Capa

    try:
        return fuente_publica(fuente, Capa.GENERAL)
    except (KeyError, ValueError):
        return False


def _autoridad_que_habla_del_dron(documento: Documento) -> Documento | None:
    """La fuente pública que habla de drones con la palabra de una autoridad: primero una cita
    revisada a mano («revisada-»), luego la declaración de una autoridad."""
    from proceso import declaraciones

    def habla(fuente: Documento) -> bool:
        frase = str(fuente.get("frase_origen") or "")
        return declaraciones.habla_de_drones(frase) and _publicable(fuente)

    fuentes = documento.get("fuentes", [])
    for fuente in fuentes:
        if str(fuente.get("id", "")).startswith("revisada-") and habla(fuente):
            return dict(fuente)
    for fuente in fuentes:
        if declaraciones.de_autoridad(fuente) and habla(fuente):
            return dict(fuente)
    return None


def _frase(texto: str) -> str:
    texto = " ".join(texto.split())
    if len(texto) <= MAX_FRASE:
        return texto
    return texto[: MAX_FRASE - 1].rsplit(" ", 1)[0] + "…"


def regla_de_motivo(motivo: str, a: str) -> str | None:
    """La regla que dice el motivo que guardó la base con el cambio (historial,
    incidentes_motivos), para los cambios que las reglas de hoy no explican: lo que decidía la
    regla de entonces. None si el motivo no habla de la presencia (un titular, un lugar)."""
    texto = motivo.strip()
    if not texto:
        return None
    if texto.startswith("un solo sitio decide"):
        encontrado = _POR_REGLA.search(texto)
        regla = encontrado["regla"] if encontrado else None
        return regla if regla in MOTIVOS else None
    if texto.startswith("criterio de presencia"):
        if a == "confirmada":
            actua = "la autoridad actúa por un dron" in texto
            return "actuacion" if actua else "autoridad_atribuye"
        return "sin_autoridad"
    if texto.startswith("control de fichas: presencia no confirmada"):
        return "abierta"
    if texto.startswith("rectificación oficial"):
        return "rectificacion"
    if texto.startswith("repaso de entrada con el experto"):
        return "experto"
    if texto.startswith(_SIN_PRESENCIA):
        return None
    # Lo demás es el motivo de una revisión a mano (configuracion/incidentes_revisados.json:
    # citas, separaciones, titulares y presencias revisadas, con su texto).
    return "revision"


_POR_REGLA = re.compile(r"presencia \w+ por (?P<regla>\w+)")
# Motivos de cambios que no son de la presencia: lo que la cambió en ese momento no se sabe.
_SIN_PRESENCIA = ("titular coherente", "control de fichas:", "cerrojo", "unión", "unido")
_CITA = re.compile(r"«([^«»]{12,})»")


def _fuente_citada(motivo: str, *documentos: Documento) -> Documento | None:
    """La fuente pública cuya frase cita el motivo entre comillas."""
    for cita in _CITA.findall(motivo):
        trozo = cita.strip(" .…")[:80]
        for documento in documentos:
            for fuente in documento.get("fuentes", []):
                if trozo and trozo in str(fuente.get("frase_origen") or "") and _publicable(fuente):
                    return dict(fuente)
    return None


def describir(
    incidente: str,
    fecha: str,
    anterior: Documento,
    nuevo: Documento,
    negadas: frozenset[str] = frozenset(),
    motivo: str = "",
) -> Cambio | None:
    """El cambio de presencia entre dos versiones guardadas de la ficha, con la regla que lo decide
    y la frase en que se apoya; None si la presencia no cambia o no es un valor conocido. Si las
    reglas de hoy no dan ese valor, manda el motivo que guardó la base con el cambio (`motivo`);
    sin él, el cambio sale sin motivo."""
    from proceso import decidir

    de, a = anterior.get("presencia_dron"), nuevo.get("presencia_dron")
    if de == a or de not in VALORES or a not in VALORES:
        return None
    try:
        decision = decidir.decidir_presencia(nuevo, negadas, de == "confirmada")
    except Exception:
        registro.exception("%s: sin regla para el cambio de presencia", incidente)
        decision = None
    fuente: Documento | None
    if decision is not None and decision.valor == a and decision.regla in MOTIVOS:
        regla = decision.regla
        fuente = _fuente(nuevo, decision.fuente_id)
    else:
        regla = regla_de_motivo(motivo, str(a)) or "sin_motivo"
        if regla == "sin_motivo":
            return Cambio(str(incidente), fecha, str(de), str(a), regla)
        fuente = _fuente_citada(motivo, nuevo, anterior)
    if not _publicable(fuente) and a == "confirmada":
        fuente = _autoridad_que_habla_del_dron(nuevo)
    previa = False
    if not _publicable(fuente) and de == "confirmada":
        # Una bajada sin frase propia: la frase en que se apoyaba la confirmación.
        try:
            antes = decidir.decidir_presencia(anterior, negadas, True)
        except Exception:
            antes = None
        if antes is not None and antes.valor == "confirmada":
            fuente = _fuente(anterior, antes.fuente_id)
        if not _publicable(fuente):
            # Sin ella (o con las reglas de hoy la versión de antes tampoco se confirmaría: la
            # regla cambió, como en EODI-2026-00821): la frase de autoridad que habla del dron.
            fuente = _autoridad_que_habla_del_dron(anterior)
        previa = fuente is not None
    if not _publicable(fuente):
        return Cambio(str(incidente), fecha, str(de), str(a), regla)
    assert fuente is not None
    return Cambio(
        str(incidente), fecha, str(de), str(a), regla,
        fuente_id=str(fuente["id"]),
        frase=_frase(str(fuente.get("frase_origen") or "")),
        enlace=str(fuente.get("enlace") or "") or None,
        medio=str(fuente.get("medio") or "") or None,
        anterior=previa,
    )  # fmt: skip


def deshecho(actual: Documento, anterior: Documento) -> Cambio:
    """La vuelta a la presencia de antes cuando el cerrojo deshace el último guardado."""
    return Cambio(
        str(anterior["id"]), ahora_utc(), str(actual.get("presencia_dron")),
        str(anterior.get("presencia_dron")), "deshecho",
    )  # fmt: skip


def ahora_utc() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def rellenar(almacen: Any) -> int:
    """Una vez: los cambios de presencia que guardó el historial de la base antes de existir la
    tabla. Lo que ya está en la tabla (guardado al guardar la ficha) no se repite. Devuelve
    cuántos añade."""
    if almacen.cursor(CURSOR_RELLENO) is not None:
        return 0
    desde = almacen.primer_cambio_de_presencia()
    motivos = almacen.motivos_guardados()
    cambios = []
    for incidente, fecha, anterior, nuevo in almacen.versiones_con_cambio_de_presencia(desde):
        motivo = _motivo_del_momento(motivos.get(incidente, []), fecha)
        cambio = describir(incidente, fecha, anterior, nuevo, motivo=motivo)
        if cambio is not None:
            cambios.append(cambio)
    almacen.anotar_cambios_presencia(cambios, origen="historial")
    almacen.guardar_cursor(CURSOR_RELLENO, {"rellenados": len(cambios), "hasta": desde})
    registro.info("cambios de presencia rellenados desde el historial: %d", len(cambios))
    return len(cambios)


def _motivo_del_momento(motivos: list[tuple[str, str]], fecha: str) -> str:
    """El motivo que guardó la base con el cambio: de los del mismo minuto, el que dice una regla
    de la presencia; si no, el primero de ese minuto."""
    del_minuto = [m for f, m in motivos if f[:16] == fecha[:16]]
    for motivo in del_minuto:
        if regla_de_motivo(motivo, "confirmada") not in (None, "revision"):
            return motivo
    return del_minuto[0] if del_minuto else ""


def _hora(fecha: str) -> str:
    return fecha[:13]


def pasos_publicos(cambios: Iterable[Documento], primera: str | None) -> list[Documento]:
    """Los cambios que se publican de una ficha: desde su primera publicación (`primera`; sin ella,
    ninguno) y, dentro de cada hora, solo el resultado (lo que va y vuelve en la misma recogida
    nunca salió en la web). Cada paso: fecha, de, a, motivo y, si la hay, la frase con su fuente.
    Una ficha que ya estaba publicada al sembrar la tabla de lo publicado tiene `primera` vacía:
    cuenta desde siempre."""
    if primera is None:
        return []
    ordenados = sorted(
        (c for c in cambios if str(c["fecha"]) >= primera), key=lambda c: (c["fecha"], c["id"])
    )
    pasos: list[Documento] = []
    for grupo in _por_hora(ordenados):
        de, ultimo = grupo[0]["de"], grupo[-1]
        if de == ultimo["a"]:
            continue
        pasos.append(_paso(de, ultimo))
    return pasos


def _por_hora(cambios: list[Documento]) -> Iterator[list[Documento]]:
    grupo: list[Documento] = []
    for cambio in cambios:
        if grupo and _hora(str(grupo[0]["fecha"])) != _hora(str(cambio["fecha"])):
            yield grupo
            grupo = []
        grupo.append(cambio)
    if grupo:
        yield grupo


def _paso(de: str, cambio: Documento) -> Documento:
    es, en = MOTIVOS.get(str(cambio["regla"]), MOTIVOS["sin_motivo"])
    if cambio.get("frase") and cambio.get("anterior"):
        es, en = f"{es}; {ANTES_SE_APOYABA[0]}", f"{en}; {ANTES_SE_APOYABA[1]}"
    paso: Documento = {
        "fecha": {"valor": str(cambio["fecha"])[:16] + "Z", "precision": "minuto"},
        "de": de,
        "a": str(cambio["a"]),
        "motivo": {"es": es, "en": en},
    }
    if cambio.get("frase"):
        paso["frase"] = str(cambio["frase"])
        for campo in ("fuente_id", "medio", "enlace"):
            if cambio.get(campo):
                paso[campo] = str(cambio[campo])
    return paso


def con_cambios(publicos: Iterable[Documento], almacen: Any) -> None:
    """Añade `presencia_cambios` a cada ficha publicada que tenga alguno (in situ). Una ficha sin
    cambios publicados no lleva el campo."""
    publicos = list(publicos)
    ids = {str(p.get("id")) for p in publicos}
    todos = almacen.cambios_presencia(ids)
    primeras = almacen.primeras_publicaciones()
    for publico in publicos:
        id_ = str(publico.get("id"))
        pasos = pasos_publicos(todos.get(id_, []), primeras.get(id_))
        if pasos:
            publico["presencia_cambios"] = pasos
