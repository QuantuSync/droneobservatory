"""Llamadas del filtro de entrada de las fichas nuevas (recogida/entrada.py), siempre con el
experto, con su esquema de salida, temperatura 0 y las instrucciones en la caché del servicio:

- entrada: una ficha nueva (sus datos, sus fuentes y sus frases) y la lista resumida de las fichas
  que pueden contar el mismo suceso (las del mismo país, y de los vecinos si el lugar es vago, de
  30 días antes a 3 después): ¿es el mismo suceso que alguna?, ¿la noticia cuenta un suceso de otro
  día?, ¿la fecha, el lugar y cada autoridad citada salen de una frase de una fuente?;
- medida: la misma ficha 24 horas después de publicarse, con la lista ampliada: ¿hay algún error
  en la fecha, el lugar, el número de drones, la autoridad o es un duplicado?

El código nunca se fía de la respuesta sin comprobarla: cada frase tiene que estar, literal, en
el texto de su fuente, y cada identificador, en la lista que se mandó.
"""

from typing import Any

from modelo.control import MAX_FUENTES, FuenteControl, _cuerpo, resumen_ficha

VERSION_ENTRADA = "entrada/1"
VERSION_MEDIDA = "medida/1"
# Decidir si una ficha es un suceso ya registrado es lo más difícil del control.
ESFUERZO_ENTRADA = "high"
MAX_SALIDA_ENTRADA = 1500
MAX_SALIDA_MEDIDA = 1200
# Fuentes de cada candidata que se mandan en la segunda pregunta (con más contexto).
MAX_FUENTES_CANDIDATA = 3
MAX_CANDIDATAS_CONTEXTO = 4
NINGUNA = "ninguna"
NO = "no"
DATOS_MEDIDA = ("fecha", "lugar", "drones", "autoridad", "duplicado")

_FRASE = {"type": "string"}
_FUENTE = {"type": "integer"}

ESQUEMA_ENTRADA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "mismo_suceso",
        "motivo_mismo",
        "otro_dia",
        "fecha_suceso",
        "fecha_fuente",
        "fecha_frase",
        "lugar_fuente",
        "lugar_frase",
        "autoridades",
        "duda",
        "dudosas",
        "motivo_es",
        "motivo_en",
    ],
    "properties": {
        "mismo_suceso": {"type": "string"},
        "motivo_mismo": {"type": "string"},
        "otro_dia": {"type": "boolean"},
        "fecha_suceso": {"type": "string"},
        "fecha_fuente": _FUENTE,
        "fecha_frase": _FRASE,
        "lugar_fuente": _FUENTE,
        "lugar_frase": _FRASE,
        "autoridades": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["nombre", "pais", "fuente", "frase"],
                "properties": {
                    "nombre": {"type": "string"},
                    "pais": {"type": "string"},
                    "fuente": _FUENTE,
                    "frase": _FRASE,
                },
            },
        },
        "duda": {"type": "boolean"},
        "dudosas": {"type": "array", "items": {"type": "string"}},
        "motivo_es": {"type": "string"},
        "motivo_en": {"type": "string"},
    },
}

INSTRUCCIONES_ENTRADA = """Eres el control de entrada del European Observatory of Drone \
Incidents. Ninguna ficha nueva se publica sin pasar por ti. Recibes una ficha nueva de un \
incidente con drones (sus datos, sus fuentes numeradas con medio, fecha de publicación, idioma, \
titular y texto, y las autoridades cuyas declaraciones cita) y la lista de las fichas que ya \
tenemos y que pueden contar el mismo suceso: las del mismo país, y de los países vecinos si el \
lugar es el mar, una frontera o solo una región, de 30 días antes a 3 después (identificador, \
fecha, lugar, titular, tipo y una frase). Muchos errores publicados fueron noticias que cuentan \
otra vez un suceso ya registrado (una reacción, un balance, un recuerdo semanas después, otra \
agencia que lo cuenta con un día de diferencia porque la noche cae a caballo de dos días UTC, \
un buque atacado en el mar entre dos países) o un suceso de otro día fechado por la publicación.

- mismo_suceso: el identificador exacto de la ficha de la lista que cuenta el mismo hecho físico \
(los mismos drones, el mismo derribo, el mismo buque, el mismo cierre del mismo aeropuerto la \
misma noche), aunque cambien la fecha de publicación, el idioma, el lugar más o menos preciso o \
el número; «ninguna» si no es ninguna. Dos sucesos parecidos en el mismo sitio en días \
distintos son distintos. motivo_mismo: por qué, en una frase.
- otro_dia: true si las fuentes cuentan un suceso de un día distinto del de la ficha (no la \
noche anterior a la publicación: eso es el mismo día del suceso). fecha_suceso: el día del \
suceso, AAAA-MM-DD, que dan las fuentes (vacío si ninguna lo da).
- fecha_fuente y fecha_frase: el número de la fuente y la frase literal, copiada tal cual de su \
texto, que da el día del suceso («el sábado», «la noche del lunes», «on 17 October», \
«overnight» en una nota del mismo día); «no» si ninguna frase lo da (la fecha de publicación \
sola no es la fecha del suceso).
- lugar_fuente y lugar_frase: la frase literal que nombra el sitio de la ficha (o uno más \
concreto); «no» si ninguna lo nombra.
- autoridades: por cada autoridad citada de la ficha, su nombre tal como viene, el país al que \
pertenece (código ISO de dos letras; «NATO» u «EU» si es de la OTAN o de la Unión Europea) y la \
fuente y la frase literal que la nombran y de las que sale ese país. El país es el de la \
institución, no el de la lengua de la fuente: un medio rumano que nombra en rumano el Consejo \
de Seguridad búlgaro habla de Bulgaria, y no de Moldavia. Si ninguna frase dice de qué país es, \
pais vacío y frase «no».
- duda: true si dudas entre dos respuestas (sobre todo si es o no el mismo suceso que una ficha \
de la lista); dudosas: los identificadores de las fichas de la lista con las que dudas.
- motivo_es y motivo_en: una frase corta, en español y en inglés, con lo que decidiste."""


def _resumenes(conjunto: list[dict[str, Any]]) -> list[str]:
    return [
        f"- {c['id']} | {c['fecha']} | {c['lugar']} | {c['tipo']} | {c['titular']} | {c['frase']}"
        for c in conjunto
    ] or ["(ninguna)"]


def contenido_entrada(
    ficha: dict[str, Any], fuentes: list[FuenteControl], autoridades: list[str],
    conjunto: list[dict[str, Any]], contexto: dict[str, list[FuenteControl]] | None = None,
) -> str:  # fmt: skip
    """El mensaje: la ficha, sus fuentes, sus autoridades y la lista; con `contexto`, también las
    fuentes de las candidatas con las que hubo duda."""
    partes = ["Ficha nueva:", resumen_ficha(ficha), "Fuentes:"]
    partes += [f.bloque(i) for i, f in enumerate(fuentes[:MAX_FUENTES], 1)]
    partes += ["Autoridades citadas:", *([f"- {a}" for a in autoridades] or ["(ninguna)"])]
    partes += ["", "Fichas que ya tenemos (id | fecha | lugar | tipo | titular | frase):"]
    partes += _resumenes(conjunto)
    for id_, bloques in (contexto or {}).items():
        partes += ["", f"Fuentes de {id_}:"]
        partes += [b.bloque(i) for i, b in enumerate(bloques[:MAX_FUENTES_CANDIDATA], 1)]
    return "\n".join(partes)


def cuerpo_entrada(
    ficha: dict[str, Any], fuentes: list[FuenteControl], autoridades: list[str],
    conjunto: list[dict[str, Any]], contexto: dict[str, list[FuenteControl]] | None = None,
) -> dict[str, Any]:  # fmt: skip
    return _cuerpo(INSTRUCCIONES_ENTRADA, ESQUEMA_ENTRADA,
                   contenido_entrada(ficha, fuentes, autoridades, conjunto, contexto),
                   MAX_SALIDA_ENTRADA, ESFUERZO_ENTRADA)  # fmt: skip


# --- Medida a las 24 horas ----------------------------------------------------------------

ESQUEMA_MEDIDA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["errores", "motivo_es", "motivo_en"],
    "properties": {
        "errores": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["dato", "correcto", "duplicado_de", "fuente", "frase"],
                "properties": {
                    "dato": {"enum": list(DATOS_MEDIDA)},
                    "correcto": {"type": "string"},
                    "duplicado_de": {"type": "string"},
                    "fuente": _FUENTE,
                    "frase": _FRASE,
                },
            },
        },
        "motivo_es": {"type": "string"},
        "motivo_en": {"type": "string"},
    },
}

INSTRUCCIONES_MEDIDA = """Eres la medida independiente del European Observatory of Drone \
Incidents. Recibes una ficha publicada hace 24 horas (sus datos, sus fuentes numeradas y las \
autoridades que cita) y la lista de las fichas que pueden contar el mismo suceso (las del mismo \
país, y de los vecinos si el lugar es vago, de 30 días antes a 3 después, también las llegadas \
después). Busca errores, sin dar por buena la ficha:

- fecha: el día del suceso no es el de la ficha (una noticia de otro día, la fecha de \
publicación de un recuerdo); correcto: el día AAAA-MM-DD.
- lugar: el sitio de la ficha no es el que dicen las fuentes; correcto: el sitio.
- drones: el número de drones no es el que dicen las fuentes; correcto: el número.
- autoridad: una autoridad citada es de otro país o no la nombra ninguna frase; correcto: su \
país (ISO de dos letras) o vacío.
- duplicado: la ficha cuenta el mismo hecho físico que una de la lista; duplicado_de: su \
identificador exacto.

Cada error con la fuente y la frase literal, copiada tal cual de su texto, que lo muestra (0 y \
vacío si el error es que ninguna frase lo respalda). Solo errores claros; ninguno, lista vacía. \
motivo_es y motivo_en: una frase corta con lo que encontraste."""


def cuerpo_medida(
    ficha: dict[str, Any], fuentes: list[FuenteControl], autoridades: list[str],
    conjunto: list[dict[str, Any]],
) -> dict[str, Any]:  # fmt: skip
    return _cuerpo(INSTRUCCIONES_MEDIDA, ESQUEMA_MEDIDA,
                   contenido_entrada(ficha, fuentes, autoridades, conjunto),
                   MAX_SALIDA_MEDIDA, ESFUERZO_ENTRADA)  # fmt: skip


# --- Repaso de lo publicado con la pregunta de entrada ------------------------------------

VERSION_REPASO = "repaso_entrada/3"
MAX_SALIDA_REPASO = 2200
DATOS_REPASO = ("drones", "tipo", "estado", "presencia")

ESQUEMA_REPASO: dict[str, Any] = {
    **ESQUEMA_ENTRADA,
    "required": [
        *ESQUEMA_ENTRADA["required"],
        "fecha_desconocida",
        "varios_sucesos",
        "resumen",
        "partes",
        "errores",
    ],
    "properties": {
        **ESQUEMA_ENTRADA["properties"],
        "fecha_desconocida": {"type": "boolean"},
        "varios_sucesos": {"type": "boolean"},
        "resumen": {"type": "boolean"},
        "partes": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["fecha", "descripcion", "fuentes"],
                "properties": {
                    "fecha": {"type": "string"},
                    "descripcion": {"type": "string"},
                    "fuentes": {"type": "array", "items": _FUENTE},
                },
            },
        },
        "errores": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["dato", "correcto", "fuente", "frase"],
                "properties": {
                    "dato": {"enum": list(DATOS_REPASO)},
                    "correcto": {"type": "string"},
                    "fuente": _FUENTE,
                    "frase": _FRASE,
                },
            },
        },
    },
}

INSTRUCCIONES_REPASO = (
    INSTRUCCIONES_ENTRADA.replace(
        "Ninguna ficha nueva se publica sin pasar por ti. Recibes una ficha nueva",
        "Repasas una ficha ya publicada como si fuera nueva: no la des por buena por estar "
        "publicada. Recibes la ficha",
    )
    + """

Además:
- fecha_desconocida: true si las fuentes cuentan un suceso anterior a su publicación sin decir \
en qué día fue (un recuerdo, «recientemente», «en las últimas semanas»); false si dan el día o si \
cuentan algo de la noche o el día de la publicación.
- mismo_suceso: solo si es seguro que es el mismo suceso. El mismo día y país no bastan: \
en una noche con varios drones, cada uno en otro lugar es otro suceso; y una noticia publicada \
antes del día del suceso no puede contarlo. Si es solo probable, duda.
- varios_sucesos: true si la ficha junta sucesos de días o lugares distintos (un resumen, un \
balance, «durante tres noches», drones en varios aeropuertos en noches distintas). partes: cada \
suceso con su día (AAAA-MM-DD), una descripción corta y los números de las fuentes que lo \
cuentan (una fuente que cuenta dos va en las dos); lista vacía si es un solo suceso.
- resumen: true si la ficha es un resumen o un balance sin ningún suceso de un día concreto.
- errores: los errores claros del número de drones, el tipo, el estado (notificado, confirmado, \
atribuido, desmentido) o la presencia del dron (confirmada o no) frente a lo que dicen las \
fuentes, cada uno con el valor correcto y la fuente y la frase literal que lo muestran; ninguno, \
lista vacía. correcto, según el dato: drones, un número o un intervalo «3-5», el de este \
suceso en este lugar (no el de otro suceso que cite la noticia); «hasta diez» es «1-10», y no \
es un error si el número de la ficha ya lo incluye; tipo, \
«incursion» (una autoridad dice que el dron entró desde fuera del país), «sobrevuelo» o \
«interrupcion_aeroportuaria» (se cerró o se paró un aeropuerto); presencia, «confirmada» solo si \
lo dice una autoridad (policía, ejército, ministerio, aeropuerto) o hay pruebas físicas (el dron \
hallado o derribado), no por un vídeo o un testigo en la prensa ni por un sindicato, y si no \
«no_confirmada». La frase, de 25 palabras como mucho."""
)


def cuerpo_repaso(
    ficha: dict[str, Any], fuentes: list[FuenteControl], autoridades: list[str],
    conjunto: list[dict[str, Any]], contexto: dict[str, list[FuenteControl]] | None = None,
) -> dict[str, Any]:  # fmt: skip
    return _cuerpo(INSTRUCCIONES_REPASO, ESQUEMA_REPASO,
                   contenido_entrada(ficha, fuentes, autoridades, conjunto, contexto),
                   MAX_SALIDA_REPASO, ESFUERZO_ENTRADA)  # fmt: skip
