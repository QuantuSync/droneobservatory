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
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory

from almacen import remoto, sitio
from almacen.base import Almacen
from almacen.cifrado import abrir_cifrada, cargar_clave_local, guardar_cifrada
from esquema import Documento
from exportacion.publicar import publicar
from modelo import cliente as servicio
from modelo import coste, ficha, paginas
from proceso import extraccion, incidentes
from proceso.configuracion import cargar_vocabulario_modelos
from proceso.noticias import TIPO_APARENTE, nomenclator
from recogida.descarga import Descargador, transporte_con_tope_total
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
# La descarga de las páginas tiene su propio plazo dentro del del paso (desde el 28 de noviembre de
# 2026): como mucho TOPE_PREPARACION_S y dejando siempre RESERVA_LLAMADAS_S para las llamadas. Del
# 28/11 de 01:17 a 07:17 UTC una sola página (newsmonkey.be, un 429 que pedía esperar) se comió el
# tope entero siete horas seguidas y ningún candidato llegó al modelo.
TOPE_PREPARACION_S = 180.0
RESERVA_LLAMADAS_S = 180.0
# Cada página: dos reintentos como mucho, 20 s por petición (el tiempo de la respuesta entera,
# no de cada lectura) y su límite total (modelo/paginas.TOPE_PAGINA_S).
REINTENTOS_PAGINA = 2
LIMITE_PETICION_PAGINA_S = 20.0


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
    # Fichas que decidió el experto y candidatos que esperan al experto.
    escalados: int = 0
    esperan: int = 0

    def resumen(self) -> str:
        return (
            f"candidatos={self.candidatos} llamadas={self.llamadas} publicados={self.publicados} "
            f"pendientes={self.pendientes} fusiones={self.fusiones} episodios={self.episodios} "
            f"escalados={self.escalados} esperan_experto={self.esperan}"
        )


def utilizables(almacen: Almacen, candidatos: list[Documento]) -> list[Documento]:
    """Sin los retirados tras sus fallos, los que siguen sin artículos en un idioma reconocido
    ni los que esperan al modelo experto; los que fallaron alguna vez, los últimos (uno que
    falla no frena a los demás)."""
    apartados = extraccion.apartados(almacen)
    ahora = datetime.now(UTC)
    elegidos = []
    for candidato in candidatos:
        entrada = apartados.get(candidato["id"], {})
        if entrada.get("retirado"):
            continue
        if extraccion.espera_experto(almacen, candidato["id"], ahora):
            continue
        if entrada.get("sin_idioma") and not extraccion.con_idioma(almacen, candidato):
            continue
        elegidos.append(candidato)
    # Los que esperaron al experto van los primeros (ya esperaron un día); los que fallaron
    # alguna vez, los últimos.
    esperaron = extraccion.esperan_experto(almacen)
    return sorted(
        elegidos,
        key=lambda c: (c["id"] not in esperaron, bool(apartados.get(c["id"], {}).get("fallos"))),
    )


def pendientes(almacen: Almacen, desde: datetime | None = None) -> list[Documento]:
    candidatos = almacen.candidatos()
    if desde is not None:
        corte = desde.strftime("%Y-%m-%dT%H:%M:%SZ")
        candidatos = [c for c in candidatos if c["ultimo"] >= corte]
    return utilizables(
        almacen, [c for c in candidatos if extraccion.necesita_extraccion(almacen, c)]
    )


@dataclass
class Preparacion:
    """Lo que pasó al preparar las peticiones de la ejecución horaria (para el registro y para
    decir por qué una ejecución acaba sin llamadas)."""

    segundos: float = 0.0
    paginas: int = 0
    # «dirección: motivo» de cada página que no se leyó.
    fallidas: list[str] = field(default_factory=list)
    # Candidatos apartados en esta ejecución por una página que falló y se reintenta en la
    # siguiente, con el motivo.
    apartados: dict[str, str] = field(default_factory=dict)
    # Candidatos que no se llegaron a preparar porque se acabó el tiempo de la preparación.
    sin_tiempo: list[str] = field(default_factory=list)
    motivo_tiempo: str = ""


@dataclass
class _Leida:
    peticion: extraccion.Peticion
    fechas: dict[str, datetime]
    # (dirección, motivo, transitorio) de cada página que no se leyó.
    fallos: list[tuple[str, str, bool]]
    leidas: list[str]
    # El motivo si se acabó el tiempo antes de leer todas sus páginas.
    sin_tiempo: str = ""


# Páginas apartadas: la dirección de cada página que falló con un fallo transitorio y las
# recogidas en que falló. Su candidato espera a la recogida siguiente (como mucho
# MAX_RECOGIDAS_APARTADA veces); después va con el titular de esa fuente, como antes.
PAGINAS_APARTADAS = "paginas_apartadas"
MAX_RECOGIDAS_APARTADA = 2
# Una página que tarda esto o más en leerse queda en el registro aunque se lea.
PAGINA_LENTA_S = 10.0


def _reintentos_de(descargador: object) -> int:
    recuentos = getattr(descargador, "recuentos", None)
    return int(recuentos.get("reintentos", 0)) if recuentos is not None else 0


def _apartar_por_paginas(almacen: Almacen, leida: _Leida, momento: datetime) -> str:
    """Anota las páginas de un candidato que fallaron con un fallo transitorio (y olvida las que
    ya se leen). Devuelve el motivo si el candidato espera a la recogida siguiente; vacío si va
    al modelo (sin fallos transitorios, o con una página que ya falló en MAX_RECOGIDAS_APARTADA
    recogidas: entonces va con su titular)."""
    documento = almacen.cursor(PAGINAS_APARTADAS) or {}
    if not isinstance(documento, dict):
        documento = {}
    fecha = momento.strftime("%Y-%m-%dT%H:%M:%SZ")
    corte = (momento - VENTANA_HORARIA).strftime("%Y-%m-%dT%H:%M:%SZ")
    cambiado = False
    for url in leida.leidas:
        cambiado |= documento.pop(url, None) is not None
    for url in [u for u, e in documento.items() if max(e.get("recogidas") or [""]) < corte]:
        documento.pop(url)
        cambiado = True
    candidato_id = leida.peticion.candidato["id"]
    motivo = ""
    for url, fallo, transitorio in leida.fallos:
        if not transitorio:
            continue
        entrada = documento.setdefault(url, {"recogidas": []})
        anteriores = [r for r in entrada["recogidas"] if r != fecha]
        if len(anteriores) >= MAX_RECOGIDAS_APARTADA:
            registro.warning(
                "candidato %s: la página %s sigue sin leerse tras %d recogidas; va con el "
                "titular de esa fuente", candidato_id, url, len(anteriores) + 1,
            )  # fmt: skip
            continue
        if fecha not in entrada["recogidas"]:
            entrada["recogidas"].append(fecha)
            entrada["motivo"] = fallo[:300]
            cambiado = True
        if not motivo:
            motivo = (
                f"la página {url} no se leyó ({fallo[:200]}); se reintenta en la recogida "
                f"siguiente (vez {len(anteriores) + 1} de {MAX_RECOGIDAS_APARTADA})"
            )
    if cambiado:
        almacen.guardar_cursor(PAGINAS_APARTADAS, documento)
    if motivo:
        registro.warning("candidato %s apartado en esta recogida: %s", candidato_id, motivo)
    return motivo


def preparar_todas(
    almacen: Almacen,
    candidatos: list[Documento],
    descargador: Callable[[], Descargador],
    ahora: datetime | None = None,
    informe: Preparacion | None = None,
    tope_pagina_s: float = paginas.TOPE_PAGINA_S,
) -> list[extraccion.Peticion]:
    """Peticiones con las páginas descargadas en paralelo; el orden se conserva.

    La base solo se lee en este hilo: los demás solo descargan. Un candidato que no se puede
    preparar se aparta (con `ahora`, queda anotado) y los demás siguen. Lo preparado sin página
    es la pista de la fuente (la frase de un artículo dirigido, el texto de una nota oficial sin
    ficha): va delante de la página descargada. Hasta el 19 de noviembre de 2026 la página la
    sustituía y la nota del MApN del 17/11 llegaba al extractor sin su texto.

    Cada página tiene su límite (`tope_pagina_s`, con sus reintentos y esperas) y cada una que
    falla, se reintenta o tarda queda en el registro con su dirección y lo que tardó. Con
    `informe` (la ejecución horaria, desde el 28 de noviembre de 2026): un candidato con una página
    que falló con un fallo transitorio espera a la recogida siguiente (_apartar_por_paginas) y uno
    que no se llegó a preparar porque se acabó el tiempo queda pendiente; los demás siguen y llegan
    al modelo. Antes, el primer TiempoAgotado de cualquier página tiraba la preparación entera y
    ningún candidato llegaba al modelo. Sin `informe`, un TiempoAgotado sale como siempre.
    """
    momento = ahora or datetime.now(UTC)
    sin_texto = []
    for candidato in candidatos:
        try:
            sin_texto.append(extraccion.preparar(almacen, candidato, None))
        except TiempoAgotado:
            raise
        except Exception as error:
            registro.exception("candidato %s: no se puede preparar", candidato["id"])
            extraccion.anotar_fallo(
                almacen, candidato["id"], f"no se puede preparar: {error!r}", momento
            )
    # Un candidato sin ningún artículo en un idioma conocido (un medio de fuera de Europa
    # que GDELT sitúa en una ciudad europea) no tiene fuentes que mandar: no se llama. Con
    # una ficha sin artículos no hay fecha del primero y el paso entero se caía.
    vacias = [p.candidato["id"] for p in sin_texto if not p.enviadas]
    if vacias:
        registro.info("candidatos sin artículos en un idioma conocido: %s", ", ".join(vacias))
        extraccion.anotar_sin_idioma(almacen, vacias, momento)
    sin_texto = [p for p in sin_texto if p.enviadas]

    def con_texto(peticion: extraccion.Peticion) -> _Leida:
        propio = descargador()
        fuentes = []
        fechas: dict[str, datetime] = {}
        fallos: list[tuple[str, str, bool]] = []
        leidas: list[str] = []
        for f, url in zip(peticion.fuentes, peticion.enviadas, strict=True):
            inicio = time.monotonic()
            antes = _reintentos_de(propio)
            try:
                # El principio, para el paso 1, y la nota, para el paso 2 (modelo/detalles.py).
                pagina = paginas.leer_pagina(propio, url, con_nota=True, tope_s=tope_pagina_s)
            except TiempoAgotado as error:
                registro.info(
                    "página %s: sin tiempo para leerla tras %.1f s (%s); el candidato %s queda "
                    "para la ejecución siguiente",
                    url, time.monotonic() - inicio, error, peticion.candidato["id"],
                )  # fmt: skip
                return _Leida(peticion, fechas, fallos, leidas, str(error))
            except Exception as error:
                pagina = paginas.Pagina("", fallo=f"{url}: {error!r}")
            segundos = time.monotonic() - inicio
            hechos = _reintentos_de(propio) - antes
            if pagina.fallo:
                # Sin la página, el titular basta para esa fuente.
                registro.warning(
                    "página sin leer en %.1f s tras %d reintentos: %s",
                    segundos, hechos, pagina.fallo,
                )  # fmt: skip
                fallos.append((url, pagina.fallo, pagina.transitorio))
            else:
                leidas.append(url)
                if hechos:
                    registro.info(
                        "página %s leída tras %d reintentos en %.1f s", url, hechos, segundos
                    )
                elif segundos >= PAGINA_LENTA_S:
                    registro.info("página %s lenta: leída en %.1f s", url, segundos)
            if pagina.fecha is not None:
                fechas[url] = pagina.fecha
            texto, nota = pagina.texto, pagina.nota
            fuentes.append(replace(
                f, texto=extraccion.con_pista(f.texto, texto),
                nota=extraccion.con_pista(f.texto, nota) if nota else "",
            ))  # fmt: skip
        return _Leida(replace(peticion, fuentes=fuentes), fechas, fallos, leidas)

    inicio = time.monotonic()
    with ThreadPoolExecutor(HILOS) as hilos:
        leidas = list(hilos.map(con_texto, sin_texto))
    preparadas = []
    for leida in leidas:
        candidato_id = leida.peticion.candidato["id"]
        if informe is not None:
            informe.paginas += len(leida.leidas) + len(leida.fallos)
            informe.fallidas += [f for _, f, _ in leida.fallos]
        if leida.sin_tiempo:
            if informe is None:
                raise TiempoAgotado(leida.sin_tiempo)
            informe.sin_tiempo.append(candidato_id)
            informe.motivo_tiempo = leida.sin_tiempo
            continue
        if informe is not None and (motivo := _apartar_por_paginas(almacen, leida, momento)):
            informe.apartados[candidato_id] = motivo
            continue
        # La fecha que da la propia página corrige la de GDELT en este hilo, el único que escribe
        # en la base (extraccion.con_fechas_de_pagina).
        preparadas.append(
            extraccion.con_fechas_de_pagina(almacen, leida.peticion, leida.fechas, momento)
        )
    if informe is not None:
        informe.segundos = time.monotonic() - inicio
    return preparadas


# Fichas antiguas que se rehacen como mucho en cada ejecución horaria: pocas, para no
# descargar páginas que el límite diario no dejará procesar.
MAX_REPROCESO_POR_HORA = 10
# Parte del límite diario que puede gastar el reproceso: el resto queda para los
# candidatos nuevos que lleguen más tarde ese día.
FRACCION_REPROCESO = 0.5
# Candidatos del repaso de las fuentes sin leer (extraccion.revisar_fuentes_sin_leer) que entran
# en cada ejecución horaria, detrás de las noticias nuevas.
MAX_SIN_LEER_POR_HORA = 3


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
    from recogida import articulos_dirigidos, medios_publicos, oficiales

    dirigidos = {
        c for a in (almacen.cursor(BUSQUEDA) or {}).get("anomalias", {}).values()
        for c in a.get("candidatos", [])
    }  # fmt: skip
    # Y los de las fuentes apuntadas a mano (recogida/articulos_dirigidos.py).
    dirigidos |= articulos_dirigidos.candidatos(almacen)
    # Y los de las notas oficiales que no encontraron ficha (recogida/oficiales.py).
    dirigidos |= oficiales.candidatos(almacen)
    # Y los de las notas de los medios públicos leídos directamente (recogida/medios_publicos.py).
    dirigidos |= medios_publicos.candidatos(almacen)
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
            # Un artículo dirigido que entró en un candidato ya extraído (Córdoba 2/02/2025, el
            # artículo de infobae): se vuelve a extraer si la ficha anterior no lo tenía y le
            # falta algo, con el tope de llamadas por candidato de siempre.
            if candidato["id"] in dirigidos and extraccion.necesita_extraccion(almacen, candidato):
                elegidos.append((MAX_MEDIOS_ORDEN, candidato["ultimo"], candidato))
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


def ordenar(almacen: Almacen, ahora: datetime, episodios: bool = True) -> tuple[int, int]:
    """Las uniones de la regla y los episodios. Sin `episodios`, solo las uniones: en la recogida
    horaria los episodios se calculan después del control de las fichas (recogida/horaria.py)."""
    modelos = extraccion.modelos_validos(almacen, modelos_base())
    return (
        incidentes.fusionar(almacen, ahora, modelos),
        incidentes.agrupar_episodios(almacen, ahora, modelos) if episodios else 0,
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


def plazo_de_preparacion(plazo: Plazo | None) -> Plazo | None:
    """El plazo de la descarga de las páginas: como mucho TOPE_PREPARACION_S y siempre dejando
    RESERVA_LLAMADAS_S del plazo del paso para las llamadas."""
    if plazo is None:
        return None
    return Plazo(max(0.0, min(TOPE_PREPARACION_S, plazo.restante() - RESERVA_LLAMADAS_S)))


def por_que_sin_llamadas(
    informe: Preparacion, extraidas: extraccion.Extraidas, peticiones: list[extraccion.Peticion]
) -> str:
    """Por qué una ejecución con candidatos no hizo ninguna llamada, para el registro."""
    motivos = []
    if informe.sin_tiempo:
        motivos.append(
            f"{len(informe.sin_tiempo)} sin preparar por falta de tiempo ({informe.motivo_tiempo})"
        )
    if informe.apartados:
        primero = next(iter(informe.apartados.items()))
        motivos.append(
            f"{len(informe.apartados)} apartados por una página que falló (el primero, "
            f"{primero[0]}: {primero[1][:200]})"
        )
    if extraidas.esperan:
        motivos.append(f"{len(extraidas.esperan)} esperan al experto")
    if extraidas.parada is not None and (peticiones or not informe.sin_tiempo):
        motivos.append(f"parada: {extraidas.parada} ({extraidas.motivo[:200]})")
    if peticiones and not motivos:
        motivos.append(f"{len(peticiones)} preparados que esperan al experto o a su turno")
    if not peticiones and not motivos:
        motivos.append("ningún candidato quedó preparado")
    if informe.fallidas:
        motivos.append(f"páginas sin leer: {'; '.join(f[:160] for f in informe.fallidas[:3])}")
    return "; ".join(motivos)


def horaria(
    almacen: Almacen,
    ahora: datetime,
    fabrica: Callable[[servicio.Configuracion], extraccion.Servicio] = servicio.Cliente,
    plazo: Plazo | None = None,
    episodios: bool = True,
) -> Resultado:
    """Paso del extractor en la ejecución horaria. Sin configuración no hace nada. Con
    `episodios` falso no calcula los episodios: lo hace quien llama, después del control."""
    comienzo = time.monotonic()
    try:
        configuracion = servicio.configuracion()
    except servicio.ClienteNoConfigurado as error:
        registro.warning("extractor sin configurar: %s", error)
        return Resultado()
    # Una sola vez: las decisiones del base desde que entró, con las reglas de escalado nuevas.
    try:
        extraccion.revisar_decisiones_base(almacen, Descargador(plazo=plazo), ahora)
    except TiempoAgotado:
        registro.warning("revisión de las decisiones del base: sin tiempo; en la siguiente")
    # Una sola vez: los descartes poco seguros del base desde el 13 de octubre de 2026, al experto.
    try:
        extraccion.revisar_descartes_dudosos(almacen, ahora)
    except Exception:
        registro.exception("repaso de los descartes dudosos: falló; en la siguiente")
    # Primero los candidatos nuevos y los que se repiten con el experto (aunque sean de antes de la
    # ventana); después, poco a poco, los incidentes ya publicados con una ficha de una versión
    # anterior, del más reciente al más antiguo. El límite diario de gasto corta la ejecución
    # donde toque.
    nuevos = pendientes(almacen, ahora - VENTANA_HORARIA)
    # Una sola vez, los de antes de la ventana con un artículo que no leyó su ficha: detrás de las
    # noticias nuevas, en tandas de MAX_SIN_LEER_POR_HORA y solo mientras el gasto horario del día
    # no pase de la parte del reproceso, para que el repaso nunca se coma el tope del día.
    try:
        sin_leer = extraccion.revisar_fuentes_sin_leer(almacen, ahora) - {c["id"] for c in nuevos}
        if sin_leer and almacen.gastado(coste.Modo.HORARIO.value, coste.dia(ahora)) < (
            coste.LIMITE_DIARIO_USD * FRACCION_REPROCESO
        ):
            nuevos += utilizables(almacen, [
                c for c in almacen.candidatos()
                if c["id"] in sin_leer and extraccion.necesita_extraccion(almacen, c)
            ])[:MAX_SIN_LEER_POR_HORA]  # fmt: skip
    except Exception:
        registro.exception("repaso de las fuentes sin leer: falló; en la siguiente")
    revision = extraccion.en_revision(almacen) - {c["id"] for c in nuevos}
    nuevos += utilizables(almacen, [c for c in almacen.candidatos() if c["id"] in revision])
    vistos = {c["id"] for c in nuevos}
    retirados = extraccion.retirados(almacen)
    historicos = sorted(
        (c for c in almacen.candidatos()
         if c["id"] not in vistos and c["id"] not in retirados
         and extraccion.desactualizado(almacen, c)),
        key=lambda c: c["ultimo"], reverse=True,
    )[:MAX_REPROCESO_POR_HORA]  # fmt: skip
    # Con lo que queda del cupo de reproceso, los nunca extraídos con varios medios.
    vistos |= {c["id"] for c in historicos}
    historicos += utilizables(almacen, [c for c in prioritarios(almacen) if c["id"] not in vistos])[
        : MAX_REPROCESO_POR_HORA - len(historicos)
    ]
    if almacen.gastado(coste.Modo.HORARIO.value, coste.dia(ahora)) >= (
        coste.LIMITE_DIARIO_USD * FRACCION_REPROCESO
    ):
        historicos = []
    candidatos = [*nuevos, *historicos]
    eleccion_s = time.monotonic() - comienzo
    # La preparación tiene su propio plazo, dentro del del paso y dejando siempre tiempo para las
    # llamadas: ninguna página ni paso previo puede gastar el tope entero. Un candidato que no se
    # llega a preparar queda pendiente; los preparados van al modelo.
    preparacion = plazo_de_preparacion(plazo)
    informe = Preparacion()
    peticiones = preparar_todas(
        almacen, candidatos,
        lambda: Descargador(
            transporte=transporte_con_tope_total, reintentos=REINTENTOS_PAGINA,
            limite_s=LIMITE_PETICION_PAGINA_S, plazo=preparacion,
        ),
        ahora, informe,
    )  # fmt: skip
    registro.info(
        "extractor: %d candidatos elegidos en %.1f s; %d preparados en %.1f s (páginas=%d "
        "sin_leer=%d apartados=%d sin_tiempo=%d)",
        len(candidatos), eleccion_s, len(peticiones), informe.segundos, informe.paginas,
        len(informe.fallidas), len(informe.apartados), len(informe.sin_tiempo),
    )  # fmt: skip
    extraidas = extraccion.extraer(
        almacen, fabrica(configuracion), peticiones, ahora, coste.Modo.HORARIO,
        modelos_base(), plazo,
    )  # fmt: skip
    if informe.sin_tiempo and extraidas.parada is None:
        # Sin el texto de las páginas no se llama: solo con titulares la ficha sale peor.
        extraidas.parar(extraccion.Parada.TIEMPO, TiempoAgotado(
            f"{informe.motivo_tiempo} al preparar las páginas; sin preparar: "
            f"{len(informe.sin_tiempo)} ({', '.join(informe.sin_tiempo[:5])})"
        ))  # fmt: skip
    fusiones, cambios_de_episodio = ordenar(almacen, ahora, episodios)
    sin_llamada = len(candidatos) - len(extraidas.incidentes)
    # Con una parada, `avisar` ya dice por qué (con el motivo); sin ella, se dice aquí.
    if candidatos and not extraidas.incidentes and extraidas.parada is None:
        registro.warning(
            "extractor sin llamadas: %s", por_que_sin_llamadas(informe, extraidas, peticiones)
        )
    return Resultado(
        candidatos=len(candidatos),
        llamadas=len(extraidas.incidentes),
        publicados=sum(i is not None for i in extraidas.incidentes),
        pendientes=sin_llamada,
        fusiones=fusiones,
        episodios=cambios_de_episodio,
        parada=extraidas.parada,
        en_rojo=avisar(almacen, ahora, extraidas, sin_llamada),
        escalados=len(extraidas.escalados),
        esperan=len(extraidas.esperan),
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
    return coste.peor_caso(letras, ficha.MAX_TOKENS_SALIDA, lote=True, esfuerzo=ficha.ESFUERZO)


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
        abierta = (
            Almacen(abrir_cifrada(args.base))
            if args.base is not None
            else sitio.abrir_base(Path(temporal), args.repositorio)
        )
        if abierta is None:
            registro.error("no hay base en la rama %s", remoto.RAMA)
            return 1
        almacen = abierta
        salida = orden(almacen)
        if salida != 0:
            # Una orden que se para a medias (una revisión cuyo lote no cabe en el límite)
            # no deja nada: ni publica ni sube una base a medio cambiar.
            registro.error("la orden terminó con código %d: no se publica ni se sube", salida)
            return salida
        # Primero se guarda la base, con lo que ya está pagado; después se publica, con la
        # hora de este momento (la orden puede haber durado horas).
        if isinstance(almacen, sitio.AlmacenEnDisco):
            sitio.guardar_disco(almacen)
        else:
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
            sitio.guardar_base(almacen, Path(temporal), args.correo, args.repositorio)
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
