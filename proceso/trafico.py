"""Cobertura, interrupciones, respuesta militar e interferencia GNSS a partir de los días
procesados de adsb.lol (`recogida/trafico.py`).

**Cobertura por aeropuerto y día.** Aterrizajes y despegues de aviones de transporte o de
negocios vistos (los que vuelan en IFR: `proceso/aeronaves.es_ifr`) frente a la referencia:
los vuelos IFR del día de EUROCONTROL (Aviation Intelligence Portal, «Airport traffic»); si
EUROCONTROL aún no ha publicado el día, la mediana del mismo día de la semana de sus cuatro
últimas semanas publicadas; y si el aeropuerto no está en EUROCONTROL, la mediana de la propia
serie en los días de la línea base. Índice = vistos / referencia. Con referencia de
EUROCONTROL: alta desde 0,80, media desde 0,50 y por debajo insuficiente. Con la mediana
propia no se sabe cuánto se ve de verdad, así que como mucho es media: media si la mediana es
de 20 movimientos o más y el día llega a 0,75 de ella. Con cobertura insuficiente no se
interpreta ningún hueco en ese aeropuerto ese día.

**Interrupciones.** Por franjas de 15 minutos, aterrizajes más despegues frente a la línea
base: la mediana de la misma franja el mismo día de la semana de las cuatro semanas
anteriores (al menos dos de esos días procesados y con cobertura). Una franja es baja si su
base es de 2 movimientos o más y se ve el 30 % o menos. Las franjas bajas seguidas (con una
franja intermedia que llegue a la mitad de su base como mucho) forman un tramo; el tramo es
una interrupción si su base suma 6 movimientos o más y se ve el 30 % o menos. Inicio y fin
medidos: si alrededor del tramo (con una franja de margen a cada lado) hay un hueco entre dos
movimientos, con como mucho un 3 % de los movimientos de su base dentro (al menos uno: el avión
al que se deja aterrizar en mitad de un cierre), que cubre la mitad del tramo o más, esos dos
movimientos; si no (el aeropuerto siguió con poco tráfico), los bordes del tramo. La base de una
franja sale de las semanas cuyo día está procesado y con cobertura; con menos de dos, la franja
no cuenta. Se
cuentan las llegadas y salidas perdidas (base menos vistos), y las esperas, frustradas y
desvíos de los aviones que iban a ese aeropuerto desde 30 minutos antes del inicio hasta el
fin, con su línea base en la misma ventana. Un avión cuenta como desviado si su trayectoria
muestra el desvío (`proceso/vuelos.py`) o si aterriza en otro aeropuerto con un indicativo que
aterrizó en este a esa hora (con dos horas de margen) el mismo día de la semana en al menos
dos de las cuatro semanas anteriores; y como en espera si hizo una espera asignada a este
aeropuerto o con uno de esos indicativos. La línea base de los desvíos solo cuenta los que
muestra la trayectoria.

**Exclusión meteorológica** (`proceso/metar.py`): si un METAR del aeropuerto de una hora antes
del inicio al fin explica el hueco, no es anomalía.

**Respuesta militar.** Aeronaves militares (marca militar de adsb.lol o tipo solo militar) a
150 km o menos del incidente desde dos horas antes de su inicio hasta dos horas después de su
fin. Muchas aeronaves militares vuelan sin emitir: la ausencia no demuestra que no hubiera
respuesta.

**Interferencia GNSS** en la celda del incidente y sus seis vecinas durante el incidente
(`proceso/gnss.py`).
"""

import itertools
import math
import statistics
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from typing import Any

from proceso import gnss, metar, vuelos

VERSION_REGLA = "trafico-1.0.0"
FRANJA_S = 900
FRANJAS_DIA = 96
SEMANAS_BASE = 4
DIAS_BASE_MINIMOS = 2

COBERTURA_ALTA = 0.80
COBERTURA_MEDIA = 0.50
COBERTURA_PROPIA = 0.75
MEDIANA_PROPIA_MINIMA = 20
ALTA, MEDIA, INSUFICIENTE = "alta", "media", "insuficiente"
CREDIBILIDAD = {ALTA: 2, MEDIA: 3}

BASE_FRANJA_MINIMA = 2.0
FRACCION_BAJA = 0.30
FRACCION_PUENTE = 0.50
BASE_TRAMO_MINIMA = 6.0
FRACCION_HUECO = 0.50
# Movimientos sueltos que se admiten dentro de un hueco: el 3 % de los de su base (al menos 1).
FRACCION_SUELTOS = 0.03
MARGEN_ANTES_S = 1800
MARGEN_METAR_S = 3600
MARGEN_HABITUAL_S = 7200

RADIO_MILITAR_KM = 150.0
MARGEN_MILITAR = timedelta(hours=2)
CASA_INCIDENTE = timedelta(minutes=60)


# --- Días procesados -----------------------------------------------------------------


@dataclass
class DiaTrafico:
    """Los resultados de un día procesado que hacen falta para evaluar."""

    dia: date
    publicacion: str
    pagina: str
    # Por aeropuerto: filas de movimientos (`vuelos.Movimiento.fila`).
    movimientos: dict[str, list[list[Any]]] = field(default_factory=dict)
    militares: list[dict[str, Any]] | None = None
    gnss_hora: list[tuple[int, str, int, int]] | None = None
    gnss_dia: list[tuple[str, int, int]] | None = None
    # Lee de disco un detalle que no se guarda en memoria (militares, gnss_hora, gnss_dia):
    # solo se necesita para los incidentes de ese día, y así la caché de días ocupa poco.
    cargador: Callable[[str], Any] | None = field(default=None, repr=False)

    def detalle(self, nombre: str) -> Any:
        valor = getattr(self, nombre)
        if valor is None and self.cargador is not None:
            return self.cargador(nombre)
        return valor


LectorDias = Callable[[date], DiaTrafico | None]


def inicio_dia(dia: date) -> float:
    return datetime(dia.year, dia.month, dia.day, tzinfo=UTC).timestamp()


def instante(t: float) -> str:
    return datetime.fromtimestamp(t, UTC).strftime("%Y-%m-%dT%H:%MZ")


def leer_instante(texto: str) -> datetime:
    return datetime.fromisoformat(texto.replace("Z", "+00:00"))


# --- Cobertura --------------------------------------------------------------------------


@dataclass(frozen=True)
class Referencia:
    """Movimientos IFR de referencia del aeropuerto ese día y de dónde salen."""

    movimientos: float
    origen: str  # eurocontrol | eurocontrol_estimada | mediana_propia


@dataclass(frozen=True)
class Cobertura:
    oaci: str
    dia: date
    vistos: int
    referencia: Referencia | None
    indice: float | None
    nivel: str

    def documento(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "oaci": self.oaci,
            "dia": self.dia.isoformat(),
            "vistos": self.vistos,
            "nivel": self.nivel,
        }
        if self.referencia is not None:
            d["referencia"] = round(self.referencia.movimientos, 1)
            d["origen_referencia"] = self.referencia.origen
        if self.indice is not None:
            d["indice"] = round(self.indice, 3)
        return d


def movimientos_ifr(filas: Iterable[list[Any]], tipos: str = "LD") -> list[float]:
    return sorted(float(f[2]) for f in filas if f[1] in tipos and f[6])


def nivel_cobertura(vistos: int, referencia: Referencia | None) -> tuple[float | None, str]:
    if referencia is None or referencia.movimientos <= 0:
        return None, INSUFICIENTE
    indice = vistos / referencia.movimientos
    if referencia.origen == "mediana_propia":
        if referencia.movimientos >= MEDIANA_PROPIA_MINIMA and indice >= COBERTURA_PROPIA:
            return indice, MEDIA
        return indice, INSUFICIENTE
    if indice >= COBERTURA_ALTA:
        return indice, ALTA
    return indice, MEDIA if indice >= COBERTURA_MEDIA else INSUFICIENTE


def cobertura(
    oaci: str, dia: date, lector: LectorDias, referencias: Callable[[str, date], Referencia | None]
) -> Cobertura | None:
    """Cobertura del aeropuerto ese día; None si el día no está procesado."""
    datos = lector(dia)
    if datos is None:
        return None
    vistos = len(movimientos_ifr(datos.movimientos.get(oaci, [])))
    referencia = referencias(oaci, dia)
    if referencia is None:
        propios = []
        for d in dias_base(dia):
            base = lector(d)
            if base is not None:
                propios.append(len(movimientos_ifr(base.movimientos.get(oaci, []))))
        if len(propios) >= DIAS_BASE_MINIMOS:
            referencia = Referencia(float(statistics.median(propios)), "mediana_propia")
    indice, nivel = nivel_cobertura(vistos, referencia)
    return Cobertura(oaci, dia, vistos, referencia, indice, nivel)


def dias_base(dia: date) -> list[date]:
    return [dia - timedelta(weeks=k) for k in range(1, SEMANAS_BASE + 1)]


# --- Series y línea base -----------------------------------------------------------------


@dataclass
class Serie:
    """Recuentos por franja de 15 minutos en una ventana [inicio, fin) alineada a franjas."""

    inicio: float
    llegadas: list[float]
    salidas: list[float]
    esperas: list[float]
    frustradas: list[float]
    desvios: list[float]

    @property
    def movimientos(self) -> list[float]:
        return [a + b for a, b in zip(self.llegadas, self.salidas, strict=True)]


def _franja(t: float, inicio: float) -> int:
    return int((t - inicio) // FRANJA_S)


def serie(filas: Iterable[list[Any]], inicio: float, franjas: int) -> Serie:
    s = Serie(inicio, *([0.0] * franjas for _ in range(5)))
    destino = {"L": s.llegadas, "D": s.salidas, "H": s.esperas, "G": s.frustradas, "V": s.desvios}
    for f in filas:
        if not f[6]:
            continue  # solo aviones IFR, como la referencia
        k = _franja(float(f[2]), inicio)
        if 0 <= k < franjas:
            destino[f[1]][k] += 1
    return s


def filas_ventana(
    oaci: str | None, inicio: float, fin: float, lector: LectorDias, extension: float = 0.0
) -> list[list[Any]] | None:
    """Movimientos del aeropuerto (de todos, sin `oaci`) en [inicio, fin + extension); None si
    falta algún día de [inicio, fin). Los días de la extensión, si faltan, no cuentan."""
    filas: list[list[Any]] = []
    dia = datetime.fromtimestamp(inicio, UTC).date()
    hasta = fin + extension
    while inicio_dia(dia) < hasta:
        datos = lector(dia)
        if datos is None:
            if inicio_dia(dia) < fin:
                return None
            break
        grupos = [datos.movimientos.get(oaci, [])] if oaci else list(datos.movimientos.values())
        for grupo in grupos:
            filas += [f for f in grupo if inicio <= float(f[2]) < hasta]
        dia += timedelta(days=1)
    return filas


# Aeropuertos sin cambio de hora (Islandia, BI; Turquía, LT, desde 2016): los demás siguen el
# horario de verano europeo, del último domingo de marzo al último de octubre a la 01:00 UTC.
SIN_HORARIO_VERANO = ("BI", "LT")


def _ultimo_domingo(anio: int, mes: int) -> datetime:
    dia = date(anio, mes + 1, 1) - timedelta(days=1)
    dia -= timedelta(days=(dia.weekday() - 6) % 7)
    return datetime(dia.year, dia.month, dia.day, 1, tzinfo=UTC)


def horario_verano(t: float) -> bool:
    momento = datetime.fromtimestamp(t, UTC)
    return _ultimo_domingo(momento.year, 3) <= momento < _ultimo_domingo(momento.year, 10)


def semana_anterior(oaci: str, inicio: float, semanas: int) -> float:
    """El mismo momento en hora local `semanas` semanas antes. Los vuelos siguen el horario
    local: tras el cambio de hora de octubre, el vuelo de las 06:00 locales sale una hora más
    tarde en UTC, y comparar la misma hora UTC daría un hueco falso cada mañana (pasó en
    Ámsterdam, Gatwick y Copenhague a finales de octubre de 2025)."""
    base = inicio - semanas * 7 * 86400
    if oaci[:2] in SIN_HORARIO_VERANO:
        return base
    return base - (int(horario_verano(base)) - int(horario_verano(inicio))) * 3600


def filas_disponibles(
    oaci: str | None, inicio: float, fin: float, lector: LectorDias
) -> list[list[Any]]:
    """Como filas_ventana, pero con los días que haya: los que faltan no cuentan."""
    filas: list[list[Any]] = []
    dia = datetime.fromtimestamp(inicio, UTC).date()
    while inicio_dia(dia) < fin:
        datos = lector(dia)
        if datos is not None:
            grupos = [datos.movimientos.get(oaci, [])] if oaci else list(datos.movimientos.values())
            for grupo in grupos:
                filas += [f for f in grupo if inicio <= float(f[2]) < fin]
        dia += timedelta(days=1)
    return filas


def valido_indicativo(indicativo: Any) -> bool:
    """Un indicativo recibido: readsb pone «@» en los que no ha recibido."""
    return isinstance(indicativo, str) and bool(indicativo.strip("@ "))


def destinos_habituales(oaci: str, inicio: float, franjas: int, lector: LectorDias) -> set[str]:
    """Indicativos que aterrizaron en el aeropuerto en la misma ventana del mismo día de la
    semana en al menos dos de las cuatro semanas anteriores (con dos horas de margen): los
    vuelos que normalmente van allí a esa hora."""
    vistas: dict[str, int] = {}
    for k in range(1, SEMANAS_BASE + 1):
        desplazado = semana_anterior(oaci, inicio, k)
        filas = filas_disponibles(
            oaci,
            desplazado - MARGEN_HABITUAL_S,
            desplazado + franjas * FRANJA_S + MARGEN_HABITUAL_S,
            lector,
        )
        for indicativo in {f[4] for f in filas if f[1] == "L" and valido_indicativo(f[4])}:
            vistas[indicativo] = vistas.get(indicativo, 0) + 1
    return {i for i, n in vistas.items() if n >= DIAS_BASE_MINIMOS}


def desviados(
    oaci: str, desde: float, hasta: float, habituales: set[str], todas: list[list[Any]]
) -> set[str]:
    """Aeronaves desviadas: un desvío detectado en su trayectoria (V) hacia este aeropuerto, o
    un aterrizaje en otro aeropuerto de un vuelo que normalmente aterriza aquí a esta hora."""
    resultado = set()
    for f in todas:
        if not f[6] or not desde <= float(f[2]) <= hasta:
            continue
        if (f[1] == "V" and f[0] == oaci) or (f[1] == "L" and f[0] != oaci and f[4] in habituales):
            resultado.add(f[3])
    return resultado


def en_espera(
    oaci: str, desde: float, hasta: float, habituales: set[str], todas: list[list[Any]]
) -> set[str]:
    """Aeronaves en espera asignada al aeropuerto, o de un vuelo que normalmente va a él."""
    return {
        f[3]
        for f in todas
        if f[1] == "H"
        and f[6]
        and desde <= float(f[2]) <= hasta
        and (f[0] == oaci or (f[4] is not None and f[4] in habituales))
    }


def linea_base(
    oaci: str, inicio: float, franjas: int, lector: LectorDias, valido: Callable[[date], bool]
) -> tuple[Serie, int] | None:
    """Mediana por franja de las cuatro semanas anteriores, franja a franja con las semanas cuyo
    día está procesado y tiene cobertura (una ventana que pasa de medianoche puede tener más
    semanas en un día que en el otro). Una franja con menos de dos semanas queda sin base (0:
    no cuenta como baja). None si ninguna franja tiene base; si no, también el mayor número de
    semanas de una franja."""
    series: list[tuple[Serie, list[bool]]] = []
    for k in range(1, SEMANAS_BASE + 1):
        desplazado = semana_anterior(oaci, inicio, k)
        dias = [
            datetime.fromtimestamp(desplazado + j * FRANJA_S, UTC).date() for j in range(franjas)
        ]
        validos = {d: valido(d) and lector(d) is not None for d in set(dias)}
        disponibles = [validos[d] for d in dias]
        if not any(disponibles):
            continue
        filas = filas_disponibles(oaci, desplazado, desplazado + franjas * FRANJA_S, lector)
        series.append((serie(filas, desplazado, franjas), disponibles))
    semanas = [sum(1 for _, d in series if d[j]) for j in range(franjas)]
    if not semanas or max(semanas) < DIAS_BASE_MINIMOS:
        return None

    def mediana(campo: str) -> list[float]:
        resultado = []
        for j in range(franjas):
            valores = [getattr(s, campo)[j] for s, d in series if d[j]]
            resultado.append(
                float(statistics.median(valores)) if len(valores) >= DIAS_BASE_MINIMOS else 0.0
            )
        return resultado

    base = Serie(
        inicio,
        mediana("llegadas"),
        mediana("salidas"),
        mediana("esperas"),
        mediana("frustradas"),
        mediana("desvios"),
    )
    return base, max(semanas)


# --- Interrupciones ----------------------------------------------------------------------


@dataclass
class Interrupcion:
    oaci: str
    inicio: float
    fin: float
    precision: str  # movimientos | franjas
    llegadas_vistas: int
    salidas_vistas: int
    llegadas_base: float
    salidas_base: float
    esperas: int
    esperas_base: float
    frustradas: int
    frustradas_base: float
    desvios: int
    desvios_base: float
    semanas_base: int
    motivos_meteorologicos: list[str] = field(default_factory=list)

    @property
    def duracion_min(self) -> int:
        return max(0, round((self.fin - self.inicio) / 60))

    @property
    def llegadas_perdidas(self) -> int:
        return max(0, round(self.llegadas_base - self.llegadas_vistas))

    @property
    def salidas_perdidas(self) -> int:
        return max(0, round(self.salidas_base - self.salidas_vistas))

    def documento(self) -> dict[str, Any]:
        return {
            "oaci": self.oaci,
            "inicio": instante(self.inicio),
            "fin": instante(self.fin),
            "duracion_min": self.duracion_min,
            "precision": self.precision,
            "llegadas_perdidas": self.llegadas_perdidas,
            "salidas_perdidas": self.salidas_perdidas,
            "llegadas_vistas": self.llegadas_vistas,
            "salidas_vistas": self.salidas_vistas,
            "llegadas_base": round(self.llegadas_base, 1),
            "salidas_base": round(self.salidas_base, 1),
            "esperas": self.esperas,
            "esperas_base": round(self.esperas_base, 1),
            "frustradas": self.frustradas,
            "frustradas_base": round(self.frustradas_base, 1),
            "desvios": self.desvios,
            "desvios_base": round(self.desvios_base, 1),
            "semanas_base": self.semanas_base,
            "motivos_meteorologicos": self.motivos_meteorologicos,
        }


def tramos_bajos(observado: list[float], base: list[float]) -> list[tuple[int, int]]:
    """Tramos [a, b] de franjas bajas que forman una interrupción."""
    bajas = [
        b >= BASE_FRANJA_MINIMA and o <= FRACCION_BAJA * b
        for o, b in zip(observado, base, strict=True)
    ]
    tramos: list[list[int]] = []
    for k, baja in enumerate(bajas):
        if not baja:
            continue
        if tramos and k - tramos[-1][1] == 2:
            puente = k - 1
            if observado[puente] <= FRACCION_PUENTE * base[puente]:
                tramos[-1][1] = k
                continue
        if tramos and k - tramos[-1][1] == 1:
            tramos[-1][1] = k
        else:
            tramos.append([k, k])
    resultado = []
    for a, b in tramos:
        suma_base = sum(base[a : b + 1])
        suma_vista = sum(observado[a : b + 1])
        if suma_base >= BASE_TRAMO_MINIMA and suma_vista <= FRACCION_BAJA * suma_base:
            resultado.append((a, b))
    return resultado


def _bordes(
    tiempos: list[float], a_t: float, b_t: float, sueltos: int = 1
) -> tuple[float, float, str]:
    """Inicio y fin medidos: el mayor intervalo alrededor del tramo entre dos movimientos con
    como mucho `sueltos` movimientos dentro (un avión al que se deja aterrizar en mitad de un
    cierre no parte el hueco en dos)."""
    margen = FRANJA_S
    antes = [t for t in tiempos if t < a_t - margen]
    dentro = [t for t in tiempos if a_t - margen <= t <= b_t + margen]
    despues = [t for t in tiempos if t > b_t + margen]
    puntos = ([antes[-1]] if antes else []) + dentro + ([despues[0]] if despues else [])
    mejor: tuple[float, float] | None = None
    for i, x in enumerate(puntos):
        for y in puntos[i + 1 : i + sueltos + 2]:
            if mejor is None or y - x > mejor[1] - mejor[0]:
                mejor = (x, y)
    if mejor is not None:
        # Los sueltos pegados a un borde son tráfico normal que se va apagando: el borde pasa a
        # ellos mientras estén a menos de un cuarto del mayor hueco interior.
        x, y = mejor
        interiores = [t for t in puntos if x < t < y]
        trozos = [b - a for a, b in itertools.pairwise([x, *interiores, y])]
        cuarto = max(trozos) / 4
        while interiores and interiores[0] - x < cuarto:
            x = interiores.pop(0)
        while interiores and y - interiores[-1] < cuarto:
            y = interiores.pop()
        mejor = (x, y)
        solape = min(mejor[1], b_t) - max(mejor[0], a_t)
        if solape >= FRACCION_HUECO * (b_t - a_t):
            return mejor[0], mejor[1], "movimientos"
    return a_t, b_t, "franjas"


def _cuenta(filas: list[list[Any]], tipo: str, desde: float, hasta: float) -> int:
    return sum(1 for f in filas if f[1] == tipo and f[6] and desde <= float(f[2]) <= hasta)


def interrupciones(
    oaci: str,
    inicio: float,
    fin: float,
    lector: LectorDias,
    valido: Callable[[date], bool],
    metares: Callable[[str, float, float], list[metar.Metar]] | None = None,
) -> list[Interrupcion] | None:
    """Interrupciones del aeropuerto en la ventana [inicio, fin) (alineada a franjas). None si
    falta algún día de la ventana o no hay línea base."""
    franjas = int((fin - inicio) // FRANJA_S)
    filas = filas_ventana(oaci, inicio, fin, lector, extension=4 * FRANJA_S)
    if filas is None:
        return None
    base = linea_base(oaci, inicio, franjas, lector, valido)
    if base is None:
        return None
    referencia, semanas = base
    vista = serie([f for f in filas if float(f[2]) < fin], inicio, franjas)
    tiempos = movimientos_ifr(filas)
    habituales: set[str] | None = None
    todas: list[list[Any]] = []
    resultado = []
    for a, b in tramos_bajos(vista.movimientos, referencia.movimientos):
        a_t, b_t = inicio + a * FRANJA_S, inicio + (b + 1) * FRANJA_S
        sueltos = max(1, int(FRACCION_SUELTOS * sum(referencia.movimientos[a : b + 1])))
        ini, fn, precision = _bordes(tiempos, a_t, b_t, sueltos)
        desde = ini - MARGEN_ANTES_S
        if habituales is None:
            habituales = destinos_habituales(oaci, inicio, franjas, lector)
            todas = filas_disponibles(None, inicio - MARGEN_ANTES_S, fin + 4 * FRANJA_S, lector)
        # Línea base de esperas, frustradas y desvíos en la misma ventana de franjas.
        k0 = max(0, _franja(desde, inicio))
        k1 = min(franjas - 1, _franja(fn, inicio))
        interrupcion = Interrupcion(
            oaci,
            ini,
            fn,
            precision,
            llegadas_vistas=round(sum(vista.llegadas[a : b + 1])),
            salidas_vistas=round(sum(vista.salidas[a : b + 1])),
            llegadas_base=sum(referencia.llegadas[a : b + 1]),
            salidas_base=sum(referencia.salidas[a : b + 1]),
            esperas=len(en_espera(oaci, desde, fn, habituales, todas)),
            esperas_base=sum(referencia.esperas[k0 : k1 + 1]),
            frustradas=_cuenta(filas, "G", desde, fn),
            frustradas_base=sum(referencia.frustradas[k0 : k1 + 1]),
            desvios=len(desviados(oaci, desde, fn + FRANJA_S, habituales, todas)),
            desvios_base=sum(referencia.desvios[k0 : min(franjas - 1, k1 + 1) + 1]),
            semanas_base=semanas,
        )
        if metares is not None:
            interrupcion.motivos_meteorologicos = metar.explica(
                metares(oaci, ini - MARGEN_METAR_S, fn),
                datetime.fromtimestamp(ini - MARGEN_METAR_S, UTC),
                datetime.fromtimestamp(fn, UTC),
            )
        resultado.append(interrupcion)
    return resultado


def indicios(
    oaci: str, inicio: float, fin: float, w0: float, w1: float, lector: LectorDias,
    valido: Callable[[date], bool],
) -> dict[str, Any]:  # fmt: skip
    """Lo que se ve en la ventana del incidente cuando no hay una interrupción que casar: los
    movimientos que se esperaban (base) y los vistos, y las esperas y los desvíos (con los
    indicativos habituales) desde 30 minutos antes hasta 15 después."""
    franjas = int((w1 - w0) // FRANJA_S)
    base = linea_base(oaci, w0, franjas, lector, valido)
    k0 = max(0, _franja(inicio, w0))
    k1 = min(franjas, _franja(fin, w0) + 1)
    esperados = sum(base[0].movimientos[k0:k1]) if base is not None else 0.0
    filas = filas_disponibles(oaci, inicio, fin, lector)
    habituales = destinos_habituales(oaci, w0, franjas, lector)
    todas = filas_disponibles(None, inicio - MARGEN_ANTES_S, fin + FRANJA_S, lector)
    return {
        "base_ventana": round(esperados, 1),
        "vistos_ventana": sum(1 for f in filas if f[1] in "LD" and f[6]),
        "esperas_ventana": len(en_espera(oaci, inicio - MARGEN_ANTES_S, fin, habituales, todas)),
        "desvios_ventana": len(
            desviados(oaci, inicio - MARGEN_ANTES_S, fin + FRANJA_S, habituales, todas)
        ),
    }


# --- Respuesta militar ---------------------------------------------------------------------


def respuesta_militar(
    lat: float, lon: float, desde: float, hasta: float, militares: Iterable[dict[str, Any]]
) -> dict[str, Any]:
    vistas = []
    for aeronave in militares:
        primera: float | None = None
        minima: float | None = None
        for t, la, lo, _alt in aeronave["puntos"]:
            if not desde <= t <= hasta:
                continue
            d = vuelos.distancia_km(lat, lon, la, lo)
            if d > RADIO_MILITAR_KM:
                continue
            primera = t if primera is None else min(primera, t)
            minima = d if minima is None else min(minima, d)
        if primera is not None and minima is not None:
            vistas.append(
                {
                    "icao": aeronave["icao"],
                    "tipo": aeronave.get("tipo"),
                    "clase": aeronave["clase"],
                    "indicativos": [
                        i for i in aeronave.get("indicativos", []) if valido_indicativo(i)
                    ],
                    "primera": instante(primera),
                    "distancia_min_km": round(minima, 1),
                }
            )
    vistas.sort(key=lambda v: (v["primera"], v["icao"]))
    clases: dict[str, int] = {}
    for v in vistas:
        clases[v["clase"]] = clases.get(v["clase"], 0) + 1
    documento: dict[str, Any] = {
        "radio_km": RADIO_MILITAR_KM,
        "ventana": {"inicio": instante(desde), "fin": instante(hasta)},
        "aeronaves": len(vistas),
        "por_clase": dict(sorted(clases.items())),
        "tipos": sorted({v["tipo"] for v in vistas if v["tipo"]}),
        "detalle": vistas,
        "ausencia_no_concluyente": True,
    }
    if vistas:
        documento["primera"] = vistas[0]["primera"]
        documento["distancia_min_km"] = min(v["distancia_min_km"] for v in vistas)
    return documento


# --- Interferencia GNSS ----------------------------------------------------------------------


def interferencia(
    lat: float, lon: float, desde: float, hasta: float, filas: Iterable[tuple[int, str, int, int]]
) -> dict[str, Any]:
    """Aeronaves y degradadas en la celda del incidente y en sus vecinas, sumando las horas
    de la ventana (una aeronave que sigue en la celda varias horas cuenta en cada una)."""
    celda = gnss.celda_de(lat, lon)
    vecinas = set(gnss.vecinas(celda)) - {celda}
    h0, h1 = int(desde // 3600), math.ceil(hasta / 3600)
    propia = [0, 0]
    alrededor = [0, 0]
    horas: set[int] = set()
    for hora, c, n, malas in filas:
        if not h0 <= hora < max(h1, h0 + 1):
            continue
        if c == celda:
            propia[0] += n
            propia[1] += malas
            horas.add(hora)
        elif c in vecinas:
            alrededor[0] += n
            alrededor[1] += malas

    def bloque(n: int, malas: int, minimo: int) -> dict[str, Any]:
        return {
            "aeronaves": n,
            "degradadas": malas,
            "proporcion": round(gnss.proporcion(n, malas), 3),
            "nivel": gnss.nivel(n, malas, minimo),
        }

    horas_ventana = max(1, max(h1, h0 + 1) - h0)
    return {
        "celda": celda,
        "resolucion_h3": gnss.RESOLUCION,
        "ventana": {"inicio": instante(desde), "fin": instante(hasta)},
        "propia": bloque(propia[0], propia[1], gnss.MINIMO_HORA * horas_ventana),
        "vecinas": bloque(alrededor[0], alrededor[1], gnss.MINIMO_HORA * horas_ventana),
    }


# --- Ventana de un incidente -------------------------------------------------------------------


def ventana_incidente(incidente: dict[str, Any]) -> tuple[float, float, str]:
    """Inicio y fin del incidente (segundos) y la precisión con que se conocen. Con solo el
    día, el día UTC entero; con la fecha de publicación (aproximada), desde el comienzo de la
    víspera hasta la publicación, como un día (solo casa una interrupción significativa); con
    hora, esa hora; con minuto y sin fin, una hora."""
    tiempo = incidente["tiempo"]
    inicio = leer_instante(tiempo["inicio"]["valor"])
    precision = tiempo["inicio"]["precision"]
    if precision == "dia":
        comienzo = datetime(inicio.year, inicio.month, inicio.day, tzinfo=UTC)
        return comienzo.timestamp(), (comienzo + timedelta(days=1)).timestamp(), "dia"
    if precision == "aproximada":
        comienzo = datetime(inicio.year, inicio.month, inicio.day, tzinfo=UTC) - timedelta(days=1)
        return comienzo.timestamp(), inicio.timestamp(), "dia"
    fin = leer_instante(tiempo["fin"]["valor"]) if "fin" in tiempo else None
    if fin is None or fin < inicio:
        fin = inicio + timedelta(hours=1)
    return inicio.timestamp(), fin.timestamp(), precision
