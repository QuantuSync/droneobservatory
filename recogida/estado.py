"""Estado del sistema para la web: estado.json, que el servidor sube al almacén público.

Al final de cada recogida horaria, `servidor/recogida.sh` compone el estado con lo que
dejó escrito la recogida (cómo fue cada fuente y la fecha de su último dato), el código
con que terminó y el estado anterior (de donde sale la última recogida correcta), y lo
sube al almacén público (recogida/almacen_publico.py) sin commit en git: así la web no se
reconstruye cada hora. Solo lleva horas y estados, ningún contenido.

Formato (versión 1), con los instantes como AAAA-MM-DDThh:mmZ:

    {"version": 1, "inicio", "fin", "resultado": correcta | con_avisos | fallida,
     "ultima_correcta": instante o null, "siguiente",
     "fuentes": [{"id", "estado": leida | con_aviso | no_leida, "ultimo_dato": instante o null}],
     "ultima_exportacion": instante o null, "ultima_deduccion": instante o null,
     "directo": {"estado": en_marcha | con_respaldo | parado, "ultimo_ciclo_correcto": instante
                 o null},
     "seguimiento": {"estado": en_marcha | con_respaldo | parado, "ultima_recepcion": instante
                     o null, "ultimo_latido": instante o null,
                     "ultimo_hueco_largo": {"desde": instante, "hasta": instante} o null}}

ultima_exportacion es la hora en que terminó bien la última exportación semanal para AEGIS
(recogida/exportacion.py), que la deja escrita en su registro; null si no consta ninguna. Sin
--exportacion el campo no va. ultima_deduccion es la hora de la última ejecución correcta del
motor de deducción (recogida/deduccion.py), del registro que deja; sin --deduccion no va.
directo es el servicio de detección en directo de cierres (recogida/directo.py), de su registro:
en marcha si tuvo un ciclo correcto en los últimos 10 minutos (con respaldo si fue con la fuente
de respaldo), parado si no; sin --directo no va.
seguimiento es la captura del seguimiento en directo (recogida/seguimiento.py), de su registro: en
marcha si recibió un heartbeat del flujo de NEPTUN en los últimos 10 minutos, con respaldo si no
pero recibió datos por el REST, parado si nada; lleva además su último hueco de más de 10 minutos
(sin datos del flujo), que el vigía convierte en aviso. Sin --seguimiento no va.

Las fuentes van siempre todas y en este orden: fuerza_aerea_ua, mindef_ru, gdelt, oficiales,
extractor, firms, las oficiales de detalle (recogida/detalle.py): airprox, parlamentos,
investigaciones, estadisticas_oficiales y paginas_js, las de la capa de guerra con lugar
(recogida/canales_guerra.py): ova_ua, estado_mayor_ua, gobernadores_ru y rosaviatsia, y las
medidas: trafico_aereo y condiciones. En firms, el último dato es la hora de la última descarga
correcta de NASA FIRMS (se descarga cada 3 horas); en las de detalle, la de su última lectura
correcta (las lee su propio temporizador cada 3 horas); en las de la capa de guerra
(administraciones militares regionales de Ucrania, Estado Mayor ucraniano, gobernadores rusos y
Rosaviatsia), la de la última lectura correcta de alguno de sus canales por el lector del
servidor: leída si se leyeron todos sus canales, con aviso si alguno no, no leída si ninguno;
en trafico_aereo, la hora en que terminó de procesarse el último día del archivo de adsb.lol;
en condiciones, la de la última petición correcta a Open-Meteo o al IEM.

Uso: python -m recogida.estado --inicio <ISO> --codigo <N> --parcial <json> --anterior <json>
    --salida <json> --minuto <minuto de la recogida> [--exportacion <json>] [--deduccion <json>]
    [--directo <json>] [--seguimiento <json>]
"""

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

VERSION = 1
FUENTES = (
    "fuerza_aerea_ua", "mindef_ru", "gdelt", "oficiales", "extractor", "firms",
    "airprox", "parlamentos", "investigaciones", "estadisticas_oficiales", "paginas_js",
    "ova_ua", "estado_mayor_ua", "gobernadores_ru", "rosaviatsia",
    "trafico_aereo", "condiciones",
)  # fmt: skip
LEIDA, CON_AVISO, NO_LEIDA = "leida", "con_aviso", "no_leida"
CORRECTA, CON_AVISOS, FALLIDA = "correcta", "con_avisos", "fallida"
# Código con avisos de la recogida (recogida.horaria.SALIDA_AVISO): se lee y se publica, pero
# alguna fuente no.
SALIDA_AVISO = 2
FORMATO = "%Y-%m-%dT%H:%MZ"
HORA = timedelta(hours=1)
# Detección en directo (recogida/directo.py): un ciclo por minuto.
EN_MARCHA, CON_RESPALDO, PARADO = "en_marcha", "con_respaldo", "parado"
FUENTE_PRINCIPAL = "adsb_lol"
DIRECTO_PARADO = timedelta(minutes=10)


@dataclass(frozen=True)
class EstadoFuente:
    estado: str
    ultimo_dato: datetime | None = None

    def documento(self, id_: str) -> dict[str, Any]:
        return {"id": id_, "estado": self.estado, "ultimo_dato": instante(self.ultimo_dato)}


def instante(momento: datetime | None) -> str | None:
    return momento.astimezone(UTC).strftime(FORMATO) if momento is not None else None


def leer_instante(texto: str | None) -> datetime | None:
    if not texto:
        return None
    return datetime.fromisoformat(texto.replace("Z", "+00:00")).astimezone(UTC)


def escribir_parcial(ruta: Path, fuentes: dict[str, EstadoFuente]) -> None:
    """Lo que deja escrito la recogida horaria: cada fuente con su estado y su último dato."""
    ruta.write_text(
        json.dumps({f: fuentes[f].documento(f) for f in fuentes}, ensure_ascii=False),
        encoding="utf-8",
    )


def siguiente(fin: datetime, minuto: int) -> datetime:
    """La siguiente recogida programada, en el minuto `minuto` de la hora, después de `fin`."""
    candidata = fin.replace(minute=minuto, second=0, microsecond=0)
    return candidata if candidata > fin else candidata + HORA


def resultado(codigo: int) -> str:
    if codigo == 0:
        return CORRECTA
    return CON_AVISOS if codigo == SALIDA_AVISO else FALLIDA


def _fuentes(parcial: dict[str, Any] | None, anterior: dict[str, Any] | None) -> list[Any]:
    """Las de la recogida; si no dejó nada (falló antes de terminar), las del estado anterior
    como no leídas, con la fecha de su último dato."""
    if parcial is not None:
        return [parcial.get(f) or EstadoFuente(NO_LEIDA).documento(f) for f in FUENTES]
    previas = {f["id"]: f for f in (anterior or {}).get("fuentes", [])}
    return [
        {"id": f, "estado": NO_LEIDA, "ultimo_dato": previas.get(f, {}).get("ultimo_dato")}
        for f in FUENTES
    ]


def componer(
    inicio: datetime,
    fin: datetime,
    codigo: int,
    parcial: dict[str, Any] | None,
    anterior: dict[str, Any] | None,
    minuto: int,
    exportacion: dict[str, Any] | None = None,
    con_exportacion: bool = False,
    deduccion: dict[str, Any] | None = None,
    con_deduccion: bool = False,
    directo: dict[str, Any] | None = None,
    con_directo: bool = False,
    seguimiento: dict[str, Any] | None = None,
    con_seguimiento: bool = False,
) -> dict[str, Any]:
    fallo = resultado(codigo)
    ultima = instante(fin) if fallo == CORRECTA else (anterior or {}).get("ultima_correcta")
    estado: dict[str, Any] = {
        "version": VERSION,
        "inicio": instante(inicio),
        "fin": instante(fin),
        "resultado": fallo,
        "ultima_correcta": ultima,
        "siguiente": instante(siguiente(fin, minuto)),
        "fuentes": _fuentes(parcial, anterior),
    }
    if con_exportacion:
        estado["ultima_exportacion"] = (exportacion or {}).get("fin")
    if con_deduccion:
        estado["ultima_deduccion"] = (deduccion or {}).get("ultima_correcta")
    if con_directo:
        estado["directo"] = estado_directo(directo, fin)
    if con_seguimiento:
        estado["seguimiento"] = estado_seguimiento(seguimiento, fin)
    return estado


def estado_directo(registro: dict[str, Any] | None, ahora: datetime) -> dict[str, Any]:
    """El servicio de detección en directo: su último ciclo correcto y si sigue en marcha (un
    ciclo correcto en los últimos 10 minutos), con la fuente principal o con el respaldo."""
    ultimo = (registro or {}).get("ultimo_ciclo_correcto")
    momento = leer_instante(ultimo)
    if momento is None or ahora - momento > DIRECTO_PARADO:
        situacion = PARADO
    else:
        situacion = (
            EN_MARCHA if (registro or {}).get("fuente") == FUENTE_PRINCIPAL else CON_RESPALDO
        )
    return {"estado": situacion, "ultimo_ciclo_correcto": ultimo}


def _minuto(texto: object) -> str | None:
    momento = leer_instante(texto) if isinstance(texto, str) else None
    return instante(momento) if momento is not None else None


def estado_seguimiento(registro: dict[str, Any] | None, ahora: datetime) -> dict[str, Any]:
    """La captura del seguimiento en directo: en marcha con un heartbeat del flujo en los últimos
    10 minutos, con respaldo si solo llegan datos por el REST, parada si nada; y su último hueco
    largo (desde y hasta), sin el motivo."""
    datos = registro or {}
    latido = leer_instante(datos.get("ultimo_latido"))
    recepcion = leer_instante(datos.get("ultima_recepcion"))
    if latido is not None and ahora - latido <= DIRECTO_PARADO:
        situacion = EN_MARCHA
    elif recepcion is not None and ahora - recepcion <= DIRECTO_PARADO:
        situacion = CON_RESPALDO
    else:
        situacion = PARADO
    hueco = datos.get("ultimo_hueco_largo")
    largo = None
    if isinstance(hueco, dict) and _minuto(hueco.get("desde")) and _minuto(hueco.get("hasta")):
        largo = {"desde": _minuto(hueco.get("desde")), "hasta": _minuto(hueco.get("hasta"))}
    return {
        "estado": situacion,
        "ultima_recepcion": instante(recepcion) if recepcion else None,
        "ultimo_latido": instante(latido) if latido else None,
        "ultimo_hueco_largo": largo,
    }


def _leer(ruta: Path | None) -> dict[str, Any] | None:
    if ruta is None or not ruta.exists() or not ruta.stat().st_size:
        return None
    try:
        datos: dict[str, Any] = json.loads(ruta.read_text(encoding="utf-8"))
    except ValueError:
        return None
    return datos


def principal(argumentos: list[str] | None = None) -> int:
    opciones = argparse.ArgumentParser(description=__doc__)
    opciones.add_argument("--inicio", required=True)
    opciones.add_argument("--codigo", type=int, required=True)
    opciones.add_argument("--parcial", type=Path)
    opciones.add_argument("--anterior", type=Path)
    opciones.add_argument("--salida", type=Path, required=True)
    opciones.add_argument("--minuto", type=int, required=True)
    opciones.add_argument("--exportacion", type=Path, help="registro de la exportación semanal")
    opciones.add_argument("--deduccion", type=Path, help="registro del motor de deducción")
    opciones.add_argument("--directo", type=Path, help="registro de la detección en directo")
    opciones.add_argument("--seguimiento", type=Path, help="registro de la captura del seguimiento")
    args = opciones.parse_args(argumentos)
    inicio = leer_instante(args.inicio) or datetime.now(UTC)
    estado = componer(
        inicio, datetime.now(UTC), args.codigo, _leer(args.parcial), _leer(args.anterior),
        args.minuto, _leer(args.exportacion), args.exportacion is not None,
        _leer(args.deduccion), args.deduccion is not None,
        _leer(args.directo), args.directo is not None,
        _leer(args.seguimiento), args.seguimiento is not None,
    )  # fmt: skip
    args.salida.write_text(json.dumps(estado, ensure_ascii=False) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(principal())
