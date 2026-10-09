"""Los ficheros publicados se escriben de una vez: se lee el anterior o el nuevo, entero."""

import os
from pathlib import Path

import pytest

from exportacion import proyeccion


def test_escribe_entero_y_sin_dejar_temporales(tmp_path: Path) -> None:
    ruta = tmp_path / "prevision.json"
    ruta.write_text('{"viejo": true}\n', encoding="utf-8")
    proyeccion.escribir({"nuevo": True}, ruta)
    assert ruta.read_text(encoding="utf-8") == '{\n "nuevo": true\n}\n'
    assert [p.name for p in tmp_path.iterdir()] == ["prevision.json"]


def test_si_falla_a_mitad_queda_el_anterior(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ruta = tmp_path / "prevision.json"
    ruta.write_text('{"viejo": true}\n', encoding="utf-8")

    def cortar(*_: object, **__: object) -> None:
        raise OSError("disco lleno")

    monkeypatch.setattr(os, "replace", cortar)
    with pytest.raises(OSError):
        proyeccion.escribir({"nuevo": True}, ruta)
    assert ruta.read_text(encoding="utf-8") == '{"viejo": true}\n'
    assert [p.name for p in tmp_path.iterdir()] == ["prevision.json"]
