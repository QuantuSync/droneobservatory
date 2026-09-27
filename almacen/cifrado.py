"""Cifrado con age de la base de datos completa.

La identidad age (clave secreta) se lee de una variable de entorno y nunca se
escribe en disco ni en el repositorio. El destinatario se deriva de ella.
"""

import os
import sqlite3
from pathlib import Path

import pyrage

VARIABLE_CLAVE = "EODI_CLAVE_AGE"


class ClaveAusente(RuntimeError):
    pass


def _identidad() -> pyrage.x25519.Identity:
    clave = os.environ.get(VARIABLE_CLAVE)
    if not clave:
        raise ClaveAusente(f"falta la variable de entorno {VARIABLE_CLAVE}")
    return pyrage.x25519.Identity.from_str(clave.strip())


def cifrar(conexion: sqlite3.Connection) -> bytes:
    """Serializa la base completa y la cifra."""
    return pyrage.encrypt(conexion.serialize(), [_identidad().to_public()])


def descifrar(cifrado: bytes) -> sqlite3.Connection:
    """Descifra y carga la base en memoria; nunca toca el disco en claro."""
    datos = pyrage.decrypt(cifrado, [_identidad()])
    conexion = sqlite3.connect(":memory:")
    conexion.deserialize(datos)
    return conexion


def guardar_cifrada(conexion: sqlite3.Connection, ruta: Path) -> None:
    ruta.write_bytes(cifrar(conexion))


def abrir_cifrada(ruta: Path) -> sqlite3.Connection:
    return descifrar(ruta.read_bytes())
