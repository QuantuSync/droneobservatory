"""Cruce de los impactos con los focos térmicos de NASA FIRMS. Regla por código, sin modelo.

Qué es un impacto aquí:

- un incidente con prueba física de impacto (el dron explotó o cayó: evidencia `explosion` o
  `caida`), con su punto y su radio de precisión;
- una región de un ataque RU→UA que el parte de la Fuerza Aérea cita entre los lugares con
  impacto (`lugares_impacto`). El parte solo nombra regiones: esos impactos quedan como no
  evaluables hasta que se sepa su localidad o su instalación.

La regla:

1. Solo se evalúan los impactos con radio de precisión de 10 km o menos (localidad o
   instalación). El radio de búsqueda es ese radio, con un mínimo de 2 km.
2. Ventana: del inicio del periodo del ataque a 36 horas después de su fin (cuando la fuente
   solo da el día, el fin es el final de ese día).
3. Se descartan los focos de baja confianza: VIIRS «l» y MODIS por debajo de 30 (la clase
   baja de MODIS, 0 a 29, según la documentación de FIRMS).
4. Línea base: los focos (de cualquier confianza) en el mismo radio en los 30 días
   anteriores al inicio. Un foco de la ventana cuenta si es nuevo (ningún foco de la base a
   menos de DISTANCIA_HABITUAL_KM: el tamaño del píxel y el error de posición) o si, siendo
   de un sitio habitual (las antorchas de una refinería, una planta), su potencia radiativa
   (FRP) pasa de FACTOR_FRP veces la mayor que tuvo ese sitio en la base con el mismo
   instrumento. Los umbrales salen de casos reales (docs/informe_firms.md).
5. Detectado si cuentan al menos FOCOS_MINIMOS focos (dos píxeles del mismo paso o dos
   pasos): un foco suelto es demasiado a menudo una quema agrícola o el titileo de una
   antorcha. Si no, no detectado, con su motivo. La ausencia de foco no demuestra nada
   (nubes, horas de paso, humo): solo el positivo se publica.
"""

import math
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import TYPE_CHECKING

from esquema import Documento

if TYPE_CHECKING:
    from almacen.base import Almacen
    from recogida.plazo import Plazo

DETECTADO, NO_DETECTADO, NO_EVALUABLE = "detectado", "no_detectado", "no_evaluable"
SIN_FOCOS, SOLO_BAJA_CONFIANZA, FUENTE_HABITUAL, FOCO_AISLADO = (
    "sin_focos",
    "solo_baja_confianza",
    "fuente_habitual",
    "foco_aislado",
)
SIN_LUGAR_PRECISO, FUERA_DE_ZONA, SIN_DATOS, FUEGO_FRECUENTE = (
    "sin_lugar_preciso",
    "fuera_de_zona",
    "sin_datos_firms",
    "fuego_frecuente",
)
# Un radio que ardió la mitad de los días de la base o más, repartido por muchos sitios (una
# ciudad del frente, una zona de quemas), no se puede evaluar: cualquier foco nuevo de la
# ventana sería uno más de los de cada día. Las antorchas de una refinería caen en uno a tres
# píxeles y no llegan al número de celdas (de 0,01°, en torno a 1 km).
DIAS_FUEGO_FRECUENTE = 15
CELDAS_FUEGO_FRECUENTE = 15

RADIO_MIN_KM = 2.0
RADIO_MAX_KM = 10.0
HORAS_TRAS_FIN = timedelta(hours=36)
DIAS_BASE = 30
# Con menos días de base con datos, no se puede separar una antorcha de un incendio nuevo.
DIAS_BASE_MINIMOS = 20
# MODIS: confianza de 0 a 100; por debajo de 30 es la clase baja de FIRMS.
CONFIANZA_MODIS_MINIMA = 30
CONFIANZA_VIIRS_BAJA = frozenset({"l", "low"})
# Un foco de la ventana es de un sitio habitual si la base tiene uno a esta distancia o menos:
# medio kilómetro más que el píxel (375 m VIIRS, 1 km MODIS) para cubrir el error de posición
# y el tamaño de una refinería grande, cuyas antorchas caen en varios píxeles vecinos.
DISTANCIA_HABITUAL_KM = {"VIIRS": 1.0, "MODIS": 2.0}
# Un sitio habitual cuenta si su potencia pasa de tantas veces la mayor de su base. En 1068
# noches sin ataque de mayo a julio de 2025 en doce refinerías, depósitos, puertos y centrales,
# la razón entre la potencia de un foco habitual y la mayor de su base tuvo mediana 0,26 y
# percentil 99 de 3,14; en los ataques validados pasó de 8 (docs/informe_firms.md).
FACTOR_FRP = 4.0
# Línea base del emplazamiento (docs/informe_capa_guerra.md, Kirishi): un sitio con calor
# habitual que pasa meses sin verse (antorchas estacionales, nubes de invierno) no está en los
# 30 días anteriores. Si con esa base el impacto saldría detectado, se mira además el año
# anterior: un foco nuevo en 30 días que cae en un sitio con al menos FOCOS_EMPLAZAMIENTO focos
# en el año solo cuenta si su potencia pasa de FACTOR_FRP veces la mediana del sitio (la base
# del año también recoge los incendios de ataques anteriores: la mediana no se mueve con
# ellos), salvo que algún paso del satélite tenga FOCOS_POR_PASO_INCENDIO focos que cuentan.
DIAS_BASE_LARGA = 365
FOCOS_EMPLAZAMIENTO = 3
PERCENTIL_EMPLAZAMIENTO = 0.9
# Un paso del satélite con tantos focos que cuentan es un incendio extenso, no una antorcha:
# la antorcha de Kirishi nunca dio más de dos píxeles en un mismo paso.
FOCOS_POR_PASO_INCENDIO = 3
# Focos que tienen que contar para dar el impacto por detectado. Con uno solo, en esas mismas
# noches salían 15 positivos sueltos en Riazán, Volgogrado y Sarátov; todos los ataques
# validados tuvieron tres o más.
FOCOS_MINIMOS = 2
# Cuánto se vuelve a evaluar un impacto tras cerrar su ventana: FIRMS completa los días
# recientes con pasos tardíos y el procesado estándar sustituye al NRT meses después, pero
# una semana basta para que el NRT esté completo.
REEVALUAR = timedelta(days=7)
# Tope del cruce en la ejecución horaria. Leer un día del verano (cuatro productos, decenas
# de miles de focos) cuesta alrededor de un segundo; la primera vez, con todos los impactos
# por evaluar, puede no caber y sigue en la hora siguiente.
TOPE_S = 240.0
# Antes de octubre de 2022 no se han descargado datos.
INICIO_DATOS = date(2022, 10, 1)
DURACION_POR_PRECISION = {
    "minuto": timedelta(0),
    "hora": timedelta(hours=1),
    "dia": timedelta(days=1),
    "aproximada": timedelta(days=1),
}
EVIDENCIA_IMPACTO = frozenset({"explosion", "caida"})
SENTIDO_RU_UA = "RU_UA"
RADIO_TIERRA_KM = 6371.0088


@dataclass(frozen=True)
class Caja:
    oeste: float
    sur: float
    este: float
    norte: float

    def contiene(self, lat: float, lon: float) -> bool:
        return self.sur <= lat <= self.norte and self.oeste <= lon <= self.este


@dataclass(frozen=True, slots=True)
class Foco:
    lat: float
    lon: float
    instante: datetime
    satelite: str
    instrumento: str
    confianza: str
    frp: float
    fuente: str

    def baja_confianza(self) -> bool:
        if self.instrumento == "MODIS":
            try:
                return int(self.confianza) < CONFIANZA_MODIS_MINIMA
            except ValueError:
                return True
        return self.confianza in CONFIANZA_VIIRS_BAJA

    def documento(self, distancia_km: float) -> Documento:
        return {
            "lat": self.lat,
            "lon": self.lon,
            "instante": _texto(self.instante),
            "satelite": self.satelite,
            "instrumento": self.instrumento,
            "confianza": self.confianza,
            "frp_mw": self.frp,
            "fuente": self.fuente,
            "distancia_km": round(distancia_km, 2),
        }


@dataclass(frozen=True)
class Impacto:
    id: str
    inicio: datetime
    fin: datetime
    lat: float | None = None
    lon: float | None = None
    radio_km: float | None = None

    @property
    def ventana_fin(self) -> datetime:
        return self.fin + HORAS_TRAS_FIN


@dataclass(frozen=True)
class Evaluacion:
    documento: Documento
    casados: list[Documento]


Lector = Callable[[date], list[Foco] | None]


def distancia_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    f1, f2 = math.radians(lat1), math.radians(lat2)
    df, dl = f2 - f1, math.radians(lon2 - lon1)
    a = math.sin(df / 2) ** 2 + math.cos(f1) * math.cos(f2) * math.sin(dl / 2) ** 2
    return 2 * RADIO_TIERRA_KM * math.asin(math.sqrt(a))


def _texto(momento: datetime) -> str:
    return momento.astimezone(UTC).strftime("%Y-%m-%dT%H:%MZ")


def _instante(momento: datetime) -> Documento:
    return {"valor": _texto(momento), "precision": "minuto"}


def _leer(valor: str) -> datetime:
    return datetime.fromisoformat(valor.replace("Z", "+00:00")).astimezone(UTC)


def _dias(desde: datetime, hasta: datetime) -> list[date]:
    dias, dia = [], desde.date()
    while dia <= hasta.date():
        dias.append(dia)
        dia += timedelta(days=1)
    return dias


def radio_busqueda(radio_km: float) -> float:
    return min(max(radio_km, RADIO_MIN_KM), RADIO_MAX_KM)


def _habitual(foco: Foco, base: list[Foco]) -> tuple[bool, float | None]:
    """Si el foco cae en un sitio que ya ardía en la base, y la mayor potencia que tuvo ese
    sitio con el mismo instrumento (o con cualquiera, si no hay del mismo)."""
    cerca = [
        b
        for b in base
        if distancia_km(foco.lat, foco.lon, b.lat, b.lon)
        <= max(DISTANCIA_HABITUAL_KM[foco.instrumento], DISTANCIA_HABITUAL_KM[b.instrumento])
    ]
    if not cerca:
        return False, None
    mismo = [b.frp for b in cerca if b.instrumento == foco.instrumento]
    return True, max(mismo or [b.frp for b in cerca])


def cuenta(foco: Foco, base: list[Foco]) -> bool:
    """Un foco válido de la ventana cuenta si es nuevo o si su potencia es anómala."""
    habitual, referencia = _habitual(foco, base)
    if not habitual:
        return True
    return referencia is not None and foco.frp > FACTOR_FRP * referencia


def _percentil(valores: list[float], q: float) -> float:
    ordenados = sorted(valores)
    return ordenados[min(len(ordenados) - 1, int(q * len(ordenados)))]


def cuenta_con_emplazamiento(foco: Foco, base_larga: list[Foco]) -> bool:
    """Un foco que es nuevo frente a los 30 días anteriores pero cae en un sitio que ya ardía
    en el año anterior (una antorcha estacional, como la de Kirishi, que pasa meses sin verse)
    cuenta solo si su potencia pasa de FACTOR_FRP veces la mediana de ese sitio en el año, con
    el mismo instrumento si lo hay."""
    cerca = [
        b for b in base_larga
        if distancia_km(foco.lat, foco.lon, b.lat, b.lon)
        <= max(DISTANCIA_HABITUAL_KM[foco.instrumento], DISTANCIA_HABITUAL_KM[b.instrumento])
    ]  # fmt: skip
    if len(cerca) < FOCOS_EMPLAZAMIENTO:
        return True
    mismo = [b.frp for b in cerca if b.instrumento == foco.instrumento] or [b.frp for b in cerca]
    return foco.frp > FACTOR_FRP * _percentil(mismo, PERCENTIL_EMPLAZAMIENTO)


def no_evaluable(motivo: str, ahora: datetime) -> Documento:
    return {"resultado": NO_EVALUABLE, "motivo": motivo, "evaluado": _instante(ahora)}


def fuego_frecuente(base: list[Foco], dias_con_focos: int) -> bool:
    """Si el radio arde de forma habitual y dispersa en la base (ver DIAS_FUEGO_FRECUENTE)."""
    celdas = {(round(f.lat, 2), round(f.lon, 2)) for f in base if not f.baja_confianza()}
    return dias_con_focos >= DIAS_FUEGO_FRECUENTE and len(celdas) >= CELDAS_FUEGO_FRECUENTE


def evaluar(impacto: Impacto, lector: Lector, ahora: datetime, caja: Caja) -> Evaluacion | None:
    """Evalúa el impacto. None si aún faltan datos de FIRMS de algún día de la ventana o de la
    base: se vuelve a intentar en la ejecución siguiente."""
    if impacto.lat is None or impacto.lon is None or impacto.radio_km is None:
        return Evaluacion(no_evaluable(SIN_LUGAR_PRECISO, ahora), [])
    if impacto.radio_km > RADIO_MAX_KM:
        return Evaluacion(no_evaluable(SIN_LUGAR_PRECISO, ahora), [])
    if not caja.contiene(impacto.lat, impacto.lon):
        return Evaluacion(no_evaluable(FUERA_DE_ZONA, ahora), [])
    inicio_base = impacto.inicio - timedelta(days=DIAS_BASE)
    if inicio_base.date() < INICIO_DATOS:
        return Evaluacion(no_evaluable(SIN_DATOS, ahora), [])
    radio = radio_busqueda(impacto.radio_km)

    def en_radio(focos: Iterable[Foco]) -> list[tuple[Foco, float]]:
        assert impacto.lat is not None and impacto.lon is not None
        return [
            (f, d)
            for f in focos
            if (d := distancia_km(impacto.lat, impacto.lon, f.lat, f.lon)) <= radio
        ]

    ventana: list[tuple[Foco, float]] = []
    for dia in _dias(impacto.inicio, impacto.ventana_fin):
        focos = lector(dia)
        if focos is None:
            return None
        ventana += [
            (f, d)
            for f, d in en_radio(focos)
            if impacto.inicio <= f.instante <= impacto.ventana_fin
        ]
    base: list[Foco] = []
    dias_con_datos = dias_con_focos = 0
    for dia in _dias(inicio_base, impacto.inicio - timedelta(minutes=1)):
        focos = lector(dia)
        if focos is None:
            continue
        dias_con_datos += 1
        del_dia = [f for f, _ in en_radio(focos) if inicio_base <= f.instante < impacto.inicio]
        dias_con_focos += bool(del_dia)
        base += del_dia
    if dias_con_datos < DIAS_BASE_MINIMOS:
        return None
    if fuego_frecuente(base, dias_con_focos):
        return Evaluacion(no_evaluable(FUEGO_FRECUENTE, ahora), [])
    validos = [(f, d) for f, d in ventana if not f.baja_confianza()]
    cuentan = sorted(
        ((f, d) for f, d in validos if cuenta(f, base)), key=lambda x: (x[0].instante, x[1])
    )
    documento: Documento = {
        "radio_km": radio,
        "ventana": {"inicio": _instante(impacto.inicio), "fin": _instante(impacto.ventana_fin)},
        "focos_en_ventana": len(ventana),
        "linea_base": {"focos": len(base), "dias": dias_con_focos},
        "fuentes_firms": sorted({f.fuente for f, _ in ventana} | {f.fuente for f in base}),
        "evaluado": _instante(ahora),
    }
    if base:
        documento["linea_base"]["frp_max_mw"] = max(f.frp for f in base)
    if len(cuentan) >= FOCOS_MINIMOS:
        nuevos = [(f, d) for f, d in cuentan if not _habitual(f, base)[0]]
        por_paso: dict[tuple[datetime, str], int] = {}
        for f, _ in cuentan:
            por_paso[(f.instante, f.satelite)] = por_paso.get((f.instante, f.satelite), 0) + 1
        if nuevos and max(por_paso.values()) < FOCOS_POR_PASO_INCENDIO:
            base_larga = _base_larga(impacto, lector, radio, inicio_base)
            descartados = {id(f) for f, _ in nuevos if not cuenta_con_emplazamiento(f, base_larga)}
            if descartados:
                cuentan = [(f, d) for f, d in cuentan if id(f) not in descartados]
                documento["linea_base"]["emplazamiento"] = {
                    "focos": len(base_larga),
                    "descartados": len(descartados),
                }
    if len(cuentan) >= FOCOS_MINIMOS:
        primero, distancia = cuentan[0]
        documento = {
            "resultado": DETECTADO,
            "primer_foco": _instante(primero.instante),
            "satelite": primero.satelite,
            "instrumento": primero.instrumento,
            "distancia_km": round(distancia, 1),
            "numero_focos": len(cuentan),
            "frp_max_mw": max(f.frp for f, _ in cuentan),
            **documento,
        }
    else:
        motivo = (
            FOCO_AISLADO if cuentan
            else SIN_FOCOS if not ventana
            else SOLO_BAJA_CONFIANZA if not validos
            else FUENTE_HABITUAL
        )  # fmt: skip
        documento = {"resultado": NO_DETECTADO, "motivo": motivo, **documento}
    return Evaluacion(documento, [f.documento(d) for f, d in cuentan])


def _base_larga(impacto: Impacto, lector: Lector, radio: float, hasta: datetime) -> list[Foco]:
    """Los focos en el radio del impacto del año anterior a la base de 30 días."""
    assert impacto.lat is not None and impacto.lon is not None
    desde = impacto.inicio - timedelta(days=DIAS_BASE_LARGA)
    resultado: list[Foco] = []
    for dia in _dias(max(desde, datetime.combine(INICIO_DATOS, datetime.min.time(), UTC)), hasta):
        for f in lector(dia) or []:
            if desde <= f.instante < hasta and (
                distancia_km(impacto.lat, impacto.lon, f.lat, f.lon) <= radio
            ):
                resultado.append(f)
    return resultado


# --- Impactos de la base ----------------------------------------------------------------


def _fin(tiempo: Documento) -> datetime:
    if "fin" in tiempo:
        return _leer(tiempo["fin"]["valor"])
    inicio = tiempo["inicio"]
    return _leer(inicio["valor"]) + DURACION_POR_PRECISION.get(inicio["precision"], timedelta(0))


def impacto_de_incidente(incidente: Documento) -> Impacto | None:
    """El incidente como impacto si tiene prueba de que el dron explotó o cayó."""
    if "fusionado_en" in incidente or "retirado" in incidente:
        return None
    evidencia = set(incidente.get("pruebas", {}).get("evidencia", []))
    if not evidencia & EVIDENCIA_IMPACTO:
        return None
    lugar, tiempo = incidente["lugar"], incidente["tiempo"]
    punto = lugar.get("punto")
    return Impacto(
        id=incidente["id"],
        inicio=_leer(tiempo["inicio"]["valor"]),
        fin=_fin(tiempo),
        lat=punto["lat"] if punto else None,
        lon=punto["lon"] if punto else None,
        radio_km=lugar.get("radio_km") if punto else None,
    )


def impacto_de_guerra(documento: Documento, inicio: datetime, fin: datetime) -> Impacto:
    """Un impacto con lugar de la capa de guerra (proceso/impactos_guerra.py): su localidad o su
    instalación, con la ventana del ataque al que está enlazado."""
    lugar = documento["lugar"]
    return Impacto(
        id=documento["id"],
        inicio=inicio,
        fin=fin,
        lat=lugar["punto"]["lat"],
        lon=lugar["punto"]["lon"],
        radio_km=lugar["radio_km"],
    )


def regiones_con_impacto(ataque: Documento, codigos: dict[str, str]) -> list[str]:
    """Regiones del ataque citadas entre los lugares con impacto (el parte las nombra por su
    nombre oficial; `codigos` va del nombre al código ISO) o con impactos contados."""
    nombradas = {codigos[n] for n in ataque.get("lugares_impacto", []) if n in codigos}
    con_cifra = {
        r["region"]
        for r in ataque.get("regiones", [])
        if isinstance(r.get("impactos"), dict) and r["impactos"]["max"] > 0
    }
    presentes = {r["region"] for r in ataque.get("regiones", [])}
    return sorted((nombradas | con_cifra) & presentes)


def impactos_de_ataque(ataque: Documento, codigos: dict[str, str]) -> list[Impacto]:
    """Las regiones con impacto de un ataque RU→UA, sin punto: el parte solo da la región."""
    if ataque.get("sentido") != SENTIDO_RU_UA:
        return []
    periodo = ataque["periodo"]
    inicio, fin = _leer(periodo["inicio"]["valor"]), _leer(periodo["fin"]["valor"])
    return [
        Impacto(id=f"{ataque['id']}/{codigo}", inicio=inicio, fin=fin)
        for codigo in regiones_con_impacto(ataque, codigos)
    ]


@dataclass
class Resumen:
    evaluados: int = 0
    pendientes: int = 0
    sin_cambios: int = 0
    resultados: dict[str, int] | None = None

    def texto(self) -> str:
        cuentas = ", ".join(f"{k} {v}" for k, v in sorted((self.resultados or {}).items()))
        return (
            f"{self.evaluados} evaluados con cambios, {self.sin_cambios} sin cambios, "
            f"{self.pendientes} pendientes de datos; en la base: {cuentas or 'ninguno'}"
        )


def evaluar_todos(
    almacen: "Almacen",
    impactos: Iterable[Impacto],
    lector: Lector,
    ahora: datetime,
    caja: Caja,
    plazo: "Plazo | None" = None,
    reevaluar_todo: bool = False,
) -> Resumen:
    """Evalúa cada impacto que aún puede cambiar y guarda su resultado y sus focos. Uno cuya
    ventana cerró hace más de una semana y ya tiene resultado (que no sea «detectado») no se
    vuelve a mirar, salvo con
    `reevaluar_todo`: mientras se descarga el histórico, un día puede tener solo algunos
    productos, y lo evaluado con ellos se rehace cuando llegan los demás. Por orden de fecha,
    para que impactos vecinos lean los mismos días; los que no caben en el plazo quedan
    pendientes para la ejecución siguiente."""
    resumen = Resumen()
    previos: dict[str, Documento] = almacen.focos_termicos()
    for impacto in sorted(impactos, key=lambda i: (i.inicio, i.id)):
        anterior = previos.get(impacto.id)
        # Las detecciones se rehacen siempre: son pocas y así les llega cualquier cambio de la
        # regla (un «detectado» sube la credibilidad y se publica; lo demás, no).
        if (
            anterior is not None
            and not reevaluar_todo
            and anterior.get("resultado") != DETECTADO
            and ahora - impacto.ventana_fin > REEVALUAR
        ):
            resumen.sin_cambios += 1
            continue
        if plazo is not None and plazo.agotado():
            resumen.pendientes += 1
            continue
        evaluacion = evaluar(impacto, lector, ahora, caja)
        if evaluacion is None:
            resumen.pendientes += 1
            continue
        cambiado = almacen.guardar_foco_termico(impacto.id, evaluacion.documento)
        almacen.guardar_focos_casados(impacto.id, evaluacion.casados)
        if cambiado:
            resumen.evaluados += 1
        else:
            resumen.sin_cambios += 1
    cuentas: dict[str, int] = {}
    for documento in almacen.focos_termicos().values():
        cuentas[documento["resultado"]] = cuentas.get(documento["resultado"], 0) + 1
    resumen.resultados = cuentas
    return resumen


# --- Publicación ------------------------------------------------------------------------


def con_focos(
    incidentes: Iterable[Documento], ataques: Iterable[Documento], focos: dict[str, Documento]
) -> tuple[list[Documento], list[Documento]]:
    """Copias de los incidentes y de los ataques con el bloque foco_termico de cada impacto
    evaluado (en el incidente o en la región del ataque). Los documentos guardados no lo
    llevan: vive en su propia tabla."""
    con_incidentes = [
        {**i, "foco_termico": focos[i["id"]]} if i.get("id") in focos else i for i in incidentes
    ]
    con_ataques = []
    for ataque in ataques:
        regiones = ataque.get("regiones")
        if regiones and any(f"{ataque['id']}/{r['region']}" in focos for r in regiones):
            ataque = {
                **ataque,
                "regiones": [
                    {**r, "foco_termico": focos[clave]}
                    if (clave := f"{ataque['id']}/{r['region']}") in focos
                    else r
                    for r in regiones
                ],
            }
        con_ataques.append(ataque)
    return con_incidentes, con_ataques


def solo_detectado(documento: Documento) -> None:
    """Quita el bloque foco_termico si no es un positivo: públicamente solo se muestra el
    foco detectado. Sirve para un incidente o para una región."""
    foco = documento.get("foco_termico")
    if foco is not None and foco.get("resultado") != DETECTADO:
        del documento["foco_termico"]
