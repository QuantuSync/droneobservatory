"""Procesado diario del tráfico aéreo de adsb.lol en el servidor.

Cada día se descarga en flujo (sin guardarlo en disco, `recogida/adsb.py`) y de cada traza
que toca Europa se sacan, en una sola pasada:

- los movimientos en los 926 aeropuertos de `configuracion/aeropuertos_trafico.json`
  (aterrizajes, despegues, frustradas, desvíos y esperas: `proceso/vuelos.py`);
- las aeronaves por celda H3 y hora con la posición degradada (`proceso/gnss.py`);
- las aeronaves militares, con su traza cada 30 s (`proceso/aeronaves.py`);
- las trazas filtradas: los puntos en tierra o por debajo de 10 000 pies a 40 km o menos de
  un aeropuerto con tráfico regular o de un incidente, o a 60 km o menos de un incidente que no
  es aeropuerto, uno cada 20 s, con codificación por diferencias (`lineas_trazas`). Las
  esperas, desvíos y aproximaciones más lejos o más altos quedan como movimientos; las
  aeronaves militares, enteras en su fichero.

Y los METAR del día de todos los aeropuertos (`recogida/metar.py`).

Todo se guarda en `<datos>/dias/AAAA/AAAA-MM-DD/` (`EODI_TRAFICO_DATOS`, por defecto
`~/datos/trafico`), fuera del repositorio y de la base: `movimientos.jsonl.gz`,
`gnss_hora.csv.gz`, `gnss_dia.csv.gz`, `militares.jsonl.gz`, `trazas.txt.gz` y, el último,
`resumen.json`, que marca el día como procesado y lleva la publicación usada, los recuentos y
lo que costó (duración, CPU y memoria). La base solo recibe los resultados agregados, en la
recogida horaria (`proceso/mediciones.py`).

**Qué días.** Primero los recientes (los 35 últimos, para que el diario tenga su línea base
de cuatro semanas), del más nuevo al más viejo; después los de los incidentes europeos de la
base y los de su línea base (el mismo día de la semana de las cuatro semanas anteriores),
con los confirmados y atribuidos delante. La lista de incidentes la deja la recogida horaria
en `<datos>/zonas.json`. Un día que adsb.lol no ha publicado se vuelve a mirar en la
ejecución siguiente; tres días después de terminado, se da por perdido.

Lo lanza `servidor/trafico.sh` con su propio cerrojo, nunca el de la recogida horaria.

Uso: python -m recogida.trafico pendientes [--tope-min N] [--datos DIR]
     python -m recogida.trafico dia AAAA-MM-DD [AAAA-MM-DD ...] [--datos DIR]
     python -m recogida.trafico resumen [--datos DIR]
"""

import argparse
import gzip
import io
import json
import logging
import math
import os
import sys
import time
from collections import Counter, OrderedDict
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

from proceso import aeronaves, gnss, trafico, vuelos
from recogida import adsb, metar

registro = logging.getLogger("recogida.trafico")

VARIABLE_DATOS = "EODI_TRAFICO_DATOS"
DATOS = Path.home() / "datos" / "trafico"
CONTROL = "control.json"
ZONAS = "zonas.json"
RESUMEN = "resumen.json"
VERSION_REGLA = trafico.VERSION_REGLA

# Zona de cálculo: la de las teselas de la web (25° O a 45° E, 34° N a 72° N), que cubre
# Europa, Turquía, Ucrania, Moldavia y Chipre. Las trazas se leen con 5° de margen para que
# un vuelo que entra en la zona tenga su aproximación entera.
CAJA = gnss.Caja(oeste=-25.0, sur=34.0, este=45.0, norte=72.0)
CAJA_LECTURA = (-30.0, 29.0, 50.0, 75.0)

RADIO_PISTA_KM = 40.0
RADIO_INCIDENTE_KM = 60.0
TECHO_CERCA_FT = 10000.0
PASO_CERCA_S = 20.0
VELOCIDAD_PARADA_KT = 3.0
PASO_MILITAR_S = 30.0
CELDA_ZONAS = 0.1

DIAS_RECIENTES = 35
SEMANAS_BASE = 4
DIAS_PARA_DAR_POR_PERDIDO = 3
# Un incidente con su línea base usa unos 10 días; los incidentes se evalúan por fecha. Un día
# en memoria (solo sus movimientos) ocupa unos 40 MB.
DIAS_EN_MEMORIA = 12


def directorio_datos() -> Path:
    return Path(os.environ.get(VARIABLE_DATOS) or DATOS)


def directorio_dia(datos: Path, dia: date) -> Path:
    return datos / "dias" / f"{dia.year}" / dia.isoformat()


def procesado(datos: Path, dia: date) -> bool:
    return (directorio_dia(datos, dia) / RESUMEN).exists()


def leer_json(ruta: Path) -> Any:
    if not ruta.exists():
        return None
    try:
        return json.loads(ruta.read_text(encoding="utf-8"))
    except ValueError:
        return None


def escribir_json(ruta: Path, contenido: Any) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    temporal = ruta.with_suffix(".tmp")
    temporal.write_text(
        json.dumps(contenido, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n"
    )
    temporal.replace(ruta)


# --- Trazas filtradas -----------------------------------------------------------------


class Zonas:
    """Celdas de 0,1° a 40 km o menos de un aeropuerto con tráfico regular o de un incidente,
    o a 60 km o menos de un incidente que no es aeropuerto."""

    def __init__(
        self,
        aeropuertos: Iterable[vuelos.Aeropuerto],
        incidentes: Iterable[tuple[float, float]],
        oaci_incidentes: Iterable[str] = (),
    ) -> None:
        self._celdas: set[tuple[int, int]] = set()
        de_incidentes = set(oaci_incidentes)
        for a in aeropuertos:
            if a.regular or a.oaci in de_incidentes:
                self._marcar(a.lat, a.lon, RADIO_PISTA_KM)
        for lat, lon in incidentes:
            self._marcar(lat, lon, RADIO_INCIDENTE_KM)

    def _marcar(self, lat: float, lon: float, radio_km: float) -> None:
        dlat = radio_km / vuelos.KM_POR_GRADO_LAT
        dlon = radio_km / (vuelos.KM_POR_GRADO_LON_ECUADOR * max(0.1, math.cos(math.radians(lat))))
        for i in range(
            math.floor((lat - dlat) / CELDA_ZONAS), math.floor((lat + dlat) / CELDA_ZONAS) + 1
        ):
            for j in range(
                math.floor((lon - dlon) / CELDA_ZONAS), math.floor((lon + dlon) / CELDA_ZONAS) + 1
            ):
                clat, clon = (i + 0.5) * CELDA_ZONAS, (j + 0.5) * CELDA_ZONAS
                if vuelos.distancia_km(lat, lon, clat, clon) <= radio_km + 6:
                    self._celdas.add((i, j))

    def dentro(self, lat: float, lon: float) -> bool:
        return (math.floor(lat / CELDA_ZONAS), math.floor(lon / CELDA_ZONAS)) in self._celdas


def _entero(valor: float | None) -> int | None:
    return None if valor is None else round(valor)


def lineas_trazas(traza: vuelos.Traza, zonas: Zonas) -> list[str]:
    """La traza filtrada en el formato de `trazas.txt.gz`: una cabecera por aeronave
    (`#icao,tipo,marcas,categoria`) y un punto por línea, cada 20 s como mucho, de los que están
    en tierra o por debajo de 10 000 pies dentro de las zonas (de una parada en tierra, solo el
    primer punto). El primer punto lleva los valores
    enteros: tiempo (s desde 1970), latitud y longitud en diezmilésimas de grado, altitud en
    unidades de 25 pies (S en tierra, vacío si no se sabe), velocidad (nudos), rumbo (grados),
    velocidad vertical (pies/min), NIC y NACp. Los siguientes llevan la diferencia con el
    anterior en tiempo, latitud, longitud y altitud (cuando las dos son números) y el valor de
    los demás campos solo si cambia (vacío si no cambia; las comas finales se quitan)."""
    lineas: list[str] = []
    anterior: list[Any] | None = None
    ultimo = -1e18
    for i in range(len(traza)):
        alt, suelo = traza.alt[i], traza.suelo[i]
        if not suelo and (alt is None or alt >= TECHO_CERCA_FT):
            continue
        if traza.t[i] - ultimo < PASO_CERCA_S or not zonas.dentro(traza.lat[i], traza.lon[i]):
            continue
        # Parada en tierra: solo el primer punto.
        parada = suelo and (traza.gs[i] or 0.0) < VELOCIDAD_PARADA_KT
        if (
            parada
            and anterior is not None
            and anterior[3] == "S"
            and (anterior[4] or 0) < VELOCIDAD_PARADA_KT
        ):
            continue
        ultimo = traza.t[i]
        valores: list[Any] = [
            round(traza.t[i]),
            round(traza.lat[i] * 1e4),
            round(traza.lon[i] * 1e4),
            "S" if suelo else ("" if alt is None else round(alt / 25)),
            _entero(traza.gs[i]),
            _entero(traza.rumbo[i]),
            _entero(traza.vz[i]),
            traza.nic[i],
            traza.nacp[i],
        ]
        if anterior is None:
            lineas.append(
                f"#{traza.icao},{traza.tipo or ''},{traza.marcas},{traza.categoria or ''}"
            )
            salida = ["" if v is None else v for v in valores]
        else:
            numericos = isinstance(valores[3], int) and isinstance(anterior[3], int)
            salida = [
                valores[0] - anterior[0],
                valores[1] - anterior[1],
                valores[2] - anterior[2],
                valores[3] - anterior[3]
                if numericos
                else ("" if valores[3] == anterior[3] else valores[3]),
                *(
                    "" if v == w or v is None else v
                    for v, w in zip(valores[4:], anterior[4:], strict=True)
                ),
            ]
        lineas.append(",".join(str(x) for x in salida).rstrip(","))
        anterior = valores
    return lineas


def leer_trazas(contenido: str | Iterable[str]) -> Iterator[tuple[str, list[list[Any]]]]:
    """Lee `trazas.txt.gz` ya descomprimido (el texto entero o sus líneas, para leerlo en
    flujo): por aeronave, su cabecera y sus puntos con los valores enteros (tiempo, lat×1e4,
    lon×1e4, altitud/25 o "S" o None, velocidad, rumbo, velocidad vertical, NIC, NACp)."""
    cabecera: str | None = None
    puntos: list[list[Any]] = []
    anterior: list[Any] | None = None
    lineas = contenido.splitlines() if isinstance(contenido, str) else contenido
    for linea in lineas:
        linea = linea.rstrip("\n")
        if linea.startswith("#"):
            if cabecera is not None:
                yield cabecera, puntos
            cabecera, puntos, anterior = linea[1:], [], None
            continue
        campos = linea.split(",")
        campos += [""] * (9 - len(campos))

        def numero(texto: str) -> int | None:
            return int(texto) if texto not in ("", "S") else None

        if anterior is None:
            valores: list[Any] = [numero(c) for c in campos]
            valores[3] = "S" if campos[3] == "S" else numero(campos[3])
        else:
            valores = [
                anterior[0] + int(campos[0]),
                anterior[1] + int(campos[1]),
                anterior[2] + int(campos[2]),
            ]
            if (
                isinstance(anterior[3], int)
                and campos[3] not in ("", "S")
                and not campos[3].startswith("S")
            ):
                valores.append(anterior[3] + int(campos[3]))
            else:
                valores.append(
                    "S" if campos[3] == "S" else (numero(campos[3]) if campos[3] else anterior[3])
                )
            valores += [numero(c) if c else anterior[k + 4] for k, c in enumerate(campos[4:9])]
        puntos.append(valores)
        anterior = valores
    if cabecera is not None:
        yield cabecera, puntos


def militar(traza: vuelos.Traza) -> dict[str, Any] | None:
    """La aeronave militar con su traza cada 30 s dentro de la zona de cálculo."""
    puntos = []
    ultimo = -1e18
    for i in range(len(traza)):
        if not CAJA.contiene(traza.lat[i], traza.lon[i]) or traza.t[i] - ultimo < PASO_MILITAR_S:
            continue
        ultimo = traza.t[i]
        alt = traza.alt[i]
        puntos.append(
            [
                round(traza.t[i]),
                round(traza.lat[i], 4),
                round(traza.lon[i], 4),
                "S" if traza.suelo[i] else (None if alt is None else round(alt)),
            ]
        )
    if not puntos:
        return None
    return {
        "icao": traza.icao,
        "matricula": traza.matricula,
        "tipo": traza.tipo,
        "descripcion": traza.descripcion,
        "operador": traza.operador,
        "marcas": traza.marcas,
        "categoria": traza.categoria,
        "clase": aeronaves.clase(traza.tipo, traza.categoria).value,
        "indicativos": sorted({c for c in traza.indicativo if c}),
        "puntos": puntos,
    }


# --- Un día ------------------------------------------------------------------------


@dataclass
class Resultado:
    movimientos: list[vuelos.Movimiento] = field(default_factory=list)
    recuento_gnss: gnss.Recuento = field(default_factory=gnss.Recuento)
    militares: list[dict[str, Any]] = field(default_factory=list)
    trazas: int = 0
    trazas_europa: int = 0
    puntos: int = 0


def procesar_documentos(
    documentos: Iterable[dict[str, Any]],
    aeropuertos: tuple[vuelos.Aeropuerto, ...],
    zonas: Zonas,
    salida_trazas: io.TextIOBase | None,
) -> Resultado:
    indice = vuelos.Indice(aeropuertos)
    celdas = gnss.Celdas()
    resultado = Resultado()
    oeste, sur, este, norte = CAJA_LECTURA
    for documento in documentos:
        resultado.trazas += 1
        if not adsb.toca_caja(documento, CAJA.oeste, CAJA.sur, CAJA.este, CAJA.norte):
            continue
        traza = adsb.leer_traza(documento, CAJA_LECTURA)
        if len(traza) < 2:
            continue
        resultado.trazas_europa += 1
        resultado.puntos += len(traza)
        ifr = aeronaves.es_ifr(traza.tipo, traza.categoria, traza.marcas)
        resultado.movimientos += vuelos.analizar(traza, indice, ifr)
        resultado.recuento_gnss.sumar(gnss.celdas_hora(traza, CAJA, celdas))
        if aeronaves.es_militar(traza.tipo, traza.marcas):
            datos = militar(traza)
            if datos is not None:
                resultado.militares.append(datos)
        if salida_trazas is not None:
            lineas = lineas_trazas(traza, zonas)
            if lineas:
                salida_trazas.write("\n".join(lineas) + "\n")
    del oeste, sur, este, norte
    return resultado


def _gz(ruta: Path, texto: str) -> None:
    temporal = ruta.with_suffix(".tmp")
    temporal.write_bytes(gzip.compress(texto.encode("utf-8"), compresslevel=6, mtime=0))
    temporal.replace(ruta)


def _recursos() -> tuple[float, float | None]:
    """CPU usada (s) y memoria máxima (MB) del proceso; la memoria solo en Linux."""
    if sys.platform == "win32":
        return time.process_time(), None
    import resource  # solo existe en Unix

    uso = resource.getrusage(resource.RUSAGE_SELF)
    return uso.ru_utime + uso.ru_stime, uso.ru_maxrss / 1024


def incidentes_de_zonas(datos: Path) -> list[dict[str, Any]]:
    contenido = leer_json(datos / ZONAS) or {}
    return list(contenido.get("incidentes", []))


def procesar_dia(
    datos: Path,
    dia: date,
    abrir: adsb.Abridor = adsb.abrir_urllib,
    descarga_metar: Callable[[], Any] | None = None,
) -> dict[str, Any]:
    """Procesa un día completo y escribe sus ficheros. Devuelve el resumen."""
    inicio = time.monotonic()
    cpu0, _ = _recursos()
    candidatas = adsb.publicaciones(dia, abrir)
    aeropuertos = vuelos.cargar_aeropuertos()
    incidentes = incidentes_de_zonas(datos)
    puntos_incidentes = [
        (i["lat"], i["lon"]) for i in incidentes if i.get("lat") is not None and not i.get("oaci")
    ]
    zonas = Zonas(aeropuertos, puntos_incidentes, [i["oaci"] for i in incidentes if i.get("oaci")])
    destino = directorio_dia(datos, dia)
    destino.mkdir(parents=True, exist_ok=True)
    temporal_trazas = destino / "trazas.txt.gz.tmp"
    for numero, publicacion in enumerate(candidatas):
        flujo = adsb.Encadenado(publicacion.urls, abrir, publicacion.tamanos)
        ilegibles: list[str] = []
        grandes: list[str] = []
        try:
            with gzip.open(temporal_trazas, "wt", encoding="utf-8", compresslevel=9) as salida:
                lector = io.BufferedReader(flujo, buffer_size=adsb.BLOQUE)
                resultado = procesar_documentos(
                    adsb.documentos(lector, ilegibles, grandes), aeropuertos, zonas, salida
                )
            if flujo.bytes != publicacion.bytes:
                raise adsb.LecturaIncompleta(
                    f"{publicacion.etiqueta}: {flujo.bytes} de {publicacion.bytes} bytes"
                )
            break
        except adsb.LecturaIncompleta as error:
            if numero == len(candidatas) - 1:
                raise
            registro.warning("%s; se prueba la otra publicación del día", error)
    temporal_trazas.replace(destino / "trazas.txt.gz")
    movimientos = sorted(resultado.movimientos, key=lambda m: (m.oaci, m.t, m.icao, m.tipo))
    _gz(
        destino / "movimientos.jsonl.gz",
        "".join(json.dumps(m.fila(), ensure_ascii=False) + "\n" for m in movimientos),
    )
    _gz(
        destino / "gnss_hora.csv.gz",
        "hora,celda,aeronaves,degradadas\n"
        + "".join(f"{h},{c},{n},{d}\n" for h, c, n, d in resultado.recuento_gnss.filas()),
    )
    _gz(
        destino / "gnss_dia.csv.gz",
        "celda,aeronaves,degradadas\n"
        + "".join(f"{c},{n},{d}\n" for c, n, d in resultado.recuento_gnss.filas_dia()),
    )
    _gz(
        destino / "militares.jsonl.gz",
        "".join(json.dumps(m, ensure_ascii=False) + "\n" for m in resultado.militares),
    )
    estaciones = sorted(a.oaci for a in aeropuertos)
    metar_ok = False
    try:
        metar.descargar(
            datos, dia, estaciones, descarga_metar() if descarga_metar else metar.descargador()
        )
        metar_ok = True
    except Exception as error:
        registro.warning("metar del %s no se descarga: %s", dia, error)
    cpu1, memoria = _recursos()
    tipos = Counter(m.tipo for m in movimientos)
    resumen = {
        "dia": dia.isoformat(),
        "version_regla": VERSION_REGLA,
        "publicacion": publicacion.etiqueta,
        "pagina": publicacion.pagina,
        "bytes_publicacion": publicacion.bytes,
        "bytes_leidos": flujo.bytes,
        "trazas": resultado.trazas,
        "trazas_europa": resultado.trazas_europa,
        "trazas_ilegibles": len(ilegibles),
        # Trazas saltadas por pasar del tope de tamaño (adsb.TOPE_TRAZA), con su nombre.
        "trazas_demasiado_grandes": grandes,
        "puntos_europa": resultado.puntos,
        "movimientos": dict(sorted(tipos.items())),
        "militares": len(resultado.militares),
        "celdas_gnss": len(resultado.recuento_gnss.aeronaves_dia),
        "metar": metar_ok,
        "duracion_s": round(time.monotonic() - inicio),
        "cpu_s": round(cpu1 - cpu0),
        "memoria_max_mb": None if memoria is None else round(memoria),
        "bytes_ficheros": {
            p.name: p.stat().st_size for p in sorted(destino.iterdir()) if p.is_file()
        },
        "procesado": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    escribir_json(destino / RESUMEN, resumen)
    control = leer_json(datos / CONTROL) or {}
    escribir_json(datos / CONTROL, {**control, "ultimo_correcto": resumen["procesado"]})
    return resumen


# --- Qué días ---------------------------------------------------------------------


def dias_base(dia: date) -> list[date]:
    return [dia - timedelta(weeks=k) for k in range(1, SEMANAS_BASE + 1)]


def cola(datos: Path, hoy: date) -> list[date]:
    """Los días por procesar, en orden: recientes primero y luego los de incidentes."""
    control = leer_json(datos / CONTROL) or {}
    perdidos = set(control.get("perdidos", []))
    orden: list[date] = []
    vistos: set[date] = set()

    def anadir(dia: date) -> None:
        if dia in vistos or dia >= hoy or dia.isoformat() in perdidos:
            return
        vistos.add(dia)
        if not procesado(datos, dia):
            orden.append(dia)

    for k in range(1, DIAS_RECIENTES + 1):
        anadir(hoy - timedelta(days=k))
    incidentes = sorted(
        incidentes_de_zonas(datos),
        key=lambda i: (not i.get("prioritario", False), str(i.get("dia", ""))),
        reverse=False,
    )
    prioritarios = [i for i in incidentes if i.get("prioritario")]
    resto = [i for i in incidentes if not i.get("prioritario")]
    for grupo in (prioritarios, resto):
        for incidente in sorted(grupo, key=lambda i: str(i.get("dia", "")), reverse=True):
            try:
                dias = [
                    date.fromisoformat(str(d)) for d in incidente.get("dias") or [incidente["dia"]]
                ]
            except (KeyError, ValueError):
                continue
            for dia in dias:
                for d in [dia, *dias_base(dia)]:
                    anadir(d)
    return orden


def anotar_sin_publicar(datos: Path, dia: date, hoy: date) -> None:
    """Un día sin publicar tres días después de terminado se da por perdido."""
    if (hoy - dia).days <= DIAS_PARA_DAR_POR_PERDIDO:
        return
    control = leer_json(datos / CONTROL) or {}
    perdidos = sorted(set(control.get("perdidos", [])) | {dia.isoformat()})
    escribir_json(datos / CONTROL, {**control, "perdidos": perdidos})


def pendientes(
    datos: Path, tope_s: float, ahora: datetime, abrir: adsb.Abridor = adsb.abrir_urllib
) -> int:
    """Procesa días de la cola mientras quepa otro en el tope. Devuelve cuántos procesó."""
    comienzo = time.monotonic()
    hechos = 0
    ultimo_s = 0.0
    for dia in cola(datos, ahora.date()):
        transcurrido = time.monotonic() - comienzo
        if hechos and transcurrido + ultimo_s > tope_s:
            break
        try:
            resumen = procesar_dia(datos, dia, abrir)
        except adsb.SinPublicar:
            registro.info("%s: adsb.lol aún no lo ha publicado", dia)
            anotar_sin_publicar(datos, dia, ahora.date())
            continue
        except (adsb.LecturaIncompleta, OSError) as error:
            # Se repite en la ejecución siguiente; los demás días siguen.
            registro.warning("%s no se ha podido leer entero: %s", dia, error)
            continue
        hechos += 1
        ultimo_s = float(resumen["duracion_s"])
        registro.info(
            "%s procesado en %d s (%d s de CPU): %d trazas en Europa, movimientos %s",
            dia,
            resumen["duracion_s"],
            resumen["cpu_s"],
            resumen["trazas_europa"],
            resumen["movimientos"],
        )
    return hechos


# --- Lectura de los días procesados (para la recogida horaria) -----------------------


class Dias:
    """Los días procesados, leídos de disco con una caché de los últimos DIAS_EN_MEMORIA."""

    def __init__(self, datos: Path) -> None:
        self.datos = datos
        self._cache: OrderedDict[date, trafico.DiaTrafico | None] = OrderedDict()
        control = leer_json(datos / CONTROL) or {}
        self.perdidos = {date.fromisoformat(d) for d in control.get("perdidos", [])}

    def resumen(self, dia: date) -> dict[str, Any] | None:
        contenido = leer_json(directorio_dia(self.datos, dia) / RESUMEN)
        return contenido if isinstance(contenido, dict) else None

    def procesados(self) -> list[date]:
        return sorted(
            date.fromisoformat(p.parent.name) for p in (self.datos / "dias").glob(f"*/*/{RESUMEN}")
        )

    def __call__(self, dia: date) -> trafico.DiaTrafico | None:
        if dia in self._cache:
            self._cache.move_to_end(dia)
            return self._cache[dia]
        resultado = self._leer(dia)
        self._cache[dia] = resultado
        while len(self._cache) > DIAS_EN_MEMORIA:
            self._cache.popitem(last=False)
        return resultado

    def _leer(self, dia: date) -> trafico.DiaTrafico | None:
        resumen = self.resumen(dia)
        if resumen is None:
            return None
        carpeta = directorio_dia(self.datos, dia)
        movimientos: dict[str, list[list[Any]]] = {}
        for linea in _lineas(carpeta / "movimientos.jsonl.gz"):
            fila = json.loads(linea)
            movimientos.setdefault(fila[0], []).append(fila)
        return trafico.DiaTrafico(
            dia,
            resumen["publicacion"],
            resumen["pagina"],
            movimientos,
            cargador=lambda nombre: _detalle(carpeta, nombre),
        )


def _detalle(carpeta: Path, nombre: str) -> Any:
    """Las aeronaves militares o la interferencia GNSS de un día procesado, leídas de disco."""
    if nombre == "militares":
        return [json.loads(linea) for linea in _lineas(carpeta / "militares.jsonl.gz")]
    if nombre == "gnss_hora":
        filas = [linea.split(",") for linea in _lineas(carpeta / "gnss_hora.csv.gz")[1:]]
        return [(int(h), c, int(n), int(m)) for h, c, n, m in filas]
    if nombre == "gnss_dia":
        filas = [linea.split(",") for linea in _lineas(carpeta / "gnss_dia.csv.gz")[1:]]
        return [(c, int(n), int(m)) for c, n, m in filas]
    raise KeyError(nombre)


def _lineas(ruta: Path) -> list[str]:
    if not ruta.exists():
        return []
    return [x for x in gzip.decompress(ruta.read_bytes()).decode("utf-8").splitlines() if x]


def resumen_general(datos: Path) -> dict[str, Any]:
    dias = sorted(p.parent.name for p in (datos / "dias").glob(f"*/*/{RESUMEN}"))
    total = sum(f.stat().st_size for f in (datos / "dias").rglob("*") if f.is_file())
    return {
        "dias_procesados": len(dias),
        "primero": dias[0] if dias else None,
        "ultimo": dias[-1] if dias else None,
        "bytes": total,
        "control": leer_json(datos / CONTROL),
    }


def principal(argumentos: list[str] | None = None) -> int:
    opciones = argparse.ArgumentParser(description=__doc__)
    sub = opciones.add_subparsers(dest="orden", required=True)
    p = sub.add_parser("pendientes")
    p.add_argument("--tope-min", type=float, default=50.0)
    p.add_argument("--datos", type=Path)
    d = sub.add_parser("dia")
    d.add_argument("dia", type=date.fromisoformat, nargs="+")
    d.add_argument("--datos", type=Path)
    r = sub.add_parser("resumen")
    r.add_argument("--datos", type=Path)
    args = opciones.parse_args(argumentos)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    datos = args.datos or directorio_datos()
    datos.mkdir(parents=True, exist_ok=True)
    if args.orden == "dia":
        for dia in args.dia:
            if procesado(datos, dia):
                registro.info("%s ya estaba procesado", dia)
                continue
            resumen = procesar_dia(datos, dia)
            registro.info("%s: %s", dia, json.dumps(resumen, ensure_ascii=False))
        return 0
    if args.orden == "resumen":
        print(json.dumps(resumen_general(datos), ensure_ascii=False, indent=1))
        return 0
    hechos = pendientes(datos, args.tope_min * 60, datetime.now(UTC))
    registro.info("días procesados en esta ejecución: %d", hechos)
    return 0


if __name__ == "__main__":
    sys.exit(principal())
