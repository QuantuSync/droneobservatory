"""Comprobación de salud de la recogida horaria y de su reloj, sin red."""

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from recogida import salud

AHORA = datetime(2026, 9, 30, 14, 0, tzinfo=UTC)


def _fecha(hace: timedelta) -> str:
    return f"{AHORA - hace:%Y-%m-%dT%H:%M:%SZ}"


def ejecuciones(*hace: timedelta) -> str:
    """La salida de `gh run list --json updatedAt` con ejecuciones terminadas hace tanto."""
    return json.dumps([{"updatedAt": _fecha(h)} for h in hace])


def relojes(*turnos: tuple[str, timedelta]) -> str:
    """La salida de `gh run list --json status,updatedAt` del reloj."""
    return json.dumps([{"status": estado, "updatedAt": _fecha(hace)} for estado, hace in turnos])


# --- Recogida -------------------------------------------------------------------------


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


# --- Reloj ----------------------------------------------------------------------------


@pytest.mark.parametrize("estado", ["in_progress", "queued", "pending"])
def test_con_un_reloj_en_marcha_o_en_cola_esta_bien(estado: str) -> None:
    texto = relojes((estado, timedelta(minutes=5)), ("completed", timedelta(hours=9)))
    assert salud.estado_reloj(texto, AHORA) == (True, "El reloj de la recogida está en marcha.")


def test_sin_reloj_pero_con_uno_reciente_esta_bien() -> None:
    texto = relojes(("completed", salud.MAX_SIN_RELOJ), ("completed", timedelta(hours=9)))
    al_dia, frase = salud.estado_reloj(texto, AHORA)
    assert al_dia
    assert frase == "El reloj de la recogida no está en marcha; el último acabó hace 2.0 h."


def test_sin_reloj_desde_hace_mas_de_dos_horas_se_senala() -> None:
    texto = relojes(("completed", salud.MAX_SIN_RELOJ + timedelta(minutes=30)))
    al_dia, frase = salud.estado_reloj(texto, AHORA)
    assert not al_dia
    assert "el último acabó hace 2.5 h: más de 2 h." in frase


def test_sin_ningun_reloj_nunca_se_senala() -> None:
    al_dia, frase = salud.estado_reloj("[]", AHORA)
    assert not al_dia
    assert "no consta que lo haya estado" in frase


@pytest.mark.parametrize("texto", ["", "no es json", '[{"otra": 1}]', '{"a": 1}'])
def test_sin_datos_del_reloj_no_se_sabe(texto: str) -> None:
    al_dia, frase = salud.estado_reloj(texto, AHORA)
    assert not al_dia
    assert "No se ha podido saber" in frase


# --- Informe --------------------------------------------------------------------------


def consultas(tmp_path: Path, recogida: str, reloj: str) -> list[str]:
    (tmp_path / "recogida.json").write_text(recogida, encoding="utf-8")
    (tmp_path / "reloj.json").write_text(reloj, encoding="utf-8")
    return ["--recogida", str(tmp_path / "recogida.json"), "--reloj", str(tmp_path / "reloj.json")]


def test_escribe_el_resumen_y_anota_los_avisos_sin_fallar(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    resumen = tmp_path / "resumen.md"
    monkeypatch.setenv(salud.VARIABLE_RESUMEN, str(resumen))
    bien = consultas(
        tmp_path, ejecuciones(timedelta(hours=1)), relojes(("in_progress", timedelta(0)))
    )
    assert salud.principal(bien, AHORA) == 0
    assert salud.ANOTACION_AVISO not in capsys.readouterr().out
    mal = consultas(
        tmp_path, ejecuciones(timedelta(hours=7)), relojes(("completed", timedelta(hours=3)))
    )
    assert salud.principal(mal, AHORA) == 0
    avisos = capsys.readouterr().out.splitlines()
    assert len(avisos) == 2
    assert all(linea.startswith(salud.ANOTACION_AVISO) for linea in avisos)
    al_dia, atrasada = resumen.read_text(encoding="utf-8").split(salud.TITULO)[1:]
    assert al_dia.count("✅") == 2 and "hace 1.0 h" in al_dia and "está en marcha" in al_dia
    assert atrasada.count("⚠️") == 2
    assert "hace 7.0 h: más de 6 h" in atrasada and "hace 3.0 h: más de 2 h" in atrasada


def test_una_consulta_que_no_dejo_fichero_cuenta_como_no_se_sabe(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv(salud.VARIABLE_RESUMEN, raising=False)
    faltan = ["--recogida", str(tmp_path / "no.json"), "--reloj", str(tmp_path / "tampoco.json")]
    assert salud.principal(faltan, AHORA) == 0
    avisos = capsys.readouterr().out.splitlines()
    assert [linea.startswith(salud.ANOTACION_AVISO) for linea in avisos] == [True, True]
