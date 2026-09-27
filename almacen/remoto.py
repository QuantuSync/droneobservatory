"""Base cifrada (db.age) en la rama "estado" del repositorio de datos.

La rama tiene siempre un único commit que se sustituye con un push forzado en
cada actualización: el historial de git no crece. El historial de cada
incidente vive dentro de la base.
"""

import os
import shutil
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory

RAMA = "estado"
FICHERO = "db.age"
REPOSITORIO = "https://github.com/QuantuSync/droneobservatory-datos.git"
AUTOR = "QuantuSync"
MENSAJE = "Estado de la base"


class RemotoFallido(RuntimeError):
    pass


def _git(*argumentos: str, directorio: Path | None = None, **entorno: str) -> str:
    resultado = subprocess.run(
        ["git", *argumentos],
        cwd=directorio,
        env={**os.environ, **entorno},
        capture_output=True,
        text=True,
        check=False,
    )
    if resultado.returncode != 0:
        # Solo el subcomando: la URL o la salida podrían llevar credenciales.
        raise RemotoFallido(f"git {argumentos[0]} falló con código {resultado.returncode}")
    return resultado.stdout


def existe(repositorio: str = REPOSITORIO) -> bool:
    return bool(_git("ls-remote", "--heads", repositorio, RAMA).strip())


def descargar(destino: Path, repositorio: str = REPOSITORIO) -> bool:
    """Copia db.age de la rama estado a `destino`. False si la rama aún no existe."""
    if not existe(repositorio):
        return False
    with TemporaryDirectory() as temporal:
        clon = Path(temporal) / "estado"
        _git("clone", "--quiet", "--depth", "1", "--branch", RAMA, "--single-branch",
             repositorio, str(clon))  # fmt: skip
        origen = clon / FICHERO
        if not origen.exists():
            raise RemotoFallido(f"la rama {RAMA} no contiene {FICHERO}")
        destino.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(origen, destino)
    return True


def subir(origen: Path, correo: str, repositorio: str = REPOSITORIO) -> None:
    """Sustituye la rama estado por un único commit con `origen` como db.age."""
    with TemporaryDirectory() as temporal:
        directorio = Path(temporal)
        _git("init", "--quiet", "--initial-branch", RAMA, directorio=directorio)
        shutil.copyfile(origen, directorio / FICHERO)
        _git("add", FICHERO, directorio=directorio)
        _git(
            "commit", "--quiet", "-m", MENSAJE, directorio=directorio,
            GIT_AUTHOR_NAME=AUTOR, GIT_AUTHOR_EMAIL=correo,
            GIT_COMMITTER_NAME=AUTOR, GIT_COMMITTER_EMAIL=correo,
        )  # fmt: skip
        _git("push", "--quiet", "--force", repositorio, f"{RAMA}:{RAMA}", directorio=directorio)
