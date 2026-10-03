"""Detección en directo de cierres de aeropuerto a partir de las posiciones en tiempo real.

Cada 80 s llegan las posiciones de las aeronaves alrededor de los aeropuertos vigilados
(`recogida/directo.py`). De cada una se guardan, como en las trazas filtradas del archivo
diario (`recogida.trafico.lineas_trazas`), los puntos en tierra o por debajo de 10 000 pies
a 40 km o menos de un aeropuerto con tráfico regular, y con ellos se reconstruyen sus
aterrizajes y despegues con las mismas reglas que el archivo (`proceso/vuelos.py`).

**Aeropuertos vigilados.** Los que tuvieron cobertura alta del archivo de adsb.lol
(`proceso/trafico.nivel_cobertura`) todos los días de su línea base que están en el archivo
(tres como mínimo) y una mediana de 40 movimientos IFR al día o más.

**Línea base.** Por franja de 15 minutos, la mediana de aterrizajes y despegues IFR del mismo
día de la semana de las cuatro semanas anteriores, a la misma hora local, con los días del
archivo con cobertura (como `proceso/trafico.linea_base`).

**Señal.** En cada ciclo, para cada aeropuerto vigilado y con los movimientos ya asentados
(los de hace `RETRASO_S` o más): se prueba como comienzo del hueco cada uno de los últimos
movimientos vistos; con el comienzo s, los vistos después (k) y los esperados entre s y
ahora (E, la línea base por el factor de cobertura del momento), hay señal si E llega a
`ESPERADOS_MINIMOS`, k no pasa de `FRACCION_VISTOS`·E y E ha crecido al menos `RITMO_MINIMO`
por minuto de hueco (un cierre en un aeropuerto con tráfico; un hueco lento es tráfico
escaso). Un despegue o un aterrizaje en curso (`Vivos.actividad`) anula la señal. El factor de
cobertura es la proporción vista de lo esperado en las tres horas anteriores al hueco (entre
0,6 y 1,2): por debajo de 0,6 los receptores no ven bien ese aeropuerto en ese momento y no
hay señal.

**Estados de un aviso.**

- `posible_cierre`: hay señal (mantenida `PERSISTENCIA_S`) y ningún METAR del aeropuerto
  desde una hora antes del comienzo explica el hueco (`proceso/metar.py`).
- `cierre_confirmado`: una fuente oficial o un incidente de la base recoge el cierre
  (`confirmar`, lo hace la recogida horaria con la base abierta).
- `operacion_reanudada`: vuelven los movimientos (`MOVIMIENTOS_REANUDACION` asentados tras el
  comienzo y lo visto en la última media hora llega a la mitad de lo esperado). La hora de
  reanudación es la del primero de ellos.

Cada aviso guarda la hora de detección, el comienzo estimado, la evidencia (movimientos
esperados y vistos, llegadas y salidas perdidas, aeronaves en espera y desviadas) y, cuando
llega, la confirmación y la hora de la primera noticia, para medir la ventaja.
"""

import bisect
import statistics
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from typing import Any

from proceso import aeronaves, metar, trafico, vuelos

VERSION_REGLA = "directo-1.0.0"

# --- Umbrales (ajustados reproduciendo días reales: docs/informe_europa_directo.md) ------
PASO_S = 80
RETRASO_S = 240
ESPERADOS_MINIMOS = 12.0
FRACCION_VISTOS = 0.10
PERSISTENCIA_S = 240
# Movimientos esperados por minuto de hueco: en un cierre de un aeropuerto con tráfico, lo que
# falta crece deprisa; un hueco que tarda en acumular los esperados es tráfico escaso (primera
# hora, última de la noche) y no se distingue de una pausa normal.
RITMO_MINIMO = 0.5
# El hueco tiene que seguir abierto: en los últimos 15 minutos, como mucho un movimiento o el
# 10 % de lo esperado en ellos.
ABIERTO_S = 900
HORAS_PREVIAS = 3
ESPERADOS_PREVIOS_MINIMOS = 10.0
FACTOR_MINIMO = 0.6
FACTOR_MAXIMO = 1.2
HUECO_MAXIMO_S = 6 * 3600
MOVIMIENTOS_REANUDACION = 2
# Fallo de la fuente o del archivo: entre todos los vigilados, en los últimos 10 minutos, se ve
# menos de la mitad de lo esperado (con 50 esperados como mínimo, para la madrugada).
VENTANA_GLOBAL_S = 600
FRACCION_GLOBAL = 0.5
ESPERADOS_GLOBALES_MINIMOS = 50.0
VENTANA_REANUDACION_S = 1800
FRACCION_REANUDACION = 0.5
MARGEN_METAR_S = 3600
DIAS_COBERTURA_ALTA = 3
FRACCION_DIA_COMPLETO = 0.5
MOVIMIENTOS_DIA_MINIMOS = 40.0
# Un aviso reanudado se publica 12 horas; uno sin reanudar se cierra a las 24 horas.
PUBLICAR_REANUDADO_S = 12 * 3600
CADUCIDAD_S = 24 * 3600

# Trazas en vivo: lo mismo que guarda el archivo diario.
TECHO_FT = 10000.0
RADIO_ZONA_KM = 40.0
MEMORIA_S = 3 * 3600
ANALISIS_S = 120
BAJO_FT = 3000.0
SIN_SENAL_S = 180
POSTERIOR_S = 120
DUPLICADO_S = 900
# Actividad en curso: una aeronave que en los últimos 5 minutos rodaba a más de 40 nudos por
# tierra o volaba por debajo de 1500 pies sobre el aeropuerto a 8 km o menos de él está
# despegando o aterrizando, aunque su movimiento aún no se haya asentado: no hay señal.
ACTIVIDAD_S = 300
ACTIVIDAD_RADIO_KM = 8.0
ACTIVIDAD_ALTURA_FT = 1500.0
ACTIVIDAD_SUELO_KT = 40.0
# Y un movimiento reconstruido sin asentar a 20 minutos o menos de ahora, de una aeronave que
# sigue baja o cuya llegada estimada (sin cobertura a baja altura) aún no ha llegado.
ACTIVIDAD_PENDIENTE_S = 1200

# Esperas en vivo: un avión en el aire entre 3000 y 25 000 pies, a más de 140 nudos, que pasa
# 8 minutos o más dentro de un círculo de 12 km de radio (un circuito de espera mide unos
# 10 km por 4).
ESPERA_TECHO_FT = 25000.0
ESPERA_SUELO_FT = 3000.0
ESPERA_VELOCIDAD_KT = 140.0
ESPERA_DURACION_S = 480
ESPERA_RADIO_KM = 12.0
ESPERA_DISTANCIA_KM = 120.0

POSIBLE, CONFIRMADO, REANUDADA = "posible_cierre", "cierre_confirmado", "operacion_reanudada"
ESTADOS = (POSIBLE, CONFIRMADO, REANUDADA)


def instante(t: float) -> str:
    return datetime.fromtimestamp(t, UTC).strftime("%Y-%m-%dT%H:%MZ")


def segundos(texto: str) -> float:
    return datetime.fromisoformat(texto.replace("Z", "+00:00")).timestamp()


# --- Línea base -----------------------------------------------------------------------------


@dataclass
class BaseDia:
    """Movimientos esperados de un aeropuerto un día, por franja de 15 minutos (UTC)."""

    oaci: str
    dia: date
    llegadas: list[float]
    salidas: list[float]
    semanas: int
    # Indicativos que aterrizan aquí habitualmente, con su hora (s desde el inicio del día).
    habituales: dict[str, list[float]] = field(default_factory=dict)

    _acumulados: dict[str, list[float]] = field(default_factory=dict, repr=False)

    @property
    def movimientos(self) -> list[float]:
        return [a + b for a, b in zip(self.llegadas, self.salidas, strict=True)]

    def acumulado(self, campo: str) -> list[float]:
        """Suma de las franjas anteriores a cada una (97 valores: el último, el día entero)."""
        if campo not in self._acumulados:
            valores: list[float] = getattr(self, campo)
            suma = [0.0]
            for v in valores:
                suma.append(suma[-1] + v)
            self._acumulados[campo] = suma
        return self._acumulados[campo]


def base_dia(
    oaci: str, dia: date, lector: trafico.LectorDias, valido: Callable[[date], bool]
) -> BaseDia | None:
    """La línea base del día entero (96 franjas), con las semanas válidas del archivo."""
    inicio = trafico.inicio_dia(dia)
    resultado = trafico.linea_base(oaci, inicio, trafico.FRANJAS_DIA, lector, valido)
    if resultado is None:
        return None
    serie, semanas = resultado
    vistas: dict[str, list[tuple[int, float]]] = {}
    for k in range(1, trafico.SEMANAS_BASE + 1):
        desplazado = trafico.semana_anterior(oaci, inicio, k)
        for f in trafico.filas_disponibles(oaci, desplazado, desplazado + 86400, lector):
            if f[1] == "L" and f[6] and trafico.valido_indicativo(f[4]):
                vistas.setdefault(str(f[4]).strip(), []).append((k, float(f[2]) - desplazado))
    habituales = {
        indicativo: sorted(t for _, t in horas)
        for indicativo, horas in vistas.items()
        if len({k for k, _ in horas}) >= trafico.DIAS_BASE_MINIMOS
    }
    return BaseDia(oaci, dia, serie.llegadas, serie.salidas, semanas, habituales)


class Bases:
    """Líneas base por aeropuerto y día, calculadas al pedirlas y guardadas."""

    def __init__(self, calcular: Callable[[str, date], BaseDia | None]) -> None:
        self._calcular = calcular
        self._cache: dict[tuple[str, date], BaseDia | None] = {}

    def __call__(self, oaci: str, dia: date) -> BaseDia | None:
        clave = (oaci, dia)
        if clave not in self._cache:
            self._cache[clave] = self._calcular(oaci, dia)
        return self._cache[clave]

    def olvidar_antes(self, dia: date) -> None:
        for clave in [c for c in self._cache if c[1] < dia]:
            del self._cache[clave]

    def _hasta(self, oaci: str, dia: date, t: float, campo: str) -> float:
        """Esperados del día `dia` desde su comienzo hasta `t` (dentro del día)."""
        base = self(oaci, dia)
        if base is None:
            return 0.0
        x = max(0.0, min(86400.0, t - trafico.inicio_dia(dia)))
        k = int(x // trafico.FRANJA_S)
        acumulado = base.acumulado(campo)
        if k >= trafico.FRANJAS_DIA:
            return acumulado[-1]
        valores: list[float] = getattr(base, campo)
        return acumulado[k] + valores[k] * (x - k * trafico.FRANJA_S) / trafico.FRANJA_S

    def esperados(self, oaci: str, desde: float, hasta: float, campo: str = "movimientos") -> float:
        """Movimientos esperados en [desde, hasta), repartidos por igual dentro de cada franja.
        Un día sin base cuenta 0."""
        if hasta <= desde:
            return 0.0
        d0 = datetime.fromtimestamp(desde, UTC).date()
        d1 = datetime.fromtimestamp(hasta, UTC).date()
        if d0 == d1:
            return self._hasta(oaci, d0, hasta, campo) - self._hasta(oaci, d0, desde, campo)
        total = self._hasta(oaci, d0, desde + 86400, campo) - self._hasta(oaci, d0, desde, campo)
        dia = d0 + timedelta(days=1)
        while dia < d1:
            total += self._hasta(oaci, dia, trafico.inicio_dia(dia) + 86400, campo)
            dia += timedelta(days=1)
        return total + self._hasta(oaci, d1, hasta, campo)

    def habituales(self, oaci: str, desde: float, hasta: float) -> set[str]:
        """Indicativos que aterrizan aquí habitualmente entre `desde` y `hasta` (dos horas de
        margen), como `proceso/trafico.destinos_habituales`."""
        resultado: set[str] = set()
        dia = datetime.fromtimestamp(desde - trafico.MARGEN_HABITUAL_S, UTC).date()
        ultimo = datetime.fromtimestamp(hasta + trafico.MARGEN_HABITUAL_S, UTC).date()
        while dia <= ultimo:
            base = self(oaci, dia)
            if base is not None:
                cero = trafico.inicio_dia(dia)
                for indicativo, horas in base.habituales.items():
                    if any(
                        desde - trafico.MARGEN_HABITUAL_S
                        <= cero + h
                        <= hasta + trafico.MARGEN_HABITUAL_S
                        for h in horas
                    ):
                        resultado.add(indicativo)
            dia += timedelta(days=1)
        return resultado


def vigilables(
    dia: date,
    candidatos: Iterable[str],
    coberturas: Callable[[str, date], str | None],
    bases: Bases,
) -> list[str]:
    """Aeropuertos con cobertura alta todos los días completos de su línea base (tres como
    mínimo) y una mediana de 40 movimientos al día o más. Un día de la línea base es incompleto
    si tuvo cobertura alta menos de la mitad de los aeropuertos que la tuvieron el mejor de esos
    días (el archivo de adsb.lol tiene días a medias): ese día no cuenta para nadie."""
    candidatos = list(candidatos)
    dias = trafico.dias_base(dia)
    altas = {d: sum(1 for o in candidatos if coberturas(o, d) == trafico.ALTA) for d in dias}
    mejor = max(altas.values(), default=0)
    completos = [d for d in dias if mejor and altas[d] >= FRACCION_DIA_COMPLETO * mejor]
    resultado = []
    for oaci in candidatos:
        niveles = [n for d in completos if (n := coberturas(oaci, d)) is not None]
        if len(niveles) < DIAS_COBERTURA_ALTA or any(n != trafico.ALTA for n in niveles):
            continue
        base = bases(oaci, dia)
        if base is None or sum(base.movimientos) < MOVIMIENTOS_DIA_MINIMOS:
            continue
        resultado.append(oaci)
    return sorted(resultado)


# --- Posiciones en vivo ------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Posicion:
    """Una posición recibida: lo que da una consulta de adsb.lol o adsb.fi (formato readsb)."""

    icao: str
    t: float
    lat: float
    lon: float
    alt: float | None
    suelo: bool
    gs: float | None = None
    rumbo: float | None = None
    vz: float | None = None
    indicativo: str | None = None
    tipo: str | None = None
    categoria: str | None = None
    marcas: int = 0


@dataclass
class _Aeronave:
    icao: str
    tipo: str | None = None
    categoria: str | None = None
    marcas: int = 0
    puntos: list[Posicion] = field(default_factory=list)
    alto: list[tuple[float, float, float]] = field(default_factory=list)
    analizada: float = -1e18
    movimientos: list[vuelos.Movimiento] = field(default_factory=list)


class Vivos:
    """Las aeronaves vistas en las últimas tres horas cerca de los aeropuertos, con sus
    movimientos reconstruidos. Una aeronave se analiza al dejar de verse (tres minutos sin
    posición) y, mientras está en tierra o por debajo de 3000 pies, cada 2 minutos. Un
    movimiento se da por asentado cuando la aeronave ya no se ve o su traza sigue dos minutos
    más allá de él, y nunca antes de `RETRASO_S`."""

    def __init__(self, aeropuertos: tuple[vuelos.Aeropuerto, ...]) -> None:
        self.indice = vuelos.Indice(aeropuertos)
        regulares = [a for a in aeropuertos if a.regular]
        self.zona = vuelos.Indice(tuple(regulares), radio_km=RADIO_ZONA_KM)
        self.cerca_espera = vuelos.Indice(tuple(regulares), radio_km=ESPERA_DISTANCIA_KM)
        self.aeronaves: dict[str, _Aeronave] = {}
        # Movimientos asentados: (icao, tipo, oaci) -> instantes.
        self.asentados: dict[tuple[str, str, str], list[float]] = {}
        self.filas: list[list[Any]] = []
        self.esperas: list[list[Any]] = []
        self._por_aeropuerto: dict[str, list[float]] = {}
        self._altas: set[str] = set()
        self._ciclos = 0
        self._actividad: tuple[float, set[str]] = (-1.0, set())

    def _en_zona(self, p: Posicion) -> bool:
        if not p.suelo and (p.alt is None or p.alt >= TECHO_FT):
            return False
        return self.zona.cercano(p.lat, p.lon, RADIO_ZONA_KM, solo_regulares=True) is not None

    def anadir(self, posiciones: Iterable[Posicion]) -> None:
        for p in posiciones:
            a = self.aeronaves.get(p.icao)
            if a is None:
                a = self.aeronaves[p.icao] = _Aeronave(p.icao)
            a.tipo = p.tipo or a.tipo
            a.categoria = p.categoria or a.categoria
            a.marcas = p.marcas or a.marcas
            if self._en_zona(p) and (not a.puntos or p.t > a.puntos[-1].t):
                a.puntos.append(p)
            if (
                not p.suelo
                and p.alt is not None
                and ESPERA_SUELO_FT <= p.alt <= ESPERA_TECHO_FT
                and (p.gs or 0.0) >= ESPERA_VELOCIDAD_KT
                and (not a.alto or p.t > a.alto[-1][0])
            ):
                a.alto.append((p.t, p.lat, p.lon))
                self._altas.add(p.icao)

    def _traza(self, a: _Aeronave) -> vuelos.Traza:
        traza = vuelos.Traza(a.icao, tipo=a.tipo, marcas=a.marcas, categoria=a.categoria)
        for p in a.puntos:
            traza.t.append(p.t)
            traza.lat.append(p.lat)
            traza.lon.append(p.lon)
            traza.alt.append(p.alt)
            traza.suelo.append(p.suelo)
            traza.gs.append(p.gs)
            traza.rumbo.append(p.rumbo)
            traza.vz.append(p.vz)
            traza.tramo_nuevo.append(False)
            traza.nic.append(None)
            traza.nacp.append(None)
            traza.version.append(None)
            traza.adsb.append(True)
            traza.indicativo.append(p.indicativo)
        return traza

    def _ya_asentado(self, m: vuelos.Movimiento) -> bool:
        return any(
            abs(t - m.t) < DUPLICADO_S for t in self.asentados.get((m.icao, m.tipo, m.oaci), [])
        )

    def _toca(self, a: _Aeronave, ahora: float) -> bool:
        ultimo = a.puntos[-1]
        if ahora - ultimo.t >= SIN_SENAL_S:
            return a.analizada < ultimo.t
        bajo = ultimo.suelo or (ultimo.alt is not None and ultimo.alt < BAJO_FT)
        return bajo and ahora - a.analizada >= ANALISIS_S

    def actualizar(self, ahora: float) -> None:
        """Analiza las aeronaves que tocan, asienta sus movimientos y detecta las esperas."""
        limite_puntos = ahora - MEMORIA_S
        for icao in list(self.aeronaves):
            a = self.aeronaves[icao]
            if a.puntos and a.puntos[0].t < limite_puntos:
                a.puntos = [p for p in a.puntos if p.t >= limite_puntos]
            if a.alto and a.alto[0][0] < ahora - 2 * ESPERA_DURACION_S:
                a.alto = [x for x in a.alto if x[0] >= ahora - 2 * ESPERA_DURACION_S]
            if not a.puntos and not a.alto:
                del self.aeronaves[icao]
                continue
            if len(a.puntos) >= 2 and self._toca(a, ahora):
                ifr = aeronaves.es_ifr(a.tipo, a.categoria, a.marcas)
                a.movimientos = [
                    m for m in vuelos.analizar(self._traza(a), self.indice, ifr) if m.tipo in "LD"
                ]
                a.analizada = ahora
            if a.movimientos:
                ultimo = a.puntos[-1].t if a.puntos else -1e18
                desaparecida = ahora - ultimo >= SIN_SENAL_S
                pendientes = []
                for m in a.movimientos:
                    if self._ya_asentado(m):
                        continue
                    if m.t > ahora - RETRASO_S or (not desaparecida and ultimo - m.t < POSTERIOR_S):
                        pendientes.append(m)
                        continue
                    self.asentados.setdefault((m.icao, m.tipo, m.oaci), []).append(m.t)
                    self.filas.append(m.fila())
                    if m.ifr:
                        self._por_aeropuerto.setdefault(m.oaci, []).append(m.t)
                a.movimientos = pendientes
        for icao in self._altas:
            alta = self.aeronaves.get(icao)
            if alta is not None:
                self._espera(alta, ahora)
        self._altas = set()
        self._ciclos += 1
        if self._ciclos % 10 == 0:
            limite = ahora - MEMORIA_S - DUPLICADO_S
            self.filas = [f for f in self.filas if f[2] >= limite]
            self.esperas = [f for f in self.esperas if f[2] >= limite]
            for oaci in list(self._por_aeropuerto):
                self._por_aeropuerto[oaci] = [t for t in self._por_aeropuerto[oaci] if t >= limite]
            for clave in list(self.asentados):
                self.asentados[clave] = [t for t in self.asentados[clave] if t >= limite]
                if not self.asentados[clave]:
                    del self.asentados[clave]

    def _espera(self, a: _Aeronave, ahora: float) -> None:
        puntos = [x for x in a.alto if x[0] >= ahora - ESPERA_DURACION_S]
        if len(puntos) < 4 or puntos[-1][0] - puntos[0][0] < ESPERA_DURACION_S - 2 * PASO_S:
            return
        lat = statistics.fmean(x[1] for x in puntos)
        lon = statistics.fmean(x[2] for x in puntos)
        if any(vuelos.distancia_km(lat, lon, x[1], x[2]) > ESPERA_RADIO_KM for x in puntos):
            return
        cercano = self.cerca_espera.cercano(lat, lon, ESPERA_DISTANCIA_KM, solo_regulares=True)
        if cercano is None:
            return
        abiertas = [f for f in self.esperas if f[3] == a.icao and ahora - f[7] < ESPERA_DURACION_S]
        if abiertas:
            for f in abiertas:
                f[7] = round(ahora)
            return
        indicativo = next((p.indicativo for p in reversed(a.puntos) if p.indicativo), None)
        ifr = aeronaves.es_ifr(a.tipo, a.categoria, a.marcas)
        self.esperas.append(
            [cercano[0].oaci, "H", round(puntos[0][0]), a.icao, indicativo, a.tipo, int(ifr),
             round(ahora), round(lat, 4), round(lon, 4)]
        )  # fmt: skip

    def movimientos(self, oaci: str) -> list[float]:
        return sorted(self._por_aeropuerto.get(oaci, []))

    def actividad(self, ahora: float) -> set[str]:
        """Aeropuertos con un despegue o un aterrizaje en curso (ver ACTIVIDAD_S)."""
        if self._actividad[0] == ahora:
            return self._actividad[1]
        resultado: set[str] = set()
        for a in self.aeronaves.values():
            # Un movimiento ya reconstruido pero aún sin asentar (la aeronave sigue a la vista o
            # su hora estimada no ha llegado) es un despegue o un aterrizaje en curso.
            if a.movimientos and a.puntos:
                ultimo = a.puntos[-1]
                bajo = ultimo.suelo or (ultimo.alt is not None and ultimo.alt < BAJO_FT)
                for m in a.movimientos:
                    reciente = abs(m.t - ahora) <= ACTIVIDAD_PENDIENTE_S
                    # Sigue baja junto al aeropuerto, o ya no se ve y su llegada estimada aún
                    # no ha llegado; una aeronave que volvió a subir (a una espera) no cuenta.
                    if m.ifr and reciente and (bajo or m.t > ahora):
                        resultado.add(m.oaci)
            for p in reversed(a.puntos):
                if p.t < ahora - ACTIVIDAD_S:
                    break
                cercano = self.indice.cercano(p.lat, p.lon, ACTIVIDAD_RADIO_KM)
                if cercano is None:
                    continue
                aeropuerto = cercano[0]
                if p.suelo:
                    en_curso = (p.gs or 0.0) > ACTIVIDAD_SUELO_KT
                else:
                    en_curso = (
                        p.alt is not None and p.alt - aeropuerto.elev_ft <= ACTIVIDAD_ALTURA_FT
                    )
                if en_curso:
                    resultado.add(aeropuerto.oaci)
                    break
        self._actividad = (ahora, resultado)
        return resultado

    def todas(self) -> list[list[Any]]:
        return self.filas + self.esperas


# --- Avisos ------------------------------------------------------------------------------


@dataclass(frozen=True)
class Umbrales:
    esperados_minimos: float = ESPERADOS_MINIMOS
    fraccion_vistos: float = FRACCION_VISTOS
    persistencia_s: float = PERSISTENCIA_S
    factor_minimo: float = FACTOR_MINIMO
    esperados_previos_minimos: float = ESPERADOS_PREVIOS_MINIMOS
    ritmo_minimo: float = RITMO_MINIMO


UMBRALES = Umbrales()


@dataclass
class Senal:
    comienzo: float
    vistos: int
    esperados: float
    factor: float
    previos: float = 0.0


def senal(
    oaci: str, ahora: float, movimientos: list[float], bases: Bases, u: Umbrales = UMBRALES
) -> tuple[Senal | None, str]:
    """La señal de cierre del aeropuerto en este momento (o None) y por qué no la hay.
    `movimientos` va ordenado."""
    horizonte = ahora - RETRASO_S
    n = bisect.bisect_right(movimientos, horizonte)
    mejor: Senal | None = None
    motivo = "sin_hueco"
    k = 0
    while k < n:
        comienzo = movimientos[n - 1 - k]
        if horizonte - comienzo > HUECO_MAXIMO_S:
            break
        esperados_brutos = bases.esperados(oaci, comienzo, horizonte)
        if k > u.fraccion_vistos * esperados_brutos * FACTOR_MAXIMO:
            k += 1
            continue  # con más vistos, ni el factor más alto da señal
        previo = comienzo - HORAS_PREVIAS * 3600
        esperados_previos = bases.esperados(oaci, previo, comienzo)
        if esperados_previos < u.esperados_previos_minimos:
            motivo = "poco_trafico_previo"
            k += 1
            continue
        vistos_previos = n - 1 - k - bisect.bisect_left(movimientos, previo)
        factor = vistos_previos / esperados_previos
        if factor < u.factor_minimo:
            motivo = "cobertura_baja"
            k += 1
            continue
        factor = min(factor, FACTOR_MAXIMO)
        esperados = esperados_brutos * factor
        ritmo = esperados / max(1.0, (horizonte - comienzo) / 60)
        # El hueco sigue abierto: en el último cuarto de hora no ha vuelto el tráfico.
        recientes = n - bisect.bisect_left(movimientos, horizonte - ABIERTO_S)
        abierto = recientes <= max(
            1.0,
            u.fraccion_vistos * bases.esperados(oaci, horizonte - ABIERTO_S, horizonte) * factor,
        )
        senalado = (
            abierto
            and esperados >= u.esperados_minimos
            and k <= u.fraccion_vistos * esperados
            and ritmo >= u.ritmo_minimo
        )
        if senalado and (mejor is None or esperados - k > mejor.esperados - mejor.vistos):
            mejor = Senal(comienzo, k, esperados, factor, esperados_previos)
        k += 1
    return mejor, ("" if mejor else motivo)


@dataclass
class Aviso:
    oaci: str
    inicio: float
    detectado: float
    estado: str
    esperados: float
    vistos: int
    llegadas_perdidas: int = 0
    salidas_perdidas: int = 0
    esperas: int = 0
    desvios: int = 0
    reanudado: float | None = None
    confirmacion: dict[str, Any] | None = None
    primera_noticia: float | None = None
    motivos_meteorologicos: list[str] = field(default_factory=list)
    fuente: str = ""
    factor: float = 1.0

    @property
    def id(self) -> str:
        return f"{self.oaci}-{datetime.fromtimestamp(self.inicio, UTC).strftime('%Y-%m-%dT%H%M')}"

    @property
    def ventaja_min(self) -> int | None:
        if self.primera_noticia is None:
            return None
        return round((self.primera_noticia - self.detectado) / 60)

    def documento(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "oaci": self.oaci,
            "estado": self.estado,
            "inicio": instante(self.inicio),
            "detectado": instante(self.detectado),
            "reanudado": None if self.reanudado is None else instante(self.reanudado),
            "evidencia": {
                "esperados": round(self.esperados, 1),
                "vistos": self.vistos,
                "llegadas_perdidas": self.llegadas_perdidas,
                "salidas_perdidas": self.salidas_perdidas,
                "esperas": self.esperas,
                "desvios": self.desvios,
            },
            "confirmacion": self.confirmacion,
            "primera_noticia": (
                None if self.primera_noticia is None else instante(self.primera_noticia)
            ),
            "ventaja_min": self.ventaja_min,
            "motivos_meteorologicos": self.motivos_meteorologicos,
            "fuente": self.fuente,
            "factor": round(self.factor, 3),
            "regla": VERSION_REGLA,
        }

    @classmethod
    def de_documento(cls, d: dict[str, Any]) -> "Aviso":
        e = d["evidencia"]
        return cls(
            oaci=d["oaci"],
            inicio=segundos(d["inicio"]),
            detectado=segundos(d["detectado"]),
            estado=d["estado"],
            esperados=float(e["esperados"]),
            vistos=int(e["vistos"]),
            llegadas_perdidas=int(e["llegadas_perdidas"]),
            salidas_perdidas=int(e["salidas_perdidas"]),
            esperas=int(e["esperas"]),
            desvios=int(e["desvios"]),
            reanudado=segundos(d["reanudado"]) if d.get("reanudado") else None,
            confirmacion=d.get("confirmacion"),
            primera_noticia=segundos(d["primera_noticia"]) if d.get("primera_noticia") else None,
            motivos_meteorologicos=list(d.get("motivos_meteorologicos", [])),
            fuente=d.get("fuente", ""),
            factor=float(d.get("factor", 1.0)),
        )


Metares = Callable[[str, float, float], list[metar.Metar]]


@dataclass
class Detector:
    """Estado de la detección: la señal de cada aeropuerto desde cuándo y los avisos."""

    bases: Bases
    metares: Metares | None = None
    umbrales: Umbrales = UMBRALES
    senales: dict[str, float] = field(default_factory=dict)
    comienzos: dict[str, float] = field(default_factory=dict)
    avisos: list[Aviso] = field(default_factory=list)
    motivos: dict[str, str] = field(default_factory=dict)
    # Filas con que se cuenta la evidencia (esperas y desvíos); sin ella, las de las posiciones
    # en vivo. La reproducción de días pasados usa las del archivo diario.
    evidencia: Callable[[float], list[list[Any]]] | None = None
    # Si la fuente dejó sin datos al aeropuerto entre dos instantes (un hueco de la fuente no
    # abre nunca un aviso: la señal que lo toca, desde las tres horas previas, no cuenta).
    hueco_fuente: Callable[[str, float, float], bool] | None = None

    def _filas(self, ahora: float, vivas: list[list[Any]]) -> list[list[Any]]:
        return vivas if self.evidencia is None else self.evidencia(ahora)

    def activo(self, oaci: str) -> Aviso | None:
        return next(
            (a for a in self.avisos if a.oaci == oaci and a.estado in (POSIBLE, CONFIRMADO)), None
        )

    def evaluar(
        self, vigilados: Iterable[str], ahora: float, vivos: Vivos, fuente: str = ""
    ) -> list[Aviso]:
        """Un ciclo. Devuelve los avisos nuevos."""
        nuevos = []
        todas = vivos.todas()
        vigilados = list(vigilados)
        fuente_caida = self._fuente_caida(vigilados, ahora, vivos)
        for oaci in vigilados:
            movimientos = vivos.movimientos(oaci)
            aviso = self.activo(oaci)
            if aviso is not None:
                self._seguir(aviso, ahora, movimientos, self._filas(ahora, todas))
                continue
            s, motivo = senal(oaci, ahora, movimientos, self.bases, self.umbrales)
            if s is not None and fuente_caida:
                s, motivo = None, "fuente"
            if s is not None and oaci in vivos.actividad(ahora):
                s, motivo = None, "actividad_en_curso"
            if s is None:
                self.senales.pop(oaci, None)
                self.comienzos.pop(oaci, None)
                self.motivos[oaci] = motivo
                continue
            if self.hueco_fuente is not None and self.hueco_fuente(
                oaci, s.comienzo - HORAS_PREVIAS * 3600, ahora
            ):
                self.senales.pop(oaci, None)
                self.comienzos.pop(oaci, None)
                self.motivos[oaci] = "hueco_fuente"
                continue
            self.motivos[oaci] = "senal"
            desde = self.senales.setdefault(oaci, ahora)
            # El comienzo más temprano del episodio de señal: el METAR se mira desde ahí, para
            # que un hueco que explicó el tiempo no vuelva como aviso al moverse el comienzo.
            primero = min(self.comienzos.get(oaci, s.comienzo), s.comienzo)
            self.comienzos[oaci] = primero
            if ahora - desde < self.umbrales.persistencia_s:
                continue
            motivos: list[str] = []
            if self.metares is not None:
                motivos = metar.explica(
                    self.metares(oaci, primero - MARGEN_METAR_S, ahora),
                    datetime.fromtimestamp(primero - MARGEN_METAR_S, UTC),
                    datetime.fromtimestamp(ahora, UTC),
                )
            if motivos:
                self.motivos[oaci] = "meteorologia"
                continue
            nuevo = Aviso(
                oaci, s.comienzo, ahora, POSIBLE, s.esperados, s.vistos, fuente=fuente,
                factor=s.factor,
            )  # fmt: skip
            self._evidencia(nuevo, ahora, movimientos, self._filas(ahora, todas))
            self.avisos.append(nuevo)
            nuevos.append(nuevo)
        self._caducar(ahora)
        return nuevos

    def _fuente_caida(self, vigilados: list[str], ahora: float, vivos: Vivos) -> bool:
        """Si entre todos los aeropuertos vigilados se ha visto en los últimos 10 minutos menos
        de la mitad de lo esperado: el fallo es de la fuente o del archivo (un cierre afecta a
        uno o a unos pocos aeropuertos, nunca a la mitad del tráfico de Europa)."""
        hasta = ahora - RETRASO_S
        desde = hasta - VENTANA_GLOBAL_S
        esperados = sum(self.bases.esperados(o, desde, hasta) for o in vigilados)
        if esperados < ESPERADOS_GLOBALES_MINIMOS:
            return False
        vistos = 0
        for oaci in vigilados:
            tiempos = vivos.movimientos(oaci)
            vistos += bisect.bisect_right(tiempos, hasta) - bisect.bisect_left(tiempos, desde)
        return vistos < FRACCION_GLOBAL * esperados

    def _evidencia(
        self, aviso: Aviso, ahora: float, movimientos: list[float], todas: list[list[Any]]
    ) -> None:
        hasta = aviso.reanudado or (ahora - RETRASO_S)
        factor = aviso.factor
        aviso.esperados = self.bases.esperados(aviso.oaci, aviso.inicio, hasta) * factor
        aviso.vistos = sum(1 for t in movimientos if aviso.inicio < t < hasta)
        llegadas = self.bases.esperados(aviso.oaci, aviso.inicio, hasta, "llegadas") * factor
        salidas = self.bases.esperados(aviso.oaci, aviso.inicio, hasta, "salidas") * factor
        filas = [f for f in todas if f[0] == aviso.oaci and aviso.inicio < float(f[2]) < hasta]
        aviso.llegadas_perdidas = max(0, round(llegadas - sum(1 for f in filas if f[1] == "L")))
        aviso.salidas_perdidas = max(0, round(salidas - sum(1 for f in filas if f[1] == "D")))
        habituales = self.bases.habituales(aviso.oaci, aviso.inicio, hasta)
        desde = aviso.inicio - trafico.MARGEN_ANTES_S
        aviso.esperas = len(trafico.en_espera(aviso.oaci, desde, ahora, habituales, todas))
        aviso.desvios = len(trafico.desviados(aviso.oaci, desde, ahora, habituales, todas))

    def _seguir(
        self, aviso: Aviso, ahora: float, movimientos: list[float], todas: list[list[Any]]
    ) -> None:
        horizonte = ahora - RETRASO_S
        despues = [t for t in movimientos if aviso.inicio < t <= horizonte]
        recientes = [t for t in despues if t > horizonte - VENTANA_REANUDACION_S]
        esperados = self.bases.esperados(aviso.oaci, horizonte - VENTANA_REANUDACION_S, horizonte)
        if len(recientes) >= MOVIMIENTOS_REANUDACION and (
            len(recientes) >= FRACCION_REANUDACION * esperados
        ):
            aviso.reanudado = recientes[0]
            aviso.estado = REANUDADA
        self._evidencia(aviso, ahora, movimientos, todas)

    def _caducar(self, ahora: float) -> None:
        vigentes = []
        for a in self.avisos:
            if (
                a.estado == REANUDADA
                and ahora - (a.reanudado or a.detectado) > PUBLICAR_REANUDADO_S
            ):
                continue
            if a.estado != REANUDADA and ahora - a.detectado > CADUCIDAD_S:
                continue
            vigentes.append(a)
        self.avisos = vigentes


def confirmar(aviso: Aviso, incidentes: Iterable[dict[str, Any]]) -> bool:
    """Marca el aviso como confirmado si un incidente de la base en ese aeropuerto recoge el
    cierre en su ventana (desde tres horas antes del comienzo hasta doce después de la
    detección). Con una fuente oficial (fiabilidad A), la confirmación es oficial. Guarda la
    hora de la primera noticia: la fecha más temprana de sus fuentes con hora."""
    desde, hasta = aviso.inicio - 3 * 3600, aviso.detectado + 12 * 3600
    for incidente in incidentes:
        if incidente.get("objetivo", {}).get("oaci") != aviso.oaci:
            continue
        inicio, fin, _ = trafico.ventana_incidente(incidente)
        if fin < desde or inicio > hasta:
            continue
        fuentes = incidente.get("fuentes", [])
        oficial = any(f.get("fiabilidad") == "A" for f in fuentes)
        horas = [
            segundos(f["fecha"]["valor"])
            for f in fuentes
            if f.get("fecha", {}).get("precision") in ("minuto", "hora")
        ]
        aviso.confirmacion = {
            "tipo": "oficial" if oficial else "incidente",
            "incidente": incidente["id"],
            "hora": instante(min(horas)) if horas else None,
        }
        if horas:
            aviso.primera_noticia = min(horas)
        if aviso.estado == POSIBLE:
            aviso.estado = CONFIRMADO
        return True
    return False
