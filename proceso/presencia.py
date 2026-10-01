"""Revisión de la presencia del dron con las declaraciones oficiales ya guardadas.

La regla está en proceso/declaraciones.py: si una autoridad (gobierno, ministerio, fuerzas
armadas, policía o gestor del espacio aéreo) dice expresamente que hubo drones, la presencia
es confirmada; también cuando lo dice al atribuir el incidente. Las declaraciones que ya
están en la base se aplicaron con la regla anterior, que solo confirmaba con «drones»: esta
revisión las vuelve a leer de las extracciones guardadas, sin llamar al extractor, y
confirma la presencia de los incidentes que la regla alcanza.

Solo cambia incidentes activos con la presencia sin confirmar. Nada se borra: el cambio
queda en el historial de la base con la afirmación de presencia_dron y la fuente que lo
provoca. Es idempotente: la recogida horaria la ejecuta en cada pasada y, una vez
aplicada, no vuelve a cambiar nada.
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from almacen.base import Almacen, DocumentoInvalido
from esquema import Documento
from proceso import declaraciones
from proceso.estados import Estado
from proceso.incidentes import activo, id_fuente


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
        return (
            f"{self.autoridad} ({self.categoria}, declaración «{self.afirma}») "
            f"nombra drones: «{self.frase}»"
        )


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
        conocidas: dict[str, dict[str, Any]] = {}
        for candidato in sorted(_candidatos(incidente, por_id, absorbidos)):
            conocidas |= _declaraciones_del_candidato(almacen, candidato)
        fuentes = sorted(incidente["fuentes"], key=lambda f: (f["fecha"]["valor"], f["id"]))
        for fuente in fuentes:
            declaracion = conocidas.get(fuente["id"])
            if declaracion is None or not fuente.get("es_autoridad"):
                continue
            if declaraciones.confirma_dron(declaracion):
                cambio = Cambio(
                    incidente["id"], fuente["id"], str(declaracion.get("autoridad", "")),
                    str(declaracion.get("categoria", "")), str(declaracion["afirma"]),
                    fuente["frase_origen"],
                )  # fmt: skip
                resultado.append((incidente, cambio))
                break
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
        documento["control"]["ultima_actualizacion"] = instante
        try:
            almacen.guardar_incidente(documento, ahora, modelos)
        except DocumentoInvalido:
            fallidos.append(incidente["id"])
            continue
        hechos.append(cambio)
    return hechos, fallidos
