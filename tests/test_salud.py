"""Salud de la recogida horaria según estado.json, sin red."""

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from recogida import salud

AHORA = datetime(2026, 9, 30, 14, 0, tzinfo=UTC)


def estado(ultima_correcta: timedelta | None, resultado: str = "correcta") -> dict[str, object]:
    fin = (AHORA - timedelta(minutes=30)).strftime("%Y-%m-%dT%H:%MZ")
    correcta = (AHORA - ultima_correcta).strftime("%Y-%m-%dT%H:%MZ") if ultima_correcta else None
    return {"version": 1, "fin": fin, "resultado": resultado, "ultima_correcta": correcta}


class Bucket:
    """Responde lo preparado, en orden; una excepción es un intento fallido."""

    def __init__(self, *respuestas: bytes | Exception) -> None:
        self.respuestas = list(respuestas)
        self.pedidas = 0
        self.esperas: list[float] = []

    def leer(self, _url: str) -> bytes:
        self.pedidas += 1
        respuesta = self.respuestas.pop(0)
        if isinstance(respuesta, Exception):
            raise respuesta
        return respuesta

    def dormir(self, segundos: float) -> None:
        self.esperas.append(segundos)


def publicado(documento: dict[str, object]) -> bytes:
    return json.dumps(documento).encode()


def test_estado_reciente_no_es_problema() -> None:
    al_dia, frase = salud.diagnostico(estado(timedelta(minutes=30)), AHORA)
    assert al_dia
    assert "hace 0.5 h" in frase


def test_estado_antiguo_es_problema() -> None:
    al_dia, frase = salud.diagnostico(estado(timedelta(hours=3)), AHORA)
    assert not al_dia
    assert "más de 2 h" in frase


def test_una_recogida_fallida_con_una_correcta_reciente_no_es_problema() -> None:
    assert salud.diagnostico(estado(timedelta(hours=1), "fallida"), AHORA)[0]


def test_recogidas_fallidas_durante_mas_de_dos_horas_son_problema() -> None:
    assert not salud.diagnostico(estado(timedelta(hours=2, minutes=5), "fallida"), AHORA)[0]
    assert not salud.diagnostico(estado(None, "fallida"), AHORA)[0]


def test_fichero_ausente_tras_tres_intentos_espaciados() -> None:
    bucket = Bucket(OSError("404"), OSError("404"), OSError("404"))
    assert salud.leer_estado(leer=bucket.leer, dormir=bucket.dormir) is None
    assert bucket.pedidas == salud.INTENTOS
    assert bucket.esperas == [salud.PAUSA_S] * (salud.INTENTOS - 1)
    al_dia, frase = salud.diagnostico(None, AHORA)
    assert not al_dia
    assert "no responde" in frase


def test_un_fallo_pasajero_no_es_problema() -> None:
    bucket = Bucket(OSError("corte"), b"no es json", publicado(estado(timedelta(minutes=5))))
    leido = salud.leer_estado(leer=bucket.leer, dormir=bucket.dormir)
    assert leido is not None
    assert salud.diagnostico(leido, AHORA)[0]


@pytest.mark.parametrize(("hace", "problema"), [(timedelta(minutes=40), "false"),
                                                (timedelta(hours=5), "true")])  # fmt: skip
def test_la_salida_del_trabajo_dice_si_hay_problema(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, hace: timedelta, problema: str
) -> None:
    salida, resumen = tmp_path / "salida", tmp_path / "resumen"
    monkeypatch.setenv(salud.VARIABLE_SALIDA, str(salida))
    monkeypatch.setenv(salud.VARIABLE_RESUMEN, str(resumen))
    bucket = Bucket(publicado(estado(hace)))
    assert salud.principal([], AHORA, bucket.leer, bucket.dormir) == 0
    lineas = salida.read_text(encoding="utf-8").splitlines()
    assert lineas[0] == f"problema={problema}"
    assert lineas[1].startswith("mensaje=La última recogida")
    assert salud.TITULO in resumen.read_text(encoding="utf-8")
