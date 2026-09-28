"""Incursiones en países europeos a partir de los cruces que declaran los partes ucranianos.

Cuando un parte de la Fuerza Aérea dice que drones del ataque cruzaron a otro
país («перетнули кордон з Румунією»), se da de alta un incidente de tipo
incursión en ese país. El origen queda demostrado por rastreo: la Fuerza Aérea
sigue la ruta del dron por radar hasta la frontera, y por eso presencia_dron
es confirmada. El estado es notificado: solo pasa a confirmado con la
confirmación del país afectado (confirmaciones oficiales).

Los partes no dicen dónde cruzan: el incidente se sitúa en la zona fronteriza
de referencia del país (`configuracion/fronteras_ucrania.json`), con el radio
máximo del esquema.
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
VERSION = "incursion/1"
NOMBRES_ES = {
    "MD": "Moldavia",
    "RO": "Rumanía",
    "PL": "Polonia",
    "HU": "Hungría",
    "SK": "Eslovaquia",
}
NOMBRES_EN = {"MD": "Moldova", "RO": "Romania", "PL": "Poland", "HU": "Hungary", "SK": "Slovakia"}


@cache
def fronteras(ruta: Path = DIRECTORIO / "fronteras_ucrania.json") -> dict[str, Any]:
    datos: dict[str, Any] = json.loads(ruta.read_text(encoding="utf-8"))
    return datos


def _instante(valor: str, precision: str) -> Documento:
    return {"valor": valor, "precision": precision}


def incidente(id_: str, ataque: Documento, cruce: Documento, ahora: datetime) -> Documento:
    datos = fronteras()
    pais = cruce["pais"]
    zona = datos["paises"][pais]
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
        "tiempo": {"inicio": periodo["inicio"], "fin": periodo["fin"]},
        "lugar": {
            "punto": {"lat": zona["lat"], "lon": zona["lon"]},
            "radio_km": datos["radio_km"],
            "pais": pais,
            "localidad": zona["nombre"],
        },
        "drones": {"numero": cruce["numero"]},
        "fuentes": [fuente],
        "control": {
            "alta": marca,
            "ultima_actualizacion": marca,
            "version_extractor": VERSION,
        },
    }


def registrar(almacen: Almacen, ahora: datetime, modelos: frozenset[str]) -> int:
    """Da de alta las incursiones que aún no existen. Devuelve cuántas crea."""
    paises = fronteras()["paises"]
    existentes = {
        (i["fuentes"][0]["id"], i["lugar"]["pais"])
        for i in almacen.incidentes()
        if i["tipo"] == "incursion" and i["control"].get("version_extractor") == VERSION
    }
    creadas = 0
    for ataque in almacen.ataques_ucrania():
        if ataque["sentido"] != "RU_UA":
            continue
        for cruce in ataque.get("cruces", []):
            clave = (ataque["fuentes"][-1]["id"], cruce["pais"])
            if cruce["pais"] not in paises or clave in existentes:
                continue
            anio = int(ataque["periodo"]["fin"]["valor"][:4])
            documento = incidente(almacen.siguiente_id_incidente(anio), ataque, cruce, ahora)
            try:
                almacen.guardar_incidente(documento, ahora, modelos)
            except DocumentoInvalido:
                continue
            existentes.add(clave)
            creadas += 1
    return creadas
