"""Petición de una rectificación oficial de la presencia del dron (recogida/rectificaciones.py).

Una ficha publicada y un texto que puede rectificarla (una fuente nueva, una declaración oficial
revisada, un titular de la búsqueda mensual): ¿una autoridad oficial cierra su investigación sin
pruebas del dron, retira su afirmación, dice que era otra cosa o corrige solo un episodio? La
respuesta la decide el experto y el código la comprueba (proceso/rectificaciones.decision_valida):
la frase tiene que estar, literal, en el texto mandado.

La búsqueda mensual manda al modelo base varios titulares de una ficha a la vez
(`cuerpo_mensual`): solo dice cuáles merecen la pregunta, que luego decide el experto.
"""

from typing import Any

from modelo.control import TEMPERATURA

VERSION = "rectificacion/1"
ESFUERZO = "medium"
MAX_SALIDA = 700
MAX_SALIDA_MENSUAL = 300
MAX_LETRAS_TEXTO = 2500
MAX_TITULARES = 12

INSTRUCCIONES = """Eres el revisor de un observatorio de incidentes con drones en Europa. El \
observatorio registra lo que se notifica y lo que declaran las autoridades, cuando lo declaran, \
con su fuente y su fecha. «Confirmado» significa que una autoridad oficial declaró que ocurrió, \
no que exista una prueba física pública.

Te damos una ficha ya publicada (un incidente con su presencia de dron) y un texto. Di si el \
texto cuenta una RECTIFICACIÓN OFICIAL de la presencia del dron en ESE incidente:

- "no_acreditada": una autoridad oficial (policía, fiscalía, fuerzas armadas, ministerio, \
gobierno, autoridad de aviación civil, gestor del aeropuerto o de la navegación aérea, \
organismo oficial de investigación) cierra su investigación sin pruebas del dron, dice que no \
puede confirmar (ni descartar) que hubiera drones, o retira su afirmación anterior sin decir \
que fuera otra cosa. No encontrar pruebas no es demostrar que no hubo dron: eso es siempre \
"no_acreditada", nunca "descartada".
- "descartada": la autoridad oficial dice que era otra cosa (un avión, un helicóptero, un \
globo, una estrella...).
- "parcial": la autoridad rectifica un episodio o una prueba concreta (un vídeo, una hora, un \
disparo) y mantiene que hubo drones en el incidente.
- "ninguna": no es una autoridad oficial (periodistas, analistas, la comunidad OSINT, \
testigos), la autoridad mantiene el dron, solo lo deja abierto el mismo día sin haberlo \
afirmado antes, o el texto habla de otro suceso (otra fecha, otro lugar).

Reglas:
- mismo_suceso: el texto habla del mismo suceso que la ficha (misma fecha o noche y mismo lugar).
- autoridad_oficial: quien rectifica es una autoridad oficial (aunque lo cuente un medio que la \
cita).
- frase: copia LITERAL, sin cambiar ni una letra, la frase del texto donde la autoridad \
rectifica (o, con "ninguna", deja vacío).
- fecha: el día en que la autoridad lo declara (AAAA-MM-DD), si se sabe; si no, vacío.
- quien_es / quien_en: la autoridad, en español y en inglés («la policía de Copenhague» / \
«Copenhagen Police»).
- motivo_es / motivo_en: qué dijo, en una frase corta, en español y en inglés («tras la \
investigación: no puede confirmar ni descartar que hubiera drones»).
- confianza: de 0 a 1.
Nunca cambias el incidente ni su efecto: si un aeropuerto cerró, cerró. Solo juzgas la \
presencia del dron."""

ESQUEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "tipo", "mismo_suceso", "autoridad_oficial", "frase", "fecha", "quien_es", "quien_en",
        "motivo_es", "motivo_en", "confianza",
    ],
    "properties": {
        "tipo": {"enum": ["no_acreditada", "descartada", "parcial", "ninguna"]},
        "mismo_suceso": {"type": "boolean"},
        "autoridad_oficial": {"type": "boolean"},
        "frase": {"type": "string"},
        "fecha": {"type": "string"},
        "quien_es": {"type": "string"},
        "quien_en": {"type": "string"},
        "motivo_es": {"type": "string"},
        "motivo_en": {"type": "string"},
        "confianza": {"type": "number"},
    },
}  # fmt: skip

INSTRUCCIONES_MENSUAL = """Eres el revisor de un observatorio de incidentes con drones en \
Europa. Te damos una ficha publicada con la presencia del dron confirmada por una autoridad y \
titulares de noticias posteriores. Di qué titulares pueden contar que una autoridad oficial \
(policía, fiscalía, fuerzas armadas, ministerio, gobierno, aviación civil, aeropuerto, \
organismo de investigación) rectifica la presencia del dron en ESE incidente: cierra la \
investigación sin pruebas del dron, no puede confirmarlo, retira lo que dijo o dice que era \
otra cosa. Lo que dicen periodistas, analistas u OSINT no cuenta. Devuelve los números de esos \
titulares (vacío si ninguno)."""

ESQUEMA_MENSUAL = {
    "type": "object",
    "additionalProperties": False,
    "required": ["titulares"],
    "properties": {"titulares": {"type": "array", "items": {"type": "integer"}}},
}


def _cuerpo(instrucciones: str, esquema: dict[str, Any], contenido: str, max_tokens: int
            ) -> dict[str, Any]:  # fmt: skip
    return {
        "max_tokens": max_tokens,
        "temperature": TEMPERATURA,
        "system": [{"type": "text", "text": instrucciones, "cache_control": {"type": "ephemeral"}}],
        "output_config": {
            "format": {"type": "json_schema", "schema": esquema},
            "effort": ESFUERZO,
        },
        "messages": [{"role": "user", "content": contenido}],
    }


def resumen(ficha: dict[str, Any]) -> str:
    return "\n".join(f"- {clave}: {valor}" for clave, valor in ficha.items())


def cuerpo(ficha: dict[str, Any], medio: str, fecha: str, idioma: str, texto: str
           ) -> dict[str, Any]:  # fmt: skip
    contenido = (
        f"Ficha:\n{resumen(ficha)}\n\nTexto ({medio}, {fecha}, {idioma or '?'}):\n"
        f"{texto[:MAX_LETRAS_TEXTO]}"
    )
    return _cuerpo(INSTRUCCIONES, ESQUEMA, contenido, MAX_SALIDA)


def cuerpo_mensual(ficha: dict[str, Any], titulares: list[tuple[str, str, str]]
                   ) -> dict[str, Any]:  # fmt: skip
    """`titulares`: (medio, fecha, titular) en orden; la respuesta los numera desde 1."""
    lineas = [
        f"{n}. ({medio}, {fecha}) {titular}"
        for n, (medio, fecha, titular) in enumerate(titulares[:MAX_TITULARES], 1)
    ]
    contenido = f"Ficha:\n{resumen(ficha)}\n\nTitulares:\n" + "\n".join(lineas)
    return _cuerpo(INSTRUCCIONES_MENSUAL, ESQUEMA_MENSUAL, contenido, MAX_SALIDA_MENSUAL)
