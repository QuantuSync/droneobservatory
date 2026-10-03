"""Catálogo vivo: lo que el barrido periódico lee de las fuentes y cómo entra en el catálogo.

El barrido (recogida/catalogo_vivo.py) lee War&Sanctions de la inteligencia militar ucraniana,
los fabricantes, las listas oficiales, las autoridades que identifican restos, los centros de
análisis, la prensa técnica y los datos propios. Aquí está lo que no depende de la red:

- **Lectores por código** de lo estructurado: la ficha de War&Sanctions («Declared
  characteristics») y las tablas de especificaciones de los fabricantes (etiqueta y valor con
  su unidad). Cada cifra lleva la frase literal de la fuente (etiqueta y valor) y se comprueba
  que el número está en ella.
- **Hallazgos**: modelo nuevo, cifra nueva de un modelo conocido, táctica (alturas de vuelo,
  rutas, señuelos, enjambres, nodrizas, control por fibra óptica, vuelo a ras de suelo) y
  aparición de un modelo en los datos propios.
- **Regla de entrada**: lo que viene de un fabricante, de inteligencia, de una lista oficial,
  de una autoridad o de un centro de análisis entra directo; lo que viene solo de prensa queda
  como candidato hasta que lo diga una segunda fuente de otro sitio. Nada se borra: un cambio es
  una cifra más (la envolvente de la clase solo se ensancha, nunca descarta más por un dato
  nuevo) y cada versión del catálogo vivo queda en su historial.
- **Clase de un modelo nuevo**: por el propósito que da War&Sanctions y sus cifras (FPV de
  ataque, señuelo, munición merodeadora, dron de ataque de largo alcance de pistón o a reacción);
  si no se puede decidir por código, el modelo queda registrado sin clase y no entra en las
  envolventes.
"""

import functools
import hashlib
import html
import itertools
import re
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlsplit

Documento = dict[str, Any]

DIRECTAS = frozenset({
    "fabricante", "inteligencia", "lista_oficial", "autoridad", "analisis_tecnico",
})  # fmt: skip
CANDIDATAS = frozenset({"prensa_tecnica", "prensa"})
PROPIOS = "propios"
MODELO_NUEVO, CIFRA_NUEVA, TACTICA, APARICION = (
    "modelo_nuevo",
    "cifra_nueva",
    "tactica",
    "aparicion",
)
ADMITIDA, CANDIDATA = "admitida", "candidata"

# --- War&Sanctions -----------------------------------------------------------------------

# Etiqueta de la ficha → campo del catálogo.
ETIQUETAS_WS: tuple[tuple[str, str], ...] = (
    (r"take-?off weight", "mtow"),
    (r"(?:target )?load weight|payload|warhead", "carga_util"),
    (r"flight time|flight duration|endurance", "autonomia"),
    (r"maximum speed|max\.? speed|top speed", "velocidad_maxima"),
    (r"cruising speed|cruise speed", "velocidad_crucero"),
    (r"combat radius|flight range|range of flight|operating range|^range", "alcance"),
    (r"communication (?:distance|range)|control range|range of control", "enlace_alcance"),
    (r"maximum flight altitude|flight altitude|ceiling|service ceiling", "techo"),
    (r"wingspan", "envergadura"),
    (r"length", "longitud"),
    (r"wind", "viento_maximo"),
)
UNIDADES_WS = {
    "kg": "kg", "g": "g", "km/h": "km/h", "km": "km", "m": "m", "min": "min", "h": "h",
    "hours": "h", "hour": "h", "minutes": "min", "minutos": "min", "m/s": "m/s", "mm": "mm",
    "cm": "cm", "°": "°",
}  # fmt: skip
# Propósito de War&Sanctions → clase del catálogo (o None: no se decide por código).
FPV, SENUELO, MERODEADORA = "fpv", "senuelo_largo_alcance", "municion_merodeadora"
PISTON, REACCION = "ataque_largo_alcance_piston", "ataque_reaccion"
LARGO_ALCANCE_KM = 300.0
VELOCIDAD_REACCION_KMH = 300.0


@dataclass
class Ficha:
    """Lo que dice una ficha: nombre, propósito, cifras (campo → entradas con frase) y texto."""

    url: str
    nombre: str
    proposito: str | None = None
    fecha: str | None = None
    cifras: dict[str, list[Documento]] = field(default_factory=dict)
    texto: str = ""


def _texto(html_: str) -> str:
    sin = re.sub(r"<(script|style)\b.*?</\1>", " ", html_, flags=re.S | re.I)
    plano = html.unescape(re.sub(r"<[^>]+>", "|", sin))
    return re.sub(r"\s*\|[\s|]*", " | ", plano).strip(" |")


_NUMERO = r"(\d+(?:[  ]\d{3})*(?:[.,]\d+)?)"


def _numero(texto: str) -> float:
    return float(texto.replace(" ", "").replace(" ", "").replace(",", "."))


def cifras_de_valor(etiqueta: str, valor: str, unidades: dict[str, str]) -> list[Documento]:
    """Las entradas del catálogo de un valor de ficha («100–140 km/h», «up to 20 km», «5 000 m»,
    «35°», «46 minutos»): valor o intervalo, en la unidad de la fuente, con la frase «etiqueta
    valor» (el texto de la fuente, sin más)."""
    texto = " ".join(valor.replace("\u00a0", " ").split())
    cita = f"{etiqueta.strip()} {texto}"
    unidad_re = r"([a-zA-Z/°]+)"
    m = re.search(rf"{_NUMERO}\s*(?:[-–—]|to|до)\s*{_NUMERO}\s*{unidad_re}", texto) or re.search(
        rf"{_NUMERO}\s*{unidad_re}", texto
    )
    if not m:
        return []
    unidad = unidades.get(m.group(m.lastindex or 0).lower())
    if unidad is None:
        return []
    if m.lastindex == 3:
        a, b = _numero(m.group(1)), _numero(m.group(2))
        if a > b:
            return []
        return [{"min": a, "max": b, "unidad": unidad, "cita": cita}]
    return [{"valor": _numero(m.group(1)), "unidad": unidad, "cita": cita}]


def ficha_war_sanctions(url: str, pagina: str) -> Ficha | None:
    """La ficha de un dron de War&Sanctions: nombre (h1), propósito (la línea bajo el nombre),
    fecha de actualización y las «Declared characteristics» (etiqueta | valor)."""
    nombre = re.search(r"<h1[^>]*>(.*?)</h1>", pagina, re.S)
    if not nombre:
        return None
    ficha = Ficha(url, " ".join(html.unescape(re.sub(r"<[^>]+>", "", nombre.group(1))).split()))
    plano = _texto(pagina)
    ficha.texto = plano
    cabecera = re.search(
        rf"\| {re.escape(ficha.nombre)} \| ([^|]+?) \| (?:Total number|Declared|Updated)",
        f"| {plano}",
    )
    if cabecera:
        ficha.proposito = cabecera.group(1).strip()
    actualizada = re.search(r"Updated:\s*(\d{2})\.(\d{2})\.(\d{4})", plano)
    if actualizada:
        d, mth, a = actualizada.groups()
        ficha.fecha = f"{a}-{mth}-{d}"
    bloque = re.search(
        r"Declared characteristics \|(.*?)(?:\| Provide additional|\| Related)", plano
    )
    if bloque:
        partes = [p.strip() for p in bloque.group(1).split("|") if p.strip()]
        for etiqueta, valor in zip(partes[0::2], partes[1::2], strict=False):
            for patron, campo in ETIQUETAS_WS:
                if re.search(patron, etiqueta, re.I):
                    for cifra in cifras_de_valor(etiqueta, valor, UNIDADES_WS):
                        ficha.cifras.setdefault(campo, []).append(cifra)
                    break
    return ficha


def lista_war_sanctions(pagina: str) -> list[tuple[str, str, str]]:
    """(url, nombre, propósito) de una página de la lista de War&Sanctions."""
    resultado = []
    for m in re.finditer(r'href="(https://war-sanctions\.gur\.gov\.ua/en/uav/\d+)"', pagina):
        trozo = _texto(pagina[m.start() : m.start() + 1500])
        g = re.search(r"Name \| ([^|]+?) \| Purpose \| ([^|]+?) \|", trozo + " |")
        if g:
            resultado.append((m.group(1), g.group(1).strip(), g.group(2).strip()))
    return list(dict.fromkeys(resultado))


def _mayor(entrada: Documento) -> float:
    """El extremo mayor de una entrada (o su valor)."""
    valor = entrada.get("max", entrada.get("valor"))
    return float(valor) if valor is not None else 0.0


def _kmh(entradas: list[Documento]) -> float | None:
    from proceso.deduccion.catalogo import convertir

    valores = [
        convertir(_mayor(e), e["unidad"], "m/s") * 3.6
        for e in entradas
        if e.get("unidad") in {"km/h", "m/s", "kn", "mph"}
    ]
    return max(valores) if valores else None


def _km(entradas: list[Documento]) -> float | None:
    from proceso.deduccion.catalogo import convertir

    valores = [
        convertir(_mayor(e), e["unidad"], "km")
        for e in entradas
        if e.get("unidad") in {"km", "m", "mi"}
    ]
    return max(valores) if valores else None


def clase_por_proposito(ficha: Ficha) -> tuple[str | None, str]:
    """La clase de un modelo nuevo de War&Sanctions y el porqué, o None si no se decide."""
    proposito = (ficha.proposito or "").lower()
    texto = ficha.texto.lower()
    alcance = _km(ficha.cifras.get("alcance", []))
    velocidad = _kmh(ficha.cifras.get("velocidad_maxima", []))
    if "fpv" in proposito:
        return FPV, "propósito «FPV kamikaze»"
    if "false target" in proposito or "decoy" in proposito:
        return SENUELO, "propósito «False target» (señuelo)"
    if proposito in {"barrage", "strike"}:
        if alcance is not None and alcance >= LARGO_ALCANCE_KM:
            if velocidad is not None and velocidad >= VELOCIDAD_REACCION_KMH:
                motivo = (
                    f"propósito «{ficha.proposito}», alcance {alcance:.0f} km y velocidad "
                    f"{velocidad:.0f} km/h"
                )
                return REACCION, motivo
            if "jet" in texto or "turbojet" in texto:
                return (
                    REACCION,
                    f"propósito «{ficha.proposito}», alcance {alcance:.0f} km y motor a reacción",
                )
            return PISTON, f"propósito «{ficha.proposito}» y alcance {alcance:.0f} km"
        if proposito == "barrage" and alcance is not None:
            return (
                MERODEADORA,
                f"propósito «Barrage» (munición merodeadora), alcance {alcance:.0f} km",
            )
    return (
        None,
        f"propósito «{ficha.proposito or 'sin propósito'}»: la clase no se decide por código",
    )


def fibra(ficha: Ficha) -> bool:
    return bool(re.search(r"fib(?:er|re)[- ]optic|оптоволок|світловод", ficha.texto, re.I))


# --- Fichas de los fabricantes ---------------------------------------------------------

# Etiquetas de las tablas de especificaciones (inglés y español: las de DJI se sirven en la
# edición del país del visitante).
ETIQUETAS_FICHA: tuple[tuple[str, str], ...] = (
    (r"max(?:imum)?\.? ascent speed|velocidad m[aá]x(?:ima)?\.? de ascenso", "velocidad_ascenso"),
    (
        r"max(?:imum)?\.? descent speed|velocidad m[aá]x(?:ima)?\.? de descenso",
        "velocidad_descenso",
    ),
    (
        r"max(?:imum)?\.? (?:horizontal )?(?:flight )?speed|velocidad (?:horizontal )?m[aá]x",
        "velocidad_maxima",
    ),
    (r"max(?:imum)?\.? (?:flight )?time|tiempo m[aá]x(?:imo)?\.? de vuelo", "autonomia"),
    (
        r"max(?:imum)?\.? wind (?:speed )?resistance|resistencia m[aá]x(?:ima)?\.? al viento",
        "viento_maximo",
    ),
    (r"take-?off weight|peso de despegue", "mtow"),
    (
        r"max(?:imum)?\.? (?:tilt|pitch|attitude) angle"
        r"|[aá]ngulo m[aá]x(?:imo)?\.? de (?:cabeceo|inclinaci[oó]n)",
        "angulo_inclinacion",
    ),
    (r"max(?:imum)?\.? (?:flight )?distance|distancia m[aá]x(?:ima)?\.? de vuelo", "alcance"),
    (r"max(?:imum)?\.? takeoff altitude|altitud m[aá]x(?:ima)?\.? de despegue", "techo"),
)
UNIDADES_FICHA = {**UNIDADES_WS, "mins": "min", "mph": "mph", "ft": "ft"}


def ficha_fabricante(url: str, nombre: str, pagina: str) -> Ficha:
    """Cifras de una tabla de especificaciones: cada fila «etiqueta | valor»."""
    ficha = Ficha(url, nombre)
    plano = _texto(pagina)
    ficha.texto = plano
    partes = [p.strip() for p in plano.split("|") if p.strip()]
    for etiqueta, valor in itertools.pairwise(partes):
        if len(etiqueta) > 80 or not re.search(r"\d", valor):
            continue
        for patron, campo in ETIQUETAS_FICHA:
            if re.search(patron, etiqueta, re.I):
                for cifra in cifras_de_valor(etiqueta, valor, UNIDADES_FICHA)[:1]:
                    ficha.cifras.setdefault(campo, []).append(cifra)
                break
    return ficha


# --- Tácticas ----------------------------------------------------------------------------

TACTICAS: tuple[tuple[str, str], ...] = (
    ("fibra_optica", r"fib(?:er|re)[- ]optic|оптоволок\w*|світловод\w*|fibra [oó]ptica|glasfaser"),
    ("enjambre", r"\bswarm\w*|\bроем\b|\bрій\b|\bрою\b|enjambre|\bschwarm"),
    ("nodriza", r"mother ?ship|carrier (?:drone|of fpv)|дрон[- ]носі\w*"
                r"|носител\w* (?:fpv|дрон)|nodriza|mutterschiff"),
    ("senuelo", r"\bdecoys?\b|false targets?|хибн\w* ціл\w*|ложн\w* цел\w*|приманк\w*"
                r"|señuelo|täuschkörper"),
    ("ras_de_suelo", r"low[- ](?:altitude|level) flight|at (?:extremely |very )?low altitudes?"
                     r"|terrain[- ]following|на (?:гранично |дуже )?малій висоті"
                     r"|на (?:предельно |сверх)?малой высоте|a ras de suelo|im tiefflug"),
    ("altura", r"(?:at|from) (?:an )?altitudes? of (?:up to |about |around )?\d[\d ,.]*\s?"
               r"(?:m|km|meters|metres|ft)\b|на висоті (?:до |близько )?\d[\d ]*\s?(?:м|км)\b"
               r"|на высоте (?:до |около )?\d[\d ]*\s?(?:м|км)\b"),
    ("ruta", r"\b(?:route|routes|flight path|trajectory)\b|маршрут\w*|траєктор\w*|траектори\w*"),
)  # fmt: skip
_TACTICAS = [(t, re.compile(r, re.I)) for t, r in TACTICAS]
_DRONES = re.compile(
    r"dron|drohn|uav|бпла|дрон|shahed|geran|герань|шахед|gerbera|lancet|ланцет", re.I
)
PAISES_NOMBRES: tuple[tuple[str, str], ...] = (
    ("UA", r"ukrain\w*|україн\w*|украин\w*"), ("RU", r"russia\w*|росі\w*|росси\w*"),
    ("BY", r"belarus\w*|білорус\w*|беларус\w*"), ("PL", r"poland|polish|польщ\w*|польш\w*"),
    ("RO", r"romania\w*|румун\w*|румын\w*"), ("MD", r"moldov\w*|молдов\w*"),
    ("LT", r"lithuania\w*|литв\w*"), ("LV", r"latvia\w*|латві\w*|латви\w*"),
    ("EE", r"estonia\w*|естон\w*|эстон\w*"), ("FI", r"finland\w*|фінлянд\w*|финлянд\w*"),
    ("DE", r"german\w*|німеччин\w*|германи\w*"), ("DK", r"denmark|danish|данi\w*|дани\w*"),
)  # fmt: skip


def frases(texto: str) -> list[str]:
    return [
        f.strip() for f in re.split(r"(?<=[.!?])\s+|\s\|\s", texto) if 20 <= len(f.strip()) <= 600
    ]


def tacticas(texto: str) -> list[tuple[str, str, list[str]]]:
    """(tipo, frase, países que nombra) de cada frase que describe una táctica con drones."""
    resultado = []
    for frase in frases(texto):
        if not _DRONES.search(frase):
            continue
        for tipo, expresion in _TACTICAS:
            if expresion.search(frase):
                paises = [p for p, e in PAISES_NOMBRES if re.search(e, frase, re.I)]
                resultado.append((tipo, frase, paises))
    return resultado


# --- Nombres de modelo en un texto ---------------------------------------------------------


def nombres_de(catalogo: Documento) -> dict[str, str]:
    """Cada nombre y alias de los modelos del catálogo (en minúsculas) → id del modelo."""
    nombres: dict[str, str] = {}
    for modelo in catalogo["modelos"]:
        if modelo.get("derivado_de"):
            continue
        for nombre in [modelo["nombre"], *modelo.get("otros_nombres", [])]:
            limpio = nombre.lower().strip()
            if len(limpio) >= 4:
                nombres.setdefault(limpio, modelo["id"])
    return nombres


SUFIJOS_COMERCIALES = re.compile(
    r"\b(?:eu|ce|fly more combo|combo|standard|standard kit|kit|bundle)\b", re.IGNORECASE
)


def modelo_de(nombre: str, nombres: dict[str, str]) -> str | None:
    """El modelo del catálogo con ese nombre (igual, o con el del catálogo entre paréntesis o
    al revés: «Izdeliye-52 (Lancet)» es el «Lancet Izdeliye-52»)."""
    limpio = nombre.lower().strip()
    if limpio in nombres:
        return nombres[limpio]
    partes = {p.strip() for p in re.split(r"[()]", limpio) if len(p.strip()) >= 4}
    for parte in partes:
        if parte in nombres:
            return nombres[parte]
    # Sin las marcas de mercado o de lote que no cambian el modelo («EU», «Fly More Combo»).
    sin_marcas = re.sub(SUFIJOS_COMERCIALES, " ", limpio)
    for candidato in (limpio, sin_marcas):
        clave = re.sub(r"[^a-z0-9]", "", candidato)
        for conocido, id_ in nombres.items():
            if clave and re.sub(r"[^a-z0-9]", "", conocido) == clave:
                return id_
    return None


@functools.lru_cache(maxsize=8)
def _buscador(nombres: tuple[tuple[str, str], ...]) -> re.Pattern[str]:
    alternativas = "|".join(re.escape(n) for n, _ in sorted(nombres, key=lambda x: -len(x[0])))
    return re.compile(rf"(?<![\w-])(?:{alternativas})(?![\w-])")


def menciones(texto: str, nombres: dict[str, str]) -> dict[str, int]:
    """Cuántas veces nombra el texto cada modelo del catálogo (una sola expresión con todos los
    nombres, de más largo a más corto: «Geran-2 serie Э» antes que «Geran-2»)."""
    if not nombres:
        return {}
    cuentas: dict[str, int] = {}
    for encontrado in _buscador(tuple(sorted(nombres.items()))).findall(texto.lower()):
        id_ = nombres[encontrado]
        cuentas[id_] = cuentas.get(id_, 0) + 1
    return cuentas


# --- Hallazgos y regla de entrada --------------------------------------------------------


def huella(*partes: Any) -> str:
    return hashlib.sha256("|".join(str(p) for p in partes).encode("utf-8")).hexdigest()[:16]


def clave_cifra(modelo: str, campo: str, cifra: Documento) -> str:
    valores = (cifra.get("valor"), cifra.get("min"), cifra.get("max"), cifra.get("unidad"))
    return f"cifra|{modelo}|{campo}|{huella(*valores)}"


def clave_modelo(nombre: str) -> str:
    return "modelo|" + re.sub(r"[^a-z0-9]", "", nombre.lower())


def clave_tactica(tipo: str, modelos: list[str], paises: list[str]) -> str:
    return f"tactica|{tipo}|{','.join(sorted(modelos))}|{','.join(sorted(paises))}"


def sitio(url: str) -> str:
    return urlsplit(url).netloc.lower().removeprefix("www.")


def estado_de(tipo_fuente: str) -> str:
    return ADMITIDA if tipo_fuente in DIRECTAS else CANDIDATA


def confirmar_candidatos(novedades: list[Documento]) -> list[Documento]:
    """Las candidatas que ya dice una segunda fuente de otro sitio pasan a admitidas (con las
    dos fuentes). Devuelve las que cambian."""
    por_clave: dict[str, list[Documento]] = {}
    for novedad in novedades:
        por_clave.setdefault(novedad["clave"], []).append(novedad)
    cambiadas = []
    for lista in por_clave.values():
        sitios = {sitio(n["fuente"]["url"]) for n in lista}
        if len(sitios) < 2:
            continue
        for novedad in lista:
            if novedad["estado"] == CANDIDATA:
                novedad["estado"] = ADMITIDA
                novedad["confirmada_por"] = sorted(
                    {n["fuente"]["url"] for n in lista if n is not novedad}
                )
                cambiadas.append(novedad)
    return cambiadas
