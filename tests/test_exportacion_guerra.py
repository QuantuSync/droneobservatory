"""Exportación de la capa de guerra con lugar: lista cerrada de campos públicos en
ucrania.json y ficheros de la exportación semanal para AEGIS con origen y método."""

import copy
import json
from typing import Any

from almacen.base import Almacen
from esquema import Esquema, Visibilidad, rutas_por_visibilidad
from exportacion import semanal
from exportacion.campos import CAMPOS_PUBLICOS_IMPACTO
from exportacion.procedencia import procedencia_impacto
from exportacion.proyeccion import rutas
from exportacion.ucrania import campos_fuera_de_lista, exportar_ucrania
from tests import ejemplos
from tests.ejemplos import AHORA


def _publicos(impactos: list[dict[str, Any]]) -> list[dict[str, Any]]:
    resultado: list[dict[str, Any]] = exportar_ucrania([], AHORA, impactos).get("impactos", [])
    return resultado


def test_la_lista_publica_no_tiene_ningun_campo_interno() -> None:
    internos = rutas_por_visibilidad(Esquema.IMPACTO_GUERRA)[Visibilidad.INTERNO]
    # Las rutas del esquema de la fuente cuelgan de «fuentes[]».
    assert not CAMPOS_PUBLICOS_IMPACTO & internos


def test_el_impacto_publico_sin_lo_interno() -> None:
    impacto = ejemplos.impacto_guerra()
    impacto["foco_termico"] = ejemplos.foco_termico()
    (publico,) = _publicos([impacto])
    assert set(rutas(publico)) <= CAMPOS_PUBLICOS_IMPACTO
    for interno in ("lecturas", "enlace_ataque", "procedencia"):
        assert interno not in publico
    assert "frp_max_mw" not in publico["foco_termico"]
    assert "campos_respaldados" not in publico["fuentes"][0]
    assert publico["lugar"]["punto"] == {"lat": 49.99, "lon": 36.23}


def test_solo_sale_el_foco_detectado_y_no_salen_unidos_ni_retirados() -> None:
    con_foco = ejemplos.impacto_guerra()
    con_foco["foco_termico"] = {**ejemplos.foco_termico(), "resultado": "no_detectado",
                                "motivo": "sin_focos"}  # fmt: skip
    unido = {**ejemplos.impacto_guerra(), "id": "EODI-IG-2025-00002",
             "fusionado_en": "EODI-IG-2025-00001"}  # fmt: skip
    baja = {"fecha": ejemplos.instante("2025-06-02T10:00Z"), "motivo": "x"}
    retirado = {**ejemplos.impacto_guerra(), "id": "EODI-IG-2025-00003", "retirado": baja}
    publicos = _publicos([con_foco, unido, retirado])
    assert [p["id"] for p in publicos] == ["EODI-IG-2025-00001"]
    assert "foco_termico" not in publicos[0]


def test_la_comprobacion_detecta_un_campo_colado() -> None:
    publicacion = exportar_ucrania([], AHORA, [ejemplos.impacto_guerra()])
    publicacion["impactos"][0]["lecturas"] = []
    assert campos_fuera_de_lista(publicacion) == ["lecturas"]


def test_procedencia_del_impacto() -> None:
    impacto = ejemplos.impacto_guerra()
    impacto["foco_termico"] = ejemplos.foco_termico()
    procedencia = procedencia_impacto(impacto)
    # La administración militar regional es fuente oficial; el lugar lo lee el código.
    assert procedencia["lugar"] == {"origen": "oficial", "metodo": "parser",
                                    "fuentes": ["kharkivoda-31198"]}  # fmt: skip
    assert procedencia["foco_termico"]["origen"] == "medido"
    assert procedencia["credibilidad"]["origen"] == "medido"
    assert procedencia["ataque"]["metodo"] == "regla"


def test_la_reivindicacion_del_estado_mayor_es_de_parte_y_del_extractor() -> None:
    impacto = copy.deepcopy(ejemplos.impacto_guerra())
    fuente = impacto["fuentes"][0]
    fuente.update(id="GeneralStaffZSU-42000", enlace="https://t.me/GeneralStaffZSU/42000",
                  fiabilidad="C")  # fmt: skip
    impacto["lecturas"] = [{"fuente_id": "GeneralStaffZSU-42000", "metodo": "extractor",
                            "version": "guerra/1", "confianza": 0.92}]  # fmt: skip
    procedencia = procedencia_impacto(impacto)
    assert procedencia["lugar"]["origen"] == "parte"
    assert procedencia["lugar"]["metodo"] == "extractor"
    assert procedencia["lugar"]["confianza"] == 0.92


def test_la_exportacion_semanal_lleva_impactos_mensajes_y_restricciones() -> None:
    almacen = Almacen.abrir()
    almacen.guardar_impacto_guerra(ejemplos.impacto_guerra())
    almacen.guardar_restriccion(ejemplos.restriccion())
    almacen.guardar_mensaje_guerra(
        "https://t.me/kharkivoda/31198", "ova_kharkiv", "2025-06-01T06:45:00Z", "h", "impactos",
        {"id": 31198, "canal_id": "ova_kharkiv", "impactos": ["EODI-IG-2025-00001"],
         "prioridad": 1, "metodo": "parser", "region": "UA-63"},
    )  # fmt: skip
    ficheros = {f.nombre: f for f in semanal.generar(almacen)}
    impactos = [json.loads(x) for x in ficheros["guerra_impactos.jsonl"].contenido.splitlines()]
    assert impactos[0]["lecturas"][0]["metodo"] == "parser"
    assert impactos[0]["procedencia"]["impacto"]["origen"] == "oficial"
    (restriccion,) = [
        json.loads(x) for x in ficheros["restricciones_aeropuertos.jsonl"].contenido.splitlines()
    ]
    assert restriccion["procedencia"]["inicio"] == {
        "origen": "oficial", "metodo": "parser",
        "fuentes": ["https://t.me/favt_info/8287", "https://t.me/favt_info/8289"],
    }  # fmt: skip
    (mensaje,) = [json.loads(x) for x in ficheros["guerra_mensajes.jsonl"].contenido.splitlines()]
    assert "huella" not in mensaje and "texto" not in mensaje
    afirmaciones = [json.loads(x) for x in ficheros["afirmaciones.jsonl"].contenido.splitlines()]
    del_impacto = [a for a in afirmaciones if a["entidad_id"] == "EODI-IG-2025-00001"]
    assert {a["campo"] for a in del_impacto} == {"lugar", "impacto", "categorias_objetivo"}
    assert {a["capa"] for a in del_impacto} == {"ucrania"}
    for nombre in ("guerra_impactos.jsonl", "guerra_mensajes.jsonl",
                   "restricciones_aeropuertos.jsonl"):  # fmt: skip
        assert ficheros[ficheros[nombre].esquema].registros == 1, nombre
