"""Recorridos de los grupos de una noche: un grupo, una línea continua desde donde aparece hasta
donde desaparece, para que en el mapa se lea por dónde entró y hacia dónde fue.

**Trozos.** Con NEPTUN, cada pista (una amenaza con sus puntos) es un trozo. Con la Fuerza Aérea,
cada tramo de la reconstrucción (proceso/rutas/reconstruccion.py) es un trozo de dos puntos.

**Enlaces entre trozos.** NEPTUN cambia de pista a menudo para el mismo grupo (la mitad de las
pistas dura menos de 8 minutos). Un trozo B sigue a un trozo A si:

- B empieza entre 10 minutos antes y 30 minutos después de que A llegue a su último punto (NEPTUN
  abre a veces la pista nueva mientras repite la última posición de la vieja);
- la distancia del final de A al principio de B, menos sus radios, se recorre a 250 km/h como
  mucho en ese tiempo;
- B va en la misma dirección que A (60° como mucho entre sus rumbos) y, si están separados, B
  está hacia donde iba A; sin rumbo en alguno de los dos, solo si se tocan.

No se inventan identidades: se enlazan A y B solo si B es el único que puede seguir a A y A el
único que puede preceder a B (sin contar los atajos: si A puede seguir con B y con C, y C ya sigue
a B, lo de A es B). Si de A salen varios trozos que solo pueden venir de A y A lleva al
menos tantos aparatos como trozos salen, el grupo se divide (la línea se bifurca); al revés, se
unen. Cualquier otra duda deja los trozos sin enlazar. Con la Fuerza Aérea los enlaces son los de
la reconstrucción (tramos que comparten zona), con sus divisiones y uniones.

**Grupo.** Los trozos enlazados forman un grupo. Sus líneas van de cada principio a cada final
(una por rama), suavizadas para que no hagan dientes.

**Avisos de región entera.** Un punto cuya incertidumbre es de 45 km o más, o un aviso «por
región», no se dibuja: sirve para enlazar el recorrido si hay puntos precisos antes y después,
pero la línea pasa de largo por él y no pinta ninguna zona.

**Franja.** La incertidumbre se ve como una franja alrededor de la línea, más ancha donde la
posición es menos precisa: el radio de cada punto, entre 2 y 15 km. Nunca una mancha de media
región.

**Orden.** Solo tienen recorrido los grupos que se desplazan 20 km o más (menos no dice hacia
dónde fueron a la escala de Ucrania). Se ordenan por aparatos (los que constan; 1 si no consta) y,
a igualdad, por la longitud del recorrido. La web dibuja los principales.
"""

import itertools
import math
import statistics
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from proceso.rutas import geometria
from proceso.rutas.neptun import instante

VERSION = "recorridos-1.0.0"
HUECO_MAX = timedelta(minutes=30)
SOLAPE_MAX = timedelta(minutes=10)
VELOCIDAD_MAX_KMH = 250.0
ANGULO_MAX = 60.0
# Desplazamiento mínimo para que un trozo tenga dirección propia.
DESPLAZAMIENTO_MIN_KM = 5.0
# Un recorrido más corto no dice hacia dónde fue el grupo a la escala de Ucrania: no se dibuja.
LONGITUD_MIN_KM = 20.0
# Separación que se tiene por «se tocan» además de los radios.
TOCAN_KM = 5.0
# Un punto así de impreciso es un aviso de región entera: enlaza, pero no se dibuja.
REGION_ENTERA_KM = 45.0
TITULO_REGION = "по області"
ANCHO_MIN_KM = 2.0
ANCHO_MAX_KM = 15.0
RADIO_DEFECTO_KM = 5.0
# Ramas como mucho por grupo (de cada principio a cada final).
RAMAS_MAX = 8
SUAVIZADO = 2
DECIMALES = 4


@dataclass
class Punto:
    t: datetime | None
    lat: float
    lon: float
    radio: float
    vago: bool
    numero: int | None = None
    kmh: float | None = None
    rumbo: float | None = None


@dataclass
class Trozo:
    id: str
    puntos: list[Punto]
    tipo: str = "ataque"
    numero: int | None = None
    confianza: str | None = None
    sucesores: list[int] = field(default_factory=list)
    predecesores: list[int] = field(default_factory=list)
    division: bool = False
    union: bool = False

    @property
    def inicio(self) -> Punto:
        return self.puntos[0]

    @property
    def fin(self) -> Punto:
        """El último punto, con la hora en que llegó allí: NEPTUN repite la última posición de
        una pista mientras abre otra para el mismo grupo, y esa repetición no es vuelo."""
        ultimo = self.puntos[-1]
        llegada = ultimo.t
        for p in reversed(self.puntos[:-1]):
            if abs(p.lat - ultimo.lat) > 1e-4 or abs(p.lon - ultimo.lon) > 1e-4:
                break
            llegada = p.t
        return Punto(llegada, ultimo.lat, ultimo.lon, ultimo.radio, ultimo.vago, ultimo.numero,
                     ultimo.kmh, ultimo.rumbo)  # fmt: skip

    def precisos(self) -> list[Punto]:
        return [p for p in self.puntos if not p.vago]

    def direccion(self) -> float | None:
        """Rumbo del trozo: el de su desplazamiento si se mueve; si no, el que da la fuente."""
        precisos = self.precisos() or self.puntos
        a, b = precisos[0], precisos[-1]
        if geometria.distancia_km(a.lat, a.lon, b.lat, b.lon) >= DESPLAZAMIENTO_MIN_KM:
            return geometria.rumbo(a.lat, a.lon, b.lat, b.lon)
        rumbos = [p.rumbo for p in self.puntos if p.rumbo is not None]
        return rumbos[-1] if rumbos else None


# --- Trozos ------------------------------------------------------------------------------------


def _vago(radio: float) -> bool:
    return radio >= REGION_ENTERA_KM


def trozos_neptun(pistas: Sequence[dict[str, Any]], tipos: Sequence[str] = ("uav",)) -> list[Trozo]:
    trozos = []
    for pista in pistas:
        # Las pistas de una noche ya son de drones (neptun.pistas); sin tipo, se toman como tales.
        if pista.get("tipo", tipos[0]) not in tipos:
            continue
        por_region = TITULO_REGION in str(pista.get("titulo") or "")
        puntos = []
        for p in pista["puntos"]:
            radio = float(p.get("incertidumbre_km") or RADIO_DEFECTO_KM)
            puntos.append(
                Punto(
                    t=instante(p["t"]),
                    lat=float(p["lat"]),
                    lon=float(p["lon"]),
                    radio=radio,
                    vago=por_region or _vago(radio),
                    numero=int(p["numero"]) if isinstance(p.get("numero"), int) else None,
                    kmh=float(p["kmh"]) if isinstance(p.get("kmh"), int | float) else None,
                    rumbo=float(p["rumbo"]) if isinstance(p.get("rumbo"), int | float) else None,
                )
            )
        if len(puntos) < 2:
            continue
        numeros = [p.numero for p in puntos if p.numero is not None]
        confianzas = [p.get("confianza") for p in pista["puntos"] if p.get("confianza")]
        trozos.append(
            Trozo(
                id=str(pista["id"]),
                puntos=puntos,
                numero=max(numeros) if numeros else None,
                confianza=str(confianzas[-1]) if confianzas else None,
            )
        )
    return trozos


def _punto_de_extremo(extremo: dict[str, Any]) -> Punto:
    radio = float(extremo.get("radio_km") or RADIO_DEFECTO_KM)
    return Punto(
        t=instante(extremo["t"]) if extremo.get("t") else None,
        lat=float(extremo["lat"]),
        lon=float(extremo["lon"]),
        radio=radio,
        vago=_vago(radio),
    )


def _clave(extremo: dict[str, Any]) -> tuple[float, float, float]:
    return (round(extremo["lat"], 2), round(extremo["lon"], 2), round(extremo["radio_km"]))


def trozos_fuerza_aerea(tramos: Sequence[dict[str, Any]]) -> list[Trozo]:
    """Un trozo por tramo, enlazados por la zona que comparten (las de la reconstrucción)."""
    trozos = []
    for i, t in enumerate(tramos):
        numero = t.get("numero")
        maximo = numero["max"] if isinstance(numero, dict) else numero
        puntos = [_punto_de_extremo(t["desde"]), _punto_de_extremo(t["hasta"])]
        if t.get("kmh"):
            puntos[-1].kmh = float(t["kmh"])
        trozos.append(
            Trozo(
                id=f"tramo-{i + 1}",
                puntos=puntos,
                tipo=str(t.get("tipo") or "ataque"),
                numero=int(maximo) if isinstance(maximo, int) else None,
                division=bool(t.get("division")),
                union=bool(t.get("union")),
            )
        )
    por_desde: dict[tuple[float, float, float], list[int]] = {}
    for i, t in enumerate(tramos):
        por_desde.setdefault(_clave(t["desde"]), []).append(i)
    for i, t in enumerate(tramos):
        for j in por_desde.get(_clave(t["hasta"]), []):
            if j != i:
                trozos[i].sucesores.append(j)
                trozos[j].predecesores.append(i)
    return trozos


# --- Enlaces entre pistas de NEPTUN ------------------------------------------------------------


def _puede_seguir(a: Trozo, b: Trozo) -> bool:
    fin, inicio = a.fin, b.inicio
    if fin.t is None or inicio.t is None or a.tipo != b.tipo:
        return False
    hueco = inicio.t - fin.t
    if hueco < -SOLAPE_MAX or hueco > HUECO_MAX:
        return False
    d = geometria.distancia_km(fin.lat, fin.lon, inicio.lat, inicio.lon)
    separacion = max(0.0, d - fin.radio - inicio.radio)
    horas = max(hueco.total_seconds(), 60.0) / 3600.0
    if separacion > VELOCIDAD_MAX_KMH * horas:
        return False
    da, db = a.direccion(), b.direccion()
    if da is None or db is None:
        return separacion <= TOCAN_KM
    if geometria.diferencia_angular(da, db) > ANGULO_MAX:
        return False
    if separacion > TOCAN_KM:
        hacia = geometria.rumbo(fin.lat, fin.lon, inicio.lat, inicio.lon)
        return geometria.diferencia_angular(da, hacia) <= ANGULO_MAX
    return True


def enlazar(trozos: list[Trozo]) -> None:
    """Enlaces sin dudas entre trozos (ver el docstring del módulo)."""
    orden = sorted(
        range(len(trozos)), key=lambda i: trozos[i].inicio.t or datetime.min.replace(tzinfo=UTC)
    )
    candidatos: dict[int, list[int]] = {i: [] for i in range(len(trozos))}
    previos: dict[int, list[int]] = {i: [] for i in range(len(trozos))}
    for i in range(len(trozos)):
        a = trozos[i]
        if a.fin.t is None:
            continue
        for j in orden:
            b = trozos[j]
            if j == i or b.inicio.t is None:
                continue
            if b.inicio.t - a.fin.t > HUECO_MAX:
                break
            if _puede_seguir(a, b):
                candidatos[i].append(j)
                previos[j].append(i)
    # Si A puede seguir con B y con C, y C ya sigue a B, A sigue con B: C llega por B. Igual al
    # revés. Así un atajo posible no se toma por una duda.
    for i in candidatos:
        atajos = {j for j in candidatos[i] if any(j in candidatos[k] for k in candidatos[i])}
        candidatos[i] = [j for j in candidatos[i] if j not in atajos]
        for j in atajos:
            previos[j].remove(i)
    for i, siguientes in candidatos.items():
        if len(siguientes) == 1 and previos[siguientes[0]] == [i]:
            _une(trozos, i, siguientes[0])
        elif (
            len(siguientes) >= 2
            and all(previos[j] == [i] for j in siguientes)
            and (trozos[i].numero or 1) >= len(siguientes)
        ):
            trozos[i].division = True
            for j in siguientes:
                _une(trozos, i, j)
    for j, anteriores in previos.items():
        if (
            len(anteriores) >= 2
            and all(candidatos[i] == [j] for i in anteriores)
            and (trozos[j].numero or 1) >= len(anteriores)
        ):
            trozos[j].union = True
            for i in anteriores:
                _une(trozos, i, j)


def _une(trozos: list[Trozo], i: int, j: int) -> None:
    if j not in trozos[i].sucesores:
        trozos[i].sucesores.append(j)
        trozos[j].predecesores.append(i)


def grupos(trozos: Sequence[Trozo]) -> list[list[int]]:
    """Los trozos de cada grupo (componentes de los enlaces), en orden de aparición."""
    padre = list(range(len(trozos)))

    def raiz(i: int) -> int:
        while padre[i] != i:
            padre[i] = padre[padre[i]]
            i = padre[i]
        return i

    for i, t in enumerate(trozos):
        for j in t.sucesores:
            padre[raiz(j)] = raiz(i)
    por_raiz: dict[int, list[int]] = {}
    for i in range(len(trozos)):
        por_raiz.setdefault(raiz(i), []).append(i)
    return sorted(por_raiz.values(), key=lambda g: (min(_t(trozos[i]) for i in g), g[0]))


def _t(trozo: Trozo) -> datetime:
    return trozo.inicio.t or datetime.max.replace(tzinfo=UTC)


# --- Líneas ------------------------------------------------------------------------------------


def ramas(trozos: Sequence[Trozo], grupo: Sequence[int]) -> list[list[int]]:
    """De cada principio (sin predecesor) a cada final (sin sucesor), sin repetir trozos."""
    dentro = set(grupo)
    principios = [i for i in grupo if not any(p in dentro for p in trozos[i].predecesores)]
    salida: list[list[int]] = []

    def seguir(camino: list[int]) -> None:
        if len(salida) >= RAMAS_MAX:
            return
        siguientes = [j for j in trozos[camino[-1]].sucesores if j in dentro and j not in camino]
        if not siguientes:
            salida.append(camino)
            return
        for j in siguientes:
            seguir([*camino, j])

    for i in principios or [grupo[0]]:
        seguir([i])
    return salida


def _sin_repetidos(puntos: Sequence[Punto]) -> list[Punto]:
    salida: list[Punto] = []
    for p in puntos:
        if salida and abs(salida[-1].lat - p.lat) < 1e-4 and abs(salida[-1].lon - p.lon) < 1e-4:
            salida[-1] = Punto(p.t, p.lat, p.lon, min(salida[-1].radio, p.radio), False)
            continue
        salida.append(p)
    return salida


def _mezcla(
    a: tuple[float, float, float], b: tuple[float, float, float], f: float
) -> tuple[float, float, float]:
    return (a[0] + f * (b[0] - a[0]), a[1] + f * (b[1] - a[1]), a[2] + f * (b[2] - a[2]))


def _suavizar(puntos: list[tuple[float, float, float]]) -> list[tuple[float, float, float]]:
    """Chaikin: cada esquina se corta a un cuarto; los extremos se quedan donde están."""
    for _ in range(SUAVIZADO):
        if len(puntos) < 3:
            return puntos
        nuevos = [puntos[0]]
        for a, b in itertools.pairwise(puntos):
            nuevos.append(_mezcla(a, b, 0.25))
            nuevos.append(_mezcla(a, b, 0.75))
        nuevos.append(puntos[-1])
        puntos = nuevos
    return puntos


def linea(trozos: Sequence[Trozo], rama: Sequence[int]) -> list[tuple[float, float, float]]:
    """(lat, lon, ancho) de la línea de una rama, sin los puntos vagos, suavizada."""
    puntos = _sin_repetidos([p for i in rama for p in trozos[i].precisos()])
    base = [(p.lat, p.lon, min(max(p.radio, ANCHO_MIN_KM), ANCHO_MAX_KM)) for p in puntos]
    return _suavizar(base)


def _km(lat0: float) -> tuple[float, float]:
    return 111.32 * math.cos(math.radians(lat0)), 110.57


def franja(puntos: Sequence[tuple[float, float, float]], lados: int = 8) -> list[list[float]]:
    """Contorno (lon, lat) de la franja: a cada lado de la línea, su ancho en ese punto, con media
    vuelta redonda en los dos extremos."""
    lat0 = statistics.fmean(p[0] for p in puntos)
    kx, ky = _km(lat0)
    xy = [(lon * kx, lat * ky, ancho) for lat, lon, ancho in puntos]
    normales = []
    for k in range(len(xy)):
        a = xy[max(k - 1, 0)]
        b = xy[min(k + 1, len(xy) - 1)]
        dx, dy = b[0] - a[0], b[1] - a[1]
        largo = math.hypot(dx, dy) or 1.0
        normales.append((-dy / largo, dx / largo))
    izquierda = [(x + nx * w, y + ny * w) for (x, y, w), (nx, ny) in zip(xy, normales, strict=True)]
    derecha = [(x - nx * w, y - ny * w) for (x, y, w), (nx, ny) in zip(xy, normales, strict=True)]

    def media_vuelta(
        centro: tuple[float, float, float], normal: tuple[float, float], signo: float
    ) -> list[tuple[float, float]]:
        x, y, w = centro
        angulo0 = math.atan2(normal[1], normal[0])
        return [
            (x + w * math.cos(angulo0 - signo * math.pi * s / lados),
             y + w * math.sin(angulo0 - signo * math.pi * s / lados))
            for s in range(1, lados)
        ]  # fmt: skip

    contorno = [
        *izquierda,
        *media_vuelta(xy[-1], normales[-1], 1.0),
        *reversed(derecha),
        *media_vuelta(xy[0], (-normales[0][0], -normales[0][1]), 1.0),
    ]
    anillo = [[round(x / kx, DECIMALES), round(y / ky, DECIMALES)] for x, y in contorno]
    return [*anillo, anillo[0]]


def longitud_km(puntos: Sequence[tuple[float, float, float]]) -> float:
    return sum(
        geometria.distancia_km(a[0], a[1], b[0], b[1]) for a, b in itertools.pairwise(puntos)
    )


# --- Documento ---------------------------------------------------------------------------------


def _instante(t: datetime | None) -> str | None:
    return None if t is None else t.strftime("%Y-%m-%dT%H:%M:%SZ")


def recorridos(trozos: list[Trozo]) -> tuple[list[dict[str, Any]], list[int]]:
    """Los recorridos de la noche, ordenados (el primero, el principal), y el grupo de cada trozo.
    Los grupos con línea van numerados del 1 en adelante por su orden; los que no se desplazan lo
    bastante (sin línea que dibujar) van detrás, con los números siguientes."""
    candidatos = []
    quietos: list[list[int]] = []
    grupo_de = [0] * len(trozos)
    for grupo in grupos(trozos):
        lineas = [linea(trozos, r) for r in ramas(trozos, grupo)]
        lineas = [x for x in lineas if len(x) >= 2 and longitud_km(x) >= LONGITUD_MIN_KM]
        if not lineas:
            quietos.append(grupo)
            continue
        miembros = [trozos[i] for i in grupo]
        puntos = [p for t in miembros for p in t.puntos]
        precisos = [p for p in puntos if not p.vago]
        numeros = [t.numero for t in miembros if t.numero is not None]
        velocidades = [p.kmh for p in puntos if p.kmh]
        instantes = [p.t for p in puntos if p.t is not None]
        largo = max(longitud_km(x) for x in lineas)
        documento: dict[str, Any] = {
            "tipo": miembros[0].tipo,
            "aparatos": max(numeros) if numeros else None,
            "kmh": round(statistics.median(velocidades)) if velocidades else None,
            "inicio": _instante(min(instantes)) if instantes else None,
            "fin": _instante(max(instantes)) if instantes else None,
            "precision_km": {
                "min": round(min(p.radio for p in precisos), 1),
                "max": round(max(p.radio for p in precisos), 1),
            },
            "longitud_km": round(largo, 1),
            "trozos": len(grupo),
            "division": any(t.division for t in miembros),
            "union": any(t.union for t in miembros),
            "lineas": [
                [[round(lon, DECIMALES), round(lat, DECIMALES)] for lat, lon, _ in x]
                for x in lineas
            ],
            "franjas": [franja(x) for x in lineas],
            "flechas": [_flecha(x) for x in lineas],
        }
        confianzas = [t.confianza for t in miembros if t.confianza]
        if confianzas:
            documento["confianza"] = max(set(confianzas), key=confianzas.count)
        pistas = sorted({t.id for t in miembros if not t.id.startswith("tramo-")})
        if pistas:
            documento["pistas"] = pistas
        candidatos.append((documento, grupo))
    candidatos.sort(key=lambda c: (-(c[0]["aparatos"] or 1), -c[0]["longitud_km"]))
    salida = []
    for n, (documento, grupo) in enumerate(candidatos, start=1):
        salida.append({"grupo": n, **documento})
        for i in grupo:
            grupo_de[i] = n
    for n, grupo in enumerate(quietos, start=len(salida) + 1):
        for i in grupo:
            grupo_de[i] = n
    return salida, grupo_de


def _flecha(puntos: Sequence[tuple[float, float, float]]) -> dict[str, float]:
    """Punta de flecha en el final, con el rumbo del último tramo de unos kilómetros."""
    fin = puntos[-1]
    previo = puntos[0]
    for p in reversed(puntos[:-1]):
        previo = p
        if geometria.distancia_km(p[0], p[1], fin[0], fin[1]) >= 3.0:
            break
    return {
        "lon": round(fin[1], DECIMALES),
        "lat": round(fin[0], DECIMALES),
        "rumbo": round(geometria.rumbo(previo[0], previo[1], fin[0], fin[1])),
    }
