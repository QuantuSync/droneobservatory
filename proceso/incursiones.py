"""Incursiones en países europeos a partir de los cruces que declaran los partes ucranianos.

Cuando un parte de la Fuerza Aérea dice que drones del ataque cruzaron a otro
país («перетнули кордон з Румунією»), se da de alta un incidente de tipo
incursión en ese país. El origen queda demostrado por rastreo: la Fuerza Aérea
sigue la ruta del dron por radar hasta la frontera, y por eso presencia_dron
es confirmada. El estado es notificado: solo pasa a confirmado con la
confirmación del país afectado (confirmaciones oficiales).

Los partes no dicen dónde cruzan: el incidente solo se sabe a nivel de país y
no lleva punto, así que se publica sin mapa. Antes se situaba en una zona
fronteriza de referencia de cada país, que era un punto inventado.
"""

import json
from datetime import datetime
from functools import cache
from pathlib import Path
from typing import Any

from almacen.base import Almacen, DocumentoInvalido
from esquema import Documento
from proceso.estados import nuevo_estado

DIRECTORIO = Path(__file__).resolve().parent.parent / "configuracion"
VERSION = "incursion/2"
# Versiones anteriores de estos incidentes, que se rehacen con la actual.
VERSIONES_ANTERIORES = frozenset({"incursion/1"})
NOMBRES_ES = {
    "MD": "Moldavia",
    "RO": "Rumanía",
    "PL": "Polonia",
    "HU": "Hungría",
    "SK": "Eslovaquia",
}
NOMBRES_EN = {"MD": "Moldova", "RO": "Romania", "PL": "Poland", "HU": "Hungary", "SK": "Slovakia"}


@cache
def paises(ruta: Path = DIRECTORIO / "fronteras_ucrania.json") -> frozenset[str]:
    """Los países vecinos de Ucrania a los que los partes dicen que cruzan drones."""
    datos: dict[str, Any] = json.loads(ruta.read_text(encoding="utf-8"))
    return frozenset(datos["paises"])


def _instante(valor: str, precision: str) -> Documento:
    return {"valor": valor, "precision": precision}


def incidente(id_: str, ataque: Documento, cruce: Documento, ahora: datetime) -> Documento:
    pais = cruce["pais"]
    fuente = dict(ataque["fuentes"][-1])
    fuente.update(
        {
            "credibilidad": fuente.get("credibilidad", 2),
            "campos_respaldados": ["tipo", "drones.numero", "lugar.pais"],
            "interna_fuera_de_ucrania": False,
            "publica": True,
        }
    )
    periodo = ataque["periodo"]
    marca = _instante(ahora.strftime("%Y-%m-%dT%H:%MZ"), "minuto")
    return {
        "id": id_,
        "tipo": "incursion",
        "origen_demostrado_por": ["rastreo"],
        "estado": nuevo_estado(fuente["fecha"], fuente["id"]),
        "titulo": {
            "es": f"Drones del ataque ruso contra Ucrania cruzan a {NOMBRES_ES[pais]}",
            "en": f"Drones from the Russian attack on Ukraine cross into {NOMBRES_EN[pais]}",
        },
        "presencia_dron": "confirmada",
        "tiempo": {
            "inicio": periodo["inicio"],
            "fin": periodo["fin"],
            "origen_inicio": {
                "tipo": "parte",
                "fuente_id": fuente["id"],
                "motivo": "periodo del ataque en el parte de la Fuerza Aérea",
            },
        },
        "lugar": {"pais": pais, "nivel": "pais"},
        "drones": {"numero": cruce["numero"]},
        # La Fuerza Aérea sigue por radar a drones del ataque ruso hasta la frontera.
        "pruebas": {"dron_estatal": True, "entrada_exterior": True, "evidencia": ["rastreo"]},
        "fuentes": [fuente],
        "control": {
            "alta": marca,
            "ultima_actualizacion": marca,
            "version_extractor": VERSION,
        },
    }


def registrar(almacen: Almacen, ahora: datetime, modelos: frozenset[str]) -> int:
    """Da de alta las incursiones que aún no existen y rehace, con el mismo identificador,
    las de una versión anterior. Devuelve cuántas crea o rehace."""
    vecinos = paises()
    existentes = {
        (i["fuentes"][0]["id"], i["lugar"]["pais"]): i
        for i in almacen.incidentes()
        if i["tipo"] == "incursion"
        and i["control"].get("version_extractor") in VERSIONES_ANTERIORES | {VERSION}
    }
    hechas = 0
    for ataque in almacen.ataques_ucrania():
        if ataque["sentido"] != "RU_UA":
            continue
        for cruce in ataque.get("cruces", []):
            clave = (ataque["fuentes"][-1]["id"], cruce["pais"])
            anterior = existentes.get(clave)
            if cruce["pais"] not in vecinos or (
                anterior is not None and anterior["control"]["version_extractor"] == VERSION
            ):
                continue
            anio = int(ataque["periodo"]["fin"]["valor"][:4])
            id_ = anterior["id"] if anterior else almacen.siguiente_id_incidente(anio)
            documento = incidente(id_, ataque, cruce, ahora)
            if anterior is not None:
                # Se conservan el alta, la fusión, el episodio y lo que sumaron las
                # confirmaciones oficiales.
                documento["control"]["alta"] = anterior["control"]["alta"]
                for campo in ("fusionado_en", "estado", "fuentes"):
                    if campo in anterior:
                        documento[campo] = anterior[campo]
            try:
                almacen.guardar_incidente(documento, ahora, modelos)
            except DocumentoInvalido:
                continue
            existentes[clave] = documento
            hechas += 1
    return hechas
