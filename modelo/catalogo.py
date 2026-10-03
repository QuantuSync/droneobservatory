"""Ficha del extractor para el barrido del catálogo vivo: cifras de prestaciones que el código no
resuelve en un texto (un análisis, una nota de una autoridad, una noticia técnica).

Solo se le pasa la frase o las frases que nombran un modelo y llevan un número con unidad, con
la lista de modelos que nombran. Devuelve por esquema, para cada cifra, el modelo, el campo del
catálogo, el valor o el intervalo con su unidad tal como lo escribe el texto y la frase copiada
literalmente. El código valida cada cifra (recogida/catalogo_vivo.py): la frase tiene que estar en
el texto, el número en la frase, el modelo en la frase, el campo y la unidad en las listas.
"""

import json
from typing import Any

VERSION = "catalogo/1"
MAX_TOKENS_SALIDA = 600
TEMPERATURA = 0.0
CAMPOS = (
    "velocidad_maxima", "velocidad_crucero", "alcance", "autonomia", "techo", "altura_tipica",
    "mtow", "carga_util", "envergadura", "longitud", "viento_maximo", "enlace_alcance",
)  # fmt: skip
UNIDADES = ("m", "km", "kg", "g", "km/h", "m/s", "kn", "mph", "min", "h", "ft", "mi", "lb")

ESQUEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["cifras"],
    "properties": {
        "cifras": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["modelo", "campo", "unidad", "frase"],
                "properties": {
                    "modelo": {"type": "string"},
                    "campo": {"enum": list(CAMPOS)},
                    "valor": {"type": "number"},
                    "min": {"type": "number"},
                    "max": {"type": "number"},
                    "unidad": {"enum": list(UNIDADES)},
                    "frase": {"type": "string"},
                },
            },
        }
    },
}

INSTRUCCIONES = """Eres el extractor del catálogo de prestaciones de drones del European \
Observatory of Drone Incidents. Recibes frases de una fuente y los modelos de dron que nombran. \
Devuelve solo las cifras de prestaciones de esos modelos que las frases dan expresamente, sin \
añadir nada que no digan ni calcular nada.

Para cada cifra:
- modelo: el nombre del modelo tal como lo escribe la frase.
- campo: velocidad_maxima, velocidad_crucero, alcance (distancia que recorre), autonomia (tiempo \
de vuelo), techo, altura_tipica (altura a la que vuela), mtow (peso al despegue), carga_util \
(carga u ojiva), envergadura, longitud, viento_maximo o enlace_alcance (alcance del enlace).
- valor (o min y max si da un intervalo) y unidad, tal como los escribe la frase.
- frase: la frase que lo dice, copiada literalmente, de 40 palabras como máximo.

No incluyas cifras de otro aparato, de un misil, de un avión tripulado, de un ataque (número de \
drones, distancias recorridas en un ataque concreto) ni estimaciones de quien escribe si no las \
atribuye. Si no hay ninguna, devuelve una lista vacía."""


def contenido(frases: list[str], modelos: list[str]) -> str:
    return "Modelos nombrados: " + ", ".join(modelos) + "\nFrases:\n" + "\n".join(frases)


def cuerpo(frases: list[str], modelos: list[str]) -> dict[str, Any]:
    """Cuerpo de la petición sin el modelo, que añade el cliente."""
    return {
        "max_tokens": MAX_TOKENS_SALIDA,
        "temperature": TEMPERATURA,
        "system": [{"type": "text", "text": INSTRUCCIONES, "cache_control": {"type": "ephemeral"}}],
        "output_config": {"format": {"type": "json_schema", "schema": ESQUEMA}},
        "messages": [{"role": "user", "content": contenido(frases, modelos)}],
    }


class RespuestaInvalida(ValueError):
    pass


def leer_respuesta(respuesta: dict[str, Any]) -> list[dict[str, Any]]:
    if respuesta.get("stop_reason") not in {"end_turn", "stop_sequence"}:
        raise RespuestaInvalida(f"parada: {respuesta.get('stop_reason')}")
    textos = [b.get("text", "") for b in respuesta.get("content", []) if b.get("type") == "text"]
    try:
        bruta = json.loads("".join(textos))
    except ValueError as error:
        raise RespuestaInvalida("la salida no es JSON") from error
    if not isinstance(bruta, dict) or not isinstance(bruta.get("cifras"), list):
        raise RespuestaInvalida("la salida no sigue el esquema")
    return [x for x in bruta["cifras"] if isinstance(x, dict)]
