"""Comprobación de salud de la recogida horaria por la fecha de la rama estado, sin red."""

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from recogida import salud

AHORA = datetime(2026, 9, 30, 14, 0, tzinfo=UTC)


def fecha(hace: timedelta) -> str:
    """La salida de `git log -1 --format=%cI` de un commit hecho hace tanto."""
    return f"{(AHORA - hace).isoformat()}\n"


def consulta(tmp_path: Path, texto: str) -> list[str]:
    (tmp_path / "estado.txt").write_text(texto, encoding="utf-8")
    return ["--estado", str(tmp_path / "estado.txt")]


def test_lee_la_fecha_del_commit() -> None:
    assert salud.ultimo_estado(fecha(timedelta(hours=1))) == AHORA - timedelta(hours=1)


def test_una_fecha_con_otra_zona_horaria_se_lleva_a_utc() -> None:
    assert salud.ultimo_estado("2026-09-30T15:00:00+02:00\n") == AHORA - timedelta(hours=1)


@pytest.mark.parametrize("texto", ["", "\n", "no es una fecha", "2026-09-30T13:00:00"])
def test_sin_fecha_no_se_sabe(texto: str) -> None:
    assert salud.ultimo_estado(texto) is None
    al_dia, frase = salud.estado(None, AHORA)
    assert not al_dia
    assert "No se ha podido saber" in frase


def test_dentro_del_margen_esta_al_dia() -> None:
    al_dia, frase = salud.estado(AHORA - salud.MAX_SIN_ESTADO, AHORA)
    assert al_dia
    assert frase == (
        "La rama estado se actualizó por última vez el 2026-09-30 12:00 UTC, hace 2.0 h."
    )


def test_pasado_el_margen_se_senala() -> None:
    ultimo = AHORA - salud.MAX_SIN_ESTADO - timedelta(minutes=30)
    al_dia, frase = salud.estado(ultimo, AHORA)
    assert not al_dia
    assert "2026-09-30 11:30 UTC, hace 2.5 h: más de 2 h." in frase


def test_escribe_el_resumen_y_anota_el_aviso_sin_fallar(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    resumen = tmp_path / "resumen.md"
    monkeypatch.setenv(salud.VARIABLE_RESUMEN, str(resumen))
    assert salud.principal(consulta(tmp_path, fecha(timedelta(hours=1))), AHORA) == 0
    assert salud.ANOTACION_AVISO not in capsys.readouterr().out
    assert salud.principal(consulta(tmp_path, fecha(timedelta(hours=3))), AHORA) == 0
    avisos = capsys.readouterr().out.splitlines()
    assert len(avisos) == 1
    assert avisos[0].startswith(salud.ANOTACION_AVISO)
    al_dia, atrasada = resumen.read_text(encoding="utf-8").split(salud.TITULO)[1:]
    assert "✅" in al_dia and "hace 1.0 h." in al_dia
    assert "⚠️" in atrasada and "hace 3.0 h: más de 2 h." in atrasada


def test_una_consulta_que_no_dejo_fichero_cuenta_como_no_se_sabe(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv(salud.VARIABLE_RESUMEN, raising=False)
    assert salud.principal(["--estado", str(tmp_path / "no.txt")], AHORA) == 0
    avisos = capsys.readouterr().out.splitlines()
    assert len(avisos) == 1
    assert avisos[0].startswith(salud.ANOTACION_AVISO)
    assert "No se ha podido saber" in avisos[0]
