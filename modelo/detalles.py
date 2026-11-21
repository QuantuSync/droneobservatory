"""Paso 2 del extractor: los detalles del suceso que la nota da más abajo de su principio.

El paso 1 (modelo/ficha.py) lee el principio de cada noticia (modelo/paginas.MAX_LETRAS) y decide
si es un incidente, qué pasó, dónde, en qué país y en qué día. El paso 2 lee la nota seguida hasta
3.000 letras (modelo/paginas.nota) y saca solo detalles de ESE suceso, cada uno con su frase
literal: el cierre y su duración, los vuelos afectados, la hora, el número de drones y lo que dicen
las autoridades. No puede cambiar el lugar, el país ni el día, ni crear sucesos: su esquema no
tiene esos campos y lo que devuelve se fusiona con reglas fijas (proceso/detalles.py).

Por qué en dos pasos (21 de noviembre de 2026): con 600 letras se perdían cierres, vuelos, horas y
declaraciones (358 de 399 fichas con alguna fuente cortada); leer la nota entera de una vez (PR
#470) los recuperaba pero colaba lugares demasiado precisos (Kotka, Druskininkai, Panevėžys),
datos de otras noticias de la misma página (b92.net) y una ficha suelta de misiles en Moldavia.
"""

from typing import Any

from modelo import ficha

VERSION = "detalles/1"
# Unos pocos datos con su frase: 1.200 tokens sobran (solo se paga lo que se escribe).
MAX_TOKENS_SALIDA = 1200
ESFUERZO = "low"

CAMPOS = (
    "cierre", "cierre_minutos", "vuelos_desviados", "vuelos_cancelados", "vuelos_retrasados",
    "inicio", "inicio_precision", "fin", "drones",
)  # fmt: skip

ESQUEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["detalles", "declaraciones"],
    "properties": {
        "detalles": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["campo", "valor", "fuente", "frase", "confianza"],
                "properties": {
                    "campo": {"enum": list(CAMPOS)},
                    "valor": {"type": "string"},
                    "fuente": {"type": "integer"},
                    "frase": {"type": "string"},
                    "confianza": {"type": "number"},
                },
            },
        },
        # Las mismas declaraciones que en la ficha del paso 1.
        "declaraciones": ficha.ESQUEMA["properties"]["declaraciones"],
    },
}

INSTRUCCIONES = """Eres el paso 2 del extractor del Observatorio Europeo de Incidentes con \
Drones. Otro paso ya ha leído el principio de las noticias y ha decidido el suceso: qué pasó, \
dónde, en qué país y en qué día. Tú recibes ese suceso y el texto de cada nota seguido desde su \
principio. Busca en todo el texto solo detalles de ESE suceso que dice la nota, cada uno con la \
frase copiada literalmente del texto (sin traducir ni cambiar nada, 25 palabras como máximo) y el \
número de la fuente. No cambias el suceso: ni su lugar, ni su país, ni su día.

Una nota larga cuenta a menudo otros sucesos: antecedentes («el mes pasado», «el 18 de \
octubre»), lo que pasó otra noche o en otro país, o los titulares de otras noticias que el medio \
añade. De esos no sacas nada. Si no está claro que una frase hable del suceso dado, no la uses. \
Si no hay ningún detalle, devuelve las listas vacías.

Detalles (campo: valor):
- cierre: «si» si la nota dice que por este suceso se cerró o se paró un aeropuerto, una pista o \
el espacio aéreo, o que se suspendieron o desviaron vuelos; «no» si dice que siguió abierto. Un \
cierre que la nota atribuye a otra causa (globos, niebla, otro suceso) no es de este suceso.
- cierre_minutos: cuánto duró ese cierre, en minutos, como «N» o «mínimo-máximo».
- vuelos_desviados, vuelos_cancelados, vuelos_retrasados: cuántos vuelos, «N» o «mínimo-máximo».
- inicio: la hora en que empezó el suceso, en UTC, como AAAA-MM-DDTHH:MM, solo si la nota la da \
y es del día del suceso. Convierte la hora local del país a UTC. inicio_precision: «minuto» si \
da la hora exacta, «hora» si da una hora aproximada o una franja corta.
- fin: cuándo acabó (el fin de la alerta o del cierre), con el mismo formato.
- drones: cuántos drones de este suceso en el país del suceso, como «N» o «mínimo-máximo», solo \
si la nota da un número o una cantidad escrita («dos drones»: «2»; «varios»: «2-10»). Los que se \
detectaron en otro país y no entraron no cuentan.
- confianza: de 0 a 1, lo seguro que estás de que el detalle es de este suceso.

Declaraciones: lo que dice una autoridad (policía, ejército, ministerio, gobierno, aeropuerto, \
control aéreo, fiscalía, aviación civil) sobre este suceso, con su frase literal, con los mismos \
campos que en la ficha: autoridad (su nombre como lo da la nota), pais (código ISO de la \
autoridad), categoria, afirma (incidente: que hubo el suceso; drones: que eran drones; \
sin_drones: que no lo eran; niega_incidente: que no pasó; autoria: quién lo hizo), autor, \
autor_tipo, autor_pais y autor_situacion (solo con afirma autoria; si no, vacíos), cita_literal \
(true si la frase es lo que dijo, entre comillas o en estilo directo), fuente y frase."""


def contenido(suceso: str, fuentes: list[ficha.FuenteTexto]) -> str:
    lineas = [f"Suceso (no se cambia): {suceso}"]
    for numero, fuente in enumerate(fuentes, 1):
        texto = fuente.nota or fuente.texto
        cuerpo = f" Texto: {texto}" if texto else ""
        lineas.append(
            f"Fuente {numero} ({fuente.medio}, {fuente.fecha}, {fuente.idioma or '?'}). "
            f"Titular: {fuente.titular}.{cuerpo}"
        )
    return "\n".join(lineas)


def cuerpo(suceso: str, fuentes: list[ficha.FuenteTexto]) -> dict[str, Any]:
    """Cuerpo de la petición del paso 2, sin el modelo (lo pone el cliente: el modelo base)."""
    return {
        "max_tokens": MAX_TOKENS_SALIDA,
        "temperature": ficha.TEMPERATURA,
        "system": [{"type": "text", "text": INSTRUCCIONES, "cache_control": {"type": "ephemeral"}}],
        "output_config": {
            "format": {"type": "json_schema", "schema": ESQUEMA},
            "effort": ESFUERZO,
        },
        "messages": [{"role": "user", "content": contenido(suceso, fuentes)}],
    }


def letras(suceso: str, fuentes: list[ficha.FuenteTexto]) -> int:
    return len(INSTRUCCIONES) + len(contenido(suceso, fuentes)) + len(str(ESQUEMA))
