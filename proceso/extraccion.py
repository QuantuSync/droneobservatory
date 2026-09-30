"""Extracción de incidentes desde los candidatos de noticias.

Una llamada por candidato nuevo, o por candidato que recibe artículos nuevos
cuando su última ficha dejó sin saber un dato esencial (la hora, el cierre o
el número de drones), con un tope de llamadas por candidato. Al modelo solo
van el titular y las primeras frases de como mucho tres fuentes; la página se
lee en memoria y no se guarda.

Vocabularios que crecen con el uso: el objetivo sale primero del nomenclátor
y del vocabulario de lugares; el modelo solo propone un lugar nuevo si la
noticia habla de otro sitio, y ese lugar, ya validado, amplía el vocabulario.
Igual con los modelos de dron.

Cada llamada anota sus tokens y su coste; los límites de gasto son duros.

Las llamadas directas se paran en el límite de gasto y en el primer error del
servicio: lo que no se llama queda pendiente para la ejecución siguiente.
"""

import hashlib
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from functools import cache
from typing import Any, Protocol

from almacen.base import Almacen, DocumentoInvalido
from esquema import Documento
from modelo import coste, ficha, paginas
from modelo.cliente import ErrorTemporal, LlamadaFallida
from proceso import declaraciones
from proceso.incidentes import Objetivo, construir, huella
from proceso.noticias import (
    GKG,
    TIPO_APARENTE,
    Nomenclator,
    configuracion,
    lugar,
    nomenclator,
    normalizar,
)
from proceso.validacion_ficha import (
    MIN_LETRAS_PALABRA,
    Contexto,
    Validada,
    otro_objetivo,
    validar,
)
from recogida.descarga import Descargador
from recogida.lugares_osm import RADIO_KM

registro = logging.getLogger(__name__)

MAX_FUENTES = 3
# Una ficha que deja datos esenciales sin saber se repite con artículos nuevos, como
# mucho tres veces por candidato: así un candidato que crece sin dar datos no gasta sin fin.
MAX_LLAMADAS_POR_CANDIDATO = 3
ESENCIALES = ("inicio", "cierre", "drones")
# Un lote termina casi siempre en menos de una hora y como mucho en 24.
ESPERA_LOTE_S = 60.0
MAX_ESPERA_LOTE = timedelta(hours=24)
VOCABULARIO_LUGARES = "lugar"
VOCABULARIO_MODELOS = "modelo_dron"
# Las peticiones de un lote se identifican con caracteres simples y 64 como mucho.
MAX_ID_LOTE = 64
# Categoría del objetivo a tipo de lugar del nomenclátor, para el radio.
TIPO_LUGAR = {"aeropuerto": "aeropuerto", "base_militar": "base", "energia": "nuclear"}


class Servicio(Protocol):
    def mensaje(self, cuerpo: dict[str, Any]) -> dict[str, Any]: ...


class ServicioLotes(Protocol):
    def crear_lote(self, peticiones: list[dict[str, Any]]) -> dict[str, Any]: ...

    def lote(self, id_: str) -> dict[str, Any]: ...

    def resultados_lote(self, lote: dict[str, Any]) -> list[dict[str, Any]]: ...


@dataclass(frozen=True)
class Peticion:
    candidato: Documento
    objetivo: Objetivo
    articulos: list[Documento]
    enviadas: list[str]
    fuentes: list[ficha.FuenteTexto]
    huella: str

    @property
    def id_lote(self) -> str:
        return hashlib.sha256(self.candidato["id"].encode()).hexdigest()[:MAX_ID_LOTE]

    def cuerpo(self) -> dict[str, Any]:
        return ficha.cuerpo(descripcion_objetivo(self.objetivo), self.fuentes)

    def letras(self) -> int:
        return (
            len(ficha.INSTRUCCIONES)
            + len(ficha.contenido("", self.fuentes))
            + len(str(ficha.ESQUEMA))
        )


def descripcion_objetivo(objetivo: Objetivo) -> str:
    oaci = f", {objetivo.oaci}" if objetivo.oaci else ""
    return f"{objetivo.nombre} ({objetivo.categoria}, {objetivo.pais}{oaci})"


# --- Qué candidatos -----------------------------------------------------------------


def _articulos(almacen: Almacen, candidato: Documento) -> list[Documento]:
    return almacen.articulos_de(candidato["articulos"])


def necesita_extraccion(almacen: Almacen, candidato: Documento) -> bool:
    anteriores = almacen.extracciones(candidato["id"])
    if not anteriores:
        return True
    if len(anteriores) >= MAX_LLAMADAS_POR_CANDIDATO:
        return False
    ultima = anteriores[-1]
    if ultima["huella"] == huella(candidato["articulos"]):
        return False
    campos = ultima.get("campos", {})
    sin_hora = campos.get("inicio_precision", {}).get("valor") not in {"minuto", "hora"}
    return sin_hora or any(c not in campos for c in ESENCIALES)


def desactualizado(almacen: Almacen, candidato: Documento) -> bool:
    """Candidato con incidente cuya última ficha es de una versión anterior del extractor."""
    anteriores = almacen.extracciones(candidato["id"])
    if not anteriores:
        return False
    ultima = anteriores[-1]
    return ultima["version"] != ficha.VERSION and bool(ultima.get("incidente"))


def elegir_fuentes(articulos: list[Documento]) -> list[Documento]:
    """El primer artículo y después los más replicados de otros medios, hasta tres."""
    ordenados = sorted(articulos, key=lambda a: (a["fecha"], a["url"]))
    elegidos = ordenados[:1]
    medios = {a["medio"] for a in elegidos}
    for articulo in sorted(ordenados[1:], key=lambda a: (-a.get("replicas", 0), a["fecha"])):
        if len(elegidos) == MAX_FUENTES:
            break
        if articulo["medio"] not in medios:
            elegidos.append(articulo)
            medios.add(articulo["medio"])
    return elegidos


def objetivo_de(almacen: Almacen, candidato: Documento, nom: Nomenclator) -> Objetivo:
    if candidato["lugar"] in nom.lugares or candidato["lugar"].startswith(GKG + ":"):
        return Objetivo.de_lugar(lugar(candidato["lugar"], nom))
    vocabulario = almacen.vocabulario(VOCABULARIO_LUGARES)
    return Objetivo(**vocabulario[candidato["lugar"]])


def preparar(
    almacen: Almacen,
    candidato: Documento,
    descargador: Descargador | None,
    nom: Nomenclator | None = None,
) -> Peticion:
    """Fuentes elegidas con su titular y, si se puede descargar, sus primeras frases."""
    articulos = [a for a in _articulos(almacen, candidato) if a.get("idioma")]
    elegidas = elegir_fuentes(articulos)
    fuentes = [
        ficha.FuenteTexto(
            medio=a["medio"],
            fecha=a["fecha"],
            idioma=a.get("idioma"),
            titular=a["titular"],
            texto=paginas.leer(descargador, a["url"]) if descargador else "",
        )
        for a in elegidas
    ]
    return Peticion(
        candidato=candidato,
        objetivo=objetivo_de(almacen, candidato, nom or nomenclator()),
        articulos=articulos,
        enviadas=[a["url"] for a in elegidas],
        fuentes=fuentes,
        huella=huella(candidato["articulos"]),
    )


# --- Respuesta ----------------------------------------------------------------------


def _fecha(momento: datetime) -> str:
    return momento.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def clave(texto: str) -> str:
    return normalizar(texto).replace(" ", "_")


def modelos_validos(almacen: Almacen, base: frozenset[str]) -> frozenset[str]:
    return base | frozenset(almacen.vocabulario(VOCABULARIO_MODELOS))


def _ampliar_vocabularios(almacen: Almacen, validada: Validada) -> Objetivo | None:
    """Añade el lugar nuevo y el modelo de dron; devuelve el objetivo nuevo si lo hay."""
    modelo = validada.valor("modelo_dron")
    if modelo:
        # Primero el vocabulario: un modelo ya visto con otra grafía se reutiliza.
        conocidos = {clave(m): m for m in almacen.vocabulario(VOCABULARIO_MODELOS)}
        canonico = conocidos.get(clave(modelo), modelo.strip())
        almacen.ampliar_vocabulario(VOCABULARIO_MODELOS, canonico, {"nombre": canonico})
        validada.campos["modelo_dron"] = {**validada.campos["modelo_dron"], "valor": canonico}
    nuevo = validada.valor("lugar_nuevo")
    if validada.valor("objetivo_conocido") is not False or not nuevo:
        return None
    id_ = f"{nuevo['pais']}-{clave(nuevo['nombre'])}"[:MAX_ID_LOTE]
    objetivo = Objetivo(
        id=id_,
        categoria=nuevo["categoria"],
        nombre=nuevo["nombre"].strip(),
        pais=nuevo["pais"],
        lat=round(float(nuevo["lat"]), 5),
        lon=round(float(nuevo["lon"]), 5),
        # El radio que da el nomenclátor a su tipo de lugar; a lo demás, el de una base.
        radio_km=RADIO_KM.get(TIPO_LUGAR.get(nuevo["categoria"], "base"), RADIO_KM["base"]),
    )
    almacen.ampliar_vocabulario(VOCABULARIO_LUGARES, id_, objetivo.__dict__)
    return objetivo


@cache
def prefijos_genericos() -> tuple[str, ...]:
    """Palabras de tipo de lugar y de señal («airport», «flughafen», «base»), normalizadas."""
    config = configuracion()
    listas = [*config["tipo_de_lugar"].values(), *config["senales"].values()]
    return tuple(sorted({normalizar(p) for lista in listas for p in lista if normalizar(p)}))


def palabras_objetivo(id_lugar: str) -> frozenset[str]:
    """Palabras propias de los nombres de la instalación; vacío si no es una instalación."""
    sitio = nomenclator().lugares.get(id_lugar)
    if sitio is None or sitio.tipo not in TIPO_APARENTE:
        return frozenset()
    genericos = prefijos_genericos()
    return frozenset(
        p
        for nombre in (sitio.nombre, *sitio.alias, *sitio.ciudades)
        for p in normalizar(nombre).split()
        if len(p) >= MIN_LETRAS_PALABRA and not p.startswith(genericos)
    )


def procesar_respuesta(
    almacen: Almacen,
    peticion: Peticion,
    respuesta: dict[str, Any],
    ahora: datetime,
    modo: coste.Modo,
    lote: bool,
    modelos_base: frozenset[str],
) -> str | None:
    """Anota el coste, valida la ficha y da de alta o actualiza el incidente.

    Devuelve el identificador del incidente, o None si la ficha no se publica.
    """
    uso = coste.Uso.de_respuesta(respuesta.get("usage", {}))
    almacen.registrar_llamada({
        "fecha": _fecha(ahora), "modo": modo.value, "candidato": peticion.candidato["id"],
        "lote": lote, "entrada": uso.entrada, "salida": uso.salida,
        "escritura_cache": uso.escritura_cache, "lectura_cache": uso.lectura_cache,
        "coste": uso.coste(lote),
    })  # fmt: skip
    documento: Documento = {"motivos": [], "campos": {}}
    incidente_id: str | None = None
    try:
        leida = ficha.leer_respuesta(respuesta)
    except ficha.RespuestaInvalida as error:
        documento["motivos"] = [str(error)]
    else:
        contexto = Contexto(
            textos=tuple(f"{f.titular}. {f.texto}" for f in peticion.fuentes),
            pais_objetivo=peticion.objetivo.pais,
            primer_articulo=min(datetime.fromisoformat(a["fecha"]) for a in peticion.articulos),
            ahora=ahora,
            palabras_objetivo=palabras_objetivo(peticion.candidato["lugar"]),
            prefijos_genericos=prefijos_genericos(),
        )
        validada = validar(leida, contexto)
        # La ficha en bruto se guarda para poder revalidarla sin volver a llamar.
        documento = {
            "motivos": validada.motivos,
            "campos": validada.campos,
            "ficha": leida,
            "enviadas": peticion.enviadas,
            "declaraciones": declaraciones.validas(leida["declaraciones"], contexto.textos),
        }
        if validada.publicable:
            incidente_id = _alta(almacen, peticion, validada, ahora, modelos_base, documento)
    documento["incidente"] = incidente_id
    almacen.guardar_extraccion(
        peticion.candidato["id"], _fecha(ahora), ficha.VERSION, peticion.huella,
        incidente_id is not None, documento,
    )  # fmt: skip
    return incidente_id


def _alta(
    almacen: Almacen,
    peticion: Peticion,
    validada: Validada,
    ahora: datetime,
    modelos_base: frozenset[str],
    documento: Documento,
) -> str | None:
    objetivo = _ampliar_vocabularios(almacen, validada) or peticion.objetivo
    anteriores = [e["incidente"] for e in almacen.extracciones(peticion.candidato["id"])]
    existente = next((i for i in reversed(anteriores) if i), None)
    inicio = validada.valor("inicio") or peticion.candidato["inicio"]
    id_ = existente or almacen.siguiente_id_incidente(int(inicio[:4]))
    modelos = modelos_validos(almacen, modelos_base)
    incidente = construir(
        id_, objetivo, peticion.candidato, peticion.articulos, peticion.enviadas, validada,
        ahora, ficha.VERSION, modelos,
    )  # fmt: skip
    anterior = almacen.incidente(id_)
    if anterior is not None:
        # Se conservan el alta, la fusión y el episodio que ya tuviera.
        incidente["control"]["alta"] = anterior["control"]["alta"]
        for campo in ("fusionado_en", "episodio"):
            if campo in anterior:
                incidente[campo] = anterior[campo]
    incidente = declaraciones.aplicar(
        incidente, documento.get("declaraciones", []), peticion.enviadas
    )
    try:
        almacen.guardar_incidente(incidente, ahora, modelos)
    except DocumentoInvalido as error:
        documento["motivos"] = [*documento["motivos"], f"incidente no válido: {error}"]
        return None
    return id_


def reconstruir(almacen: Almacen, ahora: datetime, modelos_base: frozenset[str]) -> int:
    """Rehace los incidentes desde las fichas ya validadas y guardadas, sin llamar al modelo.

    Sirve cuando cambian los candidatos (por ejemplo, al ampliar el nomenclátor y volver
    a incorporar las noticias): cada candidato con una ficha publicable recupera su
    incidente, con el mismo identificador si ya lo tenía. Devuelve cuántos rehace.
    """
    rehechos = 0
    for candidato in almacen.candidatos():
        extracciones = almacen.extracciones(candidato["id"])
        if not extracciones or "ficha" not in extracciones[-1]:
            continue
        ultima = extracciones[-1]
        peticion = preparar(almacen, candidato, None)
        enviadas = ultima.get("enviadas") or peticion.enviadas
        campos = {
            nombre: campo
            for nombre, campo in ultima["campos"].items()
            if isinstance(campo.get("fuente"), int) and 1 <= campo["fuente"] <= len(enviadas)
        }
        validada = Validada(
            campos=campos,
            motivos=[],
            titulo_es=str(ultima["ficha"].get("titulo_es", "")),
            titulo_en=str(ultima["ficha"].get("titulo_en", "")),
        )
        # Las comprobaciones del objetivo también valen para fichas anteriores a ellas.
        if any(m.startswith("pais: distinto") for m in ultima.get("motivos", [])):
            continue
        nombre = validada.valor("objetivo_nombre")
        contexto = Contexto(
            textos=(), pais_objetivo=peticion.objetivo.pais, primer_articulo=ahora, ahora=ahora,
            palabras_objetivo=palabras_objetivo(candidato["lugar"]),
            prefijos_genericos=prefijos_genericos(),
        )  # fmt: skip
        if validada.valor("objetivo_conocido") is not False and otro_objetivo(nombre, contexto):
            continue
        if not validada.publicable:
            continue
        peticion = replace(peticion, enviadas=list(enviadas))
        guardadas = {"motivos": [], "declaraciones": ultima.get("declaraciones", [])}
        if _alta(almacen, peticion, validada, ahora, modelos_base, guardadas):
            rehechos += 1
    return rehechos


# --- Llamadas -----------------------------------------------------------------------


class Parada(StrEnum):
    """Por qué una tanda de llamadas directas deja peticiones sin hacer."""

    LIMITE_GASTO = "límite de gasto"
    # Error temporal que sigue tras el reintento del cliente.
    SERVICIO_CAIDO = "servicio caído"
    # Error que no se arregla solo: petición o clave inválidas, saldo agotado.
    ERROR = "error del servicio"


@dataclass
class Extraidas:
    """Una tanda de llamadas directas: lo que dio cada una y por qué se paró, si se paró."""

    # Por cada llamada hecha, el incidente que dio de alta o actualizó, o None.
    incidentes: list[str | None] = field(default_factory=list)
    parada: Parada | None = None
    motivo: str = ""

    def parar(self, parada: Parada, error: Exception) -> "Extraidas":
        self.parada, self.motivo = parada, str(error)
        return self


def extraer(
    almacen: Almacen,
    cliente: Servicio,
    peticiones: list[Peticion],
    ahora: datetime,
    modo: coste.Modo,
    modelos_base: frozenset[str],
) -> Extraidas:
    """Una llamada directa por petición hasta la primera parada.

    Se para en el límite de gasto y en el primer error del servicio: si está caído o
    rechaza las peticiones, insistir con los demás candidatos solo alarga la ejecución.
    """
    hechas = Extraidas()
    for peticion in peticiones:
        gastado = almacen.gastado(
            modo.value, coste.dia(ahora) if modo is coste.Modo.HORARIO else None
        )
        previsto = coste.peor_caso(peticion.letras(), ficha.MAX_TOKENS_SALIDA)
        try:
            coste.comprobar(gastado, previsto, modo)
            respuesta = cliente.mensaje(peticion.cuerpo())
        except coste.LimiteGasto as error:
            return hechas.parar(Parada.LIMITE_GASTO, error)
        except ErrorTemporal as error:
            return hechas.parar(Parada.SERVICIO_CAIDO, error)
        except LlamadaFallida as error:
            return hechas.parar(Parada.ERROR, error)
        hechas.incidentes.append(
            procesar_respuesta(almacen, peticion, respuesta, ahora, modo, False, modelos_base)
        )
    return hechas


def recortar_para_lote(
    almacen: Almacen, peticiones: list[Peticion]
) -> tuple[list[Peticion], float]:
    """Las peticiones que caben en lo que queda del límite del histórico, en el peor caso."""
    queda = coste.LIMITE_HISTORICO_USD - almacen.gastado(coste.Modo.HISTORICO.value)
    elegidas: list[Peticion] = []
    previsto = 0.0
    for peticion in peticiones:
        caso = coste.peor_caso(peticion.letras(), ficha.MAX_TOKENS_SALIDA, lote=True)
        if previsto + caso > queda:
            break
        elegidas.append(peticion)
        previsto += caso
    return elegidas, previsto


def extraer_lote(
    almacen: Almacen,
    cliente: ServicioLotes,
    peticiones: list[Peticion],
    ahora: Callable[[], datetime],
    modelos_base: frozenset[str],
    dormir: Callable[[float], None] = time.sleep,
) -> dict[str, int]:
    """Envía las peticiones que caben en el límite como un lote y procesa los resultados."""
    elegidas, previsto = recortar_para_lote(almacen, peticiones)
    if not elegidas:
        return {"enviadas": 0, "publicadas": 0, "fallidas": 0, "fuera_de_limite": len(peticiones)}
    registro.info("lote: %d peticiones, peor caso %.4f USD", len(elegidas), previsto)
    lote = cliente.crear_lote([{"custom_id": p.id_lote, "params": p.cuerpo()} for p in elegidas])
    # El identificador va al registro: si algo falla después, el lote se recupera sin pagarlo
    # otra vez (el servicio guarda los resultados 29 días).
    registro.info("lote %s enviado", lote["id"])
    inicio = ahora()
    while lote.get("processing_status") != "ended":
        if ahora() - inicio > MAX_ESPERA_LOTE:
            raise LlamadaFallida("el lote no terminó en 24 horas")
        dormir(ESPERA_LOTE_S)
        lote = cliente.lote(lote["id"])
    recuentos = procesar_lote(almacen, cliente, lote, elegidas, ahora, modelos_base)
    recuentos["fuera_de_limite"] = len(peticiones) - len(elegidas)
    return recuentos


def procesar_lote(
    almacen: Almacen,
    cliente: ServicioLotes,
    lote: dict[str, Any],
    peticiones: list[Peticion],
    ahora: Callable[[], datetime],
    modelos_base: frozenset[str],
) -> dict[str, int]:
    """Procesa los resultados de un lote terminado con las peticiones que lo formaron."""
    por_id = {p.id_lote: p for p in peticiones}
    publicadas = fallidas = procesadas = 0
    for resultado in cliente.resultados_lote(lote):
        peticion = por_id.get(resultado.get("custom_id", ""))
        if peticion is None or resultado.get("result", {}).get("type") != "succeeded":
            fallidas += 1
            continue
        mensaje = resultado["result"]["message"]
        incidente = procesar_respuesta(
            almacen, peticion, mensaje, ahora(), coste.Modo.HISTORICO, True, modelos_base
        )
        procesadas += 1
        publicadas += incidente is not None
    return {"enviadas": procesadas + fallidas, "publicadas": publicadas, "fallidas": fallidas}
