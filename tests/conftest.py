from pathlib import Path

import pytest

from almacen import sitio


@pytest.fixture(autouse=True)
def base_en_modo_github(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Las pruebas no leen el interruptor de la máquina ni tocan su carpeta de la base."""
    monkeypatch.setenv(sitio.VARIABLE_MODO, sitio.GITHUB)
    monkeypatch.setenv(sitio.VARIABLE_DIRECTORIO, str(tmp_path / "base-disco"))
