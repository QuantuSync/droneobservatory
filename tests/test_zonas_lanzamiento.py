"""Nombres normalizados de las zonas de lanzamiento (docs/informe_errores_datos.md, bloque 3):
las grafías de los partes, las zonas genéricas, lo que no es una zona, el registro de revisión,
la corrección de los ataques guardados y que el motor de deducción y la web casen el nombre
normalizado con su zona del catálogo."""

import copy
from datetime import UTC, datetime

import pytest

from almacen.base import Almacen
from proceso import zonas_lanzamiento as zl
from proceso.deduccion import catalogo
from tests import ejemplos

AHORA = datetime(2026, 10, 4, 10, 0, tzinfo=UTC)


@pytest.mark.parametrize(
    ("escrito", "normalizado"),
    [
        ("Міллерово", ("Міллерово",)),
        ("Міллєрово", ("Міллерово",)),
        ("Мілерово", ("Міллерово",)),
        ("Міллєрово – рф", ("Міллерово",)),
        ("Шаталово", ("Шаталово",)),
        ("Шаталове", ("Шаталово",)),
        ("Донецьк", ("Донецьк",)),
        ("Донецьк - України", ("Донецьк",)),
        ("Донецької обл", ("Донецьк",)),
        ("Крим", ("Крим",)),
        ("окупований Крим", ("Крим",)),
        ("мис Чауда – окупований Крим", ("Чауда",)),
        ("Чауда Гвардійське", ("Чауда", "Гвардійське")),
        ("Курська обл", ("Курська область",)),
        ("Приморсько - Ахтарськ", ("Приморсько-Ахтарськ",)),
    ],
)
def test_grafias_de_los_partes(escrito: str, normalizado: tuple[str, ...]) -> None:
    assert zl.normalizar(escrito).zonas == normalizado


def test_lo_que_no_es_una_zona_se_descarta_y_lo_desconocido_va_a_revision() -> None:
    assert zl.normalizar("двома – Х-59/Х-69").descarte is not None
    assert zl.normalizar("через Сумську").descarte is not None
    desconocido = zl.normalizar("Шахти")
    assert desconocido.zonas == () and not desconocido.reconocido
    assert zl.normalizar_lista(["Міллєрово", "Міллерово", "Шахти"]) == (["Міллерово"], ["Шахти"])


def test_cada_nombre_normalizado_casa_con_sus_zonas_del_catalogo() -> None:
    cat = catalogo.cargar()
    for entrada in zl.tabla().zonas:
        assert {z.id for z in cat.zonas_de(entrada.nombre)} == set(entrada.catalogo), entrada
    for direccion in zl.tabla().direcciones:
        assert cat.zonas_de(direccion.nombre) == [] or direccion.nombre == "Крим"


def _ataque(id_: str, zonas: list[str]) -> dict[str, object]:
    documento = ejemplos.ataque_completo()
    documento.update(id=id_, zonas_lanzamiento=zonas)
    documento.pop("zonas_lanzamiento_citadas", None)
    documento.pop("restricciones_aeropuertos", None)
    return documento


def test_correccion_de_los_ataques_guardados_y_registro(monkeypatch: pytest.MonkeyPatch) -> None:
    almacen = Almacen.abrir()
    almacen.guardar_ataque_ucrania(
        copy.deepcopy(_ataque("EODI-UA-2026-0001", ["Міллєрово", "Шаталове", "Шахти"])), AHORA
    )
    resumen = zl.corregir(almacen, AHORA)
    assert resumen["cambiados"] == 1
    ataque = almacen.ataques_ucrania()[0]
    assert ataque["zonas_lanzamiento"] == ["Міллерово", "Шаталово"]
    assert ataque["zonas_lanzamiento_citadas"] == ["Міллєрово", "Шаталове", "Шахти"]
    revisar = almacen.cursor(zl.CURSOR_REVISAR)
    assert revisar is not None
    assert revisar["nombres"] == [{"nombre": "Шахти", "ataques": 1, "ejemplo": "EODI-UA-2026-0001"}]
    assert any("normalizado" in str(h) for h in almacen.historial("EODI-UA-2026-0001"))
    # Una vez por versión de la tabla.
    assert zl.corregir(almacen, AHORA) == {}
