"""Copia pública de reserva del almacén de la web, en otra ubicación (Helsinki).

El almacén público de Núremberg (configuracion/almacen_publico.json) guarda el mapa de fondo, los
datos publicados y los ficheros que pide la web. La reserva (bloque «reserva» de la misma
configuración) es otro bucket público, en Helsinki, con los mismos objetos y las mismas cabeceras
(tipo, caché, compresión y metadatos): si el principal no responde, la función de la web
(api/almacen.ts) sirve desde aquí sin que el visitante lo note.

Cada pasada compara los dos listados (tamaño y ETag) y copia lo nuevo o cambiado, con el
manifiesto de los datos publicados el último, como en el principal. Lo que el principal ya no
tiene se borra de la reserva solo si el listado del principal salió entero y trae el manifiesto
(un principal vacío o caído nunca vacía la reserva), y nunca en versiones/ ni en el historial
diario, que no cambian. Los objetos de más de 1 GiB (el mapa de fondo) no se copian aquí: los
sube servidor/preparar_almacen.py --reserva una vez; aquí solo se comprueba que están con el
mismo tamaño.

Lo lanza la unidad eodi-reserva cada 2 minutos y la recogida tras publicar. Deja en
~/.eodi/reserva.json la última pasada y la última vez que la reserva estaba al día; la vigilancia
(recogida/vigilancia.py) avisa si eso pasa de 30 minutos.

Uso: python -m almacen.reserva [sincronizar | comprobar]
"""

import argparse
import json
import logging
import os
import sys
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from almacen import copias
from almacen.sitio import casa

registro = logging.getLogger("reserva")

RAIZ = Path(__file__).resolve().parent.parent
CONFIGURACION = RAIZ / "configuracion" / "almacen_publico.json"
TOPE_COPIA = 1024**3
MANIFIESTO = "publicacion/manifiesto.json"
# Se suben al final de su grupo, como en el principal: quien los lee ya encuentra lo que citan.
ULTIMOS = frozenset({MANIFIESTO, "rutas/indice.json", "gnss/indice.json"})
# Lo que no cambia una vez publicado: nunca se borra de la reserva.
INTOCABLES = ("versiones/", "publicacion/historial/")
CABECERAS_COPIADAS = ("content-type", "cache-control", "content-encoding", "content-disposition")
MAX_ATRASO = timedelta(minutes=30)
# Cada petición, como mucho un minuto (los objetos de la pasada son pequeños): un PUT colgado de un
# almacén no deja la pasada parada los 5 minutos del tope general de almacen/copias.py.
TOPE_PETICION_S = 60.0
ESTADO = "reserva.json"


@dataclass
class Pasada:
    copiados: list[str] = field(default_factory=list)
    borrados: list[str] = field(default_factory=list)
    pendientes: list[str] = field(default_factory=list)
    grandes_pendientes: list[str] = field(default_factory=list)

    @property
    def al_dia(self) -> bool:
        return not self.pendientes and not self.grandes_pendientes


def enviar_con_tope(peticion: urllib.request.Request) -> copias.Respuesta:
    try:
        with urllib.request.urlopen(peticion, timeout=TOPE_PETICION_S) as respuesta:
            cabeceras = {k.lower(): v for k, v in respuesta.headers.items()}
            return copias.Respuesta(respuesta.status, cabeceras, respuesta.read())
    except urllib.error.HTTPError as error:
        cabeceras = {k.lower(): v for k, v in error.headers.items()}
        return copias.Respuesta(error.code, cabeceras, error.read())


def destino(datos: dict[str, Any]) -> copias.Destino:
    return copias.Destino(datos["ubicacion"], datos["punto_s3"], datos["bucket"], "", {})


def destinos(ruta: Path = CONFIGURACION) -> tuple[copias.Destino, copias.Destino]:
    datos: dict[str, Any] = json.loads(ruta.read_text(encoding="utf-8"))
    return destino(datos), destino(datos["reserva"])


def cabeceras_de(respuesta: copias.Respuesta) -> dict[str, str]:
    """Las cabeceras del objeto que se guardan igual en la reserva."""
    cabeceras = {c: respuesta.cabeceras[c] for c in CABECERAS_COPIADAS if c in respuesta.cabeceras}
    cabeceras.update({c: v for c, v in respuesta.cabeceras.items() if c.startswith("x-amz-meta-")})
    return cabeceras


def diferencias(
    origen: dict[str, copias.Objeto], destino: dict[str, copias.Objeto]
) -> tuple[list[str], list[str]]:
    """(objetos que copiar, objetos grandes que faltan o no tienen el mismo tamaño)."""
    copiar, grandes = [], []
    for clave, objeto in origen.items():
        otro = destino.get(clave)
        if objeto.tamano > TOPE_COPIA:
            if otro is None or otro.tamano != objeto.tamano:
                grandes.append(clave)
        elif otro is None or otro.etag != objeto.etag or otro.tamano != objeto.tamano:
            copiar.append(clave)
    return sorted(copiar, key=lambda c: (c in ULTIMOS, c)), sorted(grandes)


def sobrantes(origen: dict[str, copias.Objeto], destino: dict[str, copias.Objeto]) -> list[str]:
    if MANIFIESTO not in origen:
        return []
    return sorted(c for c in destino if c not in origen and not c.startswith(INTOCABLES))


def sincronizar(principal: copias.Copias, reserva: copias.Copias, escribir: bool = True) -> Pasada:
    """Una pasada. Con escribir=False solo dice lo que falta (no copia ni borra nada)."""
    origen = {o.clave: o for o in principal.listar("")}
    en_reserva = {o.clave: o for o in reserva.listar("")}
    copiar, grandes = diferencias(origen, en_reserva)
    pasada = Pasada(grandes_pendientes=grandes)
    if not escribir:
        pasada.pendientes = copiar + [f"sobra {c}" for c in sobrantes(origen, en_reserva)]
        return pasada
    for clave in copiar:
        try:
            respuesta = principal.leer(clave)
            if respuesta.estado in (403, 404):
                continue  # borrado en el principal mientras tanto
            if respuesta.estado != 200:
                raise OSError(f"GET {respuesta.estado}")
            reserva.subir(clave, respuesta.cuerpo, cabeceras_de(respuesta))
            pasada.copiados.append(clave)
        except OSError as error:
            registro.warning("%s: no se copió: %s", clave, error)
            pasada.pendientes.append(clave)
    for clave in sobrantes(origen, en_reserva):
        try:
            reserva.borrar(clave)
            pasada.borrados.append(clave)
        except OSError as error:
            registro.warning("%s: no se borró: %s", clave, error)
            pasada.pendientes.append(f"sobra {clave}")
    return pasada


def anotar(ruta: Path, pasada: Pasada | None, ahora: datetime, error: str | None = None) -> None:
    """Deja la pasada en reserva.json, conservando la última vez que la reserva estaba al día."""
    try:
        anterior: dict[str, Any] = json.loads(ruta.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        anterior = {}
    momento = ahora.isoformat(timespec="seconds").replace("+00:00", "Z")
    datos: dict[str, Any] = {
        "ultima": momento,
        "ultima_al_dia": momento
        if pasada is not None and pasada.al_dia
        else anterior.get("ultima_al_dia"),
        "error": error,
    }
    if pasada is not None:
        datos.update(
            copiados=len(pasada.copiados),
            borrados=len(pasada.borrados),
            pendientes=pasada.pendientes[:20],
            grandes_pendientes=pasada.grandes_pendientes,
        )
    temporal = ruta.with_name(ruta.name + ".tmp")
    temporal.write_text(json.dumps(datos, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(temporal, ruta)


def problema_para_vigilancia(estado: dict[str, Any], ahora: datetime) -> str | None:
    """La frase del aviso si la reserva lleva más de 30 minutos sin estar al día."""
    if not estado:
        return None  # la unidad aún no ha corrido nunca en este servidor
    texto = estado.get("ultima_al_dia")
    al_dia = datetime.fromisoformat(texto.replace("Z", "+00:00")) if texto else None
    if al_dia is not None and ahora - al_dia <= MAX_ATRASO:
        return None
    detalle = estado.get("error") or ", ".join(
        (estado.get("grandes_pendientes") or []) + (estado.get("pendientes") or [])[:3]
    )
    return (
        "La copia pública de reserva en Helsinki "
        + (f"estuvo al día por última vez el {al_dia:%Y-%m-%d %H:%M} UTC" if al_dia else
           "no ha estado al día nunca")
        + (f" (falta: {detalle})" if detalle else "")
        + ": más de 30 minutos atrasada."
    )  # fmt: skip


def principal(
    argumentos: list[str] | None = None,
    cliente: Callable[[copias.Destino], copias.Copias] | None = None,
    ahora: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> int:
    opciones = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    opciones.add_argument(
        "orden", nargs="?", default="sincronizar", choices=["sincronizar", "comprobar"]
    )
    opciones.add_argument("--configuracion", type=Path, default=CONFIGURACION)
    args = opciones.parse_args(argumentos)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    secretos = Path(os.environ.get("EODI_SECRETOS") or casa() / ".eodi")
    escribir = args.orden == "sincronizar"
    hacer = cliente or (lambda d: copias.Copias(d, copias.Credenciales.cargar(), enviar_con_tope))
    try:
        destino_principal, destino_reserva = destinos(args.configuracion)
        pasada = sincronizar(hacer(destino_principal), hacer(destino_reserva), escribir)
    except (OSError, ValueError, KeyError) as error:
        registro.error("la pasada no se pudo hacer: %s", error)
        if escribir:
            anotar(secretos / ESTADO, None, ahora(), str(error))
        return 1
    registro.info(
        "copiados %d, borrados %d, pendientes %d, grandes pendientes %d",
        len(pasada.copiados), len(pasada.borrados), len(pasada.pendientes),
        len(pasada.grandes_pendientes),
    )  # fmt: skip
    for clave in pasada.pendientes + pasada.grandes_pendientes:
        registro.info("pendiente: %s", clave)
    if escribir:
        anotar(secretos / ESTADO, pasada, ahora())
    else:
        sys.stdout.write(
            "la reserva está al día\n" if pasada.al_dia else "la reserva NO está al día\n"
        )
    return 0 if pasada.al_dia else 1


if __name__ == "__main__":
    sys.exit(principal())
