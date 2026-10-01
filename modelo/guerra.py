"""Ficha del extractor para los mensajes de la capa de guerra que el código no resuelve.

Solo se le pasan los mensajes que el analizador por código no puede cerrar
(`proceso/mensajes_guerra.py`): frases que mezclan drones con misiles, bombas o artillería, o
lugares que el nomenclátor no resuelve solo. Recibe el texto mínimo (las frases con lugar y
arma, sin saludos ni avisos), la fecha y la región del canal, y devuelve por esquema la lista
de lugares alcanzados, cada uno con el arma que lo alcanzó, la frase de origen copiada del
texto y la confianza. El código valida cada lugar (`proceso/extraccion_guerra.py`): la frase
tiene que estar en el texto, el arma tiene que ser un dron, la confianza llegar al umbral y el
lugar resolverse en el nomenclátor dentro de la región del mensaje.
"""

import json
from typing import Any

VERSION = "guerra/1"
MAX_TOKENS_SALIDA = 700
TEMPERATURA = 0.0
ARMAS = ("dron", "misil", "bomba", "artilleria", "desconocida")
NIVELES = ("localidad", "instalacion")
TIPOS = ("impacto", "restos")
CATEGORIAS = (
    "energia", "combustible", "residencial", "ferrocarril", "puerto", "industrial", "aerodromo",
)  # fmt: skip

ESQUEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["lugares"],
    "properties": {
        "lugares": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["nombre", "nivel", "arma", "tipo", "categorias", "frase", "confianza"],
                "properties": {
                    "nombre": {"type": "string"},
                    "localidad": {"type": "string"},
                    "nivel": {"enum": list(NIVELES)},
                    "arma": {"enum": list(ARMAS)},
                    "tipo": {"enum": list(TIPOS)},
                    "categorias": {"type": "array", "items": {"enum": list(CATEGORIAS)}},
                    "frase": {"type": "string"},
                    "confianza": {"type": "number"},
                },
            },
        }
    },
}

INSTRUCCIONES = """Eres el extractor del European Observatory of Drone Incidents para la capa de \
guerra. Recibes un mensaje oficial (administración militar regional ucraniana, Estado Mayor \
ucraniano o gobernador ruso) sobre un ataque, con su fecha y su región. Devuelve los lugares \
concretos que el mensaje dice que fueron alcanzados, sin añadir nada que no diga.

Para cada lugar:
- nombre: la localidad o la instalación en nominativo, en el idioma del mensaje («Харків», \
«Шебекино», «НПЗ Новокуйбишевський»). Nunca una región, un distrito ni un país.
- localidad: si el lugar es una instalación, la localidad donde está, si el mensaje la dice.
- nivel: localidad o instalacion.
- arma: lo que alcanzó ese lugar según el mensaje: dron (БпЛА, дрон, шахед, беспилотник, FPV), \
misil, bomba (КАБ, авиабомба), artilleria, o desconocida si el mensaje no lo dice para ese lugar.
- tipo: impacto si lo alcanzó; restos si cayeron restos de un dron derribado.
- categorias: los tipos de objetivo dañados en ese lugar que dice el mensaje (energia, \
combustible, residencial, ferrocarril, puerto, industrial, aerodromo); vacía si no lo dice.
- frase: la frase del mensaje que lo dice, copiada literalmente, de 25 palabras como máximo.
- confianza: de 0 a 1, cuánto apoya la frase que ese lugar fue alcanzado por esa arma. 0.9 o \
más solo si lo dice expresamente.

No incluyas lugares donde solo se derribaron drones sin daños, lugares de donde se lanzaron, \
alarmas, ni lugares de otros días que el mensaje recuerde. Si no hay ningún lugar alcanzado, \
devuelve una lista vacía."""


def contenido(texto: str, fecha: str, region: str | None) -> str:
    return f"Fecha: {fecha}. Región del canal: {region or 'todo el país'}.\nMensaje: {texto}"


def cuerpo(texto: str, fecha: str, region: str | None) -> dict[str, Any]:
    """Cuerpo de la petición sin el modelo, que añade el cliente."""
    return {
        "max_tokens": MAX_TOKENS_SALIDA,
        "temperature": TEMPERATURA,
        "system": [{"type": "text", "text": INSTRUCCIONES, "cache_control": {"type": "ephemeral"}}],
        "output_config": {"format": {"type": "json_schema", "schema": ESQUEMA}},
        "messages": [{"role": "user", "content": contenido(texto, fecha, region)}],
    }


class RespuestaInvalida(ValueError):
    pass


def leer_respuesta(respuesta: dict[str, Any]) -> list[dict[str, Any]]:
    """Los lugares de la respuesta. Lanza RespuestaInvalida si no trae la lista."""
    if respuesta.get("stop_reason") not in {"end_turn", "stop_sequence"}:
        raise RespuestaInvalida(f"parada: {respuesta.get('stop_reason')}")
    textos = [b.get("text", "") for b in respuesta.get("content", []) if b.get("type") == "text"]
    try:
        bruta = json.loads("".join(textos))
    except ValueError as error:
        raise RespuestaInvalida("la salida no es JSON") from error
    if not isinstance(bruta, dict) or not isinstance(bruta.get("lugares"), list):
        raise RespuestaInvalida("la salida no sigue el esquema")
    return [x for x in bruta["lugares"] if isinstance(x, dict)]
