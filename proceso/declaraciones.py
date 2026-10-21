"""Declaraciones oficiales citadas por la prensa: cómo cambian el incidente.

Las autoridades confirman los incidentes en declaraciones a la prensa, no en sus
webs. Cada declaración que el extractor encuentra en una noticia (con su frase
literal, que tiene que estar en el texto enviado) se registra como fuente
«declaración oficial citada», de fiabilidad B, con el enlace a la noticia. Reglas:

- incidente o drones: pasa a confirmado (la autoridad dice que ocurrió).
- Presencia del dron: si la autoridad competente lo da por hecho, está confirmada. Basta con
  que actúe o declare atribuyendo el suceso a un dron (un cierre por dron, un aviso de dron
  que comunica, una intervención por dron): drones, incidente o autoria de un gobierno,
  ministerio, fuerzas armadas, policía, fiscalía, autoridad de aviación civil, gestor de
  navegación aérea o gestor aeroportuario confirman la presencia. No se piden restos, grabación
  ni detección por sensor. Solo queda sin confirmar si la propia autoridad lo deja abierto
  («posible dron», «objeto no identificado», «se investiga si era un dron»). Cada confirmación
  deja una afirmación de presencia_dron con la fuente que la provoca.
- sin_drones: presencia_dron descartada. niega_incidente: desmentido, salvo que lo niegue una
  autoridad que no es competente sobre el espacio aéreo ni la investigación (el gestor del
  aeropuerto) y lo haya confirmado una que sí lo es (el control aéreo): entonces prevalece la
  competente y la negación queda en el historial (proceso/competencia.py).
- autoria: atribuido, solo si una autoridad competente (gobierno, ministerio, fuerzas armadas,
  fiscalía o policía) lo afirma con sus propias palabras, sin duda ni investigación, y nombra a
  quien se atribuye (un Estado o una persona; proceso/atribucion.py), con su tipo y su país.
- Lo que una autoridad dice que investiga, examina o comprueba va a la ficha como
  investigación en curso, sin cambiar el estado.

Un colectivo profesional, un sindicato o una asociación no es una autoridad aunque la noticia lo
cite como tal (configuracion/no_son_autoridades.json, `no_es_autoridad`): su declaración no se
aplica.

Una autoridad habla de su país: una declaración de una autoridad de otro país no
cambia el incidente (el gobierno letón que dice que en Letonia no entró ningún dron
no desmiente el derribo en Estonia). Las fichas anteriores no traen el país de la
autoridad: sus declaraciones valen como antes.
"""

import contextlib
import copy
import json
import re
from collections.abc import Sequence
from functools import cache
from pathlib import Path
from typing import Any

from esquema import Documento
from proceso import atribucion, competencia
from proceso.credibilidad import Credibilidad
from proceso.estados import Estado, TransicionNoPermitida, transitar
from proceso.noticias import filtro, normalizar

MAX_PALABRAS_FRASE = 25
RUTA_NO_AUTORIDADES = (
    Path(__file__).resolve().parent.parent / "configuracion" / ("no_son_autoridades.json")
)
FIABILIDAD = "B"
# Autoridades competentes: si atribuyen el suceso a un dron, la presencia está confirmada.
AUTORIDADES_DEL_DRON = frozenset(
    {
        "gobierno", "ministerio", "fuerzas_armadas", "policia", "navegacion_aerea",
        "aeropuerto", "fiscalia", "aviacion_civil",
    }
)  # fmt: skip
# Declaraciones que, de una autoridad competente, atribuyen el suceso (un dron) a lo que pasó.
_CON_DRONES = frozenset({"incidente", "autoria"})
# Formas que el filtro de noticias no recoge por la declinación (genitivo griego) o por ser
# el adjetivo y no el nombre («bezpilotní letoun»).
_DRONES_DECLINADOS = re.compile(
    r"(?<!\w)(μη επανδρωμέν\w*|bezpilot\w*|беспилот\w*|безпілот\w*|bepilo[tč]\w*|"
    # El modelo del dron de la guerra: «Un obiect zburător de tip Shahed 138 (Geran 2)»
    # (EODI-2026-00171); el lituano «bepiločio orlaivio» (EODI-2026-00037).
    r"shahed\w*|geran\w*|gerbera\w*|"
    # «dos aeronaves no tripuladas» (EODI-2026-00488): el dron sin la palabra dron.
    r"aeronaves? n(?:o|ão) tripulad\w*)",
    re.IGNORECASE,
)
# La autoridad lo deja abierto: posible, presunto o sospechoso; objeto no identificado; se
# investiga si era un dron; no confirma que lo fuera.
ABIERTO = re.compile(
    r"(?<!\w)(?:possibl\w*|posibl\w*|posibil\w*|possív\w*|mogelijk\w*|möglich\w*|eventuel\w*|"
    r"potenziel\w*|potential\w*|potencial\w*|potentiel\w*|"
    r"mulig\w*|möjlig\w*|mahdollis\w*|możliw\w*|ewentualn\w*|pravděpodob\w*|tikėtin\w*|"
    r"galim\w*|iespējam\w*|võimalik\w*|πιθαν\w*|можлив\w*|возможн\w*|"
    r"mutma\w*|vermut\w*|vermoed\w*|presunt\w*|présum\w*|supuest\w*|alleged\w*|"
    r"suspect\w*|sospech\w*|verdacht\w*|podejrzan\w*|misstänk\w*|mistænk\w*|mistenk\w*|"
    r"formod\w*|mistank\w*|misstank\w*|afkræft\w*|hverken|denken|denkt|resembl\w*|parecid\w*|przypominaj\w*|unidentified|"
    r"no identificad\w*|non identifi\w*|niet[- ]ge(?:ï|i)dentificeerd\w*|"
    r"nicht identifiziert\w*|unbekannte[snm]? (?:flug)?objekt\w*|onbekend\w* object\w*|"
    r"niezidentyfikowan\w*|oidentifier\w*|uidentificer\w*|uidentifiser\w*|"
    r"investigat\w* whether|se investiga si|investiga si|onderzo\w* of|ermittel\w* ob|"
    r"unclear|no está claro|nicht klar|niet duidelijk|pas clair|"
    r"(?:no|not|nicht|niet|pas|ikke|inte|nie)\s+(?:\w+\s+){0,3}"
    r"(?:confirm|bestätig|bevestig|bekræft|bekräft|potwierdz|confirmar)\w*)(?!\w)",
    re.IGNORECASE,
)
# Confianza de la afirmación de presencia que deja la regla: la frase es literal, comprobada
# en el texto de la noticia (validas), y la regla no interpreta nada más.
CONFIANZA_REGLA = 1.0
CONFIRMAN = frozenset({"incidente", "drones"})


def _normal(texto: str) -> str:
    return " ".join(texto.lower().split())


@cache
def _no_autoridades() -> re.Pattern[str]:
    datos = json.loads(RUTA_NO_AUTORIDADES.read_text(encoding="utf-8"))
    partes = [
        re.escape(normalizar(e.rstrip("*"))) + (r"\w*" if e.endswith("*") else "")
        for e in datos["expresiones"]
    ]
    return re.compile(r"\b(?:" + "|".join(partes) + r")\b")


def no_es_autoridad(nombre: str) -> bool:
    """Un colectivo profesional, un sindicato o una asociación: no es una autoridad."""
    return bool(_no_autoridades().search(normalizar(nombre)))


_CITADA = re.compile(r"^(?P<autoridad>.+) \(declaración oficial citada en .+\)$")


def de_autoridad(fuente: Documento) -> bool:
    """La fuente es la palabra de una autoridad: no la de un colectivo que se guardó como tal antes
    de la regla (EODI-2025-00190, «Controladores Aéreos de España (declaración oficial citada en
    abc.es)»)."""
    medio = str(fuente.get("medio", ""))
    citada = _CITADA.match(medio)
    return (
        bool(fuente.get("es_autoridad"))
        and not no_es_autoridad(citada["autoridad"] if citada else medio)
        and not cita_vacia(fuente)
    )


def cita_vacia(fuente: Documento) -> bool:
    """Una fuente de autoridad cuya cita no dice nada: solo quién habla y el verbo de decir
    (EODI-2026-00648). No vale como declaración: ni confirma el estado ni la presencia."""
    return bool(fuente.get("es_autoridad")) and sin_afirmacion(
        str(fuente.get("frase_origen") or "")
    )


def validas(declaraciones: Sequence[dict[str, Any]], textos: Sequence[str]) -> list[dict[str, Any]]:
    """Las declaraciones cuya frase está en el texto de su fuente, con la frase recortada. Una
    frase que solo dice quién habla («… przekazała») se cambia por lo que dijo, si el texto lo
    trae detrás, o la declaración no vale."""
    resultado = []
    for declaracion in declaraciones:
        numero = declaracion.get("fuente")
        frase = str(declaracion.get("frase", ""))
        if not isinstance(numero, int) or not 1 <= numero <= len(textos) or not frase.strip():
            continue
        if _normal(frase) not in _normal(textos[numero - 1]):
            continue
        palabras = frase.split()[:MAX_PALABRAS_FRASE]
        if remite(" ".join(palabras)) and not habla_de_drones(" ".join(palabras)):
            # «Das teilte die Polizei Offenburg mit.»: lo que dijo es la oración de antes.
            anterior = _con_lo_anterior(" ".join(palabras), textos[numero - 1])
            if anterior is not None:
                palabras = anterior.split()
        if sin_afirmacion(" ".join(palabras)):
            # Solo quién habla: vale lo que dijo, si el texto lo trae detrás; si no, nada.
            contenido = _con_contenido(" ".join(palabras), textos[numero - 1])
            if contenido is None:
                continue
            palabras = contenido.split()
        resultado.append({**declaracion, "frase": " ".join(palabras)})
    return resultado


# Verbos de decir (y de confirmar) con que acaba una cita que no dice nada: solo quién habla
# («Podinsp. Marta Sulowska z Komendy Stołecznej Policji przekazała», EODI-2026-00648).
_DECIR = (
    r"dijo|declaró|afirmó|explicó|informó|señaló|indicó|aseguró|confirmó|añadió|precisó|detalló|"
    r"comunicó|manifestó|apuntó|said|says|stated|states|told|explained|reported|added|"
    r"confirmed|announced|noted|declared|sagte|sagt|erklärte|erklärt|teilte mit|bestätigte|"
    r"berichtete|betonte|sagte am \w+|a déclaré|a dit|a indiqué|a précisé|a expliqué|"
    r"a confirmé|a affirmé|déclare|indique|précise|explique|ha dichiarato|ha detto|ha spiegato|"
    r"ha confermato|ha riferito|ha affermato|dichiara|spiega|przekazała|przekazał|oznajmiła|"
    r"oznajmił|powiedziała|powiedział|poinformowała|poinformował|potwierdziła|potwierdził|"
    r"wyjaśniła|wyjaśnił|dodała|dodał|przekazuje|mówi|zei|zegt|verklaarde|meldde|liet weten|"
    r"bevestigde|sagde|siger|oplyste|oplyser|udtalte|bekræfter|bekræftede|sa|sier|opplyser|"
    r"opplyste|säger|uppgav|uppger|bekräftade|disse|afirmou|declarou|explicou|informou|"
    r"confirmou|a declarat|a spus|a precizat|a explicat|a confirmat|a transmis|sakė|teigė|"
    r"pranešė|patvirtino|sacīja|paziņoja|ütles|teatas|sanoi|kertoi|řekl|řekla|uvedl|uvedla|"
    r"sdělil|sdělila|povedal|povedala|uviedol|uviedla|заявив|заявила|повідомив|повідомила|"
    r"сказав|сказала|заявил|сообщил|сообщила|сказал|δήλωσε|ανέφερε|mondta|közölte|заяви|"
    r"каза|съобщи"
)
_SIN_AFIRMACION = re.compile(
    rf"^[^,;:\"«»“”„]{{0,160}}?(?<!\w)(?:{_DECIR})(?!\w)"
    r"(?:\s+(?:[\"„“«][^\"”»]{0,40}[\"”»]|w rozmowie z \S+|to \S+|a \S+|à \S+))?"
    r"[\s:,.…\"»”–—-]*$",
    re.IGNORECASE,
)


def sin_afirmacion(frase: str) -> bool:
    """La cita no afirma nada: solo quién habla y el verbo de decir, sin lo que dijo («… z Komendy
    Stołecznej Policji przekazała», «The police said:»). Una declaración así no confirma el
    estado ni la presencia hasta tener una cita con contenido."""
    return bool(_SIN_AFIRMACION.match(frase.strip()))


# Una cita que remite a la oración anterior: «Das teilte die Polizei Offenburg mit.»
# (EODI-2025-00027), «Dies bestätigte die Innenministerin», «This was confirmed by the police».
_REMITE = re.compile(
    rf"^\W*(?:das|dies|dieses|this|that|esto|eso|ello|dat|dit|det|cela|ceci|questo|ciò|to|"
    rf"acest\w*)(?!\w).{{0,80}}?(?<!\w)(?:{_DECIR}|teilte|bestätigt\w*|meldet\w*|mitteilt\w*)"
    rf"(?!\w)",
    re.IGNORECASE,
)
MAX_PALABRAS_REMITE = 12


def remite(frase: str) -> bool:
    """La cita solo dice quién lo dijo de lo que cuenta la oración anterior."""
    return len(frase.split()) <= MAX_PALABRAS_REMITE and bool(_REMITE.match(frase.strip()))


def _con_lo_anterior(frase: str, texto: str) -> str | None:
    """La oración anterior seguida de la cita que remite a ella, literal y con como mucho
    MAX_PALABRAS_FRASE palabras (las primeras de la anterior se quitan si no caben). None si el
    texto no trae la oración anterior o si no nombra drones."""
    patron = r"\s+".join(re.escape(p) for p in frase.split())
    encontrada = re.search(patron, texto, re.IGNORECASE)
    if encontrada is None:
        return None
    antes = re.split(r"(?<=[.!?])\s+", texto[: encontrada.start()].strip())[-1]
    if not habla_de_drones(antes):
        return None
    caben = MAX_PALABRAS_FRASE - len(frase.split())
    union = " ".join([*antes.split()[-caben:], *frase.split()])
    if not habla_de_drones(union) or _normal(union) not in _normal(texto):
        return None
    return union


def _con_contenido(frase: str, texto: str) -> str | None:
    """Lo que dijo quien habla en una cita partida: la frase del texto que sigue al verbo de decir
    (hasta el final de la oración, como mucho MAX_PALABRAS_FRASE palabras), literal. None si el
    texto no lo trae."""
    patron = r"\s+".join(re.escape(p) for p in frase.split())
    encontrada = re.search(patron, texto, re.IGNORECASE)
    if encontrada is None:
        return None
    resto = texto[encontrada.end() :]
    # Lo que sigue al verbo: el destinatario entre comillas y «że», «que», «that», «dass»…
    inicio = re.match(r"[\s:,]*(?:[\"„“«][^\"”»]{0,40}[\"”»][\s,]*)?"
                      r"(?:(?:że|ze|que|that|dass|che|dat|at|att|kad|jog)(?!\w)|qu')?\s*",
                      resto)  # fmt: skip
    resto = resto[inicio.end() if inicio else 0 :]
    oracion = re.split(r"(?<=[.!?])\s|\n", resto, maxsplit=1)[0].strip(' "”»')
    contenido = " ".join(oracion.split()[:MAX_PALABRAS_FRASE]).rstrip(",;:")
    if len(contenido.split()) < 3:
        return None
    return contenido if _normal(contenido) in _normal(texto) else None


def habla_de_drones(frase: str) -> bool:
    return bool(filtro().dron.search(frase) or _DRONES_DECLINADOS.search(frase))


# La sospecha de una infracción («mistanke om ulovlig droneflyvning», «suspected of illegally
# flying a drone») no deja abierto que fuera un dron: lo que se sospecha es que fuera ilegal.
_INFRACCION = re.compile(
    r"^\W*(?:\w+\W+){0,2}(?:ulovlig\w*|olaglig\w*|ulovlig|illegal\w*|ilegal\w*|"
    r"unerlaubt\w*|verboten\w*|illegaal|nielegaln\w*|unlawful\w*|unauthori[sz]ed)",
    re.IGNORECASE,
)


# La sospecha sobre quién está detrás («Bulgaria said it suspected Russia was behind a series of
# devastating drone attacks», EODI-2026-00559) no deja abierto que fueran drones: lo abierto es
# el autor (la atribución tiene su propio estado).
_AUTOR = re.compile(
    r"^\W*(?:\w+\W+){0,3}(?:was|were|is|are|of\s+being|to\s+be|estaba|estaban|está|steck\w*)"
    r"\s+(?:behind|responsible|dahinter|verantwortlich|detrás|responsable\w*)",
    re.IGNORECASE,
)
# Tampoco la duda sobre su procedencia: «aparatul ar fi posibil de proveniență rusească»
# (EODI-2026-00238): lo abierto es de dónde venía, no que fuera un dron.
_PROCEDENCIA = re.compile(
    r"^\W*(?:\w+\W+){0,2}(?:de\s+proveniență|de\s+proveniența|of\s+\w+\s+origin|"
    r"russischer\s+herkunft|de\s+origen|di\s+provenienza|d['’]origine|"
    r"rosyjskiego\s+pochodzenia|from\s+russia|russian-made|rusesc\w*|rusească)",
    re.IGNORECASE,
)


def abierto(*textos: str) -> bool:
    """Si alguno de los textos deja abierto que fuera un dron."""
    for texto in textos:
        for duda in ABIERTO.finditer(texto or ""):
            despues = texto[duda.end() : duda.end() + 40]
            if not any(r.search(despues) for r in (_INFRACCION, _AUTOR, _PROCEDENCIA)):
                return True
    return False


# El dron negado: «no drone was detected on radar» (EODI-2025-00203), «n'avaient permis de
# retrouver aucun drone» (EODI-2025-00357). Nombrarlo así no lo atribuye a un dron.
_DRON_NEGADO = re.compile(
    r"(?<!\w)(?:no|not\s+a|kein\w*|aucun\w*|ingen|geen|żadn\w*|nessun\w*|ningún|ninguna?|"
    r"nici\s+o|nicio)\s+(?:\w+\s+)?(?:drones?|drohne\w*|dron\w*|droner?|droon\w*|drony)(?!\w)",
    re.IGNORECASE,
)


# Lo que niega una autoridad: una negación seguida, en pocas palabras, de lo negado.
_NEGACION = re.compile(
    r"(?<!\w)(?:no|not|nothing|none|never|kein\w*|nicht|nichts|niet|geen|ingen|inte|ikke|"
    r"aucun\w*|pas|rien|non|nessun\w*|niente|nie|żadn\w*|brak|nu|nici\w*|ningún|ninguna?|"
    r"nada|nunca|não|nenhum\w*|няма|не|нет|δεν|καμία|nėra|nav|ei|nincs|není|nema)(?!\w)",
    re.IGNORECASE,
)
# Negar el peligro o el problema de seguridad no es negar el dron: «няма проблем» (el director
# del aeropuerto de Sofía, EODI-2025-00124), «no danger to the public».
_PELIGRO = re.compile(
    r"^\W*(?:(?:hay|había|existe|existía|is|was|there|any|ein\w*|une?|any|hubo|ha|"
    r"habido|of|a|de|di|za|ani|e|există|a\s+fost|niciun\w*|real|immediate|immediata|"
    r"inmediato|unmittelbar\w*|größer\w*|grave|serio|serious)\W+){0,3}"
    r"(?:peligro\w*|riesgo\w*|amenaza\w*|problema\w*|danger\w*|threat\w*|risk\w*|"
    r"problem\w*|safety|security|gefahr\w*|bedrohung\w*|risiko\w*|gevaar\w*|dreiging\w*|"
    r"fare\w*|trussel\w*|fara\w*|hot\w*|risque\w*|menace\w*|pericol\w*|minacci\w*|"
    r"rischi\w*|zagrożeni\w*|niebezpiecz\w*|amenințar\w*|опасност\w*|заплах\w*|"
    r"проблем\w*|κίνδυν\w*|απειλ\w*)",
    re.IGNORECASE,
)


def niega(frase: str) -> bool:
    """La frase niega algo que no es solo el peligro: «no hay peligro», «няма проблем», «no
    safety issue» no niegan el dron ni el suceso; «è prematuro correlare l'episodio a una azione
    di Mosca» (EODI-2025-00206) no niega nada. Que el dron no se encontrara después tampoco lo
    niega (presencia.NO_HALLADO: «n'avaient permis de retrouver aucun drone», EODI-2025-00357)."""
    from proceso.presencia import NO_HALLADO

    if NO_HALLADO.search(frase):
        return False
    return any(not _PELIGRO.match(frase[m.end() : m.end() + 60]) for m in _NEGACION.finditer(frase))


def atribuye_dron(frase: str) -> bool:
    """La frase de una autoridad atribuye lo que pasó a un dron: lo nombra sin negarlo y sin
    dejarlo abierto. Una medida que no lo nombra («au fost suspendate temporar aterizările»,
    EODI-2025-00049) o una confirmación sin contenido («bestätigte den Vorfall») no basta."""
    return habla_de_drones(_DRON_NEGADO.sub(" ", frase)) and not abierto(frase)


def confirma_dron(declaracion: dict[str, Any], contexto: str = "") -> bool:
    """Si la autoridad da por hecho el dron: su frase lo nombra sin negarlo (atribuye_dron) y
    afirma que hubo drones (drones), o confirma o atribuye el suceso (incidente, autoria) una
    autoridad competente. Una medida o una confirmación que no nombra el dron no lo atribuye.
    No si la frase o el `contexto` (la frase de la noticia que la cita) lo dejan abierto."""
    if abierto(str(declaracion.get("frase", "")), contexto):
        return False
    if not atribuye_dron(str(declaracion.get("frase", ""))):
        return False
    if declaracion["afirma"] == "drones":
        return True
    return (
        declaracion["afirma"] in _CON_DRONES
        and declaracion.get("categoria") in AUTORIDADES_DEL_DRON
    )


def afirmacion_presencia(fuente_id: str) -> Documento:
    """Quién confirma la presencia del dron: queda en el incidente y en su historial."""
    return {
        "campo": "presencia_dron",
        "valor": "confirmada",
        "fuente_id": fuente_id,
        "confianza_extraccion": CONFIANZA_REGLA,
    }


def confirmar_presencia(incidente: Documento, fuente_id: str, expresa: bool = False) -> bool:
    """Deja la presencia confirmada por esa fuente. False si ya lo estaba, o si estaba
    descartada y la declaración no afirma expresamente los drones."""
    actual = incidente.get("presencia_dron")
    if actual == "confirmada" or (actual == "descartada" and not expresa):
        return False
    incidente["presencia_dron"] = "confirmada"
    afirmacion = afirmacion_presencia(fuente_id)
    if afirmacion not in incidente.get("afirmaciones", []):
        incidente["afirmaciones"] = [*incidente.get("afirmaciones", []), afirmacion]
    return True


def fuente(declaracion: dict[str, Any], noticia: Documento, numero: int) -> Documento:
    resultado = copy.deepcopy(noticia)
    resultado.update({
        "id": f"{noticia['id']}-declaracion-{numero}",
        "medio": f"{declaracion['autoridad']} (declaración oficial citada en {noticia['medio']})",
        "fiabilidad": FIABILIDAD,
        "credibilidad": int(Credibilidad.CONFIRMADO),
        "frase_origen": declaracion["frase"],
        "replicas": 0,
        "campos_respaldados": ["estado", "presencia_dron"],
        "es_autoridad": True,
    })  # fmt: skip
    return resultado


def _transitar(incidente: Documento, destino: Estado, origen: Documento) -> None:
    if incidente["estado"]["actual"] == destino:
        return
    fuentes = {f["id"]: f for f in incidente["fuentes"]}
    # Un cambio que la máquina de estados no permite (revertir un desmentido de más
    # fiabilidad, atribuir sin confirmar) se deja sin hacer.
    with contextlib.suppress(TransicionNoPermitida):
        incidente["estado"] = transitar(
            incidente["estado"], destino, origen["fecha"], origen["id"], fuentes
        )


def aplicar(
    incidente: Documento, declaraciones: Sequence[dict[str, Any]], enviadas: Sequence[str]
) -> Documento:
    """El incidente con las declaraciones como fuentes y sus cambios de estado y presencia."""
    resultado = copy.deepcopy(incidente)
    por_enlace = {f["enlace"]: f for f in resultado["fuentes"]}
    nuevas: list[tuple[dict[str, Any], Documento]] = []
    for numero, declaracion in enumerate(declaraciones, 1):
        noticia = por_enlace.get(enviadas[declaracion["fuente"] - 1])
        pais = str(declaracion.get("pais") or "").strip().upper()
        if noticia is None:
            continue
        if pais and pais != resultado["lugar"]["pais"]:
            continue
        nuevas.append((declaracion, fuente(declaracion, noticia, numero)))
    return _aplicar_nuevas(resultado, nuevas, por_enlace)


def aplicar_fuentes(
    incidente: Documento, pares: Sequence[tuple[dict[str, Any], Documento]]
) -> Documento:
    """El incidente con declaraciones que llegan ya con su fuente (una página oficial leída
    directamente, recogida/declaraciones_oficiales.py): las mismas reglas que las declaraciones
    que encuentra el extractor en las noticias. Una fuente que el incidente ya tiene no se vuelve
    a aplicar, salvo una autoría que el incidente no lleva: al unir dos fichas, la que queda recibe
    las fuentes oficiales de la otra pero no su atribución (EODI-2026-00211, atribuida por la
    Presidencia de Rumanía, unida el 14 de octubre de 2026 en la EODI-2026-00187, que quedó
    «confirmada»). Una autoridad de otro país no cambia el incidente."""
    resultado = copy.deepcopy(incidente)
    por_enlace = {f["enlace"]: f for f in resultado["fuentes"]}
    tiene = {f["id"] for f in resultado["fuentes"]}
    sin_autoria = resultado["estado"]["actual"] != atribucion.ESTADO_ATRIBUIDO
    nuevas = [
        (declaracion, fuente) for declaracion, fuente in pares
        if (fuente["id"] not in tiene or (declaracion["afirma"] == "autoria" and sin_autoria))
        and str(declaracion.get("pais") or resultado["lugar"]["pais"]).strip().upper()
        == resultado["lugar"]["pais"]
    ]  # fmt: skip
    return _aplicar_nuevas(resultado, nuevas, por_enlace)


def _negacion_que_cede(
    incidente: Documento,
    declaracion: dict[str, Any],
    origen: Documento,
    categorias: dict[str, str],
) -> Documento | None:
    """El incidente con la negación anotada si la niega una autoridad que cede ante la
    competente que lo confirmó; None si la negación vale como desmentido."""
    if not competencia.cede(str(declaracion.get("autoridad", "")), declaracion.get("categoria")):
        return None
    prevalece = competencia.confirmacion_que_prevalece(incidente, categorias)
    if prevalece is None:
        return None
    return competencia.anotar_negacion(incidente, origen, prevalece)


def _aplicar_nuevas(
    resultado: Documento,
    nuevas: Sequence[tuple[dict[str, Any], Documento]],
    por_enlace: dict[str, Documento],
) -> Documento:
    # Quien no es una autoridad no cambia nada: ni entra como declaración.
    nuevas = [(d, o) for d, o in nuevas if not no_es_autoridad(str(d.get("autoridad", "")))]
    tiene = {f["id"] for f in resultado["fuentes"]}
    resultado["fuentes"] = [*resultado["fuentes"], *(f for _, f in nuevas if f["id"] not in tiene)]
    # Primero lo que confirma y después lo que desmiente o atribuye.
    orden = {"incidente": 0, "drones": 0, "sin_drones": 1, "niega_incidente": 2, "autoria": 3}
    # La categoría de cada declaración nueva, para saber cuál es competente (competencia.py).
    categorias = {origen["id"]: str(d.get("categoria") or "") for d, origen in nuevas}
    por_frase: list[Documento] = []
    for declaracion, origen in sorted(nuevas, key=lambda n: orden[n[0]["afirma"]]):
        afirma = declaracion["afirma"]
        if afirma in CONFIRMAN:
            _transitar(resultado, Estado.CONFIRMADO, origen)
        contexto = str(por_enlace.get(origen["enlace"], {}).get("frase_origen", ""))
        if afirma == "drones" and confirma_dron(declaracion, contexto):
            # Lo afirma expresamente: vale aunque la ficha lo hubiera descartado.
            confirmar_presencia(resultado, origen["id"], expresa=True)
        elif confirma_dron(declaracion, contexto):
            por_frase.append(origen)
        if afirma == "sin_drones":
            resultado["presencia_dron"] = "descartada"
        elif afirma == "niega_incidente" and not niega(str(declaracion.get("frase", ""))):
            # No niega nada (solo el peligro, o la atribución): no es un desmentido.
            pass
        elif afirma == "niega_incidente" and (
            anotado := _negacion_que_cede(resultado, declaracion, origen, categorias)
        ):
            # Lo niega quien no es competente y lo confirmó quien sí: sigue confirmado, con la
            # negación en el historial.
            resultado = anotado
        elif afirma == "niega_incidente":
            _transitar(resultado, Estado.DESMENTIDO, origen)
            if resultado["estado"]["actual"] == Estado.DESMENTIDO:
                resultado["control"]["motivo_desmentido"] = (
                    f"{declaracion['autoridad']}: «{declaracion['frase']}»"
                )
        elif afirma == "autoria" and declaracion["categoria"] in atribucion.CATEGORIAS:
            actor = str(declaracion.get("autor", "")).strip()
            # Solo si la autoridad lo afirma con sus propias palabras, sin duda ni investigación,
            # y el autor no es quien declara (proceso/atribucion.py); si no, no hay atribución.
            decision = atribucion.evaluar(
                actor, str(declaracion.get("frase", "")), declaracion.get("autor_tipo"),
                declaracion.get("autor_pais"), literal=declaracion.get("cita_literal"),
                situacion=declaracion.get("autor_situacion"),
                declarantes=[str(declaracion["autoridad"])],
            )  # fmt: skip
            clase = decision.clase
            if clase is not None and resultado["estado"]["actual"] == Estado.CONFIRMADO:
                _transitar(resultado, Estado.ATRIBUIDO, origen)
            if clase is not None and resultado["estado"]["actual"] == Estado.ATRIBUIDO:
                resultado["atribucion"] = {
                    "actor": actor,
                    "autoridad": declaracion["autoridad"],
                    "fecha": origen["fecha"],
                    **clase,
                }
    # Lo que las autoridades dicen que investigan va a la ficha como investigación en curso,
    # sin cambiar el estado.
    if encontradas := atribucion.investigaciones(resultado):
        resultado["investigacion"] = encontradas
    # La frase que nombra drones confirma su presencia si nadie los descartó y el incidente no
    # está desmentido: una autoridad que dice que no pasó nada pesa más que la que lo cuenta.
    if resultado["estado"]["actual"] != Estado.DESMENTIDO:
        for origen in por_frase:
            if confirmar_presencia(resultado, origen["id"]):
                break
    return resultado
