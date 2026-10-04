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
    assert git("show", f"{remoto.RAMA}:{remoto.FICHERO}.000", directorio=desnudo) == "tres"


def test_base_grande_en_trozos(repositorio: str, desnudo: Path, tmp_path: Path) -> None:
    # GitHub rechaza ficheros de más de 100 MiB: la base se sube en trozos y se vuelve a unir.
    origen = tmp_path / "origen.age"
    contenido = bytes(range(256)) * 40
    origen.write_bytes(contenido)
    remoto.subir(origen, "autor@ejemplo.org", repositorio, tamano=4096)
    ficheros = git("ls-tree", "--name-only", remoto.RAMA, directorio=desnudo).split()
    assert ficheros == ["db.age.000", "db.age.001", "db.age.002"]
    destino = tmp_path / "descargado" / "db.age"
    assert remoto.descargar(destino, repositorio)
    assert destino.read_bytes() == contenido


def test_tamano_justo_y_vacio(tmp_path: Path) -> None:
    origen = tmp_path / "origen.age"
    origen.write_bytes(b"abcd")
    assert remoto.trocear(origen, tmp_path, tamano=4) == ["db.age.000"]
    origen.write_bytes(b"")
    assert remoto.trocear(origen, tmp_path, tamano=4) == ["db.age.000"]


def test_lee_la_rama_de_antes_con_el_fichero_entero(repositorio: str, tmp_path: Path) -> None:
    clon = tmp_path / "antigua"
    clon.mkdir()
    git("init", "--quiet", "--initial-branch", remoto.RAMA, directorio=clon)
    (clon / remoto.FICHERO).write_bytes(b"entera")
    git("add", remoto.FICHERO, directorio=clon)
    git("-c", "user.name=a", "-c", "user.email=a@b", "commit", "--quiet", "-m", "x",
        directorio=clon)  # fmt: skip
    git("push", "--quiet", repositorio, f"{remoto.RAMA}:{remoto.RAMA}", directorio=clon)
    destino = tmp_path / "db.age"
    assert remoto.descargar(destino, repositorio)
    assert destino.read_bytes() == b"entera"


def test_error_de_git_sin_detalles(tmp_path: Path) -> None:
    with pytest.raises(remoto.RemotoFallido, match=r"^git ls-remote falló"):
        remoto.existe((tmp_path / "no-existe").as_uri())
