"""La instalación que nombran el titular y las fuentes (proceso/objetivo_del_titular.py), con
fichas reales de la comprobación B de la auditoría (instalación no reconocida)."""

from typing import Any

from proceso.noticias import normalizar
from proceso.objetivo_del_titular import objetivo_nombrado


def _ficha(id_: str, titulo: str, lugar: dict[str, Any], frases: list[str], en: str = "") -> Any:
    return {
        "id": id_,
        "titulo": {"es": titulo, "en": en},
        "lugar": lugar,
        "fuentes": [{"id": f"f{i}", "frase_origen": f} for i, f in enumerate(frases)],
    }


FRANKFURT = _ficha(
    "EODI-2025-00109",
    "Avistamiento de dron en el aeropuerto de Frankfurt; detención del piloto",
    {"pais": "DE", "nivel": "instalacion", "punto": {"lat": 50.0333, "lon": 8.5706}},
    ["Am gestrigen Freitagmorgen (03. Oktober 2025) kam es am Frankfurter Flughafen auf Grund "
     "eines kurzzeitigen Drohnenflugs zu einem Polizeieinsatz"],
    "Drone sighting at Frankfurt airport; pilot arrested",
)  # fmt: skip
CONSTANZA = _ficha(
    "EODI-2026-00152",
    "Dron que explotó en el Puerto de Constanza",
    {"pais": "RO", "nivel": "instalacion", "punto": {"lat": 44.14862, "lon": 28.66632}},
    ["Alertă în Portul Constanța după descoperirea unei drone marine necunoscute"],
)


def test_el_aeropuerto_que_nombran_el_titular_y_la_fuente() -> None:
    assert objetivo_nombrado(FRANKFURT) == {
        "categoria": "aeropuerto", "nombre": "Flughafen Frankfurt am Main", "oaci": "EDDF",
    }  # fmt: skip
    # El puerto, por su nombre completo («Portul Constanța»), sin OACI.
    puerto = objetivo_nombrado(CONSTANZA)
    assert puerto is not None and puerto["categoria"] == "puerto" and "oaci" not in puerto
    assert normalizar(puerto["nombre"]) == normalizar("Portul Constanța")


def test_nada_si_ya_tiene_instalacion_o_esta_lejos() -> None:
    con_objetivo = {**FRANKFURT, "objetivo": {"categoria": "aeropuerto", "nombre": "Frankfurt"}}
    assert objetivo_nombrado(con_objetivo) is None
    lejos = {**FRANKFURT, "lugar": {"pais": "DE", "punto": {"lat": 50.11, "lon": 8.68 + 0.5}}}
    assert objetivo_nombrado(lejos) is None
    otro_pais = {**FRANKFURT, "lugar": {"pais": "AT", "punto": FRANKFURT["lugar"]["punto"]}}
    assert objetivo_nombrado(otro_pais) is None


def test_nada_sin_una_sola_instalacion_en_el_titular() -> None:
    # Dos barcos atacados en el mar (EODI-2026-00512): «Бяла» es el pueblo, no su aeródromo.
    barcos = _ficha(
        "EODI-2026-00512",
        "Drones atacan barcos en el mar Negro frente a Bulgaria",
        {"pais": "BG", "nivel": "region"},
        ["Два кораба са атакувани с дронове край Бяла"],
    )
    assert objetivo_nombrado(barcos) is None
    # Varios aeropuertos (EODI-2026-00510): no se elige uno.
    paris = _ficha(
        "EODI-2026-00510",
        "Dos posibles drones sobrevuelan los alrededores de los aeropuertos parisinos",
        {"pais": "FR", "nivel": "region"},
        ["Deux drones ont survolé les abords de l'aéroport du Bourget"],
    )
    assert objetivo_nombrado(paris) is None
