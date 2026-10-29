"""Lo decidido de una ficha no se pierde al volver a extraerla (proceso/decididos.py): el día de
EODI-2026-00066 («Sunday, September 13th») pasó a la fecha de publicación de la noticia al volver
a extraerla el 29 de octubre de 2026."""

import copy
from collections.abc import Iterator
from datetime import timedelta
from typing import Any

import pytest

from almacen.base import Almacen
from modelo import coste, ficha
from proceso import auditoria_fichas, decididos, extraccion
from tests.test_extraccion import (
    AHORA,
    MODELOS,
    TEXTO,
    campo,
    candidato_con_articulos,
    ficha_ejemplo,
    respuesta,
)


@pytest.fixture
def almacen() -> Iterator[Almacen]:
    a = Almacen.abrir()
    yield a
    a.cerrar()


def _peticion(almacen: Almacen) -> extraccion.Peticion:
    candidato = candidato_con_articulos(almacen)
    peticion = extraccion.preparar(almacen, candidato, None)
    return extraccion.Peticion(
        **{**peticion.__dict__, "fuentes": [
            ficha.FuenteTexto(f.medio, f.fecha, f.idioma, f.titular, TEXTO)
            for f in peticion.fuentes
        ]}
    )  # fmt: skip


def _extraer(almacen: Almacen, peticion: extraccion.Peticion, datos: dict[str, Any],
             horas: int = 0) -> str:  # fmt: skip
    id_ = extraccion.procesar_respuesta(
        almacen, peticion, respuesta(datos), AHORA + timedelta(hours=horas),
        coste.Modo.HISTORICO, True, MODELOS,
    )  # fmt: skip
    assert id_ is not None
    return id_


def _ficha(almacen: Almacen, id_: str) -> dict[str, Any]:
    incidente = almacen.incidente(id_)
    assert incidente is not None
    return incidente


SIN_DIA = {"inicio": campo(None), "inicio_precision": campo(None)}


# --- Una extracción nueva -----------------------------------------------------------------------


def test_el_dia_con_su_frase_no_pasa_a_la_fecha_de_publicacion(almacen: Almacen) -> None:
    peticion = _peticion(almacen)
    id_ = _extraer(almacen, peticion, ficha_ejemplo())
    antes = _ficha(almacen, id_)["tiempo"]
    assert antes["origen_inicio"]["tipo"] != decididos.SIN_FRASE
    # La extracción nueva (con las mismas fuentes) ya no da el día.
    assert _extraer(almacen, peticion, ficha_ejemplo(**SIN_DIA), horas=1) == id_
    despues = _ficha(almacen, id_)
    assert despues["tiempo"] == antes
    assert any(a["campo"] == "inicio" for a in despues["afirmaciones"])


def test_el_numero_de_drones_y_el_cierre_no_se_pierden(almacen: Almacen) -> None:
    peticion = _peticion(almacen)
    id_ = _extraer(almacen, peticion, ficha_ejemplo())
    antes = _ficha(almacen, id_)
    assert antes["drones"]["numero"] == {"min": 3, "max": 4}
    _extraer(almacen, peticion, ficha_ejemplo(drones=campo(None), cierre=campo(None)), horas=1)
    despues = _ficha(almacen, id_)
    assert despues["drones"]["numero"] == {"min": 3, "max": 4}
    assert despues["consecuencias"]["cierre"]["valor"] == "si"


# --- Las reglas de cada dato --------------------------------------------------------------------


def _par(almacen: Almacen) -> tuple[dict[str, Any], dict[str, Any]]:
    id_ = _extraer(almacen, _peticion(almacen), ficha_ejemplo())
    anterior = _ficha(almacen, id_)
    return anterior, copy.deepcopy(anterior)


def test_tras_una_separacion_el_dato_se_va_con_su_suceso(almacen: Almacen) -> None:
    """La fuente que daba el dato ya no está en la ficha (se separó): no se conserva."""
    anterior, nuevo = _par(almacen)
    nuevo["drones"]["numero"] = "desconocido"
    nuevo["tiempo"]["origen_inicio"] = {"tipo": "publicacion", "motivo": "sin frase"}
    nuevo["fuentes"] = [{**nuevo["fuentes"][0], "id": "gdelt-otra"}]
    assert decididos.juicios(nuevo, anterior) == {}


def test_el_lugar_no_pasa_a_uno_menos_preciso(almacen: Almacen) -> None:
    anterior, nuevo = _par(almacen)
    assert anterior["lugar"]["nivel"] == "instalacion"
    nuevo["lugar"] = {"pais": "DK", "nivel": "pais"}
    nuevo.pop("objetivo", None)
    conservacion = decididos.conservar(nuevo, anterior)
    assert conservacion.conservados == ["lugar"]
    assert conservacion.incidente["lugar"] == anterior["lugar"]
    assert conservacion.incidente.get("objetivo") == anterior.get("objetivo")
    # Otro nombre del mismo sitio, al mismo nivel, no es una pérdida.
    nuevo["lugar"] = {**anterior["lugar"], "suceso": "Copenhagen Airport"}
    assert "lugar" not in decididos.juicios(nuevo, anterior)


def test_la_hora_del_mismo_dia_no_se_pierde(almacen: Almacen) -> None:
    anterior, nuevo = _par(almacen)
    dia = anterior["tiempo"]["inicio"]["valor"][:10]
    nuevo["tiempo"] = {
        "inicio": {"valor": f"{dia}T00:00Z", "precision": "dia"},
        "origen_inicio": {**anterior["tiempo"]["origen_inicio"], "motivo": "«mandag»"},
    }
    assert decididos.juicios(nuevo, anterior) == {"inicio": "pierde"}


def test_otra_frase_con_otro_valor_pasa_al_control_sin_cambiar_la_ficha(almacen: Almacen) -> None:
    anterior, nuevo = _par(almacen)
    nuevo["drones"]["numero"] = {"min": 1, "max": 1}
    nuevo["tiempo"]["inicio"] = {"valor": "2025-09-20T00:00Z", "precision": "dia"}
    nuevo["tiempo"]["origen_inicio"] = {**anterior["tiempo"]["origen_inicio"],
                                        "motivo": "«20. september»"}  # fmt: skip
    nuevo["tiempo"].pop("fin", None)
    ahora = AHORA + timedelta(hours=2)
    queda = extraccion.conservar_decididos(almacen, nuevo, anterior, ahora)
    assert queda["drones"]["numero"] == anterior["drones"]["numero"]
    assert queda["tiempo"] == anterior["tiempo"]
    pendiente = almacen.controles(extraccion.PREFIJO_REEXTRACCION)[
        extraccion.PREFIJO_REEXTRACCION + anterior["id"]
    ]
    assert {c["dato"] for c in pendiente["contradichos"]} == {"drones", "inicio"}


def test_la_misma_frase_leida_con_las_reglas_de_ahora_no_es_una_contradiccion(
    almacen: Almacen,
) -> None:
    anterior, nuevo = _par(almacen)
    nuevo["tiempo"]["inicio"] = {"valor": "2025-09-21T00:00Z", "precision": "dia"}
    nuevo["tiempo"].pop("fin", None)
    assert "inicio" not in decididos.juicios(nuevo, anterior)


def test_lo_que_no_estaba_decidido_lo_da_la_nueva(almacen: Almacen) -> None:
    anterior, nuevo = _par(almacen)
    anterior["drones"]["numero"] = "desconocido"
    anterior["tiempo"]["origen_inicio"] = {"tipo": "publicacion", "motivo": "sin frase"}
    assert decididos.juicios(nuevo, anterior) == {}


# --- El control y la auditoría ------------------------------------------------------------------


def test_el_control_verifica_la_ficha_contradicha() -> None:
    from recogida import control_fichas

    class Ctx:
        def __init__(self, decisiones: dict[str, Any]) -> None:
            self.decisiones = decisiones

        def decision(self, clave: str) -> Any:
            return self.decisiones.get(clave)

    clave = extraccion.PREFIJO_REEXTRACCION + "EODI-2026-00066"
    ctx: Any = Ctx({clave: {"fecha": "2026-10-29T20:22:00Z", "contradichos": []}})
    assert control_fichas.contradicha(ctx, "EODI-2026-00066", None)
    assert control_fichas.contradicha(ctx, "EODI-2026-00066", {"fecha": "2026-10-29T19:30:00Z"})
    # Verificada después: resuelta.
    assert not control_fichas.contradicha(ctx, "EODI-2026-00066",
                                          {"fecha": "2026-10-29T20:30:00Z"})  # fmt: skip
    assert not control_fichas.contradicha(ctx, "EODI-2026-00001", None)


def test_auditoria_w_dato_decidido_perdido_en_una_reextraccion(almacen: Almacen) -> None:
    anterior, nuevo = _par(almacen)
    nuevo["tiempo"] = {
        "inicio": {"valor": "2025-09-24T05:00Z", "precision": "aproximada"},
        "origen_inicio": {"tipo": "publicacion", "motivo": "fecha de publicación"},
    }
    candidato = anterior["control"]["candidato"]
    cambio = {"entidad_id": anterior["id"], "tabla": "incidentes", "anterior": anterior,
              "nuevo": nuevo, "fecha": "2026-10-29T20:22:37Z"}  # fmt: skip
    extracciones = {candidato: ["2026-10-29T20:20:01Z"]}
    resultado = auditoria_fichas.auditar([nuevo], [cambio], extracciones=extracciones)
    assert resultado["W"] == [f"{anterior['id']} inicio"]
    # Recuperado después (una revisión o la siguiente extracción): ya no cuenta.
    assert auditoria_fichas.auditar([anterior], [cambio], extracciones=extracciones)["W"] == []
    # Sin una extracción de su candidato, el cambio es de otro paso (el control, una regla).
    sin = {candidato: ["2026-10-29T18:20:01Z"]}
    assert auditoria_fichas.auditar([nuevo], [cambio], extracciones=sin)["W"] == []
