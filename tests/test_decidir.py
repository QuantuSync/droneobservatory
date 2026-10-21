"""Un solo sitio decide el estado y la presencia (proceso/decidir.py): una prueba por causa de las
discrepancias de estado y presencia de la referencia, con la ficha real como ejemplo."""

import copy
import json

from esquema import Documento
from proceso import decidir, referencia
from recogida import revisados

INSTANTE = {"valor": "2026-10-21T15:00Z", "precision": "minuto"}


def _copia(id_: str) -> Documento:
    ruta = referencia.DIRECTORIO / "fichas" / f"{id_}.json"
    documento: Documento = json.loads(ruta.read_text(encoding="utf-8"))
    return documento


def _sin_revision(id_: str) -> tuple[Documento, list[Documento]]:
    """La ficha como estaba antes de sus citas revisadas (solo la noticia que la abrió) y esas
    citas de configuracion/incidentes_revisados.json."""
    documento = _copia(id_)
    citas = [c for c in revisados.cargar()["citas"] if c["incidente"] == id_]
    revisadas = {revisados.fuente_de_cita(c, documento)["id"] for c in citas}
    antes = copy.deepcopy(documento)
    antes["fuentes"] = [f for f in documento["fuentes"] if f["id"] not in revisadas]
    antes["afirmaciones"] = [
        a for a in documento.get("afirmaciones", []) if a["fuente_id"] not in revisadas
    ]
    antes["estado"] = {"actual": "notificado", "historial": documento["estado"]["historial"][:1]}
    antes.pop("atribucion", None)
    antes["presencia_dron"] = "no_confirmada"
    return antes, citas


def test_la_autoridad_que_cuenta_lo_ocurrido_confirma_el_suceso() -> None:
    # Geilenkirchen: la policía cuenta que fue a mirar y no vio ningún dron; el aviso ocurrió.
    geilenkirchen = _copia("EODI-2025-00225")
    assert geilenkirchen["estado"]["actual"] == "notificado"
    decision = decidir.decidir_estado(geilenkirchen)
    assert (decision.valor, decision.regla) == ("confirmado", "autoridad_lo_cuenta")
    aplicado = decidir.aplicar(geilenkirchen)
    assert aplicado["estado"]["historial"][-1]["fuente_id"] == decision.fuente_id
    # Schiphol: la Marechaussee concluye que era un globo; el suceso queda confirmado y la
    # presencia, descartada.
    schiphol = decidir.aplicar(_copia("EODI-2025-00203"))
    assert (schiphol["estado"]["actual"], schiphol["presencia_dron"]) == (
        "confirmado", "descartada",
    )  # fmt: skip


def test_el_desmentido_que_solo_niega_el_dron_no_desmiente_el_suceso() -> None:
    # Limburgo: «Ces recherches n'avaient permis de retrouver aucun drone».
    limburgo = _copia("EODI-2025-00357")
    assert limburgo["estado"]["actual"] == "desmentido"
    assert decidir.decidir_estado(limburgo).valor == "confirmado"
    # Vilna: el radar vio una bandada de pájaros; el tráfico se paró.
    vilna = _copia("EODI-2026-00007")
    assert vilna["estado"]["actual"] == "desmentido"
    assert decidir.aplicar(vilna)["estado"]["actual"] == "confirmado"


def test_la_cita_revisada_de_la_autoridad_confirma_o_atribuye() -> None:
    # Riga: el aeropuerto informa del aviso (cita revisada que afirma el incidente).
    riga, citas = _sin_revision("EODI-2025-00043")
    assert decidir.decidir_estado(riga).valor == "notificado"
    assert decidir.aplicar(revisados.con_citas(riga, citas))["estado"]["actual"] == "confirmado"
    # Varsovia: Tusk atribuye los drones a Rusia y el ejército confirma que los derribó.
    varsovia, citas = _sin_revision("EODI-2025-00233")
    resultado = decidir.aplicar(revisados.con_citas(varsovia, citas))
    assert resultado["estado"]["actual"] == "atribuido"
    assert resultado["atribucion"]["pais"] == "RU"
    assert resultado["presencia_dron"] == "confirmada"


def test_la_presencia_revisada_y_las_aeronaves_no_tripuladas() -> None:
    # Aalborg: Rigspolitiet cerró la investigación sin probarlo ni descartarlo.
    aalborg = _copia("EODI-2025-00228")
    decision = decidir.decidir_presencia(aalborg)
    assert (decision.valor, decision.regla) == ("no_acreditada", "revision")
    # Tulcea: el MApN detectó por radar «dos aeronaves no tripuladas».
    tulcea, citas = _sin_revision("EODI-2026-00488")
    assert decidir.aplicar(revisados.con_citas(tulcea, citas))["presencia_dron"] == "confirmada"
