"""La exportación semanal en un bucket privado de Hetzner Object Storage, en vez del repositorio
de datos.

Cada versión queda en `exportaciones/AAAA.MM.DD/` del bucket privado
(configuracion/exportaciones.json), con los mismos ficheros que tenía en el repositorio: cada
fichero comprimido con gzip y cifrado con age (`<nombre>.gz.age`, la misma clave pública que la
base) y `manifiesto.json` en claro con el tamaño y la huella SHA-256 de cada fichero, en claro y
cifrado. El manifiesto se sube el último: una versión sin manifiesto está a medias. Una versión
que ya existe no se sobrescribe (ExportacionExistente). Cada objeto lleva su huella en
`x-amz-meta-sha256`.

Leer una versión: `bajar` descarga la carpeta, comprueba cada fichero contra el manifiesto y la
deja como estaba en el repositorio (exportaciones/AAAA.MM.DD/); se descifra con la identidad age
de siempre. Credenciales S3: ALMACEN_ID y ALMACEN_SECRETO del entorno o de ~/.eodi/almacen.env.

Uso: python -m almacen.exportaciones preparar | listar
     python -m almacen.exportaciones bajar --version AAAA.MM.DD --destino <carpeta>
     python -m almacen.exportaciones subir --version AAAA.MM.DD --origen <carpeta>
"""

import argparse
import hashlib
import json
import logging
import sys
from pathlib import Path
from typing import Any

from almacen import copias

registro = logging.getLogger("exportaciones")

RAIZ = Path(__file__).resolve().parent.parent
CONFIGURACION = RAIZ / "configuracion" / "exportaciones.json"
MANIFIESTO = "manifiesto.json"


class ExportacionExistente(RuntimeError):
    """La versión ya está en el bucket: no se sobrescribe."""


class ExportacionIncompleta(RuntimeError):
    """Falta el manifiesto o un fichero no coincide con él."""


def destino(ruta: Path = CONFIGURACION) -> copias.Destino:
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    base = copias.cargar_destino()
    return copias.Destino(
        datos["ubicacion"], datos["punto_s3"], datos["bucket"], datos["prefijo"], base.retencion
    )


def cliente() -> copias.Copias:
    return copias.Copias(destino(), copias.Credenciales.cargar())


def prefijo_version(cliente: copias.Copias, version: str) -> str:
    return f"{cliente.destino.prefijo}{version}/"


def versiones(cliente: copias.Copias) -> list[str]:
    """Las versiones completas (con manifiesto), de la más antigua a la más nueva."""
    encontradas = set()
    for objeto in cliente.listar(cliente.destino.prefijo):
        resto = objeto.clave.removeprefix(cliente.destino.prefijo)
        version, _, nombre = resto.partition("/")
        if nombre == MANIFIESTO:
            encontradas.add(version)
    return sorted(encontradas)


def subir(cliente: copias.Copias, origen: Path, version: str) -> dict[str, Any]:
    """Sube la carpeta de una versión ya generada; el manifiesto, el último."""
    prefijo = prefijo_version(cliente, version)
    if any(True for _ in cliente.listar(prefijo)):
        raise ExportacionExistente(f"{prefijo} ya existe en el bucket")
    ficheros = sorted(p for p in origen.rglob("*") if p.is_file())
    nombres = [str(p.relative_to(origen)).replace("\\", "/") for p in ficheros]
    if MANIFIESTO not in nombres:
        raise ExportacionIncompleta(f"{origen}: sin {MANIFIESTO}")
    total = 0
    for ruta, nombre in sorted(
        zip(ficheros, nombres, strict=True), key=lambda x: x[1] == MANIFIESTO
    ):
        cuerpo = ruta.read_bytes()
        cliente.subir(prefijo + nombre, cuerpo)
        total += len(cuerpo)
    return {"version": version, "ficheros": len(ficheros), "bytes": total, "prefijo": prefijo}


def bajar(cliente: copias.Copias, version: str, destino_dir: Path) -> dict[str, Any]:
    """Descarga una versión y comprueba cada fichero contra su manifiesto."""
    prefijo = prefijo_version(cliente, version)
    try:
        crudo = cliente.bajar(prefijo + MANIFIESTO)
    except OSError as error:
        raise ExportacionIncompleta(f"{version}: sin manifiesto ({error})") from error
    manifiesto = json.loads(crudo)
    destino_dir.mkdir(parents=True, exist_ok=False)
    (destino_dir / MANIFIESTO).write_bytes(crudo)
    for entrada in manifiesto["ficheros"]:
        cifrado = entrada["cifrado"]
        cuerpo = cliente.bajar(prefijo + cifrado["nombre"])
        if hashlib.sha256(cuerpo).hexdigest() != cifrado["sha256"]:
            raise ExportacionIncompleta(f"{cifrado['nombre']}: no coincide con el manifiesto")
        ruta = destino_dir / cifrado["nombre"]
        ruta.parent.mkdir(parents=True, exist_ok=True)
        ruta.write_bytes(cuerpo)
    return {"version": version, "ficheros": len(manifiesto["ficheros"]) + 1}


def principal(argumentos: list[str] | None = None) -> int:
    opciones = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = opciones.add_subparsers(dest="orden", required=True)
    sub.add_parser("preparar")
    sub.add_parser("listar")
    b = sub.add_parser("bajar")
    b.add_argument("--version", required=True)
    b.add_argument("--destino", type=Path, required=True)
    s = sub.add_parser("subir")
    s.add_argument("--version", required=True)
    s.add_argument("--origen", type=Path, required=True)
    args = opciones.parse_args(argumentos)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    c = cliente()
    if args.orden == "preparar":
        registro.info("%s", c.preparar())
        prueba = c.destino.prefijo + "prueba-privada.txt"
        c.subir(prueba, b"privado")
        rechazado = c.anonimo_rechazado(prueba)
        c.borrar(prueba)
        registro.info("sin credenciales: %s", "rechazado" if rechazado else "SE PUEDE LEER")
        return 0 if rechazado else 1
    if args.orden == "listar":
        for version in versiones(c):
            sys.stdout.write(version + "\n")
        return 0
    if args.orden == "subir":
        resultado = subir(c, args.origen, args.version)
    else:
        resultado = bajar(c, args.version, args.destino)
    sys.stdout.write(json.dumps(resultado, ensure_ascii=False) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(principal())
