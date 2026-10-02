"""Motor de deducción en el servidor: cálculo con su propio temporizador e incorporación a la base
en la recogida horaria.

**Cálculo** (`python -m recogida.deduccion calcular`, lo lanza `servidor/deduccion.sh` con su
propio cerrojo): descarga la base de la rama estado (solo la lee: no toma el cerrojo de la
recogida horaria, y un clon es atómico, así que como mucho lee la versión anterior), arma cada
caso (incidentes europeos vigentes, impactos con lugar de la capa de guerra que no son partes
diarios ni FPV de la línea del frente, y ataques) y lo evalúa con el motor
(`proceso/deduccion/motor.py`). Es incremental: cada caso lleva una huella de lo que usa (sus
datos, la versión del motor, de cada regla, del catálogo y de las zonas); si no cambia, se
conserva el resultado anterior. Al subir la versión de una regla o del catálogo cambian todas
las huellas y se recalcula todo. Deja en `<datos>/` (`EODI_DEDUCCION_DATOS`):

- `resultados.jsonl.gz`: un resultado por línea ({"id", "tipo", "huella", "deduccion"});
- `control.json`: la última ejecución correcta, sus recuentos y su duración;
- `dem/`: las teselas de Copernicus DEM GLO-90 del horizonte de radar (`recogida/dem.py`).

y, si termina bien, la hora en el registro (`--registro`), de donde estado.json saca
`ultima_deduccion`.

**Incorporación** (`incorporar`, en la recogida horaria, que ya tiene su cerrojo): guarda en la
tabla `deducciones` lo que ha cambiado, en segundos. Un fallo no cambia el resultado de la
recogida: queda en el registro.

El horizonte de radar se calcula para los incidentes con punto en una instalación (aeropuerto,
base, central...): el relieve de 30 km alrededor, con un tope de teselas nuevas por ejecución.
"""

import argparse
import gzip
import json
import logging
import os
import sys
import time
import urllib.error
import urllib.request
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from almacen.base import Almacen
from proceso import impactos_guerra
from proceso.deduccion import catalogo as catalogo_
from proceso.deduccion import horizonte, motor, validacion
from recogida import dem
from recogida.descarga import AGENTE_EODI

registro = logging.getLogger("recogida.deduccion")

VARIABLE_DATOS = "EODI_DEDUCCION_DATOS"
DATOS = Path.home() / "datos" / "deduccion"
RESULTADOS = "resultados.jsonl.gz"
# Cursor de la base con el resumen de la validación (lo lee la exportación).
CURSOR = "deduccion"
CONTROL = "control.json"
HORIZONTES = "horizontes.json"
VALIDACION = "validacion.json"
# Llamadas a Open-Meteo por ejecución para la validación (se guardan en la caché común).
TOPE_METEO = 100
# Teselas nuevas del relieve por ejecución: unas 2 MB y 2 s cada una.
TESELAS_POR_EJECUCION = 150
# Tiempo de la incorporación en la recogida horaria.
TOPE_INCORPORAR_S = 120.0


def directorio_datos() -> Path:
    return Path(os.environ.get(VARIABLE_DATOS) or DATOS)


def _instante(momento: datetime) -> str:
    return momento.astimezone(UTC).strftime("%Y-%m-%dT%H:%MZ")


def descargar_url(url: str) -> bytes | None:
    """Tesela del relieve; None si no existe (mar abierto)."""
    peticion = urllib.request.Request(url, headers={"User-Agent": AGENTE_EODI})
    try:
        with urllib.request.urlopen(peticion, timeout=60) as respuesta:
            datos: bytes = respuesta.read()
            return datos
    except urllib.error.HTTPError as error:
        if error.code in (403, 404):
            return None
        raise


def leer_resultados(datos: Path) -> dict[str, dict[str, Any]]:
    ruta = datos / RESULTADOS
    if not ruta.exists():
        return {}
    resultado = {}
    with gzip.open(ruta, "rt", encoding="utf-8") as fichero:
        for linea in fichero:
            if linea.strip():
                registro_ = json.loads(linea)
                resultado[registro_["id"]] = registro_
    return resultado


def escribir_resultados(datos: Path, resultados: dict[str, dict[str, Any]]) -> None:
    datos.mkdir(parents=True, exist_ok=True)
    temporal = datos / (RESULTADOS + ".tmp")
    with gzip.open(temporal, "wt", encoding="utf-8", newline="\n") as fichero:
        for id_ in sorted(resultados):
            fichero.write(json.dumps(resultados[id_], ensure_ascii=False, sort_keys=True) + "\n")
    temporal.replace(datos / RESULTADOS)


def escribir_json(ruta: Path, contenido: Any) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    temporal = ruta.with_suffix(ruta.suffix + ".tmp")
    with open(temporal, "w", encoding="utf-8", newline="\n") as fichero:
        fichero.write(json.dumps(contenido, ensure_ascii=False, indent=1, sort_keys=True) + "\n")
    temporal.replace(ruta)


def con_radar(incidente: dict[str, Any]) -> bool:
    """El horizonte de radar se calcula en las instalaciones (donde puede haber un radar)."""
    lugar = incidente.get("lugar", {})
    return lugar.get("nivel") == "instalacion" and bool(lugar.get("punto"))


def calcular(
    almacen: Almacen,
    datos: Path,
    ahora: datetime,
    todo: bool = False,
    relieve: dem.Relieve | None = None,
    meteo: validacion.Meteo | None = None,
) -> dict[str, Any]:
    """Evalúa lo nuevo o cambiado y reescribe los resultados. Devuelve el resumen."""
    inicio = time.monotonic()
    catalogo = catalogo_.cargar()
    anteriores = {} if todo else leer_resultados(datos)
    relieve = relieve or dem.Relieve(datos / "dem", descargar_url, TESELAS_POR_EJECUCION)
    condiciones = almacen.condiciones()
    trafico = almacen.trafico_aereo()
    evaluado = motor.instante(ahora)
    resultados: dict[str, dict[str, Any]] = {}
    cuentas: Counter[str] = Counter()

    def guardar(id_: str, tipo: str, huella: str, calcula: Any) -> dict[str, Any]:
        previo = anteriores.get(id_)
        if previo is not None and previo.get("huella") == huella:
            resultados[id_] = previo
            cuentas[f"{tipo}_sin_cambios"] += 1
            return dict(previo["deduccion"])
        documento = calcula()
        documento["huella"] = huella
        documento["evaluado"] = evaluado
        resultados[id_] = {"id": id_, "tipo": tipo, "huella": huella, "deduccion": documento}
        cuentas[f"{tipo}_calculados"] += 1
        return dict(documento)

    incidentes = [
        d for d in almacen.incidentes() if "fusionado_en" not in d and "retirado" not in d
    ]
    casos = {
        d["id"]: motor.caso_de_incidente(
            d, condiciones.get(d["id"]), trafico.get(d["id"]), almacen.encuentros_de(d["id"])
        )
        for d in incidentes
    }
    sitios = motor.sitios_de(casos.values())
    # El horizonte de cada punto no cambia con el incidente: se guarda aparte y se reutiliza.
    horizontes: dict[str, Any] = (
        json.loads((datos / HORIZONTES).read_text(encoding="utf-8"))
        if (datos / HORIZONTES).exists()
        else {}
    )

    def horizonte_de(lat: float, lon: float) -> dict[str, Any] | None:
        clave = f"{lat:.5f},{lon:.5f}"
        if clave not in horizontes:
            calculado = horizonte.calcular(relieve, lat, lon)
            if calculado is None:
                return None
            horizontes[clave] = calculado
        resultado: dict[str, Any] = horizontes[clave]
        return resultado

    for documento in incidentes:
        caso = casos[documento["id"]]
        radar = con_radar(documento)
        # La huella incluye los sitios a la vez (simultaneidad) y si lleva horizonte de radar.
        clave = f"{caso.lat:.5f},{caso.lon:.5f}" if radar else None
        huella = motor.huella_caso(catalogo, caso, [sitios, clave, clave in horizontes])
        guardar(
            documento["id"],
            "incidente",
            huella,
            lambda c=caso, r=radar: motor.evaluar_incidente(
                catalogo, c, sitios, horizonte_de if r else None
            ),
        )
    ataques = {a["id"]: a for a in almacen.ataques_ucrania()}
    por_ataque: dict[str, list[dict[str, Any]]] = {}
    for impacto in impactos_guerra.vigentes(almacen):
        if not impactos_guerra.con_firms(impacto):
            continue
        ataque = ataques.get(impacto.get("ataque", ""))
        caso = motor.caso_de_impacto(
            catalogo, impacto, ataque, condiciones.get(ataque["id"]) if ataque else None
        )
        huella = motor.huella_caso(
            catalogo, caso, ataque.get("zonas_lanzamiento") if ataque else None
        )
        resultado = guardar(
            impacto["id"], "impacto", huella, lambda c=caso: motor.evaluar_impacto(catalogo, c)
        )
        if ataque:
            por_ataque.setdefault(ataque["id"], []).append(resultado)
    for id_, ataque in ataques.items():
        de_impactos = por_ataque.get(id_, [])
        huella = motor.huella(
            motor.VERSION,
            catalogo.version,
            [
                (d.get("huella"), d.get("compatibles"), d.get("descartadas"), d.get("origenes"))
                for d in de_impactos
            ],
            ataque.get("cruces"),
        )
        guardar(
            id_,
            "ataque",
            huella,
            lambda a=ataque, d=de_impactos: motor.evaluar_ataque(catalogo, a, d),
        )
    escribir_resultados(datos, resultados)
    escribir_json(datos / HORIZONTES, horizontes)
    # Validación con los casos de modelo conocido y los encuentros de Airprox, y poder de descarte.
    validado = validacion.validar(
        catalogo,
        validacion.cargar(),
        meteo,
        {k: v["deduccion"] for k, v in resultados.items() if v["tipo"] == "incidente"},
    )
    validado["airprox"] = validacion.airprox(catalogo, almacen.encuentros(), meteo)
    validado["poder_de_descarte"] = validacion.poder_de_descarte(resultados)
    escribir_json(datos / VALIDACION, validado)
    resumen = {
        "ultima_correcta": _instante(ahora),
        "version_motor": motor.VERSION,
        "version_catalogo": catalogo.version,
        "duracion_s": round(time.monotonic() - inicio, 1),
        "cuentas": dict(sorted(cuentas.items())),
        "teselas_descargadas": relieve.descargas,
        "dem_mb": round(relieve.disco_mb(), 1),
        "validacion": {
            k: validado[k] for k in ("evaluados", "aciertos", "fallos_graves", "indeterminados")
        },
    }
    escribir_json(datos / CONTROL, resumen)
    return resumen


def incorporar(almacen: Almacen, datos: Path | None = None) -> dict[str, int]:
    """Guarda en la base lo deducido que ha cambiado. Devuelve cuántos por tipo."""
    datos = datos or directorio_datos()
    inicio = time.monotonic()
    cambiados: Counter[str] = Counter()
    existentes = almacen.deducciones()
    for id_, registro_ in leer_resultados(datos).items():
        if time.monotonic() - inicio > TOPE_INCORPORAR_S:
            registro.warning("deducción: tope de tiempo, el resto en la siguiente recogida")
            break
        previo = existentes.get(id_)
        documento = registro_["deduccion"]
        if previo is not None and previo.get("huella") == documento.get("huella"):
            continue
        if almacen.guardar_deduccion(id_, registro_["tipo"], documento):
            cambiados[registro_["tipo"]] += 1
    resumen = resumen_validacion(datos)
    if resumen is not None and almacen.cursor(CURSOR) != resumen:
        almacen.guardar_cursor(CURSOR, resumen)
    return dict(cambiados)


def resumen_validacion(datos: Path) -> dict[str, Any] | None:
    """Lo que va a la base (y a la exportación) de la validación: métricas sin el detalle."""
    ruta = datos / VALIDACION
    if not ruta.exists():
        return None
    validado = json.loads(ruta.read_text(encoding="utf-8"))
    control = json.loads((datos / CONTROL).read_text(encoding="utf-8"))
    airprox = {k: v for k, v in validado.get("airprox", {}).items() if k != "incoherentes"}
    return {
        "ultima_correcta": control.get("ultima_correcta"),
        "version_motor": validado["version_motor"],
        "version_catalogo": validado["version_catalogo"],
        "validacion": {
            k: validado[k]
            for k in (
                "casos",
                "evaluados",
                "aciertos",
                "fallos_graves",
                "indeterminados",
                "en_la_base",
            )
        },
        "airprox": airprox,
        "poder_de_descarte": validado.get("poder_de_descarte", {}),
    }


def paso_horario(almacen: Almacen) -> None:
    """En la recogida horaria: nada de lo que falle aquí sale de esta función."""
    try:
        cambiados = incorporar(almacen)
        registro.info("deducción incorporada: %s", cambiados or "sin cambios")
    except Exception as error:
        registro.warning("deducción no incorporada: %s", str(error)[:300])


def cliente_meteo() -> validacion.Meteo:
    """Open-Meteo con la caché común del servidor y un tope de llamadas por ejecución. El cliente
    (y el plazo de su descargador) se crea en la primera llamada, cuando empieza la validación,
    no al arrancar el cálculo. Tras el primer fallo no se vuelve a pedir nada en la ejecución."""
    from recogida import meteo
    from recogida.plazo import Plazo

    estado: dict[str, Any] = {}

    def horario(lat: float, lon: float, dia: Any) -> dict[str, list[Any]] | None:
        if estado.get("caido"):
            return None
        if "cliente" not in estado:
            estado["cliente"] = meteo.Cliente(
                meteo.directorio_datos(), meteo.descargador(Plazo(meteo.TOPE_S)), tope=TOPE_METEO
            )
        try:
            resultado: dict[str, list[Any]] | None = estado["cliente"].horas(
                [(round(lat, 3), round(lon, 3))], dia, meteo.SUPERFICIE + meteo.PRESION, "incidente"
            )[0]
            return resultado
        except Exception as error:
            estado["caido"] = True
            registro.warning("validación: Open-Meteo no responde: %s", str(error)[:200])
            return None

    return horario


def principal(argumentos: list[str] | None = None) -> int:
    opciones = argparse.ArgumentParser(description=__doc__)
    orden = opciones.add_subparsers(dest="orden", required=True)
    calculo = orden.add_parser("calcular", help="evalúa lo nuevo y deja los resultados")
    calculo.add_argument("--repositorio", default=None, help="repositorio de datos")
    calculo.add_argument("--base", type=Path, help="base cifrada local (en lugar de descargarla)")
    calculo.add_argument("--registro", type=Path, help="registro de la última ejecución correcta")
    calculo.add_argument("--todo", action="store_true", help="recalcula todo")
    args = opciones.parse_args(argumentos)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    from almacen import remoto
    from almacen.cifrado import abrir_cifrada

    ahora = datetime.now(UTC)
    datos = directorio_datos()
    with TemporaryDirectory() as temporal:
        ruta = args.base
        if ruta is None:
            ruta = Path(temporal) / remoto.FICHERO
            if not remoto.descargar(ruta, args.repositorio or remoto.REPOSITORIO):
                registro.error("no hay base en la rama %s", remoto.RAMA)
                return 1
        almacen = Almacen(abrir_cifrada(ruta))
        resumen = calcular(almacen, datos, ahora, todo=args.todo, meteo=cliente_meteo())
        almacen.cerrar()
    registro.info("deducción: %s", json.dumps(resumen, ensure_ascii=False))
    if args.registro is not None:
        escribir_json(
            args.registro,
            {
                "ultima_correcta": resumen["ultima_correcta"],
                "version_motor": resumen["version_motor"],
                "version_catalogo": resumen["version_catalogo"],
            },
        )
    return 0


if __name__ == "__main__":
    sys.exit(principal())
