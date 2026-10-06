"""Rasgos del dron que describen los testigos y las autoridades, leídos por código.

De cada frase literal de las fuentes de un incidente (la de cada noticia, la declaración citada
de una autoridad, los pasajes de los documentos oficiales y las descripciones de la UK Airprox
Board) sale lo que la frase dice expresamente del aparato:

- forma: multirrotor, ala fija o ala delta (y «marítimo» para los drones de superficie, que no
  son aeronaves);
- ruido o propulsión: hélice, motor de combustión («como una motocicleta», «moped») o reacción;
- tamaño: pequeño o grande, y la medida si la da («10ft drone», «envergadura de 2,5 m»);
- luces;
- número de aparatos;
- duración del vuelo observado;
- altura y velocidad, con su unidad;
- hora local que escribe la frase;
- comportamiento: estático, merodeo, tránsito o formación.

Cada rasgo lleva la frase de la que sale, su fuente y el origen de esa fuente. Si la frase no lo
dice, no hay rasgo: no se infiere nada de lo que falta. Las palabras de tamaño, luces y hélice
solo cuentan a tres palabras o menos de una palabra de dron u objeto («small drone», «nogle store
droner»), para que «small airport» o «el segundo aeropuerto más grande» no den rasgos; tampoco
cuentan si empiezan por mayúscula a media frase (un nombre propio: «Kleine-Brogel»). Una negación
justo antes («not a quadcopter») anula el rasgo y una frase que cuenta una confusión («mistook
the lights of an F-15 for a drone») no da ninguno.
"""

import re
import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from proceso import textos_dron

VERSION = "rasgos-1.0.0"

FORMA, RUIDO, TAMANO, LUCES, NUMERO, DURACION, ALTURA, VELOCIDAD, HORA, COMPORTAMIENTO = (
    "forma",
    "ruido",
    "tamano",
    "luces",
    "numero",
    "duracion",
    "altura",
    "velocidad",
    "hora",
    "comportamiento",
)
RASGOS = (FORMA, RUIDO, TAMANO, LUCES, NUMERO, DURACION, ALTURA, VELOCIDAD, HORA, COMPORTAMIENTO)
MARITIMO = "maritimo"

# Palabras de dron u objeto volador (sin acentos, minúsculas): las de textos_dron y las de
# «objeto» de cada idioma.
_OBJETO = (
    textos_dron.PALABRA_DRON
    + r"|object\w*|objekt\w*|obiect\w*|obiekt\w*|objet\w*|oggetto|objeto|объект\w*|об'єкт\w*"
    r"|aircraft|aparat\w*|aeronav\w*|flugobjekt\w*|flygande|letajuc\w*|апарат\w*|uav\w*|"
    r"rpas|bpla|бпла|безпілотн\w*|беспилотн\w*|droni|drony|dronai|drooni\w*|drohn\w*|dron\w*"
)
_CERCA = 3  # palabras entre el rasgo y la palabra de dron u objeto

# Negación justo antes del rasgo.
_NEGACION = re.compile(
    r"(?<!\w)(?:not|no|never|nicht|kein\w*|ikke|inte|niet|geen|nie|nu|pas|не|ні|nera)"
    r"(?:\s+\w+){0,2}\s*$"
)
# Una frase que cuenta una confusión no describe ningún dron.
_CONFUSION = re.compile(
    r"misidentif\w*|mistook|mistaken|confus\w*|verwechsel\w*|confund\w*|pomyli\w*|"
    r"переплут\w*|перепута\w*|forvekslet|forvaxl\w*|vergist"
)
# Frases en las que quien da vueltas o se queda quieto puede ser un avión, no el dron.
_AVION = re.compile(
    r"\bplane\b|airplane|aeroplane|samolot\w*|avion\w*|flugzeug\w*|vliegtuig\w*|"
    r"lentokone\w*|самолет\w*|літак\w*|i spent|airliner|\bfly(?:et|ene)\b|\bfly\b"
)
# Drones de superficie: no son aeronaves y no tienen clase en el catálogo. La palabra va junto
# a la de dron («dronă maritimă», «sea drone»): «base navale» no cuenta.
_MARITIMO = r"maritim\w*|naval\w*|navale|sea|морськ\w*|морск\w*|suprafata|surface"
_MARITIMO_SOLO = re.compile(
    r"magura|seadrone\w*|wasserdrohne\w*|seedrohne\w*|meeresdrohne\w*|unmanned surface|"
    r"\busv\b"
)

# (valor, expresión) de cada rasgo de palabras. Sin acentos y en minúsculas.
_FORMAS: tuple[tuple[str, str], ...] = (
    (
        "multirrotor",
        r"quad-?copter\w*|quadro-?copter\w*|quadrocopt\w*|quadricott\w*|cuadricopter\w*|"
        r"kvadrokopt\w*|kwadrokopt\w*|quadrokopt\w*|multi-?copter\w*|multi-?rotor\w*|"
        r"multicopt\w*|multikopt\w*|hexa-?copter\w*|octo-?copter\w*|квадрокоптер\w*|"
        r"мультикоптер\w*|dji|mavic|matrice",
    ),
    (
        "ala_delta",
        r"delta[- ]?wing\w*|ala delta|deltaflugel\w*|aile delta|aripa delta|triangular|"
        r"triangle-shaped|dreieckig\w*|треугольн\w*|трикутн\w*|trojkatn\w*|triunghiular\w*",
    ),
    (
        "ala_fija",
        r"fixed[- ]?wing\w*|ala fija|alas fijas|ala fissa|aripa fixa|aripi fixe|voilure fixe|"
        r"starrflugel\w*|plane-like|aeroplane-like|airplane-like|aircraft-type|"
        r"model aircraft|model plane|modellflugzeug\w*|modelfly\w*|самолетного типа|"
        r"літакового типу|samolotow\w*|typu samolot\w*|de tip avion|tip avion",
    ),
)
_RUIDOS: tuple[tuple[str, str], ...] = (
    (
        "reaccion",
        r"jet[- ]powered|jet[- ]engine\w*|jet drone\w*|turbojet\w*|turboreactor\w*|"
        r"motor a reaccion|motor de reaccion|de reaccion|a reaccion|reaktivn\w*|"
        r"реактивн\w*|odrzutow\w*|strahltriebwerk\w*|dusenantrieb\w*|cu reactie|"
        r"turboreacteur\w*|propulsion par reaction",
    ),
    (
        "combustion",
        r"moped\w*|lawn ?mower\w*|motorbike\w*|motorcycle\w*|chainsaw\w*|two-stroke|"
        r"мопед\w*|газонокосил\w*|газонокосар\w*|ciclomotor\w*|cortacesped\w*|motosierra\w*|"
        r"rasenmaher\w*|mofa|kettensage\w*|motorower\w*|kosiark\w*|motoreta\w*|"
        r"motocicleta\w*|motociclet\w*|motocykl\w*|zweitakt\w*|drujba",
    ),
)
_HELICE = r"propeller\w*|helice|helices|elice|elicea|smigl\w*|пропелер\w*|пропеллер\w*"
_TAMANOS: tuple[tuple[str, str], ...] = (
    (
        "pequeno",
        r"small|smaller|tiny|mini|pequen\w*|klein|kleine|kleiner|kleinen|kleines|petit\w*|"
        r"piccol\w*|mica|mici|маленьк\w*|небольш\w*|невелик\w*|liten|litet|sma|maly|mala|"
        r"male|nieduz\w*|mazas|maza|kis|hobby",
    ),
    (
        "grande",
        r"large|big|huge|grand|grande|grandes|gross|grosse|grosser|grossen|"
        r"stor|store|stora|groot|grote|великий|великі|великого|большой|больших|duzy|duze|"
        r"duzego|didel\w*|liel\w*|suur\w*|nagy",
    ),
)
_LUCES = (
    r"lights?|lit up|lighted|blinking|flashing|luces|luz|lichter|licht|blinkend\w*|lumini\w*|"
    r"lumina|swiatl\w*|swiatel|огн\w*|огон\w*|вогн\w*|lys|lyser|lysende|ljus|ljusen|valo\w*|"
    r"feux|lumiere\w*|lampeggi\w*"
)
_FORMACION = r"formation|formacion|formatie|formacji|formazione|formatiune|формаци\w*|формуванн\w*"

# Unidades.
_DISTANCIA_M = {
    "m": 1.0, "metre": 1.0, "metres": 1.0, "meter": 1.0, "meters": 1.0, "metern": 1.0,
    "metros": 1.0, "metro": 1.0, "metri": 1.0, "metrow": 1.0, "metru": 1.0, "metrov": 1.0,
    "metrai": 1.0, "м": 1.0, "ft": 0.3048, "feet": 0.3048, "foot": 0.3048, "fot": 0.3048,
    "fuss": 0.3048, "pies": 0.3048,
}  # fmt: skip
_UNIDAD_M = (
    r"(m|metres?|meters?|metern|metros?|metri|metrow|metru|metrov|metrai|метр\w*|м|ft|feet|"
    r"foot|fot|fuss|pies)"
)
_PALABRA_ALTURA = re.compile(
    r"altitude|height|\bhigh\b|above ground|hohe|altura|altitud|altezza|wysokos\w*|"
    r"inaltime\w*|altitudine|высот\w*|висот\w*|hoyde|hojd|korkeu\w*|hoogte|aukst\w*|"
    r"augstum\w*|korgus\w*|\bat\b|flight level"
)
_PALABRA_TAMANO = re.compile(
    r"wingspan|\bspan\b|\bwing|envergadur\w*|spannweite|\blang\b|\blong\b|length|\blargo\b|"
    r"longitud|dlug\w*|lungime|размах\w*|розмах\w*|довжин\w*|длин\w*|diameter|diametro|"
    r"vingespenn|vingspann|(?:ft|foot|feet|m)[- ]drone"
)
_VELOCIDAD = re.compile(
    r"(?<![\w.,])(\d{2,4}(?:[.,]\d+)?)\s*(km/h|kmh|km/godz\w*|km/ora|km/t|km/st|км/ч|км/год|"
    r"mph|knots?|kts?|kn|noduri|m/s|м/с)(?!\w)"
)
_KMH = {
    "km/h": 1.0, "kmh": 1.0, "km/ora": 1.0, "km/t": 1.0, "km/st": 1.0, "км/ч": 1.0,
    "км/год": 1.0, "mph": 1.609344, "knot": 1.852, "knots": 1.852, "kt": 1.852, "kts": 1.852,
    "kn": 1.852, "noduri": 1.852, "m/s": 3.6, "м/с": 3.6,
}  # fmt: skip
_DURACION = re.compile(
    r"(?<![\w.,])(\d{1,3})\s*(?:de\s+)?(minut\w*|min\b|mins\b|минут\w*|хвилин\w*|hours?|"
    r"stunden?|horas?|ore\b|heures?|timer|timmar|godzin\w*|час\w*|годин\w*|valand\w*)"
)
_HORAS = ("hour", "stund", "hora", "ore", "heure", "timer", "timmar", "godzin", "час", "годин",
          "valand")  # fmt: skip
# Lo que va justo antes de la duración del vuelo: «for», «timp de», «durante», o un verbo de
# vuelo («a survolat 18 minute», «a zburat 4 minute»).
_DURACION_CONTEXTO = re.compile(
    r"\bfor\b|\bduring\b|timp de|\blang\b|\bdurante\b|\bper\b|\bprzez\b|протягом|"
    r"в течение|\bpendant\b|\bpo dobu\b|survol\w*|orbit\w*|\bflew\b|hover\w*|zburat\w*|"
    r"\bflog\b|\bfloj\b|kreist\w*|circl\w*|radar\w*"
)
# El cierre de un espacio aéreo o de un aeropuerto tiene su propia duración: esa no es la del
# vuelo del dron.
_CIERRE = re.compile(
    r"clos\w*|shut\w*|suspend\w*|inchis\w*|restrictionat\w*|geschlossen|gesperrt|sperr\w*|"
    r"cerrad\w*|cierr\w*|chius\w*|chiud\w*|ferme\w*|zamkni\w*|stengt|lukket|stang\w*|"
    r"gesloten|uzdar\w*|suletud|закрит\w*|закрыт\w*|delay\w*|retras\w*|verspat\w*|"
    r"intarzi\w*|ground\w*|blocc\w*|bloque\w*|blockier\w*|flights|voli|zboruri|fluge|vols|"
    r"vuelos|loty|lotow|pezullo\w*|\bin \d|\bin mai putin\b|\bin den letzten\b"
)
_PALABRA = re.compile(r"[^\W_]+(?:['’][^\W_]+)*")


def plano(texto: str) -> str:
    """Minúsculas y sin acentos en las letras latinas, letra por letra: las posiciones son las
    del texto original (la mayúscula de un nombre propio se mira en él). Las letras cirílicas
    se quedan como están («й» y «ї» son otras letras, no una con acento)."""
    letras = []
    for caracter in texto:
        minuscula = caracter.lower()
        if len(minuscula) != 1:
            minuscula = caracter
        if ord(minuscula) < 0x250:
            base = unicodedata.normalize("NFKD", minuscula)
            sin = "".join(c for c in base if not unicodedata.combining(c))
            letras.append(sin[0] if sin else minuscula)
        else:
            letras.append(minuscula)
    return "".join(letras)


def _compilar(expresion: str) -> re.Pattern[str]:
    return re.compile(rf"(?<![^\W\d_])(?:{expresion})(?![^\W\d_])")


# Una forma («quadcopter», «fixed-wing») también es una palabra de objeto: «a small quadcopter».
_OBJETO_RE = _compilar(_OBJETO + "|" + "|".join(e for _, e in _FORMAS))
_FORMAS_RE = [(v, _compilar(e)) for v, e in _FORMAS]
_RUIDOS_RE = [(v, _compilar(e)) for v, e in _RUIDOS]
_HELICE_RE = _compilar(_HELICE)
_TAMANOS_RE = [(v, _compilar(e)) for v, e in _TAMANOS]
_LUCES_RE = _compilar(_LUCES)
_FORMACION_RE = _compilar(_FORMACION)
_ENJAMBRE_RE = _compilar(dict(textos_dron.PATRONES)[textos_dron.ENJAMBRE])
_MARITIMO_RE = _compilar(_MARITIMO)
_ALTURA_RE = re.compile(
    rf"(?<![\w.,])(\d{{1,3}}(?:[ .,]\d{{3}})*(?:[.,]\d+)?)\s*(?:de\s+)?{_UNIDAD_M}(?!\w)"
)


@dataclass(frozen=True)
class Frase:
    """Una frase literal de una fuente del incidente."""

    texto: str
    fuente: str
    origen: str
    idioma: str | None = None


def _cerca_de_objeto(texto: str, inicio: int) -> bool:
    """Hay una palabra de dron u objeto a tres palabras o menos del rasgo."""
    palabras = [(m.start(), m.end()) for m in _PALABRA.finditer(texto)]
    posicion = next((i for i, (a, b) in enumerate(palabras) if a <= inicio < b), None)
    if posicion is None:
        return False
    return _palabra_de_objeto_entre(texto, palabras, posicion, _CERCA)


def _palabra_de_objeto_entre(
    texto: str, palabras: list[tuple[int, int]], posicion: int, distancia: int
) -> bool:
    for i in range(max(0, posicion - distancia), min(len(palabras), posicion + distancia + 1)):
        a, b = palabras[i]
        if i != posicion and _OBJETO_RE.fullmatch(texto[a:b]):
            return True
    return False


def _junto_a_dron(texto: str, inicio: int) -> bool:
    """La palabra va pegada a una de dron («dronă maritimă», «sea drone»)."""
    palabras = [(m.start(), m.end()) for m in _PALABRA.finditer(texto)]
    posicion = next((i for i, (a, b) in enumerate(palabras) if a <= inicio < b), None)
    return posicion is not None and _palabra_de_objeto_entre(texto, palabras, posicion, 1)


def _nombre_propio(original: str, inicio: int) -> bool:
    """La palabra empieza por mayúscula y no abre la frase: un nombre propio («Kleine-Brogel»,
    «Grand-Duché»). Las siglas en mayúsculas (DJI) no cuentan como nombre propio."""
    if not original[inicio].isupper():
        return False
    antes = original[:inicio].rstrip(" \"'«„“(")
    return bool(antes) and antes[-1] not in ".!?:|-–—"


def _negado(texto: str, inicio: int) -> bool:
    return _NEGACION.search(texto[max(0, inicio - 30) : inicio]) is not None


def _palabras(
    texto: str, original: str, lista: list[tuple[str, re.Pattern[str]]], cerca: bool
) -> list[str]:
    valores = []
    for valor, expresion in lista:
        for m in expresion.finditer(texto):
            if cerca and (
                not _cerca_de_objeto(texto, m.start()) or _nombre_propio(original, m.start())
            ):
                continue
            if _negado(texto, m.start()):
                continue
            valores.append(valor)
            break
    return valores


def _numero(texto: str) -> float:
    limpio = texto.replace(" ", "")
    # «1.800» o «1,800» con tres cifras detrás son miles; «2,5» o «2.5», decimales.
    if re.fullmatch(r"\d{1,3}([.,]\d{3})+", limpio):
        return float(re.sub(r"[.,]", "", limpio))
    return float(limpio.replace(",", "."))


def _unidad_m(unidad: str) -> float | None:
    if unidad.startswith("метр"):
        return 1.0
    return _DISTANCIA_M.get(unidad)


def _alturas(texto: str) -> list[float]:
    """Alturas en metros: un número con unidad de longitud junto a una palabra de altura («at
    1,800 ft», «la o înălțime de circa 500 m», «in 500 Metern Höhe»)."""
    alturas = []
    for m in _ALTURA_RE.finditer(texto):
        factor = _unidad_m(m[2])
        if factor is None:
            continue
        antes = texto[max(0, m.start() - 30) : m.start()]
        despues = texto[m.end() : m.end() + 15]
        if not (_PALABRA_ALTURA.search(antes) or _PALABRA_ALTURA.search(despues)):
            continue
        if _PALABRA_TAMANO.search(texto[max(0, m.start() - 15) : m.end() + 10]):
            continue
        valor = _numero(m[1]) * factor
        if 1 <= valor <= 15000:
            alturas.append(round(valor, 1))
    return alturas


def _medidas(texto: str) -> list[float]:
    """Tamaño en metros: un número con unidad junto a envergadura, largo o «… ft drone»."""
    medidas = []
    for m in _ALTURA_RE.finditer(texto):
        factor = _unidad_m(m[2])
        if factor is None:
            continue
        if not _PALABRA_TAMANO.search(texto[max(0, m.start() - 25) : m.end() + 10]):
            continue
        valor = _numero(m[1]) * factor
        if 0.05 <= valor <= 40:
            medidas.append(round(valor, 2))
    return medidas


def _velocidades(texto: str) -> list[float]:
    valores = []
    for m in _VELOCIDAD.finditer(texto):
        factor = _KMH.get(m[2])
        if factor is None:
            continue
        valor = _numero(m[1]) * factor
        if 5 <= valor <= 1500:
            valores.append(round(valor, 1))
    return valores


def _duraciones(texto: str) -> list[float]:
    """Minutos de vuelo observado: «a survolat 18 minute», «hovered for 20 minutes». Una frase
    de cierre, de retrasos o de recuento («in 24 hours») no cuenta: es otra duración."""
    if _CIERRE.search(texto) or not _OBJETO_RE.search(texto):
        return []
    valores = []
    for m in _DURACION.finditer(texto):
        if not _DURACION_CONTEXTO.search(texto[max(0, m.start() - 30) : m.start()]):
            continue
        n = float(m[1])
        minutos = n * 60 if m[2].startswith(_HORAS) else n
        if 1 <= minutos <= 24 * 60:
            valores.append(minutos)
    return valores


def de_frase(frase: Frase) -> list[dict[str, Any]]:
    """Los rasgos que dice una frase, cada uno con la frase, su fuente y su origen."""
    texto = plano(frase.texto)
    if _CONFUSION.search(texto):
        return []
    encontrados: list[tuple[str, Any]] = []
    if _MARITIMO_SOLO.search(texto) or any(
        _junto_a_dron(texto, m.start()) for m in _MARITIMO_RE.finditer(texto)
    ):
        encontrados.append((FORMA, MARITIMO))
    for valor in _palabras(texto, frase.texto, _FORMAS_RE, cerca=False):
        encontrados.append((FORMA, valor))
    for valor in _palabras(texto, frase.texto, _RUIDOS_RE, cerca=False):
        encontrados.append((RUIDO, valor))
    if _palabras(texto, frase.texto, [("helice", _HELICE_RE)], cerca=True):
        encontrados.append((RUIDO, "helice"))
    for valor in _palabras(texto, frase.texto, _TAMANOS_RE, cerca=True):
        encontrados.append((TAMANO, valor))
    for medida in _medidas(texto)[:1]:
        encontrados.append((TAMANO, {"metros": medida}))
    if _palabras(texto, frase.texto, [("si", _LUCES_RE)], cerca=True):
        encontrados.append((LUCES, "si"))
    numero = textos_dron.numero_drones(frase.texto, frase.idioma)
    if numero is not None:
        encontrados.append((NUMERO, {"min": numero[0], "max": numero[1]}))
    for minutos in _duraciones(texto)[:1]:
        encontrados.append((DURACION, {"minutos": minutos}))
    for metros in _alturas(texto)[:1]:
        encontrados.append((ALTURA, {"metros": metros}))
    for kmh in _velocidades(texto)[:1]:
        encontrados.append((VELOCIDAD, {"kmh": kmh}))
    hora = textos_dron.hora_local(frase.texto)
    if hora is not None:
        encontrados.append((HORA, {"local": f"{hora[0]:02d}:{hora[1]:02d}"}))
    patron = textos_dron.patron(frase.texto)
    comportamiento = {
        textos_dron.HOVER: "estatico",
        textos_dron.MERODEO: "merodeo",
        textos_dron.TRANSITO: "transito",
        textos_dron.ENJAMBRE: "formacion",
    }.get(patron or "")
    if comportamiento in {"estatico", "merodeo"} and _AVION.search(texto):
        comportamiento = None
    if comportamiento == "formacion" and not _palabras(
        texto, frase.texto, [("formacion", _ENJAMBRE_RE)], cerca=True
    ):
        # «as police swarm»: el enjambre tiene que ser de drones.
        comportamiento = None
    if comportamiento is None and _palabras(
        texto, frase.texto, [("formacion", _FORMACION_RE)], cerca=True
    ):
        comportamiento = "formacion"
    if comportamiento is not None:
        encontrados.append((COMPORTAMIENTO, comportamiento))
    return [
        {
            "rasgo": rasgo,
            "valor": valor,
            "cita": frase.texto,
            "fuente": frase.fuente,
            "origen": frase.origen,
        }
        for rasgo, valor in encontrados
    ]


def de_frases(frases: Iterable[Frase]) -> list[dict[str, Any]]:
    """Los rasgos de todas las frases, sin repetir el mismo rasgo y valor (se queda el de la
    frase de mejor origen, que llega primero)."""
    vistos: set[str] = set()
    rasgos = []
    for frase in frases:
        for rasgo in de_frase(frase):
            clave = f"{rasgo['rasgo']}|{rasgo['valor']!r}"
            if clave in vistos:
                continue
            vistos.add(clave)
            rasgos.append(rasgo)
    return rasgos
