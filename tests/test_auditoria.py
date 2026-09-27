"""Auditoría de cobertura: días sin parte y explicación de las publicaciones de esa mañana."""

from datetime import UTC, date, datetime

import pytest

from recogida import auditoria
from recogida.parte import KYIV, PALABRAS_DRON, es_parte, motivo_no_parte
from recogida.telegram import Publicacion

PARTE = "У ніч на {d} травня противник атакував 20 ударними БпЛА. Збито 18 ударних БпЛА."


def publicacion(id_: int, dia: int, hora_utc: int, texto: str) -> Publicacion:
    return Publicacion("kpszsu", id_, datetime(2023, 5, dia, hora_utc, tzinfo=UTC), texto)


def auditar(lista: list[Publicacion]) -> auditoria.Anio:
    resultado = auditoria.auditar(
        lista,
        KYIV,
        date(2023, 5, 1),
        date(2023, 5, 4),
        es_parte,
        lambda p: "Збито" in p.texto,
        PALABRAS_DRON,
        motivo_no_parte,
    )
    return resultado[2023]


def test_cuenta_dias_con_y_sin_parte_y_explica_los_huecos() -> None:
    lista = [
        publicacion(1, 1, 5, PARTE.format(d=1)),
        # Día 2: solo reconocimiento por la mañana.
        publicacion(2, 2, 6, "Знищено 3 розвідувальні БпЛА «Орлан-10»."),
        # Día 3: un formato que el detector no reconoce.
        publicacion(3, 3, 6, "Уночі окупанти нападали 12 ударними БпЛА на Одещину."),
        # Día 4: nada con cifras; la alerta de la tarde no cuenta.
        publicacion(4, 4, 15, "Група БпЛА курсом на Київ, 3 шт."),
    ]
    anio = auditar(lista)
    assert (anio.dias, anio.partes, anio.fallidos) == (4, 1, 0)
    assert (anio.dias_con_parte, anio.dias_sin_parte) == (1, 3)
    assert dict(anio.explicados) == {
        "solo drones de reconocimiento": 1,
        "sin publicaciones de drones con cifras esa mañana": 1,
    }
    assert anio.sin_explicar == ["https://t.me/kpszsu/3"]


def test_parte_detectado_pero_ilegible_cuenta_como_fallido() -> None:
    ilegible = "У ніч на 1 травня противник атакував Україну ударними БпЛА. Деталі згодом."
    anio = auditar([publicacion(1, 1, 5, ilegible)])
    assert (anio.partes, anio.fallidos, anio.dias_con_parte) == (1, 1, 1)


@pytest.mark.parametrize(
    ("texto", "motivo"),
    [
        ("💥 На відео – бойова робота. Збито 5 БпЛА.", "pie de vídeo"),
        (
            'Уночі 23 травня в зоні відповідальності повітряного командування "Схід" знищено '
            "шість ударних БпЛА.",
            "nota de un mando regional",
        ),
        ("Знищено 4 ударні БпЛА «Shahed».", "solo derribos, sin ataque declarado"),
        ("На рахунку Олександра 20 шахедів.", "otro tema (reportaje, balance, alerta)"),
        ("Цієї ночі, 28 листопада, знищено ударний БпЛА «Shahed».", "sin cifras de drones"),
    ],
)  # fmt: skip
def test_motivos_de_no_parte(texto: str, motivo: str) -> None:
    assert motivo_no_parte(texto) == motivo


def test_la_tabla_lleva_los_partes_de_antes() -> None:
    anio = auditoria.Anio(dias=4, partes=1, dias_sin_parte=3, sin_explicar=["x"])
    tabla = auditoria.tabla({2023: anio}, antes={2023: 0})
    assert tabla.splitlines()[2] == "| 2023 | 4 | 0 | 1 | 0 | 3 | 1 |"
