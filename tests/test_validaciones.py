from collections.abc import Callable
from typing import Any

import pytest

from esquema import Documento
from proceso.configuracion import cargar_fuentes, cargar_vocabulario_modelos
from proceso.validaciones import (
    Error,
    derivar_duracion_min,
    derivar_proporcion_senuelos,
    validar_ataque_ucrania,
    validar_episodio,
    validar_incidente,
)
from tests import ejemplos
from tests.ejemplos import AHORA, VOCABULARIO_MODELOS, instante


def validar(documento: Documento) -> list[Error]:
    return validar_incidente(documento, AHORA, VOCABULARIO_MODELOS)


def mensajes(errores: list[Error]) -> str:
    return " | ".join(f"{e.ruta}: {e.mensaje}" for e in errores)


@pytest.mark.parametrize("fabrica", [ejemplos.incidente_completo, ejemplos.incidente_minimo])
def test_ejemplos_sin_errores(fabrica: Callable[[], Documento]) -> None:
    assert validar(fabrica()) == []


def test_ataque_y_episodio_sin_errores() -> None:
    assert validar_ataque_ucrania(ejemplos.ataque_completo(), AHORA) == []
    assert validar_episodio(ejemplos.episodio(), AHORA) == []


def test_vocabulario_de_configuracion() -> None:
    assert cargar_vocabulario_modelos() == VOCABULARIO_MODELOS
    assert cargar_fuentes() == []


def _cambiar(documento: Documento, ruta: str, valor: Any) -> Documento:
    nodo: Any = documento
    claves = ruta.split(".")
    for clave in claves[:-1]:
        nodo = nodo[int(clave)] if isinstance(nodo, list) else nodo[clave]
    nodo[claves[-1]] = valor
    return documento


CASOS_INCIDENTE = [
    ("mínimo mayor que máximo", "drones.numero", {"min": 6, "max": 3}, "mayor que máximo"),
    ("fecha futura", "tiempo.inicio", instante("2026-03-01T00:00Z"), "fecha futura"),
    ("fecha imposible", "tiempo.inicio", instante("2025-02-30T10:00Z"), "fecha imposible"),
    ("hora imposible", "tiempo.fin", instante("2025-10-01T25:00Z"), "fecha imposible"),
    ("fin antes del inicio", "tiempo.fin", instante("2025-10-01T19:00Z"), "fin anterior"),
    ("duración no derivada", "tiempo.duracion_min", 60, "derivada"),
    ("radio bajo", "lugar.radio_km", 0.05, "fuera de"),
    ("radio alto", "lugar.radio_km", 50.5, "fuera de"),
    ("seis decimales", "lugar.punto.lat", 55.618061, "decimales"),
    ("frase larga", "fuentes.0.frase_origen", " ".join(["x"] * 26), "25 palabras"),
    ("fuente E pública", "fuentes.2.publica", True, "marcada como pública"),
    ("fuente interna fuera de Ucrania pública", "fuentes.3.publica", True, "fuera de la capa"),
    ("modelo fuera de vocabulario", "drones.modelo", "inventado", "vocabulario"),
    ("OACI sin aeropuerto", "objetivo.categoria", "puerto", "OACI"),
    ("interrupción con otro tipo", "tipo", "sobrevuelo", "manda ese tipo"),
    ("afirmación sin fuente", "afirmaciones.0.fuente_id", "F9", "fuente inexistente"),
    ("cambio de estado sin fuente", "estado.historial.1.fuente_id", "F9", "fuente inexistente"),
    ("motivo sin desmentido", "control.motivo_desmentido", "Eran aves", "sin desmentido"),
]


@pytest.mark.parametrize(
    ("ruta", "valor", "esperado"),
    [c[1:] for c in CASOS_INCIDENTE],
    ids=[c[0] for c in CASOS_INCIDENTE],
)
def test_regla_incidente(ruta: str, valor: Any, esperado: str) -> None:
    errores = validar(_cambiar(ejemplos.incidente_completo(), ruta, valor))
    assert esperado in mensajes(errores)


def test_atribuido_sin_confirmado() -> None:
    documento = ejemplos.incidente_completo()
    del documento["estado"]["historial"][1]
    texto = mensajes(validar(documento))
    assert "atribuido sin confirmado" in texto
    assert "notificado → atribuido" in texto


def test_atribucion_exige_estado_atribuido() -> None:
    documento = ejemplos.incidente_completo()
    documento["estado"]["actual"] = "confirmado"
    documento["estado"]["historial"].pop()
    assert "atribución con estado distinto" in mensajes(validar(documento))


def test_atribuido_exige_atribucion() -> None:
    documento = ejemplos.incidente_completo()
    del documento["atribucion"]
    assert "sin atribución" in mensajes(validar(documento))


def test_transicion_no_permitida_desde_desmentido() -> None:
    documento = ejemplos.incidente_minimo()
    fecha = instante("2025-11-05T10:00Z")
    documento["estado"]["historial"] += [
        {"estado": "desmentido", "fecha": fecha, "fuente_id": "F1"},
        {"estado": "confirmado", "fecha": fecha, "fuente_id": "F1"},
    ]
    documento["estado"]["actual"] = "confirmado"
    assert "desmentido → confirmado" in mensajes(validar(documento))


def test_desmentido_exige_motivo_y_sigue_siendo_valido_con_el() -> None:
    documento = ejemplos.incidente_minimo()
    documento["estado"]["historial"].append(
        {"estado": "desmentido", "fecha": instante("2025-11-05T10:00Z"), "fuente_id": "F1"}
    )
    documento["estado"]["actual"] = "desmentido"
    assert "desmentido sin motivo" in mensajes(validar(documento))
    documento["control"]["motivo_desmentido"] = "La autoridad aclara que eran aves"
    assert validar(documento) == []


def test_incursion_exige_origen_demostrado() -> None:
    documento = ejemplos.incidente_minimo()
    documento["tipo"] = "incursion"
    assert "origen demostrado" in mensajes(validar(documento))
    documento["origen_demostrado_por"] = ["restos"]
    assert validar(documento) == []


def test_minutos_de_cierre_sin_cierre() -> None:
    documento = ejemplos.incidente_minimo()
    documento["consecuencias"] = {"cierre": {"valor": "no", "minutos": {"min": 5, "max": 5}}}
    assert "minutos de cierre sin cierre" in mensajes(validar(documento))


def test_desconocido_no_es_rango_invalido() -> None:
    documento = ejemplos.incidente_minimo()
    documento["drones"] = {"numero": "desconocido", "clase": "desconocido"}
    assert validar(documento) == []


def test_errores_de_esquema_y_de_codigo_juntos() -> None:
    documento = ejemplos.incidente_completo()
    documento["lugar"]["radio_km"] = 80
    documento["drones"]["numero"] = {"min": 9, "max": 1}
    rutas = {e.ruta for e in validar(documento)}
    assert "$.lugar.radio_km" in rutas
    assert "lugar.radio_km" in rutas
    assert "drones.numero" in rutas


def test_derivar_duracion() -> None:
    tiempo = {"inicio": instante("2025-10-01T20:30Z"), "fin": instante("2025-10-01T23:30Z")}
    assert derivar_duracion_min(tiempo) == 180
    assert derivar_duracion_min({"inicio": instante("2025-10-01T20:30Z")}) is None


# --- Capa de Ucrania --------------------------------------------------------


def test_ucrania_admite_fuente_interna_fuera_de_ucrania_como_publica() -> None:
    documento = ejemplos.ataque_completo()
    assert documento["fuentes"][1]["interna_fuera_de_ucrania"]
    assert documento["fuentes"][1]["publica"]
    assert validar_ataque_ucrania(documento, AHORA) == []


def test_ucrania_rechaza_fuente_f_publica() -> None:
    documento = ejemplos.ataque_completo()
    documento["fuentes"][1]["fiabilidad"] = "F"
    assert "marcada como pública" in mensajes(validar_ataque_ucrania(documento, AHORA))


def test_ucrania_rechaza_atribucion() -> None:
    documento = ejemplos.ataque_completo()
    documento["estado"]["historial"].append(
        {"estado": "atribuido", "fecha": instante("2025-10-06T08:00Z"), "fuente_id": "P1"}
    )
    documento["estado"]["actual"] = "atribuido"
    assert "confirmado → atribuido" in mensajes(validar_ataque_ucrania(documento, AHORA))


def test_ucrania_proporcion_de_senuelos_derivada() -> None:
    documento = ejemplos.ataque_completo()
    assert derivar_proporcion_senuelos(documento["lanzados"]) == documento["proporcion_senuelos"]
    documento["proporcion_senuelos"] = 0.5
    assert "derivada" in mensajes(validar_ataque_ucrania(documento, AHORA))


def test_ucrania_proporcion_no_derivable_con_rangos() -> None:
    lanzados = {"shahed_geran": {"min": 70, "max": 90}, "gerbera_senuelos": {"min": 20, "max": 20}}
    assert derivar_proporcion_senuelos(lanzados) is None


def test_ucrania_periodo_invertido_y_rango() -> None:
    documento = ejemplos.ataque_completo()
    documento["periodo"]["fin"] = instante("2025-10-05T10:00Z")
    documento["regiones"][0]["impactos"] = {"min": 5, "max": 1}
    texto = mensajes(validar_ataque_ucrania(documento, AHORA))
    assert "fin anterior" in texto
    assert "mayor que máximo" in texto


@pytest.mark.parametrize(
    ("noche", "esperado"), [("2026-02-01", "futura"), ("2025-13-01", "imposible")]
)
def test_episodio_noche(noche: str, esperado: str) -> None:
    documento = ejemplos.episodio()
    documento["noche"] = noche
    assert validar_episodio(documento, AHORA) != []
    assert esperado in mensajes(validar_episodio(documento, AHORA))
