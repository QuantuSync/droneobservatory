"""Exportación semanal para AEGIS (exportacion/semanal.py), desde la base de la rama estado.

En el servidor la lanza cada lunes a las 03:47 UTC `servidor/exportacion.sh`, con el mismo
cerrojo que la recogida horaria. Descarga la base, genera la versión del día (AAAA.MM.DD),
la valida, la cifra y la sube a main del repositorio de datos como exportaciones/<versión>/
con la etiqueta eodi-<versión>. Una versión que ya existe no se sobrescribe: se avisa y se
sale sin error. Con --registro, al terminar bien deja escrita la versión y la hora, de donde
estado.json saca la última exportación correcta.

Al diario solo van recuentos y huellas, nunca contenido.

Destinos (--destinos, separados por comas): `github` (la carpeta y la etiqueta en el repositorio de
datos, como hasta ahora) y `almacen` (exportaciones/<versión>/ del bucket privado de Hetzner,
almacen/exportaciones.py). servidor/exportacion.sh los elige con el interruptor de la publicación:
github, los dos (doble) o solo el almacén.

Uso: python -m recogida.exportacion --correo <correo> [--repositorio <url>] [--registro <json>]
    [--base <db.age>] [--salida <carpeta>] [--sin-subir] [--version AAAA.MM.DD]
    [--destinos github,almacen]
     python -m recogida.exportacion --registro <json> --anotar-fallo <código>

Si falla, servidor/exportacion.sh lo anota en el registro (--anotar-fallo): estado.json lo
publica y el workflow vigia-recogida abre en la hora siguiente la incidencia «La exportación
semanal no se genera», sin esperar a los 8 días.
"""

import argparse
import json
import logging
import sys
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from almacen import cifrado, remoto, sitio
from almacen.base import Almacen
from exportacion import semanal

registro = logging.getLogger("exportacion")

FORMATO_INSTANTE = "%Y-%m-%dT%H:%MZ"


def escribir_registro(ruta: Path, version: str, fin: datetime, huella: str) -> None:
    datos = {"version": version, "fin": fin.strftime(FORMATO_INSTANTE), "manifiesto": huella}
    ruta.write_text(json.dumps(datos, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")


def anotar_fallo(ruta: Path, fin: datetime, codigo: int) -> None:
    """Deja en el registro que la exportación falló (hora y código), sin tocar la última
    correcta: estado.json lo publica y la vigilancia abre su aviso en la hora siguiente, sin
    esperar a los 8 días. Una exportación correcta reescribe el registro y lo quita."""
    datos: dict[str, Any] = dict(leer_registro(ruta) or {})
    datos["fallo"] = {"fin": fin.strftime(FORMATO_INSTANTE), "codigo": codigo}
    ruta.write_text(json.dumps(datos, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")


def leer_registro(ruta: Path | None) -> dict[str, Any] | None:
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
    opciones.add_argument("--correo", help="correo del autor del commit")
    opciones.add_argument("--repositorio", default=remoto.REPOSITORIO)
    opciones.add_argument("--registro", type=Path, help="última exportación correcta, en JSON")
    opciones.add_argument("--base", type=Path, help="db.age local en vez de la rama estado")
    opciones.add_argument("--salida", type=Path, help="carpeta donde dejar la versión")
    opciones.add_argument("--sin-subir", action="store_true")
    opciones.add_argument("--version", help="AAAA.MM.DD; por defecto, la fecha UTC de hoy")
    opciones.add_argument("--destinos", default="github", help="github, almacen o los dos")
    opciones.add_argument(
        "--anotar-fallo", type=int, metavar="CODIGO",
        help="solo anota en --registro que la exportación falló con ese código",
    )  # fmt: skip
    args = opciones.parse_args(argumentos)
    if args.anotar_fallo is not None:
        if args.registro is None:
            opciones.error("--anotar-fallo necesita --registro")
        anotar_fallo(args.registro, ahora or datetime.now(UTC), args.anotar_fallo)
        return 0
    destinos = {d.strip() for d in args.destinos.split(",") if d.strip()}
    if not destinos or destinos - {"github", "almacen"}:
        opciones.error(f"destinos desconocidos: {args.destinos}")
    if args.correo is None and not args.sin_subir and "github" in destinos:
        opciones.error("falta --correo")
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    ahora = ahora or datetime.now(UTC)
    version = args.version or semanal.version_de(ahora)
    with TemporaryDirectory() as temporal:
        abierta = (
            Almacen(cifrado.abrir_cifrada(args.base))
            if args.base is not None
            else sitio.abrir_base(Path(temporal), args.repositorio)
        )
        if abierta is None:
            registro.error("no hay base en la rama %s", remoto.RAMA)
            return 1
        almacen = abierta
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
        existentes = 0
        if not args.sin_subir and "almacen" in destinos:
            from almacen import exportaciones

            try:
                subida = exportaciones.subir(exportaciones.cliente(), destino, version)
            except exportaciones.ExportacionExistente as error:
                registro.warning("no se sobrescribe: %s", error)
                existentes += 1
            else:
                registro.info("versión %s en el almacén privado: %s", version, subida["prefijo"])
        if not args.sin_subir and "github" in destinos:
            try:
                remoto.subir_exportacion(destino, version, args.correo, args.repositorio)
            except remoto.ExportacionExistente as error:
                registro.warning("no se sobrescribe: %s", error)
                existentes += 1
            else:
                etiqueta = remoto.etiqueta(version)
                registro.info("versión %s subida con la etiqueta %s", version, etiqueta)
        if existentes and existentes == len(destinos):
            return 0
        if args.registro is not None:
            escribir_registro(args.registro, version, datetime.now(UTC), huella)
    return 0


if __name__ == "__main__":
    sys.exit(principal())
