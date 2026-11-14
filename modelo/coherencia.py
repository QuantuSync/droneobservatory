"""La relectura de coherencia: el modelo grande lee las fuentes de una ficha cuyas frases no
sostienen algo que la ficha dice (proceso/correccion.py) y devuelve, con la frase literal de una
fuente, lo que sí sostienen: el lugar, el número de drones, el día y, si cuentan dos días, qué
fuentes son de cada uno. Lo usa recogida/correccion.py, desde el 14 de noviembre de 2026."""

from typing import Any

from modelo import control
from modelo.control import FuenteControl

VERSION = "coherencia/1"
MAX_SALIDA = 1500
ESFUERZO = "medium"

INSTRUCCIONES = """Eres el revisor de un observatorio público de incidentes con drones en Europa.
Recibes una ficha (un suceso: un país y una jornada) y el texto de sus fuentes. Algo de la ficha no
lo sostiene ninguna frase guardada. Lee las fuentes y di qué sostienen DE ESTE SUCESO, siempre con
una frase copiada literalmente de una fuente (sin cambiar ni una letra) y el número de esa fuente.

- lugar: si alguna frase sitúa este suceso en el lugar de la ficha (o en uno dentro de él), da
  "sostenido": true y esa frase. Si no, "sostenido": false y el nivel que sí sostienen las
  fuentes: "region" (con el nombre de la región y la frase que la nombra) o "pais".
- drones: el número de drones de este suceso, solo si una frase lo dice con la palabra dron
  («dos drones», «3 Drohnen», «a drone»); un rango «min-max» o un número. Si ninguna lo dice,
  "valor": "".
- dia: el día local del suceso (AAAA-MM-DD) si una frase lo da (una fecha o un día de la semana
  que se pueda fechar con la de la fuente). Si no, "".
- dias: solo si las fuentes cuentan este suceso en dos o más días distintos (dos noches, dos
  sucesos), cada día con los números de sus fuentes. Si es una sola jornada, lista vacía.

No inventes: lo que no esté en una frase no cuenta. Responde solo con el JSON pedido."""

_FRASE = {"type": "string"}
_NUMERO = {"type": "integer"}
ESQUEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["lugar", "drones", "dia", "dias"],
    "properties": {
        "lugar": {
            "type": "object",
            "additionalProperties": False,
            "required": ["sostenido", "nivel", "region", "frase", "fuente"],
            "properties": {
                "sostenido": {"type": "boolean"},
                "nivel": {"type": "string", "enum": ["igual", "region", "pais"]},
                "region": {"type": "string"},
                "frase": _FRASE,
                "fuente": _NUMERO,
            },
        },
        "drones": {
            "type": "object",
            "additionalProperties": False,
            "required": ["valor", "frase", "fuente"],
            "properties": {"valor": {"type": "string"}, "frase": _FRASE, "fuente": _NUMERO},
        },
        "dia": {
            "type": "object",
            "additionalProperties": False,
            "required": ["valor", "frase", "fuente"],
            "properties": {"valor": {"type": "string"}, "frase": _FRASE, "fuente": _NUMERO},
        },
        "dias": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["dia", "fuentes", "frase", "fuente"],
                "properties": {
                    "dia": {"type": "string"},
                    "fuentes": {"type": "array", "items": _NUMERO},
                    "frase": _FRASE,
                    "fuente": _NUMERO,
                },
            },
        },
    },
}


def cuerpo(
    ficha: dict[str, Any], hallazgos: list[str], fuentes: list[FuenteControl]
) -> dict[str, Any]:
    """La petición: la ficha (como la ve el control), lo que no sostienen sus frases y las
    fuentes numeradas desde 1."""
    partes = ["Ficha:", control.resumen_ficha(ficha), "Lo que no sostiene ninguna frase guardada:"]
    partes += [f"- {h}" for h in hallazgos]
    partes += ["Fuentes:"]
    partes += [f.bloque(i) for i, f in enumerate(fuentes[: control.MAX_FUENTES], 1)]
    return control._cuerpo(INSTRUCCIONES, ESQUEMA, "\n".join(partes), MAX_SALIDA, ESFUERZO)
