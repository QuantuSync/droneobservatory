"""Datos publicados en el almacén público, en vez de en el repositorio.

La recogida horaria escribe los ficheros públicos (exportacion/publicar.py: incidentes.geojson,
incidentes_sin_ubicacion.json, ucrania.json y prevision.json) en una carpeta del servidor. Con el
interruptor de la publicación (`~/.eodi/publicacion_modo`, servidor/recogida.sh) en
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
- pide a Vercel que reconstruya la web con el gancho de despliegue (`~/.eodi/vercel_gancho`, una
  dirección secreta) según `decidir_reconstruccion`: enseguida si hay un incidente nuevo, uno
  retirado o un cambio de estado o de presencia del dron; lo demás (otros datos de las fichas, la
  capa de Ucrania, la previsión) espera a que pasen 3 horas desde la última reconstrucción. Así la
  web y sus páginas de texto nunca llevan datos de más de 3 horas y Vercel construye unas 10 veces
  al día en vez de 24 (desde el 20 de octubre de 2026: las construcciones del gancho eran más de
  la mitad del gasto de Vercel). La barra de estado y el estado de las fuentes los lee el
  navegador del almacén (estado.json, cada hora), sin esperar a la reconstrucción.

Cada fichero sube con la licencia de los datos dentro (recogida/licencia.py): el miembro
`licencia` al principio del JSON, como los que se descargan de la web, y `x-amz-meta-licencia` en
los metadatos del objeto. La huella del manifiesto es la de lo subido.

`comparar` comprueba que lo que sirve el almacén es idéntico, byte a byte, a una carpeta (la de
publicacion/ del clon en el modo `doble`, tras el commit) con su licencia.

Con `--reserva`, sube a la copia pública de reserva de Helsinki en vez de al principal: lo hace
servidor/recogida.sh cuando el principal de Núremberg no acepta la publicación, para que la web
(que sirve desde la reserva si el principal no responde) tenga lo nuevo igualmente. Lleva su
propio registro: cuando el principal vuelve, la recogida siguiente le sube lo que ha cambiado.

Uso: python -m recogida.publicacion subir --carpeta <dir> [--gancho <fichero>] [--registro <json>]
         [--reserva]
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
from datetime import UTC, datetime, timedelta
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
)
TIPOS = {".geojson": "application/geo+json", ".json": "application/json"}
CACHE = "public, max-age=60"
CACHE_HISTORIAL = "public, max-age=86400"
INTENTOS_GANCHO = 3
TOPE_S = 60.0
# Cada cuánto, como mucho, se reconstruye la web por cambios que no son urgentes. Con el margen,
# la recogida horaria que cae a las 3 horas (unos minutos antes o después) ya reconstruye.
RECONSTRUCCION_CADA = timedelta(hours=3)
MARGEN_RECONSTRUCCION = timedelta(minutes=15)
FICHEROS_INCIDENTES = ("incidentes.geojson", "incidentes_sin_ubicacion.json")


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


def publicable(carpeta: Path, nombre: str, ahora: datetime) -> bytes:
    """Lo que se sube de un fichero: el JSON de la carpeta con su licencia y sus créditos dentro
    (recogida/licencia.py), como los que se descargan de la web; la cita, con la versión del mes
    de `ahora`."""
    version = licencia.version_actual(ahora)
    return licencia.con_licencia((carpeta / nombre).read_bytes(), version)


def manifiesto(carpeta: Path, ahora: datetime) -> dict[str, Any]:
    ficheros = {}
    for nombre in FICHEROS:
        ruta = carpeta / nombre
        if ruta.exists():
            datos = publicable(carpeta, nombre, ahora)
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
        cuerpo = gzip.compress(publicable(carpeta, nombre, ahora), compresslevel=9, mtime=0)
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
            cuerpo = gzip.compress(publicable(carpeta, nombre, ahora), compresslevel=9, mtime=0)
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


def incidentes_publicados(carpeta: Path) -> dict[str, list[str]]:
    """Cada incidente publicado (con lugar o sin él): su estado, su presencia del dron y la huella
    de su ficha. Lo que la web enseña de ellos; con esto se decide si reconstruirla."""
    indice: dict[str, list[str]] = {}
    for nombre in FICHEROS_INCIDENTES:
        ruta = carpeta / nombre
        if not ruta.exists():
            continue
        datos = json.loads(ruta.read_text(encoding="utf-8"))
        fichas = (
            [f.get("properties") or {} for f in datos.get("features", [])]
            if "features" in datos
            else datos.get("incidentes", [])
        )
        for ficha in fichas:
            if not isinstance(ficha, dict) or not ficha.get("id"):
                continue
            estado = ficha.get("estado")
            actual = estado.get("actual") if isinstance(estado, dict) else estado
            texto = json.dumps(ficha, ensure_ascii=False, sort_keys=True).encode("utf-8")
            indice[str(ficha["id"])] = [
                str(actual),
                str(ficha.get("presencia_dron")),
                huella(texto)[:16],
            ]
    return indice


def _instante(texto: Any) -> datetime | None:
    try:
        return datetime.strptime(str(texto), "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
    except ValueError:
        return None


def decidir_reconstruccion(
    web: dict[str, Any], incidentes: dict[str, list[str]], cambiado: bool, ahora: datetime
) -> tuple[bool, str, dict[str, Any]]:
    """Si se pide ya la reconstrucción de la web, por qué y lo que queda anotado (`web`, la
    sección del registro: la última reconstrucción pedida, los incidentes que se construyeron
    entonces y desde cuándo hay cambios sin construir).

    Enseguida: un incidente nuevo, uno que ya no se publica o un cambio de estado o de presencia
    del dron. Lo demás que cambie (otros datos de las fichas, la capa de Ucrania, la previsión)
    queda pendiente y se construye cuando han pasado RECONSTRUCCION_CADA desde la última."""
    anteriores: dict[str, list[str]] = web.get("incidentes") or {}
    pendiente = web.get("pendiente_desde")
    ultima = _instante(web.get("ultima"))
    nuevo = {**web}
    if cambiado and pendiente is None:
        pendiente = ahora.strftime("%Y-%m-%dT%H:%M:%SZ")
    nuevo["pendiente_desde"] = pendiente
    if not anteriores or ultima is None:
        return (pendiente is not None or not anteriores), "primera reconstrucción anotada", nuevo
    altas = sorted(set(incidentes) - set(anteriores))
    bajas = sorted(set(anteriores) - set(incidentes))
    estados = sorted(
        i for i in set(incidentes) & set(anteriores) if incidentes[i][:2] != anteriores[i][:2]
    )
    if altas or bajas or estados:
        partes = [
            f"{texto}: {', '.join(ids[:5])}{' …' if len(ids) > 5 else ''}"
            for texto, ids in (
                ("nuevos", altas),
                ("ya no publicados", bajas),
                ("cambio de estado o presencia", estados),
            )
            if ids
        ]
        return True, "urgente (" + "; ".join(partes) + ")", nuevo
    if pendiente is not None and ahora - ultima >= RECONSTRUCCION_CADA - MARGEN_RECONSTRUCCION:
        return True, f"cambios pendientes desde {pendiente}", nuevo
    return False, (f"cambios pendientes desde {pendiente}" if pendiente else "sin cambios"), nuevo


def reconstruida(web: dict[str, Any], incidentes: dict[str, list[str]], ahora: datetime
                 ) -> dict[str, Any]:  # fmt: skip
    """La sección del registro tras pedir bien la reconstrucción."""
    return {**web, "ultima": ahora.strftime("%Y-%m-%dT%H:%M:%SZ"), "pendiente_desde": None,
            "incidentes": incidentes}  # fmt: skip


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
        if remoto != publicable(carpeta, nombre, datetime.now(UTC)):
            distintos.append(nombre)
    return distintos


def principal(argumentos: list[str] | None = None) -> int:
    opciones = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = opciones.add_subparsers(dest="orden", required=True)
    s = sub.add_parser("subir")
    s.add_argument("--carpeta", type=Path, required=True)
    s.add_argument("--registro", type=Path)
    s.add_argument("--gancho", type=Path)
    s.add_argument("--reserva", action="store_true", help="a la copia de reserva de Helsinki")
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
    destino = almacen_publico.cargar_reserva() if args.reserva else almacen_publico.cargar()
    correcto, nuevo, cambiado = subir(
        args.carpeta, datetime.now(UTC), clave_id, secreto, anterior, destino
    )
    if not correcto:
        registro.error("publicación en el almacén incompleta: la web no cambia")
        return 1
    ahora = datetime.now(UTC)
    incidentes = incidentes_publicados(args.carpeta)
    pedir, motivo, web = decidir_reconstruccion(anterior.get("web") or {}, incidentes, cambiado,
                                                ahora)  # fmt: skip
    if pedir and args.gancho is not None:
        if avisar_a_vercel(args.gancho):
            web = reconstruida(web, incidentes, ahora)
        registro.info("reconstrucción de la web: %s", motivo)
    elif args.gancho is not None:
        registro.info("reconstrucción de la web: no todavía (%s)", motivo)
    nuevo["web"] = web
    if args.registro is not None:
        escribir_registro(args.registro, nuevo)
    registro.info("publicado en el almacén (%s)", "con cambios" if cambiado else "sin cambios")
    return 0


if __name__ == "__main__":
    sys.exit(principal())
