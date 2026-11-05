"""La instalación que solo reacciona no es el lugar ni la instalación afectada del suceso
(proceso/reaccion.py): la base de la que despegan los cazas (EODI-2026-00753, 00747) y el
aeropuerto que cierra por una alerta de su región (EODI-2026-00719). El cierre del aeropuerto de
Iasi por un dron sobre el aeropuerto (EODI-2026-00015) no cambia."""

from typing import Any

import pytest

from proceso import control_fichas as reglas
from proceso import noticias, reaccion
from proceso.objetivo_del_titular import objetivo_nombrado

IASI = "Iași"

# Las frases de las fichas, tal como las dan sus fuentes.
BORCEA = (
    "Armata a ridicat două avioane F-16 de la Baza Borcea, după ce o dronă a fost detectată la "
    "graniţa României."
)
KOGALNICEANU = (
    "Los dos aviones despegaron de la base aérea Mihail Kogălniceanu tras detectarse posibles "
    "drones cerca de la frontera con Ucrania."
)
ALERTA_IASI = (
    f"Oficialii Aeroportului {IASI} anunță că, în urma mesajului RO-Alert referitor la posibilă "
    "incursiune a unei drone, spațiul aerian a fost închis"
)


@pytest.mark.parametrize(
    ("frase", "esperado"),
    [
        (BORCEA, True),
        (KOGALNICEANU, True),
        (ALERTA_IASI, True),
        ("Two Eurofighters were scrambled from Rostock-Laage after a drone was seen at the coast",
         True),
        ("Myśliwce poderwane z bazy w Łasku po wykryciu drona przy granicy", True),
        # Prudente: si la frase pone un dron «sobre» algo, no se decide por ella (queda como hoy).
        ("Myśliwce poderwane z bazy w Łasku po wykryciu drona nad Lubelszczyzną", False),
        # El dron sobre la instalación: es su lugar aunque despeguen cazas.
        ("A drone flew over the air base before two F-16 took off", False),
        ("O dronă a fost observată deasupra bazei; două avioane au decolat", False),
        ("Eine Drohne flog über den Flughafen Hannover", False),
        ("Aeroportul din Iași a fost închis după ce o dronă a survolat pista", False),
    ],
)  # fmt: skip
def test_la_frase_que_solo_cuenta_la_reaccion(frase: str, esperado: bool) -> None:
    assert reaccion.solo_reacciona(frase) is esperado


def test_la_regla_de_la_alerta_sigue_igual() -> None:
    # La de 00719 no se afloja: una alerta no sitúa el dron aunque la frase diga «deasupra».
    assert reglas.reacciona_a_una_alerta(ALERTA_IASI)
    assert reaccion.solo_reacciona("RO-Alert: dronă deasupra județului " + IASI)


def _ficha(titulo: str, frases: list[str], lugar: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": "EODI-2026-00753",
        "titulo": {"es": titulo, "en": ""},
        "lugar": lugar,
        "fuentes": [{"id": f"f{i}", "frase_origen": f} for i, f in enumerate(frases)],
    }


def test_la_base_de_la_que_despegan_los_cazas_no_es_la_instalacion_afectada() -> None:
    """EODI-2026-00753: «Dron detectado en la frontera de Rumanía: cazas F-16 despegan de la base
    de Borcea». La ficha tenía el lugar en la frontera y ninguna instalación; el titular y la
    frase nombraban Borcea y `objetivo_nombrado` la ponía como instalación afectada."""
    frontera = {"pais": "RO", "nivel": "region", "region": "graniţa României"}
    ficha = _ficha(
        "Dron detectado en la frontera de Rumanía: cazas F-16 despegan de la base de Borcea",
        [BORCEA],
        frontera,
    )
    assert objetivo_nombrado(ficha) is None
    # La misma base con un dron encima sí es la instalación afectada.
    encima = _ficha(
        "Dron sobre la base aérea de Borcea",
        ["O dronă a fost observată deasupra Bazei Aeriene Borcea"],
        frontera,
    )
    hallado = objetivo_nombrado(encima)
    assert hallado is not None and "Borcea" in hallado["nombre"]


def test_el_aeropuerto_de_iasi_con_el_dron_encima_no_cambia() -> None:
    """EODI-2026-00015: el cierre del aeropuerto de Iasi, con su instalación y su punto de la
    extracción. Ni `objetivo_nombrado` (ya tiene instalación) ni la corrección del lugar del control
    (ya tiene punto) lo tocan."""
    ficha = _ficha(
        f"Cierre del Aeropuerto Internacional de {IASI} por alerta de dron",
        [f"RO-ALERT - O dronă se apropie de {IASI} dinspre Republica Moldova. Au fost suspendate "
         f"toate zborurile de pe Aeroportul {IASI}"],
        {"pais": "RO", "nivel": "instalacion", "punto": {"lat": 47.17991, "lon": 27.62082}},
    )  # fmt: skip
    ficha["objetivo"] = {"categoria": "aeropuerto", "nombre": f"Aeroportul Internațional {IASI}",
                         "oaci": "LRIA"}  # fmt: skip
    assert objetivo_nombrado(ficha) is None
    correccion = reglas.Correccion(ficha)
    verificada = reglas.Verificada(
        datos={"lugar": ({"nombre": f"Aeroportul {IASI}", "nivel": "instalacion"}, "f0",
                         ficha["fuentes"][0]["frase_origen"])},
    )  # fmt: skip
    reglas._lugar(correccion, verificada, noticias.nomenclator())
    assert correccion.incidente == ficha and correccion.cambios == []


def _corregir_lugar(frase: str) -> reglas.Correccion:
    """EODI-2026-00747: la ficha con el lugar en el distrito de Tulcea y sin punto; la verificación
    del control daba como lugar la base de Mihail Kogălniceanu con la frase del despegue."""
    ficha = _ficha("Cazas despegan por posibles drones cerca de la frontera", [frase],
                   {"pais": "RO", "nivel": "region", "region": "Tulcea"})  # fmt: skip
    correccion = reglas.Correccion(ficha)
    nombre = "Base Aérea 57 Mihail Kogălniceanu"
    verificada = reglas.Verificada(datos={"lugar": ({"nombre": nombre, "nivel": "instalacion"},
                                                    "f0", frase)})  # fmt: skip
    reglas._lugar(correccion, verificada, noticias.nomenclator())
    return correccion


def test_la_verificacion_no_pone_el_lugar_en_la_base_de_la_que_despegan() -> None:
    despegue = _corregir_lugar(KOGALNICEANU)
    assert despegue.cambios == [] and "punto" not in despegue.incidente["lugar"]
    assert "objetivo" not in despegue.incidente
    assert any("solo su reacción" in d for d in despegue.dudas)
    # Con el dron sobre la base, la base es el lugar.
    encima = _corregir_lugar("Un dron sobrevoló la Base Aérea 57 Mihail Kogălniceanu")
    assert encima.incidente["lugar"]["nivel"] == "instalacion"
    assert encima.incidente["objetivo"]["categoria"] in {"aeropuerto", "base_militar"}
