"""Instalaciones con el mismo nombre: el estadio «Васил Левски» de Karlovo y el aeropuerto de Sofía
(LBSF), que lleva ese nombre (EODI-2026-00064 y EODI-2026-00077). Con homónimos decide el tipo que
nombra el texto y, si no, la ciudad; si tampoco, ninguna (proceso/noticias.lugares_en). La
auditoría lo vigila con la comprobación H (proceso/auditoria_fichas.py)."""

import json
from pathlib import Path

from proceso import auditoria_fichas, decidir, noticias

REFERENCIA = Path(__file__).parent / "referencia" / "fichas"
ESTADIO = "estadio:way/169361657"
# Las frases de las fuentes de las dos fichas.
FRASE_00077 = 'Три сигнала за дронове във въздушното прастранство над Летище "Васил Левски" снощи'
FRASE_00064 = (
    "Въздушното пространство над летище „Васил Левски“ – София е било затворено за кратко в "
    "събота следобед заради засечен дрон в района на летището."
)
ENLACE_00077 = "https://focus-news.net/novini/regioni/Tri-signala-za-dronove-vuv-vuzdushno-2917935"


def test_el_tipo_que_nombra_la_fuente_decide_entre_homonimos() -> None:
    nom = noticias.nomenclator()
    assert nom.lugares[ESTADIO].tipo == "estadio"
    assert noticias.lugares_en(FRASE_00077, nom) == ("LBSF",)
    assert noticias.lugares_en(FRASE_00064, nom) == ("LBSF",)
    assert noticias.lugares_en("Летище Васил Левски", nom) == ("LBSF",)


def test_sin_tipo_ni_ciudad_no_se_elige_ninguna() -> None:
    nom = noticias.nomenclator()
    assert noticias.lugares_en("Васил Левски", nom) == ()
    # Una subestación que se llama como la ciudad del aeropuerto o de la central tampoco gana.
    assert noticias.lugares_en("Cernavodă", nom) == ()
    assert noticias.lugares_en("Drone over Suceava airport", nom) == ("LRSV",)


def _ficha_00077(objetivo: dict[str, str]) -> dict[str, object]:
    return {
        "id": "EODI-2026-00077",
        "tipo": "interrupcion_aeroportuaria",
        "objetivo": objetivo,
        "lugar": {"pais": "BG", "localidad": "София", "nivel": "instalacion"},
        "fuentes": [{"id": "f", "enlace": ENLACE_00077, "frase_origen": FRASE_00077}],
    }


def test_la_revision_lleva_00077_al_aeropuerto_de_sofia() -> None:
    ficha = _ficha_00077({"categoria": "estadio", "nombre": "Васил Левски"})
    assert decidir.decidir_objetivo(ficha) == {
        "categoria": "aeropuerto",
        "nombre": "Летище „Васил Левски“ - София",
        "oaci": "LBSF",
    }


def test_auditoria_h_objetivo_que_no_casa_con_el_suceso() -> None:
    estadio = _ficha_00077({"categoria": "estadio", "nombre": "Васил Левски"})
    assert auditoria_fichas._h(estadio)
    aeropuerto = _ficha_00077(
        {"categoria": "aeropuerto", "nombre": "Летище „Васил Левски“ - София", "oaci": "LBSF"}
    )
    assert not auditoria_fichas._h(aeropuerto)
    # Una instalación que casa con el tipo, pero lejos de la localidad (Aalborg y Copenhague).
    lejos = {
        "id": "x",
        "tipo": "interrupcion_aeroportuaria",
        "objetivo": {"categoria": "aeropuerto", "nombre": "Københavns Lufthavn", "oaci": "EKCH"},
        "lugar": {"pais": "DK", "localidad": "Aalborg"},
    }
    assert auditoria_fichas._h(lejos)
    # La ficha de 00064 de la referencia es la de antes, con el estadio; con el objetivo que
    # decide su revisión, el aeropuerto.
    ficha_00064 = json.loads((REFERENCIA / "EODI-2026-00064.json").read_text(encoding="utf-8"))
    assert ficha_00064["objetivo"]["categoria"] == "estadio"
    assert auditoria_fichas._h(ficha_00064)
    decidido = decidir.decidir_objetivo(ficha_00064)
    assert decidido is not None and decidido["oaci"] == "LBSF"
    assert not auditoria_fichas._h({**ficha_00064, "objetivo": decidido})
