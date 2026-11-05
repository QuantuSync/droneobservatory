"""Las frases que cuentan cómo reacciona una instalación, no dónde estuvo el dron.

Una base o un aeropuerto desde el que despegan aviones o helicópteros para responder nunca es el
lugar ni la instalación afectada del suceso («Armata a ridicat două avioane F-16 de la Baza
Borcea, după ce o dronă a fost detectată la graniţa României», EODI-2026-00753; «Los dos aviones
despegaron…» de Mihail Kogălniceanu, EODI-2026-00747). Tampoco la que solo reacciona a una alerta
de su región (el aeropuerto de Iasi que cierra «în urma mesajului RO-Alert», EODI-2026-00719): su
cierre puede constar como consecuencia, pero el punto del suceso es donde la fuente sitúa el dron.
Solo es el lugar si la frase sitúa el dron sobre ella o junto a ella (el cierre del aeropuerto de
Iasi por un dron sobre el aeropuerto, EODI-2026-00015, no cambia).
"""

import re

# Una alerta o aviso a la población de una región (RO-Alert, sirena, alarma aérea): la frase que la
# nombra cuenta la reacción de quien la recibe, no dónde estuvo el dron.
ALERTA = re.compile(
    r"ro-alert|\balert\w*|\balarm\w*|\bavertiz\w*|\bwarnung\w*|\bwarning\b|\bostrze[zż]\w*|"
    r"\bsiren\w*|\bsirén\w*|\bsyren\w*|\bpovitrian\w* tryvo\w*|тривог\w*|тревог\w*|"
    r"\bperspėj\w*|\bbrīdinā\w*|\bhoiatus\w*|\bvarsl\w*|\bvaroitu\w*|\bσυναγερμ\w*",
    re.IGNORECASE,
)

# Aviones o helicópteros que despegan (o se elevan, se lanzan) desde la instalación para responder.
DESPEGUE = re.compile(
    r"\bdespeg\w*|\bdecol\w*|\bdécoll\w*|"
    r"\bau? ridicat\b[^.]{0,40}\b(?:avioane|aeronave|elicoptere|f-16)|"
    r"\bau fost ridicate\b|\bridicate de la\b|\btook off\b|\btake[- ]?off\b|"
    r"\btakes off\b|\btaking off\b|\bscrambl\w*|\bgestartet\b|\bstarteten\b|\baufgestiegen\b|"
    r"\bwystartow\w*|\bpoderwan\w*|\bpoderwał\w*|\bpoderwal\w*|\bsi sono alzat\w*|"
    r"\bзлет\w*|\bзліт\w*|\bвзлет\w*|\bвзлёт\w*|\bизлет\w*|\bfelszáll\w*|\bopgestegen\b|"
    r"\bvzlétl\w*|\bvzlietl\w*|\bαπογειώ\w*|\bpakil\w*|\bpacēl\w*",
    re.IGNORECASE,
)

# La frase sitúa un dron sobre la instalación o junto a ella.
SOBRE = re.compile(
    r"\bdeasupra\b|\babove\b|\bover the\b|\bsobre (?:el|la|los|las)\b|\bencima\b|\blângă\b|"
    r"\blanga\b|\bnear\b|\bîn apropierea\b|\bin apropierea\b|\bîn zona\b|\büber\b|\bnad\b|"
    r"\bнад\b|\bπάνω\b|\bsurvol\w*|\bsobrevol\w*|\boverfl\w*|\bau-dessus\b|\bsopra\b",
    re.IGNORECASE,
)
_DRON = re.compile(r"dron|drone|uav|bpla|бпла|дрон|bezza[łl]og|μη επανδρωμ", re.IGNORECASE)


def reacciona_a_una_alerta(frase: str) -> bool:
    """La frase cuenta que algo pasó a raíz de una alerta regional (cerrar el espacio aéreo de un
    aeropuerto tras un RO-Alert), no que el dron estuviera allí."""
    return bool(ALERTA.search(frase or ""))


def despegan_de_ella(frase: str) -> bool:
    """La frase cuenta que desde la instalación despegaron aviones o helicópteros."""
    return bool(DESPEGUE.search(frase or ""))


def situa_el_dron(frase: str) -> bool:
    """La frase sitúa un dron sobre la instalación o junto a ella."""
    texto = frase or ""
    return bool(_DRON.search(texto) and SOBRE.search(texto))


def despegan_sin_dron_encima(frase: str) -> bool:
    """Despegan aviones de la instalación y la frase no sitúa el dron sobre ella ni junto a ella."""
    return despegan_de_ella(frase) and not situa_el_dron(frase)


def solo_reacciona(frase: str) -> bool:
    """La instalación que nombra la frase solo reacciona: responde a una alerta, o despegan de ella
    aviones y la frase no sitúa el dron sobre ella ni junto a ella."""
    return reacciona_a_una_alerta(frase) or despegan_sin_dron_encima(frase)
