"""Auditoría de las fichas vigentes: cuántas tienen cada fallo conocido, con sus identificadores.

Solo lee y no llama a nada: las mismas reglas que corrigen las fichas, pasadas sobre todas. Corre
en cada control de las fichas (recogida/control_fichas.escribir_estado); sus recuentos salen en
el resumen diario y, si alguno sube respecto al día anterior, el aviso de silencio lo cuenta
(recogida/silencio.py). A mano: `python -m recogida.auditoria_fichas`.

- **A, cabecera**: la cabecera de la ficha en la web (el nombre de la instalación o, si no la
  hay, el titular: web/src/componentes/FichaIncidente.tsx) tiene menos de 3 palabras, o un
  objetivo «otra» se llama como la localidad del suceso (EODI-2026-00648, «Józefów · Otro
  lugar»).
- **B, instalación no reconocida**: sin objetivo o con objetivo «otra», y el titular nombra un
  aeropuerto, una base, un puerto o una central (EODI-2026-00131, «Berlín · Otro lugar»).
- **C, cita de autoridad vacía**: una fuente de autoridad cuya cita es solo quién habla y el
  verbo de decir («… Komendy Stołecznej Policji przekazała»: proceso/declaraciones.sin_afirmacion).
- **D, titular sin respaldo**: ninguna cita guardada nombra lo que afirma el titular
  (proceso/cita_titular.respalda), salvo los justificados a mano.
- **E, presencia sin base**: dron confirmado sin ninguna autoridad que lo atribuya a drones ni
  documento ni pruebas físicas de una autoridad, ni revisión a mano; o sin confirmar con una
  autoridad que sí lo atribuye; o, en lo que publica la web (proceso/coherencia.py), una misma
  fuente da un paso que confirma y otro que desmiente (EODI-2025-00124, Sofía).
- **F, lugar**: un buque como lugar, un suceso en el mar en la zona «interior», o la fecha de
  publicación como fecha del suceso cuando una fuente escribe otro día.
- **G, nombres**: un punto anterior sin nombre (`nombres.anteriores` con null), o un titular
  publicado que escribe una ciudad de otra forma que la ficha (EODI-2026-00050: «Alexandrópolis»
  frente a «Alejandrópolis»).
- **H, instalación homónima**: el objetivo no casa con el tipo del suceso (una interrupción
  aeroportuaria con un objetivo que no es un aeropuerto ni una base) o la instalación del
  nomenclátor que nombra está a más de 30 km de la localidad de la ficha (EODI-2026-00077: el
  estadio «Васил Левски» de Karlovo por el aeropuerto de Sofía).
- **I, alias genérico**: el objetivo se llama solo con palabras corrientes («Base navale»), o
  las fuentes de la ficha nombran su instalación solo con un nombre o una ciudad genéricos y
  nunca con uno propio (EODI-2025-00174: «Drohnen-Alarm im Norden», «en el norte», por el
  aeródromo de Norden-Norddeich; proceso/noticias.generico).
- **J, hora local como UTC**: el inicio publicado, leído como UTC o con el desfase del otro
  horario del año, es una hora que escribe una frase de sus fuentes (cualquier hora, nombre o no
  el dron, con 10 minutos de margen) y ninguna escribe la que le toca en la zona del suceso ese
  día (EODI-2025-00007: «gegen 19.30 Uhr» en Bremen en noviembre son las 18:30 UTC, y la ficha
  daba las 19:30 UTC; EODI-2025-00178: «12.05 val.» en Vilna el 29 de octubre de 2025, ya en
  hora de invierno, publicado como 09:05 UTC con el desfase de verano; proceso/fechas.hora_en_utc).
  No cuenta una frase que da la hora en UTC o GMT.
- **K, dato que oscila**: el mismo dato de una ficha vuelve, en las últimas 48 horas, a un valor
  que ya había dejado (A → B → A, o dos reglas que lo cambian desde el mismo valor y se queda el
  viejo) 3 veces o más: dos reglas que se pisan en cada recogida (EODI-2025-00378, el titular,
  22-23 de octubre de 2026). Lo lee de la tabla de motivos y de los cambios guardados
  (`Almacen.cambios_desde`); un arreglo deshecho una sola vez no cuenta.
- **L, autoridad perdida al unir**: la ficha que queda de una unión no tiene ninguna fuente de
  autoridad y alguna de las fichas unidas en ella sí la tenía (EODI-2026-00108, Auvere: la
  declaración de la KAPO se quedó en la unida EODI-2026-00333 y la ficha pasó a «posible dron»;
  recogida/declaraciones_oficiales.con_declaraciones_del_unido).
- **M, lugar revisado**: el lugar de una ficha con una revisión a mano del lugar no es el que fija
  la revisión: otro nivel u otro punto que el revisado, o, si la revisión da solo la localidad,
  un punto lejos de ella (EODI-2026-00278, Dublín; proceso/decidir.en_la_localidad_revisada).
- **N, noticia retrospectiva**: el inicio de la ficha es la fecha de publicación y una de sus
  fuentes nombra otro mes (EODI-2026-00134 y EODI-2026-00663, noticias de octubre sobre los drones
  de Leipzig de septiembre, y EODI-2026-00108, Auvere en marzo): la noticia cuenta un suceso
  anterior y la ficha no casa con la del suceso por la fecha. También un pasado lejano («last
  month», «letzten Monat»); «mai» en rumano es «más», no mayo. Desde el 25 de octubre de 2026 es
  la regla que retiene la ficha nueva hasta que el experto da la fecha o la une a la del suceso
  (proceso/fechas.retrospectiva): lo que marca es lo ya publicado antes o sin decidir.
- **O, fin sin frase que lo respalde**: la ficha publica una hora de fin (o una fuente con una
  afirmación de fin) que ninguna frase escribe, ni como hora ni como duración desde el inicio
  (proceso/fechas.fin_escrito). EODI-2025-00154 publicaba las 23:00 UTC en Copenhague por «gut
  vier Stunden» desde las 18:30 y EODI-2026-00112 las 20:03 UTC por «până la ora 22:03», que en
  Moldavia en marzo son las 19:03 UTC. Desde el 26 de octubre de 2026 el extractor no guarda un
  fin sin frase (proceso/incidentes._fin_con_frase) y la exportación no lo publica.
- **S, día publicado distinto del día local**: el inicio es solo el día y no es el día local del
  lugar del suceso: el motivo de su inicio escribe una hora local de otro día («01:30 hora búlgara
  del 13»), o una afirmación del inicio con su hora en UTC cae otro día en la hora local y ese día
  UTC es el publicado (EODI-2026-00512, el ataque de hacia la 01:30 hora de Bulgaria del
  13/10/2026, publicado el 12 por sus 22:30 UTC; proceso/fechas.dia_local).
- **P, presencia rebajada sin cierre**: la presencia es «no acreditada» o «descartada» y su
  historial no dice qué autoridad la rebajó ni cuándo (no hay paso con ese valor, o le falta la
  fecha o quién lo declara). EODI-2025-00228, Aalborg: rebajada con una revisión a mano, sin el
  cierre de la investigación de la policía de Jutlandia del Norte (25 de junio de 2026), y cinco
  descartadas por la extracción con la declaración de la autoridad solo dentro de una noticia
  (Vilna, Geilenkirchen, Múnich, Sofía). Se completa con su rectificación oficial
  (configuracion/rectificaciones_oficiales.json, docs/rectificaciones.md).
- **Q, ninguna fuente legible**: todas las fuentes de la ficha tienen el original caído y ninguna
  copia archivada (tabla copias_archivadas, recogida/archivo_web.py): nadie puede leer ya lo que
  la sostiene. EODI-2025-00278 (Taraclia, febrero de 2025): su única fuente, news.yam.md, daba
  404 y no tenía copia; se le añadió la noticia de adevarul.ro con la declaración de la policía
  (configuracion/incidentes_revisados.json, «citas»). Una fuente sin resultado del archivo cuenta
  como legible. Sin la tabla (las pruebas), no se mira.
- **T, titular incoherente con la presencia**: el titular, en español o en inglés, afirma el dron
  y la presencia no está confirmada, o lo da como posible con el dron confirmado
  (proceso/titulares.coherente). EODI-2026-00541 (28 de octubre de 2026): «Un dron alcanza un
  petrolero» quedó sin «posible» mientras la ficha tenía el dron de otro suceso.
- **U, concordancia del dron**: el titular en español escribe el dron en femenino («Una dron
  entra…», EODI-2026-00698; «Una posible dron…», EODI-2026-00322; proceso/titulares.concordar).
- **V, unión de fichas marcadas como relacionadas**: una ficha unida en otra que una revisión dio
  por suceso distinto (separación con «distintos» o sección `distintos` de
  configuracion/incidentes_revisados.json) o que el experto dio por distinta en el control, sin
  una unión a mano posterior (`unir`). EODI-2026-00538 (29 de octubre de 2026): la regla la unió
  en EODI-2026-00541 (docs/sucesos_mezclados.md).
- **W, dato decidido perdido en una reextracción**: en las últimas 48 horas, una extracción nueva
  de su candidato le quitó a la ficha un dato que tenía decidido con la frase de una fuente que
  sigue teniendo (el día y la hora, el número de drones, el cierre o el lugar;
  proceso/decididos.py) y la ficha no lo ha recuperado. EODI-2026-00066 (29 de octubre de 2026):
  el 13 de septiembre («Sunday, September 13th») pasó a la fecha de publicación de la noticia.
  Necesita las fechas de las extracciones (`Almacen.fechas_extraccion`); sin ellas no se mira.
"""

import json
import re
from collections import Counter
from collections.abc import Callable, Iterable
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from esquema import Documento
from proceso import (
    buques,
    cita_titular,
    coherencia,
    decidir,
    declaraciones,
    fechas,
    incidentes,
    nombres_lugar,
    noticias,
    rectificaciones,
    textos_dron,
    titulares,
)
from proceso.presencia import (
    atribuida_por_autoridad,
    documento_oficial_decide,
    presencias_revisadas,
    pruebas_fisicas_confirmadas,
)
from proceso.ubicacion import CATEGORIA_LUGAR

COMPROBACIONES = (
    "A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L", "M", "N", "O", "P", "Q", "R",
    "S", "T", "U", "V", "W",
)  # fmt: skip
NOMBRES = {
    "A": "cabecera de una palabra",
    "B": "instalación no reconocida",
    "C": "cita de autoridad vacía",
    "D": "titular sin respaldo",
    "E": "presencia sin base",
    "F": "lugar",
    "G": "nombres",
    "H": "instalación homónima",
    "I": "alias genérico",
    "J": "hora local como UTC",
    "K": "dato que oscila",
    "L": "autoridad perdida al unir",
    "M": "lugar revisado",
    "N": "noticia retrospectiva",
    "O": "fin sin frase que lo respalde",
    "P": "presencia rebajada sin cierre",
    "Q": "ninguna fuente legible",
    "R": "referencia",
    "S": "día publicado distinto del día local",
    "T": "titular incoherente con la presencia",
    "U": "concordancia del dron",
    "V": "unión de fichas marcadas como relacionadas",
    "W": "dato decidido perdido en una reextracción",
}
MIN_PALABRAS_CABECERA = 3
# Lo que nombra una instalación en un titular (en español o en inglés, las dos versiones).
_INSTALACION = re.compile(
    r"\b(?:aeropuerto|aeródromo|airport|airfield|aerodrome|base(?: aérea| militar| naval)?|"
    r"air ?base|naval base|military base|puerto|port|harbou?r|central (?:nuclear|eléctrica|"
    r"térmica)|(?:nuclear |power )plant|power station)\b",
    re.IGNORECASE,
)


def palabras(texto: str) -> int:
    return len(str(texto or "").split())


def _clave(texto: str) -> str:
    return nombres_lugar.clave(str(texto or ""))


def instalacion_de_verdad(incidente: Documento) -> bool:
    """El objetivo es una instalación con categoría propia (no «otra»): solo entonces la cabecera
    de la ficha es su nombre."""
    objetivo = incidente.get("objetivo") or {}
    return bool(objetivo.get("nombre")) and objetivo.get("categoria") not in (None, "otra")


def objetivo_es_la_localidad(incidente: Documento) -> bool:
    """Un objetivo «otra» que se llama como la localidad del suceso: no es una instalación."""
    return incidentes.objetivo_es_la_localidad(
        incidente.get("objetivo"), incidente.get("lugar") or {}
    )


def cabecera(incidente: Documento, idioma: str = "es") -> str:
    """La cabecera de la ficha en la web: el nombre de la instalación o, si no, el titular."""
    if instalacion_de_verdad(incidente):
        escrito = (_nombres(incidente).get("objetivo") or {}).get(idioma)
        return str(escrito or incidente["objetivo"]["nombre"])
    return str((incidente.get("titulo") or {}).get(idioma, ""))


def _nombres(incidente: Documento) -> Documento:
    """El campo `nombres` que publica la exportación (proceso/nombres_lugar.nombres_publicos)."""
    if incidente.get("nombres") is not None:
        return dict(incidente["nombres"])
    try:
        return nombres_lugar.nombres_publicos(incidente)
    except (KeyError, TypeError, ValueError):
        return {}


def _a(incidente: Documento) -> bool:
    # El nombre de una instalación puede ser corto («RAF Lakenheath», «Karup Airport»); de una
    # palabra, no («Józefów»). Un titular, de 3 palabras como mínimo.
    minimo = 2 if instalacion_de_verdad(incidente) else MIN_PALABRAS_CABECERA
    return objetivo_es_la_localidad(incidente) or any(
        palabras(cabecera(incidente, i)) < minimo for i in ("es", "en")
    )


def _b(incidente: Documento) -> bool:
    objetivo = incidente.get("objetivo") or {}
    if objetivo.get("categoria") not in (None, "otra"):
        return False
    # El objetivo revisado a mano con su cita (EODI-2025-00378: de la base de Borcea solo
    # despegaron los F-16) no es una instalación sin reconocer.
    if "objetivo" in decidir.revisiones(incidente):
        return False
    return any(_INSTALACION.search(str(t)) for t in (incidente.get("titulo") or {}).values())


def citas_vacias(incidente: Documento) -> list[str]:
    """Las fuentes de autoridad cuya cita no dice nada: solo quién habla y el verbo de decir."""
    return [
        f["id"] for f in incidente.get("fuentes", [])
        if declaraciones.cita_vacia(f)
    ]  # fmt: skip


def _c(incidente: Documento) -> bool:
    return bool(citas_vacias(incidente))


def _d(incidente: Documento) -> bool:
    return incidente["id"] not in cita_titular.justificados() and not cita_titular.respalda(
        incidente
    )


def misma_fuente_en_pasos_opuestos(incidente: Documento) -> bool:
    """En lo publicado, una misma fuente da un paso que confirma (o atribuye) y otro que
    desmiente."""
    pasos = coherencia.coherente(incidente)["estado"]["historial"]
    confirman = {p.get("fuente_id") for p in pasos if p["estado"] in ("confirmado", "atribuido")}
    desmienten = {p.get("fuente_id") for p in pasos if p["estado"] == "desmentido"}
    return bool((confirman & desmienten) - {None})


def _e(incidente: Documento) -> bool:
    if misma_fuente_en_pasos_opuestos(incidente):
        return True
    presencia = incidente.get("presencia_dron")
    if incidente["id"] in presencias_revisadas():
        return False
    atribuida = atribuida_por_autoridad(incidente) or documento_oficial_decide(incidente)
    if presencia == "confirmada":
        return not atribuida and not pruebas_fisicas_confirmadas(incidente)
    return presencia == "no_confirmada" and atribuida_por_autoridad(incidente)


def _fecha_de_publicacion(incidente: Documento) -> bool:
    """La ficha tomó la fecha de publicación y una fuente escribe otro día del suceso."""
    tiempo = incidente.get("tiempo") or {}
    if (tiempo.get("origen_inicio") or {}).get("tipo") != "publicacion":
        return False
    dia = str(tiempo["inicio"]["valor"])[:10]
    for fuente in incidente.get("fuentes", []):
        try:
            publicacion = datetime.fromisoformat(
                str(fuente["fecha"]["valor"]).replace("Z", "+00:00")
            )
        except (KeyError, ValueError):
            continue
        zona = fechas.zona(fuente.get("pais") or incidente["lugar"].get("pais")) or ZoneInfo("UTC")
        frase = str(fuente.get("frase_origen") or "")
        propia = publicacion.astimezone(zona).date()
        for lectura in fechas.leer(frase, publicacion, zona, fuente.get("idioma")):
            # La fecha de la propia nota («– DW – 10.11.2025», EODI-2025-00125) no es la del
            # suceso.
            if lectura.origen == "explicita" and lectura.dia not in (date.fromisoformat(dia),
                                                                       propia):  # fmt: skip
                return True
    return False


def _f(incidente: Documento) -> bool:
    textos = buques.textos_de(incidente)
    lugar = incidente.get("lugar") or {}
    if incidentes.lugar_sin_buque(lugar, textos) is not lugar:
        return True
    zona = incidente.get("zona") or {}
    if zona.get("grupo") == "interior" and incidentes.alcanzado_en_el_mar(incidente):
        return True
    return _fecha_de_publicacion(incidente)


def _g(incidente: Documento) -> bool:
    nombres = _nombres(incidente)
    if any(a is None for a in nombres.get("anteriores") or []):
        return True
    # El titular como lo publica la exportación (exportacion/geojson.py), con los nombres ya en
    # la forma de cada idioma: lo que queda de otra forma es lo que se ve en la web.
    pais = (incidente.get("lugar") or {}).get("pais")
    return any(
        nombres_lugar.formas_ajenas(str(texto), idioma, pais)
        for idioma, texto in nombres_lugar.titulo_corregido(incidente).items()
        if idioma in nombres_lugar.IDIOMAS
    )


# Lo lejos que puede estar la instalación del objetivo de la localidad de la ficha.
DISTANCIA_OBJETIVO_KM = 30.0
# Lo que puede ser el objetivo de una interrupción aeroportuaria.
OBJETIVOS_AEROPORTUARIOS = frozenset({"aeropuerto", "base_militar"})


def _instalacion_del_objetivo(incidente: Documento) -> noticias.Lugar | None:
    """La instalación del nomenclátor que nombra el objetivo: la de su OACI o la única del país
    con ese nombre."""
    objetivo = incidente.get("objetivo") or {}
    nom = noticias.nomenclator()
    if objetivo.get("oaci") and (sitio := nom.lugares.get(str(objetivo["oaci"]))) is not None:
        return sitio
    nombre = noticias.normalizar(str(objetivo.get("nombre") or ""))
    pais = (incidente.get("lugar") or {}).get("pais")
    hallados = [
        s
        for s in nom.lugares.values()
        if s.pais == pais and s.tipo in CATEGORIA_LUGAR and noticias.normalizar(s.nombre) == nombre
    ]
    return hallados[0] if nombre and len(hallados) == 1 else None


def _h(incidente: Documento) -> bool:
    objetivo = incidente.get("objetivo") or {}
    categoria = objetivo.get("categoria")
    if categoria in (None, "otra"):
        return False
    if (
        incidente.get("tipo") == "interrupcion_aeroportuaria"
        and categoria not in OBJETIVOS_AEROPORTUARIOS
    ):
        return True
    lugar = incidente.get("lugar") or {}
    sitio = _instalacion_del_objetivo(incidente)
    if sitio is None or not lugar.get("localidad"):
        return False
    nom = noticias.nomenclator()
    localidades = [
        nom.lugares[i]
        for i in noticias.localidades_declinadas(str(lugar["localidad"]), nom)
        if i in nom.lugares and nom.lugares[i].pais == lugar.get("pais")
    ]
    return len(localidades) == 1 and (
        noticias.distancia_km(localidades[0], sitio)
        > DISTANCIA_OBJETIVO_KM + localidades[0].radio_km
    )


def _i(incidente: Documento) -> bool:
    objetivo = incidente.get("objetivo") or {}
    if objetivo.get("categoria") in (None, "otra"):
        return False
    nombre = noticias.normalizar(str(objetivo.get("nombre") or ""))
    if nombre and noticias.generico(nombre):
        return True
    sitio = _instalacion_del_objetivo(incidente)
    if sitio is None:
        return False
    # Lo que escriben las fuentes y el titular; no el «suceso», que copia el nombre casado.
    textos = [
        *(incidente.get("titulo") or {}).values(),
        *(f.get("frase_origen") or "" for f in incidente.get("fuentes") or []),
    ]
    normal = " " + " ".join(noticias.normalizar(str(t)) for t in textos if t) + " "
    nombres = {noticias.normalizar(n) for n in (sitio.nombre, *sitio.alias, *sitio.ciudades)}
    nombrados = [n for n in nombres if n and f" {n} " in normal]
    return bool(nombrados) and all(noticias.generico(n) for n in nombrados)


# Una frase que da la hora en UTC no dice nada de la hora local («2230-2245GMT»).
_EN_UTC = re.compile(r"(?<![a-z])(?:utc|gmt|zulu)(?![a-z])|\d{2}:?\d{2} ?z\b", re.IGNORECASE)


def _j(incidente: Documento) -> bool:
    """La hora de las citas frente al inicio publicado: marca la ficha cuyo inicio, leído como
    UTC (o con el desfase del otro horario del año: fechas.desfases_errados), es una hora que
    escribe una frase de sus fuentes, con 10 minutos de margen, si ninguna frase escribe la hora
    local que de verdad le corresponde en la zona del suceso ese día. Cualquier hora de la frase,
    nombre o no el dron: «vers 21h20» en Bruselas (EODI-2025-00335) publicado como 21:00 UTC."""
    inicio = (incidente.get("tiempo") or {}).get("inicio") or {}
    precision = inicio.get("precision")
    if precision not in {"minuto", "hora"}:
        return False
    lugar = incidente.get("lugar") or {}
    punto = lugar.get("punto") or {}
    zona = fechas.zona(lugar.get("pais"), punto.get("lat"), punto.get("lon"))
    if zona is None:
        return False
    valor = datetime.fromisoformat(str(inicio["valor"]).replace("Z", "+00:00"))
    frases = [str(f.get("frase_origen") or "") for f in incidente.get("fuentes") or []]
    escritas = {
        h for f in frases if not _EN_UTC.search(f) for h in textos_dron.horas_escritas(f)
    }  # fmt: skip
    margen = fechas.MARGEN_FIN
    local = valor.astimezone(zona)
    if any(fechas.misma_hora(local, h, precision, margen) for h in escritas):
        return False
    return any(
        fechas.misma_hora(valor + desfase, h, precision, margen)
        for desfase in fechas.desfases_errados(valor, zona)
        for h in escritas
    )


def _m(incidente: Documento) -> bool:
    revision = decidir.revision_de(incidente, "lugar")
    if revision is None or revision.get("valor") is None:
        return False
    valor, lugar = revision["valor"], incidente.get("lugar") or {}
    if "punto" in valor:
        return any(lugar.get(c) != valor[c] for c in ("nivel", "punto") if c in valor)
    return decidir.en_la_localidad_revisada(lugar) != lugar


def _n(incidente: Documento) -> bool:
    # La misma regla que retiene las fichas nuevas hasta que el experto da la fecha
    # (proceso/fechas.retrospectiva, recogida/control_fichas.retrospectivas).
    return fechas.retrospectiva(incidente) is not None


def _o(incidente: Documento) -> bool:
    # Lo que publica la web: un fin (o una afirmación de fin) que ninguna frase de sus fuentes
    # escribe (proceso/fechas.fines_sin_frase). La exportación ya los quita
    # (fechas.sin_fin_sin_frase); esto avisa si algo los vuelve a publicar.
    from exportacion.geojson import con_afirmaciones

    publicado = con_afirmaciones(incidente)
    return publicado is not None and fechas.fines_sin_frase(publicado)


def _p(incidente: Documento) -> bool:
    # La rebajada cuyo historial no dice quién la rebajó ni cuándo (proceso/rectificaciones).
    valor = incidente.get("presencia_dron")
    if valor not in rectificaciones.RECTIFICADOS:
        return False
    pasos = rectificaciones.pasos_de_valor(incidente)
    ultimo = pasos[-1] if pasos else {}
    quien = ultimo.get("quien") or {}
    return not (
        ultimo.get("valor") == valor
        and (ultimo.get("fecha") or {}).get("valor")
        and quien.get("es")
        and quien.get("en")
    )


def sin_fuente_legible(incidente: Documento, copias: dict[str, Documento]) -> bool:
    """Q: todas sus fuentes tienen el original caído y ninguna tiene copia archivada (`copias`,
    lo vigente de cada enlace: Almacen.copias_archivadas)."""
    fuentes = incidente.get("fuentes") or []

    def ilegible(fuente: Documento) -> bool:
        copia = copias.get(str(fuente.get("enlace", ""))) or {}
        return bool(copia.get("caido")) and not copia.get("copia")

    return bool(fuentes) and all(ilegible(f) for f in fuentes)


# «01:30 hora búlgara del 13», «02:20 hora de Rumanía del 6»: una hora local con su día.
_HORA_LOCAL_DEL_DIA = re.compile(r"\b\d{1,2}[:.]\d{2} hora\b[^()]*?\bdel (\d{1,2})\b")


def _s(incidente: Documento) -> bool:
    """El inicio es solo el día y no es el día local del lugar: el motivo del inicio da una hora
    local de otro día, o una afirmación del inicio en UTC cae otro día en la hora local y su día
    UTC es el publicado (proceso/fechas.dia_local)."""
    tiempo = incidente.get("tiempo") or {}
    inicio = tiempo.get("inicio") or {}
    if inicio.get("precision") != "dia":
        return False
    publicado = str(inicio["valor"])[:10]
    motivo = str((tiempo.get("origen_inicio") or {}).get("motivo") or "")
    if any(int(m.group(1)) != int(publicado[8:]) for m in _HORA_LOCAL_DEL_DIA.finditer(motivo)):
        return True
    for afirmacion in incidente.get("afirmaciones", []):
        valor = str(afirmacion.get("valor") or "") if afirmacion.get("campo") == "inicio" else ""
        if "T" in valor and valor.endswith("Z") and valor[:10] == publicado:
            local = fechas.dia_local({"valor": valor, "precision": "minuto"}, incidente)
            if local != publicado:
                return True
    return False


def _t(incidente: Documento) -> bool:
    presencia = incidente.get("presencia_dron")
    return any(
        not titulares.coherente(str(texto), presencia, idioma)
        for idioma, texto in (incidente.get("titulo") or {}).items()
        if idioma in ("es", "en")
    )


def _u(incidente: Documento) -> bool:
    return not titulares.concuerda(str((incidente.get("titulo") or {}).get("es") or ""), "es")


_REGLAS: dict[str, Callable[[Documento], bool]] = {
    "A": _a, "B": _b, "C": _c, "D": _d, "E": _e, "F": _f, "G": _g, "H": _h, "I": _i, "J": _j,
    "M": _m, "N": _n, "O": _o, "P": _p, "S": _s, "T": _t, "U": _u,
}  # fmt: skip


def _con_autoridad(documento: Documento) -> bool:
    return any(f.get("es_autoridad") for f in documento.get("fuentes", []))


def autoridad_perdida(documentos: list[Documento]) -> list[str]:
    """Las fichas vigentes sin ninguna fuente de autoridad con alguna unida en ellas que sí la
    tenía (L). Sigue la cadena de uniones hasta la que queda."""
    por_id = {str(d["id"]): d for d in documentos}

    def final(documento: Documento) -> Documento | None:
        vistos: set[str] = set()
        while "fusionado_en" in documento and documento["id"] not in vistos:
            vistos.add(documento["id"])
            siguiente = por_id.get(str(documento["fusionado_en"]))
            if siguiente is None:
                return None
            documento = siguiente
        return documento if incidentes.activo(documento) else None

    salida: set[str] = set()
    for documento in documentos:
        if "fusionado_en" not in documento or not _con_autoridad(documento):
            continue
        destino = final(documento)
        if destino is not None and not _con_autoridad(destino):
            salida.add(str(destino["id"]))
    return sorted(salida)


def _unidas_a_mano() -> list[frozenset[str]]:
    datos = json.loads(incidentes.REVISADOS.read_text(encoding="utf-8"))
    return [frozenset(g["registros"]) for g in datos.get("unir", [])]


def uniones_marcadas(
    documentos: list[Documento],
    del_experto: frozenset[frozenset[str]] = frozenset(),
    a_mano: Iterable[frozenset[str]] = (),
) -> list[str]:
    """Las uniones vigentes (absorbido→destino) entre fichas que una revisión dio por distintas
    (separación con «distintos» o sección `distintos`) o que el experto dio por distintas en el
    control, salvo las que una revisión unió a mano (sección `unir`, o `a_mano`: las fusiones
    revisadas a mano de `incidentes.uniones_a_mano`) (V)."""
    a_mano = [*_unidas_a_mano(), *a_mano]
    por_id = {str(d["id"]): d for d in documentos}
    salida = []
    for documento in documentos:
        destino = por_id.get(str(documento.get("fusionado_en")))
        if destino is None:
            continue
        propio = {k: v for k, v in documento.items() if k != "fusionado_en"}
        par = frozenset((str(documento["id"]), str(destino["id"])))
        if any(par <= grupo for grupo in a_mano):
            continue
        if incidentes.no_se_unen(propio, destino, del_experto):
            salida.append(f"{documento['id']}→{destino['id']}")
    return sorted(salida)


HORAS_OSCILA = 48
MIN_VUELTAS = 3
# Lo que no es un dato de la ficha: lo del control, el motivo del cambio y lo que se calcula de
# los datos para publicarlos.
_NO_SON_DATOS = frozenset({"control", "motivo", "nombres", "procedencia", "id"})


def oscilan(cambios: Iterable[Documento]) -> dict[str, list[str]]:
    """{incidente: [datos]} que vuelven a un valor que ya habían dejado `MIN_VUELTAS` veces o más
    (los cambios, por orden, de `Almacen.cambios_desde`). El mismo cambio apuntado dos veces en
    el mismo instante (la ficha guardada y el motivo de la regla, que la zona anota con la tabla
    de los incidentes) cuenta una: EODI-2026-00312, 7 → 6 km al pasar a zona-1.1.0 el 27 de
    octubre de 2026, salía como vuelta."""
    dejados: dict[tuple[str, str], set[str]] = {}
    vueltas: Counter[tuple[str, str]] = Counter()
    apuntados: set[tuple[str, str, str, str, str]] = set()
    for cambio in cambios:
        anterior, nuevo = cambio.get("anterior") or {}, cambio.get("nuevo") or {}
        claves = (
            set(nuevo)
            if cambio.get("tabla") == "incidentes_motivos"
            else set(anterior) | set(nuevo)
        )
        for dato in claves - _NO_SON_DATOS:
            antes = json.dumps(anterior.get(dato), sort_keys=True, ensure_ascii=False)
            despues = json.dumps(nuevo.get(dato), sort_keys=True, ensure_ascii=False)
            if antes == despues:
                continue
            clave = (str(cambio["entidad_id"]), dato)
            if cambio.get("fecha"):
                mismo = (*clave, antes, despues, str(cambio["fecha"]))
                if mismo in apuntados:
                    continue
                apuntados.add(mismo)
            vistos = dejados.setdefault(clave, set())
            if antes in vistos or despues in vistos:
                vueltas[clave] += 1
            vistos.add(antes)
    resultado: dict[str, list[str]] = {}
    for (id_, dato), veces in sorted(vueltas.items()):
        if veces >= MIN_VUELTAS:
            resultado.setdefault(id_, []).append(dato)
    return resultado


# Lo que tarda en guardarse la ficha tras su extracción (la tanda de la recogida).
MARGEN_EXTRACCION = timedelta(minutes=30)


def _instante_iso(texto: str) -> datetime:
    return datetime.fromisoformat(texto.replace("Z", "+00:00"))


def _tras_extraccion(fecha: str, extraidas: list[str]) -> bool:
    cuando = _instante_iso(fecha)
    return any(
        timedelta(minutes=-1) <= cuando - _instante_iso(e) <= MARGEN_EXTRACCION for e in extraidas
    )


def perdidos_al_extraer(
    vigentes: dict[str, Documento],
    cambios: Iterable[Documento],
    extracciones: dict[str, list[str]],
) -> list[str]:
    """W: «<id> <dato>» de las fichas vigentes que perdieron al volver a extraerse un dato decidido
    con la frase de una fuente que siguen teniendo (proceso/decididos.py) y aún no lo han
    recuperado. EODI-2026-00066 pasó del 13 de septiembre a la fecha de publicación de la noticia
    al volver a extraerla el 29 de octubre de 2026."""
    from proceso import decididos

    resultado: set[str] = set()
    for cambio in cambios:
        if cambio.get("tabla", "incidentes") != "incidentes" or not cambio.get("fecha"):
            continue
        anterior, nuevo = cambio.get("anterior") or {}, cambio.get("nuevo") or {}
        actual = vigentes.get(str(cambio["entidad_id"]))
        candidato = str((nuevo.get("control") or {}).get("candidato") or "")
        if not anterior or actual is None or not candidato:
            continue
        if not _tras_extraccion(str(cambio["fecha"]), extracciones.get(candidato, [])):
            continue
        siguen = set(decididos.perdidos(actual, anterior))
        resultado |= {f"{actual['id']} {d}" for d in decididos.perdidos(nuevo, anterior)
                      if d in siguen}  # fmt: skip
    return sorted(resultado)


def auditar(
    documentos: Iterable[Documento],
    cambios: Iterable[Documento] = (),
    copias: dict[str, Documento] | None = None,
    del_experto: frozenset[frozenset[str]] = frozenset(),
    a_mano: Iterable[frozenset[str]] = (),
    extracciones: dict[str, list[str]] | None = None,
) -> dict[str, list[str]]:
    """Por comprobación, los identificadores de las fichas vigentes que la incumplen. `cambios`
    son los de las últimas 48 horas (`Almacen.cambios_desde`), para K y W; `copias`, las copias
    archivadas de los enlaces (`Almacen.copias_archivadas`), para Q; `del_experto`, los pares
    que el experto dio por distintos (`incidentes.distintos_del_experto`) y las uniones hechas a
    mano (`incidentes.uniones_a_mano`), para V; `extracciones`, las fechas de las extracciones de
    cada candidato en esas horas (`Almacen.fechas_extraccion`), para W."""
    resultado: dict[str, list[str]] = {c: [] for c in COMPROBACIONES}
    vistos = list(documentos)
    cambios = list(cambios)
    for documento in vistos:
        if not incidentes.activo(documento):
            continue
        for clave, regla in _REGLAS.items():
            try:
                fallo = regla(documento)
            except (KeyError, TypeError, ValueError):
                # Una ficha a la que le falta algo que la regla lee no cuenta como fallo: la
                # auditoría no para por una.
                fallo = False
            if fallo:
                resultado[clave].append(str(documento["id"]))
    vigentes = {str(d["id"]) for d in vistos if incidentes.activo(d)}
    if copias:
        resultado["Q"] = [str(d["id"]) for d in vistos
                          if incidentes.activo(d) and sin_fuente_legible(d, copias)]  # fmt: skip
    resultado["L"] = autoridad_perdida(vistos)
    resultado["V"] = uniones_marcadas(vistos, del_experto, a_mano)
    resultado["K"] = [f"{i} {'/'.join(datos)}" for i, datos in oscilan(cambios).items()
                      if i in vigentes]  # fmt: skip
    if extracciones:
        resultado["W"] = perdidos_al_extraer(
            {str(d["id"]): d for d in vistos if incidentes.activo(d)}, cambios, extracciones
        )
    # R: las fichas del conjunto de referencia (proceso/referencia.py) que se apartan del valor
    # comprobado contra sus fuentes en algo que no es una discrepancia conocida.
    from proceso import referencia

    try:
        resultado["R"] = referencia.fallos(vistos)
    except (KeyError, TypeError, ValueError, OSError) as error:
        resultado["R"] = [f"sin comparar: {str(error)[:80]}"]
    return {c: sorted(ids) for c, ids in resultado.items()}


def recuentos(resultado: dict[str, list[str]]) -> dict[str, int]:
    return {c: len(ids) for c, ids in resultado.items()}


def texto(resultado: dict[str, list[str]], limite: int = 40) -> str:
    lineas = []
    for clave in COMPROBACIONES:
        ids = resultado.get(clave, [])
        muestra = ", ".join(ids[:limite]) + (" …" if len(ids) > limite else "")
        lineas.append(f"{clave} {NOMBRES[clave]}: {len(ids)}" + (f" ({muestra})" if ids else ""))
    return "\n".join(lineas)
