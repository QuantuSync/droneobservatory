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
        if self.afirma == "cierre":
            return f"criterio de presencia: cierre por dron que cuenta la fuente: «{self.frase}»"
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


def por_cierre(incidente: Documento) -> Documento | None:
    """La fuente que cuenta el cierre por un dron: el gestor aeroportuario o el de navegación
    aérea actúan atribuyendo el suceso a un dron. None si no hubo cierre o si la frase lo deja
    abierto."""
    cierre = (incidente.get("consecuencias", {}).get("cierre") or {}).get("valor")
    if cierre != "si":
        return None
    fuentes: list[Documento] = incidente["fuentes"]
    for fuente in sorted(fuentes, key=lambda f: (f["fecha"]["valor"], f["id"])):
        frase = str(fuente.get("frase_origen", ""))
        if declaraciones.habla_de_drones(frase) and not declaraciones.abierto(frase):
            return fuente
    return None


def aplicar(incidente: Documento) -> Documento:
    """El incidente con la presencia confirmada por un cierre por dron, si el criterio lo
    alcanza y nada lo impide (desmentido, documento oficial, autoridad que lo deja abierto), y
    con el titular coherente con la presencia."""
    resultado = incidente
    if (
        incidente.get("presencia_dron") == "no_confirmada"
        and incidente["estado"]["actual"] != Estado.DESMENTIDO
        and not documento_oficial_decide(incidente)
        and not autoridad_lo_deja_abierto(incidente)
    ):
        fuente = por_cierre(incidente)
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
        if cambio is None and (cierre := por_cierre(incidente)) is not None:
            cambio = Cambio(incidente["id"], cierre["id"], "", "", "cierre", cierre["frase_origen"])
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


def anotar(almacen: Almacen, anterior: Documento, nuevo: Documento, motivo: str) -> None:
    """El motivo del cambio en el historial, con los campos que cambian."""
    campos = ("presencia_dron", "titulo", "estado", "tiempo")
    antes = {c: anterior.get(c) for c in campos if anterior.get(c) != nuevo.get(c)}
    despues = {c: nuevo.get(c) for c in antes}
    if antes:
        almacen.anotar_motivo(TABLA_MOTIVOS, nuevo["id"], antes, despues, motivo)
