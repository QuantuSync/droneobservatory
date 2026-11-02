"""EODI-2026-00728 (Viișoara, Moldavia, 31 de octubre de 2026): la unión conservó las dos autoridades,
la medida a las 24 horas dudó de una y quitó las dos, y el control bajó el estado a «notificado»
porque miraba solo la fuente del paso del historial."""

import copy
from typing import Any

from proceso import control_fichas as reglas
from proceso import declaraciones, incidentes
from recogida import entrada, revisados
from tests import ejemplos

CENTRO = "Centrul Operații Aeriene al Armatei Naționale"
MINISTERIO = "Ministerul Apărării"
INSTANTE = ejemplos.instante("2026-11-01T18:17Z")
TIMPUL = "https://timpul.md/articol/cea-de-a-doua-drona-care-a-survolat-r-moldova.html"
FRASE_MINISTERIO = (
    "Potrivit Ministerului Apărării, cea de-a doua dronă a pătruns în spațiul aerian național"
)


def _declaracion(id_: str, autoridad: str, medio: str, frase: str) -> dict[str, Any]:
    return {
        **ejemplos.fuente(id_, "B", es_autoridad=True),
        "medio": f"{autoridad} (declaración oficial citada en {medio})",
        "frase_origen": frase,
        "idioma": "ro",
        "campos_respaldados": ["estado", "presencia_dron"],
    }


def _ficha(id_: str, noticia: str, autoridad: str, medio: str, frase: str) -> dict[str, Any]:
    ficha = copy.deepcopy(ejemplos.incidente_minimo())
    ficha["id"] = id_
    ficha["lugar"]["pais"] = "MD"
    fuente = {**ejemplos.fuente(noticia, "C"), "medio": medio}
    declaracion = _declaracion(f"{noticia}-declaracion-1", autoridad, medio, frase)
    fecha = ejemplos.instante("2026-10-31T18:00Z")
    ficha["fuentes"] = [fuente, declaracion]
    ficha["afirmaciones"] = [declaraciones.afirmacion_presencia(noticia)]
    ficha["estado"] = {
        "actual": "confirmado",
        "historial": [
            {"estado": "notificado", "fecha": fecha, "fuente_id": noticia},
            {"estado": "confirmado", "fecha": fecha, "fuente_id": declaracion["id"]},
        ],
    }
    return ficha


def _unida() -> dict[str, Any]:
    destino = _ficha("EODI-2026-00728", "gdelt-moldpres", CENTRO, "moldpres.md",
                     "la ora 18:12, drona a părăsit spațiul aerian al Republicii Moldova")  # fmt: skip
    absorbido = _ficha("EODI-2026-00736", "gdelt-timpul", MINISTERIO, "timpul.md", FRASE_MINISTERIO)
    return incidentes.absorber(destino, absorbido, ejemplos.AHORA)[0]


def _autoridades(ficha: dict[str, Any]) -> set[str]:
    return set(reglas.declaraciones_de(ficha))


def test_la_union_conserva_las_autoridades_de_las_dos_fichas() -> None:
    unida = _unida()
    assert _autoridades(unida) == {CENTRO, MINISTERIO}
    assert {a["fuente_id"] for a in unida["afirmaciones"]} >= {"gdelt-moldpres", "gdelt-timpul"}
    assert unida["estado"]["actual"] == "confirmado"


def test_la_union_trae_la_confirmacion_anterior_al_notificado_del_destino() -> None:
    destino = _ficha("EODI-2026-00728", "gdelt-moldpres", CENTRO, "moldpres.md", "sin paso propio")
    destino["fuentes"] = destino["fuentes"][:1]
    destino["estado"] = {
        "actual": "notificado",
        "historial": [{"estado": "notificado", "fecha": ejemplos.instante("2026-10-31T20:00Z"),
                       "fuente_id": "gdelt-moldpres"}],
    }  # fmt: skip
    absorbido = _ficha("EODI-2026-00736", "gdelt-timpul", MINISTERIO, "timpul.md", FRASE_MINISTERIO)
    assert incidentes.absorber(destino, absorbido, ejemplos.AHORA)[0]["estado"]["actual"] == (
        "confirmado"
    )


def test_una_rebaja_con_motivo_posterior_no_la_deshace_la_union() -> None:
    destino = _ficha("EODI-2026-00728", "gdelt-moldpres", CENTRO, "moldpres.md", "sin paso propio")
    bajado = reglas.sin_oficiales(destino, [CENTRO], INSTANTE)[0]
    assert bajado["estado"]["actual"] == "notificado"
    absorbido = _ficha("EODI-2026-00736", "gdelt-timpul", MINISTERIO, "timpul.md", FRASE_MINISTERIO)
    assert incidentes.estado_con_el_absorbido(bajado, absorbido) == bajado["estado"]


def test_quitar_una_autoridad_deja_el_estado_si_la_otra_lo_sostiene() -> None:
    ficha, cambios = reglas.sin_oficiales(_unida(), [CENTRO], INSTANTE)
    assert cambios == ["declaración no oficial: gdelt-moldpres-declaracion-1"]
    assert ficha["estado"]["actual"] == "confirmado"
    assert _autoridades(ficha) == {MINISTERIO}


def test_quitar_las_dos_si_baja_el_estado() -> None:
    ficha = reglas.sin_oficiales(_unida(), [CENTRO, MINISTERIO], INSTANTE)[0]
    assert ficha["estado"]["actual"] == "notificado"


def test_una_autoridad_que_no_atribuye_a_un_dron_no_sostiene_el_estado() -> None:
    ficha = _unida()
    otra = next(f for f in ficha["fuentes"] if f["id"] == "gdelt-timpul-declaracion-1")
    otra["frase_origen"] = "Ministerul Apărării a confirmat incidentul de sâmbătă seara"
    assert reglas.sin_oficiales(ficha, [CENTRO], INSTANTE)[0]["estado"]["actual"] == "notificado"


def test_la_medida_guarda_el_nombre_y_sin_nombre_no_quita_ninguna() -> None:
    respuesta = {"errores": [{"dato": "autoridad", "autoridad": CENTRO, "correcto": "",
                              "duplicado_de": "", "fuente": 0, "frase": ""},
                             {"dato": "autoridad", "correcto": "", "duplicado_de": "",
                              "fuente": 0, "frase": ""}]}  # fmt: skip
    errores = entrada.comprobar_medida(respuesta, [], [])
    assert [e["autoridad"] for e in errores] == [CENTRO, ""]


def test_la_cita_revisada_vuelve_a_confirmar_la_ficha_rebajada() -> None:
    bajada = reglas.sin_oficiales(_unida(), [CENTRO, MINISTERIO], INSTANTE)[0]
    cita = {
        "incidente": "EODI-2026-00728",
        "enlace": TIMPUL,
        "medio": "timpul.md",
        "fecha": "2026-10-31",
        "idioma": "ro",
        "frase": FRASE_MINISTERIO,
        "declaracion": {"autoridad": MINISTERIO, "pais": "MD", "categoria": "ministerio",
                        "afirma": "drones"},
    }  # fmt: skip
    con = revisados.con_citas(bajada, [cita])
    vuelta = revisados.reconfirmar(con, [cita], ejemplos.instante("2026-11-02T04:00Z"))
    assert vuelta["estado"]["actual"] == "confirmado"
    assert MINISTERIO in _autoridades(vuelta)
    assert reglas.bajar_estado(vuelta, ejemplos.instante("2026-11-02T05:00Z")) is None
