"""Fuente: canal oficial del Ministerio de Defensa ruso (vista pública web de t.me/mod_russia).

Sentido UA_RU de la capa de guerra: drones ucranianos que el ministerio dice
haber derribado sobre Rusia y las zonas ocupadas. Solo cuentan los partes de
drones derribados («дежурными средствами ПВО перехвачены и уничтожены N
украинских беспилотных летательных аппаратов ... над территорией ...»); los
misiles y el resto de publicaciones se ignoran. Es la reivindicación de una
de las partes: fiabilidad D y marca pública «reivindicacion_de_parte».

Parser por código. Un parte que no se entiende lanza ParteIlegible con el
motivo; nunca se publica a medias.
"""

import json
import re
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from functools import cache
from pathlib import Path
from zoneinfo import ZoneInfo

from proceso.ataques import SENTIDO_UA_RU, Perfil
from recogida.descarga import Descargador
from recogida.fuente import Fuente, verificar_cabecera
from recogida.parte import (
    DESCONOCIDO,
    MAX_PALABRAS_FRASE,
    Derribo,
    Familia,
    Instante,
    ParteIlegible,
    ParteLeido,
    exacto,
)
from recogida.telegram import Pagina

MOSCU = ZoneInfo("Europe/Moscow")
CANAL = "mod_russia"
FUENTE_ID = "mindef_ru"
TITULO_OFICIAL = "Минобороны России"
VERSION_PARSER = "parte-mindef/1"
VOCABULARIO = Path(__file__).resolve().parent.parent / "configuracion" / "regiones_rusia.json"
# Inicio de la noche en los partes que lo declaran («с 20.00 мск 13 июня до 7.00 мск 14
# июня»). Los que dicen solo «в течение ночи» reciben esta hora con precisión aproximada.
HORA_INICIO_NOCHE = time(20, 0)
# «24.00» es la medianoche.
MEDIANOCHE = 24
DECENA = 10
# Un parte habla de las horas que acaban de pasar: una fecha declarada más de un día
# después de la publicación solo puede ser del año anterior.
MARGEN_FECHA = timedelta(days=1)

MESES = {
    "января": 1, "февраля": 2, "марта": 3, "апреля": 4, "мая": 5, "июня": 6,
    "июля": 7, "августа": 8, "сентября": 9, "октября": 10, "ноября": 11, "декабря": 12,
}  # fmt: skip
_MES = "(?:" + "|".join(MESES) + ")"
_PALABRAS_NUMERO = {
    "один": 1, "одного": 1, "одна": 1, "два": 2, "две": 2, "двух": 2, "три": 3, "трех": 3,
    "трёх": 3, "четыре": 4, "четырех": 4, "четырёх": 4, "пять": 5, "пяти": 5, "шесть": 6,
    "шести": 6, "семь": 7, "семи": 7, "восемь": 8, "восьми": 8, "девять": 9, "девяти": 9,
    "десять": 10, "десяти": 10, "одиннадцать": 11, "двенадцать": 12, "тринадцать": 13,
    "четырнадцать": 14, "пятнадцать": 15, "шестнадцать": 16, "семнадцать": 17,
    "восемнадцать": 18, "девятнадцать": 19,
}  # fmt: skip
_DECENAS = {
    "двадцать": 20, "тридцать": 30, "сорок": 40, "пятьдесят": 50, "шестьдесят": 60,
    "семьдесят": 70, "восемьдесят": 80, "девяносто": 90,
}  # fmt: skip
_UNIDADES = [p for p, n in _PALABRAS_NUMERO.items() if n < DECENA]
_PALABRAS_NUMERO |= _DECENAS
# «двадцать два»: decena y unidad separadas por un espacio.
_COMPUESTO = (
    "(?:"
    + "|".join(_DECENAS)
    + r")\s+(?:"
    + "|".join(sorted(_UNIDADES, key=len, reverse=True))
    + ")"
)
_NUM = (
    r"(?<![\w.:])(\d+|"
    + _COMPUESTO
    + "|"
    + "|".join(sorted(_PALABRAS_NUMERO, key=len, reverse=True))
    + r")(?![\w.:])"
)
_DRON = r"(?:беспилотн\w*\s+летательн\w*\s+аппарат\w*|БПЛА|беспилотник\w*|дрон\w*)"
_VERBO = re.compile(r"перехвач\w*|уничтож\w*|сбит\w*|подавл\w*", re.IGNORECASE)
_NEUTRALIZADOS = re.compile(r"подавл\w*|радиоэлектронн\w*|РЭБ", re.IGNORECASE)
# «над территорией», «над акваторией» o directamente «над Московским регионом».
_SOBRE = re.compile(r"(?<!\w)над\s+(?:(?:территори|акватори)\w*|(?=(?-i:[А-ЯЁ])))", re.IGNORECASE)
# «N украинских беспилотных летательных аппаратов», «два украинских БПЛА».
_CIFRA = re.compile(_NUM + r"\s+(?:украинск\w+\s+)?(?:ударн\w+\s+)?" + _DRON, re.IGNORECASE)
# Sin cifra y en singular: «уничтожен украинский беспилотный летательный аппарат»,
# «украинский БПЛА уничтожен», «беспилотный летательный аппарат уничтожен».
_SINGULAR = r"(?:беспилотный\s+летательный\s+аппарат|БПЛА|беспилотник)(?!\w)"
_VERBO_SINGULAR = r"(?:перехвачен|уничтожен|сбит|подавлен)(?!\w)"
_UNO = re.compile(
    _VERBO_SINGULAR + r"(?:\s+и\s+\w+)?\s+(?:украинский\s+)?" + _SINGULAR
    + r"|(?:украинский\s+)?" + _SINGULAR + r"(?:\s+самол[её]тного\s+типа)?\s+" + _VERBO_SINGULAR,
    re.IGNORECASE,
)  # fmt: skip
# «украинский беспилотный летательный аппарат» en nominativo, con otro verbo: uno.
_UNO_NOMINATIVO = re.compile(
    r"украинский\s+(?:беспилотный\s+летательный\s+аппарат|БПЛА|беспилотник)(?!\w)", re.I
)
# «украинские беспилотные летательные аппараты уничтожены»: sin cifra, todos los del intento.
_TODOS = re.compile(
    r"(?:украинские|все)\s+(?:беспилотные\s+летательные\s+аппараты|БПЛА|беспилотники)(?!\w)",
    re.I,
)
# «уничтожены пять и перехвачены три украинских БПЛА»: la primera cifra va sin el dron.
_Y_ANTES = re.compile(_NUM + r"\s+и\s+(?:перехвач|уничтож|подавл|сбит)\w*\s+(?=" + _NUM + ")", re.I)
# El preámbulo del intento, hasta la mención del territorio o de la defensa aérea.
_PREAMBULO = re.compile(
    r"попытк\w*.*?(?:Российской\s+Федерации|(?=ПВО)|(?=противовоздушной))", re.I | re.S
)
# «двадцать два ... уничтожено и еще тринадцать перехвачено».
_Y_OTROS = re.compile(r"и\s+ещ[её]\s+" + _NUM + r"\s+(?:перехвач|уничтож|подавл|сбит)\w*", re.I)
# La defensa aérea: la cifra de derribados va detrás; delante puede ir la del intento
# («при попытке ... с применением трех беспилотников»).
_PVO = re.compile(r"ПВО|противовоздушной\s+обороны", re.IGNORECASE)
_INTENTO = re.compile(r"попытк\w*\s+киевского\s+режима", re.IGNORECASE)
# Resúmenes que repiten partes ya publicados.
_RESUMEN = re.compile(r"^\W*(?:Главное\s+за\s+день|Итоги\s+недели|Сводка)", re.IGNORECASE)
# El pie del canal («🔹 Минобороны России», «Канал Минобороны России в MAКС») acaba el parte.
_PIE = re.compile(r"^\s*(?:🔹|💬|🎮|💥\s*Канал|Канал\s+Минобороны)", re.MULTILINE)
_PALABRA = re.compile(r"[А-ЯЁ][\w-]*")
_TIPOS = (
    (re.compile(r"самол[её]тного\s+типа", re.IGNORECASE), "ala_fija"),
    (re.compile(r"вертол[её]тного\s+типа|квадрокоптер|мультикоптер", re.IGNORECASE), "multirrotor"),
)

_H = r"(?:(?P<h{n}>\d{{1,2}})[.:](?P<n{n}>\d{{2}})|(?P<p{n}>полуночи))(?:\s+мск)?"
# «10 июля т.г.» (del año en curso) o «30.07».
_F = (
    r"(?:\s+(?:(?P<d{n}>\d{{1,2}})\s+(?P<m{n}>" + _MES + r")|(?P<e{n}>\d{{1,2}})\.(?P<f{n}>\d{{2}})"
    r"(?![\d.]))(?:\s+т\.\s?г\.)?)?"
)
# «3 сентября с 23.00 мск до полуночи», «с 22.41 8 августа до 05.05 мск 9 августа». A veces
# con una «C» latina.
_RANGO = re.compile(
    r"(?:(?P<d0>\d{1,2})\s+(?P<m0>"
    + _MES
    + r")\s+)?(?<!\w)[сc]\s+"
    + _H.format(n=1)
    + _F.format(n=1)
    # «В период с 20.00 мск 28 мая» no dice el fin.
    + r"(?:\s+до\s+"
    + _H.format(n=2)
    + _F.format(n=2)
    + ")?",
    re.IGNORECASE,
)
# «Около 15.05 мск» y «20 декабря в районе 21.00 мск» (aproximada), «В 13.40 мск» (minuto).
# «мск» puede faltar tras «около» («Около 07.15 при попытке ...»), y la hora puede ir sin
# minutos si sigue «часов» («Около 10 часов»).
_PUNTO = re.compile(
    r"(?:(?P<dia>\d{1,2})\s+(?P<mes>" + _MES + r")\s+)?(?<!\w)(?:"
    r"(?P<aprox>около|в\s+районе)\s+(?P<h>\d{1,2})(?:[.:](?P<n>\d{2})(?:\s+час\w*)?|\s+час\w*)"
    r"(?:\s+мск)?|в\s+(?P<h2>\d{1,2})[.:](?P<n2>\d{2})\s+мск)",
    re.IGNORECASE,
)
# «В течение (прошедшей, сегодняшней) ночи», «Сегодня ночью», «Ночью 16 ноября».
_NOCHE = re.compile(
    r"в\s+течени[еи]\s+(?:(?:прошедшей|сегодняшней)\s+)?ночи"
    r"|(?:этой|минувшей|прошедшей|сегодня)\s+ночью|ночью\s+(\d{1,2})\s+(" + _MES + ")",
    re.IGNORECASE,
)
# «В течение дня», «в течение прошедшего дня», «Утром», «В утренние часы 10 апреля».
_DIA = re.compile(
    r"(?:в\s+течени[еи]\s+(?:прошедшего\s+)?(?:дня|утра|суток)|утром|в\s+утренние\s+часы"
    r"|сегодня\s+(?:днем|днём|утром|вечером))"
    r"(?:\s+(\d{1,2})\s+(" + _MES + r"))?",
    re.IGNORECASE,
)
# «По состоянию на 20.00 мск»: el día hasta esa hora.
_HASTA = re.compile(r"по\s+состоянию\s+на\s+(\d{1,2})[.:](\d{2})\s+мск", re.IGNORECASE)


# --- Vocabulario --------------------------------------------------------------


@dataclass(frozen=True)
class Vocabulario:
    regiones: tuple[tuple[str, str], ...]  # (raíz, código), de la más larga a la más corta
    no_regiones: tuple[str, ...]


@cache
def vocabulario(ruta: Path = VOCABULARIO) -> Vocabulario:
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    raices = [(r, codigo) for codigo, v in datos["regiones"].items() for r in v["raices"]]
    return Vocabulario(
        regiones=tuple(sorted(raices, key=lambda x: -len(x[0]))),
        no_regiones=tuple(datos["no_regiones"]),
    )


def regiones_en(texto: str, voc: Vocabulario) -> list[str]:
    """Códigos de las regiones nombradas tras «над территорией», sin repetir.

    Una palabra con mayúscula que no es región conocida ni está en la lista de
    palabras que no son regiones deja el parte como fallido: el vocabulario crece.
    """
    codigos: list[str] = []
    for tramo in _SOBRE.split(texto)[1:]:
        # La lista de regiones acaba con la frase o con la línea (viñetas).
        tramo = re.split(r"\.\s|\n", tramo, maxsplit=1)[0]
        for palabra in _PALABRA.findall(tramo):
            codigo = next((c for r, c in voc.regiones if palabra.startswith(r)), None)
            if codigo is None:
                if not palabra.startswith(voc.no_regiones):
                    raise ParteIlegible(f"región fuera del vocabulario: {palabra}")
                continue
            if codigo not in codigos:
                codigos.append(codigo)
    return codigos


# --- Texto --------------------------------------------------------------------


def cuerpo(texto: str) -> str:
    """El parte sin el pie del canal."""
    pie = _PIE.search(texto)
    return (texto[: pie.start()] if pie else texto).strip()


def primer_parrafo(texto: str) -> str:
    return re.split(r"\n\s*\n", cuerpo(texto), maxsplit=1)[0]


def parte_principal(texto: str) -> str:
    """El primer párrafo, y el segundo si el primero es solo el preámbulo del intento.

    Hasta 2024 el parte iba en dos párrafos: «пресечена попытка киевского режима
    ...» y «Дежурными средствами ПВО ... уничтожен над ...».
    """
    parrafos = re.split(r"\n\s*\n", cuerpo(texto))
    if len(parrafos) > 1 and not _VERBO.search(parrafos[0]):
        return parrafos[0] + "\n\n" + parrafos[1]
    return parrafos[0]


def _tramo_de_derribos(parte: str) -> str:
    """El parte sin el preámbulo del intento, que puede traer otra cifra («при попытке ... с
    применением трех беспилотников»)."""
    return _PREAMBULO.sub(" ", parte, count=1)


def numero(texto: str) -> int:
    limpio = " ".join(texto.lower().split())
    if " " in limpio:
        return sum(numero(parte) for parte in limpio.split())
    return _PALABRAS_NUMERO[limpio] if limpio in _PALABRAS_NUMERO else int(limpio)


def es_parte(texto: str) -> bool:
    """Parte de drones derribados sobre Rusia o zonas ocupadas, no un resumen del día."""
    if _RESUMEN.match(texto):
        return False
    parrafo = parte_principal(texto)
    return bool(
        _VERBO.search(parrafo)
        and (_PVO.search(parrafo) or _INTENTO.search(parrafo))
        and re.search(_DRON, parrafo, re.IGNORECASE)
        and re.search(r"украинск|ВСУ|киевского\s+режима", parrafo, re.IGNORECASE)
        and _SOBRE.search(cuerpo(texto))
    )


# --- Periodo ------------------------------------------------------------------


def _fecha(dia: int, mes: int, publicado: date) -> date:
    candidata = date(publicado.year, mes, dia)
    if candidata > publicado + MARGEN_FECHA:
        candidata = date(publicado.year - 1, mes, dia)
    return candidata


def _utc(dia: date, hora: time) -> datetime:
    return datetime.combine(dia, hora, tzinfo=MOSCU).astimezone(UTC)


def _hora(m: re.Match[str], n: str) -> time | None:
    """Hora de un extremo; None es medianoche («полуночи», «24.00»)."""
    if m[f"p{n}"] or int(m[f"h{n}"]) == MEDIANOCHE:
        return None
    return time(int(m[f"h{n}"]), int(m[f"n{n}"]))


def _dia(m: re.Match[str], n: str, publicado: date) -> date | None:
    """Fecha de un extremo, con el mes en letras o en cifras, o None si no la da."""
    if m[f"d{n}"]:
        return _fecha(int(m[f"d{n}"]), MESES[m[f"m{n}"].lower()], publicado)
    if n != "0" and m[f"e{n}"]:
        return _fecha(int(m[f"e{n}"]), int(m[f"f{n}"]), publicado)
    return None


def _rango(m: re.Match[str], publicado: datetime) -> tuple[Instante, Instante]:
    local = publicado.astimezone(MOSCU)
    base = _dia(m, "0", local.date()) or local.date()
    d1, d2 = _dia(m, "1", local.date()), _dia(m, "2", local.date())
    fechado = bool(m["d0"] or d1 or d2)
    if m["h2"] is None and m["p2"] is None:
        # Solo el inicio: acaba cuando se publica.
        dia = d1 or base
        inicio = _utc(dia, _hora(m, "1") or time(0, 0))
        if inicio > publicado:
            inicio -= timedelta(days=1)
        return Instante(inicio, "minuto"), Instante(
            publicado.astimezone(UTC).replace(second=0, microsecond=0), "aproximada"
        )
    h1, h2 = _hora(m, "1"), _hora(m, "2")
    d2 = d2 or base
    # «до полуночи»: la medianoche que cierra el día.
    fin = _utc(d2 + timedelta(days=1), time(0, 0)) if h2 is None else _utc(d2, h2)
    if d1 is None:
        # Sin fecha de inicio: el mismo día que el fin, o la víspera si cruza la medianoche.
        d1 = d2 if h1 is None or h2 is None or h1 <= h2 else d2 - timedelta(days=1)
    inicio = _utc(d1, h1 or time(0, 0))
    if h1 is None and m["p1"] is None and (m["d1"] or m["e1"]):
        # «с 24.00 мск 12 апреля»: la medianoche que cierra el 12.
        inicio += timedelta(days=1)
    if not fechado and fin > publicado:
        # Sin fechas y acabando después de publicarse: es el tramo del día anterior.
        inicio, fin = inicio - timedelta(days=1), fin - timedelta(days=1)
    return Instante(inicio, "minuto"), Instante(fin, "minuto")


def periodo(texto: str, publicado: datetime) -> tuple[Instante, Instante]:
    """Periodo tal como lo declara el parte, de hora de Moscú a UTC."""
    local = publicado.astimezone(MOSCU)
    redondeado = Instante(publicado.astimezone(UTC).replace(second=0, microsecond=0), "aproximada")
    try:
        if m := _RANGO.search(texto):
            inicio, fin = _rango(m, publicado)
        elif m := _PUNTO.search(texto):
            aproximada = m["aprox"] is not None
            hora, minuto = int(m["h"] or m["h2"]), int(m["n"] or m["n2"] or 0)
            dia = _fecha(int(m["dia"]), MESES[m["mes"].lower()], local.date()) if m["dia"] else None
            momento = _utc(dia or local.date(), time(hora, minuto))
            if dia is None and momento > publicado:
                momento -= timedelta(days=1)
            inicio = fin = Instante(momento, "aproximada" if aproximada else "minuto")
        elif m := _NOCHE.search(texto):
            # La noche que acaba el día declarado o el de la publicación.
            fin_noche = _fecha(int(m[1]), MESES[m[2].lower()], local.date()) if m[1] else None
            dia = (fin_noche or local.date()) - timedelta(days=1)
            inicio, fin = Instante(_utc(dia, HORA_INICIO_NOCHE), "aproximada"), redondeado
        elif m := _HASTA.search(texto):
            momento = _utc(local.date(), time(int(m[1]), int(m[2])))
            if momento > publicado:
                momento -= timedelta(days=1)
            dia = momento.astimezone(MOSCU).date()
            inicio, fin = Instante(_utc(dia, time(0, 0)), "dia"), Instante(momento, "minuto")
        elif m := _DIA.search(texto):
            dia = _fecha(int(m[1]), MESES[m[2].lower()], local.date()) if m[1] else local.date()
            inicio, fin = Instante(_utc(dia, time(0, 0)), "dia"), redondeado
        else:
            raise ParteIlegible("sin periodo declarado")
    except ParteIlegible:
        raise
    except ValueError as error:
        raise ParteIlegible(f"fecha imposible: {error}") from error
    if fin.valor < inicio.valor:
        raise ParteIlegible("el periodo acaba antes de empezar")
    return inicio, fin


# --- Parte --------------------------------------------------------------------


def derribados(parrafo: str) -> int:
    tramo = _tramo_de_derribos(parrafo)
    cifras = list(_CIFRA.finditer(tramo))
    if cifras:
        # «уничтожены 155 ... самолетного типа:» abre la lista por regiones: la cifra es el
        # total. Si no, las cifras de la frase se suman («два ... над Брянской и еще три
        # БПЛА над акваторией»).
        if re.match(r"[^.\n]*?:", tramo[cifras[0].end() :]):
            return numero(cifras[0][1])
        frase = re.split(r"\.\s", tramo[cifras[0].start() :], maxsplit=1)[0]
        total = sum(numero(m[1]) for m in _CIFRA.finditer(frase))
        total += sum(numero(m[1]) for m in _Y_OTROS.finditer(tramo))
        total += sum(numero(m[1]) for m in _Y_ANTES.finditer(tramo))
        return total
    if _UNO.search(tramo) or _UNO_NOMINATIVO.search(tramo):
        return 1
    if _TODOS.search(tramo) and (m := _CIFRA.search(parrafo)):
        # «все беспилотники уничтожены»: todos los del intento.
        return numero(m[1])
    raise ParteIlegible("sin cifra de drones")


def leer(texto: str, publicado: datetime) -> ParteLeido:
    """Extrae los drones derribados de un parte. Lanza ParteIlegible si no lo entiende."""
    parrafo = parte_principal(texto)
    inicio, fin = periodo(parrafo, publicado)
    n = derribados(parrafo)
    regiones = regiones_en(cuerpo(texto), vocabulario())
    if not regiones and not re.search(r"акватори", texto, re.IGNORECASE):
        raise ParteIlegible("sin regiones")
    primera = re.split(r"(?<=[.:!])\s", re.sub(r"^\W+", "", parrafo), maxsplit=1)[0]
    return ParteLeido(
        inicio=inicio,
        fin=fin,
        lanzados=dict.fromkeys(["total", *Familia], DESCONOCIDO),
        zonas_lanzamiento=(),
        derribados=exacto(n),
        derribados_categoria=(
            Derribo.DERRIBADOS_O_NEUTRALIZADOS
            if _NEUTRALIZADOS.search(parrafo)
            else Derribo.DERRIBADOS
        ),
        perdidos_guerra_electronica=DESCONOCIDO,
        localizaciones_impacto=DESCONOCIDO,
        localizaciones_restos=DESCONOCIDO,
        lugares_impacto=(),
        lugares_restos=(),
        regiones=tuple(regiones),
        cruces=(),
        frase=" ".join(primera.split()[:MAX_PALABRAS_FRASE]),
        tipos_dron=tuple(tipo for patron, tipo in _TIPOS if patron.search(parrafo)),
    )


# --- Auditoría ----------------------------------------------------------------

PALABRAS_DRON = re.compile(r"беспилотн|БПЛА|дрон", re.IGNORECASE)


def motivo_no_parte(texto: str) -> str | None:
    """Por qué una publicación con drones y cifras no es un parte, o None si no se sabe."""
    if _RESUMEN.match(texto):
        return "resumen del día o de la semana"
    parrafo = parte_principal(texto)
    if not _VERBO.search(parrafo):
        return "sin derribos (frente, vídeo u otro tema)"
    if not _SOBRE.search(cuerpo(texto)):
        return "derribos en la zona de combate, no sobre territorio"
    return None


def verificar(descargador: Descargador, portada: Pagina) -> None:
    """Insignia de verificado y título del ministerio. No enlaza a una web que lo confirme."""
    verificar_cabecera(portada, TITULO_OFICIAL)


FUENTE = Fuente(
    id=FUENTE_ID,
    canal=CANAL,
    perfil=Perfil(
        sentido=SENTIDO_UA_RU,
        idioma="ru",
        zona=MOSCU,
        version_parser=VERSION_PARSER,
        reivindicacion=True,
    ),
    verificar=verificar,
    es_parte=es_parte,
    leer=leer,
    palabras_dron=PALABRAS_DRON,
    explicar=motivo_no_parte,
)
