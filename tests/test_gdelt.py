"""Recogida de GDELT sin red: consultas, partición de ventanas, réplicas y candidatos."""

import json
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import parse_qs, urlsplit

import pytest

from almacen.base import Almacen
from recogida import gdelt
from recogida.descarga import Descargador, Respuesta

AHORA = datetime(2025, 9, 23, 12, tzinfo=UTC)


def bruto(n: int, titular: str, horas: float, pais: str = "Denmark") -> dict[str, Any]:
    return {
        "url": f"https://www.medio{n}.dk/nyhed/{n}?utm_source=x",
        "url_mobile": "",
        "title": titular,
        "seendate": (AHORA - timedelta(hours=horas)).strftime("%Y%m%dT%H%M%SZ"),
        "socialimage": "",
        "domain": f"medio{n}.dk",
        "language": "Danish",
        "sourcecountry": pais,
    }


class ApiFalsa:
    """Devuelve los artículos de la ventana pedida; con `tope` simula el límite de 250."""

    def __init__(self, articulos: list[dict[str, Any]], tope: int = gdelt.MAX_RESULTADOS) -> None:
        self.articulos = articulos
        self.tope = tope
        self.pedidas: list[dict[str, list[str]]] = []
        self.fallar = False

    def __call__(self, url: str, cabeceras: dict[str, str], limite_s: float) -> Respuesta:
        if self.fallar:
            return 429, {}, b"Please limit requests to one every 5 seconds"
        parametros = parse_qs(urlsplit(url).query)
        self.pedidas.append(parametros)
        inicio, fin = parametros["startdatetime"][0], parametros["enddatetime"][0]
        dentro = [a for a in self.articulos if inicio <= a["seendate"].replace("T", "")[:14] < fin][
            : self.tope
        ]
        return 200, {}, json.dumps({"articles": dentro}).encode()


def descargador(api: ApiFalsa) -> Descargador:
    return Descargador(api, dormir=lambda _: None, pausa_minima_s=0)


@pytest.fixture
def almacen() -> Iterator[Almacen]:
    a = Almacen.abrir()
    yield a
    a.cerrar()


def test_consultas_con_palabras_y_grupos_de_paises() -> None:
    consultas = gdelt.consultas()
    assert len(consultas) == -(-42 // gdelt.PAISES_POR_CONSULTA)
    assert all(c.startswith("(drone OR drones OR UAV OR UAVs) (") for c in consultas)
    assert "sourcecountry:germany" in " ".join(consultas)
    assert "sourcecountry:russia" not in " ".join(consultas)


def test_una_ventana_llena_se_parte_en_dos(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(gdelt, "MAX_RESULTADOS", 4)
    # A las 11:57, 11:51 ... 11:27: la hora no cabe y la media hora final tampoco.
    api = ApiFalsa([bruto(i, f"Drone {i}", 0.05 + i / 10) for i in range(6)], tope=4)
    articulos = gdelt.pedir(descargador(api), "q", AHORA - timedelta(hours=1), AHORA)
    assert len(articulos) == 6
    assert len(api.pedidas) == 5


def test_respuesta_de_error_en_texto_no_es_valida() -> None:
    assert not gdelt.es_json("Your search contained a phrase that was too short")
    assert gdelt.es_json(' {"articles": []}')


def test_incorpora_filtra_deduplica_y_agrupa(almacen: Almacen) -> None:
    brutos = [
        bruto(1, "Droner over Københavns Lufthavn: lufthavnen lukket", 10),
        # Réplica: el mismo titular en otro medio.
        bruto(2, "Droner over Københavns Lufthavn: lufthavnen lukket - TV2", 9),
        bruto(3, "Politiet: droner ved Københavns Lufthavn i nat, flyvninger aflyst", 8),
        # Ocio: fuera.
        bruto(4, "Stort droneshow i Aarhus", 7),
        # La misma URL otra vez.
        bruto(1, "Droner over Københavns Lufthavn: lufthavnen lukket", 10),
    ]
    recuentos = gdelt.incorporar(almacen, brutos)
    assert (recuentos.recibidos, recuentos.ya_vistos, recuentos.descartados) == (5, 1, 1)
    assert (recuentos.replicas, recuentos.nuevos, recuentos.candidatos_nuevos) == (1, 2, 1)
    articulos = almacen.articulos()
    assert [a["replicas"] for a in articulos] == [1, 0]
    assert articulos[0]["url"] == "https://medio1.dk/nyhed/1"
    assert (articulos[0]["idioma"], articulos[0]["pais"], articulos[0]["lugares"]) == (
        "da",
        "DK",
        ["EKCH"],
    )
    (candidato,) = almacen.candidatos()
    assert candidato["lugar"] == "EKCH"
    assert len(candidato["articulos"]) == 2
    assert {a["candidato"] for a in articulos} == {candidato["id"]}


def test_el_candidato_crece_entre_ejecuciones(almacen: Almacen) -> None:
    gdelt.incorporar(almacen, [bruto(1, "Droner over Københavns Lufthavn: lufthavnen lukket", 10)])
    gdelt.incorporar(almacen, [bruto(3, "Politiet: nye droner ved Københavns Lufthavn i nat", 2)])
    (candidato,) = almacen.candidatos()
    assert len(candidato["articulos"]) == 2


def test_ejecucion_avanza_el_cursor_con_una_hora_de_solape(almacen: Almacen) -> None:
    api = ApiFalsa([bruto(1, "Droner over Københavns Lufthavn: lufthavnen lukket", 3)])
    gdelt.ejecutar(almacen, descargador(api), AHORA)
    assert almacen.cursor("gdelt") == {
        "hasta": "2025-09-23T12:00:00Z",
        "inicio": "2025-09-22T12:00:00Z",
    }
    api.pedidas.clear()
    gdelt.ejecutar(almacen, descargador(api), AHORA + timedelta(hours=1))
    assert {p["startdatetime"][0] for p in api.pedidas} == {"20250923110000"}


def test_si_la_api_no_responde_el_cursor_no_avanza(almacen: Almacen) -> None:
    api = ApiFalsa([])
    gdelt.ejecutar(almacen, descargador(api), AHORA)
    api.fallar = True
    assert gdelt.ejecutar(almacen, descargador(api), AHORA + timedelta(hours=5)).recibidos == 0
    cursor = almacen.cursor("gdelt")
    assert cursor is not None
    assert cursor["hasta"] == "2025-09-23T12:00:00Z"
    # Más de un día sin respuesta: la ejecución queda en rojo.
    with pytest.raises(gdelt.GdeltNoDisponible):
        gdelt.ejecutar(almacen, descargador(api), AHORA + timedelta(days=2))
