"""Correcciones revisadas a mano: registros del mismo suceso que se unen y una ficha que mezcló
dos sucesos (configuracion/incidentes_revisados.json)."""

import copy
from datetime import UTC, datetime
from typing import Any

import pytest

from almacen.base import Almacen
from proceso import incidentes
from recogida import revisados
from tests import ejemplos

AHORA = datetime(2026, 10, 4, 16, 17, tzinfo=UTC)
MODELOS: frozenset[str] = frozenset()


def _registro(id_: str, inicio: str, origen: str, fuentes: list[tuple[str, str]],
              cierre: bool = False) -> dict[str, Any]:  # fmt: skip
    documento = ejemplos.incidente_minimo()
    documento.update(
        id=id_, titulo={"es": "Dron con explosivos en el aeropuerto de Leipzig",
                        "en": "Drone with explosives at Leipzig airport"},
        lugar={"punto": {"lat": 51.42, "lon": 12.24}, "radio_km": 5, "pais": "DE",
               "nivel": "instalacion", "suceso": "Flughafen Leipzig/Halle"},
    )  # fmt: skip
    documento["tiempo"] = {
        "inicio": ejemplos.instante(inicio, "hora"),
        "origen_inicio": {"tipo": origen, "fuente_id": fuentes[0][0], "motivo": "prueba"},
    }
    documento["fuentes"] = []
    for fuente_id, fecha in fuentes:
        fuente = ejemplos.fuente(fuente_id, "B")
        fuente["fecha"] = ejemplos.instante(fecha)
        fuente["enlace"] = f"https://ejemplo.de/{fuente_id}"
        documento["fuentes"].append(fuente)
    documento["estado"]["historial"][0]["fuente_id"] = fuentes[0][0]
    documento["estado"]["historial"][0]["fecha"] = ejemplos.instante(fuentes[0][1])
    documento["control"]["alta"] = ejemplos.instante(fuentes[0][1])
    if cierre:
        documento["consecuencias"] = {"cierre": {"valor": "si"}}
    return documento


@pytest.fixture
def leipzig(monkeypatch: pytest.MonkeyPatch) -> Almacen:
    almacen = Almacen.abrir()
    # Escrito por una fuente («dienstag»), pocas noticias.
    almacen.guardar_incidente(_registro(
        "EODI-2026-00391", "2026-08-03T22:00Z", "explicita",
        [("a1", "2026-08-05T09:30Z"), ("a2", "2026-08-05T09:45Z")]), AHORA, MODELOS)  # fmt: skip
    # Con el cierre y más noticias, pero con un inicio posterior a su primera noticia.
    almacen.guardar_incidente(_registro(
        "EODI-2026-00134", "2026-08-05T17:30Z", "explicita",
        [("b1", "2026-08-05T05:30Z"), ("b2", "2026-08-05T06:45Z"), ("b3", "2026-08-05T07:00Z")],
        cierre=True), AHORA, MODELOS)  # fmt: skip
    # Noticia de septiembre sobre la acusación, fechada por su publicación.
    almacen.guardar_incidente(_registro(
        "EODI-2026-00239", "2026-09-03T02:00Z", "publicacion",
        [("c1", "2026-09-03T02:15Z")]), AHORA, MODELOS)  # fmt: skip
    monkeypatch.setattr(revisados, "cargar", lambda: {
        "unir": [{"registros": ["EODI-2026-00391", "EODI-2026-00134", "EODI-2026-00239"],
                  "motivo": "el mismo suceso"}],
        "reextraer": [],
    })  # fmt: skip
    return almacen


def test_los_registros_del_mismo_suceso_quedan_en_uno(leipzig: Almacen) -> None:
    assert revisados.unir(leipzig, AHORA, MODELOS) == 2
    vivos = [i for i in leipzig.incidentes() if incidentes.activo(i)]
    assert [i["id"] for i in vivos] == ["EODI-2026-00134"]
    (unido,) = vivos
    assert {f["id"] for f in unido["fuentes"]} == {"a1", "a2", "b1", "b2", "b3", "c1"}
    # Su inicio era posterior a su primera noticia: toma el escrito del 4 de agosto.
    assert unido["tiempo"]["inicio"]["valor"] == "2026-08-03T22:00Z"
    assert unido["consecuencias"]["cierre"]["valor"] == "si"
    fusiones = leipzig.fusiones()
    assert {f["absorbido"] for f in fusiones} == {"EODI-2026-00391", "EODI-2026-00239"}
    assert all(f["motivo"] == "revisión: el mismo suceso" for f in fusiones)
    # Una regla no las deshace, y volver a pasar no cambia nada.
    assert incidentes.revisar_fusiones(leipzig, AHORA, MODELOS) == []
    assert revisados.unir(leipzig, AHORA, MODELOS) == 0


def test_la_ficha_que_mezcla_dos_sucesos_se_vuelve_a_extraer_una_vez(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    almacen = Almacen.abrir()
    mezclado = _registro("EODI-2026-00283", "2026-08-04T18:00Z", "explicita",
                         [("w1", "2026-09-18T10:15Z")])  # fmt: skip
    almacen.guardar_incidente(mezclado, AHORA, MODELOS)
    almacen.guardar_candidato({"id": "CAND-W", "articulos": ["https://ejemplo.de/w1"]})
    almacen.guardar_extraccion("CAND-W", "2026-09-18T11:00Z", "ficha/5", "h", True,
                               {"incidente": "EODI-2026-00283"})  # fmt: skip
    revision_ = {"incidente": "EODI-2026-00283", "candidato": "CAND-W", "motivo": "mezcla",
                 "no_lugar": "Leipzig", "no_antes_de": "2026-09-01"}  # fmt: skip
    monkeypatch.setattr(revisados, "cargar", lambda: {"unir": [], "reextraer": [revision_]})
    llamadas = []

    def falsa(almacen_: Almacen, cliente: Any, candidato: Any, ahora: datetime) -> int:
        # Con la hora de la ejecución, la misma con que se valida lo publicado.
        assert ahora == AHORA
        llamadas.append(candidato["id"])
        # La ficha nueva vuelve a dar Leipzig.
        almacen_.guardar_incidente(copy.deepcopy(mezclado), AHORA, MODELOS)
        return 1

    monkeypatch.setattr(revisados, "_extraer", falsa)
    assert revisados.reextraer(almacen, object(), AHORA, MODELOS) == ["EODI-2026-00283"]
    retirado = almacen.incidente("EODI-2026-00283")
    assert retirado is not None and "sigue mezclándolos" in retirado["retirado"]["motivo"]
    # Una sola vez.
    assert revisados.reextraer(almacen, object(), AHORA, MODELOS) == []
    assert llamadas == ["CAND-W"]


def test_la_configuracion_revisada() -> None:
    datos = revisados.cargar()
    leipzig, wunstorf = datos["unir"]
    assert "EODI-2026-00391" in leipzig["registros"] and len(leipzig["registros"]) == 16
    # Otro suceso en el mismo aeropuerto: no se une.
    assert "EODI-2026-00058" not in leipzig["registros"]
    # Wunstorf, aparte de Leipzig.
    assert "EODI-2026-00309" in wunstorf["registros"] and len(wunstorf["registros"]) == 6
    assert not set(leipzig["registros"]) & set(wunstorf["registros"])
    (revision_,) = datos["reextraer"]
    assert revision_["incidente"] == "EODI-2026-00283"
