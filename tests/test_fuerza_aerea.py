from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from almacen.base import Almacen
from recogida.cache import CachePaginas
from recogida.ejecucion import SinCursor, ejecutar
from recogida.fuerza_aerea import CanalNoVerificado, HuecoDemasiadoGrande, leer_desde, verificar
from recogida.recorrido import pagina
from recogida.telegram import Pagina
from tests.telegram_falso import CanalFalso, descargador

AHORA = datetime(2026, 9, 28, tzinfo=UTC)
PARTE = (
    "⚡️ ЗБИТО/ПОДАВЛЕНО {derribados} ВОРОЖИХ БПЛА\n\n"
    "У ніч на {dia} вересня (з 18:00 {vispera} вересня) противник атакував {lanzados} ударними "
    "БпЛА типу Shahed із напрямків: Курськ, Орел – рф.\n\n"
    "За попередніми даними, станом на 08:00, збито/подавлено {derribados} ворожих БпЛА."
)


def parte(dia: int, lanzados: int, derribados: int) -> str:
    return PARTE.format(dia=dia, vispera=dia - 1, lanzados=lanzados, derribados=derribados)


def canal() -> CanalFalso:
    base = datetime(2026, 9, 20, 5, tzinfo=UTC)
    textos = {
        1: "БпЛА курсом на Київ.",
        2: parte(20, 50, 40),
        3: "Відбій тривоги.",
        4: parte(21, 60, 55),
        5: "У ніч на 22 вересня противник атакував Україну. Деталі згодом, БпЛА.",
        6: parte(22, 70, 65),
        7: "Загроза БпЛА на сході.",
    }
    return CanalFalso({i: (base + timedelta(days=i // 2, minutes=i), t) for i, t in textos.items()})


@pytest.fixture
def almacen() -> Iterator[Almacen]:
    a = Almacen.abrir()
    yield a
    a.cerrar()


def portada(falso: CanalFalso, tmp_path: Path) -> Pagina:
    return pagina(descargador(falso), CachePaginas(tmp_path), "kpszsu", None, usar_cache=False)


def test_canal_oficial_verificado(tmp_path: Path) -> None:
    falso = canal()
    verificar(descargador(falso), portada(falso, tmp_path))
    assert falso.web in falso.pedidas


@pytest.mark.parametrize(
    ("cambio", "motivo"),
    [
        ({"verificado": False}, "insignia"),
        ({"titulo": "Повітряні новини"}, "título"),
        ({"web": "https://t.me/otro"}, "ninguna web"),
        ({"web_enlaza": "<html>sin enlaces</html>"}, "ya no enlaza"),
        ({"web_enlaza": '<html><a href="https://t.me/kpszsu_falso">x</a></html>'}, "ya no enlaza"),
    ],
)
def test_canal_no_verificado(cambio: dict[str, object], motivo: str, tmp_path: Path) -> None:
    falso = canal()
    for clave, valor in cambio.items():
        setattr(falso, clave, valor)
    with pytest.raises(CanalNoVerificado, match=motivo):
        verificar(descargador(falso), portada(falso, tmp_path))


def test_la_web_oficial_admite_el_enlace_codificado(tmp_path: Path) -> None:
    falso = canal()
    falso.web_enlaza = '<html><a href="https://www.google.com/url?q=https://t.me%2Fkpszsu&x=1">'
    verificar(descargador(falso), portada(falso, tmp_path))


def test_lee_hacia_atras_hasta_el_cursor(tmp_path: Path) -> None:
    falso = canal()
    d = descargador(falso)
    lectura = leer_desde(d, CachePaginas(tmp_path), portada(falso, tmp_path), 2)
    assert [p.id for p in lectura.publicaciones] == [3, 4, 5, 6, 7]
    assert lectura.paginas == 2


def test_hueco_demasiado_grande(tmp_path: Path) -> None:
    falso = canal()
    with pytest.raises(HuecoDemasiadoGrande):
        leer_desde(
            descargador(falso), CachePaginas(tmp_path), portada(falso, tmp_path), 0, max_paginas=2
        )


def test_ejecucion_completa(almacen: Almacen, tmp_path: Path) -> None:
    falso = canal()
    almacen.guardar_cursor("fuerza_aerea_ua", {"ultimo_id": 1})
    recuentos = ejecutar(almacen, descargador(falso), CachePaginas(tmp_path), AHORA)
    assert (recuentos.publicaciones, recuentos.partes, recuentos.leidos) == (6, 4, 3)
    assert (recuentos.fallidos, recuentos.nuevos) == (1, 3)
    assert recuentos.motivos == {"sin cifras de drones": 1}
    assert almacen.cursor("fuerza_aerea_ua") == {
        "ultimo_id": 7,
        "fecha": falso.publicaciones[7][0].isoformat(),
    }
    assert [a["derribados"] for a in almacen.ataques_ucrania()] == [
        {"min": 40, "max": 40},
        {"min": 55, "max": 55},
        {"min": 65, "max": 65},
    ]
    (fallido,) = almacen.fallidos("fuerza_aerea_ua")
    assert fallido["enlace"] == "https://t.me/kpszsu/5"


def test_sin_cambios_nuevos_no_toca_nada(almacen: Almacen, tmp_path: Path) -> None:
    falso = canal()
    almacen.guardar_cursor("fuerza_aerea_ua", {"ultimo_id": 7})
    recuentos = ejecutar(almacen, descargador(falso), CachePaginas(tmp_path), AHORA)
    assert recuentos.publicaciones == 0
    assert almacen.cursor("fuerza_aerea_ua") == {"ultimo_id": 7}


def test_sin_cursor_no_lee(almacen: Almacen, tmp_path: Path) -> None:
    falso = canal()
    with pytest.raises(SinCursor):
        ejecutar(almacen, descargador(falso), CachePaginas(tmp_path), AHORA)
    assert falso.pedidas == []


def test_canal_no_verificado_no_lee_nada(almacen: Almacen, tmp_path: Path) -> None:
    falso = canal()
    falso.verificado = False
    almacen.guardar_cursor("fuerza_aerea_ua", {"ultimo_id": 1})
    with pytest.raises(CanalNoVerificado):
        ejecutar(almacen, descargador(falso), CachePaginas(tmp_path), AHORA)
    assert almacen.ataques_ucrania() == []
    assert almacen.cursor("fuerza_aerea_ua") == {"ultimo_id": 1}


def test_relee_las_ultimas_48_horas_y_recoge_un_parte_editado(
    almacen: Almacen, tmp_path: Path
) -> None:
    falso = canal()
    almacen.guardar_cursor("fuerza_aerea_ua", {"ultimo_id": 1})
    # Un día después del último parte: el 6 queda dentro de las 48 horas y el 2, fuera.
    ahora = falso.publicaciones[7][0] + timedelta(days=1)
    ejecutar(almacen, descargador(falso), CachePaginas(tmp_path), ahora)
    fecha, _ = falso.publicaciones[6]
    falso.publicaciones[6] = (fecha, parte(22, 70, 68))
    antes = almacen.conexion.serialize()
    recuentos = ejecutar(almacen, descargador(falso), CachePaginas(tmp_path), ahora)
    assert recuentos.actualizados == 1
    assert almacen.conexion.serialize() != antes
    editado = next(a for a in almacen.ataques_ucrania() if a["derribados"]["min"] == 68)
    cambios = [h for h in almacen.historial(editado["id"]) if h["operacion"] == "cambio"]
    assert [h["anterior"]["derribados"] for h in cambios if h["tabla"] == "ataques_ucrania"] == [
        {"min": 65, "max": 65}
    ]


def test_releer_sin_cambios_no_toca_la_base(almacen: Almacen, tmp_path: Path) -> None:
    falso = canal()
    almacen.guardar_cursor("fuerza_aerea_ua", {"ultimo_id": 1})
    ahora = falso.publicaciones[7][0] + timedelta(hours=1)
    ejecutar(almacen, descargador(falso), CachePaginas(tmp_path), ahora)
    antes = almacen.conexion.serialize()
    recuentos = ejecutar(almacen, descargador(falso), CachePaginas(tmp_path), ahora)
    assert recuentos.publicaciones > 0
    assert (recuentos.nuevos, recuentos.actualizados) == (0, 0)
    assert almacen.conexion.serialize() == antes
