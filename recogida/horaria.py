"""Ejecución horaria: descarga la base, recoge lo nuevo, publica y vuelve a subir la base.

Cada fuente y el extractor tienen un tope de tiempo propio (TOPE_S en su módulo, con
la medida que lo justifica). Entre todos suman 24 minutos en el peor caso, frente a los
5 a 7 de una ejecución normal y a los 45 que tiene el trabajo: ningún paso puede dejar
sin tiempo a los demás ni impedir que la base se suba.

Al final, cada 3 horas, las anomalías térmicas de NASA FIRMS y su cruce con los impactos
(`recogida/firms.py`, `proceso/focos_termicos.py`). Un fallo de FIRMS no cambia el resultado
de la recogida ni la retrasa más que su tope: queda en el registro y en estado.json, y la
ejecución siguiente vuelve a intentarlo.

Antes de FIRMS, la capa de guerra con lugar (`recogida/guerra.py`): las publicaciones que el
lector de canales dejó en el disco del servidor se convierten en impactos con localidad o
instalación, y el extractor lee, con su límite diario propio, los mensajes que el código no
resuelve. Un fallo ahí tampoco cambia el resultado de la recogida.

Después de FIRMS, el tráfico aéreo medido con adsb.lol (lo que el procesado diario dejó en el
disco del servidor) y las condiciones medidas de Open-Meteo y del IEM (`recogida/mediciones.py`),
cada uno con su tope y sin cambiar el código de salida si fallan.

Después, lo que el motor de deducción dejó calculado en el disco del servidor con su propio
temporizador (`recogida/deduccion.py`): se guarda en la base en segundos y un fallo no cambia el
resultado de la recogida.

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
from proceso import focos_termicos, impactos_guerra, incidentes, incursiones, presencia, solapes
from proceso.ataques import SENTIDO_UA_RU
from proceso.extraccion import Parada
from recogida import (
    busqueda_dirigida,
    catalogo_vivo,
    criterio_presencia,
    deduccion,
    detalle,
    directo_horaria,
    extractor,
    firms,
    gdelt,
    guerra,
    mediciones,
    oficiales,
)
from recogida.cache import CachePaginas
from recogida.descarga import Descargador, DescargaFallida
from recogida.ejecucion import SinCursor, ejecutar
from recogida.estado import CON_AVISO, LEIDA, NO_LEIDA, EstadoFuente, escribir_parcial
from recogida.fuente import CanalNoVerificado, HuecoDemasiadoGrande
from recogida.fuentes import FUENTES
from recogida.parte import vocabulario
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


def impactos(almacen: Almacen) -> list[focos_termicos.Impacto]:
    """Los impactos que se cruzan con FIRMS: incidentes con explosión o caída, regiones con
    impacto de los ataques RU→UA e impactos con lugar de la capa de guerra (los dos
    sentidos)."""
    codigos = {nombre: codigo for codigo, nombre in vocabulario().nombres.items()}
    hallados = [i for d in almacen.incidentes() if (i := focos_termicos.impacto_de_incidente(d))]
    ataques = almacen.ataques_ucrania()
    for ataque in ataques:
        hallados += focos_termicos.impactos_de_ataque(ataque, codigos)
    por_id = {a["id"]: a for a in ataques}
    hallados += [
        focos_termicos.impacto_de_guerra(d, *impactos_guerra.periodo_del_impacto(d, por_id))
        for d in impactos_guerra.vigentes(almacen)
        if impactos_guerra.con_firms(d)
    ]
    return hallados


def paso_guerra(almacen: Almacen, ahora: datetime) -> dict[str, EstadoFuente]:
    """Capa de guerra con lugar y su extractor. Nada de lo que falle aquí sale de esta función:
    queda en el registro y las fuentes, como no leídas."""
    from proceso.lugares_guerra import cargar

    try:
        return _paso_guerra(almacen, ahora)
    finally:
        # El nomenclátor ocupa cientos de megas: no se queda en memoria para los pasos siguientes.
        cargar.cache_clear()


def _paso_guerra(almacen: Almacen, ahora: datetime) -> dict[str, EstadoFuente]:
    from modelo import cliente as servicio
    from proceso import extraccion_guerra
    from proceso.lugares_guerra import cargar
    from recogida.canales_guerra import Datos, cargar_canales, directorio_datos
    from recogida.estado import leer_instante

    try:
        estados, resumen = guerra.paso_horario(almacen, ahora)
    except Exception as error:
        registro.warning("guerra no se procesa: %s", error)
        return {g: EstadoFuente(NO_LEIDA) for g in guerra.GRUPOS}
    resultado = {
        g: EstadoFuente(e["estado"], leer_instante(e["ultimo_dato"])) for g, e in estados.items()
    }
    try:
        configuracion = servicio.configuracion()
    except servicio.ClienteNoConfigurado:
        return resultado
    try:
        lote = extraccion_guerra.paso_lote(
            almacen, lambda: servicio.Cliente(configuracion, insistencia=servicio.HISTORICO),
            Datos(directorio_datos()), cargar_canales(), cargar(), guerra.raices_regiones(),
            ahora, al_dia=not resumen.pendientes,
        )  # fmt: skip
        if lote is not None:
            registro.info("lote del histórico de guerra: %s", lote)
    except Exception as error:
        registro.warning("lote del histórico de guerra fallido: %s", error)
    if resumen.mensajes == 0 and not almacen.mensajes_guerra(extraccion_guerra.PENDIENTE):
        return resultado
    try:
        hecho = extraccion_guerra.horaria(
            almacen, Datos(directorio_datos()), cargar_canales(), cargar(),
            guerra.raices_regiones(), ahora,
            lambda: servicio.Cliente(configuracion), Plazo(extraccion_guerra.TOPE_S),
        )  # fmt: skip
        registro.info(
            "extractor de guerra: llamadas=%d impactos=%d parada=%s",
            hecho.llamadas, hecho.impactos, hecho.parada,
        )  # fmt: skip
    except Exception as error:
        registro.warning("extractor de guerra fallido: %s", error)
    return resultado


def paso_firms(almacen: Almacen, ahora: datetime) -> EstadoFuente:
    """Descarga de FIRMS (si toca) y cruce con los impactos. Nada de lo que falle aquí sale
    de esta función: se registra, sin la clave, y la fuente queda como no leída."""
    datos = firms.Datos(firms.directorio_datos())
    clave = firms.clave_desde_entorno()
    estado = LEIDA
    lectura = firms.lectura_sin_descarga(datos)
    try:
        lectura = firms.recoger(datos, ahora, clave, firms.descargador(Plazo(firms.TOPE_S)))
        if lectura.descargada:
            registro.info("firms: %d focos en los dos últimos días", lectura.focos)
    except Exception as error:
        registro.warning("firms no se lee: %s", firms.redactar(str(error), clave))
        estado, lectura = NO_LEIDA, firms.lectura_sin_descarga(datos)
    try:
        todos = impactos(almacen)
        # Al leer los CSV solo se guardan los focos de alrededor de los impactos.
        datos.zonas = [(i.lat, i.lon) for i in todos if i.lat is not None and i.lon is not None]
        resumen = focos_termicos.evaluar_todos(
            almacen, todos, datos.focos, ahora, firms.CAJA,
            Plazo(focos_termicos.TOPE_S), firms.historico_reciente(datos, ahora),
        )  # fmt: skip
        registro.info("focos térmicos: %s", resumen.texto())
    except Exception as error:
        registro.warning("cruce con firms fallido: %s", firms.redactar(str(error), clave))
        estado = NO_LEIDA
    return EstadoFuente(estado, lectura.ultima_correcta)


def paso_busqueda(almacen: Almacen, ahora: datetime) -> None:
    """Incorporación de la búsqueda dirigida. Un fallo no cambia el resultado de la recogida."""
    try:
        hecho = busqueda_dirigida.paso_horario(almacen, ahora)
        registro.info("búsqueda dirigida: %s", hecho.texto())
    except Exception as error:
        registro.warning("búsqueda dirigida no incorporada: %s", str(error)[:300])


def paso_directo(almacen: Almacen, ahora: datetime) -> None:
    """Confirmación de los avisos en directo. Un fallo no cambia el resultado de la recogida."""
    try:
        registro.info(
            "avisos en directo confirmados: %d", directo_horaria.paso_horario(almacen, ahora)
        )
    except Exception as error:
        registro.warning("avisos en directo sin confirmar: %s", str(error)[:300])


def paso_detalle(almacen: Almacen, ahora: datetime) -> dict[str, EstadoFuente]:
    """Incorporación de las fuentes oficiales de detalle. Nada de lo que falle aquí sale de esta
    función: queda en el registro y sus fuentes, con aviso en estado.json."""
    leidas = detalle.estados()
    try:
        hecho = detalle.incorporar(almacen, ahora, modelos(almacen), plazo=Plazo(detalle.TOPE_S))
        registro.info("fuentes de detalle: %s", hecho.texto())
    except Exception as error:
        registro.warning("fuentes de detalle no incorporadas: %s", str(error)[:300])
        return {
            grupo: EstadoFuente(CON_AVISO if e.estado == LEIDA else e.estado, e.ultimo_dato)
            for grupo, e in leidas.items()
        }
    return leidas


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
        # Una vez por versión: criterio de presencia, titulares y un incidente por noche de
        # cierre en lo ya guardado (recogida/criterio_presencia.py), antes del extractor para
        # que extraiga en esta pasada los candidatos que se separan.
        try:
            criterio_presencia.aplicar(almacen, ahora, extractor.modelos_base())
        except Exception as error:
            registro.warning("criterio de presencia sin aplicar: %s", str(error)[:300])
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
        # Fuentes oficiales de detalle: lo que dejó en disco su temporizador entra en la base y
        # se cruza con los incidentes; lo nuevo se extrae con lo que deje del límite diario el
        # extractor de noticias. Como FIRMS, no cambia el código de salida.
        estados.update(paso_detalle(almacen, ahora))
        # Capa de guerra con lugar: no cambia el código de salida.
        estados.update(paso_guerra(almacen, ahora))
        # Anomalías térmicas: no cambian el código de salida.
        estados[firms.FUENTE_ID] = paso_firms(almacen, ahora)
        try:
            registro.info(
                "credibilidad de impactos de guerra con foco: %d cambiados",
                impactos_guerra.aplicar_focos(almacen, ahora),
            )
        except Exception as error:
            registro.warning("credibilidad con focos fallida: %s", error)
        # Tráfico aéreo y condiciones medidas: tampoco cambian el código de salida.
        estados[mediciones.FUENTE_TRAFICO] = mediciones.paso_trafico(almacen, ahora)
        estados[mediciones.FUENTE_CONDICIONES] = mediciones.paso_condiciones(almacen, ahora)
        # Búsqueda dirigida: lo que halló su temporizador para los cierres medidos sin
        # incidente entra como artículos; y la lista de lo que falta buscar, al día.
        paso_busqueda(almacen, ahora)
        # Avisos de la detección en directo: los que recoge un incidente de la base pasan a
        # confirmados (recogida/directo_horaria.py). No cambia el código de salida.
        paso_directo(almacen, ahora)
        # Lo que dejó calculado el motor de deducción (su propio temporizador): no cambia el
        # código de salida si falla.
        deduccion.paso_horario(almacen)
        # Lo que dejó el barrido del catálogo vivo (su propio temporizador): tampoco cambia el
        # código de salida si falla.
        catalogo_vivo.paso_horario(almacen)
        # Presencia del dron que confirman las declaraciones oficiales ya guardadas: la regla
        # se amplió y lo anterior se revisa en cada pasada; ya aplicada, no cambia nada.
        # Fusiones que las reglas de ahora ya no hacen (dos cierres de noches distintas, un cierre
        # que se repite): se deshacen; el absorbido vuelve con sus fuentes.
        try:
            vueltos = incidentes.revisar_fusiones(almacen, ahora, modelos(almacen))
            registro.info("fusiones deshechas por las reglas de ahora: %d", len(vueltos))
        except Exception as error:
            registro.warning("revisión de fusiones fallida: %s", str(error)[:300])
        confirmadas, sin_guardar = presencia.revisar(almacen, ahora, modelos(almacen))
        registro.info("presencia del dron confirmada por declaraciones: %d", len(confirmadas))
        if sin_guardar:
            registro.warning(
                "presencia sin guardar en %d incidentes que no validan", len(sin_guardar)
            )
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
