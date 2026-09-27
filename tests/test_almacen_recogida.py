import sqlite3
from collections.abc import Iterator

import pytest

from almacen.base import Almacen
from tests import ejemplos
from tests.ejemplos import AHORA


@pytest.fixture
def almacen() -> Iterator[Almacen]:
    a = Almacen.abrir()
    yield a
    a.cerrar()


def test_cursor_por_fuente(almacen: Almacen) -> None:
    assert almacen.cursor("fuerza_aerea_ua") is None
    almacen.guardar_cursor("fuerza_aerea_ua", {"ultimo_id": 10})
    almacen.guardar_cursor("fuerza_aerea_ua", {"ultimo_id": 12})
    assert almacen.cursor("fuerza_aerea_ua") == {"ultimo_id": 12}
    with pytest.raises(sqlite3.IntegrityError, match="nada se borra"):
        almacen.conexion.execute("DELETE FROM cursores")


def test_partes_fallidos_se_registran_y_se_resuelven(almacen: Almacen) -> None:
    almacen.registrar_fallido("https://t.me/kpszsu/2", "fa", "sin periodo declarado", "2026-01-02")
    almacen.registrar_fallido("https://t.me/kpszsu/1", "fa", "sin cifras de drones", "2026-01-01")
    assert [f["enlace"] for f in almacen.fallidos("fa")] == [
        "https://t.me/kpszsu/1",
        "https://t.me/kpszsu/2",
    ]
    almacen.resolver_fallido("https://t.me/kpszsu/1")
    assert [f["motivo"] for f in almacen.fallidos("fa")] == ["sin periodo declarado"]
    # Resuelto no es borrado: la fila sigue en la base.
    (total,) = almacen.conexion.execute("SELECT count(*) FROM partes_fallidos").fetchone()
    assert total == 2
    with pytest.raises(sqlite3.IntegrityError, match="nada se borra"):
        almacen.conexion.execute("DELETE FROM partes_fallidos")


def test_busca_ataques_por_fuente_y_por_periodo(almacen: Almacen) -> None:
    ataque = ejemplos.ataque_completo()
    almacen.guardar_ataque_ucrania(ataque, AHORA)
    assert almacen.ataque_con_fuente("P1") == ataque
    assert almacen.ataque_con_fuente("P9") is None
    inicio = ataque["periodo"]["inicio"]["valor"]
    assert almacen.ataque_con_periodo("RU_UA", inicio) == ataque
    assert almacen.ataque_con_periodo("UA_RU", inicio) is None
    assert almacen.ataque_con_periodo("RU_UA", "2025-10-05T16:00Z") is None


def test_identificadores_correlativos_por_anio(almacen: Almacen) -> None:
    assert almacen.siguiente_id_ataque(2025) == "EODI-UA-2025-0001"
    almacen.guardar_ataque_ucrania(ejemplos.ataque_completo(), AHORA)
    assert almacen.siguiente_id_ataque(2025) == "EODI-UA-2025-0002"
    assert almacen.siguiente_id_ataque(2024) == "EODI-UA-2024-0001"
