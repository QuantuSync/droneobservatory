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
from exportacion.publicar import modelos, publicar
from proceso import incursiones, solapes
from proceso.ataques import SENTIDO_UA_RU
from recogida import extractor, gdelt, oficiales
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
        # Los tramos del ministerio que ya cubre un total, o que se solapan, no se suman.
        registro.info(
            "tramos con enlace cambiado: %d", solapes.enlazar(almacen, SENTIDO_UA_RU, ahora)
        )
        try:
            gdelt.ejecutar(almacen, gdelt.descargador(), ahora)
        except gdelt.GdeltNoDisponible as error:
            registro.warning("gdelt no se lee: %s", error)
            salida = SALIDA_FUENTE_NO_VERIFICADA
        # Cruces a otros países de los partes ucranianos: incursiones notificadas.
        registro.info(
            "incursiones nuevas: %d", incursiones.registrar(almacen, ahora, modelos(almacen))
        )
        # Confirmaciones oficiales de los incidentes que ya hay.
        oficiales.ejecutar(almacen, ahora, modelos(almacen))
        # Candidatos de noticias a incidentes; una llamada fallida deja la ejecución en rojo.
        resultado = extractor.horaria(almacen, ahora)
        registro.info("extractor %s", resultado.resumen())
        if resultado.fallidas:
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
