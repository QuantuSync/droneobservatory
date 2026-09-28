"""Declaraciones oficiales citadas por la prensa: una prueba por regla.

Las frases siguen las de los casos de 2025 (Copenhague, Múnich, Polonia, Gardermoen).
"""

import json
from typing import Any

from almacen.base import Almacen
from esquema import Documento
from modelo import ficha
from proceso import declaraciones
from proceso.validaciones import validar_incidente
from tests.test_extraccion import AHORA, MODELOS, a_servicio, extraer_ejemplo, ficha_ejemplo

TEXTO = (
    "Københavns Politi: Vi kan bekræfte, at der i aften er observeret droner over lufthavnen, "
    "og at lufthavnen er lukket. Politiet har modtaget flere anmeldelser om droner i Kastrup."
)


def declaracion(
    afirma: str, frase: str, categoria: str = "policia", **resto: Any
) -> dict[str, Any]:
    return {"autoridad": "Københavns Politi", "categoria": categoria, "afirma": afirma,
            "autor": "", "fuente": 1, "frase": frase, **resto}  # fmt: skip


def incidente() -> tuple[Documento, list[str]]:
    almacen = Almacen.abrir()
    id_ = extraer_ejemplo(almacen)
    resultado = almacen.incidente(str(id_))
    assert resultado is not None
    return resultado, [resultado["fuentes"][0]["enlace"]]


def aplicar(*lista: dict[str, Any]) -> Documento:
    base, enviadas = incidente()
    resultado = declaraciones.aplicar(base, list(lista), enviadas)
    assert validar_incidente(resultado, AHORA, MODELOS) == []
    return resultado


def test_la_autoridad_que_afirma_el_cierre_confirma() -> None:
    resultado = aplicar(declaracion(
        "incidente", "Der Flugbetrieb wurde am Donnerstagabend eingestellt", "aeropuerto",
        autoridad="Flughafen München",
    ))  # fmt: skip
    assert resultado["estado"]["actual"] == "confirmado"
    assert resultado["presencia_dron"] == "no_confirmada"
    citada = resultado["fuentes"][-1]
    assert (citada["fiabilidad"], citada["es_autoridad"]) == ("B", True)
    assert "declaración oficial citada" in citada["medio"]
    assert citada["enlace"] == resultado["fuentes"][0]["enlace"]


def test_drones_afirmados_por_las_fuerzas_armadas_confirman_la_presencia() -> None:
    resultado = aplicar(declaracion(
        "drones", "Siły Zbrojne RP zestrzeliły drony, które naruszyły polską przestrzeń powietrzną",
        "fuerzas_armadas", autoridad="Dowództwo Operacyjne RSZ",
    ))  # fmt: skip
    assert resultado["estado"]["actual"] == "confirmado"
    assert resultado["presencia_dron"] == "confirmada"


def test_los_avisos_recibidos_no_confirman_nada() -> None:
    resultado = aplicar(
        declaracion("drones", "Politiet har modtaget flere anmeldelser om droner i Kastrup")
    )
    assert resultado["estado"]["actual"] == "notificado"
    assert resultado["presencia_dron"] == "no_confirmada"
    assert not any(f["id"].endswith("-declaracion-1") for f in resultado["fuentes"])


def test_sin_drones_descarta_la_presencia() -> None:
    resultado = aplicar(declaracion("sin_drones", "Ingen droner ved Gardermoen likevel"))
    assert resultado["presencia_dron"] == "descartada"


def test_negar_el_incidente_lo_desmiente() -> None:
    resultado = aplicar(declaracion(
        "niega_incidente", "Der har ikke været nogen droner eller lukning af lufthavnen"
    ))  # fmt: skip
    assert resultado["estado"]["actual"] == "desmentido"


def test_solo_un_gobierno_atribuye() -> None:
    confirma = declaracion("drones", "Vi kan bekræfte, at der i aften er observeret droner")
    policia = declaracion("autoria", "Det er en kapabel aktør", autor="Rusia")
    assert aplicar(confirma, policia)["estado"]["actual"] == "confirmado"
    gobierno = declaracion(
        "autoria", "To była prowokacja rosyjskich dronów", "gobierno",
        autoridad="Premier RP", autor="Rusia",
    )  # fmt: skip
    resultado = aplicar(confirma, gobierno)
    assert resultado["estado"]["actual"] == "atribuido"
    assert resultado["atribucion"]["actor"] == "Rusia"


def test_la_frase_tiene_que_estar_en_la_noticia() -> None:
    buena = declaracion("incidente", "vi kan bekræfte, at der i aften er observeret droner")
    inventada = declaracion("drones", "Politiet har fundet dronen")
    assert declaraciones.validas([buena, inventada], [TEXTO]) == [buena]


def test_la_ficha_trae_las_declaraciones_y_las_antiguas_se_leen_sin_ellas() -> None:
    salida = a_servicio(ficha_ejemplo())
    antigua = {"stop_reason": "end_turn",
               "content": [{"type": "text", "text": json.dumps(salida)}]}  # fmt: skip
    assert ficha.leer_respuesta(antigua)["declaraciones"] == []
    salida["declaraciones"] = [
        declaracion("incidente", "lufthavnen er lukket"),
        declaracion("incidente", "x", categoria="periodico"),
    ]
    nueva = {"stop_reason": "end_turn",
             "content": [{"type": "text", "text": json.dumps(salida)}]}  # fmt: skip
    assert [d["frase"] for d in ficha.leer_respuesta(nueva)["declaraciones"]] == [
        "lufthavnen er lukket"
    ]
