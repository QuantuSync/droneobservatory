"""Ninguna ficha cambia de ida y vuelta cada hora (EODI-2025-00248, desde el 14 de octubre de
2026): la regla de la presencia confirmaba lo que el control de las fichas dejaba sin confirmar
y cada vuelta añadía otra afirmación repetida."""

import json
from datetime import timedelta

from almacen.base import Almacen, sin_afirmaciones_repetidas
from proceso import control_fichas as reglas
from proceso import presencia
from tests.test_declaraciones import afirmaciones_de_presencia, extraer_con_declaracion
from tests.test_extraccion import AHORA, MODELOS

FRASE = "Zowel in de lucht als op de grond werd niets meer gevonden"


def _sin_confirmar(almacen: Almacen) -> str:
    """Un incidente con la declaración de la policía que la regla confirmaría, guardado sin
    confirmar (como lo deja el control)."""
    id_ = extraer_con_declaracion(almacen)
    nuevo = almacen.incidente(id_)
    assert nuevo is not None and nuevo["presencia_dron"] == "confirmada"
    anterior = {**nuevo, "presencia_dron": "no_confirmada",
                "afirmaciones": [a for a in nuevo["afirmaciones"]
                                 if a not in afirmaciones_de_presencia(nuevo)]}  # fmt: skip
    with almacen._conexion:
        almacen._upsert("incidentes", {"id": id_, "tipo": anterior["tipo"],
                                       "estado": anterior["estado"]["actual"],
                                       "documento": json.dumps(anterior)})  # fmt: skip
    return id_


def _niega_el_control(almacen: Almacen, id_: str) -> str:
    incidente = almacen.incidente(id_)
    assert incidente is not None
    fuente = next(f["id"] for f in incidente["fuentes"] if not f.get("es_autoridad"))
    almacen.guardar_controles({f"verificacion:{id_}": {
        "fecha": "2025-09-24T12:00:00Z", "huella": "x", "version": "control/4",
        "datos": {"presencia": ["no_hallado", fuente, FRASE]},
    }}, "2025-09-24T12:00:00Z")  # fmt: skip
    return str(fuente)


def test_la_regla_de_la_presencia_no_confirma_lo_que_el_control_lee_como_no_hallado() -> None:
    almacen = Almacen.abrir()
    id_ = _sin_confirmar(almacen)
    # Sin el control, la regla la confirmaría con la declaración de la policía.
    assert [i["id"] for i, _ in presencia.pendientes(almacen)] == [id_]
    _niega_el_control(almacen, id_)
    assert presencia.pendientes(almacen) == []
    antes = len(almacen.historial(id_))
    for hora in range(3):
        assert presencia.revisar(almacen, AHORA + timedelta(hours=hora), MODELOS)[0] == []
    assert len(almacen.historial(id_)) == antes
    incidente = almacen.incidente(id_)
    assert incidente is not None and incidente["presencia_dron"] == "no_confirmada"


def test_una_verificacion_anulada_no_frena_la_regla() -> None:
    almacen = Almacen.abrir()
    id_ = _sin_confirmar(almacen)
    fuente = _niega_el_control(almacen, id_)
    almacen.guardar_controles({f"verificacion:{id_}": {
        "fecha": "2025-09-24T13:00:00Z", "huella": "x", "version": "control/4", "anulada": True,
        "datos": {"presencia": ["no_hallado", fuente, FRASE]},
    }}, "2025-09-24T13:00:00Z")  # fmt: skip
    assert [i["id"] for i, _ in presencia.pendientes(almacen)] == [id_]


def test_el_control_no_repite_la_afirmacion_al_dejarla_sin_confirmar() -> None:
    almacen = Almacen.abrir()
    id_ = extraer_con_declaracion(almacen)
    incidente = almacen.incidente(id_)
    assert incidente is not None
    fuente = next(f["id"] for f in incidente["fuentes"] if not f.get("es_autoridad"))
    afirmacion = reglas._afirmacion("presencia_dron", "no_confirmada", fuente)
    con_ella = {**incidente, "presencia_dron": "confirmada",
                "afirmaciones": [*incidente["afirmaciones"], afirmacion]}  # fmt: skip
    correccion = reglas.Correccion(con_ella)
    reglas._presencia(correccion, reglas.Verificada({"presencia": ("no_hallado", fuente, FRASE)}))
    afirmaciones = correccion.incidente["afirmaciones"]
    assert afirmaciones.count(afirmacion) == 1


def test_las_afirmaciones_repetidas_no_se_guardan() -> None:
    almacen = Almacen.abrir()
    id_ = extraer_con_declaracion(almacen)
    incidente = almacen.incidente(id_)
    assert incidente is not None
    repetida = incidente["afirmaciones"][0]
    almacen.guardar_incidente(
        {**incidente, "afirmaciones": [*incidente["afirmaciones"], repetida, repetida]},
        AHORA, MODELOS,
    )  # fmt: skip
    guardado = almacen.incidente(id_)
    assert guardado is not None and guardado["afirmaciones"] == incidente["afirmaciones"]
    # Igual a lo que había: no deja cambio en el historial.
    antes = len(almacen.historial(id_))
    almacen.guardar_incidente(guardado, AHORA, MODELOS)
    assert len(almacen.historial(id_)) == antes
    assert sin_afirmaciones_repetidas(guardado) is guardado
