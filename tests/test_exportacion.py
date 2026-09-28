import json
from pathlib import Path

import pytest

from esquema import Documento, Esquema, Visibilidad, rutas_por_visibilidad
from exportacion.campos import CAMPOS_PUBLICOS_INCIDENTE
from exportacion.geojson import campos_fuera_de_lista, exportar
from exportacion.proyeccion import ExportacionInvalida, escribir, rutas
from tests import ejemplos
from tests.ejemplos import AHORA, VOCABULARIO_MODELOS, instante

VISIBILIDAD = rutas_por_visibilidad(Esquema.INCIDENTE)


def exportar_ejemplos() -> Documento:
    return exportar(
        [ejemplos.incidente_completo(), ejemplos.incidente_minimo()], AHORA, VOCABULARIO_MODELOS
    )


def rutas_publicadas(coleccion: Documento) -> set[str]:
    return {r for f in coleccion["features"] for r in rutas(f["properties"])}


def test_ningun_campo_fuera_de_la_lista_cerrada() -> None:
    publicadas = rutas_publicadas(exportar_ejemplos())
    assert publicadas - CAMPOS_PUBLICOS_INCIDENTE == set()


def test_ningun_campo_interno_del_esquema_llega_al_geojson() -> None:
    publicadas = rutas_publicadas(exportar_ejemplos())
    assert publicadas & VISIBILIDAD[Visibilidad.INTERNO] == set()


def test_la_lista_cerrada_solo_contiene_campos_publicos_del_esquema() -> None:
    assert CAMPOS_PUBLICOS_INCIDENTE - VISIBILIDAD[Visibilidad.PUBLICO] == set()
    assert CAMPOS_PUBLICOS_INCIDENTE.isdisjoint(VISIBILIDAD[Visibilidad.INTERNO])


def test_el_ejemplo_completo_rellena_todos_los_campos_internos() -> None:
    # Garantiza que los tests anteriores ejercitan de verdad cada campo interno.
    presentes = set(rutas(ejemplos.incidente_completo()))
    # fusionado_en saca al incidente de la publicación: tiene su propio test.
    internos_hoja = {
        r
        for r in VISIBILIDAD[Visibilidad.INTERNO]
        if not r.startswith("drones.velocidad_ms.") and r != "fusionado_en"
    }
    assert internos_hoja - presentes == set()


def test_un_incidente_fundido_en_otro_no_se_publica() -> None:
    fundido = ejemplos.incidente_minimo()
    fundido["fusionado_en"] = ejemplos.incidente_completo()["id"]
    coleccion = exportar([ejemplos.incidente_completo(), fundido], AHORA, VOCABULARIO_MODELOS)
    assert [f["id"] for f in coleccion["features"]] == [ejemplos.incidente_completo()["id"]]


def test_presencia_dron_se_publica() -> None:
    (feature, _) = exportar_ejemplos()["features"]
    assert feature["properties"]["presencia_dron"] == "no_confirmada"


def test_la_comprobacion_detecta_un_campo_colado() -> None:
    coleccion = exportar_ejemplos()
    coleccion["features"][0]["properties"]["lugar"]["nuts2"] = "DK01"
    coleccion["features"][0]["properties"]["extra"] = 1
    assert campos_fuera_de_lista(coleccion) == ["extra", "lugar.nuts2"]


def test_geometria_y_estructura_geojson() -> None:
    coleccion = exportar_ejemplos()
    assert coleccion["type"] == "FeatureCollection"
    primera = coleccion["features"][0]
    assert set(primera) == {"type", "id", "geometry", "properties"}
    assert primera["geometry"] == {"type": "Point", "coordinates": [12.65611, 55.61806]}
    assert "punto" not in primera["properties"]["lugar"]
    assert primera["properties"]["lugar"]["radio_km"] == 5


def test_fuentes_internas_no_se_publican() -> None:
    texto = json.dumps(exportar_ejemplos(), ensure_ascii=False)
    # F3 es de fiabilidad E y F4 es interna fuera de la capa de Ucrania.
    for interna in ("nota/F3", "nota/F4", "Medio F3", "Medio F4"):
        assert interna not in texto
    fuentes = exportar_ejemplos()["features"][0]["properties"]["fuentes"]
    assert [f["id"] for f in fuentes] == ["F1", "F2"]


def test_historial_no_cita_fuentes_internas() -> None:
    documento = ejemplos.incidente_minimo()
    documento["fuentes"].append(ejemplos.fuente("F3", "E", publica=False))
    documento["estado"]["historial"].append(
        {"estado": "desmentido", "fecha": instante("2025-11-05T10:00Z"), "fuente_id": "F3"}
    )
    documento["estado"]["actual"] = "desmentido"
    documento["control"]["motivo_desmentido"] = "Eran aves"
    (publicado,) = exportar([documento], AHORA, VOCABULARIO_MODELOS)["features"]
    historial = publicado["properties"]["estado"]["historial"]
    assert [p.get("fuente_id") for p in historial] == ["F1", None]
    assert "F3" not in json.dumps(publicado)


def test_desmentido_sigue_visible_con_su_motivo() -> None:
    documento = ejemplos.incidente_minimo()
    documento["estado"]["historial"].append(
        {"estado": "desmentido", "fecha": instante("2025-11-05T10:00Z"), "fuente_id": "F1"}
    )
    documento["estado"]["actual"] = "desmentido"
    documento["control"]["motivo_desmentido"] = "Eran aves"
    (publicado,) = exportar([documento], AHORA, VOCABULARIO_MODELOS)["features"]
    assert publicado["properties"]["estado"]["actual"] == "desmentido"
    assert publicado["properties"]["control"]["motivo_desmentido"] == "Eran aves"


def test_incidente_sin_fuentes_publicas_no_se_publica() -> None:
    documento = ejemplos.incidente_minimo()
    documento["fuentes"] = [ejemplos.fuente("F1", "E", publica=False)]
    assert exportar([documento], AHORA, VOCABULARIO_MODELOS)["features"] == []


def test_incidente_invalido_detiene_la_exportacion() -> None:
    documento = ejemplos.incidente_minimo()
    documento["fuentes"][0]["fiabilidad"] = "F"  # marcada pública con fiabilidad F
    with pytest.raises(ExportacionInvalida):
        exportar([documento], AHORA, VOCABULARIO_MODELOS)


def test_escribe_un_fichero_determinista(tmp_path: Path) -> None:
    ruta = tmp_path / "incidentes.geojson"
    escribir(exportar_ejemplos(), ruta)
    primero = ruta.read_bytes()
    escribir(exportar_ejemplos(), ruta)
    assert ruta.read_bytes() == primero
    assert json.loads(primero)["type"] == "FeatureCollection"
