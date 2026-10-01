"""Exportación semanal para AEGIS (exportacion/semanal.py), desde la base de la rama estado.

En el servidor la lanza cada lunes a las 03:47 UTC `servidor/exportacion.sh`, con el mismo
cerrojo que la recogida horaria. Descarga la base, genera la versión del día (AAAA.MM.DD),
la valida, la cifra y la sube a main del repositorio de datos como exportaciones/<versión>/
con la etiqueta eodi-<versión>. Una versión que ya existe no se sobrescribe: se avisa y se
sale sin error. Con --registro, al terminar bien deja escrita la versión y la hora, de donde
estado.json saca la última exportación correcta.

Al diario solo van recuentos y huellas, nunca contenido.

Uso: python -m recogida.exportacion --correo <correo> [--repositorio <url>] [--registro <json>]
    [--base <db.age>] [--salida <carpeta>] [--sin-subir] [--version AAAA.MM.DD]
"""

import argparse
import json
import logging
import sys
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory

from almacen import cifrado, remoto
from almacen.base import Almacen
from exportacion import semanal

registro = logging.getLogger("exportacion")

FORMATO_INSTANTE = "%Y-%m-%dT%H:%MZ"


def escribir_registro(ruta: Path, version: str, fin: datetime, huella: str) -> None:
    datos = {"version": version, "fin": fin.strftime(FORMATO_INSTANTE), "manifiesto": huella}
    ruta.write_text(json.dumps(datos, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")


def leer_registro(ruta: Path | None) -> dict[str, str] | None:
    if ruta is None or not ruta.exists():
        return None
    try:
        datos = json.loads(ruta.read_text(encoding="utf-8"))
    except ValueError:
        return None
    return datos if isinstance(datos, dict) else None


def exportar(almacen: Almacen, version: str, ahora: datetime, destino: Path) -> str:
    """Escribe la versión en `destino` y devuelve la huella del manifiesto."""
    ficheros = semanal.generar(almacen)
    contenido = semanal.empaquetar(
        ficheros, version, almacen.ultimo_cambio() or ahora.strftime(semanal.FORMATO_INSTANTE),
        ahora, cifrado.destinatario(),
    )  # fmt: skip
    semanal.escribir(contenido, destino)
    for fichero in ficheros:
        if not fichero.nombre.startswith("esquema/"):
            registro.info("%s: %d registros", fichero.nombre, fichero.registros)
    return semanal.sha256(contenido[semanal.MANIFIESTO])


def principal(argumentos: list[str] | None = None, ahora: datetime | None = None) -> int:
    opciones = argparse.ArgumentParser(description=__doc__)
    opciones.add_argument("--correo", required=True, help="correo del autor del commit")
    opciones.add_argument("--repositorio", default=remoto.REPOSITORIO)
    opciones.add_argument("--registro", type=Path, help="última exportación correcta, en JSON")
    opciones.add_argument("--base", type=Path, help="db.age local en vez de la rama estado")
    opciones.add_argument("--salida", type=Path, help="carpeta donde dejar la versión")
    opciones.add_argument("--sin-subir", action="store_true")
    opciones.add_argument("--version", help="AAAA.MM.DD; por defecto, la fecha UTC de hoy")
    args = opciones.parse_args(argumentos)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    ahora = ahora or datetime.now(UTC)
    version = args.version or semanal.version_de(ahora)
    with TemporaryDirectory() as temporal:
        base = args.base
        if base is None:
            base = Path(temporal) / remoto.FICHERO
            if not remoto.descargar(base, args.repositorio):
                registro.error("no hay base en la rama %s", remoto.RAMA)
                return 1
        almacen = Almacen(cifrado.abrir_cifrada(base))
        destino = args.salida or Path(temporal) / version
        if destino.exists() and any(destino.iterdir()):
            registro.error("la carpeta de salida no está vacía: no se sobrescribe")
            return 1
        try:
            huella = exportar(almacen, version, ahora, destino)
        except semanal.ExportacionInvalida as error:
            registro.error("la versión %s no valida y no se publica: %s", version, error)
            return 1
        finally:
            almacen.cerrar()
        registro.info("versión %s generada; manifiesto %s", version, huella)
        if not args.sin_subir:
            try:
                remoto.subir_exportacion(destino, version, args.correo, args.repositorio)
            except remoto.ExportacionExistente as error:
                registro.warning("no se sobrescribe: %s", error)
                return 0
            registro.info("versión %s subida con la etiqueta %s", version, remoto.etiqueta(version))
        if args.registro is not None:
            escribir_registro(args.registro, version, datetime.now(UTC), huella)
    return 0


if __name__ == "__main__":
    sys.exit(principal())
