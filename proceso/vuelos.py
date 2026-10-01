"""Movimientos de cada aeronave en los aeropuertos: aterrizajes, despegues, aproximaciones
frustradas, desvíos y esperas, a partir de su traza de adsb.lol.

Una traza se parte en tramos (la marca de tramo nuevo de readsb, un hueco de más de 30
minutos o más de 10 minutos parada en tierra). En cada tramo, con la altitud sobre el
aeropuerto más cercano (a 15 km como mucho) de los puntos por debajo de 8000 pies:

- **Aterrizaje**: el tramo termina cerca de un aeropuerto por debajo de 2500 pies sobre él,
  después de haber estado más alto o más lejos, y baja a 1500 pies o menos (o toca tierra).
  La hora es la del primer punto en tierra o, sin él (sin cobertura a ras de pista), la del
  último punto en el aire.
- **Despegue**: el tramo empieza cerca de un aeropuerto, en tierra o por debajo de 2500 pies,
  y sube por encima. La hora es la del último punto en tierra o la del primero en el aire.
- **Sin cobertura a baja altura** (en muchos aeropuertos los receptores de adsb.lol no ven los
  aviones por debajo de unos miles de pies, o solo en un sentido): cuenta como aterrizaje un
  tramo que termina a 30 km o menos de un aeropuerto con tráfico regular, por debajo de 6000
  pies sobre él, acercándose (3 km o más) y bajando (1000 pies o más) en sus últimos 5
  minutos; y como despegue, el que empieza así alejándose y subiendo. La hora se estima con la
  distancia que queda y la velocidad (como mucho 15 minutos).
- **Aproximación frustrada**: en mitad del tramo baja a 1000 pies o menos sobre un aeropuerto,
  a 8 km o menos de un umbral y alineada con su pista (25°), a más de 80 nudos y sin tocar
  tierra, y vuelve a subir por encima de 2000 pies en 10 minutos o menos, sin alejarse más
  de 25 km y sin huecos de más de 2 minutos en la traza (un hueco largo con el avión bajo es
  una escala sin cobertura en tierra, no una frustrada). Es el mismo criterio que la biblioteca
  «traffic» (dos intentos de aterrizaje alineados con la pista con una subida entre ellos), con
  una tolerancia de alineación en grados porque la cobertura a baja altura es irregular.
- **Desvío**: el tramo termina en un aeropuerto B, pero antes iba a otro A con tráfico regular,
  a 50 km o más de B: hizo una espera asignada a A, o bajaba hacia A (a 40 km o menos y por
  debajo de 8000 pies sobre él, con el rumbo a 20° o menos de A y a más de 45° del de B,
  acercándose y perdiendo altura de un minuto al siguiente) y después se alejó 20 km de su
  punto más cercano a A. La hora es la del punto más cercano a A o la del fin de la espera.
- **Espera**: el detector de la biblioteca «traffic» (`proceso/espera.py`) en los puntos en el
  aire por debajo de 25 000 pies; se asigna al aeropuerto de llegada si está a 120 km o menos y,
  si no, al aeropuerto con tráfico regular más cercano en ese radio.

Las distancias son las de la aproximación equirrectangular, de sobra precisa a menos de 150 km.
"""

import json
import math
from collections.abc import Iterator
from dataclasses import dataclass, field
from functools import cache
from pathlib import Path

from proceso import espera

AEROPUERTOS = Path(__file__).resolve().parent.parent / "configuracion" / "aeropuertos_trafico.json"
KM_POR_GRADO_LAT = 110.57
KM_POR_GRADO_LON_ECUADOR = 111.32

HUECO_TRAMO_S = 1800.0
HUECO_ESCALA_S = 600.0
ESCALA_FT = 5000.0
PARADA_TIERRA_S = 600.0
RADIO_AEROPUERTO_KM = 15.0
ALTITUD_BAJA_FT = 8000.0
BAJO_FT = 2500.0
MUY_BAJO_FT = 1500.0
FRUSTRADA_FT = 1000.0
FRUSTRADA_SUBIDA_FT = 2000.0
FRUSTRADA_UMBRAL_KM = 8.0
FRUSTRADA_ALEJAMIENTO_KM = 25.0
FRUSTRADA_HUECO_S = 120.0
FRUSTRADA_ALTO_FT = 3000.0
FRUSTRADA_SUBIDA_S = 600.0
FRUSTRADA_VELOCIDAD_KT = 80.0
ALINEACION_GRADOS = 25.0
DESVIO_RADIO_KM = 100.0
DESVIO_APROXIMACION_KM = 40.0
DESVIO_APROXIMACION_FT = 8000.0
DESVIO_TECHO_FT = 15000.0
DESVIO_SEPARACION_KM = 50.0
DESVIO_MUESTRA_S = 60.0
DESVIO_ANGULO = 20.0
DESVIO_ANGULO_DESTINO = 45.0
DESVIO_ALEJAMIENTO_KM = 20.0
INDICE_RADIO_KM = 25.0
EXTREMO_RADIO_KM = 30.0
EXTREMO_ALTURA_FT = 6000.0
EXTREMO_DESCENSO_FT = 1000.0
EXTREMO_ACERCAMIENTO_KM = 3.0
EXTREMO_VENTANA_S = 300.0
EXTREMO_VELOCIDAD_KT = 150.0
EXTREMO_MAXIMO_S = 900.0
ESPERA_TECHO_FT = 25000.0
ESPERA_RADIO_KM = 120.0
CELDA_INDICE = 0.25


@dataclass(frozen=True)
class Pista:
    id: str
    lat: float
    lon: float
    rumbo: float


@dataclass(frozen=True)
class Aeropuerto:
    oaci: str
    nombre: str
    pais: str
    lat: float
    lon: float
    elev_ft: float
    grande: bool
    regular: bool
    pistas: tuple[Pista, ...] = ()


def distancia_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    coseno = math.cos(math.radians((lat1 + lat2) / 2))
    dx = (lon2 - lon1) * KM_POR_GRADO_LON_ECUADOR * coseno
    dy = (lat2 - lat1) * KM_POR_GRADO_LAT
    return math.hypot(dx, dy)


def rumbo_hacia(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    coseno = math.cos(math.radians((lat1 + lat2) / 2))
    dx = (lon2 - lon1) * coseno
    dy = lat2 - lat1
    return math.degrees(math.atan2(dx, dy)) % 360


def diferencia_angular(a: float, b: float) -> float:
    return abs((a - b + 180.0) % 360.0 - 180.0)


@cache
def cargar_aeropuertos(ruta: Path = AEROPUERTOS) -> tuple[Aeropuerto, ...]:
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    return tuple(
        Aeropuerto(
            oaci=a["oaci"],
            nombre=a["nombre"],
            pais=a["pais"],
            lat=a["lat"],
            lon=a["lon"],
            elev_ft=float(a["elev_ft"]),
            grande=a["grande"],
            regular=a["regular"],
            pistas=tuple(Pista(p["id"], p["lat"], p["lon"], p["rumbo"]) for p in a["pistas"]),
        )
        for a in datos["aeropuertos"]
    )


class Indice:
    """Aeropuertos por celdas de 0,25°: cada celda lista los que pueden estar a menos de 25 km
    de un punto suyo (y aparte, los regulares a menos de 100 km, para los desvíos), así que
    una consulta solo mira esos."""

    def __init__(
        self, aeropuertos: tuple[Aeropuerto, ...], radio_km: float = INDICE_RADIO_KM
    ) -> None:
        self.aeropuertos = aeropuertos
        self.por_oaci = {a.oaci: a for a in aeropuertos}
        self._celdas = _rejilla(aeropuertos, radio_km)
        self._regulares = _rejilla(tuple(a for a in aeropuertos if a.regular), DESVIO_RADIO_KM)

    def regulares_cerca(self, lat: float, lon: float) -> list[Aeropuerto]:
        """Los aeropuertos con tráfico regular que pueden estar a 100 km o menos."""
        return self._regulares.get((_celda(lat), _celda(lon)), [])

    def candidatos(self, lat: float, lon: float) -> list[Aeropuerto]:
        return self._celdas.get((_celda(lat), _celda(lon)), [])

    def cercano(
        self, lat: float, lon: float, radio_km: float | None = None, solo_regulares: bool = False
    ) -> tuple[Aeropuerto, float] | None:
        radio = RADIO_AEROPUERTO_KM if radio_km is None else radio_km
        mejor: tuple[Aeropuerto, float] | None = None
        for a in self.candidatos(lat, lon):
            if solo_regulares and not a.regular:
                continue
            d = distancia_km(lat, lon, a.lat, a.lon)
            if d <= radio and (mejor is None or d < mejor[1]):
                mejor = (a, d)
        return mejor


def _rejilla(
    aeropuertos: tuple[Aeropuerto, ...], radio_km: float
) -> dict[tuple[int, int], list[Aeropuerto]]:
    celdas: dict[tuple[int, int], list[Aeropuerto]] = {}
    margen_lat = radio_km / KM_POR_GRADO_LAT
    for a in aeropuertos:
        margen_lon = radio_km / (KM_POR_GRADO_LON_ECUADOR * math.cos(math.radians(a.lat)))
        for i in range(_celda(a.lat - margen_lat), _celda(a.lat + margen_lat) + 1):
            for j in range(_celda(a.lon - margen_lon), _celda(a.lon + margen_lon) + 1):
                celdas.setdefault((i, j), []).append(a)
    return celdas


def _celda(grados: float) -> int:
    return math.floor(grados / CELDA_INDICE)


@dataclass
class Traza:
    """La traza de un día de una aeronave, ya ordenada por tiempo y sin puntos repetidos.
    Altitud barométrica en pies (None si no se conoce); `suelo` si readsb la da en tierra."""

    icao: str
    matricula: str | None = None
    tipo: str | None = None
    marcas: int = 0
    descripcion: str | None = None
    operador: str | None = None
    categoria: str | None = None
    t: list[float] = field(default_factory=list)
    lat: list[float] = field(default_factory=list)
    lon: list[float] = field(default_factory=list)
    alt: list[float | None] = field(default_factory=list)
    suelo: list[bool] = field(default_factory=list)
    gs: list[float | None] = field(default_factory=list)
    rumbo: list[float | None] = field(default_factory=list)
    vz: list[float | None] = field(default_factory=list)
    tramo_nuevo: list[bool] = field(default_factory=list)
    nic: list[int | None] = field(default_factory=list)
    nacp: list[int | None] = field(default_factory=list)
    version: list[int | None] = field(default_factory=list)
    adsb: list[bool] = field(default_factory=list)
    indicativo: list[str | None] = field(default_factory=list)

    def __len__(self) -> int:
        return len(self.t)


@dataclass(frozen=True)
class Movimiento:
    """Un movimiento en un aeropuerto. tipo: L (aterrizaje), D (despegue), G (frustrada),
    V (desvío: `otro` es el aeropuerto donde aterrizó), H (espera, de `t` a `fin`)."""

    oaci: str
    tipo: str
    t: float
    icao: str
    indicativo: str | None
    tipo_aeronave: str | None
    ifr: bool
    fin: float | None = None
    otro: str | None = None
    lat: float | None = None
    lon: float | None = None

    def fila(self) -> list[object]:
        fila: list[object] = [
            self.oaci,
            self.tipo,
            round(self.t),
            self.icao,
            self.indicativo,
            self.tipo_aeronave,
            int(self.ifr),
        ]
        if self.tipo == "H":
            fila += [round(self.fin or self.t), self.lat, self.lon]
        elif self.tipo == "V":
            fila += [self.otro]
        return fila


def _bajo_o_suelo(traza: Traza, i: int) -> bool:
    alt = traza.alt[i]
    return traza.suelo[i] or (alt is not None and alt < ESCALA_FT)


def tramos(traza: Traza) -> Iterator[tuple[int, int]]:
    """Índices [inicio, fin] de cada tramo de la traza: se corta en la marca de tramo nuevo,
    en un hueco de más de 30 minutos, en un hueco de más de 10 con el avión por debajo de
    5000 pies a ambos lados y tras 10 minutos parada en tierra (lo que sigue es el vuelo
    siguiente, que empieza en tierra)."""
    n = len(traza)
    if not n:
        return
    inicio = 0
    tierra_desde: float | None = None
    cortado = False
    for i in range(1, n):
        hueco = traza.t[i] - traza.t[i - 1]
        corte = traza.tramo_nuevo[i] or hueco > HUECO_TRAMO_S
        # Un hueco de más de 10 minutos con el avión bajo antes y después es una escala sin
        # cobertura en tierra: aterrizó y volvió a despegar.
        if hueco > HUECO_ESCALA_S and _bajo_o_suelo(traza, i - 1) and _bajo_o_suelo(traza, i):
            corte = True
        if traza.suelo[i] and (traza.gs[i] or 0.0) < 50:
            if tierra_desde is None:
                tierra_desde, cortado = traza.t[i], False
            elif not cortado and traza.t[i] - tierra_desde > PARADA_TIERRA_S:
                corte, cortado = True, True
        else:
            tierra_desde = None
        if corte:
            yield inicio, i - 1
            inicio = i
    yield inicio, n - 1


@dataclass
class _Contexto:
    traza: Traza
    indice: Indice
    cerca: list[tuple[Aeropuerto, float] | None]
    altura: list[float | None]


def _contexto(traza: Traza, indice: Indice, a: int, b: int) -> _Contexto:
    cerca: list[tuple[Aeropuerto, float] | None] = []
    altura: list[float | None] = []
    for i in range(a, b + 1):
        alt, suelo = traza.alt[i], traza.suelo[i]
        if suelo or (alt is not None and alt < ALTITUD_BAJA_FT):
            c = indice.cercano(traza.lat[i], traza.lon[i])
        else:
            c = None
        cerca.append(c)
        if c is None:
            altura.append(None)
        else:
            altura.append(0.0 if suelo else (alt - c[0].elev_ft if alt is not None else None))
    return _Contexto(traza, indice, cerca, altura)


def _bajo(ctx: _Contexto, k: int, oaci: str, techo: float = BAJO_FT) -> bool:
    c, h = ctx.cerca[k], ctx.altura[k]
    return c is not None and c[0].oaci == oaci and h is not None and h <= techo


def _mov(
    traza: Traza, oaci: str, tipo: str, i: int, ifr: bool, otro: str | None = None
) -> Movimiento:
    return Movimiento(
        oaci, tipo, traza.t[i], traza.icao, traza.indicativo[i], traza.tipo, ifr, otro=otro
    )


def _aterrizaje(ctx: _Contexto, a: int, b: int, ifr: bool) -> Movimiento | None:
    n = b - a + 1
    final = ctx.cerca[n - 1]
    if final is None:
        return None
    oaci = final[0].oaci
    k = n - 1
    while k >= 0 and _bajo(ctx, k, oaci):
        k -= 1
    primero = k + 1
    if primero == 0:
        return None  # todo el tramo está bajo junto al aeropuerto: movimientos en tierra
    segmento = range(primero, n)
    if not any(ctx.traza.suelo[a + j] or (ctx.altura[j] or 1e9) <= MUY_BAJO_FT for j in segmento):
        return None
    suelo = [j for j in segmento if ctx.traza.suelo[a + j]]
    j = suelo[0] if suelo else max(j for j in segmento if not ctx.traza.suelo[a + j])
    return _mov(ctx.traza, oaci, "L", a + j, ifr)


def _despegue(ctx: _Contexto, a: int, b: int, ifr: bool) -> Movimiento | None:
    n = b - a + 1
    inicial = ctx.cerca[0]
    if inicial is None:
        return None
    oaci = inicial[0].oaci
    k = 0
    while k < n and _bajo(ctx, k, oaci):
        k += 1
    if k >= n:
        return None
    if not (ctx.traza.suelo[a] or (ctx.altura[0] or 1e9) <= MUY_BAJO_FT):
        return None
    suelo = [j for j in range(k) if ctx.traza.suelo[a + j]]
    j = suelo[-1] if suelo else 0
    return _mov(ctx.traza, oaci, "D", a + j, ifr)


def _punto_a(ctx: _Contexto, i: int, paso: int, limite: int) -> int:
    """El punto del tramo a 5 minutos de `i` hacia atrás (paso −1) o hacia delante (+1), o el
    extremo del tramo si está más cerca."""
    t = ctx.traza.t
    k = i
    while k != limite and abs(t[k] - t[i]) < EXTREMO_VENTANA_S:
        k += paso
    return k


def _estimado(ctx: _Contexto, a: int, b: int, ifr: bool, llegada: bool) -> Movimiento | None:
    """Llegada o salida sin puntos a ras de pista, donde la cobertura no llega a baja altura:
    el tramo termina (o empieza) a 30 km o menos de un aeropuerto con tráfico regular, por
    debajo de 6000 pies sobre él, acercándose y bajando 1000 pies o más en sus últimos 5
    minutos (o alejándose y subiendo en los primeros). La hora es la del extremo más el tiempo
    de recorrer la distancia que queda a su velocidad (como mucho 15 minutos)."""
    t = ctx.traza
    i = b if llegada else a
    alt_i = t.alt[i]
    if t.suelo[i] or alt_i is None or alt_i > ALTITUD_BAJA_FT:
        return None
    j = _punto_a(ctx, i, -1 if llegada else 1, a if llegada else b)
    alt_j = t.alt[j]
    if j == i or alt_j is None or t.suelo[j] or alt_j - alt_i < EXTREMO_DESCENSO_FT:
        return None
    mejor: tuple[float, Aeropuerto] | None = None
    for aeropuerto in ctx.indice.regulares_cerca(t.lat[i], t.lon[i]):
        d_i = distancia_km(t.lat[i], t.lon[i], aeropuerto.lat, aeropuerto.lon)
        if d_i > EXTREMO_RADIO_KM or alt_i - aeropuerto.elev_ft > EXTREMO_ALTURA_FT:
            continue
        d_j = distancia_km(t.lat[j], t.lon[j], aeropuerto.lat, aeropuerto.lon)
        if d_j - d_i < EXTREMO_ACERCAMIENTO_KM:
            continue
        if mejor is None or d_i < mejor[0]:
            mejor = (d_i, aeropuerto)
    if mejor is None:
        return None
    distancia, aeropuerto = mejor
    velocidad_kms = max(t.gs[i] or 0.0, EXTREMO_VELOCIDAD_KT) * 1.852 / 3600
    recorrido = min(distancia / velocidad_kms, EXTREMO_MAXIMO_S)
    instante = t.t[i] + recorrido if llegada else t.t[i] - recorrido
    return Movimiento(aeropuerto.oaci, "L" if llegada else "D", instante, t.icao,
                      t.indicativo[i], t.tipo, ifr)  # fmt: skip


def _alineado(aeropuerto: Aeropuerto, lat: float, lon: float, rumbo: float | None) -> bool:
    """A 8 km o menos de un umbral, yendo hacia él y con el rumbo de su pista (25°)."""
    if not aeropuerto.pistas:
        return distancia_km(lat, lon, aeropuerto.lat, aeropuerto.lon) <= FRUSTRADA_UMBRAL_KM
    for pista in aeropuerto.pistas:
        if distancia_km(lat, lon, pista.lat, pista.lon) > FRUSTRADA_UMBRAL_KM:
            continue
        if rumbo is None or diferencia_angular(rumbo, pista.rumbo) <= ALINEACION_GRADOS:
            return True
    return False


def _frustradas(ctx: _Contexto, a: int, b: int, ifr: bool) -> list[Movimiento]:
    t = ctx.traza
    n = b - a + 1
    resultado = []
    j = 0
    # Solo cuenta una bajada después de haber estado arriba (más de 3000 pies sobre el
    # aeropuerto más cercano o por encima de 8000): la subida inicial de un despegue no es
    # una frustrada.
    alto = False
    while j < n:
        c, h = ctx.cerca[j], ctx.altura[j]
        alt = t.alt[a + j]
        if t.suelo[a + j]:
            alto = False
        elif (c is None and alt is not None) or (h is not None and h > FRUSTRADA_ALTO_FT):
            alto = True
        if not alto or c is None or h is None or t.suelo[a + j] or h > FRUSTRADA_FT:
            j += 1
            continue
        aeropuerto = c[0]
        # El tramo bajo sobre este aeropuerto, sin tocar tierra.
        k = j
        minimo = j
        toca = False
        while k < n and _bajo(ctx, k, aeropuerto.oaci, FRUSTRADA_SUBIDA_FT):
            toca = toca or t.suelo[a + k]
            if (ctx.altura[k] or 0) < (ctx.altura[minimo] or 0):
                minimo = k
            k += 1
        sube = False
        m = k
        while m < n:
            i = a + m
            if (
                distancia_km(t.lat[i], t.lon[i], aeropuerto.lat, aeropuerto.lon)
                > FRUSTRADA_ALEJAMIENTO_KM
            ):
                break
            alt = t.alt[i]
            if (
                alt is not None
                and not t.suelo[i]
                and alt - aeropuerto.elev_ft > FRUSTRADA_SUBIDA_FT
            ):
                sube = True
                break
            m += 1
        i = a + minimo
        continuo = sube and all(
            t.t[a + x + 1] - t.t[a + x] <= FRUSTRADA_HUECO_S for x in range(max(0, j - 1), m)
        )
        rapida = sube and t.t[a + m] - t.t[i] <= FRUSTRADA_SUBIDA_S
        en_vuelo = (t.gs[i] or FRUSTRADA_VELOCIDAD_KT) >= FRUSTRADA_VELOCIDAD_KT
        if (
            not toca
            and continuo
            and rapida
            and en_vuelo
            and j > 0
            and _alineado(aeropuerto, t.lat[i], t.lon[i], t.rumbo[i])
        ):
            resultado.append(_mov(t, aeropuerto.oaci, "G", i, ifr))
        alto = False
        j = max(k, j + 1)
    return resultado


def _desvio(
    ctx: _Contexto, a: int, b: int, llegada: Movimiento, esperas: list[Movimiento], ifr: bool
) -> Movimiento | None:
    """El primer desvío del tramo: una espera asignada a otro aeropuerto o una aproximación a
    otro aeropuerto antes de aterrizar en el de llegada."""
    t = ctx.traza
    destino = ctx.indice.por_oaci[llegada.oaci]

    def lejos(oaci: str) -> bool:
        otro = ctx.indice.por_oaci[oaci]
        return distancia_km(otro.lat, otro.lon, destino.lat, destino.lon) >= DESVIO_SEPARACION_KM

    for e in esperas:
        if e.oaci != destino.oaci and e.t < llegada.t and lejos(e.oaci):
            return Movimiento(
                e.oaci, "V", e.fin or e.t, t.icao, e.indicativo, t.tipo, ifr, otro=destino.oaci
            )
    # Puntos en descenso por debajo de 15 000 pies, uno por minuto, antes del aterrizaje.
    muestras: list[int] = []
    ultimo = -1e18
    for i in range(a, b + 1):
        if t.t[i] >= llegada.t:
            break
        alt, rumbo = t.alt[i], t.rumbo[i]
        if t.suelo[i] or alt is None or rumbo is None or alt > DESVIO_TECHO_FT:
            continue
        if t.t[i] - ultimo >= DESVIO_MUESTRA_S:
            muestras.append(i)
            ultimo = t.t[i]
    for x, i in enumerate(muestras[:-1]):
        siguiente = muestras[x + 1]
        lat, lon, rumbo = t.lat[i], t.lon[i], t.rumbo[i] or 0.0
        alt_i, alt_s = t.alt[i] or 0.0, t.alt[siguiente] or 0.0
        if alt_s >= alt_i:
            continue  # no está bajando
        hacia_destino = rumbo_hacia(lat, lon, destino.lat, destino.lon)
        if diferencia_angular(rumbo, hacia_destino) < DESVIO_ANGULO_DESTINO:
            continue  # va hacia su destino: puede pasar por encima de otro aeropuerto
        for otro in ctx.indice.regulares_cerca(lat, lon):
            if otro.oaci == destino.oaci or not lejos(otro.oaci):
                continue
            d = distancia_km(lat, lon, otro.lat, otro.lon)
            if d > DESVIO_APROXIMACION_KM or alt_i - otro.elev_ft > DESVIO_APROXIMACION_FT:
                continue
            if diferencia_angular(rumbo, rumbo_hacia(lat, lon, otro.lat, otro.lon)) > DESVIO_ANGULO:
                continue
            d_s = distancia_km(t.lat[siguiente], t.lon[siguiente], otro.lat, otro.lon)
            if d_s >= d:
                continue  # no se acerca
            # Después se aleja: el más cercano a ese aeropuerto y luego 20 km más lejos.
            minimo, k_min = d, i
            for k in range(i, b + 1):
                if t.t[k] >= llegada.t:
                    break
                dk = distancia_km(t.lat[k], t.lon[k], otro.lat, otro.lon)
                if dk < minimo:
                    minimo, k_min = dk, k
                elif dk - minimo >= DESVIO_ALEJAMIENTO_KM:
                    return _mov(t, otro.oaci, "V", k_min, ifr, otro=destino.oaci)
    return None


def _esperas(
    ctx: _Contexto, a: int, b: int, llegada: Movimiento | None, ifr: bool
) -> list[Movimiento]:
    t = ctx.traza
    indices = [
        i
        for i in range(a, b + 1)
        if not t.suelo[i]
        and t.rumbo[i] is not None
        and (t.alt[i] or 0) < ESPERA_TECHO_FT
        and t.alt[i] is not None
    ]
    if len(indices) < 2:
        return []
    tiempos = [t.t[i] for i in indices]
    rumbos = [t.rumbo[i] or 0.0 for i in indices]
    resultado = []
    for e in espera.detectar(tiempos, rumbos):
        medio = indices[(e.indice_inicio + e.indice_fin) // 2]
        lat, lon = t.lat[medio], t.lon[medio]
        aeropuerto: Aeropuerto | None = None
        if llegada is not None:
            destino = ctx.indice.por_oaci[llegada.oaci]
            if distancia_km(lat, lon, destino.lat, destino.lon) <= ESPERA_RADIO_KM:
                aeropuerto = destino
        if aeropuerto is None:
            cercano = ctx.indice.cercano(lat, lon, ESPERA_RADIO_KM, solo_regulares=True)
            aeropuerto = cercano[0] if cercano else None
        if aeropuerto is None:
            continue
        resultado.append(
            Movimiento(
                aeropuerto.oaci,
                "H",
                e.inicio,
                t.icao,
                t.indicativo[indices[e.indice_inicio]],
                t.tipo,
                ifr,
                fin=e.fin,
                lat=round(lat, 4),
                lon=round(lon, 4),
            )
        )
    return resultado


def analizar(traza: Traza, indice: Indice, ifr: bool) -> list[Movimiento]:
    """Todos los movimientos de una traza en los aeropuertos del índice."""
    resultado: list[Movimiento] = []
    for a, b in tramos(traza):
        if b - a < 1:
            continue
        ctx = _contexto(traza, indice, a, b)
        despegue = _despegue(ctx, a, b, ifr) or _estimado(ctx, a, b, ifr, llegada=False)
        llegada = _aterrizaje(ctx, a, b, ifr) or _estimado(ctx, a, b, ifr, llegada=True)
        if despegue is not None:
            resultado.append(despegue)
        resultado += _frustradas(ctx, a, b, ifr)
        esperas = _esperas(ctx, a, b, llegada, ifr)
        resultado += esperas
        if llegada is not None:
            resultado.append(llegada)
            desvio = _desvio(ctx, a, b, llegada, esperas, ifr)
            if desvio is not None:
                resultado.append(desvio)
    return resultado
