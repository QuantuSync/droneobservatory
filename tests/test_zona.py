"""Frontera o interior (proceso/zona.py)."""

import copy

from almacen.base import Almacen
from proceso import zona
from tests import base_prueba
from tests.ejemplos import AHORA, VOCABULARIO_MODELOS


def incidente(pais: str, tipo: str = "sobrevuelo", **lugar: object) -> dict:  # type: ignore[type-arg]
    return {
        "id": "EODI-2026-00001", "tipo": tipo, "titulo": {"es": "Dron", "en": "Drone"},
        "lugar": {"pais": pais, **lugar},
    }  # fmt: skip


def punto(lat: float, lon: float) -> dict[str, float]:
    return {"lat": lat, "lon": lon}


def test_enlazado_con_un_ataque_es_frontera() -> None:
    documento = incidente("RO", punto=punto(44.43, 26.10))
    documento["ataque"] = {"id": "EODI-UA-2026-0001", "jornada": {}, "por": "fecha"}
    assert zona.clasificar(documento) == {"grupo": "frontera", "motivo": "ataque"}


def test_cerca_de_la_frontera_con_su_distancia() -> None:
    # Galați, junto a Ucrania y Moldavia.
    resultado = zona.clasificar(incidente("RO", punto=punto(45.43, 28.04)))
    assert resultado["grupo"] == "frontera" and resultado["motivo"] == "cerca_de_la_frontera"
    assert resultado["distancia_km"] < 20
    # Vilna, a unos 30 km de Bielorrusia.
    assert zona.clasificar(incidente("LT", punto=punto(54.64, 25.29)))["grupo"] == "frontera"


def test_lejos_es_interior() -> None:
    # Bucarest (aeropuerto de Otopeni), a más de 150 km de Ucrania y a más de 50 km del mar.
    resultado = zona.clasificar(incidente("RO", punto=punto(44.57, 26.09)))
    assert resultado["grupo"] == "interior" and resultado["motivo"] == "lejos_de_la_frontera"
    # Múnich.
    assert zona.clasificar(incidente("DE", punto=punto(48.35, 11.79)))["grupo"] == "interior"


def test_costa_del_mar_negro() -> None:
    # Varna, lejos de Ucrania pero en la costa.
    resultado = zona.clasificar(incidente("BG", punto=punto(43.20, 27.92)))
    assert resultado == {
        "grupo": "frontera", "motivo": "costa_mar_negro", "distancia_km": resultado["distancia_km"]
    }  # fmt: skip
    assert resultado["distancia_km"] > zona.BANDA_FRONTERA_KM


def test_sin_punto_con_lugar_nombrado() -> None:
    documento = incidente("RO", nivel="pais")
    documento["titulo"] = {"es": "Dron explota en el Puerto de Constanza", "en": "Drone"}
    assert zona.clasificar(documento)["grupo"] == "frontera"


def test_sin_punto_ni_lugar() -> None:
    assert zona.clasificar(incidente("MD", nivel="pais"))["motivo"] == "pais_dentro_de_la_banda"
    assert zona.clasificar(incidente("LV", "incursion", nivel="pais")) == {
        "grupo": "frontera", "motivo": "incursion_en_pais_fronterizo"
    }  # fmt: skip
    con_pruebas = incidente("PL", nivel="pais")
    con_pruebas["pruebas"] = {"entrada_exterior": True}
    assert zona.clasificar(con_pruebas)["motivo"] == "incursion_en_pais_fronterizo"
    assert zona.clasificar(incidente("LV", nivel="pais")) == {
        "grupo": "interior", "motivo": "sin_lugar"
    }  # fmt: skip
    # Una incursión en un país sin frontera con la guerra es interior.
    assert zona.clasificar(incidente("BE", "incursion", nivel="pais"))["grupo"] == "interior"


def test_la_decide_el_guardado_y_la_pasada_no_cambia_nada() -> None:
    almacen = Almacen.abrir()
    documento = copy.deepcopy(base_prueba.completo())
    documento.pop("zona", None)
    almacen.guardar_incidente(documento, AHORA, VOCABULARIO_MODELOS)
    # El guardado ya la decide (proceso/decidir.aplicar): la pasada horaria no cambia nada.
    guardado = almacen.incidentes()[0]
    assert guardado["zona"] == zona.clasificar(guardado)
    assert zona.clasificar_todos(almacen, AHORA, VOCABULARIO_MODELOS)["cambiados"] == 0


def test_zona_revisada_a_mano_con_su_cita() -> None:
    # Chopin (EODI-2025-00233), cerrado por los drones rusos del 10 de septiembre de 2025, a 151 km
    # de Bielorrusia: la regla de los 150 km no puede y manda la revisión con la cita.
    enlace = (
        "https://saudigazette.com.sa/article/654845/World/Europe/"
        "Warsaw-airport-shut-after-Ukrainian-reports-of-Russian-drones-over-Poland"
    )
    chopin = {
        **incidente("PL", "interrupcion_aeroportuaria", punto=punto(52.16309, 20.96362)),
        "id": "EODI-2025-00233", "fuentes": [{"enlace": enlace}],
    }  # fmt: skip
    assert zona.clasificar(chopin) == {"grupo": "frontera", "motivo": "ataque"}
    # Sin esa fuente (una ficha de prueba con el mismo identificador), la regla: interior.
    sin_fuente = {**chopin, "fuentes": []}
    assert zona.clasificar(sin_fuente)["grupo"] == "interior"
    assert zona.clasificar(sin_fuente)["distancia_km"] == 151
