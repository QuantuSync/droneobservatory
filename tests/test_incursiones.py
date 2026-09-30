"""Incursiones a partir de los cruces de los partes ucranianos."""

from datetime import UTC, datetime

from almacen.base import Almacen
from proceso import incursiones
from proceso.validaciones import validar_incidente
from tests.test_ataques import MANANA, publicar

AHORA = datetime(2026, 9, 28, tzinfo=UTC)
MODELOS = frozenset({"shahed_geran", "gerbera_senuelos", "otros"})


def con_cruce(almacen: Almacen, pais: str) -> None:
    publicar(almacen, 1, MANANA, 50, 40)
    (ataque,) = almacen.ataques_ucrania()
    ataque["cruces"] = [{"pais": pais, "numero": {"min": 2, "max": 2}}]
    almacen.guardar_ataque_ucrania(ataque, AHORA)


def test_un_cruce_a_rumania_es_una_incursion_notificada() -> None:
    almacen = Almacen.abrir()
    con_cruce(almacen, "RO")
    assert incursiones.registrar(almacen, AHORA, MODELOS) == 1
    (incidente,) = almacen.incidentes()
    assert validar_incidente(incidente, AHORA, MODELOS) == []
    assert (incidente["tipo"], incidente["estado"]["actual"]) == ("incursion", "notificado")
    assert incidente["origen_demostrado_por"] == ["rastreo"]
    assert incidente["presencia_dron"] == "confirmada"
    # Los partes solo dicen a qué país cruzan: sin punto, se publica sin mapa.
    assert incidente["lugar"] == {"pais": "RO", "nivel": "pais"}
    assert incidente["drones"]["numero"] == {"min": 2, "max": 2}
    # Volver a registrar no la duplica.
    assert incursiones.registrar(almacen, AHORA, MODELOS) == 0


def test_bielorrusia_queda_fuera() -> None:
    almacen = Almacen.abrir()
    con_cruce(almacen, "BY")
    assert incursiones.registrar(almacen, AHORA, MODELOS) == 0


def test_una_incursion_de_la_version_anterior_se_rehace_sin_punto() -> None:
    almacen = Almacen.abrir()
    con_cruce(almacen, "RO")
    incursiones.registrar(almacen, AHORA, MODELOS)
    (incidente,) = almacen.incidentes()
    # Como la guardaba la versión anterior: en una zona fronteriza inventada.
    incidente["lugar"] = {"punto": {"lat": 45.3, "lon": 28.4}, "radio_km": 50, "pais": "RO"}
    incidente["control"]["version_extractor"] = "incursion/1"
    incidente.pop("pruebas")
    almacen.guardar_incidente(incidente, AHORA, MODELOS)
    assert incursiones.registrar(almacen, AHORA, MODELOS) == 1
    (rehecho,) = almacen.incidentes()
    assert rehecho["id"] == incidente["id"]
    assert "punto" not in rehecho["lugar"]
    assert rehecho["control"]["version_extractor"] == incursiones.VERSION
