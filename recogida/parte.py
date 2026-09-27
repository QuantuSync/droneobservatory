"""Parser por código de los partes de ataque de la Fuerza Aérea de Ucrania.

Solo se registran drones: las cifras de misiles del mismo parte se ignoran.
Un parte que no se entiende lanza ParteIlegible con el motivo; nunca se
publica a medias.
"""

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
}  # fmt: skip
_APOSTROFOS = str.maketrans({"’": "'", "ʼ": "'", "`": "'", "\xa0": " "})

# Número en cifras con sufijo de caso opcional ("23-ма", "30-ю") o en letras.
_NUM = (
    r"(?<![\w:.])(\d+|" + "|".join(sorted(_PALABRAS_NUMERO, key=len, reverse=True)) + r")(?![\w:])"
)
_SUFIJO = r"(?:-?(?:ма|ми|ю|ти|х|м|ох|ьох|ьма|ома|ий|і|ів))?"
_DRON = (
    r"(?:БпЛА|БПЛА|безпілотник\w*|безпілотн\w+\s+літальн\w+\s+апарат\w*|дрон\w*"
    r"|шахед\w*|Shahed\w*|Шахед\w*|Герань\w*|Гербер\w*|Gerbera|Бандерол\w*)"
)
# Hasta cuatro palabras entre la cifra y el dron ("ударними", "ворожих", "S8000"),
# nunca una conjunción, una preposición ni un misil: "3 ракетами та 50 БпЛА" no es 3.
_ENTRE = (
    r"(?:\s+(?!ракет|(?:та|і|й|а|також|з|із|до|по|на|в|у)\b)"
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


def exacto(n: int) -> Documento:
    return {"min": n, "max": n}


_VINETA = re.compile(r"^\s*[-–—•]\s*")


def frases(texto: str) -> list[str]:
    """Frases del parte. Una cabecera terminada en ":" se une con sus viñetas,
    aunque haya líneas en blanco entre ellas.

    Solo se corta tras un punto si sigue una mayúscula: "обл. рф" no corta.
    """
    bloques: list[str] = []
    abierto = False
    for linea in texto.translate(_APOSTROFOS).splitlines():
        if not linea.strip():
            continue
        if abierto and _VINETA.match(linea):
            bloques[-1] += "; " + _VINETA.sub("", linea).strip()
            continue
        bloques.append(linea.strip())
        abierto = linea.rstrip().endswith(":")
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
    r"ніч\w*\s+(?:з\s+\d{1,2}\s+(?:" + _MES[1:-1] + r"\s+)?)?на\s+(\d{1,2})\s+" + _MES + _ANIO,
    re.IGNORECASE,
)
_DIA = re.compile(r"(?:протягом|впродовж|за)\s+(?:доби|дня)\s+(\d{1,2})\s+" + _MES + _ANIO, re.I)
_DESDE = re.compile(r"(?:з|із|від)\s+" + _HORA + r"(?:\s+(\d{1,2})\s+" + _MES + ")?", re.I)
_HASTA = re.compile(r"до\s+" + _HORA + r"(?:\s+(\d{1,2})\s+" + _MES + ")?", re.I)
_STANOM = re.compile(r"станом\s+на\s+" + _HORA + r"(?:\s+(\d{1,2})\s+" + _MES + ")?", re.I)


def _hora(m: re.Match[str], dia: date, publicado: datetime) -> datetime:
    if m[3]:
        dia = _fecha(int(m[3]), MESES[m[4].lower()], dia.year, publicado)
    return _utc(dia, time(int(m[1]), int(m[2])))


def periodo(texto: str, publicado: datetime) -> tuple[Instante, Instante]:
    """Periodo tal como lo declara el parte, en UTC."""
    noche = _NOCHE.search(texto)
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
            inicio = Instante(_hora(desde, base, publicado), "minuto")
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
    ]


def lanzados(frase: str) -> dict[str, Rango]:
    """Lanzados por familia y total a partir de la frase del ataque."""
    total = 0
    exactos: dict[Familia, int] = {}
    combinados: list[tuple[int, set[Familia]]] = []
    cifras = _cifras(frase)
    for i, m in enumerate(cifras):
        n = numero(m[1])
        limite = cifras[i + 1].start() if i + 1 < len(cifras) else len(frase)
        tipos = _FIN_TIPOS.split(frase[m.end() : limite], maxsplit=1)[0]
        familias = familias_en(m[0] + " " + tipos) or set(Familia)
        total += n
        if len(familias) == 1:
            (familia,) = familias
            exactos[familia] = exactos.get(familia, 0) + n
        else:
            combinados.append((n, familias))
    if not total:
        return {}
    minimos: dict[Familia, int] = {}
    for m in _DE_ELLOS.finditer(frase):
        for familia in familias_en(m[3]):
            minimos[familia] = minimos.get(familia, 0) + numero(m[2])
    resultado: dict[str, Rango] = {"total": exacto(total)}
    for familia in Familia:
        minimo = exactos.get(familia, 0)
        maximo = minimo + sum(n for n, fs in combinados if familia in fs)
        resultado[familia.value] = {"min": max(minimo, min(minimos.get(familia, 0), maximo)),
                                    "max": maximo}  # fmt: skip
    return resultado


_LIMPIAR_ZONA = (
    (re.compile(r"\b(?:ТОТ|АР|н\.п\.|тимчасово\s+окупован\w+)(?=\s|$)\.?", re.I), " "),
    (re.compile(r"[()«»\"“”]"), " "),
    (re.compile(r"\s*[-–—]\s*(?:рф|РФ|Крим)\.?\s*$|^\s*(?:рф|РФ|Крим)\s*[-–—]\s*"), ""),
    (re.compile(r"\s+(?:рф|РФ)\.?$"), ""),
    (re.compile(r"\s+"), " "),
)


def zonas(frase: str) -> tuple[str, ...]:
    """Zonas de lanzamiento declaradas tras "з напрямків" / "з району"."""
    primera = CIFRA_DRONES.search(frase)
    cola = frase[primera.start() :] if primera else frase
    m = re.search(r"(?:із|з)\s+(?:напрямк\w*|район\w*)\s*:?\s*(.+)", cola, re.IGNORECASE)
    if m is None:
        return ()
    lista = re.split(r"[,.]\s*(?:близько|понад|з них|із них)\b|\.\s*$|;\s*(?=\d)", m[1])[0]
    resultado: list[str] = []
    for elemento in re.split(r"\s*(?:,|;|\s+та\s+|\s+і\s+|\s+й\s+)\s*", lista):
        for patron, sustituto in _LIMPIAR_ZONA:
            elemento = patron.sub(sustituto, elemento)
        elemento = elemento.strip(" .-–—")
        if elemento and elemento not in resultado:
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
    cifras = [numero(m[1]) for m in _cifras(frase)]
    if cifras:
        return sum(cifras)
    todos = re.search(r"(?:всі|усі)\s+" + _NUM, frase, re.I)
    return numero(todos[1]) if todos else None


def _cifra_suelta(frase: str) -> int | None:
    m = re.search(_NUM, frase)
    return numero(m[1]) if m else None


_ES_ATAQUE = re.compile(r"(?:атакува|застосува|випусти|запусти)\w*", re.I)
_ES_DERRIBO = re.compile(r"збит|знищ|подавл|збиття|знешкодж", re.I)
_ES_PERDIDO = re.compile(r"локаційно|втрачен\w*[^;]*РЕБ|РЕБ[^;]*втрачен", re.I)
_ES_CRUCE = re.compile(
    r"перетну\w*|залет\w*|(?:у|в)\s+повітряний\s+простір|на\s+територію|(?:в|у)\s+бік", re.I
)
_LOCALIZACIONES = r"[^.;]*?\s+на\s+" + _NUM + r"\s+локаці"


def es_parte(texto: str) -> bool:
    """Resumen de un ataque (no una alerta en tiempo real) que menciona drones."""
    return bool(
        (_NOCHE.search(texto) or _DIA.search(texto))
        and _ES_ATAQUE.search(texto)
        and re.search(_DRON, texto, re.IGNORECASE)
    )


def _tramo(frase: str, desde: str, hasta: str | None) -> str:
    inicio = re.search(desde, frase, re.I)
    if inicio is None:
        return ""
    cola = frase[inicio.start() :]
    fin = re.search(hasta, cola, re.I) if hasta else None
    return cola[: fin.start()] if fin else cola


def leer(texto: str, publicado: datetime) -> ParteLeido:
    """Extrae los datos de drones de un parte. Lanza ParteIlegible si no lo entiende."""
    voc = vocabulario()
    inicio, fin = periodo(texto, publicado)
    lanz: dict[str, Rango] = {}
    zonas_l: tuple[str, ...] = ()
    derribados: int | None = None
    perdidos: int | None = None
    loc_impacto: int | None = None
    loc_restos: int | None = None
    lugares_i: list[str] = []
    lugares_r: list[str] = []
    cruces: dict[str, Rango] = {}
    para_regiones: list[str] = []
    for frase in frases(texto):
        if not lanz and _ES_ATAQUE.search(frase) and _cifras(frase):
            lanz = lanzados(frase)
            zonas_l = zonas(frase)
            # Las zonas de lanzamiento no son regiones afectadas.
            para_regiones.append(re.split(r"(?:із|з)\s+(?:напрямк|район)", frase, flags=re.I)[0])
            continue
        para_regiones.append(frase)
        total = lanz.get("total")
        total_n = total["max"] if isinstance(total, dict) else None
        trozos = frase.split(";")
        perdidas = [t for t in trozos if _ES_PERDIDO.search(t)]
        for trozo in perdidas:
            n = _suma_drones(trozo, None) or _cifra_suelta(trozo)
            if n is not None:
                perdidos = (perdidos or 0) + n
        resto = ";".join(t for t in trozos if t not in perdidas)
        if derribados is None and _ES_DERRIBO.search(resto):
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
    if not lanz and derribados is None:
        raise ParteIlegible("sin cifras de drones")

    def rango(n: int | None) -> Rango:
        return exacto(n) if n is not None else DESCONOCIDO

    return ParteLeido(
        inicio=inicio,
        fin=fin,
        lanzados=lanz or dict.fromkeys(["total", *Familia], DESCONOCIDO),
        zonas_lanzamiento=zonas_l,
        derribados=rango(derribados),
        perdidos_guerra_electronica=rango(perdidos),
        localizaciones_impacto=rango(loc_impacto),
        localizaciones_restos=rango(loc_restos),
        lugares_impacto=tuple(dict.fromkeys(voc.nombres[c] for c in lugares_i)),
        lugares_restos=tuple(dict.fromkeys(voc.nombres[c] for c in lugares_r)),
        regiones=tuple(regiones_en("\n".join(para_regiones), voc)),
        cruces=tuple(sorted(cruces.items())),
        frase=frase_origen(texto),
    )
