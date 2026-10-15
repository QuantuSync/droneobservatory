"""«No se encontró» en las lenguas que lee el observatorio (EODI-2025-00248: la policía
neerlandesa contó «niets meer gevonden» y el criterio de presencia no lo reconocía)."""

import pytest

from proceso import presencia

NO_ENCONTRADO = [
    # neerlandés
    "Zowel in de lucht als op de grond werd niets meer gevonden",
    "De politie heeft niets gevonden na de melding van een drone",
    "Er is geen drone aangetroffen",
    # inglés
    "Police searched the area but nothing was found",
    "Officers could not find anything after the drone report",
    "No drone was located by the patrol",
    # alemán
    "Die Polizei hat nichts mehr gefunden",
    "Eine Streife fand vor Ort nichts",
    # francés
    "Rien n'a été trouvé lors des recherches",
    "Les gendarmes n'ont rien trouvé",
    # italiano
    "Le forze dell'ordine non hanno trovato nulla",
    "Il drone non è stato trovato",
    "Nessun drone è stato individuato",
    # polaco
    "Policjanci nic nie znaleźli",
    "Nie znaleziono niczego w okolicy lotniska",
    # rumano
    "Nu a fost găsit nimic în zonă",
    "Nu a fost identificată nicio dronă",
    # lituano
    "Pareigūnai nieko nerado, nieko nerasta",
    "Nerasta jokio drono",
    # letón
    "Nekas netika atrasts",
    "Drons netika atrasts",
    # estonio
    "Midagi ei leitud",
    "Drooni ei leitud",
    # finés
    "Mitään ei löydetty",
    "Poliisi ei löytänyt mitään",
    # sueco, danés, noruego
    "Ingenting hittades vid sökningen",
    "Politiet fandt ingenting",
    "Ingenting ble funnet",
    "Politiet fant ikke noe",
    # checo y eslovaco
    "Nic nebylo nalezeno",
    "Dron nebyl nalezen",
    "Nič sa nenašlo",
    # húngaro
    "A rendőrök nem találtak semmit",
    "A drónt nem találták",
    # búlgaro
    "Нищо не беше открито",
    "Дронът не е открит",
    # griego
    "Δεν βρέθηκε τίποτα στην περιοχή",
    # ucraniano y ruso
    "Нічого не було знайдено",
    "Ничего не обнаружено",
    # español y portugués
    "No se encontró nada en la zona",
    "Nada foi encontrado no local",
    "Nenhum drone foi encontrado",
]

SIGUE_SIN_DECIR = [
    # lo que no se encontró era una persona o un vehículo
    "Bij de verdachte werd niets gevonden",
    "Nothing was found in the suspect's car",
    "Im Fahrzeug wurde nichts gefunden",
    # formas que no dicen que no se encontrara (revisadas a mano)
    "Nada indica que fuera un dron",
    "Rien ne permet de dire qu'il s'agissait d'un drone",
    "Nichts Neues zur Drohne über dem Flughafen",
    "La riunione si è conclusa con un nulla di fatto",
    "No Drone Debris Found",
    "Een drone werd gezien boven de luchthaven",
]


@pytest.mark.parametrize("frase", NO_ENCONTRADO)
def test_reconoce_no_se_encontro(frase: str) -> None:
    assert presencia.dice_no_hallado(frase), frase


@pytest.mark.parametrize("frase", SIGUE_SIN_DECIR)
def test_no_confunde_otras_frases(frase: str) -> None:
    assert not presencia.dice_no_hallado(frase), frase


def test_la_00248_queda_sin_confirmar() -> None:
    """Con la frase de la policía la presencia no puede quedar confirmada."""
    incidente = {
        "id": "EODI-2025-00248",
        "presencia_dron": "confirmada",
        "fuentes": [{
            "id": "f1", "fecha": {"valor": "2025-09-24"}, "es_autoridad": False,
            "frase_origen": "Zowel in de lucht als op de grond werd niets meer gevonden",
        }],
    }  # fmt: skip
    assert presencia.no_hallado(incidente) is not None
