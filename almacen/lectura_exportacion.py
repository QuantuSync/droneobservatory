"""Acceso de solo lectura a la exportación semanal para AEGIS (bucket privado de exportaciones).

En Hetzner Object Storage cada credencial S3 vale para todos los buckets de su proyecto, con
lectura y escritura, y solo se crea desde la consola (no hay API). La forma de dar solo lectura
de un bucket es la que recomienda Hetzner: la credencial de lectura vive en **otro proyecto**, sin
buckets, y la política del bucket de exportaciones le permite `s3:GetObject` y
`s3:ListBucket` y nada más. Así no puede escribir en ningún bucket del observatorio ni leer los
demás; la credencial del servidor sigue como estaba (es del proyecto dueño del bucket).

Órdenes:

- `politica --proyecto <id> --clave-id <id de la credencial>`: con la credencial del servidor
  (ALMACEN_ID y ALMACEN_SECRETO o ~/.eodi/almacen.env), pone en el bucket la declaración
  «LecturaExportacionAEGIS» para esa credencial y conserva las demás declaraciones que tuviera.
  `<id>` es el número del proyecto de la credencial (console.hetzner.com/projects/<id>/…) y
  `<id de la credencial>`, su Access Key (no el secreto).
- `comprobar --credenciales <fichero>`: con la credencial de lectura (mismo formato que
  almacen.env) comprueba que lista las versiones y descarga y verifica un manifiesto y un
  fichero, y que NO puede escribir ni borrar en el bucket ni listar o leer los demás buckets del
  observatorio. Sale con 0 solo si todo es así. No escribe secretos en ninguna parte.

Uso: python -m almacen.lectura_exportacion politica --proyecto <id> --clave-id <id>
     python -m almacen.lectura_exportacion comprobar --credenciales <fichero .env de lectura>
"""

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any

from almacen import buckets, copias, exportaciones

SID = "LecturaExportacionAEGIS"
CONFIGURACIONES = (
    "almacen_publico.json", "archivo_seguimiento.json", "copias_base.json", "replica.json",
)  # fmt: skip


def politica(bucket: str, prefijo: str, principal: str, actual: dict[str, Any] | None) -> str:
    """La política del bucket con la declaración de lectura para `principal` (sustituye la
    anterior del mismo Sid y conserva las demás)."""
    otras = [d for d in (actual or {}).get("Statement", []) if d.get("Sid") != SID]
    declaracion = {
        "Sid": SID,
        "Effect": "Allow",
        "Principal": {"AWS": [principal]},
        "Action": ["s3:GetObject", "s3:ListBucket"],
        "Resource": [f"arn:aws:s3:::{bucket}", f"arn:aws:s3:::{bucket}/{prefijo}*"],
    }
    return json.dumps({"Version": "2012-10-17", "Statement": [*otras, declaracion]})


def principal_de(proyecto: str, clave_id: str) -> str:
    if not proyecto.isdigit() or not clave_id.isalnum():
        raise ValueError("el proyecto es un número y la credencial, su Access Key")
    return f"arn:aws:iam:::user/p{proyecto}:{clave_id}"


def poner_politica(cliente: copias.Copias, principal: str) -> int:
    respuesta = cliente._peticion("GET", consulta="policy=")
    actual = json.loads(respuesta.cuerpo) if respuesta.estado == 200 else None
    cuerpo = politica(cliente.destino.bucket, cliente.destino.prefijo, principal, actual).encode()
    puesta = cliente._peticion(
        "PUT", cuerpo=cuerpo, cabeceras={"Content-Type": "application/json"}, consulta="policy="
    )
    sys.stdout.write(f"política del bucket {cliente.destino.bucket}: PUT {puesta.estado}\n")
    return 0 if puesta.estado in (200, 204) else 1


def _credenciales(ruta: Path) -> copias.Credenciales:
    anteriores = {v: os.environ.pop(v, None) for v in (copias.VARIABLE_ID, copias.VARIABLE_SECRETO)}
    os.environ[copias.VARIABLE_CREDENCIALES] = str(ruta)
    try:
        return copias.Credenciales.cargar()
    finally:
        os.environ.pop(copias.VARIABLE_CREDENCIALES, None)
        for nombre, valor in anteriores.items():
            if valor is not None:
                os.environ[nombre] = valor


def _otros_destinos() -> list[copias.Destino]:
    destinos = []
    for nombre in CONFIGURACIONES:
        datos = json.loads((exportaciones.RAIZ / "configuracion" / nombre).read_text("utf-8"))
        for bloque in (datos, datos.get("reserva") or {}):
            if (bloque.get("bucket") or bloque.get("bucket_variable")) and bloque.get("punto_s3"):
                destinos.append(
                    copias.Destino(
                        bloque["ubicacion"], bloque["punto_s3"], buckets.nombre(bloque), "", {}
                    )
                )
    return destinos


def comprobar(
    credenciales: copias.Credenciales, enviar: copias.Enviar = copias.enviar_http
) -> list[tuple[str, bool, str]]:
    """(prueba, correcta, detalle) de cada comprobación de la credencial de lectura."""
    resultados: list[tuple[str, bool, str]] = []
    cliente = copias.Copias(exportaciones.destino(), credenciales, enviar)
    try:
        versiones = exportaciones.versiones(cliente)
        resultados.append(("listar las versiones", bool(versiones), f"{len(versiones)} versiones"))
    except OSError as error:
        versiones = []
        resultados.append(("listar las versiones", False, str(error)[:120]))
    if versiones:
        prefijo = exportaciones.prefijo_version(cliente, versiones[-1])
        manifiesto = json.loads(cliente.bajar(prefijo + exportaciones.MANIFIESTO))
        entrada = min(manifiesto["ficheros"], key=lambda e: e["cifrado"]["bytes"])
        cuerpo = cliente.bajar(prefijo + entrada["cifrado"]["nombre"])
        bien = hashlib.sha256(cuerpo).hexdigest() == entrada["cifrado"]["sha256"]
        resultados.append((f"descargar {versiones[-1]}/{entrada['cifrado']['nombre']}", bien,
                           "huella del manifiesto"))  # fmt: skip
    prueba = cliente.destino.prefijo + "prueba-escritura-lectura.txt"
    escrita = cliente._peticion("PUT", prueba, b"no")
    resultados.append(("NO escribir en el bucket", escrita.estado in (401, 403),
                       f"PUT {escrita.estado}"))  # fmt: skip
    if escrita.estado in (200, 204):
        cliente._peticion("DELETE", prueba)
    if versiones:
        borrada = cliente._peticion(
            "DELETE", exportaciones.prefijo_version(cliente, versiones[-1]) + "no-existe"
        )
        resultados.append(("NO borrar en el bucket", borrada.estado in (401, 403),
                           f"DELETE {borrada.estado}"))  # fmt: skip
    for destino in _otros_destinos():
        otro = copias.Copias(destino, credenciales, enviar)
        lista = otro._peticion("GET", consulta="list-type=2&max-keys=1")
        resultados.append((f"NO listar {destino.bucket}", lista.estado in (401, 403),
                           f"GET {lista.estado}"))  # fmt: skip
        escrita = otro._peticion("PUT", "prueba-escritura-lectura.txt", b"no")
        resultados.append((f"NO escribir en {destino.bucket}", escrita.estado in (401, 403),
                           f"PUT {escrita.estado}"))  # fmt: skip
        if escrita.estado in (200, 204):
            otro._peticion("DELETE", "prueba-escritura-lectura.txt")
    return resultados


def principal(argumentos: list[str] | None = None) -> int:
    opciones = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = opciones.add_subparsers(dest="orden", required=True)
    p = sub.add_parser("politica")
    p.add_argument("--proyecto", required=True)
    p.add_argument("--clave-id", required=True)
    c = sub.add_parser("comprobar")
    c.add_argument("--credenciales", type=Path, required=True)
    args = opciones.parse_args(argumentos)
    if args.orden == "politica":
        return poner_politica(exportaciones.cliente(), principal_de(args.proyecto, args.clave_id))
    resultados = comprobar(_credenciales(args.credenciales))
    for prueba, correcta, detalle in resultados:
        sys.stdout.write(f"{'bien' if correcta else 'MAL '}  {prueba}: {detalle}\n")
    return 0 if resultados and all(c for _, c, _ in resultados) else 1


if __name__ == "__main__":
    sys.exit(principal())
