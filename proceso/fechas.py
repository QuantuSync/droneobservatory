"""El día del suceso, leído de la frase que lo dice y no de la fecha de la noticia.

La prensa publica el día del suceso o el siguiente, y el extractor tiene que pasar «anoche»,
«el jueves» o «am Donnerstagabend» a una fecha. Aquí se comprueba con código, con el léxico
de `configuracion/fechas.json`:

- **Explícita**: la frase escribe el día («22 de septiembre», «am 3. Oktober», «22.09.»).
- **Relativa**: la frase da el día respecto a la publicación («ayer», «anoche», «el lunes»).
  Se resuelve con la fecha local del medio cuando publicó la nota (la zona horaria de su
  país; si no se sabe, la del país del suceso): una nota de las 07:10 de Berlín que dice
  «heute Nacht» habla de la noche anterior.
- **Pasado sin día**: la frase sitúa el suceso antes de la publicación sin decir el día («la
  semana pasada», «letzte Woche», «hace unos días»): no es la fecha de publicación. El inicio es
  aproximado, la víspera de la nota como muy tarde, y su motivo dice la ventana en que cae
  (pasado_de, ventana_de_motivo): la fusión lo compara con los incidentes del mismo sitio en esa
  ventana (proceso/suceso.misma_ventana), y un artículo que cuenta un suceso ya registrado se
  une a él como fuente nueva. El 19 de octubre de 2026 una nota de nordbayern.de («Erst letzte
  Woche…») sobre el aeropuerto de Núremberg del 13 de octubre salió como incidente nuevo del 19.
- **Sin día**: la frase no escribe ningún día (solo una hora, o nada). Una fecha sin día
  escrito en su frase no vale como día: el inicio pasa a ser la fecha de publicación, con
  precisión «aproximada», y se declara que lo es.

Si la frase escribe el día y el extractor dio otro, se corrige al de la frase, con su hora
si la tenía. Una fecha en UTC puede caer un día antes que la local (la una de la madrugada
en Europa central es medianoche en UTC) y un suceso de la noche, en la madrugada siguiente:
esos márgenes no son una discrepancia.
"""

import copy
import json
import re
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime, time, timedelta
from functools import cache
from itertools import pairwise
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from proceso.noticias import normalizar

RUTA = Path(__file__).resolve().parent.parent / "configuracion" / "fechas.json"
EXPLICITA, RELATIVA, OFICIAL, PARTE, PUBLICACION = (
    "explicita", "relativa", "oficial", "parte", "publicacion",
)  # fmt: skip
# Orígenes con el día escrito por una fuente: la fecha del suceso está verificada.
VERIFICADOS = frozenset({EXPLICITA, RELATIVA, OFICIAL, PARTE})
# Una nota que sale antes de esta hora local y dice «esta noche» habla de la que acaba de
# pasar; después, de la que empieza.
HORA_NOCHE_SIGUIENTE = 15
# Una hora sin día se toma del día de publicación si cae en las 30 horas anteriores a la
# nota (el día de la nota o la víspera): más atrás, la hora no es de ese día.
MAX_HORA_SIN_DIA = timedelta(hours=30)
# Hasta esta hora local, una hora del día siguiente es aún la noche que nombra la frase.
HORA_FIN_MADRUGADA = 6
ANIO_MIN, ANIO_MAX = 2014, 2099
DIAS_SEMANA = 7
MESES = 12
_APOSTROFOS = re.compile(r"['’ʼ`´]")
# 22.09.2025, 22/09/2025, 22.09.25, 22.09. (día y mes, en ese orden en toda Europa).
_NUMERICA = re.compile(r"(?<![\d.:/])(\d{1,2})[./](\d{1,2})(?:[./](\d{4}|\d{2})(?!\d)|\.)(?![\d:])")
_ISO = re.compile(r"(?<!\d)(\d{4})-(\d{2})-(\d{2})(?!\d)")
# «22», «22nd», «3.», «1er», «22º» junto al mes.
_NUMERO_DIA = re.compile(r"^(\d{1,2})(?:st|nd|rd|th|er|e|o|a|º|ª)?$")
_ANIO = re.compile(r"^(\d{4})$")
# Palabras que pueden ir entre el día y el mes («22 de septiembre», «22nd of September»).
_ENLACES = frozenset({"de", "of", "di", "do", "da", "del", "the", "den", "d"})


# El motivo de un inicio de pasado sin día lleva su ventana: «…: suceso anterior a la publicación,
# entre el AAAA-MM-DD y el AAAA-MM-DD».
MARCA_PASADO = "suceso anterior a la publicación, entre el "
_VENTANA = re.compile(re.escape(MARCA_PASADO) + r"(\d{4}-\d{2}-\d{2}) y el (\d{4}-\d{2}-\d{2})")
DIAS_PASADO = 10


def _normal(texto: str) -> str:
    """Como la frase: sin apóstrofos que partan la palabra («п'ятниця», «aujourd'hui»)."""
    return normalizar(_APOSTROFOS.sub("", texto))


def normal(texto: str) -> str:
    """La frase normalizada como la leen los léxicos (la auditoría de las fichas)."""
    return _normal(texto)


@dataclass(frozen=True)
class Lexico:
    meses: dict[str, int]
    dias: tuple[tuple[str, int], ...]
    relativos: tuple[tuple[str, int], ...]
    noches: tuple[str, ...]
    noche_hacia: tuple[str, ...]
    compone: bool
    # Las noches que son una tarde («am Abend», «dans la soirée»): acaban ese día.
    tardes: frozenset[str] = frozenset()


@cache
def configuracion(ruta: Path = RUTA) -> dict[str, Any]:
    datos: dict[str, Any] = json.loads(ruta.read_text(encoding="utf-8"))
    return datos


@cache
def lexicos() -> dict[str, Lexico]:
    config = configuracion()
    resultado = {}
    for idioma, datos in config["idiomas"].items():
        resultado[idioma] = Lexico(
            meses={_normal(f): n for n, formas in enumerate(datos["meses"], 1) for f in formas},
            dias=tuple((_normal(f), n) for n, formas in enumerate(datos["dias"]) for f in formas),
            relativos=tuple(
                sorted(
                    (
                        (_normal(f), int(d))
                        for d, formas in datos["relativos"].items()
                        for f in formas
                    ),
                    key=lambda par: -len(par[0]),
                )
            ),
            noches=tuple(sorted((_normal(f) for f in datos["noches"]), key=len, reverse=True)),
            noche_hacia=tuple(_normal(f) for f in datos["noche_hacia"]),
            compone=idioma in config["componen_dias"],
            tardes=frozenset(_normal(f) for f in datos.get("tardes", [])),
        )
    return resultado


def zona(pais: str | None, lat: float | None = None, lon: float | None = None) -> ZoneInfo | None:
    """La hora local del suceso: la del territorio en que cae el punto (Canarias, las Azores,
    los departamentos franceses de ultramar, Groenlandia: configuracion/territorios.json) o, si
    no, la del país."""
    from proceso.territorios import zona_del_punto

    propia = zona_del_punto(lat, lon)
    if propia is not None:
        return propia
    nombre = configuracion()["zonas"].get(pais or "")
    return ZoneInfo(nombre) if nombre else None


@dataclass(frozen=True)
class Lectura:
    """Lo que la frase dice del día: los días locales posibles y a cuál corregir."""

    origen: str  # EXPLICITA o RELATIVA
    # Días (UTC) compatibles con lo que dice la frase.
    admitidos: frozenset[date]
    # El día local que dice la frase, al que se corrige una fecha que no casa.
    dia: date
    expresion: str
    # «La noche hacia el 11» («naktī uz 11. novembri», «in der Nacht zum Freitag»): `dia` es la
    # víspera, cuando empieza la noche. Una ficha con el día a secas lleva ese día, no el
    # siguiente; con hora, la madrugada del siguiente sigue valiendo.
    hacia: bool = False


def _contiene(normal: str, expresion: str) -> int:
    """Posición de la expresión como palabras enteras, o -1."""
    m = re.search(r"(?<!\w)" + re.escape(expresion) + r"(?!\w)", normal)
    return m.start() if m else -1


def _anio_probable(mes: int, dia: int, referencia: date) -> int:
    """El año del último día con ese mes y ese día que no pasa de la publicación (más un día)."""
    for anio in (referencia.year, referencia.year - 1):
        try:
            candidato = date(anio, mes, dia)
        except ValueError:
            continue
        if candidato <= referencia + timedelta(days=1):
            return anio
    return referencia.year - 1


def _fecha(anio: int | None, mes: int, dia: int, referencia: date) -> date | None:
    if not 1 <= mes <= MESES or not 1 <= dia <= 31:
        return None
    anio = anio if anio is not None else _anio_probable(mes, dia, referencia)
    if not ANIO_MIN <= anio <= ANIO_MAX:
        return None
    try:
        return date(anio, mes, dia)
    except ValueError:
        return None


def _explicitas(frase: str, lexico: list[Lexico], referencia: date) -> list[tuple[date, str]]:
    """Fechas con el día escrito: con el mes por su nombre o con cifras."""
    halladas: list[tuple[date, str]] = []
    for m in _ISO.finditer(frase):
        if (f := _fecha(int(m[1]), int(m[2]), int(m[3]), referencia)) is not None:
            halladas.append((f, m[0]))
    sin_iso = _ISO.sub(" ", frase)
    for m in _NUMERICA.finditer(sin_iso):
        anio = int(m[3]) if m[3] else None
        if anio is not None and anio < 100:
            anio += 2000
        if (f := _fecha(anio, int(m[2]), int(m[1]), referencia)) is not None:
            halladas.append((f, m[0]))
    palabras = _normal(sin_iso).split()
    for i, palabra in enumerate(palabras):
        mes = next((lx.meses[palabra] for lx in lexico if palabra in lx.meses), None)
        if mes is None:
            continue
        anio = next(
            (int(p) for p in palabras[i + 1 : i + 3] if _ANIO.match(p)), None
        )  # fmt: skip
        dia: int | None = None
        # Antes del mes: «22 septiembre», «22 de septiembre», «22nd of September».
        previas = palabras[max(0, i - 3) : i]
        while previas and previas[-1] in _ENLACES:
            previas = previas[:-1]
        antes = _NUMERO_DIA.match(previas[-1]) if previas else None
        despues = _NUMERO_DIA.match(palabras[i + 1]) if i + 1 < len(palabras) else None
        if antes is not None:
            dia = int(antes[1])
        elif despues is not None:
            # Después: «September 22», «September 22nd, 2025».
            dia = int(despues[1])
            anio = next((int(p) for p in palabras[i + 2 : i + 4] if _ANIO.match(p)), None)
        if dia is not None and (f := _fecha(anio, mes, dia, referencia)) is not None:
            halladas.append((f, f"{dia} {palabra}"))
    return halladas


def _dia_semana(palabras: list[str], normal: str, lx: Lexico) -> list[tuple[int, str]]:
    """Días de la semana que nombra la frase (lunes = 0), en orden de aparición."""
    hallados: list[tuple[int, int, str]] = []
    for forma, numero in lx.dias:
        if " " in forma:
            if (pos := _contiene(normal, forma)) >= 0:
                hallados.append((pos, numero, forma))
            continue
        for i, palabra in enumerate(palabras):
            if palabra == forma or (lx.compone and palabra.startswith(forma)):
                hallados.append((len(" ".join(palabras[:i])), numero, forma))
    hallados.sort()
    return [(n, f) for _, n, f in dict.fromkeys(hallados)]


def _relativas(normal: str, lx: Lexico) -> tuple[list[tuple[int, str]], list[str]]:
    """Desplazamientos («ayer» −1) y noches que nombra la frase. Las expresiones más largas
    primero: «heute Nacht» no es «heute»."""
    resto = f" {normal} "
    noches: list[str] = []
    for forma in lx.noches:
        if _contiene(resto, forma) >= 0:
            noches.append(forma)
            resto = re.sub(r"(?<!\w)" + re.escape(forma) + r"(?!\w)", " ", resto)
    desplazamientos: list[tuple[int, str]] = []
    for forma, desplazamiento in lx.relativos:
        if _contiene(resto, forma) >= 0:
            desplazamientos.append((desplazamiento, forma))
            resto = re.sub(r"(?<!\w)" + re.escape(forma) + r"(?!\w)", " ", resto)
    return desplazamientos, noches


def _ultimo(dia_semana: int, referencia: date) -> date:
    """El último día de la semana pedido, como muy tarde el de referencia."""
    return referencia - timedelta(days=(referencia.weekday() - dia_semana) % DIAS_SEMANA)


def leer(
    frase: str, publicacion: datetime, zona_medio: ZoneInfo, idioma: str | None
) -> list[Lectura]:
    """Lo que dice la frase del día, respecto a la publicación de su nota: primero con el
    léxico del idioma de la nota (y el inglés, que las notas citan a menudo); si no dice
    nada, con todos, por si la frase está en otro idioma (una nota belga en francés que
    GDELT da en neerlandés). Con todos, solo vale una lectura que dé un solo día."""
    todos = lexicos()
    if idioma in todos:
        propios = [todos[idioma], *([todos["en"]] if idioma != "en" else [])]
        lecturas = _leer_con(frase, publicacion, zona_medio, propios)
        if lecturas:
            return lecturas
    otros = [lx for clave, lx in todos.items() if clave != idioma]
    lecturas = _leer_con(frase, publicacion, zona_medio, otros)
    return lecturas if len({lec.dia for lec in lecturas}) == 1 else []


# Palabras entre la marca de «la noche hacia» y la fecha: «naktī uz 11. novembri», «in der Nacht
# zum Mittwoch, 11. November», «naktį į lapkričio 11-ąją».
MAX_HASTA_LA_FECHA = 4


def nombra_la_noche(frase: str, idioma: str) -> bool:
    """La frase habla de una noche («naktī uz 11. novembri», «pagājušajā naktī», «in der
    Nacht»), con el léxico de ese idioma."""
    lx = lexicos().get(idioma)
    if lx is None:
        return False
    normal = _normal(frase)
    return any(_contiene(normal, forma) >= 0 for forma in (*lx.noches, *lx.noche_hacia))


def _noche_hacia_la_fecha(palabras: list[str], lexico: list[Lexico], dia: date) -> bool:
    """La frase dice «la noche hacia» justo antes de esa fecha escrita (su día y un mes)."""
    for lx in lexico:
        for marca in lx.noche_hacia:
            trozos = marca.split()
            for i in range(len(palabras) - len(trozos) + 1):
                if palabras[i : i + len(trozos)] != trozos:
                    continue
                tras = palabras[i + len(trozos) : i + len(trozos) + MAX_HASTA_LA_FECHA]
                numeros = [m for p in tras if (m := _NUMERO_DIA.match(p))]
                if any(int(m[1]) == dia.day for m in numeros) and any(p in lx.meses for p in tras):
                    return True
    return False


def _leer_con(
    frase: str, publicacion: datetime, zona_medio: ZoneInfo, lexico: list[Lexico]
) -> list[Lectura]:
    local = publicacion.astimezone(zona_medio)
    hoy = local.date()
    lecturas: list[Lectura] = []
    normal = _normal(frase)
    palabras = normal.split()
    for dia, texto in _explicitas(frase, lexico, hoy):
        # «Naktī uz 11. novembri», «in der Nacht zum 11. November»: la noche hacia el 11 empieza
        # el 10. La nota de las Fuerzas Armadas de Letonia sobre la noche del 10 al 11 de
        # noviembre de 2026 daba una ficha del 11 (EODI-2026-00784) y la de sus alertas, del 10.
        vispera = dia - timedelta(days=1)
        hacia = _noche_hacia_la_fecha(palabras, lexico, dia)
        primero = vispera if hacia else dia
        lecturas.append(Lectura(EXPLICITA, frozenset({dia, vispera}), primero, texto, hacia))
    if lecturas:
        return lecturas
    for lx in lexico:
        dias = _dia_semana(palabras, normal, lx)
        hacia = any(_contiene(normal, m) >= 0 for m in lx.noche_hacia)
        if dias:
            fechas = [_ultimo(n, hoy) for n, _ in dias]
            primero = min(fechas)
            texto = " ".join(f for _, f in dias)
            de_vispera = len(dias) == 1 and hacia
            if de_vispera:
                # «la noche hacia el viernes» empieza el jueves.
                primero -= timedelta(days=1)
            admitidos = {primero, primero + timedelta(days=1), *fechas}
            lecturas.append(Lectura(RELATIVA, frozenset(admitidos), primero, texto, de_vispera))
            continue
        desplazamientos, noches = _relativas(normal, lx)
        for desplazamiento, forma in desplazamientos:
            dia = hoy + timedelta(days=desplazamiento)
            lecturas.append(
                Lectura(RELATIVA, frozenset({dia, dia - timedelta(days=1)}), dia, forma)
            )
        for forma in noches:
            tarde = hoy - timedelta(days=1) if local.hour < HORA_NOCHE_SIGUIENTE else hoy
            # La noche empieza la tarde de `tarde` y puede seguir pasada la medianoche. Una
            # tarde («am Abend») no: acaba ese día. En una nota de las 14:30 es la de la
            # víspera, y la ficha no puede llevar el día de la nota (EODI-2026-00771, el dron
            # de la Führungsakademie de Hamburgo, publicado con el 9 de noviembre de 2026).
            admitidos = {tarde} if forma in lx.tardes else {tarde, tarde + timedelta(days=1)}
            lecturas.append(Lectura(RELATIVA, frozenset(admitidos), tarde, forma))
        if lecturas:
            return lecturas
    return lecturas


@dataclass(frozen=True)
class Resolucion:
    """El inicio del suceso tras comprobar su día con la frase."""

    valor: datetime
    precision: str
    origen: str
    motivo: str
    corregido: bool = False
    # Lo que se restó a la hora de la ficha por venir en hora local y no en UTC (hora_en_utc):
    # el fin de la misma ficha lleva el mismo error.
    desfase: timedelta = timedelta(0)


def hora_en_utc(valor: datetime, precision: str | None, frase: str,
                zona_suceso: ZoneInfo) -> datetime | None:  # fmt: skip
    """La hora de la ficha pasada a UTC si el extractor copió la hora local de la frase sin
    convertirla, o None si no. Lo es si la frase escribe una sola hora (textos_dron.hora_local),
    la hora UTC de la ficha es esa misma y en la zona del suceso no lo es: «gegen 19.30 Uhr» en
    Bremen el 2 de noviembre de 2025 (UTC+1) son las 18:30 UTC, y EODI-2025-00007 publicaba las
    19:30 UTC. Con la hora local de la frase ya bien convertida, o con otra hora, no se toca."""
    from proceso.textos_dron import hora_local

    if precision not in {"minuto", "hora"}:
        return None
    # La frase es la del inicio: el extractor tomó de ella la hora aunque no nombre el dron.
    escrita = hora_local(frase, con_dron=False)
    if escrita is None:
        return None
    utc = valor.astimezone(UTC)
    if misma_hora(utc.astimezone(zona_suceso), escrita, precision):
        return None
    for desfase in desfases_errados(utc, zona_suceso):
        leida = utc + desfase
        if misma_hora(leida, escrita, precision):
            local = datetime.combine(leida.date(), time(*escrita), zona_suceso)
            return local.astimezone(UTC)
    return None


# Lo más que pueden separarse las horas del inicio que dicen las frases de una ficha.
MAX_DESACUERDO = timedelta(minutes=10)
# La hora de un aterrizaje no es la del inicio del suceso (EODI-2025-00158: «Aeronava a aterizat în
# siguranță la ora 15:45», el avión que vio el dron al aproximarse a Otopeni).
_ATERRIZAJE = re.compile(
    r"\b(aterizat|aterizeaz|aterizare|landed|landing|gelandet|landete|atterri|aterriz|atterr"
    r"|wylądowa|ląduj|přistál|přistan|landade|landet)\w*",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class HoraDicha:
    """La hora del inicio que dice la frase de una fuente, ya en UTC."""

    valor: datetime
    fuente_id: str
    local: str
    zona: str


def hora_de_las_frases(incidente: dict[str, Any]) -> HoraDicha | None:
    """La hora del inicio de una ficha que solo tiene el día, si la dice la frase de una de sus
    fuentes: la de una afirmación del inicio con hora cuya fuente escribe esa hora en su frase
    (`frase_origen`), en UTC con hora_en_utc si el extractor copió la hora local o le sumó el
    desfase del otro horario, y del mismo día local que la ficha. Con varias, la más temprana si
    no se separan más de MAX_DESACUERDO; si no, ninguna.
    EODI-2026-00719: «Primul mesaj RO-Alert a fost emis în județul Iași, la ora 17:04» (hotnews.ro,
    15:04 UTC) llegó al unir otra ficha y la de Iași se quedó con el día de su primera nota."""
    from proceso.textos_dron import hora_local

    tiempo = incidente.get("tiempo") or {}
    inicio = tiempo.get("inicio") or {}
    if inicio.get("precision") != "dia":
        return None
    dia = str(inicio.get("valor", ""))[:10]
    lugar = incidente.get("lugar") or {}
    punto = lugar.get("punto") or {}
    zona_suceso = zona(lugar.get("pais"), punto.get("lat"), punto.get("lon"))
    if zona_suceso is None:
        return None
    fuentes = {str(f.get("id")): f for f in incidente.get("fuentes", [])}
    frases = {i: str(f.get("frase_origen") or "") for i, f in fuentes.items()}
    halladas: list[HoraDicha] = []
    todas: list[HoraDicha] = []
    for afirmacion in incidente.get("afirmaciones", []) or []:
        valor = str(afirmacion.get("valor") or "")
        frase = frases.get(str(afirmacion.get("fuente_id")), "")
        if afirmacion.get("campo") != "inicio" or "T" not in valor or not frase:
            continue
        escrita = hora_local(frase, con_dron=False)
        if escrita is None or _ATERRIZAJE.search(frase):
            continue
        try:
            leido = _momento(valor if valor.endswith("Z") else valor + "Z")
        except ValueError:
            continue
        en_utc = hora_en_utc(leido, "minuto", frase, zona_suceso)
        if en_utc is None:
            if not misma_hora(leido.astimezone(zona_suceso), escrita, "minuto"):
                continue
            en_utc = leido
        local = en_utc.astimezone(zona_suceso)
        if local.date().isoformat() != dia:
            continue
        fin = tiempo.get("fin")
        if fin and _momento(str(fin["valor"])) < en_utc:
            continue
        hallada = HoraDicha(en_utc, str(afirmacion["fuente_id"]), local.strftime("%H:%M"),
                            zona_suceso.key)  # fmt: skip
        todas.append(hallada)
        medio = _zona_del_dominio(str(fuentes[str(afirmacion["fuente_id"])].get("enlace") or ""))
        if medio is None or medio.utcoffset(en_utc) == zona_suceso.utcoffset(en_utc):
            # Un medio de otro huso puede dar la hora en la suya («gegen 17.43 Uhr» en heute.at
            # para un suceso de Rumanía, EODI-2026-00582): esa no se toma.
            halladas.append(hallada)
    if not halladas or max(h.valor for h in todas) - min(h.valor for h in todas) > MAX_DESACUERDO:
        # Las frases dan horas distintas («gegen 17.43 Uhr» y «în jurul orei 18:00» en
        # EODI-2026-00582): no se sabe cuál es la del inicio.
        return None
    return min(halladas, key=lambda h: (h.valor, h.fuente_id))


def _zona_del_dominio(enlace: str) -> ZoneInfo | None:
    """La hora local del país del dominio de un enlace con dominio de país («heute.at»: Austria),
    o None con un dominio genérico («.com», «.eu») o de un país sin zona conocida."""
    from urllib.parse import urlparse

    dominio = (urlparse(enlace).hostname or "").rsplit(".", 1)[-1].upper()
    if len(dominio) != 2 or not dominio.isalpha():
        return None
    return zona({"UK": "GB"}.get(dominio, dominio))


def misma_hora(momento: datetime, escrita: tuple[int, int], precision: str | None,
               margen: timedelta = timedelta(0)) -> bool:  # fmt: skip
    """La hora del reloj de `momento` es la escrita, con `margen` a cada lado (también pasada la
    medianoche). Con precisión «hora» basta con la misma hora."""
    if precision == "hora" and momento.hour == escrita[0]:
        return True
    diferencia = abs(momento.hour * 60 + momento.minute - escrita[0] * 60 - escrita[1])
    return min(diferencia, 24 * 60 - diferencia) <= margen.total_seconds() / 60


def desfases_errados(momento: datetime, zona_suceso: ZoneInfo) -> list[timedelta]:
    """Lo que un extractor pudo sumar a la hora UTC creyendo que era la local: nada (la hora
    local tomada como UTC: «gegen 19.30 Uhr» en Bremen el 2 de noviembre de 2025 publicado como
    19:30 UTC, EODI-2025-00007) o el desfase del otro horario del año («apie 21 valandą» en
    Vilna el 11 de septiembre de 2025, UTC+3, publicado como 19:00 UTC con el UTC+2 de invierno,
    EODI-2025-00099). Nunca el desfase correcto de ese día."""
    correcto = momento.astimezone(zona_suceso).utcoffset()
    anio = momento.astimezone(UTC).year
    posibles = [timedelta(0)] + [
        datetime(anio, mes, 15, 12, tzinfo=UTC).astimezone(zona_suceso).utcoffset() or timedelta(0)
        for mes in (1, 7)
    ]
    return [d for d in dict.fromkeys(posibles) if d != correcto]


def _con_dia(momento: datetime, dia: date, zona_suceso: ZoneInfo) -> datetime:
    """El mismo momento del día (en UTC) llevado al día local `dia`: una hora de las 22:30 UTC
    de una noche de Berlín es del día anterior en UTC."""
    hora = momento.timetz() if momento.tzinfo else time(momento.hour, momento.minute, tzinfo=UTC)
    for desplazamiento in (0, 1, -1):
        candidato = datetime.combine(dia + timedelta(days=desplazamiento), hora)
        if candidato.astimezone(zona_suceso).date() == dia:
            return candidato
    return datetime.combine(dia, hora)


def _admitido(
    valor: datetime, precision: str | None, lectura: Lectura, zona_suceso: ZoneInfo
) -> bool:
    """El día de la ficha casa con la lectura. El día siguiente al de la frase («el jueves por la
    noche») solo vale de madrugada: a las 19:30 del viernes ya es otro suceso."""
    if valor.date() not in lectura.admitidos:
        return False
    if valor.date() > lectura.dia and precision in {"minuto", "hora"}:
        return valor.astimezone(zona_suceso).hour < HORA_FIN_MADRUGADA
    # «La noche hacia el 11» sin hora es del 10: el día a secas del 11 no casa y se corrige.
    return not (lectura.hacia and valor.date() > lectura.dia)


def resolver(
    valor: datetime | None,
    precision: str | None,
    frases: list[str],
    publicacion: datetime,
    zona_medio: ZoneInfo,
    zona_suceso: ZoneInfo,
    idioma: str | None,
) -> Resolucion:
    """El inicio que vale: el de la ficha si su día está escrito en la frase (o en otra frase
    o el titular de la misma nota), el corregido al de la frase si no casa y, si ninguna
    escribe el día, la fecha de publicación con precisión aproximada."""
    publicado = publicacion.astimezone(zona_medio).strftime("%Y-%m-%d %H:%M")
    for frase in frases:
        lecturas = leer(frase, publicacion, zona_medio, idioma)
        if not lecturas:
            continue
        dias = {lec.dia for lec in lecturas}
        expresiones = ", ".join(f"«{lec.expresion}»" for lec in lecturas)
        cita = f"{expresiones} en una nota publicada el {publicado} (hora local del medio)"
        if valor is not None and any(
            _admitido(valor, precision, lec, zona_suceso) for lec in lecturas
        ):
            return Resolucion(valor, precision or "dia", lecturas[0].origen, cita)
        if len(dias) != 1:
            # La frase escribe varios días y ninguno es el de la ficha: no se sabe cuál es.
            continue
        dia = next(iter(dias))
        if valor is not None and precision in {"minuto", "hora"}:
            nuevo = _con_dia(valor, dia, zona_suceso)
            return Resolucion(nuevo, precision, lecturas[0].origen,
                              f"{cita}: el día es {dia}", corregido=True)  # fmt: skip
        nuevo = datetime.combine(dia, time(0, 0), UTC)
        return Resolucion(nuevo, "dia", lecturas[0].origen,
                          f"{cita}: el día es {dia}", corregido=valor is None
                          or valor.date() != dia)  # fmt: skip
    pasado = _resolucion_pasado(frases, publicacion, zona_medio, corregido=True)
    if pasado is not None:
        # «La semana pasada»: el suceso no es del día de la nota.
        return pasado
    if (
        valor is not None
        and precision in {"minuto", "hora"}
        and timedelta(0) <= publicacion - valor <= MAX_HORA_SIN_DIA
    ):
        # La frase da la hora («gegen 22 Uhr») pero no el día: el día sale de la publicación
        # y no está verificado. Se conserva la hora, con precisión aproximada.
        return Resolucion(
            valor, "aproximada", PUBLICACION,
            f"la frase da la hora pero no el día: día de la publicación ({publicado}, hora "
            "local del medio)",
            corregido=True,
        )  # fmt: skip
    return Resolucion(
        publicacion.astimezone(UTC),
        "aproximada",
        PUBLICACION,
        f"ninguna frase escribe el día del suceso: fecha de publicación ({publicado}, hora "
        "local del medio)",
        corregido=valor is not None,
    )


@cache
def _pasados() -> tuple[tuple[str, str], ...]:
    """(expresión normalizada, clase) de los pasados sin día, las más largas primero."""
    datos = configuracion().get("pasados", {})
    pares = {(_normal(f), clase) for clase in ("semana", "dias") for f in datos.get(clase, [])}
    return tuple(sorted(pares, key=lambda par: (-len(par[0]), par)))


def pasado_de(frase: str, publicacion: datetime, zona_medio: ZoneInfo
              ) -> tuple[date, date, str] | None:  # fmt: skip
    """(desde, hasta, expresión) si la frase sitúa el suceso en un pasado sin día respecto a la
    publicación: «la semana pasada», la semana natural anterior (con el domingo de antes);
    «hace unos días», de DIAS_PASADO días antes a la víspera. None si no."""
    normal = _normal(frase)
    hoy = publicacion.astimezone(zona_medio).date()
    for expresion, clase in _pasados():
        if _contiene(normal, expresion) < 0:
            continue
        if clase == "semana":
            lunes = hoy - timedelta(days=hoy.weekday() + DIAS_SEMANA)
            return lunes - timedelta(days=1), lunes + timedelta(days=DIAS_SEMANA - 1), expresion
        return hoy - timedelta(days=DIAS_PASADO), hoy - timedelta(days=1), expresion
    return None


def ventana_de_motivo(motivo: str) -> tuple[date, date] | None:
    """La ventana de un inicio de pasado sin día, leída de su motivo (MARCA_PASADO)."""
    hallada = _VENTANA.search(motivo or "")
    if hallada is None:
        return None
    return date.fromisoformat(hallada.group(1)), date.fromisoformat(hallada.group(2))


def _resolucion_pasado(frases: list[str], publicacion: datetime, zona_medio: ZoneInfo,
                       corregido: bool) -> Resolucion | None:  # fmt: skip
    for frase in frases:
        pasado = pasado_de(frase, publicacion, zona_medio)
        if pasado is None:
            continue
        desde, hasta, expresion = pasado
        publicado = publicacion.astimezone(zona_medio).strftime("%Y-%m-%d %H:%M")
        return Resolucion(
            datetime.combine(hasta, time(0, 0), UTC), "aproximada", PUBLICACION,
            f"«{expresion}» en una nota publicada el {publicado} (hora local del medio): "
            f"{MARCA_PASADO}{desde} y el {hasta}",
            corregido=corregido,
        )  # fmt: skip
    return None


def _momento(texto: str) -> datetime:
    return datetime.fromisoformat(texto.replace("Z", "+00:00")).astimezone(UTC)


def dia_local(instante: dict[str, Any], documento: dict[str, Any]) -> str:
    """El día local del lugar del suceso de un instante («AAAA-MM-DD»): una fecha con precisión de
    día es siempre el día local, nunca el de UTC (EODI-2026-00512, el ataque de hacia la 01:30
    hora de Bulgaria del 13/10/2026, salía el 12 por sus 22:30 UTC). Si el instante ya es solo
    el día, es ese. `documento`: la ficha (con `lugar`) o sus propiedades publicadas."""
    valor = str(instante["valor"])
    if instante.get("precision") == "dia":
        return valor[:10]
    lugar = documento.get("lugar") or {}
    punto = lugar.get("punto") or {}
    zona_suceso = zona(
        lugar.get("pais") or documento.get("pais"), punto.get("lat", documento.get("lat")),
        punto.get("lon", documento.get("lon")),
    ) or ZoneInfo("UTC")  # fmt: skip
    return _momento(valor).astimezone(zona_suceso).date().isoformat()


def inicio_de_ficha(
    campos: dict[str, dict[str, Any]],
    enviadas: list[str],
    articulos: list[dict[str, Any]],
    inicio_candidato: str,
    pais_suceso: str | None,
    lat: float | None = None,
    lon: float | None = None,
) -> Resolucion:
    """El inicio del incidente que sale de su ficha validada, comprobado con su frase.

    `articulos` son los del candidato (con fecha, país del medio, idioma y titular). Sin
    inicio en la ficha, la fecha es la del primer artículo: la de publicación, aproximada.
    """
    por_url = {a["url"]: a for a in articulos}
    zona_suceso = zona(pais_suceso, lat, lon) or ZoneInfo("UTC")
    inicio = campos.get("inicio")
    fuente = inicio.get("fuente") if inicio else None
    if inicio is None or not isinstance(fuente, int) or not 1 <= fuente <= len(enviadas):
        primero = min(articulos, key=lambda a: a["fecha"]) if articulos else None
        publicacion = _momento(primero["fecha"] if primero else inicio_candidato)
        medio = zona(primero.get("pais")) if primero else None
        frases_ficha = [str(c.get("frase") or "") for c in campos.values() if c.get("frase")]
        frases_ficha += [str(a.get("titular") or "") for a in articulos if a.get("titular")]
        pasado = _resolucion_pasado(frases_ficha, publicacion, medio or zona_suceso, False)
        if pasado is not None:
            return pasado
        local = publicacion.astimezone(medio or zona_suceso).strftime("%Y-%m-%d %H:%M")
        # Una frase escribe el día, anterior a la publicación («2025. gada 13. janvārī Rīgas
        # lidostā», EODI-2025-00153, publicada el 6 de febrero): el suceso es de ese día, si
        # todas las que lo escriben dicen el mismo.
        idioma = primero.get("idioma") if primero else None
        hoy = publicacion.astimezone(medio or zona_suceso).date()
        escritos = {
            lectura.dia
            for frase in frases_ficha
            for lectura in leer(frase, publicacion, medio or zona_suceso, idioma)
            if lectura.origen == EXPLICITA and lectura.dia < hoy
        }
        if len(escritos) == 1:
            dia = next(iter(escritos))
            return Resolucion(
                datetime.combine(dia, time(0, 0), UTC), "dia", EXPLICITA,
                f"la ficha no da el inicio; una frase escribe el día {dia} (nota publicada el "
                f"{local}, hora local del medio)",
                corregido=True,
            )  # fmt: skip
        return Resolucion(
            publicacion, "aproximada", PUBLICACION,
            f"la ficha no da el inicio: fecha de publicación de la primera nota ({local}, hora "
            "local del medio)",
        )  # fmt: skip
    articulo = por_url.get(enviadas[fuente - 1], {})
    publicacion = _momento(articulo.get("fecha") or inicio_candidato)
    zona_medio = zona(articulo.get("pais")) or zona_suceso
    texto = str(inicio["valor"])
    valor = _momento(texto + ("Z" if "T" in texto else "T00:00Z"))
    precision = campos.get("inicio_precision", {}).get("valor") if "T" in texto else "dia"
    frases = [str(inicio.get("frase") or "")]
    frases += [
        str(c.get("frase") or "") for nombre, c in sorted(campos.items())
        if nombre != "inicio" and c.get("fuente") == fuente and c.get("frase")
    ]  # fmt: skip
    if articulo.get("titular"):
        frases.append(str(articulo["titular"]))
    en_utc = hora_en_utc(valor, precision, frases[0], zona_suceso)
    if en_utc is not None:
        desfase, valor = valor - en_utc, en_utc
    resolucion = resolver(
        valor, precision or "dia", list(dict.fromkeys(f for f in frases if f)), publicacion,
        zona_medio, zona_suceso, articulo.get("idioma"),
    )  # fmt: skip
    if en_utc is None:
        return resolucion
    local = en_utc.astimezone(zona_suceso).strftime("%H:%M")
    return replace(
        resolucion, desfase=desfase, corregido=True,
        motivo=f"{resolucion.motivo}; la hora de la frase ({local}) es hora local "
               f"({zona_suceso.key}): en UTC, {en_utc.strftime('%H:%M')}",
    )  # fmt: skip


def dia_escrito(valor: str, frase: str, publicacion: datetime) -> bool:
    """El día de la fecha está escrito en la frase («22 de septiembre», «22.09.»), en
    cualquier idioma: una noticia que vuelve sobre un suceso de hace semanas vale si lo dice."""
    try:
        dia = date.fromisoformat(valor[:10])
    except ValueError:
        return False
    lexico = list(lexicos().values())
    return any(
        dia in {f, f - timedelta(days=1)}
        for f, _ in _explicitas(frase, lexico, publicacion.astimezone(UTC).date())
    )


# --- Noticias retrospectivas ---------------------------------------------------------------

# Lo que marca en el motivo del inicio que el control ya preguntó la fecha de una noticia que
# parecía contar un suceso anterior (recogida/control_fichas.retrospectivas): el experto dijo
# que no lo es o dio la fecha. La auditoría (N) y la retención ya no la vuelven a marcar.
MARCA_RETROSPECTIVA = "noticia retrospectiva revisada"
# Formas de un mes que en su idioma también son una palabra corriente («mai», «más» en rumano).
MESES_AMBIGUOS = {"en": frozenset({"may", "march"}), "ro": frozenset({"mai"})}


def retrospectiva_revisada(incidente: dict[str, Any]) -> bool:
    """El control ya preguntó al experto la fecha de esta noticia y no era retrospectiva."""
    origen = (incidente.get("tiempo") or {}).get("origen_inicio") or {}
    return MARCA_RETROSPECTIVA in str(origen.get("motivo", ""))


@cache
def _anteriores() -> tuple[str, ...]:
    """Los pasados lejanos o sin medida («el mes pasado», «earlier this year»), normalizados."""
    formas = configuracion().get("pasados", {}).get("anterior", [])
    return tuple(sorted({_normal(f) for f in formas}, key=len, reverse=True))


def retrospectiva(incidente: dict[str, Any]) -> str | None:
    """La palabra que sitúa el suceso antes de la noticia, si la ficha tomó la fecha de
    publicación como inicio: un mes que no es el del inicio (ni el de la víspera en los
    primeros días del mes: «u augustu» en una nota del 22 de octubre, EODI-2026-00663) o un
    pasado lejano («last month», «letzten Monat»). None si no la hay o el control ya la revisó.
    Una noticia así cuenta un suceso anterior y no casa con su ficha por la fecha."""
    tiempo = incidente.get("tiempo") or {}
    origen = tiempo.get("origen_inicio") or {}
    if origen.get("tipo") != PUBLICACION or retrospectiva_revisada(incidente):
        return None
    for fuente in incidente.get("fuentes", []):
        frase = _normal(str(fuente.get("frase_origen") or ""))
        if (mes := _mes_anterior(incidente, fuente)) is not None:
            return mes[0]
        for expresion in _anteriores():
            if _contiene(frase, expresion) >= 0:
                return expresion
    return None


def _mes_anterior(incidente: dict[str, Any], fuente: dict[str, Any]) -> tuple[str, int] | None:
    """La palabra de un mes anterior al del inicio en la frase de la fuente, y su número."""
    inicio = date.fromisoformat(str(incidente["tiempo"]["inicio"]["valor"])[:10])
    vale = {inicio.month} | ({(inicio.month - 2) % 12 + 1} if inicio.day <= 3 else set())
    idioma = str(fuente.get("idioma") or "")
    lexico = lexicos().get(idioma)
    if lexico is None:
        return None
    ambiguos = MESES_AMBIGUOS.get(idioma, frozenset())
    for palabra in _normal(str(fuente.get("frase_origen") or "")).split():
        mes = lexico.meses.get(palabra)
        if mes is not None and mes not in vale and palabra not in ambiguos:
            return palabra, mes
    return None


def mes_retrospectivo(incidente: dict[str, Any]) -> tuple[str, str, date] | None:
    """El mes que la frase literal de una fuente da a una noticia retrospectiva: (fuente_id,
    frase, día 1 de ese mes), el último anterior a la publicación. None si ninguna frase lo da (un
    pasado sin medida, «el mes pasado», no dice qué mes). Es la precisión que sostienen las fuentes
    cuando el experto no da el día (recogida/control_fichas.salir_de_la_retencion)."""
    if retrospectiva(incidente) is None:
        return None
    publicacion = date.fromisoformat(str(incidente["tiempo"]["inicio"]["valor"])[:10])
    for fuente in incidente.get("fuentes", []):
        if (encontrado := _mes_anterior(incidente, fuente)) is None:
            continue
        mes = encontrado[1]
        anio = publicacion.year if mes < publicacion.month else publicacion.year - 1
        frase = " ".join(str(fuente.get("frase_origen") or "").split())
        return str(fuente.get("id") or ""), frase, date(anio, mes, 1)
    return None


# Margen entre el fin publicado y lo que escribe la frase (una hora en punto, una duración
# redondeada): diez minutos. «pendant quatre heures» desde las 18:30 no respalda las 23:00
# (EODI-2025-00154).
MARGEN_FIN = timedelta(minutes=10)


def fin_escrito(frase: str, idioma: str | None, fin: datetime, inicio: datetime | None,
                zona_suceso: ZoneInfo) -> bool:  # fmt: skip
    """La frase respalda el fin: escribe esa hora (en la hora local del suceso o en UTC) o una
    duración que, contada desde el inicio, da ese fin (EODI-2026-00112: «monitorizat până la
    ora 22:03» son las 19:03 UTC en Moldavia en marzo, no las 20:03 que publicaba)."""
    from proceso.textos_dron import duraciones, horas_escritas

    fin = fin.astimezone(UTC)
    for hora, minuto in horas_escritas(frase):
        for momento in (fin, fin.astimezone(zona_suceso)):
            escrita = momento.replace(hour=hora, minute=minuto)
            if (
                abs(escrita - momento) <= MARGEN_FIN
                or abs(escrita - momento) >= timedelta(hours=24) - MARGEN_FIN
            ):
                return True
    if inicio is not None:
        real = fin - inicio.astimezone(UTC)
        return any(
            abs(real - timedelta(minutes=m)) <= MARGEN_FIN for m in duraciones(frase, idioma)
        )
    return False


def _instante_utc(fecha: dict[str, Any] | str | None) -> datetime | None:
    texto = str(fecha.get("valor") if isinstance(fecha, dict) else fecha or "")
    if "T" not in texto:
        return None
    return datetime.fromisoformat(texto.rstrip("Z")).replace(tzinfo=UTC)


def frases_del_fin(incidente: dict[str, Any], fin: datetime) -> list[tuple[str, str | None]]:
    """Las frases (con su idioma) de las fuentes que afirman ese fin o lo respaldan."""
    ids = {
        a["fuente_id"] for a in incidente.get("afirmaciones", [])
        if a.get("campo") == "fin" and _instante_utc(a.get("valor")) == fin
    }  # fmt: skip
    return [
        (str(f.get("frase_origen") or ""), f.get("idioma"))
        for f in incidente.get("fuentes", [])
        if f["id"] in ids or "fin" in (f.get("campos_respaldados") or [])
    ]


def fin_respaldado(incidente: dict[str, Any]) -> bool:
    """El fin publicado lo escribe alguna frase de las fuentes de la ficha (fin_escrito). Sin
    fin, no hay nada que respaldar."""
    tiempo = incidente.get("tiempo") or {}
    fin = _instante_utc(tiempo.get("fin"))
    if fin is None:
        return True
    lugar = incidente.get("lugar") or {}
    punto = lugar.get("punto") or {}
    zona_suceso = zona(lugar.get("pais"), punto.get("lat"), punto.get("lon")) or ZoneInfo("UTC")
    inicio = _instante_utc(tiempo.get("inicio"))
    return any(
        fin_escrito(frase, idioma, fin, inicio, zona_suceso)
        for frase, idioma in frases_del_fin(incidente, fin)
    )


def fines_sin_frase(incidente: dict[str, Any]) -> bool:
    """El fin de la ficha o alguna afirmación de fin no los escribe ninguna frase."""
    return not fin_respaldado(incidente) or len(
        sin_fin_sin_frase(copy.deepcopy(incidente)).get("afirmaciones", [])
    ) != len(incidente.get("afirmaciones", []))


def sin_fin_sin_frase(incidente: dict[str, Any]) -> dict[str, Any]:
    """Quita del documento el fin que ninguna frase respalda, con su duración, y las
    afirmaciones de fin cuya frase no lo escribe: «fin sin frase que lo respalde» (auditoría O;
    EODI-2025-00154, 23:00 UTC de «gut vier Stunden lang» desde las 18:30)."""
    tiempo = incidente.get("tiempo") or {}
    if tiempo.get("fin") and not fin_respaldado(incidente):
        tiempo.pop("fin", None)
        tiempo.pop("duracion_min", None)
    fuentes = {f["id"]: f for f in incidente.get("fuentes", [])}
    lugar = incidente.get("lugar") or {}
    punto = lugar.get("punto") or {}
    zona_suceso = zona(lugar.get("pais"), punto.get("lat"), punto.get("lon")) or ZoneInfo("UTC")
    inicio = _instante_utc(tiempo.get("inicio"))

    def vale(afirmacion: dict[str, Any]) -> bool:
        if afirmacion.get("campo") != "fin":
            return True
        fin = _instante_utc(afirmacion.get("valor"))
        fuente = fuentes.get(afirmacion.get("fuente_id", ""))
        return (
            fin is not None and fuente is not None
            and fin_escrito(str(fuente.get("frase_origen") or ""), fuente.get("idioma"), fin,
                            inicio, zona_suceso)
        )  # fmt: skip

    if "afirmaciones" in incidente:
        incidente["afirmaciones"] = [a for a in incidente["afirmaciones"] if vale(a)]
    return incidente


# Dos días de una misma frase unidos por una conjunción son dos sucesos: «w niedzielę i wtorek
# dwa drony», el domingo y el martes. La fecha toma el más temprano (_leer_con) y la ficha
# quedaba con un solo día y los drones de los dos (EODI-2026-00756, Letonia, 1 y 3 de noviembre
# de 2026). Dos días seguidos también («am Samstag und Sonntag jeweils eine der beiden
# Landebahnen kurzzeitig gesperrt», EODI-2026-00770, Leipzig/Halle, 7 y 8 de noviembre de 2026),
# salvo que la frase hable de la noche o de una parte del día junto a ellos («late Saturday and
# early Sunday», «Samstagabend und Sonntag»): eso es una noche que cruza la medianoche.
DIAS_MISMA_NOCHE = 1
# Entre los dos días, como mucho la conjunción y un artículo o preposición («y el», «i we»).
MAX_ENTRE_DIAS = 3
# Palabras alrededor de los dos días en que se busca la noche («late Saturday», «Sunday morning»).
MARGEN_NOCHE = 3
# Un día con hasta 3 letras más es el mismo día declinado («šeštadienį», «lauantaina»,
# «szombaton»); con más, en los idiomas que los componen, es el día con su parte
# («Samstagabend», «zaterdagavond», «lördagskvällen»).
MAX_DECLINACION = 3


@cache
def _conjunciones() -> frozenset[str]:
    return frozenset(_normal(c) for c in configuracion()["conjunciones_dias"])


@cache
def _partes_noche(idioma: str) -> tuple[frozenset[str], tuple[str, ...]]:
    """Las palabras de la noche del idioma: sueltas y las de varias palabras («gece yarısı»)."""
    formas = [_normal(f) for f in configuracion().get("partes_noche", {}).get(idioma, [])]
    return (
        frozenset(f for f in formas if " " not in f),
        tuple(f for f in formas if " " in f),
    )


def _dias_en(palabras: list[str], lx: Lexico) -> list[tuple[int, int, int, bool]]:
    """Los días de la semana de la frase: (primera palabra, última palabra, día, con su parte
    del día pegada), en orden. Casa la forma entera, la de varias palabras («e shtunë»), la
    declinada y, en los idiomas que componen, la compuesta («Samstagabend»)."""
    hallados: dict[int, tuple[int, int, int, bool]] = {}
    for forma, numero in lx.dias:
        trozos = forma.split()
        n = len(trozos)
        for i in range(len(palabras) - n + 1):
            if n > 1:
                if palabras[i : i + n] == trozos:
                    hallados.setdefault(i, (i, i + n - 1, numero, False))
                continue
            palabra = palabras[i]
            if not palabra.startswith(forma):
                continue
            resto = len(palabra) - len(forma)
            if resto <= MAX_DECLINACION:
                hallados[i] = (i, i, numero, False)
            elif lx.compone:
                hallados.setdefault(i, (i, i, numero, True))
    return [hallados[i] for i in sorted(hallados)]


def _de_noche(palabras: list[str], desde: int, hasta: int, idioma: str) -> bool:
    """Alguna palabra de la noche del idioma (o del inglés) entre las palabras desde…hasta,
    con un margen de MARGEN_NOCHE a cada lado."""
    tramo = palabras[max(0, desde - MARGEN_NOCHE) : hasta + MARGEN_NOCHE + 1]
    texto = f" {' '.join(tramo)} "
    for i in dict.fromkeys([idioma, "en"]):
        sueltas, compuestas = _partes_noche(i)
        if sueltas & set(tramo) or any(f" {c} " in texto for c in compuestas):
            return True
    return False


def dias_distintos(
    frase: str, publicacion: datetime, zona_medio: ZoneInfo, idioma: str | None
) -> list[date]:
    """Los días locales que nombra la frase si son dos días de la semana distintos unidos por
    una conjunción («w niedzielę i wtorek», «el domingo y el martes», «am Samstag und
    Sonntag»); si no, []. Dos días seguidos con la noche o una parte del día junto a ellos
    («late Saturday and early Sunday») son una noche, no dos sucesos. Con una fecha escrita no
    cuenta: el día de la semana que la acompaña es el mismo («donderdag 15 januari»). Dos días
    sueltos en la frase tampoco: «le detuvieron el lunes… este miércoles» cuenta dos momentos de
    un mismo suceso."""
    todos = lexicos()
    idiomas = [i for i in dict.fromkeys([idioma or "", "en"]) if i in todos]
    hoy = publicacion.astimezone(zona_medio).date()
    if _explicitas(frase, [todos[i] for i in idiomas], hoy):
        return []
    palabras = _normal(frase).split()
    conjunciones = _conjunciones()
    for idioma_lx in idiomas:
        for (i0, i1, uno, parte_uno), (j0, j1, otro, parte_otro) in pairwise(
            _dias_en(palabras, todos[idioma_lx])
        ):
            entre = set(palabras[i1 + 1 : j0])
            if j0 - i1 - 1 > MAX_ENTRE_DIAS or not entre & conjunciones:
                continue
            dias = sorted({_ultimo(uno, hoy), _ultimo(otro, hoy)})
            separados = (dias[-1] - dias[0]).days
            if (otro - uno) % DIAS_SEMANA == 1:
                # El segundo es el día siguiente al primero: son seguidos aunque la nota salga
                # el primero y el segundo, que aún no ha llegado, caiga en la semana anterior
                # («Naktį iš antradienio į trečiadienį», publicada el martes por la noche: el
                # miércoles salía seis días antes y la ficha de las alertas de Lituania del 10
                # de noviembre de 2026 quedaba retenida por «dos días»).
                separados = 1
            if separados > DIAS_MISMA_NOCHE:
                return dias
            if separados == 1 and not (
                parte_uno or parte_otro or _de_noche(palabras, i0, j1, idioma_lx)
            ):
                return dias
    return []


def frase_de_dos_dias(incidente: dict[str, Any]) -> tuple[str, list[date]] | None:
    """La primera frase de una fuente de la ficha que da dos días distintos (dias_distintos),
    con esos días; None si ninguna. Una ficha es un suceso de un día: esa frase pide separarla
    o una revisión que diga a qué día va cada cosa."""
    pais = (incidente.get("lugar") or {}).get("pais")
    for fuente in incidente.get("fuentes", []):
        frase = str(fuente.get("frase_origen") or "")
        valor = (fuente.get("fecha") or {}).get("valor")
        if not frase or not valor:
            continue
        zona_medio = (
            _zona_del_dominio(str(fuente.get("enlace") or "")) or zona(pais) or ZoneInfo("UTC")
        )
        publicacion = _momento(str(valor))
        if dias := dias_distintos(frase, publicacion, zona_medio, fuente.get("idioma")):
            return frase, dias
    return None
