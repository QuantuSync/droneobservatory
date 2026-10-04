"""Tipo de actor y país de una atribución (proceso/atribucion.py), en la extracción, en la
validación y en la corrección de lo guardado (recogida/tipo_atribucion.py).

Las frases de los casos guardados son las de las declaraciones reales de la base: Chisináu
(noviembre de 2025 y septiembre de 2026), Leipzig, la base aérea de septiembre de 2026 y el
aeropuerto rumano del 8 de septiembre de 2026, donde el autor guardado era el propio prefecto.
"""

import copy
import json
from datetime import UTC, datetime, timedelta

import pytest

from almacen.base import Almacen
from esquema import Documento
from modelo import ficha
from proceso import atribucion
from proceso.validaciones import validar_incidente
from recogida import tipo_atribucion
from tests import ejemplos
from tests.test_declaraciones import aplicar, declaracion
from tests.test_extraccion import AHORA, MODELOS

# Después de las fechas del ejemplo completo (octubre de 2025).
DESPUES = datetime(2026, 10, 4, 12, tzinfo=UTC)
CONFIRMA = ("drones", "Vi kan bekræfte, at der i aften er observeret droner")


# --- La regla ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("autor", "frase"),
    [
        ("Rusia", "Prezydent Maia Sandu oskarżyła Moskwę o próbę destabilizacji."),
        ("Rusia", "Молдавские власти сразу назвали аппарат «российским»"),
        ("Russland", "die Bundesregierung von einem russischen Anschlagsversuch ausging"),
        ("Russland", "правительство Германии приходит к выводу, что Россия несет ответственность"),
    ],
)
def test_las_atribuciones_guardadas_a_rusia_son_de_un_estado(autor: str, frase: str) -> None:
    assert atribucion.clasificar(autor, frase) == {"tipo": "estado", "pais": "RU"}


def test_el_nombre_de_quien_habla_no_es_un_autor() -> None:
    # La frase del prefecto solo dice por dónde entró el dron: no atribuye a nadie.
    frase = "The drone entered Romanian territory from the Republic of Moldova"
    assert atribucion.clasificar("Constantin Dolachi-Pelin", frase) is None
    assert atribucion.clasificar("Constantin Dolachi-Pelin", frase, "persona", "RO") is None


def test_un_estado_que_la_frase_no_nombra_no_se_atribuye() -> None:
    assert atribucion.clasificar("Rusia", "El dron llegó desde Ucrania", "estado", "RU") is None


def test_el_pais_del_estado_sale_del_autor_y_no_del_extractor() -> None:
    frase = "Berlin accuse Moscou d'avoir envoyé des drones"
    assert atribucion.clasificar("Rusia", frase, "estado", "BY") == {"tipo": "estado", "pais": "RU"}


def test_la_nacionalidad_de_una_persona_solo_si_la_frase_la_dice() -> None:
    dice = "La Fiscalía acusa a Ion Popescu, ciudadano ruso, de pilotar el dron"
    assert atribucion.clasificar("Ion Popescu", dice, "persona", "RU") == {
        "tipo": "persona", "pais": "RU",
    }  # fmt: skip
    # Un país nombrado como lugar no es una nacionalidad.
    lugar = "La Fiscalía acusa a Ion Popescu, llegado desde Rusia, de pilotar el dron"
    assert atribucion.clasificar("Ion Popescu", lugar, "persona", "RU") == {"tipo": "persona"}
    # Ni el nombre ni el idioma dan la nacionalidad.
    nada = "Politia l-a retinut pe Ion Popescu pentru zborul dronei"
    assert atribucion.clasificar("Ion Popescu", nada, "persona", "RO") == {"tipo": "persona"}


def test_un_tipo_vacio_no_da_atribucion() -> None:
    assert atribucion.clasificar("Rusia", "Rusia es responsable", "") is None


def test_palabra_entera() -> None:
    assert atribucion.menciona("un cetățean rus", "RU", solo_gentilicio=True)
    assert not atribucion.menciona("rustic drone", "RU")


def test_la_tabla_cubre_las_banderas_de_la_web() -> None:
    europeos = {
        "AD", "AL", "AT", "BA", "BE", "BG", "CH", "CY", "CZ", "DE", "DK", "EE", "ES", "FI", "FR",
        "GB", "GR", "HR", "HU", "IE", "IS", "IT", "LI", "LT", "LU", "LV", "MC", "MD", "ME", "MK",
        "MT", "NL", "NO", "PL", "PT", "RO", "RS", "SE", "SI", "SK", "SM", "XK",
    }  # fmt: skip
    assert atribucion.paises() == europeos | {"RU", "BY", "UA", "TR", "VA", "IR"}


# --- La extracción ----------------------------------------------------------------------


def test_la_ficha_pide_tipo_y_pais_del_autor() -> None:
    declaraciones = ficha.ESQUEMA["properties"]["declaraciones"]["items"]
    assert {"autor_tipo", "autor_pais"} <= set(declaraciones["required"])
    assert declaraciones["properties"]["autor_tipo"]["enum"] == ["estado", "persona", ""]
    assert "nunca la deduzcas del nombre" in ficha.INSTRUCCIONES


def test_una_autoria_a_un_estado_lleva_tipo_y_pais() -> None:
    gobierno = declaracion(
        "autoria", "To była prowokacja rosyjskich dronów", "gobierno",
        autoridad="Premier RP", autor="Rusia", autor_tipo="estado", autor_pais="RU",
    )  # fmt: skip
    resultado = aplicar(declaracion(*CONFIRMA), gobierno)
    assert resultado["estado"]["actual"] == "atribuido"
    assert resultado["atribucion"]["tipo"] == "estado"
    assert resultado["atribucion"]["pais"] == "RU"


def test_una_autoria_a_una_persona_sin_nacionalidad_dicha_queda_sin_pais() -> None:
    gobierno = declaracion(
        "autoria", "El Gobierno señala a Ion Popescu como autor del vuelo", "gobierno",
        autoridad="Gobierno", autor="Ion Popescu", autor_tipo="persona", autor_pais="RO",
    )  # fmt: skip
    resultado = aplicar(declaracion(*CONFIRMA), gobierno)
    assert resultado["estado"]["actual"] == "atribuido"
    assert resultado["atribucion"]["tipo"] == "persona"
    assert "pais" not in resultado["atribucion"]


def test_una_autoria_que_la_frase_no_sostiene_deja_el_incidente_confirmado() -> None:
    prefecto = declaracion(
        "autoria", "The drone entered Romanian territory from the Republic of Moldova",
        "gobierno", autoridad="Prefect", autor="Constantin Dolachi-Pelin",
    )  # fmt: skip
    resultado = aplicar(declaracion(*CONFIRMA), prefecto)
    assert resultado["estado"]["actual"] == "confirmado"
    assert "atribucion" not in resultado


# --- La validación ----------------------------------------------------------------------


def _errores(documento: Documento) -> list[str]:
    errores = validar_incidente(documento, AHORA, MODELOS)
    return [e.mensaje for e in errores if e.ruta == "atribucion"]


def test_la_validacion_exige_el_tipo() -> None:
    documento = ejemplos.incidente_completo()
    del documento["atribucion"]["tipo"]
    assert _errores(documento) == ["atribución sin tipo de actor (estado o persona)"]


def test_la_validacion_rechaza_un_pais_que_la_frase_no_dice() -> None:
    documento = ejemplos.incidente_completo()
    documento["atribucion"]["pais"] = "BY"
    assert len(_errores(documento)) == 1


def test_la_validacion_rechaza_una_nacionalidad_deducida() -> None:
    documento = ejemplos.incidente_completo()
    autoridad = next(f for f in documento["fuentes"] if f["id"] == "F2")
    autoridad["frase_origen"] = "El Gobierno atribuye a Ion Popescu el vuelo sobre el aeropuerto"
    documento["atribucion"] = {**documento["atribucion"], "actor": "Ion Popescu",
                               "tipo": "persona", "pais": "RO"}  # fmt: skip
    assert len(_errores(documento)) == 1
    del documento["atribucion"]["pais"]
    assert _errores(documento) == []


# --- La corrección de lo guardado -------------------------------------------------------


def _guardado(actor: str, frase: str) -> Documento:
    """Un atribuido como los de antes del esquema 1.10.0: sin tipo ni país."""
    documento = ejemplos.incidente_completo()
    autoridad = next(f for f in documento["fuentes"] if f["id"] == "F2")
    autoridad["frase_origen"] = frase
    documento["atribucion"] = {"actor": actor, "autoridad": "Gobierno",
                               "fecha": documento["atribucion"]["fecha"]}  # fmt: skip
    return documento


def _guardar_sin_validar(almacen: Almacen, documento: Documento) -> None:
    with almacen.conexion:
        almacen.conexion.execute(
            "INSERT INTO incidentes (id, tipo, estado, documento) VALUES (?, ?, ?, json(?))",
            (documento["id"], documento["tipo"], documento["estado"]["actual"],
             json.dumps(documento)),
        )  # fmt: skip


def test_la_correccion_clasifica_y_deja_el_motivo() -> None:
    almacen = Almacen.abrir()
    _guardar_sin_validar(almacen, _guardado("Rusia", "Prezydent oskarżyła Moskwę o prowokację"))
    resumen = tipo_atribucion.aplicar(almacen, DESPUES, MODELOS)
    assert resumen["clasificados"] == ["EODI-2025-00001"]
    nuevo = almacen.incidente("EODI-2025-00001")
    assert nuevo is not None
    assert nuevo["estado"]["actual"] == "atribuido"
    assert nuevo["atribucion"]["tipo"] == "estado" and nuevo["atribucion"]["pais"] == "RU"
    motivos = [h for h in almacen.historial("EODI-2025-00001") if "motivo" in (h["nuevo"] or {})]
    assert motivos[-1]["nuevo"]["motivo"] == tipo_atribucion.MOTIVO_TIPO
    # Una vez por versión.
    assert tipo_atribucion.aplicar(almacen, DESPUES + timedelta(hours=1), MODELOS) == {}


def test_la_correccion_quita_la_atribucion_que_la_frase_no_sostiene() -> None:
    almacen = Almacen.abrir()
    frase = "The drone entered Romanian territory from the Republic of Moldova"
    antes = _guardado("Constantin Dolachi-Pelin", frase)
    _guardar_sin_validar(almacen, antes)
    resumen = tipo_atribucion.aplicar(almacen, DESPUES, MODELOS)
    assert resumen["sin_atribucion"] == ["EODI-2025-00001"]
    nuevo = almacen.incidente("EODI-2025-00001")
    assert nuevo is not None
    assert nuevo["estado"]["actual"] == "confirmado"
    assert [p["estado"] for p in nuevo["estado"]["historial"]] == ["notificado", "confirmado"]
    assert "atribucion" not in nuevo
    # Las fuentes no cambian: la declaración sigue confirmando.
    assert nuevo["fuentes"] == antes["fuentes"]
    motivos = [h for h in almacen.historial("EODI-2025-00001") if "motivo" in (h["nuevo"] or {})]
    assert motivos[-1]["nuevo"]["motivo"] == tipo_atribucion.MOTIVO_SIN_ATRIBUCION


def test_corregir_no_toca_lo_que_ya_esta_bien() -> None:
    documento = ejemplos.incidente_completo()
    assert atribucion.corregir(documento) is documento
    sin = copy.deepcopy(documento)
    del sin["atribucion"]
    sin["estado"]["actual"] = "confirmado"
    assert atribucion.corregir(sin) is sin
