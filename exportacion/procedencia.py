"""Origen y método de cada valor exportado, valores sin respaldo y nivel de detalle.

Principio: la exportación para AEGIS da datos de calidad. Un campo vacío es mejor que uno de
relleno, y cada valor dice de dónde sale para que AEGIS se quede solo con lo que le sirve.

- origen (comun#/$defs/origen) sale de la tabla de fuentes, nunca se supone:
  declaración de una autoridad citada por un medio (fuente «…-declaracion-N») →
  oficial_citado; fuente interna fuera de la capa de guerra (Ministerio de Defensa ruso) →
  parte; autoridad o fiabilidad A (notas oficiales leídas) y el canal de la Fuerza Aérea de
  Ucrania → oficial; lo demás (noticias) → prensa; el foco térmico de FIRMS → medido.
- metodo: extractor (afirmaciones de la ficha), parser (partes y notas oficiales) o regla
  (valores que calcula el código: tipo, geocodificación, duración, presencia por
  declaraciones…). Un valor por regla toma el origen de mayor rango de los valores de que sale.
- Con varias fuentes, el origen del valor es el de mayor rango: medido, oficial,
  oficial_citado, parte, prensa.
- Sin relleno: un valor que solo respalda el extractor sin frase de origen o con confianza
  por debajo del umbral de la validación se quita del documento exportado; su procedencia
  lo dice («sin_respaldo», con la confianza). «desconocido» (ninguna fuente lo dice) se
  conserva y su procedencia lo marca. Nunca se pone un valor por defecto.
- Un valor sin origen es un error: la versión no se publica (ExportacionInvalida).
"""

import json
from collections import defaultdict
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from typing import Any

from almacen.base import Almacen
from esquema import Documento
from exportacion import mejor_origen
from proceso import declaraciones, extraccion, fechas
from proceso.estados import Estado
from proceso.validacion_ficha import UMBRAL_CONFIANZA

MEDIDO, OFICIAL, REGISTRO, OFICIAL_CITADO, PARTE, PRENSA, DEDUCIDO = (
    "medido", "oficial", "registro", "oficial_citado", "parte", "prensa", "deducido",
)  # fmt: skip
# registro: dato de un registro público de instalaciones (el nomenclátor, de OpenStreetMap),
# lo pone exportacion/mejor_origen.py en los campos de la instalación.
RANGO = (MEDIDO, OFICIAL, REGISTRO, OFICIAL_CITADO, PARTE, PRENSA, DEDUCIDO)
PARSER, EXTRACTOR, REGLA = "parser", "extractor", "regla"
DESCONOCIDO = "desconocido"
CONFIRMADOS = frozenset({Estado.CONFIRMADO, Estado.ATRIBUIDO})
NIVELES = ("A", "B", "C", "D")
# Canal de la Fuerza Aérea de Ucrania (configuracion/fuentes.json, fuerza_aerea_ua).
CANAL_FUERZA_AEREA = "t.me/kpszsu"
MARCA_DECLARACION = "-declaracion-"
RADIO_MAX_B_KM = 5.0
CIERRE_MEDIDO = "cierre_medido"
# Un cierre medido cuenta como indicador con cobertura alta o media (como sale a la web) y
# para el nivel B solo con cobertura alta.
COBERTURA_MEDIDA = frozenset({"alta", "media"})
COBERTURA_B = frozenset({"alta"})
PRECISIONES_B = frozenset({"minuto", "hora"})
DINAMICA = ("drones.trayectoria", "drones.altura_m", "drones.velocidad_ms")


class SinOrigen(ValueError):
    """Un valor exportado del que no se sabe el origen."""


def mejor(origenes: Iterable[str]) -> str | None:
    presentes = set(origenes)
    return next((o for o in RANGO if o in presentes), None)


def _origen_canal_guerra(fuente: Documento) -> str | None:
    """El origen de un canal de la capa de guerra con lugar (configuracion/canales_guerra.json):
    oficial (administraciones militares regionales de Ucrania) o parte (Estado Mayor ucraniano,
    gobernadores rusos y autoridades instaladas por Rusia)."""
    from proceso.impactos_guerra import canal_de_fuente

    canal = canal_de_fuente(fuente)
    return canal.origen if canal is not None else None


def origen_de_fuente(fuente: Documento) -> str:
    if MARCA_DECLARACION in fuente["id"]:
        return OFICIAL_CITADO
    guerra = _origen_canal_guerra(fuente)
    if guerra is not None:
        return guerra
    if fuente.get("interna_fuera_de_ucrania"):
        return PARTE
    if fuente.get("es_autoridad") or fuente["fiabilidad"] == "A":
        return OFICIAL
    if CANAL_FUERZA_AEREA in fuente.get("enlace", ""):
        return OFICIAL
    return PRENSA


def metodo_de_fuente(fuente: Documento) -> str:
    """Cómo llega a la base lo que dice una fuente que no es una noticia: la declaración la
    encuentra el extractor en la noticia que la cita; partes y notas oficiales, un parser. Las
    fuentes oficiales de detalle declaran el suyo (parser, extractor o regla)."""
    if fuente.get("metodo"):
        return str(fuente["metodo"])
    return EXTRACTOR if MARCA_DECLARACION in fuente["id"] else PARSER


def confirma(fuente: Documento) -> bool:
    """Fuente de una autoridad que respalda el estado: confirma el incidente aunque ya lo
    hubiera confirmado otra antes (y su paso no esté en el historial). Solo las leídas
    directamente (fiabilidad A): una declaración citada puede negar el incidente."""
    return (
        bool(fuente.get("es_autoridad"))
        and fuente["fiabilidad"] == "A"
        and MARCA_DECLARACION not in fuente["id"]
        and "estado" in fuente.get("campos_respaldados", [])
    )


# --- Recorrido de valores ------------------------------------------------------------

# Bloques del registro que no son datos del suceso: identificación, fuentes, control del
# proceso y lo que añade la exportación. El título es una etiqueta descriptiva.
META_INCIDENTE = frozenset({
    "id", "titulo", "fuentes", "afirmaciones", "afirmaciones_publicas", "control",
    "procedencia", "nivel_detalle", "indicadores", "fusionado_en", "retirado", "episodio",
    "encuentros",
    "deduccion",
})  # fmt: skip
# deduccion: lo deducido va aparte, con su propia procedencia (procedencia_deduccion).
META_ATAQUE = frozenset({"id", "fuentes", "afirmaciones", "control", "procedencia", "deduccion"})
# Bloques de mediciones físicas, con origen medido y método regla.
MEDICIONES = frozenset({"trafico_aereo", "condiciones"})
# Nodos que se tratan como un solo valor.
HOJAS = frozenset({
    "estado", "atribucion", "foco_termico", "drones.trayectoria", "consecuencias.danos",
    "trafico_aereo", "condiciones", "tiempo.origen_inicio",
})  # fmt: skip
CLAVES_VALOR = (frozenset({"valor", "precision"}), frozenset({"min", "max"}),
                frozenset({"lat", "lon"}))  # fmt: skip


def _es_valor(nodo: Any) -> bool:
    return not isinstance(nodo, dict) or any(set(nodo) == c for c in CLAVES_VALOR)


def valores(documento: Documento, meta: frozenset[str] = META_INCIDENTE) -> Iterator[str]:
    """Rutas de los valores del documento («tiempo.inicio», «drones.numero»)."""

    def recorrer(nodo: Documento, ruta: str) -> Iterator[str]:
        for clave, hijo in nodo.items():
            sub = f"{ruta}.{clave}" if ruta else clave
            if not ruta and clave in meta:
                continue
            if sub in HOJAS or _es_valor(hijo):
                yield sub
            else:
                yield from recorrer(hijo, sub)

    yield from recorrer(documento, "")


def leer(documento: Documento, ruta: str) -> Any:
    valor: Any = documento
    for parte in ruta.split("."):
        if not isinstance(valor, dict) or parte not in valor:
            return None
        valor = valor[parte]
    return valor


def quitar(documento: Documento, ruta: str) -> None:
    *padres, ultima = ruta.split(".")
    nodo = documento
    for parte in padres:
        nodo = nodo[parte]
    del nodo[ultima]
    # Un objeto que se queda vacío tampoco es un valor.
    if padres and not nodo:
        quitar(documento, ".".join(padres))


# --- Correspondencias ----------------------------------------------------------------

# Campo de la ficha del extractor → ruta del valor en el incidente.
FICHA_A_RUTA = {
    "inicio": "tiempo.inicio", "inicio_precision": "tiempo.inicio", "fin": "tiempo.fin",
    "pais": "lugar.pais", "lugar_suceso": "lugar.suceso", "lugar_nuevo": "lugar.suceso",
    "localidad": "lugar.localidad",
    "objetivo_categoria": "objetivo.categoria", "objetivo_nombre": "objetivo.nombre",
    "drones": "drones.numero", "modelo_dron": "drones.modelo", "presencia_dron": "presencia_dron",
    "cierre": "consecuencias.cierre.valor", "cierre_minutos": "consecuencias.cierre.minutos",
    "vuelos_desviados": "consecuencias.vuelos_desviados",
    "vuelos_cancelados": "consecuencias.vuelos_cancelados",
    "vuelos_retrasados": "consecuencias.vuelos_retrasados",
    "medidas": "respuesta.medidas",
    "dron_estatal": "pruebas.dron_estatal", "entrada_exterior": "pruebas.entrada_exterior",
    "evidencia": "pruebas.evidencia", "origen_demostrado": "pruebas.evidencia",
}  # fmt: skip
# «noticias»: si no hay otra cosa, el valor sale del candidato de noticias (la fecha del
# primer artículo, el lugar que nombran los titulares): su origen es el de las noticias.
NOTICIAS = "noticias"
_LUGAR = ("lugar.suceso", "lugar.localidad", "objetivo.nombre", "lugar.pais", "ficha:lugar_suceso",
          "ficha:objetivo_conocido", NOTICIAS)  # fmt: skip
_TIPO = ("pruebas.dron_estatal", "pruebas.entrada_exterior", "pruebas.evidencia", "estado")
# Valores que calcula el código, con los valores de que salen («ficha:» es un campo de la
# ficha que no queda como valor del incidente).
REGLAS: dict[str, tuple[str, ...]] = {
    "tipo": (*_TIPO, "consecuencias.cierre.valor", "consecuencias.vuelos_desviados",
             "consecuencias.vuelos_cancelados", "consecuencias.vuelos_retrasados",
             "objetivo.categoria", "ficha:tipo"),
    "origen_demostrado_por": _TIPO,
    "tiempo.duracion_min": ("tiempo.inicio", "tiempo.fin"),
    "tiempo.origen_inicio": ("tiempo.inicio",),
    "tiempo.inicio": ("ficha:inicio", NOTICIAS),
    "lugar.suceso": ("ficha:lugar_suceso", "ficha:lugar_nuevo", "ficha:localidad",
                     "ficha:objetivo_nombre", NOTICIAS),
    "lugar.punto": _LUGAR, "lugar.radio_km": _LUGAR, "lugar.nivel": _LUGAR,
    "lugar.region": _LUGAR, "lugar.geocodificacion": _LUGAR, "lugar.nuts2": _LUGAR,
    "lugar.pais": _LUGAR,
    "objetivo.categoria": ("ficha:objetivo_conocido", "lugar.suceso", NOTICIAS),
    "objetivo.nombre": ("ficha:objetivo_conocido", "lugar.suceso", NOTICIAS),
    "objetivo.oaci": ("objetivo.nombre",), "objetivo.uso": ("objetivo.nombre",),
    "pruebas.dron_estatal": ("pruebas.evidencia", "drones.modelo"),
    "pruebas.entrada_exterior": ("ficha:tipo", "pruebas.evidencia"),
    "pruebas.evidencia": ("ficha:origen_demostrado",),
    "presencia_dron": ("estado", "pruebas.evidencia"),
}  # fmt: skip
# Rutas cuyo valor puede cambiarlo una regla: la afirmación cuenta solo si coincide.
MISMO_VALOR = frozenset({
    "presencia_dron", "pruebas.dron_estatal", "pruebas.entrada_exterior",
    "consecuencias.cierre.valor",
})  # fmt: skip
# Valores que la regla pone cuando ninguna fuente dice nada (el esquema no deja escribir
# «desconocido» en ellos): falso o lista vacía no son una afirmación.
POR_DEFECTO_DE_REGLA = frozenset({
    "pruebas.dron_estatal", "pruebas.entrada_exterior", "pruebas.evidencia",
})  # fmt: skip
# Incidentes que hace un parser (cruces de los partes de Ucrania): todo sale de sus fuentes.
PREFIJOS_PARSER = ("incursion/",)
# Rutas que el esquema exige: un valor sin respaldo en ellas es un error, no se quita.
OBLIGATORIAS = frozenset({"tipo", "estado", "tiempo.inicio", "lugar.pais"})


# --- Frases de las fichas ------------------------------------------------------------


def _canonico(valor: Any) -> str:
    return json.dumps(valor, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


@dataclass
class Fichas:
    """Lo que guardan las extracciones de cada incidente: por campo y valor, si tenía frase."""

    almacen: Almacen
    candidatos: dict[str, set[str]] = field(default_factory=dict)
    _campos: dict[str, dict[str, list[tuple[str, bool]]]] = field(default_factory=dict)
    no_enlazadas: int = 0

    @classmethod
    def de(cls, almacen: Almacen) -> "Fichas":
        candidatos: dict[str, set[str]] = defaultdict(set)
        for candidato_id, incidente_id in extraccion.vincular(almacen).items():
            candidatos[incidente_id].add(candidato_id)
        for candidato in almacen.candidatos():
            for extraida in almacen.extracciones(candidato["id"]):
                if extraida.get("incidente"):
                    candidatos[extraida["incidente"]].add(candidato["id"])
        for incidente in almacen.incidentes():
            if incidente["control"].get("candidato"):
                candidatos[incidente["id"]].add(incidente["control"]["candidato"])
        # Lo de los incidentes fundidos en otro también es del destino.
        absorbidos: dict[str, list[str]] = defaultdict(list)
        for fusion in almacen.fusiones():
            if not fusion["revertida"]:
                absorbidos[fusion["destino"]].append(fusion["absorbido"])
        cerrados: dict[str, set[str]] = {}
        for id_ in list(candidatos) + list(absorbidos):
            vistos, pendientes, propios = set(), [id_], set()
            while pendientes:
                actual = pendientes.pop()
                if actual in vistos:
                    continue
                vistos.add(actual)
                propios |= candidatos.get(actual, set())
                pendientes += absorbidos.get(actual, [])
            cerrados[id_] = propios
        return cls(almacen, cerrados)

    def _de_candidato(self, candidato: str) -> dict[str, list[tuple[str, bool]]]:
        if candidato not in self._campos:
            campos: dict[str, list[tuple[str, bool]]] = defaultdict(list)
            for extraida in self.almacen.extracciones(candidato):
                for nombre, campo in (extraida.get("campos") or {}).items():
                    frase = bool(str(campo.get("frase") or "").strip())
                    campos[nombre].append((_canonico(campo.get("valor")), frase))
            self._campos[candidato] = campos
        return self._campos[candidato]

    def tiene_frase(self, entidad: str, campo: str, valor: Any) -> bool | None:
        """Si la ficha que dio el valor traía frase; None si no se encuentra la extracción
        (vale lo que comprobó la validación al guardarla: frase literal en la fuente)."""
        vistos = [
            par
            for candidato in sorted(self.candidatos.get(entidad, ()))
            for par in self._de_candidato(candidato).get(campo, [])
        ]
        iguales = [frase for v, frase in vistos if v == _canonico(valor)]
        hallados = iguales or [frase for _, frase in vistos]
        if not hallados:
            self.no_enlazadas += 1
            return None
        return any(hallados)


def sin_respaldo(afirmacion: Documento, entidad: str, fichas: Fichas) -> dict[str, Any] | None:
    """{confianza, motivo} si el extractor dio el valor sin respaldo; None si lo tiene."""
    confianza = float(afirmacion["confianza_extraccion"])
    if confianza < UMBRAL_CONFIANZA:
        return {"confianza": confianza, "motivo": "confianza_baja"}
    if fichas.tiene_frase(entidad, afirmacion["campo"], afirmacion["valor"]) is False:
        return {"confianza": confianza, "motivo": "sin_frase"}
    return None


def de_regla(afirmacion: Documento) -> bool:
    """La afirmación de presencia que deja el criterio de presencia (no el extractor): la de una
    declaración oficial citada, la de un cierre por dron o la de un documento oficial."""
    return afirmacion == declaraciones.afirmacion_presencia(afirmacion["fuente_id"])


def de_reconstruccion(afirmacion: Documento) -> bool:
    """objetivo_conocido falso que pone la reconstrucción cuando la ficha nombra otra
    instalación (extraccion.reconstruir): sin frase y con confianza 1, es una regla."""
    return (
        afirmacion["campo"] == "objetivo_conocido"
        and afirmacion["valor"] is False
        and float(afirmacion["confianza_extraccion"]) == 1.0
    )


# --- Incidentes ----------------------------------------------------------------------


@dataclass
class Valor:
    origenes: set[str] = field(default_factory=set)
    metodo: str | None = None
    fuentes: set[str] = field(default_factory=set)
    confianza: float | None = None

    def documento(self) -> Documento:
        origen = mejor(self.origenes)
        if origen is None or self.metodo is None:
            raise SinOrigen("valor sin origen")
        resultado: Documento = {"origen": origen, "metodo": self.metodo,
                                "fuentes": sorted(self.fuentes)}  # fmt: skip
        if self.confianza is not None:
            resultado["confianza"] = self.confianza
        return resultado


def _respaldan(fuente: Documento, ruta: str) -> bool:
    return any(
        c == ruta or ruta.startswith(f"{c}.") or c.startswith(f"{ruta}.")
        for c in fuente.get("campos_respaldados", [])
    )


def procedencia_incidente(documento: Documento, fichas: Fichas) -> tuple[Documento, Documento]:
    """El incidente como se exporta (sin los valores sin respaldo) y su procedencia."""
    fuentes = {f["id"]: f for f in documento["fuentes"]}
    origen = {id_: origen_de_fuente(f) for id_, f in fuentes.items()}
    extraidas: dict[str, list[Documento]] = defaultdict(list)
    por_ficha: dict[str, list[Documento]] = defaultdict(list)
    regla: dict[str, list[Documento]] = defaultdict(list)
    for afirmacion in documento.get("afirmaciones", []):
        if afirmacion["fuente_id"] not in fuentes:
            continue
        if de_regla(afirmacion):
            regla[afirmacion["campo"]].append(afirmacion)
            continue
        por_ficha[afirmacion["campo"]].append(afirmacion)
        # Campo de la ficha, o ya la ruta del valor (las afirmaciones de los partes).
        ruta = FICHA_A_RUTA.get(afirmacion["campo"], afirmacion["campo"])
        if leer(documento, ruta) is not None or ruta in FICHA_A_RUTA.values():
            extraidas[ruta].append(afirmacion)
    exportado = json.loads(json.dumps(documento))
    procedencia: Documento = {}
    pendientes: list[str] = []

    def de_fuentes(ruta: str) -> Valor | None:
        valor = Valor()
        if ruta == "estado":
            actual = documento["estado"]["actual"]
            pasos = [p for p in documento["estado"]["historial"] if p["estado"] == actual]
            valor.fuentes = {p["fuente_id"] for p in pasos if p["fuente_id"] in fuentes}
            if actual in CONFIRMADOS:
                valor.fuentes |= {id_ for id_, f in fuentes.items() if confirma(f)}
            valor.origenes = {origen[f] for f in valor.fuentes}
            valor.metodo = REGLA
            return valor if valor.fuentes else None
        if ruta == "atribucion":
            pasos = [p for p in documento["estado"]["historial"] if p["estado"] == Estado.ATRIBUIDO]
            valor.fuentes = {p["fuente_id"] for p in pasos[-1:] if p["fuente_id"] in fuentes}
            valor.origenes = {origen[f] for f in valor.fuentes}
            valor.metodo = min((metodo_de_fuente(fuentes[f]) for f in valor.fuentes),
                               default=None)  # fmt: skip
            return valor if valor.fuentes else None
        if ruta == "foco_termico":
            return Valor({MEDIDO}, PARSER)
        if ruta in MEDICIONES:
            # Tráfico aéreo y condiciones medidas: los calcula el código (proceso/mediciones.py)
            # a partir de datos físicos; su regla y su versión van en el propio bloque.
            bloque = documento[ruta]
            return Valor({MEDIDO}, REGLA, {bloque["fuente_id"]} if "fuente_id" in bloque else set())
        if ruta == "presencia_dron":
            confirmadas = [a for a in regla.get("presencia_dron", [])
                           if a["valor"] == documento.get("presencia_dron")]  # fmt: skip
            if confirmadas:
                valor.fuentes = {a["fuente_id"] for a in confirmadas}
                valor.origenes = {origen[f] for f in valor.fuentes}
                valor.metodo = REGLA
                return valor
        actual = leer(documento, ruta)
        afirmaciones = [a for a in extraidas.get(ruta, [])
                        if ruta not in MISMO_VALOR or a["valor"] == actual]  # fmt: skip
        # Lo que respaldan las fuentes que no son noticias (partes, notas oficiales). Una
        # noticia cuenta solo por sus afirmaciones; una declaración, por el estado, la
        # atribución y la presencia, que se tratan aparte.
        respaldo = [f for f in fuentes.values()
                    if origen[f["id"]] != PRENSA and MARCA_DECLARACION not in f["id"]
                    and _respaldan(f, ruta)]  # fmt: skip
        if not afirmaciones and not respaldo:
            return None
        valor.fuentes = {a["fuente_id"] for a in afirmaciones} | {f["id"] for f in respaldo}
        valor.origenes = {origen[f] for f in valor.fuentes}
        mejor_origen = mejor(valor.origenes)
        de_parser = [f for f in respaldo if origen[f["id"]] == mejor_origen]
        valor.metodo = metodo_de_fuente(de_parser[0]) if de_parser else EXTRACTOR
        if afirmaciones:
            valor.confianza = max(float(a["confianza_extraccion"]) for a in afirmaciones)
            if not respaldo:
                faltas = [sin_respaldo(a, documento["id"], fichas) for a in afirmaciones]
                if all(faltas):
                    peor = max(faltas, key=lambda f: f["confianza"] if f else 0)
                    if ruta in OBLIGATORIAS:
                        raise SinOrigen(f"{documento['id']}: {ruta} sin respaldo y obligatorio")
                    valor.confianza = None
                    resultado = valor.documento()
                    resultado["sin_respaldo"] = peor
                    procedencia[ruta] = resultado
                    quitar(exportado, ruta)
                    return Valor()  # ya resuelto
        return valor

    def de_regla_(ruta: str) -> Valor | None:
        entradas = REGLAS.get(ruta)
        if entradas is None:
            return None
        valor = Valor(metodo=REGLA)
        for entrada in entradas:
            if entrada == NOTICIAS:
                if not valor.origenes:
                    noticias = {f for f, o in origen.items() if o == PRENSA}
                    valor.fuentes |= noticias
                    valor.origenes |= {PRENSA} if noticias else set()
            elif entrada.startswith("ficha:"):
                for afirmacion in por_ficha.get(entrada[len("ficha:") :], []):
                    valor.fuentes.add(afirmacion["fuente_id"])
                    valor.origenes.add(origen[afirmacion["fuente_id"]])
            elif entrada in procedencia and "sin_respaldo" not in procedencia[entrada]:
                valor.fuentes |= set(procedencia[entrada]["fuentes"])
                valor.origenes.add(procedencia[entrada]["origen"])
        return valor if valor.origenes else None

    def de_parser(ruta: str) -> Documento | None:
        version = str(documento["control"].get("version_extractor", ""))
        if not version.startswith(PREFIJOS_PARSER) or not fuentes:
            return None
        return {"origen": mejor(origen.values()), "metodo": PARSER, "fuentes": sorted(fuentes)}

    def desconocido(ruta: str) -> Documento | None:
        actual = leer(documento, ruta)
        por_defecto = ruta in POR_DEFECTO_DE_REGLA and actual in (False, [])
        if actual != DESCONOCIDO and not por_defecto:
            return None
        # Ninguna fuente lo dice: su origen es el de las fuentes leídas.
        origen_leidas = mejor(origen.values())
        if origen_leidas is None:
            return None
        return {"origen": origen_leidas, "metodo": REGLA, "fuentes": [], "desconocido": True}

    rutas = list(valores(documento))
    # Primero lo que dicen las fuentes; después, en orden, lo que calcula el código.
    for ruta in rutas:
        valor = de_fuentes(ruta)
        if valor is None:
            pendientes.append(ruta)
        elif valor.origenes:
            procedencia[ruta] = valor.documento()
    for _ in range(len(pendientes) + 1):
        resueltas = []
        for ruta in pendientes:
            marca = de_parser(ruta) or desconocido(ruta)
            valor = de_regla_(ruta) if marca is None else None
            if marca is not None:
                procedencia[ruta] = marca
            elif valor is not None:
                procedencia[ruta] = valor.documento()
            else:
                continue
            resueltas.append(ruta)
        pendientes = [r for r in pendientes if r not in resueltas]
        if not resueltas:
            break
    if pendientes:
        raise SinOrigen(f"{documento['id']}: sin origen en {', '.join(sorted(pendientes))}")
    return exportado, dict(sorted(procedencia.items()))


def _origen_confirmacion(documento: Documento, procedencia: Documento) -> str | None:
    """Origen de la confirmación del incidente: el de la fuente del último paso a confirmado
    y el de las autoridades que, además, respaldan el estado; el de mayor rango."""
    if documento["estado"]["actual"] not in CONFIRMADOS:
        return None
    fuentes = {f["id"]: f for f in documento["fuentes"]}
    pasos = [p for p in documento["estado"]["historial"] if p["estado"] == Estado.CONFIRMADO]
    if not pasos or pasos[-1]["fuente_id"] not in fuentes:
        origen: str | None = procedencia.get("estado", {}).get("origen")
        return origen
    origenes = {origen_de_fuente(fuentes[pasos[-1]["fuente_id"]])}
    origenes |= {origen_de_fuente(f) for f in fuentes.values() if confirma(f)}
    return mejor(origenes)


def _precision_b(documento: Documento) -> bool:
    """Hora con precisión de minuto u hora y radio de 5 km o menos, en los valores públicos o
    en los que precisa un registro oficial (detalle_oficial)."""
    detalle = documento.get("detalle_oficial", {})
    precisiones = {documento["tiempo"]["inicio"]["precision"]}
    if "inicio" in detalle:
        precisiones.add(detalle["inicio"]["precision"])
    radios = [
        float(r) for r in (documento["lugar"].get("radio_km"), detalle.get("radio_km"))
        if r is not None
    ]  # fmt: skip
    return bool(precisiones & PRECISIONES_B) and bool(radios) and min(radios) <= RADIO_MAX_B_KM


def _cierre_medido(documento: Documento, cobertura: frozenset[str] = COBERTURA_MEDIDA) -> bool:
    """Cierre medido con tráfico aéreo con la cobertura pedida (alta para el nivel B)."""
    cierre = documento.get("trafico_aereo", {}).get("cierre", {})
    nivel = cierre.get("cobertura", {}).get("nivel")
    return cierre.get("resultado") == CIERRE_MEDIDO and nivel in cobertura


def nivel_detalle(documento: Documento, procedencia: Documento) -> str:
    """A, B, C o D (comun#/$defs/nivel_detalle), sobre el incidente ya exportado."""
    for ruta in DINAMICA:
        valor = leer(documento, ruta)
        if valor not in (None, DESCONOCIDO) and procedencia.get(ruta, {}).get("origen") in {
            MEDIDO, OFICIAL,
        }:  # fmt: skip
            return "A"
    confirmacion = _origen_confirmacion(documento, procedencia)
    precisa = _precision_b(documento)
    if precisa and (confirmacion == OFICIAL or _cierre_medido(documento, COBERTURA_B)):
        return "B"
    if confirmacion in {OFICIAL, OFICIAL_CITADO}:
        return "C"
    return "D"


def _fecha_verificada(documento: Documento) -> bool:
    """El día del inicio lo escribe una fuente, lo da una autoridad o un parte, lo mide el
    tráfico aéreo (exportacion/mejor_origen.py) o lo confirma un cierre medido con cobertura
    alta que empieza ese mismo día."""
    origen = documento["tiempo"].get("origen_inicio", {}).get("tipo")
    if origen in fechas.VERIFICADOS or origen == "medido":
        return True
    cierre = documento.get("trafico_aereo", {}).get("cierre", {})
    inicio_medido = cierre.get("inicio", {}).get("valor", "")
    return (
        _cierre_medido(documento, COBERTURA_B)
        and inicio_medido[:10] == documento["tiempo"]["inicio"]["valor"][:10]
    )


def _con_valores(datos: Any) -> bool:
    """Algún valor medido: Open-Meteo deja vacío (null) lo que no da."""
    return isinstance(datos, dict) and any(v is not None for v in datos.values())


def indicadores(documento: Documento) -> Documento:
    """Lo que tiene el incidente, por separado del nivel (comun#/$defs/indicadores)."""
    medido = documento.get("trafico_aereo", {})
    condiciones = documento.get("condiciones", {})
    lugar = condiciones.get("lugar", {}) if isinstance(condiciones, dict) else {}
    gnss = medido.get("interferencia_gnss", {})
    niveles_gnss = {gnss.get(z, {}).get("nivel") for z in ("propia", "vecinas")}
    confirmado = documento["estado"]["actual"] in CONFIRMADOS
    return {
        "tiene_cierre_medido": _cierre_medido(documento),
        "tiene_condiciones_medidas": _con_valores(lugar.get("superficie"))
        or "metar" in lugar
        or any(_con_valores(n) for n in lugar.get("niveles", {}).values()),
        "tiene_respuesta_militar_observada": (
            medido.get("respuesta_militar", {}).get("resultado") == "vistas"
        ),
        "tiene_interferencia_gnss_medida": (
            gnss.get("resultado") == "medida" and bool(niveles_gnss & {"media", "alta"})
        ),
        "tiene_foco_termico": documento.get("foco_termico", {}).get("resultado") == "detectado",
        "tiene_confirmacion_oficial_directa": confirmado
        and any(confirma(f) for f in documento["fuentes"]),
        "fecha_del_suceso_verificada": _fecha_verificada(documento),
    }


def procedencia_deduccion(deduccion: Documento) -> Documento:
    """Lo que deduce el motor de deducción: origen deducido, método regla, con su versión. Va
    aparte de lo medido y de lo oficial y no cuenta para el nivel de detalle."""
    return {
        "origen": DEDUCIDO, "metodo": REGLA, "fuentes": [],
        "regla": {"nombre": "motor_deduccion", "version": deduccion["version_motor"]},
    }  # fmt: skip


def _sin_deduccion(documento: Documento) -> tuple[Documento, Documento | None]:
    deduccion = documento.get("deduccion")
    if deduccion is None:
        return documento, None
    return {k: v for k, v in documento.items() if k != "deduccion"}, deduccion


def _con_deduccion(exportado: Documento, deduccion: Documento | None) -> Documento:
    if deduccion is None:
        return exportado
    procedencia = {**exportado["procedencia"], "deduccion": procedencia_deduccion(deduccion)}
    return {**exportado, "deduccion": deduccion, "procedencia": dict(sorted(procedencia.items()))}


def exportar_incidente(
    documento: Documento, fichas: Fichas, contexto: "mejor_origen.Contexto | None" = None
) -> Documento:
    documento, deduccion = _sin_deduccion(documento)
    exportado, procedencia = procedencia_incidente(documento, fichas)
    # Valor a valor, el de mejor origen que hay en la base (medido, oficial, registro).
    mejor_origen.aplicar(exportado, procedencia, contexto or mejor_origen.Contexto(),
                         origen_de_fuente)  # fmt: skip
    procedencia = dict(sorted(procedencia.items()))
    exportado["procedencia"] = procedencia
    # El nivel de detalle no cambia por tener deducción: se calcula sin ella.
    exportado["nivel_detalle"] = nivel_detalle(exportado, procedencia)
    exportado["indicadores"] = indicadores(exportado)
    return _con_deduccion(exportado, deduccion)


# --- Capa de Ucrania -----------------------------------------------------------------

# El cruce con las anomalías térmicas de NASA FIRMS: dato de satélite.
FOCO_TERMICO: Documento = {"origen": MEDIDO, "metodo": PARSER, "fuentes": []}

# Valores que calcula el código a partir de otros del mismo ataque.
REGLAS_ATAQUE: dict[str, tuple[str, ...]] = {
    "proporcion_senuelos": ("lanzados",),
    "duracion_oleada_min": ("periodo", "horas_llegada"),
    "incluido_en": ("periodo",),
    "solapado_con": ("periodo",),
}


def procedencia_ataque(documento: Documento) -> Documento:
    """Cada valor del ataque sale del parte (parser) de las fuentes que lo respaldan; el estado
    y los valores derivados, de una regla."""
    fuentes = {f["id"]: f for f in documento["fuentes"]}
    origen = {id_: origen_de_fuente(f) for id_, f in fuentes.items()}
    procedencia: Documento = {}
    rutas = [r for r in documento if r not in META_ATAQUE]
    for ruta in rutas:
        if ruta in REGLAS_ATAQUE:
            continue
        if ruta == "estado":
            actual = documento["estado"]["actual"]
            ids = {p["fuente_id"] for p in documento["estado"]["historial"]
                   if p["estado"] == actual and p["fuente_id"] in fuentes}  # fmt: skip
            metodo = REGLA
        else:
            ids = {f for f, d in fuentes.items() if _respaldan(d, ruta)} or set(fuentes)
            metodo = PARSER
        if ruta == "foco_termico":
            procedencia[ruta] = dict(FOCO_TERMICO)
            continue
        procedencia[ruta] = {"origen": mejor(origen[f] for f in ids), "metodo": metodo,
                             "fuentes": sorted(ids)}  # fmt: skip
    for ruta in rutas:
        if ruta in REGLAS_ATAQUE:
            entradas = [procedencia[e] for e in REGLAS_ATAQUE[ruta] if e in procedencia]
            if not entradas:
                entradas = [{"origen": mejor(origen.values()), "fuentes": sorted(fuentes)}]
            procedencia[ruta] = {
                "origen": mejor(e["origen"] for e in entradas), "metodo": REGLA,
                "fuentes": sorted({f for e in entradas for f in e["fuentes"]}),
            }  # fmt: skip
    if any("foco_termico" in r for r in documento.get("regiones", [])):
        procedencia["regiones.foco_termico"] = FOCO_TERMICO
    if any(p["origen"] is None for p in procedencia.values()):
        raise SinOrigen(f"{documento['id']}: valor sin origen")
    return dict(sorted(procedencia.items()))


def procedencia_region(region: Documento, del_ataque: Documento) -> Documento:
    """La de los datos de la región (los del campo regiones del ataque) y, si lo hay, la del
    foco térmico, que es medido."""
    resultado = dict(del_ataque["regiones"])
    if "foco_termico" in region:
        resultado["foco_termico"] = FOCO_TERMICO
    return resultado


def exportar_ataque(documento: Documento) -> Documento:
    documento, deduccion = _sin_deduccion(documento)
    return _con_deduccion({**documento, "procedencia": procedencia_ataque(documento)}, deduccion)


# --- Capa de guerra con lugar ----------------------------------------------------------

META_IMPACTO = frozenset({
    "id", "tipo", "fuentes", "lecturas", "control", "procedencia", "fusionado_en", "retirado",
    "deduccion",
})  # fmt: skip
# Valores que calcula el código: el enlace con el ataque, la región (la del lugar), la
# credibilidad y la marca de reivindicación (de las fuentes y el foco).
REGLAS_IMPACTO = frozenset({
    "ataque", "enlace_ataque", "region", "credibilidad", "reivindicacion_de_parte", "sentido",
})  # fmt: skip


def procedencia_impacto(documento: Documento) -> Documento:
    """Cada valor del impacto: de las fuentes que lo respaldan, leído por el código (parser) o
    por el extractor (con su confianza); los que calcula el código, por regla; el foco térmico,
    medido. La credibilidad con foco detectado sale también de un dato medido."""
    fuentes = {f["id"]: f for f in documento["fuentes"]}
    origen = {id_: origen_de_fuente(f) for id_, f in fuentes.items()}
    lecturas = {x["fuente_id"]: x for x in documento.get("lecturas", [])}
    procedencia: Documento = {}
    for ruta in (r for r in documento if r not in META_IMPACTO):
        if ruta == "foco_termico":
            procedencia[ruta] = dict(FOCO_TERMICO)
            continue
        ids = {f for f, d in fuentes.items() if ruta in d.get("campos_respaldados", [])}
        ids = ids or set(fuentes)
        if ruta in REGLAS_IMPACTO:
            origenes = [origen[f] for f in ids]
            detectado = documento.get("foco_termico", {}).get("resultado") == "detectado"
            if ruta in {"credibilidad", "reivindicacion_de_parte"} and detectado:
                origenes.append(MEDIDO)
            procedencia[ruta] = {"origen": mejor(origenes), "metodo": REGLA,
                                 "fuentes": sorted(ids)}  # fmt: skip
            continue
        metodos = {lecturas.get(f, {}).get("metodo", PARSER) for f in ids}
        entrada: Documento = {
            "origen": mejor(origen[f] for f in ids),
            "metodo": PARSER if PARSER in metodos else EXTRACTOR,
            "fuentes": sorted(ids),
        }
        confianzas = [lecturas[f]["confianza"] for f in ids if "confianza" in lecturas.get(f, {})]
        if entrada["metodo"] == EXTRACTOR and confianzas:
            entrada["confianza"] = max(confianzas)
        procedencia[ruta] = entrada
    if any(p["origen"] is None for p in procedencia.values()):
        raise SinOrigen(f"{documento['id']}: valor sin origen")
    return dict(sorted(procedencia.items()))


def exportar_impacto(documento: Documento) -> Documento:
    documento, deduccion = _sin_deduccion(documento)
    return _con_deduccion({**documento, "procedencia": procedencia_impacto(documento)}, deduccion)


# Rosaviatsia, agencia federal: lo que anuncia es oficial; el enlace con el ataque, regla.
def procedencia_restriccion(documento: Documento) -> Documento:
    fuentes = sorted({documento["fuente_inicio"], documento.get("fuente_fin", "")} - {""})
    procedencia: Documento = {}
    for ruta in ("aeropuerto", "inicio", "fin", "horas", "emparejado", "ataque"):
        if ruta not in documento:
            continue
        metodo = REGLA if ruta in {"horas", "emparejado", "ataque"} else PARSER
        procedencia[ruta] = {"origen": OFICIAL, "metodo": metodo, "fuentes": fuentes}
    if "lugar_id" in documento["aeropuerto"]:
        procedencia["aeropuerto.lugar_id"] = {"origen": OFICIAL, "metodo": REGLA,
                                              "fuentes": fuentes}  # fmt: skip
    return procedencia


def exportar_restriccion(documento: Documento) -> Documento:
    return {**documento, "procedencia": procedencia_restriccion(documento)}


# --- Afirmaciones --------------------------------------------------------------------


def exportar_afirmacion(
    afirmacion: Documento, entidad: str, fuente: Documento, fichas: Fichas, extractor: bool
) -> Documento:
    """La afirmación con su origen y su método. La del extractor sin respaldo no lleva su
    valor: «sin_respaldo», con la confianza. Las medidas (tráfico aéreo) ya traen los suyos."""
    if afirmacion.get("origen") == MEDIDO and afirmacion.get("metodo") == REGLA:
        return dict(afirmacion)
    resultado = {**afirmacion, "origen": origen_de_fuente(fuente)}
    if not extractor or fuente.get("metodo"):
        resultado["metodo"] = metodo_de_fuente(fuente)
        return resultado
    if de_regla(afirmacion):
        resultado["metodo"] = REGLA
        return resultado
    falta = (
        sin_respaldo(afirmacion, entidad, fichas) if not entidad.startswith("EODI-UA-") else None
    )
    if falta is not None and falta["motivo"] == "sin_frase" and de_reconstruccion(afirmacion):
        resultado["metodo"] = REGLA
        return resultado
    resultado["metodo"] = EXTRACTOR
    if falta is not None:
        resultado["valor"] = "sin_respaldo"
        resultado["sin_respaldo"] = falta
    return resultado
