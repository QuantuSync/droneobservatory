"""Almacén público de la web: dónde está y cómo se sube un fichero desde el servidor.

El almacén es un bucket compatible con S3 (Hetzner Object Storage) con las teselas del mapa
de fondo y estado.json. Su dirección no está en el código: sale de
configuracion/almacen_publico.json, que leen también la vigilancia (recogida/salud.py), la
preparación del bucket (servidor/preparar_almacen.py) y la web.

La subida firma la petición con AWS Signature Version 4 sin dependencias, con las
credenciales en el entorno (ALMACEN_ID y ALMACEN_SECRETO; nunca en la línea de órdenes).
Reintenta con espera creciente dentro de un tope total. Un fallo nunca es un error de la
recogida: sale con código 1, que servidor/recogida.sh deja como aviso en el diario.

Uso: python -m recogida.almacen_publico subir --fichero <ruta> --objeto estado.json \
         [--tipo application/json] [--cache "public, max-age=60"]
"""

import argparse
import hashlib
import hmac
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

RAIZ = Path(__file__).resolve().parent.parent
CONFIGURACION = RAIZ / "configuracion" / "almacen_publico.json"
VARIABLE_ID = "ALMACEN_ID"
VARIABLE_SECRETO = "ALMACEN_SECRETO"
SERVICIO = "s3"
ALGORITMO = "AWS4-HMAC-SHA256"
# Tres intentos con 2 y 4 s entre ellos; cada uno con su tope y todos dentro del total.
INTENTOS = 3
ESPERA_INICIAL_S = 2.0
TOPE_INTENTO_S = 20.0
TOPE_TOTAL_S = 60.0
# Lo que no se arregla repitiendo (credenciales, permisos, bucket inexistente): un intento.
CODIGOS_DEFINITIVOS = frozenset({400, 401, 403, 404})


@dataclass(frozen=True)
class Almacen:
    ubicacion: str
    punto_s3: str
    bucket: str
    publico: str
    objetos: dict[str, str]

    def url_publica(self, objeto: str) -> str:
        return f"{self.publico.rstrip('/')}/{objeto}"

    def url_s3(self, objeto: str) -> str:
        """Dirección con el bucket en la ruta, que firma igual en cualquier proveedor S3."""
        return f"{self.punto_s3.rstrip('/')}/{self.bucket}/{urllib.parse.quote(objeto)}"


def cargar(ruta: Path = CONFIGURACION) -> Almacen:
    datos: dict[str, Any] = json.loads(ruta.read_text(encoding="utf-8"))
    for campo in ("ubicacion", "punto_s3", "bucket", "publico"):
        valor = datos.get(campo)
        if not isinstance(valor, str) or not valor:
            raise ValueError(f"{ruta.name}: falta {campo}")
    for campo in ("punto_s3", "publico"):
        if urllib.parse.urlsplit(datos[campo]).scheme != "https":
            raise ValueError(f"{ruta.name}: {campo} tiene que ser https")
    return Almacen(
        ubicacion=datos["ubicacion"],
        punto_s3=datos["punto_s3"],
        bucket=datos["bucket"],
        publico=datos["publico"],
        objetos=dict(datos.get("objetos", {})),
    )


def _hmac(clave: bytes, texto: str) -> bytes:
    return hmac.new(clave, texto.encode("utf-8"), hashlib.sha256).digest()


def firmar(
    metodo: str,
    url: str,
    cabeceras: Mapping[str, str],
    huella_cuerpo: str,
    region: str,
    clave_id: str,
    secreto: str,
    momento: datetime,
) -> dict[str, str]:
    """Las cabeceras de la petición con su firma SigV4 (Authorization, x-amz-date, host…)."""
    partes = urllib.parse.urlsplit(url)
    fecha_hora = momento.astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")
    fecha = fecha_hora[:8]
    todas = {k.lower(): " ".join(v.split()) for k, v in cabeceras.items()}
    todas["host"] = partes.netloc
    todas["x-amz-date"] = fecha_hora
    todas["x-amz-content-sha256"] = huella_cuerpo
    firmadas = ";".join(sorted(todas))
    consulta = "&".join(
        f"{urllib.parse.quote(k, safe='-_.~')}={urllib.parse.quote(v, safe='-_.~')}"
        for k, v in sorted(urllib.parse.parse_qsl(partes.query, keep_blank_values=True))
    )
    canonica = "\n".join(
        [
            metodo,
            urllib.parse.quote(partes.path or "/", safe="/-_.~%"),
            consulta,
            "".join(f"{k}:{todas[k]}\n" for k in sorted(todas)),
            firmadas,
            huella_cuerpo,
        ]
    )
    ambito = f"{fecha}/{region}/{SERVICIO}/aws4_request"
    texto = "\n".join(
        [ALGORITMO, fecha_hora, ambito, hashlib.sha256(canonica.encode("utf-8")).hexdigest()]
    )
    clave = _hmac(f"AWS4{secreto}".encode(), fecha)
    for parte in (region, SERVICIO, "aws4_request"):
        clave = _hmac(clave, parte)
    firma = hmac.new(clave, texto.encode("utf-8"), hashlib.sha256).hexdigest()
    todas["authorization"] = (
        f"{ALGORITMO} Credential={clave_id}/{ambito}, SignedHeaders={firmadas}, Signature={firma}"
    )
    return todas


Envio = Callable[[urllib.request.Request, float], int]


def _enviar(peticion: urllib.request.Request, tope_s: float) -> int:
    with urllib.request.urlopen(peticion, timeout=tope_s) as respuesta:
        estado: int = respuesta.status
        return estado


def subir(
    almacen: Almacen,
    objeto: str,
    cuerpo: bytes,
    clave_id: str,
    secreto: str,
    tipo: str = "application/octet-stream",
    cache: str | None = None,
    enviar: Envio = _enviar,
    dormir: Callable[[float], None] = time.sleep,
    reloj: Callable[[], float] = time.monotonic,
    ahora: Callable[[], datetime] = lambda: datetime.now(UTC),
    codificacion: str | None = None,
) -> tuple[bool, str]:
    """Sube un objeto con reintentos de espera creciente. Nunca lanza: (correcto, motivo)."""
    url = almacen.url_s3(objeto)
    huella = hashlib.sha256(cuerpo).hexdigest()
    cabeceras = {"Content-Type": tipo}
    if cache:
        cabeceras["Cache-Control"] = cache
    if codificacion:
        cabeceras["Content-Encoding"] = codificacion
    inicio = reloj()
    espera = ESPERA_INICIAL_S
    motivo, hechos = "sin intentos", 0
    for intento in range(INTENTOS):
        if intento:
            if reloj() - inicio + espera >= TOPE_TOTAL_S:
                break
            dormir(espera)
            espera *= 2
        firmadas = firmar(
            "PUT", url, cabeceras, huella, almacen.ubicacion, clave_id, secreto, ahora()
        )
        firmadas.pop("host")
        peticion = urllib.request.Request(url, data=cuerpo, method="PUT", headers=firmadas)
        tope = min(TOPE_INTENTO_S, max(1.0, TOPE_TOTAL_S - (reloj() - inicio)))
        hechos += 1
        try:
            estado = enviar(peticion, tope)
        except urllib.error.HTTPError as error:
            motivo = f"HTTP {error.code}"
            if error.code in CODIGOS_DEFINITIVOS:
                return False, f"{motivo} (definitivo, sin reintentar)"
            continue
        except (OSError, ValueError) as error:
            motivo = type(error).__name__
            continue
        if 200 <= estado < 300:
            return True, f"subido en el intento {intento + 1}"
        motivo = f"HTTP {estado}"
    return False, f"{motivo} tras {hechos} intentos"


def borrar(
    almacen: Almacen,
    objeto: str,
    clave_id: str,
    secreto: str,
    enviar: Envio = _enviar,
    ahora: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> tuple[bool, str]:
    """Borra un objeto (DELETE firmado). Borrar uno que ya no está también es correcto. Nunca
    lanza: (correcto, motivo)."""
    url = almacen.url_s3(objeto)
    motivo = "sin intentos"
    for intento in range(2):
        firmadas = firmar(
            "DELETE",
            url,
            {},
            hashlib.sha256(b"").hexdigest(),
            almacen.ubicacion,
            clave_id,
            secreto,
            ahora(),
        )
        firmadas.pop("host")
        peticion = urllib.request.Request(url, method="DELETE", headers=firmadas)
        try:
            estado = enviar(peticion, TOPE_INTENTO_S)
        except urllib.error.HTTPError as error:
            if error.code == 404:
                return True, "no estaba"
            motivo = f"HTTP {error.code}"
            continue
        except (OSError, ValueError) as error:
            motivo = type(error).__name__
            continue
        if 200 <= estado < 300:
            return True, f"borrado en el intento {intento + 1}"
        motivo = f"HTTP {estado}"
    return False, motivo


def principal(
    argumentos: list[str] | None = None,
    entorno: Mapping[str, str] = os.environ,
    enviar: Envio = _enviar,
    dormir: Callable[[float], None] = time.sleep,
) -> int:
    opciones = argparse.ArgumentParser(description=__doc__)
    ordenes = opciones.add_subparsers(dest="orden", required=True)
    orden = ordenes.add_parser("subir")
    orden.add_argument("--fichero", type=Path, required=True)
    orden.add_argument("--objeto", required=True)
    orden.add_argument("--tipo", default="application/octet-stream")
    orden.add_argument("--cache")
    orden.add_argument("--configuracion", type=Path, default=CONFIGURACION)
    args = opciones.parse_args(argumentos)
    clave_id, secreto = entorno.get(VARIABLE_ID, ""), entorno.get(VARIABLE_SECRETO, "")
    if not clave_id or not secreto:
        print(f"sin {VARIABLE_ID} o {VARIABLE_SECRETO}: no se sube {args.objeto}")
        return 1
    try:
        almacen = cargar(args.configuracion)
        cuerpo = args.fichero.read_bytes()
    except (OSError, ValueError) as error:
        print(f"no se sube {args.objeto}: {error}")
        return 1
    correcto, motivo = subir(
        almacen, args.objeto, cuerpo, clave_id, secreto, args.tipo, args.cache, enviar, dormir
    )
    print(f"{args.objeto}: {motivo}")
    return 0 if correcto else 1


if __name__ == "__main__":
    sys.exit(principal())
