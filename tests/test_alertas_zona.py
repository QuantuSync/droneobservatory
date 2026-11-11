"""Alertas aéreas por zonas: la noche del 10 al 11 de noviembre de 2026 en Letonia. Las notas
reales de mil.lv, leídas desde el servidor el 11, y la ficha EODI-2026-00777 tal como estaba."""

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from proceso import alertas_zona
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
    gaisa telpas apdraudējums…» y «Atcelts Latvijas gaisa telpas apdraudējums…» no casaban con
    «apdraudējums Latvijas gaisa telp» y no se abrían."""
    pagina = (FIXTURES / "mil_lv" / "zinas-2026-11-11.html").read_text(encoding="utf-8")
    dron = filtro().dron
    interesan = [
        t for _, t in paginas_oficiales.enlaces(pagina, _mil_lv())
        if paginas_oficiales.interesa(t, _mil_lv(), dron)
    ]  # fmt: skip
    assert len(interesan) == 7
    assert TITULOS[ANULADA_SMILTENE] in interesan
    assert any(t.startswith("PAPILDINĀTS plkst. 03:18") for t in interesan)
    assert "Izsludināts gaisa telpas apdraudējums Ludzas novadā" in interesan
    assert not any("Lāčplēša" in t for t in interesan)


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


def test_otra_zona_y_otra_hora_es_otra_alerta() -> None:
    de_la_ficha = oficiales.titulos_de(F777, _mil_lv())
    assert len(de_la_ficha) == 3  # las de las 00.23 y las 01.25, y la frase de la primera
    for nombre in (SMILTENE, ANULADA_SMILTENE):
        assert alertas_zona.otra_alerta(de_la_ficha, [TITULOS[nombre]], "LV", _hora())
    # La nota que anula la de Balvi no escribe la hora ni una zona del nomenclátor: no dice nada.
    assert not alertas_zona.otra_alerta(de_la_ficha, [TITULOS[ANULADA_BALVI]], "LV", _hora())
    # La misma zona a otra hora (la anulación de las 00.35) es la misma alerta.
    anulada = "Atcelti iespējamie Latvijas gaisa telpas apdraudējumi Ludzas, Augšdaugavas un " \
              "Krāslavas novados plkst. 03.35"  # fmt: skip
    assert not alertas_zona.otra_alerta(de_la_ficha, [anulada], "LV", _hora())
    # Otra zona a menos de una hora es la alerta que se amplía al municipio vecino.
    ampliada = "PAPILDINĀTS plkst. 00:50 Gaisa telpas apdraudējums Smiltenes novadā"
    assert not alertas_zona.otra_alerta(de_la_ficha, [ampliada], "LV", _hora())
    # A medianoche el reloj da la vuelta: las 23.25 y las 00.23 están a 58 minutos.
    ludza = "Izsludināts gaisa telpas apdraudējums Ludzas novadā plkst. 23.25"
    solo_kraslava = ["plkst. 00.23 Iespējams apdraudējums Krāslavas novadā"]
    assert not alertas_zona.otra_alerta(solo_kraslava, [ludza], "LV", _hora())


def test_la_alerta_de_smiltene_no_se_enlaza_a_la_ficha_de_kraslava() -> None:
    """Con la regla anterior la nota de las 03.18 era de EODI-2026-00777 por ser otra nota de la
    misma autoridad el mismo día. Ahora no encuentra ficha y entra como suceso propio."""
    base: Any = _Base(F777)
    assert oficiales.otra_alerta(F777, _nota(SMILTENE))
    assert oficiales.posibles(base, _nota(SMILTENE)) == []
    assert oficiales.posibles(base, _nota(ANULADA_SMILTENE)) == []
    assert oficiales.lugar_de_candidato(_nota(SMILTENE)) == "loc:455406"  # Smiltene
    # La que anula la de Balvi sigue siendo de la ficha, como antes.
    assert [i["id"] for i in oficiales.posibles(base, _nota(ANULADA_BALVI))] == ["EODI-2026-00777"]


def test_la_regla_solo_vale_para_las_fuentes_que_la_piden() -> None:
    sin_regla = {k: v for k, v in _mil_lv().items() if k != "alertas_por_zona"}
    nota = _nota(SMILTENE)
    otra = oficiales.Nota(
        sin_regla, nota.id, nota.titulo, nota.enlace, nota.fecha, nota.texto, nota.precision
    )
    assert not oficiales.otra_alerta(F777, otra)
    assert [f["id"] for f in oficiales.fuentes() if f.get("alertas_por_zona")] == [
        "mil_lv", "mod_lv",
    ]  # fmt: skip
