"""Alertas aéreas por zonas: la noche del 10 al 11 de noviembre de 2026 en Letonia. Las notas
reales de mil.lv, leídas desde el servidor el 11, y la ficha EODI-2026-00777 tal como estaba."""

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from proceso import alertas_zona, suceso
from proceso.noticias import filtro
from recogida import oficiales, paginas_oficiales

FIXTURES = Path(__file__).resolve().parent / "fixtures"
CASO = json.loads((FIXTURES / "alertas_2026-11-11.json").read_text(encoding="utf-8"))
F777 = CASO["EODI-2026-00777"]
SMILTENE = (
    "papildinats-plkst-0318-gaisa-telpas-apdraudejums-izsludinats-smiltenes-un-gulbenes-novados"
)
ANULADA_SMILTENE = (
    "atcelts-latvijas-gaisa-telpas-apdraudejums-smiltenes-un-gulbenes-novados-plkst-0330"
)
ANULADA_BALVI = "atcelts-latvijas-gaisa-telpas-apdraudejums-balvu-novada"
TITULOS = {
    SMILTENE: "PAPILDINĀTS plkst. 03:18 – Gaisa telpas apdraudējums izsludināts Smiltenes un "
    "Gulbenes novados; Apdraudējums atcelts Cēsu novadā",
    ANULADA_SMILTENE: "Atcelts Latvijas gaisa telpas apdraudējums Smiltenes un Gulbenes novados "
    "plkst. 03.30",
    ANULADA_BALVI: "Atcelts Latvijas gaisa telpas apdraudējums Balvu novadā",
}


def _mil_lv() -> dict[str, Any]:
    return next(f for f in oficiales.fuentes() if f["id"] == "mil_lv")


def _hora() -> str:
    return str(_mil_lv()["alertas_por_zona"]["hora"])


def _nota(nombre: str) -> oficiales.Nota:
    html = (FIXTURES / "mil_lv" / f"{nombre}.html").read_text(encoding="utf-8")
    leido = paginas_oficiales.contenido(html, _mil_lv(), TITULOS[nombre])
    assert leido is not None
    fecha, precision, texto = leido
    enlace = f"https://www.mil.lv/lv/zinas/{nombre}"
    id_ = paginas_oficiales.identificador(_mil_lv(), enlace)
    return oficiales.Nota(_mil_lv(), id_, TITULOS[nombre], enlace, fecha, texto, precision)


class _Base:
    """Lo que `oficiales.posibles` pide al almacén."""

    def __init__(self, *fichas: dict[str, Any]) -> None:
        self._fichas = list(fichas)

    def incidentes(self) -> list[dict[str, Any]]:
        return self._fichas


def test_los_titulos_nuevos_de_mil_lv_se_abren() -> None:
    """El 11 de noviembre de 2026 solo entraron dos de las siete notas de la noche: «Izsludināts
    gaisa telpas apdraudējums…» y «… Gaisa telpas apdraudējums izsludināts…» no casaban con
    «apdraudējums Latvijas gaisa telp» y no se abrían. Las que anulan una alerta («Atcelts…») no
    se abren: no dicen nada nuevo del suceso y la fuente rozaba su tope de tiempo."""
    pagina = (FIXTURES / "mil_lv" / "zinas-2026-11-11.html").read_text(encoding="utf-8")
    dron = filtro().dron
    interesan = [
        t
        for _, t in paginas_oficiales.enlaces(pagina, _mil_lv())
        if paginas_oficiales.interesa(t, _mil_lv(), dron)
    ]
    assert len(interesan) == 4
    assert any(t.startswith("PAPILDINĀTS plkst. 03:18") for t in interesan)
    assert any(t.startswith("PAPILDINĀTS plkst. 01:25") for t in interesan)
    assert any(t.startswith("PAPILDINĀTS 11.NOV plkst. 00.23") for t in interesan)
    assert "Izsludināts gaisa telpas apdraudējums Ludzas novadā" in interesan
    assert not any(t.startswith("Atcelt") or "Lāčplēša" in t for t in interesan)


def test_de_mil_lv_se_abren_tres_notas_por_pasada() -> None:
    """mil.lv tarda y corta conexiones: con cinco notas, su lista y su robots.txt la fuente
    llegaba a su tope de 45 s (43 s medidos desde el servidor el 11 de noviembre de 2026)."""
    pagina = (FIXTURES / "mil_lv" / "zinas-2026-11-11.html").read_text(encoding="utf-8")
    pedidas: list[str] = []

    class _Descargador:
        def texto(self, url: str, valido: Any) -> str:
            pedidas.append(url)
            nombre = url.rsplit("/", 1)[-1]
            return (FIXTURES / "mil_lv" / f"{SMILTENE}.html").read_text(encoding="utf-8") + nombre

    class _Robots:
        def can_fetch(self, agente: str, url: str) -> bool:
            return True

    descargador: Any = _Descargador()
    robots: Any = _Robots()
    notas = oficiales.leer_pagina(descargador, robots, _mil_lv(), pagina)
    assert _mil_lv()["max_notas"] == 3
    assert len(pedidas) == len(notas) == 3
    # Las más recientes: la de las 03.18, la de las 01.25 y la de las 00.23.
    assert [n.titulo[:30] for n in notas] == [
        "PAPILDINĀTS plkst. 03:18 – Gai",
        "PAPILDINĀTS plkst. 01:25 - Ies",
        "PAPILDINĀTS 11.NOV plkst. 00.2",
    ]


def test_la_nota_de_smiltene_da_su_dia_y_cuenta_un_suceso() -> None:
    nota = _nota(SMILTENE)
    assert (nota.fecha, nota.precision) == (datetime(2026, 11, 11, tzinfo=UTC), "dia")
    assert "11. novembrī no plkst. 03:18 Latvijas gaisa telpā Smiltenes un Gulbenes" in nota.texto
    assert filtro().dron.search(f"{nota.titulo} {nota.texto}")
    assert oficiales.suceso(nota)


def test_zonas_y_horas_de_un_titulo() -> None:
    zonas = alertas_zona.zonas(TITULOS[SMILTENE], "LV")
    assert len(zonas) == 2  # Smiltene y Gulbene (Cēsis no está en el nomenclátor)
    assert alertas_zona.horas(TITULOS[SMILTENE], _hora()) == {3 * 60 + 18}
    assert alertas_zona.horas(TITULOS[ANULADA_SMILTENE], _hora()) == {3 * 60 + 30}
    # Una fecha no es una hora: «11.NOV plkst. 00.23» da solo las 00.23.
    assert alertas_zona.horas("PAPILDINĀTS 11.NOV plkst. 00.23 Iespējams", _hora()) == {23}


def test_las_notas_que_guarda_la_ficha_de_la_autoridad() -> None:
    de_la_ficha = suceso.notas_de(F777, _mil_lv())
    assert len(de_la_ficha) == 3  # las de las 00.23 y las 01.25, y la frase de la primera
    assert alertas_zona.zonas(" . ".join(de_la_ficha), "LV")
    assert alertas_zona.horas(" . ".join(de_la_ficha), _hora())


def test_la_alerta_de_smiltene_es_de_la_ficha_de_esa_noche() -> None:
    """Las alertas que una autoridad va dando por zonas en una noche son el mismo suceso
    (docs/definicion_suceso.md). Del 11 de noviembre de 2026 a las 11:41 hasta la definición
    hubo una regla («otra zona y otra hora es otra alerta») por la que la nota de las 03.18 no
    era de EODI-2026-00777 y entraba como suceso propio: la misma noche de Letonia, en dos."""
    base: Any = _Base(F777)
    ids = [i["id"] for i in oficiales.posibles(base, _nota(SMILTENE))]
    assert ids == ["EODI-2026-00777"]
    assert [i["id"] for i in oficiales.posibles(base, _nota(ANULADA_BALVI))] == ["EODI-2026-00777"]
    # Y nada en la definición las da por sucesos distintos: no hay regla de zonas.
    smiltene = {
        **F777,
        "id": "EODI-2026-09790",
        "fuentes": [
            {
                **F777["fuentes"][0],
                "id": "gdelt-smiltene",
                "es_autoridad": False,
                "enlace": f"https://www.mil.lv/lv/zinas/{SMILTENE}",
                "frase_origen": TITULOS[SMILTENE],
            }
        ],
    }
    assert suceso.nunca_el_mismo(smiltene, F777) is None


def test_las_fuentes_que_dan_sus_alertas_por_zonas() -> None:
    assert [f["id"] for f in oficiales.fuentes() if f.get("alertas_por_zona")] == [
        "mil_lv", "mod_lv",
    ]  # fmt: skip
    assert [f["id"] for f in suceso._fuentes_por_zonas()] == ["mil_lv", "mod_lv"]
