"""Recuperación del histórico de la Fuerza Aérea desde octubre de 2022, una vez y en local.

Reanudable: el recorrido guarda su avance tras cada página y las páginas ya
descargadas salen de la caché. Al terminar construye la base desde cero,
la sube cifrada a la rama estado, regenera los ficheros públicos y escribe
un informe de cobertura por año con una muestra de partes para comprobarlos.

Uso: python -m recogida.historico --correo <correo del autor> [--sin-subir] [--reemplazar]
"""

import argparse
import json
import logging
import random
import sys
from collections import Counter, defaultdict
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from almacen import remoto
from almacen.base import Almacen
from almacen.cifrado import cargar_clave_local, guardar_cifrada
from esquema import Documento
from exportacion.publicar import publicar
from recogida import fuerza_aerea, parte
from recogida.cache import CachePaginas
from recogida.descarga import Descargador
from recogida.ejecucion import Recuentos, configuracion_fuente, procesar
from recogida.recorrido import pagina, publicaciones_en_cache, recorrer_historico
from recogida.telegram import Publicacion

registro = logging.getLogger("recogida")

# 1 de octubre de 2022 a medianoche en Kyiv (UTC+3 en esa fecha).
DESDE = datetime(2022, 9, 30, 21, 0, tzinfo=UTC)
DIRECTORIO = Path(__file__).resolve().parent.parent / "data" / "historico"
# Semilla fija para que la muestra de comprobación sea reproducible; su valor no importa.
SEMILLA_MUESTRA = 1
TAMANO_MUESTRA = 5


def publicaciones(cache: CachePaginas, inicio: int) -> list[Publicacion]:
    """Publicaciones del histórico sin repetir, de la más antigua a la más reciente."""
    unicas = {p.id: p for p in publicaciones_en_cache(cache, fuerza_aerea.CANAL, inicio, DESDE)}
    return [unicas[i] for i in sorted(unicas)]


def cobertura(
    almacen: Almacen, lista: list[Publicacion], config: Documento, ahora: datetime
) -> dict[int, Recuentos]:
    """Procesa por años para poder contar la cobertura de cada uno."""
    por_anio: dict[int, list[Publicacion]] = defaultdict(list)
    for publicacion in lista:
        por_anio[publicacion.fecha.astimezone(parte.KYIV).year].append(publicacion)
    return {anio: procesar(almacen, por_anio[anio], config, ahora) for anio in sorted(por_anio)}


def muestra(lista: list[Publicacion]) -> list[Documento]:
    leidos = []
    for publicacion in lista:
        if not parte.es_parte(publicacion.texto):
            continue
        try:
            leidos.append((publicacion, parte.leer(publicacion.texto, publicacion.fecha)))
        except parte.ParteIlegible:
            continue
    elegidos = random.Random(SEMILLA_MUESTRA).sample(leidos, TAMANO_MUESTRA)
    resultado = []
    for publicacion, leido in sorted(elegidos, key=lambda x: x[0].id):
        datos = asdict(leido)
        datos["inicio"] = leido.inicio.documento()
        datos["fin"] = leido.fin.documento()
        resultado.append({"enlace": publicacion.enlace, "extraido": datos})
    return resultado


def informe(por_anio: dict[int, Recuentos], ejemplos: list[Documento]) -> str:
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
    lineas += ["", "Muestra:", ""]
    for ejemplo in ejemplos:
        extraido = json.dumps(ejemplo["extraido"], ensure_ascii=False, indent=1)
        lineas += [f"- {ejemplo['enlace']}", "", "```json", extraido, "```", ""]
    return "\n".join(lineas) + "\n"


def principal(argumentos: list[str] | None = None) -> int:
    opciones = argparse.ArgumentParser(description=__doc__)
    opciones.add_argument("--correo", required=True, help="correo del autor del commit de estado")
    opciones.add_argument("--repositorio", default=remoto.REPOSITORIO)
    opciones.add_argument("--sin-subir", action="store_true", help="no sube la base a la rama")
    opciones.add_argument("--reemplazar", action="store_true", help="sustituye una base ya subida")
    args = opciones.parse_args(argumentos)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
    cargar_clave_local()
    if not args.sin_subir and not args.reemplazar and remoto.existe(args.repositorio):
        registro.error("la rama %s ya existe: usa --reemplazar para sustituirla", remoto.RAMA)
        return 1

    descargador, cache = Descargador(), CachePaginas()
    portada = pagina(descargador, cache, fuerza_aerea.CANAL, None, usar_cache=False)
    fuerza_aerea.verificar(descargador, portada)
    ruta_progreso = cache.directorio / fuerza_aerea.CANAL / "historico.json"
    progreso = recorrer_historico(descargador, cache, fuerza_aerea.CANAL, DESDE, ruta_progreso)
    registro.info("recorrido completo: %d páginas", progreso.paginas)

    ahora = datetime.now(UTC)
    lista = publicaciones(cache, progreso.inicio)
    almacen = Almacen.abrir()
    config = configuracion_fuente()
    por_anio = cobertura(almacen, lista, config, ahora)
    ultima = lista[-1]
    cursor = {"ultimo_id": ultima.id, "fecha": ultima.fecha.isoformat()}
    almacen.guardar_cursor(config["id"], cursor)
    for anio, r in por_anio.items():
        registro.info("%d: %s", anio, r.resumen())

    DIRECTORIO.mkdir(parents=True, exist_ok=True)
    (DIRECTORIO / "cobertura.md").write_text(
        informe(por_anio, muestra(lista)), encoding="utf-8", newline="\n"
    )
    motivos = Counter(f["motivo"] for f in almacen.fallidos(config["id"]))
    registro.info("motivos de fallo: %s", dict(motivos.most_common()))
    publicar(almacen, ahora)
    ruta = DIRECTORIO / remoto.FICHERO
    guardar_cifrada(almacen.conexion, ruta)
    if not args.sin_subir:
        remoto.subir(ruta, args.correo, args.repositorio)
        registro.info("base subida a la rama %s", remoto.RAMA)
    almacen.cerrar()
    return 0


if __name__ == "__main__":
    sys.exit(principal())
