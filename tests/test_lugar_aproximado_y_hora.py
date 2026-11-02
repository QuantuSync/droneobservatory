"""La ficha del día tarde, lejos y sin hora (2 de noviembre de 2026): el centro de la región de
Natural Earth para el marcador aproximado (proceso/regiones_aproximadas.py), las localidades que
nombra la fuente (proceso/ubicacion.lugar_de_las_localidades, EODI-2026-00725) y la hora dicha
en la frase de una fuente (proceso/fechas.hora_de_las_frases, EODI-2026-00719)."""

import copy
import json
from datetime import UTC, datetime
from typing import Any

import pytest

from exportacion.campos import CAMPOS_PUBLICOS_SIN_UBICACION
from proceso import decidir, fechas, noticias, regiones_aproximadas, ubicacion
from recogida.regiones_natural_earth import DESTINO, leer_dbf, nombres_de, sin_genericos

IASI = (27.303, 47.205)


@pytest.mark.parametrize(
    "nombre", ["Iași", "județul Iași", "Iasi", "Яссы", "Iași County", "Iasi, judetul"]
)
def test_la_region_de_iasi_en_todas_sus_formas(nombre: str) -> None:
    assert regiones_aproximadas.centro("RO", nombre) == IASI


def test_los_judete_y_los_raioane_estan_y_lo_desconocido_no() -> None:
    suceava = regiones_aproximadas.centro("RO", "Suceava")
    assert suceava is not None and 47.0 < suceava[1] < 47.6 and 25.3 < suceava[0] < 26.3
    assert regiones_aproximadas.centro("MD", "raionul Ștefan Vodă") is not None
    assert regiones_aproximadas.centro("MD", "Rîșcani") is not None
    # De otro país no vale: Iași no es una región de Moldavia.
    assert regiones_aproximadas.centro("MD", "Iași") is None
    assert regiones_aproximadas.centro("RO", "Nowhere") is None
    assert regiones_aproximadas.centro("RO", None) is None


def test_el_lugar_publicado_lleva_el_centro_de_su_region() -> None:
    lugar = {"nivel": "localidad", "pais": "RO", "region": "Suceava"}
    con = regiones_aproximadas.con_centro(lugar)
    assert set(con["centro_region"]) == {"lon", "lat"}
    assert lugar == {"nivel": "localidad", "pais": "RO", "region": "Suceava"}
    # Uno de nivel país no lleva centro de región, ni uno con punto.
    assert "centro_region" not in regiones_aproximadas.con_centro({"nivel": "pais", "pais": "RO"})
    assert {"lugar.centro_region.lon", "lugar.centro_region.lat"} <= CAMPOS_PUBLICOS_SIN_UBICACION


def test_la_tabla_esta_generada_con_los_genericos_de_la_web() -> None:
    datos = json.loads(DESTINO.read_text(encoding="utf-8"))
    assert len(datos["regiones"]) > 1500
    assert "judetul" in datos["genericos"] and "raionul" in datos["genericos"]
    assert sin_genericos("iasi, judetul") == "iasi"


def test_el_lector_de_dbf_y_los_nombres() -> None:
    campos = [("name", 10), ("name_alt", 12), ("iso_a2", 2)]
    cabecera = 32 + 32 * len(campos) + 1
    largo = 1 + sum(a for _, a in campos)
    datos = bytearray(b"\x03" + bytes(3))
    datos += (
        (1).to_bytes(4, "little") + cabecera.to_bytes(2, "little") + largo.to_bytes(2, "little")
    )
    datos += bytes(20)
    for nombre, ancho in campos:
        datos += nombre.encode().ljust(11, b"\0") + b"C" + bytes(4) + bytes([ancho]) + bytes(15)
    datos += b"\r"
    datos += b" " + "Iași".encode().ljust(10, b"\0") + b"Iasi|Jassy".ljust(12, b"\0") + b"RO"
    filas = leer_dbf(bytes(datos))
    assert filas == [{"name": "Iași", "name_alt": "Iasi|Jassy", "iso_a2": "RO"}]
    assert nombres_de(filas[0]) == ["iasi", "jassy"]


FRATAUTI = {
    "nivel": "localidad",
    "pais": "RO",
    "region": "Suceava",
    "suceso": "Frătăuți și Horodnic",
}


def test_las_localidades_que_nombra_la_fuente_tienen_punto() -> None:
    """EODI-2026-00725: «Drone semnalate în zonele Frătăuți și Horodnic» (monitorulsv.ro). Son
    Frătăuții Noi y Vechi y Horodnic de Jos y de Sus, junto a Rădăuți: el punto en medio."""
    lugar = ubicacion.lugar_de_las_localidades({"lugar": FRATAUTI}, noticias.nomenclator())
    assert lugar is not None
    assert abs(lugar["punto"]["lat"] - 47.89) < 0.05 and abs(lugar["punto"]["lon"] - 25.84) < 0.05
    assert lugar["radio_km"] < 15
    assert lugar["geocodificacion"] == "localidad" and lugar["suceso"] == FRATAUTI["suceso"]


def test_sin_region_homonimos_lejanos_u_otra_region_no_hay_punto() -> None:
    nom = noticias.nomenclator()
    # Dos Gaižiūnai a 24 km en Kaunas (EODI-2025-00246): no se sabe cuál es.
    gaiziunai = {"nivel": "localidad", "pais": "LT", "region": "Kaunas", "suceso": "Gaiziunai"}
    assert ubicacion.lugar_de_las_localidades({"lugar": gaiziunai}, nom) is None
    assert (
        ubicacion.lugar_de_las_localidades({"lugar": {**FRATAUTI, "region": "Iași"}}, nom) is None
    )
    sin_region = {k: v for k, v in FRATAUTI.items() if k != "region"}
    assert ubicacion.lugar_de_las_localidades({"lugar": sin_region}, nom) is None
    con_punto = {**FRATAUTI, "punto": {"lat": 47.0, "lon": 25.0}}
    assert ubicacion.lugar_de_las_localidades({"lugar": con_punto}, nom) is None


HOTNEWS = "gdelt-249c0c52f121250f"


def ficha_iasi() -> dict[str, Any]:
    """Lo que importa de EODI-2026-00719 tal como estaba el 2/11: el día de su primera nota y la
    afirmación de hotnews.ro con la hora y el desfase de verano (14:04 por 15:04 UTC)."""
    return {
        "id": "EODI-2026-00719",
        "lugar": {"pais": "RO", "punto": {"lat": 47.17991, "lon": 27.62082}},
        "tiempo": {
            "inicio": {"precision": "dia", "valor": "2026-10-31T00:00Z"},
            "origen_inicio": {
                "tipo": "relativa",
                "fuente_id": "gdelt-5c1093f0aedf575d",
                "motivo": "«sambata» en una nota publicada el 2026-10-31 18:00",
            },
        },
        "fuentes": [
            {
                "id": "gdelt-5c1093f0aedf575d",
                "enlace": "https://ziare.com/a",
                "frase_origen": "Un mesaj RO-Alert a fost primit sâmbătă de locuitorii din Iași",
            },
            {
                "id": HOTNEWS,
                "enlace": "https://hotnews.ro/b",
                "frase_origen": "Primul mesaj RO-Alert a fost emis în județul Iași, la ora 17:04.",
            },
        ],
        "afirmaciones": [
            {"campo": "inicio", "fuente_id": "gdelt-5c1093f0aedf575d", "valor": "2026-10-31"},
            {"campo": "inicio", "fuente_id": HOTNEWS, "valor": "2026-10-31T14:04"},
        ],
    }


def test_la_hora_de_la_frase_llega_a_la_ficha_en_utc() -> None:
    hora = fechas.hora_de_las_frases(ficha_iasi())
    assert hora is not None
    assert hora.valor == datetime(2026, 10, 31, 15, 4, tzinfo=UTC)
    assert (hora.local, hora.fuente_id, hora.zona) == ("17:04", HOTNEWS, "Europe/Bucharest")
    ficha = ficha_iasi()
    decidir._con_hora_de_la_frase(ficha)
    assert ficha["tiempo"]["inicio"] == {"valor": "2026-10-31T15:04Z", "precision": "minuto"}
    origen = ficha["tiempo"]["origen_inicio"]
    assert (
        origen["tipo"] == "relativa" and "17:04" in origen["motivo"] and "15:04" in origen["motivo"]
    )
    # Ya con la hora, no se vuelve a tocar.
    otra = copy.deepcopy(ficha)
    decidir._con_hora_de_la_frase(otra)
    assert otra == ficha


def test_sin_hora_en_la_frase_de_otro_dia_o_de_otro_huso_no_se_pone() -> None:
    sin_hora = ficha_iasi()
    sin_hora["fuentes"][1]["frase_origen"] = "Primul mesaj RO-Alert a fost emis în județul Iași."
    assert fechas.hora_de_las_frases(sin_hora) is None
    otro_dia = ficha_iasi()
    otro_dia["tiempo"]["inicio"]["valor"] = "2026-11-01T00:00Z"
    assert fechas.hora_de_las_frases(otro_dia) is None
    # Un medio austríaco da la hora en la suya (EODI-2026-00582, heute.at): no se sabe cuál es.
    austriaco = ficha_iasi()
    austriaco["fuentes"][1]["enlace"] = "https://heute.at/c"
    assert fechas.hora_de_las_frases(austriaco) is None
    # Dos frases con horas distintas (EODI-2026-00582: «gegen 17.43 Uhr» y «în jurul orei 18:00»).
    distintas = ficha_iasi()
    distintas["fuentes"].append(
        {
            "id": "otra",
            "enlace": "https://capital.ro/d",
            "frase_origen": "Intervențiile au avut loc în jurul orei 17:40.",
        }
    )
    distintas["afirmaciones"].append({"campo": "inicio", "fuente_id": "otra",
                                      "valor": "2026-10-31T15:40"})  # fmt: skip
    assert fechas.hora_de_las_frases(distintas) is None
    oficial = ficha_iasi()
    oficial["tiempo"]["origen_inicio"]["tipo"] = "oficial"
    decidir._con_hora_de_la_frase(oficial)
    assert oficial["tiempo"]["inicio"]["precision"] == "dia"


def test_la_recogida_vuelve_a_guardar_la_ficha_guardada_sin_la_hora(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Las fichas guardadas antes de la regla las vuelve a guardar recogida/revisados.py, una vez:
    nada más las vuelve a guardar."""
    from recogida import revisados
    from tests.ejemplos import VOCABULARIO_MODELOS
    from tests.test_control_fichas import AHORA, _base, _nuremberg_alemana

    documento = _nuremberg_alemana()
    fuente = documento["fuentes"][0]
    fuente["frase_origen"] = "Am Flughafen Nürnberg wurde um 10.30 Uhr eine Drohne gesehen."
    documento["tiempo"] = {
        "inicio": {"valor": "2026-10-13T00:00Z", "precision": "dia"},
        "origen_inicio": {"tipo": "relativa", "fuente_id": fuente["id"], "motivo": "«Dienstag»"},
    }
    documento["afirmaciones"] = [
        *(a for a in documento["afirmaciones"] if a.get("campo") != "inicio"),
        {
            "campo": "inicio",
            "fuente_id": fuente["id"],
            "valor": "2026-10-13T10:30",
            "confianza_extraccion": 0.8,
        },
    ]
    con_regla = decidir._con_lo_que_dicen_las_frases
    monkeypatch.setattr(decidir, "_con_lo_que_dicen_las_frases", lambda r, v: None)
    almacen = _base(documento)
    guardado = almacen.incidente(documento["id"])
    assert guardado is not None and guardado["tiempo"]["inicio"]["precision"] == "dia"
    monkeypatch.setattr(decidir, "_con_lo_que_dicen_las_frases", con_regla)
    monkeypatch.setattr(revisados, "cargar", lambda: {})
    hechos = revisados.corregir(almacen, AHORA, VOCABULARIO_MODELOS)
    assert hechos.de_las_frases == [documento["id"]]
    guardado = almacen.incidente(documento["id"])
    assert guardado is not None
    assert guardado["tiempo"]["inicio"] == {"valor": "2026-10-13T08:30Z", "precision": "minuto"}
    assert revisados.corregir(almacen, AHORA, VOCABULARIO_MODELOS).de_las_frases == []
