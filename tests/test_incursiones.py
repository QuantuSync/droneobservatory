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
    assert (incidente["lugar"]["pais"], incidente["lugar"]["radio_km"]) == ("RO", 50)
    assert incidente["drones"]["numero"] == {"min": 2, "max": 2}
    # Volver a registrar no la duplica.
    assert incursiones.registrar(almacen, AHORA, MODELOS) == 0


def test_bielorrusia_queda_fuera() -> None:
    almacen = Almacen.abrir()
    con_cruce(almacen, "BY")
    assert incursiones.registrar(almacen, AHORA, MODELOS) == 0
