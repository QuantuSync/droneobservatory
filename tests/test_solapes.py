"""Tramos que se solapan del Ministerio de Defensa ruso: casos reales de la caché."""

from datetime import UTC, datetime

from esquema import Documento
from proceso import solapes
from proceso.solapes import INCLUIDO_EN, SOLAPADO_CON
from tests.test_mindef import almacen_con_partes

AHORA = datetime(2026, 9, 28, tzinfo=UTC)


def ataque(
    n: int,
    inicio: str,
    fin: str,
    derribados: int,
    publicado: str,
    precision_inicio: str = "minuto",
    precision_fin: str = "minuto",
    regiones: dict[str, int] | None = None,
) -> Documento:
    """Ataque mínimo con lo que mira la regla: periodo, derribos, regiones y publicación."""
    return {
        "id": f"EODI-UA-2025-{n:04d}",
        "sentido": "UA_RU",
        "periodo": {
            "inicio": {"valor": inicio, "precision": precision_inicio},
            "fin": {"valor": fin, "precision": precision_fin},
        },
        "derribados": {"min": derribados, "max": derribados},
        "regiones": [
            {"region": r, "derribados": {"min": v, "max": v}} for r, v in (regiones or {}).items()
        ],
        "fuentes": [{"fecha": {"valor": publicado, "precision": "minuto"}}],
    }


def enlaces(*ataques: Documento) -> dict[str, tuple[str, str]]:
    return solapes.enlaces([t for a in ataques if (t := solapes.tramo(a)) is not None])


# 51073 y 51077: tramo de 22.00 a 22.15 (5) y, después, el resumen de 20.00 a 06.00 (158).
TRAMO = ataque(1, "2025-04-08T19:00Z", "2025-04-08T19:15Z", 5, "2025-04-08T19:37Z",
               regiones={"RU-ROS": 4})  # fmt: skip
TOTAL = ataque(2, "2025-04-08T17:00Z", "2025-04-09T03:00Z", 158, "2025-04-09T04:04Z",
               regiones={"RU-KDA": 67, "RU-ROS": 29})  # fmt: skip


def test_el_total_cuenta_y_el_tramo_queda_enlazado() -> None:
    assert enlaces(TRAMO, TOTAL) == {TRAMO["id"]: (INCLUIDO_EN, TOTAL["id"])}


def test_no_es_total_si_una_region_del_tramo_supera_a_la_del_total() -> None:
    menor = ataque(2, "2025-04-08T17:00Z", "2025-04-09T03:00Z", 158, "2025-04-09T04:04Z",
                   regiones={"RU-KDA": 155, "RU-ROS": 3})  # fmt: skip
    # Un solape de 15 minutos es el redondeo entre tramos: se suman los dos.
    assert enlaces(TRAMO, menor) == {}


def test_no_es_total_si_se_publico_antes_que_el_tramo() -> None:
    posterior = {**TRAMO, "fuentes": [{"fecha": {"valor": "2025-04-09T05:00Z"}}]}
    assert enlaces(posterior, TOTAL) == {}


def test_tramos_que_se_solapan_una_hora_cuenta_el_de_mas_derribos() -> None:
    # 54393 (de 23.00 a 7.00, 94) y 54394 (de 6.00 a 8.00, 12).
    noche = ataque(3, "2025-07-04T20:00Z", "2025-07-05T04:00Z", 94, "2025-07-05T04:54Z")
    manana = ataque(4, "2025-07-05T03:00Z", "2025-07-05T05:00Z", 12, "2025-07-05T06:19Z")
    assert enlaces(noche, manana) == {manana["id"]: (SOLAPADO_CON, noche["id"])}


def test_el_redondeo_de_la_frontera_no_es_solape() -> None:
    # 52931 (de 20.00 a 4.05, 127) y 52932 (de 4.00 a 8.00, 32).
    noche = ataque(5, "2025-05-20T17:00Z", "2025-05-21T01:05Z", 127, "2025-05-21T04:27Z")
    manana = ataque(6, "2025-05-21T01:00Z", "2025-05-21T05:00Z", 32, "2025-05-21T05:01Z")
    assert enlaces(noche, manana) == {}


def test_una_noche_sin_horas_no_cubre_el_tramo_de_la_tarde() -> None:
    # 37773 (de 21.00 a 22.00, 3) y 37778 («в течение прошедшей ночи», 50).
    tarde = ataque(7, "2024-04-19T18:00Z", "2024-04-19T19:00Z", 3, "2024-04-19T19:50Z")
    noche = ataque(8, "2024-04-19T17:00Z", "2024-04-20T04:14Z", 50, "2024-04-20T04:14Z",
                   "aproximada", "aproximada")  # fmt: skip
    assert enlaces(tarde, noche) == {}


def test_un_parte_con_solo_el_inicio_cubre_hasta_su_publicacion() -> None:
    # «В 14.05 мск» (1) dentro de «с 13.00 мск», publicado a las 17.30.
    punto = ataque(9, "2025-12-02T11:05Z", "2025-12-02T11:05Z", 1, "2025-12-02T11:30Z")
    tarde = ataque(10, "2025-12-02T10:00Z", "2025-12-02T14:30Z", 6, "2025-12-02T14:30Z",
                   precision_fin="aproximada")  # fmt: skip
    assert enlaces(punto, tarde) == {punto["id"]: (INCLUIDO_EN, tarde["id"])}


def test_enlazar_guarda_los_cambios_en_el_historial_y_es_estable() -> None:
    almacen = almacen_con_partes()
    assert solapes.enlazar(almacen, "UA_RU", AHORA) == 1
    tramo, total = almacen.ataques_ucrania()
    assert tramo[INCLUIDO_EN] == total["id"]
    assert solapes.derribados_contados([tramo, total]) == total["derribados"]["min"]
    assert almacen.historial(tramo["id"])[-1]["operacion"] == "cambio"
    assert solapes.enlazar(almacen, "UA_RU", AHORA) == 0
