"""Revisión del contenido hecha a mano (recogida/revisados.corregir; docs/
informe_revision_contenido.md): retiradas, citas, titulares con su presencia y su estado, y el
lugar que da la autoridad. Todo con su motivo y sin repetir nada en la recogida siguiente."""

import copy
from typing import Any

import pytest

from almacen.base import Almacen
from proceso import cita_titular
from proceso.estados import errores_historial
from recogida import revisados
from tests import ejemplos
from tests.ejemplos import AHORA, VOCABULARIO_MODELOS

ID = "EODI-2025-00140"


def _arna() -> dict[str, Any]:
    """Como EODI-2025-00140: confirmado por una declaración de la policía que no vio drones, con
    el país equivocado y una cita que no nombra el lugar."""
    documento = ejemplos.incidente_minimo()
    documento["id"] = ID
    documento["titulo"] = {"es": "Múltiples avistamientos de drones sobre Arna, Suecia",
                           "en": "Multiple drone sightings over Arna, Sweden"}  # fmt: skip
    documento["lugar"] = {"pais": "SE", "nivel": "region", "region": "Hordaland"}
    documento["fuentes"][0]["frase_origen"] = (
        "Ifølge stasjonssjefen skal det dreie seg om flere store droner."
    )
    declaracion = {**copy.deepcopy(documento["fuentes"][0]), "id": "F1-declaracion-1",
                   "es_autoridad": True, "fiabilidad": "B",
                   "frase_origen": "Politiet har mottatt tips."}  # fmt: skip
    documento["fuentes"].append(declaracion)
    documento["estado"] = {
        "actual": "confirmado",
        "historial": [
            *documento["estado"]["historial"],
            {"estado": "confirmado", "fecha": ejemplos.instante("2025-11-04T19:30Z"),
             "fuente_id": "F1-declaracion-1"},
        ],
    }  # fmt: skip
    documento["presencia_dron"] = "confirmada"
    return documento


NO_VIO = "Politiet var i området en halvtime senere, men observerte ingen droner"
TIPS = (
    "Politiet har de siste dagene mottatt en rekke tips fra folk i Arna som har observert "
    "omfattende droneaktivitet."
)
REVISION: dict[str, Any] = {
    "citas": [
        {"incidente": ID, "enlace": "https://www.ba.no/arna", "medio": "ba.no",
         "fecha": "2025-02-12", "idioma": "no", "frase": TIPS,
         "comprobada": {"fecha": "2026-10-05", "en": "https://www.ba.no/arna"}},
        {"incidente": ID, "enlace": "https://www.ba.no/arna", "medio": "ba.no",
         "fecha": "2025-02-12", "idioma": "no", "frase": NO_VIO,
         "comprobada": {"fecha": "2026-10-05", "en": "https://www.ba.no/arna"}},
    ],
    "titulares": [{
        "incidente": ID,
        "titulo": {"es": "Vecinos avisan a la policía de varios avistamientos de drones sobre "
                         "Arna, en Noruega",
                   "en": "Residents report several drone sightings over Arna, Norway, to police"},
        "presencia": {"valor": "no_confirmada", "cita": NO_VIO},
        "estado": {"valor": "notificado", "cita": NO_VIO,
                   "motivo": {"es": "La policía acudió y no vio ningún dron.",
                              "en": "Police went to the area and saw no drones."}},
        "lugar": {"pais": "NO", "region": "Vestland", "localidad": "Arna", "nivel": "localidad"},
        "motivo": {"es": "Arna está en Noruega y la policía no vio drones.",
                   "en": "Arna is in Norway and police saw no drones."},
    }],
    "retirar": [{"incidente": "EODI-2025-00065",
                 "motivo": {"es": "Es una estadística, no un suceso.",
                            "en": "It is a statistic, not an event."}}],
    "ubicaciones": [],
}  # fmt: skip


@pytest.fixture
def revision(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    datos = copy.deepcopy(REVISION)
    monkeypatch.setattr(revisados, "cargar", lambda: datos)
    return datos


def test_cita_titular_presencia_estado_y_lugar(revision: dict[str, Any]) -> None:
    almacen = Almacen.abrir()
    almacen.guardar_incidente(_arna(), AHORA, VOCABULARIO_MODELOS)
    antes = almacen.incidente(ID)
    assert antes is not None and not cita_titular.respalda(antes)
    hechos = revisados.corregir(almacen, AHORA, VOCABULARIO_MODELOS)
    assert hechos.citas == [ID] and hechos.titulares == [ID] and not hechos.sin_guardar
    despues = almacen.incidente(ID)
    assert despues is not None
    assert despues["titulo"]["es"].endswith("Arna, en Noruega")
    assert despues["lugar"]["pais"] == "NO" and despues["lugar"]["localidad"] == "Arna"
    assert despues["presencia_dron"] == "no_confirmada"
    # La confirmación se retira con su motivo, en un paso nuevo; lo anterior no se toca.
    pasos = despues["estado"]["historial"]
    assert [p["estado"] for p in pasos] == ["notificado", "confirmado", "notificado"]
    assert pasos[-1]["motivo"]["en"] and errores_historial(despues["estado"], {}) == []
    assert cita_titular.respalda(despues)
    # La recogida siguiente no cambia nada.
    hechos = revisados.corregir(almacen, AHORA, VOCABULARIO_MODELOS)
    assert hechos.citas == hechos.titulares == []
    assert almacen.incidente(ID) == despues


def test_la_palabra_de_una_autoridad_confirma_con_las_reglas_de_siempre(
    revision: dict[str, Any],
) -> None:
    documento = ejemplos.incidente_minimo()
    documento["presencia_dron"] = "no_confirmada"
    almacen = Almacen.abrir()
    almacen.guardar_incidente(documento, AHORA, VOCABULARIO_MODELOS)
    revision["titulares"] = []
    revision["citas"] = [{
        "incidente": documento["id"], "enlace": "https://ejemplo.org/policia",
        "medio": "ejemplo.org", "fecha": "2025-11-05", "idioma": "nl",
        "frase": "De politie heeft een drone in beslag genomen.",
        "comprobada": {"fecha": "2026-10-05", "en": "https://ejemplo.org/policia"},
        "declaracion": {"autoridad": "Politie", "pais": "BE", "categoria": "policia",
                        "afirma": "drones"},
    }]  # fmt: skip
    revisados.corregir(almacen, AHORA, VOCABULARIO_MODELOS)
    despues = almacen.incidente(documento["id"])
    assert despues is not None
    assert despues["estado"]["actual"] == "confirmado"
    assert despues["presencia_dron"] == "confirmada"
    citada = next(f for f in despues["fuentes"] if f["id"].startswith(revisados.PREFIJO_REVISADA))
    assert citada["id"].endswith("-declaracion-1") and citada["es_autoridad"]


def test_retirar_con_motivo_en_los_dos_idiomas(revision: dict[str, Any]) -> None:
    documento = ejemplos.incidente_minimo()
    documento["id"] = "EODI-2025-00065"
    almacen = Almacen.abrir()
    almacen.guardar_incidente(documento, AHORA, VOCABULARIO_MODELOS)
    hechos = revisados.corregir(almacen, AHORA, VOCABULARIO_MODELOS)
    assert hechos.retirados == ["EODI-2025-00065"]
    retirado = almacen.incidente("EODI-2025-00065")
    assert retirado is not None
    assert retirado["retirado"]["motivo"] == "Es una estadística, no un suceso."
    assert retirado["retirado"]["motivo_en"] == "It is a statistic, not an event."
    assert revisados.corregir(almacen, AHORA, VOCABULARIO_MODELOS).retirados == []


def _polonia() -> dict[str, Any]:
    documento = ejemplos.incidente_minimo()
    documento["id"] = "EODI-2025-00295"
    documento["lugar"] = {"pais": "PL", "nivel": "pais"}
    documento["fuentes"][0]["frase_origen"] = "Drony naruszyły polską przestrzeń powietrzną."
    return documento


UBICACION: dict[str, Any] = {
    "incidente": "EODI-2025-00295",
    "lugar": {"nombre": "Wyryki-Wola", "nivel": "localidad", "lat": 51.5625, "lon": 23.36389,
              "radio_km": 2, "region": "Lubelskie"},
    "otros_lugares": [{"nombre": "Cześniki", "lat": 50.705, "lon": 23.44111},
                      {"nombre": "Smyków"}],
    "fuente": {"incidente": "EODI-2025-00295", "enlace": "https://www.gov.pl/web/po-lublin/x",
               "medio": "gov.pl", "fecha": "2025-09-11", "idioma": "pl", "oficial": True,
               "frase": "uderzyła w dach budynku mieszkalnego w miejscowości Wyryki Wola.",
               "comprobada": {"fecha": "2026-10-05", "en": "https://www.gov.pl/web/po-lublin/x"},
               "declaracion": {"autoridad": "Prokuratura Okręgowa w Lublinie", "pais": "PL",
                               "categoria": "fiscalia", "afirma": "incidente"}},
}  # fmt: skip


def test_el_lugar_que_da_la_autoridad(revision: dict[str, Any]) -> None:
    almacen = Almacen.abrir()
    almacen.guardar_incidente(_polonia(), AHORA, VOCABULARIO_MODELOS)
    revision["citas"], revision["titulares"] = [], []
    revision["ubicaciones"] = [UBICACION]
    assert revisados.corregir(almacen, AHORA, VOCABULARIO_MODELOS).ubicados == ["EODI-2025-00295"]
    lugar = almacen.incidente("EODI-2025-00295")["lugar"]  # type: ignore[index]
    assert lugar["punto"] == {"lat": 51.5625, "lon": 23.36389} and lugar["radio_km"] == 2
    assert lugar["geocodificacion"] == "oficial" and lugar["localidad"] == "Wyryki-Wola"
    assert [o["nombre"] for o in lugar["otros_lugares"]] == ["Cześniki", "Smyków"]
    fuente = next(
        f
        for f in almacen.incidente("EODI-2025-00295")["fuentes"]  # type: ignore[index]
        if f["id"] == lugar["fuente_punto"]
    )
    assert fuente["fiabilidad"] == "A" and fuente["metodo"] == "parser"
    assert revisados.corregir(almacen, AHORA, VOCABULARIO_MODELOS).ubicados == []


def test_un_punto_fuera_del_pais_no_se_pone(revision: dict[str, Any]) -> None:
    almacen = Almacen.abrir()
    almacen.guardar_incidente(_polonia(), AHORA, VOCABULARIO_MODELOS)
    revision["citas"], revision["titulares"] = [], []
    fuera = copy.deepcopy(UBICACION)
    fuera["lugar"].update(lat=47.0, lon=28.8)  # Moldavia
    revision["ubicaciones"] = [fuera]
    assert revisados.corregir(almacen, AHORA, VOCABULARIO_MODELOS).ubicados == []
    assert "punto" not in almacen.incidente("EODI-2025-00295")["lugar"]  # type: ignore[index]


def test_la_configuracion_de_la_revision() -> None:
    datos = revisados.cargar()
    for cita in datos["citas"]:
        assert len(cita["frase"].split()) <= 25
        assert cita["comprobada"]["fecha"] == "2026-10-05"
    for retirada in datos["retirar"]:
        assert retirada["motivo"]["es"] and retirada["motivo"]["en"]
    for revision in datos["titulares"]:
        assert revision["motivo"]["es"] and revision["motivo"]["en"]
        if "titulo" in revision:
            assert revision["titulo"]["es"] and revision["titulo"]["en"]
    for ubicacion in datos["ubicaciones"]:
        assert 0.1 <= ubicacion["lugar"]["radio_km"] <= 50
        assert len(ubicacion["fuente"]["frase"].split()) <= 25
