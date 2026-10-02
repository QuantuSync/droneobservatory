"""Reglas físicas del motor de deducción. Cada una tiene identificador y versión y, para cada
clase de dron, da evidencias: descarta (con los datos que lo hacen imposible), compatible (la
regla tenía datos y no descarta), condición (compatible solo si se cumple algo: relevos, despegue
dentro del país...), indicio a favor o en contra (solo la descripción) o anotación. Una regla sin
los datos que necesita no da nada para esa clase.

Márgenes (todos a favor de no descartar):

- distancia (R1): se resta el radio de la zona de lanzamiento y el del lugar de llegada, y la
  clase se descarta solo si la distancia que queda supera su alcance en el suelo (en aire en
  calma más lo que el viento a favor pueda sumar en su tiempo máximo de vuelo) en más de un
  10 %;
- viento (R2): al viento medido se le quitan 2 m/s (error típico del viento de un modelo
  meteorológico) y debe superar en un 25 % el límite de la clase en toda su banda de vuelo
  (el viento más flojo de la banda); temperatura: 10 °C fuera del intervalo de trabajo;
- autonomía (R3): la permanencia declarada debe pasar la autonomía en más de un 10 %, y da una
  condición, nunca un descarte;
- velocidad (R4): la velocidad observada (la más baja del rango) debe superar en un 20 % la
  máxima de la clase;
- radar (R5): solo con una sección radar con fuente; sin ella, nada;
- simultaneidad (R6): la separación entre sitios a la vez debe superar en un 20 % lo que la
  clase recorre en ese tiempo a su velocidad máxima;
- descripción (R7) y GNSS (R8) nunca descartan.
"""

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any

from proceso.deduccion import capacidades, geo, viento
from proceso.deduccion.capacidades import Cota
from proceso.deduccion.catalogo import Catalogo, Zona

DESCARTA = "descarta"
COMPATIBLE = "compatible"
CONDICION = "condicion"
A_FAVOR = "a_favor"
EN_CONTRA = "en_contra"
ANOTACION = "anotacion"

# Identificador y versión de cada regla.
R1 = ("distancia", "1.0.0")
R2 = ("meteorologia", "1.0.0")
R3 = ("autonomia", "1.0.0")
R4 = ("velocidad", "1.0.0")
R5 = ("radar", "1.0.0")
R6 = ("simultaneidad", "1.0.0")
R7 = ("descripcion", "1.0.0")
R8 = ("gnss", "1.0.0")
REGLAS = (R1, R2, R3, R4, R5, R6, R7, R8)
# Las que pueden decir que una clase es compatible (las demás solo anotan o suman indicios).
FISICAS = frozenset({R1[0], R2[0], R3[0], R4[0], R5[0], R6[0]})

MARGEN_DISTANCIA = 0.10
ERROR_VIENTO_MS = 2.0
MARGEN_VIENTO = 0.25
MARGEN_TEMPERATURA_C = 10.0
MARGEN_AUTONOMIA = 0.10
MARGEN_VELOCIDAD = 0.20
MARGEN_SIMULTANEIDAD = 0.20
# Una permanencia sobre un sitio que un ala fija no puede mantener si el viento la supera.
PERMANENCIA_MIN = 15.0
# Detección por un radar de control aéreo: una sección radar con fuente por debajo de este valor
# no la vería. 0,01 m² es el orden de un multirrotor pequeño que da la bibliografía de radar
# primario; solo se aplica si la clase tiene sección radar con fuente.
RCS_MINIMO_RADAR_M2 = 0.01


@dataclass(frozen=True)
class Evidencia:
    regla: str
    version: str
    clase: str
    efecto: str
    motivo: str
    datos: dict[str, Any] = field(default_factory=dict)

    def documento(self) -> dict[str, Any]:
        resultado: dict[str, Any] = {
            "regla": self.regla,
            "version": self.version,
            "efecto": self.efecto,
            "motivo": self.motivo,
        }
        if self.datos:
            resultado["datos"] = self.datos
        return resultado


@dataclass(frozen=True)
class Origen:
    """Un sitio desde el que pudo salir el dron: zona de lanzamiento declarada o el territorio
    de la parte (impactos UA→RU)."""

    nombre: str
    distancia_km: float  # cota inferior, ya con los radios restados
    fuente: str | None = None


@dataclass
class Caso:
    """Lo que el motor sabe de un incidente, un impacto o un ataque, ya normalizado."""

    id: str
    tipo: str  # incidente | impacto | ataque | encuentro
    pais: str | None = None
    lat: float | None = None
    lon: float | None = None
    radio_km: float = 0.0
    inicio: float | None = None  # segundos desde 1970 (UTC)
    fin: float | None = None
    precision: str | None = None
    duracion_min: float | None = None
    entrada_exterior: bool = False
    entrada_confirmada: bool = False
    condiciones: dict[str, Any] | None = None
    gnss: str | None = None  # sin_interferencia | media | alta
    textos: list[str] = field(default_factory=list)
    luces: str | None = None
    clase_declarada: str | None = None
    velocidad_ms: tuple[float, float] | None = None
    velocidad_oficial: bool = False
    deteccion_radar: bool = False
    origenes: list[Origen] = field(default_factory=list)
    altura_m: tuple[float, float] | None = None
    lanzados: dict[str, Any] = field(default_factory=dict)

    @property
    def con_punto(self) -> bool:
        return self.lat is not None and self.lon is not None


def _ev(regla: tuple[str, str], clase: str, efecto: str, motivo: str, **datos: Any) -> Evidencia:
    return Evidencia(regla[0], regla[1], clase, efecto, motivo, _limpio(datos))


def _limpio(datos: dict[str, Any]) -> dict[str, Any]:
    def valor(v: Any) -> Any:
        if isinstance(v, float):
            return round(v, 3)
        if isinstance(v, Cota):
            return v.documento()
        if isinstance(v, dict):
            return {k: valor(x) for k, x in v.items()}
        if isinstance(v, list | tuple):
            return [valor(x) for x in v]
        return v

    return {k: valor(v) for k, v in datos.items() if v is not None}


# --- R1: distancia -------------------------------------------------------------------


def _decide(pasa: bool, cota: Cota) -> str | None:
    """Compatible si un modelo con dato pasa; descarta solo si todos tienen dato y ninguno
    pasa; si no, la regla no dice nada de la clase."""
    if pasa:
        return COMPATIBLE
    return DESCARTA if cota.sirve else None


def alcance_suelo_km(catalogo: Catalogo, clase: str, viento_ms: float) -> Cota:
    """Alcance en el suelo de la clase con el viento más favorable: el mayor de sus modelos."""
    return capacidades.de_clase(catalogo, clase, capacidades.suelo_km(viento_ms))


def viento_max_ruta(
    caso: Caso, catalogo: Catalogo | None = None, clase: str | None = None
) -> float:
    """El viento más fuerte medido en el caso en la banda de vuelo de la clase (sin clase, a
    cualquier altura): lo más que el viento puede empujar a favor. -1 sin medida."""
    lista = viento.lecturas((caso.condiciones or {}).get("lugar"))
    if catalogo is not None and clase is not None:
        lista = viento.en_banda(lista, *_banda(catalogo, clase))
    return max((x.velocidad_ms for x in lista), default=-1.0)


def r1_distancia_guerra(catalogo: Catalogo, caso: Caso) -> list[Evidencia]:
    """Capa de guerra: distancia desde la zona de lanzamiento (o desde el territorio de la parte)
    hasta el lugar alcanzado, frente al alcance de cada clase. El dron salió de alguno de los
    orígenes: basta con que llegue desde el más cercano. Sin viento medido no se descarta (el
    viento a favor no tiene cota)."""
    if not caso.origenes or not caso.con_punto:
        return []
    cercano = min(caso.origenes, key=lambda o: o.distancia_km)
    resultado = []
    for clase in catalogo.clases:
        empuje = viento_max_ruta(caso, catalogo, clase)
        suelo = alcance_suelo_km(catalogo, clase, max(empuje, 0.0))
        if suelo.valor is None:
            continue
        datos = dict(
            origen=cercano.nombre,
            distancia_km=cercano.distancia_km,
            alcance_suelo_km=suelo,
            viento_max_ms=empuje if empuje >= 0 else None,
        )
        pasa = cercano.distancia_km <= suelo.valor * (1 + MARGEN_DISTANCIA)
        efecto = _decide(pasa, suelo)
        if efecto == DESCARTA and empuje < 0:
            efecto = None
        if efecto == COMPATIBLE:
            resultado.append(_ev(R1, clase, COMPATIBLE, "llega desde algún origen", **datos))
        elif efecto == DESCARTA:
            resultado.append(
                _ev(R1, clase, DESCARTA, "no llega desde el origen más cercano", **datos)
            )
    return resultado


def r1_distancia_europa(
    catalogo: Catalogo, caso: Caso
) -> tuple[list[Evidencia], list[dict[str, Any]], dict[str, Any] | None]:
    """Europa: distancia desde lo más cercano de fuera del país (tierra de otro país o aguas
    internacionales). Una clase que no llega desde fuera solo es compatible con un despegue
    dentro del país; si una autoridad declara que el dron entró desde fuera, se descarta.
    Devuelve evidencias, conclusiones y las distancias medidas."""
    if not caso.con_punto or not caso.pais or caso.lat is None or caso.lon is None:
        return [], [], None
    medido = geo.exterior(caso.pais, caso.lat, caso.lon)
    fuera = medido.fuera_km
    distancias = medido.documento()
    if fuera is None:
        return [], [], distancias
    fuera = max(0.0, fuera - caso.radio_km)
    evidencias: list[Evidencia] = []
    no_llegan: list[str] = []
    llegan: list[str] = []
    if viento_max_ruta(caso) < 0:
        # Sin viento medido, el viento a favor no tiene cota.
        return [], [], distancias
    for clase in catalogo.clases:
        empuje = viento_max_ruta(caso, catalogo, clase)
        suelo = alcance_suelo_km(catalogo, clase, empuje)
        if suelo.valor is None:
            continue
        enlace = capacidades.de_clase(catalogo, clase, capacidades.enlace_max_km)
        datos = dict(
            exterior_km=fuera, alcance_suelo_km=suelo, enlace_km=enlace, viento_max_ms=empuje
        )
        pasa = fuera <= suelo.valor * (1 + MARGEN_DISTANCIA)
        efecto = _decide(pasa, suelo)
        if efecto == COMPATIBLE:
            llegan.append(clase)
            motivo = "llega desde fuera"
            if enlace.valor is not None and fuera > enlace.valor:
                motivo = "llega desde fuera, pero solo con vuelo programado más allá del enlace"
            evidencias.append(_ev(R1, clase, COMPATIBLE, motivo, **datos))
        elif efecto == DESCARTA:
            no_llegan.append(clase)
            if caso.entrada_exterior and caso.entrada_confirmada:
                evidencias.append(
                    _ev(
                        R1,
                        clase,
                        DESCARTA,
                        "la autoridad declara entrada desde fuera y no llega",
                        **datos,
                    )
                )
            else:
                evidencias.append(
                    _ev(R1, clase, CONDICION, "solo con despegue dentro del país", **datos)
                )
    conclusiones: list[dict[str, Any]] = []
    cortas = [c for c, d in catalogo.clases.items() if d.corto_alcance]
    evaluadas_cortas = [c for c in cortas if c in no_llegan or c in llegan]
    if evaluadas_cortas and all(c in no_llegan for c in evaluadas_cortas):
        conclusiones.append(
            {
                "regla": R1[0],
                "version": R1[1],
                "conclusion": "despegue_cercano_o_largo_alcance",
                "datos": _limpio({"exterior_km": fuera, "clases_corto_alcance": evaluadas_cortas}),
            }
        )
    return evidencias, conclusiones, distancias


# --- R2: viento, temperatura y lluvia ------------------------------------------------


def _banda(catalogo: Catalogo, clase: str) -> tuple[float | None, float | None]:
    """Altura de vuelo de la clase: de la más baja a la más alta de su altura típica (si la
    tienen todos sus modelos); si no, desde el suelo hasta su techo (o sin tope)."""
    tipica = catalogo.envolvente(clase, "altura_tipica")
    techo = catalogo.envolvente(clase, "techo")
    if tipica.minimo is not None and tipica.maximo is not None and not tipica.debil:
        return tipica.minimo, tipica.maximo
    return 0.0, techo.maximo if not techo.debil else None


def r2_meteorologia(catalogo: Catalogo, caso: Caso) -> list[Evidencia]:
    lugar = (caso.condiciones or {}).get("lugar")
    lista = viento.lecturas(lugar)
    temperatura = viento.temperatura(lugar)
    if not lista and temperatura is None:
        return []
    resultado: list[Evidencia] = []
    for clase, datos_clase in catalogo.clases.items():
        desde, hasta = _banda(catalogo, clase)
        banda = viento.en_banda(lista, desde, hasta)
        if banda:
            flojo = min(x.velocidad_ms for x in banda)
            efectivo = flojo - ERROR_VIENTO_MS
            datos = dict(
                viento_banda_ms=flojo,
                niveles=[x.nombre for x in banda],
                banda_m=[desde, hasta],
                racha_10m_ms=viento.racha(lugar),
            )
            limite = capacidades.de_clase(catalogo, clase, capacidades.viento_max_ms)
            propia = capacidades.de_clase(catalogo, clase, capacidades.crucero_max_ms)
            if limite.valor is not None:
                efecto = _decide(efectivo <= limite.valor * (1 + MARGEN_VIENTO), limite)
                if efecto == COMPATIBLE:
                    resultado.append(
                        _ev(
                            R2,
                            clase,
                            COMPATIBLE,
                            "viento dentro de su límite",
                            limite_ms=limite,
                            **datos,
                        )
                    )
                elif efecto == DESCARTA:
                    resultado.append(
                        _ev(
                            R2,
                            clase,
                            DESCARTA,
                            "viento por encima de su límite",
                            limite_ms=limite,
                            **datos,
                        )
                    )
            elif datos_clase.tipo_aeronave in {"ala_fija", "reaccion"} and propia.valor is not None:
                # Sin límite de viento publicado, el de un ala fija es su velocidad propia
                # frente al viento en contra (valor deducido).
                efecto = _decide(efectivo <= propia.valor * (1 + MARGEN_VIENTO), propia)
                if efecto == COMPATIBLE:
                    resultado.append(
                        _ev(
                            R2,
                            clase,
                            COMPATIBLE,
                            "avanza contra ese viento",
                            velocidad_propia_ms=propia,
                            limite_deducido=True,
                            **datos,
                        )
                    )
                elif efecto == DESCARTA:
                    permanece = (caso.duracion_min or 0) >= PERMANENCIA_MIN
                    motivo = (
                        "no puede mantenerse sobre el sitio con ese viento"
                        if permanece
                        else "solo con el viento a favor (no avanza contra él)"
                    )
                    resultado.append(
                        _ev(
                            R2,
                            clase,
                            DESCARTA if permanece else CONDICION,
                            motivo,
                            velocidad_propia_ms=propia,
                            limite_deducido=True,
                            **datos,
                        )
                    )
        if temperatura is not None:
            frio, calor = temperatura
            estados = [
                capacidades.temperatura_ok(m, frio, calor, MARGEN_TEMPERATURA_C)
                for m in catalogo.modelos_de(clase)
            ]
            datos_t = dict(
                temperatura_c=[frio, calor],
                trabajo_c=[
                    capacidades.minimo_de_clase(catalogo, clase, "temperatura").valor,
                    capacidades.maximo_de_clase(catalogo, clase, "temperatura").valor,
                ],
            )
            if any(e is True for e in estados):
                resultado.append(
                    _ev(R2, clase, COMPATIBLE, "temperatura dentro de su intervalo", **datos_t)
                )
            elif estados and all(e is False for e in estados):
                resultado.append(
                    _ev(R2, clase, DESCARTA, "temperatura fuera de su intervalo", **datos_t)
                )
        lluvia = viento.precipitacion(lugar)
        if lluvia is not None and lluvia > 0:
            textos = [
                t.texto for m in catalogo.modelos_de(clase) for t in m.textos.get("lluvia", ())
            ]
            resultado.append(
                _ev(
                    R2,
                    clase,
                    ANOTACION,
                    "lluvia medida (no descarta)",
                    precipitacion_mm=lluvia,
                    resistencia=textos or None,
                )
            )
    return resultado


# --- R3: duración frente a autonomía -------------------------------------------------


def r3_autonomia(catalogo: Catalogo, caso: Caso) -> list[Evidencia]:
    if caso.duracion_min is None or caso.duracion_min <= 0:
        return []
    resultado = []
    for clase in catalogo.clases:
        tiempo = capacidades.de_clase(catalogo, clase, capacidades.tiempo_max_min)
        if tiempo.valor is None:
            continue
        datos = dict(permanencia_min=caso.duracion_min, autonomia_min=tiempo)
        efecto = _decide(caso.duracion_min <= tiempo.valor * (1 + MARGEN_AUTONOMIA), tiempo)
        if efecto == COMPATIBLE:
            resultado.append(_ev(R3, clase, COMPATIBLE, "cabe en su autonomía", **datos))
        elif efecto == DESCARTA:
            # Nunca un descarte seco: con relevos o varios drones es posible.
            resultado.append(
                _ev(
                    R3,
                    clase,
                    CONDICION,
                    "solo con relevos (operador cerca) o varios drones",
                    **datos,
                )
            )
    return resultado


# --- R4: velocidad -------------------------------------------------------------------


def r4_velocidad(catalogo: Catalogo, caso: Caso) -> list[Evidencia]:
    if caso.velocidad_ms is None:
        return []
    observada = caso.velocidad_ms[0]
    resultado = []
    for clase in catalogo.clases:
        maxima = capacidades.de_clase(catalogo, clase, capacidades.velocidad_max_ms)
        if maxima.valor is None:
            continue
        datos = dict(
            velocidad_observada_ms=list(caso.velocidad_ms),
            velocidad_max_ms=maxima,
            oficial=caso.velocidad_oficial,
        )
        efecto = _decide(observada <= maxima.valor * (1 + MARGEN_VELOCIDAD), maxima)
        if efecto == COMPATIBLE:
            resultado.append(_ev(R4, clase, COMPATIBLE, "velocidad a su alcance", **datos))
        elif efecto == DESCARTA:
            if caso.velocidad_oficial:
                resultado.append(
                    _ev(R4, clase, DESCARTA, "más rápido de lo que puede volar", **datos)
                )
            else:
                resultado.append(
                    _ev(
                        R4,
                        clase,
                        CONDICION,
                        "más rápido de lo que puede volar (velocidad no oficial)",
                        **datos,
                    )
                )
    return resultado


def velocidad_entre(a: tuple[float, float, float], b: tuple[float, float, float]) -> float | None:
    """Velocidad mínima entre dos avistamientos fechados (lat, lon, segundos) en sitios
    distintos, en m/s; None si son a la vez o en el mismo sitio."""
    segundos = abs(b[2] - a[2])
    metros = geo.distancia_km(a[0], a[1], b[0], b[1]) * 1000.0
    if segundos <= 0 or metros <= 0:
        return None
    return metros / segundos


# --- R5: radar -----------------------------------------------------------------------


def r5_radar(catalogo: Catalogo, caso: Caso) -> list[Evidencia]:
    if not caso.deteccion_radar:
        return []
    resultado = []
    for clase in catalogo.clases:
        rcs = capacidades.maximo_de_clase(catalogo, clase, "rcs")
        if rcs.valor is None:
            continue
        datos = dict(rcs_max_m2=rcs, umbral_m2=RCS_MINIMO_RADAR_M2)
        efecto = _decide(rcs.valor >= RCS_MINIMO_RADAR_M2, rcs)
        if efecto == COMPATIBLE:
            resultado.append(_ev(R5, clase, COMPATIBLE, "visible para el radar", **datos))
        elif efecto == DESCARTA:
            resultado.append(_ev(R5, clase, DESCARTA, "el radar no lo vería", **datos))
    return resultado


# --- R6: simultaneidad ---------------------------------------------------------------


@dataclass(frozen=True)
class Sitio:
    id: str
    lat: float
    lon: float
    radio_km: float
    inicio: float
    fin: float


def r6_simultaneidad(catalogo: Catalogo, caso: Caso, otros: list[Sitio]) -> list[Evidencia]:
    """Sitios con drones a la vez (sus ventanas se solapan) más separados de lo que la clase
    recorre en el tiempo más largo que pudo pasar entre uno y otro, con el viento más fuerte
    medido a favor y sin pasar de su alcance: hacen falta varios drones o equipos. No descarta
    la clase: dice que serían varios."""
    propio = next((s for s in otros if s.id == caso.id), None)
    if propio is None:
        return []
    if viento_max_ruta(caso) < 0:
        # Sin viento medido no hay cota de lo que el viento puede sumar.
        return []
    lejanos: dict[str, list[dict[str, Any]]] = {}
    for otro in otros:
        if otro.id == caso.id or min(otro.fin, propio.fin) <= max(otro.inicio, propio.inicio):
            continue
        separacion_s = max(otro.fin - propio.inicio, propio.fin - otro.inicio)
        distancia = (
            geo.distancia_km(propio.lat, propio.lon, otro.lat, otro.lon)
            - propio.radio_km
            - otro.radio_km
        )
        if distancia <= 0:
            continue
        for clase in catalogo.clases:
            maxima = capacidades.de_clase(catalogo, clase, capacidades.velocidad_max_ms)
            if not maxima.sirve or maxima.valor is None:
                continue
            empuje = viento_max_ruta(caso, catalogo, clase)
            recorre = (maxima.valor + empuje) * separacion_s / 1000.0
            suelo = alcance_suelo_km(catalogo, clase, empuje)
            if not suelo.sirve or suelo.valor is None:
                continue
            recorre = min(recorre, suelo.valor)
            if distancia > recorre * (1 + MARGEN_SIMULTANEIDAD):
                lejanos.setdefault(clase, []).append(
                    {
                        "otro": otro.id,
                        "distancia_km": round(distancia, 1),
                        "separacion_max_min": round(separacion_s / 60.0, 1),
                        "recorre_km": round(recorre, 1),
                    }
                )
    return [
        _ev(R6, clase, CONDICION, "varios drones o equipos (sitios a la vez)", sitios=lista)
        for clase, lista in lejanos.items()
    ]


# --- R7: descripción -----------------------------------------------------------------


def normalizar(texto: str) -> str:
    sin = unicodedata.normalize("NFKD", texto.lower())
    return "".join(c for c in sin if not unicodedata.combining(c))


# Rasgos que nombran los testigos, pilotos y fuentes, en los idiomas de la base. Cada rasgo se
# compara con los de la clase (forma, propulsión, tamaño) y con los nombres de sus modelos.
PALABRAS: dict[str, tuple[str, ...]] = {
    "multirrotor": (
        "quadcopter",
        "quadrocopter",
        "quadricopter",
        "multicopter",
        "multirotor",
        "multi-rotor",
        "hexacopter",
        "octocopter",
        "cuadricoptero",
        "cuadrocoptero",
        "multirrotor",
        "drohne mit",
        "quadrokopter",
        "multikopter",
        "квадрокоптер",
        "квадрокоптер",
        "rotors",
        "rotor",
    ),
    "ala_fija": (
        "fixed-wing",
        "fixed wing",
        "ala fija",
        "plane-type",
        "aircraft-type",
        "flugzeug",
        "самолетного типа",
        "літакового типу",
        "крило",
        "крыло",
        "самолет",
        "літак",
        "aripa fixa",
        "skrzydl",
        "wing",
    ),
    "ala_delta": ("delta", "triangular", "triangle"),
    "reaccion": ("jet", "reactiv", "turbojet", "реактив"),
    "combustion": (
        "moped",
        "lawnmower",
        "lawn mower",
        "motorbike",
        "motorcycle",
        "chainsaw",
        "мопед",
        "газонокосил",
        "ciclomotor",
        "cortacesped",
        "motosierra",
        "mofa",
        "rasenmaher",
    ),
    "pequeno": ("small", "pequen", "klein", "petit", "mini", "tiny", "маленьк", "малий"),
    "grande": (
        "large",
        "big",
        "grande",
        "gross",
        "store droner",
        "stor drone",
        "groot",
        "великий",
        "большой",
        "10ft",
        "3m",
    ),
}


def rasgos_de(textos: list[str]) -> set[str]:
    hallados = set()
    for texto in textos:
        normal = normalizar(texto)
        for rasgo, palabras in PALABRAS.items():
            if any(
                re.search(r"(?<![a-zа-яіїєґ])" + re.escape(normalizar(p)), normal) for p in palabras
            ):
                hallados.add(rasgo)
    return hallados


def _nombra_modelo(catalogo: Catalogo, clase: str, textos: list[str]) -> str | None:
    normales = [normalizar(t) for t in textos]
    for modelo in catalogo.modelos_de(clase):
        for nombre in (modelo.nombre, *modelo.otros_nombres):
            raiz = normalizar(nombre)
            raiz = re.split(r"[\s(/]", raiz)[0] if len(raiz) > 3 else raiz
            if len(raiz) >= 4 and any(raiz in n for n in normales):
                return modelo.id
    return None


def r7_descripcion(catalogo: Catalogo, caso: Caso) -> list[Evidencia]:
    """Lo que dicen testigos, pilotos y fuentes (forma, sonido, tamaño, luces, modelo) frente a
    los rasgos de cada clase: suma o resta, nunca descarta."""
    textos = [t for t in caso.textos if t]
    rasgos = rasgos_de(textos)
    if caso.clase_declarada == "multirrotor_pequeno":
        rasgos |= {"multirrotor"}
    elif caso.clase_declarada == "ala_fija":
        rasgos |= {"ala_fija"}
    resultado = []
    for clase, datos in catalogo.clases.items():
        modelo = _nombra_modelo(catalogo, clase, textos)
        if modelo:
            resultado.append(
                _ev(R7, clase, A_FAVOR, "la fuente nombra un modelo de la clase", modelo=modelo)
            )
        forma_ala = datos.tipo_aeronave in {"ala_fija", "reaccion"}
        if "multirrotor" in rasgos:
            efecto = A_FAVOR if datos.tipo_aeronave == "multirrotor" else EN_CONTRA
            resultado.append(_ev(R7, clase, efecto, "descrito como multirrotor"))
        if "ala_fija" in rasgos or "ala_delta" in rasgos:
            efecto = A_FAVOR if forma_ala or datos.tipo_aeronave == "vtol" else EN_CONTRA
            resultado.append(_ev(R7, clase, efecto, "descrito como ala fija"))
        if "reaccion" in rasgos:
            efecto = A_FAVOR if datos.propulsion == "reaccion" else EN_CONTRA
            resultado.append(_ev(R7, clase, efecto, "descrito con motor a reacción"))
        if "combustion" in rasgos:
            efecto = A_FAVOR if datos.propulsion == "combustion" else EN_CONTRA
            resultado.append(_ev(R7, clase, efecto, "sonido de motor de combustión"))
        if "pequeno" in rasgos and "grande" not in rasgos:
            efecto = A_FAVOR if datos.tamano == "pequeno" else EN_CONTRA
            resultado.append(_ev(R7, clase, efecto, "descrito como pequeño"))
        if "grande" in rasgos and "pequeno" not in rasgos:
            efecto = A_FAVOR if datos.tamano == "grande" else EN_CONTRA
            resultado.append(_ev(R7, clase, efecto, "descrito como grande"))
        if caso.luces == "si":
            con_luces = [m.id for m in catalogo.modelos_de(clase) if m.textos.get("luces")]
            if con_luces:
                resultado.append(
                    _ev(R7, clase, A_FAVOR, "con luces, como sus modelos", modelos=con_luces)
                )
    return resultado


# --- R8: interferencia GNSS ----------------------------------------------------------

RESISTENTE = (
    "crpa",
    "kometa",
    "antiinterferencia",
    "anti-jam",
    "antijam",
    "visual",
    "vision",
    "slam",
    "inercial",
    "inertial",
    "fibra",
    "fibre",
    "fiber",
)


def r8_gnss(catalogo: Catalogo, caso: Caso) -> list[Evidencia]:
    """Con interferencia GNSS medida (media o alta) en la zona, qué clases se verían afectadas
    según su navegación. No descarta."""
    if caso.gnss not in {"media", "alta"}:
        return []
    resultado = []
    for clase in catalogo.clases:
        textos = [
            normalizar(t.texto)
            for m in catalogo.modelos_de(clase)
            for campo in ("navegacion", "interferencia_gnss")
            for t in m.textos.get(campo, ())
        ]
        if not textos:
            resultado.append(
                _ev(
                    R8,
                    clase,
                    ANOTACION,
                    "sin dato de navegación",
                    nivel=caso.gnss,
                    afectada="sin_dato",
                )
            )
        elif any(p in t for t in textos for p in RESISTENTE):
            resultado.append(
                _ev(
                    R8,
                    clase,
                    ANOTACION,
                    "navegación que resiste o prescinde del GNSS",
                    nivel=caso.gnss,
                    afectada="resistente",
                )
            )
        else:
            resultado.append(
                _ev(
                    R8,
                    clase,
                    ANOTACION,
                    "navegación que depende del GNSS",
                    nivel=caso.gnss,
                    afectada="afectada",
                )
            )
    return resultado


def origenes_de_zonas(caso: Caso, zonas: list[Zona]) -> list[Origen]:
    """Las zonas de lanzamiento con punto, como orígenes con su distancia (cota inferior)."""
    if not caso.con_punto or caso.lat is None or caso.lon is None:
        return []
    resultado = []
    for zona in zonas:
        if zona.lat is None or zona.lon is None:
            continue
        d = geo.distancia_km(zona.lat, zona.lon, caso.lat, caso.lon)
        resultado.append(
            Origen(zona.id, max(0.0, d - (zona.radio_km or 0.0) - caso.radio_km), zona.fuente)
        )
    return resultado
