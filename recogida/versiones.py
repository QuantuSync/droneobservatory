"""Versiones citables de los datos abiertos (configuracion/versiones_datos.json).

El día 1 de cada mes se congela una versión de los datos abiertos: los mismos ficheros que se
descargan de la web (/datos/incidentes.geojson, .csv…), tal cual, en el almacén público bajo
`versiones/AAAA-MM/`, con su huella SHA-256, la licencia en los metadatos de cada objeto
(`x-amz-meta-licencia`) y un `metadatos.json` con la fecha, la huella y el tamaño de cada fichero,
la licencia, cómo citarla y el número de incidentes. La web la sirve en
droneobservatory.eu/datos/versiones/AAAA-MM/ (vercel.json reescribe los ficheros hacia el
almacén) y la lista en «Metodología y datos abiertos» (`versiones/indice.json`).

**Una versión publicada nunca cambia ni se borra.** La regla:

- una versión está publicada cuando su `metadatos.json` está en el almacén (se sube el último);
- `generar` no toca una versión publicada: si ya está, no sube nada (un intento a medias, sin
  `metadatos.json`, no está publicado y se repite entero);
- nada en el código borra un objeto de `versiones/`;
- `comprobar` mira cada día cada versión del índice: que su `metadatos.json` tiene la huella
  anotada en el índice y que cada fichero tiene el tamaño, la huella y la etiqueta (ETag) de
  cuando se publicó (con `--completa`, el día 1, además lo baja entero y recalcula la huella).
  Cualquier diferencia o falta queda en `/home/eodi/.eodi/versiones.json`, y la vigilancia
  (recogida/vigilancia.py) avisa, como si el día 1 no se generara la del mes.

Los ficheros se bajan de la web en una sola versión de los datos: `resumen.json` antes y después
tiene que dar la misma hora de actualización (si una recogida publica en medio, se repite).

Uso: python -m recogida.versiones mensual       # la del mes si falta, y la comprobación
     python -m recogida.versiones comprobar [--completa]
"""

import argparse
import hashlib
import json
import logging
import os
import sys
import time
import urllib.request
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from functools import cache
from pathlib import Path
from typing import Any

from almacen import copias
from almacen.sitio import casa
from recogida import almacen_publico, licencia
from recogida.descarga import AGENTE_EODI

registro = logging.getLogger("versiones")

RAIZ = Path(__file__).resolve().parent.parent
CONFIGURACION = RAIZ / "configuracion" / "versiones_datos.json"
METADATOS = "metadatos.json"
INTENTOS = 3
TOPE_S = 120.0
CACHE_INDICE = "public, max-age=300"
# Cada cuánto tiene que haber una comprobación correcta para que la vigilancia no avise.
MAX_SIN_COMPROBAR = timedelta(days=2)

Leer = Callable[[str], bytes]


class VersionInvalida(RuntimeError):
    pass


@cache
def configuracion(ruta: Path = CONFIGURACION) -> dict[str, Any]:
    datos: dict[str, Any] = json.loads(ruta.read_text(encoding="utf-8"))
    return datos


def leer_http(url: str) -> bytes:
    peticion = urllib.request.Request(
        url, headers={"User-Agent": AGENTE_EODI, "Cache-Control": "no-cache"}
    )
    with urllib.request.urlopen(peticion, timeout=TOPE_S) as respuesta:
        datos: bytes = respuesta.read()
        return datos


def huella(datos: bytes) -> str:
    return hashlib.sha256(datos).hexdigest()


def version_de(momento: datetime) -> str:
    return f"{momento:%Y-%m}"


def toca(momento: datetime, conf: dict[str, Any] | None = None) -> bool:
    """Ya tendría que estar la versión del mes: el día de generarla, pasada la hora límite, o
    cualquier día después."""
    conf = conf or configuracion()
    dia = int(conf["dia"])
    return momento.day > dia or (momento.day == dia and momento.hour >= conf["hora_limite_utc"])


def cita(version: str, conf: dict[str, Any] | None = None) -> dict[str, str]:
    conf = conf or configuracion()
    anio = version[:4]
    return {i: conf["cita"][i].format(anio=anio, version=version) for i in ("es", "en")}


def cliente() -> copias.Copias:
    """El almacén público con las credenciales de siempre (ALMACEN_ID y ALMACEN_SECRETO)."""
    publico = almacen_publico.cargar()
    destino = copias.Destino(publico.ubicacion, publico.punto_s3, publico.bucket, "", {})
    return copias.Copias(destino, copias.Credenciales.cargar())


def bajar_version(leer: Leer, conf: dict[str, Any], dormir: Callable[[float], None]) -> tuple[
    dict[str, Any], dict[str, bytes]
]:  # fmt: skip
    """El resumen y los ficheros de una misma versión de los datos de la web."""
    origen = conf["origen"].rstrip("/") + "/datos/"
    for intento in range(INTENTOS):
        if intento:
            dormir(60.0)
        antes = json.loads(leer(origen + conf["resumen"]))
        ficheros = {nombre: leer(origen + nombre) for nombre in conf["ficheros"]}
        despues = json.loads(leer(origen + conf["resumen"]))
        if antes.get("actualizado") == despues.get("actualizado"):
            return despues, ficheros
        registro.info("los datos de la web cambiaron mientras se bajaban: se repite")
    raise VersionInvalida("los datos de la web cambiaron en cada intento")


def comprobar_ficheros(ficheros: dict[str, bytes]) -> None:
    """Lo bajado es lo que se espera: JSON que se lee, con su licencia; CSV con su cabecera."""
    for nombre, datos in ficheros.items():
        if not datos:
            raise VersionInvalida(f"{nombre} está vacío")
        if nombre.endswith((".json", ".geojson")):
            documento = json.loads(datos)
            if not isinstance(documento, dict) or "licencia" not in documento:
                raise VersionInvalida(f"{nombre} no lleva su licencia")
        elif not datos.splitlines()[0].strip():
            raise VersionInvalida(f"{nombre} no tiene cabecera")


def generar(
    almacen: copias.Copias,
    ahora: datetime,
    leer: Leer = leer_http,
    conf: dict[str, Any] | None = None,
    dormir: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    """Publica la versión del mes de `ahora` si no está. Nunca sobrescribe una publicada."""
    conf = conf or configuracion()
    version = version_de(ahora)
    carpeta = f"{conf['prefijo']}{version}/"
    if almacen.existe(carpeta + METADATOS):
        return {"version": version, "hecho": "ya_publicada"}
    resumen, ficheros = bajar_version(leer, conf, dormir)
    comprobar_ficheros(ficheros)
    cabeceras_licencia = licencia.cabeceras()
    descripcion: dict[str, Any] = {}
    etiquetas: dict[str, str] = {}
    for nombre, datos in ficheros.items():
        almacen.subir(
            carpeta + nombre, datos,
            {"Content-Type": conf["ficheros"][nombre], "Cache-Control": conf["cache"],
             "x-amz-meta-version": version, **cabeceras_licencia},
        )  # fmt: skip
        descripcion[nombre] = {"bytes": len(datos), "sha256": huella(datos)}
    metadatos = {
        "version": version,
        "nombre": f"{licencia.cargar()['titular']}, datos abiertos, versión {version}",
        "fecha": ahora.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "datos_actualizados": resumen.get("actualizado"),
        "incidentes": len(resumen.get("incidentes", [])),
        "direccion": f"{conf['direccion']}{version}/",
        "licencia": licencia.de_version(),
        "cita": cita(version, conf),
        "ficheros": descripcion,
    }
    cuerpo = (json.dumps(metadatos, ensure_ascii=False, indent=1) + "\n").encode("utf-8")
    # El último: con él la versión queda publicada.
    almacen.subir(
        carpeta + METADATOS, cuerpo,
        {"Content-Type": "application/json", "Cache-Control": conf["cache"],
         "x-amz-meta-version": version, **cabeceras_licencia},
    )  # fmt: skip
    for nombre in [*ficheros, METADATOS]:
        etiqueta = almacen.metadato(carpeta + nombre, "etag")
        if etiqueta is None:
            raise VersionInvalida(f"{nombre} no está en el almacén tras subirlo")
        etiquetas[nombre] = etiqueta
    indice = leer_indice(almacen, conf)
    entrada = {
        "version": version,
        "fecha": metadatos["fecha"],
        "datos_actualizados": metadatos["datos_actualizados"],
        "incidentes": metadatos["incidentes"],
        "metadatos_sha256": huella(cuerpo),
    }
    indice["versiones"] = sorted(
        [v for v in indice["versiones"] if v["version"] != version] + [entrada],
        key=lambda v: str(v["version"]),
        reverse=True,
    )
    almacen.subir(
        conf["indice"],
        (json.dumps(indice, ensure_ascii=False, indent=1) + "\n").encode("utf-8"),
        {"Content-Type": "application/json", "Cache-Control": CACHE_INDICE},
    )
    return {"version": version, "hecho": "publicada", "etiquetas": etiquetas, **entrada}


def leer_indice(almacen: copias.Copias, conf: dict[str, Any]) -> dict[str, Any]:
    if not almacen.existe(conf["indice"]):
        return {"version": 1, "versiones": []}
    datos: dict[str, Any] = json.loads(almacen.bajar(conf["indice"]))
    return datos


def comprobar(
    almacen: copias.Copias,
    etiquetas: dict[str, dict[str, str]],
    completa: bool = False,
    conf: dict[str, Any] | None = None,
) -> list[str]:
    """Lo que no cuadra en las versiones publicadas (vacía si todas siguen como se publicaron).
    `etiquetas`: las ETag de cada fichero de cada versión al publicarla."""
    conf = conf or configuracion()
    problemas: list[str] = []
    for entrada in leer_indice(almacen, conf)["versiones"]:
        version = entrada["version"]
        carpeta = f"{conf['prefijo']}{version}/"
        try:
            cuerpo = almacen.bajar(carpeta + METADATOS)
        except OSError as error:
            problemas.append(f"{version}: metadatos.json no se lee ({error})")
            continue
        if huella(cuerpo) != entrada["metadatos_sha256"]:
            problemas.append(f"{version}: metadatos.json ha cambiado")
            continue
        metadatos = json.loads(cuerpo)
        propias = etiquetas.get(version, {})
        for nombre, esperado in metadatos["ficheros"].items():
            objeto = carpeta + nombre
            try:
                if completa:
                    datos = almacen.bajar(objeto)
                    if len(datos) != esperado["bytes"] or huella(datos) != esperado["sha256"]:
                        problemas.append(f"{version}: {nombre} ha cambiado")
                    continue
                guardada = almacen.metadato(objeto, "x-amz-meta-sha256")
                if guardada is None:
                    problemas.append(f"{version}: falta {nombre}")
                elif guardada != esperado["sha256"]:
                    problemas.append(f"{version}: {nombre} ha cambiado")
                elif nombre in propias and almacen.metadato(objeto, "etag") != propias[nombre]:
                    problemas.append(f"{version}: {nombre} se ha vuelto a subir")
            except OSError as error:
                problemas.append(f"{version}: {nombre} no se lee ({error})")
    return problemas


def leer_registro(ruta: Path) -> dict[str, Any]:
    try:
        datos = json.loads(ruta.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return datos if isinstance(datos, dict) else {}


def escribir_registro(ruta: Path, datos: dict[str, Any]) -> None:
    temporal = ruta.with_name(ruta.name + ".tmp")
    temporal.write_text(json.dumps(datos, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    os.replace(temporal, ruta)


def mensual(
    almacen: copias.Copias,
    ruta_registro: Path,
    ahora: datetime,
    leer: Leer = leer_http,
    completa: bool | None = None,
) -> dict[str, Any]:
    """Publica la versión del mes si falta y comprueba todas. Devuelve el registro nuevo."""
    conf = configuracion()
    anterior = leer_registro(ruta_registro)
    etiquetas: dict[str, dict[str, str]] = dict(anterior.get("etiquetas", {}))
    resultado = dict(anterior)
    resultado["fallo"] = None
    try:
        hecho = generar(almacen, ahora, leer, conf)
        registro.info("versión %s: %s", hecho["version"], hecho["hecho"])
        if hecho["hecho"] == "publicada":
            etiquetas[hecho["version"]] = hecho["etiquetas"]
            resultado["generada"] = hecho["fecha"]
            registro.info(
                "versión %s publicada: %d incidentes, metadatos %s",
                hecho["version"], hecho["incidentes"], hecho["metadatos_sha256"],
            )  # fmt: skip
    except (OSError, ValueError, VersionInvalida) as error:
        registro.error("la versión %s no se ha publicado: %s", version_de(ahora), error)
        resultado["fallo"] = f"{ahora:%Y-%m-%dT%H:%M:%SZ} {error}"
    indice = leer_indice(almacen, conf)
    publicadas = [v["version"] for v in indice["versiones"]]
    completa = ahora.day == conf["dia"] if completa is None else completa
    problemas = comprobar(almacen, etiquetas, completa, conf)
    for problema in problemas:
        registro.warning("versiones: %s", problema)
    resultado.update(
        etiquetas=etiquetas,
        publicadas=publicadas,
        ultima=publicadas[0] if publicadas else None,
        comprobada=ahora.strftime("%Y-%m-%dT%H:%M:%SZ"),
        completa=completa,
        problemas=problemas,
    )
    escribir_registro(ruta_registro, resultado)
    return resultado


def problemas_para_vigilancia(registro_: dict[str, Any], ahora: datetime) -> list[str]:
    """Las frases de los problemas de las versiones para salud.json (sin contenido)."""
    frases: list[str] = []
    version = version_de(ahora)
    if toca(ahora) and version not in registro_.get("publicadas", []):
        frases.append(
            f"La versión citable {version} de los datos abiertos no se ha generado"
            + (f" ({registro_['fallo']})" if registro_.get("fallo") else "")
            + "."
        )
    comprobada = registro_.get("comprobada")
    if (
        comprobada
        and ahora - datetime.strptime(comprobada, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
        > MAX_SIN_COMPROBAR
    ):
        frases.append(f"Las versiones citables no se comprueban desde el {comprobada}.")
    if registro_.get("problemas"):
        frases.append(
            "Una versión citable publicada ha cambiado o falta: "
            + "; ".join(registro_["problemas"][:3])
            + "."
        )
    return frases


def principal(argumentos: list[str] | None = None) -> int:
    opciones = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = opciones.add_subparsers(dest="orden", required=True)
    sub.add_parser("mensual")
    c = sub.add_parser("comprobar")
    c.add_argument("--completa", action="store_true")
    args = opciones.parse_args(argumentos)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    ruta = Path(os.environ.get("EODI_SECRETOS") or casa() / ".eodi") / "versiones.json"
    ahora = datetime.now(UTC)
    almacen = cliente()
    if args.orden == "mensual":
        resultado = mensual(almacen, ruta, ahora)
    else:
        resultado = mensual(almacen, ruta, ahora, completa=args.completa)
    return 1 if resultado.get("fallo") or resultado.get("problemas") else 0


if __name__ == "__main__":
    sys.exit(principal())
