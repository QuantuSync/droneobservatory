"""La presencia del dron confirmada exige el suceso confirmado.

EODI-2025-00278 («Dron militar descubierto en un campo en Taraclia», Moldavia, 12 de febrero de
2025) se publicaba con el suceso «notificado» y la presencia «confirmada». La presencia la daba la
revisión a mano (incidentes_revisados.json, «titulares») con una frase del periódico, «O dronă a
fost descoperită pe un câmp din apropierea satului Salcia, raionul Taraclia», y `decidir_presencia`
la aplicaba sin mirar el estado; el estado solo lo confirma una autoridad, y ninguna fuente de la
ficha era de autoridad. Lo mismo en otras diez fichas, todas por una revisión de la presencia.

El artículo original (adevarul.ro, 12/02/2025) sí trae a la autoridad: «După primele examinări
s-a determinat că aceasta nu are atașat explozibil.Nu există riscuri sau pericole pentru siguranța
cetățenilor din regiune”, au informat reprezentanții IGP.» Con esa cita revisada, el suceso queda
confirmado y la presencia, confirmada. Sin cita de autoridad (00056, 00080 y 00629: solo la prensa
cuenta lo que hicieron los agentes), la presencia queda no confirmada.
"""

import copy

import pytest

from esquema import Documento
from proceso import auditoria_fichas, decidir, declaraciones, protegido
from recogida import revisados
from tests import ejemplos
from tests.test_calidad_datos_3 import inc

ENLACE = (
    "https://adevarul.ro/stiri-externe/republica-moldova/"
    "o-drona-a-cazut-in-republica-moldova-politia-2421467.html"
)
# Las fichas publicadas el 22/11/2026 con presencia confirmada y suceso «notificado».
CON_CITA = [
    "EODI-2025-00048", "EODI-2025-00158", "EODI-2025-00278", "EODI-2025-00296",
    "EODI-2025-00317", "EODI-2025-00390", "EODI-2026-00359", "EODI-2026-00519",
]  # fmt: skip
SIN_AUTORIDAD = ["EODI-2026-00056", "EODI-2026-00080", "EODI-2026-00629"]


def taraclia() -> Documento:
    """EODI-2025-00278 como se publicaba el 22/11/2026."""
    documento = inc("EODI-2025-00278", "2025-02-12T00:00Z", "dia", "Salcia", (45.73, 28.6), "MD")
    documento.pop("objetivo")
    documento["fuentes"][0] = {
        **ejemplos.fuente("gdelt-7d8db24e3c395739", "C"),
        "enlace": "https://news.yam.md/ro/story/16381588",
        "medio": "news.yam.md",
        "fecha": ejemplos.instante("2025-02-12T12:00Z", "aproximada"),
        "frase_origen": "Dronă militară, descoperită pe un câmp, la Taraclia.",
    }
    documento["fuentes"].append({
        **ejemplos.fuente("revisada-d564796cdfce594f", "C"),
        "enlace": ENLACE,
        "medio": "adevarul.ro",
        "fecha": ejemplos.instante("2025-02-12T00:00Z", "aproximada"),
        "frase_origen": "O dronă a fost descoperită pe un câmp din apropierea satului Salcia, "
        "raionul Taraclia, din sudul Republicii Moldova",
    })  # fmt: skip
    documento["estado"] = {
        "actual": "notificado",
        "historial": [{"estado": "notificado", "fecha": documento["fuentes"][0]["fecha"],
                       "fuente_id": documento["fuentes"][0]["id"]}],
    }  # fmt: skip
    documento["presencia_dron"] = "confirmada"
    return documento


def _citas(id_: str) -> list[Documento]:
    return [c for c in revisados.cargar()["citas"] if c["incidente"] == id_]


def test_taraclia_la_presencia_revisada_no_se_confirma_sin_el_suceso() -> None:
    documento = taraclia()
    decision = decidir.decidir_presencia(documento)
    assert decision.valor == "no_confirmada"
    assert decision.regla == decidir.SIN_SUCESO_CONFIRMADO
    # Sin el estado, la revisión a mano la daría confirmada: es el camino que las desacoplaba.
    confirmado = {**documento, "estado": {**documento["estado"], "actual": "confirmado"}}
    assert decidir.decidir_presencia(confirmado).regla == "revision"


def test_taraclia_auditoria_ad() -> None:
    documento = taraclia()
    assert auditoria_fichas.confirmada_sin_suceso(documento)
    assert auditoria_fichas.auditar([documento])["AD"] == ["EODI-2025-00278"]
    # Tras decidir (al guardar), ya no.
    assert not auditoria_fichas.confirmada_sin_suceso(decidir.aplicar(copy.deepcopy(documento)))


def test_taraclia_con_la_cita_de_la_policia_el_suceso_y_la_presencia_se_confirman() -> None:
    documento = taraclia()
    citas = _citas("EODI-2025-00278")
    igp = [c for c in citas if c.get("declaracion")]
    assert len(igp) == 1
    assert igp[0]["declaracion"]["autoridad"] == "Inspectoratul General al Poliției"
    assert "au informat reprezentanții IGP" in igp[0]["frase"]
    con_cita = revisados.con_citas(documento, citas)
    decidido = decidir.aplicar(con_cita)
    assert decidido["estado"]["actual"] == "confirmado"
    assert decidido["presencia_dron"] == "confirmada"
    assert not auditoria_fichas.confirmada_sin_suceso(decidido)
    assert not auditoria_fichas.estado_sin_frase_que_reconozca(decidido)


def test_taraclia_sin_cita_la_presencia_baja_y_el_cerrojo_la_deja_pasar() -> None:
    guardado = taraclia()
    nuevo = decidir.aplicar(copy.deepcopy(guardado))
    assert nuevo["estado"]["actual"] == "notificado"
    assert nuevo["presencia_dron"] == "no_confirmada"
    veredicto = protegido.juzgar(
        guardado, nuevo, ["recogida.control_fichas.reglas_deterministas"], lambda fuente: ""
    )
    assert veredicto.retenidos == []


def test_la_revision_de_la_presencia_no_se_aplica_con_el_suceso_sin_confirmar() -> None:
    documento = taraclia()
    revision = {"incidente": "EODI-2025-00278", "presencia": {"valor": "confirmada"}}
    assert revisados.presencia_sin_suceso(revision, documento)
    documento["estado"]["actual"] = "confirmado"
    assert not revisados.presencia_sin_suceso(revision, documento)
    assert not revisados.presencia_sin_suceso({"presencia": {"valor": "no_confirmada"}}, taraclia())


@pytest.mark.parametrize("id_", CON_CITA)
def test_cada_ficha_medida_tiene_una_cita_de_autoridad_que_reconoce_el_suceso(id_: str) -> None:
    citas = [c for c in _citas(id_) if c.get("declaracion")]
    assert citas, id_
    assert any(
        declaraciones.reconoce_suceso(c["frase"], c["declaracion"]["autoridad"])
        and c["declaracion"]["afirma"] in declaraciones.CONFIRMAN
        for c in citas
    )


@pytest.mark.parametrize("id_", SIN_AUTORIDAD)
def test_sin_autoridad_no_queda_revision_que_confirme_la_presencia(id_: str) -> None:
    assert decidir.presencias_revisadas().get(id_) != "confirmada"
