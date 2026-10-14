"""Llamadas del control de calidad de las fichas (recogida/control_fichas.py).

Tres peticiones, cada una con su esquema de salida, temperatura 0 y las instrucciones en la
caché del servicio:

- comparar: dos fichas del mismo país y de fechas cercanas, con lo que dicen sus fuentes (en el
  idioma de cada una): ¿son el mismo suceso, dos sucesos distintos o no se puede saber?
- verificar: una ficha y sus fuentes (titular y primeras frases, como las lee el extractor):
  qué dice cada fuente de la presencia del dron, del número de drones, del cierre y su duración,
  de la fecha y del lugar, con la frase literal que lo respalda;
- traducir: citas de las fuentes, cada una al español y al inglés.

El código nunca se fía de la respuesta sin comprobarla: cada frase tiene que estar, literal, en
el texto de su fuente; lo que no se comprueba no cambia nada.
"""

import json
from dataclasses import dataclass
from typing import Any

VERSION = "control/4"
TEMPERATURA = 0.0
# Esfuerzo de los modelos nuevos (el de antes no lo admite): decidir si dos fichas son el mismo
# suceso es lo más difícil, verificar cada dato pide atención y traducir es mecánico.
ESFUERZO_COMPARAR = "high"
ESFUERZO_VERIFICAR = "medium"
ESFUERZO_TRADUCIR = "low"
MAX_SALIDA_COMPARAR = 400
MAX_SALIDA_VERIFICAR = 1200
# Treinta citas en dos idiomas: con el modelo base (unos 30 % más de tokens por el mismo texto)
# 4000 se quedaban cortos.
MAX_SALIDA_TRADUCIR = 8000
# Letras de cada texto que se mandan: el titular entero y las primeras frases.
MAX_LETRAS_TEXTO = 700
MAX_FUENTES = 6
DECISIONES = ("mismo", "distinto", "dudoso")
PRESENCIAS = ("confirmada", "posible", "no_hallado", "desmentido", "sin_dato")
CIERRES = ("si", "no", "sin_dato")
NIVELES = ("instalacion", "localidad", "region", "pais", "sin_dato")

_FRASE = {"type": "string"}
_FUENTE = {"type": "integer"}

ESQUEMA_COMPARAR: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "mismo_dia",
        "mismo_sitio",
        "varios_sucesos",
        "decision",
        "motivo_es",
        "motivo_en",
    ],
    "properties": {
        "mismo_dia": {"type": "boolean"},
        "mismo_sitio": {"type": "boolean"},
        "varios_sucesos": {"type": "boolean"},
        "decision": {"enum": list(DECISIONES)},
        "motivo_es": {"type": "string"},
        "motivo_en": {"type": "string"},
    },
}


def _dato(valor: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["valor", "fuente", "frase"],
        "properties": {"valor": valor, "fuente": _FUENTE, "frase": _FRASE},
    }


ESQUEMA_VERIFICAR: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["presencia", "drones", "cierre", "duracion_min", "dia", "hora", "lugar"],
    "properties": {
        "presencia": _dato({"enum": list(PRESENCIAS)}),
        "drones": _dato({"type": "string"}),
        "cierre": _dato({"enum": list(CIERRES)}),
        "duracion_min": _dato({"type": "string"}),
        "dia": _dato({"type": "string"}),
        "hora": _dato({"type": "string"}),
        "lugar": {
            "type": "object",
            "additionalProperties": False,
            "required": ["nombre", "nivel", "fuente", "frase"],
            "properties": {
                "nombre": {"type": "string"},
                "nivel": {"enum": list(NIVELES)},
                "fuente": _FUENTE,
                "frase": _FRASE,
            },
        },
    },
}

ESQUEMA_TRADUCIR: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["traducciones"],
    "properties": {
        "traducciones": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["n", "es", "en"],
                "properties": {
                    "n": {"type": "integer"},
                    "es": {"type": "string"},
                    "en": {"type": "string"},
                },
            },
        }
    },
}

INSTRUCCIONES_COMPARAR = """Eres el control de calidad del European Observatory of Drone \
Incidents. Recibes dos fichas de incidentes con drones del mismo país y de fechas cercanas, cada \
una con sus fuentes (medio, fecha de publicación, idioma, titular y frase), en idiomas \
distintos. Decide si cuentan el mismo suceso, es decir, el mismo hecho físico: el mismo dron o \
los mismos drones, en el mismo sitio y el mismo día o la misma noche (la misma alerta, el mismo \
cierre, el mismo derribo, el mismo ataque a un barco).

- mismo_dia: las dos fichas cuentan algo ocurrido el mismo día o la misma noche (no el día en \
que se publicó: una noticia posterior sobre ese hecho cuenta como ese día).
- mismo_sitio: el mismo aeropuerto, la misma base, el mismo barco o la misma localidad. Que una \
ficha diga solo el país o la zona (aguas búlgaras, la costa) y la otra el sitio con más detalle \
(los puntos frente a la costa donde se atacó a cada barco) no las hace distintas; dos \
aeropuertos, dos bases o dos localidades distintas que una ficha cuenta y la otra no, sí, aunque \
sea la misma noche y la misma oleada de drones.
- varios_sucesos: una de las dos fichas junta hechos de días o sitios distintos que la otra no \
cuenta (un balance de varias noches frente a una de ellas, varios derribos frente a uno, varios \
aeropuertos frente a uno) o no cuenta ninguno concreto. Si las dos cuentan el mismo conjunto (el \
ataque de esa noche a dos barcos, los drones de esa noche sobre una base), es falso.
- decision: «mismo» solo si mismo_dia y mismo_sitio son ciertos y varios_sucesos es falso; \
«distinto» si alguno de los dos es falso («de nuevo», «otra vez», «un segundo ataque», otro día, \
otro sitio) o si una ficha resume varios sucesos; «dudoso» si las fuentes no permiten saberlo.

Decide solo por lo que dicen las fuentes. Escribe el motivo en una frase, en español \
(motivo_es) y en inglés (motivo_en), con el dato que lo decide (el sitio, el día, la hora)."""

INSTRUCCIONES_VERIFICAR = """Eres el control de calidad del European Observatory of Drone \
Incidents. Recibes la ficha de un incidente con drones y sus fuentes numeradas (medio, fecha, \
idioma, titular y primeras frases). Para cada dato, di lo que dicen las fuentes, con el número \
de la fuente y la frase copiada literalmente de su titular o de su texto (sin traducir, sin \
cambiar nada, 25 palabras como máximo). Si ninguna fuente lo dice, el valor es «sin_dato» (o \
vacío en los textos), la fuente 0 y la frase vacía. No deduzcas nada.

- presencia: «confirmada» si una autoridad (policía, ejército, ministerio, aeropuerto, control \
aéreo, fiscalía) da por hecho que hubo un dron o actúa por él; «posible» si se habla de un \
posible dron, de un avistamiento sin confirmar o de lo que vieron pilotos o testigos; \
«no_hallado» si una fuente dice que se buscó el dron y no se encontró, que no se vio ninguno o \
que era otra cosa (un globo, pájaros); «desmentido» si una autoridad niega que hubiera dron; \
«sin_dato» si no lo dicen. Si una fuente dice «no_hallado» o «desmentido», elige ese.
- drones: cuántos drones dice una fuente, como «N» o «mínimo-máximo», solo si da un número o una \
cantidad escrita («dos drones», «varios drones», «un enjambre»: «2», «2-10», «5-50»). Un plural \
sin cantidad («drones vistos») o el número de pilotos, de vuelos o de testigos no es un número \
de drones: vacío.
- cierre: «si» si una fuente dice que se cerró o se paró el aeropuerto, una pista o el espacio \
aéreo, o que se suspendieron o desviaron los vuelos; «no» si dice que siguió abierto.
- duracion_min: cuántos minutos estuvo cerrado o parado el aeropuerto, la pista o el espacio \
aéreo, solo si una fuente lo dice de ese cierre («cerrado durante una hora»: «60»; cerrado de \
las 6:10 a las 7:00: «50»). No el tiempo que un avión esperó o dio vueltas, ni el retraso de un \
vuelo.
- dia: el día del suceso como AAAA-MM-DD, solo si la frase lo escribe («13 de octubre») o lo da \
respecto a la publicación de su fuente («el martes», «anoche», «esta mañana»). Si la frase no \
dice el día, vacío: la fecha de publicación no es el día del suceso.
- hora: la hora local del suceso como HH:MM, solo si una fuente la escribe («gegen 6 Uhr»: \
«06:00»; «entre las 2 y las 4 de la madrugada»: «02:00»).
- lugar: el sitio más concreto donde ocurrió el suceso según las fuentes (el aeropuerto, la \
base, el puerto, la ciudad), con su nivel. No el sitio de una reacción, de una rueda de prensa \
ni de un aeropuerto al que se desviaron vuelos."""

INSTRUCCIONES_TRADUCIR = """Traduces citas de noticias y de comunicados oficiales sobre \
incidentes con drones para el European Observatory of Drone Incidents. Para cada cita numerada \
da su traducción al español (es) y al inglés (en): fiel, completa, sin añadir ni quitar nada, \
con los nombres propios como en el original (los de ciudades y aeropuertos, en su forma \
habitual en cada idioma). Si la cita ya está en español, deja «es» vacío; si ya está en \
inglés, deja «en» vacío."""


@dataclass(frozen=True)
class FuenteControl:
    """Una fuente como la ve el control: titular y primeras frases (o la frase guardada)."""

    medio: str
    fecha: str
    idioma: str
    titular: str
    texto: str

    def bloque(self, numero: int) -> str:
        texto = self.texto[:MAX_LETRAS_TEXTO]
        cuerpo = f" Texto: {texto}" if texto else ""
        return (
            f"Fuente {numero} ({self.medio}, {self.fecha}, {self.idioma or '?'}). "
            f"Titular: {self.titular}.{cuerpo}"
        )


def _cuerpo(instrucciones: str, esquema: dict[str, Any], contenido: str,
            max_tokens: int, esfuerzo: str) -> dict[str, Any]:  # fmt: skip
    return {
        "max_tokens": max_tokens,
        "temperature": TEMPERATURA,
        "system": [{"type": "text", "text": instrucciones, "cache_control": {"type": "ephemeral"}}],
        "output_config": {
            "format": {"type": "json_schema", "schema": esquema}, "effort": esfuerzo,
        },
        "messages": [{"role": "user", "content": contenido}],
    }


def resumen_ficha(ficha: dict[str, Any]) -> str:
    """Los datos de una ficha en una línea por dato."""
    return "\n".join(f"- {clave}: {valor}" for clave, valor in ficha.items())


def cuerpo_comparar(
    a: dict[str, Any], fuentes_a: list[FuenteControl],
    b: dict[str, Any], fuentes_b: list[FuenteControl],
) -> dict[str, Any]:  # fmt: skip
    partes = ["Ficha A:", resumen_ficha(a), "Fuentes de A:"]
    partes += [f.bloque(i) for i, f in enumerate(fuentes_a[:MAX_FUENTES], 1)]
    partes += ["", "Ficha B:", resumen_ficha(b), "Fuentes de B:"]
    partes += [f.bloque(i) for i, f in enumerate(fuentes_b[:MAX_FUENTES], 1)]
    return _cuerpo(INSTRUCCIONES_COMPARAR, ESQUEMA_COMPARAR, "\n".join(partes),
                   MAX_SALIDA_COMPARAR, ESFUERZO_COMPARAR)  # fmt: skip


def cuerpo_verificar(ficha: dict[str, Any], fuentes: list[FuenteControl]) -> dict[str, Any]:
    partes = ["Ficha:", resumen_ficha(ficha), "Fuentes:"]
    partes += [f.bloque(i) for i, f in enumerate(fuentes[:MAX_FUENTES], 1)]
    return _cuerpo(INSTRUCCIONES_VERIFICAR, ESQUEMA_VERIFICAR, "\n".join(partes),
                   MAX_SALIDA_VERIFICAR, ESFUERZO_VERIFICAR)  # fmt: skip


def cuerpo_traducir(citas: list[tuple[str, str]]) -> dict[str, Any]:
    """`citas`: (idioma, texto) en orden; la respuesta las numera desde 1."""
    lineas = [f"{n}. ({idioma or '?'}) {texto}" for n, (idioma, texto) in enumerate(citas, 1)]
    return _cuerpo(INSTRUCCIONES_TRADUCIR, ESQUEMA_TRADUCIR, "\n".join(lineas),
                   MAX_SALIDA_TRADUCIR, ESFUERZO_TRADUCIR)  # fmt: skip


def letras(cuerpo: dict[str, Any]) -> int:
    """Letras de entrada de la petición, para el peor caso del gasto."""
    return sum(len(b["text"]) for b in cuerpo["system"]) + sum(
        len(str(m["content"])) for m in cuerpo["messages"]
    )


class RespuestaInvalida(ValueError):
    pass


def leer(respuesta: dict[str, Any]) -> dict[str, Any]:
    """El JSON de la respuesta. Lanza RespuestaInvalida si no lo trae entero."""
    if respuesta.get("stop_reason") not in {"end_turn", "stop_sequence"}:
        raise RespuestaInvalida(f"parada: {respuesta.get('stop_reason')}")
    textos = [b.get("text", "") for b in respuesta.get("content", []) if b.get("type") == "text"]
    try:
        datos = json.loads("".join(textos))
    except ValueError as error:
        raise RespuestaInvalida("la salida no es JSON") from error
    if not isinstance(datos, dict):
        raise RespuestaInvalida("la salida no es un objeto")
    return datos
