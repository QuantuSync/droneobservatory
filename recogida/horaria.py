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
from recogida.cache import CachePaginas
from recogida.descarga import Descargador
from recogida.ejecucion import ejecutar
from recogida.fuerza_aerea import CanalNoVerificado

registro = logging.getLogger("recogida")

# Código de salida cuando la fuente no pudo verificarse: la ejecución termina y
# publica, pero queda en rojo para que se vea.
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
        try:
            ejecutar(almacen, Descargador(), CachePaginas(), ahora)
        except CanalNoVerificado as error:
            registro.warning("fuente no verificada, no se lee nada: %s", error)
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
