"""Prepara el almacén público (configuracion/almacen_publico.json) y le copia las teselas.

Pasos, todos repetibles (lo que ya está bien se deja como está):

1. crea el bucket si no existe;
2. lo deja de lectura pública (política del bucket: solo s3:GetObject para todos);
3. le pone el CORS de la configuración (orígenes de la web, GET y HEAD, cabecera Range);
4. copia el fichero de teselas, por partes de 128 MiB y sin pasar por el disco: desde un
   fichero local (--fichero), desde el bucket R2 anterior por su API S3 (--desde-r2, con
   R2_ID, R2_SECRETO y R2_CUENTA en el entorno) o, para la reserva, desde el almacén
   principal por su dirección pública (--desde-principal). Comprueba mientras sube la huella SHA-256
   anotada en la configuración (huellas_sha256) y, si no coincide, aborta la subida sin
   dejar nada a medias;
5. comprueba por la dirección pública: tamaño, respuesta 206 a una petición Range con la
   cabecera de PMTiles, CORS para cada origen y que estado.json, si ya está, responde.

Con --reserva hace lo mismo con la copia pública de reserva (bloque «reserva» de la
configuración: otro bucket, en otra ubicación, con el mismo CORS). Los demás objetos de la
reserva los copia y los tiene al día almacen/reserva.py.

Las credenciales del almacén van en el entorno (ALMACEN_ID y ALMACEN_SECRETO). Necesita
boto3 (servidor/requisitos_almacen.txt); no es una dependencia de la recogida.

Uso: python servidor/preparar_almacen.py (--fichero <ruta> | --desde-r2 | --desde-principal)
         [--reserva] [--configuracion configuracion/almacen_publico.json] [--solo-comprobar]
Lo lanza servidor/preparar_almacen.sh, que deja antes las credenciales en el servidor.
"""

import argparse
import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

RAIZ = Path(__file__).resolve().parent.parent
CONFIGURACION = RAIZ / "configuracion" / "almacen_publico.json"
PARTE = 128 * 1024 * 1024
CACHE_TESELAS = "public, max-age=3600"
CABECERA_PMTILES = b"PMTiles"
R2_BUCKET = "eodi-teselas"
AGENTE = "EODI-bot/1.0 (+https://droneobservatory.eu)"


def cliente(punto: str, region: str, clave: str, secreto: str) -> Any:
    return boto3.client(
        "s3",
        endpoint_url=punto,
        region_name=region,
        aws_access_key_id=clave,
        aws_secret_access_key=secreto,
        config=Config(
            retries={"max_attempts": 6, "mode": "standard"},
            s3={"addressing_style": "path"},
            request_checksum_calculation="when_required",
            response_checksum_validation="when_required",
        ),
    )


def politica_publica(bucket: str) -> str:
    return json.dumps(
        {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Sid": "LecturaPublica",
                    "Effect": "Allow",
                    "Principal": "*",
                    "Action": ["s3:GetObject"],
                    "Resource": [f"arn:aws:s3:::{bucket}/*"],
                }
            ],
        }
    )


def reglas_cors(cors: dict[str, Any]) -> dict[str, Any]:
    return {
        "CORSRules": [
            {
                "AllowedOrigins": cors["origenes"],
                "AllowedMethods": cors["metodos"],
                "AllowedHeaders": cors["cabeceras"],
                "ExposeHeaders": cors["expuestas"],
                "MaxAgeSeconds": cors["max_edad_s"],
            }
        ]
    }


def preparar_bucket(s3: Any, configuracion: dict[str, Any]) -> None:
    bucket = configuracion["bucket"]
    try:
        s3.head_bucket(Bucket=bucket)
        print(f"bucket {bucket}: ya existe")
    except ClientError:
        try:
            s3.create_bucket(Bucket=bucket)
        except ClientError as error:
            # Algunos puntos S3 piden la ubicación explícita al crear el bucket.
            if error.response["Error"]["Code"] != "IllegalLocationConstraintException":
                raise
            s3.create_bucket(
                Bucket=bucket,
                CreateBucketConfiguration={"LocationConstraint": configuracion["ubicacion"]},
            )
        print(f"bucket {bucket}: creado en {configuracion['ubicacion']}")
        # Un bucket recién creado tarda unos segundos en aceptar su política (NoSuchBucket).
        for _ in range(30):
            try:
                s3.head_bucket(Bucket=bucket)
                break
            except ClientError:
                time.sleep(2)
    s3.put_bucket_policy(Bucket=bucket, Policy=politica_publica(bucket))
    print("lectura pública: política aplicada")
    s3.put_bucket_cors(Bucket=bucket, CORSConfiguration=reglas_cors(configuracion["cors"]))
    print(f"CORS: {', '.join(configuracion['cors']['origenes'])}")


def partes_de_fichero(ruta: Path) -> Iterator[bytes]:
    with ruta.open("rb") as fichero:
        while bloque := fichero.read(PARTE):
            yield bloque


def partes_de_r2(r2: Any, objeto: str, tamano: int) -> Iterator[bytes]:
    for inicio in range(0, tamano, PARTE):
        fin = min(inicio + PARTE, tamano) - 1
        respuesta = r2.get_object(Bucket=R2_BUCKET, Key=objeto, Range=f"bytes={inicio}-{fin}")
        bloque: bytes = respuesta["Body"].read()
        if len(bloque) != fin - inicio + 1:
            raise RuntimeError(f"R2 devolvió {len(bloque)} bytes para {inicio}-{fin}")
        yield bloque


def partes_del_principal(url: str, tamano: int) -> Iterator[bytes]:
    """El fichero del almacén principal por partes, con peticiones Range a su dirección pública."""
    for inicio in range(0, tamano, PARTE):
        fin = min(inicio + PARTE, tamano) - 1
        for intento in range(5):
            try:
                peticion = urllib.request.Request(
                    url, headers={"User-Agent": AGENTE, "Range": f"bytes={inicio}-{fin}"}
                )
                with urllib.request.urlopen(peticion, timeout=120) as respuesta:
                    bloque: bytes = respuesta.read()
                if len(bloque) == fin - inicio + 1:
                    break
            except OSError:
                if intento == 4:
                    raise
        else:
            raise RuntimeError(f"el principal devolvió {len(bloque)} bytes para {inicio}-{fin}")
        yield bloque


def de_la_reserva(configuracion: dict[str, Any]) -> dict[str, Any]:
    """La configuración de la reserva: la del principal con su bucket, ubicación y dirección."""
    reserva = configuracion["reserva"]
    return {
        **configuracion,
        **{c: reserva[c] for c in ("ubicacion", "punto_s3", "bucket", "publico")},
        "principal": configuracion["publico"],
    }


def ya_copiado(s3: Any, bucket: str, objeto: str, tamano: int, huella: str) -> bool:
    try:
        cabecera = s3.head_object(Bucket=bucket, Key=objeto)
    except ClientError:
        return False
    return bool(
        cabecera["ContentLength"] == tamano and cabecera.get("Metadata", {}).get("sha256") == huella
    )


def copiar(
    s3: Any, bucket: str, objeto: str, partes: Iterator[bytes], tamano: int, huella: str
) -> None:
    subida = s3.create_multipart_upload(
        Bucket=bucket,
        Key=objeto,
        ContentType="application/octet-stream",
        CacheControl=CACHE_TESELAS,
        Metadata={"sha256": huella},
    )
    ident, hechas, sha, enviados = subida["UploadId"], [], hashlib.sha256(), 0
    try:
        for numero, bloque in enumerate(partes, start=1):
            sha.update(bloque)
            respuesta = s3.upload_part(
                Bucket=bucket, Key=objeto, UploadId=ident, PartNumber=numero, Body=bloque
            )
            hechas.append({"PartNumber": numero, "ETag": respuesta["ETag"]})
            enviados += len(bloque)
            print(f"  parte {numero}: {enviados / 1e9:.2f} de {tamano / 1e9:.2f} GB", flush=True)
        if enviados != tamano or sha.hexdigest() != huella:
            raise RuntimeError(f"la copia no coincide: {enviados} bytes, sha256 {sha.hexdigest()}")
        s3.complete_multipart_upload(
            Bucket=bucket, Key=objeto, UploadId=ident, MultipartUpload={"Parts": hechas}
        )
    except BaseException:
        s3.abort_multipart_upload(Bucket=bucket, Key=objeto, UploadId=ident)
        raise
    print(f"{objeto}: copiado, {tamano} bytes, sha256 {huella}")


def pedir(
    url: str, cabeceras: dict[str, str], metodo: str = "GET"
) -> tuple[int, dict[str, str], bytes]:
    peticion = urllib.request.Request(
        url, headers={"User-Agent": AGENTE, **cabeceras}, method=metodo
    )
    try:
        with urllib.request.urlopen(peticion, timeout=30) as respuesta:
            return respuesta.status, dict(respuesta.headers), respuesta.read(64)
    except urllib.error.HTTPError as error:
        return error.code, dict(error.headers or {}), b""


def comprobar(configuracion: dict[str, Any], tamano: int | None) -> list[str]:
    """Comprobaciones por la dirección pública; devuelve los problemas encontrados."""
    problemas: list[str] = []
    base = configuracion["publico"].rstrip("/")
    teselas = f"{base}/{configuracion['objetos']['teselas']}"
    codigo, cabeceras, _ = pedir(teselas, {}, "HEAD")
    largo = int({k.lower(): v for k, v in cabeceras.items()}.get("content-length", -1))
    print(f"HEAD teselas: {codigo}, {largo} bytes")
    if codigo != 200 or (tamano is not None and largo != tamano):
        problemas.append(f"teselas: HEAD {codigo}, {largo} bytes")
    for origen in configuracion["cors"]["origenes"]:
        codigo, cabeceras, cuerpo = pedir(teselas, {"Range": "bytes=0-6", "Origin": origen})
        minusculas = {k.lower(): v for k, v in cabeceras.items()}
        permitido = minusculas.get("access-control-allow-origin")
        print(f"Range desde {origen}: {codigo}, {cuerpo!r}, CORS {permitido}")
        if codigo != 206 or cuerpo != CABECERA_PMTILES or permitido not in (origen, "*"):
            problemas.append(f"Range/CORS desde {origen}: {codigo} {cuerpo!r} {permitido}")
    estado = f"{base}/{configuracion['objetos']['estado']}"
    codigo, _, _ = pedir(estado, {"Origin": configuracion["cors"]["origenes"][0]})
    # Con lectura pública solo de objetos (sin listar), un objeto que aún no existe responde
    # 403 y no 404: estado.json lo sube la recogida y puede no estar todavía.
    print(f"estado.json: {codigo}" + ("" if codigo == 200 else " (aún no publicado)"))
    if codigo not in (200, 403, 404):
        problemas.append(f"estado.json: {codigo}")
    return problemas


def principal(argumentos: list[str] | None = None) -> int:
    opciones = argparse.ArgumentParser(description=__doc__)
    origen = opciones.add_mutually_exclusive_group()
    origen.add_argument("--fichero", type=Path)
    origen.add_argument("--desde-r2", action="store_true")
    origen.add_argument("--desde-principal", action="store_true")
    opciones.add_argument("--reserva", action="store_true", help="la copia de reserva")
    opciones.add_argument(
        "--forzar",
        action="store_true",
        help="sube las teselas aunque ya estén con la misma huella (una subida nueva queda en "
        "otro sitio del almacén: arregla un trozo que se lee lento)",
    )
    opciones.add_argument("--configuracion", type=Path, default=CONFIGURACION)
    opciones.add_argument("--solo-comprobar", action="store_true")
    args = opciones.parse_args(argumentos)
    configuracion = json.loads(args.configuracion.read_text(encoding="utf-8"))
    if args.reserva:
        configuracion = de_la_reserva(configuracion)
    elif args.desde_principal:
        opciones.error("--desde-principal solo vale con --reserva")
    tamano: int | None = None
    if not args.solo_comprobar:
        if args.fichero is None and not args.desde_r2 and not args.desde_principal:
            opciones.error("hace falta --fichero, --desde-r2 o --desde-principal")
        s3 = cliente(
            configuracion["punto_s3"],
            configuracion["ubicacion"],
            os.environ["ALMACEN_ID"],
            os.environ["ALMACEN_SECRETO"],
        )
        preparar_bucket(s3, configuracion)
        objeto = configuracion["objetos"]["teselas"]
        huella = configuracion["huellas_sha256"][objeto]
        if args.fichero is not None:
            tamano = args.fichero.stat().st_size
            partes = partes_de_fichero(args.fichero)
        elif args.desde_principal:
            url = f"{configuracion['principal'].rstrip('/')}/{objeto}"
            codigo, cabeceras, _ = pedir(url, {}, "HEAD")
            if codigo != 200:
                print(f"el principal no responde: HEAD {codigo}")
                return 1
            tamano = int({k.lower(): v for k, v in cabeceras.items()}["content-length"])
            partes = partes_del_principal(url, tamano)
        else:
            r2 = cliente(
                f"https://{os.environ['R2_CUENTA']}.r2.cloudflarestorage.com",
                "auto",
                os.environ["R2_ID"],
                os.environ["R2_SECRETO"],
            )
            tamano = int(r2.head_object(Bucket=R2_BUCKET, Key=objeto)["ContentLength"])
            partes = partes_de_r2(r2, objeto, tamano)
        if not args.forzar and ya_copiado(s3, configuracion["bucket"], objeto, tamano, huella):
            print(f"{objeto}: ya está copiado con la misma huella")
        else:
            copiar(s3, configuracion["bucket"], objeto, partes, tamano, huella)
    problemas = comprobar(configuracion, tamano)
    for problema in problemas:
        print(f"problema: {problema}")
    return 1 if problemas else 0


if __name__ == "__main__":
    sys.exit(principal())
