"""Dónde vive la base de datos y cómo se abre y se guarda.

Un solo interruptor elige el modo: la variable de entorno EODI_BASE_MODO o, si no está, el
fichero ~/.eodi/base_modo con una palabra. Sin ninguno de los dos, el modo es «github».

- github: la base cifrada de la rama estado del repositorio de datos (almacen/remoto.py),
  cargada entera en memoria y vuelta a subir al guardar. Es el modo de siempre, y el único en
  los equipos sin el interruptor (GitHub Actions, el equipo local).
- doble: igual que github, que sigue siendo la que manda. Además, cada vez que se sube la base,
  se deja una copia en el fichero SQLite del disco y una copia de seguridad cifrada en el
  almacén de objetos (almacen/copias.py). Un fallo de esa parte solo deja un aviso.
- disco: manda el fichero SQLite del disco del servidor (~/base/eodi.sqlite), que se abre desde
  disco sin cargarlo en memoria. Cada sesión trabaja sobre una copia propia en ~/base/trabajo/
  (modo WAL) y, si termina bien, esa copia sustituye a la base de golpe (os.replace): una
  recogida que falla a medias no deja nada, como cuando no se subía a la rama. La versión que
  sustituye queda como ~/base/eodi.anterior.sqlite. Tras guardar, la copia de seguridad cifrada
  y, como copia secundaria, la base cifrada en la rama estado; un fallo de cualquiera de las dos
  solo deja un aviso.

La base en disco va en claro, en una carpeta con permisos solo para el usuario del servicio.
"""

import argparse
import atexit
import gzip
import hashlib
import io
import json
import logging
import lzma
import os
import secrets
import sqlite3
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory

from almacen import cifrado, remoto
from almacen.base import Almacen

registro = logging.getLogger("base")

GITHUB, DOBLE, DISCO = "github", "doble", "disco"
MODOS = (GITHUB, DOBLE, DISCO)
VARIABLE_MODO = "EODI_BASE_MODO"
VARIABLE_DIRECTORIO = "EODI_BASE_DIRECTORIO"


def casa() -> Path:
    """La carpeta del usuario que ejecuta, de la base de usuarios del sistema y no de HOME:
    con `sudo -u eodi` HOME puede seguir siendo la del operador."""
    if sys.platform != "win32":
        import pwd

        return Path(pwd.getpwuid(os.getuid()).pw_dir)
    return Path.home()


FICHERO_MODO = casa() / ".eodi" / "base_modo"
DIRECTORIO = casa() / "base"
NOMBRE = "eodi.sqlite"
ANTERIOR = "eodi.anterior.sqlite"
TRABAJO = "trabajo"
# Caché de páginas de cada conexión a la copia de trabajo: el resto lo pone la caché del
# sistema, que se libera sola cuando hace falta memoria.
CACHE_KIB = 262_144
BLOQUE = 1 << 20


class BaseAusente(RuntimeError):
    """En modo disco, sin fichero de la base."""


class BaseCambiada(RuntimeError):
    """Otra sesión guardó la base mientras esta trabajaba: no se pisa lo suyo."""


def modo() -> str:
    valor = os.environ.get(VARIABLE_MODO, "").strip()
    if not valor:
        try:
            valor = FICHERO_MODO.read_text(encoding="utf-8").strip()
        except FileNotFoundError:
            valor = GITHUB
    if valor not in MODOS:
        # Mejor parar que trabajar con una base que ya no es la que manda.
        raise ValueError(f"modo de la base desconocido: {valor!r} (válidos: {', '.join(MODOS)})")
    return valor


def directorio() -> Path:
    return Path(os.environ.get(VARIABLE_DIRECTORIO) or DIRECTORIO)


def ruta_base(raiz: Path | None = None) -> Path:
    return (raiz or directorio()) / NOMBRE


@dataclass(frozen=True)
class Sello:
    """Identidad del fichero de la base en un momento: cambia cada vez que se sustituye."""

    inodo: int
    modificado_ns: int
    tamano: int

    @classmethod
    def de(cls, ruta: Path) -> "Sello":
        datos = ruta.stat()
        return cls(datos.st_ino, datos.st_mtime_ns, datos.st_size)


class AlmacenEnDisco(Almacen):
    """La base abierta sobre una copia de trabajo; al cerrarla, la copia se borra."""

    def __init__(self, conexion: sqlite3.Connection, trabajo: Path, sello: Sello) -> None:
        super().__init__(conexion)
        self.trabajo = trabajo
        self.sello = sello

    @property
    def raiz(self) -> Path:
        return self.trabajo.parent.parent

    def cerrar(self) -> None:
        super().cerrar()
        _borrar_sqlite(self.trabajo)


# --- Ficheros SQLite ----------------------------------------------------------------------


def _borrar_sqlite(ruta: Path) -> None:
    for sufijo in ("", "-wal", "-shm", "-journal"):
        Path(f"{ruta}{sufijo}").unlink(missing_ok=True)


def _sincronizar(ruta: Path) -> None:
    # En Windows, fsync pide el fichero abierto para escribir.
    with ruta.open("r+b") as fichero:
        os.fsync(fichero.fileno())


def _sincronizar_carpeta(carpeta: Path) -> None:
    if os.name != "posix":
        return
    descriptor = os.open(carpeta, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _carpeta_privada(carpeta: Path) -> Path:
    carpeta.mkdir(mode=0o700, parents=True, exist_ok=True)
    return carpeta


def _solo_lectura(ruta: Path) -> sqlite3.Connection:
    return sqlite3.connect(f"{ruta.resolve().as_uri()}?mode=ro", uri=True)


def _conectar_trabajo(ruta: Path) -> sqlite3.Connection:
    # Los ficheros temporales de SQLite (ordenaciones grandes), junto a la copia y no en /tmp,
    # que en el servidor está en memoria.
    os.environ.setdefault("SQLITE_TMPDIR", str(ruta.parent))
    conexion = sqlite3.connect(ruta)
    conexion.execute("PRAGMA journal_mode = WAL")
    # Si la sesión se corta, la copia de trabajo se tira: no hace falta esperar al disco en
    # cada transacción. La base solo se sustituye con una copia completa y sincronizada.
    conexion.execute("PRAGMA synchronous = OFF")
    conexion.execute(f"PRAGMA cache_size = -{CACHE_KIB}")
    return conexion


def volcar(conexion: sqlite3.Connection, destino: Path) -> None:
    """Copia consistente de la base abierta en `destino`, sincronizada en disco."""
    _borrar_sqlite(destino)
    copia = sqlite3.connect(destino)
    try:
        conexion.backup(copia)
        # La base guardada, en modo de diario normal: se lee sin ficheros -wal ni -shm.
        copia.execute("PRAGMA journal_mode = DELETE")
    finally:
        copia.close()
    os.chmod(destino, 0o600)
    _sincronizar(destino)


def _sustituir(raiz: Path, nuevo: Path) -> None:
    """La versión actual pasa a ser la anterior y `nuevo` ocupa su sitio, de golpe: en ningún
    momento falta el fichero de la base."""
    base = raiz / NOMBRE
    if base.exists():
        enlace = raiz / f"{ANTERIOR}.enlace"
        enlace.unlink(missing_ok=True)
        os.link(base, enlace)
        os.replace(enlace, raiz / ANTERIOR)
    os.replace(nuevo, base)
    _sincronizar_carpeta(raiz)


def _pid_vivo(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def limpiar_trabajo(carpeta: Path) -> list[str]:
    """Borra las copias de trabajo que dejaron procesos que ya no existen (un corte, un tope
    de memoria). Solo en Linux, donde se puede preguntar por un proceso sin tocarlo."""
    if os.name != "posix" or not carpeta.exists():
        return []
    borradas = []
    for copia in carpeta.glob("*.sqlite"):
        pid = copia.name.split("-", 1)[0]
        if pid.isdigit() and int(pid) != os.getpid() and not _pid_vivo(int(pid)):
            _borrar_sqlite(copia)
            borradas.append(copia.name)
    return borradas


# --- Abrir y guardar ----------------------------------------------------------------------


def abrir_disco(raiz: Path | None = None) -> AlmacenEnDisco:
    """Copia de trabajo de la base del disco, abierta desde disco."""
    raiz = raiz or directorio()
    base = raiz / NOMBRE
    if not base.exists():
        raise BaseAusente(f"no hay base en {base}")
    carpeta = _carpeta_privada(raiz / TRABAJO)
    for nombre in limpiar_trabajo(carpeta):
        registro.info("copia de trabajo abandonada borrada: %s", nombre)
    sello = Sello.de(base)
    trabajo = carpeta / f"{os.getpid()}-{secrets.token_hex(4)}.sqlite"
    atexit.register(_borrar_sqlite, trabajo)
    origen = _solo_lectura(base)
    try:
        volcar(origen, trabajo)
    finally:
        origen.close()
    return AlmacenEnDisco(_conectar_trabajo(trabajo), trabajo, sello)


def abrir_base(temporal: Path, repositorio: str = remoto.REPOSITORIO) -> Almacen | None:
    """La base para trabajar, según el modo. En github y doble, None si la rama estado aún no
    existe; la base cifrada queda en `temporal`/db.age."""
    if modo() == DISCO:
        return abrir_disco()
    ruta = temporal / remoto.FICHERO
    if not remoto.descargar(ruta, repositorio):
        return None
    return Almacen(cifrado.abrir_cifrada(ruta))


def guardar_disco(almacen: AlmacenEnDisco) -> Path:
    """Sustituye la base del disco por la copia de trabajo, si nadie la ha cambiado entretanto."""
    raiz = almacen.raiz
    base = raiz / NOMBRE
    if Sello.de(base) != almacen.sello:
        raise BaseCambiada(f"{base} ha cambiado desde que se abrió esta sesión: no se sustituye")
    almacen.conexion.commit()
    nuevo = raiz / f"{NOMBRE}.nuevo"
    volcar(almacen.conexion, nuevo)
    _sustituir(raiz, nuevo)
    almacen.sello = Sello.de(base)
    return base


def copiar_a_disco(conexion: sqlite3.Connection, raiz: Path | None = None) -> Path:
    """Modo doble: deja en el disco una copia de la base que manda (la de la rama estado)."""
    raiz = _carpeta_privada(raiz or directorio())
    nuevo = raiz / f"{NOMBRE}.nuevo"
    volcar(conexion, nuevo)
    _sustituir(raiz, nuevo)
    return raiz / NOMBRE


def guardar_base(
    almacen: Almacen, temporal: Path, correo: str, repositorio: str = remoto.REPOSITORIO
) -> None:
    """Guarda la base según el modo. Lo que no manda (el disco en doble; la rama estado y la
    copia de seguridad en disco) solo deja un aviso si falla."""
    from almacen import copias

    ahora = datetime.now(UTC)
    if isinstance(almacen, AlmacenEnDisco):
        base = guardar_disco(almacen)
        registro.info("base guardada en %s", base)
        cifrada = almacen.trabajo.with_name(f"{almacen.trabajo.stem}.db.age")
        try:
            cifrar_fichero(base, cifrada)
        except Exception as error:
            registro.warning("aviso: la base no se pudo cifrar para las copias: %s", error)
            return
        try:
            try:
                registro.info("copia de seguridad: %s", copias.guardar(cifrada, ahora))
            except Exception as error:
                registro.warning("aviso: copia de seguridad no guardada: %s", str(error)[:300])
            try:
                remoto.subir(cifrada, correo, repositorio)
                registro.info("copia secundaria subida a la rama %s", remoto.RAMA)
            except Exception as error:
                registro.warning(
                    "aviso: copia secundaria no subida a la rama %s: %s", remoto.RAMA, error
                )
        finally:
            cifrada.unlink(missing_ok=True)
        return
    # Abierta en memoria (github o doble): se guarda como se abrió, también si el interruptor
    # ha pasado a disco mientras tanto; entonces la copia en disco recoge lo de esta sesión.
    ruta = temporal / remoto.FICHERO
    cifrado.guardar_cifrada(almacen.conexion, ruta)
    remoto.subir(ruta, correo, repositorio)
    registro.info("base subida a la rama %s", remoto.RAMA)
    if modo() != GITHUB:
        try:
            registro.info("copia de la base en disco: %s", copiar_a_disco(almacen.conexion))
            registro.info("copia de seguridad: %s", copias.guardar(ruta, ahora))
        except Exception as error:
            registro.warning("aviso: copia en disco o de seguridad no hecha: %s", str(error)[:300])


def marca(almacen: Almacen) -> object:
    """Lo que permite saber al final si la sesión ha cambiado la base. En memoria, la base
    entera, como siempre; en disco, el recuento de cambios y la versión del esquema, sin leerla."""
    if isinstance(almacen, AlmacenEnDisco):
        conexion = almacen.conexion
        return (conexion.total_changes, conexion.execute("PRAGMA schema_version").fetchone()[0])
    return almacen.conexion.serialize()


def sin_cambios(almacen: Almacen, anterior: object) -> bool:
    return marca(almacen) == anterior


# --- Cifrado de ficheros, sin cargar la base en memoria -----------------------------------


def cifrar_fichero(origen: Path, destino: Path) -> Path:
    """La base `origen`, comprimida con xz y cifrada con age como en la rama estado: la leen
    igual cifrado.abrir_cifrada y descifrar_a_fichero. Solo la versión comprimida pasa por la
    memoria."""
    comprimido = destino.with_name(f"{destino.name}.xz")
    compresor = lzma.LZMACompressor(preset=cifrado.NIVEL_XZ)
    try:
        with origen.open("rb") as entrada, comprimido.open("wb") as salida:
            while bloque := entrada.read(BLOQUE):
                salida.write(compresor.compress(bloque))
            salida.write(compresor.flush())
        destino.write_bytes(cifrado.cifrar_datos(comprimido.read_bytes()))
    finally:
        comprimido.unlink(missing_ok=True)
    return destino


def descifrar_a_fichero(cifrada: bytes, destino: Path) -> Path:
    """Descifra una base (xz, gzip o sin comprimir) y la escribe en `destino` por bloques."""
    datos = cifrado.descifrar_datos(cifrada)
    with destino.open("wb") as salida:
        if datos[:6] == cifrado._XZ:
            descompresor = lzma.LZMADecompressor()
            salida.write(descompresor.decompress(datos, max_length=BLOQUE))
            del datos
            while not descompresor.eof:
                if descompresor.needs_input:
                    raise lzma.LZMAError("la base comprimida está incompleta")
                salida.write(descompresor.decompress(b"", max_length=BLOQUE))
        elif datos[:2] == cifrado._GZIP:
            with gzip.GzipFile(fileobj=io.BytesIO(datos)) as entrada:
                while bloque := entrada.read(BLOQUE):
                    salida.write(bloque)
        else:
            salida.write(datos)
    os.chmod(destino, 0o600)
    return destino


# --- Comprobaciones -----------------------------------------------------------------------


def _valor(valor: object) -> object:
    return {"hex": valor.hex()} if isinstance(valor, bytes) else valor


def huella_contenido(conexion: sqlite3.Connection) -> str:
    """SHA-256 del esquema y de todas las filas de todas las tablas, en orden: dos bases con la
    misma huella tienen el mismo contenido aunque sus ficheros no sean idénticos byte a byte."""
    suma = hashlib.sha256()
    tablas = conexion.execute(
        "SELECT name, sql FROM sqlite_master WHERE type = 'table' ORDER BY name"
    ).fetchall()
    for objeto in conexion.execute(
        "SELECT type, name, sql FROM sqlite_master WHERE sql IS NOT NULL ORDER BY type, name"
    ):
        suma.update(json.dumps(objeto, ensure_ascii=False).encode("utf-8"))
    for nombre, sql in tablas:
        suma.update(f"\0tabla {nombre}\0".encode())
        orden = "" if "WITHOUT ROWID" in (sql or "").upper() else " ORDER BY rowid"
        if orden == "":
            claves = [f'"{c[1]}"' for c in conexion.execute(f'PRAGMA table_info("{nombre}")')]
            orden = f" ORDER BY {', '.join(claves)}"
        for fila in conexion.execute(f'SELECT * FROM "{nombre}"{orden}'):
            texto = json.dumps([_valor(v) for v in fila], ensure_ascii=False)
            suma.update(texto.encode("utf-8"))
            suma.update(b"\n")
    return suma.hexdigest()


def huella_fichero(ruta: Path) -> str:
    conexion = _solo_lectura(ruta)
    try:
        return huella_contenido(conexion)
    finally:
        conexion.close()


def integra(ruta: Path) -> bool:
    conexion = _solo_lectura(ruta)
    try:
        return bool(conexion.execute("PRAGMA integrity_check").fetchone()[0] == "ok")
    finally:
        conexion.close()


def base_de_github(destino: Path, repositorio: str = remoto.REPOSITORIO) -> bool:
    """La base de la rama estado descifrada en `destino`, sin cargarla entera en memoria."""
    with TemporaryDirectory(dir=destino.parent) as temporal:
        cifrada = Path(temporal) / remoto.FICHERO
        if not remoto.descargar(cifrada, repositorio):
            return False
        descifrar_a_fichero(cifrada.read_bytes(), destino)
    return True


# --- Órdenes ------------------------------------------------------------------------------


def _estado() -> dict[str, object]:
    raiz = directorio()
    base = raiz / NOMBRE
    datos: dict[str, object] = {"modo": modo(), "directorio": str(raiz), "existe": base.exists()}
    if base.exists():
        informacion = base.stat()
        datos["tamano"] = informacion.st_size
        datos["modificada"] = datetime.fromtimestamp(informacion.st_mtime, UTC).isoformat()
    trabajo = raiz / TRABAJO
    datos["copias_de_trabajo"] = sorted(p.name for p in trabajo.glob("*.sqlite"))
    return datos


def principal(argumentos: list[str] | None = None) -> int:
    opciones = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ordenes = opciones.add_subparsers(dest="orden", required=True)
    ordenes.add_parser("estado", help="modo, fichero de la base y copias de trabajo")
    huella = ordenes.add_parser("huella", help="huella del contenido de un fichero SQLite")
    huella.add_argument("fichero", type=Path, nargs="?")
    comparar = ordenes.add_parser("comparar", help="la base del disco frente a la de la rama")
    comparar.add_argument("--repositorio", default=remoto.REPOSITORIO)
    desde = ordenes.add_parser("desde-github", help="deja en disco la base de la rama estado")
    desde.add_argument("--repositorio", default=remoto.REPOSITORIO)
    hacia = ordenes.add_parser("a-github", help="sube a la rama estado la base del disco")
    hacia.add_argument("--repositorio", default=remoto.REPOSITORIO)
    hacia.add_argument("--correo", required=True)
    args = opciones.parse_args(argumentos)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    if args.orden == "estado":
        sys.stdout.write(json.dumps(_estado(), ensure_ascii=False, indent=1) + "\n")
        return 0
    if args.orden == "huella":
        ruta = args.fichero or ruta_base()
        sys.stdout.write(f"{huella_fichero(ruta)}  {ruta}\n")
        return 0
    cifrado.cargar_clave_local()
    raiz = directorio()
    carpeta = _carpeta_privada(raiz / TRABAJO)
    if args.orden == "comparar":
        with TemporaryDirectory(dir=carpeta) as temporal:
            rama = Path(temporal) / "rama.sqlite"
            if not base_de_github(rama, args.repositorio):
                registro.error("no hay base en la rama %s", remoto.RAMA)
                return 1
            de_rama, de_disco = huella_fichero(rama), huella_fichero(ruta_base())
        iguales = de_rama == de_disco
        sys.stdout.write(
            json.dumps({"rama": de_rama, "disco": de_disco, "iguales": iguales}, indent=1) + "\n"
        )
        return 0 if iguales else 3
    if args.orden == "desde-github":
        nuevo = raiz / f"{NOMBRE}.nuevo"
        if not base_de_github(nuevo, args.repositorio):
            registro.error("no hay base en la rama %s", remoto.RAMA)
            return 1
        if not integra(nuevo):
            registro.error("la base de la rama no pasa la comprobación de integridad")
            return 1
        _sincronizar(nuevo)
        _sustituir(raiz, nuevo)
        registro.info("base de la rama %s copiada en %s", remoto.RAMA, ruta_base())
        return 0
    with TemporaryDirectory(dir=carpeta) as temporal:
        cifrada = cifrar_fichero(ruta_base(), Path(temporal) / remoto.FICHERO)
        remoto.subir(cifrada, args.correo, args.repositorio)
    registro.info("base del disco subida a la rama %s", remoto.RAMA)
    return 0


if __name__ == "__main__":
    sys.exit(principal())
