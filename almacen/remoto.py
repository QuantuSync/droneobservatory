"""Base cifrada (db.age) en la rama "estado" del repositorio de datos.

La rama tiene siempre un único commit que se sustituye con un push forzado en
cada actualización: el historial de git no crece. El historial de cada
incidente vive dentro de la base.
"""

import os
import shutil
import subprocess
import time
from collections.abc import Callable
from pathlib import Path
from tempfile import TemporaryDirectory

RAMA = "estado"
FICHERO = "db.age"
REPOSITORIO = "https://github.com/QuantuSync/droneobservatory-datos.git"
AUTOR = "QuantuSync"
MENSAJE = "Estado de la base"


# Rama de los resultados parciales del histórico de noticias: cada trabajo añade su fichero.
RAMA_PARCIALES = "historico-gdelt"
DIRECTORIO_PARCIALES = "parciales"
# Hasta 20 trabajos pueden terminar a la vez: si otro ha escrito antes, se vuelve a clonar
# y a intentar. 10 intentos con esperas de 5 s crecientes (5, 10 ... 45 s) suman casi 4
# minutos, de sobra para que pasen los demás.
INTENTOS_PARCIAL = 10
ESPERA_PARCIAL_S = 5.0


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


def _identidad_git(correo: str) -> dict[str, str]:
    return {
        "GIT_AUTHOR_NAME": AUTOR, "GIT_AUTHOR_EMAIL": correo,
        "GIT_COMMITTER_NAME": AUTOR, "GIT_COMMITTER_EMAIL": correo,
    }  # fmt: skip


def reiniciar_parciales(correo: str, etiqueta: str, repositorio: str = REPOSITORIO) -> None:
    """Deja la rama de parciales con un único commit vacío para un recorrido nuevo."""
    with TemporaryDirectory() as temporal:
        directorio = Path(temporal)
        _git("init", "--quiet", "--initial-branch", RAMA_PARCIALES, directorio=directorio)
        _git("commit", "--quiet", "--allow-empty", "-m", f"Recorrido {etiqueta}",
             directorio=directorio, **_identidad_git(correo))  # fmt: skip
        _git("push", "--quiet", "--force", repositorio, f"{RAMA_PARCIALES}:{RAMA_PARCIALES}",
             directorio=directorio)  # fmt: skip


def subir_parcial(
    origen: Path,
    nombre: str,
    correo: str,
    repositorio: str = REPOSITORIO,
    dormir: Callable[[float], None] = time.sleep,
) -> int:
    """Añade `origen` a la rama de parciales como `parciales/<nombre>`, sin forzar.

    Si otro trabajo ha escrito a la vez, el push se rechaza: se vuelve a clonar y se
    reintenta. Devuelve el número de intentos.
    """
    for intento in range(1, INTENTOS_PARCIAL + 1):
        with TemporaryDirectory() as temporal:
            clon = Path(temporal) / "parciales"
            _git("clone", "--quiet", "--depth", "1", "--branch", RAMA_PARCIALES,
                 "--single-branch", repositorio, str(clon))  # fmt: skip
            destino = clon / DIRECTORIO_PARCIALES / nombre
            destino.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(origen, destino)
            _git("add", str(destino.relative_to(clon)), directorio=clon)
            _git("commit", "--quiet", "-m", f"Parcial {nombre}", directorio=clon,
                 **_identidad_git(correo))  # fmt: skip
            try:
                _git("push", "--quiet", "origin", f"HEAD:{RAMA_PARCIALES}", directorio=clon)
            except RemotoFallido:
                if intento == INTENTOS_PARCIAL:
                    raise
                dormir(ESPERA_PARCIAL_S * intento)
                continue
            return intento
    raise RemotoFallido("sin intentos")


# Exportación semanal para AEGIS: en main, una carpeta por versión y una etiqueta.
RAMA_EXPORTACIONES = "main"
DIRECTORIO_EXPORTACIONES = "exportaciones"
PREFIJO_ETIQUETA = "eodi-"
# Si otro commit llega a main a la vez, el push se rechaza: se vuelve a clonar y se reintenta.
INTENTOS_EXPORTACION = 3
ESPERA_EXPORTACION_S = 10.0


class ExportacionExistente(RuntimeError):
    """La versión ya está publicada: nunca se sobrescribe."""


def etiqueta(version: str) -> str:
    return f"{PREFIJO_ETIQUETA}{version}"


def subir_exportacion(
    origen: Path,
    version: str,
    correo: str,
    repositorio: str = REPOSITORIO,
    dormir: Callable[[float], None] = time.sleep,
) -> None:
    """Añade la carpeta `origen` como exportaciones/<versión>/ en main, con la etiqueta
    eodi-<versión>, en un único push atómico. Si la versión o la etiqueta ya existen, no
    toca nada (ExportacionExistente). Clona sin descargar las versiones anteriores."""
    destino_relativo = f"{DIRECTORIO_EXPORTACIONES}/{version}"
    nombre_etiqueta = etiqueta(version)
    for intento in range(1, INTENTOS_EXPORTACION + 1):
        if _git("ls-remote", "--tags", repositorio, f"refs/tags/{nombre_etiqueta}").strip():
            raise ExportacionExistente(f"la etiqueta {nombre_etiqueta} ya existe")
        with TemporaryDirectory() as temporal:
            clon = Path(temporal) / "datos"
            _git("clone", "--quiet", "--depth", "1", "--filter=blob:none", "--sparse", "--branch",
                 RAMA_EXPORTACIONES, "--single-branch", repositorio, str(clon))  # fmt: skip
            if _git("ls-tree", "-d", "HEAD", destino_relativo, directorio=clon).strip():
                raise ExportacionExistente(f"{destino_relativo} ya existe")
            _git("sparse-checkout", "set", destino_relativo, directorio=clon)
            shutil.copytree(origen, clon / destino_relativo)
            _git("add", destino_relativo, directorio=clon)
            _git("commit", "--quiet", "-m", f"Exportación {version}", directorio=clon,
                 **_identidad_git(correo))  # fmt: skip
            _git("tag", "--annotate", "-m", f"Exportación {version}", nombre_etiqueta,
                 directorio=clon, **_identidad_git(correo))  # fmt: skip
            try:
                _git("push", "--quiet", "--atomic", "origin", f"HEAD:{RAMA_EXPORTACIONES}",
                     f"refs/tags/{nombre_etiqueta}", directorio=clon)  # fmt: skip
            except RemotoFallido:
                if intento == INTENTOS_EXPORTACION:
                    raise
                dormir(ESPERA_EXPORTACION_S * intento)
                continue
            return


def descargar_parciales(destino: Path, repositorio: str = REPOSITORIO) -> list[Path]:
    """Copia los ficheros de la rama de parciales a `destino`, ordenados por nombre."""
    with TemporaryDirectory() as temporal:
        clon = Path(temporal) / "parciales"
        _git("clone", "--quiet", "--depth", "1", "--branch", RAMA_PARCIALES,
             "--single-branch", repositorio, str(clon))  # fmt: skip
        destino.mkdir(parents=True, exist_ok=True)
        copiados = []
        for fichero in sorted((clon / DIRECTORIO_PARCIALES).glob("*")):
            copiados.append(Path(shutil.copyfile(fichero, destino / fichero.name)))
        return copiados
