"""Quién dice qué: el valor de cada campo público según cada fuente pública del incidente.

Cada incidente guarda, en sus afirmaciones internas, el valor que dio el extractor para
cada campo de la ficha con la fuente de la que sale. Al publicar, cada afirmación se
traduce al campo público que corresponde (`drones` es `drones.numero`, `inicio` es
`tiempo.inicio`…), con el valor en el mismo formato que ese campo, y se acompaña del
medio, el código del Almirantazgo (fiabilidad y credibilidad) y la fecha de la fuente.

La presencia de dron lleva además la cita de la fuente que justifica el valor (la frase
literal de la autoridad o de la noticia, de 25 palabras como máximo).

Solo salen las fuentes que ya salen en el incidente (`solo_fuentes_publicas`: nunca de
fiabilidad E ni F, ni internas fuera de la capa de Ucrania, como el Ministerio de Defensa
ruso) y solo los campos de la lista cerrada.
"""

import json
from typing import Any

from esquema import Documento

# Campo de la ficha a campo público.
CAMPO_PUBLICO = {
    "tipo": "tipo",
    "presencia_dron": "presencia_dron",
    "inicio": "tiempo.inicio",
    "fin": "tiempo.fin",
    "pais": "lugar.pais",
    "localidad": "lugar.localidad",
    "objetivo_categoria": "objetivo.categoria",
    "objetivo_nombre": "objetivo.nombre",
    "drones": "drones.numero",
    "modelo_dron": "drones.modelo",
    "cierre": "consecuencias.cierre.valor",
    "cierre_minutos": "consecuencias.cierre.minutos",
    "vuelos_desviados": "consecuencias.vuelos_desviados",
    "vuelos_cancelados": "consecuencias.vuelos_cancelados",
    "vuelos_retrasados": "consecuencias.vuelos_retrasados",
    "medidas": "respuesta.medidas",
}
INSTANTES = frozenset({"inicio", "fin"})
# Campos cuya afirmación pública lleva la cita literal de su fuente.
CON_CITA = frozenset({"presencia_dron"})
# Las fechas de la ficha van sin zona («2025-09-22T18:30» o «2025-09-22»), en UTC.
HORA_DEL_DIA = "T00:00"


def _instante(texto: str) -> Documento:
    """La fecha de la ficha como instante público, con la precisión que da su formato."""
    if "T" in texto:
        return {"valor": f"{texto}Z", "precision": "minuto"}
    return {"valor": f"{texto}{HORA_DEL_DIA}Z", "precision": "dia"}


def _valor(campo: str, valor: Any) -> Any:
    if campo in INSTANTES and isinstance(valor, str):
        return _instante(valor)
    if isinstance(valor, dict) and set(valor) == {"min", "max"}:
        return {"min": valor["min"], "max": valor["max"]}
    return valor


def afirmaciones_publicas(documento: Documento) -> list[Documento]:
    """Las afirmaciones del incidente cuyas fuentes son públicas, sin repetir.

    `documento` ya trae solo las fuentes públicas; sus afirmaciones internas, todas."""
    fuentes = {f["id"]: f for f in documento["fuentes"]}
    resultado: list[Documento] = []
    vistas: set[str] = set()
    for afirmacion in documento.get("afirmaciones", []):
        publico = CAMPO_PUBLICO.get(afirmacion["campo"])
        fuente = fuentes.get(afirmacion["fuente_id"])
        if publico is None or fuente is None:
            continue
        entrada = {
            "campo": publico,
            "fuente_id": fuente["id"],
            "medio": fuente["medio"],
            "fiabilidad": fuente["fiabilidad"],
            "credibilidad": fuente["credibilidad"],
            "fecha": fuente["fecha"],
            "valor": _valor(afirmacion["campo"], afirmacion["valor"]),
        }
        if afirmacion["campo"] in CON_CITA and fuente.get("frase_origen"):
            entrada["cita"] = fuente["frase_origen"]
        clave = json.dumps(entrada, sort_keys=True, ensure_ascii=False)
        if clave not in vistas:
            vistas.add(clave)
            resultado.append(entrada)
    return sorted(resultado, key=lambda a: (a["campo"], a["fecha"]["valor"], a["fuente_id"]))
