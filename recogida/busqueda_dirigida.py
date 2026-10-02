"""Búsqueda dirigida de noticias para los cierres medidos sin incidente.

Cuando el tráfico aéreo mide en un aeropuerto con cobertura alta una interrupción que no casa
con ningún incidente y que no explica el tiempo (anomalía candidata, `proceso/trafico.py`), se
buscan en los ficheros GKG de GDELT de ese día y del siguiente las noticias que nombran el
aeropuerto o su ciudad (también con sus nombres en otros idiomas: «Lüttich», «Luik», «Lieja»)
junto a una palabra de dron, aunque no traigan la señal de incidente que pide el filtro general
ni una instalación que el nomenclátor reconozca («Drohnen über Lüttich»). Lo que aparece entra
como artículo del aeropuerto por el flujo normal (deduplicado, candidato, extractor); si no
aparece nada, la anomalía sigue interna, como hasta ahora. Se buscan también los documentos
oficiales guardados (`recogida/detalle.py`) que citan un suceso en ese aeropuerto esos días.

En dos tiempos, como las fuentes oficiales de detalle:

1. **Lectura** (`servidor/busqueda.sh`, temporizador propio, sin tocar la base): lee
   `anomalias.json`, que deja la recogida horaria con las anomalías por buscar; descarga los
   GKG de cada día que aún no tiene y guarda todos los titulares con dron de ese día
   (`dias/AAAA-MM-DD.jsonl.gz`), para no volver a bajarlos para otra anomalía; deja lo hallado
   de cada anomalía en `hallados/<anomalía>.json`.
2. **Incorporación** (recogida horaria, o la revisión de `recogida/calidad.py`): guarda los
   hallados como artículos del aeropuerto, los agrupa y anota cada anomalía como buscada
   (cursor `busqueda_dirigida`, con lo que se halló).

Uso:
    python -m recogida.busqueda_dirigida buscar --datos <dir> [--tope-min 50]
    python -m recogida.busqueda_dirigida pendientes --datos <dir> [--base <db.age>]
        [--repositorio <url del repositorio de datos>]
"""

import argparse
import gzip
import json
import logging
import os
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from almacen.base import Almacen
from esquema import Documento
from proceso.noticias import (
    Articulo,
    Nomenclator,
    _mayusculas,
    nomenclator,
    normalizar,
    titular_normalizado,
)
from proceso.ubicacion import nombres_en_idiomas
from recogida import gdelt
from recogida.descarga import DescargaFallida
from recogida.plazo import Plazo, TiempoAgotado

registro = logging.getLogger("recogida")

FUENTE_ID = "busqueda_dirigida"
ANOMALIAS = "anomalias.json"
DIAS = "dias"
HALLADOS = "hallados"
DIRECTORIO_POR_DEFECTO = Path("/home/eodi/datos/busqueda")
VARIABLE_DATOS = "EODI_BUSQUEDA_DATOS"
VERSION = "1.0.0"
# Solo las anomalías de un aeropuerto con cobertura alta: con media, un hueco puede ser de los
# receptores y no del tráfico.
COBERTURA = "alta"
# El día de la anomalía y el siguiente: la noticia de un cierre de la tarde sale esa noche o a
# la mañana siguiente.
DIAS_BUSQUEDA = 2
FRANJAS_DIA = 96
# Una localidad del nomenclátor es la ciudad del aeropuerto si se llama como una de sus
# ciudades y está a 30 km o menos: así entran sus nombres en otros idiomas.
RADIO_CIUDAD_KM = 30.0
MIN_LETRAS_NOMBRE = 4
# Tiempo de la incorporación en la recogida horaria: solo lee ficheros pequeños.
TOPE_S = 60.0


def directorio_datos() -> Path:
    return Path(os.environ.get(VARIABLE_DATOS, DIRECTORIO_POR_DEFECTO))


# --- Qué se busca ---------------------------------------------------------------------


def elegibles(almacen: Almacen) -> list[Documento]:
    """Anomalías candidatas de un aeropuerto con cobertura alta, sin mal tiempo, sin incidente
    y sin buscar todavía (con esta versión de la búsqueda)."""
    buscadas = (almacen.cursor(FUENTE_ID) or {}).get("anomalias", {})
    resultado = []
    for anomalia in almacen.anomalias():
        id_ = identificador(anomalia)
        if (
            anomalia["estado"] == "candidata"
            and anomalia.get("cobertura", {}).get("nivel") == COBERTURA
            and not anomalia.get("motivos_meteorologicos")
            and buscadas.get(id_, {}).get("version") != VERSION
        ):
            resultado.append(anomalia)
    return resultado


def identificador(anomalia: Documento) -> str:
    return f"{anomalia['oaci']}/{anomalia['inicio']}"


def nombre_fichero(id_: str) -> str:
    return id_.replace("/", "_").replace(":", "") + ".json"


def dias_de(anomalia: Documento) -> list[date]:
    primero = date.fromisoformat(anomalia["inicio"][:10])
    return [primero + timedelta(days=n) for n in range(DIAS_BUSQUEDA)]


def nombres(oaci: str, nom: Nomenclator) -> set[str]:
    """Los nombres del aeropuerto y de su ciudad, en todos sus idiomas."""
    return nombres_en_idiomas(oaci, nom)


def nombra(titular: str, nombres_: set[str]) -> bool:
    """El titular nombra alguno: un nombre de una sola palabra, con mayúscula («Leck» es un
    nombre de Lieja en GeoNames; «leck», una fuga en alemán)."""
    texto = f" {normalizar(titular)} "
    mayusculas = _mayusculas(titular)
    return any(f" {n} " in texto and (" " in n or n in mayusculas) for n in nombres_)


# --- Lectura (temporizador, sin la base) ------------------------------------------------


def _documento(a: Articulo) -> Documento:
    return {**gdelt.documento_articulo(a), "titular_normalizado": titular_normalizado(a.titular)}


def leer_dia(
    dia: date, leer_franja: Callable[[datetime], list[Articulo]], plazo: Plazo | None = None
) -> list[Documento]:
    """Todos los titulares con dron del día, de sus 96 franjas y los dos flujos."""
    encontrados: list[Documento] = []
    inicio = datetime.combine(dia, datetime.min.time(), UTC)
    for n in range(FRANJAS_DIA):
        if plazo is not None:
            plazo.comprobar()
        encontrados += [_documento(a) for a in leer_franja(inicio + gdelt.FRANJA * n)]
    return encontrados


def _ruta_dia(datos: Path, dia: date) -> Path:
    return datos / DIAS / f"{dia.isoformat()}.jsonl.gz"


def guardar_dia(datos: Path, dia: date, documentos: list[Documento]) -> None:
    ruta = _ruta_dia(datos, dia)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    temporal = ruta.with_suffix(".tmp")
    lineas = "".join(json.dumps(d, ensure_ascii=False, sort_keys=True) + "\n" for d in documentos)
    temporal.write_bytes(gzip.compress(lineas.encode("utf-8")))
    temporal.replace(ruta)


def cargar_dia(datos: Path, dia: date) -> list[Documento] | None:
    ruta = _ruta_dia(datos, dia)
    if not ruta.exists():
        return None
    texto = gzip.decompress(ruta.read_bytes()).decode("utf-8")
    return [json.loads(linea) for linea in texto.splitlines() if linea]


def hallados_de(
    anomalia: Documento, titulares: list[Documento], nom: Nomenclator
) -> list[Documento]:
    """Los titulares con dron de esos días que nombran el aeropuerto o su ciudad."""
    nombres_ = nombres(anomalia["oaci"], nom)
    primero = dias_de(anomalia)[0]
    hasta = primero + timedelta(days=DIAS_BUSQUEDA)
    return sorted(
        (d for d in titulares
         if primero.isoformat() <= d["fecha"][:10] < hasta.isoformat()
         and nombra(d["titular"], nombres_)),
        key=lambda d: (d["fecha"], d["url"]),
    )  # fmt: skip


def buscar(
    datos: Path,
    leer_franja: Callable[[datetime], list[Articulo]],
    plazo: Plazo | None = None,
    nom: Nomenclator | None = None,
) -> dict[str, int]:
    """Lee los días que faltan de las anomalías de anomalias.json y deja lo hallado. Se para
    al agotar el plazo; lo que falte sigue en la ejecución siguiente."""
    nom = nom or nomenclator()
    ruta = datos / ANOMALIAS
    anomalias = json.loads(ruta.read_text(encoding="utf-8"))["anomalias"] if ruta.exists() else []
    recuentos = {"anomalias": 0, "dias_leidos": 0, "con_noticias": 0}
    for anomalia in anomalias:
        destino = datos / HALLADOS / nombre_fichero(identificador(anomalia))
        if destino.exists():
            continue
        titulares: list[Documento] = []
        try:
            for dia in dias_de(anomalia):
                cargados = cargar_dia(datos, dia)
                if cargados is None:
                    cargados = leer_dia(dia, leer_franja, plazo)
                    guardar_dia(datos, dia, cargados)
                    recuentos["dias_leidos"] += 1
                titulares += cargados
        except (TiempoAgotado, DescargaFallida, gdelt.FranjaPendiente) as error:
            registro.info("búsqueda dirigida parada: %s", type(error).__name__)
            break
        hallados = hallados_de(anomalia, titulares, nom)
        destino.parent.mkdir(parents=True, exist_ok=True)
        temporal = destino.with_suffix(".tmp")
        temporal.write_text(
            json.dumps({"anomalia": anomalia, "version": VERSION, "articulos": hallados},
                       ensure_ascii=False, indent=1),
            encoding="utf-8",
        )  # fmt: skip
        temporal.replace(destino)
        recuentos["anomalias"] += 1
        recuentos["con_noticias"] += bool(hallados)
    return recuentos


def escribir_pendientes(almacen: Almacen, datos: Path) -> int:
    """Deja en anomalias.json las anomalías por buscar (lo hace la recogida horaria)."""
    anomalias = elegibles(almacen)
    datos.mkdir(parents=True, exist_ok=True)
    temporal = datos / (ANOMALIAS + ".tmp")
    temporal.write_text(
        json.dumps({"anomalias": anomalias}, ensure_ascii=False, sort_keys=True), encoding="utf-8"
    )
    temporal.replace(datos / ANOMALIAS)
    return len(anomalias)


# --- Incorporación (con la base) ----------------------------------------------------------


@dataclass
class Incorporacion:
    anomalias: int = 0
    con_noticias: int = 0
    articulos: int = 0
    candidatos: list[str] = field(default_factory=list)
    oficiales: int = 0

    def texto(self) -> str:
        return (
            f"anomalías buscadas={self.anomalias} con noticias={self.con_noticias} "
            f"artículos={self.articulos} candidatos={len(set(self.candidatos))} "
            f"documentos oficiales={self.oficiales}"
        )


def oficiales_de(almacen: Almacen, anomalia: Documento) -> list[str]:
    """Documentos oficiales guardados con un suceso de esos días en ese aeropuerto."""
    nom = nomenclator()
    nombres_ = nombres(anomalia["oaci"], nom)
    dias = {d.isoformat() for d in dias_de(anomalia)}
    encontrados = []
    for documento in almacen.documentos_oficiales():
        for suceso in documento.get("sucesos", []):
            datos = suceso.get("datos", {})
            inicio = str(datos.get("inicio", {}).get("valor", ""))[:10]
            lugar = json.dumps(datos.get("lugar_suceso", {}).get("valor", ""), ensure_ascii=False)
            if inicio in dias and nombra(lugar, nombres_):
                encontrados.append(documento["id"])
    return sorted(set(encontrados))


def incorporar(
    almacen: Almacen, datos: Path, ahora: datetime, plazo: Plazo | None = None
) -> Incorporacion:
    """Guarda como artículos del aeropuerto lo hallado y anota cada anomalía como buscada."""
    from recogida.calidad import situar_en_candidatos

    resultado = Incorporacion()
    cursor = almacen.cursor(FUENTE_ID) or {"anomalias": {}}
    directorio = datos / HALLADOS
    for ruta in sorted(directorio.glob("*.json")) if directorio.exists() else []:
        if plazo is not None:
            plazo.comprobar()
        hallado = json.loads(ruta.read_text(encoding="utf-8"))
        anomalia = hallado["anomalia"]
        id_ = identificador(anomalia)
        if cursor["anomalias"].get(id_, {}).get("version") == hallado["version"]:
            continue
        nuevos: list[Documento] = []
        for documento in hallado["articulos"]:
            documento = {**documento, "lugares": [anomalia["oaci"]]}
            if almacen.guardar_articulo(documento):
                nuevos.append(documento)
            else:
                existente = almacen.articulos_de([documento["url"]])
                if existente and not existente[0]["candidato"]:
                    nuevos.append({**existente[0], "lugares": [anomalia["oaci"]]})
        candidatos = situar_en_candidatos(
            almacen, [(d, [anomalia["oaci"]]) for d in nuevos], MOTIVO
        )
        oficiales = oficiales_de(almacen, anomalia)
        cursor["anomalias"][id_] = {
            "version": hallado["version"], "buscada": ahora.strftime("%Y-%m-%dT%H:%MZ"),
            "articulos": len(hallado["articulos"]), "nuevos": len(nuevos),
            "candidatos": sorted(set(candidatos)), "oficiales": oficiales,
        }  # fmt: skip
        resultado.anomalias += 1
        resultado.con_noticias += bool(hallado["articulos"])
        resultado.articulos += len(nuevos)
        resultado.candidatos += candidatos
        resultado.oficiales += len(oficiales)
    almacen.guardar_cursor(FUENTE_ID, cursor)
    return resultado


MOTIVO = (
    "búsqueda dirigida: noticia con el nombre del aeropuerto o de su ciudad y una palabra de "
    "dron, el día de una interrupción medida sin incidente o el siguiente"
)


def paso_horario(almacen: Almacen, ahora: datetime) -> Incorporacion:
    """En la recogida horaria: incorpora lo hallado y deja la lista de lo que falta buscar."""
    datos = directorio_datos()
    resultado = incorporar(almacen, datos, ahora, Plazo(TOPE_S))
    escribir_pendientes(almacen, datos)
    return resultado


# --- Órdenes ------------------------------------------------------------------------------


def _lector(plazo: Plazo) -> Callable[[datetime], list[Articulo]]:
    descargador = gdelt.descargador(plazo)
    ahora = datetime.now(UTC)

    def leer(franja: datetime) -> list[Articulo]:
        encontrados, _ = gdelt.leer_franja(descargador, franja, ahora)
        return encontrados

    return leer


def principal(argumentos: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
    opciones = argparse.ArgumentParser(description=__doc__)
    ordenes = opciones.add_subparsers(dest="orden", required=True)
    o_buscar = ordenes.add_parser("buscar")
    o_buscar.add_argument("--datos", type=Path, default=directorio_datos())
    o_buscar.add_argument("--tope-min", type=float, default=50.0)
    o_pendientes = ordenes.add_parser("pendientes")
    o_pendientes.add_argument("--datos", type=Path, default=directorio_datos())
    o_pendientes.add_argument("--base", type=Path, help="base cifrada local; si no, la remota")
    o_pendientes.add_argument(
        "--repositorio", help="repositorio de datos (por defecto, el público)"
    )
    args = opciones.parse_args(argumentos)
    if args.orden == "buscar":
        inicio = time.monotonic()
        plazo = Plazo(args.tope_min * 60)
        recuentos = buscar(args.datos, _lector(plazo), plazo)
        registro.info("búsqueda dirigida: %s en %.0f s", recuentos, time.monotonic() - inicio)
        return 0
    return _pendientes(args.datos, args.base, args.repositorio)


def _pendientes(datos: Path, base: Path | None, repositorio: str | None = None) -> int:
    """Escribe anomalias.json desde la base (para la primera búsqueda, sin esperar a la
    recogida horaria). Solo lee la base."""
    from tempfile import TemporaryDirectory

    from almacen import remoto
    from almacen.cifrado import abrir_cifrada, cargar_clave_local

    cargar_clave_local()
    with TemporaryDirectory() as temporal:
        ruta = base or Path(temporal) / remoto.FICHERO
        if base is None and not remoto.descargar(ruta, repositorio or remoto.REPOSITORIO):
            registro.error("no hay base en la rama %s", remoto.RAMA)
            return 1
        almacen = Almacen(abrir_cifrada(ruta))
        registro.info("anomalías por buscar: %d", escribir_pendientes(almacen, datos))
    return 0


if __name__ == "__main__":
    sys.exit(principal())
