"""Incursiones en países fronterizos enlazadas con el ataque de su noche, en los dos sentidos
(docs/informe_errores_datos.md, bloque 4)."""

import copy
from datetime import UTC, datetime
from typing import Any

from almacen.base import Almacen
from proceso import cruces
from proceso.ataques import jornada
from proceso.impactos_guerra import Ataques
from tests import ejemplos

AHORA = datetime(2026, 10, 4, 10, 0, tzinfo=UTC)
MODELOS: frozenset[str] = frozenset()


def _ataque(id_: str, inicio: str, fin: str, **extra: Any) -> dict[str, Any]:
    documento = ejemplos.ataque_completo()
    documento.update(
        id=id_, sentido="RU_UA", cruces=[],
        periodo={"inicio": ejemplos.instante(inicio), "fin": ejemplos.instante(fin)}, **extra,
    )  # fmt: skip
    for campo in ("cruces_parte", "restricciones_aeropuertos", "incluido_en", "solapado_con"):
        documento.pop(campo, None)
    return documento


NOCHE = _ataque("EODI-UA-2025-0244", "2025-09-12T15:00Z", "2025-09-13T05:00Z")


def _incidente(id_: str, pais: str, titulo: str, inicio: str, **pruebas: bool) -> dict[str, Any]:
    documento: dict[str, Any] = {}
    documento.update(
        id=id_, tipo="incursion", titulo={"es": titulo, "en": titulo},
        lugar={"pais": pais, "nivel": "pais"},
        tiempo={"inicio": ejemplos.instante(inicio)},
        pruebas={"dron_estatal": True, "entrada_exterior": True, "evidencia": [], **pruebas},
        fuentes=[{"id": f"f-{id_}", "frase_origen": titulo}],
        control={"version_extractor": "ficha/5"},
    )  # fmt: skip
    return documento


def _enlace(incidente: dict[str, Any]) -> tuple[str, str] | None:
    return cruces.enlace(incidente, Ataques([NOCHE]), {})


def test_jornada_del_parte_como_la_web() -> None:
    assert jornada(NOCHE["periodo"]) == {"tipo": "noche", "desde": "2025-09-12",
                                         "hasta": "2025-09-13"}  # fmt: skip
    dia = {"inicio": {"valor": "2025-09-13T05:00Z"}, "fin": {"valor": "2025-09-13T15:00Z"}}
    assert jornada(dia) == {"tipo": "dia", "desde": "2025-09-13", "hasta": "2025-09-13"}


def test_incursion_de_rumania_por_la_fuente_y_por_la_fecha() -> None:
    por_fuente = _incidente(
        "EODI-2025-00216", "RO", "Dron ruso en Rumanía durante el ataque contra Ucrania",
        "2025-09-12T23:00Z",
    )  # fmt: skip
    assert _enlace(por_fuente) == ("EODI-UA-2025-0244", "fuente")
    por_fecha = _incidente("EODI-2025-00217", "RO", "Dron interceptado cerca de Tulcea",
                           "2025-09-13T01:30Z")  # fmt: skip
    assert _enlace(por_fecha) == ("EODI-UA-2025-0244", "fecha")
    fuera = _incidente("EODI-2025-00218", "MD", "Dron sobre Moldavia", "2025-09-13T14:00Z")
    assert _enlace(fuera) is None


def test_no_se_enlaza_lo_de_bielorrusia_los_globos_ni_los_drones_ucranianos() -> None:
    for titulo, pais in [
        ("Cazas de la OTAN derriban un dron sobre Lituania procedente de Bielorrusia", "LT"),
        ("Cierre del aeropuerto de Vilna por globos de contrabando", "LT"),
        ("Dron ucraniano desviado golpea una central en Estonia", "EE"),
        ("Dron marino ucraniano explota en el Puerto de Constanza", "RO"),
        ("Dron derribado sobre Letonia", "LV"),
    ]:
        assert _enlace(_incidente("EODI-2025-00300", pais, titulo, "2025-09-12T23:00Z")) is None
    # Fuera de Rumanía y Moldavia, un dron ruso solo con la fuente que lo relaciona con el
    # ataque o que dice que viene de Ucrania.
    ruso = _incidente(
        "EODI-2025-00301", "PL", "Drones rusos invaden el espacio aéreo de Polonia",
        "2025-09-12T23:00Z",
    )  # fmt: skip
    assert _enlace(ruso) is None
    ruso["fuentes"] = [{"id": "f", "frase_origen": "Russian drones entered from Ukraine"}]
    assert _enlace(ruso) == ("EODI-UA-2025-0244", "fecha")


def test_el_enlace_va_en_los_dos_sentidos() -> None:
    ataque = {**NOCHE, "cruces": [{"pais": "RO", "numero": {"min": 1, "max": 1}}]}
    incidentes = [
        _incidente("EODI-2025-00216", "RO", "Dron ruso en Rumanía", "2025-09-12T23:00Z"),
        {**_incidente("EODI-2025-00217", "MD", "Dron ruso en Moldavia", "2025-09-12T23:30Z"),
         "drones": {"numero": {"min": 2, "max": 2}}},
    ]  # fmt: skip
    resultado = cruces.cruces_con_incidentes(ataque, incidentes)
    assert resultado == [
        {"pais": "RO", "numero": {"min": 1, "max": 1}, "incidentes": ["EODI-2025-00216"]},
        {"pais": "MD", "numero": {"min": 2, "max": 2}, "incidentes": ["EODI-2025-00217"]},
    ]
    # Los cruces se rehacen desde lo que declaró el parte: el de Moldavia desaparece si la
    # incursión deja de enlazarse.
    guardado = {**ataque, "cruces": resultado, "cruces_parte": ataque["cruces"]}
    assert cruces.cruces_con_incidentes(guardado, []) == ataque["cruces"]


def test_en_la_base_se_guarda_en_los_dos_sentidos() -> None:
    almacen = Almacen.abrir()
    almacen.guardar_ataque_ucrania(copy.deepcopy(NOCHE), AHORA)
    incidente = ejemplos.incidente_minimo()
    incidente.update(
        id="EODI-2025-00216", tipo="sobrevuelo",
        titulo={"es": "Dron ruso interceptado en Rumanía", "en": "Russian drone over Romania"},
        tiempo={"inicio": ejemplos.instante("2025-09-12T23:00Z", "hora")},
        lugar={"punto": {"lat": 45.17, "lon": 28.8}, "radio_km": 10, "pais": "RO"},
    )  # fmt: skip
    almacen.guardar_incidente(incidente, AHORA, MODELOS)
    resumen = cruces.enlazar(almacen, AHORA, MODELOS)
    assert resumen["incidentes_cambiados"] == resumen["ataques_cambiados"] == 1
    guardado = almacen.incidente("EODI-2025-00216")
    assert guardado is not None
    assert guardado["ataque"] == {
        "id": NOCHE["id"], "jornada": jornada(NOCHE["periodo"]), "por": "fecha",
    }  # fmt: skip
    ataque = almacen.ataques_ucrania()[0]
    assert ataque["cruces"] == [
        {"pais": "RO", "numero": "desconocido", "incidentes": ["EODI-2025-00216"]}
    ]
    assert any("enlazada" in str(h) for h in almacen.historial("EODI-2025-00216"))
    # Sin cambios, no se vuelve a guardar nada.
    assert cruces.enlazar(almacen, AHORA, MODELOS)["incidentes_cambiados"] == 0
