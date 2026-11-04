"""EODI-2026-00728 (Viișoara, Moldavia, 31 de octubre de 2026): la unión conservó las dos
autoridades, la medida a las 24 horas dudó de una y quitó las dos, y el control bajó el estado a
«notificado» porque miraba solo la fuente del paso del historial."""

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
    frase = "la ora 18:12, drona a părăsit spațiul aerian al Republicii Moldova"
    destino = _ficha("EODI-2026-00728", "gdelt-moldpres", CENTRO, "moldpres.md", frase)
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


def test_la_cita_traducida_nombra_el_ministerio_de_moldavia() -> None:
    # El traductor escribía «Ministerio de Defensa Nacional», el nombre del rumano (4/11/2026).
    from exportacion import citas

    frase = "Ministerul Apărării a anunțat că drona a părăsit spațiul aerian al Republicii Moldova"
    publico: dict[str, Any] = {
        "lugar": {"pais": "MD"},
        "fuentes": [{"id": "f1", "frase_origen": frase, "traduccion": {
            "es": "el Ministerio de Defensa Nacional anunció que el dron abandonó el espacio aéreo",
            "en": "the Ministry of National Defence announced that the drone left the airspace",
        }}],
        "afirmaciones_publicas": [{"cita": FRASE_MINISTERIO, "cita_traduccion": {
            "es": "Según el Ministerio de Defensa, el segundo dron penetró",
            "en": "According to the Ministry of National Defence, the second drone entered",
        }}],
    }  # fmt: skip
    citas.con_su_pais(publico)
    assert publico["fuentes"][0]["traduccion"] == {
        "es": "el Ministerio de Defensa anunció que el dron abandonó el espacio aéreo",
        "en": "the Ministry of Defence announced that the drone left the airspace",
    }
    assert publico["afirmaciones_publicas"][0]["cita_traduccion"]["en"] == (
        "According to the Ministry of Defence, the second drone entered"
    )


def test_el_ministerio_rumano_citado_en_moldavia_sigue_siendo_de_defensa_nacional() -> None:
    from proceso import autoridades

    original = "Ministerul Apărării Naționale al României a anunțat"
    traducida = "El Ministerio de Defensa Nacional de Rumanía anunció"
    assert autoridades.traduccion_de_su_pais(original, traducida, "es", "MD") == traducida
    # Y en Rumanía no cambia nada.
    assert (
        autoridades.traduccion_de_su_pais("Ministerul Apărării a anunțat", traducida, "es", "RO")
        == traducida
    )


def test_lo_que_resume_varios_sucesos_se_retira_como_no_es_un_suceso() -> None:
    # EODI-2026-00744, el balance mensual de Moldavia, se retiró como «no verificable» (3/11/2026).
    from recogida import control_fichas

    decisiones = {
        "par:EODI-2026-00728|EODI-2026-00744": {"decision": "distinto", "varios_sucesos": True},
        "par:EODI-2026-00700|EODI-2026-00701": {"decision": "distinto", "varios_sucesos": True},
    }
    assert control_fichas.resume_varios_sucesos(decisiones, "EODI-2026-00744")
    assert not control_fichas.resume_varios_sucesos(decisiones, "EODI-2026-00702")
    assert control_fichas.MOTIVO_VARIOS_SUCESOS.startswith("No es un suceso")
