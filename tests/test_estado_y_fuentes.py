"""Estado del sistema (estado.json) y quién dice qué (afirmaciones públicas por fuente)."""

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from exportacion.afirmaciones import afirmaciones_publicas
from exportacion.campos import CAMPOS_PUBLICOS_INCIDENTE
from exportacion.geojson import exportar
from exportacion.proyeccion import rutas
from recogida import estado
from tests import ejemplos
from tests.ejemplos import AHORA, VOCABULARIO_MODELOS

INICIO = datetime(2026, 9, 30, 18, 17, 3, tzinfo=UTC)
FIN = datetime(2026, 9, 30, 18, 24, 40, tzinfo=UTC)
MINUTO = 17


def parcial() -> dict[str, object]:
    def dato(hora: int, minuto: int = 0) -> datetime:
        return datetime(2026, 9, 30, hora, minuto, tzinfo=UTC)

    fuentes = {
        "fuerza_aerea_ua": estado.EstadoFuente(estado.LEIDA, dato(5, 1)),
        "mindef_ru": estado.EstadoFuente(estado.NO_LEIDA),
        "gdelt": estado.EstadoFuente(estado.LEIDA, dato(18)),
        "oficiales": estado.EstadoFuente(estado.CON_AVISO),
        "extractor": estado.EstadoFuente(estado.CON_AVISO, dato(17, 20)),
        "firms": estado.EstadoFuente(estado.LEIDA, dato(15, 17)),
        "airprox": estado.EstadoFuente(estado.LEIDA, dato(15, 5)),
        "parlamentos": estado.EstadoFuente(estado.CON_AVISO, dato(12, 5)),
        "ova_ua": estado.EstadoFuente(estado.CON_AVISO, dato(17, 52)),
        "estado_mayor_ua": estado.EstadoFuente(estado.LEIDA, dato(17, 52)),
        "gobernadores_ru": estado.EstadoFuente(estado.NO_LEIDA),
        "rosaviatsia": estado.EstadoFuente(estado.LEIDA, dato(17, 52)),
        "trafico_aereo": estado.EstadoFuente(estado.LEIDA, dato(4, 2)),
        "condiciones": estado.EstadoFuente(estado.NO_LEIDA, dato(17, 17)),
    }
    return {f: fuentes[f].documento(f) for f in fuentes}


def test_estado_de_una_recogida_correcta() -> None:
    documento = estado.componer(INICIO, FIN, 0, parcial(), None, MINUTO)
    assert documento == {
        "version": 1,
        "inicio": "2026-09-30T18:17Z",
        "fin": "2026-09-30T18:24Z",
        "resultado": "correcta",
        "ultima_correcta": "2026-09-30T18:24Z",
        "siguiente": "2026-09-30T19:17Z",
        "fuentes": [
            {"id": "fuerza_aerea_ua", "estado": "leida", "ultimo_dato": "2026-09-30T05:01Z"},
            {"id": "mindef_ru", "estado": "no_leida", "ultimo_dato": None},
            {"id": "gdelt", "estado": "leida", "ultimo_dato": "2026-09-30T18:00Z"},
            {"id": "oficiales", "estado": "con_aviso", "ultimo_dato": None},
            {"id": "extractor", "estado": "con_aviso", "ultimo_dato": "2026-09-30T17:20Z"},
            {"id": "firms", "estado": "leida", "ultimo_dato": "2026-09-30T15:17Z"},
            {"id": "airprox", "estado": "leida", "ultimo_dato": "2026-09-30T15:05Z"},
            {"id": "parlamentos", "estado": "con_aviso", "ultimo_dato": "2026-09-30T12:05Z"},
            # Las que la recogida no informa salen como no leídas.
            {"id": "investigaciones", "estado": "no_leida", "ultimo_dato": None},
            {"id": "estadisticas_oficiales", "estado": "no_leida", "ultimo_dato": None},
            {"id": "paginas_js", "estado": "no_leida", "ultimo_dato": None},
            {"id": "ova_ua", "estado": "con_aviso", "ultimo_dato": "2026-09-30T17:52Z"},
            {"id": "estado_mayor_ua", "estado": "leida", "ultimo_dato": "2026-09-30T17:52Z"},
            {"id": "gobernadores_ru", "estado": "no_leida", "ultimo_dato": None},
            {"id": "rosaviatsia", "estado": "leida", "ultimo_dato": "2026-09-30T17:52Z"},
            {"id": "trafico_aereo", "estado": "leida", "ultimo_dato": "2026-09-30T04:02Z"},
            {"id": "condiciones", "estado": "no_leida", "ultimo_dato": "2026-09-30T17:17Z"},
        ],
    }


@pytest.mark.parametrize(("codigo", "resultado"), [(2, "con_avisos"), (1, "fallida")])
def test_la_ultima_correcta_sale_del_estado_anterior(codigo: int, resultado: str) -> None:
    anterior = estado.componer(INICIO, FIN, 0, parcial(), None, MINUTO)
    despues = datetime(2026, 9, 30, 19, 20, tzinfo=UTC)
    documento = estado.componer(despues, despues, codigo, parcial(), anterior, MINUTO)
    assert documento["resultado"] == resultado
    assert documento["ultima_correcta"] == "2026-09-30T18:24Z"


def test_si_la_recogida_no_dejo_nada_las_fuentes_quedan_no_leidas_con_su_ultimo_dato() -> None:
    anterior = estado.componer(INICIO, FIN, 0, parcial(), None, MINUTO)
    documento = estado.componer(INICIO, FIN, 1, None, anterior, MINUTO)
    assert [f["id"] for f in documento["fuentes"]] == list(estado.FUENTES)
    assert {f["estado"] for f in documento["fuentes"]} == {"no_leida"}
    assert documento["fuentes"][0]["ultimo_dato"] == "2026-09-30T05:01Z"


def test_la_siguiente_es_la_del_minuto_de_la_hora_que_viene_si_ya_paso() -> None:
    assert estado.siguiente(datetime(2026, 9, 30, 18, 10, tzinfo=UTC), MINUTO) == datetime(
        2026, 9, 30, 18, 17, tzinfo=UTC
    )
    assert estado.siguiente(datetime(2026, 9, 30, 23, 30, tzinfo=UTC), MINUTO) == datetime(
        2026, 10, 1, 0, 17, tzinfo=UTC
    )


def test_la_orden_escribe_el_estado(tmp_path: Path) -> None:
    ruta_parcial, salida = tmp_path / "parcial.json", tmp_path / "estado.json"
    ruta_parcial.write_text(json.dumps(parcial()), encoding="utf-8")
    assert estado.principal([
        "--inicio", "2026-09-30T18:17:03Z", "--codigo", "0", "--parcial", str(ruta_parcial),
        "--anterior", str(tmp_path / "no-existe.json"), "--salida", str(salida),
        "--minuto", str(MINUTO),
    ]) == 0  # fmt: skip
    documento = json.loads(salida.read_text(encoding="utf-8"))
    assert documento["resultado"] == "correcta"
    assert documento["inicio"] == "2026-09-30T18:17Z"


# --- Quién dice qué --------------------------------------------------------------------


def con_afirmaciones() -> dict[str, object]:
    documento = ejemplos.incidente_minimo()
    documento["fuentes"] += [
        ejemplos.fuente("F2", "C"),
        ejemplos.fuente("F3", "E", publica=False),
        ejemplos.fuente("F4", "C", publica=False, interna_fuera_de_ucrania=True),
    ]
    documento["afirmaciones"] = [
        {"campo": "drones", "valor": {"min": 2, "max": 10}, "fuente_id": "F1",
         "confianza_extraccion": 0.9},
        {"campo": "inicio", "valor": "2025-11-04T18:00", "fuente_id": "F2",
         "confianza_extraccion": 0.9},
        {"campo": "inicio", "valor": "2025-11-04", "fuente_id": "F1", "confianza_extraccion": 0.8},
        {"campo": "cierre", "valor": "si", "fuente_id": "F3", "confianza_extraccion": 0.9},
        {"campo": "drones", "valor": {"min": 5, "max": 5}, "fuente_id": "F4",
         "confianza_extraccion": 0.9},
        {"campo": "es_incidente", "valor": True, "fuente_id": "F1", "confianza_extraccion": 1},
    ]  # fmt: skip
    return documento


def test_cada_fuente_publica_con_su_valor_en_el_formato_del_campo_publico() -> None:
    (feature,) = exportar([con_afirmaciones()], AHORA, VOCABULARIO_MODELOS)["features"]
    publicas = feature["properties"]["afirmaciones_publicas"]
    assert [(a["campo"], a["fuente_id"], a["valor"]) for a in publicas] == [
        ("drones.numero", "F1", {"min": 2, "max": 10}),
        ("tiempo.inicio", "F1", {"valor": "2025-11-04T00:00Z", "precision": "dia"}),
        ("tiempo.inicio", "F2", {"valor": "2025-11-04T18:00Z", "precision": "minuto"}),
    ]
    assert {a["fiabilidad"] for a in publicas} <= {"A", "B", "C", "D"}
    assert publicas[0]["medio"] == "Medio F1" and publicas[0]["credibilidad"] == 2


def test_nunca_fuentes_e_ni_f_ni_internas_fuera_de_ucrania() -> None:
    (feature,) = exportar([con_afirmaciones()], AHORA, VOCABULARIO_MODELOS)["features"]
    texto = json.dumps(feature["properties"]["afirmaciones_publicas"])
    assert '"F3"' not in texto and '"F4"' not in texto


def test_las_afirmaciones_estan_en_la_lista_cerrada() -> None:
    (feature,) = exportar([con_afirmaciones()], AHORA, VOCABULARIO_MODELOS)["features"]
    assert set(rutas(feature["properties"])) - CAMPOS_PUBLICOS_INCIDENTE == set()


def test_sin_afirmaciones_publicas_no_hay_campo() -> None:
    documento = ejemplos.incidente_minimo()
    assert afirmaciones_publicas(documento) == []
    (feature,) = exportar([documento], AHORA, VOCABULARIO_MODELOS)["features"]
    assert "afirmaciones_publicas" not in feature["properties"]
