"""Parser por código de los partes de ataque de la Fuerza Aérea de Ucrania.

Solo se registran drones: las cifras de misiles del mismo parte se ignoran.
Un parte que no se entiende lanza ParteIlegible con el motivo; nunca se
publica a medias.
"""

import itertools
import json
import re
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from enum import StrEnum
from functools import cache
from pathlib import Path
from zoneinfo import ZoneInfo

from esquema import Documento

KYIV = ZoneInfo("Europe/Kyiv")
VOCABULARIO = Path(__file__).resolve().parent.parent / "configuracion" / "regiones_ucrania.json"
VERSION_PARSER = "parte-fuerza-aerea/1"
MAX_PALABRAS_FRASE = 25
# Inicio habitual de la noche en los partes que lo declaran ("з 18:00"). Los
# que no lo declaran reciben esta hora con precisión aproximada.
HORA_INICIO_NOCHE = time(18, 0)
# Un parte habla de la noche que acaba de pasar: una fecha declarada más de un
# día después de la publicación solo puede ser del año anterior.
MARGEN_FECHA = timedelta(days=1)
# Una línea con al menos un 80 % de letras mayúsculas es el titular del parte; el
# cuerpo, con nombres propios y siglas, no pasa de un 20 %.
PROPORCION_TITULAR = 0.8
# "проводив повітряну розвідку трьома безпілотниками": basta mirar las 30 letras previas.
VENTANA_RECONOCIMIENTO = 30
DECENA = 10
MEDIANOCHE = 24

DESCONOCIDO = "desconocido"
Rango = Documento | str

MESES = {
    "січня": 1, "лютого": 2, "березня": 3, "квітня": 4, "травня": 5, "червня": 6,
    "липня": 7, "серпня": 8, "вересня": 9, "жовтня": 10, "листопада": 11, "грудня": 12,
}  # fmt: skip
_MES = "(" + "|".join(MESES) + ")"
_PALABRAS_NUMERO = {
    "один": 1, "одним": 1, "одного": 1, "два": 2, "двома": 2, "двох": 2, "три": 3,
    "трьома": 3, "трьох": 3, "чотири": 4, "чотирма": 4, "чотирьох": 4, "п'ять": 5,
    "п'ятьма": 5, "п'яти": 5, "шість": 6, "шістьма": 6, "сім": 7, "сімома": 7,
    "вісім": 8, "вісьмома": 8, "дев'ять": 9, "дев'ятьма": 9, "десять": 10, "десятьма": 10,
    "шести": 6, "семи": 7, "восьми": 8, "дев'яти": 9, "десяти": 10, "п'ятьох": 5,
    "шістьох": 6, "сімох": 7, "вісьмох": 8, "дев'ятьох": 9, "десятьох": 10,
}  # fmt: skip
# De 11 a 30 en nominativo, genitivo e instrumental: "одинадцять", "двадцятьма".
_DECENAS = {
    "одинадцят": 11, "дванадцят": 12, "тринадцят": 13, "чотирнадцят": 14, "п'ятнадцят": 15,
    "шістнадцят": 16, "сімнадцят": 17, "вісімнадцят": 18, "дев'ятнадцят": 19, "двадцят": 20,
    "тридцят": 30,
}  # fmt: skip
_PALABRAS_NUMERO |= {r + s: n for r, n in _DECENAS.items() for s in ("ь", "и", "ьма")}
_APOSTROFOS = str.maketrans({"’": "'", "ʼ": "'", "`": "'", "\xa0": " "})

# Número en cifras con sufijo de caso opcional ("23-ма", "30-ю") o en letras.
_NUM = (
    r"(?<![\w:.])(\d+|" + "|".join(sorted(_PALABRAS_NUMERO, key=len, reverse=True)) + r")(?![\w:])"
)
_SUFIJO = r"(?:-[^\W\d_]{1,4}|ма|ми|ю|ти|х|м|ох|ьох|ьма|ома|ий|і|ів)?"
_DRON = (
    r"(?:БпЛА|БПЛА|безпілотник\w*|безпілотн\w+\s+літальн\w+\s+апарат\w*|дрон\w*"
    r"|шахед\w*|Shahed\w*|Шахед\w*|Герань\w*|Гербер\w*|Gerbera|Бандерол\w*"
    r"|баражуюч\w+\s+боєприпас\w*)"
)
# Hasta cuatro palabras entre la cifra y el dron ("ударними", "ворожих", "S8000"),
# nunca una conjunción, una preposición, un misil, un mes, un verbo ni otro número:
# "3 ракетами та 50 БпЛА" no es 3 y "1 листопада уночі збито шість дронів" no es 1.
_NO_INTERMEDIA = (
    r"ракет|року|атакув|застосув|випуст|запуст|уночі|вночі|збит|знищ|"
    + _MES[1:-1]
    + "|"
    + "|".join(sorted(_PALABRAS_NUMERO, key=len, reverse=True))
)
_ENTRE = (
    r"(?:\s+(?!(?:" + _NO_INTERMEDIA + r")|(?:та|і|й|а|також|з|із|до|по|на|в|у)\b)"
    r"[«\"“]?[^\W\d][\w'’/-]*[»\"”]?|\s+S\d+){0,4}?"
)
CIFRA_DRONES = re.compile(_NUM + _SUFIJO + _ENTRE + r"\s+[«\"“]?" + _DRON, re.IGNORECASE)
# Subcuenta de la cifra anterior: "(понад 50 із них - реактивні)".
_DE_ELLOS = re.compile(
    r"(понад|близько|щонайменше|майже|до)?\s*" + _NUM + r"\s+(?:із|з)\s+них\s*[-–—:]?\s*([^,.;)]+)",
    re.IGNORECASE,
)
# Derribados como "58 з 59".
_DE_TOTAL = re.compile(_NUM + r"\s+(?:із|з)\s+" + _NUM + _SUFIJO + r"(?!\s+них)", re.IGNORECASE)


class ParteIlegible(ValueError):
    """El parte parece un parte de ataque, pero el parser no lo entiende."""


class Familia(StrEnum):
    SHAHED_GERAN = "shahed_geran"
    GERBERA_SENUELOS = "gerbera_senuelos"
    OTROS = "otros"


FAMILIAS_POR_PALABRA: tuple[tuple[re.Pattern[str], Familia], ...] = (
    (re.compile(r"шахед|shahed|герань|geran|реактивн", re.I), Familia.SHAHED_GERAN),
    (
        re.compile(r"гербер|гербар|gerbera|імітатор|пароді|хибн|обманк", re.I),
        Familia.GERBERA_SENUELOS,
    ),
    (
        re.compile(r"інш\w+\s+тип|італмас|ланцет|молні|бандерол|дань-т|s8000", re.I),
        Familia.OTROS,
    ),
)


@dataclass(frozen=True)
class Instante:
    valor: datetime
    precision: str

    def documento(self) -> Documento:
        return {"valor": self.valor.strftime("%Y-%m-%dT%H:%MZ"), "precision": self.precision}


@dataclass(frozen=True)
class ParteLeido:
    inicio: Instante
    fin: Instante
    lanzados: dict[str, Rango]
    zonas_lanzamiento: tuple[str, ...]
    derribados: Rango
    perdidos_guerra_electronica: Rango
    localizaciones_impacto: Rango
    localizaciones_restos: Rango
    lugares_impacto: tuple[str, ...]
    lugares_restos: tuple[str, ...]
    regiones: tuple[str, ...]
    cruces: tuple[tuple[str, Rango], ...]
    frase: str


# --- Vocabulario --------------------------------------------------------------


@dataclass(frozen=True)
class Vocabulario:
    regiones: tuple[tuple[str, str], ...]  # (raíz, código), de la raíz más larga a la más corta
    nombres: dict[str, str]
    paises: tuple[tuple[str, str], ...]


@cache
def vocabulario(ruta: Path = VOCABULARIO) -> Vocabulario:
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    raices = [(r, codigo) for codigo, v in datos["regiones"].items() for r in v["raices"]]
    paises = [(r, codigo) for codigo, lista in datos["paises"].items() for r in lista]
    return Vocabulario(
        regiones=tuple(sorted(raices, key=lambda x: -len(x[0]))),
        nombres={codigo: v["nombre"] for codigo, v in datos["regiones"].items()},
        paises=tuple(sorted(paises, key=lambda x: -len(x[0]))),
    )


_PALABRA = re.compile(r"[\w'’-]+")


def regiones_en(texto: str, voc: Vocabulario) -> list[str]:
    """Códigos de las regiones nombradas, en orden de aparición y sin repetir."""
    codigos: list[str] = []
    for palabra in _PALABRA.findall(texto):
        if not palabra[0].isupper():
            continue
        for raiz, codigo in voc.regiones:
            if palabra.startswith(raiz):
                if codigo not in codigos:
                    codigos.append(codigo)
                break
    return codigos


def pais_en(texto: str, voc: Vocabulario) -> str | None:
    for palabra in _PALABRA.findall(texto):
        for raiz, codigo in voc.paises:
            if palabra.lower().startswith(raiz.lower()):
                return codigo
    return None


# --- Texto --------------------------------------------------------------------


def numero(texto: str) -> int:
    limpio = texto.translate(_APOSTROFOS).lower()
    if limpio in _PALABRAS_NUMERO:
        return _PALABRAS_NUMERO[limpio]
    return int(limpio)


def valor(cifra: re.Match[str]) -> int:
    """Valor de una cifra de drones: "чотирма десятками" son 40."""
    return numero(cifra[1]) * (
        DECENA if re.search(r"десят", cifra[0][len(cifra[1]) :], re.I) else 1
    )


def exacto(n: int) -> Documento:
    return {"min": n, "max": n}


# Guion, punto o un emoji delante de una cifra ("🛬 21 ударний БпЛА").
_VINETA = re.compile(r"^\s*(?:[-–—•]|[^\w\s«\"“(]+(?=\s*\d))\s*")


_SIGUE = re.compile(r"\s*[\da-zа-яіїєґ]")


def frases(texto: str) -> list[str]:
    """Frases del parte. Una cabecera terminada en ":" se une con sus viñetas,
    aunque haya líneas en blanco entre ellas.

    Una línea que sigue sin cerrar la anterior ("атакував\\n118-ма ...") continúa su
    frase. Solo se corta tras un punto si sigue una mayúscula: "обл. рф" no corta.
    """
    bloques: list[str] = []
    abierto = False
    anterior = ""
    for linea in texto.translate(_APOSTROFOS).splitlines():
        if not linea.strip():
            anterior = ""
            continue
        if abierto and _VINETA.match(linea):
            bloques[-1] += "; " + _VINETA.sub("", linea).strip()
        elif (
            anterior
            and not re.search(r"[.!?:;]\s*$", anterior)
            and not _es_titular(anterior)
            and _SIGUE.match(linea)
        ):
            bloques[-1] += " " + linea.strip()
            abierto = linea.rstrip().endswith(":")
        else:
            bloques.append(linea.strip())
            abierto = linea.rstrip().endswith(":")
        anterior = linea
    resultado: list[str] = []
    for bloque in bloques:
        resultado += re.split(r"(?<=[.!?])\s+(?=[^\W\d_a-zа-яіїєґ])", bloque)
    return [f.strip() for f in resultado if f.strip()]


def frase_origen(texto: str) -> str:
    """Primera frase del ataque, recortada a 25 palabras."""
    for frase in frases(texto):
        if _ES_ATAQUE.search(frase):
            return " ".join(frase.split()[:MAX_PALABRAS_FRASE])
    return " ".join(texto.split()[:MAX_PALABRAS_FRASE])


# --- Periodo ------------------------------------------------------------------


def _fecha(dia: int, mes: int, anio: int | None, publicado: datetime) -> date:
    if anio is not None:
        return date(anio, mes, dia)
    local = publicado.astimezone(KYIV).date()
    candidata = date(local.year, mes, dia)
    if candidata > local + MARGEN_FECHA:
        candidata = date(local.year - 1, mes, dia)
    return candidata


def _utc(dia: date, hora: time) -> datetime:
    return datetime.combine(dia, hora, tzinfo=KYIV).astimezone(UTC)


def _anio(texto: str | None) -> int | None:
    return int(texto) if texto else None


_HORA = r"(\d{1,2})[:.](\d{2})"
_ANIO = r"(?:\s+(\d{4})\s*(?:року|р\.?)?)?"
_NOCHE = re.compile(
    r"(?:ніч\w*|уночі|вночі),?\s+(?:з\s+\d{1,2}\s+(?:" + _MES[1:-1] + r"\s+)?)?на\s+"
    r"(?:(?:понеділок|вівторок|середу|четвер|п'ятницю|суботу|неділю)\s+)?"
    r"(\d{1,2})(?:-?го)?,?\s+" + _MES + _ANIO,
    re.IGNORECASE,
)
# "протягом дня 25 вересня", "протягом поточної доби 13 липня".
_DIA = re.compile(
    r"(?:(?:протягом|впродовж|за)\s+(?:\w+ої\s+)?(?:доби|дня)|увечері|ввечері|вранці),?\s+"
    r"(\d{1,2}),?\s+" + _MES + _ANIO,
    re.I,
)
# 2023: "Із 18.30 25 грудня по 03.00 26 грудня", "з 21.10 год 30 березня по 01.30 год 31 березня".
_RANGO = re.compile(
    r"(?:з|із)\s+"
    + _HORA
    + r"\s+(?:год\s+)?(\d{1,2})\s+"
    + _MES
    + r"\s+(?:по|до)\s+"
    + _HORA
    + r"\s+(?:год\s+)?(\d{1,2})\s+"
    + _MES
    + _ANIO,
    re.IGNORECASE,
)
# "У період із 14.30 по 20.30 7 травня".
# 2022: "Уночі 5 жовтня", "2 жовтня уночі".
_NOCHE_2022 = (
    re.compile(r"(?:уночі|вночі),?\s+(\d{1,2})\s+" + _MES + _ANIO, re.IGNORECASE),
    re.compile(r"(\d{1,2})\s+" + _MES + _ANIO + r",?\s+(?:уночі|вночі)", re.IGNORECASE),
)
# 2022: "6 жовтня з 15:00 по 20:00", "06 жовтня, в проміжок часу з 09.00 до 11.30".
_INTERVALO_2022 = re.compile(
    r"(\d{1,2})\s+"
    + _MES
    + r",?\s+(?:в\s+проміжок\s+часу\s+|у\s+період\s+)?(?:з|із)\s+"
    + _HORA
    + r"\s+(?:по|до)\s+"
    + _HORA,
    re.IGNORECASE,
)
_INTERVALO = re.compile(
    r"період\w*\s+(?:з|із)\s+" + _HORA + r"\s+(?:по|до)\s+" + _HORA + r"\s+(\d{1,2})\s+" + _MES,
    re.IGNORECASE,
)
# Fecha opcional tras la hora: "25 вересня" o "23.09".
_FECHA_OPCIONAL = r"(?:\s+(\d{1,2})(?:\s+" + _MES + r"|\.(\d{2})(?!\d)))?"
_DESDE = re.compile(r"(?:з|із|від)\s+" + _HORA + _FECHA_OPCIONAL, re.I)
_HASTA = re.compile(r"(?:до|по)\s+" + _HORA + _FECHA_OPCIONAL, re.I)
_STANOM = re.compile(r"станом\s+на\s+" + _HORA + _FECHA_OPCIONAL, re.I)


def _sin_errata(m: re.Match[str], base: date) -> re.Match[str]:
    """El inicio se admite en la fecha esperada o la víspera; otra fecha es una errata.

    Se corrige a la fecha esperada si el día es ese ("з 19.00 2 червня" en la noche
    del 3 de agosto) o el siguiente ("із 21.00 15 листопада" en la noche del 15, que
    acabaría antes de empezar); si no, el periodo no es fiable.
    """
    if not m[3]:
        return m
    declarado = (int(m[3]), _mes(m))
    if declarado in {(d.day, d.month) for d in (base - timedelta(days=1), base)}:
        return m
    siguiente = base + timedelta(days=1)
    if int(m[3]) == base.day or declarado == (siguiente.day, siguiente.month):
        sin_fecha = _DESDE.match(f"з {m[1]}:{m[2]}")
        assert sin_fecha is not None
        return sin_fecha
    raise ParteIlegible("periodo incoherente")


def _mes(m: re.Match[str]) -> int:
    return MESES[m[4].lower()] if m[4] else int(m[5])


def _hora(m: re.Match[str], dia: date, publicado: datetime) -> datetime:
    if m[3]:
        dia = _fecha(int(m[3]), _mes(m), dia.year, publicado)
    return _utc(dia, time(int(m[1]), int(m[2])))


def _a_la_hora(dia: date, hora: int, minuto: int) -> datetime:
    """Hora de Kyiv en UTC; "24.00" es la medianoche del día siguiente."""
    if hora == MEDIANOCHE:
        return _utc(dia + timedelta(days=1), time(0, minuto))
    return _utc(dia, time(hora, minuto))


def _intervalo(texto: str) -> tuple[int, str, int, int, int, int] | None:
    """(día, mes, hora, minuto, hora, minuto) de un intervalo explícito de un solo día."""
    if m := _INTERVALO.search(texto):
        return int(m[5]), m[6], int(m[1]), int(m[2]), int(m[3]), int(m[4])
    if m := _INTERVALO_2022.search(texto):
        return int(m[1]), m[2], int(m[3]), int(m[4]), int(m[5]), int(m[6])
    return None


def declara_periodo(texto: str) -> bool:
    patrones = (_NOCHE, *_NOCHE_2022, _DIA, _INTERVALO, _INTERVALO_2022, _RANGO)
    return any(p.search(texto) for p in patrones)


def periodo(texto: str, publicado: datetime) -> tuple[Instante, Instante]:
    """Periodo tal como lo declara el parte, en UTC."""
    if rango := _RANGO.search(texto):
        try:
            anio = _anio(rango[9])
            abre = _a_la_hora(
                _fecha(int(rango[3]), MESES[rango[4].lower()], anio, publicado),
                int(rango[1]),
                int(rango[2]),
            )
            cierra = _a_la_hora(
                _fecha(int(rango[7]), MESES[rango[8].lower()], anio, publicado),
                int(rango[5]),
                int(rango[6]),
            )
        except ValueError as error:
            raise ParteIlegible(f"fecha imposible: {error}") from error
        if cierra < abre:
            raise ParteIlegible("el periodo acaba antes de empezar")
        return Instante(abre, "minuto"), Instante(cierra, "minuto")
    intervalo = None if _NOCHE.search(texto) else _intervalo(texto)
    if intervalo is not None:
        d, mes, h1, m1, h2, m2 = intervalo
        try:
            dia = _fecha(d, MESES[mes.lower()], None, publicado)
            abre = _a_la_hora(dia, h1, m1)
            cierra = _a_la_hora(dia, h2, m2)
        except ValueError as error:
            raise ParteIlegible(f"fecha imposible: {error}") from error
        if cierra < abre:
            raise ParteIlegible("el periodo acaba antes de empezar")
        return Instante(abre, "minuto"), Instante(cierra, "minuto")
    noche = _NOCHE.search(texto) or _NOCHE_2022[0].search(texto) or _NOCHE_2022[1].search(texto)
    declarado = noche or _DIA.search(texto)
    if declarado is None:
        raise ParteIlegible("sin periodo declarado")
    cola = texto[declarado.end() : declarado.end() + 80]
    try:
        dia = _fecha(int(declarado[1]), MESES[declarado[2].lower()], _anio(declarado[3]), publicado)
        # El intervalo explícito va justo detrás: "(з 18:00 25 вересня)", "(із 7.00 до 18.30)".
        explicito = cola.lstrip().startswith(("(", "з", "і"))
        desde = _DESDE.match(cola.lstrip(" (")) if explicito else None
        hasta = _HASTA.search(cola[: cola.find(")")]) if desde and ")" in cola else None
        if desde is not None:
            base = dia - timedelta(days=1) if noche and int(desde[1]) >= 12 else dia
            inicio = Instante(_hora(_sin_errata(desde, base), base, publicado), "minuto")
        elif noche is not None:
            inicio = Instante(_utc(dia - timedelta(days=1), HORA_INICIO_NOCHE), "aproximada")
        else:
            inicio = Instante(_utc(dia, time(0, 0)), "dia")
        stanom = _STANOM.search(texto)
        if hasta is not None:
            fin = Instante(_hora(hasta, dia, publicado), "minuto")
        elif stanom is not None:
            fin = Instante(_hora(stanom, dia, publicado), "minuto")
        else:
            redondeado = publicado.astimezone(UTC).replace(second=0, microsecond=0)
            fin = Instante(redondeado, "aproximada")
    except ParteIlegible:
        raise
    except ValueError as error:
        raise ParteIlegible(f"fecha imposible: {error}") from error
    if fin.valor < inicio.valor:
        raise ParteIlegible("el periodo acaba antes de empezar")
    return inicio, fin


# --- Drones -------------------------------------------------------------------


def familias_en(texto: str) -> set[Familia]:
    return {familia for patron, familia in FAMILIAS_POR_PALABRA if patron.search(texto)}


# Los tipos de dron van tras la cifra hasta la zona de lanzamiento o el fin de frase.
_FIN_TIPOS = re.compile(
    r"\s(?:із|з)\s+(?:напрямк|район|території|акваторії|повітряного)"
    r"|[.;]\s+(?=[^\W\d_a-zа-яіїєґ])|;|\.$",
    re.IGNORECASE,
)


def _cifras(frase: str) -> list[re.Match[str]]:
    """Cifras de drones que no son subcuenta de otra ("50 із них")."""
    subcuentas = [m.span() for m in _DE_ELLOS.finditer(frase)]
    return [
        m
        for m in CIFRA_DRONES.finditer(frase)
        if not any(a < m.end() and m.start() < b for a, b in subcuentas)
        # Los drones de reconocimiento (Orlan, Zala, Supercam) no son de ataque.
        and not re.search(r"розвідувальн", m[0], re.IGNORECASE)
        and not re.search(
            r"розвідк\w*\s*$", frase[max(0, m.start() - VENTANA_RECONOCIMIENTO) : m.start()], re.I
        )
    ]


# "понад 200 ударних безпілотників": un mínimo sin máximo no cabe en un rango.
_SIN_MAXIMO = re.compile(r"(?:понад|більше|щонайменше|більш\s+ніж)\s*$", re.IGNORECASE)


def lanzados(frase: str) -> dict[str, Rango]:
    """Lanzados por familia y total a partir de la frase del ataque."""
    total = 0
    hasta = 0
    exactos: dict[Familia, int] = {}
    combinados: list[tuple[int, set[Familia]]] = []
    # Con viñetas la cabecera repite el total ("559 засобів – 40 ракет та 519 БпЛА:").
    cabecera, _, vinetas = frase.partition(";")
    if _cifras(vinetas) and _cifras(cabecera):
        frase = vinetas
    cifras = _cifras(frase)
    for i, m in enumerate(cifras):
        if _SIN_MAXIMO.search(frase[: m.start()]):
            raise ParteIlegible("cifra de lanzados sin máximo")
        n = valor(m)
        # "до 20 ударних дронів": como mucho 20.
        solo_maximo = re.search(r"\bдо\s*$", frase[: m.start()], re.IGNORECASE) is not None
        limite = cifras[i + 1].start() if i + 1 < len(cifras) else len(frase)
        tipos = _FIN_TIPOS.split(frase[m.end() : limite], maxsplit=1)[0]
        # Una subcuenta ("понад 100 із них – реактивні") dice que ese modelo está, no que
        # sea el único: sin otros tipos nombrados, la cifra puede ser de cualquiera.
        nombrados = familias_en(m[0] + " " + _DE_ELLOS.sub(" ", tipos))
        de_subcuentas = {f for s in _DE_ELLOS.finditer(tipos) for f in familias_en(s[3])}
        familias = nombrados | de_subcuentas if nombrados else set(Familia)
        if solo_maximo:
            hasta += n
            combinados.append((n, familias))
            continue
        total += n
        if len(familias) == 1:
            (familia,) = familias
            exactos[familia] = exactos.get(familia, 0) + n
        else:
            combinados.append((n, familias))
    if not total and not hasta:
        return {}
    minimos: dict[Familia, int] = {}
    for m in _DE_ELLOS.finditer(frase):
        for familia in familias_en(m[3]):
            minimos[familia] = minimos.get(familia, 0) + numero(m[2])
    resultado: dict[str, Rango] = {"total": {"min": total, "max": total + hasta}}
    for familia in Familia:
        minimo = exactos.get(familia, 0)
        maximo = minimo + sum(n for n, fs in combinados if familia in fs)
        resultado[familia.value] = {"min": max(minimo, min(minimos.get(familia, 0), maximo)),
                                    "max": maximo}  # fmt: skip
    return resultado


_LIMPIAR_ZONA = (
    (re.compile(r"\b(?:ТОТ|АР|н\.п\.|тимчасово\s+окупован\w+)(?=\s|$)\.?", re.I), " "),
    (re.compile(r"[()«»\"“”]"), " "),
    (re.compile(r"\s*[-–—]\s*(?:рф|РФ|Крим\w*)\.?\s*$|^\s*(?:рф|РФ|Крим\w*)\s*[-–—]\s*"), ""),
    (re.compile(r"\s+(?:рф|РФ)\.?$"), ""),
    (re.compile(r"(?<=\w)-\s+(?=\w)"), "-"),
    (re.compile(r"\s+"), " "),
)


def zonas(frase: str) -> tuple[str, ...]:
    """Zonas de lanzamiento declaradas tras "з напрямків" / "з району"."""
    primera = CIFRA_DRONES.search(frase)
    cola = frase[primera.start() :] if primera else frase
    m = re.search(
        r"(?:із|з)\s+(?:[\w-]+\s+){0,2}?(?:напрямк\w*|район\w*)\s*:?\s*(.+)", cola, re.IGNORECASE
    )
    if m is None and primera is not None:
        # "Із району Приморсько-Ахтарськ ... зафіксовано пуски 9 ударних БпЛА".
        m = re.search(
            r"(?:із|з)\s+(?:напрямк\w*|район\w*)\s*:?\s*(.+?)\s+(?:зафіксовано|здійснено|випущено)",
            frase[: primera.start()],
            re.IGNORECASE,
        )
    if m is None:
        return ()
    # "з південно-східного напрямку (Приморсько-Ахтарськ – рф.)": las zonas van entre paréntesis.
    if entre := re.match(r"\s*\(([^)]*)\)", m[1]):
        return _lista_de_zonas(entre[1])
    return _lista_de_zonas(m[1])


def _lista_de_zonas(texto: str) -> tuple[str, ...]:
    fin = (
        r"[,.(\s]\s*\(?\s*(?:близько|понад|майже|до|з них|із них|а\s+також)\b"
        r"|\.\s*$|\.\s+(?=[^\W\d_a-zа-яіїєґ])|;\s*(?=\d)"
    )
    lista = re.split(fin, texto)[0]
    resultado: list[str] = []
    for elemento in re.split(r"\s*(?:,|;|\s+та\s+|\s+і\s+|\s+й\s+)\s*", lista):
        # La lista acaba donde el parte pasa a otra arma: "..., протикорабельною ракетою".
        if re.search(r"ракет|боєприпас|пуск", elemento, re.IGNORECASE):
            break
        # "Приморсько-Ахтарськ (Краснодарський край)": la aclaración sobra.
        elemento = re.sub(r"\([^)]*\)", " ", elemento)
        for patron, sustituto in _LIMPIAR_ZONA:
            elemento = patron.sub(sustituto, elemento)
        elemento = re.sub(r"^(?:та|і|й)\s+", "", elemento.strip(" .-–—"))
        # Una zona es un lugar con nombre propio, no el dron ni la zona de un mando.
        if not re.search(r"(?:^|\s)[^\W\d_a-zа-яіїєґ]", elemento) or re.search(
            _DRON + r"|командуванн|відповідальн", elemento, re.IGNORECASE
        ):
            continue
        if elemento.lower() != "рф" and elemento not in resultado:
            resultado.append(elemento)
    return tuple(resultado)


def _suma_drones(frase: str, total_lanzados: int | None) -> int | None:
    """Cifra de drones de una frase de derribos: "58 з 59", suma de cifras o "усі N"."""
    for m in _DE_TOTAL.finditer(frase):
        cola = frase[m.end() :]
        if re.match(_ENTRE + r"\s+[«\"“]?" + _DRON, cola, re.I) or (
            total_lanzados is not None and numero(m[2]) == total_lanzados
        ):
            return numero(m[1])
    # Con viñetas la cabecera repite el total ("541 ціль – ... 515 безпілотників"):
    # si las viñetas traen cifras de drones, manda su suma.
    cabecera, _, vinetas = frase.partition(";")
    cifras = _cuentas(vinetas) or _cuentas(cabecera)
    if cifras:
        return sum(cifras)
    todos = re.search(
        r"(?:всі|усі)\s+" + _NUM + r"(" + _ENTRE + r"\s+[«\"“]?" + _DRON + ")?", frase, re.I
    )
    if todos and todos[2]:
        return numero(todos[1])
    # "Усі 14 повітряних цілей" puede incluir misiles, y "100% дронів" no da cifra:
    # en los dos casos son todos los drones lanzados.
    if (todos or re.search(r"100\s*%", frase)) and total_lanzados is not None:
        return total_lanzados
    # "Усі цілі було збито", "усі ворожі БпЛА знищено": todos los lanzados.
    todas = r"(?:всі|усі)\s+(?:[\w'-]+\s+){0,2}?(?:цілі|" + _DRON + ")"
    if total_lanzados is not None and re.search(todas, frase, re.I):
        return total_lanzados
    return None


def _cuentas(frase: str) -> list[int]:
    """Cifras de drones que cuentan algo: "із 140 БпЛА ... збито 120" solo cuenta 120."""
    return [valor(m) for m in _cifras(frase) if not re.search(r"(?:з|із)\s+$", frase[: m.start()])]


def _cifra_suelta(frase: str) -> int | None:
    m = re.search(_NUM, frase)
    return numero(m[1]) if m else None


# "атакував", "застосував", "завдав удару" (también con la errata "задав"), "(в)дарив".
_ES_ATAQUE = re.compile(
    r"(?:атакува|застосува|застосован|випусти|випущен|запусти)\w*|здійсн\w*\s+пуск|за(?:в)?да\w*\s+удар|\b(?:в|у)?дари(?:в|ла|ли)\b",
    re.IGNORECASE,
)
_ES_DERRIBO = re.compile(r"збит|збил|знищ|подавл|збиття|знешкодж", re.I)
_ES_PERDIDO = re.compile(r"локаційно|втрачен\w*[^;]*РЕБ|РЕБ[^;]*втрачен", re.I)
_ES_MISIL = re.compile(r"ракет", re.IGNORECASE)
_ES_CRUCE = re.compile(
    r"перетну\w*|залет\w*|(?:у|в)\s+повітряний\s+простір|на\s+територію|(?:в|у)\s+бік", re.I
)
_LOCALIZACIONES = r"[^.;]*?\s+на\s+" + _NUM + r"\s+локаці"
_CONTINUACION = re.compile(r"(?:а\s+)?також\s|крім\s+того", re.IGNORECASE)
_RECUENTO = re.compile(r"зафіксовано|виявлено|супровід|усього|загалом", re.IGNORECASE)
_EFECTOS = re.compile(r"влучан|падін|уламк", re.IGNORECASE)


def _del_titular(titular: str | None, lanz: dict[str, Rango]) -> int | None:
    """Derribos del titular, leído al final: "100% ДРОНІВ" necesita el total lanzado."""
    total = lanz.get("total")
    return (
        _suma_drones(titular, total["max"] if isinstance(total, dict) else None)
        if titular
        else None
    )


def _es_titular(frase: str) -> bool:
    """Titular en mayúsculas: "⚡️ ЗБИТО 17 «ШАХЕДІВ» ТА 8 РОЗВІДУВАЛЬНИХ БПЛА"."""
    letras = [c for c in frase if c.isalpha()]
    return bool(letras) and sum(c.isupper() for c in letras) >= PROPORCION_TITULAR * len(letras)


def _continua(frase: str) -> bool:
    """ "А також N БпЛА ..." sigue la frase de lanzamiento, salvo que hable de derribos."""
    return bool(_CONTINUACION.match(frase) and _cifras(frase)) and not _ES_DERRIBO.search(frase)


def _es_lanzamiento(frase: str, siguientes: list[str]) -> bool:
    """Frase de lo lanzado: verbo de ataque, o "зафіксовано N засобів" que no son impactos.

    Las cifras pueden estar en las frases que la continúan ("А також ...").
    """
    lanzamiento = _ES_ATAQUE.search(frase) or (
        _RECUENTO.search(frase) and not _EFECTOS.search(frase) and not _ES_DERRIBO.search(frase)
    )
    completa = " ".join([frase, *itertools.takewhile(_continua, siguientes)])
    cifras = _cifras(completa)
    # "знищено шість «Shahed», якими ... атакували": la cifra es de derribos.
    derribo = _ES_DERRIBO.search(completa)
    if cifras and derribo and derribo.start() < cifras[0].start():
        return False
    return bool(lanzamiento and cifras)


# Los mandos aéreos regionales publican balances parciales de su zona: no son el
# parte nacional y, fundidos con él por periodo, pisarían sus cifras.
# Solo la firma en nominativo ("Повітряне командування "Захід""): los partes nacionales
# de 2022 citan al mando que derribó ("повітряного командування") y sí cuentan.
_REGIONAL = re.compile(r"Повітряне\s+командування")


def es_parte(texto: str) -> bool:
    """Resumen de un ataque (no una alerta ni un pie de vídeo) que menciona drones.

    El verbo de ataque tiene que ir en la frase que declara el periodo o en una
    frase con una cifra de drones. Los balances de un mando regional no cuentan.
    """
    if not re.search(_DRON, texto, re.IGNORECASE) or _REGIONAL.search(texto):
        return False
    lista = frases(texto)
    # 2024: "У ніч на 17 вересня ... виявлено та здійснено супровід 51 ударного БпЛА".
    periodo_con_verbo = any(
        declara_periodo(f)
        and (_ES_ATAQUE.search(f) or (_RECUENTO.search(f) and not _EFECTOS.search(f)))
        for f in lista
    )
    verbo_con_cifra = any(_ES_ATAQUE.search(f) and _cifras(f) for f in lista)
    hay_periodo = declara_periodo(texto)
    return periodo_con_verbo or (hay_periodo and verbo_con_cifra)


def _tramo(frase: str, desde: str, hasta: str | None) -> str:
    inicio = re.search(desde, frase, re.I)
    if inicio is None:
        return ""
    cola = frase[inicio.start() :]
    fin = re.search(hasta, cola, re.I) if hasta else None
    return cola[: fin.start()] if fin else cola


def _perdidos(frase: str) -> tuple[int | None, str]:
    """Drones perdidos por guerra electrónica y la frase sin esas cláusulas.

    Pueden ir en la misma frase que los derribos ("213 — збито ..., 172 — локаційно
    втрачені"), así que se separan por cláusula. Con viñetas mandan las viñetas y se
    saltan las de misiles; la cabecera repite el total de todas las armas.
    """
    trozos = frase.split(";")
    limpios: list[str] = []
    por_trozo: list[list[str]] = []
    for trozo in trozos:
        clausulas = trozo.split(",")
        propias = [c for c in clausulas if _ES_PERDIDO.search(c)]
        por_trozo.append(propias)
        limpios.append(",".join(c for c in clausulas if c not in propias))
    candidatos = list(zip(trozos, por_trozo, strict=True))
    if any(propias for _, propias in candidatos[1:]):
        candidatos = candidatos[1:]
    total: int | None = None
    for trozo, propias in candidatos:
        if _ES_MISIL.search(trozo) and not re.search(_DRON, trozo, re.IGNORECASE):
            continue
        for clausula in propias:
            if re.search(r"(?:понад|більше|щонайменше)\s+\d", clausula, re.IGNORECASE):
                continue
            n = _suma_drones(clausula, None) or _cifra_suelta(clausula)
            if n is not None:
                total = (total or 0) + n
    return total, ";".join(limpios)


def _lanzados_de_referencia(texto: str) -> dict[str, Rango]:
    """Sin frase de lanzamiento, "збито 18 із 20 ударних дронів" da los 20 lanzados."""
    for frase in frases(texto):
        if not _ES_DERRIBO.search(frase):
            continue
        for m in _DE_TOTAL.finditer(frase):
            cola = frase[m.start(2) :]
            if CIFRA_DRONES.match(cola):
                return lanzados(cola)
    return {}


def leer(texto: str, publicado: datetime) -> ParteLeido:
    """Extrae los datos de drones de un parte. Lanza ParteIlegible si no lo entiende."""
    voc = vocabulario()
    inicio, fin = periodo(texto, publicado)
    lanz: dict[str, Rango] = {}
    zonas_l: tuple[str, ...] = ()
    derribados: int | None = None
    titular: str | None = None
    perdidos: int | None = None
    loc_impacto: int | None = None
    loc_restos: int | None = None
    lugares_i: list[str] = []
    lugares_r: list[str] = []
    cruces: dict[str, Rango] = {}
    para_regiones: list[str] = []
    lista = frases(texto)
    while lista:
        frase = lista.pop(0)
        if not lanz and _es_lanzamiento(frase, lista):
            # "... ракетами. А також 168 ударними БпЛА ...": sigue en la frase siguiente.
            while lista and _continua(lista[0]):
                frase += " " + lista.pop(0)
            lanz = lanzados(frase)
            zonas_l = zonas(frase)
            # Las zonas de lanzamiento no son regiones afectadas.
            para_regiones.append(re.split(r"(?:із|з)\s+(?:напрямк|район)", frase, flags=re.I)[0])
            continue
        # Las frases de los puntos de lanzamiento ("Пуски ... з трьох напрямків: Чауда –
        # Крим") no hablan de regiones afectadas.
        if not re.search(r"пуск", frase, re.IGNORECASE):
            para_regiones.append(frase)
        total = lanz.get("total")
        total_n = total["max"] if isinstance(total, dict) else None
        perdidos_frase, resto = _perdidos(frase)
        # El titular y el cuerpo repiten la cifra: vale la primera frase que la da.
        if perdidos is None:
            perdidos = perdidos_frase
        # El titular a veces suma drones de reconocimiento: solo vale si el cuerpo calla.
        if _ES_DERRIBO.search(resto):
            if _es_titular(frase):
                titular = titular if titular is not None else resto
            elif derribados is None:
                derribados = _suma_drones(resto, total_n)
        if m := re.search(r"влучан" + _LOCALIZACIONES, frase, re.I):
            loc_impacto = numero(m[1])
        if m := re.search(r"(?:падін|уламк)" + _LOCALIZACIONES, frase, re.I):
            loc_restos = numero(m[1])
        lugares_i += regiones_en(_tramo(frase, "влучан", "падін"), voc)
        lugares_r += regiones_en(_tramo(frase, "падін|уламк", None), voc)
        pais = pais_en(frase, voc) if _ES_CRUCE.search(frase) else None
        if pais is not None and re.search(_DRON, frase, re.IGNORECASE):
            n = _suma_drones(frase, None)
            cruces[pais] = exacto(n) if n is not None else DESCONOCIDO
    if not lanz:
        lanz = _lanzados_de_referencia(texto)
    if not zonas_l:
        # Con las cifras en viñetas, las zonas van en la frase del ataque.
        candidatas = [f for f in frases(texto) if _ES_ATAQUE.search(f) and not _ES_MISIL.search(f)]
        zonas_l = next((z for f in candidatas if (z := zonas(f))), ())
    if not lanz and derribados is None:
        raise ParteIlegible("sin cifras de drones")

    def rango(n: int | None) -> Rango:
        return exacto(n) if n is not None else DESCONOCIDO

    return ParteLeido(
        inicio=inicio,
        fin=fin,
        lanzados=lanz or dict.fromkeys(["total", *Familia], DESCONOCIDO),
        zonas_lanzamiento=zonas_l,
        derribados=rango(derribados if derribados is not None else _del_titular(titular, lanz)),
        perdidos_guerra_electronica=rango(perdidos),
        localizaciones_impacto=rango(loc_impacto),
        localizaciones_restos=rango(loc_restos),
        lugares_impacto=tuple(dict.fromkeys(voc.nombres[c] for c in lugares_i)),
        lugares_restos=tuple(dict.fromkeys(voc.nombres[c] for c in lugares_r)),
        regiones=tuple(regiones_en("\n".join(para_regiones), voc)),
        cruces=tuple(sorted(cruces.items())),
        frase=frase_origen(texto),
    )
