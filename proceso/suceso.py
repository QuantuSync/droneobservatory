"""La definición de suceso (docs/definicion_suceso.md) y lo único que decide si dos fichas
cuentan el mismo.

Un suceso es un episodio físico (los mismos drones o la misma oleada) en un país y en una
jornada: un día local o una noche que cruza la medianoche. Todo lo que une, separa, compara,
audita o comprueba fichas pregunta aquí:

- `veredicto(a, b)`: lo que la definición dice de dos fichas sin leer sus fuentes. «mismo» y
  «distintos» son firmes y nadie los contradice (ni el experto); «experto» es que pueden serlo y
  lo decide quien lee las fuentes, con `DEFINICION` delante; «ajenas», que ni se pregunta.
- `DEFINICION`: el texto que llevan las peticiones al modelo que preguntan por el mismo suceso
  (el filtro de entrada, la medida, el repaso y la comparación de pares del control).
- `conjunto` y `previas_del_sitio`: con qué fichas se compara una nueva, y con cuáles una
  noticia sobre un suceso anterior.
- `varios_dias`: la ficha que cuenta dos días que no son una noche (dos sucesos en una ficha).
- `queda`, `destino_de` y `toma_el_tiempo`: qué ficha queda de una unión y de dónde sale su
  fecha.
- `episodios_calculados`: los sucesos que se enlazan entre sí (varios objetivos de un país en
  una noche, o el mismo episodio a los dos lados de una frontera).

Las reglas firmes, en su orden (la primera que habla, decide):

1. Una revisión a mano manda: lo que separó o dio por distinto no se une; lo que unió, unido
   está.
2. Países distintos son sucesos distintos si el país de alguna de las dos es firme (cita a una
   autoridad de su país). Sin eso (un buque en el mar entre dos países) el país de una de las
   dos puede estar mal y lo decide el experto.
3. La nota con la que una autoridad cuenta una noche y sus alertas por zonas de esa noche, en
   el mismo país, son el mismo suceso, aunque el experto dijera otra cosa.
4. Lo que el experto dio por distinto leyendo las fuentes de las dos no se vuelve a unir solo.
5. Dos cierres del mismo sitio en noches distintas, o un cierre que las fuentes cuentan como
   repetido, son dos sucesos (`noches_del_cierre`).
6. El mismo sitio y la misma jornada sin nada de lo anterior es el mismo suceso sin preguntar
   (la regla de fusión): con hora, inicios a menos de 6 horas; con día, el mismo día. Dos días
   seguidos sin hora pueden ser una noche o dos sucesos: decide el experto. Y la regla no une
   sola dos fichas que ya tienen su página en la web (proceso/incidentes.fusionar).

Lo que este módulo no hace: leer el día de una frase (proceso/fechas.py), ejecutar una unión o
deshacerla (proceso/incidentes.py, recogida/control_fichas.py, recogida/revisados.py) ni agrupar
artículos en candidatos antes de que haya ficha (proceso/noticias.py).
"""

import json
import math
from collections import defaultdict
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from functools import cache
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import urlsplit

from esquema import Documento
from proceso import alertas_zona, autoridades, fechas, fronteras
from proceso.noticias import filtro, normalizar

if TYPE_CHECKING:
    from almacen.base import Almacen

# --- El veredicto ---------------------------------------------------------------------------

MISMO, DISTINTOS, EXPERTO, AJENAS = "mismo", "distintos", "experto", "ajenas"

# Las reglas firmes (el nombre que queda en las decisiones y en los registros).
REGLA_REVISION = "revision"
REGLA_PAISES = "paises_distintos"
REGLA_RESUMEN = "resumen_de_la_misma_noche"
REGLA_EXPERTO = "experto"
REGLA_CIERRES = "cierres_de_noches_distintas"
REGLA_SITIO_Y_JORNADA = "mismo_sitio_y_jornada"
REGLA_CANDIDATAS = "candidatas"
MOTIVO_SITIO_Y_JORNADA = "mismo sitio y misma ventana"


@dataclass(frozen=True)
class Veredicto:
    """Lo que la definición dice de dos fichas: la relación, la regla que habló y su motivo."""

    relacion: str
    regla: str = ""
    motivo: str = ""

    @property
    def firme(self) -> bool:
        return self.relacion in (MISMO, DISTINTOS)


# --- La definición, para quien lee las fuentes ------------------------------------------------

DEFINICION = (
    "Qué es un suceso (la misma definición en todo el observatorio): un episodio físico, es "
    "decir, los mismos drones o la misma oleada, en un país y en una jornada (un día, o una "
    "noche que cruza la medianoche, que es una sola jornada). Dos fichas cuentan el mismo suceso "
    "si cuentan ese mismo episodio, aunque cambien la fecha de publicación, el idioma, el número "
    "o lo preciso del lugar (una dice el país o la zona y la otra, el sitio). "
    "Son el mismo suceso: el dron o la oleada que recorre varias zonas del mismo país en una "
    "noche (cada alerta que la autoridad va dando por zonas y la nota con la que después cuenta "
    "esa noche entera); varios sitios que una misma comunicación oficial cuenta juntos sin "
    "separar el día, la hora ni los drones de cada uno; y una noticia posterior (una reacción, "
    "un balance, la investigación, un recuerdo semanas después) sobre un suceso ya contado, que "
    "es de la jornada del suceso y no de la de su publicación. "
    "Son sucesos distintos: los de países distintos, aunque sea el mismo dron que cruza la "
    "frontera (cada país tiene su suceso); los de jornadas distintas (dos días distintos, dos "
    "noches distintas, «de nuevo», «otra vez», «un segundo ataque»), salvo la noche que cruza "
    "la medianoche; y, en la misma jornada y el mismo país, drones distintos en sitios u horas "
    "distintos que las fuentes cuentan por separado (otro dron horas después, otro aeropuerto, "
    "otro barco). Una noticia que cuenta varios de esos (un balance de varias noches, un "
    "resumen de dos países) no es un suceso nuevo: cada uno de los que cuenta es el suyo. La "
    "ficha hecha con una noticia así es del suceso de su país y de su jornada (el lugar y el día "
    "de la ficha), el mismo que el de otra ficha de ese país y esa jornada, aunque la noticia "
    "hable también del país vecino o de otra noche."
)
# --- Lo que mide el sitio y la jornada --------------------------------------------------------

# El mismo sitio sin preguntar: puntos a menos de la suma de sus radios más este margen.
MARGEN_FUSION_KM = 10.0
# Con hora en las dos, inicios a menos de esto; y sin actividad del suceso más de lo otro es
# otro suceso.
INICIOS_HORA = timedelta(hours=6)
SIN_ACTIVIDAD = timedelta(hours=12)
RADIO_TIERRA_KM = 6371.0
PRECISIONES_HORA = frozenset({"minuto", "hora"})
APROXIMADA = "aproximada"
# Hasta las 06:00 locales, una hora es aún de la noche que empezó la víspera.
MADRUGADA = timedelta(hours=6)
# Desde las 18:00 locales, una hora es ya de la noche que acaba la madrugada siguiente.
HORA_TARDE = 18
# Una nota que vuelve sobre un suceso ya pasado: la primera de sus noticias sale al menos estos
# días después del día del suceso que escribe (nota_posterior).
DIAS_NOTA_POSTERIOR = 2
MOTIVO_NOTA_POSTERIOR = "nota posterior sobre un suceso ya registrado: mismo país, tipo y día"
# Lo que puede ser el mismo suceso y se pregunta: fechas escritas a menos de esto (el mismo día
# o la misma noche); con la fecha de publicación en alguna, a menos de lo otro.
VENTANA_PAR_ESCRITA = timedelta(hours=30)
VENTANA_PAR = timedelta(hours=48)
MARGEN_PAR_KM = 15.0
# Dos instalaciones de distinto tipo solo son el mismo sitio si están juntas.
MARGEN_MISMO_SITIO_KM = 10.0
# Dos fichas con su día sacado de una frase y a más de estos días no se unen sin revisión.
DIAS_FIRMES = 2
# La nota de una noche y sus alertas: sus días (sin hora) son el mismo o seguidos.
DIAS_MISMA_NOCHE = 1
# El conjunto con el que se compara una ficha nueva.
DIAS_ANTES = 30
DIAS_DESPUES = 3
MAX_CONJUNTO = 40


def leer_instante(instante: Documento) -> datetime:
    return datetime.strptime(instante["valor"], "%Y-%m-%dT%H:%MZ").replace(tzinfo=UTC)


def instante(ficha: Documento) -> datetime:
    """El inicio del suceso de la ficha."""
    return leer_instante(ficha["tiempo"]["inicio"])


def primera_noticia(documento: Documento) -> str:
    """Cuándo se publicó la primera de sus fuentes."""
    return min((f["fecha"]["valor"] for f in documento["fuentes"]), default="9999")


def momento_primera_noticia(ficha: Documento) -> datetime:
    return datetime.strptime(primera_noticia(ficha)[:16], "%Y-%m-%dT%H:%M").replace(tzinfo=UTC)


def _activa(documento: Documento) -> bool:
    return "fusionado_en" not in documento and "retirado" not in documento


# --- El sitio ---------------------------------------------------------------------------------


def _distancia_km(a: Documento, b: Documento) -> float:
    pa, pb = a["lugar"]["punto"], b["lugar"]["punto"]
    f1, f2 = math.radians(pa["lat"]), math.radians(pb["lat"])
    df, dl = f2 - f1, math.radians(pb["lon"] - pa["lon"])
    h = math.sin(df / 2) ** 2 + math.cos(f1) * math.cos(f2) * math.sin(dl / 2) ** 2
    return 2 * RADIO_TIERRA_KM * math.asin(math.sqrt(h))


def con_punto(documento: Documento) -> bool:
    return "punto" in documento["lugar"]


def mismo_sitio(a: Documento, b: Documento) -> bool:
    if a["lugar"]["pais"] != b["lugar"]["pais"]:
        return False
    if not con_punto(a) or not con_punto(b):
        # Sin punto, solo dos sin punto con el mismo lugar del suceso.
        sucesos = [normalizar(d["lugar"].get("suceso", "")) for d in (a, b)]
        return not con_punto(a) and not con_punto(b) and bool(sucesos[0]) and len(set(sucesos)) == 1
    oa, ob = a.get("objetivo", {}), b.get("objetivo", {})
    if oa.get("nombre") and oa.get("nombre") == ob.get("nombre"):
        return True
    radios = float(a["lugar"]["radio_km"]) + float(b["lugar"]["radio_km"])
    return _distancia_km(a, b) < radios + MARGEN_FUSION_KM


def _cerca_en_el_espacio(a: Documento, b: Documento) -> bool:
    """Pueden ser el mismo sitio: el mismo país y, si las dos tienen punto, a menos de la suma
    de sus radios más MARGEN_PAR_KM."""
    if a["lugar"]["pais"] != b["lugar"]["pais"]:
        return False
    if not con_punto(a) or not con_punto(b):
        return True
    radios = float(a["lugar"].get("radio_km", 0)) + float(b["lugar"].get("radio_km", 0))
    return _distancia_km(a, b) <= radios + MARGEN_PAR_KM


def _mismo_tipo_de_sitio(a: Documento, b: Documento) -> bool:
    """Dos sitios de distinto tipo (un aeropuerto y una base) no son el mismo suceso, salvo que
    estén juntos (aeropuertos de uso mixto)."""
    from proceso.ubicacion import CATEGORIA_LUGAR

    instalaciones = frozenset(CATEGORIA_LUGAR.values())
    ca = (a.get("objetivo") or {}).get("categoria")
    cb = (b.get("objetivo") or {}).get("categoria")
    if ca not in instalaciones or cb not in instalaciones or ca == cb:
        return True
    return con_punto(a) and con_punto(b) and _distancia_km(a, b) <= MARGEN_MISMO_SITIO_KM


# --- La jornada -------------------------------------------------------------------------------


def ultima_actividad(documento: Documento) -> datetime:
    """El último momento del suceso: su fin, si se sabe, o su inicio. Las noticias no son
    actividad: se siguen publicando un día entero después de un cierre."""
    momentos = [leer_instante(documento["tiempo"]["inicio"])]
    if "fin" in documento["tiempo"]:
        momentos.append(leer_instante(documento["tiempo"]["fin"]))
    return max(momentos)


def dia_local(momento: datetime, pais: str) -> date:
    """El día local de una hora en UTC («la una de la madrugada en Galați» es el día anterior
    en UTC)."""
    zona = fechas.zona(pais)
    return momento.astimezone(zona).date() if zona else momento.date()


def con_hora(documento: Documento) -> bool:
    """El inicio es una hora que escribe una fuente: con precisión de hora o de minuto, o una
    hora aproximada con su día escrito (no la de publicación de la noticia ni un pasado sin día).
    El sábado a las 19:20 y el domingo a las 8:15 de Leipzig/Halle (EODI-2026-00770 y
    EODI-2026-00773) llevan su hora «aproximada»: tratadas como fechas de publicación («ese día o
    la víspera») eran la misma jornada."""
    inicio = documento["tiempo"]["inicio"]
    if inicio["precision"] in PRECISIONES_HORA:
        return True
    return (
        inicio["precision"] == APROXIMADA
        and fecha_verificada(documento)
        and not ventana_pasada(documento)
    )


def _dias_de(documento: Documento, pais: str, estricta: bool = False) -> tuple[str, set[date]]:
    """La clase de fecha («hora», «dia» o «publicacion») y sus días locales posibles. Un día
    es el que dice la fuente (si el extractor le puso hora, cuenta su fecha); con hora, su día
    local y, de madrugada, también la víspera, porque la prensa fecha una noche por su tarde;
    con la fecha de publicación, ese día y el anterior. Para lo que se pregunta (sin
    `estricta`), una hora de la tarde-noche llega también a la madrugada del día siguiente: es
    la misma noche (las alertas de Lituania desde las 23:00 del 10 de noviembre de 2026 y el
    misil caído en Biržai la madrugada del 11)."""
    instante_ = documento["tiempo"]["inicio"]
    momento = leer_instante(instante_)
    if instante_["precision"] == "dia":
        return "dia", {momento.date()}
    dia = dia_local(momento, pais)
    if not con_hora(documento):
        return "publicacion", {dia, dia - timedelta(days=1)}
    dias = {dia}
    if dia != dia_local(momento - MADRUGADA, pais):
        dias.add(dia - timedelta(days=1))
    zona = fechas.zona(pais)
    hora_local = momento.astimezone(zona).hour if zona else momento.hour
    if not estricta and hora_local >= HORA_TARDE:
        dias.add(dia + timedelta(days=1))
    return "hora", dias


def ventana_pasada(documento: Documento) -> set[date]:
    """Los días en que puede caer un inicio de pasado sin día («la semana pasada»), leídos del
    motivo de su origen (proceso/fechas.ventana_de_motivo); vacío si no lo es."""
    origen = documento["tiempo"].get("origen_inicio") or {}
    if documento["tiempo"]["inicio"]["precision"] != APROXIMADA:
        return set()
    ventana = fechas.ventana_de_motivo(str(origen.get("motivo") or ""))
    if ventana is None:
        return set()
    desde, hasta = ventana
    return {desde + timedelta(days=n) for n in range((hasta - desde).days + 1)}


def misma_ventana(a: Documento, b: Documento, estricta: bool = False) -> bool:
    """Las dos pueden ser de la misma jornada. `a` empezó antes o a la vez que `b`.

    - Hora con hora: inicios a menos de 6 horas y sin 12 horas sin actividad del suceso.
    - Día con día: el mismo o el siguiente (una noche se fecha por su tarde o por su madrugada);
      sin hora no se mide la actividad. Con `estricta` (lo que se une sin preguntar), solo el
      mismo día: dos días seguidos sin hora pueden ser una noche o dos sucesos (el sábado y el
      domingo de Leipzig/Halle, EODI-2026-00770 y EODI-2026-00773).
    - Día con hora: la hora local cae ese día (o en la madrugada del siguiente).
    - Con la fecha de publicación: el suceso es de ese día o de la víspera.
    """
    ta, tb = instante(a), instante(b)
    if con_hora(a) and con_hora(b):
        return abs(tb - ta) < INICIOS_HORA and tb - ultima_actividad(a) <= SIN_ACTIVIDAD
    if "fin" in a["tiempo"] and con_hora(b) and tb - ultima_actividad(a) > SIN_ACTIVIDAD:
        # Con un fin conocido sí se miden las 12 horas sin actividad.
        return False
    pais = str(a["lugar"].get("pais", ""))
    clase_a, dias_a = _dias_de(a, pais, estricta)
    clase_b, dias_b = _dias_de(b, pais, estricta)
    if "fin" in a["tiempo"]:
        # Un suceso que pasa de medianoche abarca también el día de su fin.
        dias_a.add(dia_local(ultima_actividad(a), pais))
    # Un pasado sin día («la semana pasada»): cualquier día de su ventana (proceso/fechas.py).
    dias_a |= ventana_pasada(a)
    dias_b |= ventana_pasada(b)
    if clase_a == clase_b == "dia":
        return abs((min(dias_b) - min(dias_a)).days) <= (0 if estricta else 1)
    return bool(dias_a & dias_b)


def _en_orden(a: Documento, b: Documento) -> tuple[Documento, Documento]:
    primero, segundo = sorted((a, b), key=lambda d: (d["tiempo"]["inicio"]["valor"], d["id"]))
    return primero, segundo


def misma_jornada(a: Documento, b: Documento, estricta: bool = False) -> bool:
    """`misma_ventana` sin tener que saber cuál empezó antes."""
    return misma_ventana(*_en_orden(a, b), estricta=estricta)


def _cerca_en_el_tiempo(a: Documento, b: Documento) -> bool:
    """Pueden ser de la misma jornada y hay que preguntarlo."""
    if all(d["tiempo"]["inicio"]["precision"] == "dia" or con_hora(d) for d in (a, b)):
        # Dos fechas escritas: el mismo día local o la misma noche.
        return abs(instante(a) - instante(b)) <= VENTANA_PAR_ESCRITA and misma_jornada(a, b)
    if abs(instante(a) - instante(b)) <= VENTANA_PAR:
        return True
    # Con la fecha de publicación, también la primera noticia.
    return abs(momento_primera_noticia(a) - momento_primera_noticia(b)) <= VENTANA_PAR


def fecha_verificada(documento: Documento) -> bool:
    """El día del inicio lo escribe una fuente (o lo da una autoridad o un parte)."""
    origen = documento["tiempo"].get("origen_inicio", {}).get("tipo")
    return origen in fechas.VERIFICADOS


def fecha_firme(incidente: Documento) -> bool:
    """El inicio sale de una frase con su día (no es la fecha de publicación ni aproximado)."""
    inicio = incidente["tiempo"]["inicio"]
    origen = incidente["tiempo"].get("origen_inicio") or {}
    con_dia = inicio.get("precision") in ("dia", "hora", "minuto")
    return con_dia and origen.get("tipo") not in ("publicacion", None)


def fecha_aproximada(incidente: Documento) -> bool:
    """La fecha es la de publicación o aproximada: sin una frase que la dé, no se publica."""
    origen = incidente["tiempo"].get("origen_inicio") or {}
    return incidente["tiempo"]["inicio"].get("precision") == APROXIMADA or (
        origen.get("tipo") == "publicacion"
    )


def fechas_distintas(incidente: Documento, otra: Documento) -> str | None:
    """Las dos fichas tienen fechas firmes a más de DIAS_FIRMES días: el texto de las dos fechas,
    o None. Un mismo suceso con dos días firmes tan separados casi siempre son dos sucesos (en la
    prueba del 28 de octubre de 2026, el ataque a buques frente a Bulgaria del 12 de octubre,
    EODI-2026-00512, salía unido al del 6, EODI-2026-00489): si quien lee las fuentes insiste en
    que es el mismo, lo decide una revisión."""
    if not (fecha_firme(incidente) and fecha_firme(otra)):
        return None
    a, b = instante(incidente), instante(otra)
    if abs((a - b).total_seconds()) <= DIAS_FIRMES * 86400:
        return None
    return f"{a.date().isoformat()} y {b.date().isoformat()}"


def otro_dia_lejano(incidente: Documento, dia: str) -> bool:
    """El día que da una frase está a más de DIAS_FIRMES de la fecha firme de la ficha: un día
    sacado de una frase no se cambia por otro lejano sin revisión."""
    nuevo = datetime.strptime(dia, "%Y-%m-%d").replace(tzinfo=UTC)
    distancia = abs((nuevo - instante(incidente)).total_seconds())
    return fecha_firme(incidente) and distancia > DIAS_FIRMES * 86400


# --- Los cierres ------------------------------------------------------------------------------


def noche_del_cierre(documento: Documento) -> date | None:
    """La noche (el día local de su tarde) de un cierre con el día sabido: con hora, la de la
    hora local (la madrugada es de la noche anterior); con el día escrito, ese día. None si no
    hubo cierre o si el día es el de la publicación."""
    if (documento.get("consecuencias", {}).get("cierre") or {}).get("valor") != "si":
        return None
    inicio = documento["tiempo"]["inicio"]
    momento = leer_instante(inicio)
    if inicio["precision"] == "dia":
        return momento.date()
    if inicio["precision"] in PRECISIONES_HORA:
        return dia_local(momento - MADRUGADA, str(documento["lugar"].get("pais", "")))
    return None


def noches_del_cierre(documento: Documento) -> set[date]:
    """Las noches (el día local de su tarde) en que pudo ser un cierre con el día sabido: con
    hora, una sola (`noche_del_cierre`). Con el día a secas, la de ese día; y también la de la
    víspera si su primera noticia salió antes de la tarde de ese día: entonces el cierre no fue
    esa tarde, sino de madrugada, que es la noche que empezó la víspera (una noche se fecha por
    su tarde o por su madrugada: «in der Nacht auf Dienstag (13. Oktober)», «am frühen
    Dienstagmorgen»). Vacío si no hubo cierre o si el día es el de la publicación."""
    unica = noche_del_cierre(documento)
    if unica is None:
        return set()
    if documento["tiempo"]["inicio"]["precision"] != "dia" or not documento.get("fuentes"):
        return {unica}
    suyo = str(documento["lugar"].get("pais", ""))
    zona = fechas.zona(suyo)
    primera = momento_primera_noticia(documento)
    local = primera.astimezone(zona) if zona else primera
    antes_de_la_tarde = (local.date(), local.hour) < (unica, HORA_TARDE)
    return {unica, unica - timedelta(days=1)} if antes_de_la_tarde else {unica}


def cierres_de_noches_distintas(a: Documento, b: Documento) -> bool:
    """Dos cierres del mismo sitio en noches distintas son dos incidentes, aunque las noticias
    del segundo salgan al día siguiente del primero (Lieja, 8 y 9 de noviembre de 2025). Con el
    día a secas en alguno de los dos, solo si ninguna de sus noches posibles es la del otro: el
    cierre de Kaunas fechado el 11 de noviembre de 2026 por una nota de las 02:30 de ese día
    (EODI-2026-00779) es de la noche que empezó el 10 a las 23:00 (EODI-2026-00792)."""
    noches_a, noches_b = noches_del_cierre(a), noches_del_cierre(b)
    return bool(noches_a) and bool(noches_b) and noches_a.isdisjoint(noches_b)


def _cierre(documento: Documento) -> bool:
    return (documento.get("consecuencias", {}).get("cierre") or {}).get("valor") == "si"


def repite_un_cierre_anterior(anterior: Documento, posterior: Documento) -> bool:
    """El posterior es otro cierre: sus fuentes dicen que se repite («opnieuw stilgelegd», «de
    nouveau», «erneut») y se publican un día después de la noche del anterior. Vale aunque su
    fecha sea la de publicación (Lieja: el cierre del domingo 9 de noviembre de 2025, contado
    como «opnieuw», no es el del sábado 8)."""
    # Con la fecha del suceso sabida decide la noche (cierres_de_noches_distintas): «igen» y
    # «vėl» también dicen que se reabrió o que pasó en otro sitio.
    if posterior["tiempo"]["inicio"]["precision"] != APROXIMADA:
        return False
    if not (_cierre(anterior) and _cierre(posterior)):
        return False
    noche_ = noche_del_cierre(anterior) or leer_instante(anterior["tiempo"]["inicio"]).date()
    pais = str(posterior["lugar"].get("pais", ""))
    filtro_ = filtro()
    return any(
        filtro_.repite(str(fuente.get("frase_origen", "")))
        and dia_local(leer_instante(fuente["fecha"]), pais) > noche_
        for fuente in posterior["fuentes"]
        if not fuente.get("es_autoridad")
    )


# --- Lo que decidió una revisión o el experto -------------------------------------------------

REVISADOS = Path(__file__).resolve().parent.parent / "configuracion" / "incidentes_revisados.json"
# Motivo de las fusiones revisadas a mano (recogida/revisados.py) y, dentro de ellas, de las que
# hizo el control leyendo las fuentes (recogida/control_fichas.unir).
PREFIJO_REVISADA = "revisión: "
PREFIJO_CONTROL = PREFIJO_REVISADA + "control de fichas: "


@cache
def separaciones_distintas(ruta: Path = REVISADOS) -> frozenset[str]:
    """Los incidentes separados a mano (sección `separar`) con `"distintos": true`: sus partes
    son sucesos distintos que la regla de fusión no vuelve a juntar. Sin la marca, una parte
    puede acabar con razón en la misma ficha que otra (la que coincide con otra ficha,
    `coincide_con`, o dos registros de la misma parte)."""
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    return frozenset(e["incidente"] for e in datos.get("separar", []) if e.get("distintos"))


@cache
def pares_distintos(ruta: Path = REVISADOS) -> frozenset[frozenset[str]]:
    """Los pares que una revisión dio por sucesos distintos sin separar ninguna ficha (sección
    `distintos`): se enlazan como sucesos relacionados y ninguna unión automática los junta. El
    29 de octubre de 2026 la regla unió EODI-2026-00538 (un blanco aéreo a las 17:38) en
    EODI-2026-00541 (el petrolero, hacia las 20:00), que una revisión había dado por distintos sin
    dejarlo escrito."""
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    return frozenset(frozenset(e["incidentes"]) for e in datos.get("distintos", []))


@cache
def grupos_unidos_a_mano(ruta: Path = REVISADOS) -> tuple[frozenset[str], ...]:
    """Los grupos de fichas que una revisión unió a mano (sección `unir`)."""
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    return tuple(frozenset(g["registros"]) for g in datos.get("unir", []))


def _articulo(fuente_id: str) -> str:
    """El artículo de una fuente: una declaración citada en él («…-declaracion-2») es del mismo."""
    return fuente_id.partition("-declaracion-")[0]


@cache
def partes_por_articulo(ruta: Path = REVISADOS) -> dict[str, frozenset[tuple[str, int]]]:
    """Por artículo, la parte de una separación (sección `separar`, incidente y número de parte)
    a la que pertenece. Solo cuentan las partes que son sucesos, y no los artículos que una
    revisión puso en dos partes de la misma separación (cuentan los dos sucesos)."""
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    por_articulo: dict[str, set[tuple[str, int]]] = defaultdict(set)
    for revision in datos.get("separar", []):
        de_esta: dict[str, set[int]] = defaultdict(set)
        for n, parte in enumerate(revision.get("partes", [])):
            if parte.get("es_suceso", True):
                for fuente in parte.get("fuentes", []):
                    de_esta[_articulo(fuente)].add(n)
        for articulo, partes in de_esta.items():
            if len(partes) == 1:
                por_articulo[articulo].add((revision["incidente"], next(iter(partes))))
    return {a: frozenset(p) for a, p in por_articulo.items()}


def partes_de_separacion(documento: Documento) -> frozenset[tuple[str, int]]:
    """Las partes de separaciones revisadas de las que la ficha lleva algún artículo."""
    mapa = partes_por_articulo()
    return frozenset(
        parte
        for fuente in documento.get("fuentes", [])
        for parte in mapa.get(_articulo(str(fuente.get("id", ""))), ())
    )


def de_partes_separadas(a: Documento, b: Documento) -> bool:
    """Uno lleva un artículo de una parte de una separación revisada y el otro, uno de otra parte
    de la misma: son sucesos distintos desde que nace la ficha de cada parte, con el identificador
    que tenga y antes de que se enlacen como relacionados. El 30 de octubre de 2026 la parte del
    29/10 de EODI-2025-00178 nació como EODI-2025-00472 y la regla la volvió a fundir en 00178 en
    la misma recogida (fusión 2438), porque la separación no llevaba la marca «distintos»."""
    partes_a = partes_de_separacion(a)
    if not partes_a:
        return False
    partes_b = partes_de_separacion(b)
    # Si comparten una parte de esa separación, cuentan al menos en parte el mismo suceso (dos
    # registros de una parte, o una ficha que todavía junta varias): eso lo deciden las reglas.
    return any(
        {n for r, n in partes_a if r == revision}.isdisjoint(
            {n for r, n in partes_b if r == revision}
        )
        for revision in {r for r, _ in partes_a} & {r for r, _ in partes_b}
    )


def separados_por_revision(a: Documento, b: Documento) -> bool:
    """Uno lleva al otro entre sus sucesos relacionados por una separación marcada como de
    sucesos distintos, o una revisión los dio por distintos (`pares_distintos`). El 19 de
    octubre de 2026 la regla juntó otra vez el desvío del 19/10/2025 en Fuerteventura
    (EODI-2025-00468), fechado por su publicación, con las esperas de la víspera
    (EODI-2025-00397), de las que se separó."""
    if frozenset((a["id"], b["id"])) in pares_distintos():
        return True
    distintas = separaciones_distintas()
    return any(
        r.get("id") == otro["id"] and r.get("separado_de") in distintas
        for uno, otro in ((a, b), (b, a))
        for r in uno.get("relacionados", [])
    )


def distintos_en(decisiones: dict[str, Documento]) -> frozenset[frozenset[str]]:
    """Los pares que el experto dio por sucesos distintos, de las decisiones del control
    («par:<a>|<b>»): la decisión escalada, no la que da el plazo de un dudoso."""
    return frozenset(
        frozenset(clave.split(":", 1)[1].split("|"))
        for clave, d in decisiones.items()
        if clave.startswith("par:")
        and d.get("decision") == "distinto"
        and d.get("escalado")
        and not d.get("plazo")
    )


def distintos_del_experto(almacen: "Almacen") -> frozenset[frozenset[str]]:
    """Los pares que el experto dio por sucesos distintos en el control de las fichas: ninguna
    unión automática los junta; si más tarde alguien quiere unirlos, queda como propuesta para
    revisar."""
    return distintos_en(almacen.controles("par:"))


def autoridades_decididas(almacen: "Almacen", *ids: str) -> dict[str, dict[str, str]]:
    """Por ficha, los países de sus autoridades que comprobó el filtro de entrada con su frase
    (nombre -> país): con ellos se sabe si el país de una ficha es firme
    (`paises_de_autoridades`). Sin `ids`, las de todas."""
    if ids:
        decisiones: dict[str, Documento] = {}
        for id_ in ids:
            decisiones |= almacen.controles(f"entrada:{id_}")
    else:
        decisiones = almacen.controles("entrada:")
    return {
        clave.split(":", 1)[1]: dict(decision.get("autoridades") or {})
        for clave, decision in decisiones.items()
        if decision.get("autoridades")
    }


def veredicto_en(
    almacen: "Almacen", a: Documento, b: Documento,
    del_experto: frozenset[frozenset[str]] | None = None, vigente: bool = False,
) -> "Veredicto":  # fmt: skip
    """`veredicto` con lo que guarda la base: los pares que el experto dio por distintos y las
    autoridades que el filtro de entrada comprobó en cada una."""
    decididas = autoridades_decididas(almacen, str(a["id"]), str(b["id"]))
    return veredicto(
        a, b, distintos_del_experto(almacen) if del_experto is None else del_experto,
        decididas.get(str(a["id"])), decididas.get(str(b["id"])), vigente,
    )  # fmt: skip


def uniones_a_mano(almacen: "Almacen") -> frozenset[frozenset[str]]:
    """Los pares de las fusiones vigentes revisadas a mano (recogida/revisados.py: `unir` y la
    parte de una separación que coincide con otra ficha), no las del control de las fichas."""
    return frozenset(
        frozenset((f["absorbido"], f["destino"]))
        for f in almacen.fusiones()
        if not f["revertida"]
        and f["motivo"].startswith(PREFIJO_REVISADA)
        and not f["motivo"].startswith(PREFIJO_CONTROL)
    )


def no_se_unen(a: Documento, b: Documento, del_experto: frozenset[frozenset[str]]) -> bool:
    """Una revisión o el experto los dio por sucesos distintos."""
    return separados_por_revision(a, b) or frozenset((a["id"], b["id"])) in del_experto


def no_se_juntan(a: Documento, b: Documento, del_experto: frozenset[frozenset[str]]) -> bool:
    """Para una unión nueva (la regla o el control): además de `no_se_unen`, las fichas de partes
    distintas de una separación (`de_partes_separadas`). Las uniones ya hechas no se comparan así:
    una ficha anterior a la separación puede llevar artículos de varias partes y estar bien unida
    (EODI-2025-00172 en EODI-2025-00154, el cierre de Copenhague del 22/09/2025); esas las mira la
    separación con sus propios registros (recogida/revisados._deshacer_entre_partes)."""
    return no_se_unen(a, b, del_experto) or de_partes_separadas(a, b)


def enlazados_como_relacionados(a: Documento, b: Documento) -> bool:
    """Una de las dos lleva a la otra entre sus sucesos relacionados (una separación revisada)."""
    relacionados = {r.get("id") for r in a.get("relacionados", [])} | {
        r.get("id") for r in b.get("relacionados", [])
    }
    return a["id"] in relacionados or b["id"] in relacionados


# --- El país ----------------------------------------------------------------------------------

FUERA_DE_PAIS = frozenset({"NATO", "OTAN", "EU", "UE"})
# Los países que se miran también cuando el lugar es vago: los vecinos por tierra (y por un
# estrecho) y los ribereños de cada mar.
MARES: dict[str, frozenset[str]] = {
    "negro": frozenset({"BG", "RO", "UA", "TR", "GE", "MD"}),
    "baltico": frozenset({"SE", "FI", "EE", "LV", "LT", "PL", "DE", "DK", "RU"}),
    "norte": frozenset({"GB", "NO", "DK", "DE", "NL", "BE", "FR"}),
    "mediterraneo": frozenset(
        {"ES", "FR", "MC", "IT", "MT", "SI", "HR", "BA", "ME", "AL", "GR", "TR", "CY"}
    ),
}
VECINOS: dict[str, frozenset[str]] = {
    p: frozenset(v.split())
    for p, v in {
        "PT": "ES", "ES": "PT FR AD", "FR": "ES AD MC IT CH DE LU BE GB",
        "BE": "FR LU DE NL GB", "NL": "BE DE GB", "LU": "BE FR DE",
        "DE": "DK NL BE LU FR CH AT CZ PL", "DK": "DE SE NO", "NO": "SE FI RU DK GB",
        "SE": "NO FI DK", "FI": "SE NO RU EE", "EE": "LV RU FI", "LV": "EE LT BY RU",
        "LT": "LV BY PL RU", "PL": "DE CZ SK UA BY LT RU", "CZ": "DE PL SK AT",
        "SK": "CZ PL UA HU AT", "AT": "DE CZ SK HU SI IT CH LI", "CH": "DE FR IT AT LI",
        "IT": "FR CH AT SI SM VA MT", "SI": "IT AT HU HR", "HR": "SI HU RS BA ME",
        "HU": "AT SK UA RO RS HR SI", "RO": "HU UA MD BG RS", "MD": "RO UA",
        "BG": "RO RS MK GR TR", "GR": "AL MK BG TR CY", "CY": "GR TR", "IE": "GB",
        "GB": "IE FR BE NL NO", "UA": "PL SK HU RO MD BY RU", "RS": "HU RO BG MK ME BA HR",
        "BA": "HR RS ME", "ME": "HR BA RS AL", "AL": "ME MK GR", "MK": "RS BG GR AL",
        "MT": "IT", "TR": "BG GR GE", "GE": "TR RU", "BY": "PL LT LV UA RU",
    }.items()
}  # fmt: skip


def pais(ficha: Documento) -> str:
    return str(ficha["lugar"]["pais"])


def vago(incidente: Documento) -> bool:
    """El lugar no sitúa el suceso en un país solo: el mar, una frontera, una región o el país."""
    lugar = incidente["lugar"]
    zona = incidente.get("zona") or {}
    return (
        lugar.get("nivel") in {"pais", "region"}
        or "punto" not in lugar
        or zona.get("grupo") == "frontera"
    )


def paises(incidente: Documento) -> frozenset[str]:
    """El país de la ficha y, con el lugar vago, sus vecinos y los ribereños de sus mares."""
    suyo = pais(incidente)
    if not vago(incidente):
        return frozenset({suyo})
    mares = [m for m in MARES.values() if suyo in m]
    return frozenset({suyo}) | VECINOS.get(suyo, frozenset()) | frozenset().union(*mares)


def nombra_el_pais(codigo: str, texto: str) -> bool:
    """El texto nombra el país (el principio de su nombre en alguna lengua de Natural Earth:
    «lithu» vale para «Lithuanian officials»)."""
    normal = normalizar(texto)
    return any(n[:5] in normal for n in fronteras.nombres_del_pais(codigo) if len(n) >= 5)


def paises_de_autoridades(
    incidente: Documento, decididas: dict[str, str] | None = None
) -> frozenset[str]:
    """Los países de las autoridades que cita la ficha: los que el filtro de entrada comprobó
    con su frase (`decididas`: nombre -> país, de su decisión), los de sus fuentes de autoridad
    que se saben por la tabla o por la fuente oficial que las publica, y el suyo si el nombre de
    una de ellas lo dice («Lithuanian officials», «Lettische Streitkräfte»)."""
    paises_ = {str(p) for p in (decididas or {}).values() if p}
    suyo = pais(incidente)
    for fuente in incidente.get("fuentes", []):
        if not fuente.get("es_autoridad") or fuente.get("publica", True) is False:
            continue
        medio = str(fuente.get("medio") or "")
        conocido = autoridades.pais_del_organismo(medio)
        if conocido:
            paises_.add(conocido)
        elif nombra_el_pais(suyo, autoridades.DECLARACION_CITADA.sub(r"\1", medio)):
            paises_.add(suyo)
    return frozenset(paises_ - FUERA_DE_PAIS)


def pais_firme(incidente: Documento, decididas: dict[str, str] | None = None) -> bool:
    """El país de la ficha es seguro: cita a una autoridad de ese país."""
    return pais(incidente) in paises_de_autoridades(incidente, decididas)


def paises_distintos(
    a: Documento, b: Documento,
    de_a: dict[str, str] | None = None, de_b: dict[str, str] | None = None,
) -> str | None:  # fmt: skip
    """Por qué las dos fichas son de países distintos y por eso sucesos distintos, o None.

    Cada país cuenta su suceso. El 11 de noviembre de 2026 el filtro unió la ficha de Lituania
    (EODI-2026-00779: el aviso del Centro Nacional de Gestión de Crisis y el aeropuerto de
    Kaunas) a la de un resumen con el lugar en Letonia (EODI-2026-00778), y de Lituania no salió
    nada; y desde octubre el dron derribado sobre Letonia el 14 de agosto (EODI-2026-00218)
    estaba dentro de una ficha de Tulcea, en Rumanía (EODI-2026-00230). Sin autoridad de ninguno
    de los dos países (un buque en el mar, una frontera) el país de una puede estar mal: decide
    el experto."""
    pais_a, pais_b = pais(a), pais(b)
    if pais_a == pais_b:
        return None
    if pais_firme(a, de_a) or pais_firme(b, de_b):
        return (
            f"países distintos ({pais_a} y {pais_b}) con una autoridad del suyo: cada país "
            "cuenta su suceso"
        )
    return None


# --- La nota de una noche y sus alertas -------------------------------------------------------

MOTIVO_RESUMEN_EN = (
    "The authority's summary note of the night and its zone alerts of that same night are the "
    "same event."
)
FUENTES_OFICIALES = REVISADOS.parent / "fuentes_oficiales.json"


@cache
def _fuentes_por_zonas(ruta: Path = FUENTES_OFICIALES) -> tuple[Documento, ...]:
    """Las fuentes oficiales que dan sus alertas por zonas (`alertas_por_zona`)."""
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    return tuple(f for f in datos["fuentes"] if f.get("alertas_por_zona"))


def notas_de(incidente: Documento, fuente: Documento) -> list[str]:
    """Lo que la ficha guarda de las notas de esa fuente oficial: el título de las enlazadas y
    la frase de las que entraron como artículo de su página (antes de enlazarse) o como
    declaración suya."""
    prefijo = f"{fuente['id']}-"
    sitio = urlsplit(str(fuente["url"])).netloc
    return [
        str(f.get("frase_origen") or "") for f in incidente["fuentes"]
        if (str(f.get("id", "")).startswith(prefijo) and f.get("es_autoridad"))
        or urlsplit(str(f.get("enlace") or "")).netloc == sitio
    ]  # fmt: skip


def resumen_de_la_misma_noche(incidente: Documento, otra: Documento) -> str | None:
    """Por qué las dos fichas son el mismo suceso sin preguntarlo, o None: una es la nota-resumen
    de una autoridad que da sus alertas por zonas y la otra, las alertas de esa misma noche en el
    mismo país. La nota-resumen no nombra una zona («Naktī uz 11. novembri Latvijas gaisa telpā
    ielidoja trīs bezpilota lidaparāti»); las alertas, sí.

    El 11 de noviembre de 2026 el experto dio por distintas la ficha de las alertas letonas de la
    noche (EODI-2026-00777, municipios) y la de la nota con la que las Fuerzas Armadas contaron
    esa misma noche a la mañana siguiente (EODI-2026-00784, el país), y salieron las dos."""
    suyo = pais(incidente)
    if suyo != pais(otra):
        return None
    dias = abs((instante(incidente).date() - instante(otra).date()).days)
    if dias > DIAS_MISMA_NOCHE:
        return None
    for fuente in _fuentes_por_zonas():
        if fuente["pais"] != suyo:
            continue
        hora = str(fuente["alertas_por_zona"]["hora"])
        textos = [" . ".join(notas_de(ficha, fuente)) for ficha in (incidente, otra)]
        if not all(textos):
            continue
        for de_la_noche, de_las_alertas in (textos, textos[::-1]):
            # La nota de la noche: no nombra ninguna zona y habla de «la noche». Las alertas:
            # nombran su zona y escriben su hora.
            if (
                not alertas_zona.zonas(de_la_noche, suyo)
                and fechas.nombra_la_noche(de_la_noche, str(fuente["idioma"]))
                and alertas_zona.zonas(de_las_alertas, suyo)
                and alertas_zona.horas(de_las_alertas, hora)
            ):
                return (
                    f"la nota de {fuente['medio']} que cuenta la noche y sus alertas por zonas "
                    "de esa misma noche son el mismo suceso"
                )
    return None


# --- El veredicto de dos fichas ---------------------------------------------------------------


def separados(a: Documento, b: Documento) -> bool:
    """Una revisión los separó o los dio por distintos (sucesos relacionados) o son cierres de
    noches distintas: ni se unen solas ni se preguntan."""
    return (
        enlazados_como_relacionados(a, b)
        or separados_por_revision(a, b)
        or de_partes_separadas(a, b)
        or cierres_de_noches_distintas(a, b)
    )


def encajan(a: Documento, b: Documento) -> bool:
    """El mismo sitio y la misma jornada, sin nada que los separe: el mismo suceso sin preguntar
    (regla 6). Un lado puede no ser una ficha sino el punto y el día de una nota oficial o de un
    documento."""
    primero, segundo = _en_orden(a, b)
    return (
        not separados_por_revision(a, b)
        and not de_partes_separadas(a, b)
        and mismo_sitio(a, b)
        and not cierres_de_noches_distintas(a, b)
        and not repite_un_cierre_anterior(primero, segundo)
        and misma_ventana(primero, segundo, estricta=True)
    )


def todos_encajan(documentos: list[Documento]) -> bool:
    """Cada par de la lista encaja (mismo sitio y misma jornada)."""
    return all(encajan(a, b) for n, a in enumerate(documentos) for b in documentos[n + 1 :])


def candidatos(a: Documento, b: Documento) -> bool:
    """Pueden ser el mismo suceso y lo tiene que decidir quien lee las fuentes."""
    return (
        a["id"] != b["id"]
        and _cerca_en_el_tiempo(a, b)
        and _cerca_en_el_espacio(a, b)
        and _mismo_tipo_de_sitio(a, b)
        and not separados(a, b)
    )


def veredicto(
    a: Documento, b: Documento,
    del_experto: frozenset[frozenset[str]] = frozenset(),
    de_a: dict[str, str] | None = None, de_b: dict[str, str] | None = None,
    vigente: bool = False,
) -> Veredicto:  # fmt: skip
    """Lo que la definición dice de dos fichas sin leer sus fuentes. `del_experto`: los pares
    que el experto dio por distintos (`distintos_del_experto`); `de_a` y `de_b`: los países de
    las autoridades de cada una que comprobó el filtro de entrada (si los hay). Con `vigente`
    se juzga una unión ya hecha: una ficha anterior a una separación puede llevar artículos de
    varias partes y estar bien unida (EODI-2025-00172 en EODI-2025-00154, el cierre de
    Copenhague del 22/09/2025), así que las partes de una separación solo cuentan para una
    unión nueva."""
    par = frozenset((str(a["id"]), str(b["id"])))
    if any(par <= grupo for grupo in grupos_unidos_a_mano()):
        return Veredicto(MISMO, REGLA_REVISION, "una revisión las unió a mano")
    if separados_por_revision(a, b) or (not vigente and de_partes_separadas(a, b)):
        return Veredicto(DISTINTOS, REGLA_REVISION, "una revisión las dio por sucesos distintos")
    de_paises = paises_distintos(a, b, de_a, de_b)
    if de_paises is not None:
        return Veredicto(DISTINTOS, REGLA_PAISES, de_paises)
    de_la_noche = resumen_de_la_misma_noche(a, b)
    if de_la_noche is not None:
        return Veredicto(MISMO, REGLA_RESUMEN, de_la_noche)
    if par in del_experto:
        return Veredicto(DISTINTOS, REGLA_EXPERTO, "el experto las dio por sucesos distintos")
    if pais(a) == pais(b):
        primero, segundo = _en_orden(a, b)
        if cierres_de_noches_distintas(a, b) or repite_un_cierre_anterior(primero, segundo):
            return Veredicto(DISTINTOS, REGLA_CIERRES, "dos cierres en noches distintas")
        if mismo_sitio(a, b) and misma_ventana(primero, segundo, estricta=True):
            return Veredicto(MISMO, REGLA_SITIO_Y_JORNADA, MOTIVO_SITIO_Y_JORNADA)
        if candidatos(a, b):
            return Veredicto(EXPERTO, REGLA_CANDIDATAS, "cerca en el tiempo y en el espacio")
        return Veredicto(AJENAS)
    if pais(b) in paises(a) or pais(a) in paises(b):
        # Otro país sin autoridad de ninguno y con el lugar vago: el país de una puede estar mal.
        return Veredicto(EXPERTO, REGLA_CANDIDATAS, "países vecinos con el lugar vago")
    return Veredicto(AJENAS)


# Al repasar una ficha ya publicada como si fuera nueva (recogida/repaso_entrada.py) una unión
# es imposible si las noticias de una ficha son todas de antes del día firme de la otra (con
# este margen por la hora local), o si las dos tienen un lugar preciso a más de esta distancia.
# Muestreo del 28 de octubre de 2026: el aeropuerto de Vilna del 25 y del 26 de septiembre
# (EODI-2025-00060 y 00004) y dos drones de la misma noche en Moldavia, en Hîrbovăț y en Orhei
# (EODI-2026-00168 y 00636), salían unidos.
MARGEN_DIA_H = 3
DISTANCIA_MAX_KM = 25.0
PRECISOS = frozenset({"localidad", "instalacion"})


def _ultima_noticia(incidente: Documento) -> datetime | None:
    momentos = [leer_instante(f["fecha"]) for f in incidente.get("fuentes", []) if f.get("fecha")]
    return max(momentos) if momentos else None


def imposible_al_repasar(incidente: Documento, otra: Documento) -> str | None:
    """Por qué dos fichas ya publicadas no pueden ser el mismo suceso al repasarlas, o None: son
    de países distintos (cada país cuenta su incursión: el Shahed que cruzó Moldavia y cayó en
    Rumanía, EODI-2026-00171 y 00106), las noticias de una son todas de antes del día firme de
    la otra, o sus lugares precisos están a más de DISTANCIA_MAX_KM. Más estricto que
    `nunca_el_mismo`: el repaso une fichas que llevan tiempo publicadas."""
    if pais(incidente) != pais(otra):
        return f"países distintos ({pais(incidente)} y {pais(otra)})"
    for una, dos in ((incidente, otra), (otra, incidente)):
        if not fecha_firme(una):
            continue
        dia = instante(una).replace(hour=0, minute=0, second=0, microsecond=0)
        ultima = _ultima_noticia(dos)
        if ultima is not None and ultima < dia - timedelta(hours=MARGEN_DIA_H):
            return f"las noticias de {dos['id']} son de antes del {dia.date().isoformat()}"
    a, b = incidente["lugar"], otra["lugar"]
    if {a.get("nivel"), b.get("nivel")} <= PRECISOS and "punto" in a and "punto" in b:
        km = _distancia_km(incidente, otra)
        if km > DISTANCIA_MAX_KM:
            return f"lugares a {km:.0f} km"
    return None


def nunca_el_mismo(
    a: Documento, b: Documento,
    de_a: dict[str, str] | None = None, de_b: dict[str, str] | None = None,
) -> str | None:  # fmt: skip
    """Por qué las dos fichas no pueden ser el mismo suceso diga lo que diga quien lee las
    fuentes (una regla firme que no es una decisión suya anterior), o None."""
    dicho = veredicto(a, b, de_a=de_a, de_b=de_b)
    return dicho.motivo if dicho.relacion == DISTINTOS else None


def pares_candidatos(
    activos: list[Documento], foco: set[str],
    criterio: Callable[[Documento, Documento], bool] = candidatos,
) -> list[tuple[Documento, Documento]]:  # fmt: skip
    """Los pares de candidatos con al menos uno del foco, primero los más cercanos en el
    tiempo. Con otro `criterio`, los pares que cumplen ese (la segunda lectura, con márgenes más
    amplios: proceso/segunda_lectura.py)."""
    pares: dict[str, tuple[Documento, Documento]] = {}
    por_pais: dict[str, list[Documento]] = {}
    for d in activos:
        por_pais.setdefault(d["lugar"]["pais"], []).append(d)
    for d in activos:
        if d["id"] not in foco:
            continue
        for otro in por_pais.get(d["lugar"]["pais"], []):
            if criterio(d, otro):
                pares.setdefault(clave_par(d["id"], otro["id"]), (d, otro))
    return sorted(pares.values(), key=lambda p: abs(instante(p[0]) - instante(p[1])))


def clave_par(a: str, b: str) -> str:
    uno, otro = sorted((a, b))
    return f"par:{uno}|{otro}"


def conjunto(
    incidente: Documento, activos: list[Documento],
    distintos: frozenset[frozenset[str]] = frozenset(),
) -> list[Documento]:  # fmt: skip
    """Las fichas activas con las que se compara una nueva, sin mirar la distancia: de sus
    países (`paises`), de 30 días antes a 3 después de su inicio o de su primera noticia, salvo
    las que una revisión separó y las que el experto ya dio por distintas de ella en el control
    (`distintos`: distintos_del_experto). Si son más de MAX_CONJUNTO, las del mismo tipo y las
    más cercanas en el tiempo.

    Un par que el experto dio por distinto comparando las fuentes de las dos no lo une nadie: si
    el filtro, que solo ve una línea de la otra, decía «el mismo», la ficha quedaba retenida como
    «propuesta para revisar» y, con las mismas fuentes, para siempre (EODI-2026-00778 frente a
    EODI-2026-00777, 11 de noviembre de 2026). La nota de una noche y sus alertas (regla 3) no
    pasan por aquí: se unen antes."""
    referencias = [instante(incidente), momento_primera_noticia(incidente)]
    validos = paises(incidente)
    elegidas = []
    for otra in activos:
        if otra["id"] == incidente["id"] or otra["lugar"]["pais"] not in validos:
            continue
        if frozenset((str(incidente["id"]), str(otra["id"]))) in distintos:
            continue
        momento = instante(otra)
        if not any(
            r - timedelta(days=DIAS_ANTES) <= momento <= r + timedelta(days=DIAS_DESPUES)
            for r in referencias
        ):
            continue
        if separados(incidente, otra):
            continue
        elegidas.append(otra)

    def orden(otra: Documento) -> tuple[int, float, str]:
        distancia = min(abs((instante(otra) - r).total_seconds()) for r in referencias)
        return (0 if otra.get("tipo") == incidente.get("tipo") else 1, distancia, otra["id"])

    return sorted(elegidas, key=orden)[:MAX_CONJUNTO]


# --- La noticia sobre un suceso anterior ------------------------------------------------------


def nota_posterior(documento: Documento) -> bool:
    """Vuelve sobre un suceso pasado: el día lo escribe una fuente (no es el de la publicación) y
    la primera noticia sale días después («el archivo de la investigación de los drones del 9 al
    10 de septiembre», publicado un año más tarde)."""
    if not fecha_verificada(documento) or documento["tiempo"]["inicio"]["precision"] == APROXIMADA:
        return False
    suceso = leer_instante(documento["tiempo"]["inicio"]).date()
    publicada = datetime.strptime(primera_noticia(documento)[:10], "%Y-%m-%d").date()
    return (publicada - suceso).days >= DIAS_NOTA_POSTERIOR


# Una noticia retrospectiva puede contar otra vez un suceso del mismo sitio de hasta estos días
# atrás; se comparan como mucho estas fichas, las más recientes.
DIAS_RETROSPECTIVA = 400
MAX_CANDIDATAS_RETROSPECTIVA = 6


def previas_del_sitio(incidente: Documento, activos: list[Documento]) -> list[Documento]:
    """Las fichas anteriores del mismo sitio (la misma instalación, o el mismo lugar sin
    instalación), con su fecha comprobada, de más reciente a más antigua, sin ventana de días: las
    que una noticia sobre un suceso anterior puede contar otra vez. Quien lee las fuentes dice si
    es una de ellas (se une a su ficha) o si no se sabe de cuándo es (no crea ficha)."""
    inicio = instante(incidente)
    desde = inicio - timedelta(days=DIAS_RETROSPECTIVA)
    previas = [
        d
        for d in activos
        if d["id"] != incidente["id"]
        and fecha_verificada(d)
        and desde <= instante(d) < inicio - timedelta(days=1)
        and mismo_sitio(incidente, d)
    ]
    return sorted(previas, key=instante, reverse=True)[:MAX_CANDIDATAS_RETROSPECTIVA]


def mismo_suceso_posterior(registrado: Documento, nota: Documento) -> bool:
    """`nota` es una nota posterior (nota_posterior) que cuenta el suceso de `registrado`: el mismo
    país y el mismo tipo, el mismo día (misma_ventana), y la nota no da un sitio distinto: o no
    tiene punto (solo el país o la región, y entonces la misma región si las dos la dicen) o su
    punto es el mismo sitio. La duda la resuelve quien llama: solo se une si hay un candidato."""
    if not nota_posterior(nota) or nota_posterior(registrado):
        return False
    if registrado["lugar"]["pais"] != nota["lugar"]["pais"] or registrado["tipo"] != nota["tipo"]:
        return False
    if con_punto(nota):
        if not con_punto(registrado) or not mismo_sitio(registrado, nota):
            return False
    else:
        regiones = [normalizar(str(d["lugar"].get("region", ""))) for d in (registrado, nota)]
        if all(regiones) and regiones[0] != regiones[1]:
            return False
    if cierres_de_noches_distintas(registrado, nota):
        return False
    # Se une sin preguntar: la misma jornada, no la de al lado (Lieja, los cierres del 8 y del 9
    # de noviembre de 2025).
    return misma_jornada(registrado, nota, estricta=True)


# --- La ficha que queda -----------------------------------------------------------------------

CLASE_FECHA = {"minuto": 0, "hora": 0, "dia": 1, APROXIMADA: 2}


def de_mejor_fecha(documentos: list[Documento]) -> list[Documento]:
    """Los de la clase de fecha más precisa: con hora, con solo el día o con la de publicación."""
    if len(documentos) < 2:
        return documentos
    clase = {d["id"]: CLASE_FECHA.get(d["tiempo"]["inicio"]["precision"], 2) for d in documentos}
    mejor = min(clase.values())
    return [d for d in documentos if clase[d["id"]] == mejor]


def destino_de(
    uno: Documento, otro: Documento, publicados: frozenset[str] = frozenset()
) -> tuple[Documento, Documento]:
    """(destino, absorbido) de dos incidentes que encajan. Queda el que ya estaba publicado si
    solo lo estaba uno (su enlace sigue valiendo); si no, el de un año anterior (entre una
    ficha de 2025 y una de 2026 queda la de 2025: EODI-2025-00199, Bruselas, se quedó dentro
    de EODI-2026-00094 por tener esta más fuentes), después el que tiene más fuentes oficiales
    leídas directamente, el de más fuentes, el que se conoció antes (su primera noticia salió
    antes) y, a la par, el de número más bajo. Una noticia que vuelve semanas después sobre un
    suceso no le quita su número: Copenhague sigue siendo el EODI-2025-00154, con las notas de
    la policía y casi 300 noticias."""

    def clave(d: Documento) -> tuple[bool, str, int, int, str, str]:
        oficiales = sum(1 for f in d["fuentes"] if f["fiabilidad"] == "A" and f.get("es_autoridad"))
        return (d["id"] not in publicados, d["id"][:9], -oficiales, -len(d["fuentes"]),
                primera_noticia(d), d["id"])  # fmt: skip

    primero, segundo = sorted((uno, otro), key=clave)
    return primero, segundo


def orden_registro(id_: str) -> tuple[int, int, str]:
    """El orden en que se dio de alta un registro: su año y su número (EODI-2025-00243 va antes
    que EODI-2025-00247). La fecha de alta guardada no sirve: cambia al reconstruir la base."""
    partes = id_.split("-")
    try:
        return int(partes[1]), int(partes[2]), id_
    except (IndexError, ValueError):
        return 9999, 99999, id_


def mas_antiguo(a: Documento, b: Documento) -> tuple[Documento, Documento]:
    """(el que se conserva, el que se une) cuando lo decide quien lee las fuentes: el más
    antiguo, el de número de registro menor. Hasta el 14 de octubre de 2026 era el de fecha de
    alta más antigua, que cambia al reconstruir la base: en Moldavia (28 de noviembre de 2025)
    quedó EODI-2025-00247 en vez de 00243."""
    uno, otro = sorted((a, b), key=lambda d: orden_registro(d["id"]))
    return uno, otro


def queda(
    a: Documento, b: Documento, sale: Callable[[str], bool] | None = None
) -> tuple[Documento, Documento]:
    """(la que se conserva, la que se une) cuando lo decide quien lee las fuentes: la que tiene
    su página en la web si solo la tiene una (`sale`: Almacen.sale_en_la_web), porque una ficha
    publicada no se funde en una que nunca salió; si no, la más antigua (`mas_antiguo`).

    Las fichas de Lituania de la noche del 10 al 11 de noviembre de 2026 que quedaron dentro de
    una ficha retirada (EODI-2026-00779 y siguientes) tienen el número más bajo que la ficha
    publicada de ese suceso (EODI-2026-00792): al volver se unen a ella, y no al revés."""
    if sale is not None:
        sale_a, sale_b = sale(str(a["id"])), sale(str(b["id"]))
        if sale_a != sale_b:
            return (a, b) if sale_a else (b, a)
    return mas_antiguo(a, b)


def toma_el_tiempo(destino: Documento, absorbido: Documento) -> bool:
    """La ficha que queda toma la fecha de la que se une: solo si a la suya le falta el día
    escrito por una fuente, la otra lo tiene y ese día puede ser el de su jornada (el suyo, la
    víspera o el siguiente). La fecha sale del suceso, no de la ficha que llega: una noticia
    sobre un suceso anterior fechada por otro día no se lo cambia. EODI-2025-00049 (el dron de
    Otopeni del domingo 28 de septiembre de 2025) pasaba al 30 al unírsele EODI-2025-00106, dos
    noticias del expediente penal de dos días después («acum două zile»)."""
    if fecha_verificada(destino) or not fecha_verificada(absorbido):
        return False
    suyo = str(destino["lugar"].get("pais", ""))
    _, del_destino = _dias_de(destino, suyo, estricta=True)
    del_destino |= ventana_pasada(destino)
    _, del_absorbido = _dias_de(absorbido, suyo, estricta=True)
    return any(abs((d - o).days) <= 1 for d in del_destino for o in del_absorbido)


# --- Dos días en una ficha --------------------------------------------------------------------


@cache
def _fecha_revisada(ruta: Path = REVISADOS) -> frozenset[str]:
    """Las fichas cuya fecha ya fijó una revisión: las de una separación (la ficha separada y
    la que recibe una parte), las de «distintos» y las que tienen el inicio revisado con cita."""
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    ids = {str(e["incidente"]) for e in datos.get("separar", [])}
    ids |= {
        str(p["coincide_con"])
        for e in datos.get("separar", [])
        for p in e.get("partes", [])
        if p.get("coincide_con")
    }
    ids |= {str(i) for e in datos.get("distintos", []) for i in e.get("incidentes", [])}
    ids |= {str(e["incidente"]) for e in datos.get("datos", []) if e.get("campo") == "inicio"}
    return frozenset(ids)


def varios_dias(incidente: Documento) -> tuple[str, list[date]] | None:
    """La frase de una fuente de la ficha que da dos días que no son una noche («w niedzielę i
    wtorek», «am Samstag und Sonntag jeweils»), con esos días; None si ninguna. Dos días
    distintos son dos sucesos: la ficha cuenta más de uno (proceso/fechas.frase_de_dos_dias lee
    la frase)."""
    return fechas.frase_de_dos_dias(incidente)


def dos_dias_sin_revisar(incidente: Documento) -> bool:
    """Una frase de sus fuentes da dos días distintos (`varios_dias`) y ninguna revisión ha
    dicho a qué día va cada cosa: una ficha es un suceso de una jornada; hay que separarla
    (EODI-2026-00756, 1 y 3 de noviembre de 2026). Una parte nacida de una separación lleva
    «relacionados» y no cuenta."""
    if incidente.get("relacionados") or str(incidente["id"]) in _fecha_revisada():
        return False
    return varios_dias(incidente) is not None


# --- Las uniones vigentes frente a la definición ----------------------------------------------


def union_contraria(
    absorbido: Documento, destino: Documento,
    del_experto: frozenset[frozenset[str]] = frozenset(),
    a_mano: Iterable[frozenset[str]] = (),
) -> Veredicto | None:  # fmt: skip
    """El veredicto «distintos» de una unión vigente (la ficha unida, sin su `fusionado_en`, y
    la que queda) que la definición no admite, o None. Las que una revisión unió a mano
    (`a_mano`, además de la sección `unir`) no se miran: mandan."""
    propio = {k: v for k, v in absorbido.items() if k != "fusionado_en"}
    par = frozenset((str(absorbido["id"]), str(destino["id"])))
    if any(par <= grupo for grupo in a_mano):
        return None
    dicho = veredicto(propio, destino, del_experto, vigente=True)
    return dicho if dicho.relacion == DISTINTOS else None


def uniones_contrarias(
    documentos: list[Documento],
    del_experto: frozenset[frozenset[str]] = frozenset(),
    a_mano: Iterable[frozenset[str]] = (),
    reglas: frozenset[str] | None = None,
) -> list[tuple[str, str, Veredicto]]:  # fmt: skip
    """Las uniones vigentes (absorbido, destino, veredicto) que la definición da por sucesos
    distintos. Con `reglas`, solo las de esas reglas."""
    a_mano = list(a_mano)
    por_id = {str(d["id"]): d for d in documentos}
    salida = []
    for documento in documentos:
        destino = por_id.get(str(documento.get("fusionado_en")))
        if destino is None:
            continue
        dicho = union_contraria(documento, destino, del_experto, a_mano)
        if dicho is not None and (reglas is None or dicho.regla in reglas):
            salida.append((str(documento["id"]), str(destino["id"]), dicho))
    return sorted(salida, key=lambda t: (t[0], t[1]))


# --- Los episodios ----------------------------------------------------------------------------

# La noche de un episodio: de las 16:00 a las 06:00 UTC (17:00 a 07:00 en Europa central
# en invierno, 18:00 a 08:00 en verano), cuando se producen casi todos los avistamientos.
HORA_INICIO_NOCHE = 16
HORA_FIN_NOCHE = 6
MEDIODIA = 12
# «Varios objetivos»: dos o más.
MIN_OBJETIVOS_EPISODIO = 2


def noche(documento: Documento) -> str | None:
    """Fecha de la tarde de la noche del incidente, o None si no fue de noche o no se sabe."""
    inicio = documento["tiempo"]["inicio"]
    if inicio["precision"] not in PRECISIONES_HORA:
        return None
    momento = leer_instante(inicio)
    if HORA_FIN_NOCHE <= momento.hour < HORA_INICIO_NOCHE:
        return None
    return (momento - timedelta(hours=MEDIODIA)).date().isoformat()


def _grupos_de_una_noche(miembros: list[Documento]) -> list[list[Documento]]:
    """Grupos de una noche: los del mismo país, unidos a los de otro país con una fuente en
    común (una noticia que cuenta los dos)."""
    padre = {m["id"]: m["id"] for m in miembros}

    def raiz(id_: str) -> str:
        while padre[id_] != id_:
            padre[id_] = padre[padre[id_]]
            id_ = padre[id_]
        return id_

    def unir(a: str, b: str) -> None:
        padre[raiz(a)] = raiz(b)

    for i, uno in enumerate(miembros):
        enlaces = {f["enlace"] for f in uno["fuentes"]}
        for otro in miembros[i + 1 :]:
            mismo_pais = uno["lugar"]["pais"] == otro["lugar"]["pais"]
            if mismo_pais or enlaces & {f["enlace"] for f in otro["fuentes"]}:
                unir(uno["id"], otro["id"])
    grupos: dict[str, list[Documento]] = defaultdict(list)
    for miembro in miembros:
        grupos[raiz(miembro["id"])].append(miembro)
    return list(grupos.values())


def _nombra_al_otro_pais(ficha: Documento, otro_pais: str) -> bool:
    """Una frase de las fuentes de la ficha nombra el otro país («flew into Latvian airspace»,
    «pasiekė Estiją»)."""
    return any(
        nombra_el_pais(otro_pais, str(f.get("frase_origen") or ""))
        for f in ficha.get("fuentes", [])
        if f.get("publica", True) is not False
    )


def entra_de_fuera(documento: Documento) -> bool:
    """El suceso es de drones que entran en el país desde fuera (`pruebas.entrada_exterior`)."""
    return (documento.get("pruebas") or {}).get("entrada_exterior") is True


def mismo_episodio_transfronterizo(a: Documento, b: Documento) -> bool:
    """Dos sucesos de países vecinos que son el mismo episodio físico a los dos lados de la
    frontera: en los dos, drones que entran desde fuera, de la misma jornada, y las fuentes de
    uno cuentan el paso al país del otro (una frase suya nombra ese país) o los dos comparten
    una noticia. Siguen siendo dos sucesos, uno por país; se enlazan con el mismo episodio. El
    dron de la noche del 10 al 11 de noviembre de 2026 cruzó Lituania (EODI-2026-00792), Letonia
    (EODI-2026-00777) y llegó a Estonia (EODI-2026-00801).

    Que una noticia nombre el otro país no basta: las de un aeropuerto cerrado citan los de los
    países de al lado («Drohne legt Flugverkehr in Bremen lahm – weitere Sichtung in Belgien»)
    y no es el mismo episodio. Medido sobre el registro del 11 de noviembre de 2026: 35 pares
    con la frase sola, 14 con los drones que entran desde fuera en los dos, todos de la misma
    oleada."""
    pais_a, pais_b = pais(a), pais(b)
    if pais_a == pais_b or not (entra_de_fuera(a) and entra_de_fuera(b)):
        return False
    if pais_b not in VECINOS.get(pais_a, frozenset()) and pais_a not in VECINOS.get(
        pais_b, frozenset()
    ):
        return False
    if APROXIMADA in {a["tiempo"]["inicio"]["precision"], b["tiempo"]["inicio"]["precision"]}:
        return False
    if abs(instante(a) - instante(b)) > VENTANA_PAR_ESCRITA or not misma_jornada(a, b):
        return False
    comparten = {f["enlace"] for f in a["fuentes"]} & {f["enlace"] for f in b["fuentes"]}
    return bool(comparten) or _nombra_al_otro_pais(a, pais_b) or _nombra_al_otro_pais(b, pais_a)


def _transfronterizos(activos: list[Documento]) -> list[tuple[str, list[Documento]]]:
    """(día en que empieza, miembros) de cada episodio transfronterizo: los grupos de fichas
    activas enlazadas entre sí por `mismo_episodio_transfronterizo`."""
    padre = {m["id"]: m["id"] for m in activos}
    por_id = {m["id"]: m for m in activos}

    def raiz(id_: str) -> str:
        while padre[id_] != id_:
            padre[id_] = padre[padre[id_]]
            id_ = padre[id_]
        return id_

    ordenados = sorted(activos, key=lambda d: d["tiempo"]["inicio"]["valor"])
    for i, uno in enumerate(ordenados):
        for otro in ordenados[i + 1 :]:
            if instante(otro) - instante(uno) > VENTANA_PAR_ESCRITA:
                break
            if mismo_episodio_transfronterizo(uno, otro):
                padre[raiz(uno["id"])] = raiz(otro["id"])
    grupos: dict[str, list[Documento]] = defaultdict(list)
    for id_ in padre:
        grupos[raiz(id_)].append(por_id[id_])
    resultado = []
    for grupo in grupos.values():
        if len({pais(m) for m in grupo}) < 2:
            continue
        primero = min(grupo, key=lambda d: d["tiempo"]["inicio"]["valor"])
        dia = dia_local(instante(primero) - MADRUGADA, pais(primero))
        if primero["tiempo"]["inicio"]["precision"] == "dia":
            dia = instante(primero).date()
        resultado.append((dia.isoformat(), sorted(grupo, key=lambda m: m["id"])))
    return sorted(resultado, key=lambda par: (par[0], par[1][0]["id"]))


def episodios_calculados(incidentes_: list[Documento]) -> list[tuple[str, list[Documento]]]:
    """(noche, miembros) de cada episodio:

    - varios objetivos del mismo país en una misma noche (incidentes activos, con punto y de
      noche), o de varios países si una misma fuente los cuenta;
    - el mismo episodio físico a los dos lados de una frontera
      (`mismo_episodio_transfronterizo`), aunque sus fichas solo digan el país.

    Un incidente va en un solo episodio: el transfronterizo se suma al de su noche si ya lo
    tiene."""
    por_noche: dict[str, list[Documento]] = defaultdict(list)
    for incidente in incidentes_:
        fecha = noche(incidente)
        if _activa(incidente) and con_punto(incidente) and fecha is not None:
            por_noche[fecha].append(incidente)
    resultado: list[tuple[str, list[Documento]]] = []
    for fecha, miembros in sorted(por_noche.items()):
        for grupo in _grupos_de_una_noche(sorted(miembros, key=lambda m: m["id"])):
            objetivos = {m.get("objetivo", {}).get("nombre") or m["id"] for m in grupo}
            if len(objetivos) >= MIN_OBJETIVOS_EPISODIO:
                resultado.append((fecha, grupo))
    en_alguno = {m["id"]: n for n, (_, grupo) in enumerate(resultado) for m in grupo}
    for fecha, grupo in _transfronterizos([i for i in incidentes_ if _activa(i)]):
        ya = sorted({en_alguno[m["id"]] for m in grupo if m["id"] in en_alguno})
        if not ya:
            en_alguno |= {m["id"]: len(resultado) for m in grupo}
            resultado.append((fecha, grupo))
            continue
        # Alguno ya está en el episodio de su noche: los demás se suman a ese (al primero).
        noche_, miembros = resultado[ya[0]]
        ids = {m["id"] for m in miembros}
        nuevos = [m for m in grupo if m["id"] not in ids and m["id"] not in en_alguno]
        resultado[ya[0]] = (noche_, sorted([*miembros, *nuevos], key=lambda m: m["id"]))
        en_alguno |= {m["id"]: ya[0] for m in nuevos}
    return resultado
