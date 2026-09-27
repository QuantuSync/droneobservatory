from collections.abc import Iterator
from datetime import UTC, datetime

import pytest

from almacen.base import Almacen
from proceso.ataques import incorporar
from recogida.ejecucion import configuracion_fuente
from recogida.parte import leer
from recogida.telegram import Publicacion

AHORA = datetime(2026, 9, 28, tzinfo=UTC)
MANANA = datetime(2026, 9, 27, 5, 0, tzinfo=UTC)
TARDE = datetime(2026, 9, 27, 9, 0, tzinfo=UTC)
PARTE = (
    "У ніч на 27 вересня (з 18:00 26 вересня) противник атакував {n} ударними БпЛА типу "
    "Shahed із напрямків: Курськ – рф.\nСтаном на {hora}, збито/подавлено {d} ворожих БпЛА."
)


@pytest.fixture
def almacen() -> Iterator[Almacen]:
    a = Almacen.abrir()
    yield a
    a.cerrar()


def publicar(
    almacen: Almacen, id_: int, fecha: datetime, n: int, d: int, hora: str = "08:00"
) -> str:
    texto = PARTE.format(n=n, d=d, hora=hora)
    publicacion = Publicacion("kpszsu", id_, fecha, texto)
    resultado = incorporar(
        almacen, publicacion, leer(texto, fecha), configuracion_fuente(), texto, AHORA
    )
    return resultado.id


def test_alta_confirmada_por_el_parte_oficial(almacen: Almacen) -> None:
    id_ = publicar(almacen, 10, MANANA, 100, 90)
    assert id_ == "EODI-UA-2026-0001"
    (ataque,) = almacen.ataques_ucrania()
    assert ataque["sentido"] == "RU_UA"
    assert ataque["estado"]["actual"] == "confirmado"
    assert [p["estado"] for p in ataque["estado"]["historial"]] == ["notificado", "confirmado"]
    (fuente,) = ataque["fuentes"]
    assert fuente["id"] == "kpszsu-10"
    assert fuente["enlace"] == "https://t.me/kpszsu/10"
    # Fiabilidad B sin contradicción: credibilidad 2 (B2).
    assert (fuente["fiabilidad"], fuente["credibilidad"]) == ("B", 2)
    assert fuente["publica"] is True
    assert ataque["periodo"]["inicio"] == {"valor": "2026-09-26T15:00Z", "precision": "minuto"}
    assert ataque["zonas_lanzamiento"] == ["Курськ"]


def test_mismo_periodo_actualiza_con_las_cifras_mas_recientes(almacen: Almacen) -> None:
    publicar(almacen, 10, MANANA, 100, 90)
    id_ = publicar(almacen, 20, TARDE, 100, 95, hora="12:00")
    assert id_ == "EODI-UA-2026-0001"
    (ataque,) = almacen.ataques_ucrania()
    assert ataque["derribados"] == {"min": 95, "max": 95}
    assert [f["id"] for f in ataque["fuentes"]] == ["kpszsu-10", "kpszsu-20"]
    # El cambio queda en el historial de la base.
    assert [h["operacion"] for h in almacen.historial(id_)] == ["alta", "cambio"]


def test_un_parte_anterior_no_pisa_las_cifras_nuevas(almacen: Almacen) -> None:
    publicar(almacen, 20, TARDE, 100, 95, hora="12:00")
    publicar(almacen, 10, MANANA, 100, 90)
    (ataque,) = almacen.ataques_ucrania()
    assert ataque["derribados"] == {"min": 95, "max": 95}
    assert [f["id"] for f in ataque["fuentes"]] == ["kpszsu-10", "kpszsu-20"]


def test_reprocesar_el_mismo_parte_no_cambia_nada(almacen: Almacen) -> None:
    id_ = publicar(almacen, 10, MANANA, 100, 90)
    antes = almacen.ataques_ucrania()
    publicar(almacen, 10, MANANA, 100, 90)
    assert almacen.ataques_ucrania() == antes
    assert len(almacen.historial(id_)) == 1
