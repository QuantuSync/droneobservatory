"""Dos autoridades oficiales que se contradicen (proceso/competencia.py): prevalece la competente
sobre el espacio aéreo o la investigación, y la otra queda en el historial. Caso: Bruselas,
12/09/2026 (EODI-2026-00293), skeyes frente a Brussels Airport; su corrección revisada a mano
(recogida/revisados.con_titular) y que una recogida posterior no la deshace."""

import copy
from datetime import UTC, datetime
from typing import Any

from almacen.base import Almacen
from proceso import competencia, declaraciones
from proceso.estados import errores_historial
from recogida import revisados
from tests import ejemplos
from tests.ejemplos import VOCABULARIO_MODELOS

SKEYES = (
    "Skeyes hatte die Drohne eigenen Angaben zufolge sowohl mit bloßem Auge als auch über "
    "Detektionsgeräte erfasst."
)
AEROPUERTO = "Brussels Airport erklärte hingegen, keine Meldung erhalten zu haben."
ID = "EODI-2026-00293"
# Después del suceso: las fechas de septiembre de 2026 no son futuras.
AHORA = datetime(2026, 10, 16, 9, tzinfo=UTC)


def _noticia(
    enlace: str = "https://brf.be/national/2108502", id_: str = "gdelt-33e66272912bbe6a"
) -> dict[str, Any]:
    return {
        **ejemplos.fuente(id_, "C"),
        "enlace": enlace,
        "medio": enlace.split("/")[2],
        "fecha": ejemplos.instante("2026-09-13T09:30Z", "aproximada"),
        "frase_origen": "Über dem Flughafen Zaventem ist eine Drohne gesichtet worden.",
    }


def _bruselas() -> dict[str, Any]:
    documento = ejemplos.incidente_minimo()
    documento["id"] = ID
    noticia = _noticia()
    documento["fuentes"] = [noticia]
    documento["estado"]["historial"][0]["fuente_id"] = noticia["id"]
    return documento


def _pares(
    noticia: dict[str, Any], categoria_niega: str = "aeropuerto"
) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    confirma = {
        "autoridad": "Skeyes",
        "pais": "BE",
        "categoria": "navegacion_aerea",
        "afirma": "incidente",
        "frase": SKEYES,
    }
    niega = {
        "autoridad": "Brussels Airport",
        "pais": "BE",
        "categoria": categoria_niega,
        "afirma": "niega_incidente",
        "frase": AEROPUERTO,
    }
    return [
        (confirma, declaraciones.fuente(confirma, noticia, 1)),
        (niega, declaraciones.fuente(niega, noticia, 2)),
    ]


def test_quien_es_competente_y_quien_cede() -> None:
    assert competencia.es_competente("Skeyes")
    assert competencia.es_competente("Københavns Politi")
    assert competencia.es_competente("Polisen i Stockholm")
    assert competencia.es_competente("UK Airprox Board")
    assert competencia.cede("Brussels Airport")
    assert competencia.cede("Københavns Lufthavn")
    # La policía del aeropuerto es policía: no cede.
    assert not competencia.cede("Airport Police")
    # Las siglas, palabra entera y en mayúsculas: «Bearn» no es la BEA.
    assert not competencia.es_competente("Bearn")
    assert competencia.es_competente("BEA")
    # La categoría de una declaración nueva manda sobre el nombre.
    assert competencia.cede("Lo que sea", "aeropuerto")
    assert not competencia.cede("Brussels Airport", "gobierno")
    assert (
        competencia.autoridad({"medio": "Skeyes (declaración oficial citada en brf.be)"})
        == "Skeyes"
    )


def test_el_aeropuerto_no_desmiente_lo_que_confirma_el_control_aereo() -> None:
    resultado = declaraciones.aplicar_fuentes(_bruselas(), _pares(_noticia()))
    assert resultado["estado"]["actual"] == "confirmado"
    pasos = resultado["estado"]["historial"]
    assert [p["estado"] for p in pasos] == ["notificado", "confirmado", "desmentido", "confirmado"]
    # La negación queda con su fecha y su fuente; el paso que la sigue, con el motivo.
    assert pasos[2]["fuente_id"].endswith("-declaracion-2")
    assert pasos[3]["fuente_id"].endswith("-declaracion-1")
    assert "Skeyes" in pasos[3]["motivo"]["es"] and "Brussels Airport" in pasos[3]["motivo"]["en"]
    assert "motivo_desmentido" not in resultado["control"]
    fuentes = {f["id"]: f for f in resultado["fuentes"]}
    assert errores_historial(resultado["estado"], fuentes) == []

    # Otra noticia que repite lo del aeropuerto no añade pasos.
    otra = _noticia("https://vrt.be/vrtnws/nl/2026/09/12/drone", "gdelt-0ceea3108039ea74")
    resultado["fuentes"].append(otra)
    _, niega = _pares(otra)[1]
    despues = declaraciones.aplicar_fuentes(resultado, [_pares(otra)[1]])
    assert niega["id"] in {f["id"] for f in despues["fuentes"]}
    assert despues["estado"] == resultado["estado"]


def test_si_lo_niega_la_competente_el_desmentido_vale() -> None:
    noticia = _noticia()
    confirma = {
        "autoridad": "Brussels Airport",
        "pais": "BE",
        "categoria": "aeropuerto",
        "afirma": "incidente",
        "frase": AEROPUERTO,
    }
    niega = {
        "autoridad": "Skeyes",
        "pais": "BE",
        "categoria": "navegacion_aerea",
        "afirma": "niega_incidente",
        "frase": SKEYES,
    }
    pares = [
        (confirma, declaraciones.fuente(confirma, noticia, 1)),
        (niega, declaraciones.fuente(niega, noticia, 2)),
    ]
    resultado = declaraciones.aplicar_fuentes(_bruselas(), pares)
    assert resultado["estado"]["actual"] == "desmentido"
    # Y un gobierno que niega no es un aeropuerto: el desmentido de siempre.
    gobierno = declaraciones.aplicar_fuentes(
        _bruselas(), _pares(_noticia(), categoria_niega="gobierno")
    )
    assert gobierno["estado"]["actual"] == "desmentido"


def _bruselas_desmentido() -> dict[str, Any]:
    """Como quedó EODI-2026-00293 antes de la regla: confirmado por skeyes y desmentido después
    por el aeropuerto, en la misma noticia."""
    documento = _bruselas()
    noticia = documento["fuentes"][0]
    for declaracion, fuente in _pares(noticia):
        documento["fuentes"].append(fuente)
        estado = "confirmado" if declaracion["afirma"] == "incidente" else "desmentido"
        documento["estado"]["historial"].append(
            {"estado": estado, "fecha": noticia["fecha"], "fuente_id": fuente["id"]}
        )
    documento["estado"]["actual"] = "desmentido"
    documento["control"]["motivo_desmentido"] = f"Brussels Airport: «{AEROPUERTO}»"
    documento["presencia_dron"] = "confirmada"
    return documento


def test_la_correccion_revisada_lo_deja_confirmado_con_el_desmentido_en_el_historial() -> None:
    revision = next(t for t in revisados.cargar()["titulares"] if t["incidente"] == ID)
    assert revision["estado"]["valor"] == "confirmado"
    assert revision["estado"]["cita"] == SKEYES
    instante = ejemplos.instante("2026-10-16T09:00Z")
    nuevo = revisados.con_titular(_bruselas_desmentido(), revision, instante)
    pasos = nuevo["estado"]["historial"]
    assert nuevo["estado"]["actual"] == "confirmado"
    assert [p["estado"] for p in pasos] == ["notificado", "confirmado", "desmentido", "confirmado"]
    assert pasos[-1]["motivo"] == revision["estado"]["motivo"]
    assert "skeyes" in pasos[-1]["motivo"]["es"]
    assert "motivo_desmentido" not in nuevo["control"]
    assert errores_historial(nuevo["estado"], {f["id"]: f for f in nuevo["fuentes"]}) == []
    # Ya aplicada, no cambia nada.
    assert revisados.con_titular(nuevo, revision, instante)["estado"] == nuevo["estado"]


def test_una_recogida_posterior_no_lo_deshace() -> None:
    almacen = Almacen.abrir()
    documento = _bruselas_desmentido()
    documento["titulo"] = {
        "es": "Dron sobre el aeropuerto de Bruselas, en Bélgica",
        "en": "Drone over Brussels Airport, Belgium",
    }
    almacen.guardar_incidente(documento, AHORA, VOCABULARIO_MODELOS)
    revisados.corregir(almacen, AHORA, VOCABULARIO_MODELOS)
    guardado = almacen.incidente(ID)
    assert guardado is not None and guardado["estado"]["actual"] == "confirmado"
    # La pasada siguiente no cambia nada.
    revisados.corregir(almacen, AHORA, VOCABULARIO_MODELOS)
    assert almacen.incidente(ID)["estado"] == guardado["estado"]  # type: ignore[index]
    # Y una noticia nueva que vuelve a citar al aeropuerto tampoco lo desmiente.
    otra = _noticia("https://lavenir.net/actu/belgique/2026/09/13/drone", "gdelt-c6edf408dea4408a")
    con_otra = copy.deepcopy(guardado)
    con_otra["fuentes"].append(otra)
    despues = declaraciones.aplicar_fuentes(con_otra, [_pares(otra)[1]])
    assert despues["estado"] == guardado["estado"]
