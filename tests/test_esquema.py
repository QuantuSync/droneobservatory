import json
from pathlib import Path
from typing import Any

import pytest
from jsonschema import ValidationError

from esquema import (
    DIRECTORIO,
    VERSION,
    Esquema,
    Visibilidad,
    cargar,
    recorrer,
    rutas_por_visibilidad,
    validador,
)
from tests import ejemplos

RAIZ = Path(__file__).resolve().parent.parent


@pytest.mark.parametrize("esquema", list(Esquema))
def test_esquema_es_draft_2020_12_valido(esquema: Esquema) -> None:
    validador(esquema).check_schema(cargar(esquema))


@pytest.mark.parametrize("esquema", list(Esquema))
def test_esquema_declara_su_version(esquema: Esquema) -> None:
    contenido = cargar(esquema)
    assert contenido["x-version"] == VERSION
    assert contenido["$id"].endswith(f":{VERSION}:{esquema.value}")


def test_no_hay_esquemas_sin_registrar() -> None:
    en_disco = {p.name.removesuffix(".schema.json") for p in DIRECTORIO.glob("*.schema.json")}
    assert en_disco == {e.value for e in Esquema}


@pytest.mark.parametrize("esquema", list(Esquema))
def test_cada_campo_lleva_marca_propia(esquema: Esquema) -> None:
    sin_marca = [ruta for ruta, marca, _ in recorrer(esquema) if marca is None]
    assert sin_marca == []


def test_hijo_de_campo_interno_es_interno() -> None:
    rutas = rutas_por_visibilidad(Esquema.INCIDENTE)
    for ruta in rutas[Visibilidad.PUBLICO]:
        partes = ruta.replace("[]", "").split(".")
        for i in range(1, len(partes)):
            assert ".".join(partes[:i]) not in rutas[Visibilidad.INTERNO], ruta


def test_campos_internos_de_la_ficha() -> None:
    internas = rutas_por_visibilidad(Esquema.INCIDENTE)[Visibilidad.INTERNO]
    esperadas = {
        "lugar.nuts2",
        "drones.luces",
        "drones.altura_m",
        "drones.velocidad_ms",
        "drones.trayectoria",
        "drones.patron",
        "respuesta.deteccion",
        "respuesta.resultado_contramedidas",
        "fuentes[].campos_respaldados",
        "afirmaciones",
        "control.alta",
        "control.version_extractor",
        "control.huella_fuentes",
        "control.vocabulario_aegis",
        "control.distancia_instalaciones_km",
    }
    assert esperadas <= internas


def test_campos_internos_de_la_capa_ucrania() -> None:
    internas = rutas_por_visibilidad(Esquema.ATAQUE_UCRANIA)[Visibilidad.INTERNO]
    assert {"horas_llegada", "duracion_oleada_min", "proporcion_senuelos"} <= internas


@pytest.mark.parametrize(
    ("esquema", "documento"),
    [
        (Esquema.INCIDENTE, ejemplos.incidente_completo()),
        (Esquema.INCIDENTE, ejemplos.incidente_minimo()),
        (Esquema.ATAQUE_UCRANIA, ejemplos.ataque_completo()),
        (Esquema.REGION_UCRANIA, ejemplos.region()),
        (Esquema.EPISODIO, ejemplos.episodio()),
        (Esquema.FUENTE, ejemplos.fuente()),
        (Esquema.AFIRMACION, ejemplos.incidente_completo()["afirmaciones"][0]),
    ],
)
def test_ejemplos_validos(esquema: Esquema, documento: Any) -> None:
    validador(esquema).validate(documento)


@pytest.mark.parametrize(
    ("ruta", "valor"),
    [
        (("id",), "EODI-25-1"),
        (("tipo",), "ataque_guerra"),
        (("lugar", "radio_km"), 0.05),
        (("lugar", "radio_km"), 51),
        (("lugar", "pais"), "ESP"),
        (("tiempo", "inicio", "precision"), "segundo"),
        (("tiempo", "inicio", "valor"), "2025-10-01 20:30"),
        (("drones", "numero"), 5),
        (("drones", "numero"), None),
        (("objetivo", "oaci"), "KAS"),
        (("control", "huella_fuentes"), "xyz"),
    ],
)
def test_incidente_rechaza_valores_mal_formados(ruta: tuple[str, ...], valor: Any) -> None:
    documento = ejemplos.incidente_completo()
    nodo = documento
    for clave in ruta[:-1]:
        nodo = nodo[clave]
    nodo[ruta[-1]] = valor
    with pytest.raises(ValidationError):
        validador(Esquema.INCIDENTE).validate(documento)


def test_frase_de_origen_de_mas_de_25_palabras_rechazada() -> None:
    documento = ejemplos.fuente()
    documento["frase_origen"] = " ".join(["palabra"] * 26)
    with pytest.raises(ValidationError):
        validador(Esquema.FUENTE).validate(documento)
    documento["frase_origen"] = " ".join(["palabra"] * 25)
    validador(Esquema.FUENTE).validate(documento)


def test_campo_desconocido_rechazado() -> None:
    documento = ejemplos.incidente_minimo()
    documento["texto_completo"] = "no se guarda nunca"
    with pytest.raises(ValidationError):
        validador(Esquema.INCIDENTE).validate(documento)


@pytest.mark.parametrize("nombre", ["fuentes.json", "modelos_dron.json"])
def test_configuracion_declara_version(nombre: str) -> None:
    contenido = json.loads((RAIZ / "configuracion" / nombre).read_text(encoding="utf-8"))
    assert contenido["version_esquema"] == VERSION


def test_configuracion_de_fuentes_valida() -> None:
    contenido = json.loads((RAIZ / "configuracion" / "fuentes.json").read_text(encoding="utf-8"))
    validador(Esquema.CONFIGURACION_FUENTES).validate(contenido)
