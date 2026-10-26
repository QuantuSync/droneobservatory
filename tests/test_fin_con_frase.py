"""Un fin que ninguna frase escribe no se publica (proceso/fechas.fin_escrito, auditoría O):
EODI-2025-00154 y EODI-2026-00112, 26 de octubre de 2026."""

from datetime import UTC, datetime
from typing import Any
from zoneinfo import ZoneInfo

from proceso import fechas
from proceso.textos_dron import duraciones, horas_escritas

CHISINAU = ZoneInfo("Europe/Chisinau")
COPENHAGUE = ZoneInfo("Europe/Copenhagen")
FRASE_ORHEI = (
    "Aparatul a fost monitorizat până la ora 22:03, moment în care a dispărut de pe radar în "
    "zona raionului Orhei."
)


def _utc(texto: str) -> datetime:
    return datetime.fromisoformat(texto).replace(tzinfo=UTC)


def test_la_hora_local_de_la_frase_respalda_su_utc_y_no_otra() -> None:
    inicio = _utc("2026-03-30T18:29")
    assert fechas.fin_escrito(FRASE_ORHEI, "ro", _utc("2026-03-30T19:03"), inicio, CHISINAU)
    # 20:03 UTC era la hora de Moldavia tomada como UTC+2: ninguna frase la escribe.
    assert not fechas.fin_escrito(FRASE_ORHEI, "ro", _utc("2026-03-30T20:03"), inicio, CHISINAU)


def test_una_duracion_respalda_el_fin_que_da_desde_el_inicio() -> None:
    frase = "pendant quatre heures lundi soir 22 septembre"
    inicio = _utc("2025-09-22T18:30")
    assert fechas.fin_escrito(frase, "fr", _utc("2025-09-22T22:30"), inicio, COPENHAGUE)
    assert not fechas.fin_escrito(frase, "fr", _utc("2025-09-22T23:00"), inicio, COPENHAGUE)


def test_formas_de_escribir_horas_y_duraciones() -> None:
    assert horas_escritas("tra le 19 e le 21 di venerdì sera") == [(19, 0), (21, 0)]
    assert horas_escritas("operacijos atnaujintos apie 00.35 val.") == [(0, 35)]
    assert (0, 0) in horas_escritas("bis zum Beginn des Nachtflugverbots um Mitternacht")
    assert duraciones("suspendido durante treinta minutos", "es") == [30]
    assert duraciones("een half uur stilgelegd", "nl") == [30]
    assert 150 in duraciones("Observerte droner i to og en halv time", "no")
    assert duraciones("gut vier Stunden lang keine Flüge", "de") == [240]
    assert duraciones("Gardaí investigating sighting of large drone", "en") == []


def _ficha(fin: str, frase: str) -> dict[str, Any]:
    return {
        "id": "EODI-2025-00154",
        "lugar": {"pais": "DK", "punto": {"lat": 55.618, "lon": 12.656}},
        "tiempo": {
            "inicio": {"valor": "2025-09-22T18:30Z", "precision": "minuto"},
            "fin": {"valor": fin, "precision": "minuto"},
            "duracion_min": 270,
        },
        "fuentes": [
            {"id": "f1", "idioma": "de", "frase_origen": frase, "campos_respaldados": ["fin"]},
            {"id": "f2", "idioma": "de", "frase_origen": "Drohnen über dem Flughafen"},
        ],
        "afirmaciones": [
            {"campo": "fin", "valor": fin.rstrip("Z"), "fuente_id": "f1"},
            {"campo": "fin", "valor": "2025-09-23T06:00", "fuente_id": "f2"},
            {"campo": "tipo", "valor": "sobrevuelo", "fuente_id": "f2"},
        ],
    }


def test_sin_frase_se_quitan_el_fin_su_duracion_y_sus_afirmaciones() -> None:
    ficha = _ficha("2025-09-22T23:00Z", "gut vier Stunden lang keine Flüge")
    assert fechas.fines_sin_frase(ficha)
    limpia = fechas.sin_fin_sin_frase(ficha)
    assert "fin" not in limpia["tiempo"] and "duracion_min" not in limpia["tiempo"]
    assert [a["campo"] for a in limpia["afirmaciones"]] == ["tipo"]
    assert not fechas.fines_sin_frase(limpia)


def test_con_frase_el_fin_se_queda() -> None:
    ficha = _ficha("2025-09-22T22:30Z", "gut vier Stunden lang keine Flüge")
    limpia = fechas.sin_fin_sin_frase(ficha)
    assert limpia["tiempo"]["fin"]["valor"] == "2025-09-22T22:30Z"
    # La afirmación de las 06:00 de una frase que no da ninguna hora sí se va.
    assert [a["valor"] for a in limpia["afirmaciones"] if a["campo"] == "fin"] == [
        "2025-09-22T22:30"
    ]
