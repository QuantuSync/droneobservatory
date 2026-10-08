"""Segunda copia, en otra ubicación de Hetzner, de las copias de la base y del archivo.

Las copias de seguridad están en Núremberg (`nbg1`), como el servidor: la copia cifrada de la
base (`droneobservatory-base`, almacen/copias.py) y el archivo del seguimiento con las rutas
calculadas (`droneobservatory-archivo`, recogida/seguimiento_archivo.py). Esta réplica las lleva a
un bucket privado en Helsinki (`hel1`, configuracion/replica.json), con las mismas credenciales del
proyecto, para que un problema de una ubicación no se lleve las dos:

- `base/…`: los mismos objetos de la copia de la base, que ya van cifrados con age; la réplica
  aplica por su cuenta la misma retención (48 horas, 30 días, un año). Nunca borra porque falte en
  el origen: si el origen se vaciara, la réplica sigue entera.
- `archivo/<clave>.age`: cada objeto del archivo cifrado con la clave pública age de la base (el
  archivo está en claro en su bucket privado). Lleva la huella del cifrado en `x-amz-meta-sha256`
  y la del original en `x-amz-meta-sha256-claro`. No se sobrescribe nada, salvo
  `rutas/ultima.tar.gz`, que se sustituye cuando cambia.
- `exportaciones/…`: la exportación semanal del bucket privado (almacen/exportaciones.py), que ya
  va cifrada, tal cual. No se sobrescribe ni se borra.
- `versiones/…`: las versiones citables de los datos abiertos del almacén público
  (recogida/versiones.py), tal cual: son públicas. Solo las publicadas (con su metadatos.json) y
  nunca se sobrescriben ni se borran.

Para cifrar basta la clave pública (`destinatario_age` de la configuración): esta unidad no
necesita la identidad. Para restaurar sí (EODI_CLAVE_AGE o ~/.eodi/clave_age.txt).

Cada pasada deja la hora y lo hecho en /home/eodi/.eodi/replica.json, que mira la vigilancia.

Uso: python -m almacen.replica preparar | replicar | listar
     python -m almacen.replica restaurar --objeto <clave en la réplica> --destino <fichero>
"""

import argparse
import hashlib
import json
import logging
import os
import sys
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pyrage

from almacen import copias
from almacen.sitio import casa
from recogida import almacen_publico

registro = logging.getLogger("replica")

RAIZ = Path(__file__).resolve().parent.parent
CONFIGURACION = RAIZ / "configuracion" / "replica.json"
CONFIGURACION_ARCHIVO = RAIZ / "configuracion" / "archivo_seguimiento.json"
PREFIJO_BASE = "base/"
PREFIJO_ARCHIVO = "archivo/"
PREFIJO_EXPORTACIONES = "exportaciones/"
PREFIJO_VERSIONES = "versiones/"
SUFIJO_CIFRADO = ".age"
# Lo único del archivo que cambia de contenido con la misma clave (se puede volver a calcular).
SUSTITUIBLES = frozenset({"rutas/ultima.tar.gz"})
META_CLARO = "x-amz-meta-sha256-claro"


def cargar(ruta: Path = CONFIGURACION) -> dict[str, Any]:
    datos: dict[str, Any] = json.loads(ruta.read_text(encoding="utf-8"))
    return datos


def destino_replica(configuracion: dict[str, Any]) -> copias.Destino:
    """La réplica con la retención de la copia de la base (para podar su parte base/)."""
    base = copias.cargar_destino()
    return copias.Destino(
        configuracion["ubicacion"], configuracion["punto_s3"], configuracion["bucket"],
        PREFIJO_BASE, base.retencion,
    )  # fmt: skip


def destino_archivo() -> copias.Destino:
    datos = json.loads(CONFIGURACION_ARCHIVO.read_text(encoding="utf-8"))
    base = copias.cargar_destino()
    return copias.Destino(
        datos["ubicacion"], datos["punto_s3"], datos["bucket"], "", base.retencion
    )


def cifrar(datos: bytes, destinatario: str) -> bytes:
    return pyrage.encrypt(datos, [pyrage.x25519.Recipient.from_str(destinatario)])


def replicar(
    origen_base: copias.Copias,
    origen_archivo: copias.Copias,
    replica: copias.Copias,
    destinatario: str,
    ahora: datetime,
    origen_exportaciones: copias.Copias | None = None,
    origen_versiones: copias.Copias | None = None,
) -> dict[str, Any]:
    """Una pasada: lo que falta en la réplica se sube; después se poda su parte base/."""
    hechos: dict[str, Any] = {
        "base": 0,
        "archivo": 0,
        "sustituidos": 0,
        "exportaciones": 0,
        "versiones": 0,
        "podados": [],
    }
    en_replica = {o.clave for o in replica.listar("")}

    for objeto in origen_base.listar(origen_base.destino.prefijo):
        clave = PREFIJO_BASE + objeto.clave.removeprefix(origen_base.destino.prefijo)
        if clave in en_replica or copias.nivel_y_momento(clave, PREFIJO_BASE) is None:
            continue
        replica.subir(clave, origen_base.bajar(objeto.clave))
        hechos["base"] += 1

    for objeto in origen_archivo.listar(""):
        clave = PREFIJO_ARCHIVO + objeto.clave + SUFIJO_CIFRADO
        sustituible = objeto.clave in SUSTITUIBLES
        if clave in en_replica and not sustituible:
            continue
        claro = origen_archivo.bajar(objeto.clave)
        huella = hashlib.sha256(claro).hexdigest()
        if clave in en_replica and replica.metadato(clave, META_CLARO) == huella:
            continue
        replica.subir(clave, cifrar(claro, destinatario), {META_CLARO: huella})
        hechos["sustituidos" if clave in en_replica else "archivo"] += 1

    if origen_exportaciones is not None:
        prefijo = origen_exportaciones.destino.prefijo
        for objeto in origen_exportaciones.listar(prefijo):
            clave = PREFIJO_EXPORTACIONES + objeto.clave.removeprefix(prefijo)
            if clave in en_replica:
                continue
            replica.subir(clave, origen_exportaciones.bajar(objeto.clave))
            hechos["exportaciones"] += 1

    if origen_versiones is not None:
        objetos = list(origen_versiones.listar(PREFIJO_VERSIONES))
        publicadas = {
            o.clave.rsplit("/", 1)[0] + "/" for o in objetos if o.clave.endswith("/metadatos.json")
        }
        for objeto in objetos:
            carpeta = objeto.clave.rsplit("/", 1)[0] + "/"
            if carpeta not in publicadas or objeto.clave in en_replica:
                continue
            replica.subir(objeto.clave, origen_versiones.bajar(objeto.clave))
            hechos["versiones"] += 1

    hechos["podados"] = replica.podar(ahora)
    return hechos


def restaurar(replica: copias.Copias, objeto: str, destino: Path) -> dict[str, Any]:
    """Baja un objeto de la réplica (comprueba la huella del cifrado), lo descifra si es del
    archivo y comprueba la huella del original."""
    from almacen import cifrado

    cuerpo = replica.bajar(objeto)
    resultado: dict[str, Any] = {"objeto": objeto, "bytes_cifrado": len(cuerpo)}
    if objeto.startswith(PREFIJO_ARCHIVO):
        claro = cifrado.descifrar_datos(cuerpo)
        esperada = replica.metadato(objeto, META_CLARO)
        calculada = hashlib.sha256(claro).hexdigest()
        if esperada != calculada:
            raise OSError(f"{objeto}: la huella del original no coincide")
        destino.write_bytes(claro)
        resultado.update(bytes=len(claro), sha256=calculada)
    else:
        destino.write_bytes(cuerpo)
        resultado.update(bytes=len(cuerpo), sha256=hashlib.sha256(cuerpo).hexdigest())
    return resultado


def anotar(ruta: Path, hechos: dict[str, Any], ahora: datetime) -> None:
    datos = {"ultima": ahora.strftime("%Y-%m-%dT%H:%M:%SZ"), **hechos}
    temporal = ruta.with_name(ruta.name + ".tmp")
    temporal.write_text(json.dumps(datos, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(temporal, ruta)


def principal(
    argumentos: list[str] | None = None,
    ahora: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> int:
    opciones = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = opciones.add_subparsers(dest="orden", required=True)
    sub.add_parser("preparar")
    sub.add_parser("replicar")
    sub.add_parser("listar")
    r = sub.add_parser("restaurar")
    r.add_argument("--objeto", required=True)
    r.add_argument("--destino", type=Path, required=True)
    args = opciones.parse_args(argumentos)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    configuracion = cargar()
    credenciales = copias.Credenciales.cargar()
    replica = copias.Copias(destino_replica(configuracion), credenciales)
    if args.orden == "preparar":
        registro.info("%s", replica.preparar())
        prueba = PREFIJO_BASE + "prueba-privada.txt"
        replica.subir(prueba, b"privado")
        rechazado = replica.anonimo_rechazado(prueba)
        replica.borrar(prueba)
        registro.info("sin credenciales: %s", "rechazado" if rechazado else "SE PUEDE LEER")
        return 0 if rechazado else 1
    if args.orden == "listar":
        for objeto in replica.listar(""):
            sys.stdout.write(f"{objeto.tamano}\t{objeto.clave}\n")
        return 0
    if args.orden == "restaurar":
        if args.destino.exists():
            registro.error("%s ya existe: no se sobrescribe", args.destino)
            return 1
        resultado = restaurar(replica, args.objeto, args.destino)
        sys.stdout.write(json.dumps(resultado, ensure_ascii=False, indent=1) + "\n")
        return 0
    momento = ahora()
    origen_base = copias.Copias(copias.cargar_destino(), credenciales)
    origen_archivo = copias.Copias(destino_archivo(), credenciales)
    from almacen import exportaciones

    origen_exportaciones = copias.Copias(exportaciones.destino(), credenciales)
    publico = almacen_publico.cargar()
    origen_versiones = copias.Copias(
        copias.Destino(publico.ubicacion, publico.punto_s3, publico.bucket, "", {}), credenciales
    )
    hechos = replicar(
        origen_base, origen_archivo, replica, configuracion["destinatario_age"], momento,
        origen_exportaciones, origen_versiones,
    )  # fmt: skip
    registro.info("réplica: %s", json.dumps(hechos, ensure_ascii=False))
    registro_ruta = Path(os.environ.get("EODI_SECRETOS") or casa() / ".eodi") / "replica.json"
    anotar(registro_ruta, hechos, momento)
    return 0


if __name__ == "__main__":
    sys.exit(principal())
