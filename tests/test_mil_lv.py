"""Fuerzas Armadas Nacionales de Letonia (mil.lv, NBS): la lista de noticias y tres notas reales
de drones y espacio aéreo del 22 y el 24 de octubre de 2026, leídas desde el servidor el 28."""

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from proceso import autoridades
from recogida import oficiales, paginas_oficiales

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "mil_lv"
NOTAS = [
    (
        "aluksnes-novada-atrasts-bezpilota-lidaparats",
        "Alūksnes novadā atrasts bezpilota lidaparāts",
        datetime(2026, 10, 24, tzinfo=UTC),
        "Sestdien, 24. oktobrī, Alūksnes novada Liepnas pagastā atrasts bezpilota lidaparāts",
    ),
    (
        "iespejams-apdraudejums-latvijas-gaisa-telpa-kraslavas-uz-rezeknes-novada",
        "Iespējams apdraudējums Latvijas gaisa telpā Krāslavas uz Rēzeknes novadā",
        datetime(2026, 10, 22, tzinfo=UTC),
        "no plkst. 12.39 iespējams apdraudējums Latvijas gaisa telpā",
    ),
    (
        "iespejams-apdraudejums-latvijas-gaisa-telpa-nosledzies",
        "Iespējams apdraudējums Latvijas gaisa telpā noslēdzies",
        datetime(2026, 10, 22, tzinfo=UTC),
        "ir noslēdzies plkst. 13.16",
    ),
]


def _fuente() -> dict[str, Any]:
    return next(f for f in oficiales.fuentes() if f["id"] == "mil_lv")


def test_la_fuente_de_las_fuerzas_armadas_de_letonia() -> None:
    fuente = _fuente()
    assert fuente["medio"] == "Nacionālie bruņotie spēki"
    assert (fuente["pais"], fuente["idioma"], fuente["zona"], fuente["tipo"]) == (
        "LV", "lv", "Europe/Riga", "pagina",
    )  # fmt: skip
    assert fuente["url"] == "https://www.mil.lv/lv/zinas"


def test_la_lista_da_las_notas_con_su_direccion_y_su_titulo() -> None:
    pagina = (FIXTURES / "zinas.html").read_text(encoding="utf-8")
    enlaces = paginas_oficiales.enlaces(pagina, _fuente())
    assert len(enlaces) == 10
    assert all(d.startswith("https://www.mil.lv/lv/zinas/") for d, _ in enlaces)
    for nombre, titulo, _, _ in NOTAS:
        assert (f"https://www.mil.lv/lv/zinas/{nombre}", titulo) in enlaces


@pytest.mark.parametrize(("nombre", "titulo", "fecha", "frase"), NOTAS)
def test_cada_nota_da_su_dia_y_su_texto(
    nombre: str, titulo: str, fecha: datetime, frase: str
) -> None:
    html = (FIXTURES / f"{nombre}.html").read_text(encoding="utf-8")
    resultado = paginas_oficiales.contenido(html, _fuente(), titulo)
    assert resultado is not None
    publicada, precision, texto = resultado
    assert (publicada, precision) == (fecha, "dia")
    assert frase in texto


def test_su_organismo_en_las_dos_lenguas() -> None:
    nbs = autoridades.tabla()["Nacionālie bruņotie spēki"]
    assert nbs["es"] == "las Fuerzas Armadas Nacionales de Letonia"
    assert nbs["en"] == "the Latvian National Armed Forces"
