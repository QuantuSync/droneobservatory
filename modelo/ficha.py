"""Ficha que devuelve el extractor: esquema de salida, instrucciones y petición.

La salida está obligada por el esquema (salida estructurada del servicio). Cada
campo lleva la fuente de la que sale, la frase de origen (25 palabras como
máximo, copiada del texto) y la confianza. El servicio no admite mínimos ni
máximos en el esquema: los rangos, las fechas y las coordenadas se validan con
código (`proceso/validacion_ficha.py`).

Las instrucciones y el esquema van delante y marcados para la caché del
servicio; el candidato va detrás. Los ejemplos hacen que el bloque fijo pase
del mínimo que el servicio cachea con este modelo (4096 tokens).
"""

import json
from dataclasses import dataclass
from typing import Any

VERSION = "ficha/1"
# La ficha completa ocupa unos 600 tokens; 1500 dejan margen sin pagar de más.
MAX_TOKENS_SALIDA = 1500
TIPOS = ("interrupcion_aeroportuaria", "sobrevuelo", "incursion")
CATEGORIAS = (
    "aeropuerto", "base_militar", "puerto", "energia", "presa", "estadio", "industrial",
    "gubernamental", "otra",
)  # fmt: skip
PRECISIONES = ("minuto", "hora", "dia")
PRESENCIA = ("confirmada", "no_confirmada", "descartada")
CIERRE = ("si", "no", "desconocido")
MEDIDAS = ("cierre_espacio_aereo", "patrulla", "cazas", "derribo", "inhibicion")
ORIGEN = ("rastreo", "restos")


def _nulo(esquema: dict[str, Any]) -> dict[str, Any]:
    return {"anyOf": [esquema, {"type": "null"}]}


def _campo(valor: dict[str, Any]) -> dict[str, Any]:
    """Un campo con su valor (o null si ninguna fuente lo dice), fuente, frase y confianza."""
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["valor", "fuente", "frase", "confianza"],
        "properties": {
            "valor": _nulo(valor),
            "fuente": {"type": "integer"},
            "frase": {"type": "string"},
            "confianza": {"type": "number"},
        },
    }


_TEXTO = {"type": "string"}
_ENTERO = {"type": "integer"}
_RANGO = {
    "type": "object",
    "additionalProperties": False,
    "required": ["min", "max"],
    "properties": {"min": _ENTERO, "max": _ENTERO},
}
_LUGAR = {
    "type": "object",
    "additionalProperties": False,
    "required": ["nombre", "categoria", "pais", "lat", "lon"],
    "properties": {
        "nombre": _TEXTO,
        "categoria": {"enum": list(CATEGORIAS)},
        "pais": _TEXTO,
        "lat": {"type": "number"},
        "lon": {"type": "number"},
    },
}
CAMPOS: dict[str, dict[str, Any]] = {
    "es_incidente": _campo({"type": "boolean"}),
    "tipo": _campo({"enum": list(TIPOS)}),
    "inicio": _campo(_TEXTO),
    "inicio_precision": _campo({"enum": list(PRECISIONES)}),
    "fin": _campo(_TEXTO),
    "pais": _campo(_TEXTO),
    "localidad": _campo(_TEXTO),
    "objetivo_conocido": _campo({"type": "boolean"}),
    "objetivo_categoria": _campo({"enum": list(CATEGORIAS)}),
    "objetivo_nombre": _campo(_TEXTO),
    "lugar_nuevo": _campo(_LUGAR),
    "drones": _campo(_RANGO),
    "presencia_dron": _campo({"enum": list(PRESENCIA)}),
    "cierre": _campo({"enum": list(CIERRE)}),
    "cierre_minutos": _campo(_RANGO),
    "vuelos_desviados": _campo(_RANGO),
    "vuelos_cancelados": _campo(_RANGO),
    "vuelos_retrasados": _campo(_RANGO),
    "modelo_dron": _campo(_TEXTO),
    "medidas": _campo({"type": "array", "items": {"enum": list(MEDIDAS)}}),
    "origen_demostrado": _campo({"type": "array", "items": {"enum": list(ORIGEN)}}),
}
ESQUEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": [*CAMPOS, "titulo_es", "titulo_en"],
    "properties": {**CAMPOS, "titulo_es": _TEXTO, "titulo_en": _TEXTO},
}

INSTRUCCIONES = """Eres el extractor del Observatorio Europeo de Incidentes con Drones. Recibes \
las fuentes de un posible incidente con drones en Europa: para cada una, el medio, la fecha de \
publicación, el titular y las primeras frases. Devuelve una ficha con los hechos que dicen las \
fuentes, sin añadir nada que no digan.

Qué es un incidente: un dron visto, detectado, derribado o caído en Europa (fuera de Ucrania y \
de Rusia) cerca de un aeropuerto, una base militar, una central, un puerto u otra \
infraestructura, o que entra en el espacio aéreo de un país. No son incidentes: ataques de la \
guerra en Ucrania o en Rusia, espectáculos, reparto, agricultura, compras, ejercicios y pruebas \
anunciados, leyes y planes contra drones, ni noticias que solo hablan de drones en general. Si \
no es un incidente, es_incidente vale false y el resto de campos puede ir con valor null.

Cada campo tiene cuatro partes:
- valor: el dato, o null si ninguna fuente lo dice.
- fuente: el número de la fuente de la que sale (1, 2 o 3); 0 si el valor es null.
- frase: la frase de esa fuente que lo dice, copiada literalmente en su idioma, de 25 palabras \
como máximo; vacía si el valor es null.
- confianza: de 0 a 1, cuánto apoya la frase ese valor. Usa 0.9 o más solo si la frase lo dice \
expresamente; 0.5 a 0.8 si se deduce con claridad; menos de 0.5 si es una suposición.

Campos:
- tipo: interrupcion_aeroportuaria si un aeropuerto cierra, desvía, cancela o retrasa vuelos; \
incursion solo si una autoridad dice que el dron entró desde otro país (rastreo por radar o \
restos); si no, sobrevuelo.
- inicio: cuándo empezó el incidente (no cuándo se publicó), en UTC, como AAAA-MM-DDTHH:MM o \
AAAA-MM-DD. Convierte la hora local del país a UTC. inicio_precision: minuto si la fuente da \
la hora exacta, hora si da una hora aproximada o una franja corta, dia si solo da el día o \
dice anoche, ayer, el lunes. fin: cuándo acabó, con el mismo formato, si lo dice.
- pais: código ISO 3166-1 alfa-2 del país del incidente. localidad: ciudad o municipio.
- objetivo_conocido: true si el incidente ocurre en el objetivo conocido que se te indica; \
false si ocurre en otro sitio. objetivo_categoria y objetivo_nombre: la instalación afectada \
tal como la nombra la fuente.
- lugar_nuevo: solo si objetivo_conocido es false y la fuente nombra la instalación: su nombre, \
categoría, país y coordenadas aproximadas en grados decimales. Si no sabes dónde está, null.
- drones: número de drones como rango mínimo y máximo («varios» es de 2 a 10; «un enjambre», de \
5 a 50; un número exacto, mínimo igual a máximo).
- presencia_dron: confirmada solo si hay restos, rastreo por radar o una autoridad afirma \
expresamente que era un dron; descartada si una autoridad dice que no lo era (un globo, un \
avión, una estrella); no_confirmada si solo hay avistamientos.
- cierre: si se cerró el aeropuerto o el espacio aéreo; cierre_minutos: cuánto duró.
- vuelos_desviados, vuelos_cancelados, vuelos_retrasados: rangos de vuelos afectados.
- modelo_dron: el modelo o tipo que nombra la fuente (por ejemplo, Shahed, Gerbera, DJI Mavic); \
null si no lo nombra.
- medidas: lo que hicieron las autoridades: cierre_espacio_aereo, patrulla, cazas, derribo, \
inhibicion.
- origen_demostrado: rastreo si una autoridad siguió al dron por radar desde otro país; restos si \
se encontraron restos que prueban el origen.
- titulo_es y titulo_en: un título breve y neutro, en español y en inglés, con lugar y hecho \
(«Drones sobre el aeropuerto de Copenhague obligan a cerrarlo»), sin fecha.

Reglas: nunca inventes; si las fuentes discrepan, usa la más precisa y dilo con la confianza. \
No uses la fecha de publicación como fecha del incidente salvo que la fuente diga que ocurrió \
ese mismo día. No confundas un aeropuerto con la ciudad. Copia las frases tal cual.

Ejemplo 1.
Objetivo conocido: Aeropuerto de Copenhague (aeropuerto, DK, EKCH).
Fuente 1 (dr.dk, 2025-09-23T05:12Z, da). Titular: Droner over Københavns Lufthavn: lufthavnen \
lukket i fire timer. Texto: Københavns Lufthavn var lukket fra klokken 20.30 mandag aften, \
efter at der blev observeret tre til fire store droner. Politiet siger, at der er tale om en \
dygtig aktør. 31 fly blev omdirigeret.
Ficha esperada (resumida): es_incidente true (fuente 1, «Københavns Lufthavn var lukket fra \
klokken 20.30 mandag aften», 0.95); tipo interrupcion_aeroportuaria; inicio 2025-09-22T18:30 \
con precisión minuto (20.30 en Copenhague es 18.30 UTC); pais DK; localidad Copenhague; \
objetivo_conocido true; drones de 3 a 4; presencia_dron no_confirmada (solo observación); \
cierre si, de 240 a 240 minutos; vuelos_desviados de 31 a 31; medidas []; origen_demostrado [].

Ejemplo 2.
Objetivo conocido: Aeropuerto de Múnich (aeropuerto, DE, EDDM).
Fuente 1 (br.de, 2025-10-03T06:40Z, de). Titular: Drohnensichtungen: Flughafen München stellt \
Betrieb ein. Texto: Wegen mehrerer Drohnensichtungen ist der Flugbetrieb am Münchner Flughafen \
am Donnerstagabend gegen 22 Uhr eingestellt worden. 17 Flüge konnten nicht starten, 15 \
landende Maschinen wurden umgeleitet. Die Bundespolizei suchte das Gelände ab.
Ficha esperada (resumida): tipo interrupcion_aeroportuaria; inicio 2025-10-02T20:00 con \
precisión hora («gegen 22 Uhr»); drones de 2 a 10 («mehrerer»); vuelos_cancelados de 17 a 17; \
vuelos_desviados de 15 a 15; cierre si; medidas [patrulla]; presencia_dron no_confirmada.

Ejemplo 3.
Objetivo conocido: Base aérea de Kleine Brogel (base_militar, BE).
Fuente 1 (vrt.be, 2025-11-01T09:00Z, nl). Titular: Opnieuw drones gespot boven militaire \
basis Kleine Brogel. Texto: Vrijdagavond zijn opnieuw drones gezien boven de basis. Defensie \
bevestigt de waarnemingen maar kon de toestellen niet uitschakelen.
Ficha esperada (resumida): tipo sobrevuelo; inicio 2025-10-31 con precisión dia; objetivo \
base_militar; drones de 2 a 10; presencia_dron no_confirmada (Defensie confirma que hubo \
avistamientos, no que fueran drones); cierre desconocido; medidas []; origen_demostrado [].

Ejemplo 4.
Objetivo conocido: Aeropuerto de Rzeszów (aeropuerto, PL, EPRZ).
Fuente 1 (tvn24.pl, 2025-09-10T07:00Z, pl). Titular: Rosyjskie drony nad Polską zestrzelone. \
Texto: W nocy z wtorku na środę przestrzeń powietrzna Polski została naruszona przez rosyjskie \
drony. Dowództwo Operacyjne potwierdza, że część z nich zestrzelono. Lotnisko w Rzeszowie było \
zamknięte do rana.
Ficha esperada (resumida): tipo interrupcion_aeroportuaria (el aeropuerto cerró; manda sobre \
incursión); inicio 2025-09-09 con precisión dia; presencia_dron confirmada (el mando militar \
confirma que eran drones y los derribó); medidas [derribo, cazas si la fuente los nombra]; \
origen_demostrado [rastreo] solo si la fuente dice que se siguieron desde fuera.

Ejemplo 5.
Objetivo conocido: Aeropuerto de Oslo (aeropuerto, NO, ENGM).
Fuente 1 (nrk.no, 2025-09-23T06:00Z, no). Titular: Politiet: Ingen droner ved Gardermoen likevel. \
Texto: Det som ble meldt som droner over Oslo lufthavn i natt, var trolig et fly, sier politiet.
Ficha esperada (resumida): es_incidente true; tipo sobrevuelo; presencia_dron descartada \
(la policía dice que era un avión, 0.8 porque dice «trolig»).

Ejemplo 6.
Objetivo conocido: Aeropuerto de Barcelona (aeropuerto, ES, LEBL).
Fuente 1 (lavanguardia.com, 2025-06-01T10:00Z, es). Titular: El mejor espectáculo de drones del \
verano llega a Barcelona. Texto: Mil drones iluminarán la playa el sábado.
Ficha esperada (resumida): es_incidente false; resto de campos con valor null.
"""


@dataclass(frozen=True)
class FuenteTexto:
    medio: str
    fecha: str
    idioma: str | None
    titular: str
    texto: str

    def bloque(self, numero: int) -> str:
        cuerpo = f" Texto: {self.texto}" if self.texto else ""
        return (
            f"Fuente {numero} ({self.medio}, {self.fecha}, {self.idioma or '?'}). "
            f"Titular: {self.titular}.{cuerpo}"
        )


def contenido(objetivo: str, fuentes: list[FuenteTexto]) -> str:
    lineas = [f"Objetivo conocido: {objetivo}."]
    lineas += [f.bloque(i) for i, f in enumerate(fuentes, 1)]
    return "\n".join(lineas)


def cuerpo(objetivo: str, fuentes: list[FuenteTexto]) -> dict[str, Any]:
    """Cuerpo de la petición sin el modelo, que añade el cliente."""
    return {
        "max_tokens": MAX_TOKENS_SALIDA,
        "system": [{"type": "text", "text": INSTRUCCIONES, "cache_control": {"type": "ephemeral"}}],
        "output_config": {"format": {"type": "json_schema", "schema": ESQUEMA}},
        "messages": [{"role": "user", "content": contenido(objetivo, fuentes)}],
    }


class RespuestaInvalida(ValueError):
    pass


def leer_respuesta(respuesta: dict[str, Any]) -> dict[str, Any]:
    """La ficha de la respuesta del servicio. Lanza RespuestaInvalida si no la hay."""
    if respuesta.get("stop_reason") not in {"end_turn", "stop_sequence"}:
        raise RespuestaInvalida(f"parada: {respuesta.get('stop_reason')}")
    textos = [b.get("text", "") for b in respuesta.get("content", []) if b.get("type") == "text"]
    try:
        ficha = json.loads("".join(textos))
    except ValueError as error:
        raise RespuestaInvalida("la salida no es JSON") from error
    if not isinstance(ficha, dict) or set(ficha) != set(ESQUEMA["required"]):
        raise RespuestaInvalida("la salida no sigue el esquema")
    return ficha
