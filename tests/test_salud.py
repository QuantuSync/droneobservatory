"""Comprobación de salud de la recogida horaria, sin red."""

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from recogida import salud

AHORA = datetime(2026, 9, 30, 14, 0, tzinfo=UTC)


def ejecuciones(*hace: timedelta) -> str:
    """La salida de `gh run list --json updatedAt` con ejecuciones terminadas hace tanto."""
    return json.dumps([{"updatedAt": f"{AHORA - h:%Y-%m-%dT%H:%M:%SZ}"} for h in hace])


def test_la_ultima_correcta_es_la_mas_reciente() -> None:
    texto = ejecuciones(timedelta(hours=9), timedelta(hours=2))
    assert salud.ultima_correcta(texto) == AHORA - timedelta(hours=2)


@pytest.mark.parametrize("texto", ["", "[]", "no es json", '[{"otra": 1}]', '{"a": 1}'])
def test_sin_datos_no_se_sabe(texto: str) -> None:
    assert salud.ultima_correcta(texto) is None
    al_dia, frase = salud.estado(None, AHORA)
    assert not al_dia
    assert "No se ha podido saber" in frase


def test_dentro_del_margen_esta_al_dia() -> None:
    al_dia, frase = salud.estado(AHORA - salud.MAX_SIN_RECOGIDA, AHORA)
    assert al_dia
    assert frase == "La última ejecución correcta terminó el 2026-09-30 08:00 UTC, hace 6.0 h."


def test_pasado_el_margen_se_senala() -> None:
    ultima = AHORA - salud.MAX_SIN_RECOGIDA - timedelta(minutes=30)
    al_dia, frase = salud.estado(ultima, AHORA)
    assert not al_dia
    assert "2026-09-30 07:30 UTC, hace 6.5 h: más de 6 h" in frase


def test_escribe_el_resumen_y_anota_el_aviso_sin_fallar(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    resumen = tmp_path / "resumen.md"
    monkeypatch.setenv(salud.VARIABLE_RESUMEN, str(resumen))
    assert salud.principal(ejecuciones(timedelta(hours=1)), AHORA) == 0
    assert not capsys.readouterr().out.startswith(salud.ANOTACION_AVISO)
    assert salud.principal(ejecuciones(timedelta(hours=7)), AHORA) == 0
    assert capsys.readouterr().out.startswith(salud.ANOTACION_AVISO)
    al_dia, atrasada = resumen.read_text(encoding="utf-8").split(salud.TITULO)[1:]
    assert "✅" in al_dia and "hace 1.0 h" in al_dia
    assert "⚠️" in atrasada and "hace 7.0 h: más de 6 h" in atrasada


def test_sin_fichero_de_resumen_solo_escribe_en_el_registro(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv(salud.VARIABLE_RESUMEN, raising=False)
    assert salud.principal("", AHORA) == 0
    assert capsys.readouterr().out.startswith(salud.ANOTACION_AVISO)
