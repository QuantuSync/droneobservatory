"""Extractor sobre los candidatos de noticias: en la ejecución horaria y para el histórico.

- Horaria: llamadas directas a los candidatos con actividad en los últimos tres
  días que lo necesitan, con el límite de 0,30 dólares al día. Si el servicio
  está caído no se insiste: los candidatos quedan pendientes para la ejecución
  siguiente y solo una caída de más de seis horas deja la ejecución en rojo.
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
from proceso.noticias import TIPO_APARENTE, nomenclator
from recogida.descarga import Descargador
from recogida.plazo import Plazo, TiempoAgotado

registro = logging.getLogger("recogida")

# La ejecución horaria solo mira candidatos con artículos de los últimos tres días: lo
# anterior es del histórico, que va por lotes.
VENTANA_HORARIA = timedelta(days=3)
# Descargas de páginas en paralelo para preparar el lote: cada hilo con su descargador,
# que respeta la pausa por sitio. 8 hilos bajan unas 4000 páginas en menos de una hora.
HILOS = 8
SEMILLA_MUESTRA = 1
MUESTRA = 10


# Fila de la tabla de cursores con el estado del servicio: desde cuándo está caído, para
# saber de una ejecución a otra cuánto dura la caída.
ESTADO_SERVICIO = "extractor"
# Una caída temporal no es un fallo de la recogida: los candidatos esperan. Si dura más
# de seis horas seguidas ya no es un bache y la ejecución queda en rojo para que se vea.
MAX_CAIDA = timedelta(hours=6)
HORA = timedelta(hours=1)
# Tope de tiempo del paso en la ejecución horaria, con la descarga de las páginas. Medido
# del 28 al 30 de septiembre de 2026: como mucho 165 s (29 candidatos). 420 s son dos
# veces y media; los candidatos que no quepan quedan pendientes para la siguiente.
TOPE_S = 420.0


@dataclass
class Resultado:
    candidatos: int = 0
    llamadas: int = 0
    publicados: int = 0
    # Candidatos sin llamada en esta ejecución: los recoge la siguiente.
    pendientes: int = 0
    fusiones: int = 0
    episodios: int = 0
    parada: extraccion.Parada | None = None
    # Error definitivo del servicio o caída de más de MAX_CAIDA.
    en_rojo: bool = False

    def resumen(self) -> str:
        return (
            f"candidatos={self.candidatos} llamadas={self.llamadas} publicados={self.publicados} "
            f"pendientes={self.pendientes} fusiones={self.fusiones} episodios={self.episodios}"
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


# Fichas antiguas que se rehacen como mucho en cada ejecución horaria: pocas, para no
# descargar páginas que el límite diario no dejará procesar.
MAX_REPROCESO_POR_HORA = 10
# Parte del límite diario que puede gastar el reproceso: el resto queda para los
# candidatos nuevos que lleguen más tarde ese día.
FRACCION_REPROCESO = 0.5


# Candidatos nunca extraídos que merecen una llamada aunque ya no sean recientes: los de una
# instalación con noticias de dos medios o más, y los de una localidad con tres o más. Así
# entraron Esbjerg y Skrydstrup (24 de septiembre de 2025), que el histórico dejó sin extraer.
MIN_MEDIOS_INSTALACION = 2
MIN_MEDIOS_LOCALIDAD = 3
# Los de la búsqueda dirigida van delante de todos.
MAX_MEDIOS_ORDEN = 1_000_000
# Cursor de la búsqueda dirigida (recogida/busqueda_dirigida.FUENTE_ID).
BUSQUEDA = "busqueda_dirigida"


def prioritarios(almacen: Almacen) -> list[Documento]:
    """Candidatos nunca extraídos, y los separados en dos sucesos: primero los separados,
    después los de la búsqueda dirigida (un cierre medido sin incidente), después los que
    tienen noticias de varios medios, de más medios a menos y, a la par, del más reciente al
    más antiguo."""
    nom = nomenclator()
    dirigidos = {
        c for a in (almacen.cursor(BUSQUEDA) or {}).get("anomalias", {}).values()
        for c in a.get("candidatos", [])
    }  # fmt: skip
    elegidos: list[tuple[int, str, Documento]] = []
    for candidato in almacen.candidatos():
        # Los que se separaron en dos sucesos (las dos partes) van delante de todos: la ficha
        # anterior ya no los describe.
        if candidato.get("separado_de") and not almacen.extracciones(candidato["id"]):
            elegidos.append((MAX_MEDIOS_ORDEN + 1, candidato["ultimo"], candidato))
            continue
        if extraccion.articulos_retirados(almacen, candidato):
            elegidos.append((MAX_MEDIOS_ORDEN + 1, candidato["ultimo"], candidato))
            continue
        if almacen.extracciones(candidato["id"]):
            continue
        if candidato["id"] in dirigidos:
            elegidos.append((MAX_MEDIOS_ORDEN, candidato["ultimo"], candidato))
            continue
        sitio = nom.lugares.get(candidato["lugar"])
        instalacion = sitio is not None and sitio.tipo in TIPO_APARENTE
        medios = len({a["medio"] for a in almacen.articulos_de(candidato["articulos"])})
        minimo = MIN_MEDIOS_INSTALACION if instalacion else MIN_MEDIOS_LOCALIDAD
        if medios >= minimo:
            elegidos.append((medios, candidato["ultimo"], candidato))
    return [c for _, _, c in sorted(elegidos, key=lambda e: (e[0], e[1]), reverse=True)]


def modelos_base() -> frozenset[str]:
    return cargar_vocabulario_modelos()


def ordenar(almacen: Almacen, ahora: datetime) -> tuple[int, int]:
    modelos = extraccion.modelos_validos(almacen, modelos_base())
    return (
        incidentes.fusionar(almacen, ahora, modelos),
        incidentes.agrupar_episodios(almacen, ahora, modelos),
    )


def duracion_caida(
    almacen: Almacen, ahora: datetime, extraidas: extraccion.Extraidas
) -> timedelta | None:
    """Anota el estado del servicio y devuelve cuánto lleva caído, o None si no lo está.

    Una respuesta cierra la caída anterior y una caída nueva empieza a contar en esta
    ejecución. Sin llamadas no se sabe nada nuevo y el estado no cambia.
    """
    anterior = (almacen.cursor(ESTADO_SERVICIO) or {}).get("caido_desde")
    desde = None if extraidas.incidentes else anterior
    caido = extraidas.parada is extraccion.Parada.SERVICIO_CAIDO
    if caido and desde is None:
        desde = ahora.isoformat()
    if desde != anterior:
        almacen.guardar_cursor(ESTADO_SERVICIO, {"caido_desde": desde})
    return ahora - datetime.fromisoformat(desde) if caido and desde else None


def avisar(
    almacen: Almacen, ahora: datetime, extraidas: extraccion.Extraidas, pendientes: int
) -> bool:
    """Deja en el registro por qué paró el extractor. True si la ejecución queda en rojo."""
    caida = duracion_caida(almacen, ahora, extraidas)
    if extraidas.parada is extraccion.Parada.LIMITE_GASTO:
        # No es un fallo: el límite está para eso y mañana se sigue.
        registro.info("extractor: %s; pendientes=%d", extraidas.motivo, pendientes)
    elif extraidas.parada is extraccion.Parada.TIEMPO:
        registro.warning(
            "extractor: %s; pendientes=%d para la ejecución siguiente",
            extraidas.motivo, pendientes,
        )  # fmt: skip
    elif caida is not None:
        registro.warning(
            "extractor: servicio caído desde hace %.1f h: %s; pendientes=%d para la "
            "ejecución siguiente",
            caida / HORA, extraidas.motivo, pendientes,
        )  # fmt: skip
        return caida > MAX_CAIDA
    elif extraidas.parada is extraccion.Parada.ERROR:
        registro.error("extractor parado: %s; pendientes=%d", extraidas.motivo, pendientes)
        return True
    return False


def horaria(
    almacen: Almacen,
    ahora: datetime,
    fabrica: Callable[[servicio.Configuracion], extraccion.Servicio] = servicio.Cliente,
    plazo: Plazo | None = None,
) -> Resultado:
    """Paso del extractor en la ejecución horaria. Sin configuración no hace nada."""
    try:
        configuracion = servicio.configuracion()
    except servicio.ClienteNoConfigurado as error:
        registro.warning("extractor sin configurar: %s", error)
        return Resultado()
    # Primero los candidatos nuevos; después, poco a poco, los incidentes ya publicados
    # con una ficha de una versión anterior, del más reciente al más antiguo. El límite
    # diario de gasto corta la ejecución donde toque.
    nuevos = pendientes(almacen, ahora - VENTANA_HORARIA)
    vistos = {c["id"] for c in nuevos}
    historicos = sorted(
        (c for c in almacen.candidatos()
         if c["id"] not in vistos and extraccion.desactualizado(almacen, c)),
        key=lambda c: c["ultimo"], reverse=True,
    )[:MAX_REPROCESO_POR_HORA]  # fmt: skip
    # Con lo que queda del cupo de reproceso, los nunca extraídos con varios medios.
    vistos |= {c["id"] for c in historicos}
    historicos += [c for c in prioritarios(almacen) if c["id"] not in vistos][
        : MAX_REPROCESO_POR_HORA - len(historicos)
    ]
    if almacen.gastado(coste.Modo.HORARIO.value, coste.dia(ahora)) >= (
        coste.LIMITE_DIARIO_USD * FRACCION_REPROCESO
    ):
        historicos = []
    candidatos = [*nuevos, *historicos]
    try:
        peticiones = preparar_todas(almacen, candidatos, lambda: Descargador(plazo=plazo))
    except TiempoAgotado as error:
        # Sin el texto de las páginas no se llama: solo con titulares la ficha sale peor.
        extraidas = extraccion.Extraidas().parar(extraccion.Parada.TIEMPO, error)
    else:
        extraidas = extraccion.extraer(
            almacen, fabrica(configuracion), peticiones, ahora, coste.Modo.HORARIO,
            modelos_base(), plazo,
        )  # fmt: skip
    fusiones, episodios = ordenar(almacen, ahora)
    sin_llamada = len(candidatos) - len(extraidas.incidentes)
    return Resultado(
        candidatos=len(candidatos),
        llamadas=len(extraidas.incidentes),
        publicados=sum(i is not None for i in extraidas.incidentes),
        pendientes=sin_llamada,
        fusiones=fusiones,
        episodios=episodios,
        parada=extraidas.parada,
        en_rojo=avisar(almacen, ahora, extraidas, sin_llamada),
    )


# --- Histórico --------------------------------------------------------------------------


def estimar(almacen: Almacen, cliente: extraccion.Servicio, muestra: int, ahora: datetime) -> str:
    """Llamadas directas de muestra y coste previsto del lote con todos los pendientes."""
    candidatos = pendientes(almacen)
    elegidos = random.Random(SEMILLA_MUESTRA).sample(candidatos, min(muestra, len(candidatos)))
    peticiones = preparar_todas(almacen, elegidos, Descargador)
    antes = len(almacen.llamadas())
    extraidas = extraccion.extraer(
        almacen, cliente, peticiones, ahora, coste.Modo.HISTORICO, modelos_base()
    )
    if extraidas.parada is not None:
        registro.warning("muestra cortada por %s: %s", extraidas.parada, extraidas.motivo)
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
    cliente = servicio.Cliente(servicio.configuracion(), insistencia=servicio.HISTORICO)
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
    cliente = servicio.Cliente(servicio.configuracion(), insistencia=servicio.HISTORICO)
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
    cliente = servicio.Cliente(servicio.configuracion(), insistencia=servicio.HISTORICO)
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


def opciones_base(descripcion: str | None) -> argparse.ArgumentParser:
    """Opciones comunes de las órdenes que trabajan sobre la base remota o una local."""
    opciones = argparse.ArgumentParser(description=descripcion)
    opciones.add_argument("--repositorio", default=remoto.REPOSITORIO)
    opciones.add_argument("--correo", default="")
    opciones.add_argument("--sin-subir", action="store_true")
    opciones.add_argument(
        "--base", type=Path, help="base cifrada local: se lee y se reescribe, sin subir"
    )
    return opciones


def con_base(args: argparse.Namespace, orden: Callable[[Almacen], int]) -> int:
    """Descarga la base (o abre la local), ejecuta la orden, guarda, publica y sube."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
    cargar_clave_local()
    servicio.cargar_local()
    with TemporaryDirectory() as temporal:
        ruta = Path(temporal) / remoto.FICHERO
        if args.base is None and not remoto.descargar(ruta, args.repositorio):
            registro.error("no hay base en la rama %s", remoto.RAMA)
            return 1
        almacen = Almacen(abrir_cifrada(args.base or ruta))
        salida = orden(almacen)
        if salida != 0:
            # Una orden que se para a medias (una revisión cuyo lote no cabe en el límite)
            # no deja nada: ni publica ni sube una base a medio cambiar.
            registro.error("la orden terminó con código %d: no se publica ni se sube", salida)
            return salida
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


def principal(argumentos: list[str] | None = None) -> int:
    opciones = opciones_base(__doc__)
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
    ordenes_ = {
        "estimar": orden_estimar,
        "lote": orden_lote,
        "recuperar": orden_recuperar,
        "reconstruir": orden_reconstruir,
    }
    ahora = datetime.now(UTC)
    return con_base(args, lambda almacen: ordenes_[args.orden](args, almacen, ahora))


if __name__ == "__main__":
    sys.exit(principal())
