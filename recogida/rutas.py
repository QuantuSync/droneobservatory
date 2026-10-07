"""Rutas de los drones sobre Ucrania: del archivo del seguimiento a las franjas publicadas.

Órdenes (en el servidor, como `eodi`, con su propio temporizador y tope de memoria):

- `importar-historico --cache <carpeta>`: pasa las páginas ya descargadas del canal de la Fuerza
  Aérea (la caché `data/cache/kpszsu/antes-<id>.html.gz`) al archivo del seguimiento, un fichero
  por mes (`kpszsu/historico/kpszsu-historico-AAAA-MM.jsonl.gz`), sin volver a descargar nada.
  Un mes que ya está no se reescribe: solo se añade lo que falta en un fichero `.parteN`.
- `estructurar [--todo]`: cada noche a su fichero (`datos/rutas/noches/AAAA-MM-DD.json.gz`), de
  una en una; sin `--todo`, solo las noches nuevas y las de los dos últimos días.
- `calcular`: reconstruye las rutas de cada noche, las compara con NEPTUN y con la línea recta y
  escribe lo publicable (`datos/rutas/rutas.json`) y la comprobación (`comprobacion.json`).

Nada de esto toca la base ni el clon: la recogida horaria publica `rutas.json` cuando cambia.
"""

import argparse
import gzip
import json
import logging
import os
import re
import sys
import time
from collections import defaultdict
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from proceso.rutas import noches
from recogida import seguimiento

registro = logging.getLogger(__name__)
VARIABLE_DATOS = "EODI_RUTAS_DATOS"
VARIABLE_SEGUIMIENTO = "EODI_SEGUIMIENTO_DATOS"


DATOS = Path.home() / "datos" / "rutas"


def datos_rutas() -> Path:
    return Path(os.environ.get(VARIABLE_DATOS) or DATOS)


def datos_seguimiento() -> Path:
    return seguimiento.directorio_datos()


def _escribir_gz(ruta: Path, texto: str) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    temporal = ruta.with_suffix(ruta.suffix + ".tmp")
    temporal.write_bytes(gzip.compress(texto.encode("utf-8"), mtime=0))
    temporal.replace(ruta)


# --- Histórico del canal ---------------------------------------------------------------------


_PAGINA = re.compile(r"antes-(\d+)\.html\.gz$")


def _numero_de_pagina(ruta: Path) -> int:
    encontrado = _PAGINA.search(ruta.name)
    return int(encontrado.group(1)) if encontrado else 0


def importar_historico(cache: Path, datos: Path) -> dict[str, int]:
    """Publicaciones de las páginas en caché, por mes, en el formato del archivo. Lo que ya está
    en el archivo no se reescribe."""
    por_mes: dict[str, dict[int, dict[str, Any]]] = defaultdict(dict)
    paginas = sorted(cache.glob("antes-*.html.gz"), key=_numero_de_pagina)
    for ruta in paginas:
        html = gzip.decompress(ruta.read_bytes()).decode("utf-8")
        for bloque in seguimiento.bloques_pagina(html):
            if not bloque.fecha:
                continue
            texto = noches._texto_bloque(bloque.crudo)
            por_mes[bloque.fecha[:7]][bloque.id] = {
                "via": "cache_paginas",
                "pagina": ruta.name,
                "id": bloque.id,
                "fecha": bloque.fecha,
                "texto": texto,
                "crudo": bloque.crudo,
            }
    carpeta = datos / "kpszsu" / "historico"
    carpeta.mkdir(parents=True, exist_ok=True)
    escritos = {}
    for mes, publicaciones in sorted(por_mes.items()):
        existentes: set[int] = set()
        ficheros = sorted(carpeta.glob(f"kpszsu-historico-{mes}*.jsonl.gz"))
        for fichero in ficheros:
            with gzip.open(fichero, "rt", encoding="utf-8") as f:
                existentes |= {int(json.loads(x)["id"]) for x in f if x.strip()}
        nuevas = [publicaciones[i] for i in sorted(publicaciones) if i not in existentes]
        if not nuevas:
            continue
        nombre = (
            f"kpszsu-historico-{mes}.jsonl.gz"
            if not ficheros
            else f"kpszsu-historico-{mes}.parte{len(ficheros) + 1}.jsonl.gz"
        )
        _escribir_gz(
            carpeta / nombre, "".join(json.dumps(p, ensure_ascii=False) + "\n" for p in nuevas)
        )
        escritos[mes] = len(nuevas)
    return escritos


def copiar_historico(datos: Path) -> dict[str, int]:
    """Sube a la copia privada del archivo (bucket droneobservatory-archivo) los ficheros del
    histórico que no estén ya; nunca sobrescribe uno con otra huella."""
    from collections import Counter

    from recogida import seguimiento_archivo as archivo

    credenciales = archivo.Credenciales.del_entorno()
    if credenciales is None:
        return {"sin_credenciales": 1}
    copia = archivo.Copia(archivo.cargar_destino(), credenciales)
    resultado: Counter[str] = Counter()
    for ruta in sorted((datos / "kpszsu" / "historico").glob("*.jsonl.gz")):
        relativa = str(ruta.relative_to(datos)).replace(os.sep, "/")
        resultado[
            copia.subir(copia.destino.prefijo + relativa, ruta.read_bytes(), "application/gzip")
        ] += 1
    return dict(resultado)


# --- Noches ----------------------------------------------------------------------------------


def ruta_noche(salida: Path, noche: str) -> Path:
    return salida / "noches" / f"{noche}.json.gz"


def estructurar(
    seguimiento_datos: Path, salida: Path, todo: bool, ahora: datetime, tope_s: float = 1500.0
) -> dict[str, Any]:
    """Cada noche a su fichero, de una en una (la memoria no crece con el archivo)."""
    inicio = time.monotonic()
    recientes = {noches.noche_de(ahora - timedelta(days=d)) for d in range(3)}
    hechas = cuentas = 0
    mensajes = avisos = pistas = 0
    for noche in noches.noches_del_archivo(seguimiento_datos):
        destino = ruta_noche(salida, noche)
        if destino.exists() and not todo and noche not in recientes:
            continue
        if time.monotonic() - inicio > tope_s:
            registro.warning("rutas: tope de tiempo, el resto en la siguiente ejecución")
            break
        documento = noches.estructurar(seguimiento_datos, noche)
        _escribir_gz(destino, json.dumps(documento, ensure_ascii=False, sort_keys=True))
        hechas += 1
        mensajes += len(documento["kpszsu"])
        avisos += sum(len(m["avisos"]) for m in documento["kpszsu"])
        pistas += len(documento["neptun"]["pistas"])
        cuentas += 1
    return {"noches": hechas, "mensajes": mensajes, "avisos": avisos, "pistas_neptun": pistas}


# --- Cálculo y publicación ----------------------------------------------------------------------

ATAQUES = "ataques.json"
COMPROBACION = "comprobacion.json"
ESTADISTICAS = "estadisticas.jsonl"
SUBIDOS = "subidos.json"
PREFIJO = "rutas"
CACHE_INDICE = "public, max-age=300"
CACHE_NOCHE = "public, max-age=3600"

Subir = Callable[[str, bytes, str, str], bool]


def frontera_km(lat: float, lon: float) -> float:
    """Distancia a Rusia o Bielorrusia o al mar Negro: dónde puede empezar una ruta."""
    from proceso.deduccion import geo
    from proceso.rutas import geometria

    return min(
        geo.distancia_a_pais_km("RU", lat, lon),
        geo.distancia_a_pais_km("BY", lat, lon),
        geometria.distancia_km(lat, lon, 45.8, 31.2) - 90.0,
    )


def subida() -> Subir | None:
    """Subida al almacén público, comprimida (Content-Encoding: gzip): una noche pasa de unos
    300 KB a unos 60 KB, y la subcapa aparece antes en el teléfono."""
    from recogida import almacen_publico

    almacen = almacen_publico.cargar()
    clave_id = os.environ.get(almacen_publico.VARIABLE_ID, "")
    secreto = os.environ.get(almacen_publico.VARIABLE_SECRETO, "")

    def subir(objeto: str, cuerpo: bytes, tipo: str, cache: str) -> bool:
        if not clave_id or not secreto:
            registro.warning("sin credenciales del almacén: no se sube %s", objeto)
            return False
        correcto, motivo = almacen_publico.subir(
            almacen, objeto, gzip.compress(cuerpo, mtime=0), clave_id, secreto, tipo, cache,
            codificacion="gzip",
        )  # fmt: skip
        if not correcto:
            registro.warning("%s: %s", objeto, motivo)
        return correcto

    return subir


def _leer_noche(ruta: Path) -> dict[str, Any]:
    datos: dict[str, Any] = json.loads(gzip.decompress(ruta.read_bytes()))
    return datos


def _texto(documento: Any) -> str:
    return json.dumps(documento, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def calcular(salida: Path, ahora: datetime, subir: Subir | None) -> dict[str, Any]:
    """Comprobación, noches publicables, índice y estadísticas; sube al almacén lo que cambia."""
    from proceso.rutas import calculo, esquema, neptun

    ataques: dict[str, Any] = (
        json.loads((salida / ATAQUES).read_text(encoding="utf-8"))
        if (salida / ATAQUES).exists()
        else {}
    )
    rutas_noches = sorted((salida / "noches").glob("*.json.gz"))
    comprobadas = []
    for ruta in rutas_noches:
        noche = _leer_noche(ruta)
        if calculo.con_neptun(noche):
            comprobadas.append(
                calculo.comprobar_noche(noche, ataques.get(noche["noche"], {}), frontera_km)
            )
    resumen = calculo.resumen_comprobacion([c for c in comprobadas if c is not None])
    resumen["calculado"] = ahora.strftime("%Y-%m-%dT%H:%MZ")
    (salida / COMPROBACION).write_text(_texto(resumen), encoding="utf-8")
    publicar = salida / "publicar" / "noches"
    publicar.mkdir(parents=True, exist_ok=True)
    indice: list[dict[str, Any]] = []
    estadisticas: list[dict[str, Any]] = []
    for ruta in rutas_noches:
        noche = _leer_noche(ruta)
        if not calculo.cerrada(noche, ahora):
            continue
        ataque = ataques.get(noche["noche"], {})
        documento = calculo.noche_publica(noche, ataque, frontera_km, bool(resumen["pasa"]))
        if documento is None:
            continue
        esquema.validar("noche", documento)
        (publicar / f"{noche['noche']}.json").write_text(_texto(documento), encoding="utf-8")
        indice.append(calculo.resumen_noche(documento, ataque))
        for grupo in documento["grupos"]:
            estadisticas.append({"noche": noche["noche"], **grupo})
    # Lo que ya no se publica (una noche cuya fuente dejó de pasar la comprobación) se quita de la
    # carpeta: el índice no lo nombra y la subida lo retira del almacén.
    vigentes = {f"{n['noche']}.json" for n in indice}
    for fichero in publicar.glob("*.json"):
        if fichero.name not in vigentes:
            fichero.unlink()
    documento_indice = {
        "version": calculo.VERSION,
        "generado": ahora.strftime("%Y-%m-%dT%H:%MZ"),
        "comprobacion": {
            k: resumen[k]
            for k in ("pasa", "mediana_reconstruccion_km", "mediana_recta_km", "puntos", "criterio")
        },
        "noches_con_mensajes": len(rutas_noches),
        "noches": indice,
        "atribucion_neptun": dict(neptun.ATRIBUCION),
    }
    esquema.validar("indice", documento_indice)
    (salida / "publicar" / "indice.json").write_text(_texto(documento_indice), encoding="utf-8")
    (salida / ESTADISTICAS).write_text(
        "".join(_texto(e) + "\n" for e in estadisticas), encoding="utf-8"
    )
    subidos = _subir_cambios(salida, subir, retirada())
    return {
        "noches_publicadas": len(indice),
        "comprobacion_pasa": resumen["pasa"],
        "noches_comprobadas": len(resumen["noches"]),
        "subidos": subidos,
    }


def retirada() -> Callable[[str], bool] | None:
    from recogida import satelite

    return satelite.borrado_del_almacen(os.environ)


AJUSTE_WEB = Path(__file__).resolve().parent.parent / "configuracion" / "rutas_en_la_web.json"


def en_la_web() -> bool:
    """El interruptor de las rutas en la web (configuracion/rutas_en_la_web.json): apagado, las
    rutas se calculan y se guardan igual, pero no se publican en el almacén público."""
    return bool(json.loads(AJUSTE_WEB.read_text(encoding="utf-8"))["mostrar"])


def _subir_cambios(
    salida: Path,
    subir: Subir | None,
    borrar: Callable[[str], bool] | None = None,
    publicar: bool | None = None,
) -> int:
    """Sube al almacén lo que ha cambiado desde la última subida (por su huella) y retira lo que
    ya no se publica. Con las rutas apagadas en la web no sube nada y retira del almacén público
    todo lo subido antes (las noches siguen en datos/rutas/publicar); al encenderlas, como el
    registro de subidas queda vacío, se vuelve a subir todo."""
    import hashlib

    registro_subidos = salida / SUBIDOS
    previos: dict[str, str] = (
        json.loads(registro_subidos.read_text(encoding="utf-8"))
        if registro_subidos.exists()
        else {}
    )
    if not (en_la_web() if publicar is None else publicar):
        for objeto in sorted(previos):
            if borrar is not None and borrar(objeto):
                del previos[objeto]
        registro_subidos.write_text(_texto(previos), encoding="utf-8")
        if previos:
            registro.warning("rutas apagadas en la web: sin retirar %s", ", ".join(previos))
        return 0
    if subir is None:
        return 0
    ficheros = sorted((salida / "publicar" / "noches").glob("*.json"))
    ficheros.append(salida / "publicar" / "indice.json")
    hechos = 0
    for fichero in ficheros:
        cuerpo = fichero.read_bytes()
        huella = hashlib.sha256(cuerpo).hexdigest()
        objeto = (
            f"{PREFIJO}/indice.json"
            if fichero.name == "indice.json"
            else f"{PREFIJO}/noches/{fichero.name}"
        )
        if previos.get(objeto) == huella:
            continue
        cache = CACHE_INDICE if fichero.name == "indice.json" else CACHE_NOCHE
        if subir(objeto, cuerpo, "application/json", cache):
            previos[objeto] = huella
            hechos += 1
    vigentes = {
        f"{PREFIJO}/noches/{f.name}" for f in (salida / "publicar" / "noches").glob("*.json")
    } | {f"{PREFIJO}/indice.json"}
    for objeto in sorted(set(previos) - vigentes):
        if borrar is not None and borrar(objeto):
            del previos[objeto]
    registro_subidos.write_text(_texto(previos), encoding="utf-8")
    return hechos


# --- Paso de la recogida horaria -----------------------------------------------------------------


def ataques_por_noche(almacen: Any) -> dict[str, Any]:
    """Para el cálculo de las rutas, sin cargar la base: por noche, los ataques rusos de esa
    noche, sus zonas de lanzamiento, lo lanzado y los puntos de sus impactos."""
    from proceso import ataques as ataques_

    por_noche: dict[str, Any] = {}
    noche_de_ataque: dict[str, str] = {}
    for ataque in almacen.ataques_ucrania():
        if ataque.get("sentido") != "RU_UA" or "periodo" not in ataque:
            continue
        jornada = ataques_.jornada(ataque["periodo"])
        noche = jornada["desde"]
        entrada = por_noche.setdefault(
            noche, {"ataques": [], "zonas": [], "lanzados": None, "impactos": []}
        )
        entrada["ataques"].append(ataque["id"])
        for zona in ataque.get("zonas_lanzamiento", []):
            if zona not in entrada["zonas"]:
                entrada["zonas"].append(zona)
        total = (ataque.get("lanzados") or {}).get("total")
        if isinstance(total, dict) and isinstance(total.get("max"), int):
            entrada["lanzados"] = max(entrada["lanzados"] or 0, total["max"])
        noche_de_ataque[ataque["id"]] = noche
    for impacto in almacen.impactos_guerra():
        noche = noche_de_ataque.get(str(impacto.get("ataque", "")))
        punto = (impacto.get("lugar") or {}).get("punto")
        if noche is None or not punto or impacto.get("retirado"):
            continue
        por_noche[noche]["impactos"].append([punto["lat"], punto["lon"]])
    # Incidentes europeos de frontera de cada noche, para enlazarlos con las rutas que acaban
    # en ellos (sin crear incidentes nuevos).
    for incidente in almacen.incidentes():
        if incidente.get("retirado") or incidente.get("fusionado_en"):
            continue
        punto = (incidente.get("lugar") or {}).get("punto")
        inicio = ((incidente.get("tiempo") or {}).get("inicio") or {}).get("valor")
        if not punto or not inicio or (incidente.get("zona") or {}).get("grupo") != "frontera":
            continue
        noche = noches.noche_de(datetime.fromisoformat(str(inicio).replace("Z", "+00:00")))
        if noche in por_noche:
            por_noche[noche].setdefault("incidentes", []).append(
                {"id": incidente["id"], "lat": punto["lat"], "lon": punto["lon"]}
            )
    for entrada in por_noche.values():
        entrada["ataques"].sort()
        entrada.setdefault("incidentes", []).sort(key=lambda x: x["id"])
    return por_noche


def paso_horario(almacen: Any) -> None:
    """En la recogida horaria: deja los ataques de cada noche para el cálculo de las rutas.
    Nada de lo que falle aquí sale de esta función."""
    try:
        salida = datos_rutas()
        salida.mkdir(parents=True, exist_ok=True)
        texto = _texto(ataques_por_noche(almacen))
        ruta = salida / ATAQUES
        if not ruta.exists() or ruta.read_text(encoding="utf-8") != texto:
            temporal = ruta.with_suffix(".tmp")
            temporal.write_text(texto, encoding="utf-8")
            temporal.replace(ruta)
        registro.info("rutas: ataques por noche al día")
    except Exception as error:
        registro.warning("rutas: ataques por noche sin escribir: %s", str(error)[:300])


def principal(argumentos: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    analizador = argparse.ArgumentParser(prog="recogida.rutas")
    ordenes = analizador.add_subparsers(dest="orden", required=True)
    importar = ordenes.add_parser("importar-historico")
    importar.add_argument("--cache", type=Path, required=True)
    estructura = ordenes.add_parser("estructurar")
    estructura.add_argument("--todo", action="store_true")
    ordenes.add_parser("calcular")
    args = analizador.parse_args(argumentos)
    ahora = datetime.now(UTC)
    if args.orden == "importar-historico":
        registro.info(
            "histórico importado: %s", importar_historico(args.cache, datos_seguimiento())
        )
        registro.info("histórico en la copia privada: %s", copiar_historico(datos_seguimiento()))
        return 0
    if args.orden == "estructurar":
        registro.info(
            "noches estructuradas: %s",
            estructurar(datos_seguimiento(), datos_rutas(), args.todo, ahora),
        )
        return 0
    registro.info("rutas: %s", calcular(datos_rutas(), ahora, subida()))
    return 0


if __name__ == "__main__":
    sys.exit(principal())
