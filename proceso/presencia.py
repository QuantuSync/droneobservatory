"""Presencia del dron: si la autoridad competente lo da por hecho, está confirmada.

Dos valores para los incidentes vigentes (además de descartada, que no se toca):

- confirmada: una autoridad competente (gestor aeroportuario, gestor de navegación aérea,
  policía, fuerzas armadas, ministerio, gobierno, fiscalía, autoridad de aviación civil) actúa
  o declara atribuyendo el suceso a un dron: su declaración citada (proceso/declaraciones.py)
  o un cierre por dron que cuenta la fuente («stilgelegd na melding drone»). No se piden
  restos, grabación ni detección por sensor;
- no_confirmada: la propia autoridad lo deja abierto («posible dron», «objeto no
  identificado», «se investiga si era un dron») o ninguna autoridad lo atribuye a un dron.

La revisión vuelve a leer las declaraciones de las extracciones guardadas y las frases de las
fuentes, sin llamar al extractor ni descargar nada, y confirma la presencia de los incidentes
que el criterio alcanza; ajusta después el titular (proceso/titulares.py). Lo que dice una
autoridad en su propio documento (proceso/detalle.py) manda. Nada se borra: cada cambio entra
como versión nueva del incidente, con la afirmación de presencia_dron y su fuente, y el motivo
queda en el historial. Es idempotente: la recogida horaria la ejecuta en cada pasada.
"""

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from almacen.base import Almacen, DocumentoInvalido
from esquema import Documento
from proceso import declaraciones, titulares
from proceso.estados import Estado
from proceso.incidentes import activo, id_fuente

TABLA_MOTIVOS = "incidentes_motivos"


@dataclass(frozen=True)
class Cambio:
    incidente: str
    fuente_id: str
    autoridad: str
    categoria: str
    afirma: str
    frase: str

    @property
    def motivo(self) -> str:
        if self.afirma == "actuacion":
            return (
                "criterio de presencia: la autoridad actúa por un dron (cierre o intervención) "
                f"y lo cuenta la fuente: «{self.frase}»"
            )
        return (
            f"criterio de presencia: {self.autoridad} ({self.categoria}, declaración "
            f"«{self.afirma}») atribuye el suceso a un dron: «{self.frase}»"
        )


def documento_oficial_decide(incidente: Documento) -> bool:
    """Una autoridad dice algo de la presencia en su propio documento: manda."""
    return any(
        f.get("documento_oficial") and "presencia_dron" in f.get("campos_respaldados", [])
        for f in incidente["fuentes"]
    )


def autoridad_lo_deja_abierto(incidente: Documento) -> bool:
    """Todas las autoridades que cita el incidente lo dejan abierto."""
    autoridades = [f for f in incidente["fuentes"] if f.get("es_autoridad")]
    return bool(autoridades) and all(
        declaraciones.abierto(str(f.get("frase_origen", ""))) for f in autoridades
    )


# Medidas de una autoridad por el dron (respuesta.medidas): intervención policial, cazas,
# derribo, inhibición, cierre del espacio aéreo.
MEDIDAS_DE_AUTORIDAD = frozenset(
    {"cierre_espacio_aereo", "patrulla", "cazas", "derribo", "inhibicion"}
)


def actua_la_autoridad(incidente: Documento) -> bool:
    """Una autoridad actuó por el suceso: cerró el aeropuerto o el espacio aéreo, o intervino."""
    cierre = (incidente.get("consecuencias", {}).get("cierre") or {}).get("valor")
    medidas = set((incidente.get("respuesta") or {}).get("medidas") or [])
    return cierre == "si" or bool(medidas & MEDIDAS_DE_AUTORIDAD)


# La policía acude, detiene, multa o decomisa por un dron: actúa por el dron.
DETENCION = re.compile(
    r"(?<!\w)(?:rykker (?:ut|til)|rykket (?:ut|til)|ryckte ut|rückt\w* aus|ausgerückt|"
    r"responding to|responded to|acudi\w*|interv(?:ino|inieron|ened|ention)|ruszy\w*|"
    r"detenid\w*|arrestad\w*|arrested|arrests?|festgenommen|festnahme\w*|"
    r"verhaftet|anholdt|pågrepet|innbrakt|gripen|zatrzyma\w*|aangehouden|opgepakt|aresta\w*|"
    r"interpel\w*|multad\w*|sancionad\w*|fined|bußgeld\w*|beboet|bötfäll\w*|"
    r"incautad\w*|decomisad\w*|seized|beschlagnahmt|in beslag)(?!\w)",
    re.IGNORECASE,
)


# La frase cuenta el cierre del aeropuerto o del espacio aéreo («wegen Drohnen gesperrt»).
CIERRE_EN_FRASE = re.compile(
    r"(?<!\w)(?:gesperrt|geschlossen|stillgelegt|eingestellt|cerrad\w*|cierr\w*|paraliz\w*|"
    r"closed|closure|shut|lukket|lukke\w*|stengt|stengte|stängd\w*|zamkni\w*|ferm[ée]\w*|"
    r"fermeture|stilgelegd|gesloten|chius\w*|[îi]nchis\w*|paralys\w*|suspendid\w*|"
    r"suspended)(?!\w)",
    re.IGNORECASE,
)


def por_actuacion(incidente: Documento) -> Documento | None:
    """La fuente que cuenta que la autoridad actuó por un dron (un cierre, una intervención
    policial, cazas, un derribo, una detención o una multa por volarlo): actúa atribuyendo el
    suceso a un dron. Con el cierre o la medida registrados basta la primera fuente que no lo
    deja abierto, aunque su frase no repita la palabra dron (el incidente es de un dron). None si
    no actuó o si las fuentes que nombran el dron lo dejan abierto."""
    fuentes: list[Documento] = sorted(
        incidente["fuentes"], key=lambda f: (f["fecha"]["valor"], f["id"])
    )
    actua = actua_la_autoridad(incidente)
    titulo = " ".join(str(v) for v in (incidente.get("titulo") or {}).values())
    for fuente in fuentes:
        frase = str(fuente.get("frase_origen", ""))
        if not declaraciones.habla_de_drones(frase) or declaraciones.abierto(frase):
            continue
        if (
            actua
            or DETENCION.search(frase)
            or DETENCION.search(titulo)
            or CIERRE_EN_FRASE.search(frase)
        ):
            return fuente
    if actua and not any(
        declaraciones.habla_de_drones(str(f.get("frase_origen", "")))
        and declaraciones.abierto(str(f.get("frase_origen", "")))
        for f in fuentes
    ):
        for fuente in fuentes:
            frase = str(fuente.get("frase_origen", ""))
            if frase and not declaraciones.abierto(frase):
                return fuente
    return None


def aplicar(incidente: Documento) -> Documento:
    """El incidente con la presencia confirmada por la actuación de la autoridad (un cierre o una
    intervención por dron), si el criterio lo
    alcanza y nada lo impide (desmentido, documento oficial, autoridad que lo deja abierto), y
    con el titular coherente con la presencia."""
    resultado = incidente
    if (
        incidente.get("presencia_dron") == "no_confirmada"
        and incidente["estado"]["actual"] != Estado.DESMENTIDO
        and not documento_oficial_decide(incidente)
        and not autoridad_lo_deja_abierto(incidente)
    ):
        fuente = por_actuacion(incidente)
        if fuente is not None:
            resultado = {**incidente, "afirmaciones": list(incidente.get("afirmaciones", []))}
            declaraciones.confirmar_presencia(resultado, fuente["id"])
    return titulares.ajustar_incidente(resultado)


def _declaraciones_del_candidato(almacen: Almacen, candidato: str) -> dict[str, dict[str, Any]]:
    """Identificador de la fuente de cada declaración (el que le da declaraciones.fuente) y la
    declaración. Una extracción posterior sustituye a la anterior."""
    resultado: dict[str, dict[str, Any]] = {}
    for extraccion in almacen.extracciones(candidato):
        enviadas = extraccion.get("enviadas") or []
        for numero, declaracion in enumerate(extraccion.get("declaraciones") or [], 1):
            indice = declaracion.get("fuente")
            if isinstance(indice, int) and 1 <= indice <= len(enviadas):
                noticia = id_fuente(enviadas[indice - 1])
                resultado[f"{noticia}-declaracion-{numero}"] = declaracion
    return resultado


def _candidatos(incidente: Documento, por_id: dict[str, Documento], absorbidos: Any) -> set[str]:
    """Los candidatos del incidente y de los que se fundieron en él."""
    resultado: set[str] = set()
    pendientes, vistos = [incidente["id"]], set()
    while pendientes:
        id_ = pendientes.pop()
        if id_ in vistos or id_ not in por_id:
            continue
        vistos.add(id_)
        candidato = por_id[id_]["control"].get("candidato")
        if candidato:
            resultado.add(candidato)
        pendientes.extend(absorbidos.get(id_, ()))
    return resultado


def pendientes(almacen: Almacen) -> list[tuple[Documento, Cambio]]:
    """Los incidentes cuya presencia confirma la regla y aún no la tienen, con el cambio."""
    todos = almacen.incidentes()
    por_id = {i["id"]: i for i in todos}
    absorbidos: dict[str, list[str]] = {}
    for fusion in almacen.fusiones():
        if not fusion["revertida"]:
            absorbidos.setdefault(fusion["destino"], []).append(fusion["absorbido"])
    resultado = []
    for incidente in todos:
        if not activo(incidente) or incidente.get("presencia_dron") != "no_confirmada":
            continue
        # Desmentido por una autoridad: la frase de otra que cuenta los drones no lo cambia.
        if incidente["estado"]["actual"] == Estado.DESMENTIDO:
            continue
        # Lo que dice de la presencia una autoridad en su propio documento (proceso/detalle.py:
        # una investigación cerrada que no pudo demostrar que fueran drones) manda sobre la
        # declaración que cita un medio.
        if any(
            f.get("documento_oficial") and "presencia_dron" in f.get("campos_respaldados", [])
            for f in incidente["fuentes"]
        ):
            continue
        conocidas: dict[str, dict[str, Any]] = {}
        for candidato in sorted(_candidatos(incidente, por_id, absorbidos)):
            conocidas |= _declaraciones_del_candidato(almacen, candidato)
        if autoridad_lo_deja_abierto(incidente):
            continue
        fuentes = sorted(incidente["fuentes"], key=lambda f: (f["fecha"]["valor"], f["id"]))
        por_enlace = {f["enlace"]: f for f in fuentes if not f.get("es_autoridad")}
        cambio = None
        for fuente in fuentes:
            declaracion = conocidas.get(fuente["id"])
            if declaracion is None or not fuente.get("es_autoridad"):
                continue
            contexto = str(por_enlace.get(fuente["enlace"], {}).get("frase_origen", ""))
            if declaraciones.confirma_dron(declaracion, contexto):
                cambio = Cambio(
                    incidente["id"], fuente["id"], str(declaracion.get("autoridad", "")),
                    str(declaracion.get("categoria", "")), str(declaracion["afirma"]),
                    fuente["frase_origen"],
                )  # fmt: skip
                break
        if cambio is None and (actua := por_actuacion(incidente)) is not None:
            cambio = Cambio(
                incidente["id"], actua["id"], "", "", "actuacion", actua["frase_origen"]
            )
        if cambio is not None:
            resultado.append((incidente, cambio))
    return resultado


def revisar(
    almacen: Almacen, ahora: datetime, modelos: frozenset[str]
) -> tuple[list[Cambio], list[str]]:
    """Aplica la regla a la base. Devuelve los cambios hechos y los incidentes que no se
    pudieron guardar (no validan con las reglas de ahora; se quedan como estaban)."""
    hechos, fallidos = [], []
    instante = {"valor": ahora.astimezone(UTC).strftime("%Y-%m-%dT%H:%MZ"), "precision": "minuto"}
    for incidente, cambio in pendientes(almacen):
        documento = {**incidente, "control": {**incidente["control"]}}
        if not declaraciones.confirmar_presencia(documento, cambio.fuente_id):
            continue
        documento = titulares.ajustar_incidente(documento)
        documento["control"]["ultima_actualizacion"] = instante
        try:
            almacen.guardar_incidente(documento, ahora, modelos)
        except DocumentoInvalido:
            fallidos.append(incidente["id"])
            continue
        anotar(almacen, incidente, documento, cambio.motivo)
        hechos.append(cambio)
    # Confirmada solo por la actuación (un cierre o una intervención que cuenta la prensa) y la
    # autoridad, después, lo deja abierto («mulige droner»): queda sin confirmar.
    for incidente in almacen.incidentes():
        if not activo(incidente) or incidente.get("presencia_dron") != "confirmada":
            continue
        documento = quitar_por_actuacion(incidente)
        if documento is incidente:
            continue
        documento = titulares.ajustar_incidente(documento)
        documento = {**documento, "control": {**documento["control"],
                                              "ultima_actualizacion": instante}}  # fmt: skip
        try:
            almacen.guardar_incidente(documento, ahora, modelos)
        except DocumentoInvalido:
            fallidos.append(incidente["id"])
            continue
        anotar(almacen, incidente, documento, MOTIVO_ABIERTO)
    # Los titulares que no dicen lo mismo que la presencia (los guardados antes de la regla).
    for incidente in almacen.incidentes():
        if not activo(incidente):
            continue
        documento = titulares.ajustar_incidente(incidente)
        if documento is incidente:
            continue
        documento = {**documento, "control": {**documento["control"],
                                              "ultima_actualizacion": instante}}  # fmt: skip
        try:
            almacen.guardar_incidente(documento, ahora, modelos)
        except DocumentoInvalido:
            fallidos.append(incidente["id"])
            continue
        anotar(almacen, incidente, documento, MOTIVO_TITULAR)
    return hechos, fallidos


MOTIVO_TITULAR = "titular coherente con la presencia del dron (proceso/titulares.py)"
MOTIVO_ABIERTO = (
    "criterio de presencia: la autoridad lo deja abierto; la actuación que contaba la prensa no "
    "basta"
)


def quitar_por_actuacion(incidente: Documento) -> Documento:
    """Sin la confirmación que solo venía de la actuación (fuente que no es autoridad) cuando
    todas las autoridades citadas lo dejan abierto. El mismo incidente si no hay nada que
    quitar."""
    if not autoridad_lo_deja_abierto(incidente) or documento_oficial_decide(incidente):
        return incidente
    fuentes = {f["id"]: f for f in incidente["fuentes"]}
    de_regla = [
        a for a in incidente.get("afirmaciones", [])
        if a["campo"] == "presencia_dron" and a["valor"] == "confirmada"
        and a == declaraciones.afirmacion_presencia(a["fuente_id"])
    ]  # fmt: skip
    if not de_regla or any(fuentes.get(a["fuente_id"], {}).get("es_autoridad") for a in de_regla):
        return incidente
    return {
        **incidente,
        "presencia_dron": "no_confirmada",
        "afirmaciones": [a for a in incidente.get("afirmaciones", []) if a not in de_regla],
    }


def anotar(almacen: Almacen, anterior: Documento, nuevo: Documento, motivo: str) -> None:
    """El motivo del cambio en el historial, con los campos que cambian."""
    campos = ("presencia_dron", "titulo", "estado", "tiempo")
    antes = {c: anterior.get(c) for c in campos if anterior.get(c) != nuevo.get(c)}
    despues = {c: nuevo.get(c) for c in antes}
    if antes:
        almacen.anotar_motivo(TABLA_MOTIVOS, nuevo["id"], antes, despues, motivo)
