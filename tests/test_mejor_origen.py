"""Origen valor a valor (exportacion/mejor_origen.py) y lectura de frases (proceso/textos_dron.py):
registro, cierre medido, registro oficial, hora de una autoridad, fecha por el tráfico aéreo,
número de drones y patrón de vuelo. Sin red."""

import copy
from typing import Any

import pytest

from almacen.base import Almacen
from esquema import Esquema, validador
from exportacion import mejor_origen
from exportacion import procedencia as origenes
from proceso import textos_dron
from tests import ejemplos
from tests.ejemplos import AHORA, VOCABULARIO_MODELOS


def exportar(documento: dict[str, Any], contexto: mejor_origen.Contexto | None = None) -> Any:
    almacen = Almacen.abrir()
    almacen.guardar_incidente(documento, AHORA, VOCABULARIO_MODELOS)
    exportado = origenes.exportar_incidente(documento, origenes.Fichas.de(almacen), contexto)
    assert validador(Esquema.INCIDENTE).is_valid(exportado)
    return exportado


def copenhague(**cambios: Any) -> dict[str, Any]:
    """Incidente de prensa en el aeropuerto de Copenhague (instalación del nomenclátor)."""
    documento = ejemplos.incidente_minimo()
    documento["id"] = "EODI-2025-00154"
    documento["fuentes"] = [ejemplos.fuente("F1", "C")]
    documento["tiempo"] = {"inicio": ejemplos.instante("2025-09-22T18:00Z", "hora"),
                           "origen_inicio": {"tipo": "explicita"}}  # fmt: skip
    documento["lugar"] = {"punto": {"lat": 55.618, "lon": 12.656}, "radio_km": 5.0, "pais": "DK",
                          "nivel": "instalacion", "geocodificacion": "nomenclator"}  # fmt: skip
    documento["objetivo"] = {"categoria": "aeropuerto", "nombre": "Københavns Lufthavn, Kastrup",
                             "oaci": "EKCH"}  # fmt: skip
    documento.update(cambios)
    return documento


# --- Registro --------------------------------------------------------------------------


def test_la_instalacion_del_nomenclator_tiene_origen_registro() -> None:
    documento = copenhague()
    if mejor_origen.instalacion_de(documento) is None:
        nombre = next(
            n for n, lista in mejor_origen.registro().items()
            if any(i.oaci == "EKCH" for i in lista)
        )  # fmt: skip
        documento["objetivo"]["nombre"] = nombre
    exportado = exportar(documento)
    for ruta in ("objetivo.categoria", "objetivo.nombre", "objetivo.oaci", "lugar.pais"):
        assert exportado["procedencia"][ruta]["origen"] == "registro", ruta
        assert exportado["procedencia"][ruta]["registro"]["nombre"] == "OpenStreetMap"
    # Un objetivo que no está en el registro sigue con el origen de sus fuentes.
    otro = copenhague(objetivo={"categoria": "otra", "nombre": "Un sitio sin registro"})
    assert exportar(otro)["procedencia"].get("objetivo.nombre", {}).get("origen") != "registro"


# --- Hora y duración --------------------------------------------------------------------


def con_cierre(documento: dict[str, Any], nivel: str = "alta") -> dict[str, Any]:
    resultado = copy.deepcopy(documento)
    medido = ejemplos.trafico_aereo()
    medido["cierre"]["cobertura"]["nivel"] = nivel
    resultado["trafico_aereo"] = medido
    return resultado


def test_el_cierre_medido_da_hora_y_duracion_de_origen_medido() -> None:
    documento = con_cierre(copenhague())
    cierre = documento["trafico_aereo"]["cierre"]
    exportado = exportar(documento)
    assert exportado["tiempo"]["inicio"] == cierre["inicio"]
    assert exportado["tiempo"]["duracion_min"] == cierre["duracion_min"]
    procedencia = exportado["procedencia"]["tiempo.inicio"]
    assert procedencia["origen"] == "medido" and procedencia["regla"]["nombre"] == "cierre_medido"
    assert procedencia["sustituye"] == {
        "valor": copenhague()["tiempo"]["inicio"],
        "origen": "prensa",
    }
    assert exportado["tiempo"]["origen_inicio"]["tipo"] == "medido"
    # Con cobertura baja no se usa.
    assert exportar(con_cierre(copenhague(), "insuficiente"))["procedencia"]["tiempo.inicio"][
        "origen"] == "prensa"  # fmt: skip


def test_el_registro_oficial_da_la_hora_oficial() -> None:
    documento = copenhague()
    documento["detalle_oficial"] = {"inicio": ejemplos.instante("2025-09-22T18:26Z")}
    documento["fuentes"].append({**ejemplos.fuente("ukab-1", "A", es_autoridad=True),
                                 "campos_respaldados": ["detalle_oficial.inicio"]})  # fmt: skip
    exportado = exportar(documento)
    assert exportado["tiempo"]["inicio"]["valor"] == "2025-09-22T18:26Z"
    assert exportado["procedencia"]["tiempo.inicio"]["origen"] == "oficial"


def test_la_hora_que_escribe_una_autoridad_en_su_dia() -> None:
    documento = copenhague()
    documento["lugar"] = {"punto": {"lat": 47.0105, "lon": 28.8638}, "radio_km": 10.0, "pais": "MD"}
    documento["objetivo"] = {"categoria": "otra"}
    documento["tiempo"] = {"inicio": ejemplos.instante("2025-08-20T00:00Z", "dia"),
                           "origen_inicio": {"tipo": "explicita"}}  # fmt: skip
    declaracion = {**ejemplos.fuente("F1-declaracion-1", "B", es_autoridad=True), "idioma": "ro",
                   "frase_origen": "Potrivit Ministerului Apărării de la Chișinău, drona a fost "
                                   "detectată miercuri, 20 august, la ora 3.16."}  # fmt: skip
    documento["fuentes"].append(declaracion)
    exportado = exportar(documento)
    # 03:16 en Chișinău en verano es 00:16 UTC.
    assert exportado["tiempo"]["inicio"] == {"precision": "minuto", "valor": "2025-08-20T00:16Z"}
    assert exportado["procedencia"]["tiempo.inicio"]["origen"] == "oficial_citado"


def test_con_la_fecha_de_publicacion_la_unica_interrupcion_medida_da_la_fecha() -> None:
    documento = copenhague()
    documento["tiempo"] = {"inicio": ejemplos.instante("2025-09-23T08:00Z", "aproximada"),
                           "origen_inicio": {"tipo": "publicacion"}}  # fmt: skip
    anomalia = ejemplos.anomalia()
    exportado = exportar(documento, mejor_origen.Contexto(anomalias=[anomalia]))
    assert exportado["tiempo"]["inicio"] == {"precision": "minuto", "valor": anomalia["inicio"]}
    assert exportado["procedencia"]["tiempo.inicio"]["regla"]["nombre"] == "fecha_medida"
    assert exportado["indicadores"]["fecha_del_suceso_verificada"]
    # Con dos interrupciones no se sabe cuál: no se elige.
    otra = {**anomalia, "inicio": "2025-09-22T09:00Z"}
    exportado = exportar(documento, mejor_origen.Contexto(anomalias=[anomalia, otra]))
    assert exportado["procedencia"]["tiempo.inicio"]["origen"] == "prensa"


# --- Número de drones y patrón ---------------------------------------------------------


def test_el_numero_de_una_autoridad_sustituye_al_de_la_prensa() -> None:
    documento = copenhague()
    documento["drones"] = {"numero": {"min": 2, "max": 10}}
    documento["afirmaciones"] = [{"campo": "drones", "valor": {"min": 2, "max": 10},
                                  "fuente_id": "F1", "confianza_extraccion": 0.9,
                                  "credibilidad": 3}]  # fmt: skip
    declaracion = {**ejemplos.fuente("F1-declaracion-1", "B", es_autoridad=True),
                   "frase_origen": "Lufthavnen er pt. lukket ned, og det er grundet to til tre "
                                   "droner, som flyver omkring lufthavnsområdet"}  # fmt: skip
    documento["fuentes"].append(declaracion)
    exportado = exportar(documento)
    assert exportado["drones"]["numero"] == {"min": 2, "max": 3}
    procedencia = exportado["procedencia"]["drones.numero"]
    assert procedencia["origen"] == "oficial_citado"
    assert procedencia["sustituye"]["valor"] == {"min": 2, "max": 10}
    assert exportado["drones"]["patron"] == "merodeo"
    assert exportado["procedencia"]["drones.patron"]["origen"] == "oficial_citado"


def test_lo_que_solo_dice_la_prensa_sigue_siendo_prensa() -> None:
    documento = copenhague()
    documento["fuentes"] = [{**ejemplos.fuente("F1", "C"),
                             "frase_origen": "Three drones hovered over the runway"}]  # fmt: skip
    exportado = exportar(documento)
    assert exportado["drones"]["patron"] == "hover"
    assert exportado["procedencia"]["drones.patron"]["origen"] == "prensa"


@pytest.mark.parametrize(
    ("frase", "idioma", "esperado"),
    [
        ("og det er grundet to til tre droner", "da", (2, 3)),
        ("Bis zu fünf Drohnen wurden gesichtet", "de", (1, 5)),
        ("Gisteravond zijn 4 drones gezien", "nl", (4, 4)),
        ("două drone au survolat spațiul aerian", "ro", (2, 2)),
        ("flights were suspended due to drones", "en", None),
        ("omtaler det nu som et droneangreb", "da", None),
        ("drie keer drones boven twee luchthavens", "nl", None),
        ("at det ikke var en drone fra Niras", "da", None),
        ("O nouă dronă a intrat în spațiul aerian", "ro", None),
        ("two drone intrusions were detected", "en", None),
    ],
)
def test_numero_de_drones_en_una_frase(frase: str, idioma: str, esperado: Any) -> None:
    assert textos_dron.numero_drones(frase, idioma) == esperado


@pytest.mark.parametrize(
    ("frase", "esperado"),
    [
        ("în jurul orei locale 20:00, o dronă a fost observată", (20, 0)),
        ("Kl. 20.15 blev der observeret droner", (20, 15)),
        ("The two drones were seen at about 10 p.m.", (22, 0)),
        ("the airport reopened at 23:00 after drones", None),
        ("Version 2.5 drone with 3.14 m wingspan", None),
        ("2 drones at 08:15 and 09:30", None),
    ],
)
def test_hora_local_en_una_frase(frase: str, esperado: Any) -> None:
    assert textos_dron.hora_local(frase) == esperado


def test_pais_de_entrada_y_patron() -> None:
    assert textos_dron.pais_de_entrada("the drone entered from neighbouring Belarus", "LT") == "BY"
    assert textos_dron.pais_de_entrada("drona a intrat din Federatia Rusa", "RO") == "RU"
    assert textos_dron.pais_de_entrada("drones over the base", "LT") is None
    assert textos_dron.patron("a swarm of drones over the port") == "enjambre"
    assert textos_dron.patron("the drone crossed into Polish airspace") == "transito"
    assert textos_dron.patron("aircraft circled the airport") is None


def test_con_la_fecha_de_publicacion_un_documento_oficial_del_sitio_da_la_fecha() -> None:
    documento = copenhague()
    documento["tiempo"] = {"inicio": ejemplos.instante("2025-09-23T08:00Z", "aproximada"),
                           "origen_inicio": {"tipo": "publicacion"}}  # fmt: skip
    datos: dict[str, Any] = {"inicio": {"valor": "2025-09-22T18:30", "confianza": 0.9},
                             "inicio_precision": {"valor": "minuto", "confianza": 0.9}}  # fmt: skip
    suceso: dict[str, Any] = {"cruce": "sin_incidente", "datos": datos,
                              "punto": {"lat": 55.62, "lon": 12.65, "radio_km": 3.0}}  # fmt: skip
    contexto = mejor_origen.Contexto(sucesos_sin_incidente=[("politi:1", suceso)])
    exportado = exportar(documento, contexto)
    assert exportado["tiempo"]["inicio"] == {"valor": "2025-09-22T18:30Z", "precision": "minuto"}
    assert exportado["procedencia"]["tiempo.inicio"]["origen"] == "oficial"
    assert exportado["procedencia"]["tiempo.inicio"]["fuentes"] == ["politi:1"]
    # Un suceso de otro sitio o de un mes antes no cuenta.
    lejos = {**suceso, "punto": {"lat": 56.2, "lon": 10.6, "radio_km": 3.0}}
    antes = {**datos, "inicio": {"valor": "2025-08-01T18:30", "confianza": 0.9}}
    viejo = {**suceso, "datos": antes}
    for otro in (lejos, viejo):
        contexto = mejor_origen.Contexto(sucesos_sin_incidente=[("politi:2", otro)])
        assert exportar(documento, contexto)["procedencia"]["tiempo.inicio"]["origen"] == "prensa"
