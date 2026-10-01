"""Ficha del extractor para documentos oficiales: sucesos citados y cifras agregadas.

El extractor recibe solo los párrafos y tablas del documento que se localizaron antes por
palabras clave (proceso/pasajes.py), nunca el documento entero, y devuelve, con la salida
obligada por el esquema:

- sucesos: incidentes concretos que cita el documento (fecha, lugar, número de drones,
  altura, detección, contramedidas y su resultado...), cada dato con su frase literal y su
  confianza, con los mismos nombres y formatos de campo que la ficha de noticias
  (modelo/ficha.py) más los de detalle;
- cifras: cifras agregadas (sobrevuelos, avistamientos, afectaciones... por periodo y ámbito),
  cada una con su frase literal y su confianza.

Como en la ficha de noticias, es una lista de datos y no un objeto con un campo por dato: el
servicio rechaza los esquemas grandes. El código interpreta cada valor y lo valida
(proceso/validacion_oficial.py); lo que no se entiende se descarta con su motivo.
"""

import json
import re
from typing import Any

from modelo import ficha

VERSION = "oficial/1"
# Un documento puede citar varios sucesos y varias cifras: más salida que una ficha de noticias.
# En las pruebas del 1 de octubre de 2026 las respuestas ocuparon de 200 a 800 tokens; 2000 dejan
# margen sin inflar el peor caso con que se recorta el lote del histórico.
MAX_TOKENS_SALIDA = 2000
TEMPERATURA = 0.0
DETECCION = ("radar", "visual", "piloto", "camara", "ciudadano")
RESULTADOS = ("funciono", "no_funciono", "desconocido")
METRICAS = (
    "avistamientos", "sobrevuelos", "afectaciones", "detecciones", "encuentros",
    "investigaciones", "detenciones", "otra",
)  # fmt: skip
CATEGORIAS = ficha.CATEGORIAS
# Campos de detalle que la ficha de noticias no tiene.
REALES = ("altura_m", "velocidad_ms")
CAMPOS_SUCESO: tuple[str, ...] = (
    "inicio", "inicio_precision", "fin", "pais", "lugar_suceso", "localidad", "objetivo_nombre",
    "objetivo_categoria", "tipo", "presencia_dron", "dron_estatal", "entrada_exterior",
    "evidencia", "drones", "modelo_dron", "cierre", "cierre_minutos", "vuelos_desviados",
    "vuelos_cancelados", "vuelos_retrasados", "medidas", *REALES, "deteccion",
    "resultado_contramedidas",
)  # fmt: skip

ESQUEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["sucesos", "cifras"],
    "properties": {
        "sucesos": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["titulo_es", "titulo_en", "datos"],
                "properties": {
                    "titulo_es": {"type": "string"},
                    "titulo_en": {"type": "string"},
                    "datos": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "required": ["campo", "valor", "frase", "confianza"],
                            "properties": {
                                "campo": {"enum": list(CAMPOS_SUCESO)},
                                "valor": {"type": "string"},
                                "frase": {"type": "string"},
                                "confianza": {"type": "number"},
                            },
                        },
                    },
                },
            },
        },
        "cifras": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "metrica",
                    "valor",
                    "periodo_inicio",
                    "periodo_fin",
                    "pais",
                    "categoria",
                    "instalacion",
                    "frase",
                    "confianza",
                ],
                "properties": {
                    "metrica": {"enum": list(METRICAS)},
                    "valor": {"type": "string"},
                    "periodo_inicio": {"type": "string"},
                    "periodo_fin": {"type": "string"},
                    "pais": {"type": "string"},
                    "categoria": {"type": "string"},
                    "instalacion": {"type": "string"},
                    "frase": {"type": "string"},
                    "confianza": {"type": "number"},
                },
            },
        },
    },
}

INSTRUCCIONES = """Eres el extractor del European Observatory of Drone Incidents para documentos \
oficiales: respuestas de gobiernos a preguntas parlamentarias, informes finales de organismos \
de investigación de accidentes, comunicados de cierre de investigaciones policiales y \
sentencias. Recibes los datos del documento (autoridad, país, fecha, título) y solo los \
párrafos y tablas que hablan de drones. Devuelve lo que dicen sobre drones en Europa, sin \
añadir nada que no digan.

Dos listas:

1. sucesos: cada incidente concreto que el texto cita con su fecha o con su lugar (un dron \
sobre una base, un aeropuerto, una central, un puerto o una infraestructura, o que entra en el \
espacio aéreo de un país). No son sucesos: cifras totales, programas, leyes, compras, \
ejercicios ni la guerra en Ucrania o en Rusia. Cada suceso lleva titulo_es y titulo_en (breves y \
neutros, con lugar y hecho, sin fecha) y una lista de datos. Incluye solo los datos que el \
texto dice. Cada dato tiene campo, valor (texto con el formato del campo), frase (la frase del \
texto que lo dice, copiada literalmente en su idioma, de 25 palabras como máximo) y confianza \
(de 0 a 1: 0.9 o más solo si la frase lo dice expresamente; 0.5 a 0.8 si se deduce con claridad; \
menos de 0.5 si es una suposición).

Campos y formato del valor (los valores de una lista van tal cual aparecen aquí, en español y \
sin acentos):
- inicio: cuándo empezó, en UTC, como AAAA-MM-DDTHH:MM o AAAA-MM-DD (convierte la hora local a \
UTC); inicio_precision: minuto, hora o dia. fin: cuándo acabó, igual.
- pais: código ISO 3166-1 alfa-2 del país donde ocurrió. localidad: ciudad o municipio, \
copiada tal como la escribe el texto, sin traducir.
- lugar_suceso: siempre cuatro partes separadas por punto y coma, «nombre; nivel; país; \
región»: el nombre copiado de la frase tal como lo escribe el texto, sin traducir \
(«Københavns Lufthavn», no «Aeropuerto de Copenhague»); nivel instalacion, localidad, region o \
pais; el código ISO del país; la región de primer nivel si se sabe sin duda o vacía. Ejemplo: \
«Københavns Lufthavn; instalacion; DK; Hovedstaden».
- objetivo_nombre (copiado tal como lo escribe el texto, sin traducir) y objetivo_categoria \
(aeropuerto, base_militar, puerto, energia, presa, estadio, industrial, gubernamental u otra): \
la instalación afectada.
- tipo: interrupcion_aeroportuaria si un aeropuerto cerró, desvió, canceló o retrasó vuelos; \
incursion si un dron militar o de un Estado entró desde fuera del país y lo demuestra una \
autoridad o una prueba física; si no, sobrevuelo.
- presencia_dron: confirmada solo si el texto afirma expresamente que había un dron (detectado \
por radar o por sensores, visto por personal propio, derribado, recuperado); descartada si dice \
que no lo era; no_confirmada si solo hubo avistamientos o sospechas.
- dron_estatal: true o false. entrada_exterior: true si entró desde fuera del país. evidencia: \
explosion, restos, caida, derribo o recuperado, separados por comas.
- drones: número como «N» o «mínimo-máximo».
- modelo_dron: el modelo o tipo que nombra el texto.
- cierre: si o no. cierre_minutos, vuelos_desviados, vuelos_cancelados, vuelos_retrasados: «N» \
o «mínimo-máximo».
- medidas: cierre_espacio_aereo, patrulla, cazas, derribo, inhibicion, separados por comas.
- altura_m: altura del dron en metros como «N» o «mínimo-máximo» (convierte pies a metros: \
1 pie = 0,3048 m). velocidad_ms: velocidad del dron en metros por segundo (1 km/h = 0,2778 m/s; \
1 nudo = 0,5144 m/s).
- deteccion: cómo se detectó el dron: radar, visual, piloto, camara o ciudadano, separados por \
comas.
- resultado_contramedidas: funciono si las contramedidas (inhibición, derribo, captura) \
neutralizaron el dron; no_funciono si se emplearon y no lo lograron; desconocido si se \
emplearon y el texto no dice el resultado.

2. cifras: cada cifra agregada de drones que da el texto: cuántos sobrevuelos, avistamientos, \
afectaciones del tráfico aéreo, detecciones, encuentros con aeronaves, investigaciones o \
detenciones hubo en un periodo y un ámbito. Cada cifra: metrica (avistamientos: avisos u \
observaciones notificadas; sobrevuelos: sobrevuelos de instalaciones; afectaciones: \
interrupciones o afectaciones del tráfico aéreo, «Behinderungen»; detecciones: por radar u \
otros sensores; encuentros: casi colisiones con aeronaves; investigaciones; detenciones; u \
otra), valor («N» o «mínimo-máximo», en cifras y sin separador de miles; «más de N» es «N» y \
la frase lo dice), periodo_inicio y periodo_fin (AAAA-MM-DD: del primer al último día que \
cubre; «en 2025» es 2025-01-01 a 2025-12-31; «hasta el 30 de septiembre» acaba ese día; «desde \
el 22 de septiembre» sin fin («fra den 22. september og frem», «seit dem 22. September») acaba \
el día del documento, no en otra fecha que nombre el texto), pais (código ISO del ámbito), \
categoria (la categoría de instalación si la cifra es de un tipo de instalación o de una \
instalación, o vacío), instalacion (su nombre si la cifra es de una \
instalación concreta, o vacío), frase (la frase literal con la cifra, 25 palabras como máximo) y \
confianza. Si el texto da la cifra por instalación y el total, incluye cada una.

Reglas: nunca inventes ni completes con lo que sabes; si el texto no lo dice, no incluyas el \
dato. Una pregunta de un diputado no es una afirmación del gobierno: solo cuenta lo que \
afirma la respuesta o el informe. Copia las frases tal cual. Si no hay sucesos ni cifras, \
devuelve las dos listas vacías.
"""


def contenido(datos: dict[str, str], pasajes: list[str]) -> str:
    cabecera = (
        f"Documento: {datos['tipo']} de {datos['autoridad']} ({datos['pais']}), "
        f"{datos['fecha']}, idioma {datos['idioma']}. Título: {datos['titulo']}."
    )
    return "\n\n".join([cabecera, *(f"Pasaje {i}: {p}" for i, p in enumerate(pasajes, 1))])


def cuerpo(datos: dict[str, str], pasajes: list[str]) -> dict[str, Any]:
    """Cuerpo de la petición sin el modelo, que añade el cliente."""
    return {
        "max_tokens": MAX_TOKENS_SALIDA,
        "temperature": TEMPERATURA,
        "system": [{"type": "text", "text": INSTRUCCIONES, "cache_control": {"type": "ephemeral"}}],
        "output_config": {"format": {"type": "json_schema", "schema": ESQUEMA}},
        "messages": [{"role": "user", "content": contenido(datos, pasajes)}],
    }


_MILES = re.compile(r"(?<=\d)[.,'\s  ](?=\d{3}(?!\d))")
_REAL = re.compile(r"^\s*(\d+(?:[.,]\d+)?)\s*(?:[-–]\s*(\d+(?:[.,]\d+)?))?\s*$")


def interpretar(campo: str, texto: str) -> Any:
    """El valor tipado de un dato del suceso. Lanza ficha.ValorIlegible si no se entiende."""
    limpio = texto.strip()
    if campo in REALES:
        m = _REAL.match(limpio)
        if m is None:
            raise ficha.ValorIlegible("no es un número ni un rango")
        minimo = float(m[1].replace(",", "."))
        maximo = float(m[2].replace(",", ".")) if m[2] else minimo
        return {"min": round(minimo, 2), "max": round(maximo, 2)}
    if campo == "deteccion":
        elementos = [ficha._clave(e) for e in limpio.split(",") if e.strip()]
        if not elementos or any(e not in DETECCION for e in elementos):
            raise ficha.ValorIlegible("elemento fuera de la lista")
        return sorted(set(elementos))
    if campo == "resultado_contramedidas":
        return ficha.de_la_lista(ficha._clave(limpio), RESULTADOS)
    if campo == "evidencia" or campo == "medidas":
        return ficha.interpretar(campo, limpio)
    return ficha.interpretar(campo, limpio)


def leer_respuesta(respuesta: dict[str, Any]) -> dict[str, Any]:
    """Sucesos y cifras de la respuesta del servicio, con los valores tipados. Lo que no sigue
    el formato se anota en «ilegibles». Lanza ficha.RespuestaInvalida si no trae la ficha."""
    if respuesta.get("stop_reason") not in {"end_turn", "stop_sequence"}:
        raise ficha.RespuestaInvalida(f"parada: {respuesta.get('stop_reason')}")
    textos = [b.get("text", "") for b in respuesta.get("content", []) if b.get("type") == "text"]
    try:
        bruta = json.loads("".join(textos))
    except ValueError as error:
        raise ficha.RespuestaInvalida("la salida no es JSON") from error
    if not isinstance(bruta, dict) or not {"sucesos", "cifras"} <= set(bruta):
        raise ficha.RespuestaInvalida("la salida no sigue el esquema")
    ilegibles: list[str] = []
    sucesos = []
    for numero, bruto in enumerate(bruta["sucesos"], 1):
        datos: dict[str, Any] = {}
        for dato in sorted(bruto.get("datos", []), key=lambda d: d.get("confianza", 0)):
            nombre = dato.get("campo")
            if nombre not in CAMPOS_SUCESO:
                continue
            try:
                valor = interpretar(nombre, str(dato.get("valor", "")))
            except ficha.ValorIlegible as error:
                ilegibles.append(f"suceso {numero}, {nombre}: {error}")
                continue
            datos[nombre] = {
                "valor": valor,
                "frase": dato.get("frase"),
                "confianza": dato.get("confianza"),
            }
        sucesos.append({
            "titulo_es": str(bruto.get("titulo_es", "")),
            "titulo_en": str(bruto.get("titulo_en", "")),
            "datos": datos,
        })  # fmt: skip
    cifras = []
    for numero, bruta_cifra in enumerate(bruta["cifras"], 1):
        # «7.000», «7,000» o «7 000» son siete mil: fuera el separador de miles.
        limpio = _MILES.sub("", str(bruta_cifra.get("valor", "")))
        try:
            valor = ficha.interpretar("drones", limpio)
        except ficha.ValorIlegible as error:
            ilegibles.append(f"cifra {numero}: {error}")
            continue
        cifras.append({**bruta_cifra, "valor": valor})
    return {"sucesos": sucesos, "cifras": cifras, "ilegibles": ilegibles}
