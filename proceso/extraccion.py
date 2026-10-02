"""Extracción de incidentes desde los candidatos de noticias.

Una llamada por candidato nuevo, o por candidato que recibe artículos nuevos
cuando su última ficha dejó sin saber un dato esencial (la hora, el cierre o
el número de drones), con un tope de llamadas por candidato. Al modelo solo
van el titular y las primeras frases de como mucho tres fuentes; la página se
lee en memoria y no se guarda.

El lugar del incidente es el del suceso que describe la ficha, situado con el
nomenclátor, el vocabulario de lugares y, como último recurso, el GKG
(`proceso/ubicacion.py`); el objetivo del candidato solo es donde casó un nombre
del titular. Vocabularios que crecen con el uso: un lugar nuevo que propone la
ficha, validado y usado como lugar del suceso, amplía el vocabulario. Igual con
los modelos de dron.

Una ficha nueva que ya no es publicable, o cuyo lugar no vale, retira el
incidente que tuviera el candidato: deja de publicarse, sin borrarse.

Cada llamada anota sus tokens y su coste; los límites de gasto son duros.

Las llamadas directas se paran en el límite de gasto y en el primer error del
servicio: lo que no se llama queda pendiente para la ejecución siguiente.
"""

import contextlib
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
from proceso import declaraciones, detalle
from proceso.estados import Estado, TransicionNoPermitida, transitar
from proceso.incidentes import aplicar_reglas, construir, huella
from proceso.noticias import (
    GKG,
    TIPO_APARENTE,
    Nomenclator,
    configuracion,
    lugar,
    lugares_en,
    nomenclator,
    normalizar,
)
from proceso.ubicacion import (
    Objetivo,
    Pistas,
    Ubicacion,
    afinar,
    nombres_en_idiomas,
    pais_del_suceso,
    ubicar,
)
from proceso.validacion_ficha import (
    MIN_LETRAS_PALABRA,
    Contexto,
    Validada,
    otro_objetivo,
    recuperar_inicio,
    revalidar,
    validar,
)
from proceso.validaciones import errores_ubicacion as validar_incidente_ubicacion
from recogida.descarga import Descargador
from recogida.plazo import Plazo, TiempoAgotado

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
# El motivo de una retirada es para leerlo en la base: basta con su comienzo.
MAX_LETRAS_MOTIVO = 500
# Fuentes oficiales que confirman un incidente (recogida/oficiales.py): se conservan al
# rehacerlo, porque sus notas solo se leen mientras siguen en la portada del organismo.
FIABILIDAD_OFICIAL = "A"


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


def _ampliar_modelos(almacen: Almacen, validada: Validada) -> None:
    """Añade el modelo de dron al vocabulario, o usa la grafía que ya tenía."""
    modelo = validada.valor("modelo_dron")
    if modelo:
        # Primero el vocabulario: un modelo ya visto con otra grafía se reutiliza.
        conocidos = {clave(m): m for m in almacen.vocabulario(VOCABULARIO_MODELOS)}
        canonico = conocidos.get(clave(modelo), modelo.strip())
        almacen.ampliar_vocabulario(VOCABULARIO_MODELOS, canonico, {"nombre": canonico})
        validada.campos["modelo_dron"] = {**validada.campos["modelo_dron"], "valor": canonico}


def _ampliar_lugares(almacen: Almacen, ubicacion: Ubicacion) -> None:
    """Un lugar nuevo de la ficha, ya situado dentro de su país, amplía el vocabulario."""
    if ubicacion.origen == "lugar_nuevo" and ubicacion.sitio is not None:
        sitio = ubicacion.sitio
        id_ = sitio.id[:MAX_ID_LOTE]
        almacen.ampliar_vocabulario(VOCABULARIO_LUGARES, id_, {**sitio.__dict__, "id": id_})


def nombres_objetivo(id_lugar: str, objetivo: Objetivo) -> tuple[str, ...]:
    """Los nombres del objetivo del candidato: los del nomenclátor o el del vocabulario."""
    sitio = nomenclator().lugares.get(id_lugar)
    if sitio is None:
        return (objetivo.nombre,)
    return (sitio.nombre, *sitio.alias, *sitio.ciudades)


def pistas(almacen: Almacen, peticion: Peticion) -> Pistas:
    id_lugar = peticion.candidato["lugar"]
    return Pistas(
        lugar_candidato=id_lugar,
        objetivo_candidato=peticion.objetivo,
        nombres_candidato=nombres_objetivo(id_lugar, peticion.objetivo),
        vocabulario=almacen.vocabulario(VOCABULARIO_LUGARES),
        genericos=prefijos_genericos(),
    )


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


def publicaciones(articulos: list[Documento], enviadas: list[str]) -> tuple[datetime, ...]:
    """La hora de publicación de cada fuente enviada, en su orden (la del primer artículo si
    una ya no está entre los del candidato)."""
    por_url = {a["url"]: datetime.fromisoformat(a["fecha"]) for a in articulos}
    primera = min(por_url.values(), default=datetime.now(UTC))
    return tuple(por_url.get(url, primera) for url in enviadas)


# Titulares del candidato que nombran a la vez su objetivo y el que da la ficha para que el
# suceso cuente también en el suyo («Brussels, Liege airports closed for hours due to drones»).
MIN_TITULARES_COMPARTIDOS = 2
MAX_PALABRAS_FRASE = 25


def _nombra(titular: str, nombres: set[str]) -> bool:
    texto = f" {normalizar(titular)} "
    return any(f" {n} " in texto for n in nombres)


def objetivo_compartido(
    validada: Validada, id_lugar: str, articulos: list[Documento], enviadas: list[str]
) -> bool:
    """Un incidente por objetivo: si los titulares del candidato nombran a la vez su
    instalación y otra del mismo país («cierran los aeropuertos de Bruselas y Lieja») y la
    ficha sitúa el suceso en la otra, el de este candidato es el de su instalación; el de la
    otra lo da su propio candidato. True si cambia el lugar del suceso."""
    nom = nomenclator()
    propio = nom.lugares.get(id_lugar)
    suceso = validada.valor("lugar_suceso")
    if (
        propio is None
        or propio.tipo not in TIPO_APARENTE
        or not suceso
        or suceso.get("nivel") != "instalacion"
        or validada.valor("objetivo_conocido") is not False
    ):
        return False
    otros = [i for i in lugares_en(str(suceso["nombre"]), nom) if i != id_lugar]
    if len(otros) != 1 or nom.lugares[otros[0]].pais != propio.pais:
        return False
    nombres_propio, nombres_otro = (
        nombres_en_idiomas(id_lugar, nom),
        nombres_en_idiomas(otros[0], nom),
    )
    ambos = [
        a for a in articulos
        if _nombra(str(a["titular"]), nombres_propio) and _nombra(str(a["titular"]), nombres_otro)
    ]  # fmt: skip
    if len(ambos) < MIN_TITULARES_COMPARTIDOS:
        return False
    enviada = next((a for a in ambos if a["url"] in enviadas), None)
    fuente = enviadas.index(enviada["url"]) + 1 if enviada else 1
    frase = " ".join(str((enviada or ambos[0])["titular"]).split()[:MAX_PALABRAS_FRASE])
    validada.campos["lugar_suceso"] = {
        "valor": {"nombre": propio.nombre, "nivel": "instalacion", "pais": propio.pais,
                  "region": ""},
        "fuente": fuente, "frase": frase, "confianza": 1.0,
    }  # fmt: skip
    validada.campos["objetivo_conocido"] = {
        "valor": True, "fuente": fuente, "frase": frase, "confianza": 1.0,
    }  # fmt: skip
    for campo in ("objetivo_nombre", "objetivo_categoria"):
        validada.campos.pop(campo, None)
    validada.motivos.append(
        f"lugar_suceso: {len(ambos)} titulares nombran {propio.nombre} junto a "
        f"{nom.lugares[otros[0]].nombre}: un incidente por objetivo"
    )
    return True


def completar_pais(
    validada: Validada, ficha_bruta: dict[str, Any], textos: tuple[str, ...]
) -> None:
    """Si la ficha no da un país válido, el que se deduce sin ambigüedad del lugar del suceso
    que describe (proceso/ubicacion.pais_del_suceso). Nunca el país del medio."""
    if validada.pais is not None:
        return
    deducido = pais_del_suceso(ficha_bruta, textos, prefijos_genericos(), nomenclator())
    if deducido is None:
        return
    pais, nombre_campo, campo = deducido
    validada.campos["pais"] = {**campo, "valor": pais}
    if nombre_campo == "lugar_suceso":
        validada.campos["lugar_suceso"] = {**campo, "valor": {**campo["valor"], "pais": pais}}
    else:
        validada.campos.setdefault(nombre_campo, campo)
    validada.motivos.append(f"pais: deducido de {nombre_campo}")


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
            publicaciones=publicaciones(peticion.articulos, peticion.enviadas),
        )
        validada = validar(leida, contexto)
        completar_pais(validada, leida, contexto.textos)
        objetivo_compartido(
            validada, peticion.candidato["lugar"], peticion.articulos, peticion.enviadas
        )
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
    if incidente_id is None:
        motivo = "; ".join(documento["motivos"]) or "no es un incidente"
        retirar_del_candidato(almacen, peticion.candidato["id"], motivo, ahora, modelos_base)
    documento["incidente"] = incidente_id
    almacen.guardar_extraccion(
        peticion.candidato["id"], _fecha(ahora), ficha.VERSION, peticion.huella,
        incidente_id is not None, documento,
    )  # fmt: skip
    return incidente_id


def incidente_del_candidato(
    almacen: Almacen, candidato_id: str, vinculos: dict[str, str] | None = None
) -> str | None:
    """El incidente del candidato: el último que dio de alta una de sus fichas o, si se hizo
    al reconstruir, el que lleva el candidato en su control. Con `vinculos` (una
    reconstrucción entera), se busca ahí."""
    if vinculos is not None:
        return vinculos.get(candidato_id)
    anteriores = [e["incidente"] for e in almacen.extracciones(candidato_id)]
    extraido = next((i for i in reversed(anteriores) if i), None)
    if extraido is not None:
        return str(extraido)
    return next(
        (
            str(i["id"])
            for i in almacen.incidentes()
            if i["control"].get("candidato") == candidato_id
        ),
        None,
    )


def de_noticias(incidente: Documento) -> bool:
    """Incidente hecho con una ficha del extractor (no con los partes de Ucrania)."""
    return str(incidente["control"].get("version_extractor", "")).startswith("ficha/")


def vincular(almacen: Almacen) -> dict[str, str]:
    """Para cada candidato, su incidente: el de sus extracciones, el que lo lleva en su
    control o, para los hechos al reconstruir antes de que se anotara, el de número más bajo
    que contiene todos sus artículos. Así una reconstrucción reutiliza el identificador en
    vez de numerar otro: los enlaces por incidente siguen valiendo."""
    vinculos: dict[str, str] = {}
    candidatos = almacen.candidatos()
    for candidato in candidatos:
        anteriores = [e["incidente"] for e in almacen.extracciones(candidato["id"])]
        extraido = next((i for i in reversed(anteriores) if i), None)
        if extraido is not None:
            vinculos[candidato["id"]] = extraido
    incidentes = [i for i in almacen.incidentes() if de_noticias(i)]
    for incidente in incidentes:
        candidato_id = incidente["control"].get("candidato")
        if candidato_id and candidato_id not in vinculos:
            vinculos[candidato_id] = incidente["id"]
    reclamados = set(vinculos.values())
    por_enlace: dict[str, set[str]] = {}
    for incidente in incidentes:
        for fuente in incidente["fuentes"]:
            por_enlace.setdefault(fuente["enlace"], set()).add(incidente["id"])
    for candidato in candidatos:
        if candidato["id"] in vinculos:
            continue
        conjuntos = [por_enlace.get(url, set()) for url in candidato["articulos"]]
        comunes = set.intersection(*conjuntos) - reclamados if conjuntos else set()
        if comunes:
            vinculos[candidato["id"]] = min(comunes)
            reclamados.add(min(comunes))
    return vinculos


def retirar(
    almacen: Almacen, id_: str, motivo: str, ahora: datetime, modelos_base: frozenset[str]
) -> bool:
    """Deja de publicar el incidente, sin borrarlo. True si estaba publicado."""
    incidente = almacen.incidente(id_)
    if incidente is None or "retirado" in incidente:
        return False
    documento = {k: v for k, v in incidente.items() if k not in {"episodio", "fusionado_en"}}
    documento["retirado"] = {
        "fecha": {"valor": ahora.strftime("%Y-%m-%dT%H:%MZ"), "precision": "minuto"},
        "motivo": motivo[:MAX_LETRAS_MOTIVO],
    }
    if validar_incidente_ubicacion(documento):
        # Un punto que no vale no se guarda ni siquiera en un incidente retirado.
        documento["lugar"] = {
            k: v for k, v in documento["lugar"].items() if k not in {"punto", "radio_km"}
        }
    almacen.guardar_incidente(documento, ahora, modelos_validos(almacen, modelos_base))
    return True


def retirar_del_candidato(
    almacen: Almacen,
    candidato_id: str,
    motivo: str,
    ahora: datetime,
    modelos_base: frozenset[str],
    vinculos: dict[str, str] | None = None,
) -> bool:
    id_ = incidente_del_candidato(almacen, candidato_id, vinculos)
    return id_ is not None and retirar(almacen, id_, motivo, ahora, modelos_base)


def conservar_oficiales(incidente: Documento, anterior: Documento) -> Documento:
    """El incidente rehecho con las fuentes oficiales que confirmaban el anterior."""
    ids = {f["id"] for f in incidente["fuentes"]}
    oficiales = [
        f for f in anterior["fuentes"]
        if f["fiabilidad"] == FIABILIDAD_OFICIAL and f.get("es_autoridad") and f["id"] not in ids
    ]  # fmt: skip
    if not oficiales:
        return incidente
    resultado = {**incidente, "fuentes": [*incidente["fuentes"], *oficiales]}
    for fuente in oficiales:
        if resultado["estado"]["actual"] == Estado.CONFIRMADO:
            break
        # Un desmentido de una autoridad más fiable no se revierte con esta nota.
        with contextlib.suppress(TransicionNoPermitida):
            resultado["estado"] = transitar(
                resultado["estado"], Estado.CONFIRMADO, fuente["fecha"], fuente["id"],
                {f["id"]: f for f in resultado["fuentes"]},
            )  # fmt: skip
    return resultado


def _alta(
    almacen: Almacen,
    peticion: Peticion,
    validada: Validada,
    ahora: datetime,
    modelos_base: frozenset[str],
    documento: Documento,
    rehacer: bool = False,
    vinculos: dict[str, str] | None = None,
) -> str | None:
    """Da de alta o rehace el incidente del candidato. Con `rehacer`, el incidente no
    conserva su fusión ni su episodio: se vuelven a calcular después."""
    _ampliar_modelos(almacen, validada)
    ubicacion = ubicar(validada, pistas(almacen, peticion), nomenclator())
    if ubicacion.valida and ubicacion.sitio is None:
        # Un suceso que solo se sitúa en una región gana el punto del único sitio de esa
        # región que nombran sus frases y los titulares de su candidato.
        textos = tuple(
            [str(c.get("frase") or "") for c in validada.campos.values()]
            + [str(a["titular"]) for a in peticion.articulos]
        )
        ubicacion = afinar(ubicacion, textos, nomenclator())
    if not ubicacion.valida:
        documento["motivos"] = [*documento["motivos"], f"ubicación: {ubicacion.motivo}"]
        return None
    existente = incidente_del_candidato(almacen, peticion.candidato["id"], vinculos)
    inicio = validada.valor("inicio") or peticion.candidato["inicio"]
    id_ = existente or almacen.siguiente_id_incidente(int(inicio[:4]))
    if vinculos is not None:
        vinculos[peticion.candidato["id"]] = id_
    modelos = modelos_validos(almacen, modelos_base)
    incidente = construir(
        id_, ubicacion, peticion.candidato, peticion.articulos, peticion.enviadas, validada,
        ahora, ficha.VERSION, modelos,
    )  # fmt: skip
    anterior = almacen.incidente(id_)
    if anterior is not None:
        # Se conservan el alta y, salvo al rehacer, la fusión y el episodio.
        incidente["control"]["alta"] = anterior["control"]["alta"]
        for campo in () if rehacer else ("fusionado_en", "episodio"):
            if campo in anterior:
                incidente[campo] = anterior[campo]
    incidente = declaraciones.aplicar(
        incidente, documento.get("declaraciones", []), peticion.enviadas
    )
    if anterior is not None:
        incidente = conservar_oficiales(incidente, anterior)
        # Lo que aportan los registros oficiales de detalle vuelve entero (proceso/detalle.py).
        incidente = detalle.reaplicar(almacen, incidente)
    incidente = aplicar_reglas(incidente)
    try:
        almacen.guardar_incidente(incidente, ahora, modelos)
    except DocumentoInvalido as error:
        documento["motivos"] = [*documento["motivos"], f"incidente no válido: {error}"]
        return None
    _ampliar_lugares(almacen, ubicacion)
    return id_


def reconstruir(
    almacen: Almacen, ahora: datetime, modelos_base: frozenset[str], rehacer: bool = False
) -> int:
    """Rehace los incidentes desde las fichas ya validadas y guardadas, sin llamar al modelo.

    Sirve cuando cambian los candidatos (por ejemplo, al ampliar el nomenclátor y volver
    a incorporar las noticias) o las reglas: cada candidato con una ficha publicable
    recupera su incidente, con el mismo identificador si ya lo tenía; el de un candidato
    cuya última ficha ya no es publicable se retira. Las comprobaciones que solo necesitan
    la frase (el cierre, el lugar del suceso) se repiten con las reglas de ahora. Con
    `rehacer`, fusiones y episodios se vuelven a calcular después. Devuelve cuántos rehace.
    """
    rehechos = 0
    vinculos = vincular(almacen)
    for candidato in almacen.candidatos():
        # La última ficha legible: una respuesta que no traía ficha no deshace la anterior.
        legibles = [e for e in almacen.extracciones(candidato["id"]) if "ficha" in e]
        if not legibles:
            continue
        ultima = legibles[-1]
        peticion = preparar(almacen, candidato, None)
        enviadas = ultima.get("enviadas") or peticion.enviadas
        campos = {
            nombre: campo
            for nombre, campo in ultima["campos"].items()
            if isinstance(campo.get("fuente"), int) and 1 <= campo["fuente"] <= len(enviadas)
        }
        # De las fuentes solo se guardan los titulares: son el texto con que se comprueba
        # que la fuente nombra el país.
        titulares = tuple(
            str(a["titular"]) for a in peticion.articulos if a["url"] in set(enviadas)
        )
        validada = revalidar(
            Validada(
                campos=campos,
                motivos=[],
                titulo_es=str(ultima["ficha"].get("titulo_es", "")),
                titulo_en=str(ultima["ficha"].get("titulo_en", "")),
            ),
            ultima["ficha"],
            titulares,
            prefijos_genericos(),
        )
        completar_pais(validada, ultima["ficha"], titulares)
        recuperar_inicio(
            validada, ultima["ficha"], list(ultima.get("motivos", [])),
            publicaciones(peticion.articulos, list(enviadas)), ahora,
        )  # fmt: skip
        objetivo_compartido(validada, candidato["lugar"], peticion.articulos, list(enviadas))
        nombre = validada.valor("objetivo_nombre")
        contexto = Contexto(
            textos=(), pais_objetivo=peticion.objetivo.pais, primer_articulo=ahora, ahora=ahora,
            palabras_objetivo=palabras_objetivo(candidato["lugar"]),
            prefijos_genericos=prefijos_genericos(),
        )  # fmt: skip
        if validada.valor("objetivo_conocido") is not False and otro_objetivo(nombre, contexto):
            validada.campos["objetivo_conocido"] = {
                **validada.campos.get("objetivo_conocido", {"fuente": 1, "frase": "",
                                                            "confianza": 1.0}),
                "valor": False,
            }  # fmt: skip
        if not validada.publicable:
            retirar_del_candidato(
                almacen, candidato["id"], "ficha no publicable con las reglas actuales", ahora,
                modelos_base, vinculos,
            )  # fmt: skip
            continue
        peticion = replace(peticion, enviadas=list(enviadas))
        guardadas = {"motivos": [], "declaraciones": ultima.get("declaraciones", [])}
        if _alta(almacen, peticion, validada, ahora, modelos_base, guardadas, rehacer, vinculos):
            rehechos += 1
        else:
            retirar_del_candidato(
                almacen, candidato["id"], "; ".join(guardadas["motivos"]), ahora, modelos_base,
                vinculos,
            )  # fmt: skip
    if rehacer:
        # Los incidentes de noticias que ya no son de ningún candidato son copias numeradas
        # de más por reconstrucciones anteriores: se retiran, sin borrarse.
        propios = set(vinculos.values())
        todos = almacen.incidentes()
        enlaces = {i["id"]: {f["enlace"] for f in i["fuentes"]} for i in todos}
        for incidente in todos:
            if de_noticias(incidente) and incidente["id"] not in propios:
                original = min(
                    (p for p in propios if enlaces.get(p, set()) & enlaces[incidente["id"]]),
                    default=None,
                )
                motivo = f"copia de {original}" if original else "sin candidato"
                retirar(almacen, incidente["id"], f"{motivo}: numerada de más al reconstruir",
                        ahora, modelos_base)  # fmt: skip
    return rehechos


# --- Llamadas -----------------------------------------------------------------------


class Parada(StrEnum):
    """Por qué una tanda de llamadas directas deja peticiones sin hacer."""

    LIMITE_GASTO = "límite de gasto"
    TIEMPO = "tope de tiempo"
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
    plazo: Plazo | None = None,
) -> Extraidas:
    """Una llamada directa por petición hasta la primera parada.

    Se para en el límite de gasto, al agotar el plazo y en el primer error del servicio:
    si está caído o rechaza las peticiones, insistir con los demás candidatos solo alarga
    la ejecución.
    """
    hechas = Extraidas()
    for peticion in peticiones:
        gastado = almacen.gastado(
            modo.value, coste.dia(ahora) if modo is coste.Modo.HORARIO else None
        )
        previsto = coste.peor_caso(peticion.letras(), ficha.MAX_TOKENS_SALIDA)
        try:
            if plazo is not None:
                plazo.comprobar()
            coste.comprobar(gastado, previsto, modo)
            respuesta = cliente.mensaje(peticion.cuerpo())
        except TiempoAgotado as error:
            return hechas.parar(Parada.TIEMPO, error)
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
    almacen: Almacen, peticiones: list[Peticion], modo: coste.Modo = coste.Modo.HISTORICO
) -> tuple[list[Peticion], float]:
    """Las peticiones que caben en lo que queda del límite del modo, en el peor caso."""
    queda = coste.limite(modo) - almacen.gastado(modo.value)
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
    modo: coste.Modo = coste.Modo.HISTORICO,
) -> dict[str, int]:
    """Envía las peticiones que caben en el límite como un lote y procesa los resultados."""
    elegidas, previsto = recortar_para_lote(almacen, peticiones, modo)
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
    recuentos = procesar_lote(almacen, cliente, lote, elegidas, ahora, modelos_base, modo)
    recuentos["fuera_de_limite"] = len(peticiones) - len(elegidas)
    return recuentos


def procesar_lote(
    almacen: Almacen,
    cliente: ServicioLotes,
    lote: dict[str, Any],
    peticiones: list[Peticion],
    ahora: Callable[[], datetime],
    modelos_base: frozenset[str],
    modo: coste.Modo = coste.Modo.HISTORICO,
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
            almacen, peticion, mensaje, ahora(), modo, True, modelos_base
        )
        procesadas += 1
        publicadas += incidente is not None
    return {"enviadas": procesadas + fallidas, "publicadas": publicadas, "fallidas": fallidas}
