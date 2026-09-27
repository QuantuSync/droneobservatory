"""La rama estado se prueba contra un repositorio git local: sin red."""

import subprocess
from pathlib import Path

import pytest

from almacen import remoto


def git(*argumentos: str, directorio: Path) -> str:
    return subprocess.run(
        ["git", *argumentos], cwd=directorio, capture_output=True, text=True, check=True
    ).stdout


@pytest.fixture
def desnudo(tmp_path: Path) -> Path:
    ruta = tmp_path / "datos.git"
    ruta.mkdir()
    git("init", "--quiet", "--bare", directorio=ruta)
    return ruta


@pytest.fixture
def repositorio(desnudo: Path) -> str:
    return desnudo.as_uri()


def test_sin_rama_estado_no_descarga(repositorio: str, tmp_path: Path) -> None:
    assert not remoto.existe(repositorio)
    assert not remoto.descargar(tmp_path / "db.age", repositorio)


def test_sube_y_descarga(repositorio: str, tmp_path: Path) -> None:
    origen = tmp_path / "origen.age"
    origen.write_bytes(b"cifrado-1")
    remoto.subir(origen, "autor@ejemplo.org", repositorio)
    destino = tmp_path / "descargado" / "db.age"
    assert remoto.descargar(destino, repositorio)
    assert destino.read_bytes() == b"cifrado-1"


def test_cada_subida_sustituye_el_unico_commit(
    repositorio: str, desnudo: Path, tmp_path: Path
) -> None:
    origen = tmp_path / "origen.age"
    for contenido in (b"uno", b"dos", b"tres"):
        origen.write_bytes(contenido)
        remoto.subir(origen, "autor@ejemplo.org", repositorio)
    registro = git("log", "--format=%an <%ae>|%B", remoto.RAMA, directorio=desnudo)
    assert registro.strip() == f"{remoto.AUTOR} <autor@ejemplo.org>|{remoto.MENSAJE}"
    assert git("show", f"{remoto.RAMA}:{remoto.FICHERO}", directorio=desnudo) == "tres"


def test_error_de_git_sin_detalles(tmp_path: Path) -> None:
    with pytest.raises(remoto.RemotoFallido, match=r"^git ls-remote falló"):
        remoto.existe((tmp_path / "no-existe").as_uri())
