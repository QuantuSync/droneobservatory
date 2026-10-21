"""Presencia del dron: si la autoridad competente lo da por hecho, está confirmada.

Dos valores para los incidentes vigentes (además de descartada, que no se toca):

- confirmada: una autoridad (gestor aeroportuario, gestor de navegación aérea, policía, fuerzas
  armadas, ministerio, gobierno, fiscalía, autoridad de aviación civil) dice que lo que se vio,
  detectó, derribó o causó el efecto era un dron: su declaración citada lo nombra
  (proceso/declaraciones.atribuye_dron). No se piden restos, grabación ni detección por sensor;
- no_confirmada: la propia autoridad lo deja abierto («posible dron», «objeto no
  identificado», «se investiga si era un dron»), actúa sin atribuirlo (un cierre, cazas o una
  patrulla no son atribución: desde el 21 de octubre de 2026 la actuación ya no la confirma) o
  solo lo cuentan la prensa o los testigos. La confirmada sin base pasa a no_confirmada
  (quitar_sin_base), salvo las dudosas (dudosa_por), que van al experto.

Si una fuente cuenta que se buscó el dron y no se encontró («allerdings konnte eine Drohne nicht
gefunden werden», «Politiet fandt ingen droner»), la presencia no puede quedar confirmada: ni
la regla la confirma ni se conserva la confirmación que hubiera. Solo la mantienen una autoridad
que atribuye el suceso a un dron en la declaración con que se confirmó («la policía confirmó el
avistamiento, pero no encontró el dron»), las pruebas físicas que confirma una autoridad
(restos, derribo, explosión) y el documento propio de una autoridad, que mandan sobre la prensa.

La revisión vuelve a leer las declaraciones de las extracciones guardadas y las frases de las
fuentes, sin llamar al extractor ni descargar nada, y confirma la presencia de los incidentes
que el criterio alcanza; ajusta después el titular (proceso/titulares.py). Lo que dice una
autoridad en su propio documento (proceso/detalle.py) manda. Nada se borra: cada cambio entra
como versión nueva del incidente, con la afirmación de presencia_dron y su fuente, y el motivo
queda en el historial. Es idempotente: la recogida horaria la ejecuta en cada pasada.
"""

import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import cache
from pathlib import Path
from typing import Any

from almacen.base import Almacen, DocumentoInvalido
from esquema import Documento
from proceso import competencia, declaraciones, incidentes, titulares
from proceso.estados import Estado
from proceso.incidentes import CONFIRMADOS, PRUEBAS_FISICAS, activo, id_fuente

TABLA_MOTIVOS = "incidentes_motivos"
REVISADOS = Path(__file__).resolve().parent.parent / "configuracion" / "incidentes_revisados.json"


@dataclass(frozen=True)
class Cambio:
    incidente: str
    fuente_id: str
    autoridad: str
    categoria: str
    afirma: str
    frase: str

    @property
    def motivo(self) -> str:
        if self.afirma == "actuacion":
            return (
                "criterio de presencia: la autoridad actúa por un dron (cierre o intervención) "
                f"y lo cuenta la fuente: «{self.frase}»"
            )
        return (
            f"criterio de presencia: {self.autoridad} ({self.categoria}, declaración "
            f"«{self.afirma}») atribuye el suceso a un dron: «{self.frase}»"
        )


def documento_oficial_decide(incidente: Documento) -> bool:
    """Una autoridad dice algo de la presencia en su propio documento: manda."""
    return any(
        f.get("documento_oficial") and "presencia_dron" in f.get("campos_respaldados", [])
        for f in incidente["fuentes"]
    )


def atribuida_por_autoridad(incidente: Documento) -> bool:
    """Una autoridad atribuye el suceso a drones: una declaración suya habla de drones sin dejarlo
    abierto (lo que dice en su propio documento lo cubre documento_oficial_decide). Que después no
    se encontraran (EODI-2025-00066, Volkel: Defensa dispara a los drones y «no fueron
    encontrados») no lo cambia: no encontrar pruebas no demuestra que no hubiera dron. Una
    declaración que no nombra el dron («un objeto misterioso», EODI-2026-00515) no basta."""
    return any(
        declaraciones.de_autoridad(f)
        and declaraciones.atribuye_dron(str(f.get("frase_origen") or ""))
        for f in incidente["fuentes"]
    )


def autoridad_lo_deja_abierto(incidente: Documento) -> bool:
    """Todas las autoridades que cita el incidente lo dejan abierto."""
    autoridades = [f for f in incidente["fuentes"] if declaraciones.de_autoridad(f)]
    return bool(autoridades) and all(
        declaraciones.abierto(str(f.get("frase_origen", ""))) for f in autoridades
    )


# Medidas de una autoridad por el dron (respuesta.medidas): intervención policial, cazas,
# derribo, inhibición, cierre del espacio aéreo.
MEDIDAS_DE_AUTORIDAD = frozenset(
    {"cierre_espacio_aereo", "patrulla", "cazas", "derribo", "inhibicion"}
)


# Las fuentes dan otra causa (globos): el cierre no es por un dron.
OTRA_CAUSA = re.compile(
    r"(?<!\w)(?:globos?|balloons?|ballons?|ballone?|αερόστατ\w*|μπαλόνι\w*|balion\w*|"
    r"balon\w*|baloane|baloanele|ballong\w*|ilmapallo\w*)(?!\w)",
    re.IGNORECASE,
)


def otra_causa(incidente: Documento) -> bool:
    """Alguna fuente o el titular dan otra causa que un dron (globos sobre Vilna)."""
    textos = [str(f.get("frase_origen", "")) for f in incidente["fuentes"]]
    textos += [str(v) for v in (incidente.get("titulo") or {}).values()]
    return any(OTRA_CAUSA.search(texto) for texto in textos)


# Una fuente cuenta que se buscó el dron y no se encontró, o que no se vio ninguno. Cada forma
# lleva el nombre del dron: «No Drone Debris Found» (restos) o «nu a fost detectat de radare»
# (radar) no dicen que no hubiera dron.
_DRON = (
    r"(?:drohne\w*|drones?|drone\w*|dron\w*|drön\w*|drón\w*|droon\w*|drony|lennok\w*|"
    r"дрон\w*|беспилотник\w*|безпілотник\w*)"
)
NO_HALLADO = re.compile(
    r"(?<!\w)(?:"
    rf"{_DRON}\s+(?:\w+\s+){{0,3}}nicht\s+(?:\w+\s+)?(?:gefunden|entdeckt|aufgefunden|"
    r"gesichtet|festgestellt|ausgemacht|lokalisiert)"
    rf"|keine?n?\s+{_DRON}\s+(?:\w+\s+){{0,2}}(?:gefunden|entdeckt|aufgefunden|gesichtet|"
    r"festgestellt|gesehen|zu\s+sehen|ausgemacht|lokalisiert)"
    rf"|no\s+{_DRON}\s+(?:was|were|has\s+been|had\s+been|could\s+be)?\s*"
    r"(?:found|located|spotted|seen|sighted)"
    rf"|(?:found|spotted|saw|located|find)\s+no\s+{_DRON}"
    rf"|(?:did\s+not|didn't|could\s+not|couldn't|failed\s+to)\s+(?:find|locate)\s+"
    rf"(?:the|a|any)\s+{_DRON}"
    rf"|{_DRON}\s+(?:was|were|could)\s+not\s+(?:be\s+)?(?:found|located)"
    rf"|no\s+trace\s+of\s+(?:the|a|any)\s+{_DRON}"
    rf"|no\s+se\s+(?:encontr\w+|hall\w+|localiz\w+|vio|vieron)\s+"
    rf"(?:ningún|ningun|el|un|los|ni\s+rastro\s+del?)\s+{_DRON}"
    rf"|ningún\s+{_DRON}|sin\s+rastro\s+del\s+{_DRON}"
    rf"|no\s+(?:encontraron|hallaron|localizaron)\s+(?:ningún|ningun|el|un|los)\s+{_DRON}"
    rf"|aucun\s+{_DRON}|(?:trouvé|retrouvé|repéré|localisé)\s+(?:aucun|de)\s+{_DRON}"
    rf"|pas\s+de\s+{_DRON}\s+(?:\w+\s+){{0,2}}(?:trouvé|retrouvé|repéré|vu)"
    rf"|geen\s+{_DRON}\s+(?:\w+\s+){{0,2}}(?:gezien|gevonden|aangetroffen|waargenomen|"
    rf"gesignaleerd)|geen\s+{_DRON}\s+was"
    rf"|(?:fandt|fant|fann|observerte|observerede|så|såg|hittade|hittet|fundet)\s+ingen\s+{_DRON}"
    rf"|(?:ikke|inte)\s+(?:funnet|fundet|hittat|hittet)\s+(?:den|dronen|drönaren|{_DRON})"
    rf"|nie\s+(?:znaleziono|odnaleziono|zlokalizowano|odnaleźli|znaleźli)\s+(?:\w+\s+){{0,2}}"
    rf"{_DRON}|żadnego\s+drona|zadnego\s+drona"
    rf"|{_DRON}\s+nie\s+(?:został\w*|zostały)\s+(?:znalezion\w*|odnalezion\w*)"
    r"|nicio\s+dron\w*\s+nu\s+a\s+fost\s+(?:găsit\w*|gasit\w*|descoperit\w*|observat\w*)"
    rf"|{_DRON}\s+nu\s+a\s+fost\s+(?:găsit\w*|gasit\w*|localizat\w*|descoperit\w*)"
    rf"|{_DRON}\s+не\s+(?:был\w*\s+)?(?:найден\w*|обнаружен\w*)"
    rf"|не\s+(?:нашли|обнаружили|знайшли|виявили|знайдено)\s+(?:жодного\s+|никакого\s+)?{_DRON}"
    r"|δεν\s+βρέθηκε\s+(?:κανένα\s+)?(?:drone|μη\s+επανδρωμέν\w*)"
    rf"|{_DRON}\s+ei\s+(?:löydetty|löytynyt)|ei\s+löytynyt\s+(?:\w+\s+)?{_DRON}"
    rf"|{_DRON}\s+non\s+(?:è\s+stat[oa]\s+|sono\s+stati\s+)?(?:trovat\w|individuat\w|rinvenut\w)"
    rf"|nessun\s+{_DRON}\s+(?:\w+\s+){{0,2}}(?:trovat\w|individuat\w|avvistat\w|rinvenut\w)"
    rf"|nenhum\s+{_DRON}\s+(?:\w+\s+){{0,2}}(?:encontrad\w|localizad\w|avistad\w|detetad\w|"
    r"detectad\w)"
    rf"|{_DRON}\s+não\s+foi\s+(?:encontrad\w|localizad\w)"
    rf"|nu\s+a\s+fost\s+(?:găsit\w*|gasit\w*|identificat\w*|depistat\w*)\s+nicio\s+{_DRON}"
    rf"|(?:nerasta|neaptikta|nerado)\s+(?:jokio|jokių|jokį)\s+{_DRON}"
    rf"|{_DRON}\s+(?:nebuvo\s+rastas|nerastas|neaptiktas)"
    rf"|{_DRON}\s+netika\s+(?:atrast\w|atklāt\w|konstatēt\w)|neatrada\s+nevienu\s+{_DRON}"
    rf"|{_DRON}\s+ei\s+(?:leitud|tuvastatud)|ei\s+(?:leitud|leidnud)\s+(?:ühtegi\s+)?{_DRON}"
    rf"|ingen\s+{_DRON}\s+(?:\w+\s+){{0,2}}(?:hittades|upptäcktes|sågs|blev\s+fundet|"
    r"ble\s+funnet|ble\s+observert)"
    rf"|{_DRON}\s+(?:nebyl\w?|nebyly|nebol\w?|neboli)\s+(?:nalezen\w*|objeven\w*|nájden\w*|"
    r"objaven\w*)"
    rf"|(?:žádn|žiadn)\w+\s+{_DRON}\s+(?:\w+\s+){{0,2}}(?:nalezen\w*|nájden\w*|nenašl\w*)"
    rf"|nem\s+találták\s+(?:meg\s+)?a\s+{_DRON}|{_DRON}\s+nem\s+találták"
    rf"|{_DRON}\s+не\s+(?:е|беше|бе)\s+(?:открит\w*|намерен\w*)"
    rf"|{_DRON}\s+не\s+(?:було\s+)?(?:знайдено|виявлено)"
    r")(?!\w)",
    re.IGNORECASE,
)

# La fuente cuenta que se buscó y no se encontró nada («Zowel in de lucht als op de grond werd
# niets meer gevonden», EODI-2025-00248), sin nombrar el dron: la frase sale de una fuente del
# suceso, así que lo buscado es el dron. Revisadas a mano: «nada» o «rien» solos, «nulla di
# fatto» y «nichts Neues» no dicen que no se encontrara, y no entran.
NADA_HALLADO = re.compile(
    r"(?<!\w)(?:"
    # neerlandés
    r"ni(?:ets|ks)\s+(?:meer\s+|verdachts\s+)?(?:gevonden|aangetroffen|waargenomen|gezien)"
    r"|(?:vond|vonden|trof|troffen)\s+(?:\w+\s+)?ni(?:ets|ks)"
    # inglés
    r"|nothing\s+(?:more\s+|else\s+|suspicious\s+)?(?:was\s+|could\s+be\s+|has\s+been\s+)?"
    r"(?:found|located|spotted|seen|detected)"
    r"|(?:found|located|spotted|detected)\s+nothing"
    r"|(?:did\s+not|didn't|could\s+not|couldn't|failed\s+to)\s+(?:find|locate|spot|detect)\s+"
    r"anything"
    # alemán
    r"|nichts\s+(?:mehr\s+|Verdächtiges\s+|Auffälliges\s+)?(?:\w+\s+)?(?:gefunden|entdeckt|"
    r"festgestellt|gesichtet|aufgefunden|ausgemacht)"
    r"|(?:fanden|fand|entdeckten|stellten)\s+(?:\w+\s+){0,2}nichts"
    # francés
    r"|rien\s+(?:de\s+suspect\s+|de\s+plus\s+)?n['’]\s*a\s+été\s+(?:trouvé|retrouvé|découvert|"
    r"repéré|détecté|observé)"
    r"|n['’]\s*(?:a|ont|avons)\s+rien\s+(?:trouvé|retrouvé|découvert|repéré|détecté|observé)"
    # italiano
    r"|non\s+(?:è\s+stato|sono\s+stati|hanno|ha|abbiamo)\s+(?:trovato|rinvenuto|individuato|"
    r"rilevato|avvistato)\s+(?:nulla|niente)"
    r"|(?:nulla|niente)\s+(?:di\s+sospetto\s+)?(?:è\s+stato\s+)?(?:trovato|rinvenuto|"
    r"individuato|rilevato)"
    # polaco
    r"|(?:nic|niczego)\s+(?:więcej\s+|podejrzanego\s+)?nie\s+(?:znaleziono|odnaleziono|"
    r"znaleźli|wykryto|stwierdzono|zauważono)"
    r"|nie\s+(?:znaleziono|odnaleziono|znaleźli|wykryto|stwierdzono)\s+(?:już\s+)?(?:nic|niczego)"
    # rumano
    r"|nu\s+(?:a\s+fost|s-a|s-au|au|am)\s+(?:găsit|gasit|descoperit|identificat|depistat)\s+nimic"
    r"|nimic\s+(?:suspect\s+)?nu\s+a\s+fost\s+(?:găsit|gasit|descoperit|identificat|depistat)"
    # lituano
    r"|nieko\s+(?:daugiau\s+|įtartino\s+)?(?:nerasta|neaptikta|nebuvo\s+(?:rasta|aptikta))"
    r"|nerad(?:o|ome)\s+nieko"
    # letón
    r"|nekas\s+(?:vairs\s+|aizdomīgs\s+)?netika\s+(?:atrasts|atklāts|konstatēts)"
    r"|netika\s+(?:atrasts|atklāts|konstatēts)\s+nekas|neatrada\s+neko"
    # estonio
    r"|midagi\s+(?:rohkem\s+|kahtlast\s+)?ei\s+(?:leitud|tuvastatud|leidnud)"
    r"|ei\s+(?:leitud|leidnud|tuvastatud)\s+midagi"
    # finés
    r"|mitään\s+(?:muuta\s+|epäilyttävää\s+)?ei\s+(?:löydetty|löytynyt|havaittu)"
    r"|ei\s+(?:löydetty|löytynyt|havaittu|löytänyt|löytäneet)\s+mitään"
    # sueco, danés, noruego
    r"|(?:ingenting|inget|intet)\s+(?:mer\s+|mere\s+|misstänkt\s+|mistænkeligt\s+)?"
    r"(?:hittades|upptäcktes|kunde\s+hittas|blev\s+fundet|ble\s+funnet|ble\s+observert|"
    r"ble\s+påvist)"
    r"|(?:hittade|upptäckte|fann|fandt|fant|observerede|observerte)\s+(?:ingenting|inget|intet)"
    r"|fant\s+ikke\s+noe|ikke\s+noe\s+(?:ble\s+)?funnet|ikke\s+noget\s+(?:blev\s+)?fundet"
    # checo y eslovaco
    r"|nic\s+(?:dalšího\s+|podezřelého\s+)?(?:nebylo\s+(?:nalezeno|zjištěno|objeveno)|"
    r"se\s+nenašlo)"
    r"|nena(?:šli|šla|šel)\s+nic|nič\s+(?:viac\s+|podozrivé\s+)?(?:sa\s+nenašlo|"
    r"nebolo\s+(?:nájdené|zistené|objavené))"
    r"|nenašl\w+\s+nič"
    # húngaro
    r"|nem\s+talált(?:ak|unk)?\s+semmit|semmit\s+(?:sem\s+)?nem\s+találtak"
    # búlgaro
    r"|нищо\s+(?:подозрително\s+)?не\s+(?:беше|е|бе)\s+(?:открито|намерено|установено)"
    r"|не\s+(?:откриха|намериха|установиха)\s+нищо"
    # griego
    r"|δεν\s+(?:βρέθηκε|εντοπίστηκε|βρήκαν|εντόπισαν)\s+τίποτα"
    r"|τίποτα\s+(?:ύποπτο\s+)?δεν\s+(?:βρέθηκε|εντοπίστηκε)"
    # ucraniano y ruso
    r"|нічого\s+(?:підозрілого\s+)?не\s+(?:було\s+)?(?:знайдено|виявлено|знайшли|виявили)"
    r"|не\s+(?:знайшли|виявили|знайдено|виявлено)\s+нічого"
    r"|ничего\s+(?:подозрительного\s+)?не\s+(?:было\s+)?(?:найдено|обнаружено|нашли|обнаружили)"
    r"|не\s+(?:нашли|обнаружили|найдено|обнаружено)\s+ничего"
    # español y portugués
    r"|no\s+se\s+(?:encontr\w+|hall\w+|localiz\w+|detect\w+)\s+nada"
    r"|no\s+(?:encontraron|hallaron|localizaron|encontró|halló|detectaron)\s+nada"
    r"|nada\s+(?:sospechoso\s+)?fue\s+(?:encontrado|hallado|localizado)"
    r"|nada\s+(?:mais\s+|suspeito\s+)?foi\s+(?:encontrado|localizado|detetado|detectado)"
    r"|não\s+(?:foi\s+encontrado|se\s+encontrou|encontraram|encontrou|localizaram)\s+nada"
    r")(?!\w)",
    re.IGNORECASE,
)

# Lo que no se encontró era una persona, un vehículo o lo que se registró («bij de bestuurder
# werd niets gevonden», «nothing was found in the suspect's car»): no habla del dron.
_OTRA_BUSQUEDA = re.compile(
    r"(?<!\w)(?:sospechos\w*|suspect\w*|verdächtig\w*|tatverdächtig\w*|verdachte\w*|"
    r"podejrzan\w*|suspeit\w*|sospett\w*|bestuurder\w*|täter\w*|dader\w*|auto|car|vehicle|"
    r"vehículo|fahrzeug\w*|wohnung\w*|woning\w*|house|huiszoeking\w*|registro\s+domiciliario|"
    r"perquisition\w*)(?!\w)",
    re.IGNORECASE,
)


def dice_no_hallado(texto: str) -> bool:
    """La frase cuenta que no se encontró el dron o que no se vio ninguno, o que se buscó y no
    se encontró nada (sin decir que lo buscado fuera una persona o un vehículo)."""
    if NO_HALLADO.search(texto) and declaraciones.habla_de_drones(texto):
        return True
    return bool(NADA_HALLADO.search(texto)) and not _OTRA_BUSQUEDA.search(texto)


def no_hallado(incidente: Documento) -> Documento | None:
    """La primera fuente (por fecha) que cuenta que no se encontró el dron, o None."""
    fuentes = sorted(incidente.get("fuentes", []), key=lambda f: (f["fecha"]["valor"], f["id"]))
    return next((f for f in fuentes if dice_no_hallado(str(f.get("frase_origen", "")))), None)


def pruebas_fisicas_confirmadas(incidente: Documento) -> bool:
    """Una autoridad confirma el suceso y hay pruebas físicas del dron (restos, derribo...)."""
    evidencia = set((incidente.get("pruebas") or {}).get("evidencia", []))
    return bool(evidencia & PRUEBAS_FISICAS) and incidente["estado"]["actual"] in CONFIRMADOS


def _vuelos(valor: object) -> bool:
    """Hubo al menos un vuelo (un rango con mínimo mayor que cero)."""
    return isinstance(valor, dict) and isinstance(valor.get("min"), int) and valor["min"] > 0


def actua_la_autoridad(incidente: Documento) -> bool:
    """Una autoridad actuó por el suceso: cerró el aeropuerto o el espacio aéreo, desvió o
    canceló vuelos (el control aéreo), o intervino."""
    consecuencias = incidente.get("consecuencias") or {}
    cierre = (consecuencias.get("cierre") or {}).get("valor")
    medidas = set((incidente.get("respuesta") or {}).get("medidas") or [])
    return (
        cierre == "si"
        or bool(medidas & MEDIDAS_DE_AUTORIDAD)
        or _vuelos(consecuencias.get("vuelos_desviados"))
        or _vuelos(consecuencias.get("vuelos_cancelados"))
    )


# La policía acude, detiene, multa o decomisa por un dron: actúa por el dron.
DETENCION = re.compile(
    r"(?<!\w)(?:rykker (?:ut|til)|rykket (?:ut|til)|ryckte ut|rückt\w* aus|ausgerückt|"
    r"responding to|responded to|acudi\w*|interv(?:ino|inieron|ened|ention)|ruszy\w*|"
    r"detenid\w*|arrestad\w*|arrested|arrests?|festgenommen|festnahme\w*|"
    r"verhaftet|anholdt|pågrepet|innbrakt|gripen|zatrzyma\w*|aangehouden|opgepakt|aresta\w*|"
    r"interpel\w*|multad\w*|sancionad\w*|fined|bußgeld\w*|beboet|bötfäll\w*|"
    r"incautad\w*|decomisad\w*|seized|beschlagnahmt|in beslag)(?!\w)",
    re.IGNORECASE,
)


# La frase cuenta el cierre del aeropuerto o del espacio aéreo («wegen Drohnen gesperrt»).
CIERRE_EN_FRASE = re.compile(
    r"(?<!\w)(?:gesperrt|geschlossen|stillgelegt|eingestellt|lahmgelegt|lahmleg\w*|"
    r"unterbroch\w*|interrump\w*|interrupted|halted|umgeleitet|desviad\w*|diverted|"
    r"omdirigere\w*|omdirigert|tussenlanding|zwischenlandung|"
    r"cerrad\w*|cierr\w*|paraliz\w*|"
    r"closed|closure|shut|lukket|lukke\w*|stengt|stengte|stängd\w*|zamkni\w*|ferm[ée]\w*|"
    r"fermeture|stilgelegd|gesloten|chius\w*|[îi]nchis\w*|paralys\w*|suspendid\w*|"
    r"suspended|приостанов\w*|закрыт\w*|закрыл\w*|прекращ\w*|остановлен\w*|зачинен\w*|"
    r"закрил\w*|призупин\w*|gestaakt|buiten gebruik)(?!\w)",
    re.IGNORECASE,
)
# Una pista: su cierre es un cierre del aeropuerto, aunque el resto siga abierto (Schiphol,
# EODI-2025-00058: «приостанавливал работу взлетно-посадочной полосы из-за дрона»).
PISTA = re.compile(
    r"(?<!\w)(?:pista\w*|runway\w*|landebahn\w*|start- en landingsbaan|landingsbaan|"
    r"baan\b|piste\w*|взлетно-посадочн\w+\s+полос\w*|полос\w*|злітно-посадков\w+\s+смуг\w*|"
    r"pas\w*\s+startow\w*|banan)(?!\w)",
    re.IGNORECASE,
)
MOTIVO_PISTA = (
    "cierre de una pista por un dron registrado como cierre (la autoridad del aeropuerto actúa por "
    "el dron)"
)


def _cuenta_cierre_de_pista(texto: str) -> bool:
    return bool(
        PISTA.search(texto)
        and CIERRE_EN_FRASE.search(texto)
        and declaraciones.habla_de_drones(texto)
    )


def respaldo_cierre_de_pista(incidente: Documento) -> tuple[list[str], bool]:
    """De dónde sale el cierre de pista: las fuentes cuya frase cuenta que se cerró o se
    suspendió una pista por un dron, y si lo cuenta el titular (que sale de las noticias). Lo usa
    también la exportación para dar el origen de `consecuencias.cierre.valor`."""
    objetivo = (incidente.get("objetivo") or {}).get("categoria")
    if incidente.get("tipo") != "interrupcion_aeroportuaria" and objetivo != "aeropuerto":
        return [], False
    fuentes = [
        f["id"]
        for f in incidente.get("fuentes", [])
        if _cuenta_cierre_de_pista(str(f.get("frase_origen", "")))
    ]
    titulo = " ".join(str(v) for v in (incidente.get("titulo") or {}).values())
    return fuentes, _cuenta_cierre_de_pista(titulo)


def cierre_de_pista(incidente: Documento) -> Documento:
    """Una interrupción aeroportuaria (o un suceso en un aeropuerto) sin cierre registrado cuya
    fuente cuenta que se cerró o se suspendió una pista por un dron: el cierre de la pista es un
    cierre (`consecuencias.cierre` «si») y el suceso, una interrupción del aeropuerto. Así cuenta
    como actuación de la autoridad del aeropuerto para la presencia del dron."""
    consecuencias = incidente.get("consecuencias") or {}
    if (consecuencias.get("cierre") or {}).get("valor") not in (None, "desconocido"):
        return incidente
    fuentes, titulo = respaldo_cierre_de_pista(incidente)
    if not fuentes and not titulo:
        return incidente
    cierre = {**(consecuencias.get("cierre") or {}), "valor": "si"}
    # Con el cierre, el suceso es una interrupción del aeropuerto (manda ese tipo).
    return {**incidente, "tipo": "interrupcion_aeroportuaria",
            "consecuencias": {**consecuencias, "cierre": cierre}}  # fmt: skip


def por_actuacion(incidente: Documento) -> Documento | None:
    """La fuente que cuenta que la autoridad actuó por un dron (un cierre, una intervención
    policial, cazas, un derribo, una detención o una multa por volarlo): actúa atribuyendo el
    suceso a un dron. Con el cierre o la medida registrados basta la primera fuente que no lo
    deja abierto, aunque su frase no repita la palabra dron (el incidente es de un dron). None si
    no actuó o si las fuentes que nombran el dron lo dejan abierto."""
    if otra_causa(incidente) or no_hallado(incidente) is not None:
        return None
    fuentes: list[Documento] = sorted(
        incidente["fuentes"], key=lambda f: (f["fecha"]["valor"], f["id"])
    )
    actua = actua_la_autoridad(incidente)
    titulo = " ".join(str(v) for v in (incidente.get("titulo") or {}).values())
    for fuente in fuentes:
        frase = str(fuente.get("frase_origen", ""))
        if not declaraciones.habla_de_drones(frase) or declaraciones.abierto(frase):
            continue
        if (
            actua
            or DETENCION.search(frase)
            or DETENCION.search(titulo)
            or CIERRE_EN_FRASE.search(frase)
        ):
            return fuente
    if actua and not any(
        declaraciones.habla_de_drones(str(f.get("frase_origen", "")))
        and declaraciones.abierto(str(f.get("frase_origen", "")))
        for f in fuentes
    ):
        for fuente in fuentes:
            frase = str(fuente.get("frase_origen", ""))
            if frase and not declaraciones.abierto(frase):
                return fuente
    return None


def aplicar(incidente: Documento) -> Documento:
    """El incidente con el cierre de una pista registrado como cierre y el titular coherente con
    la presencia. La actuación de la autoridad (un cierre, cazas, una patrulla) no confirma la
    presencia: no es atribución (desde el 21 de octubre de 2026)."""
    return titulares.ajustar_incidente(cierre_de_pista(incidente))


def _declaraciones_del_candidato(almacen: Almacen, candidato: str) -> dict[str, dict[str, Any]]:
    """Identificador de la fuente de cada declaración (el que le da declaraciones.fuente) y la
    declaración. Una extracción posterior sustituye a la anterior."""
    resultado: dict[str, dict[str, Any]] = {}
    for extraccion in almacen.extracciones(candidato):
        enviadas = extraccion.get("enviadas") or []
        for numero, declaracion in enumerate(extraccion.get("declaraciones") or [], 1):
            indice = declaracion.get("fuente")
            if isinstance(indice, int) and 1 <= indice <= len(enviadas):
                noticia = id_fuente(enviadas[indice - 1])
                resultado[f"{noticia}-declaracion-{numero}"] = declaracion
    return resultado


def _candidatos(incidente: Documento, por_id: dict[str, Documento], absorbidos: Any) -> set[str]:
    """Los candidatos del incidente y de los que se fundieron en él."""
    resultado: set[str] = set()
    pendientes, vistos = [incidente["id"]], set()
    while pendientes:
        id_ = pendientes.pop()
        if id_ in vistos or id_ not in por_id:
            continue
        vistos.add(id_)
        candidato = por_id[id_]["control"].get("candidato")
        if candidato:
            resultado.add(candidato)
        pendientes.extend(absorbidos.get(id_, ()))
    return resultado


@cache
def presencias_revisadas(ruta: Path = REVISADOS) -> frozenset[str]:
    """Los incidentes con la presencia del dron revisada a mano."""
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    return frozenset(t["incidente"] for t in datos.get("titulares", []) if "presencia" in t)


# Lo que la verificación del control de las fichas lee de la presencia y la niega
# (proceso/control_fichas.NIEGAN).
NIEGAN_CONTROL = frozenset({"no_hallado", "desmentido"})


def negadas_por_el_control(almacen: Almacen) -> dict[str, set[str]]:
    """Por incidente, las fuentes en que la verificación vigente del control de las fichas
    (recogida/control_fichas.py) lee que no se encontró el dron o que se desmiente, con su frase
    literal. Las verificaciones anuladas al revisarlas no cuentan."""
    resultado: dict[str, set[str]] = {}
    for clave, decision in almacen.controles("verificacion:").items():
        if decision.get("anulada"):
            continue
        dato = (decision.get("datos") or {}).get("presencia")
        if isinstance(dato, list) and len(dato) >= 2 and dato[0] in NIEGAN_CONTROL:
            resultado.setdefault(clave.removeprefix("verificacion:"), set()).add(str(dato[1]))
    return resultado


def pendientes(almacen: Almacen) -> list[tuple[Documento, Cambio]]:
    """Los incidentes cuya presencia confirma la regla y aún no la tienen, con el cambio."""
    todos = almacen.incidentes()
    por_id = {i["id"]: i for i in todos}
    negadas = negadas_por_el_control(almacen)
    absorbidos: dict[str, list[str]] = {}
    for fusion in almacen.fusiones():
        if not fusion["revertida"]:
            absorbidos.setdefault(fusion["destino"], []).append(fusion["absorbido"])
    resultado = []
    for incidente in todos:
        if not activo(incidente) or incidente.get("presencia_dron") != "no_confirmada":
            continue
        # Desmentido por una autoridad: la frase de otra que cuenta los drones no lo cambia.
        if incidente["estado"]["actual"] == Estado.DESMENTIDO:
            continue
        # Revisada a mano con la cita que la deja abierta (configuracion/incidentes_revisados.json,
        # recogida/revisados.py): la regla no la vuelve a confirmar.
        if incidente["id"] in presencias_revisadas():
            continue
        # Una fuente cuenta que no se encontró el dron: no se confirma.
        if no_hallado(incidente) is not None and not pruebas_fisicas_confirmadas(incidente):
            continue
        # Lo que dice de la presencia una autoridad en su propio documento (proceso/detalle.py:
        # una investigación cerrada que no pudo demostrar que fueran drones) manda sobre la
        # declaración que cita un medio.
        if any(
            f.get("documento_oficial") and "presencia_dron" in f.get("campos_respaldados", [])
            for f in incidente["fuentes"]
        ):
            continue
        # El control de las fichas leyó en una de sus fuentes que no se encontró el dron (o que
        # se desmiente) y la dejó sin confirmar: la regla no la vuelve a confirmar. Si no, cada
        # hora una la confirmaba y el otro la quitaba (EODI-2025-00248, desde el 14 de octubre
        # de 2026).
        tiene = {f["id"] for f in incidente["fuentes"]}
        if negadas.get(incidente["id"], set()) & tiene:
            continue
        conocidas: dict[str, dict[str, Any]] = {}
        for candidato in sorted(_candidatos(incidente, por_id, absorbidos)):
            conocidas |= _declaraciones_del_candidato(almacen, candidato)
        if autoridad_lo_deja_abierto(incidente):
            continue
        fuentes = sorted(incidente["fuentes"], key=lambda f: (f["fecha"]["valor"], f["id"]))
        por_enlace = {f["enlace"]: f for f in fuentes if not f.get("es_autoridad")}
        cambio = None
        for fuente in fuentes:
            declaracion = conocidas.get(fuente["id"])
            if declaracion is None or not declaraciones.de_autoridad(fuente):
                continue
            contexto = str(por_enlace.get(fuente["enlace"], {}).get("frase_origen", ""))
            if declaraciones.confirma_dron(declaracion, contexto):
                cambio = Cambio(
                    incidente["id"], fuente["id"], str(declaracion.get("autoridad", "")),
                    str(declaracion.get("categoria", "")), str(declaracion["afirma"]),
                    fuente["frase_origen"],
                )  # fmt: skip
                break
        if cambio is not None:
            resultado.append((incidente, cambio))
    return resultado


def revisar(
    almacen: Almacen, ahora: datetime, modelos: frozenset[str]
) -> tuple[list[Cambio], list[str]]:
    """Aplica la regla a la base. Devuelve los cambios hechos y los incidentes que no se
    pudieron guardar (no validan con las reglas de ahora; se quedan como estaban)."""
    hechos, fallidos = [], []
    instante = {"valor": ahora.astimezone(UTC).strftime("%Y-%m-%dT%H:%MZ"), "precision": "minuto"}
    # El cierre de una pista por un dron se registra como cierre (antes de mirar la actuación).
    for incidente in almacen.incidentes():
        if not activo(incidente):
            continue
        documento = cierre_de_pista(incidente)
        if documento is incidente:
            continue
        documento = {**documento, "control": {**documento["control"],
                                              "ultima_actualizacion": instante}}  # fmt: skip
        try:
            almacen.guardar_incidente(documento, ahora, modelos)
        except DocumentoInvalido:
            fallidos.append(incidente["id"])
            continue
        anotar(almacen, incidente, documento, MOTIVO_PISTA)
    for incidente, cambio in pendientes(almacen):
        documento = {**incidente, "control": {**incidente["control"]}}
        if not declaraciones.confirmar_presencia(documento, cambio.fuente_id):
            continue
        documento = titulares.ajustar_incidente(documento)
        documento["control"]["ultima_actualizacion"] = instante
        try:
            almacen.guardar_incidente(documento, ahora, modelos)
        except DocumentoInvalido:
            fallidos.append(incidente["id"])
            continue
        anotar(almacen, incidente, documento, cambio.motivo)
        hechos.append(cambio)
    # Confirmada solo por la actuación (un cierre o una intervención que cuenta la prensa) y la
    # autoridad, después, lo deja abierto («mulige droner»): queda sin confirmar.
    for incidente in almacen.incidentes():
        if not activo(incidente) or incidente.get("presencia_dron") != "confirmada":
            continue
        documento = quitar_por_actuacion(incidente)
        if documento is incidente:
            continue
        documento = titulares.ajustar_incidente(documento)
        documento = {**documento, "control": {**documento["control"],
                                              "ultima_actualizacion": instante}}  # fmt: skip
        try:
            almacen.guardar_incidente(documento, ahora, modelos)
        except DocumentoInvalido:
            fallidos.append(incidente["id"])
            continue
        anotar(almacen, incidente, documento, MOTIVO_ABIERTO)
    # La confirmaba solo una cita de autoridad vacía (el verbo de decir sin lo que dijo).
    for incidente in almacen.incidentes():
        if not activo(incidente) or incidente.get("presencia_dron") != "confirmada":
            continue
        documento = quitar_por_cita_vacia(incidente)
        if documento is incidente:
            continue
        documento = titulares.ajustar_incidente(documento)
        documento = {**documento, "control": {**documento["control"],
                                              "ultima_actualizacion": instante}}  # fmt: skip
        try:
            almacen.guardar_incidente(documento, ahora, modelos)
        except DocumentoInvalido:
            fallidos.append(incidente["id"])
            continue
        anotar(almacen, incidente, documento, MOTIVO_CITA_VACIA)
    # Un desmentido que no vale (no niega nada, o lo niega quien cede ante la autoridad
    # competente que lo confirmó: proceso/competencia.py): otra vez confirmado y, si esa autoridad
    # dice que fue un dron, con la presencia confirmada por ella.
    for incidente in almacen.incidentes():
        if not activo(incidente):
            continue
        corregido = competencia.corregir_desmentido(incidente)
        if corregido is None:
            continue
        documento, prevalece = corregido
        frase = str(prevalece.get("frase_origen") or "")
        if declaraciones.atribuye_dron(frase) and incidente["id"] not in presencias_revisadas():
            declaraciones.confirmar_presencia(documento, prevalece["id"], expresa=True)
        documento = titulares.ajustar_incidente(incidentes.aplicar_reglas(documento))
        documento = {**documento, "control": {**documento["control"],
                                              "ultima_actualizacion": instante}}  # fmt: skip
        try:
            almacen.guardar_incidente(documento, ahora, modelos)
        except DocumentoInvalido:
            fallidos.append(incidente["id"])
            continue
        anotar(
            almacen, incidente, documento, str(documento["estado"]["historial"][-1]["motivo"]["es"])
        )
    # Confirmada sin que ninguna autoridad la atribuya a drones (la puso el extractor, la
    # actuación de la autoridad o una regla anterior): sin confirmar, salvo las dudosas.
    todos = almacen.incidentes()
    por_id = {i["id"]: i for i in todos}
    absorbidos: dict[str, list[str]] = {}
    for fusion in almacen.fusiones():
        if not fusion["revertida"]:
            absorbidos.setdefault(fusion["destino"], []).append(fusion["absorbido"])
    for incidente in todos:
        if not activo(incidente) or incidente.get("presencia_dron") != "confirmada":
            continue
        documento = quitar_sin_base(incidente)
        if documento is incidente or dudosa(
            almacen, incidente, _candidatos(incidente, por_id, absorbidos)
        ):
            continue
        documento = titulares.ajustar_incidente(documento)
        documento = {**documento, "control": {**documento["control"],
                                              "ultima_actualizacion": instante}}  # fmt: skip
        try:
            almacen.guardar_incidente(documento, ahora, modelos)
        except DocumentoInvalido:
            fallidos.append(incidente["id"])
            continue
        anotar(almacen, incidente, documento, motivo_sin_base(incidente))
    # Una fuente cuenta que se buscó el dron y no se encontró: la presencia no queda confirmada.
    for incidente in almacen.incidentes():
        if not activo(incidente) or incidente.get("presencia_dron") != "confirmada":
            continue
        documento = quitar_por_no_hallado(incidente)
        if documento is incidente:
            continue
        documento = titulares.ajustar_incidente(documento)
        documento = {**documento, "control": {**documento["control"],
                                              "ultima_actualizacion": instante}}  # fmt: skip
        try:
            almacen.guardar_incidente(documento, ahora, modelos)
        except DocumentoInvalido:
            fallidos.append(incidente["id"])
            continue
        fuente = no_hallado(incidente) or {}
        anotar(almacen, incidente, documento,
               f"{MOTIVO_NO_HALLADO}: «{fuente.get('frase_origen', '')}»")  # fmt: skip
    # Los titulares que no dicen lo mismo que la presencia (los guardados antes de la regla).
    for incidente in almacen.incidentes():
        if not activo(incidente):
            continue
        documento = titulares.ajustar_incidente(incidente)
        if documento is incidente:
            continue
        documento = {**documento, "control": {**documento["control"],
                                              "ultima_actualizacion": instante}}  # fmt: skip
        try:
            almacen.guardar_incidente(documento, ahora, modelos)
        except DocumentoInvalido:
            fallidos.append(incidente["id"])
            continue
        anotar(almacen, incidente, documento, MOTIVO_TITULAR)
    return hechos, fallidos


MOTIVO_TITULAR = "titular coherente con la presencia del dron (proceso/titulares.py)"
MOTIVO_ABIERTO = (
    "criterio de presencia: la autoridad lo deja abierto; la actuación que contaba la prensa no "
    "basta"
)


MOTIVO_CITA_VACIA = (
    "criterio de presencia: la cita de la autoridad que la confirmaba solo dice quién habla, no "
    "lo que dijo; la presencia no queda confirmada"
)
MOTIVO_NO_HALLADO = (
    "criterio de presencia: una fuente cuenta que no se encontró el dron; la presencia no "
    "queda confirmada"
)


MOTIVO_SIN_BASE = (
    "criterio de presencia: ninguna autoridad dice que fuera un dron (solo la prensa o los "
    "testigos, o una medida de la autoridad sin atribuirlo); la presencia no queda confirmada"
)


MOTIVO_PRUEBAS_PRENSA = (
    "criterio de presencia: los restos, el derribo o las fotos del dron solo los cuenta la "
    "prensa, sin una autoridad que diga que era un dron; la presencia no queda confirmada"
)


def motivo_sin_base(incidente: Documento) -> str:
    """El motivo de quitar la confirmación sin base: las pruebas físicas que solo cuenta la
    prensa (EODI-2025-00312, «Dronă militară de tip Gerbera a fost găsită pe un câmp») o, si no
    las hay, que ninguna autoridad lo atribuye."""
    evidencia = set((incidente.get("pruebas") or {}).get("evidencia", []))
    return MOTIVO_PRUEBAS_PRENSA if evidencia & PRUEBAS_FISICAS else MOTIVO_SIN_BASE


def sin_base(incidente: Documento) -> bool:
    """Confirmada sin base: ninguna autoridad la atribuye a drones (atribuida_por_autoridad), ni
    lo dice en su propio documento, ni hay pruebas físicas que confirme una autoridad, ni está
    revisada a mano o rectificada por una autoridad (presencia_historial). Lo mismo que cuenta la
    comprobación E de la auditoría (proceso/auditoria_fichas.py)."""
    return (
        incidente.get("presencia_dron") == "confirmada"
        and incidente["id"] not in presencias_revisadas()
        and not incidente.get("presencia_historial")
        and not atribuida_por_autoridad(incidente)
        and not documento_oficial_decide(incidente)
        and not pruebas_fisicas_confirmadas(incidente)
    )


def quitar_sin_base(incidente: Documento) -> Documento:
    """Sin confirmar la presencia que ninguna autoridad atribuye a drones, sin las afirmaciones
    «confirmada» (el extractor la daba por la actuación de la autoridad o por la prensa,
    EODI-2025-00049: «au fost suspendate temporar aterizările»). El mismo incidente si tiene
    base."""
    if not sin_base(incidente):
        return incidente
    return {
        **incidente,
        "presencia_dron": "no_confirmada",
        "afirmaciones": [
            a for a in incidente.get("afirmaciones", [])
            if not (a["campo"] == "presencia_dron" and a["valor"] == "confirmada")
        ],
    }  # fmt: skip


def dudosa_por(incidente: Documento, conocidas: dict[str, dict[str, Any]]) -> bool:
    """La regla no decide (va al experto o a la revisión a mano, y la presencia se queda como
    está): una autoridad afirma los drones según el extractor («drones»), pero su cita guardada
    no los nombra (EODI-2025-00340, Bundeswehr: «Das bestätigte eine Sprecherin»). Las pruebas
    físicas (restos, derribo, explosión) que solo cuenta la prensa no son dudosas: sin una
    autoridad no confirman (EODI-2025-00312, motivo_sin_base). `conocidas`: las declaraciones
    del incidente por el identificador de su fuente (_declaraciones_del_candidato)."""
    autoridades = {f["id"] for f in incidente["fuentes"] if declaraciones.de_autoridad(f)}
    return any(d.get("afirma") == "drones" and id_ in autoridades for id_, d in conocidas.items())


def dudosa(almacen: Almacen, incidente: Documento, candidatos: set[str] | None = None) -> bool:
    """dudosa_por con las declaraciones guardadas de sus candidatos (por omisión, el suyo)."""
    conocidas: dict[str, dict[str, Any]] = {}
    for candidato in sorted(candidatos or {str(incidente["control"].get("candidato"))}):
        conocidas |= _declaraciones_del_candidato(almacen, candidato)
    return dudosa_por(incidente, conocidas)


def quitar_por_no_hallado(incidente: Documento) -> Documento:
    """La presencia sin confirmar si una fuente cuenta que no se encontró el dron, con la
    afirmación «no_confirmada» de esa fuente. El mismo incidente si no hay nada que quitar: la
    presencia revisada a mano, el documento propio de una autoridad, las pruebas físicas que
    confirma una autoridad y la atribución a drones de una autoridad mandan."""
    fuente = no_hallado(incidente)
    if (
        fuente is None
        or incidente.get("presencia_dron") != "confirmada"
        or incidente["id"] in presencias_revisadas()
        or documento_oficial_decide(incidente)
        or pruebas_fisicas_confirmadas(incidente)
        # Lo atribuyó a drones una autoridad: no encontrarlos no lo cambia (lo cambia solo otra
        # autoridad, por las rectificaciones con el experto).
        or atribuida_por_autoridad(incidente)
    ):
        return incidente
    afirmacion = {
        "campo": "presencia_dron",
        "valor": "no_confirmada",
        "fuente_id": fuente["id"],
        "confianza_extraccion": declaraciones.CONFIANZA_REGLA,
    }
    afirmaciones = [
        a for a in incidente.get("afirmaciones", [])
        if not (a["campo"] == "presencia_dron" and a["valor"] == "confirmada")
    ]  # fmt: skip
    if afirmacion not in afirmaciones:
        afirmaciones.append(afirmacion)
    resultado = {**incidente, "presencia_dron": "no_confirmada", "afirmaciones": afirmaciones}
    # La autoridad que confirmó el suceso lo atribuye a un dron («la policía confirmó el
    # avistamiento, pero no encontró el dron»): manda la autoridad (validaciones.errores_presencia).
    from proceso.validaciones import errores_presencia

    return incidente if errores_presencia(resultado) else resultado


def quitar_por_actuacion(incidente: Documento) -> Documento:
    """Sin la confirmación que solo venía de la actuación (fuente que no es autoridad) cuando
    todas las autoridades citadas lo dejan abierto o las fuentes dan otra causa. El mismo
    incidente si no hay nada que quitar."""
    if documento_oficial_decide(incidente) or not (
        autoridad_lo_deja_abierto(incidente) or otra_causa(incidente)
    ):
        return incidente
    fuentes = {f["id"]: f for f in incidente["fuentes"]}
    de_regla = [
        a for a in incidente.get("afirmaciones", [])
        if a["campo"] == "presencia_dron" and a["valor"] == "confirmada"
        and a == declaraciones.afirmacion_presencia(a["fuente_id"])
    ]  # fmt: skip
    if not de_regla or any(fuentes.get(a["fuente_id"], {}).get("es_autoridad") for a in de_regla):
        return incidente
    return {
        **incidente,
        "presencia_dron": "no_confirmada",
        "afirmaciones": [a for a in incidente.get("afirmaciones", []) if a not in de_regla],
    }


def quitar_por_cita_vacia(incidente: Documento) -> Documento:
    """Sin la confirmación que solo daba una cita de autoridad vacía (quién habla y el verbo de
    decir: «… Komendy Stołecznej Policji przekazała», EODI-2026-00648). El mismo incidente si
    alguna otra fuente la sostiene o no hay nada que quitar."""
    if (
        incidente.get("presencia_dron") != "confirmada"
        or incidente["id"] in presencias_revisadas()
        or documento_oficial_decide(incidente)
        or pruebas_fisicas_confirmadas(incidente)
        or atribuida_por_autoridad(incidente)
    ):
        return incidente
    fuentes = {f["id"]: f for f in incidente["fuentes"]}
    confirman = [
        a for a in incidente.get("afirmaciones", [])
        if a["campo"] == "presencia_dron" and a["valor"] == "confirmada"
    ]  # fmt: skip
    vacias = [a for a in confirman if declaraciones.cita_vacia(fuentes.get(a["fuente_id"], {}))]
    if not vacias or len(vacias) < len(confirman):
        return incidente
    return {
        **incidente,
        "presencia_dron": "no_confirmada",
        "afirmaciones": [a for a in incidente.get("afirmaciones", []) if a not in vacias],
    }


def anotar(almacen: Almacen, anterior: Documento, nuevo: Documento, motivo: str) -> None:
    """El motivo del cambio en el historial, con los campos que cambian."""
    campos = ("presencia_dron", "titulo", "estado", "tiempo")
    antes = {c: anterior.get(c) for c in campos if anterior.get(c) != nuevo.get(c)}
    despues = {c: nuevo.get(c) for c in antes}
    if antes:
        almacen.anotar_motivo(TABLA_MOTIVOS, nuevo["id"], antes, despues, motivo)
