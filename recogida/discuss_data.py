"""Paquete trimestral para Discuss Data (exportacion/discuss_data.py): lo genera, lo guarda en el
almacén privado y avisa una vez al responsable para que lo suba a mano.

En el servidor lo lanza la exportación semanal (servidor/exportacion.sh), al terminar, con
`trimestral`. Hay un paquete por trimestre: la primera exportación desde el día 1 de enero, abril,
julio u octubre genera el del trimestre si aún no está en el almacén privado
(`discuss-data/eodi-incidentes-AAAA-MM-DD.zip`, en el bucket de las exportaciones), con los datos
publicados en la web en ese momento (los mismos ficheros que la descarga abierta, bajados en una
sola versión de los datos, como las versiones citables de recogida/versiones.py) y el registro de
cambios respecto al paquete anterior. Después manda un único aviso al tema privado del responsable
(el del resumen diario) con el nombre, las cifras y un enlace firmado de descarga que vale 7 días.

Nunca falla hacia fuera: sale siempre con código 0 y no cambia el código de la exportación ni el
de la recogida. Si algo falla, lo anota en `discuss_data.json` (carpeta de secretos) y se
reintenta en la exportación siguiente; solo avisa del fallo cuando lleva 2 intentos fallidos en el
trimestre, y una sola vez. Un paquete publicado no se sobrescribe ni se borra.

Uso: python -m recogida.discuss_data trimestral                 # en el servidor
     python -m recogida.discuss_data generar --salida <carpeta> [--anterior <zip>] [--fecha F]
     python -m recogida.discuss_data bajar --destino <carpeta> [--nombre <zip>]
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import logging
import os
import sys
import time
import urllib.parse
from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from almacen import copias, exportaciones
from almacen.sitio import casa
from exportacion import discuss_data as paquete
from recogida import versiones
from recogida.almacen_publico import ALGORITMO, SERVICIO

registro = logging.getLogger("discuss_data")

RAIZ = Path(__file__).resolve().parent.parent
PREFIJO = "discuss-data/"
# Otro prefijo del bucket para un ensayo.
VARIABLE_PREFIJO = "EODI_DISCUSS_DATA_PREFIJO"
REGISTRO = "discuss_data.json"
INTENTOS_ANTES_DE_AVISAR = 2
VALIDEZ_ENLACE_S = 7 * 24 * 3600
TITULO_AVISO = "EODI · Discuss Data"

Leer = Callable[[str], bytes]
Avisar = Callable[[str], None]


def _leer_json(ruta: Path) -> dict[str, Any]:
    return json.loads(ruta.read_text(encoding="utf-8"))  # type: ignore[no-any-return]


def entradas() -> dict[str, Any]:
    """Lo que el paquete toma del repositorio: licencia, avisos, nombres de país y la cita."""
    avisos = _leer_json(RAIZ / "configuracion" / "avisos.json")
    return {
        "licencia": _leer_json(RAIZ / "configuracion" / "licencia_datos.json"),
        "avisos": avisos,
        "nombres_pais": {c: v["en"] for c, v in avisos["paises"].items()},
        "repositorio_cff": (RAIZ / "CITATION.cff").read_text(encoding="utf-8"),
    }


def bajar_web(leer: Leer, dormir: Callable[[float], None] = time.sleep) -> tuple[
    dict[str, bytes], str
]:  # fmt: skip
    """Los ficheros de la descarga abierta (una sola versión de los datos) y la metodología."""
    conf = {**versiones.configuracion(), "ficheros": dict.fromkeys(paquete.FICHEROS, "")}
    resumen, ficheros = versiones.bajar_version(leer, conf, dormir)
    ficheros[paquete.RESUMEN] = json.dumps(resumen).encode("utf-8")
    pagina = leer(paquete.METODOLOGIA_EN).decode("utf-8")
    return ficheros, pagina


def generar(
    leer: Leer, fecha: date, anterior: tuple[date, paquete.Incidentes] | None
) -> tuple[bytes, dict[str, Any]]:
    ficheros, pagina = bajar_web(leer)
    return paquete.construir(ficheros, pagina, fecha, anterior=anterior, **entradas())


# --- El almacén privado -------------------------------------------------------------------------


def cliente() -> copias.Copias:
    """El bucket privado de las exportaciones, con el prefijo de los paquetes."""
    prefijo = os.environ.get(VARIABLE_PREFIJO) or PREFIJO
    destino = replace(exportaciones.destino(), prefijo=prefijo)
    return copias.Copias(destino, copias.Credenciales.cargar())


def publicados(almacen: copias.Copias) -> list[tuple[date, str]]:
    """Los paquetes del almacén, del más antiguo al más nuevo: (fecha, objeto)."""
    hallados = []
    for objeto in almacen.listar(almacen.destino.prefijo):
        fecha = paquete.fecha_de_nombre(objeto.clave)
        if fecha is not None:
            hallados.append((fecha, objeto.clave))
    return sorted(hallados)


def url_firmada(
    almacen: copias.Copias, objeto: str, momento: datetime, validez_s: int = VALIDEZ_ENLACE_S
) -> str:
    """Enlace de descarga firmado (SigV4 en la consulta) que caduca a los `validez_s` segundos."""
    destino, credenciales = almacen.destino, almacen.credenciales
    partes = urllib.parse.urlsplit(destino.url(objeto))
    fecha_hora = momento.astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")
    ambito = f"{fecha_hora[:8]}/{destino.ubicacion}/{SERVICIO}/aws4_request"
    parametros = {
        "X-Amz-Algorithm": ALGORITMO,
        "X-Amz-Credential": f"{credenciales.clave_id}/{ambito}",
        "X-Amz-Date": fecha_hora,
        "X-Amz-Expires": str(validez_s),
        "X-Amz-SignedHeaders": "host",
    }
    consulta = "&".join(
        f"{urllib.parse.quote(k, safe='-_.~')}={urllib.parse.quote(v, safe='-_.~')}"
        for k, v in sorted(parametros.items())
    )
    canonica = "\n".join(
        ["GET", partes.path, consulta, f"host:{partes.netloc}\n", "host", "UNSIGNED-PAYLOAD"]
    )
    texto = "\n".join(
        [ALGORITMO, fecha_hora, ambito, hashlib.sha256(canonica.encode("utf-8")).hexdigest()]
    )
    clave = f"AWS4{credenciales.secreto}".encode()
    for parte in (fecha_hora[:8], destino.ubicacion, SERVICIO, "aws4_request"):
        clave = hmac.new(clave, parte.encode("utf-8"), hashlib.sha256).digest()
    firma = hmac.new(clave, texto.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{partes.scheme}://{partes.netloc}{partes.path}?{consulta}&X-Amz-Signature={firma}"


# --- La pasada trimestral -----------------------------------------------------------------------


def leer_registro(ruta: Path) -> dict[str, Any]:
    try:
        datos = json.loads(ruta.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return datos if isinstance(datos, dict) else {}


def escribir_registro(ruta: Path, datos: dict[str, Any]) -> None:
    temporal = ruta.with_name(ruta.name + ".tmp")
    temporal.write_text(
        json.dumps(datos, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n"
    )
    os.replace(temporal, ruta)


def texto_aviso(resumen: dict[str, Any], enlace: str, objeto: str) -> str:
    return (
        f"Nueva versión del paquete para Discuss Data lista para subir: {resumen['nombre']} "
        f"({resumen['incidentes']} incidentes, {resumen['paises']} países, datos de "
        f"{resumen['corte']}).\n"
        f"Descarga (el enlace vale 7 días): {enlace}\n"
        f"Está en el almacén privado de las exportaciones ({objeto}). Desde el ordenador: "
        "python -m recogida.discuss_data bajar --destino <carpeta>"
    )


def trimestral(
    almacen: copias.Copias,
    ruta_registro: Path,
    ahora: datetime,
    avisar: Avisar | None,
    leer: Leer = versiones.leer_http,
) -> dict[str, Any]:
    """Genera el paquete del trimestre si falta, lo guarda y avisa. Nunca lanza excepciones."""
    datos = leer_registro(ruta_registro)
    hoy = ahora.astimezone(UTC).date()
    trimestre = paquete.trimestre(hoy)
    estado: dict[str, Any] = dict(datos.get("trimestres", {}).get(trimestre, {}))
    try:
        hechos = publicados(almacen)
        del_trimestre = [o for f, o in hechos if paquete.trimestre(f) == trimestre]
        if del_trimestre:
            estado.setdefault("objeto", del_trimestre[-1])
            registro.info("paquete del trimestre %s ya guardado: %s", trimestre, del_trimestre[-1])
        else:
            anterior = None
            if hechos:
                fecha_anterior, objeto_anterior = hechos[-1]
                anterior = (fecha_anterior, paquete.leer_paquete(almacen.bajar(objeto_anterior)))
            cuerpo, resumen = generar(leer, hoy, anterior)
            objeto = almacen.destino.prefijo + resumen["nombre"]
            almacen.subir(objeto, cuerpo, {"Content-Type": "application/zip"})
            estado.update(
                objeto=objeto,
                generado=ahora.strftime("%Y-%m-%dT%H:%M:%SZ"),
                sha256=hashlib.sha256(cuerpo).hexdigest(),
                bytes=len(cuerpo),
                resumen=resumen,
                fallo=None,
            )
            registro.info(
                "paquete %s guardado: %d incidentes, %d países, sha256 %s",
                resumen["nombre"], resumen["incidentes"], resumen["paises"], estado["sha256"],
            )  # fmt: skip
        if not estado.get("avisado") and estado.get("resumen") and avisar is not None:
            enlace = url_firmada(almacen, estado["objeto"], ahora)
            avisar(texto_aviso(estado["resumen"], enlace, estado["objeto"]))
            estado["avisado"] = ahora.strftime("%Y-%m-%dT%H:%M:%SZ")
            registro.info("aviso enviado al responsable")
    except Exception as error:  # la capa nunca falla hacia fuera
        estado["intentos_fallidos"] = int(estado.get("intentos_fallidos", 0)) + 1
        estado["fallo"] = f"{ahora:%Y-%m-%dT%H:%M:%SZ} {type(error).__name__}: {error}"
        registro.warning(
            "el paquete del trimestre %s no se ha hecho (intento %d): %s",
            trimestre, estado["intentos_fallidos"], error,
        )  # fmt: skip
        if (
            estado["intentos_fallidos"] >= INTENTOS_ANTES_DE_AVISAR
            and not estado.get("fallo_avisado")
            and avisar is not None
        ):
            try:
                avisar(
                    f"El paquete trimestral para Discuss Data ({trimestre}) lleva "
                    f"{estado['intentos_fallidos']} intentos fallidos. Último: {estado['fallo']}. "
                    "Se reintenta en la exportación siguiente."
                )
                estado["fallo_avisado"] = ahora.strftime("%Y-%m-%dT%H:%M:%SZ")
            except Exception as error_aviso:
                registro.warning("no se pudo avisar del fallo: %s", error_aviso)
    datos.setdefault("trimestres", {})[trimestre] = estado
    try:
        escribir_registro(ruta_registro, datos)
    except OSError as error:
        registro.warning("no se pudo escribir el registro: %s", error)
    return estado


def principal(argumentos: list[str] | None = None) -> int:
    opciones = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = opciones.add_subparsers(dest="orden", required=True)
    sub.add_parser("trimestral")
    g = sub.add_parser("generar")
    g.add_argument("--salida", type=Path, required=True)
    g.add_argument("--anterior", type=Path, help="paquete anterior, para el registro de cambios")
    g.add_argument("--fecha", type=date.fromisoformat, help="por defecto, hoy (UTC)")
    b = sub.add_parser("bajar")
    b.add_argument("--destino", type=Path, required=True)
    b.add_argument("--nombre", help="por defecto, el último")
    args = opciones.parse_args(argumentos)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    ahora = datetime.now(UTC)
    if args.orden == "generar":
        fecha = args.fecha or ahora.date()
        anterior = None
        if args.anterior is not None:
            previa = paquete.fecha_de_nombre(args.anterior.name)
            if previa is None:
                opciones.error("--anterior tiene que llamarse eodi-incidentes-AAAA-MM-DD.zip")
            anterior = (previa, paquete.leer_paquete(args.anterior.read_bytes()))
        cuerpo, resumen = generar(versiones.leer_http, fecha, anterior)
        args.salida.mkdir(parents=True, exist_ok=True)
        destino = args.salida / resumen["nombre"]
        if destino.exists():
            registro.error("%s ya existe: no se sobrescribe", destino)
            return 1
        destino.write_bytes(cuerpo)
        resumen["sha256"] = hashlib.sha256(cuerpo).hexdigest()
        sys.stdout.write(json.dumps(resumen, ensure_ascii=False, indent=1) + "\n")
        return 0
    if args.orden == "bajar":
        almacen = cliente()
        hechos = publicados(almacen)
        elegido = next(
            (o for _, o in reversed(hechos) if not args.nombre or o.endswith("/" + args.nombre)),
            None,
        )
        if elegido is None:
            registro.error("no hay ningún paquete%s", f" {args.nombre}" if args.nombre else "")
            return 1
        args.destino.mkdir(parents=True, exist_ok=True)
        destino = args.destino / elegido.rsplit("/", 1)[-1]
        if destino.exists():
            registro.error("%s ya existe: no se sobrescribe", destino)
            return 1
        destino.write_bytes(almacen.bajar(elegido))
        sys.stdout.write(f"{destino}\n")
        return 0
    from recogida import visitas

    secretos = Path(os.environ.get("EODI_SECRETOS") or casa() / ".eodi")
    try:
        almacen = cliente()
        avisar = visitas.avisador_privado(TITULO_AVISO, secretos)
    except Exception as error:  # la capa nunca falla hacia fuera
        # Sin almacén no se puede hacer nada: se anota y se reintenta la semana siguiente.
        registro.warning("el paquete trimestral no se puede preparar: %s", error)
        return 0
    trimestral(almacen, secretos / REGISTRO, ahora, avisar)
    return 0


if __name__ == "__main__":
    sys.exit(principal())
