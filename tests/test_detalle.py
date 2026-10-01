"""Datos de las fuentes oficiales de detalle en los incidentes: cruce, aportación, idempotencia,
visibilidad, nivel de detalle y alta de sucesos citados."""

import copy
from datetime import UTC, datetime
from typing import Any

from almacen.base import Almacen
from esquema import Documento
from exportacion import procedencia as origenes
from exportacion.campos import CAMPOS_PUBLICOS_INCIDENTE
from exportacion.geojson import exportar
from exportacion.proyeccion import rutas
from proceso import detalle, incidentes
from tests import ejemplos
from tests.ejemplos import VOCABULARIO_MODELOS

AHORA = datetime(2026, 10, 1, 12, tzinfo=UTC)


def leido(documento: Documento | None) -> Documento:
    assert documento is not None
    return documento


def instante(valor: str, precision: str = "minuto") -> Documento:
    return {"valor": valor, "precision": precision}


def noticia(id_: str = "gdelt-0123456789abcdef") -> Documento:
    return {
        "id": id_,
        "enlace": f"https://medio.example/{id_}",
        "medio": "medio.example",
        "fecha": instante("2025-08-21T08:00Z", "aproximada"),
        "idioma": "en",
        "fiabilidad": "C",
        "credibilidad": 3,
        "frase_origen": "A drone came close to a plane near Heathrow",
        "replicas": 0,
        "es_autoridad": False,
        "interna_fuera_de_ucrania": False,
        "publica": True,
        "campos_respaldados": ["drones", "inicio"],
    }


def heathrow(id_: str = "EODI-2025-00134", dia: str = "2025-08-20") -> Documento:
    """Un incidente de noticias en Heathrow, con precisión de día."""
    fuente = noticia()
    return {
        "id": id_,
        "tipo": "sobrevuelo",
        "estado": {
            "actual": "notificado",
            "historial": [
                {"estado": "notificado", "fecha": fuente["fecha"], "fuente_id": fuente["id"]}
            ],
        },
        "titulo": {
            "es": "Dron cerca de un avión en Heathrow",
            "en": "Drone near a plane at Heathrow",
        },
        "presencia_dron": "no_confirmada",
        "pruebas": {"dron_estatal": False, "entrada_exterior": False, "evidencia": []},
        "tiempo": {"inicio": instante(f"{dia}T13:00Z", "dia")},
        "lugar": {
            "punto": {"lat": 51.46775, "lon": -0.45477},
            "radio_km": 3.0,
            "pais": "GB",
            "nivel": "instalacion",
            "suceso": "Heathrow Airport",
            "geocodificacion": "nomenclator",
        },
        "objetivo": {
            "categoria": "aeropuerto",
            "nombre": "London Heathrow Airport",
            "oaci": "EGLL",
        },
        "drones": {"numero": {"min": 1, "max": 1}},
        "consecuencias": {"cierre": {"valor": "desconocido"}},
        "fuentes": [fuente],
        "afirmaciones": [
            {
                "campo": "drones",
                "valor": {"min": 1, "max": 1},
                "fuente_id": fuente["id"],
                "confianza_extraccion": 0.9,
            }
        ],
        "control": {
            "alta": instante("2025-08-21T09:00Z"),
            "ultima_actualizacion": instante("2025-08-21T09:00Z"),
            "version_extractor": "ficha/5",
            "candidato": "CAND-1",
        },
    }


def encuentro(
    instante_: str = "2025-08-20T13:45Z", lat: float = 51.48, lon: float = -0.42
) -> Documento:
    documento = ejemplos.encuentro()
    documento.update(
        {
            "id": "UKAB-2025150",
            "numero": "2025150",
            "instante": instante(instante_),
            "posicion": {"punto": {"lat": lat, "lon": lon}, "descripcion": "2NM E Heathrow"},
        }
    )
    return documento


def base(*documentos: Documento) -> Almacen:
    almacen = Almacen.abrir()
    for documento in documentos:
        almacen.guardar_incidente(documento, AHORA, VOCABULARIO_MODELOS)
    return almacen


def test_el_encuentro_se_enlaza_con_el_unico_incidente_que_encaja() -> None:
    almacen = base(heathrow())
    almacen.guardar_encuentro(encuentro(), AHORA)
    assert detalle.cruzar_encuentros(almacen, AHORA) == 1
    assert leido(almacen.encuentro("UKAB-2025150"))["incidente"] == "EODI-2025-00134"


def test_lejos_o_otro_dia_no_se_enlaza() -> None:
    almacen = base(heathrow())
    almacen.guardar_encuentro(encuentro(lat=53.35, lon=-2.27), AHORA)  # Manchester
    assert detalle.cruzar_encuentros(almacen, AHORA) == 0
    almacen = base(heathrow())
    almacen.guardar_encuentro(encuentro("2025-08-25T13:45Z"), AHORA)
    assert detalle.cruzar_encuentros(almacen, AHORA) == 0


def test_con_dos_incidentes_que_encajan_no_se_enlaza() -> None:
    otro = heathrow("EODI-2025-00135")
    otro["fuentes"][0]["id"] = otro["estado"]["historial"][0]["fuente_id"] = (
        "gdelt-fedcba9876543210"
    )
    otro["afirmaciones"][0]["fuente_id"] = "gdelt-fedcba9876543210"
    almacen = base(heathrow(), otro)
    almacen.guardar_encuentro(encuentro(), AHORA)
    assert detalle.cruzar_encuentros(almacen, AHORA) == 0
    assert "incidente" not in leido(almacen.encuentro("UKAB-2025150"))


def revisado(almacen: Almacen) -> Documento:
    detalle.revisar(almacen, AHORA, VOCABULARIO_MODELOS)
    incidente = almacen.incidente("EODI-2025-00134")
    assert incidente is not None
    return incidente


def test_el_encuentro_aporta_sus_datos_sin_tocar_lo_publico() -> None:
    almacen = base(heathrow())
    almacen.guardar_encuentro(encuentro(), AHORA)
    antes = heathrow()
    incidente = revisado(almacen)
    # Confirmado por la UKAB, que entra como fuente oficial pública con su enlace y su frase.
    assert incidente["estado"]["actual"] == "confirmado"
    fuente = next(f for f in incidente["fuentes"] if f["id"] == "ukab-2025150")
    assert (fuente["fiabilidad"], fuente["credibilidad"], fuente["publica"]) == ("A", 2, True)
    assert fuente["metodo"] == "parser" and fuente["documento_oficial"] == "UKAB-2025150"
    # Los datos de detalle van a campos internos.
    assert incidente["detalle_oficial"]["inicio"] == instante("2025-08-20T13:45Z")
    assert incidente["detalle_oficial"]["radio_km"] == detalle.RADIO_ENCUENTRO_KM
    assert incidente["drones"]["altura_m"] == {"min": 99.06, "max": 129.54}
    assert incidente["respuesta"]["deteccion"] == ["piloto"]
    assert incidente["encuentros"] == ["UKAB-2025150"]
    # Lo público no cambia: hora, lugar y número siguen siendo los de la prensa.
    for campo in ("tiempo", "lugar", "objetivo", "presencia_dron"):
        assert incidente[campo] == antes[campo]
    assert incidente["drones"]["numero"] == antes["drones"]["numero"]


def test_lo_interno_nuevo_no_sale_a_la_web() -> None:
    almacen = base(heathrow())
    almacen.guardar_encuentro(encuentro(), AHORA)
    incidente = revisado(almacen)
    coleccion = exportar([incidente], AHORA, VOCABULARIO_MODELOS)
    publicado = coleccion["features"][0]["properties"]
    assert set(rutas(publicado)) <= CAMPOS_PUBLICOS_INCIDENTE
    assert "detalle_oficial" not in publicado and "encuentros" not in publicado
    # La respuesta solo traía la detección, que es interna: no sale un objeto vacío.
    assert "respuesta" not in publicado
    assert any(f["id"] == "ukab-2025150" for f in publicado["fuentes"])


def test_aplicar_dos_veces_no_cambia_nada() -> None:
    almacen = base(heathrow())
    almacen.guardar_encuentro(encuentro(), AHORA)
    primero = revisado(almacen)
    historial = len(almacen.historial("EODI-2025-00134"))
    segundo = revisado(almacen)
    assert primero == segundo
    assert len(almacen.historial("EODI-2025-00134")) == historial


def test_rehacer_el_incidente_desde_su_ficha_conserva_lo_oficial() -> None:
    almacen = base(heathrow())
    almacen.guardar_encuentro(encuentro(), AHORA)
    con_oficial = revisado(almacen)
    # Lo que deja una reconstrucción: el incidente de la ficha, sin lo oficial.
    rehecho = detalle.reaplicar(almacen, heathrow())
    assert rehecho["detalle_oficial"] == con_oficial["detalle_oficial"]
    assert rehecho["drones"]["altura_m"] == con_oficial["drones"]["altura_m"]
    assert rehecho["estado"]["actual"] == "confirmado"


def test_un_encuentro_fundido_lleva_lo_oficial_al_destino() -> None:
    almacen = base(heathrow())
    almacen.guardar_encuentro({**encuentro(), "incidente": "EODI-2025-00134"}, AHORA)
    fundido = {**heathrow(), "fusionado_en": "EODI-2025-00099"}
    destino = heathrow("EODI-2025-00099")
    almacen.guardar_incidente(destino, AHORA, VOCABULARIO_MODELOS)
    almacen.guardar_incidente(fundido, AHORA, VOCABULARIO_MODELOS)
    detalle.revisar(almacen, AHORA, VOCABULARIO_MODELOS)
    assert leido(almacen.encuentro("UKAB-2025150"))["incidente"] == "EODI-2025-00099"
    assert leido(almacen.incidente("EODI-2025-00099"))["encuentros"] == ["UKAB-2025150"]


def exportado(incidente: Documento, almacen: Almacen) -> Documento:
    return origenes.exportar_incidente(incidente, origenes.Fichas.de(almacen))


def test_la_altura_oficial_sube_el_incidente_a_nivel_a() -> None:
    almacen = base(heathrow())
    assert exportado(heathrow(), almacen)["nivel_detalle"] == "D"
    almacen.guardar_encuentro(encuentro(), AHORA)
    documento = exportado(revisado(almacen), almacen)
    assert documento["procedencia"]["drones.altura_m"]["origen"] == "oficial"
    assert documento["procedencia"]["drones.altura_m"]["metodo"] == "parser"
    assert documento["procedencia"]["detalle_oficial.inicio"]["origen"] == "oficial"
    assert documento["nivel_detalle"] == "A"


def test_sin_altura_la_hora_y_el_radio_oficiales_dan_nivel_b() -> None:
    almacen = base(heathrow())
    sin_altura = encuentro()
    del sin_altura["objeto"]["altura_m"]
    almacen.guardar_encuentro(sin_altura, AHORA)
    documento = exportado(revisado(almacen), almacen)
    assert documento["nivel_detalle"] == "B"
    assert documento["procedencia"]["estado"]["origen"] == "oficial"


def suceso(datos: dict[str, Any]) -> Documento:
    return {
        "datos": {
            k: {"valor": v, "frase": "Frase literal del documento.", "confianza": 0.95}
            for k, v in datos.items()
        },
        "cruce": "existente",
        "incidente": "EODI-2025-00134",
    }


def documento_oficial(sucesos: list[Documento]) -> Documento:
    return {
        **ejemplos.documento_oficial(),
        "pais": "GB",
        "idioma": "en",
        "enlace": "https://questions.example/answer/1",
        "sucesos": sucesos,
    }


def test_un_suceso_citado_confirma_y_aporta_deteccion_y_contramedidas() -> None:
    almacen = base(heathrow())
    almacen.guardar_documento_oficial(
        documento_oficial(
            [
                suceso(
                    {
                        "inicio": "2025-08-20T13:40",
                        "inicio_precision": "minuto",
                        "deteccion": ["radar"],
                        "resultado_contramedidas": "no_funciono",
                        "medidas": ["inhibicion"],
                        "presencia_dron": "confirmada",
                        "drones": {"min": 2, "max": 2},
                    }
                )
            ]
        ),
        AHORA,
    )
    incidente = revisado(almacen)
    assert incidente["estado"]["actual"] == "confirmado"
    assert incidente["presencia_dron"] == "confirmada"  # afirmación expresa con confianza alta
    assert incidente["respuesta"]["deteccion"] == ["radar"]
    assert incidente["respuesta"]["resultado_contramedidas"] == "no_funciono"
    assert incidente["detalle_oficial"]["medidas"] == ["inhibicion"]
    assert incidente["detalle_oficial"]["numero"] == {"min": 2, "max": 2}
    assert incidente["detalle_oficial"]["inicio"] == instante("2025-08-20T13:40Z")
    # La medida pública y el número de la prensa no cambian.
    assert "medidas" not in incidente["respuesta"]
    assert incidente["drones"]["numero"] == {"min": 1, "max": 1}
    fuente = next(
        f
        for f in incidente["fuentes"]
        if f["id"] == detalle.id_fuente("https://questions.example/answer/1")
    )
    assert fuente["metodo"] == "extractor" and fuente["credibilidad"] == 1


def test_presencia_con_confianza_baja_no_se_confirma() -> None:
    almacen = base(heathrow())
    dato = suceso({"presencia_dron": "confirmada"})
    dato["datos"]["presencia_dron"]["confianza"] = 0.7
    almacen.guardar_documento_oficial(documento_oficial([dato]), AHORA)
    assert revisado(almacen)["presencia_dron"] == "no_confirmada"


def test_un_desmentido_solo_lo_revierte_una_autoridad_igual_de_fiable() -> None:
    desmentido = heathrow()
    autoridad = {**noticia("politi-1"), "fiabilidad": "A", "es_autoridad": True, "credibilidad": 1}
    desmentido["fuentes"].append(autoridad)
    desmentido["estado"] = {
        "actual": "desmentido",
        "historial": [
            *desmentido["estado"]["historial"],
            {"estado": "desmentido", "fecha": autoridad["fecha"], "fuente_id": "politi-1"},
        ],
    }
    desmentido["control"]["motivo_desmentido"] = "era un globo"
    almacen = base(desmentido)
    almacen.guardar_encuentro(encuentro(), AHORA)
    incidente = revisado(almacen)
    # La UKAB es una autoridad de fiabilidad A, como la policía que desmintió (proceso/estados).
    assert incidente["estado"]["actual"] == "confirmado"
    assert [p["estado"] for p in incidente["estado"]["historial"]] == [
        "notificado",
        "desmentido",
        "confirmado",
    ]
    assert incidente["control"]["motivo_desmentido"] == "era un globo"


def test_aplicar_sin_aportaciones_devuelve_el_mismo_incidente() -> None:
    documento = heathrow()
    assert detalle.aplicar(documento, []) is documento
    assert incidentes.activo(copy.deepcopy(documento))
