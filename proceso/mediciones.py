"""Mediciones físicas de cada incidente en la base: tráfico aéreo medido con adsb.lol y
condiciones medidas (meteorología y astronomía). Todo con origen «medido» y método «regla».

Lo llama la recogida horaria con el cerrojo de la base (`recogida/horaria.py`), que ya tiene
la base abierta: el procesado pesado de cada día (`recogida/trafico.py`) corre aparte, con su
propio cerrojo, y aquí solo se leen sus resultados del disco y se escriben en la base, en
segundos. En cada pasada:

1. `zonas.json` para el procesado: los incidentes europeos con su día, su lugar y si están
   confirmados o atribuidos (van primero en el histórico).
2. Cobertura de cada aeropuerto y día nuevo (`cobertura_trafico`) e interferencia GNSS diaria
   por celda (`gnss_diaria`).
3. Interrupciones de todos los aeropuertos con cobertura en cada día con línea base
   (`anomalias_trafico`): casadas con un incidente, explicadas por el tiempo o candidatas.
4. Por incidente, el bloque `trafico_aereo` (cierre medido, respuesta militar e interferencia
   GNSS) y, si hay cierre medido con cobertura, las afirmaciones de la fuente «tráfico aéreo
   medido (adsb.lol)» (fiabilidad B; credibilidad 2 con cobertura alta y 3 con media).
5. Por incidente y por ataque de la capa de guerra, el bloque `condiciones`.

Una evaluación solo se repite si cambia algo de lo que depende (su huella): el incidente, los
días procesados que usa o la versión de la regla.
"""

import hashlib
import json
import logging
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from typing import TYPE_CHECKING, Any

from esquema import Documento
from proceso import condiciones, gnss, metar, trafico, vuelos

if TYPE_CHECKING:
    from almacen.base import Almacen
    from recogida.plazo import Plazo

registro = logging.getLogger("proceso.mediciones")

REGLA_TRAFICO = {"nombre": "trafico_aereo", "version": trafico.VERSION_REGLA.split("-", 1)[1]}
REGLA_CONDICIONES = {"nombre": "condiciones", "version": "1.0.0"}
FUENTE_TRAFICO = "trafico_aereo"
FUENTE_CONDICIONES = "condiciones"
MEDIO_TRAFICO = "Tráfico aéreo medido (adsb.lol)"
MEDIO_CONDICIONES = "Condiciones medidas (Open-Meteo, METAR del IEM)"
FIABILIDAD = "B"
PREVIA_S = 2 * 3600
POSTERIOR_S = 4 * 3600
# Diferencias con lo declarado: más de 15 minutos y más de un 25 % en la duración; más de 2
# vuelos y más de un 30 % en los desvíos.
DIFERENCIA_MINUTOS = 15
DIFERENCIA_FRACCION = 0.25
DIFERENCIA_VUELOS = 2
DIFERENCIA_VUELOS_FRACCION = 0.30
RADIO_CASA_KM = 25.0
ANOMALIA_MINUTOS = 30
ANOMALIA_PERDIDOS = 8
ANOMALIA_FRACCION = 0.8
ESTADOS_PRIORITARIOS = frozenset({"confirmado", "atribuido"})
# Días que hay que esperar a la línea base antes de calcular la cobertura sin ella.
ESPERA_LINEA_BASE = timedelta(days=7)


def ahora_instante(ahora: datetime) -> Documento:
    return {"valor": ahora.astimezone(UTC).strftime("%Y-%m-%dT%H:%MZ"), "precision": "minuto"}


def _inst(texto: str, precision: str = "minuto") -> Documento:
    return {"valor": texto, "precision": precision}


def huella(*partes: Any) -> str:
    texto = json.dumps(partes, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


def vigente(incidente: Documento) -> bool:
    return "fusionado_en" not in incidente and "retirado" not in incidente


# --- Zonas para el procesado ----------------------------------------------------------


def lugar_de(
    incidente: Documento, aeropuertos: dict[str, vuelos.Aeropuerto]
) -> tuple[float, float, str] | None:
    """Punto del incidente: el del lugar o, si no tiene, el del aeropuerto objetivo."""
    punto = incidente.get("lugar", {}).get("punto")
    if punto:
        return float(punto["lat"]), float(punto["lon"]), "punto"
    oaci = incidente.get("objetivo", {}).get("oaci")
    if oaci in aeropuertos:
        a = aeropuertos[oaci]
        return a.lat, a.lon, "aeropuerto"
    return None


def aeropuerto_de(
    incidente: Documento, aeropuertos: dict[str, vuelos.Aeropuerto]
) -> vuelos.Aeropuerto | None:
    oaci = incidente.get("objetivo", {}).get("oaci")
    return aeropuertos.get(oaci) if oaci else None


def dias_ventana(incidente: Documento) -> list[date]:
    """Los días UTC de la ventana del incidente (con su margen posterior y el militar)."""
    inicio, fin, precision = trafico.ventana_incidente(incidente)
    if precision == "dia":
        return _dias(inicio, fin - 1)
    return _dias(inicio - PREVIA_S, fin + POSTERIOR_S)


def zonas(incidentes: Iterable[Documento], aeropuertos: dict[str, vuelos.Aeropuerto]) -> Documento:
    lista = []
    for i in incidentes:
        if not vigente(i):
            continue
        lugar = lugar_de(i, aeropuertos)
        aeropuerto = aeropuerto_de(i, aeropuertos)
        lista.append(
            {
                "id": i["id"],
                "dia": i["tiempo"]["inicio"]["valor"][:10],
                "dias": [d.isoformat() for d in dias_ventana(i)],
                "lat": None if lugar is None else round(lugar[0], 4),
                "lon": None if lugar is None else round(lugar[1], 4),
                "oaci": aeropuerto.oaci if aeropuerto else None,
                "prioritario": i["estado"]["actual"] in ESTADOS_PRIORITARIOS,
            }
        )
    return {"incidentes": sorted(lista, key=lambda x: x["id"])}


# --- Cobertura, GNSS diaria y anomalías ------------------------------------------------


@dataclass
class Entorno:
    """Lo que hace falta para evaluar: los días procesados y sus referencias."""

    lector: trafico.LectorDias
    procesados: list[date]
    perdidos: set[date]
    referencias: Callable[[str, date], trafico.Referencia | None]
    metares: Callable[[str, float, float], list[metar.Metar]]
    resumen: Callable[[date], Documento | None]
    aeropuertos: dict[str, vuelos.Aeropuerto] = field(default_factory=dict)
    _coberturas: dict[tuple[str, date], trafico.Cobertura | None] = field(default_factory=dict)

    def cobertura(self, oaci: str, dia: date) -> trafico.Cobertura | None:
        clave = (oaci, dia)
        if clave not in self._coberturas:
            self._coberturas[clave] = trafico.cobertura(oaci, dia, self.lector, self.referencias)
        return self._coberturas[clave]

    def valido(self, oaci: str) -> Callable[[date], bool]:
        """Si un día sirve de línea base para el aeropuerto: procesado y con cobertura. Sin
        referencia de EUROCONTROL, la cobertura de un día de la línea base saldría de su propia
        línea base, en cadena: basta con que tenga 20 movimientos o más."""

        def comprobar(dia: date) -> bool:
            if self.referencias(oaci, dia) is None:
                datos = self.lector(dia)
                if datos is None:
                    return False
                vistos = len(trafico.movimientos_ifr(datos.movimientos.get(oaci, [])))
                return vistos >= trafico.MEDIANA_PROPIA_MINIMA
            c = self.cobertura(oaci, dia)
            return c is not None and c.nivel != trafico.INSUFICIENTE

        return comprobar


def base_disponible(entorno: Entorno, dia: date) -> int:
    procesados = set(entorno.procesados)
    return sum(1 for d in trafico.dias_base(dia) if d in procesados)


def coberturas_nuevas(almacen: "Almacen", entorno: Entorno, hoy: date, plazo: "Plazo") -> int:
    hechos = {
        (c["oaci"], c["dia"]) for c in almacen.coberturas() if c["version"] == trafico.VERSION_REGLA
    }
    hechos_dias = {d for _, d in hechos}
    nuevas = 0
    for dia in entorno.procesados:
        if dia.isoformat() in hechos_dias or plazo.agotado():
            continue
        resumen = entorno.resumen(dia) or {}
        procesado = datetime.fromisoformat(
            str(resumen.get("procesado", "1970-01-01T00:00:00Z")).replace("Z", "+00:00")
        )
        if (
            base_disponible(entorno, dia) < trafico.DIAS_BASE_MINIMOS
            and hoy - procesado.date() < ESPERA_LINEA_BASE
        ):
            continue
        filas = []
        for a in entorno.aeropuertos.values():
            if not a.regular:
                continue
            c = entorno.cobertura(a.oaci, dia)
            if c is not None and (c.vistos or c.referencia is not None):
                filas.append(c.documento())
        nuevas += almacen.guardar_coberturas(trafico.VERSION_REGLA, filas)
    return nuevas


def gnss_nuevas(almacen: "Almacen", entorno: Entorno, plazo: "Plazo") -> int:
    """Celdas con el mínimo de aeronaves en el día y al menos una degradada de más (la que se
    resta): las demás celdas con aeronaves suficientes no tienen interferencia ese día."""
    hechos = almacen.dias_gnss(trafico.VERSION_REGLA)
    nuevas = 0
    for dia in entorno.procesados:
        if dia.isoformat() in hechos or plazo.agotado():
            continue
        datos = entorno.lector(dia)
        gnss_dia = None if datos is None else datos.detalle("gnss_dia")
        if gnss_dia is None:
            continue
        filas = [(c, n, m) for c, n, m in gnss_dia if n >= gnss.MINIMO_DIA and m >= 2]
        # Un día sin ninguna celda con interferencia deja una fila vacía de control.
        filas = filas or [("000000000000000", 0, 0)]
        nuevas += almacen.guardar_gnss_diaria(trafico.VERSION_REGLA, dia.isoformat(), filas)
    return nuevas


def _incidentes_por_aeropuerto(
    incidentes: Iterable[Documento], aeropuertos: dict[str, vuelos.Aeropuerto]
) -> dict[str, list[Documento]]:
    resultado: dict[str, list[Documento]] = {}
    for i in incidentes:
        if not vigente(i):
            continue
        a = aeropuerto_de(i, aeropuertos)
        if a is not None:
            resultado.setdefault(a.oaci, []).append(i)
            continue
        lugar = i.get("lugar", {}).get("punto")
        if lugar:
            for otro in aeropuertos.values():
                if (
                    vuelos.distancia_km(lugar["lat"], lugar["lon"], otro.lat, otro.lon)
                    <= RADIO_CASA_KM
                ):
                    resultado.setdefault(otro.oaci, []).append(i)
    return resultado


def casa(interrupcion: trafico.Interrupcion, incidente: Documento) -> bool:
    """La interrupción coincide con el incidente: se solapan con una hora de margen."""
    inicio, fin, _ = trafico.ventana_incidente(incidente)
    margen = trafico.CASA_INCIDENTE.total_seconds()
    return interrupcion.inicio <= fin + margen and interrupcion.fin >= inicio - margen


def significativa(interrupcion: trafico.Interrupcion) -> bool:
    """Un hueco real (sin tráfico entre dos movimientos, o con el 80 % o más de lo esperado
    perdido: Múnich el 3 de octubre de 2025 perdió 97 de 97 con algún movimiento suelto) de 30
    minutos o más con 8 movimientos perdidos o más. Las interrupciones más cortas o pequeñas, o
    donde el tráfico solo bajó, son la variación de un día normal (unas 20 por día en Europa,
    medido en septiembre de 2025): quedan como «menor». Para casar con un incidente cuentan
    todas."""
    perdidos = interrupcion.llegadas_perdidas + interrupcion.salidas_perdidas
    base = interrupcion.llegadas_base + interrupcion.salidas_base
    casi_parado = base > 0 and perdidos >= ANOMALIA_FRACCION * base
    return (
        (interrupcion.precision == "movimientos" or casi_parado)
        and interrupcion.duracion_min >= ANOMALIA_MINUTOS
        and perdidos >= ANOMALIA_PERDIDOS
    )


def anomalias_nuevas(
    almacen: "Almacen",
    entorno: Entorno,
    incidentes: list[Documento],
    ahora: datetime,
    plazo: "Plazo",
) -> int:
    """Interrupciones de todos los aeropuertos con cobertura en cada día con línea base."""
    cursor = almacen.cursor(FUENTE_TRAFICO) or {}
    hechas: dict[str, int] = dict(cursor.get("anomalias", {}))
    por_aeropuerto = _incidentes_por_aeropuerto(incidentes, entorno.aeropuertos)
    guardadas = 0
    for dia in entorno.procesados:
        if plazo.agotado():
            break
        semanas = base_disponible(entorno, dia)
        if semanas < trafico.DIAS_BASE_MINIMOS or hechas.get(dia.isoformat(), 0) >= semanas:
            continue
        datos = entorno.lector(dia)
        if datos is None:
            continue
        inicio = trafico.inicio_dia(dia)
        completo = True
        for oaci, a in sorted(entorno.aeropuertos.items()):
            if plazo.agotado():
                completo = False  # el día se termina en la ejecución siguiente
                break
            if not a.regular:
                continue
            c = entorno.cobertura(oaci, dia)
            if c is None or c.nivel == trafico.INSUFICIENTE:
                continue
            encontradas = trafico.interrupciones(
                oaci, inicio, inicio + 86400, entorno.lector, entorno.valido(oaci), entorno.metares
            )
            for interrupcion in encontradas or []:
                casadas = sorted(
                    i["id"] for i in por_aeropuerto.get(oaci, []) if casa(interrupcion, i)
                )
                estado = (
                    "casada"
                    if casadas
                    else "meteorologia"
                    if interrupcion.motivos_meteorologicos
                    else "candidata"
                    if significativa(interrupcion)
                    else "menor"
                )
                documento = {
                    **interrupcion.documento(),
                    "estado": estado,
                    "cobertura": _cobertura_doc(c),
                    "datos": datos.pagina,
                    "regla": REGLA_TRAFICO,
                    "evaluado": ahora_instante(ahora),
                }
                if casadas:
                    documento["incidentes"] = casadas
                del documento["oaci"]
                guardadas += almacen.guardar_anomalia({"oaci": oaci, **documento})
        if completo:
            hechas[dia.isoformat()] = semanas
    almacen.guardar_cursor(FUENTE_TRAFICO, {**cursor, "anomalias": dict(sorted(hechas.items()))})
    return guardadas


def _cobertura_doc(c: trafico.Cobertura) -> Documento:
    d = c.documento()
    return {
        k: d[k] for k in ("nivel", "vistos", "referencia", "origen_referencia", "indice") if k in d
    }


# --- Tráfico aéreo de un incidente ------------------------------------------------------


def _dias(desde: float, hasta: float) -> list[date]:
    dia = datetime.fromtimestamp(desde, UTC).date()
    fin = datetime.fromtimestamp(hasta, UTC).date()
    resultado = []
    while dia <= fin:
        resultado.append(dia)
        dia += timedelta(days=1)
    return resultado


def recortar(entorno: Entorno, dia: date, desde: float, hasta: float) -> tuple[float, float]:
    """La ventana [desde, hasta) recortada a los días procesados seguidos alrededor del día del
    incidente: una ventana que pasa de medianoche se evalúa hasta donde haya datos."""
    procesados = set(entorno.procesados)
    primero = dia
    while primero - timedelta(days=1) in procesados and trafico.inicio_dia(primero) > desde:
        primero -= timedelta(days=1)
    ultimo = dia
    while ultimo + timedelta(days=1) in procesados and trafico.inicio_dia(ultimo) + 86400 < hasta:
        ultimo += timedelta(days=1)
    return max(desde, trafico.inicio_dia(primero)), min(hasta, trafico.inicio_dia(ultimo) + 86400)


def _alinear(t: float) -> float:
    return t - t % trafico.FRANJA_S


def _rango_medio(rango: Any) -> float | None:
    if isinstance(rango, dict) and "min" in rango:
        return (float(rango["min"]) + float(rango["max"])) / 2
    return None


def diferencias(cierre: Documento, consecuencias: Documento) -> list[str]:
    resultado = []
    declarado = consecuencias.get("cierre", {})
    if declarado.get("valor") == "no":
        resultado.append("cierre")
    minutos = _rango_medio(declarado.get("minutos"))
    medida = cierre["duracion_min"]
    if minutos is not None:
        rango = declarado["minutos"]
        fuera = (
            medida < rango["min"] - DIFERENCIA_MINUTOS or medida > rango["max"] + DIFERENCIA_MINUTOS
        )
        if fuera and abs(medida - minutos) > DIFERENCIA_FRACCION * max(minutos, 1):
            resultado.append("duracion")
    desviados = consecuencias.get("vuelos_desviados")
    if isinstance(desviados, dict):
        medidos = cierre["vuelos_desviados"]
        fuera = (
            medidos < desviados["min"] - DIFERENCIA_VUELOS
            or medidos > desviados["max"] + DIFERENCIA_VUELOS
        )
        medio = (desviados["min"] + desviados["max"]) / 2
        if fuera and abs(medidos - medio) > DIFERENCIA_VUELOS_FRACCION * max(medio, 1):
            resultado.append("vuelos_desviados")
    return resultado


def _cierre(
    incidente: Documento,
    aeropuerto: vuelos.Aeropuerto | None,
    entorno: Entorno,
    inicio: float,
    fin: float,
    precision: str,
) -> tuple[Documento, list[str]]:
    """El bloque cierre y las páginas de adsb.lol usadas."""
    if aeropuerto is None or not aeropuerto.regular:
        return {"resultado": "no_aplicable"}, []
    if precision == "dia":
        w0, w1 = inicio, fin
    else:
        w0, w1 = _alinear(inicio - PREVIA_S), _alinear(fin + POSTERIOR_S) + trafico.FRANJA_S
    dia_incidente = datetime.fromtimestamp(inicio, UTC).date()
    w0, w1 = recortar(entorno, dia_incidente, w0, w1)
    if any(d in entorno.perdidos for d in _dias(w0, w1 - 1)):
        return {"resultado": "sin_datos", "aeropuerto": aeropuerto.oaci}, []
    # La ventana se queda en los días con cobertura alrededor del del incidente: el día
    # siguiente sin cobertura (o aún sin línea base propia) no tumba la medida del incidente.
    for d in _dias(w0, w1 - 1):
        c = entorno.cobertura(aeropuerto.oaci, d)
        if d > dia_incidente and (c is None or c.nivel == trafico.INSUFICIENTE):
            w1 = min(w1, trafico.inicio_dia(d))
            break
    dias = _dias(w0, w1 - 1)
    datos = [entorno.lector(d) for d in dias]
    paginas = sorted({d.pagina for d in datos if d is not None})
    coberturas = [entorno.cobertura(aeropuerto.oaci, d) for d in dias]
    peor = min(
        (c for c in coberturas if c is not None), key=lambda c: c.indice or 0.0, default=None
    )
    base: Documento = {"aeropuerto": aeropuerto.oaci}
    if peor is not None:
        base["cobertura"] = _cobertura_doc(peor)
    if peor is None or peor.nivel == trafico.INSUFICIENTE:
        return {"resultado": "cobertura_insuficiente", **base}, paginas
    encontradas = trafico.interrupciones(
        aeropuerto.oaci, w0, w1, entorno.lector, entorno.valido(aeropuerto.oaci), entorno.metares
    )
    if encontradas is None:
        return {"resultado": "sin_linea_base", **base}, paginas
    margen = trafico.CASA_INCIDENTE.total_seconds()
    casadas = [i for i in encontradas if i.inicio <= fin + margen and i.fin >= inicio - margen]
    if precision == "dia":
        # Con solo el día, un bajón corto de cualquier hora casaría por azar: solo cuenta una
        # interrupción significativa (un hueco real de 30 minutos y 8 movimientos perdidos).
        casadas = [i for i in casadas if significativa(i)]
    if not casadas:
        # Sin interrupción, o sin tráfico que pueda interrumpirse (de madrugada): se dice cuál
        # y se guardan las esperas y los desvíos de la ventana del incidente como indicios.
        indicios = trafico.indicios(
            aeropuerto.oaci, inicio, fin, w0, w1, entorno.lector, entorno.valido(aeropuerto.oaci)
        )
        resultado = (
            "sin_trafico_esperado"
            if indicios["base_ventana"] < trafico.BASE_TRAMO_MINIMA
            else "sin_interrupcion"
        )
        return {
            "resultado": resultado,
            **base,
            "otras_interrupciones": len(encontradas),
            "indicios": indicios,
        }, paginas
    elegida = max(casadas, key=lambda i: (i.llegadas_perdidas + i.salidas_perdidas, i.duracion_min))
    cierre: Documento = {
        "resultado": "cierre_medido",
        **base,
        "inicio": _inst(trafico.instante(elegida.inicio)),
        "fin": _inst(trafico.instante(elegida.fin)),
        "duracion_min": elegida.duracion_min,
        "vuelos_desviados": elegida.desvios,
        "vuelos_en_espera": elegida.esperas,
        "aproximaciones_frustradas": elegida.frustradas,
        "llegadas_perdidas": elegida.llegadas_perdidas,
        "salidas_perdidas": elegida.salidas_perdidas,
        "precision_bordes": elegida.precision,
        "linea_base": {
            "semanas": elegida.semanas_base,
            "llegadas": round(elegida.llegadas_base, 1),
            "salidas": round(elegida.salidas_base, 1),
            "llegadas_vistas": elegida.llegadas_vistas,
            "salidas_vistas": elegida.salidas_vistas,
            "esperas": round(elegida.esperas_base, 1),
            "frustradas": round(elegida.frustradas_base, 1),
            "desvios": round(elegida.desvios_base, 1),
        },
        "motivos_meteorologicos": elegida.motivos_meteorologicos,
        "otras_interrupciones": len(encontradas) - 1,
    }
    consecuencias = incidente.get("consecuencias", {})
    declarado = {}
    if "minutos" in consecuencias.get("cierre", {}):
        declarado["minutos"] = consecuencias["cierre"]["minutos"]
    if "vuelos_desviados" in consecuencias:
        declarado["vuelos_desviados"] = consecuencias["vuelos_desviados"]
    if declarado:
        cierre["declarado"] = declarado
    distintas = diferencias(cierre, consecuencias)
    cierre["diferencias"] = distintas
    cierre["difiere_de_declarado"] = bool(distintas)
    return cierre, paginas


def _militar(
    lugar: tuple[float, float, str] | None, entorno: Entorno, inicio: float, fin: float
) -> Documento:
    if lugar is None:
        return {"resultado": "sin_lugar"}
    desde, hasta = recortar(
        entorno,
        datetime.fromtimestamp(inicio, UTC).date(),
        inicio - trafico.MARGEN_MILITAR.total_seconds(),
        fin + trafico.MARGEN_MILITAR.total_seconds(),
    )
    dias = _dias(desde, hasta - 1)
    militares: list[dict[str, Any]] = []
    for d in dias:
        datos = entorno.lector(d)
        del_dia = None if datos is None else datos.detalle("militares")
        if del_dia is None:
            return {"resultado": "sin_datos"}
        militares += del_dia
    documento = trafico.respuesta_militar(lugar[0], lugar[1], desde, hasta, militares)
    documento["ventana"] = {k: _inst(v) for k, v in documento["ventana"].items()}
    documento["detalle"] = [{**v, "primera": _inst(v["primera"])} for v in documento["detalle"]]
    if "primera" in documento:
        documento["primera"] = _inst(documento["primera"])
    return {"resultado": "vistas" if documento["aeronaves"] else "ninguna_vista", **documento}


def _gnss(
    lugar: tuple[float, float, str] | None, entorno: Entorno, inicio: float, fin: float
) -> Documento:
    if lugar is None:
        return {"resultado": "sin_lugar"}
    filas: list[tuple[int, str, int, int]] = []
    for d in _dias(inicio, fin - 1):
        datos = entorno.lector(d)
        por_hora = None if datos is None else datos.detalle("gnss_hora")
        if por_hora is None:
            return {"resultado": "sin_datos"}
        filas += por_hora
    documento = trafico.interferencia(lugar[0], lugar[1], inicio, fin, filas)
    documento["ventana"] = {k: _inst(v) for k, v in documento["ventana"].items()}
    return {"resultado": "medida", **documento}


def dias_necesarios(incidente: Documento) -> list[date]:
    inicio, fin, precision = trafico.ventana_incidente(incidente)
    if precision == "dia":
        ventana = _dias(inicio, fin - 1)
    else:
        ventana = _dias(inicio - PREVIA_S, fin + POSTERIOR_S)
    todos = set(ventana)
    for d in ventana:
        todos.update(trafico.dias_base(d))
    todos.update(
        _dias(
            inicio - trafico.MARGEN_MILITAR.total_seconds(),
            fin + trafico.MARGEN_MILITAR.total_seconds(),
        )
    )
    return sorted(todos)


def evaluar_incidente(incidente: Documento, entorno: Entorno, ahora: datetime) -> Documento | None:
    """El bloque trafico_aereo del incidente; None si aún falta algún día de la ventana."""
    inicio, fin, precision = trafico.ventana_incidente(incidente)
    ventana_dias = _dias(inicio, fin - 1)
    procesados = set(entorno.procesados)
    if not all(d in procesados or d in entorno.perdidos for d in ventana_dias):
        return None
    aeropuerto = aeropuerto_de(incidente, entorno.aeropuertos)
    lugar = lugar_de(incidente, entorno.aeropuertos)
    cierre, paginas = _cierre(incidente, aeropuerto, entorno, inicio, fin, precision)
    documento: Documento = {
        "cierre": cierre,
        "respuesta_militar": _militar(lugar, entorno, inicio, fin),
        "interferencia_gnss": _gnss(lugar, entorno, inicio, fin),
        "ventana": {"inicio": _inst(trafico.instante(inicio)), "fin": _inst(trafico.instante(fin))},
        "precision_incidente": incidente["tiempo"]["inicio"]["precision"],
        "origen": "medido",
        "metodo": "regla",
        "regla": REGLA_TRAFICO,
        "evaluado": ahora_instante(ahora),
    }
    if paginas:
        documento["datos"] = paginas
    return documento


def huella_incidente(incidente: Documento, entorno: Entorno) -> str:
    dias = dias_necesarios(incidente)
    procesados = {d.isoformat(): (entorno.resumen(d) or {}).get("procesado") for d in dias}
    return huella(
        trafico.VERSION_REGLA,
        incidente.get("tiempo"),
        incidente.get("lugar", {}).get("punto"),
        incidente.get("objetivo", {}).get("oaci"),
        incidente.get("consecuencias"),
        procesados,
        sorted(d.isoformat() for d in dias if d in entorno.perdidos),
    )


def fuente_trafico(
    incidente_id: str, cierre: Documento, paginas: list[str], credibilidad: int
) -> Documento:
    dia = cierre["inicio"]["valor"][:10]
    frase = (
        f"Cierre medido en {cierre['aeropuerto']}: {cierre['inicio']['valor'][11:16]}–"
        f"{cierre['fin']['valor'][11:16]} UTC, {cierre['duracion_min']} minutos, "
        f"{cierre['vuelos_desviados']} desvíos y {cierre['vuelos_en_espera']} esperas."
    )
    return {
        "id": f"adsblol-{cierre['aeropuerto']}-{dia}-{incidente_id}",
        "enlace": paginas[0],
        "medio": MEDIO_TRAFICO,
        "fecha": {"valor": f"{dia}T00:00Z", "precision": "dia"},
        "idioma": "es",
        "fiabilidad": FIABILIDAD,
        "credibilidad": credibilidad,
        "frase_origen": frase,
        "replicas": 0,
        "campos_respaldados": ["cierre", "cierre_minutos", "vuelos_desviados"],
        "es_autoridad": False,
        "publica": True,
    }


def afirmaciones_trafico(
    fuente: Documento, cierre: Documento, credibilidad: int
) -> list[Documento]:
    comunes = {
        "fuente_id": fuente["id"],
        "confianza_extraccion": 1.0,
        "credibilidad": credibilidad,
        "origen": "medido",
        "metodo": "regla",
    }
    d, v = cierre["duracion_min"], cierre["vuelos_desviados"]
    return [
        {"campo": "cierre", "valor": "si", **comunes},
        {"campo": "cierre_minutos", "valor": {"min": d, "max": d}, **comunes},
        {"campo": "vuelos_desviados", "valor": {"min": v, "max": v}, **comunes},
    ]


@dataclass
class ResumenTrafico:
    coberturas: int = 0
    gnss: int = 0
    anomalias: int = 0
    evaluados: int = 0
    cambiados: int = 0
    pendientes: int = 0
    cierres: int = 0

    def texto(self) -> str:
        return (
            f"{self.coberturas} coberturas, {self.gnss} celdas GNSS, "
            f"{self.anomalias} interrupciones, {self.evaluados} incidentes evaluados "
            f"({self.cambiados} cambiados, {self.cierres} con "
            f"cierre medido), {self.pendientes} pendientes"
        )


def evaluar_trafico(
    almacen: "Almacen", entorno: Entorno, ahora: datetime, plazo: "Plazo"
) -> ResumenTrafico:
    resumen = ResumenTrafico()
    incidentes = [i for i in almacen.incidentes() if vigente(i)]
    resumen.coberturas = coberturas_nuevas(almacen, entorno, ahora.date(), plazo)
    resumen.gnss = gnss_nuevas(almacen, entorno, plazo)
    guardados = almacen.trafico_aereo()
    # Por fecha: los incidentes cercanos comparten días y línea base en la caché.
    for incidente in sorted(incidentes, key=lambda i: (i["tiempo"]["inicio"]["valor"], i["id"])):
        if plazo.agotado():
            break
        anterior = guardados.get(incidente["id"])
        firma = huella_incidente(incidente, entorno)
        if anterior is not None and anterior.get("huella") == firma:
            resumen.cierres += anterior["cierre"]["resultado"] == "cierre_medido"
            continue
        documento = evaluar_incidente(incidente, entorno, ahora)
        if documento is None:
            resumen.pendientes += 1
            continue
        documento["huella"] = firma
        resumen.evaluados += 1
        cierre = documento["cierre"]
        nivel = cierre.get("cobertura", {}).get("nivel")
        if cierre["resultado"] == "cierre_medido" and nivel in trafico.CREDIBILIDAD:
            credibilidad = trafico.CREDIBILIDAD[nivel]
            fuente = fuente_trafico(
                incidente["id"], cierre, documento.get("datos", []), credibilidad
            )
            documento["fuente_id"] = fuente["id"]
            almacen.guardar_fuente(fuente)
            almacen.guardar_afirmaciones(
                incidente["id"], afirmaciones_trafico(fuente, cierre, credibilidad)
            )
            resumen.cierres += 1
        resumen.cambiados += almacen.guardar_trafico_aereo(incidente["id"], documento)
    # Las interrupciones de todos los aeropuertos, después de los incidentes y con lo que quede
    # del tope: mientras avanza el histórico se acumulan más días de los que caben en una
    # ejecución (el 1 de octubre de 2026, dos ejecuciones seguidas se fueron enteras en ellas
    # sin evaluar ningún incidente); el cursor sigue donde se quedó.
    resumen.anomalias = anomalias_nuevas(almacen, entorno, incidentes, ahora, plazo)
    return resumen


# --- Publicación ------------------------------------------------------------------------


def solo_publico(documento: Documento) -> None:
    """Deja el bloque trafico_aereo solo si hay un cierre medido válido (con cobertura alta o
    media); la proyección sobre la lista cerrada quita lo interno."""
    bloque = documento.get("trafico_aereo")
    if bloque is None:
        return
    cierre = bloque.get("cierre", {})
    if (
        cierre.get("resultado") != "cierre_medido"
        or cierre.get("cobertura", {}).get("nivel") not in trafico.CREDIBILIDAD
    ):
        del documento["trafico_aereo"]


def con_mediciones(
    incidentes: Iterable[Documento], ataques: Iterable[Documento], almacen: "Almacen"
) -> tuple[list[Documento], list[Documento]]:
    """Copias de los incidentes con sus bloques trafico_aereo y condiciones, y con la fuente y
    las afirmaciones del tráfico medido cuando hay cierre medido; y de los ataques con sus
    condiciones. Los documentos guardados no los llevan: viven en sus tablas."""
    medidos = almacen.trafico_aereo()
    medidas = almacen.condiciones()
    fuentes = almacen.fuentes()
    con_incidentes = []
    for i in incidentes:
        extra: Documento = {}
        bloque = medidos.get(i.get("id", ""))
        if bloque is not None:
            extra["trafico_aereo"] = bloque
            fuente = fuentes.get(bloque.get("fuente_id", ""))
            if fuente is not None:
                nivel = bloque["cierre"].get("cobertura", {}).get("nivel")
                credibilidad = trafico.CREDIBILIDAD.get(nivel or "", 3)
                extra["fuentes"] = [*i["fuentes"], {**fuente, "credibilidad": credibilidad}]
                extra["afirmaciones"] = [
                    *i.get("afirmaciones", []),
                    *afirmaciones_trafico(fuente, bloque["cierre"], credibilidad),
                ]
        if i.get("id") in medidas:
            extra["condiciones"] = medidas[i["id"]]
        con_incidentes.append({**i, **extra} if extra else i)
    con_ataques = [
        {**a, "condiciones": medidas[a["id"]]} if a.get("id") in medidas else a for a in ataques
    ]
    return con_incidentes, con_ataques


# --- Condiciones medidas ----------------------------------------------------------------


@dataclass
class ResumenCondiciones:
    evaluados: int = 0
    cambiados: int = 0
    pendientes: int = 0
    ataques: int = 0

    def texto(self) -> str:
        return (
            f"{self.evaluados} incidentes ({self.cambiados} cambiados), {self.ataques} ataques, "
            f"{self.pendientes} pendientes del cupo de Open-Meteo"
        )


URL_OPEN_METEO = "https://open-meteo.com/"
URL_IEM = "https://mesonet.agron.iastate.edu/request/download.phtml"


def fuente_condiciones(entidad_id: str, dia: str) -> Documento:
    return {
        "id": f"condiciones-{entidad_id}",
        "enlace": URL_OPEN_METEO,
        "medio": MEDIO_CONDICIONES,
        "fecha": {"valor": f"{dia}T00:00Z", "precision": "dia"},
        "idioma": "es",
        "fiabilidad": FIABILIDAD,
        "credibilidad": 2,
        "frase_origen": (
            "Meteorología de Open-Meteo, METAR del Iowa Environmental Mesonet y sol y luna "
            "calculados."
        ),
        "replicas": 0,
        "es_autoridad": False,
        "publica": False,
    }


def _meta_condiciones(
    entidad_id: str, firma: str, ahora: datetime, fuentes: list[str]
) -> Documento:
    return {
        "fuentes": sorted(set(fuentes)),
        "fuente_id": f"condiciones-{entidad_id}",
        "origen": "medido",
        "metodo": "regla",
        "regla": REGLA_CONDICIONES,
        "huella": firma,
        "evaluado": ahora_instante(ahora),
    }


def condiciones_incidente(
    incidente: Documento,
    aeropuertos: dict[str, vuelos.Aeropuerto],
    pedir: condiciones.PedirHorario,
    metares_de: Callable[[str, date], list[metar.Metar]],
    firma: str,
    ahora: datetime,
) -> Documento | None:
    """El bloque condiciones del incidente; None si no queda cupo de Open-Meteo."""
    lugar = lugar_de(incidente, aeropuertos)
    meta = _meta_condiciones(incidente["id"], firma, ahora, [URL_OPEN_METEO])
    if lugar is None:
        return {"origen_lugar": "sin_lugar", **meta}
    lat, lon, origen = lugar
    inicio = trafico.leer_instante(incidente["tiempo"]["inicio"]["valor"])
    precision = incidente["tiempo"]["inicio"]["precision"]
    momento = None if precision == "dia" else inicio
    dia = inicio.date()
    horario = pedir([(lat, lon)], dia, "incidente")[0]
    if horario is None:
        return None
    oaci = incidente.get("objetivo", {}).get("oaci")
    estacion = condiciones.estacion_metar(lat, lon, oaci, aeropuertos)
    metares = metares_de(estacion[0], dia) if estacion else []
    if estacion and metares:
        meta["fuentes"] = sorted({*meta["fuentes"], URL_IEM})
    bloque = condiciones.lugar_incidente(None, lat, lon, momento, dia, horario, metares, estacion)
    return {"lugar": bloque, "origen_lugar": origen, **meta}


def condiciones_ataque(
    ataque: Documento, pedir: condiciones.PedirHorario, firma: str, ahora: datetime
) -> Documento | None:
    lanzamiento, impacto = condiciones.puntos_ataque(ataque)
    meta = _meta_condiciones(ataque["id"], firma, ahora, [URL_OPEN_METEO])
    if not lanzamiento and not impacto:
        return {"origen_lugar": "sin_lugar", **meta}
    inicio = trafico.leer_instante(ataque["periodo"]["inicio"]["valor"])
    fin_texto = ataque["periodo"].get("fin", {}).get("valor")
    fin = trafico.leer_instante(fin_texto) if fin_texto else inicio
    medio = inicio + (max(fin, inicio) - inicio) / 2
    documento: Documento = {"origen_lugar": "zonas_del_parte", **meta}
    for clave, puntos, momento in (
        ("lanzamiento", lanzamiento, inicio),
        ("impacto", impacto, medio),
    ):
        if not puntos:
            continue
        horarios = pedir([(la, lo) for _, la, lo in puntos], momento.date(), "guerra")
        if any(h is None for h in horarios):
            return None
        documento[clave] = [
            condiciones.lugar_viento(nombre, la, lo, momento, h or {})
            for (nombre, la, lo), h in zip(puntos, horarios, strict=True)
        ]
    return documento


def evaluar_condiciones(
    almacen: "Almacen",
    aeropuertos: dict[str, vuelos.Aeropuerto],
    pedir: condiciones.PedirHorario,
    metares_de: Callable[[str, date], list[metar.Metar]],
    ahora: datetime,
    plazo: "Plazo",
) -> ResumenCondiciones:
    """Condiciones de los incidentes y de los ataques RU→UA que aún no las tienen o cuyo
    momento o lugar ha cambiado, de los más recientes a los más antiguos."""
    resumen = ResumenCondiciones()
    guardadas = almacen.condiciones()
    entidades: list[tuple[str, Documento, str]] = []
    for i in almacen.incidentes():
        if vigente(i):
            firma = huella(
                REGLA_CONDICIONES,
                i.get("tiempo", {}).get("inicio"),
                i.get("lugar", {}).get("punto"),
                i.get("objetivo", {}).get("oaci"),
            )
            entidades.append(("incidente", i, firma))
    for a in almacen.ataques_ucrania():
        if a.get("sentido") == "RU_UA":
            firma = huella(
                REGLA_CONDICIONES,
                a.get("periodo"),
                a.get("zonas_lanzamiento"),
                [r.get("region") for r in a.get("regiones") or []],
            )
            entidades.append(("ataque", a, firma))

    def fecha(e: tuple[str, Documento, str]) -> str:
        d = e[1]
        return str(
            (d.get("tiempo") or {}).get("inicio", {}).get("valor")
            or d["periodo"]["inicio"]["valor"]
        )

    for tipo, documento, firma in sorted(entidades, key=fecha, reverse=True):
        if plazo.agotado():
            break
        anterior = guardadas.get(documento["id"])
        if anterior is not None and anterior.get("huella") == firma:
            continue
        if tipo == "incidente":
            bloque = condiciones_incidente(documento, aeropuertos, pedir, metares_de, firma, ahora)
        else:
            bloque = condiciones_ataque(documento, pedir, firma, ahora)
        if bloque is None:
            resumen.pendientes += 1
            break  # sin cupo de Open-Meteo en esta ejecución
        dia = fecha((tipo, documento, firma))[:10]
        almacen.guardar_fuente(fuente_condiciones(documento["id"], dia))
        cambiado = almacen.guardar_condiciones(documento["id"], bloque)
        if tipo == "incidente":
            resumen.evaluados += 1
            resumen.cambiados += cambiado
        else:
            resumen.ataques += 1
    return resumen
