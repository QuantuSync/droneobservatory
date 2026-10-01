"""Formas declinadas de los topónimos de Ucrania y de Rusia, en ucraniano y en ruso.

Los mensajes nombran los lugares declinados: «у Харкові», «в Одесі», «Києва», «на
Сумщині», «в районе Белгорода», «в Брянске», «Новокуйбышевского НПЗ». El nomenclátor
guarda el nombre en nominativo; aquí se generan, por la terminación del nombre, las formas
de los casos que aparecen en los mensajes (genitivo, dativo, acusativo, instrumental y
locativo). Una forma que no existe no hace daño: no casa con nada. Las formas van en
minúsculas, palabra a palabra; la normalización del índice (sin acentos, como
`proceso.noticias.normalizar`) se aplica después.

Los nombres de dos o más palabras se declinan palabra a palabra: el adjetivo concuerda con
el sustantivo («Біла Церква» → «Білій Церкві», «Кривого Рогу» no: Кривий Ріг es irregular
y va en ALIAS_IRREGULARES). Las palabras con guion se declinan solo en su última parte
(«Івано-Франківськ» → «Івано-Франківська»).
"""

from itertools import product

# Formas que las reglas no generan: alternancias irregulares de nombres frecuentes.
ALIAS_IRREGULARES: dict[str, tuple[str, ...]] = {
    "кривий ріг": ("кривого рогу", "кривому розі", "кривим рогом", "кривому рогу"),
    "кривой рог": ("кривого рога", "кривом роге", "кривым рогом"),
    "біла церква": ("білої церкви", "білій церкві", "білу церкву", "білою церквою"),
    "лубни": ("лубен", "лубнах"),
    "орёл": ("орла", "орле", "орлом"),
    "орел": ("орла", "орле", "орлом"),
    "елец": ("ельца", "ельце", "ельцом"),
    "єлець": ("єльця", "єльці"),
    "старий оскол": ("старого осколу", "старому осколі"),
    "старый оскол": ("старого оскола", "старом осколе"),
    "великий новгород": ("великого новгорода", "великом новгороде"),
    "нижний новгород": ("нижнего новгорода", "нижнем новгороде", "нижнему новгороду"),
    "нижній новгород": ("нижнього новгорода", "нижньому новгороді"),
}

_ADJ_UK_M = ("ий", "ій")
_ADJ_RU_M = ("ий", "ый", "ой")


def _sin_guion(palabra: str) -> tuple[str, str]:
    """(prefijo con guion, última parte): solo se declina la última parte."""
    if "-" in palabra:
        prefijo, _, ultima = palabra.rpartition("-")
        return prefijo + "-", ultima
    return "", palabra


def _sustantivo_uk(p: str) -> set[str]:
    formas = {p}
    if len(p) < 3:
        return formas
    if p.endswith("ія"):
        r = p[:-1]
        return formas | {r + "ї", r + "ю", r + "єю"}
    if p.endswith("я"):
        r = p[:-1]
        return formas | {r + "і", r + "ї", r + "ю", r + "ею", r + "ям"}
    if p.endswith("а"):
        r = p[:-1]
        formas |= {r + "и", r + "і", r + "у", r + "ою"}
        if r.endswith("к"):
            formas.add(r[:-1] + "ці")
        elif r.endswith("г"):
            formas.add(r[:-1] + "зі")
        elif r.endswith("х"):
            formas.add(r[:-1] + "сі")
        if r.endswith(("ж", "ч", "ш", "щ", "ц")):
            formas |= {r + "і", r + "ею"}
        return formas
    if p.endswith("о"):
        r = p[:-1]
        return formas | {r + "а", r + "і", r + "у", r + "ом", r + "ові"}
    if p.endswith("ці"):
        r = p[:-1]
        return formas | {r + "ів", r + "ях", r + "ям", r + "ями"}
    if p.endswith(("и", "і")):
        r = p[:-1]
        return formas | {r, r + "ів", r + "ах", r + "ам", r + "ами", r + "ях"}
    if p.endswith("ець"):
        r = p[:-3]
        return formas | {r + "ця", r + "ці", r + "цем", r + "цю"}
    if p.endswith("ь"):
        r = p[:-1]
        formas |= {r + "я", r + "ю", r + "і", r + "ем", r + "еві"}
        if r.endswith(("іль", "іл")) or r[-2:-1] == "і":
            # Бориспіль → Борисполя.
            alterna = r[:-2] + "о" + r[-1:]
            formas |= {alterna + "я", alterna + "і", alterna + "ем", alterna + "ю"}
        return formas
    # Consonante final: Харків, Львів, Київ, Луцьк, Ізюм.
    raices = {p}
    if p.endswith("ів"):
        raices.add(p[:-2] + "ов")
    if p.endswith("їв"):
        raices.add(p[:-2] + "єв")
    if len(p) > 3 and p[-2] == "і" and p[-1] not in "аеєиіїоуюяь":
        raices.add(p[:-2] + "о" + p[-1])
    if p.endswith("ок"):
        raices.add(p[:-2] + "к")
    for r in raices:
        formas |= {r + "а", r + "у", r + "і", r + "ові", r + "ом", r + "ем"}
    return formas


def _adjetivo_uk(p: str) -> set[str] | None:
    """Formas del adjetivo (masculino -ий/-ій, femenino -а/-я, neutro -е/-є), o None."""
    if p.endswith("ий"):
        r = p[:-2]
        return {p, r + "ого", r + "ому", r + "им", r + "ім"}
    if p.endswith("ій") and len(p) > 4:
        r = p[:-2]
        return {p, r + "ього", r + "ьому", r + "ім"}
    if p.endswith(("ське", "цьке", "зьке", "не", "ве", "ре", "ле", "ке", "те", "де", "че")):
        r = p[:-1]
        return {p, r + "ого", r + "ому", r + "им", r + "ім"}
    return None


def _adjetivo_fem_uk(p: str) -> set[str]:
    r = p[:-1]
    return {p, r + "ої", r + "ій", r + "у", r + "ою"}


def formas_uk(nombre: str) -> set[str]:
    """Formas de un topónimo en ucraniano, en minúsculas."""
    base = " ".join(nombre.lower().replace("’", "'").replace("ʼ", "'").split())
    resultado = {base, *ALIAS_IRREGULARES.get(base, ())}
    palabras = base.split(" ")
    por_palabra: list[set[str]] = []
    for i, palabra in enumerate(palabras):
        prefijo, ultima = _sin_guion(palabra)
        siguiente_fem = i + 1 < len(palabras) and palabras[i + 1].endswith(("а", "я"))
        if ultima.endswith("а") and siguiente_fem and len(palabras) > 1:
            formas = _adjetivo_fem_uk(ultima)
        else:
            formas = _adjetivo_uk(ultima) or _sustantivo_uk(ultima)
        por_palabra.append({prefijo + f for f in formas})
    if len(palabras) <= 3:
        resultado |= {" ".join(c) for c in product(*por_palabra)}
    return resultado


def _sustantivo_ru(p: str) -> set[str]:
    formas = {p}
    if len(p) < 3:
        return formas
    if p.endswith(("е", "э", "у", "ю")):
        # Туапсе: los nombres en -е, -э, -у y -ю no se declinan.
        return formas
    if p.endswith("ия"):
        r = p[:-1]
        return formas | {r + "и", r + "ю", r + "ей"}
    if p.endswith("я"):
        r = p[:-1]
        return formas | {r + "и", r + "е", r + "ю", r + "ей"}
    if p.endswith("а"):
        r = p[:-1]
        duras = ("к", "г", "х", "ж", "ш", "ч", "щ")
        formas |= {r + ("и" if r.endswith(duras) else "ы"), r + "е", r + "у", r + "ой", r + "ей"}
        return formas
    if p.endswith(("ово", "ево", "ино", "ыно")):
        # Иваново: indeclinable en el habla corriente, declinado en la norma.
        r = p[:-1]
        return formas | {r + "а", r + "е", r + "у", r + "ом"}
    if p.endswith("о"):
        r = p[:-1]
        return formas | {r + "а", r + "е", r + "у", r + "ом"}
    if p.endswith(("ы", "и")):
        r = p[:-1]
        return formas | {r, r + "ах", r + "ам", r + "ами", r + "ов"}
    if p.endswith("ь"):
        r = p[:-1]
        return formas | {r + "я", r + "ю", r + "е", r + "ем", r + "и"}
    if p.endswith("ец"):
        r = p[:-2]
        formas |= {r + "ца", r + "це", r + "цом", r + "цу"}
    if p.endswith("ок"):
        r = p[:-2] + "к"
        formas |= {r + "а", r + "е", r + "у", r + "ом"}
    if p.endswith("й"):
        r = p[:-1]
        return formas | {r + "я", r + "е", r + "ю", r + "ем"}
    return formas | {p + "а", p + "у", p + "е", p + "ом"}


def _adjetivo_ru(p: str) -> set[str] | None:
    if p.endswith(_ADJ_RU_M) and len(p) > 4:
        r = p[:-2]
        suave = p.endswith("ий") and r.endswith(("н",)) and not r.endswith(("ск", "цк"))
        if suave:
            return {p, r + "его", r + "ему", r + "ем", r + "им"}
        return {p, r + "ого", r + "ому", r + "ом", r + "ым", r + "им"}
    if p.endswith(("ое", "ее")) and len(p) > 4:
        r = p[:-2]
        return {p, r + "ого", r + "ому", r + "ом", r + "его", r + "ем"}
    return None


def _adjetivo_fem_ru(p: str) -> set[str]:
    r = p[:-2]
    return {p, r + "ой", r + "ую", r + "ей"}


def formas_ru(nombre: str) -> set[str]:
    """Formas de un topónimo en ruso, en minúsculas."""
    base = " ".join(nombre.lower().split())
    resultado = {base, *ALIAS_IRREGULARES.get(base, ())}
    palabras = base.split(" ")
    por_palabra: list[set[str]] = []
    for i, palabra in enumerate(palabras):
        prefijo, ultima = _sin_guion(palabra)
        siguiente = i + 1 < len(palabras)
        if ultima.endswith(("ая", "яя")) and (siguiente or len(palabras) == 1):
            formas = _adjetivo_fem_ru(ultima)
        else:
            formas = _adjetivo_ru(ultima) or _sustantivo_ru(ultima)
        por_palabra.append({prefijo + f for f in formas})
    if len(palabras) <= 3:
        resultado |= {" ".join(c) for c in product(*por_palabra)}
    return resultado


def formas(nombre: str, idioma: str) -> set[str]:
    """Formas en el idioma del nombre («uk» o «ru»); otro idioma, solo el nombre."""
    if idioma == "uk":
        return formas_uk(nombre)
    if idioma == "ru":
        return formas_ru(nombre)
    return {" ".join(nombre.lower().split())}
