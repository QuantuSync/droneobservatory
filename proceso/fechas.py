"""El día del suceso, leído de la frase que lo dice y no de la fecha de la noticia.

La prensa publica el día del suceso o el siguiente, y el extractor tiene que pasar «anoche»,
«el jueves» o «am Donnerstagabend» a una fecha. Aquí se comprueba con código, con el léxico
de `configuracion/fechas.json`:

- **Explícita**: la frase escribe el día («22 de septiembre», «am 3. Oktober», «22.09.»).
- **Relativa**: la frase da el día respecto a la publicación («ayer», «anoche», «el lunes»).
  Se resuelve con la fecha local del medio cuando publicó la nota (la zona horaria de su
  país; si no se sabe, la del país del suceso): una nota de las 07:10 de Berlín que dice
  «heute Nacht» habla de la noche anterior.
- **Sin día**: la frase no escribe ningún día (solo una hora, o nada). Una fecha sin día
  escrito en su frase no vale como día: el inicio pasa a ser la fecha de publicación, con
  precisión «aproximada», y se declara que lo es.

Si la frase escribe el día y el extractor dio otro, se corrige al de la frase, con su hora
si la tenía. Una fecha en UTC puede caer un día antes que la local (la una de la madrugada
en Europa central es medianoche en UTC) y un suceso de la noche, en la madrugada siguiente:
esos márgenes no son una discrepancia.
"""

import json
import re
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from functools import cache
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


def _normal(texto: str) -> str:
    """Como la frase: sin apóstrofos que partan la palabra («п'ятниця», «aujourd'hui»)."""
    return normalizar(_APOSTROFOS.sub("", texto))


@dataclass(frozen=True)
class Lexico:
    meses: dict[str, int]
    dias: tuple[tuple[str, int], ...]
    relativos: tuple[tuple[str, int], ...]
    noches: tuple[str, ...]
    noche_hacia: tuple[str, ...]
    compone: bool


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
        )
    return resultado


def zona(pais: str | None) -> ZoneInfo | None:
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


def _leer_con(
    frase: str, publicacion: datetime, zona_medio: ZoneInfo, lexico: list[Lexico]
) -> list[Lectura]:
    local = publicacion.astimezone(zona_medio)
    hoy = local.date()
    lecturas: list[Lectura] = []
    for dia, texto in _explicitas(frase, lexico, hoy):
        lecturas.append(Lectura(EXPLICITA, frozenset({dia, dia - timedelta(days=1)}), dia, texto))
    if lecturas:
        return lecturas
    normal = _normal(frase)
    palabras = normal.split()
    for lx in lexico:
        dias = _dia_semana(palabras, normal, lx)
        hacia = any(_contiene(normal, m) >= 0 for m in lx.noche_hacia)
        if dias:
            fechas = [_ultimo(n, hoy) for n, _ in dias]
            primero = min(fechas)
            texto = " ".join(f for _, f in dias)
            if len(dias) == 1 and hacia:
                # «la noche hacia el viernes» empieza el jueves.
                primero -= timedelta(days=1)
            admitidos = {primero, primero + timedelta(days=1), *fechas}
            lecturas.append(Lectura(RELATIVA, frozenset(admitidos), primero, texto))
            continue
        desplazamientos, noches = _relativas(normal, lx)
        for desplazamiento, forma in desplazamientos:
            dia = hoy + timedelta(days=desplazamiento)
            lecturas.append(
                Lectura(RELATIVA, frozenset({dia, dia - timedelta(days=1)}), dia, forma)
            )
        for forma in noches:
            tarde = hoy - timedelta(days=1) if local.hour < HORA_NOCHE_SIGUIENTE else hoy
            # La noche empieza la tarde de `tarde` y puede seguir pasada la medianoche.
            lecturas.append(
                Lectura(RELATIVA, frozenset({tarde, tarde + timedelta(days=1)}), tarde, forma)
            )
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
    return True


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


def _momento(texto: str) -> datetime:
    return datetime.fromisoformat(texto.replace("Z", "+00:00")).astimezone(UTC)


def inicio_de_ficha(
    campos: dict[str, dict[str, Any]],
    enviadas: list[str],
    articulos: list[dict[str, Any]],
    inicio_candidato: str,
    pais_suceso: str | None,
) -> Resolucion:
    """El inicio del incidente que sale de su ficha validada, comprobado con su frase.

    `articulos` son los del candidato (con fecha, país del medio, idioma y titular). Sin
    inicio en la ficha, la fecha es la del primer artículo: la de publicación, aproximada.
    """
    por_url = {a["url"]: a for a in articulos}
    zona_suceso = zona(pais_suceso) or ZoneInfo("UTC")
    inicio = campos.get("inicio")
    fuente = inicio.get("fuente") if inicio else None
    if inicio is None or not isinstance(fuente, int) or not 1 <= fuente <= len(enviadas):
        primero = min(articulos, key=lambda a: a["fecha"]) if articulos else None
        publicacion = _momento(primero["fecha"] if primero else inicio_candidato)
        medio = zona(primero.get("pais")) if primero else None
        local = publicacion.astimezone(medio or zona_suceso).strftime("%Y-%m-%d %H:%M")
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
    return resolver(
        valor, precision or "dia", list(dict.fromkeys(f for f in frases if f)), publicacion,
        zona_medio, zona_suceso, articulo.get("idioma"),
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
