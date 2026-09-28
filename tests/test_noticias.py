"""Noticias: URL canónica, réplicas, filtro sin modelo, lugares y regla de fusión."""

from datetime import UTC, datetime, timedelta

import pytest

from proceso.noticias import (
    Agrupacion,
    Articulo,
    Lugar,
    Nomenclator,
    agrupar,
    casi_iguales,
    filtro,
    lugares_en,
    nomenclator,
    titular_normalizado,
    url_canonica,
)

T0 = datetime(2025, 9, 22, 20, tzinfo=UTC)


def lugar(id_: str, lat: float, lon: float, tipo: str = "aeropuerto") -> Lugar:
    return Lugar(id_, tipo, id_, lat, lon, 5.0, "DK", (id_,), ())


# Copenhague y Oslo; una base a 15 km de Copenhague (5 + 5 + 10 = 20 km de margen).
CPH = lugar("EKCH", 55.61806, 12.65611)
OSL = lugar("ENGM", 60.19392, 11.10036)
CERCA = lugar("base:1", 55.7, 12.85, "base")
# Otro aeropuerto a 15 km de Copenhague: se funde con él (menos de 20 km).
CPH2 = lugar("EKCH2", 55.7, 12.85)
NOM = Nomenclator({x.id: x for x in (CPH, OSL, CERCA, CPH2)}, (), (), {})


def articulo(
    n: int, horas: float, sitio: str, titular: str = "Drones over the airport"
) -> Articulo:
    return Articulo(
        f"https://m.eu/{n}", "m.eu", T0 + timedelta(hours=horas), titular, lugares=(sitio,)
    )


# --- Normalización ---------------------------------------------------------------


@pytest.mark.parametrize(
    ("url", "canonica"),
    [
        ("http://www.Ejemplo.eu/a/b/?utm_source=x&id=3#arriba", "https://ejemplo.eu/a/b?id=3"),
        ("https://ejemplo.eu/a?b=2&a=1&fbclid=z", "https://ejemplo.eu/a?a=1&b=2"),
        ("https://ejemplo.eu", "https://ejemplo.eu/"),
    ],
)
def test_url_canonica(url: str, canonica: str) -> None:
    assert url_canonica(url) == canonica


def test_titulares_casi_identicos_son_replicas() -> None:
    a = titular_normalizado("Drones sighted over Copenhagen Airport, flights halted - The Local")
    b = titular_normalizado("Drones sighted over Copenhagen airport; flights halted | Reuters Wire")
    assert a == "drones sighted over copenhagen airport flights halted"
    assert casi_iguales(a, b)
    otro = titular_normalizado("Drones sighted over Oslo Airport, flights halted")
    assert not casi_iguales(a, otro)
    # Titulares cortos: solo la igualdad.
    assert not casi_iguales("drones en barajas", "drones en el prat")


# --- Filtro y lugares ------------------------------------------------------------


@pytest.mark.parametrize(
    ("titular", "pasa"),
    [
        ("Drohnen über Flughafen München: Flugbetrieb eingestellt", True),
        ("Drony nad lotniskiem w Rzeszowie", True),
        ("Nuevo espectáculo de drones en Benidorm", False),
        ("Mejores drones para regalar: oferta", False),
        # Dron sin señal de incidente ni lugar conocido.
        ("Wie funktioniert eine Drohne?", False),
        ("Stock market closes higher", False),
    ],
)
def test_filtro_sin_modelo(titular: str, pasa: bool) -> None:
    f = filtro()
    assert f.pasa(titular, lugares_en(titular, nomenclator())) is pasa


def test_lugares_por_alias_y_por_ciudad_con_tipo_de_lugar() -> None:
    nom = nomenclator()
    assert lugares_en("Drohnen über dem Flughafen München gesichtet", nom) == ("EDDM",)
    assert lugares_en("Drones spotted near Munich airport", nom) == ("EDDM",)
    # La ciudad sola no basta: puede ser la ciudad y no su aeropuerto.
    assert lugares_en("Drones over Munich city centre", nom) == ()
    assert "ETAR" in lugares_en("Drones sighted over Ramstein Air Base", nom)


def test_tipo_aparente() -> None:
    f = filtro()
    assert f.tipo("Drones over Copenhagen", CPH) == "aeropuerto"
    assert f.tipo("Drones violate Polish airspace", None) == "espacio_aereo"


# --- Regla de fusión -------------------------------------------------------------


def test_mismo_objetivo_mismo_dia_y_siguiente_se_funden() -> None:
    grupo = agrupar([articulo(1, 0, "EKCH"), articulo(2, 5, "EKCH")], filtro(), NOM)
    assert [len(c.articulos) for c in grupo.candidatos] == [2]


def test_puntos_cercanos_se_funden_y_lejanos_no() -> None:
    cerca = agrupar(
        [articulo(1, 0, "EKCH"), articulo(2, 1, "base:1", "Drones over the air base")],
        filtro(),
        NOM,
    )
    # El tipo aparente distinto (aeropuerto y militar) no se funde aunque esté cerca.
    assert len(cerca.candidatos) == 2
    mismo_tipo = agrupar([articulo(1, 0, "EKCH"), articulo(2, 1, "EKCH2")], filtro(), NOM)
    assert len(mismo_tipo.candidatos) == 1
    lejos = agrupar([articulo(1, 0, "EKCH"), articulo(2, 1, "ENGM")], filtro(), NOM)
    assert len(lejos.candidatos) == 2


def test_mas_de_12_horas_sin_actividad_es_un_candidato_nuevo() -> None:
    grupo = agrupar([articulo(1, 0, "EKCH"), articulo(2, 13, "EKCH")], filtro(), NOM)
    assert len(grupo.candidatos) == 2


def test_con_precision_de_dia_el_dia_siguiente_se_funde_pero_no_el_otro() -> None:
    serie = [articulo(i, h, "EKCH") for i, h in enumerate([0, 11, 22, 33, 44])]
    grupo = agrupar(serie, filtro(), NOM)
    # 20:00 del 22, 07:00, 18:00 y 05:00 del 24 (ya no es el día siguiente al inicio).
    assert [len(c.articulos) for c in grupo.candidatos] == [3, 2]


def test_con_precision_de_hora_inicios_a_menos_de_6_horas() -> None:
    grupo = agrupar(
        [articulo(1, 0, "EKCH"), articulo(2, 5, "EKCH"), articulo(3, 10, "EKCH")],
        filtro(),
        NOM,
        precision="hora",
    )
    assert [len(c.articulos) for c in grupo.candidatos] == [2, 1]


def test_la_agrupacion_dudosa_no_se_hace() -> None:
    varios = Articulo(
        "https://m.eu/x", "m.eu", T0, "Drones over airports", lugares=("EKCH", "ENGM")
    )
    sin_lugar = Articulo("https://m.eu/y", "m.eu", T0, "Drones over Europe")
    grupo = agrupar([varios, sin_lugar], filtro(), NOM)
    assert (grupo.candidatos, grupo.dudosos, grupo.sin_lugar) == ([], 1, 1)
    # Encaja en dos candidatos abiertos a la vez: tampoco se agrupa.
    abierto = agrupar([articulo(1, 0, "EKCH")], filtro(), NOM)
    otro = agrupar([articulo(2, 0, "base:1", "Drones over the base")], filtro(), NOM)
    doble = Agrupacion(candidatos=[*abierto.candidatos, *otro.candidatos])
    for candidato in doble.candidatos:
        candidato.tipo = "aeropuerto"
    agrupar([articulo(3, 1, "EKCH")], filtro(), NOM, doble)
    assert doble.dudosos == 1


@pytest.mark.parametrize(
    "titular",
    [
        # «lentokenttä» es «aeropuerto» en finés, no el nombre de uno.
        "Alicanten lentokenttä suljettiin – Epäily drooneista",
        # «Militär» y «wojskowa» figuran como ciudad de dos lugares, pero son palabras comunes.
        "VIDEO // Un militar ucrainean face o demonstrație despre drone",
        "Ukraińskie drony uderzyły w głąb Rosji. Celowali w bazę wojskową",
    ],
)
def test_palabras_comunes_no_son_lugares(titular: str) -> None:
    assert lugares_en(titular, nomenclator()) == ()
