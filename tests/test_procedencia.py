"""Origen y método de cada valor exportado, valores sin respaldo y nivel de detalle."""

from typing import Any

import pytest

from almacen.base import Almacen
from esquema import Documento, Esquema, validador
from exportacion import procedencia as origenes
from exportacion import semanal
from tests import ejemplos
from tests.ejemplos import AHORA, VOCABULARIO_MODELOS
from tests.test_exportacion_semanal import completo_con_fuentes, lineas, poblado, por_nombre


def fuente(id_: str, fiabilidad: str = "C", **resto: Any) -> Documento:
    return {**ejemplos.fuente(id_, fiabilidad), "campos_respaldados": [], **resto}


@pytest.mark.parametrize(
    ("datos", "origen"),
    [
        (fuente("gdelt-1"), "prensa"),
        (fuente("gdelt-1-declaracion-2", "B", es_autoridad=True), "oficial_citado"),
        (fuente("mod_russia-7", "D", interna_fuera_de_ucrania=True), "parte"),
        (fuente("kpszsu-9", "B", enlace="https://t.me/kpszsu/9"), "oficial"),
        (fuente("politi_kobenhavn-1", "A", es_autoridad=True), "oficial"),
        (fuente("anonimo", "E"), "prensa"),
    ],
)
def test_el_origen_sale_de_la_fuente(datos: Documento, origen: str) -> None:
    assert origenes.origen_de_fuente(datos) == origen


def test_con_varias_fuentes_manda_la_de_mayor_rango() -> None:
    assert origenes.mejor(["prensa", "parte", "oficial_citado"]) == "oficial_citado"
    assert origenes.mejor(["prensa", "oficial", "medido"]) == "medido"
    assert origenes.mejor([]) is None


def exportar(documento: Documento) -> Documento:
    almacen = Almacen.abrir()
    almacen.guardar_incidente(documento, AHORA, VOCABULARIO_MODELOS)
    return origenes.exportar_incidente(documento, origenes.Fichas.de(almacen))


def test_ningun_valor_exportado_carece_de_origen() -> None:
    ficheros = por_nombre(semanal.generar(poblado()))
    for incidente in lineas(ficheros["incidentes.jsonl"]):
        rutas = set(origenes.valores(incidente))
        assert rutas and rutas <= set(incidente["procedencia"]), incidente["id"]
        assert all(p["origen"] and p["metodo"] for p in incidente["procedencia"].values())
    for ataque in lineas(ficheros["ucrania_ataques.jsonl"]):
        rutas = set(origenes.valores(ataque, origenes.META_ATAQUE))
        assert {r.split(".")[0] for r in rutas} <= set(ataque["procedencia"])
    for region in lineas(ficheros["ucrania_regiones.jsonl"]):
        assert region["procedencia"]["origen"] in origenes.RANGO
    for afirmacion in lineas(ficheros["afirmaciones.jsonl"]):
        assert afirmacion["origen"] in origenes.RANGO and afirmacion["metodo"], afirmacion


def test_un_valor_sin_fuente_no_se_exporta() -> None:
    documento = ejemplos.incidente_completo()  # sus fuentes no respaldan drones.luces
    with pytest.raises(origenes.SinOrigen, match=r"drones\.luces"):
        exportar(documento)


def test_la_nota_oficial_manda_sobre_la_noticia_y_dice_su_metodo() -> None:
    exportado = exportar(completo_con_fuentes())
    numero = exportado["procedencia"]["drones.numero"]
    # F1 y F3 (noticias) lo dicen por el extractor; F2 (nota oficial) y F4 (parte) lo
    # respaldan: manda la nota oficial.
    assert (numero["origen"], numero["metodo"]) == ("oficial", "parser")
    assert set(numero["fuentes"]) == {"F1", "F2", "F3", "F4"}
    estado = exportado["procedencia"]["estado"]
    assert (estado["origen"], estado["metodo"], estado["fuentes"]) == ("oficial", "regla", ["F2"])
    duracion = exportado["procedencia"]["tiempo.duracion_min"]
    assert duracion["metodo"] == "regla"


def de_prensa() -> Documento:
    documento = ejemplos.incidente_minimo()
    documento["fuentes"] = [fuente("gdelt-1")]
    documento["estado"]["historial"][0]["fuente_id"] = "gdelt-1"
    return documento


def con_afirmacion(campo: str, valor: Any, confianza: float) -> Documento:
    documento = de_prensa()
    documento["drones"] = {"numero": valor}
    documento["afirmaciones"] = [
        {"campo": campo, "valor": valor, "fuente_id": "gdelt-1", "confianza_extraccion": confianza}
    ]
    return documento


def test_lo_que_el_extractor_dio_con_confianza_baja_no_se_exporta_como_valor() -> None:
    exportado = exportar(con_afirmacion("drones", {"min": 2, "max": 9}, 0.3))
    assert "drones" not in exportado  # sin relleno: ni el valor ni un objeto vacío
    marca = exportado["procedencia"]["drones.numero"]
    assert marca["sin_respaldo"] == {"confianza": 0.3, "motivo": "confianza_baja"}
    assert (marca["origen"], marca["metodo"]) == ("prensa", "extractor")
    assert validador(Esquema.INCIDENTE).is_valid(exportado)


def test_con_confianza_suficiente_se_exporta_con_su_confianza() -> None:
    exportado = exportar(con_afirmacion("drones", {"min": 2, "max": 9}, 0.8))
    assert exportado["drones"]["numero"] == {"min": 2, "max": 9}
    assert exportado["procedencia"]["drones.numero"]["confianza"] == 0.8


def test_desconocido_se_conserva_y_se_marca() -> None:
    documento = de_prensa()
    documento["drones"] = {"numero": "desconocido"}
    exportado = exportar(documento)
    assert exportado["drones"]["numero"] == "desconocido"
    marca = exportado["procedencia"]["drones.numero"]
    assert marca["desconocido"] is True and marca["fuentes"] == []


def test_la_afirmacion_sin_respaldo_no_lleva_su_valor() -> None:
    almacen = Almacen.abrir()
    almacen.guardar_incidente(con_afirmacion("drones", {"min": 2, "max": 9}, 0.3), AHORA,
                              VOCABULARIO_MODELOS)  # fmt: skip
    [afirmacion] = [
        a
        for a in lineas(por_nombre(semanal.generar(almacen))["afirmaciones.jsonl"])
        if a["metodo"] == "extractor"
    ]
    assert afirmacion["valor"] == "sin_respaldo"
    assert afirmacion["sin_respaldo"] == {"confianza": 0.3, "motivo": "confianza_baja"}


def confirmado(origen_fuente: Documento, precision: str = "minuto", radio: float = 3) -> Documento:
    documento = de_prensa()
    documento["fuentes"].append(origen_fuente)
    documento["tiempo"] = {"inicio": ejemplos.instante("2025-11-04T18:00Z", precision)}
    documento["lugar"]["radio_km"] = radio
    documento["estado"]["historial"].append(
        {"estado": "confirmado", "fecha": ejemplos.instante("2025-11-04T20:00Z"),
         "fuente_id": origen_fuente["id"]}
    )  # fmt: skip
    documento["estado"]["actual"] = "confirmado"
    return documento


NOTA_OFICIAL = fuente("politi-1", "A", es_autoridad=True)
DECLARACION = fuente("gdelt-1-declaracion-1", "B", es_autoridad=True)


def test_nivel_de_detalle() -> None:
    # A: altura del dron respaldada por una autoridad.
    con_altura = confirmado({**NOTA_OFICIAL, "campos_respaldados": ["drones.altura_m"]})
    con_altura["drones"] = {"altura_m": {"min": 100, "max": 150}}
    assert exportar(con_altura)["nivel_detalle"] == "A"
    # B: hora precisa, radio de 5 km o menos y confirmación oficial.
    assert exportar(confirmado(NOTA_OFICIAL))["nivel_detalle"] == "B"
    # C: confirmado por una autoridad, sin la precisión de B.
    assert exportar(confirmado(NOTA_OFICIAL, radio=10))["nivel_detalle"] == "C"
    assert exportar(confirmado(NOTA_OFICIAL, precision="dia"))["nivel_detalle"] == "C"
    assert exportar(confirmado(DECLARACION))["nivel_detalle"] == "C"
    # D: solo prensa.
    assert exportar(de_prensa())["nivel_detalle"] == "D"


def test_la_altura_que_solo_da_la_prensa_no_es_nivel_a() -> None:
    documento = confirmado(DECLARACION)
    documento["drones"] = {"altura_m": {"min": 100, "max": 150}}
    documento["afirmaciones"] = [
        {"campo": "drones.altura_m", "valor": {"min": 100, "max": 150}, "fuente_id": "gdelt-1",
         "confianza_extraccion": 0.9},
    ]  # fmt: skip
    exportado = exportar(documento)
    assert exportado["procedencia"]["drones.altura_m"]["origen"] == "prensa"
    assert exportado["nivel_detalle"] == "C"


def test_el_vocabulario_dice_los_mismos_origenes_metodos_y_niveles() -> None:
    vocabulario = semanal.vocabulario()
    por_rango = sorted(vocabulario["origenes"], key=lambda o: vocabulario["origenes"][o]["rango"])
    assert tuple(por_rango) == origenes.RANGO
    assert set(vocabulario["metodos"]) == {origenes.PARSER, origenes.EXTRACTOR, origenes.REGLA}
    assert tuple(vocabulario["niveles_detalle"]) == origenes.NIVELES


def test_el_foco_termico_de_una_region_es_medido() -> None:
    ataque = ejemplos.ataque_completo()
    ataque["regiones"][0]["foco_termico"] = {"resultado": "no_detectado", "motivo": "sin_focos"}
    procedencia = origenes.procedencia_ataque(ataque)
    assert procedencia["regiones.foco_termico"]["origen"] == "medido"
    region = origenes.procedencia_region(ataque["regiones"][0], procedencia)
    assert region["foco_termico"] == {"origen": "medido", "metodo": "parser", "fuentes": []}
    assert region["origen"] == "oficial"
