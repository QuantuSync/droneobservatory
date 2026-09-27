"""Histórico de GDELT sin red: días, reanudación, tope de tiempo y fusión con la base fresca."""

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest

from almacen.base import Almacen
from recogida import gdelt, historico_gdelt
from tests.test_gdelt import ApiFalsa, bruto, descargador

TITULAR = "Droner over Københavns Lufthavn: lufthavnen lukket"


@pytest.fixture
def almacen() -> Iterator[Almacen]:
    a = Almacen.abrir()
    yield a
    a.cerrar()


def test_recorre_por_dias_y_se_reanuda(almacen: Almacen, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(historico_gdelt, "DESDE", datetime(2025, 9, 20, tzinfo=UTC))
    api = ApiFalsa([bruto(1, TITULAR, 30)])
    hasta = datetime(2025, 9, 23, tzinfo=UTC)
    # El reloj se agota tras el primer día.
    tiempos = iter([0.0, 2.0])
    dias = historico_gdelt.recorrer(almacen, descargador(api), hasta, 1.0, lambda: next(tiempos))
    assert dias == 1
    assert almacen.cursor("gdelt_historico") == {"hasta": "2025-09-21T00:00:00Z"}
    dias = historico_gdelt.recorrer(almacen, descargador(api), hasta, float("inf"))
    assert dias == 2
    assert len(almacen.articulos()) == 1


def test_un_dia_sin_respuesta_se_reintenta_y_luego_para(almacen: Almacen) -> None:
    api = ApiFalsa([])
    api.fallar = True
    esperas: list[float] = []
    dias = historico_gdelt.recorrer(
        almacen,
        descargador(api),
        historico_gdelt.DESDE + timedelta(days=2),
        float("inf"),
        dormir=esperas.append,
    )
    assert dias == 0
    assert len(esperas) == historico_gdelt.MAX_FALLOS_SEGUIDOS - 1
    assert almacen.cursor("gdelt_historico") is None


def test_fusion_con_la_base_fresca(almacen: Almacen) -> None:
    gdelt.incorporar(almacen, [bruto(1, TITULAR, 30), bruto(2, TITULAR + " - TV2", 29)])
    almacen.guardar_cursor("gdelt_historico", {"hasta": "2025-09-22T00:00:00Z"})
    fresca = Almacen.abrir()
    fresca.guardar_cursor("gdelt", {"hasta": "2025-09-23T12:00:00Z", "inicio": "x"})
    historico_gdelt.fusionar(almacen, fresca)
    (articulo,) = fresca.articulos()
    assert articulo["replicas"] == 1
    assert articulo["candidato"] == almacen.articulos()[0]["candidato"]
    assert fresca.candidatos() == almacen.candidatos()
    assert fresca.cursor("gdelt_historico") == {"hasta": "2025-09-22T00:00:00Z"}
    assert fresca.cursor("gdelt") == {"hasta": "2025-09-23T12:00:00Z", "inicio": "x"}
    # Fusionar dos veces no duplica réplicas.
    historico_gdelt.fusionar(almacen, fresca)
    assert fresca.articulos()[0]["replicas"] == 1
    fresca.cerrar()
