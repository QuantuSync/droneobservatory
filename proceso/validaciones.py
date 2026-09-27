"""Validaciones comprobables sin datos externos.

Cada validar_* ejecuta el esquema y después las reglas por código. Las reglas
acceden a los documentos de forma defensiva para poder informar de todo a la
vez aunque el esquema ya haya fallado.
"""

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any, TypeIs

from esquema import Documento, Esquema, validador
from proceso.credibilidad import FIABILIDAD_INTERNA, Fiabilidad
from proceso.estados import Capa, Estado, errores_historial

RADIO_MIN_KM = 0.1
RADIO_MAX_KM = 50
DECIMALES_COORDENADAS = 5
MAX_PALABRAS_FRASE = 25
SEGUNDOS_POR_MINUTO = 60
FORMATOS_INSTANTE = ("%Y-%m-%dT%H:%MZ", "%Y-%m-%dT%H:%M:%SZ")


@dataclass(frozen=True)
class Error:
    ruta: str
    mensaje: str


def _dict(valor: Any) -> Documento:
    return valor if isinstance(valor, dict) else {}


def _lista(valor: Any) -> list[Any]:
    return valor if isinstance(valor, list) else []


def _es_numero(valor: Any) -> TypeIs[int | float]:
    return isinstance(valor, int | float) and not isinstance(valor, bool)


def _nodos(valor: Any, ruta: str = "") -> Iterator[tuple[str, Documento]]:
    """Todos los objetos del documento con su ruta."""
    if isinstance(valor, dict):
        yield ruta, valor
        for clave, hijo in valor.items():
            yield from _nodos(hijo, f"{ruta}.{clave}" if ruta else clave)
    elif isinstance(valor, list):
        for i, hijo in enumerate(valor):
            yield from _nodos(hijo, f"{ruta}[{i}]")


def leer_instante(instante: Any) -> datetime | None:
    """Convierte un instante a datetime UTC; None si la fecha es imposible."""
    valor = _dict(instante).get("valor")
    if not isinstance(valor, str):
        return None
    for formato in FORMATOS_INSTANTE:
        try:
            return datetime.strptime(valor, formato).replace(tzinfo=UTC)
        except ValueError:
            continue
    return None


def derivar_duracion_min(tiempo: Documento) -> int | None:
    inicio = leer_instante(tiempo.get("inicio"))
    fin = leer_instante(tiempo.get("fin"))
    if inicio is None or fin is None or fin < inicio:
        return None
    return int((fin - inicio).total_seconds()) // SEGUNDOS_POR_MINUTO


def _valor_exacto(rango: Any) -> int | None:
    rango = _dict(rango)
    if _es_numero(rango.get("min")) and rango.get("min") == rango.get("max"):
        return int(rango["min"])
    return None


def derivar_proporcion_senuelos(lanzados: Documento) -> float | None:
    """Señuelos entre lanzados; solo derivable si los tres números son exactos."""
    valores = [
        _valor_exacto(lanzados.get(m)) for m in ("shahed_geran", "gerbera_senuelos", "otros")
    ]
    if any(v is None for v in valores):
        return None
    shahed, senuelos, otros = (v or 0 for v in valores)
    total = shahed + senuelos + otros
    return senuelos / total if total else None


# --- Reglas comunes ---------------------------------------------------------


def errores_esquema(esquema: Esquema, documento: Any) -> list[Error]:
    return [
        Error(e.json_path, e.message)
        for e in sorted(validador(esquema).iter_errors(documento), key=lambda e: e.json_path)
    ]


def errores_rangos(documento: Any) -> list[Error]:
    return [
        Error(ruta, f"mínimo {nodo['min']} mayor que máximo {nodo['max']}")
        for ruta, nodo in _nodos(documento)
        if _es_numero(nodo.get("min")) and _es_numero(nodo.get("max")) and nodo["min"] > nodo["max"]
    ]


def errores_fechas(documento: Any, ahora: datetime) -> list[Error]:
    errores: list[Error] = []
    for ruta, nodo in _nodos(documento):
        if set(nodo) != {"valor", "precision"}:
            continue
        momento = leer_instante(nodo)
        if momento is None:
            errores.append(Error(ruta, f"fecha imposible: {nodo.get('valor')}"))
        elif momento > ahora:
            errores.append(Error(ruta, f"fecha futura: {nodo['valor']}"))
    return errores


def errores_coordenadas(documento: Any) -> list[Error]:
    errores: list[Error] = []
    for ruta, nodo in _nodos(documento):
        if set(nodo) != {"lat", "lon"}:
            continue
        for eje in ("lat", "lon"):
            valor = nodo[eje]
            if _es_numero(valor) and round(valor, DECIMALES_COORDENADAS) != valor:
                errores.append(
                    Error(f"{ruta}.{eje}", f"más de {DECIMALES_COORDENADAS} decimales: {valor}")
                )
    return errores


def errores_estado(documento: Documento, capa: Capa) -> list[Error]:
    estado = _dict(documento.get("estado"))
    historial = _lista(estado.get("historial"))
    try:
        errores = [Error("estado", e) for e in errores_historial(estado, capa)]
        pasos = [Estado(str(_dict(p).get("estado"))) for p in historial]
    except (KeyError, ValueError):
        return [Error("estado", "estado o historial mal formado")]

    if (
        Estado.ATRIBUIDO in pasos
        and Estado.CONFIRMADO not in pasos[: pasos.index(Estado.ATRIBUIDO)]
    ):
        errores.append(Error("estado", "atribuido sin confirmado"))

    ids = {_dict(f).get("id") for f in _lista(documento.get("fuentes"))}
    for i, paso in enumerate(historial):
        if _dict(paso).get("fuente_id") not in ids:
            errores.append(Error(f"estado.historial[{i}]", "el cambio cita una fuente inexistente"))

    desmentido = estado.get("actual") == Estado.DESMENTIDO
    motivo = _dict(documento.get("control")).get("motivo_desmentido")
    if desmentido and not motivo:
        errores.append(Error("control.motivo_desmentido", "desmentido sin motivo"))
    if motivo and not desmentido:
        errores.append(Error("control.motivo_desmentido", "motivo de desmentido sin desmentido"))
    return errores


def errores_fuentes(documento: Documento, capa: Capa) -> list[Error]:
    errores: list[Error] = []
    for i, fuente in enumerate(_lista(documento.get("fuentes"))):
        fuente = _dict(fuente)
        ruta = f"fuentes[{i}]"
        frase = fuente.get("frase_origen")
        if isinstance(frase, str) and len(frase.split()) > MAX_PALABRAS_FRASE:
            errores.append(Error(f"{ruta}.frase_origen", f"más de {MAX_PALABRAS_FRASE} palabras"))
        if not fuente.get("publica"):
            continue
        if fuente.get("fiabilidad") in {f.value for f in FIABILIDAD_INTERNA}:
            errores.append(Error(ruta, f"fuente {fuente['fiabilidad']} marcada como pública"))
        if capa is Capa.GENERAL and fuente.get("interna_fuera_de_ucrania"):
            errores.append(
                Error(ruta, "fuente interna fuera de la capa de Ucrania marcada pública")
            )
    return errores


def errores_afirmaciones(documento: Documento) -> list[Error]:
    ids = {_dict(f).get("id") for f in _lista(documento.get("fuentes"))}
    return [
        Error(f"afirmaciones[{i}]", "la afirmación cita una fuente inexistente")
        for i, a in enumerate(_lista(documento.get("afirmaciones")))
        if _dict(a).get("fuente_id") not in ids
    ]


# --- Incidente --------------------------------------------------------------


def _hay_interrupcion(documento: Documento) -> bool:
    consecuencias = _dict(documento.get("consecuencias"))
    cierre_aeropuerto = (
        _dict(consecuencias.get("cierre")).get("valor") == "si"
        and _dict(documento.get("objetivo")).get("categoria") == "aeropuerto"
    )
    vuelos_afectados = any(
        _es_numero(_dict(consecuencias.get(c)).get("min")) and consecuencias[c]["min"] > 0
        for c in ("vuelos_desviados", "vuelos_cancelados", "vuelos_retrasados")
    )
    return cierre_aeropuerto or vuelos_afectados


def errores_tipo(documento: Documento) -> list[Error]:
    tipo = documento.get("tipo")
    errores: list[Error] = []
    if _hay_interrupcion(documento) and tipo != "interrupcion_aeroportuaria":
        errores.append(Error("tipo", "hay interrupción de aeropuerto: manda ese tipo"))
    if tipo == "incursion" and not _lista(documento.get("origen_demostrado_por")):
        errores.append(Error("tipo", "incursión sin origen demostrado por rastreo o restos"))
    return errores


def errores_incidente(documento: Documento, vocabulario_modelos: frozenset[str]) -> list[Error]:
    errores: list[Error] = []

    tiempo = _dict(documento.get("tiempo"))
    inicio, fin = leer_instante(tiempo.get("inicio")), leer_instante(tiempo.get("fin"))
    if inicio and fin and fin < inicio:
        errores.append(Error("tiempo.fin", "fin anterior al inicio"))
    if "duracion_min" in tiempo and tiempo["duracion_min"] != derivar_duracion_min(tiempo):
        errores.append(Error("tiempo.duracion_min", "no coincide con la derivada de inicio y fin"))

    radio = _dict(documento.get("lugar")).get("radio_km")
    if _es_numero(radio) and not RADIO_MIN_KM <= radio <= RADIO_MAX_KM:
        errores.append(Error("lugar.radio_km", f"fuera de {RADIO_MIN_KM} a {RADIO_MAX_KM} km"))

    objetivo = _dict(documento.get("objetivo"))
    if "oaci" in objetivo and objetivo.get("categoria") != "aeropuerto":
        errores.append(Error("objetivo.oaci", "código OACI en un objetivo que no es aeropuerto"))

    modelo = _dict(documento.get("drones")).get("modelo")
    if modelo is not None and modelo not in vocabulario_modelos:
        errores.append(Error("drones.modelo", f"modelo fuera del vocabulario: {modelo}"))

    cierre = _dict(_dict(documento.get("consecuencias")).get("cierre"))
    if "minutos" in cierre and cierre.get("valor") != "si":
        errores.append(Error("consecuencias.cierre.minutos", "minutos de cierre sin cierre"))

    atribuido = _dict(documento.get("estado")).get("actual") == Estado.ATRIBUIDO
    if atribuido and "atribucion" not in documento:
        errores.append(Error("atribucion", "estado atribuido sin atribución"))
    if "atribucion" in documento and not atribuido:
        errores.append(Error("atribucion", "atribución con estado distinto de atribuido"))

    return errores + errores_tipo(documento)


def validar_incidente(
    documento: Documento, ahora: datetime, vocabulario_modelos: frozenset[str]
) -> list[Error]:
    return [
        *errores_esquema(Esquema.INCIDENTE, documento),
        *errores_rangos(documento),
        *errores_fechas(documento, ahora),
        *errores_coordenadas(documento),
        *errores_estado(documento, Capa.GENERAL),
        *errores_fuentes(documento, Capa.GENERAL),
        *errores_afirmaciones(documento),
        *errores_incidente(documento, vocabulario_modelos),
    ]


# --- Capa de Ucrania y episodio ---------------------------------------------


def errores_ataque(documento: Documento) -> list[Error]:
    errores: list[Error] = []
    periodo = _dict(documento.get("periodo"))
    inicio, fin = leer_instante(periodo.get("inicio")), leer_instante(periodo.get("fin"))
    if inicio and fin and fin < inicio:
        errores.append(Error("periodo.fin", "fin anterior al inicio"))
    if "proporcion_senuelos" in documento:
        derivada = derivar_proporcion_senuelos(_dict(documento.get("lanzados")))
        if derivada is not None and derivada != documento["proporcion_senuelos"]:
            errores.append(Error("proporcion_senuelos", "no coincide con la derivada de lanzados"))
    return errores


def validar_ataque_ucrania(documento: Documento, ahora: datetime) -> list[Error]:
    return [
        *errores_esquema(Esquema.ATAQUE_UCRANIA, documento),
        *errores_rangos(documento),
        *errores_fechas(documento, ahora),
        *errores_estado(documento, Capa.UCRANIA),
        *errores_fuentes(documento, Capa.UCRANIA),
        *errores_afirmaciones(documento),
        *errores_ataque(documento),
    ]


def validar_episodio(documento: Documento, ahora: datetime) -> list[Error]:
    errores = errores_esquema(Esquema.EPISODIO, documento)
    noche = documento.get("noche")
    if isinstance(noche, str):
        try:
            if date.fromisoformat(noche) > ahora.date():
                errores.append(Error("noche", f"fecha futura: {noche}"))
        except ValueError:
            errores.append(Error("noche", f"fecha imposible: {noche}"))
    return errores + errores_fechas(documento, ahora)


def fiabilidad_interna(fiabilidad: str) -> bool:
    return Fiabilidad(fiabilidad) in FIABILIDAD_INTERNA
