"""Ejecución horaria: descarga la base, recoge lo nuevo, publica y vuelve a subir la base.

Cada fuente y el extractor tienen un tope de tiempo propio (TOPE_S en su módulo, con
la medida que lo justifica). Entre todos suman 24 minutos en el peor caso, frente a los
5 a 7 de una ejecución normal y a los 45 que tiene el trabajo: ningún paso puede dejar
sin tiempo a los demás ni impedir que la base se suba.

Con --estado, deja escrito cómo fue cada fuente y la fecha de su último dato, para el
estado del sistema que publica el servidor (`recogida/estado.py`).

Uso: python -m recogida.horaria --correo <correo del autor> [--repositorio <url>]
    [--estado <json>]
"""

import argparse
import logging
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory

from almacen import remoto
from almacen.base import Almacen
from almacen.cifrado import abrir_cifrada, guardar_cifrada
from exportacion.publicar import modelos, publicar
from proceso import incursiones, solapes
from proceso.ataques import SENTIDO_UA_RU
from proceso.extraccion import Parada
from recogida import extractor, gdelt, oficiales
from recogida.cache import CachePaginas
from recogida.descarga import Descargador, DescargaFallida
from recogida.ejecucion import SinCursor, ejecutar
from recogida.estado import CON_AVISO, LEIDA, NO_LEIDA, EstadoFuente, escribir_parcial
from recogida.fuente import CanalNoVerificado, HuecoDemasiadoGrande
from recogida.fuentes import FUENTES
from recogida.plazo import Plazo, TiempoAgotado

registro = logging.getLogger("recogida")

# Código de salida cuando la ejecución termina con avisos (una fuente que no pudo leerse,
# un error del extractor): lo demás se lee, la base se sube y el workflow publica, pero
# la ejecución queda en rojo para que se vea. El workflow lo conoce como SALIDA_AVISO.
SALIDA_AVISO = 2
# Motivos por los que una fuente de partes no se lee en una ejecución: se avisa y se
# sigue con las demás. La siguiente ejecución la lee desde el mismo cursor.
NO_LEIDA_PARTE = (
    CanalNoVerificado, SinCursor, HuecoDemasiadoGrande, DescargaFallida, TiempoAgotado,
)  # fmt: skip
# Una franja de GDELT dura 15 minutos: su último dato es el final de la última leída.
FRANJA_GDELT = timedelta(minutes=15)


def ultimo_dato(almacen: Almacen, cursor: str, campo: str) -> datetime | None:
    documento = almacen.cursor(cursor) or {}
    valor = documento.get(campo)
    return datetime.fromisoformat(valor.replace("Z", "+00:00")) if valor else None


def ultima_llamada(almacen: Almacen) -> datetime | None:
    fechas = [ll["fecha"] for ll in almacen.llamadas()]
    return datetime.fromisoformat(max(fechas).replace("Z", "+00:00")) if fechas else None


def principal(argumentos: list[str] | None = None) -> int:
    opciones = argparse.ArgumentParser(description=__doc__)
    opciones.add_argument("--correo", required=True, help="correo del autor del commit de estado")
    opciones.add_argument("--repositorio", default=remoto.REPOSITORIO)
    opciones.add_argument("--estado", type=Path, help="estado de cada fuente, en JSON")
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
        estados: dict[str, EstadoFuente] = {}
        for fuente in FUENTES:
            # Cada paso tiene su tope de tiempo: el que lo agota no se lo quita a los demás.
            descargador.plazo = Plazo(fuente.tope_s)
            leida = LEIDA
            try:
                ejecutar(almacen, descargador, cache, fuente, ahora)
            except NO_LEIDA_PARTE as error:
                registro.warning("%s no se lee: %s", fuente.id, error)
                salida, leida = SALIDA_AVISO, NO_LEIDA
            estados[fuente.id] = EstadoFuente(leida, ultimo_dato(almacen, fuente.id, "fecha"))
        # Los tramos del ministerio que ya cubre un total, o que se solapan, no se suman.
        registro.info(
            "tramos con enlace cambiado: %d", solapes.enlazar(almacen, SENTIDO_UA_RU, ahora)
        )
        estado_gdelt = LEIDA
        try:
            gdelt.ejecutar(almacen, gdelt.descargador(Plazo(gdelt.TOPE_S)), ahora)
        except gdelt.GdeltNoDisponible as error:
            registro.warning("gdelt no se lee: %s", error)
            salida, estado_gdelt = SALIDA_AVISO, CON_AVISO
        franja = ultimo_dato(almacen, gdelt.FUENTE_ID, "franja")
        estados[gdelt.FUENTE_ID] = EstadoFuente(estado_gdelt, franja and franja + FRANJA_GDELT)
        # Cruces a otros países de los partes ucranianos: incursiones notificadas.
        registro.info(
            "incursiones nuevas: %d", incursiones.registrar(almacen, ahora, modelos(almacen))
        )
        # Confirmaciones oficiales de los incidentes que ya hay. Si no da tiempo a leer
        # todas las fuentes se avisa: lo normal es que sobre más de la mitad del tope.
        confirmaciones = oficiales.ejecutar(
            almacen, ahora, modelos(almacen), plazo=Plazo(oficiales.TOPE_S)
        )
        if confirmaciones.sin_leer:
            salida = SALIDA_AVISO
        avisos_oficiales = confirmaciones.sin_leer or confirmaciones.bloqueadas
        estados["oficiales"] = EstadoFuente(
            CON_AVISO if avisos_oficiales else LEIDA, confirmaciones.ultima
        )
        # Candidatos de noticias a incidentes. El límite de gasto o una caída temporal del
        # servicio dejan candidatos pendientes sin más; un error que no se arregla solo o
        # una caída larga dejan la ejecución en rojo.
        resultado = extractor.horaria(almacen, ahora, plazo=Plazo(extractor.TOPE_S))
        registro.info("extractor %s", resultado.resumen())
        if resultado.en_rojo:
            salida = SALIDA_AVISO
        # Error que no se arregla solo: no leída. Límite de gasto, caída o falta de tiempo: los
        # candidatos esperan, con aviso.
        estado_extractor = (
            LEIDA if resultado.parada is None
            else NO_LEIDA if resultado.parada is Parada.ERROR
            else CON_AVISO
        )  # fmt: skip
        estados["extractor"] = EstadoFuente(estado_extractor, ultima_llamada(almacen))
        if args.estado is not None:
            escribir_parcial(args.estado, estados)
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
