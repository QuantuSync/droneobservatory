"""Datos publicados en el almacén público, en vez de en el repositorio.

La recogida horaria escribe los ficheros públicos (exportacion/publicar.py: incidentes.geojson,
incidentes_sin_ubicacion.json, ucrania.json, prevision.json y correcciones.json) en una carpeta
del servidor. Con el
interruptor de la publicación (`/home/eodi/.eodi/publicacion_modo`, servidor/recogida.sh) en
`doble` o en `almacen`, este módulo los sube al almacén público
(configuracion/almacen_publico.json, prefijo `publicacion/`):

- cada fichero que ha cambiado, comprimido con gzip (`Content-Encoding: gzip`: quien lo pide
  recibe el JSON tal cual) y con la huella SHA-256 del JSON en `x-amz-meta-sha256`, con
  `Cache-Control: public, max-age=60`;
- al final, `publicacion/manifiesto.json` con el nombre, el tamaño y la huella de cada fichero:
  la web lo lee primero y comprueba con él cada fichero, así nunca construye con una mezcla de dos
  recogidas;
- la primera publicación de cada día (UTC), una instantánea fechada que no se sobrescribe:
  `publicacion/historial/AAAA-MM-DD/<fichero>.gz` y su manifiesto. Sustituye al historial de git
  de la carpeta publicacion/, que se queda donde estaba;
- si algo ha cambiado, pide a Vercel que reconstruya la web con el gancho de despliegue
  (`/home/eodi/.eodi/vercel_gancho`, una dirección secreta).

Cada fichero sube con la licencia de los datos dentro (recogida/licencia.py): el miembro
`licencia` al principio del JSON, como los que se descargan de la web, y `x-amz-meta-licencia` en
los metadatos del objeto. La huella del manifiesto es la de lo subido.

`comparar` comprueba que lo que sirve el almacén es idéntico, byte a byte, a una carpeta (la de
publicacion/ del clon en el modo `doble`, tras el commit) con su licencia.

Uso: python -m recogida.publicacion subir --carpeta <dir> [--gancho <fichero>] [--registro <json>]
     python -m recogida.publicacion comparar --carpeta <dir>
"""

import argparse
import gzip
import hashlib
import json
import logging
import os
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from recogida import almacen_publico, licencia
from recogida.descarga import AGENTE_EODI

registro = logging.getLogger("publicacion")

PREFIJO = "publicacion/"
MANIFIESTO = "manifiesto.json"
HISTORIAL = "historial"
FICHEROS = (
    "incidentes.geojson",
    "incidentes_sin_ubicacion.json",
    "ucrania.json",
    "prevision.json",
    "correcciones.json",
)
TIPOS = {".geojson": "application/geo+json", ".json": "application/json"}
CACHE = "public, max-age=60"
CACHE_HISTORIAL = "public, max-age=86400"
INTENTOS_GANCHO = 3
TOPE_S = 60.0


def huella(datos: bytes) -> str:
    return hashlib.sha256(datos).hexdigest()


def leer_registro(ruta: Path | None) -> dict[str, Any]:
    if ruta is None or not ruta.exists():
        return {}
    try:
        datos = json.loads(ruta.read_text(encoding="utf-8"))
    except ValueError:
        return {}
    return datos if isinstance(datos, dict) else {}


def escribir_registro(ruta: Path, datos: dict[str, Any]) -> None:
    temporal = ruta.with_name(ruta.name + ".tmp")
    temporal.write_text(json.dumps(datos, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(temporal, ruta)


def publicable(carpeta: Path, nombre: str) -> bytes:
    """Lo que se sube de un fichero: el JSON de la carpeta con su licencia dentro
    (recogida/licencia.py), como los que se descargan de la web."""
    return licencia.con_licencia((carpeta / nombre).read_bytes())


def manifiesto(carpeta: Path, ahora: datetime) -> dict[str, Any]:
    ficheros = {}
    for nombre in FICHEROS:
        ruta = carpeta / nombre
        if ruta.exists():
            datos = publicable(carpeta, nombre)
            ficheros[nombre] = {"bytes": len(datos), "sha256": huella(datos)}
    return {
        "version": 1,
        "generado": ahora.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "ficheros": ficheros,
    }


Subir = Callable[..., tuple[bool, str]]


def subir(
    carpeta: Path,
    ahora: datetime,
    clave_id: str,
    secreto: str,
    registro_anterior: dict[str, Any],
    almacen: almacen_publico.Almacen | None = None,
    enviar: Subir = almacen_publico.subir,
) -> tuple[bool, dict[str, Any], bool]:
    """Sube lo que ha cambiado, el manifiesto y, si es la primera del día, la instantánea.
    Devuelve (correcto, registro nuevo, si ha cambiado algo)."""
    almacen = almacen or almacen_publico.cargar()
    nuevo = manifiesto(carpeta, ahora)
    anteriores = registro_anterior.get("ficheros", {})
    cambiado = False
    for nombre, datos in nuevo["ficheros"].items():
        if anteriores.get(nombre, {}).get("sha256") == datos["sha256"]:
            continue
        cuerpo = gzip.compress(publicable(carpeta, nombre), compresslevel=9, mtime=0)
        correcto, motivo = enviar(
            almacen, PREFIJO + nombre, cuerpo, clave_id, secreto,
            TIPOS[Path(nombre).suffix], CACHE, codificacion="gzip",
            metadatos={"x-amz-meta-sha256": datos["sha256"], **licencia.cabeceras()},
        )  # fmt: skip
        registro.info("%s: %s", nombre, motivo)
        if not correcto:
            return False, registro_anterior, cambiado
        cambiado = True
    texto = json.dumps(nuevo, ensure_ascii=False, indent=1).encode("utf-8") + b"\n"
    if cambiado or not registro_anterior:
        correcto, motivo = enviar(
            almacen, PREFIJO + MANIFIESTO, texto, clave_id, secreto, "application/json", CACHE
        )
        registro.info("%s: %s", MANIFIESTO, motivo)
        if not correcto:
            return False, registro_anterior, cambiado
    resultado = {**nuevo, "subido": ahora.strftime("%Y-%m-%dT%H:%M:%SZ")}
    resultado["historial"] = registro_anterior.get("historial")
    dia = ahora.strftime("%Y-%m-%d")
    if registro_anterior.get("historial") != dia:
        destino = f"{PREFIJO}{HISTORIAL}/{dia}/"
        todo = True
        for nombre in nuevo["ficheros"]:
            cuerpo = gzip.compress(publicable(carpeta, nombre), compresslevel=9, mtime=0)
            correcto, motivo = enviar(
                almacen, f"{destino}{nombre}.gz", cuerpo, clave_id, secreto,
                "application/gzip", CACHE_HISTORIAL, metadatos=licencia.cabeceras(),
            )  # fmt: skip
            todo = todo and correcto
        correcto, _ = enviar(
            almacen, destino + MANIFIESTO, texto, clave_id, secreto, "application/json",
            CACHE_HISTORIAL,
        )  # fmt: skip
        if todo and correcto:
            resultado["historial"] = dia
            registro.info("instantánea del día en %s", destino)
        else:
            registro.warning("instantánea del día sin subir: se repite en la siguiente")
    return True, resultado, cambiado


def avisar_a_vercel(gancho: Path, dormir: Callable[[float], None] = time.sleep) -> bool:
    """Pide a Vercel una reconstrucción de la web (gancho de despliegue). La dirección es
    secreta: no se escribe en ningún registro."""
    if not gancho.exists():
        registro.warning("sin gancho de despliegue: la web no se reconstruye")
        return False
    url = gancho.read_text(encoding="utf-8").strip()
    for intento in range(INTENTOS_GANCHO):
        if intento:
            dormir(5.0 * intento)
        try:
            peticion = urllib.request.Request(url, data=b"", method="POST")
            with urllib.request.urlopen(peticion, timeout=TOPE_S) as respuesta:
                if 200 <= respuesta.status < 300:
                    registro.info("reconstrucción de la web pedida a Vercel")
                    return True
        except (OSError, ValueError) as error:
            registro.info("gancho de despliegue: %s", type(error).__name__)
    registro.warning("no se pudo pedir la reconstrucción de la web")
    return False


def leer_publico(url: str) -> bytes:
    """Un objeto del almacén público, descomprimido si viene con gzip."""
    peticion = urllib.request.Request(
        url, headers={"User-Agent": AGENTE_EODI, "Cache-Control": "no-cache"}
    )
    with urllib.request.urlopen(peticion, timeout=TOPE_S) as respuesta:
        datos: bytes = respuesta.read()
        if respuesta.headers.get("Content-Encoding") == "gzip":
            datos = gzip.decompress(datos)
        return datos


def comparar(
    carpeta: Path,
    almacen: almacen_publico.Almacen | None = None,
    leer: Callable[[str], bytes] = leer_publico,
) -> list[str]:
    """Los ficheros que no son idénticos entre la carpeta y el almacén (vacía si todo igual)."""
    almacen = almacen or almacen_publico.cargar()
    distintos = []
    for nombre in FICHEROS:
        local = carpeta / nombre
        if not local.exists():
            continue
        try:
            remoto = leer(almacen.url_publica(PREFIJO + nombre))
        except (OSError, ValueError) as error:
            distintos.append(f"{nombre} (no se lee: {type(error).__name__})")
            continue
        if remoto != publicable(carpeta, nombre):
            distintos.append(nombre)
    return distintos


def principal(argumentos: list[str] | None = None) -> int:
    opciones = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = opciones.add_subparsers(dest="orden", required=True)
    s = sub.add_parser("subir")
    s.add_argument("--carpeta", type=Path, required=True)
    s.add_argument("--registro", type=Path)
    s.add_argument("--gancho", type=Path)
    c = sub.add_parser("comparar")
    c.add_argument("--carpeta", type=Path, required=True)
    args = opciones.parse_args(argumentos)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    if args.orden == "comparar":
        distintos = comparar(args.carpeta)
        if distintos:
            registro.warning("el almacén y %s no coinciden: %s", args.carpeta, ", ".join(distintos))
            return 3
        registro.info("almacén idéntico byte a byte a %s", args.carpeta)
        return 0
    clave_id = os.environ.get(almacen_publico.VARIABLE_ID, "")
    secreto = os.environ.get(almacen_publico.VARIABLE_SECRETO, "")
    if not (clave_id and secreto):
        registro.error("sin credenciales del almacén: no se publica en el almacén")
        return 1
    anterior = leer_registro(args.registro)
    correcto, nuevo, cambiado = subir(args.carpeta, datetime.now(UTC), clave_id, secreto, anterior)
    if not correcto:
        registro.error("publicación en el almacén incompleta: la web no cambia")
        return 1
    if args.registro is not None:
        escribir_registro(args.registro, nuevo)
    if cambiado and args.gancho is not None:
        avisar_a_vercel(args.gancho)
    registro.info("publicado en el almacén (%s)", "con cambios" if cambiado else "sin cambios")
    return 0


if __name__ == "__main__":
    sys.exit(principal())
