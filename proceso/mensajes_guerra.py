"""Lectura por código de los mensajes de los canales de la capa de guerra: qué lugares
concretos alcanzó un ataque con drones, con qué tipo de objetivo, daños y víctimas.

Solo drones: los misiles, las bombas guiadas y la artillería de los mismos mensajes no se
registran. Cada frase se atribuye a un arma: la que nombra, o la de la frase anterior si no
nombra ninguna, o la del mensaje entero. Los lugares de una frase cuentan solo si su arma
son drones y nada más. Si la frase mezcla drones con otras armas, el mensaje queda para el
extractor (`proceso/extraccion_guerra.py`), que dice qué lugar alcanzó cada arma; si solo
nombra otras armas, se ignora.

Una frase da lugares con impacto si dice que algo se alcanzó, se dañó, ardió o hubo
víctimas («влучання», «пошкоджено», «пожежа», «поранено», «попадание», «повреждены»,
«возгорание», «ранены»…). Las frases que solo cuentan derribos («над Сумщиною збито 12
БпЛА»), avisos de alarma («Дронова загроза») o movimientos de drones no dan lugares.
La caída de restos («уламки», «обломки», «падіння») es un impacto de tipo «restos».

Lo que no dice el mensaje queda vacío: sin cifra de heridos no hay heridos; las víctimas solo
se asignan a un lugar si el mensaje nombra uno solo.
"""

import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from proceso.lugares_guerra import TIPOS_INSTALACION, Hallazgo, Lugar, Nomenclator, raiz_adjetivo

MAX_PALABRAS_FRASE = 25
KYIV = ZoneInfo("Europe/Kyiv")
VERSION = "mensajes-guerra/2"

DRON = re.compile(
    r"БпЛА|БПЛА|безпілотн|беспилотн|\bдрон|дронов|дронам|шахед|shahed|герань|гербер|"
    r"\bFPV\b|ФПВ|коптер|ланцет|молні[яюї]|молни[яеи]|самол[её]тн\w+\s+тип|\bБАК\b|\bUAV\b",
    re.IGNORECASE,
)
OTRA_ARMA = re.compile(
    r"ракет|іскандер|искандер|калібр|калибр|кинджал|кинжал|\bХ-\d+|балістич|баллистич|"
    r"крилат|крылат|\bКАБ\w*|авіабомб|авиабомб|керован\w+\s+бомб|управляем\w+\s+бомб|"
    r"артилер|артиллер|\bРСЗВ\b|\bРСЗО\b|міномет|миномет|\bГрад\w*|снаряд|танк\w*|"
    r"HIMARS|Хаймарс|ATACMS|Нептун|Storm\s+Shadow|Шторм|бомбардувальн|бомб[аиу]\b|"
    # Ataques aéreos y bombardeos sin arma: no se pueden atribuir a un dron por código.
    r"авіаудар|авиаудар|авіаційн\w+\s+(?:удар|обстріл)|авиацион\w+\s+удар|обстріл|обстріля|"
    r"обстрел",
    re.IGNORECASE,
)
IMPACTO = re.compile(
    r"влуча|влучив|влучил|поціли|пошкодж|зруйн|руйнув|пожеж|загоран|займан|загорів|"
    r"уражен|уразил|ураже|вибух|атакува|вдари|удар\w*\s+по|наслідк|постражда|поранен|"
    r"травмован|загин|загибл|вбит|уламк|падінн|падіння|знеструм|"
    r"попадан|прил[её]т|поврежд|разруш|пожар|возгоран|загорел|взрыв|детонац|атакова|"
    r"атаки\s+БПЛА|атаке\s+БПЛА|ранен|погиб|пострадал|травмир|обломк|падени|сдетонир|"
    r"обесточ|задел|выбит|выбиты",
    re.IGNORECASE,
)
DERRIBO = re.compile(r"збит|знищ|подавл|знешкодж|сбит|уничтож|перехвач|подавлен|нейтрализ", re.I)
RESTOS = re.compile(r"уламк|обломк|падінн|падіння|падени|падение", re.IGNORECASE)
IMPACTO_DIRECTO = re.compile(
    r"влуча|влучив|поціли|прям\w+\s+попад|попадан|прил[её]т|удар\w*\s+по|уражен|уразил|"
    r"атакува\w*\s+[А-ЯІЇЄҐ]|атакова\w*\s+[А-ЯЁ]",
    re.IGNORECASE,
)
# Mensajes que recuerdan un ataque pasado sin dar uno nuevo: condecoraciones, homenajes,
# reuniones, aniversarios. Enlazarían el lugar con la noche de su publicación.
RETROSPECTIVO = re.compile(
    r"нагород|відзнак|вшанув|річниц|роковин|зустрілас|зустрівс|подяку|орден\w*\s|"
    r"награ[дж]|памят|годовщин|встретил|вручил|вручи|навестил|відвідав|відвідала|провідав|"
    r"проверил,?\s+как|перевірив,?\s+як",
    re.IGNORECASE,
)
# El dron como objetivo y no como arma: «уражено склад БпЛА», «місце запуску БпЛА»,
# «пункти управління БпЛА». Se quita antes de buscar el arma.
DRON_OBJETIVO = re.compile(
    r"(?:склад\w*|пункт\w*\s+управління|місц\w+\s+(?:запуску|зберігання|базування|"
    r"підготовки)|запуску|зберігання|підготовки|пуску|оператор\w*|розрахун\w*|виробництв\w*|"
    r"майстер\w*|ангар\w*|цех\w*|завод\w*|пункт\w*\s+управления|мест\w+\s+запуска|"
    r"производств\w*|підрозділ\w*|дислокації)(?:[\s,]+(?:та\s+|і\s+|й\s+|и\s+)?"
    r"[^\W\d_]+){0,3}[\s,]+(?:ударн\w+\s+)?"
    r"(?:БпЛА|БПЛА|безпілотник\w*|беспилотник\w*|дрон\w*)",
    re.IGNORECASE,
)
# El Estado Mayor reivindica ataques sin decir casi nunca con qué arma; solo cuentan los que
# dicen que el medio fueron drones propios.
DRON_PROPIO = re.compile(
    r"Сил\w*\s+безпілотних\s+систем|\bСБС\b|(?:із|з)\s+застосуванням\s+(?:\w+\s+){0,2}"
    r"(?:БпЛА|безпілотник\w*|дрон\w*)|БпЛА\s+(?:Сил|СБС|ГУР|СБУ)"
    # «ударними БпЛА», «дронами» como medio, no como objetivo («ретранслятори для управління
    # ударними БпЛА», «боротьба з дронами»).
    r"|(?<!управління )(?<!керування )(?<!з )(?<!із )(?<!проти )"
    r"(?:(?:ударними|далекобійними)\s+(?:БпЛА|дронами|безпілотниками)|дронами|безпілотниками)",
    re.IGNORECASE,
)
# Lugares de donde salen los drones: no son lugares alcanzados.
LANZAMIENTO = re.compile(r"(?:із|з|с)\s+напрямк|направлени[яй]|із\s+районів|запуск\w*\s+з", re.I)
# Reivindicación de un ataque propio (Estado Mayor ucraniano): sin estos verbos, la frase no
# reivindica nada (los partes de derribos que reproduce el canal hablan de ataques rusos).
REIVINDICA = re.compile(
    r"уражен|уразил|уразили|ураженн|завдал\w*\s+ураженн|підтверджено\s+(?:ураження|знищення)|"
    r"знищено|знищили|поразил|поражен",
    re.IGNORECASE,
)
# Avisos que no son ataques: alarmas, amenazas, «отбой».
AVISO = re.compile(
    r"повітряна\s+тривога|відбій|загроза\s+застосування|дронова\s+загроза|"
    r"ракетная\s+опасность|беспилотная\s+опасность|отбой|угроза\s+атаки|режим\s+беспилотной",
    re.IGNORECASE,
)

CATEGORIAS: tuple[tuple[str, re.Pattern[str]], ...] = tuple(
    (categoria, re.compile(patron, re.IGNORECASE))
    for categoria, patron in (
        ("combustible", r"\bНПЗ\b|нафтопереробн|нефтеперерабат|нафтобаз|нефтебаз|паливн|"
                        r"топливн|\bПММ\b|\bГСМ\b|\bАЗС\b|нафтов|нефтян|резервуар"),
        ("energia", r"енергети|энергети|енергооб|энергообъект|підстанц|подстанц|\bТЕС\b|\bТЕЦ\b|"
                    r"\bГЕС\b|\bТЭЦ\b|\bТЭС\b|\bГРЭС\b|електро|электро|газопровод|газорозпод|"
                    r"газов\w+\s+(?:інфраструктур|об)|котельн|знеструм|обесточ|ЛЕП\b|ЛЭП\b"),
        ("residencial", r"будин|житлов|квартир|багатоповерх|приватн\w+\s+(?:будин|сектор|"
                        r"садиб)|домоволод|\bдом\b|\bдома\b|домов|жил\w+\s+дом|многоквартир|"
                        r"частн\w+\s+(?:дом|сектор|домовладен)|гуртожит|общежит"),
        ("ferrocarril", r"залізнич|залізниц|локомотив|вагон|\bдепо\b|укрзалізн|железнодорож|"
                        r"\bРЖД\b|тепловоз|электричк|електричк"),
        ("puerto", r"\bпорт\w{0,3}\b|портов|причал|термінал|терминал|судн|судов"),
        ("industrial", r"підприємств|завод|виробнич|промислов|склад|предприят|"
                       r"производствен|промышлен|комбінат|комбинат|цех"),
        ("aerodromo", r"аеродром|аэродром|аеропорт|аэропорт|авіабаз|авиабаз"),
    )
)  # fmt: skip

_NUMEROS = {
    "один": 1, "одна": 1, "одну": 1, "одного": 1, "одной": 1, "одній": 1, "два": 2, "дві": 2,
    "две": 2, "двоє": 2, "двое": 2, "двох": 2, "двух": 2, "три": 3, "троє": 3, "трое": 3,
    "трьох": 3, "трех": 3, "трёх": 3, "чотири": 4, "четыре": 4, "четверо": 4, "чотирьох": 4,
    "четырех": 4, "четырёх": 4, "п'ять": 5, "пять": 5, "п'ятеро": 5, "пятеро": 5, "п'ятьох": 5,
    "пяти": 5, "шість": 6, "шесть": 6, "шестеро": 6, "сім": 7, "семь": 7, "семеро": 7,
    "вісім": 8, "восемь": 8, "дев'ять": 9, "девять": 9, "десять": 10,
}  # fmt: skip
_NUM = (
    r"(\d{1,4}|" + "|".join(sorted((re.escape(k) for k in _NUMEROS), key=len, reverse=True)) + ")"
)
# Una persona sin cifra: «загинула жінка», «поранено чоловіка», «ранен мужчина».
_UNA_PERSONA = (
    r"(?:жінк\w*|чоловік\w*|людин\w*|дитин\w*|хлопчик\w*|дівчин\w*|підліт\w*|пенсіонер\w*|"
    r"мужчин\w*|женщин\w*|человек\b|ребен\w*|ребён\w*|мальчик\w*|девочк\w*|подрост\w*|"
    r"пенсионер\w*|водител\w*|водій\w*|мешкан\w*|житель\w*|жительниц\w*)"
)
_HERIDOS = (
    r"(?:поранен\w*|травмован\w*|постраждал\w*|постраждав\w*|ранен\w*|травмирован\w*|"
    r"пострадал\w*|госпіталізован\w*|госпитализирован\w*)"
)
_MUERTOS = r"(?:загин\w*|загибл\w*|вбит\w*|погиб\w*|убит\w*)"
_PERSONAS = (
    r"(?:\s+(?:мирн\w+\s+)?(?:людин\w*|люд\w*|особ\w*|чоловік\w*|жінк\w*|дит\w*|"
    r"цивільн\w*|мешканц\w*|человек\w*|жител\w*|мирн\w*|граждан\w*|ребен\w*|детей))?"
)
_CIFRA_ANTES = r"(?<![\w-])" + _NUM + _PERSONAS + r"\s+(?:\w+\s+)?"
_CIFRA_DESPUES = r"\s+(?:\w+\s+)?" + _NUM + _PERSONAS


def _numero(texto: str) -> int:
    limpio = texto.lower().replace("’", "'").replace("ʼ", "'")
    return _NUMEROS[limpio] if limpio in _NUMEROS else int(limpio)


# Cifras que no son de personas: fechas («29 вересня»), edades («81-річна», «45-летний»),
# horas y números de casa.
_NO_PERSONAS = re.compile(
    r"\d{1,2}\s+(?:"
    + "|".join(
        [
            "січня",
            "лютого",
            "березня",
            "квітня",
            "травня",
            "червня",
            "липня",
            "серпня",
            "вересня",
            "жовтня",
            "листопада",
            "грудня",
            "января",
            "февраля",
            "марта",
            "апреля",
            "мая",
            "июня",
            "июля",
            "августа",
            "сентября",
            "октября",
            "ноября",
            "декабря",
        ]
    )
    + r")|\d+\s*-\s*(?:річн|рiчн|летн|лiтн)\w*|\d{1,2}[:.]\d{2}|№\s*\d+|\d+-\w+",
    re.IGNORECASE,
)


def _victimas(texto: str, verbo: str) -> int | None:
    """La mayor cifra de víctimas del texto para el verbo («поранено 3 людей», «двоє
    загиблих», «ранены два человека», «загинула жінка»), o None si no da ninguna."""
    texto = _NO_PERSONAS.sub(" ", texto)
    cifras = []
    for patron in (_CIFRA_ANTES + verbo, verbo + _CIFRA_DESPUES):
        for m in re.finditer(patron, texto, re.IGNORECASE):
            cifras.append(_numero(m.group(1)))
    if not cifras:
        persona = re.search(
            verbo + r"\s+(?:\d+-\w+\s+)?" + _UNA_PERSONA + "|" + _UNA_PERSONA + r"\s+" + verbo,
            texto, re.IGNORECASE,
        )  # fmt: skip
        if persona and not re.search(r"(?:без|не)\s+" + verbo, texto, re.IGNORECASE):
            cifras.append(1)
    return max(cifras) if cifras else None


_DERRIBADOS = re.compile(
    r"(?:збит\w*|знищен\w*|подавлен\w*|знешкоджен\w*|сбит\w*|уничтожен\w*|перехвачен\w*)"
    r"(?:\s+(?:та|і|и|/)\s*\w+)?\s+(?:\w+\s+){0,3}?" + _NUM + r"\s+(?:\w+\s+){0,2}?"
    r"(?:БпЛА|БПЛА|безпілотн\w*|беспилотн\w*|дрон\w*|шахед\w*|ударн\w+)"
    r"|" + _NUM + r"\s+(?:\w+\s+){0,2}?(?:БпЛА|БПЛА|безпілотн\w*|беспилотн\w*|дрон\w*)\s+"
    r"(?:\w+\s+){0,3}?(?:збит\w*|знищен\w*|подавлен\w*|сбит\w*|уничтожен\w*|перехвачен\w*)",
    re.IGNORECASE,
)

MESES = {
    "січня": 1, "лютого": 2, "березня": 3, "квітня": 4, "травня": 5, "червня": 6,
    "липня": 7, "серпня": 8, "вересня": 9, "жовтня": 10, "листопада": 11, "грудня": 12,
    "января": 1, "февраля": 2, "марта": 3, "апреля": 4, "мая": 5, "июня": 6, "июля": 7,
    "августа": 8, "сентября": 9, "октября": 10, "ноября": 11, "декабря": 12,
}  # fmt: skip
_NOCHE_FECHA = re.compile(
    r"(?:у|в)\s+ніч\s+на\s+(\d{1,2})\s+(" + "|".join(MESES) + r")|"
    r"в\s+ночь\s+на\s+(\d{1,2})\s+(" + "|".join(MESES) + r")",
    re.IGNORECASE,
)
_NOCHE = re.compile(
    r"вночі|уночі|у\s+ніч|минулої\s+ночі|цієї\s+ночі|протягом\s+ночі|нічн\w+\s+атак|"
    r"ночью|в\s+ночь|минувшей\s+ночью|этой\s+ночью|ночн\w+\s+атак|в\s+течение\s+ночи",
    re.IGNORECASE,
)
# Parte diario de una administración («упродовж доби окупанти завдали 391 удар…», «за
# минувшие сутки»): cubre las 24 horas anteriores, no una noche, así que no se enlaza con un
# ataque concreto; el día es el anterior a la publicación.
PARTE_DIARIO = re.compile(
    r"(?:упродовж|впродовж|протягом|за\s+минулу|минулої)\s+(?:минулої\s+)?доби|за\s+добу|"
    r"за\s+(?:минувшие\s+|прошедшие\s+)?сутки|в\s+течение\s+(?:прошедших\s+)?суток",
    re.IGNORECASE,
)
_FRASES = re.compile(r"[^.!?\n;]+[.!?;]?")
_COMILLAS = re.compile(r"[«\"“„]([^»\"”“]{3,60})[»\"”“]")
# Tiempo de lectura de un mensaje del canal; una frase de más de 600 letras se corta.
MAX_LETRAS_FRASE = 600


@dataclass(frozen=True)
class ImpactoLeido:
    lugar: Lugar
    tipo: str  # impacto o restos
    categorias: tuple[str, ...]
    frase: str
    heridos: int | None = None
    fallecidos: int | None = None


@dataclass
class MensajeLeido:
    """Lo que da un mensaje. `motivo` dice por qué no da impactos (si no los da)."""

    impactos: list[ImpactoLeido] = field(default_factory=list)
    derribados: int | None = None
    heridos: int | None = None
    fallecidos: int | None = None
    noche: date | None = None
    es_noche: bool = False
    # Día anterior a la publicación que nombra el mensaje: el ataque fue entonces.
    dia: date | None = None
    # Parte diario: las 24 horas anteriores a la publicación, sin ataque concreto.
    parte_diario: bool = False
    # El código no puede atribuir los lugares a un arma, o hay lugares sin resolver.
    para_extractor: bool = False
    sin_resolver: list[Hallazgo] = field(default_factory=list)
    motivo: str | None = None
    prioridad: int = 0


def frase_breve(frase: str, centro: int | None = None) -> str:
    """La frase en 25 palabras como máximo, alrededor de la posición `centro`."""
    palabras = frase.split()
    if len(palabras) <= MAX_PALABRAS_FRASE:
        return " ".join(palabras)
    if centro is None:
        return " ".join(palabras[:MAX_PALABRAS_FRASE])
    antes = len(frase[:centro].split())
    inicio = max(0, min(antes - MAX_PALABRAS_FRASE // 2, len(palabras) - MAX_PALABRAS_FRASE))
    return " ".join(palabras[inicio : inicio + MAX_PALABRAS_FRASE])


def categorias(texto: str) -> tuple[str, ...]:
    return tuple(c for c, patron in CATEGORIAS if patron.search(texto))


_FECHA = re.compile(r"(?<!\d)(\d{1,2})\s+(" + "|".join(MESES) + r")", re.IGNORECASE)


def dia_declarado(texto: str, publicado: datetime) -> date | None:
    """El último día que nombra el texto («вночі 29 вересня», «26 сентября») si no es el de la
    publicación: el mensaje habla de un ataque anterior. None si no nombra otro día."""
    dias = []
    for m in _FECHA.finditer(texto):
        try:
            dia = date(publicado.year, MESES[m.group(2).lower()], int(m.group(1)))
        except ValueError:
            continue
        if (dia - publicado.date()).days > 1:
            dia = dia.replace(year=publicado.year - 1)
        if dia <= publicado.date():
            dias.append(dia)
    if not dias:
        return None
    ultimo = max(dias)
    return None if ultimo >= publicado.date() else ultimo


def noche_declarada(texto: str, publicado: datetime) -> date | None:
    """«У ніч на 22 серpня», «в ночь на 5 октября»: el día en que acaba la noche."""
    m = _NOCHE_FECHA.search(texto)
    if m is None:
        return None
    dia, mes = (m.group(1), m.group(2)) if m.group(1) else (m.group(3), m.group(4))
    anio = publicado.year
    try:
        fecha = date(anio, MESES[mes.lower()], int(dia))
    except ValueError:
        return None
    # Una noche declarada más de un día después de la publicación es del año anterior.
    if (fecha - publicado.date()).days > 1:
        fecha = fecha.replace(year=anio - 1)
    return fecha


def _armas(texto: str) -> frozenset[str]:
    armas = set()
    if DRON.search(texto):
        armas.add("dron")
    if OTRA_ARMA.search(texto):
        armas.add("otra")
    return frozenset(armas)


def _texto_limpio(texto: str) -> str:
    return texto.replace("\xa0", " ").replace("ʼ", "'").replace("’", "'")


_UNIFICAR = str.maketrans({"ь": None, "ъ": None, "'": None, "і": "и", "ї": "и", "є": "е",
                           "ё": "е", "й": "и", "ы": "и"})  # fmt: skip


def _unificar(texto: str) -> str:
    """Ucraniano y ruso con las mismas letras, para comparar raíces de regiones: «Самарській»
    y «Самарской» quedan «самарскии» y «самарскои»."""
    return texto.lower().replace("’", "'").replace("ʼ", "'").translate(_UNIFICAR)


def regiones_en_texto(texto: str, raices: tuple[tuple[str, str], ...]) -> frozenset[str]:
    """Regiones que nombra el texto, por las raíces del vocabulario de regiones de Ucrania y de
    Rusia, en ucraniano o en ruso («Самарській області», «Самарской области»)."""
    encontradas = set()
    unificado = _unificar(texto)
    for raiz, codigo in raices:
        if re.search(r"(?<![\w-])" + re.escape(_unificar(raiz)), unificado):
            encontradas.add(codigo)
    return frozenset(encontradas)


def analizar(
    texto: str,
    publicado: datetime,
    nomenclator: Nomenclator,
    regiones: frozenset[str] | None,
    raices_regiones: tuple[tuple[str, str], ...] = (),
    reivindicacion: bool = False,
) -> MensajeLeido:
    """Los impactos con lugar de un mensaje. `regiones`: las del canal (una administración
    regional, un gobernador); None en los canales de todo el país, que toman la región de
    la propia frase (`raices_regiones`). Con `reivindicacion` (Estado Mayor ucraniano), solo
    cuentan las frases que reivindican un ataque propio («уразили», «уражено»)."""
    texto = _texto_limpio(texto)
    leido = MensajeLeido()
    if not DRON.search(DRON_OBJETIVO.sub(" ", texto)) or (
        reivindicacion and not DRON_PROPIO.search(texto)
    ):
        leido.motivo = "sin_dron"
        return leido
    leido.noche = noche_declarada(texto, publicado)
    leido.dia = dia_declarado(texto, publicado)
    leido.es_noche = leido.noche is not None or bool(_NOCHE.search(texto))
    if PARTE_DIARIO.search(texto) and leido.noche is None:
        leido.parte_diario = True
        leido.es_noche = False
        if leido.dia is None:
            leido.dia = (publicado.astimezone(KYIV) - timedelta(days=1)).date()
    derribos = [int(_numero(next(g for g in m.groups() if g))) for m in _DERRIBADOS.finditer(texto)]
    leido.derribados = max(derribos) if derribos else None
    leido.heridos = _victimas(texto, _HERIDOS)
    leido.fallecidos = _victimas(texto, _MUERTOS)
    if not IMPACTO.search(texto):
        leido.motivo = "aviso" if AVISO.search(texto) else "sin_impacto"
        return leido
    if RETROSPECTIVO.search(texto):
        leido.motivo = "retrospectivo"
        return leido
    armas_mensaje = _armas(DRON_OBJETIVO.sub(" ", texto))
    anterior: frozenset[str] = frozenset()
    impactos: dict[str, ImpactoLeido] = {}
    mezclado = False
    for m in _FRASES.finditer(texto):
        frase = m.group(0)[:MAX_LETRAS_FRASE]
        propias = _armas(DRON_OBJETIVO.sub(" ", frase))
        armas = propias or anterior or armas_mensaje
        anterior = armas
        if not IMPACTO.search(frase) or AVISO.search(frase):
            continue
        if DERRIBO.search(frase) and not _danos(frase):
            continue
        if LANZAMIENTO.search(frase) or (reivindicacion and not REIVINDICA.search(frase)):
            continue
        ambito = regiones
        otras = regiones_en_texto(frase, raices_regiones) - (regiones or frozenset())
        if regiones is not None and otras:
            # La frase habla de otra región («Заріччя Чернігівської області»): sus lugares no
            # se buscan en la del canal.
            continue
        if ambito is None:
            ambito = regiones_en_texto(frase, raices_regiones) or regiones_en_texto(
                texto, raices_regiones
            )
            if not ambito:
                continue
        hallazgos = nomenclator.localidades_en(frase, ambito)
        instalaciones = _instalaciones(frase, hallazgos, nomenclator, ambito)
        if not hallazgos and not instalaciones:
            continue
        if armas != frozenset({"dron"}):
            if "dron" in armas:
                mezclado = True
            continue
        tipo = "restos" if RESTOS.search(frase) and not IMPACTO_DIRECTO.search(frase) else "impacto"
        # El tipo de objetivo, sin los nombres de lugar («Залізничне» no es un ferrocarril).
        sin_nombres = frase
        for h in sorted(hallazgos, key=lambda x: -x.inicio):
            sin_nombres = sin_nombres[: h.inicio] + " " * (h.fin - h.inicio) + sin_nombres[h.fin :]
        cats = categorias(sin_nombres)
        usadas = {i.localidad for i in instalaciones if i.localidad}
        for instalacion in instalaciones:
            impactos.setdefault(
                instalacion.id,
                ImpactoLeido(instalacion, tipo, cats or _categoria_instalacion(instalacion),
                             frase_breve(frase)),
            )  # fmt: skip
        for h in hallazgos:
            if h.lugar is None:
                leido.sin_resolver.append(h)
                continue
            if h.lugar.nombre in usadas:
                continue
            impactos.setdefault(
                h.lugar.id,
                ImpactoLeido(h.lugar, tipo, cats, frase_breve(frase, h.inicio)),
            )
    leido.impactos = list(impactos.values())
    if len(leido.impactos) == 1:
        unico = leido.impactos[0]
        leido.impactos = [
            ImpactoLeido(
                unico.lugar,
                unico.tipo,
                unico.categorias,
                unico.frase,
                leido.heridos,
                leido.fallecidos,
            )
        ]
    leido.para_extractor = mezclado or bool(leido.sin_resolver)
    if not leido.impactos and not leido.para_extractor:
        leido.motivo = "sin_lugar"
    leido.prioridad = _prioridad(texto)
    return leido


def _danos(frase: str) -> bool:
    """La frase dice algo más que un derribo: daños, fuego o víctimas."""
    return bool(
        re.search(
            r"пошкодж|зруйн|пожеж|загоран|займан|поранен|загин|загибл|влуча|уламк|"
            r"поврежд|разруш|пожар|возгоран|ранен|погиб|пострадал|попадан|обломк|падени|"
            r"падінн|падіння",
            frase,
            re.IGNORECASE,
        )
    )


def _categoria_instalacion(instalacion: Lugar) -> tuple[str, ...]:
    return {
        "refineria": ("combustible",), "deposito_combustible": ("combustible",),
        "central": ("energia",), "subestacion": ("energia",), "aerodromo": ("aerodromo",),
        "puerto": ("puerto",), "ferrocarril": ("ferrocarril",), "industrial": ("industrial",),
    }.get(instalacion.categoria, ())  # fmt: skip


def _instalaciones(
    frase: str, hallazgos: list[Hallazgo], nomenclator: Nomenclator, ambito: frozenset[str]
) -> list[Lugar]:
    """Instalaciones que nombra la frase: su tipo con el nombre entre comillas, con la
    localidad de la frase o con el adjetivo de la localidad («Рязанский НПЗ»)."""
    resultado: list[Lugar] = []
    localidades = [h.lugar for h in hallazgos if h.lugar is not None]
    for patron, categoria in TIPOS_INSTALACION:
        for m in patron.finditer(frase):
            comillas = _COMILLAS.search(frase, m.end(), min(len(frase), m.end() + 60))
            nombre = comillas.group(1) if comillas else None
            cerca = min(localidades, key=lambda loc: 0) if len(localidades) == 1 else None
            if cerca is None:
                previa = re.findall(r"[^\W\d_]+", frase[max(0, m.start() - 40) : m.start()])
                if previa:
                    cerca = nomenclator.localidad_por_adjetivo(previa[-1], ambito)
            if cerca is None and nombre:
                cerca = nomenclator.localidad_por_adjetivo(nombre.split()[0], ambito)
            instalacion = nomenclator.instalacion(categoria, ambito, cerca, nombre)
            if instalacion is not None and instalacion.id not in {r.id for r in resultado}:
                resultado.append(instalacion)
    return resultado


def _prioridad(texto: str) -> int:
    """Para el extractor: primero los objetivos que FIRMS puede comprobar (combustible,
    energía, industria)."""
    cats = set(categorias(texto))
    if "combustible" in cats:
        return 3
    if "energia" in cats or "industrial" in cats:
        return 2
    return 1


def raiz(adjetivo: str) -> str:
    return raiz_adjetivo(adjetivo)
