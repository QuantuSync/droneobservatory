"""Histórico de una fuente de partes desde octubre de 2022, en local.

Reanudable: el recorrido guarda su avance tras cada página y las páginas ya
descargadas salen de la caché. Con --solo-cache no se recorre nada: se
reprocesa lo que ya está en la caché, por ejemplo tras mejorar el parser.

Las publicaciones se incorporan a la base de la rama estado (o a una base
nueva si aún no hay): los ataques ya publicados conservan su identificador y
un cambio de cifras queda en el historial. Después la fuente se pone al día
desde el final de la caché como en una ejecución horaria. Al terminar escribe
la auditoría de cobertura por año con una muestra de partes para comprobarlos.

Uso: python -m recogida.historico --fuente <id> --correo <correo> [--solo-cache] [--sin-subir]
     [--base <db.age local>]
"""

import argparse
import json
import logging
import random
import sys
from collections import defaultdict
from collections.abc import Callable
from dataclasses import asdict
from datetime import UTC, date, datetime
from pathlib import Path
from tempfile import TemporaryDirectory

from almacen import remoto, sitio
from almacen.base import Almacen
from almacen.cifrado import abrir_cifrada, cargar_clave_local, guardar_cifrada
from esquema import Documento
from exportacion.publicar import publicar
from proceso import solapes
from proceso.ataques import SENTIDO_UA_RU
from recogida import auditoria
from recogida.cache import CachePaginas
from recogida.descarga import Descargador
from recogida.ejecucion import Recuentos, configuracion_fuente, ejecutar, procesar
from recogida.fuente import Fuente
from recogida.fuentes import POR_ID
from recogida.parte import ParteIlegible
from recogida.recorrido import Progreso, pagina, publicaciones_en_cache, recorrer_historico
from recogida.telegram import Publicacion

registro = logging.getLogger("recogida")

# 1 de octubre de 2022 a medianoche en Kyiv y en Moscú (UTC+3 las dos en esa fecha).
DESDE = datetime(2022, 9, 30, 21, 0, tzinfo=UTC)
DIRECTORIO = Path(__file__).resolve().parent.parent / "data" / "historico"
# Semilla fija para que la muestra de comprobación sea reproducible; su valor no importa.
SEMILLA_MUESTRA = 1
TAMANO_MUESTRA = 5


class HistoricoIncompleto(RuntimeError):
    pass


def publicaciones(cache: CachePaginas, canal: str, inicio: int) -> list[Publicacion]:
    """Publicaciones del histórico sin repetir, de la más antigua a la más reciente."""
    unicas = {p.id: p for p in publicaciones_en_cache(cache, canal, inicio, DESDE)}
    return [unicas[i] for i in sorted(unicas)]


def cobertura(
    almacen: Almacen, lista: list[Publicacion], fuente: Fuente, config: Documento, ahora: datetime
) -> dict[int, Recuentos]:
    """Procesa por años para poder contar la cobertura de cada uno."""
    por_anio: dict[int, list[Publicacion]] = defaultdict(list)
    for publicacion in lista:
        por_anio[publicacion.fecha.astimezone(fuente.perfil.zona).year].append(publicacion)
    return {
        anio: procesar(almacen, por_anio[anio], fuente, config, ahora) for anio in sorted(por_anio)
    }


def legible(fuente: Fuente) -> Callable[[Publicacion], bool]:
    def comprobar(publicacion: Publicacion) -> bool:
        try:
            fuente.leer(publicacion.texto, publicacion.fecha)
        except ParteIlegible:
            return False
        return True

    return comprobar


def muestra(lista: list[Publicacion], fuente: Fuente) -> list[Documento]:
    leidos = []
    for publicacion in lista:
        if not fuente.es_parte(publicacion.texto):
            continue
        try:
            leidos.append((publicacion, fuente.leer(publicacion.texto, publicacion.fecha)))
        except ParteIlegible:
            continue
    elegidos = random.Random(SEMILLA_MUESTRA).sample(leidos, min(TAMANO_MUESTRA, len(leidos)))
    resultado = []
    for publicacion, leido in sorted(elegidos, key=lambda x: x[0].id):
        datos = asdict(leido)
        datos["inicio"] = leido.inicio.documento()
        datos["fin"] = leido.fin.documento()
        resultado.append({"enlace": publicacion.enlace, "extraido": datos})
    return resultado


def informe(
    por_anio: dict[int, Recuentos],
    cobertura_dias: dict[int, auditoria.Anio],
    ejemplos: list[Documento],
) -> str:
    lineas = [
        "| Año | Publicaciones leídas | Partes detectados | Leídos bien | Fallidos "
        "| Motivo más frecuente |",
        "| --- | ---: | ---: | ---: | ---: | --- |",
    ]
    total = Recuentos()
    for anio, r in por_anio.items():
        total.sumar(r)
        motivo = r.motivos.most_common(1)[0][0] if r.motivos else "—"
        lineas.append(
            f"| {anio} | {r.publicaciones} | {r.partes} | {r.leidos} | {r.fallidos} | {motivo} |"
        )
    motivo = total.motivos.most_common(1)[0][0] if total.motivos else "—"
    lineas.append(
        f"| Total | {total.publicaciones} | {total.partes} | {total.leidos} | {total.fallidos} "
        f"| {motivo} |"
    )
    lineas += ["", "Cobertura por días:", "", auditoria.tabla(cobertura_dias)]
    lineas += [auditoria.explicaciones(cobertura_dias), "Muestra:", ""]
    for ejemplo in ejemplos:
        extraido = json.dumps(ejemplo["extraido"], ensure_ascii=False, indent=1, default=str)
        lineas += [f"- {ejemplo['enlace']}", "", "```json", extraido, "```", ""]
    return "\n".join(lineas) + "\n"


def base_de_estado(repositorio: str, temporal: Path) -> Almacen:
    """La base de la rama estado (o del disco, según el modo), o una nueva si la rama aún no
    existe."""
    almacen = sitio.abrir_base(temporal, repositorio)
    if almacen is not None:
        return almacen
    registro.info("no hay base en la rama %s: se empieza una nueva", remoto.RAMA)
    return Almacen.abrir()


def principal(argumentos: list[str] | None = None) -> int:
    opciones = argparse.ArgumentParser(description=__doc__)
    opciones.add_argument("--fuente", required=True, choices=sorted(POR_ID))
    opciones.add_argument("--correo", required=True, help="correo del autor del commit de estado")
    opciones.add_argument("--repositorio", default=remoto.REPOSITORIO)
    opciones.add_argument("--solo-cache", action="store_true", help="no recorre el canal")
    opciones.add_argument("--sin-subir", action="store_true", help="no sube la base a la rama")
    opciones.add_argument(
        "--base", type=Path, help="base cifrada local de la que partir en vez de la rama estado"
    )
    args = opciones.parse_args(argumentos)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
    cargar_clave_local()
    fuente = POR_ID[args.fuente]

    descargador, cache = Descargador(), CachePaginas()
    portada = pagina(descargador, cache, fuente.canal, None, usar_cache=False)
    fuente.verificar(descargador, portada)
    ruta_progreso = cache.directorio / fuente.canal / "historico.json"
    if args.solo_cache:
        progreso = Progreso.leer(ruta_progreso)
    else:
        progreso = recorrer_historico(descargador, cache, fuente.canal, DESDE, ruta_progreso)
    if progreso is None or progreso.siguiente is not None:
        raise HistoricoIncompleto(f"el recorrido de {fuente.canal} no ha terminado")
    registro.info("recorrido completo: %d páginas", progreso.paginas)

    ahora = datetime.now(UTC)
    lista = publicaciones(cache, fuente.canal, progreso.inicio)
    config = configuracion_fuente(fuente.id)
    with TemporaryDirectory() as temporal:
        almacen = (
            Almacen(abrir_cifrada(args.base))
            if args.base
            else base_de_estado(args.repositorio, Path(temporal))
        )
        por_anio = cobertura(almacen, lista, fuente, config, ahora)
        if almacen.cursor(fuente.id) is None:
            ultima = lista[-1]
            almacen.guardar_cursor(
                fuente.id, {"ultimo_id": ultima.id, "fecha": ultima.fecha.isoformat()}
            )
        for anio, r in por_anio.items():
            registro.info("%d: %s", anio, r.resumen())
        # Lo publicado después de la caché y la relectura de las últimas 48 horas.
        ejecutar(almacen, descargador, cache, fuente, ahora)
        enlazados = solapes.enlazar(almacen, SENTIDO_UA_RU, ahora)
        registro.info("tramos con enlace cambiado: %d", enlazados)

        hasta: date = lista[-1].fecha.astimezone(fuente.perfil.zona).date()
        dias = auditoria.auditar(
            lista,
            fuente.perfil.zona,
            DESDE.astimezone(fuente.perfil.zona).date(),
            hasta,
            fuente.es_parte,
            legible(fuente),
            fuente.palabras_dron,
            fuente.explicar,
        )
        DIRECTORIO.mkdir(parents=True, exist_ok=True)
        (DIRECTORIO / f"cobertura-{fuente.id}.md").write_text(
            informe(por_anio, dias, muestra(lista, fuente)), encoding="utf-8", newline="\n"
        )
        publicar(almacen, ahora)
        ruta = DIRECTORIO / remoto.FICHERO
        guardar_cifrada(almacen.conexion, ruta)
        if not args.sin_subir:
            sitio.guardar_base(almacen, Path(temporal), args.correo, args.repositorio)
        almacen.cerrar()
    return 0


if __name__ == "__main__":
    sys.exit(principal())
