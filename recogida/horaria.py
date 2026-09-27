"""Ejecución horaria: descarga la base, recoge lo nuevo, publica y vuelve a subir la base.

Uso: python -m recogida.horaria --correo <correo del autor> [--repositorio <url>]
"""

import argparse
import logging
import sys
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory

from almacen import remoto
from almacen.base import Almacen
from almacen.cifrado import abrir_cifrada, guardar_cifrada
from exportacion.publicar import publicar
from recogida import gdelt
from recogida.cache import CachePaginas
from recogida.descarga import Descargador
from recogida.ejecucion import SinCursor, ejecutar
from recogida.fuente import CanalNoVerificado, HuecoDemasiadoGrande
from recogida.fuentes import FUENTES

registro = logging.getLogger("recogida")

# Código de salida cuando una fuente no pudo leerse (canal no verificado, sin cursor o
# con un hueco demasiado grande): las demás se leen y se publica, pero la ejecución
# queda en rojo para que se vea.
SALIDA_FUENTE_NO_VERIFICADA = 2


def principal(argumentos: list[str] | None = None) -> int:
    opciones = argparse.ArgumentParser(description=__doc__)
    opciones.add_argument("--correo", required=True, help="correo del autor del commit de estado")
    opciones.add_argument("--repositorio", default=remoto.REPOSITORIO)
    args = opciones.parse_args(argumentos)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    ahora = datetime.now(UTC)
    salida = 0
    with TemporaryDirectory() as temporal:
        ruta = Path(temporal) / remoto.FICHERO
        if not remoto.descargar(ruta, args.repositorio):
            registro.error("no hay base en la rama %s: ejecuta antes el histórico", remoto.RAMA)
            return 1
        almacen = Almacen(abrir_cifrada(ruta))
        antes = almacen.conexion.serialize()
        descargador, cache = Descargador(), CachePaginas()
        for fuente in FUENTES:
            try:
                ejecutar(almacen, descargador, cache, fuente, ahora)
            except (CanalNoVerificado, SinCursor, HuecoDemasiadoGrande) as error:
                registro.warning("%s no se lee: %s", fuente.id, error)
                salida = SALIDA_FUENTE_NO_VERIFICADA
        try:
            gdelt.ejecutar(almacen, Descargador(pausas_por_sitio=gdelt.PAUSAS), ahora)
        except gdelt.GdeltNoDisponible as error:
            registro.warning("gdelt no se lee: %s", error)
            salida = SALIDA_FUENTE_NO_VERIFICADA
        cambiados = publicar(almacen, ahora)
        registro.info("ficheros publicados con cambios: %d", len(cambiados))
        if almacen.conexion.serialize() != antes:
            guardar_cifrada(almacen.conexion, ruta)
            remoto.subir(ruta, args.correo, args.repositorio)
            registro.info("base subida a la rama %s", remoto.RAMA)
        else:
            registro.info("base sin cambios")
        almacen.cerrar()
    return salida


if __name__ == "__main__":
    sys.exit(principal())
