"""Fuentes oficiales de detalle: recogida en disco e incorporación a la base.

Las fuentes de configuracion/fuentes_detalle.json (UK Airprox Board, respuestas de gobiernos
en el parlamento, informes de investigación, cierres de investigaciones policiales, sentencias
y estadísticas oficiales) y las listas de noticias oficiales que se cargan con JavaScript se
leen en dos tiempos, como FIRMS y el tráfico aéreo:

1. **Recogida** (`python -m recogida.detalle recoger`), con su propio temporizador cada 3 horas
   y su propio cerrojo (servidor/detalle.sh): descarga lo nuevo de cada fuente con las reglas
   de siempre (identificación del observatorio, robots.txt, pausas, comprobación de contenido
   real) y lo deja en la carpeta de datos, fuera de la base: los encuentros con aeronave ya
   leídos, los documentos con sus pasajes sobre drones ya localizados y las listas
   renderizadas. No toca la base ni llama al extractor. Una fuente que falla no para las
   demás: queda en control.json con su error y la siguiente ejecución lo vuelve a intentar.
2. **Incorporación**, dentro de la recogida horaria y con el cerrojo de siempre: guarda en la
   base los encuentros y los documentos nuevos, extrae los documentos nuevos de los últimos
   30 días dentro del límite diario de gasto, procesa los resultados de lotes del histórico
   ya terminados y cruza todo con los incidentes (proceso/detalle.py). Tarda segundos.

El histórico (`python -m recogida.detalle historico`) se procesa una sola vez, por lotes, con
su propio presupuesto (modo de gasto «detalle», 3 dólares): envía los documentos pendientes y
deja los resultados en la carpeta de datos, que la recogida horaria incorpora.

Uso:
    python -m recogida.detalle recoger [--historico]
    python -m recogida.detalle historico [--repositorio <url>]
"""

import argparse
import contextlib
import json
import logging
import os
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from almacen import remoto, sitio
from almacen.base import Almacen, DocumentoInvalido
from esquema import Documento
from modelo import cliente as servicio
from modelo import coste
from proceso import detalle, extraccion_oficial
from recogida import airprox, navegador, oficiales
from recogida.descarga import AGENTE_EODI, Descargador
from recogida.estado import CON_AVISO, LEIDA, NO_LEIDA, EstadoFuente
from recogida.plazo import Plazo, TiempoAgotado

registro = logging.getLogger("recogida")

DIRECTORIO = Path(__file__).resolve().parent.parent / "configuracion"
VARIABLE_DATOS = oficiales.VARIABLE_DATOS_DETALLE
# Lo que entra cada hora con el límite diario: documentos de los últimos 30 días. Lo anterior
# es del histórico, que va por lotes con su presupuesto.
VENTANA_DIARIA = timedelta(days=30)
# Tope de la incorporación en la recogida horaria: guardar registros tarda segundos; las
# llamadas al extractor, de 5 a 15 s cada una. 300 s caben de sobra en lo que deja libre la
# recogida (horaria.py) y lo que no quepa queda para la siguiente.
TOPE_S = 300.0
# Grupos con que salen en estado.json, en este orden.
GRUPOS = ("airprox", "parlamentos", "investigaciones", "estadisticas_oficiales", "paginas_js")
CONTROL = "control.json"


def carpeta() -> Path:
    return Path(os.environ.get(VARIABLE_DATOS, "data/detalle"))


def fuentes(ruta: Path = DIRECTORIO / "fuentes_detalle.json") -> list[Documento]:
    datos: dict[str, Any] = json.loads(ruta.read_text(encoding="utf-8"))
    return list(datos["fuentes"])


def _escribir(ruta: Path, contenido: Any) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    temporal = ruta.with_suffix(ruta.suffix + ".tmp")
    temporal.write_text(json.dumps(contenido, ensure_ascii=False, sort_keys=True, indent=1),
                        encoding="utf-8", newline="\n")  # fmt: skip
    temporal.replace(ruta)


def _leer(ruta: Path, defecto: Any) -> Any:
    return json.loads(ruta.read_text(encoding="utf-8")) if ruta.exists() else defecto


def _instante(momento: datetime) -> str:
    return momento.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


# --- Documentos recogidos ---------------------------------------------------------------


def ruta_documentos(raiz: Path, fuente_id: str) -> Path:
    return raiz / "documentos" / f"{fuente_id}.json"


def documentos_recogidos(raiz: Path) -> list[Documento]:
    """Todos los documentos recogidos, de todas las fuentes, en orden de identificador."""
    resultado: dict[str, Documento] = {}
    for ruta in sorted((raiz / "documentos").glob("*.json")):
        for documento in _leer(ruta, []):
            resultado[documento["id"]] = documento
    return [resultado[k] for k in sorted(resultado)]


def guardar_documentos(raiz: Path, fuente_id: str, nuevos: list[Documento]) -> int:
    """Añade o sustituye los documentos de la fuente. Devuelve cuántos son nuevos o cambian."""
    ruta = ruta_documentos(raiz, fuente_id)
    actuales = {d["id"]: d for d in _leer(ruta, [])}
    cambios = sum(1 for d in nuevos if actuales.get(d["id"]) != d)
    actuales.update({d["id"]: d for d in nuevos})
    _escribir(ruta, [actuales[k] for k in sorted(actuales)])
    return cambios


def estadisticas_recogidas(raiz: Path) -> list[Documento]:
    """Las tablas de cifras leídas por código: cada una con su documento y sus cifras."""
    resultado = []
    for ruta in sorted((raiz / "estadisticas").glob("*.json")):
        resultado += _leer(ruta, [])
    return resultado


# --- Recolectores ---------------------------------------------------------------------

Recolector = Callable[[Documento, Path, Descargador, datetime, bool], int]


def recolector_airprox(
    fuente: Documento, raiz: Path, descargador: Descargador, ahora: datetime, historico: bool
) -> int:
    """El Excel histórico, los catálogos y los informes que faltan; deja los encuentros leídos."""
    datos = airprox.Datos(raiz / "airprox")
    hasta = ahora.year
    anios = list(range(airprox.PRIMER_ANIO if historico else hasta - 1, hasta + 1))
    recuentos = airprox.recoger(datos, descargador, anios, frozenset({hasta - 1, hasta}))
    lista = airprox.encuentros(datos, ahora)
    _escribir(raiz / "airprox" / "encuentros.json", lista)
    registro.info("airprox %s encuentros=%d", recuentos.texto(), len(lista))
    return len(lista)


def recolector_paginas_js(
    fuente: Documento, raiz: Path, descargador: Descargador, ahora: datetime, historico: bool
) -> int:
    """Renderiza las listas de noticias oficiales que se cargan con JavaScript."""
    leidas = 0
    errores = []
    for oficial in navegador.con_javascript(oficiales.fuentes()):
        lector = oficiales.robots(descargador, oficial["url"])
        if not lector.can_fetch(AGENTE_EODI, oficial["url"]):
            errores.append(f"{oficial['id']}: robots.txt no lo permite")
            continue
        try:
            render = navegador.leer(oficial, raiz / "paginas_js")
        except Exception as error:
            errores.append(f"{oficial['id']}: {str(error)[:200]}")
            continue
        registro.info(
            "paginas_js %s enlaces=%d segundos=%.1f memoria_mb=%s",
            render.id, render.enlaces, render.segundos, render.memoria_mb,
        )  # fmt: skip
        leidas += 1
    if errores:
        raise RuntimeError("; ".join(errores))
    return leidas


RECOLECTORES: dict[str, Recolector] = {
    "airprox": recolector_airprox,
    "paginas_js": recolector_paginas_js,
}


def registrar_recolector(tipo: str, funcion: Recolector) -> None:
    RECOLECTORES[tipo] = funcion


def _cargar_recolectores() -> None:
    """Los recolectores de documentos viven en sus módulos y se registran al importarlos."""
    for modulo in (
        "recogida.parlamentos", "recogida.investigaciones", "recogida.estadisticas",
        "recogida.guardia_civil",
    ):  # fmt: skip
        with contextlib.suppress(ModuleNotFoundError):
            __import__(modulo)


@dataclass
class Resultado:
    leidas: list[str] = field(default_factory=list)
    fallidas: list[str] = field(default_factory=list)


def recoger(raiz: Path, ahora: datetime, historico: bool = False,
            solo: frozenset[str] = frozenset()) -> Resultado:  # fmt: skip
    """Recoge cada fuente; anota en control.json la última lectura correcta y los errores."""
    _cargar_recolectores()
    control: dict[str, Any] = _leer(raiz / CONTROL, {})
    resultado = Resultado()
    for fuente in fuentes():
        if solo and fuente["id"] not in solo:
            continue
        recolector = RECOLECTORES.get(fuente["tipo"])
        entrada = control.setdefault(fuente["id"], {})
        entrada["grupo"] = fuente["grupo"]
        entrada["ultimo_intento"] = _instante(ahora)
        if recolector is None:
            entrada.update({"estado": NO_LEIDA, "error": f"sin lector para {fuente['tipo']}"})
            resultado.fallidas.append(fuente["id"])
            continue
        try:
            cuantos = recolector(fuente, raiz, Descargador(agente=AGENTE_EODI), ahora, historico)
        except Exception as error:
            registro.warning("detalle: %s no se lee: %s", fuente["id"], str(error)[:300])
            entrada.update({"estado": NO_LEIDA, "error": str(error)[:300]})
            resultado.fallidas.append(fuente["id"])
        else:
            entrada.update(
                {"estado": LEIDA, "ultima_correcta": _instante(ahora), "registros": cuantos}
            )
            entrada.pop("error", None)
            resultado.leidas.append(fuente["id"])
        _escribir(raiz / CONTROL, control)
    return resultado


# --- Incorporación en la recogida horaria -----------------------------------------------


@dataclass
class Incorporacion:
    encuentros: int = 0
    documentos: int = 0
    estadisticas: int = 0
    extraidos: int = 0
    lotes: int = 0
    retirados: list[str] = field(default_factory=list)
    parada: str | None = None
    revision: detalle.Revision | None = None

    def texto(self) -> str:
        revision = self.revision.texto() if self.revision else "sin revisión"
        return (
            f"encuentros={self.encuentros} documentos={self.documentos} "
            f"estadisticas={self.estadisticas} extraidos={self.extraidos} lotes={self.lotes} "
            f"altas_retiradas={len(self.retirados)} "
            f"parada={self.parada or 'ninguna'}; {revision}"
        )


def incorporar_encuentros(almacen: Almacen, raiz: Path, ahora: datetime) -> int:
    """Guarda los encuentros leídos; conserva el alta y el enlace de los que ya estaban."""
    guardados = 0
    for encuentro in _leer(raiz / "airprox" / "encuentros.json", []):
        previo = almacen.encuentro(encuentro["id"])
        if previo is not None:
            encuentro["control"]["alta"] = previo["control"]["alta"]
            if "incidente" in previo:
                encuentro["incidente"] = previo["incidente"]
        try:
            guardados += almacen.guardar_encuentro(encuentro, ahora)
        except DocumentoInvalido as error:
            registro.warning("encuentro %s no válido: %s", encuentro["id"], str(error)[:200])
    return guardados


def incorporar_documentos(almacen: Almacen, raiz: Path, ahora: datetime) -> int:
    """Da de alta los documentos recogidos que aún no están en la base."""
    nuevos = 0
    for recogido in documentos_recogidos(raiz):
        if almacen.documento_oficial(recogido["id"]) is not None:
            continue
        try:
            almacen.guardar_documento_oficial(
                extraccion_oficial.documento_base(recogido, ahora), ahora
            )
        except DocumentoInvalido as error:
            registro.warning("documento %s no válido: %s", recogido["id"], str(error)[:200])
            continue
        nuevos += 1
    return nuevos


def incorporar_estadisticas(almacen: Almacen, raiz: Path, ahora: datetime) -> int:
    """Las cifras de las tablas leídas por código, con su documento. Devuelve cuántas cifras
    son nuevas o han cambiado."""
    guardadas = 0
    for tabla in estadisticas_recogidas(raiz):
        documento = extraccion_oficial.documento_base({**tabla["documento"], "pasajes": []}, ahora)
        documento["estado"] = "extraido"
        documento["control"]["metodo"] = "parser"
        previo = almacen.documento_oficial(documento["id"])
        if previo is not None:
            documento["control"]["alta"] = previo["control"]["alta"]
        ids, motivos, cambiadas = extraccion_oficial.guardar_estadisticas(
            almacen, documento, tabla["cifras"], "parser", ahora, None
        )
        documento["estadisticas"] = ids
        if motivos:
            documento["descartados"] = motivos
        try:
            almacen.guardar_documento_oficial(documento, ahora)
        except DocumentoInvalido as error:
            registro.warning("tabla %s no válida: %s", documento["id"], str(error)[:200])
        guardadas += cambiadas
    return guardadas


def pendientes(almacen: Almacen, raiz: Path, desde: datetime | None) -> list[Documento]:
    """Los documentos recogidos con pasajes que aún no se han extraído; con `desde`, solo los
    publicados desde ese día. Los más recientes primero."""
    por_extraer = {d["id"] for d in almacen.documentos_oficiales("pendiente")}
    corte = desde.date().isoformat() if desde else ""
    lista = [
        r for r in documentos_recogidos(raiz)
        if r["id"] in por_extraer and r.get("pasajes") and r["fecha"] >= corte
    ]  # fmt: skip
    return sorted(lista, key=lambda r: (r["fecha"], r["id"]), reverse=True)


def incorporar_lotes(almacen: Almacen, raiz: Path, ahora: datetime, modelos: frozenset[str]) -> int:
    """Procesa los resultados de los lotes del histórico que aún no se han incorporado."""
    hechos = 0
    recogidos = documentos_recogidos(raiz)
    for ruta in sorted((raiz / "lotes").glob("*.resultados.json")):
        marca = ruta.with_suffix(".incorporado")
        if marca.exists():
            continue
        cuentas = extraccion_oficial.procesar_resultados(
            almacen, _leer(ruta, []), recogidos, ahora, modelos, coste.Modo.DETALLE
        )
        registro.info("lote %s incorporado: %s", ruta.name, cuentas)
        marca.write_text(_instante(ahora), encoding="utf-8")
        hechos += 1
    return hechos


def incorporar(
    almacen: Almacen,
    ahora: datetime,
    modelos: frozenset[str],
    raiz: Path | None = None,
    plazo: Plazo | None = None,
    fabrica: Callable[[servicio.Configuracion], Any] = servicio.Cliente,
) -> Incorporacion:
    """El paso de la recogida horaria: registros nuevos, extracción de lo nuevo y cruce."""
    raiz = raiz or carpeta()
    hecho = Incorporacion()
    hecho.encuentros = incorporar_encuentros(almacen, raiz, ahora)
    hecho.documentos = incorporar_documentos(almacen, raiz, ahora)
    hecho.estadisticas = incorporar_estadisticas(almacen, raiz, ahora)
    hecho.lotes = incorporar_lotes(almacen, raiz, ahora, modelos)
    nuevos = pendientes(almacen, raiz, ahora - VENTANA_DIARIA)
    if nuevos:
        try:
            cliente = fabrica(servicio.configuracion())
        except servicio.ClienteNoConfigurado as error:
            hecho.parada = f"extractor sin configurar: {error}"
        else:
            extraidos = extraccion_oficial.extraer(
                almacen, cliente, nuevos, ahora, coste.Modo.HORARIO, modelos, plazo
            )
            hecho.extraidos = len(extraidos.documentos)
            if extraidos.parada is not None:
                hecho.parada = f"{extraidos.parada}: {extraidos.motivo[:120]}"
    hecho.retirados = extraccion_oficial.revalidar_altas(almacen, ahora, modelos)
    hecho.revision = detalle.revisar(almacen, ahora, modelos)
    return hecho


def estados(raiz: Path | None = None) -> dict[str, EstadoFuente]:
    """Para estado.json, por grupo: leída si todas sus fuentes se leyeron la última vez, con
    aviso si alguna falló, sin leer si ninguna; y la última lectura correcta."""
    control: dict[str, Any] = _leer((raiz or carpeta()) / CONTROL, {})
    resultado = {}
    for grupo in GRUPOS:
        entradas = [e for e in control.values() if e.get("grupo") == grupo]
        correctas = [e["ultima_correcta"] for e in entradas if e.get("ultima_correcta")]
        ultima = (
            datetime.fromisoformat(max(correctas).replace("Z", "+00:00")) if correctas else None
        )
        if not entradas or all(e.get("estado") == NO_LEIDA for e in entradas):
            estado = NO_LEIDA
        elif any(e.get("estado") != LEIDA for e in entradas):
            estado = CON_AVISO
        else:
            estado = LEIDA
        resultado[grupo] = EstadoFuente(estado, ultima)
    return resultado


# --- Histórico por lotes --------------------------------------------------------------


def historico(raiz: Path, almacen: Almacen, cliente: Any, ahora: datetime) -> int:
    """Envía como un lote los documentos pendientes que caben en el presupuesto del histórico,
    espera a que termine y deja los resultados para la recogida horaria. Devuelve cuántos."""
    sin_incorporar = [
        r for r in (raiz / "lotes").glob("*.resultados.json")
        if not r.with_suffix(".incorporado").exists()
    ]  # fmt: skip
    if sin_incorporar:
        # Su gasto aún no está en la base: otro lote ahora podría pasar del presupuesto.
        registro.error("hay lotes sin incorporar: %s", [r.name for r in sin_incorporar])
        return 0
    todos = pendientes(almacen, raiz, None)
    # Los documentos recogidos que la base aún no tiene también cuentan: la recogida horaria
    # los dará de alta como pendientes antes de incorporar los resultados.
    conocidos = {d["id"] for d in almacen.documentos_oficiales()}
    todos += [
        r for r in documentos_recogidos(raiz) if r["id"] not in conocidos and r.get("pasajes")
    ]
    # Lo de los últimos 30 días lo extrae la recogida horaria con el límite diario.
    corte = (ahora - VENTANA_DIARIA).date().isoformat()
    todos = [r for r in todos if r["fecha"] < corte]
    elegidos = extraccion_oficial.recortar(almacen, todos, coste.Modo.DETALLE)
    registro.info("histórico: pendientes=%d caben=%d", len(todos), len(elegidos))
    if not elegidos:
        return 0
    lote = extraccion_oficial.enviar_lote(cliente, elegidos)
    carpeta_lotes = raiz / "lotes"
    enviado = {
        "id": lote["id"],
        "enviado": _instante(ahora),
        "documentos": [r["id"] for r in elegidos],
    }
    _escribir(carpeta_lotes / f"{lote['id']}.json", enviado)
    registro.info("lote %s enviado con %d documentos", lote["id"], len(elegidos))
    lote = extraccion_oficial.esperar_lote(cliente, lote)
    _escribir(carpeta_lotes / f"{lote['id']}.resultados.json", cliente.resultados_lote(lote))
    registro.info("lote %s terminado: resultados en disco", lote["id"])
    return len(elegidos)


def principal(argumentos: list[str] | None = None) -> int:
    opciones = argparse.ArgumentParser(description=__doc__)
    ordenes = opciones.add_subparsers(dest="orden", required=True)
    o_recoger = ordenes.add_parser("recoger")
    o_recoger.add_argument("--historico", action="store_true")
    o_recoger.add_argument("--solo", nargs="*", default=[])
    o_historico = ordenes.add_parser("historico")
    o_historico.add_argument("--repositorio", default=remoto.REPOSITORIO)
    args = opciones.parse_args(argumentos)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    ahora = datetime.now(UTC)
    raiz = carpeta()
    if args.orden == "recoger":
        resultado = recoger(raiz, ahora, args.historico, frozenset(args.solo))
        registro.info("detalle: leídas=%s fallidas=%s", resultado.leidas, resultado.fallidas)
        return 0
    servicio.cargar_local()
    cliente = servicio.Cliente(servicio.configuracion(), insistencia=servicio.HISTORICO)
    with TemporaryDirectory() as temporal:
        abierta = sitio.abrir_base(Path(temporal), args.repositorio)
        if abierta is None:
            registro.error("no hay base en la rama %s", remoto.RAMA)
            return 1
        # Solo se lee: la base la escribe la recogida horaria al incorporar los resultados.
        almacen = abierta
        try:
            historico(raiz, almacen, cliente, ahora)
        except TiempoAgotado:
            return 1
        finally:
            almacen.cerrar()
    return 0


if __name__ == "__main__":
    # Con «python -m», este fichero es __main__ y los lectores de otros módulos se registran
    # en recogida.detalle, otra copia: la orden tiene que ejecutarse en esa.
    from recogida import detalle as _modulo

    sys.exit(_modulo.principal())
