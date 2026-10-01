import json
from pathlib import Path

import pytest

from esquema import Documento, Esquema, Visibilidad, rutas_por_visibilidad
from exportacion.campos import CAMPOS_PUBLICOS_ATAQUE
from exportacion.proyeccion import ExportacionInvalida, escribir, rutas
from exportacion.ucrania import campos_fuera_de_lista, exportar_ucrania
from tests import ejemplos
from tests.ejemplos import AHORA, instante

VISIBILIDAD = rutas_por_visibilidad(Esquema.ATAQUE_UCRANIA)


def ataque_con_fuente_interna() -> Documento:
    ataque = ejemplos.ataque_completo()
    ataque["fuentes"].append(ejemplos.fuente("P3", "E", publica=False))
    ataque["regiones"].insert(0, {**ejemplos.region(), "region": "UA-71"})
    ataque["regiones"].append({**ejemplos.region(), "region": "UA-18"})
    return ataque


def exportar_ejemplo() -> Documento:
    return exportar_ucrania([ataque_con_fuente_interna()], AHORA)


def rutas_publicadas(publicacion: Documento) -> set[str]:
    return {r for a in publicacion["ataques"] for r in rutas(a)}


def test_ningun_campo_fuera_de_la_lista_cerrada() -> None:
    assert rutas_publicadas(exportar_ejemplo()) - CAMPOS_PUBLICOS_ATAQUE == set()


def test_ningun_campo_interno_del_esquema_llega_a_ucrania_json() -> None:
    assert rutas_publicadas(exportar_ejemplo()) & VISIBILIDAD[Visibilidad.INTERNO] == set()


def test_la_lista_cerrada_solo_contiene_campos_publicos_del_esquema() -> None:
    assert CAMPOS_PUBLICOS_ATAQUE - VISIBILIDAD[Visibilidad.PUBLICO] == set()
    assert CAMPOS_PUBLICOS_ATAQUE.isdisjoint(VISIBILIDAD[Visibilidad.INTERNO])


def test_el_ejemplo_rellena_todos_los_campos_internos() -> None:
    presentes = set(rutas(ataque_con_fuente_interna()))
    # El motivo solo lo lleva un foco no detectado, que nunca sale: tiene su propio test. El
    # método y el documento de la fuente solo los llevan las fuentes oficiales de detalle,
    # que no llegan a la capa de Ucrania.
    internos = VISIBILIDAD[Visibilidad.INTERNO] - {
        "regiones[].foco_termico.motivo",
        "fuentes[].metodo",
        "fuentes[].documento_oficial",
    }
    assert internos - presentes == set()


def test_la_comprobacion_detecta_un_campo_colado() -> None:
    publicacion = exportar_ejemplo()
    publicacion["ataques"][0]["proporcion_senuelos"] = 0.2
    publicacion["ataques"][0]["extra"] = 1
    assert campos_fuera_de_lista(publicacion) == ["extra", "proporcion_senuelos"]


def test_regiones_por_codigo_iso_ordenadas() -> None:
    (ataque,) = exportar_ejemplo()["ataques"]
    assert [r["region"] for r in ataque["regiones"]] == ["UA-18", "UA-63", "UA-71"]
    assert {k: v for k, v in ataque["regiones"][1].items() if k != "foco_termico"} == (
        ejemplos.region()
    )


def test_fuentes_en_la_capa_de_ucrania() -> None:
    (ataque,) = exportar_ejemplo()["ataques"]
    # P2 es interna fuera de la capa de Ucrania: aquí sí se publica. P3 es E: nunca.
    assert [f["id"] for f in ataque["fuentes"]] == ["P1", "P2"]
    assert "nota/P3" not in json.dumps(ataque)


def test_historial_no_cita_fuentes_internas() -> None:
    ataque = ataque_con_fuente_interna()
    ataque["estado"]["historial"].append(
        {"estado": "desmentido", "fecha": instante("2025-10-07T10:00Z"), "fuente_id": "P3"}
    )
    ataque["estado"]["actual"] = "desmentido"
    ataque["control"]["motivo_desmentido"] = "El parte se corrige"
    (publicado,) = exportar_ucrania([ataque], AHORA)["ataques"]
    assert [p.get("fuente_id") for p in publicado["estado"]["historial"]] == ["P1", "P1", None]
    assert publicado["control"]["motivo_desmentido"] == "El parte se corrige"


def test_ataque_sin_fuentes_publicas_no_se_publica() -> None:
    ataque = ejemplos.ataque_completo()
    for fuente in ataque["fuentes"]:
        fuente["publica"] = False
    assert exportar_ucrania([ataque], AHORA) == {"ataques": []}


def test_ataque_invalido_detiene_la_exportacion() -> None:
    ataque = ejemplos.ataque_completo()
    ataque["derribados"] = {"min": 90, "max": 10}
    with pytest.raises(ExportacionInvalida):
        exportar_ucrania([ataque], AHORA)


def test_escribe_un_fichero_determinista(tmp_path: Path) -> None:
    ruta = tmp_path / "ucrania.json"
    escribir(exportar_ejemplo(), ruta)
    primero = ruta.read_bytes()
    escribir(exportar_ejemplo(), ruta)
    assert ruta.read_bytes() == primero
    assert list(json.loads(primero)) == ["ataques"]


def test_la_web_recibe_que_cuenta_la_cifra_de_derribados() -> None:
    (ataque,) = exportar_ejemplo()["ataques"]
    assert ataque["derribados_categoria"] == "derribados_o_neutralizados"
