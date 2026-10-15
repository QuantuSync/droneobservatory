import os
from pathlib import Path

import pytest

from almacen import sitio


@pytest.fixture(autouse=True)
def base_en_modo_github(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Las pruebas no leen el interruptor de la máquina ni tocan su carpeta de la base."""
    monkeypatch.setenv(sitio.VARIABLE_MODO, sitio.GITHUB)
    monkeypatch.setenv(sitio.VARIABLE_DIRECTORIO, str(tmp_path / "base-disco"))


# Los buckets privados no llevan su nombre en el repositorio (almacen/buckets.py): en las pruebas,
# unos de mentira.
BUCKETS_PRUEBA = {
    "EODI_BUCKET_BASE": "prueba-base",
    "EODI_BUCKET_ARCHIVO": "prueba-archivo",
    "EODI_BUCKET_EXPORTACIONES": "prueba-exportaciones",
    "EODI_BUCKET_REPLICA": "prueba-replica",
}
# También al cargar: hay pruebas que leen la configuración al importarse.
os.environ.update(BUCKETS_PRUEBA)
# El correo del autor tampoco está en el repositorio (recogida/licencia.py).
CORREO_PRUEBA = "autor@ejemplo.org"
os.environ["EODI_CORREO_AUTOR"] = CORREO_PRUEBA


@pytest.fixture(autouse=True)
def buckets_de_prueba(monkeypatch: pytest.MonkeyPatch) -> None:
    for variable, nombre in BUCKETS_PRUEBA.items():
        monkeypatch.setenv(variable, nombre)
