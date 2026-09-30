"""Ficha que devuelve el extractor: esquema de salida, instrucciones y petición.

La salida está obligada por el esquema (salida estructurada del servicio): una
lista de datos, cada uno con el nombre del campo (lista cerrada), su valor como
texto con un formato fijo, la fuente de la que sale, la frase de origen (25
palabras como máximo, copiada del texto) y la confianza, más los títulos.

Es una lista y no un objeto con un campo por dato porque el servicio rechaza
los esquemas grandes: admite como mucho 16 parámetros con tipos unión y limita
el tamaño de la gramática que compila; con 21 campos de cinco partes cada uno,
la gramática era demasiado grande. Así, además, solo salen los datos que las
fuentes dicen. El código interpreta cada valor (`leer_respuesta`) y lo valida
(`proceso/validacion_ficha.py`); lo que no se entiende se descarta con su motivo.

Las instrucciones van delante y marcadas para la caché del servicio; el
candidato va detrás. Con el modelo configurado, el servicio solo cachea bloques
de 4096 tokens o más, y las instrucciones son unas 2000: la marca queda puesta y
se aprovecha si el bloque crece o el modelo cambia. Rellenarlo hasta el mínimo
encarecería cada llamada que no acierte en la caché.
"""

import json
import re
from dataclasses import dataclass
from typing import Any

from proceso.noticias import sin_acentos

VERSION = "ficha/5"
# Una ficha con todos los datos ocupa unos 900 tokens; 1500 dejan margen sin pagar de más.
MAX_TOKENS_SALIDA = 1500
# Extraer no es redactar: con temperatura 0, la misma noticia da la misma ficha. Con la de
# por defecto, dos llamadas sobre la misma nota de Anenii Noi dieron fichas distintas.
TEMPERATURA = 0.0
# Un valor de lista escrito en otro idioma («confirmata») vale si comparte con uno solo de
# los valores todas sus letras menos las dos últimas.
LETRAS_TERMINACION = 2
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
# Pruebas físicas de que hubo un dron: el propio aparato explotó, dejó restos, cayó, fue
# derribado o se recuperó.
EVIDENCIAS = ("explosion", "restos", "caida", "derribo", "recuperado")
# Nivel del lugar del suceso, del más concreto al menos.
NIVELES = ("instalacion", "localidad", "region", "pais")
AUTORIDADES = (
    "policia", "aeropuerto", "navegacion_aerea", "fuerzas_armadas", "ministerio", "gobierno",
)  # fmt: skip
AFIRMACIONES = ("incidente", "drones", "sin_drones", "niega_incidente", "autoria")

BOOLEANOS = ("es_incidente", "objetivo_conocido", "dron_estatal", "entrada_exterior")
ENUMERADOS: dict[str, tuple[str, ...]] = {
    "tipo": TIPOS,
    "inicio_precision": PRECISIONES,
    "objetivo_categoria": CATEGORIAS,
    "presencia_dron": PRESENCIA,
    "cierre": CIERRE,
}
TEXTOS = ("inicio", "fin", "pais", "localidad", "objetivo_nombre", "modelo_dron")
RANGOS = ("drones", "cierre_minutos", "vuelos_desviados", "vuelos_cancelados", "vuelos_retrasados")
LISTAS: dict[str, tuple[str, ...]] = {
    "medidas": MEDIDAS, "origen_demostrado": ORIGEN, "evidencia": EVIDENCIAS,
}  # fmt: skip
CAMPOS: tuple[str, ...] = (
    *BOOLEANOS, *ENUMERADOS, *TEXTOS, "lugar_suceso", "lugar_nuevo", *RANGOS, *LISTAS,
)  # fmt: skip

ESQUEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["datos", "declaraciones", "titulo_es", "titulo_en"],
    "properties": {
        "datos": {
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
        "declaraciones": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "autoridad",
                    "pais",
                    "categoria",
                    "afirma",
                    "autor",
                    "fuente",
                    "frase",
                ],
                "properties": {
                    "autoridad": {"type": "string"},
                    "pais": {"type": "string"},
                    "categoria": {"enum": list(AUTORIDADES)},
                    "afirma": {"enum": list(AFIRMACIONES)},
                    "autor": {"type": "string"},
                    "fuente": {"type": "integer"},
                    "frase": {"type": "string"},
                },
            },
        },
        "titulo_es": {"type": "string"},
        "titulo_en": {"type": "string"},
    },
}
# Fichas guardadas antes de las declaraciones: se leen igual, sin ellas.
_OBLIGATORIAS = frozenset({"datos", "titulo_es", "titulo_en"})

INSTRUCCIONES = """Eres el extractor del Observatorio Europeo de Incidentes con Drones. Recibes \
las fuentes de un posible incidente con drones en Europa: para cada una, el medio, la fecha de \
publicación, el titular y las primeras frases. Devuelve una ficha con los hechos que dicen las \
fuentes, sin añadir nada que no digan.

Qué es un incidente: un dron visto, detectado, derribado o caído en Europa (fuera de Ucrania y \
de Rusia) cerca de un aeropuerto, una base militar, una central, un puerto u otra \
infraestructura, o que entra en el espacio aéreo de un país. No son incidentes: ataques de la \
guerra en Ucrania o en Rusia, espectáculos, reparto, agricultura, compras, ejercicios y pruebas \
anunciados, leyes y planes contra drones, ni noticias que solo hablan de drones en general.

La ficha es una lista de datos. Incluye solo los datos que alguna fuente dice; el dato \
es_incidente va siempre. Cada dato tiene:
- campo: su nombre.
- valor: el dato como texto, con el formato de su campo (abajo). Los valores de una lista \
(tipo, precisión, categoría, presencia, cierre, nivel, medidas, evidencia) van siempre \
escritos tal cual aparecen aquí, en español y sin acentos, aunque la fuente esté en otro \
idioma.
- fuente: el número de la fuente de la que sale (1, 2 o 3).
- frase: la frase de esa fuente que lo dice, copiada literalmente en su idioma, de 25 palabras \
como máximo.
- confianza: de 0 a 1, cuánto apoya la frase ese valor. Usa 0.9 o más solo si la frase lo dice \
expresamente; 0.5 a 0.8 si se deduce con claridad; menos de 0.5 si es una suposición.

Campos y formato del valor:
- es_incidente: true o false. Si es false, no hace falta ningún otro dato.
- tipo: interrupcion_aeroportuaria si un aeropuerto cierra, desvía, cancela o retrasa vuelos; \
incursion si un dron militar o de un Estado entró desde fuera del país y lo demuestra una \
autoridad o una prueba física (explosión, restos, caída, derribo o rastreo por radar); si no, \
sobrevuelo. Un avistamiento sin esa demostración nunca es incursión.
- inicio: cuándo empezó el incidente (no cuándo se publicó), en UTC, como AAAA-MM-DDTHH:MM o \
AAAA-MM-DD. Convierte la hora local del país a UTC. inicio_precision: minuto si la fuente da \
la hora exacta, hora si da una hora aproximada o una franja corta, dia si solo da el día o \
dice anoche, ayer, el lunes. fin: cuándo acabó, con el mismo formato.
- lugar_suceso: dónde ocurrió el suceso (donde se vio, cayó, explotó o fue derribado el dron), \
no otro lugar que nombre la noticia (la capital desde la que habla un ministro, el país de \
origen del dron, la sede del medio). Va siempre que es_incidente es true, como «nombre; nivel; \
país; región»: nombre, copiado de la frase tal como lo escribe la fuente (no el nombre del \
objetivo conocido si la fuente lo llama de otra forma); nivel, instalacion (aeropuerto, base, \
central, puerto), localidad (ciudad, pueblo, municipio, distrito), region (provincia, región, \
costa, frontera, una zona sin localidad concreta) o pais (si solo se sabe el país; el nombre es \
entonces el del país); país, su código ISO; región, la de primer nivel del país (provincia, \
región, condado, judeţ, raion) si se sabe sin duda, o vacío.
- pais: código ISO 3166-1 alfa-2 del país donde ocurrió el suceso, aunque sea otro que el del \
objetivo conocido. localidad: ciudad o municipio donde ocurrió.
- objetivo_conocido: true si el incidente ocurre en el objetivo conocido que se te indica; \
false si ocurre en otro sitio. objetivo_categoria (aeropuerto, base_militar, puerto, energia, \
presa, estadio, industrial, gubernamental u otra) y objetivo_nombre: la instalación afectada.
- lugar_nuevo: solo si objetivo_conocido es false y la fuente nombra la instalación, como \
«nombre; categoría; país; latitud; longitud», con coordenadas aproximadas en grados \
decimales. Si no sabes dónde está, no lo incluyas.
- drones: número de drones como «N» o «mínimo-máximo» («varios» es 2-10; «un enjambre», 5-50).
- presencia_dron: confirmada solo si hay restos, rastreo por radar o una autoridad afirma \
expresamente que era un dron; descartada si una autoridad dice que no lo era (un globo, un \
avión, una estrella); no_confirmada si solo hay avistamientos.
- dron_estatal: true si la fuente dice que el dron es militar o de un Estado (un dron ruso o \
ucraniano de la guerra lo es), nombra un modelo militar (Shahed, Geran, Gerbera) o dice que \
llevaba explosivos; false si dice que era de un particular.
- entrada_exterior: true si la fuente dice que el dron entró en el espacio aéreo del país desde \
fuera (desde otro país o desde el mar).
- evidencia: pruebas físicas del propio dron, separadas por comas: explosion (explotó), restos \
(se hallaron restos), caida (cayó o se estrelló), derribo (fue derribado), recuperado (se \
recuperó el aparato).
- cierre: si solo si la fuente dice que se cerró o se paralizó un aeropuerto o el espacio \
aéreo; no si dice que no se cerró o que las operaciones siguieron con normalidad. Si la fuente \
no habla de cierre, no incluyas el dato. cierre_minutos: cuánto duró, en minutos, como «N» o \
«mínimo-máximo».
- vuelos_desviados, vuelos_cancelados, vuelos_retrasados: «N» o «mínimo-máximo».
- modelo_dron: el modelo o tipo que nombra la fuente (Shahed, Gerbera, DJI Mavic).
- medidas: lo que hicieron las autoridades, separado por comas: cierre_espacio_aereo, patrulla, \
cazas, derribo, inhibicion.
- origen_demostrado: rastreo si una autoridad siguió al dron por radar desde otro país; restos si \
se encontraron restos que prueban el origen; separado por comas.
- declaraciones: aparte de los datos, una por cada declaración de una autoridad que cite la \
noticia (vacía si no hay). autoridad: su nombre («Københavns Politi»). pais: el código ISO \
del país de la autoridad (una autoridad de un país habla de lo que pasa en el suyo; un gobierno \
que dice que en su país no pasó nada no desmiente un suceso de otro país). categoria: policia, \
aeropuerto, navegacion_aerea (gestor de navegación aérea), fuerzas_armadas, ministerio o \
gobierno. afirma: incidente si dice que el incidente o el cierre ocurrió; drones si afirma \
expresamente que había drones (los vio ella misma, por radar o por restos); sin_drones si dice \
que no los hubo; niega_incidente si dice que no pasó nada; autoria si atribuye la autoría (a \
quién, en autor; vacío en los demás casos). fuente: el número de la fuente. frase: la frase \
literal de la declaración, de 25 palabras como máximo. Que la policía recibiera avisos o \
llamadas no es una afirmación suya: no la incluyas como incidente ni como drones.
- titulo_es y titulo_en: un título breve y neutro, en español y en inglés, con lugar y hecho \
(«Drones sobre el aeropuerto de Copenhague obligan a cerrarlo»), sin fecha. Van aparte de los \
datos y siempre.

Reglas: nunca inventes; si las fuentes discrepan, usa la más precisa y dilo con la confianza. \
No uses la fecha de publicación como fecha del incidente salvo que la fuente diga que ocurrió \
ese mismo día. No confundas un aeropuerto con la ciudad. Copia las frases tal cual.

Ejemplo 1.
Objetivo conocido: Aeropuerto de Copenhague (aeropuerto, DK, EKCH).
Fuente 1 (dr.dk, 2025-09-23T05:12Z, da). Titular: Droner over Københavns Lufthavn: lufthavnen \
lukket i fire timer. Texto: Københavns Lufthavn var lukket fra klokken 20.30 mandag aften, \
efter at der blev observeret tre til fire store droner. 31 fly blev omdirigeret.
Datos esperados: es_incidente «true» (fuente 1, «Københavns Lufthavn var lukket fra klokken \
20.30 mandag aften», 0.95); tipo «interrupcion_aeroportuaria»; inicio «2025-09-22T18:30» (20.30 \
en Copenhague es 18.30 UTC) con inicio_precision «minuto»; pais «DK»; lugar_suceso «Københavns \
Lufthavn; instalacion; DK; Hovedstaden»; objetivo_conocido «true»; \
drones «3-4»; presencia_dron «no_confirmada» (solo observación); cierre «si»; cierre_minutos \
«240»; vuelos_desviados «31».

Ejemplo 2.
Objetivo conocido: Aeropuerto de Múnich (aeropuerto, DE, EDDM).
Fuente 1 (br.de, 2025-10-03T06:40Z, de). Titular: Drohnensichtungen: Flughafen München stellt \
Betrieb ein. Texto: Wegen mehrerer Drohnensichtungen ist der Flugbetrieb am Münchner Flughafen \
am Donnerstagabend gegen 22 Uhr eingestellt worden. 17 Flüge konnten nicht starten, 15 \
landende Maschinen wurden umgeleitet. Die Bundespolizei suchte das Gelände ab.
Datos esperados: tipo «interrupcion_aeroportuaria»; inicio «2025-10-02T20:00» con precisión \
«hora» («gegen 22 Uhr»); drones «2-10» («mehrerer»); vuelos_cancelados «17»; vuelos_desviados \
«15»; cierre «si»; medidas «patrulla»; presencia_dron «no_confirmada».

Ejemplo 3.
Objetivo conocido: Base aérea de Kleine Brogel (base_militar, BE).
Fuente 1 (vrt.be, 2025-11-01T09:00Z, nl). Titular: Opnieuw drones gespot boven militaire \
basis Kleine Brogel. Texto: Vrijdagavond zijn opnieuw drones gezien boven de basis. Defensie \
bevestigt de waarnemingen maar kon de toestellen niet uitschakelen.
Datos esperados: tipo «sobrevuelo»; inicio «2025-10-31» con precisión «dia»; drones «2-10»; \
presencia_dron «no_confirmada» (Defensie confirma que hubo avistamientos, no que fueran drones).

Ejemplo 4.
Objetivo conocido: Aeropuerto de Rzeszów (aeropuerto, PL, EPRZ).
Fuente 1 (tvn24.pl, 2025-09-10T07:00Z, pl). Titular: Rosyjskie drony nad Polską zestrzelone. \
Texto: W nocy z wtorku na środę przestrzeń powietrzna Polski została naruszona przez rosyjskie \
drony. Dowództwo Operacyjne potwierdza, że część z nich zestrzelono. Lotnisko w Rzeszowie było \
zamknięte do rana.
Datos esperados: tipo «interrupcion_aeroportuaria» (el aeropuerto cerró; manda sobre la \
incursión); inicio «2025-09-09» con precisión «dia»; presencia_dron «confirmada» (el mando \
militar confirma que eran drones y los derribó); medidas «derribo»; origen_demostrado solo si \
la fuente dice que se siguieron desde fuera.

Ejemplo 5.
Objetivo conocido: Aeropuerto de Oslo (aeropuerto, NO, ENGM).
Fuente 1 (nrk.no, 2025-09-23T06:00Z, no). Titular: Politiet: Ingen droner ved Gardermoen likevel. \
Texto: Det som ble meldt som droner over Oslo lufthavn i natt, var trolig et fly, sier politiet.
Datos esperados: es_incidente «true»; tipo «sobrevuelo»; presencia_dron «descartada» con \
confianza 0.8 («trolig»).

Ejemplo 6.
Objetivo conocido: Aeropuerto de Barcelona (aeropuerto, ES, LEBL).
Fuente 1 (lavanguardia.com, 2025-06-01T10:00Z, es). Titular: El mejor espectáculo de drones del \
verano llega a Barcelona. Texto: Mil drones iluminarán la playa el sábado.
Datos esperados: solo es_incidente «false».

Ejemplo 7.
Objetivo conocido: Fundu Moldovei (otra, RO).
Fuente 1 (news.yam.md, 2026-09-30T08:00Z, ro). Titular: O dronă a survolat spațiul aerian al \
Moldovei și a explodat în raionul Anenii Noi. Texto: O dronă a pătruns în spațiul aerian al \
Republicii Moldova în dimineața zilei de 30 septembrie, prăbușindu-se și explodând ulterior în \
raionul Anenii Noi. Ministerul Apărării a confirmat incidentul.
Datos esperados: tipo «incursion» (entró desde fuera, explotó y el ministerio lo confirma); pais \
«MD»; lugar_suceso «Anenii Noi; localidad; MD; Anenii Noi»; objetivo_conocido «false» (el \
suceso no ocurre en Fundu Moldovei, que solo casa por el nombre del país); dron_estatal «true» \
(explotó: llevaba explosivos); entrada_exterior «true»; evidencia «caida, explosion»; \
presencia_dron «no_confirmada» si nadie afirma expresamente que era un dron; sin cierre (la \
fuente no habla de él). Declaración: Ministerul Apărării, MD, ministerio, afirma «incidente».

Ejemplo 8.
Objetivo conocido: Fuentes de Andalucía (otra, ES).
Fuente 1 (krone.at, 2026-05-19T09:00Z, de). Titular: Offenbar aus Ukraine: NATO-Jets \
schießen Militärdrohne über Estland ab.
Datos esperados: pais «EE»; lugar_suceso «Estland; pais; EE;» (solo se sabe el país); \
objetivo_conocido «false»; dron_estatal «true» (militar); entrada_exterior «true» (llegó desde \
Ucrania); evidencia «derribo»; tipo «incursion».
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
        "temperature": TEMPERATURA,
        "system": [{"type": "text", "text": INSTRUCCIONES, "cache_control": {"type": "ephemeral"}}],
        "output_config": {"format": {"type": "json_schema", "schema": ESQUEMA}},
        "messages": [{"role": "user", "content": contenido(objetivo, fuentes)}],
    }


class RespuestaInvalida(ValueError):
    pass


class ValorIlegible(ValueError):
    pass


_RANGO = re.compile(r"^\s*(\d+)\s*(?:[-–]\s*(\d+))?\s*$")


def _clave(texto: str) -> str:
    return "_".join(texto.strip().lower().split())


def interpretar(campo: str, texto: str) -> Any:
    """El valor tipado de un dato. Lanza ValorIlegible si no sigue el formato del campo."""
    limpio = texto.strip()
    if campo in BOOLEANOS:
        if limpio.lower() not in {"true", "false"}:
            raise ValorIlegible("no es true ni false")
        return limpio.lower() == "true"
    if campo in ENUMERADOS:
        # «No confirmada» y «no_confirmada» son el mismo valor.
        return de_la_lista(_clave(sin_acentos(limpio)), ENUMERADOS[campo])
    if campo in RANGOS:
        m = _RANGO.match(limpio)
        if m is None:
            raise ValorIlegible("no es un número ni un rango")
        minimo = int(m[1])
        return {"min": minimo, "max": int(m[2]) if m[2] else minimo}
    if campo in LISTAS:
        elementos = [_clave(e) for e in limpio.split(",") if e.strip()]
        if any(e not in LISTAS[campo] for e in elementos):
            raise ValorIlegible("elemento fuera de la lista")
        return sorted(set(elementos))
    if campo == "lugar_suceso":
        return _lugar_suceso(limpio)
    if campo == "lugar_nuevo":
        partes = [p.strip() for p in limpio.split(";")]
        if len(partes) != len(("nombre", "categoria", "pais", "lat", "lon")):
            raise ValorIlegible("lugar sin sus cinco partes")
        nombre, categoria, pais, lat, lon = partes
        categoria = _clave(categoria)
        if categoria not in CATEGORIAS:
            raise ValorIlegible("categoría fuera de la lista")
        try:
            return {"nombre": nombre, "categoria": categoria, "pais": pais,
                    "lat": float(lat), "lon": float(lon)}  # fmt: skip
        except ValueError as error:
            raise ValorIlegible("coordenadas no numéricas") from error
    return limpio


def de_la_lista(clave: str, valores: tuple[str, ...]) -> str:
    """El valor de la lista, también con otra terminación («confirmata», «localitate» no)."""
    if clave in valores:
        return clave
    parecidos = [
        v for v in valores
        if len(clave) >= len(v) - LETRAS_TERMINACION
        and clave[: len(v) - LETRAS_TERMINACION] == v[: len(v) - LETRAS_TERMINACION]
    ]  # fmt: skip
    if len(parecidos) != 1:
        raise ValorIlegible("fuera de la lista")
    return parecidos[0]


def _lugar_suceso(texto: str) -> dict[str, str]:
    """«nombre; nivel; país; región», con la región vacía o ausente."""
    partes = [p.strip() for p in texto.split(";")]
    sin_region = len(("nombre", "nivel", "pais"))
    if len(partes) == sin_region:
        partes.append("")
    if len(partes) != sin_region + 1 or not partes[0]:
        raise ValorIlegible("lugar del suceso sin sus partes")
    nombre, nivel, pais, region = partes
    nivel = de_la_lista(_clave(sin_acentos(nivel)), NIVELES)
    return {"nombre": nombre, "nivel": nivel, "pais": pais.upper(), "region": region}


def leer_respuesta(respuesta: dict[str, Any]) -> dict[str, Any]:
    """La ficha de la respuesta del servicio, un dato por campo con su valor tipado.

    Si un campo sale dos veces, vale el de más confianza. Un valor que no sigue el
    formato de su campo se anota en «ilegibles» y no pasa. Lanza RespuestaInvalida si
    la respuesta no trae la ficha.
    """
    if respuesta.get("stop_reason") not in {"end_turn", "stop_sequence"}:
        raise RespuestaInvalida(f"parada: {respuesta.get('stop_reason')}")
    textos = [b.get("text", "") for b in respuesta.get("content", []) if b.get("type") == "text"]
    try:
        bruta = json.loads("".join(textos))
    except ValueError as error:
        raise RespuestaInvalida("la salida no es JSON") from error
    if not isinstance(bruta, dict) or not set(bruta) >= _OBLIGATORIAS:
        raise RespuestaInvalida("la salida no sigue el esquema")
    ficha: dict[str, Any] = {"titulo_es": bruta["titulo_es"], "titulo_en": bruta["titulo_en"]}
    ilegibles: list[str] = []
    for dato in sorted(bruta["datos"], key=lambda d: d.get("confianza", 0)):
        nombre = dato.get("campo")
        if nombre not in CAMPOS:
            continue
        try:
            valor = interpretar(nombre, str(dato.get("valor", "")))
        except ValorIlegible as error:
            ilegibles.append(f"{nombre}: {error}")
            continue
        ficha[nombre] = {
            "valor": valor,
            "fuente": dato.get("fuente"),
            "frase": dato.get("frase"),
            "confianza": dato.get("confianza"),
        }
    ficha["declaraciones"] = [
        d for d in bruta.get("declaraciones", [])
        if isinstance(d, dict) and d.get("categoria") in AUTORIDADES
        and d.get("afirma") in AFIRMACIONES and isinstance(d.get("autoridad"), str)
    ]  # fmt: skip
    ficha["ilegibles"] = ilegibles
    return ficha
