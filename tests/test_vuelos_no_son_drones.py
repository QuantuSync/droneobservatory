"""Vilna, EODI-2025-00004 (8 de noviembre de 2026): la ficha llevaba 3 drones por la frase
«ketvirtadienį Viešojo saugumo tarnyba Vilniuje fiksavo 3 draudžiamus dronų skrydžius», que cuenta
tres vuelos prohibidos de drones (y del jueves, no del viernes de la ficha). Un número junto a la
palabra dron que cuenta vuelos, entradas, violaciones o avisos de drones no es un número de drones
(proceso/control_fichas.NUMERO_DE_DRONES)."""

from typing import Any

import pytest

from proceso import control_fichas as reglas

VILNA = (
    "ketvirtadienį Viešojo saugumo tarnyba Vilniuje fiksavo 3 draudžiamus dronų skrydžius oro "
    "uosto apylinkėse"
)


@pytest.mark.parametrize(
    "frase",
    [
        VILNA,
        "zabilježili dva upada bespilotnih letjelica u svoj zračni prostor",
        "two drone intrusions were detected in its airspace near the border with Ukraine",
        "dos aviones F-16 despegaron por drones",
    ],
)
def test_vuelos_entradas_y_avisos_no_son_drones(frase: str) -> None:
    assert not reglas.NUMERO_DE_DRONES.search(frase)


@pytest.mark.parametrize(
    "frase",
    [
        "Četiri drona viđena su u nedjelju navečer iznad belgijske vojne zračne baze Kleine-Brogel",
        "Nava de marfă a fost atacată de trei drone aeriene",
        "Het gaat om 1 tot 3 drones die werden opgemerkt door het detectiesysteem",
        "Samedi soir, nos militaires ont détecté quatre ou cinq drones survolant la base",
        "Uppringare såg två drönare i luften som blinkade rött och grönt",
        "Δύο τουρκικά μη επανδρωμένα αεροσκάφη καταγράφηκαν",
        "Три дрона са засечени над летището в София снощи",
        "Bis zu fünf Drohnen wurden im Bereich des Flughafens gesichtet",
        "A police patrol also observed two blinking drones hovering.",
    ],
)
def test_los_drones_contados_siguen_valiendo(frase: str) -> None:
    assert reglas.NUMERO_DE_DRONES.search(frase)


def _ficha() -> dict[str, Any]:
    return {
        "id": "EODI-2025-09004",
        "tipo": "sobrevuelo",
        "lugar": {"pais": "LT", "nivel": "pais"},
        "tiempo": {"inicio": {"valor": "2025-09-26T00:00Z", "precision": "dia"}},
        "drones": {"numero": {"min": 3, "max": 3}},
        "fuentes": [
            {
                "id": "respublika",
                "enlace": "https://respublika.lt/lt/naujienos/lietuva/x",
                "frase_origen": "",
                "fecha": {"valor": "2025-09-27T08:00Z", "precision": "aproximada"},
            }
        ],
        "estado": {"actual": "confirmado", "historial": []},
        "presencia_dron": "confirmada",
        "afirmaciones": [
            {"campo": "drones", "valor": {"min": 3, "max": 3}, "fuente_id": "respublika"}
        ],
    }


def test_tres_vuelos_de_drones_no_dejan_tres_drones() -> None:
    verificada = reglas.Verificada({"drones": ({"min": 3, "max": 3}, "respublika", VILNA)})
    corregida = reglas.aplicar(_ficha(), verificada, True, None)
    assert corregida.incidente["drones"]["numero"] == "desconocido"
