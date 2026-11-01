"""Configuración de las pruebas. Lo primero, antes de importar nada que lea la carpeta de casa: el
aislamiento (docs/pruebas_aisladas.md). Ninguna prueba ve el token de ntfy, las claves ni el
estado de verdad aunque corra como el usuario del servicio, y ninguna llega a la red."""

import os
import socket
import sys
import tempfile
from pathlib import Path
from typing import Any

import pytest

from almacen.casa import VARIABLE_CASA, VARIABLE_SIN_AVISOS, casa

# Lo que traiga el entorno de quien ejecuta (una unidad del servidor, una sesión) no vale aquí.
SECRETOS_DEL_ENTORNO = ("ALMACEN_ID", "ALMACEN_SECRETO", "HCLOUD_TOKEN", "VERCEL_TOKEN")
for _variable in list(os.environ):
    if _variable.startswith("EODI_") or _variable in SECRETOS_DEL_ENTORNO:
        os.environ.pop(_variable)
CASA_REAL = casa()
# Una casa para lo que se calcula al importar (constantes de los módulos); cada prueba trae la suya.
_CARPETA_SESION = tempfile.TemporaryDirectory(prefix="eodi-pruebas-")
CASA_SESION = Path(_CARPETA_SESION.name)
os.environ[VARIABLE_CASA] = str(CASA_SESION)
os.environ[VARIABLE_SIN_AVISOS] = "1"
PAQUETES = ("almacen", "esquema", "exportacion", "modelo", "proceso", "recogida", "tests")
LOCALES = ("127.0.0.1", "::1", "localhost")
RUTAS_REALES = tuple(str(CASA_REAL / carpeta) for carpeta in (".eodi", "datos", "base"))


def _texto(valor: object) -> str:
    return valor.decode("ascii", "replace") if isinstance(valor, bytes) else str(valor)


def _guardia(evento: str, argumentos: tuple[Any, ...]) -> None:
    """Corta en el acto lo que el aislamiento no debe dejar pasar: abrir un fichero de la casa
    real o conectar con fuera de esta máquina. Audita Python entero, también el código que no
    pase por `casa()`."""
    if evento == "open":
        ruta = argumentos[0]
        if isinstance(ruta, str | os.PathLike):
            texto = os.fspath(ruta)
            if isinstance(texto, str) and texto.startswith(RUTAS_REALES):
                raise PermissionError(f"una prueba ha intentado abrir {texto}")
    elif evento == "socket.getaddrinfo":
        if argumentos[0] is not None and _texto(argumentos[0]) not in LOCALES:
            raise socket.gaierror(f"una prueba ha intentado resolver {_texto(argumentos[0])}")
    elif evento == "socket.connect":
        direccion = argumentos[1]
        if isinstance(direccion, tuple) and _texto(direccion[0]) not in LOCALES:
            raise ConnectionRefusedError(f"una prueba ha intentado conectar con {direccion[0]}")


sys.addaudithook(_guardia)

from almacen import sitio  # noqa: E402

_constantes: list[tuple[Any, str, Path]] = []
_modulos_vistos = 0


def _constantes_de_casa() -> list[tuple[Any, str, Path]]:
    """Las rutas que los módulos del proyecto calcularon al importarse desde la casa de la
    sesión. La lista solo se rehace si hay módulos nuevos."""
    global _modulos_vistos
    if len(sys.modules) != _modulos_vistos:
        _modulos_vistos = len(sys.modules)
        _constantes.clear()
        for nombre, modulo in list(sys.modules.items()):
            if nombre.split(".")[0] not in PAQUETES:
                continue
            for constante, valor in list(vars(modulo).items()):
                if isinstance(valor, Path) and CASA_SESION in valor.parents:
                    _constantes.append((modulo, constante, valor))
    return _constantes


@pytest.fixture(autouse=True)
def casa_aislada(tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch) -> None:
    """Cada prueba, su casa: vacía, sin token ni claves, y sin envío de avisos."""
    casa_prueba = tmp_path_factory.mktemp("casa", numbered=True)
    (casa_prueba / ".eodi").mkdir()
    monkeypatch.setenv(VARIABLE_CASA, str(casa_prueba))
    monkeypatch.setenv(VARIABLE_SIN_AVISOS, "1")
    for modulo, constante, valor in _constantes_de_casa():
        monkeypatch.setattr(modulo, constante, casa_prueba / valor.relative_to(CASA_SESION))


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
