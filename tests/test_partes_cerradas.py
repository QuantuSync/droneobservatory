"""Las partes de una separación revisada (docs/ciclo_de_vida.md): su primera extracción con su
suceso no está atada a lo que decidía la ficha mezclada, su candidato está cerrado a los artículos
nuevos, y el gasto de esas extracciones tiene un tope diario."""

import copy
from datetime import UTC, datetime

import pytest

from almacen.base import Almacen
from exportacion import puerta
from modelo import coste
from proceso import decidir, extraccion, protegido
from proceso.noticias import Agrupacion, agrupar, filtro
from tests.ejemplos import VOCABULARIO_MODELOS
from tests.test_cerrojo import base, ficha, version_mala
from tests.test_control_fichas import AHORA
from tests.test_noticias import NOM, articulo

ID = "EODI-2026-09600"
PARTE = {"fecha": "2026-11-08", "descripcion": "el domingo", "desde": "2026-11-09T19:17Z"}
CANDIDATO = {"id": "CAND-PARTE", "articulos": [], "parte": PARTE}
PILA_DE_PARTE = [protegido.PARTE_SEPARADA, "proceso.extraccion._guardar_version"]
PILA_NORMAL = ["proceso.extraccion._guardar_version", "proceso.extraccion._alta"]


def _publicada() -> Almacen:
    almacen = base(ficha())
    puerta.dar_pase(almacen, AHORA, [ID])
    return almacen


def test_la_primera_extraccion_de_la_parte_cambia_lo_decidido_con_cita(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # EODI-2026-00770 (Leipzig/Halle): la parte que conserva el identificador no podía dejar los
    # datos de la ficha mezclada, porque las frases compartidas los daban por «decididos».
    almacen = _publicada()
    guardado = almacen.incidente(ID)
    assert guardado is not None
    del_domingo = version_mala(guardado, "inicio")
    # Una extracción cualquiera: el cerrojo retiene el día decidido con cita.
    monkeypatch.setattr(protegido, "pila", lambda: PILA_NORMAL)
    almacen.guardar_incidente(copy.deepcopy(del_domingo), AHORA, VOCABULARIO_MODELOS)
    assert almacen.incidente(ID) == guardado
    # La primera extracción de la parte, hecha solo con su suceso: pasa.
    monkeypatch.setattr(protegido, "pila", lambda: PILA_DE_PARTE)
    extraccion.guardar_parte_separada(almacen, del_domingo, AHORA, VOCABULARIO_MODELOS)
    queda = almacen.incidente(ID)
    assert queda is not None and queda["tiempo"]["inicio"] == del_domingo["tiempo"]["inicio"]
    permitidos = almacen.controles(protegido.PREFIJO_PERMITIDO)
    assert {d["motivo"] for d in permitidos.values()} == {"separacion"}


def test_lo_revisado_a_mano_manda_tambien_en_la_parte(monkeypatch: pytest.MonkeyPatch) -> None:
    almacen = _publicada()
    guardado = almacen.incidente(ID)
    assert guardado is not None
    revision = {
        "incidente": ID, "campo": "drones", "valor": {"min": 1, "max": 1}, "cita": "la frase",
        "enlace": guardado["fuentes"][0]["enlace"], "pais": "DE", "motivo": "revisado",
    }  # fmt: skip
    monkeypatch.setattr(decidir, "_revisiones_de_datos", lambda: {ID: {"drones": revision}})
    monkeypatch.setattr(protegido, "pila", lambda: PILA_DE_PARTE)
    dos = copy.deepcopy(guardado)
    dos["drones"] = {"numero": {"min": 2, "max": 2}}
    extraccion.guardar_parte_separada(almacen, dos, AHORA, VOCABULARIO_MODELOS)
    queda = almacen.incidente(ID)
    assert queda is not None and queda["drones"]["numero"] == {"min": 1, "max": 1}


def test_la_parte_es_la_primera_una_sola_vez() -> None:
    almacen = Almacen.abrir()
    assert extraccion.primera_de_la_parte(almacen, CANDIDATO) is True
    extraccion.anotar_parte_extraida(almacen, CANDIDATO, ID, AHORA)
    assert extraccion.primera_de_la_parte(almacen, CANDIDATO) is False
    # Un candidato sin parte no lo es nunca; y si la revisión cambia la parte, vuelve a serlo.
    assert extraccion.primera_de_la_parte(almacen, {"id": "CAND-X", "articulos": []}) is False
    otra = {**CANDIDATO, "parte": {**PARTE, "desde": "2026-11-10T08:17Z"}}
    assert extraccion.primera_de_la_parte(almacen, otra) is True


def test_el_candidato_de_una_parte_no_recibe_articulos_nuevos() -> None:
    # Fallo 7 del repaso del 10/11/2026: tras una separación, un artículo nuevo del sitio iba al
    # candidato de una sola de las partes (la de inicio más reciente), fuera o no de su suceso.
    agrupacion = agrupar([articulo(1, 0, "EKCH")], filtro(), NOM)
    (parte,) = agrupacion.candidatos
    parte.parte = dict(PARTE)
    antes = list(parte.articulos)
    agrupar([articulo(2, 3, "EKCH")], filtro(), NOM, agrupacion)
    assert parte.articulos == antes
    (_, nuevo) = agrupacion.candidatos
    assert nuevo.parte is None and len(nuevo.articulos) == 1
    # Sin parte, como siempre: el artículo va al candidato abierto del sitio.
    normal = agrupar([articulo(1, 0, "EKCH")], filtro(), NOM, Agrupacion())
    agrupar([articulo(2, 3, "EKCH")], filtro(), NOM, normal)
    assert len(normal.candidatos) == 1 and len(normal.candidatos[0].articulos) == 2


def test_el_gasto_de_las_separaciones_es_diario() -> None:
    # Decisión del 10 de noviembre de 2026: de 5 USD de por vida a 0,50 USD al día.
    assert coste.limite(coste.Modo.REVISION) == 0.50
    assert coste.diario(coste.Modo.REVISION)
    hoy = datetime(2026, 11, 10, 15, 0, tzinfo=UTC)
    assert coste.dia_del_gasto(coste.Modo.REVISION, hoy) == "2026-11-10"
    assert coste.dia_del_gasto(coste.Modo.HORARIO, hoy) == "2026-11-10"
    assert coste.dia_del_gasto(coste.Modo.HISTORICO, hoy) is None


def test_la_parte_ya_extraida_tras_su_separacion_no_es_la_primera() -> None:
    # EODI-2026-00770 (Leipzig/Halle): separada el 9 de noviembre de 2026, antes de llevar la
    # cuenta de las partes extraídas, y ya corregida. Al volver a extraerse contaba como «primera»
    # y perdía la localidad y la región que el cerrojo le guardaba.
    almacen = Almacen.abrir()
    desde = str(PARTE["desde"])
    # Una extracción anterior a la separación, o una que no dio ficha, no cuenta.
    almacen.guardar_extraccion("CAND-PARTE", "2026-11-01T10:00:00Z", "v", "h", True, {})
    almacen.guardar_extraccion("CAND-PARTE", desde[:16] + ":30Z", "v", "h", False, {})
    assert extraccion.primera_de_la_parte(almacen, CANDIDATO) is True
    almacen.guardar_extraccion("CAND-PARTE", desde[:16] + ":40Z", "v", "h", True, {})
    assert extraccion.primera_de_la_parte(almacen, CANDIDATO) is False
