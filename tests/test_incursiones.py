"""Un cruce que cuenta solo el parte ucraniano no es un incidente europeo, y enlazar un incidente
con su ataque nunca crea otro (docs/informe_errores_datos.md, cruces sin copias)."""

import copy
from datetime import UTC, datetime
from typing import Any

from almacen.base import Almacen
from exportacion.geojson import publicables
from proceso import cita_titular, cruces, incursiones
from proceso.ataques import incorporar
from recogida.ejecucion import configuracion_fuente
from recogida.fuerza_aerea import FUENTE
from recogida.parte import leer
from recogida.telegram import Publicacion
from tests import ejemplos

AHORA = datetime(2026, 10, 4, 15, 0, tzinfo=UTC)
MODELOS = frozenset({"shahed_geran", "gerbera_senuelos", "otros"})
FECHA = datetime(2025, 1, 30, 6, 0, tzinfo=UTC)
ARRANQUE = "У ніч на 30 січня 2025 року противник атакував 81 ударним БпЛА типу Shahed"
PARTE = (
    "У ніч на 30 січня 2025 року (з 18:00 29 січня) противник атакував 81 ударним БпЛА типу "
    "Shahed із напрямків: Курськ – рф.\nСтаном на 09:00, збито 46 ворожих БпЛА. "
    "{cruce}"
)
CRUCE_RO = "Один безпілотник увійшов в повітряний простір Румунії."


def _parte(almacen: Almacen, cruce: str = "") -> dict[str, Any]:
    texto = PARTE.format(cruce=cruce)
    publicacion = Publicacion("kpszsu", 41000, FECHA, texto)
    incorporar(almacen, publicacion, leer(texto, FECHA), configuracion_fuente(FUENTE.id), texto,
               AHORA, FUENTE.perfil)  # fmt: skip
    (ataque,) = almacen.ataques_ucrania()
    return ataque


def _borcea(id_: str = "EODI-2025-00378") -> dict[str, Any]:
    """La incursión de Borcea, con su fuente rumana y su lugar."""
    incidente = ejemplos.incidente_minimo()
    incidente.update(
        id=id_, tipo="sobrevuelo",
        titulo={"es": "Drones rusos cerca de la base aérea de Borcea provocan el despegue de "
                      "cazas", "en": "Russian drones near Borcea air base scramble jets"},
        tiempo={"inicio": ejemplos.instante("2025-01-30T00:00Z", "dia")},
        lugar={"punto": {"lat": 44.38, "lon": 27.73}, "radio_km": 10, "pais": "RO"},
        pruebas={"dron_estatal": True, "entrada_exterior": True, "evidencia": []},
    )  # fmt: skip
    incidente["fuentes"][0]["frase_origen"] = (
        "Drone rusești în apropierea bazei aeriene Borcea au determinat decolarea avioanelor"
    )
    return incidente


def _copia_del_parte(ataque: dict[str, Any], id_: str = "EODI-2025-00417") -> dict[str, Any]:
    """Como las guardaba la versión anterior: el parte como única fuente y su arranque como
    cita."""
    fuente = copy.deepcopy(ataque["fuentes"][-1])
    fuente.update(frase_origen=ARRANQUE, campos_respaldados=["tipo", "drones.numero", "lugar.pais"],
                  interna_fuera_de_ucrania=False, publica=True)  # fmt: skip
    return {
        "id": id_, "tipo": "incursion", "origen_demostrado_por": ["rastreo"],
        "estado": {"actual": "notificado", "historial": [
            {"estado": "notificado", "fecha": fuente["fecha"], "fuente_id": fuente["id"]}]},
        "titulo": {"es": "Drones del ataque ruso contra Ucrania cruzan a Rumanía",
                   "en": "Drones from the Russian attack on Ukraine cross into Romania"},
        "presencia_dron": "confirmada",
        "tiempo": {"inicio": ataque["periodo"]["inicio"], "fin": ataque["periodo"]["fin"]},
        "lugar": {"pais": "RO", "nivel": "pais"},
        "drones": {"numero": {"min": 1, "max": 1}},
        "pruebas": {"dron_estatal": True, "entrada_exterior": True, "evidencia": ["rastreo"]},
        "fuentes": [fuente],
        "control": {"alta": ejemplos.instante("2026-10-04T12:20Z"),
                    "ultima_actualizacion": ejemplos.instante("2026-10-04T12:20Z"),
                    "version_extractor": "incursion/2"},
    }  # fmt: skip


def _recogida(almacen: Almacen) -> None:
    """Los dos pasos de la recogida horaria, en su orden, dos veces: la segunda vuelta es la
    que creaba las copias."""
    for _ in range(2):
        incursiones.retirar(almacen, AHORA, MODELOS)
        cruces.enlazar(almacen, AHORA, MODELOS)


def test_enlazar_un_incidente_con_su_ataque_no_crea_ninguno() -> None:
    almacen = Almacen.abrir()
    _parte(almacen)
    almacen.guardar_incidente(_borcea(), AHORA, MODELOS)
    _recogida(almacen)
    assert [i["id"] for i in almacen.incidentes()] == ["EODI-2025-00378"]
    (ataque,) = almacen.ataques_ucrania()
    assert ataque["cruces"] == [
        {"pais": "RO", "numero": "desconocido", "incidentes": ["EODI-2025-00378"]}
    ]


def test_un_cruce_solo_ucraniano_queda_en_el_ataque_y_no_en_el_total() -> None:
    almacen = Almacen.abrir()
    ataque = _parte(almacen, CRUCE_RO)
    # La cita del cruce es la frase que lo dice, no el arranque del parte.
    assert ataque["cruces"] == [{"pais": "RO", "numero": {"min": 1, "max": 1},
                                 "frase": CRUCE_RO}]  # fmt: skip
    _recogida(almacen)
    assert almacen.incidentes() == []
    assert publicables(almacen.incidentes(), AHORA, MODELOS) == []
    (ataque,) = almacen.ataques_ucrania()
    assert ataque["cruces"][0]["frase"] == CRUCE_RO
    assert "incidentes" not in ataque["cruces"][0]


def test_la_copia_de_borcea_se_retira_y_el_enlace_queda_en_el_bueno() -> None:
    almacen = Almacen.abrir()
    ataque = _parte(almacen)
    almacen.guardar_incidente(_borcea(), AHORA, MODELOS)
    copia = _copia_del_parte(ataque)
    copia["ataque"] = {"id": ataque["id"], "jornada": {"tipo": "noche", "desde": "2025-01-29",
                       "hasta": "2025-01-30"}, "por": "fuente"}  # fmt: skip
    almacen.guardar_incidente(copia, AHORA, MODELOS)
    # Su cita no nombra Rumanía: no respalda el titular.
    assert not cita_titular.respalda(copia)
    assert cita_titular.respalda(_borcea())
    _recogida(almacen)
    retirada = almacen.incidente("EODI-2025-00417")
    assert retirada is not None
    assert retirada["retirado"]["motivo"].startswith("duplicado de EODI-2025-00378")
    assert "queda en EODI-2025-00378" in retirada["retirado"]["motivo"]
    buena = almacen.incidente("EODI-2025-00378")
    assert buena is not None and "retirado" not in buena
    assert buena["ataque"]["id"] == ataque["id"]
    (ataque,) = almacen.ataques_ucrania()
    assert ataque["cruces"] == [
        {"pais": "RO", "numero": "desconocido", "incidentes": ["EODI-2025-00378"]}
    ]
    assert [i["id"] for i in publicables(almacen.incidentes(), AHORA, MODELOS)] == [
        "EODI-2025-00378"
    ]


def test_sin_pareja_queda_como_cruce_declarado_si_el_parte_lo_dice() -> None:
    almacen = Almacen.abrir()
    ataque = _parte(almacen, CRUCE_RO)
    almacen.guardar_incidente(_copia_del_parte(ataque, "EODI-2024-00001"), AHORA, MODELOS)
    _recogida(almacen)
    retirada = almacen.incidente("EODI-2024-00001")
    assert retirada is not None
    assert retirada["retirado"]["motivo"].startswith("cruce declarado solo por Ucrania")
    (ataque,) = almacen.ataques_ucrania()
    assert ataque["cruces"] == [{"pais": "RO", "numero": {"min": 1, "max": 1},
                                 "frase": CRUCE_RO}]  # fmt: skip


def test_sin_pareja_y_sin_cruce_en_el_parte_se_retira() -> None:
    almacen = Almacen.abrir()
    ataque = _parte(almacen)
    almacen.guardar_incidente(_copia_del_parte(ataque), AHORA, MODELOS)
    _recogida(almacen)
    retirada = almacen.incidente("EODI-2025-00417")
    assert retirada is not None
    assert retirada["retirado"]["motivo"].startswith("el parte no dice que hubiera un cruce")


def test_la_frase_de_los_partes_guardados_antes() -> None:
    ataque = {"fuentes": [{"id": "kpszsu-20107"}],
              "cruces_parte": [{"pais": "RO", "numero": {"min": 1, "max": 1}}]}  # fmt: skip
    (cruce,) = cruces.cruces_del_parte(ataque)
    assert "повітряний простір Румунії" in cruce["frase"]
