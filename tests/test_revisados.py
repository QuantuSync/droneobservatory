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


def test_el_que_queda_toma_el_cierre_y_con_el_el_tipo(monkeypatch: pytest.MonkeyPatch) -> None:
    """EODI-2026-00183 (Gran Canaria, sobrevuelo) y EODI-2026-00398 (el mismo suceso, con el
    cierre del aeropuerto): la unión no se guardaba («hay interrupción de aeropuerto»)."""
    almacen = Almacen.abrir()
    objetivo = {"categoria": "aeropuerto", "nombre": "Flughafen Leipzig/Halle", "oaci": "EDDP"}
    queda = _registro("EODI-2026-00183", "2026-08-03T22:00Z", "explicita",
                      [("a1", "2026-08-04T09:30Z")])  # fmt: skip
    otro = _registro("EODI-2026-00398", "2026-08-05T10:00Z", "publicacion",
                     [("b1", "2026-08-05T10:30Z")], cierre=True)  # fmt: skip
    for documento, tipo in ((queda, "sobrevuelo"), (otro, "interrupcion_aeroportuaria")):
        documento.update(objetivo=objetivo, tipo=tipo)
        almacen.guardar_incidente(documento, AHORA, MODELOS)
    monkeypatch.setattr(revisados, "cargar", lambda: {
        "unir": [{"registros": ["EODI-2026-00183", "EODI-2026-00398"],
                  "conserva": "EODI-2026-00183", "motivo": "el mismo suceso"}],
        "reextraer": [],
    })  # fmt: skip
    assert revisados.unir(almacen, AHORA, MODELOS) == 1
    unido = almacen.incidente("EODI-2026-00183")
    assert unido is not None and unido["consecuencias"]["cierre"]["valor"] == "si"
    assert unido["tipo"] == "interrupcion_aeroportuaria"


def test_lo_que_una_revision_separo_como_distinto_no_lo_vuelve_a_juntar_la_regla(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """EODI-2025-00397 y EODI-2025-00468 (Fuerteventura, 18 y 19 de octubre de 2025): separados
    por la revisión, la regla de fusión los volvió a juntar porque el del 19 solo tenía la fecha
    de publicación. Solo la marca «distintos» lo impide: sin ella, un enlace de `relacionados`
    (una parte que coincide con otra ficha) no cambia nada."""
    almacen = Almacen.abrir()
    vispera = _registro("EODI-2025-00397", "2026-08-04T06:40Z", "explicita",
                        [("a1", "2026-08-04T07:37Z")])  # fmt: skip
    otro = _registro("EODI-2025-00468", "2026-08-05T17:15Z", "publicacion",
                     [("b1", "2026-08-05T17:15Z")])  # fmt: skip
    otro["tiempo"]["inicio"] = ejemplos.instante("2026-08-05T17:15Z", "aproximada")
    otro["control"]["alta"] = ejemplos.instante("2026-08-05T17:15Z")
    for documento, pareja in ((vispera, otro), (otro, vispera)):
        documento["relacionados"] = [{"id": pareja["id"], "separado_de": "EODI-2025-00397",
                                      "nota": {"es": "separados", "en": "separated"}}]  # fmt: skip
    monkeypatch.setattr(incidentes, "separaciones_distintas", lambda: frozenset())
    assert incidentes.encajan(vispera, otro)
    monkeypatch.setattr(incidentes, "separaciones_distintas",
                        lambda: frozenset({"EODI-2025-00397"}))  # fmt: skip
    assert not incidentes.encajan(vispera, otro)
    for documento in (vispera, otro):
        almacen.guardar_incidente(documento, AHORA, MODELOS)
    assert incidentes.fusionar(almacen, AHORA, MODELOS) == 0
    # La fusión que ya se hizo se deshace.
    monkeypatch.setattr(incidentes, "separaciones_distintas", lambda: frozenset())
    assert incidentes.fusionar(almacen, AHORA, MODELOS) == 1
    monkeypatch.setattr(incidentes, "separaciones_distintas",
                        lambda: frozenset({"EODI-2025-00397"}))  # fmt: skip
    assert incidentes.revisar_fusiones(almacen, AHORA, MODELOS) == ["EODI-2025-00468"]


def test_la_marca_distintos_solo_esta_en_las_separaciones_revisadas() -> None:
    # Fuerteventura y, desde el 19 de octubre de 2026, las ocho que la regla de fusión había vuelto
    # a juntar (Kleine-Brogel, Volkel, Moldavia, Rumanía, Aalborg, Palanca y Hîrbovăț).
    assert incidentes.separaciones_distintas() == frozenset(
        {
            "EODI-2025-00397",
            "EODI-2025-00131",
            "EODI-2025-00080",
            "EODI-2025-00066",
            "EODI-2025-00261",
            "EODI-2025-00268",
            "EODI-2025-00349",
            "EODI-2026-00203",
            "EODI-2026-00281",
        }
    )
    # Dos registros de una misma parte se unen a mano: la marca no los deja juntarse solos.
    unir = {frozenset(u["registros"]) for u in revisados.cargar()["unir"]}
    assert frozenset({"EODI-2025-00344", "EODI-2025-00447"}) in unir
    assert frozenset({"EODI-2026-00141", "EODI-2026-00531"}) in unir
    assert frozenset({"EODI-2026-00527", "EODI-2026-00159"}) in unir


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
    leipzig, wunstorf = datos["unir"][:2]
    # 00346 se une en la revisión del contenido: era Leipzig con el lugar de Rzeszów.
    assert "EODI-2026-00391" in leipzig["registros"] and len(leipzig["registros"]) == 17
    assert "EODI-2026-00346" in leipzig["registros"]
    # Otro suceso en el mismo aeropuerto: no se une.
    assert "EODI-2026-00058" not in leipzig["registros"]
    # Wunstorf, aparte de Leipzig.
    assert "EODI-2026-00309" in wunstorf["registros"] and len(wunstorf["registros"]) == 6
    assert not set(leipzig["registros"]) & set(wunstorf["registros"])
    (revision_,) = datos["reextraer"]
    assert revision_["incidente"] == "EODI-2026-00283"


def test_ninguna_presencia_revisada_contradice_una_rectificacion_oficial() -> None:
    # EODI-2025-00164 (Lakenheath) estaba revisada «no_confirmada» con la rectificación del UK
    # Airprox Board que la deja «descartada»: ahora dicen lo mismo, y el control lo comprueba.
    assert revisados.revisiones_contra_rectificaciones() == []
    lakenheath = next(t for t in revisados.cargar()["titulares"]
                      if t["incidente"] == "EODI-2025-00164" and "presencia" in t)  # fmt: skip
    assert lakenheath["presencia"]["valor"] == "descartada"


def test_una_presencia_revisada_contra_la_rectificacion_se_detecta_y_no_se_aplica() -> None:
    revision = {
        "incidente": "EODI-2025-09001",
        "presencia": {"valor": "no_confirmada", "cita": "x"},
    }
    oficiales = {"rectificaciones": [
        {"incidente": "EODI-2025-09001", "tipo": "parcial", "fecha_declaracion": "2025-07-01"},
        {"incidente": "EODI-2025-09001", "tipo": "descartada", "fecha_declaracion": "2025-06-26"},
    ]}  # fmt: skip
    assert revisados.revisiones_contra_rectificaciones({"titulares": [revision]}, oficiales) == [
        "EODI-2025-09001: revisada «no_confirmada», rectificada «descartada» el 2025-06-26"
    ]
    acorde = {**revision, "presencia": {"valor": "descartada", "cita": "x"}}
    assert revisados.revisiones_contra_rectificaciones({"titulares": [acorde]}, oficiales) == []
    # En la ficha: el último paso de su historial que no es parcial manda.
    ficha = {"presencia_historial": [{"valor": "no_confirmada"}, {"valor": "descartada"},
                                     {"valor": "descartada", "parcial": True}]}  # fmt: skip
    assert revisados.contradice_rectificacion(revision, ficha)
    assert not revisados.contradice_rectificacion(acorde, ficha)
    assert not revisados.contradice_rectificacion(revision, {"presencia_historial": [
        {"valor": "confirmada"}]})  # fmt: skip
