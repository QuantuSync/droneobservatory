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
  recogida/declaraciones_oficiales.con_declaraciones_del_unido). También sale si la unión la
  conservó y otra regla se la quitó después (EODI-2026-00728, la medida a las 24 horas).
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
- **X, cambio a algo protegido sin justificación**: en las últimas 48 horas se guardó un cambio a
  un dato protegido (proceso/protegido.py) sin el apunte `permitido:` que deja el cerrojo cuando
  lo deja pasar. Con el cerrojo en «aplicar» debe valer 0: cualquier otro valor es un agujero. En
  «observar» cuenta lo que se habría retenido y aun así se guardó (docs/cerrojo.md).
- **Y, autoridad de otro país sin frase**: una autoridad de la ficha, escrita como en la web (con
  su país si su nombre es de varios: proceso/autoridades.con_pais), es de un país distinto al de
  la ficha (`pais` de configuracion/autoridades.json) y ninguna frase de sus fuentes nombra ese
  país. EODI-2026-00728 (2 de noviembre de 2026): «Ministerul Apărării» de Moldavia salía como «el
  Ministerio de Defensa Nacional de Rumanía».
- **Z, fuente anterior al suceso**: una fuente de la ficha se publicó más de dos días antes del
  día del suceso (proceso/protegido.fuentes_anteriores): una nota no cuenta lo que aún no ha pasado,
  así que la ficha junta dos sucesos. EODI-2026-00079 (2 de noviembre de 2026): las notas del 17 de
  febrero de 2026 acabaron en la ficha del 11 de agosto.
- **AA, una frase con dos días**: una frase de sus fuentes da dos días de la semana unidos por
  una conjunción que no caben en una noche (proceso/fechas.frase_de_dos_dias) y ninguna revisión
  (una separación, «distintos» o el inicio revisado con cita) ha dicho a qué día va cada cosa:
  la ficha junta dos sucesos y hay que separarla. EODI-2026-00756 (5 de noviembre de 2026): «W
  łotewską przestrzeń powietrzną wkroczyły w niedzielę i wtorek dwa drony» quedó en una ficha del
  domingo con los drones de los dos días. Desde el 9 de noviembre de 2026 también dos días
  seguidos sin la noche junto a ellos: EODI-2026-00770, «am Samstag und Sonntag jeweils eine der
  beiden Landebahnen kurzzeitig gesperrt» (Leipzig/Halle).
- **AB, presencia confirmada sin frase que afirme el dron**: la presencia es «confirmada» y
  ninguna fuente de autoridad tiene una frase que afirme el dron (proceso/declaraciones.
  atribuye_dron): solo hablan de avisos, de una sospecha o de su respuesta a ellos, o no lo
  nombran. No cuentan la presencia revisada a mano, el documento propio de una autoridad ni las
  pruebas físicas que confirma una autoridad. EODI-2026-00821 (RAF Lakenheath, 13 de noviembre de
  2026): «responded to "suspected unauthorised drone activity"» y «responded to reports of
  unauthorised drone activity» la dejaban confirmada. Desde el 28 de noviembre de 2026, en
  cualquier lengua: la frase que no está en inglés solo afirma el dron si también lo afirma su
  traducción inglesa guardada (declaraciones.afirma_el_dron), y sin traducción no lo afirma.
  EODI-2026-00821 volvió a confirmada el 28/11 con «καταγράφηκαν αναφορές για μη
  εξουσιοδοτημένη δραστηριότητα drones» («reports of unauthorised drone activity were
  recorded»).
- **AC, estado confirmado o atribuido sin frase de autoridad que reconozca el suceso**: el estado
  es «confirmado» o «atribuido» y ninguna fuente de autoridad tiene una frase que reconozca el
  suceso (proceso/declaraciones.reconoce): solo cuentan que la autoridad lo investiga o que la
  avisaron, o la fuente dice que no está confirmado oficialmente. No cuenta el estado que da una
  revisión a mano con su cita. EODI-2026-00937 (Sigonella, 20 de noviembre de 2026): «Zdarzenie
  bada włoska żandarmeria wojskowa.», una frase del periódico, la dejaba confirmada.
- **AJ, titular que dice del dron más o menos que la presencia**: en español o en inglés, el
  titular duda del dron con la presencia confirmada, o lo afirma con la presencia no confirmada,
  no acreditada o descartada (proceso/titulares.postura y POSTURAS_VALIDAS: la duda cuenta también
  lejos del dron, «por sospecha de dron», «Posible caída de dron», «Suspected airspace violation
  by drones»; «dron no identificado» lo afirma). Un titular que no nombra el dron vale con
  cualquier presencia. EODI-2025-00095, 2025-00299, 2026-00041 y 2026-00903 (27 de noviembre de
  2026): el inglés había perdido la duda con el dron confirmado y el español no, y la T, que solo
  miraba el «posible» pegado al dron, no lo veía. La letra que sigue a AH no se usa: el gancho que
  revisa los ficheros antes de subirlos no deja escribir esa sigla.
"""

import json
import re
from collections import Counter
from collections.abc import Callable, Iterable
from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from esquema import Documento
from proceso import (
    atribucion,
    autoridades,
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
    suceso,
    textos_dron,
    titulares,
)
from proceso import control_fichas as reglas_control
from proceso.presencia import (
    MOTIVO_PRUEBAS_PRENSA,
    MOTIVO_SIN_BASE,
    atribuida_por_autoridad,
    documento_oficial_decide,
    presencias_revisadas,
    pruebas_fisicas_confirmadas,
)
from proceso.ubicacion import CATEGORIA_LUGAR

COMPROBACIONES = (
    "A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L", "M", "N", "O", "P", "Q", "R",
    "S", "T", "U", "V", "W", "X", "Y", "Z", "AA", "AB", "AC", "AD", "AE", "AF", "AG", "AH",
    "AJ",
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
    "X": "cambio a algo protegido sin justificación",
    "Y": "autoridad de otro país sin frase",
    "Z": "fuente anterior al suceso",
    "AA": "una frase con dos días",
    "AB": "presencia confirmada sin frase que afirme el dron",
    "AC": "estado confirmado o atribuido sin frase de autoridad que reconozca el suceso",
    "AD": "presencia confirmada con el suceso sin confirmar",
    "AE": "declaración atribuida a una autoridad que no la dijo",
    "AF": "el mismo sitio días antes y la fecha de un «ayer» de una nota de seguimiento",
    "AG": "la fecha de una nota que dice que el suceso fue antes",
    "AH": "presencia confirmada por un resumen del medio que otra fuente pone en duda",
    "AJ": "titular que dice del dron más o menos que la presencia",
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


# P, con nombre propio: la coherencia la corrige en las fichas que nunca se han publicado
# (proceso/correccion.presencia_sin_quien).
presencia_rebajada_sin_cierre = _p


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


def autoridades_de_otro_pais(incidente: Documento) -> list[str]:
    """Las autoridades de la ficha, escritas como en la web (proceso/autoridades.con_pais), de un
    país distinto al de la ficha sin una frase que nombre ese país: la de sus fuentes (la
    declaración, el medio o la fuente de quien atribuye o investiga) o, si no tiene ninguna
    propia, la de cualquier fuente de la ficha."""
    return list(fuentes_de_otro_pais(incidente))


def fuentes_de_otro_pais(incidente: Documento) -> dict[str, list[str]]:
    """Como `autoridades_de_otro_pais`, cada una con los identificadores de sus fuentes (la
    declaración, o la de quien atribuye o investiga): lo que quita la puerta (letra Y)."""
    pais_ficha = (incidente.get("lugar") or {}).get("pais")
    if not pais_ficha:
        return {}
    # Solo las fuentes que enseña la web: una declaración que dejó de ser oficial y pública (la
    # corrección de esta letra, recogida/control_fichas.sin_autoridades_de_otro_pais) no cuenta.
    visibles = [
        f for f in incidente.get("fuentes") or []
        if isinstance(f, dict) and f.get("publica", True) and f.get("fiabilidad") not in {"E", "F"}
    ]  # fmt: skip
    documento = autoridades.con_pais(json.loads(json.dumps(
        {**{c: incidente.get(c) for c in ("lugar", "atribucion", "investigacion")},
         "fuentes": visibles}
    )))  # fmt: skip
    fuentes = [f for f in documento.get("fuentes") or [] if isinstance(f, dict)]
    frases = {str(f.get("id")): str(f.get("frase_origen") or "") for f in fuentes}
    propias: dict[str, list[str]] = {}
    for fuente in fuentes:
        medio = str(fuente.get("medio") or "")
        citada = autoridades.DECLARACION_CITADA.match(medio)
        propias.setdefault(citada.group(1) if citada else medio, []).append(str(fuente.get("id")))
    for entrada in [documento.get("atribucion") or {}, *(documento.get("investigacion") or [])]:
        if isinstance(entrada, dict) and entrada.get("autoridad"):
            propias.setdefault(str(entrada["autoridad"]), []).append(str(entrada.get("fuente_id")))
    malas: dict[str, list[str]] = {}
    for nombre, _ in autoridades.nombres(documento):
        pais = autoridades.pais_escrito(nombre)
        if pais is None or pais == pais_ficha:
            continue
        suyas = [frases.get(i, "") for i in propias.get(nombre, [])] or list(frases.values())
        if not any(atribucion.menciona(frase, pais) for frase in suyas if frase):
            malas[nombre] = list(propias.get(nombre, []))
    return malas


def _en_la_ficha(campo: str, valor: Any, vista: Documento) -> bool:
    """Si la ficha tiene ese dato de la verificación (como lo lee la web: reglas.vista)."""
    if campo in ("drones", "duracion_min"):
        return bool(reglas_control.rango_texto(valor) == vista.get(campo))
    if campo == "presencia":
        return bool(valor == vista.get("presencia_dron"))
    if campo == "cierre":
        return bool(valor == vista.get("cierre"))
    if campo == "lugar" and isinstance(valor, dict):
        return str(vista.get("lugar") or "").startswith(f"{valor.get('nombre')} (")
    return False


def datos_de_otro_pais(incidente: Documento, verificacion: Documento | None) -> list[str]:
    """Los datos de la ficha que dio su última verificación con una frase de otro país
    (proceso/atribucion.de_otro_pais) y que la ficha sigue teniendo (EODI-2026-00728: dos
    drones por «Două drone au pătruns în spațiul aerian al României»)."""
    pais = (incidente.get("lugar") or {}).get("pais")
    if not verificacion or not pais:
        return []
    vista = reglas_control.vista(incidente)
    return sorted(
        campo for campo, dato in (verificacion.get("datos") or {}).items()
        if isinstance(dato, list) and len(dato) == 3
        and atribucion.de_otro_pais(str(dato[2]), str(pais)) is not None
        and _en_la_ficha(campo, dato[0], vista)
    )  # fmt: skip


def de_otro_pais(incidente: Documento, verificacion: Documento | None = None) -> list[str]:
    """Y: lo de otro país en la ficha, «autoridad <nombre>» o el dato."""
    return [f"autoridad {n}" for n in autoridades_de_otro_pais(incidente)] + datos_de_otro_pais(
        incidente, verificacion
    )


def confirmada_sin_frase_que_afirme(incidente: Documento) -> bool:
    """AB: presencia confirmada sin ninguna frase de autoridad que afirme el dron."""
    return (
        incidente.get("presencia_dron") == "confirmada"
        and incidente["id"] not in presencias_revisadas()
        and not documento_oficial_decide(incidente)
        and not pruebas_fisicas_confirmadas(incidente)
        and not any(
            declaraciones.de_autoridad(f) and declaraciones.afirma_el_dron(f)
            for f in incidente.get("fuentes", [])
        )
    )


def estado_sin_frase_que_reconozca(incidente: Documento) -> bool:
    """AC: estado confirmado o atribuido sin ninguna frase de autoridad que reconozca el suceso."""
    estado = incidente["estado"]
    if estado["actual"] not in ("confirmado", "atribuido"):
        return False
    revisado = any(
        str(paso.get("fuente_id", "")).startswith(reglas_control.REVISADA)
        for paso in estado["historial"]
        if paso["estado"] == estado["actual"]
    )
    return not revisado and not any(
        f.get("publica", True) is not False and declaraciones.reconoce(f, incidente)
        for f in incidente.get("fuentes", [])
    )


def confirmada_sin_suceso(incidente: Documento) -> bool:
    """AD: presencia confirmada con el suceso sin confirmar (ni confirmado ni atribuido): la
    autoridad que afirma el dron reconoce también el suceso (EODI-2025-00278)."""
    return incidente.get("presencia_dron") == "confirmada" and incidente["estado"][
        "actual"
    ] not in ("confirmado", "atribuido")


def declaracion_ajena(incidente: Documento) -> bool:
    """AE: una declaración citada pone en boca de una autoridad una frase que no es suya: a ella
    la avisaron, le entregaron el caso o solo se cuenta que investiga (EODI-2026-00362)."""
    return any(declaraciones.atribuida_a_quien_no_habla(f) for f in incidente.get("fuentes", []))


def fecha_de_una_nota_posterior(incidente: Documento) -> bool:
    """AG: el día de la ficha lo da una nota de ese día (o del siguiente) cuya frase dice que el
    suceso fue antes, sin decir cuándo («nesen notikušo», «la doar două săptămâni de când»): es
    el día de la noticia (una reunión, una decisión, una compra), no el del suceso. EODI-2025-00191
    tenía el 29 de enero de 2025, el día en que el Consejo de Seguridad habló del dron del
    aeropuerto de Riga del 13 (EODI-2025-00176), y EODI-2026-00178 el 10 de agosto de 2026, el día
    en que el aeropuerto de Cluj compró defensas contra el dron de dos semanas antes. La fecha de
    publicación sin frase es N; un pasado sin día con su ventana o una fecha revisada, no cuentan.
    Solo mira la fuente que dio el día: una nota del mismo día que recuerda otro suceso de antes
    («last month», EODI-2026-00152) no lo es."""
    tiempo = incidente.get("tiempo") or {}
    origen = tiempo.get("origen_inicio") or {}
    if origen.get("tipo") in (None, fechas.PUBLICACION) or not origen.get("fuente_id"):
        return False
    if decidir.inicio_revisado(incidente) or fechas.retrospectiva_revisada(incidente):
        return False
    if fechas.ventana_de_motivo(str(origen.get("motivo") or "")) is not None:
        return False
    dia = date.fromisoformat(str(tiempo["inicio"]["valor"])[:10])
    fuente = next(
        (f for f in incidente.get("fuentes", []) if f.get("id") == origen["fuente_id"]), None
    )
    if fuente is None or fechas.pasado_anterior(str(fuente.get("frase_origen") or "")) is None:
        return False
    publicacion = datetime.fromisoformat(str(fuente["fecha"]["valor"]).replace("Z", "+00:00"))
    zona = fechas.zona(fuente.get("pais") or incidente["lugar"].get("pais")) or ZoneInfo("UTC")
    propia = publicacion.astimezone(zona).date()
    return dia in (propia, propia - timedelta(days=1))


# El medio cuenta lo que dijo la autoridad («informs … that», «a anunțat că»): la frase no es suya.
_ESTILO_INDIRECTO = re.compile(
    r"\b(?:informs?|informed|announced|announces|a anunțat|a anuntat|anunță|informează|"
    r"a informat|anunció|informó|informa|ha informado)\b[^\"«“„']{0,80}\b(?:that|că|ca|que)\b",
    re.IGNORECASE,
)
# Una fuente que pone en duda que fuera un dron.
_EN_DUDA = re.compile(
    r"\b(?:posibil\w*|possibl\w*|probabl\w*|presum\w*|posible|posiblemente|"
    r"prawdopodobn\w*|möglicherweise|mutmaßlich|feltételez\w*|valószínűleg)\b",
    re.IGNORECASE,
)


def confirmada_por_estilo_indirecto(incidente: Documento) -> bool:
    """AH: la presencia confirmada la sostiene una declaración que es el resumen del medio en
    estilo indirecto («The Ministry … informs on Friday morning that a drone had crashed») y otra
    fuente de la ficha dice que el dron es posible. El comunicado literal del Ministerio de
    Defensa rumano sobre Plauru (EODI-2026-00271, 2 de octubre de 2026) decía «căderea unui
    obiect, posibil o dronă aeriană» y que los radares no vieron ninguna entrada."""
    decision = decidir.decidir_presencia(incidente)
    if decision.valor != "confirmada" or decision.regla != "autoridad_atribuye":
        return False
    fuentes = incidente.get("fuentes", [])
    sostiene = next((f for f in fuentes if f.get("id") == decision.fuente_id), None)
    if sostiene is None or not _ESTILO_INDIRECTO.search(str(sostiene.get("frase_origen") or "")):
        return False
    return any(_EN_DUDA.search(str(f.get("frase_origen") or "")) for f in fuentes)


def titular_distinto_de_la_presencia(incidente: Documento) -> bool:
    """AJ: el titular, en español o en inglés, dice del dron algo que la presencia no permite
    (titulares.POSTURAS_VALIDAS): duda de él con la presencia confirmada o lo afirma sin ella."""
    validas = titulares.POSTURAS_VALIDAS.get(str(incidente.get("presencia_dron")))
    if validas is None:
        return False
    return any(
        titulares.postura(str(texto), idioma) not in validas
        for idioma, texto in (incidente.get("titulo") or {}).items()
        if idioma in ("es", "en")
    )


_REGLAS: dict[str, Callable[[Documento], bool]] = {
    "A": _a, "B": _b, "C": _c, "D": _d, "E": _e, "F": _f, "G": _g, "H": _h, "I": _i, "J": _j,
    "M": _m, "N": _n, "O": _o, "P": _p, "S": _s, "T": _t, "U": _u,
    "AA": suceso.dos_dias_sin_revisar,
    "AB": confirmada_sin_frase_que_afirme,
    "AC": estado_sin_frase_que_reconozca,
    "AD": confirmada_sin_suceso,
    "AE": declaracion_ajena,
    "AG": fecha_de_una_nota_posterior,
    "AH": confirmada_por_estilo_indirecto,
    "AJ": titular_distinto_de_la_presencia,
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


REGLAS_DE_V = frozenset({suceso.REGLA_REVISION, suceso.REGLA_EXPERTO, suceso.REGLA_PAISES})


# AF: días entre una ficha y la del mismo sitio que la precede para que su «ayer» pueda ser el de
# una nota de seguimiento.
DIAS_SEGUIMIENTO = 4
# AF: días entre la primera noticia de la otra ficha y la de la nota de seguimiento.
DIAS_NOTA_TARDIA = 2


def _sitio(documento: Documento) -> tuple[str, str] | None:
    """(país, instalación) de una ficha situada en una instalación: el OACI o el nombre."""
    lugar = documento.get("lugar") or {}
    if lugar.get("nivel") != "instalacion":
        return None
    objetivo = documento.get("objetivo") or {}
    nombre = objetivo.get("oaci") or _clave(
        str(lugar.get("suceso") or objetivo.get("nombre") or "")
    )
    return (str(lugar.get("pais") or ""), str(nombre)) if nombre else None


def _de_un_ayer(documento: Documento) -> bool:
    """El día de la ficha sale de un «ayer», «anoche» o «esta noche» sin día escrito: lo pone la
    publicación de la nota (fechas.relativa_sin_dia)."""
    origen = documento["tiempo"].get("origen_inicio") or {}
    return origen.get("tipo") == fechas.RELATIVA and fechas.relativa_sin_dia(
        str(origen.get("motivo") or "")
    )


def seguimientos_de_otro_dia(
    documentos: list[Documento], distintos: frozenset[frozenset[str]] = frozenset()
) -> list[str]:
    """AF: «posterior→anterior» de las fichas vigentes fechadas por un «ayer» sin día
    (`_de_un_ayer`) en la misma instalación y el mismo país que otra vigente de 1 a
    DIAS_SEGUIMIENTO días antes, cuando ninguna de sus fuentes es de su propio día y la primera
    llega DIAS_NOTA_TARDIA días o más después de la primera de la otra: una nota que vuelve a
    contar el suceso días después, cuyo «ayer» es el de su primera publicación y no el de la copia
    (EODI-2026-00997: la nota de Il Messaggero del 21/11 sobre la alerta del 20/11 en Sigonella,
    que leggo.it volvió a publicar y GDELT vio el 24/11, frente a EODI-2026-00937). No cuentan las
    que el experto o una revisión dieron por distintas ni las que una revisión enlazó en la misma
    serie (`relacionados`). No las marca un suceso nuevo contado el mismo día (Brønnøysund, 28 y
    30/9/2025: «Nye meldinger» del 30) ni dos contados juntos («Afgelopen nacht en zaterdag»,
    Marche-en-Famenne, 25 y 28/10/2025)."""
    vigentes = [d for d in documentos if incidentes.activo(d) and _sitio(d) is not None]

    def enlazadas(documento: Documento) -> set[str]:
        return {str(r.get("id")) for r in documento.get("relacionados", [])}

    salida = []
    for posterior in vigentes:
        if not _de_un_ayer(posterior):
            continue
        dia = fechas.dia_local(posterior["tiempo"]["inicio"], posterior)
        publicadas = [
            fechas.dia_local(f["fecha"], posterior) for f in posterior.get("fuentes", [])
            if f.get("fecha")
        ]  # fmt: skip
        if not publicadas or min(publicadas) <= dia:
            continue
        primera = suceso.momento_primera_noticia(posterior)
        for anterior in vigentes:
            if anterior is posterior or _sitio(anterior) != _sitio(posterior):
                continue
            dias = (suceso.instante(posterior).date() - suceso.instante(anterior).date()).days
            par = frozenset((str(posterior["id"]), str(anterior["id"])))
            serie = enlazadas(posterior) & ({str(anterior["id"])} | enlazadas(anterior))
            tarde = primera - suceso.momento_primera_noticia(anterior)
            if (
                1 <= dias <= DIAS_SEGUIMIENTO
                and tarde >= timedelta(days=DIAS_NOTA_TARDIA)
                and par not in distintos
                and not serie
            ):
                salida.append(f"{posterior['id']}→{anterior['id']}")
    return salida


def uniones_marcadas(
    documentos: list[Documento],
    del_experto: frozenset[frozenset[str]] = frozenset(),
    a_mano: Iterable[frozenset[str]] = (),
) -> list[str]:
    """Las uniones vigentes (absorbido→destino) entre fichas que la definición da por sucesos
    distintos (proceso/suceso.uniones_contrarias) por una regla que manda sobre quien leyó las
    fuentes: una revisión las separó o las dio por distintas, el experto las dio por distintas
    en el control o son de países distintos con una autoridad del suyo; salvo las que una
    revisión unió a mano (sección `unir`, o `a_mano`: las fusiones revisadas a mano de
    `suceso.uniones_a_mano`) (V). Los cierres de noches distintas no se miran aquí: las uniones
    de la regla de fusión que lo son se deshacen solas (`incidentes.revisar_fusiones`, y la
    invariante I6 si no pudo), y las que hizo el control leyendo las fuentes valen."""
    return [
        f"{absorbido}→{destino}"
        for absorbido, destino, _ in suceso.uniones_contrarias(
            documentos, del_experto, a_mano, REGLAS_DE_V
        )
    ]


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
    cambios = list(cambios)
    # Los guardados de la ficha: en ese instante, el cambio de verdad es el de la ficha (de lo
    # guardado antes a lo guardado después), no los pasos intermedios que anotan sus reglas.
    # EODI-2025-00043, 1 de noviembre de 2026 a las 11:30:27: el titular volvió una vez a lo
    # revisado, y los motivos de decidir y de la atribución, con titulares que nunca se
    # guardaron, contaban otras dos vueltas (auditoría K).
    guardados = {
        (str(c["entidad_id"]), str(c["fecha"]))
        for c in cambios
        if c.get("tabla", "incidentes") == "incidentes" and c.get("fecha")
    }  # fmt: skip
    for cambio in cambios:
        if (
            cambio.get("tabla") == "incidentes_motivos"
            and (str(cambio["entidad_id"]), str(cambio.get("fecha"))) in guardados
        ):
            continue
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


def _motivo_al_guardar(motivo: str) -> bool:
    """El motivo que anota el guardado de cualquier versión (proceso/decidir.motivo)."""
    return motivo.startswith("un solo sitio decide") or motivo in (
        MOTIVO_PRUEBAS_PRENSA, MOTIVO_SIN_BASE,
    )  # fmt: skip


def _guardados_con_motivo(cambios: list[Documento]) -> set[tuple[str, str]]:
    """(incidente, fecha) de los guardados de otro paso que el de la extracción: el control, una
    revisión, una separación o una unión anotan su motivo en el mismo instante."""
    return {
        (str(c["entidad_id"]), str(c.get("fecha")))
        for c in cambios
        if c.get("tabla") == "incidentes_motivos"
        and not _motivo_al_guardar(str((c.get("nuevo") or {}).get("motivo") or ""))
    }  # fmt: skip


def perdidos_al_extraer(
    vigentes: dict[str, Documento],
    cambios: Iterable[Documento],
    extracciones: dict[str, list[str]],
) -> list[str]:
    """W: «<id> <dato>» de las fichas vigentes que perdieron al volver a extraerse un dato decidido
    con la frase de una fuente que siguen teniendo (proceso/decididos.py) y aún no lo han
    recuperado. EODI-2026-00066 pasó del 13 de septiembre a la fecha de publicación de la noticia
    al volver a extraerla el 29 de octubre de 2026. Lo que quita otro paso en la misma recogida
    (el control: «ninguna fuente da el número») deja su motivo y no cuenta."""
    from proceso import decididos

    cambios = list(cambios)
    de_otro_paso = _guardados_con_motivo(cambios)
    resultado: set[str] = set()
    for cambio in cambios:
        if cambio.get("tabla", "incidentes") != "incidentes" or not cambio.get("fecha"):
            continue
        if (str(cambio["entidad_id"]), str(cambio["fecha"])) in de_otro_paso:
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
    permitidos: frozenset[tuple[str, str, str]] | None = None,
    verificaciones: dict[str, Documento] | None = None,
    primeras: dict[str, str] | None = None,
) -> dict[str, list[str]]:
    """Por comprobación, los identificadores de las fichas vigentes que la incumplen. `cambios`
    son los de las últimas 48 horas (`Almacen.cambios_desde`), para K y W; `copias`, las copias
    archivadas de los enlaces (`Almacen.copias_archivadas`), para Q; `del_experto`, los pares
    que el experto dio por distintos (`suceso.distintos_del_experto`) y las uniones hechas a
    mano (`suceso.uniones_a_mano`), para V; `extracciones`, las fechas de las extracciones de
    cada candidato en esas horas (`Almacen.fechas_extraccion`), para W; `permitidos`, los cambios
    que dejó pasar el cerrojo (`protegido.permitidos`), para X; `verificaciones`, la última
    verificación de cada ficha (`Almacen.controles("verificacion:")`, por identificador), para
    los datos de Y."""
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
    for documento in vistos:
        if not incidentes.activo(documento):
            continue
        try:
            otros = de_otro_pais(documento, (verificaciones or {}).get(str(documento["id"])))
        except (KeyError, TypeError, ValueError):
            otros = []
        resultado["Y"].extend(f"{documento['id']} {o}" for o in otros)
    if copias:
        resultado["Q"] = [str(d["id"]) for d in vistos
                          if incidentes.activo(d) and sin_fuente_legible(d, copias)]  # fmt: skip
    from proceso import protegido as _protegido

    resultado["Z"] = [str(d["id"]) for d in vistos
                      if incidentes.activo(d) and _protegido.fuentes_anteriores(d)]  # fmt: skip
    resultado["L"] = autoridad_perdida(vistos)
    resultado["V"] = uniones_marcadas(vistos, del_experto, a_mano)
    resultado["AF"] = seguimientos_de_otro_dia(vistos, del_experto)
    resultado["K"] = [f"{i} {'/'.join(datos)}" for i, datos in oscilan(cambios).items()
                      if i in vigentes]  # fmt: skip
    if extracciones:
        resultado["W"] = perdidos_al_extraer(
            {str(d["id"]): d for d in vistos if incidentes.activo(d)}, cambios, extracciones
        )
    if permitidos is not None:
        from proceso import protegido

        # Solo lo que la ficha aún tiene (lo deshecho o fijado por una revisión no cuenta).
        actuales = {str(d["id"]): d for d in vistos}
        resultado["X"] = protegido.cambios_sin_permiso(cambios, permitidos, actuales, primeras)
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
