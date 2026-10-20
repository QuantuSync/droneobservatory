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

Un candidato que falla por sí solo (una excepción al prepararlo o al procesar su respuesta,
una respuesta del servicio que no se entiende) se aparta: se anota en el cursor
`candidatos_apartados` con su motivo y los demás de la hora siguen. Tras fallar en tres
recogidas distintas se retira con su motivo y no vuelve a intentarse. Los que no tienen ningún
artículo en un idioma reconocido también se anotan ahí y no se llaman mientras sigan así.

Dos modelos (docs/modelos.md): la ficha la hace el modelo base y, si las reglas de
proceso/escalado.py lo piden, se repite con el experto y vale la suya. Las llamadas al experto
cuentan solo contra su propio tope (modelo/coste.py), nunca contra el del modo. Si el experto ha
agotado su tope del día (o no responde), el candidato espera (cursor `esperan_experto`) en vez de
publicarse con la ficha del base; los demás siguen. Si el único motivo es una autoridad que habla
en la noticia sin declaración en la ficha (escalado.opcionales) y el tope está agotado, vale la
ficha del base y no espera. Un caso crítico (escalado.es_critico) usa
antes la reserva crítica y, si también se agotó, se reintenta en cada recogida; el que no es
crítico y espera por el tope vuelve al día siguiente (UTC), o antes si el tope sube; el que espera
por un fallo, en la recogida siguiente. Cada ficha guarda qué modelo la decidió y la extracción,
por qué se escaló.

Nada publicado se retira ni se rebaja sin el experto: una ficha del base que retiraría o
rebajaría la ficha ya publicada de su candidato se escala siempre y, si llega sin el experto (un
lote, o una retirada que solo se ve al validar), no se aplica: la publicada se queda como estaba,
la extracción se guarda aparte (`ficha_base`, que una reconstrucción no lee) y el candidato
vuelve a extraerse con el experto (cursor `esperan_experto`, con `revision`).
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
from modelo import coste, ficha, modelos, paginas
from modelo.cliente import ErrorTemporal, LlamadaFallida
from proceso import declaraciones, detalle, escalado, no_es_suceso, presencia
from proceso.estados import Estado, TransicionNoPermitida, transitar
from proceso.incidentes import activo, aplicar_reglas, construir, huella
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
# El cursor de los artículos dirigidos (recogida/articulos_dirigidos.FUENTE_ID).
CURSOR_DIRIGIDOS = "articulos_dirigidos"
VOCABULARIO_LUGARES = "lugar"
VOCABULARIO_MODELOS = "modelo_dron"
# Las peticiones de un lote se identifican con caracteres simples y 64 como mucho.
MAX_ID_LOTE = 64
# El motivo de una retirada es para leerlo en la base: basta con su comienzo.
MAX_LETRAS_MOTIVO = 500
# Fuentes oficiales que confirman un incidente (recogida/oficiales.py): se conservan al
# rehacerlo, porque sus notas solo se leen mientras siguen en la portada del organismo.
FIABILIDAD_OFICIAL = "A"
# Candidatos que fallan por sí solos (cursor de la base): fallos por recogida y retirada.
APARTADOS = "candidatos_apartados"
MAX_FALLOS_CANDIDATO = 3
SIN_IDIOMA = "sin artículos en un idioma reconocido"
# Candidatos que esperan al modelo experto: {candidato: {"hasta": instante, "motivos": [...]}}.
ESPERAN_EXPERTO = "esperan_experto"
# Tras un fallo del experto, se reintenta en la recogida siguiente.
ESPERA_FALLO_EXPERTO = timedelta(minutes=50)
# Motivo que anota escalar cuando el experto se paga con un cupo propio («cupo: <modo>»).
PREFIJO_CUPO = "cupo"
# Las reglas «publicada» y «senal» (docs/modelos.md) llegaron el 15 de octubre de 2026: una sola
# vez, las decisiones del base desde que entró en producción se repasan con ellas.
REVISION_REGLAS = "revision_reglas_experto"
ENTRADA_MODELO_BASE = "2026-10-14T13:42:00Z"
# La regla de los descartes dudosos (escalado.descarte_dudoso) llegó el 20 de octubre de 2026: una
# sola vez, los descartes del base desde el 13 de octubre se repasan con ella.
REVISION_DUDOSOS = "revision_descartes_dudosos"
DESDE_DUDOSOS = "2026-10-13T00:00:00Z"


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


# --- Candidatos apartados -----------------------------------------------------------


def apartados(almacen: Almacen) -> dict[str, Any]:
    documento = almacen.cursor(APARTADOS) or {}
    return documento if isinstance(documento, dict) else {}


def retirados(almacen: Almacen) -> set[str]:
    """Candidatos que no se vuelven a intentar: retirados tras sus fallos."""
    return {id_ for id_, d in apartados(almacen).items() if d.get("retirado")}


def anotar_fallo(almacen: Almacen, candidato_id: str, motivo: str, ahora: datetime) -> bool:
    """Anota que el candidato falló en esta recogida. True si con este queda retirado.

    Varios fallos en la misma recogida cuentan como uno: se retira tras fallar en
    MAX_FALLOS_CANDIDATO recogidas distintas.
    """
    documento = apartados(almacen)
    entrada = documento.setdefault(candidato_id, {"fallos": []})
    entrada.setdefault("fallos", [])
    fecha = _fecha(ahora)
    if any(f.get("fecha") == fecha for f in entrada["fallos"]):
        return False
    entrada["fallos"].append({"fecha": fecha, "motivo": motivo[:MAX_LETRAS_MOTIVO]})
    retirado = len(entrada["fallos"]) >= MAX_FALLOS_CANDIDATO and not entrada.get("retirado")
    if retirado:
        entrada["retirado"] = fecha
        entrada["motivo"] = (
            f"retirado tras fallar en {len(entrada['fallos'])} recogidas distintas; el último: "
            + motivo[:MAX_LETRAS_MOTIVO]
        )
        registro.warning("candidato %s retirado: %s", candidato_id, entrada["motivo"])
    else:
        registro.warning(
            "candidato %s apartado en esta recogida (fallo %d de %d): %s",
            candidato_id, len(entrada["fallos"]), MAX_FALLOS_CANDIDATO, motivo[:300],
        )  # fmt: skip
    almacen.guardar_cursor(APARTADOS, documento)
    return retirado


def anotar_sin_idioma(almacen: Almacen, ids: list[str], ahora: datetime) -> None:
    """Candidatos sin ningún artículo en un idioma reconocido: no se llaman mientras sigan así
    (si les llega uno, vuelven solos)."""
    documento = apartados(almacen)
    nuevos = [i for i in ids if not documento.get(i, {}).get("sin_idioma")]
    if not nuevos:
        return
    for id_ in nuevos:
        entrada = documento.setdefault(id_, {"fallos": []})
        entrada.update({"sin_idioma": _fecha(ahora), "motivo": SIN_IDIOMA})
    almacen.guardar_cursor(APARTADOS, documento)


def esperan_experto(almacen: Almacen) -> dict[str, Any]:
    documento = almacen.cursor(ESPERAN_EXPERTO) or {}
    return documento if isinstance(documento, dict) else {}


def espera_experto(almacen: Almacen, candidato_id: str, ahora: datetime) -> bool:
    """El candidato espera al experto en este momento (no se llama)."""
    entrada = esperan_experto(almacen).get(candidato_id)
    return isinstance(entrada, dict) and not coste.espera_vencida(
        str(entrada.get("hasta", "")), _fecha(ahora), entrada.get("tope")
    )


def anotar_espera(
    almacen: Almacen, candidato_id: str, motivos: list[str], ahora: datetime, por_tope: bool,
    revision: bool = False, critico: bool = False, cupo: str | None = None,
) -> None:  # fmt: skip
    """El candidato espera al experto: si se agotó su tope, hasta el día siguiente (UTC), o hasta
    la recogida siguiente si es crítico (se agotó también la reserva); si falló, hasta la
    recogida siguiente. Con `revision`, se vuelve a extraer aunque sus artículos no hayan cambiado
    y se escala siempre, con esos motivos. Con `cupo` (un modo con cupo propio del experto,
    coste.Modo.SEGUNDA_BUSQUEDA), la llamada al experto se paga con ese cupo y no con su tope."""
    documento = esperan_experto(almacen)
    if por_tope:
        hasta = coste.espera_experto(ahora, critico)
    else:
        hasta = _fecha(ahora + ESPERA_FALLO_EXPERTO)
    anterior = documento.get(candidato_id, {})
    documento[candidato_id] = {
        "hasta": hasta, "desde": anterior.get("desde", _fecha(ahora)),
        "motivos": motivos[:10], "por": "tope" if por_tope else "fallo",
        "tope": coste.LIMITE_EXPERTO_DIARIO_USD,
    }  # fmt: skip
    if critico or anterior.get("critico"):
        documento[candidato_id]["critico"] = True
    if revision or anterior.get("revision"):
        documento[candidato_id]["revision"] = True
    if cupo or anterior.get("cupo"):
        documento[candidato_id]["cupo"] = cupo or anterior["cupo"]
    registro.info("candidato %s espera al experto hasta %s: %s", candidato_id, hasta,
                  "; ".join(motivos[:3]))  # fmt: skip
    almacen.guardar_cursor(ESPERAN_EXPERTO, documento)


def quitar_espera(almacen: Almacen, candidato_id: str) -> None:
    documento = esperan_experto(almacen)
    if candidato_id in documento:
        documento.pop(candidato_id)
        almacen.guardar_cursor(ESPERAN_EXPERTO, documento)


def revisar_decisiones_base(
    almacen: Almacen, descargador: Descargador | None, ahora: datetime,
    desde: str = ENTRADA_MODELO_BASE,
) -> list[str]:  # fmt: skip
    """Una sola vez (cursor `revision_reglas_experto`): la última ficha de cada candidato que el
    base dio por «no es incidente» desde `desde`, sin escalar, se vuelve a mirar con las reglas de
    escalado de ahora y con el texto de sus fuentes; si alguna pide el experto, el candidato se
    repite con él (`esperan_experto` con `revision`). Devuelve los marcados."""
    if almacen.cursor(REVISION_REGLAS) is not None:
        return []
    candidatos = {c["id"]: c for c in almacen.candidatos()}
    marcados: dict[str, list[str]] = {}
    for candidato_id in almacen.candidatos_extraidos_desde(desde):
        candidato = candidatos.get(candidato_id)
        anteriores = almacen.extracciones(candidato_id)
        ultima = anteriores[-1] if anteriores else {}
        leida = ultima.get("ficha")
        if candidato is None or not leida or ultima.get("escalado"):
            continue
        if (leida.get("es_incidente") or {}).get("valor") is not False:
            continue
        peticion = preparar(almacen, candidato, descargador)
        motivos = escalado.motivos_ficha(leida, textos_de(peticion), con_fuente_oficial(peticion))
        if motivos:
            marcados[candidato_id] = motivos
            anotar_espera(almacen, candidato_id, motivos, ahora - ESPERA_FALLO_EXPERTO, False, True)
    almacen.guardar_cursor(REVISION_REGLAS, {
        "fecha": _fecha(ahora), "desde": desde, "marcados": marcados,
    })  # fmt: skip
    registro.info("revisión de las decisiones del base desde %s: %d al experto", desde,
                  len(marcados))  # fmt: skip
    return list(marcados)


def revisar_descartes_dudosos(
    almacen: Almacen, ahora: datetime, desde: str = DESDE_DUDOSOS
) -> list[str]:
    """Una sola vez (cursor `revision_descartes_dudosos`): la última ficha de cada candidato
    extraído desde `desde` que el base, sin el experto, no dio por incidente con poca seguridad
    en un dato clave (escalado.descarte_dudoso) y sin ficha publicada se repite con el experto
    por el camino normal (`esperan_experto` con `revision`), por orden de fecha. Devuelve los
    marcados."""
    if almacen.cursor(REVISION_DUDOSOS) is not None:
        return []
    candidatos = {c["id"] for c in almacen.candidatos()}
    elegidos: list[tuple[str, str, list[str]]] = []
    for candidato_id in almacen.candidatos_extraidos_desde(desde):
        anteriores = almacen.extracciones(candidato_id)
        ultima = anteriores[-1] if anteriores else {}
        leida = ultima.get("ficha")
        if candidato_id not in candidatos or not leida or ultima.get("escalado"):
            continue
        if ultima.get("incidente") or publicada_del_candidato(almacen, candidato_id) is not None:
            continue
        motivos = [m for m in escalado.motivos_ficha(leida, ()) if m.startswith("poca_seguridad")]
        if escalado.descarte_dudoso(motivos, leida):
            motivos.append(f"{escalado.MOTIVO_DUDOSO}: el base lo descartó con poca seguridad")
            elegidos.append((str(ultima.get("fecha", "")), candidato_id, motivos))
    for _, candidato_id, motivos in sorted(elegidos):
        anotar_espera(almacen, candidato_id, motivos, ahora - ESPERA_FALLO_EXPERTO, False, True)
    almacen.guardar_cursor(REVISION_DUDOSOS, {
        "fecha": _fecha(ahora), "desde": desde, "marcados": [c for _, c, _ in sorted(elegidos)],
    })  # fmt: skip
    registro.info("descartes dudosos desde %s: %d al experto", desde, len(elegidos))
    return [c for _, c, _ in sorted(elegidos)]


def en_revision(almacen: Almacen) -> set[str]:
    """Los candidatos que se repiten con el experto (`revision`)."""
    return {id_ for id_, e in esperan_experto(almacen).items() if e.get("revision")}


def con_idioma(almacen: Almacen, candidato: Documento) -> bool:
    return any(a.get("idioma") for a in _articulos(almacen, candidato))


def descripcion_objetivo(objetivo: Objetivo) -> str:
    oaci = f", {objetivo.oaci}" if objetivo.oaci else ""
    return f"{objetivo.nombre} ({objetivo.categoria}, {objetivo.pais}{oaci})"


# --- Qué candidatos -----------------------------------------------------------------


def _articulos(almacen: Almacen, candidato: Documento) -> list[Documento]:
    return almacen.articulos_de(candidato["articulos"])


def articulos_retirados(almacen: Almacen, candidato: Documento) -> bool:
    """La última ficha se hizo con artículos que el candidato ya no tiene (se separó en dos
    sucesos): ya no describe el candidato y hay que volver a extraerlo."""
    anteriores = almacen.extracciones(candidato["id"])
    if not anteriores:
        return False
    actuales = set(candidato["articulos"])
    return any(url not in actuales for url in anteriores[-1].get("enviadas") or [])


def necesita_extraccion(almacen: Almacen, candidato: Documento) -> bool:
    anteriores = almacen.extracciones(candidato["id"])
    if not anteriores:
        return True
    if esperan_experto(almacen).get(candidato["id"], {}).get("revision"):
        # Una ficha del base que no se aplicó sin el experto: se repite con él.
        return True
    if len(anteriores) >= MAX_LLAMADAS_POR_CANDIDATO:
        return False
    if articulos_retirados(almacen, candidato):
        return True
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


def elegir_fuentes(
    articulos: list[Documento], dirigidos: frozenset[str] = frozenset()
) -> list[Documento]:
    """El primer artículo y después los más replicados de otros medios, hasta tres. Un artículo
    dirigido (apuntado a mano porque trae lo que los demás no dicen) va siempre."""
    ordenados = sorted(articulos, key=lambda a: (a["fecha"], a["url"]))
    elegidos = [a for a in ordenados if a["url"] in dirigidos][: MAX_FUENTES - 1]
    elegidos += [a for a in ordenados[:1] if a not in elegidos]
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
    """Fuentes elegidas con su titular y, si se puede descargar, sus primeras frases y las
    marcas de su página (con lo que dicen de ella: proceso/no_es_suceso.py)."""
    articulos = [a for a in _articulos(almacen, candidato) if a.get("idioma")]
    # Los artículos dirigidos (recogida/articulos_dirigidos.py: su cursor, por dirección).
    dirigidos = almacen.cursor(CURSOR_DIRIGIDOS) or {}
    elegidas = elegir_fuentes(articulos, frozenset(dirigidos))
    fuentes = []
    for a in elegidas:
        pagina = paginas.leer_pagina(descargador, a["url"]) if descargador else paginas.Pagina("")
        texto = pagina.texto
        # La frase literal de la página que encontró la segunda lectura (una declaración más
        # abajo de las primeras frases): va delante para que la lea la extracción.
        pista = str((dirigidos.get(a["url"]) or {}).get("frase") or "")
        if pista and normalizar(pista) not in normalizar(texto):
            texto = f"{pista} … {texto}".strip(" …")
        fuentes.append(no_es_suceso.con_aviso(ficha.FuenteTexto(
            medio=a["medio"], fecha=a["fecha"], idioma=a.get("idioma"), titular=a["titular"],
            texto=texto, url=a["url"], marcas=pagina.marcas,
        )))  # fmt: skip
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
        # Un titular que enumera varias instalaciones del mismo tipo, entre ellas la del
        # candidato y no la de la ficha («Drones Observed by Airports in Esbjerg, Sonderborg,
        # Skrydstrup»), y ninguno que nombre las dos: el suceso del candidato es el suyo.
        enumeran = [
            a for a in articulos
            if _nombra(str(a["titular"]), nombres_propio)
            and not _nombra(str(a["titular"]), nombres_otro)
            and any(i != id_lugar and nom.lugares[i].tipo == propio.tipo
                    for i in lugares_en(str(a["titular"]), nom))
        ]  # fmt: skip
        if ambos or not enumeran:
            return False
        ambos = enumeran
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
        f"lugar_suceso: {len(ambos)} titulares nombran {propio.nombre} (con "
        f"{nom.lugares[otros[0]].nombre} o en una lista): un incidente por objetivo"
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
    escalado_por: list[str] | None = None,
) -> str | None:
    """Anota el coste, valida la ficha y da de alta o actualiza el incidente.

    Con `escalado_por`, la respuesta es la del experto y esos son los motivos del escalado.
    Devuelve el identificador del incidente, o None si la ficha no se publica.
    """
    anotar_llamada(almacen, peticion, respuesta, ahora, modo, lote, bool(escalado_por))
    documento: Documento = {"motivos": [], "campos": {}}
    incidente_id: str | None = None
    publicada = publicada_sin_experto(almacen, peticion, escalado_por)
    conservar: list[str] = []
    # Ninguna fuente cuenta un suceso (proceso/no_es_suceso.py). Si son contenido patrocinado o
    # de socio, la respuesta del base no crea ficha; la del experto decide.
    veredicto = no_es_suceso.de_fuentes(peticion.fuentes)
    descarte = (
        veredicto if veredicto is not None and veredicto.segura and not escalado_por else None
    )
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
        if respuesta.get("model"):
            documento["modelo"] = str(respuesta["model"])
        if escalado_por:
            documento["escalado"] = list(escalado_por)
        if veredicto is not None:
            documento["no_es_suceso"] = veredicto.documento()
        conservar = escalado.motivos_publicada(leida, publicada)
        if descarte is not None:
            documento["motivos"] = [*documento["motivos"], descarte.motivo_escalado()]
            if publicada is not None:
                conservar = [
                    f"publicada: {publicada['id']} retirada por «{descarte.motivo_escalado()}»",
                    *conservar,
                ]
        if validada.publicable and not conservar and descarte is None:
            incidente_id = _alta(almacen, peticion, validada, ahora, modelos_base, documento)
    if publicada is not None and (conservar or incidente_id is None):
        # Nada publicado se retira ni se rebaja sin el experto: la ficha publicada se queda como
        # estaba y el candidato se repite con él.
        conservar = conservar or [
            f"publicada: {publicada['id']} retirada: "
            + ("; ".join(documento["motivos"]) or "ficha no publicable")
        ]
        if "ficha" in documento:
            documento["ficha_base"] = documento.pop("ficha")
        documento["conservada"] = conservar
        incidente_id = publicada["id"]
        anotar_espera(almacen, peticion.candidato["id"], conservar, ahora, False, True, True)
        registro.warning("candidato %s: %s; se repite con el experto", peticion.candidato["id"],
                         "; ".join(conservar))  # fmt: skip
    if incidente_id is None and veredicto is not None:
        # Lo que no es un suceso se retira con su motivo en los dos idiomas.
        retirar_del_candidato(almacen, peticion.candidato["id"], veredicto.motivo(), ahora,
                              modelos_base, motivo_en=veredicto.motivo_en())  # fmt: skip
    elif incidente_id is None:
        motivo = "; ".join(documento["motivos"]) or "no es un incidente"
        retirar_del_candidato(almacen, peticion.candidato["id"], motivo, ahora, modelos_base)
    documento["incidente"] = incidente_id
    almacen.guardar_extraccion(
        peticion.candidato["id"], _fecha(ahora), ficha.VERSION, peticion.huella,
        incidente_id is not None, documento,
    )  # fmt: skip
    return incidente_id


def anotar_llamada(
    almacen: Almacen, peticion: Peticion, respuesta: dict[str, Any], ahora: datetime,
    modo: coste.Modo, lote: bool, escalada: bool = False,
) -> float:  # fmt: skip
    """Anota la llamada con su coste (a la tarifa del modelo que la hizo). Devuelve el coste."""
    uso = coste.Uso.de_mensaje(respuesta)
    gasto = uso.coste(lote)
    almacen.registrar_llamada({
        "fecha": _fecha(ahora), "modo": modo.value, "candidato": peticion.candidato["id"],
        "lote": lote, "entrada": uso.entrada, "salida": uso.salida,
        "escritura_cache": uso.escritura_cache, "lectura_cache": uso.lectura_cache,
        "coste": gasto, "modelo": uso.modelo, "escalada": escalada,
    })  # fmt: skip
    return gasto


class EsperaExperto(Exception):
    """La ficha necesita al experto y no puede ser ahora (tope del día o fallo)."""

    def __init__(
        self, motivos: list[str], por_tope: bool, detalle: str, critico: bool = False,
        revision: bool = False,
    ) -> None:  # fmt: skip
        super().__init__(detalle)
        self.motivos = motivos
        self.por_tope = por_tope
        self.critico = critico
        # Se repite con el experto aunque sus artículos no cambien (un descarte dudoso).
        self.revision = revision


def textos_de(peticion: Peticion) -> tuple[str, ...]:
    return tuple(f"{f.titular}. {f.texto}" for f in peticion.fuentes)


def con_fuente_oficial(peticion: Peticion) -> bool:
    enviadas = set(peticion.enviadas)
    return any(
        escalado.fuente_oficial(str(a.get("medio", "")), str(a.get("url", "")))
        for a in peticion.articulos if a.get("url") in enviadas
    )  # fmt: skip


def publicada_del_candidato(almacen: Almacen, candidato_id: str) -> Documento | None:
    """La ficha publicada (activa) del candidato, o None."""
    id_ = incidente_del_candidato(almacen, candidato_id)
    incidente = almacen.incidente(id_) if id_ else None
    return incidente if incidente is not None and activo(incidente) else None


def publicada_sin_experto(
    almacen: Almacen, peticion: Peticion, escalado_por: list[str] | None
) -> Documento | None:
    """La ficha publicada del candidato que una respuesta del base no puede retirar ni rebajar:
    solo con dos modelos y si la respuesta no es del experto."""
    if escalado_por or not modelos.experto():
        return None
    return publicada_del_candidato(almacen, peticion.candidato["id"])


def motivos_escalado(
    peticion: Peticion, respuesta: dict[str, Any], publicada: Documento | None = None
) -> list[str]:
    """Por qué la respuesta del base se escala (proceso/escalado.py); vacía si no se escala."""
    try:
        leida = ficha.leer_respuesta(respuesta)
    except ficha.RespuestaInvalida as error:
        return [f"respuesta_invalida: {error}"]
    return escalado.motivos_ficha(
        leida, textos_de(peticion), con_fuente_oficial(peticion), publicada
    )


def _leida(respuesta: dict[str, Any]) -> dict[str, Any] | None:
    """La ficha leída de una respuesta, o None si no se puede leer."""
    try:
        return ficha.leer_respuesta(respuesta)
    except ficha.RespuestaInvalida:
        return None


def _da_suceso(respuesta: dict[str, Any]) -> bool:
    """La respuesta da el candidato por incidente."""
    try:
        dato = ficha.leer_respuesta(respuesta).get("es_incidente")
    except ficha.RespuestaInvalida:
        return False
    return isinstance(dato, dict) and dato.get("valor") is True


def escalar(
    almacen: Almacen, cliente: Servicio, peticion: Peticion, respuesta: dict[str, Any],
    ahora: datetime, modo: coste.Modo,
) -> tuple[dict[str, Any], list[str] | None]:  # fmt: skip
    """La respuesta que vale y, si se escaló, los motivos.

    Si el cliente tiene experto y las reglas piden escalar, la llamada del base se anota aquí y
    se llama al experto dentro de su tope diario (o de la reserva crítica, si el caso es crítico),
    sin contar contra el tope del modo. Lanza EsperaExperto si no se puede ahora: el candidato
    espera y la ficha del base no se publica.
    """
    fabrica_experto = getattr(cliente, "experto", None)
    experto = fabrica_experto() if callable(fabrica_experto) else None
    if experto is None:
        return respuesta, None
    candidato_id = peticion.candidato["id"]
    publicada = publicada_del_candidato(almacen, candidato_id)
    motivos = motivos_escalado(peticion, respuesta, publicada)
    espera = esperan_experto(almacen).get(candidato_id, {})
    veredicto = no_es_suceso.de_fuentes(peticion.fuentes)
    if (
        veredicto is not None
        and veredicto.segura
        and publicada is None
        and not espera.get("revision")
    ):
        # Contenido patrocinado o de socio sin ficha publicada: no se crea, sin experto.
        return respuesta, None
    if veredicto is not None and (publicada is not None or _da_suceso(respuesta)):
        # La página dice que no es un suceso y el base cree que sí, o hay una ficha publicada en
        # juego: decide el experto.
        motivos.append(veredicto.motivo_escalado())
    if espera.get("revision"):
        # Una ficha del base que no se aplicó sin el experto: se escala siempre.
        motivos += [m for m in espera.get("motivos", []) if m not in motivos]
    if not escalado.escala(motivos):
        # Sin motivos, o solo la marca de caso crítico: vale el base.
        return respuesta, None
    modelo_experto = str(getattr(experto, "modelo", ""))
    previsto = coste.peor_caso(
        peticion.letras(), ficha.MAX_TOKENS_SALIDA, modelo=modelo_experto, esfuerzo=ficha.ESFUERZO
    )
    critico = bool(espera.get("critico")) or escalado.es_critico(
        motivos, textos_de(peticion), peticion.objetivo.pais, peticion.objetivo.categoria
    )
    gastado_hoy = almacen.gastado_modelo(modelo_experto, coste.dia(ahora))
    mes = coste.del_mes(almacen, ahora, modelo_experto)
    opcional = escalado.opcionales(motivos) and not espera.get("revision")
    cupo = espera.get("cupo")
    # Un descarte del base poco seguro no se queda sin el experto: espera (o, si nombra una
    # autoridad o una infraestructura del alcance, usa la reserva crítica).
    dudoso = (
        publicada is None
        and not cupo
        and (
            escalado.descarte_dudoso(motivos, _leida(respuesta))
            or any(str(m).startswith(escalado.MOTIVO_DUDOSO) for m in espera.get("motivos", []))
        )
    )
    if dudoso:
        if not any(m.startswith(escalado.MOTIVO_DUDOSO) for m in motivos):
            motivos.append(f"{escalado.MOTIVO_DUDOSO}: el base lo descarta con poca seguridad")
        pais_ficha = ((_leida(respuesta) or {}).get("pais") or {}).get("valor")
        paises = (peticion.objetivo.pais, str(pais_ficha or ""))
        critico = critico or escalado.dudoso_critico(
            textos_de(peticion), paises, con_fuente_oficial(peticion)
        )
    if cupo:
        # Lo que entrega la segunda lectura es una relectura de lo ya recogido (o una noticia de
        # días antes): nunca sale de la reserva crítica. El 20 de octubre de 2026, de 00:00 a
        # 06:30 UTC, cuatro entregas suyas la usaron por el texto de la noticia.
        critico = False
    try:
        if cupo:
            # Su propio cupo del día y su parte del mes (coste.Modo.SEGUNDA_BUSQUEDA): ni el tope
            # normal del experto, ni su ritmo, ni la reserva crítica.
            coste.comprobar_cupo(almacen.gastado_experto_en(cupo, coste.dia(ahora)), previsto,
                                 coste.Modo(cupo), coste.del_mes(almacen, ahora))  # fmt: skip
            tramo = coste.Tramo.NORMAL
            motivos = [*motivos, f"{PREFIJO_CUPO}: {cupo}"]
        elif opcional and not dudoso:
            # Poca seguridad o una autoridad citada sin declaración: el experto solo si le sobra
            # (al ritmo de su tope del día), nunca de la reserva.
            coste.comprobar_al_ritmo(gastado_hoy, previsto, ahora, mes)
            tramo = coste.Tramo.NORMAL
        else:
            tramo = coste.comprobar_experto(gastado_hoy, previsto, critico, mes)
    except coste.LimiteGasto as error:
        if dudoso:
            # Sin margen del experto, el descarte dudoso espera y se repite con él (revision);
            # los demás candidatos siguen.
            anotar_llamada(almacen, peticion, respuesta, ahora, modo, False)
            raise EsperaExperto(motivos, True, str(error), critico, revision=True) from error
        if opcional and not cupo:
            # Sin experto ahora, vale la ficha del base (procesar_respuesta anota su llamada).
            registro.info("candidato %s: sin experto ahora (%s), vale el base", candidato_id, error)
            return respuesta, None
        anotar_llamada(almacen, peticion, respuesta, ahora, modo, False)
        raise EsperaExperto(motivos, True, str(error), critico) from error
    anotar_llamada(almacen, peticion, respuesta, ahora, modo, False)
    if tramo is coste.Tramo.RESERVA:
        registro.info("candidato %s: el experto usa la reserva crítica", candidato_id)
    try:
        return experto.mensaje(peticion.cuerpo()), motivos
    except LlamadaFallida as error:
        raise EsperaExperto(motivos, False, str(error), critico) from error


def modo_de_la_respuesta(escalado_por: list[str] | None, modo: coste.Modo) -> coste.Modo:
    """El modo con que se anota la respuesta: el del cupo propio si la dio el experto con él
    (escalar lo anota en los motivos)."""
    for motivo in escalado_por or []:
        if motivo.startswith(f"{PREFIJO_CUPO}: "):
            return coste.Modo(motivo.removeprefix(f"{PREFIJO_CUPO}: "))
    return modo


def experto_sin_base(
    almacen: Almacen, cliente: Servicio, peticion: Peticion, ahora: datetime,
    error: coste.LimiteGasto,
) -> tuple[dict[str, Any], list[str]]:  # fmt: skip
    """Un caso crítico que esperaba al experto cuando el tope del modo ya no deja llamar al base:
    va directo al experto, con su tope o la reserva crítica (lo crítico no espera por los topes
    normales). Lanza EsperaExperto si tampoco cabe en la reserva o el experto falla, y el
    LimiteGasto del modo si no hay experto."""
    fabrica_experto = getattr(cliente, "experto", None)
    experto = fabrica_experto() if callable(fabrica_experto) else None
    if experto is None:
        raise error
    espera = esperan_experto(almacen).get(peticion.candidato["id"], {})
    motivos = [*espera.get("motivos", [])[:9], f"{escalado.CRITICO_SIN_BASE}: {error}"[:300]]
    modelo_experto = str(getattr(experto, "modelo", ""))
    previsto = coste.peor_caso(
        peticion.letras(), ficha.MAX_TOKENS_SALIDA, modelo=modelo_experto, esfuerzo=ficha.ESFUERZO
    )
    try:
        coste.comprobar_experto(
            almacen.gastado_modelo(modelo_experto, coste.dia(ahora)), previsto, True,
            coste.del_mes(almacen, ahora, modelo_experto),
        )  # fmt: skip
    except coste.LimiteGasto as tope:
        raise EsperaExperto(motivos, True, str(tope), True) from tope
    registro.info("candidato %s: crítico sin el base (%s), directo al experto",
                  peticion.candidato["id"], error)  # fmt: skip
    try:
        return experto.mensaje(peticion.cuerpo()), motivos
    except LlamadaFallida as fallo:
        raise EsperaExperto(motivos, False, str(fallo), True) from fallo


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
    almacen: Almacen, id_: str, motivo: str, ahora: datetime, modelos_base: frozenset[str],
    motivo_en: str = "",
) -> bool:  # fmt: skip
    """Deja de publicar el incidente, sin borrarlo. True si estaba publicado."""
    incidente = almacen.incidente(id_)
    if incidente is None or "retirado" in incidente:
        return False
    documento = {k: v for k, v in incidente.items() if k not in {"episodio", "fusionado_en"}}
    documento["retirado"] = {
        "fecha": {"valor": ahora.strftime("%Y-%m-%dT%H:%MZ"), "precision": "minuto"},
        "motivo": motivo[:MAX_LETRAS_MOTIVO],
    }
    if motivo_en:
        documento["retirado"]["motivo_en"] = motivo_en[:MAX_LETRAS_MOTIVO]
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
    motivo_en: str = "",
) -> bool:
    id_ = incidente_del_candidato(almacen, candidato_id, vinculos)
    return id_ is not None and retirar(almacen, id_, motivo, ahora, modelos_base, motivo_en)


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
    if documento.get("modelo"):
        # Qué modelo decidió cada dato de la ficha (docs/modelos.md); el control anota después
        # los que corrige con el suyo.
        incidente["control"]["modelos"] = dict.fromkeys(
            sorted(validada.campos), str(documento["modelo"])
        )
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
    # Criterio de presencia (un cierre por dron la confirma) y titular coherente con ella.
    incidente = presencia.aplicar(incidente)
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
        # Un dato de un artículo que el candidato ya no tiene (se separó) no vale para él: se
        # queda sin ese dato hasta que se vuelva a extraer.
        actuales = set(candidato["articulos"])
        campos = {
            nombre: campo
            for nombre, campo in ultima["campos"].items()
            if isinstance(campo.get("fuente"), int)
            and 1 <= campo["fuente"] <= len(enviadas)
            and enviadas[campo["fuente"] - 1] in actuales
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
        if ultima.get("modelo"):
            guardadas["modelo"] = ultima["modelo"]
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
    # Candidatos apartados por un fallo propio en esta tanda.
    apartados: list[str] = field(default_factory=list)
    # Candidatos que esperan al modelo experto (su ficha no se publica todavía).
    esperan: list[str] = field(default_factory=list)
    # Candidatos cuya ficha decidió el experto.
    escalados: list[str] = field(default_factory=list)
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
    # Agotado el tope del modo, siguen solo los casos críticos que esperaban al experto: van
    # directos a él (critico_sin_base) y la tanda acaba con la parada del límite.
    sin_tope: coste.LimiteGasto | None = None
    for peticion in peticiones:
        candidato_id = peticion.candidato["id"]
        if espera_experto(almacen, candidato_id, ahora):
            continue
        critico_pendiente = bool(esperan_experto(almacen).get(candidato_id, {}).get("critico"))
        if sin_tope is not None and not critico_pendiente:
            continue
        gastado = almacen.gastado(
            modo.value, coste.dia(ahora) if modo is coste.Modo.HORARIO else None
        )
        previsto = coste.peor_caso(
            peticion.letras(), ficha.MAX_TOKENS_SALIDA, esfuerzo=ficha.ESFUERZO
        )
        try:
            if plazo is not None:
                plazo.comprobar()
            if sin_tope is None:
                try:
                    coste.comprobar(gastado, previsto, modo, coste.del_mes(almacen, ahora))
                except coste.LimiteGasto as error:
                    sin_tope = error
            if sin_tope is not None and not critico_pendiente:
                continue
            try:
                escalado_por: list[str] | None
                if sin_tope is not None:
                    respuesta, escalado_por = experto_sin_base(
                        almacen, cliente, peticion, ahora, sin_tope
                    )
                else:
                    respuesta = cliente.mensaje(peticion.cuerpo())
                    respuesta, escalado_por = escalar(
                        almacen, cliente, peticion, respuesta, ahora, modo
                    )
            except EsperaExperto as espera:
                # La ficha necesita al experto y no puede ser ahora: el candidato espera y los
                # demás siguen (la llamada del base ya está anotada).
                anotar_espera(almacen, candidato_id, espera.motivos, ahora, espera.por_tope,
                              revision=espera.revision, critico=espera.critico)  # fmt: skip
                hechas.esperan.append(candidato_id)
                continue
        except TiempoAgotado as error:
            return hechas.parar(Parada.TIEMPO, error)
        except coste.LimiteGasto as error:
            return hechas.parar(Parada.LIMITE_GASTO, error)
        except ErrorTemporal as error:
            return hechas.parar(Parada.SERVICIO_CAIDO, error)
        except LlamadaFallida as error:
            return hechas.parar(Parada.ERROR, error)
        except Exception as error:
            # Una respuesta que el cliente no sabe leer: se aparta este candidato y se para como
            # con una caída (insistir con los demás solo gastaría). Los apartados van los últimos
            # en la recogida siguiente, así que uno solo no frena a los demás.
            motivo = f"respuesta del servicio ilegible: {error!r}"
            anotar_fallo(almacen, candidato_id, motivo, ahora)
            hechas.apartados.append(candidato_id)
            return hechas.parar(Parada.SERVICIO_CAIDO, error)
        try:
            incidente = procesar_respuesta(
                almacen, peticion, respuesta, ahora, modo_de_la_respuesta(escalado_por, modo),
                False, modelos_base, escalado_por,
            )  # fmt: skip
            quitar_espera(almacen, candidato_id)
            if escalado_por:
                hechas.escalados.append(candidato_id)
        except Exception as error:
            # El fallo es de este candidato (sus datos o su ficha): se aparta y los demás siguen.
            registro.exception("candidato %s: fallo al procesar su respuesta", candidato_id)
            anotar_fallo(almacen, candidato_id, f"fallo al procesar la respuesta: {error!r}", ahora)
            hechas.apartados.append(candidato_id)
            incidente = None
        hechas.incidentes.append(incidente)
    if sin_tope is not None:
        return hechas.parar(Parada.LIMITE_GASTO, sin_tope)
    return hechas


def recortar_para_lote(
    almacen: Almacen, peticiones: list[Peticion], modo: coste.Modo = coste.Modo.HISTORICO
) -> tuple[list[Peticion], float]:
    """Las peticiones que caben en lo que queda del límite del modo, en el peor caso."""
    queda = coste.limite(modo) - almacen.gastado(modo.value)
    elegidas: list[Peticion] = []
    previsto = 0.0
    for peticion in peticiones:
        caso = coste.peor_caso(
            peticion.letras(), ficha.MAX_TOKENS_SALIDA, lote=True, esfuerzo=ficha.ESFUERZO
        )
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
        momento = ahora()
        try:
            incidente = procesar_respuesta(
                almacen, peticion, mensaje, momento, modo, True, modelos_base
            )
        except Exception as error:
            registro.exception("candidato %s: fallo al procesar su respuesta", peticion.id_lote)
            motivo = f"fallo al procesar la respuesta: {error!r}"
            anotar_fallo(almacen, peticion.candidato["id"], motivo, momento)
            fallidas += 1
            continue
        procesadas += 1
        publicadas += incidente is not None
    return {"enviadas": procesadas + fallidas, "publicadas": publicadas, "fallidas": fallidas}
