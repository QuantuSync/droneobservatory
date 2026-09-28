"""Extractor sobre los candidatos de noticias: en la ejecución horaria y para el histórico.

- Horaria: llamadas directas a los candidatos con actividad en los últimos tres
  días que lo necesitan, con el límite de 0,30 dólares al día.
- Histórico, en local: `estimar` hace unas pocas llamadas directas de muestra y
  calcula lo que costaría el lote entero; `lote` envía todos los pendientes como
  un lote (la mitad de precio) dentro del límite de 5 dólares, y después funde,
  agrupa en episodios, publica y sube la base.

Uso:
    python -m recogida.extractor [--base <db.age local>] estimar [--muestra 10]
    python -m recogida.extractor [--base <db.age local>] --correo <correo> lote [--sin-subir]
    python -m recogida.extractor [--base <db.age local>] recuperar --lote <id>
"""

import argparse
import logging
import random
import sys
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory

from almacen import remoto
from almacen.base import Almacen
from almacen.cifrado import abrir_cifrada, cargar_clave_local, guardar_cifrada
from esquema import Documento
from exportacion.publicar import publicar
from modelo import cliente as servicio
from modelo import coste, ficha, paginas
from proceso import extraccion, incidentes
from proceso.configuracion import cargar_vocabulario_modelos
from recogida.descarga import Descargador

registro = logging.getLogger("recogida")

# La ejecución horaria solo mira candidatos con artículos de los últimos tres días: lo
# anterior es del histórico, que va por lotes.
VENTANA_HORARIA = timedelta(days=3)
# Descargas de páginas en paralelo para preparar el lote: cada hilo con su descargador,
# que respeta la pausa por sitio. 8 hilos bajan unas 4000 páginas en menos de una hora.
HILOS = 8
SEMILLA_MUESTRA = 1
MUESTRA = 10


@dataclass
class Resultado:
    candidatos: int = 0
    llamadas: int = 0
    publicados: int = 0
    fallidas: int = 0
    fusiones: int = 0
    episodios: int = 0

    def resumen(self) -> str:
        return (
            f"candidatos={self.candidatos} llamadas={self.llamadas} publicados={self.publicados} "
            f"fallidas={self.fallidas} fusiones={self.fusiones} episodios={self.episodios}"
        )


def pendientes(almacen: Almacen, desde: datetime | None = None) -> list[Documento]:
    candidatos = almacen.candidatos()
    if desde is not None:
        corte = desde.strftime("%Y-%m-%dT%H:%M:%SZ")
        candidatos = [c for c in candidatos if c["ultimo"] >= corte]
    return [c for c in candidatos if extraccion.necesita_extraccion(almacen, c)]


def preparar_todas(
    almacen: Almacen, candidatos: list[Documento], descargador: Callable[[], Descargador]
) -> list[extraccion.Peticion]:
    """Peticiones con las páginas descargadas en paralelo; el orden se conserva.

    La base solo se lee en este hilo: los demás solo descargan.
    """
    sin_texto = [extraccion.preparar(almacen, c, None) for c in candidatos]

    def con_texto(peticion: extraccion.Peticion) -> extraccion.Peticion:
        propio = descargador()
        fuentes = [
            replace(f, texto=paginas.leer(propio, url))
            for f, url in zip(peticion.fuentes, peticion.enviadas, strict=True)
        ]
        return replace(peticion, fuentes=fuentes)

    with ThreadPoolExecutor(HILOS) as hilos:
        return list(hilos.map(con_texto, sin_texto))


def modelos_base() -> frozenset[str]:
    return cargar_vocabulario_modelos()


def ordenar(almacen: Almacen, ahora: datetime) -> tuple[int, int]:
    modelos = extraccion.modelos_validos(almacen, modelos_base())
    return (
        incidentes.fusionar(almacen, ahora, modelos),
        incidentes.agrupar_episodios(almacen, ahora, modelos),
    )


def horaria(
    almacen: Almacen,
    ahora: datetime,
    fabrica: Callable[[servicio.Configuracion], extraccion.Servicio] = servicio.Cliente,
) -> Resultado:
    """Paso del extractor en la ejecución horaria. Sin configuración no hace nada."""
    try:
        configuracion = servicio.configuracion()
    except servicio.ClienteNoConfigurado as error:
        registro.warning("extractor sin configurar: %s", error)
        return Resultado()
    candidatos = pendientes(almacen, ahora - VENTANA_HORARIA)
    peticiones = preparar_todas(almacen, candidatos, Descargador)
    resultados = extraccion.extraer(
        almacen, fabrica(configuracion), peticiones, ahora, coste.Modo.HORARIO, modelos_base()
    )
    fusiones, episodios = ordenar(almacen, ahora)
    return Resultado(
        candidatos=len(candidatos),
        llamadas=len(resultados),
        publicados=sum(r is not None for r in resultados),
        fallidas=len(peticiones) - len(resultados),
        fusiones=fusiones,
        episodios=episodios,
    )


# --- Histórico --------------------------------------------------------------------------


def estimar(almacen: Almacen, cliente: extraccion.Servicio, muestra: int, ahora: datetime) -> str:
    """Llamadas directas de muestra y coste previsto del lote con todos los pendientes."""
    candidatos = pendientes(almacen)
    elegidos = random.Random(SEMILLA_MUESTRA).sample(candidatos, min(muestra, len(candidatos)))
    peticiones = preparar_todas(almacen, elegidos, Descargador)
    antes = len(almacen.llamadas())
    extraccion.extraer(almacen, cliente, peticiones, ahora, coste.Modo.HISTORICO, modelos_base())
    hechas = almacen.llamadas()[antes:]
    if not hechas:
        return "sin llamadas de muestra: no se puede estimar"
    medio = sum(ll["coste"] for ll in hechas) / len(hechas)
    restantes = len(candidatos) - len(hechas)
    lote = medio * coste.DESCUENTO_LOTE * restantes
    total = almacen.gastado(coste.Modo.HISTORICO.value) + lote
    return (
        f"muestra={len(hechas)} coste_medio_directo={medio:.5f} candidatos={len(candidatos)} "
        f"lote_previsto={lote:.4f} total_previsto={total:.4f} "
        f"limite={coste.LIMITE_HISTORICO_USD:.2f} cabe={total <= coste.LIMITE_HISTORICO_USD}"
    )


def orden_estimar(args: argparse.Namespace, almacen: Almacen, ahora: datetime) -> int:
    cliente = servicio.Cliente(servicio.configuracion())
    registro.info("estimación %s", estimar(almacen, cliente, args.muestra, ahora))
    return 0


# Titular más largo que se envía: los de GDELT pasan pocas veces de 300 letras.
LETRAS_TITULAR = 300


def peor_caso_peticion() -> float:
    """Coste máximo de una petición del lote: tres fuentes con titular y texto completos."""
    fuente = LETRAS_TITULAR + paginas.MAX_LETRAS
    letras = len(ficha.INSTRUCCIONES) + len(str(ficha.ESQUEMA)) + extraccion.MAX_FUENTES * fuente
    return coste.peor_caso(letras, ficha.MAX_TOKENS_SALIDA, lote=True)


def orden_lote(args: argparse.Namespace, almacen: Almacen, ahora: datetime) -> int:
    cliente = servicio.Cliente(servicio.configuracion())
    # Si no caben todos en el límite, primero los de más artículos: son los más probables
    # de ser un incidente real.
    candidatos = sorted(pendientes(almacen), key=lambda c: (-len(c["articulos"]), c["id"]))
    # Solo se descargan las páginas de los que caben en el peor caso, dejando la reserva.
    queda = coste.LIMITE_HISTORICO_USD - almacen.gastado(coste.Modo.HISTORICO.value) - args.reserva
    caben = max(0, int(queda / peor_caso_peticion()))
    registro.info("pendientes=%d caben=%d", len(candidatos), min(caben, len(candidatos)))
    peticiones = preparar_todas(almacen, candidatos[:caben], Descargador)
    recuentos = extraccion.extraer_lote(
        almacen, cliente, peticiones, lambda: datetime.now(UTC), modelos_base()
    )
    fusiones, episodios = ordenar(almacen, datetime.now(UTC))
    registro.info("lote %s fusiones=%d episodios=%d", recuentos, fusiones, episodios)
    return 0


def orden_recuperar(args: argparse.Namespace, almacen: Almacen, ahora: datetime) -> int:
    """Procesa un lote ya terminado y pagado cuyos resultados no llegaron a la base."""
    cliente = servicio.Cliente(servicio.configuracion())
    lote = cliente.lote(args.lote)
    if lote.get("processing_status") != "ended":
        registro.error("el lote %s no ha terminado", args.lote)
        return 1
    candidatos = pendientes(almacen)
    peticiones = preparar_todas(almacen, candidatos, Descargador)
    recuentos = extraccion.procesar_lote(
        almacen, cliente, lote, peticiones, lambda: datetime.now(UTC), modelos_base()
    )
    fusiones, episodios = ordenar(almacen, datetime.now(UTC))
    registro.info("recuperado %s fusiones=%d episodios=%d", recuentos, fusiones, episodios)
    return 0


def orden_reconstruir(args: argparse.Namespace, almacen: Almacen, ahora: datetime) -> int:
    """Rehace los incidentes desde las fichas guardadas, sin llamar al modelo."""
    rehechos = extraccion.reconstruir(almacen, datetime.now(UTC), modelos_base())
    fusiones, episodios = ordenar(almacen, datetime.now(UTC))
    registro.info("rehechos=%d fusiones=%d episodios=%d", rehechos, fusiones, episodios)
    return 0


def principal(argumentos: list[str] | None = None) -> int:
    opciones = argparse.ArgumentParser(description=__doc__)
    opciones.add_argument("--repositorio", default=remoto.REPOSITORIO)
    opciones.add_argument("--correo", default="")
    opciones.add_argument("--sin-subir", action="store_true")
    opciones.add_argument(
        "--base", type=Path, help="base cifrada local: se lee y se reescribe, sin subir"
    )
    ordenes = opciones.add_subparsers(dest="orden", required=True)
    o_estimar = ordenes.add_parser("estimar")
    o_estimar.add_argument("--muestra", type=int, default=MUESTRA)
    o_lote = ordenes.add_parser("lote")
    o_lote.add_argument(
        "--reserva", type=float, default=0.0, help="dólares del límite que se dejan sin usar"
    )
    o_recuperar = ordenes.add_parser("recuperar")
    o_recuperar.add_argument("--lote", required=True, help="identificador del lote")
    ordenes.add_parser("reconstruir")
    args = opciones.parse_args(argumentos)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
    cargar_clave_local()
    servicio.cargar_local()
    ahora = datetime.now(UTC)
    with TemporaryDirectory() as temporal:
        ruta = Path(temporal) / remoto.FICHERO
        if args.base is None and not remoto.descargar(ruta, args.repositorio):
            registro.error("no hay base en la rama %s", remoto.RAMA)
            return 1
        almacen = Almacen(abrir_cifrada(args.base or ruta))
        ordenes_ = {
            "estimar": orden_estimar,
            "lote": orden_lote,
            "recuperar": orden_recuperar,
            "reconstruir": orden_reconstruir,
        }
        salida = ordenes_[args.orden](args, almacen, ahora)
        # Primero se guarda la base, con lo que ya está pagado; después se publica, con la
        # hora de este momento (la orden puede haber durado horas).
        guardar_cifrada(almacen.conexion, ruta)
        if args.base is not None:
            guardar_cifrada(almacen.conexion, args.base)
        publicar(almacen, datetime.now(UTC))
        if args.base is not None:
            guardar_cifrada(almacen.conexion, args.base)
        elif args.sin_subir or not args.correo:
            destino = Path.cwd() / "data" / "historico" / remoto.FICHERO
            destino.parent.mkdir(parents=True, exist_ok=True)
            guardar_cifrada(almacen.conexion, destino)
        else:
            remoto.subir(ruta, args.correo, args.repositorio)
            registro.info("base subida a la rama %s", remoto.RAMA)
    return salida


if __name__ == "__main__":
    sys.exit(principal())
