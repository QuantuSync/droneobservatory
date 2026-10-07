"""Probabilidad de cada clase de dron de un incidente, con sus razones.

Por clase del catálogo (configuracion/catalogo_drones.json) se multiplica:

1. la frecuencia de partida de la clase en la zona del incidente (frontera o interior), sacada de
   los casos en que una autoridad identificó el dron (sin el caso que se evalúa al comprobar);
2. la verosimilitud de cada rasgo descrito (forma, ruido, tamaño, comportamiento) según lo que
   el catálogo dice de la clase (configuracion/tipo_dron.json, fijada de antemano);
3. las restricciones físicas: distancia a Ucrania, Rusia y Bielorrusia (y a la costa) frente al
   alcance de la clase; velocidad (por debajo de 230 km/h, hélice; por encima de 300 km/h,
   reacción; entre medias, nada) y frente a la máxima de la clase; altura frente al techo;
   duración frente a la autonomía; y lo que ya descartan o condicionan las reglas físicas del
   motor de deducción (viento y temperatura de esa hora y ese lugar, entre otras).

Se normaliza y se suma por grupo (las clases que ve el usuario). Cada factor que pesa queda en
la lista de razones, con el rasgo y su cita cuando sale de una frase.
"""

import json
import math
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from functools import cache
from pathlib import Path
from typing import Any

from proceso.deduccion import capacidades
from proceso.deduccion.catalogo import Catalogo

CONFIGURACION = Path(__file__).resolve().parent.parent.parent / "configuracion" / "tipo_dron.json"
KMH_POR_MS = 3.6
# Razones que solo dicen dónde está el incidente respecto a la guerra (ver con_base).
SOLO_DISTANCIA = ("distancia", "entrada_exterior")


@cache
def configuracion() -> dict[str, Any]:
    datos: dict[str, Any] = json.loads(CONFIGURACION.read_text(encoding="utf-8"))
    return datos


def version() -> str:
    return str(configuracion()["version"])


def grupos() -> list[dict[str, Any]]:
    return list(configuracion()["grupos"])


def grupo_de_clase() -> dict[str, str]:
    return {c: g["id"] for g in grupos() for c in g["clases"]}


def clases_del_modelo() -> list[str]:
    return [c for g in grupos() for c in g["clases"]]


@dataclass
class Entrada:
    """Lo que se sabe del incidente para calcular la clase."""

    zona: str | None
    d_partes_km: float | None = None  # a Ucrania, Rusia o Bielorrusia; None: más de 600 km
    d_costa_km: float | None = None
    con_punto: bool = False
    entrada_exterior: bool = False
    rasgos: list[dict[str, Any]] = field(default_factory=list)
    # Lo que ya dicen las reglas físicas del motor de deducción: {clase: [(efecto, regla)]}.
    motor: dict[str, list[tuple[str, str]]] = field(default_factory=dict)


@dataclass(frozen=True)
class Razon:
    """Un factor que ha pesado en una o varias clases."""

    tipo: str  # rasgo | restriccion | motor
    clave: str
    clases: tuple[str, ...]
    factor: float
    detalle: dict[str, Any]


@dataclass
class Resultado:
    por_clase: dict[str, float]
    por_grupo: dict[str, float]
    razones: list[Razon]
    previa: dict[str, float]

    def ordenados(self) -> list[tuple[str, float]]:
        return sorted(self.por_grupo.items(), key=lambda x: (-x[1], x[0]))


# --- Frecuencia de partida ---------------------------------------------------------------------


def previa(casos: Iterable[tuple[str | None, Iterable[str]]], zona: str | None) -> dict[str, float]:
    """Frecuencia de cada clase en los casos de la misma zona (respuesta conocida), con
    suavizado. Un caso cuya respuesta son varias clases reparte su peso entre ellas. Sin casos
    de la zona, los de todas las zonas."""
    suavizado = float(configuracion()["previa"]["suavizado"])
    clases = clases_del_modelo()
    lista = [(z, tuple(r)) for z, r in casos]
    elegidos = [r for z, r in lista if z == zona] or [r for _, r in lista]
    cuenta = dict.fromkeys(clases, suavizado / len(clases))
    for respuesta in elegidos:
        validas = [c for c in respuesta if c in cuenta]
        for c in validas:
            cuenta[c] += 1.0 / len(validas)
    total = sum(cuenta.values())
    return {c: v / total for c, v in cuenta.items()}


# --- Verosimilitudes ---------------------------------------------------------------------------


def _atributo(catalogo: Catalogo, clase: str, nombre: str) -> str:
    return str(getattr(catalogo.clases[clase], nombre))


def _factor_rasgo(catalogo: Catalogo, clase: str, regla: Mapping[str, Any]) -> float:
    for atributo, tabla in regla.items():
        if atributo == "clases":
            return float(tabla.get(clase, regla.get("resto", 1.0)))
        if atributo == "resto":
            continue
        valor = _atributo(catalogo, clase, atributo)
        return float(tabla.get(valor, 1.0))
    return 1.0


def _rasgos_que_pesan(rasgos: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Un rasgo por tipo y valor; los que la tabla de verosimilitud conoce."""
    tabla = configuracion()["verosimilitud"]
    vistos: set[tuple[str, str]] = set()
    lista = []
    for r in rasgos:
        valor = r["valor"]
        if not isinstance(valor, str) or valor not in tabla.get(r["rasgo"], {}):
            continue
        clave = (r["rasgo"], valor)
        if clave in vistos:
            continue
        vistos.add(clave)
        lista.append(r)
    return lista


def _numerico(rasgos: list[dict[str, Any]], rasgo: str, campo: str) -> dict[str, Any] | None:
    for r in rasgos:
        if r["rasgo"] == rasgo and isinstance(r["valor"], dict) and campo in r["valor"]:
            return r
    return None


# --- Cálculo -----------------------------------------------------------------------------------


def calcular(
    catalogo: Catalogo,
    entrada: Entrada,
    casos_previa: Iterable[tuple[str | None, Iterable[str]]],
) -> Resultado:
    conf = configuracion()
    lim = conf["restricciones"]
    clases = clases_del_modelo()
    p0 = previa(casos_previa, entrada.zona)
    log = {c: math.log(p0[c]) for c in clases}
    razones: list[Razon] = []

    def aplicar(tipo: str, clave: str, factores: dict[str, float], detalle: dict[str, Any]) -> None:
        afectadas = tuple(c for c, f in factores.items() if f != 1.0)
        if not afectadas:
            return
        for c, f in factores.items():
            log[c] += math.log(max(f, 1e-9))
        menor = min(factores[c] for c in afectadas)
        razones.append(Razon(tipo, clave, afectadas, round(menor, 3), detalle))

    # Rasgos descritos.
    tabla = conf["verosimilitud"]
    for r in _rasgos_que_pesan(entrada.rasgos):
        regla = tabla[r["rasgo"]][r["valor"]]
        factores = {c: _factor_rasgo(catalogo, c, regla) for c in clases}
        aplicar("rasgo", f"{r['rasgo']}:{r['valor']}", factores, _cita(r))

    # Distancia a donde pudo despegar una clase que no se lanza en Europa.
    desde_fuera = set(conf["clases_lanzadas_desde_fuera"])
    if entrada.con_punto:
        d = entrada.d_partes_km if entrada.d_partes_km is not None else 600.0
        factores = {}
        for c in clases:
            if c not in desde_fuera and not entrada.entrada_exterior:
                factores[c] = 1.0
                continue
            alcance = capacidades.de_clase(catalogo, c, capacidades.alcance_aire_km)
            if alcance.valor is None:
                factores[c] = 1.0
                continue
            limite = alcance.valor * float(lim["distancia_margen"])
            if d <= limite:
                factores[c] = 1.0
            elif entrada.d_costa_km is not None and entrada.d_costa_km <= limite:
                factores[c] = float(lim["fuera_de_alcance_con_costa"])
            else:
                factores[c] = float(lim["fuera_de_alcance"])
        detalle_d = {
            "distancia_km": None if entrada.d_partes_km is None else round(d, 1),
            "mas_de_600_km": entrada.d_partes_km is None,
            "costa_km": None if entrada.d_costa_km is None else round(entrada.d_costa_km, 1),
            "entrada_exterior": entrada.entrada_exterior,
        }
        antes = len(razones)
        aplicar("restriccion", "distancia", factores, detalle_d)
        # Entró desde fuera y todas las clases llegan: no cambia ninguna probabilidad, pero es la
        # razón de que el incidente tenga base en la frontera (con_base) y se enseña como tal.
        if len(razones) == antes and entrada.entrada_exterior:
            razones.append(Razon("restriccion", "entrada_exterior", (), 1.0, detalle_d))

    # Velocidad: hélice o reacción, y la máxima de cada clase.
    rasgo_v = _numerico(entrada.rasgos, "velocidad", "kmh")
    if rasgo_v is not None:
        kmh = float(rasgo_v["valor"]["kmh"])
        factores = {}
        for c in clases:
            f = 1.0
            reaccion = _atributo(catalogo, c, "propulsion") == "reaccion"
            if kmh < lim["velocidad_helice_max_kmh"] and reaccion:
                f = float(lim["velocidad_contraria"])
            if kmh > lim["velocidad_reaccion_min_kmh"] and not reaccion:
                f = float(lim["velocidad_contraria"])
            maxima = capacidades.de_clase(catalogo, c, capacidades.velocidad_max_ms)
            limite = (maxima.valor or 0.0) * KMH_POR_MS * float(lim["velocidad_margen"])
            if maxima.sirve and maxima.valor is not None and kmh > limite:
                f = min(f, float(lim["velocidad_contraria"]))
            factores[c] = f
        aplicar("restriccion", "velocidad", factores, {"kmh": kmh, **_cita(rasgo_v)})

    # Altura frente al techo.
    rasgo_a = _numerico(entrada.rasgos, "altura", "metros")
    if rasgo_a is not None:
        metros = float(rasgo_a["valor"]["metros"])
        factores = {}
        for c in clases:
            techo = capacidades.de_clase(catalogo, c, capacidades.techo_m)
            alto = techo.sirve and techo.valor is not None
            supera = alto and metros > float(techo.valor or 0) * float(lim["altura_margen"])
            factores[c] = float(lim["por_encima_del_techo"]) if supera else 1.0
        aplicar("restriccion", "altura", factores, {"metros": metros, **_cita(rasgo_a)})

    # Duración frente a la autonomía.
    rasgo_d = _numerico(entrada.rasgos, "duracion", "minutos")
    if rasgo_d is not None:
        minutos = float(rasgo_d["valor"]["minutos"])
        factores = {}
        for c in clases:
            tiempo = capacidades.de_clase(catalogo, c, capacidades.tiempo_max_min)
            corto = tiempo.sirve and tiempo.valor is not None
            supera = corto and minutos > float(tiempo.valor or 0) * float(lim["duracion_margen"])
            factores[c] = float(lim["mas_que_su_autonomia"]) if supera else 1.0
        aplicar("restriccion", "duracion", factores, {"minutos": minutos, **_cita(rasgo_d)})

    # Lo que descartan o condicionan las reglas físicas del motor de deducción.
    por_regla: dict[str, dict[str, float]] = {}
    for c, efectos in entrada.motor.items():
        if c not in log:
            continue
        for efecto, regla in efectos:
            f = (
                float(lim["descarte_del_motor"])
                if efecto == "descarta"
                else float(lim["condicion_del_motor"])
            )
            actual = por_regla.setdefault(regla, dict.fromkeys(clases, 1.0))
            actual[c] = min(actual[c], f)
    for regla, factores in sorted(por_regla.items()):
        aplicar("motor", regla, factores, {})

    maximo = max(log.values())
    pesos = {c: math.exp(v - maximo) for c, v in log.items()}
    total = sum(pesos.values())
    por_clase = {c: pesos[c] / total for c in clases}
    por_grupo: dict[str, float] = {}
    for c, p in por_clase.items():
        g = grupo_de_clase()[c]
        por_grupo[g] = por_grupo.get(g, 0.0) + p
    return Resultado(por_clase, por_grupo, razones, p0)


def _cita(rasgo: dict[str, Any]) -> dict[str, Any]:
    return {
        "rasgo": rasgo["rasgo"],
        "valor": rasgo["valor"],
        "cita": rasgo.get("cita"),
        "fuente": rasgo.get("fuente"),
        "origen": rasgo.get("origen"),
    }


def con_base(entrada: Entrada, resultado: Resultado) -> bool:
    """Hay base para decir algo del incidente: algún rasgo descrito o alguna restricción física
    ha cambiado las probabilidades de partida (una altura por debajo del techo de todas las
    clases, por ejemplo, no cambia nada), o el dron entró desde fuera en la zona de frontera (la
    zona y la distancia dicen entonces de dónde vino). Un dron de superficie (marítimo) no tiene
    clase en el catálogo: sin base."""
    if any(r["rasgo"] == "forma" and r["valor"] == "maritimo" for r in entrada.rasgos):
        return False
    if any(
        r.tipo == "rasgo" or (r.tipo == "restriccion" and r.clave not in SOLO_DISTANCIA)
        for r in resultado.razones
    ):
        return True
    # La distancia sola descarta los drones de largo alcance lejos de la guerra, pero eso no
    # dice qué dron era: solo cuenta en la frontera, con el dron entrado desde fuera.
    return entrada.con_punto and entrada.zona == "frontera" and entrada.entrada_exterior
