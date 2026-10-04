"""Cifrado con age de la base de datos completa.

La identidad age (clave secreta) se lee de una variable de entorno y nunca se
escribe en el repositorio. En local puede cargarse desde un fichero fuera de
cualquier repositorio. El destinatario se deriva de ella.
"""

import gzip
import lzma
import os
import sqlite3
from pathlib import Path

import pyrage

VARIABLE_CLAVE = "EODI_CLAVE_AGE"
# Solo en local y fuera de cualquier repositorio.
RUTA_CLAVE_LOCAL = Path.home() / ".eodi" / "clave_age.txt"


# La base se comprime antes de cifrar: con el histórico de noticias pasaba de los 100 MB
# que admite GitHub por fichero. Con gzip (nivel 6) volvió a llegar a ellos el 4 de octubre
# de 2026 (99,4 MiB de 966 MiB en claro; la subida de las 12:17 falló); con xz, nivel 3, la
# misma base ocupa 45,7 MiB y se comprime en unos 26 s y se descomprime en 3 s. Se leen
# también las bases comprimidas con gzip y las anteriores sin comprimir.
NIVEL_COMPRESION = 6
NIVEL_XZ = 3
_GZIP = b"\x1f\x8b"
_XZ = b"\xfd7zXZ\x00"


class ClaveAusente(RuntimeError):
    pass


def _identidad() -> pyrage.x25519.Identity:
    contenido = os.environ.get(VARIABLE_CLAVE, "")
    # Admite el fichero de identidad completo: se ignoran comentarios y líneas vacías.
    lineas = [x.strip() for x in contenido.splitlines() if x.strip() and not x.startswith("#")]
    if not lineas:
        raise ClaveAusente(f"falta la variable de entorno {VARIABLE_CLAVE}")
    return pyrage.x25519.Identity.from_str(lineas[0])


def cargar_clave_local(ruta: Path = RUTA_CLAVE_LOCAL) -> None:
    """Para ejecuciones en local: lleva la identidad del fichero a la variable si falta."""
    if not os.environ.get(VARIABLE_CLAVE):
        os.environ[VARIABLE_CLAVE] = ruta.read_text(encoding="utf-8")


def cifrar(conexion: sqlite3.Connection) -> bytes:
    """Serializa la base completa, la comprime y la cifra."""
    return cifrar_datos(lzma.compress(conexion.serialize(), preset=NIVEL_XZ))


def cifrar_datos(datos: bytes) -> bytes:
    return pyrage.encrypt(datos, [_identidad().to_public()])


def destinatario() -> str:
    """La clave pública de la base (age1…): con ella se cifra también la exportación."""
    return str(_identidad().to_public())


def descifrar_datos(cifrado: bytes) -> bytes:
    return pyrage.decrypt(cifrado, [_identidad()])


def descifrar(cifrado: bytes) -> sqlite3.Connection:
    """Descifra y carga la base en memoria; nunca toca el disco en claro."""
    datos = descifrar_datos(cifrado)
    # Las bases comprimidas con gzip y las cifradas antes de comprimir se leen igual.
    if datos[:6] == _XZ:
        datos = lzma.decompress(datos)
    elif datos[:2] == _GZIP:
        datos = gzip.decompress(datos)
    conexion = sqlite3.connect(":memory:")
    conexion.deserialize(datos)
    return conexion


def guardar_cifrada(conexion: sqlite3.Connection, ruta: Path) -> None:
    ruta.write_bytes(cifrar(conexion))


def abrir_cifrada(ruta: Path) -> sqlite3.Connection:
    return descifrar(ruta.read_bytes())
