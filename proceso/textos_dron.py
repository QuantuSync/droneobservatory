"""Número de drones y patrón de vuelo que escribe una frase, leídos por código.

Sirve para las frases literales de las fuentes (la de cada noticia, la declaración citada de una
autoridad, los pasajes de los documentos oficiales y las descripciones de la UK Airprox Board):
el origen del valor es el de la frase. Solo se lee lo que la frase dice expresamente:

- número: una cifra o un número escrito junto a la palabra dron («two to three drones», «to
  til tre droner», «bis zu fünf Drohnen», «4 drony»). Un intervalo da [mínimo, máximo]; «hasta
  cinco» da [1, 5]; «varios» sin cifra no da número (no se inventa el máximo).
- patrón: hover (quieto en el aire), merodeo (dando vueltas sobre el sitio), transito (pasa y
  sigue), enjambre (muchos drones juntos), por palabras de cada idioma.
"""

import re
import unicodedata

# La palabra dron, en sus formas de cada idioma, como palabra entera: un compuesto
# («droneangreb», «Drohnensichtung», «dronejammer») no cuenta drones.
SINGULAR = frozenset({
    "drone", "dron", "drona", "dronă", "drohne", "dronen", "drooni", "dronas", "dronu", "uav",
    "uas", "rpas", "дрон", "бпла", "беспилотник", "безпілотник",
})  # fmt: skip
PLURAL = frozenset({
    "drones", "droner", "dronerne", "dronene", "drony", "dronów", "drone", "droni", "drohnen",
    "droonid", "dronai", "dronų", "drönare", "drönarna", "uavs", "дроны", "дронов", "дронів",
    "дрони", "беспилотники", "беспилотников", "безпілотники", "безпілотників",
})  # fmt: skip
PALABRA_DRON = (
    "(?:"
    + "|".join(sorted((re.escape(p) for p in SINGULAR | PLURAL), key=len, reverse=True))
    + r"|unmanned aircraft)(?![\w-])"
)
# Formas que en ese idioma son singulares aunque en otro sean plurales («drone» es plural en
# rumano y singular en inglés): un número mayor que uno con ellas es otra cosa («o nouă dronă»
# es «un dron nuevo», no nueve).
SINGULAR_EN = {
    "ro": {"dronă", "drona", "dronu"}, "en": {"drone", "uav", "uas"}, "de": {"drohne"},
    "da": {"drone", "dronen"}, "no": {"drone", "dronen"}, "nl": {"drone"}, "fr": {"drone"},
    "it": {"drone"}, "es": {"dron"}, "pt": {"drone"}, "pl": {"dron", "drona"},
    "lt": {"dronas"}, "fi": {"drooni"},
}  # fmt: skip
# Palabras entre el número y la palabra dron que hacen que el número no cuente drones («drie
# keer drones», «two drone intrusions» se ve por la palabra siguiente).
NO_ENTRE = frozenset({
    "times", "keer", "mal", "gange", "ganger", "gånger", "fois", "veces", "volte", "razy", "ori",
    "kartus", "reizes", "korda", "kertaa", "krát", "alkalommal", "days", "dage", "dager", "dagar",
    "tage", "dni", "zile", "jours", "días", "giorni", "nights", "nächte", "nætter", "nopți",
    "hours", "stunden", "timer", "ore", "heures", "horas", "weeks", "wochen", "uger",
})  # fmt: skip
DESPUES_NO = re.compile(
    r"\s*(?:intrusion|incident|sighting|attack|activit|alarm|alert|jammer|defen[cs]e|operator|"
    r"pilot|threat|observation|flight|strike|warning|zone|wall|ban|traffic|detection|system|"
    r"incursion|violation|crash|wreck|debris|component|part|launch|unit|production|program|"
    r"factor|maker|manufactur|industr|company|show)",
    re.IGNORECASE,
)
# Negación o condición justo antes: «det ikke var en drone», «als wij een drone denken te zien».
ANTES_NO = re.compile(
    r"(?<!\w)(?:not|no|never|ikke|ikkje|inte|nicht|kein\w*|niet|geen|nie|non|ne|pas|nu|nėra|"
    r"nav|ei|if|als|wenn|falls|hvis|om|si|se|jeśli|jeżeli|dacă|whether|ob)(?!\w)",
    re.IGNORECASE,
)

_LISTAS = {
    "en": "one two three four five six seven eight nine ten eleven twelve",
    "de": "ein zwei drei vier fünf sechs sieben acht neun zehn elf zwölf",
    "da": "en to tre fire fem seks syv otte ni ti elleve tolv",
    "no": "en to tre fire fem seks sju åtte ni ti elleve tolv",
    "sv": "en två tre fyra fem sex sju åtta nio tio elva tolv",
    "nl": "een twee drie vier vijf zes zeven acht negen tien elf twaalf",
    "fr": "un deux trois quatre cinq six sept huit neuf dix onze douze",
    "es": "un dos tres cuatro cinco seis siete ocho nueve diez once doce",
    "it": "un due tre quattro cinque sei sette otto nove dieci undici dodici",
    "pt": "um dois três quatro cinco seis sete oito nove dez onze doze",
    "pl": "jeden dwa trzy cztery pięć sześć siedem osiem dziewięć dziesięć jedenaście dwanaście",
    "ro": "o două trei patru cinci șase șapte opt nouă zece unsprezece doisprezece",
    "lt": "vienas du trys keturi penki šeši septyni aštuoni devyni dešimt",
    "lv": "viens divi trīs četri pieci seši septiņi astoņi deviņi desmit",
    "et": "üks kaks kolm neli viis kuus seitse kaheksa üheksa kümme",
    "fi": "yksi kaksi kolme neljä viisi kuusi seitsemän kahdeksan yhdeksän kymmenen",
    "cs": "jeden dva tři čtyři pět šest sedm osm devět deset",
    "hu": "egy kettő három négy öt hat hét nyolc kilenc tíz",
}
# Formas declinadas o alternativas frecuentes, por idioma.
_OTRAS = {
    "en": {"a": 1, "an": 1, "single": 1, "pair": 2, "couple": 2, "dozen": 12},
    "de": {"eine": 1, "einer": 1, "zwo": 2, "dutzend": 12},
    "da": {"et": 1, "dusin": 12}, "no": {"ett": 1, "et": 1, "dusin": 12},
    "sv": {"ett": 1, "dussin": 12}, "fr": {"une": 1}, "es": {"una": 1, "uno": 1},
    "it": {"una": 1, "uno": 1}, "pt": {"uma": 1, "duas": 2}, "pl": {"dwie": 2, "dwóch": 2,
    "trzech": 3}, "ro": {"un": 1, "doi": 2, "două": 2}, "cs": {"dvě": 2}, "lt": {"dvi": 2},
    "lv": {"divas": 2},
}  # fmt: skip
NUMEROS: dict[str, dict[str, int]] = {
    idioma: {
        **{palabra: n for n, palabra in enumerate(lista.split(), start=1)},
        **_OTRAS.get(idioma, {}),
    }
    for idioma, lista in _LISTAS.items()
}
# Palabras de «uno» que solo cuentan pegadas a la palabra dron («a drone», no «a las 8»).
SOLO_JUNTO = frozenset({"a", "an", "un", "une", "una", "uno", "uma", "en", "et", "ett", "eine",
                        "ein", "einer", "een", "o", "um", "egy", "üks", "yksi", "jeden",
                        "vienas", "viens", "single"})  # fmt: skip

UNION = (
    r"(?:(?:to|til|till|bis|tot|à|a|y|o|or|and|und|og|och|en|et|e|i|do|până la|și|iki|ir|"
    r"līdz|un)(?!\w)|[–/-])"
)
HASTA = (
    r"(?:up to|bis zu|op til|upp till|tot|jusqu'à|hasta|fino a|até|do|până la|iki|līdz|enintään)"
)

_NUM = r"(\d{1,3}|[^\W\d_]+)"


def _plano(texto: str) -> str:
    return unicodedata.normalize("NFC", texto.lower())


def _valor(palabra: str, idioma: str | None) -> int | None:
    if palabra.isdigit():
        return int(palabra)
    return NUMEROS.get(idioma or "", {}).get(palabra)


# Dentro de una búsqueda hacia delante: así se prueban todas las posiciones, también las que
# se solapan («grundet to til tre droner» no se come el «to»).
_INTERVALO = re.compile(
    rf"(?<!\w)(?={_NUM}\s*{UNION}\s*{_NUM}\s+(?:\w+\s+){{0,2}}?{PALABRA_DRON})", re.IGNORECASE
)
_HASTA = re.compile(
    rf"(?<!\w)(?={HASTA}(?!\w)\s+{_NUM}\s+(?:\w+\s+){{0,2}}?{PALABRA_DRON})", re.IGNORECASE
)
_UNO = re.compile(rf"(?<!\w)(?={_NUM}\s+((?:\w+\s+){{0,2}}?){PALABRA_DRON})", re.IGNORECASE)


def _cuenta(texto: str, inicio: int, fin_dron: int, n: int, idioma: str | None) -> bool:
    """Si el número que empieza en `inicio` cuenta los drones de la palabra que acaba en
    `fin_dron`: sin negación ni condición en las tres palabras de antes, sin una palabra después
    que haga de la palabra dron un modificador («drone intrusions») y en plural si es más de uno."""
    previas = " ".join(texto[:inicio].split()[-3:])
    if ANTES_NO.search(previas):
        return False
    if DESPUES_NO.match(texto[fin_dron:]):
        return False
    palabra = re.findall(r"[\w-]+", texto[:fin_dron])[-1]
    return not (n > 1 and palabra in SINGULAR_EN.get(idioma or "", set()))


def numero_drones(frase: str, idioma: str | None = None) -> tuple[int, int] | None:
    """[mínimo, máximo] de drones que escribe la frase, o None. Los números escritos con
    letras solo se leen en el idioma de la frase (el «to» danés es un dos; el inglés, no)."""
    texto = _plano(frase)
    for m in _INTERVALO.finditer(texto):
        a, b = _valor(m.group(1), idioma), _valor(m.group(2), idioma)
        if (
            a is not None
            and b is not None
            and 0 < a <= b <= 100
            and _cuenta(texto, m.start(), _fin(texto, m.start()), b, idioma)
        ):
            return a, b
    for m in _HASTA.finditer(texto):
        b = _valor(m.group(1), idioma)
        if (
            b is not None
            and 0 < b <= 100
            and _cuenta(texto, m.start(), _fin(texto, m.start()), b, idioma)
        ):
            return 1, b
    for m in _UNO.finditer(texto):
        palabra, intermedias = m.group(1), m.group(2)
        n = _valor(palabra, idioma)
        if n is None or not 0 < n <= 100:
            continue
        if (palabra in SOLO_JUNTO or palabra.isdigit()) and intermedias.strip():
            continue
        if NO_ENTRE & set(intermedias.split()):
            continue
        if _cuenta(texto, m.start(), _fin(texto, m.start()), n, idioma):
            return n, n
    return None


_DRON = re.compile(rf"(?<![\w-]){PALABRA_DRON}", re.IGNORECASE)


def _fin(texto: str, desde: int) -> int:
    """Fin de la primera palabra dron desde una posición."""
    m = _DRON.search(texto, desde)
    return m.end() if m else len(texto)


HOVER, MERODEO, TRANSITO, ENJAMBRE = "hover", "merodeo", "transito", "enjambre"
PATRONES: tuple[tuple[str, str], ...] = (
    (
        ENJAMBRE,
        r"swarm\w*|schwarm|schwärme\w*|sværm\w*|svärm\w*|zwerm\w*|essaim\w*|enjambre\w*|"
        r"sciam\w*|r[oó]j\w*|roi(?:uri)?\b|spiet\w*|parv\w*|parvi\w*|рой|рій",
    ),
    (
        MERODEO,
        r"circl\w*|loiter\w*|flew around|flying around|fly around|kreist\w*|umkreist\w*|"
        r"flyver omkring|fløj rundt|flyr rundt|flög runt|flyger runt|cirkel\w*|"
        r"rondcirkel\w*|tournoy\w*|tourn(?:é|ait|aient) autour|volando en círculos|"
        r"dando vueltas|giravan\w*|sorvolava in cerchio|krąży\w*|kroužil\w*|"
        r"au survolat în cerc|rotit\w*",
    ),
    (
        HOVER,
        r"hover\w*|stationary|schweb\w*|svæve\w*|sveve\w*|sväva\w*|zawis\w*|"
        r"stand still|stood still|vol stationnaire|suspendid\w* en el aire|"
        r"stazionari\w*|staționa\w*|staţiona\w*",
    ),
    (
        TRANSITO,
        r"crossed|passed over|flew past|flew across|überquer\w*|weitergeflogen|"
        r"krydsede|krysset|korsade|traversat|a traversé|ont traversé|atravesó|"
        r"attraversat\w*|przeleciał\w*|przekroczył\w*|preletěl\w*|perskrid\w*|"
        r"šķērsoja|ületas",
    ),
)
_PATRONES = [(p, re.compile(rf"(?<!\w)(?:{r})", re.IGNORECASE)) for p, r in PATRONES]


def patron(frase: str) -> str | None:
    """El patrón de vuelo que escribe la frase, o None. Si escribe varios, el primero de la
    lista (enjambre, merodeo, hover, transito): el más específico."""
    texto = _plano(frase)
    if not re.search(PALABRA_DRON, texto, re.IGNORECASE):
        return None
    for nombre, expresion in _PATRONES:
        if expresion.search(texto):
            return nombre
    return None


# Hora local escrita en la frase: «20:00», «20h15», «20.15 Uhr», «kl. 20.15», «um 21 Uhr».
_CONTEXTO_HORA = (
    r"(?<!\w)(?:kl\.?|klokken|klockan|um|godz\.?|ora|orei|ore|à|a las|at|around|ok\.|ca\.)"
)
_FIN = r"(?![\d]|[.,:]\d)"
_HORA = re.compile(
    rf"(?<![\d.,:])([01]?\d|2[0-3])\s?[:h]\s?([0-5]\d){_FIN}"
    rf"|{_CONTEXTO_HORA}\s+(?:\w+\s+)?([01]?\d|2[0-3])\.([0-5]\d){_FIN}"
    rf"|(?<![\d.,:])([01]?\d|2[0-3])\.([0-5]\d)\s*(?:uhr|h\b)"
    rf"|{_CONTEXTO_HORA}\s+(?:about\s+|around\s+|approximately\s+|gegen\s+|circa\s+)?"
    rf"([01]?\d|2[0-3]){_FIN}(?:\s*(?:uhr|h\b|hrs|o'clock))?",
    re.IGNORECASE,
)
# Frases que dan la hora de otra cosa (la reapertura, el final).
_OTRA_HORA = re.compile(
    r"reopen|re-open|wieder ge|wiedereröffn|genåbn|gjenåpn|återöppn|heropend|rouvert|reabri|"
    r"redeschi|ponownie otw|resumed|wznowi|reluat|wieder aufgenommen|until|bis |indtil|"
    r"inntil|tills|tot |jusqu|hasta|până",
    re.IGNORECASE,
)


def hora_local(frase: str) -> tuple[int, int] | None:
    """La hora local del suceso que escribe una frase que habla de drones, o None. Si la frase
    habla también de una reapertura o de un «hasta», no se lee: la hora puede ser la de eso."""
    texto = _plano(frase)
    if not re.search(PALABRA_DRON, texto, re.IGNORECASE) or _OTRA_HORA.search(texto):
        return None
    horas = []
    for m in _HORA.finditer(texto):
        grupos = m.groups()
        for i in (0, 2, 4):
            if grupos[i] is not None:
                horas.append((int(grupos[i]), int(grupos[i + 1])))
                break
        else:
            if grupos[6] is not None:
                horas.append((int(grupos[6]), 0))
        sufijo = texto[m.end() : m.end() + 6].strip().replace(".", "")
        if horas and sufijo.startswith(("pm", "am")):
            hora, minuto = horas[-1]
            if sufijo.startswith("pm") and hora < 12:
                horas[-1] = (hora + 12, minuto)
            elif sufijo.startswith("am") and hora == 12:
                horas[-1] = (0, minuto)
    return horas[0] if len(set(horas)) == 1 else None


# País desde el que entró el dron, cuando la frase lo dice con un verbo de entrada: «entered
# from Belarus», «a intrat din Ucraina», «wleciał z Białorusi», «įskrido iš Baltarusijos».
_ENTRADA = re.compile(
    r"enter\w*|cross\w*|came from|coming from|flew in|eingedrungen|eingeflogen|kam aus|"
    r"a intrat|au intrat|a pătruns|au pătruns|pătrun\w*|traversat|wleciał\w*|wtargn\w*|"
    r"przylecia\w*|įskrid\w*|įskrend\w*|ielidoj\w*|ielid\w*|tunginud|saapui|tuli|"
    r"kom fra|kommet inn|komme ind|залетел\w*|залетів|залетіл\w*|"
    r"provenit|venit din|venind din|dinspre|from the direction of",
    re.IGNORECASE,
)
PAISES_ENTRADA: tuple[tuple[str, str], ...] = (
    ("BY", r"belarus\w*|bielorrusia|biélorussie|weißrussland|hviterussland|hviderusland|"
           r"vitryssland|wit-rusland|białoru\w*|baltarusij\w*|baltkrievij\w*|valgevene|"
           r"valko-venäj\w*|bielorusi\w*|беларус\w*|білорус\w*"),
    ("RU", r"russia\w*|rusia\w*|russie|russland|rusland|ryssland|rosj\w*|rusij\w*|krievij\w*|"
           r"venemaa|venäj\w*|federa\w+ rus\w*|kaliningrad\w*|россии|росії|рф"),
    ("UA", r"ukrain\w*|ucrania|ucrainei|ucraina|oekraïne|ukrajin\w*|ukrainy|ukrainos|"
           r"ukrainas|украин\w*|україн\w*"),
    ("MD", r"moldov\w*|republica moldova|moldawi\w*|mołdaw\w*|молдов\w*"),
)  # fmt: skip
_PAISES_ENTRADA = [(p, re.compile(rf"(?<!\w)(?:{r})", re.IGNORECASE)) for p, r in PAISES_ENTRADA]


def pais_de_entrada(frase: str, pais_incidente: str | None = None) -> str | None:
    """El país (ISO) desde el que la frase dice que entró el dron, o None. Solo si la frase
    habla de drones, tiene un verbo de entrada y nombra un solo país distinto del incidente."""
    texto = _plano(frase)
    if not re.search(PALABRA_DRON, texto, re.IGNORECASE) or not _ENTRADA.search(texto):
        return None
    nombrados = {p for p, e in _PAISES_ENTRADA if e.search(texto) and p != pais_incidente}
    return nombrados.pop() if len(nombrados) == 1 else None
