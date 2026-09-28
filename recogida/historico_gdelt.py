"""Histórico de noticias desde los ficheros GKG de GDELT, repartido en trabajos paralelos.

El workflow `historico-gdelt` lo reparte así:

1. `tramos`: parte el recorrido (del 1 de enero de 2025 hasta donde empezó la
   recogida horaria) en tramos de franjas iguales, uno por trabajo.
2. `tramo`: cada trabajo lee sus franjas, se queda con los artículos que pasan
   el filtro y los guarda cifrados con la clave age en la rama de parciales
   del repositorio de datos. Nada queda como artefacto del workflow.
3. `incorporar`: un trabajo final junta todos los parciales en orden de fecha
   y los incorpora a la base con el deduplicado y la agrupación de siempre.

El registro de cada paso solo lleva recuentos.

Uso:
    python -m recogida.historico_gdelt tramos --trabajos 20 [--desde ...] [--hasta ...]
    python -m recogida.historico_gdelt reiniciar --correo ... --etiqueta ...
    python -m recogida.historico_gdelt tramo --desde ... --hasta ... --correo ...
    python -m recogida.historico_gdelt incorporar --correo ...
"""

import argparse
import json
import logging
import sys
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from almacen import remoto
from almacen.base import Almacen
from almacen.cifrado import abrir_cifrada, cifrar_datos, descifrar_datos, guardar_cifrada
from proceso.noticias import Articulo, filtro, lugares_en, nomenclator
from recogida import gdelt
from recogida.descarga import Descargador, DescargaFallida

registro = logging.getLogger("recogida")

DESDE = datetime(2025, 1, 1, tzinfo=UTC)
CURSOR = "gdelt_historico"
# GitHub Actions admite hasta 20 trabajos en paralelo en el plan gratuito.
MAX_TRABAJOS = 20
# Un trabajo dura como mucho 6 horas: a las 5,5 deja de leer y sube lo que tiene.
HORAS_POR_TRABAJO = 5.5
# Una franja que falla tras los reintentos se vuelve a intentar al final una vez.
REINTENTOS_FINALES = 1
FORMATO = "%Y-%m-%dT%H:%M:%SZ"


def _fecha(momento: datetime) -> str:
    return momento.astimezone(UTC).strftime(FORMATO)


def _leer_fecha(texto: str) -> datetime:
    return datetime.fromisoformat(texto.replace("Z", "+00:00")).astimezone(UTC)


# --- Tramos -------------------------------------------------------------------------


def tramos(desde: datetime, hasta: datetime, trabajos: int) -> list[dict[str, str]]:
    """Tramos contiguos de franjas [desde, hasta), del mismo número de franjas (±1)."""
    total = int((hasta - desde) / gdelt.FRANJA)
    trabajos = max(1, min(trabajos, MAX_TRABAJOS, total))
    base, resto = divmod(total, trabajos)
    resultado = []
    inicio = desde
    for i in range(trabajos):
        fin = inicio + gdelt.FRANJA * (base + (i < resto))
        resultado.append({"desde": _fecha(inicio), "hasta": _fecha(fin)})
        inicio = fin
    return resultado


# --- Un tramo -----------------------------------------------------------------------


@dataclass
class Tramo:
    articulos: list[Articulo] = field(default_factory=list)
    recuentos: gdelt.Recuentos = field(default_factory=gdelt.Recuentos)
    fallidas: list[str] = field(default_factory=list)
    # Primera franja sin leer si se agotó el tiempo; None si se acabó el tramo.
    cortado_en: str | None = None


def leer_tramo(
    descargador: Descargador,
    desde: datetime,
    hasta: datetime,
    limite: float,
    reloj: Callable[[], float] = time.monotonic,
) -> Tramo:
    """Lee las franjas [desde, hasta) y se queda con los artículos que pasan el filtro."""
    resultado = Tramo()
    filtro_ = filtro()
    # Son franjas antiguas: un fichero que falta ya no va a aparecer.
    ultima = hasta + gdelt.ESPERA_AUSENTE

    def leer(franja: datetime) -> bool:
        try:
            encontrados, lectura = gdelt.leer_franja(descargador, franja, ultima)
        except DescargaFallida:
            return False
        resultado.recuentos.sumar(lectura)
        resultado.recuentos.recibidos += len(encontrados)
        pasan = [a for a in encontrados if filtro_.pasa(a.titular, a.lugares)]
        resultado.recuentos.descartados += len(encontrados) - len(pasan)
        resultado.articulos += pasan
        return True

    pendientes: list[datetime] = []
    franja = desde
    while franja < hasta:
        if reloj() >= limite:
            resultado.cortado_en = _fecha(franja)
            break
        if not leer(franja):
            pendientes.append(franja)
        franja += gdelt.FRANJA
    for _ in range(REINTENTOS_FINALES):
        pendientes = [f for f in pendientes if not leer(f)]
    resultado.fallidas = [_fecha(f) for f in pendientes]
    return resultado


def serializar(tramo: Tramo, desde: datetime, hasta: datetime) -> bytes:
    """Una línea de cabecera con los recuentos y una por artículo, en JSON."""
    r = tramo.recuentos
    cabecera = {
        "desde": _fecha(desde),
        "hasta": _fecha(hasta),
        "franjas": r.franjas,
        "ausentes": r.ausentes,
        "filas": r.filas,
        "recibidos": r.recibidos,
        "descartados": r.descartados,
        "fallidas": tramo.fallidas,
        "cortado_en": tramo.cortado_en,
    }
    lineas = [json.dumps(cabecera, ensure_ascii=False)]
    lineas += [
        json.dumps(gdelt.documento_articulo(a), ensure_ascii=False, sort_keys=True)
        for a in tramo.articulos
    ]
    return ("\n".join(lineas) + "\n").encode("utf-8")


def deserializar(datos: bytes) -> tuple[dict[str, Any], list[Articulo]]:
    lineas = datos.decode("utf-8").splitlines()
    cabecera = json.loads(lineas[0])
    return cabecera, [gdelt.articulo_de_documento(json.loads(x)) for x in lineas[1:] if x]


# --- Incorporación ------------------------------------------------------------------


def incorporar(almacen: Almacen, lotes: Iterable[list[Articulo]]) -> gdelt.Recuentos:
    """Incorpora los artículos en orden de fecha, un día cada vez, como la recogida horaria.

    Los lugares se vuelven a buscar con el nomenclátor actual: si ha mejorado desde que
    se leyeron los tramos, cuenta la mejora.
    """
    nom = nomenclator()
    todos = sorted(
        (replace(a, lugares=lugares_en(a.titular, nom)) for lote in lotes for a in lote),
        key=lambda a: (a.fecha, a.url),
    )
    total = gdelt.Recuentos()
    dia: list[Articulo] = []
    for articulo in todos:
        if dia and articulo.fecha.date() != dia[0].fecha.date():
            total.sumar(gdelt.incorporar(almacen, dia))
            dia = []
        dia.append(articulo)
    if dia:
        total.sumar(gdelt.incorporar(almacen, dia))
    return total


def cobertura(cabeceras: list[dict[str, Any]]) -> dict[str, Any]:
    """Resumen de todos los tramos para el cursor del histórico."""
    ordenadas = sorted(cabeceras, key=lambda c: str(c["desde"]))

    def suma(clave: str) -> int:
        return sum(int(c[clave]) for c in ordenadas)

    return {
        "desde": ordenadas[0]["desde"] if ordenadas else None,
        "hasta": ordenadas[-1]["hasta"] if ordenadas else None,
        "tramos": len(ordenadas),
        "franjas": suma("franjas"),
        "ausentes": suma("ausentes"),
        "filas": suma("filas"),
        "fallidas": [f for c in ordenadas for f in c["fallidas"]],
        "cortados": [c["cortado_en"] for c in ordenadas if c["cortado_en"]],
    }


# --- Órdenes ------------------------------------------------------------------------


def _hasta_por_defecto(repositorio: str) -> datetime:
    """Donde empezó la recogida horaria, según su cursor en la base."""
    with TemporaryDirectory() as temporal:
        ruta = Path(temporal) / remoto.FICHERO
        if not remoto.descargar(ruta, repositorio):
            return gdelt.franja_de(datetime.now(UTC))
        cursor = Almacen(abrir_cifrada(ruta)).cursor(gdelt.FUENTE_ID)
    if cursor is None:
        return gdelt.franja_de(datetime.now(UTC))
    return gdelt.franja_de(_leer_fecha(cursor["inicio"]))


def orden_tramos(args: argparse.Namespace) -> int:
    desde = _leer_fecha(args.desde) if args.desde else DESDE
    hasta = _leer_fecha(args.hasta) if args.hasta else _hasta_por_defecto(args.repositorio)
    sys.stdout.write(json.dumps(tramos(desde, hasta, args.trabajos)) + "\n")
    return 0


def orden_reiniciar(args: argparse.Namespace) -> int:
    remoto.reiniciar_parciales(args.correo, args.etiqueta, args.repositorio)
    return 0


def orden_tramo(args: argparse.Namespace) -> int:
    desde, hasta = _leer_fecha(args.desde), _leer_fecha(args.hasta)
    limite = time.monotonic() + args.horas * 3600
    tramo = leer_tramo(gdelt.descargador(), desde, hasta, limite)
    registro.info(
        "tramo %s %s fallidas=%d cortado=%s",
        _fecha(desde),
        tramo.recuentos.resumen(),
        len(tramo.fallidas),
        tramo.cortado_en is not None,
    )
    with TemporaryDirectory() as temporal:
        ruta = Path(temporal) / "parcial.age"
        ruta.write_bytes(cifrar_datos(serializar(tramo, desde, hasta)))
        nombre = f"{desde:%Y%m%dT%H%M}.jsonl.age"
        intentos = remoto.subir_parcial(ruta, nombre, args.correo, args.repositorio)
    registro.info("parcial subido en %d intentos", intentos)
    return 0


def orden_incorporar(args: argparse.Namespace) -> int:
    with TemporaryDirectory() as temporal:
        directorio = Path(temporal)
        cabeceras: list[dict[str, Any]] = []
        lotes: list[list[Articulo]] = []
        for fichero in remoto.descargar_parciales(directorio / "parciales", args.repositorio):
            cabecera, articulos = deserializar(descifrar_datos(fichero.read_bytes()))
            cabeceras.append(cabecera)
            lotes.append(articulos)
        resumen = cobertura(cabeceras)
        registro.info(
            "tramos=%s franjas=%s ausentes=%s fallidas=%d cortados=%d",
            resumen["tramos"],
            resumen["franjas"],
            resumen["ausentes"],
            len(resumen["fallidas"]),
            len(resumen["cortados"]),
        )
        ruta = directorio / remoto.FICHERO
        if not remoto.descargar(ruta, args.repositorio):
            registro.error("no hay base en la rama %s", remoto.RAMA)
            return 1
        almacen = Almacen(abrir_cifrada(ruta))
        recuentos = incorporar(almacen, lotes)
        almacen.guardar_cursor(CURSOR, resumen)
        registro.info("histórico %s", recuentos.resumen())
        guardar_cifrada(almacen.conexion, ruta)
        remoto.subir(ruta, args.correo, args.repositorio)
        registro.info("base subida a la rama %s", remoto.RAMA)
    return 0


def principal(argumentos: list[str] | None = None) -> int:
    opciones = argparse.ArgumentParser(description=__doc__)
    opciones.add_argument("--repositorio", default=remoto.REPOSITORIO)
    ordenes = opciones.add_subparsers(dest="orden", required=True)
    o_tramos = ordenes.add_parser("tramos")
    o_tramos.add_argument("--trabajos", type=int, default=MAX_TRABAJOS)
    o_tramos.add_argument("--desde")
    o_tramos.add_argument("--hasta")
    o_reiniciar = ordenes.add_parser("reiniciar")
    o_reiniciar.add_argument("--correo", required=True)
    o_reiniciar.add_argument("--etiqueta", required=True)
    o_tramo = ordenes.add_parser("tramo")
    o_tramo.add_argument("--desde", required=True)
    o_tramo.add_argument("--hasta", required=True)
    o_tramo.add_argument("--correo", required=True)
    o_tramo.add_argument("--horas", type=float, default=HORAS_POR_TRABAJO)
    o_incorporar = ordenes.add_parser("incorporar")
    o_incorporar.add_argument("--correo", required=True)
    args = opciones.parse_args(argumentos)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
    acciones = {
        "tramos": orden_tramos,
        "reiniciar": orden_reiniciar,
        "tramo": orden_tramo,
        "incorporar": orden_incorporar,
    }
    return acciones[args.orden](args)


if __name__ == "__main__":
    sys.exit(principal())
