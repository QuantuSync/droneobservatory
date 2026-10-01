"""Extracción de los documentos oficiales de detalle y su entrada en la base.

Cada documento recogido (recogida/detalle.py) llega con los pasajes que hablan de drones ya
localizados por código (proceso/pasajes.py). Si no tiene ninguno, se guarda como «sin_drones»
y no se llama al extractor. Si los tiene, una llamada con solo esos pasajes devuelve los
sucesos que cita y las cifras agregadas que da, cada dato con su frase y su confianza; el
código los valida (proceso/validacion_oficial.py) y:

- cada cifra válida es una estadística oficial;
- cada suceso válido se cruza con los incidentes por la regla de fusión: si encaja con uno solo
  le aporta sus datos (proceso/detalle.py); si no encaja con ninguno y tiene fecha y lugar,
  entra como incidente nuevo por el flujo normal; si encaja con varios, no se enlaza.

Las cifras que da una tabla legible por código (recogida/detalle.py) entran sin extractor, con
método parser. Cada llamada anota sus tokens y su coste con el modo de gasto que toca: «horario»
para lo nuevo de cada día (el límite diario de siempre) y «detalle» para el histórico, por lotes.
"""

import hashlib
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from typing import Any

from almacen.base import Almacen, DocumentoInvalido
from esquema import Documento
from modelo import coste, ficha, ficha_oficial
from modelo.cliente import ErrorTemporal, LlamadaFallida
from proceso import detalle, incidentes
from proceso.extraccion import Parada, Servicio, ServicioLotes, prefijos_genericos
from proceso.fronteras import paises
from proceso.validacion_oficial import Suceso, validar_cifra, validar_suceso
from recogida.plazo import Plazo, TiempoAgotado

registro = logging.getLogger(__name__)

MAX_ID_LOTE = 64
MAX_PALABRAS = 25
# Solo una respuesta del gobierno en el parlamento da de alta un incidente que no estaba: un
# informe de investigación o una sentencia llegan meses después y casi nunca son de un
# incidente de la recogida; aportan a los que ya hay.
TIPOS_ALTA = frozenset({"respuesta_parlamentaria"})
ESPERA_LOTE_S = 60.0
MAX_ESPERA_LOTE = timedelta(hours=24)
MAX_MOTIVOS = 20


def _instante(momento: datetime) -> Documento:
    return {"valor": momento.astimezone(UTC).strftime("%Y-%m-%dT%H:%MZ"), "precision": "minuto"}


def id_lote(documento_id: str) -> str:
    return hashlib.sha256(documento_id.encode("utf-8")).hexdigest()[:MAX_ID_LOTE]


def _datos(recogido: Documento) -> dict[str, str]:
    return {k: str(recogido[k]) for k in ("tipo", "autoridad", "pais", "fecha", "idioma", "titulo")}


def cuerpo(recogido: Documento) -> dict[str, Any]:
    return ficha_oficial.cuerpo(_datos(recogido), list(recogido["pasajes"]))


def letras(recogido: Documento) -> int:
    return (
        len(ficha_oficial.INSTRUCCIONES)
        + len(ficha_oficial.contenido(_datos(recogido), list(recogido["pasajes"])))
        + len(str(ficha_oficial.ESQUEMA))
    )


def peor_caso(recogido: Documento, lote: bool = False) -> float:
    return coste.peor_caso(letras(recogido), ficha_oficial.MAX_TOKENS_SALIDA, lote)


def documento_base(recogido: Documento, ahora: datetime) -> Documento:
    """El registro del documento leído, sin lo que se saque de él."""
    pasajes = list(recogido.get("pasajes", []))
    documento: Documento = {
        "id": recogido["id"],
        "fuente_detalle": recogido["fuente_detalle"],
        "tipo": recogido["tipo"],
        "autoridad": recogido["autoridad"],
        "pais": recogido["pais"],
        "idioma": recogido["idioma"],
        "titulo": recogido["titulo"],
        "enlace": recogido["enlace"],
        "fecha": recogido["fecha"],
        "fiabilidad": recogido.get("fiabilidad", "A"),
        "credibilidad": recogido.get("credibilidad", 1),
        "estado": "pendiente" if pasajes else "sin_drones",
        "pasajes": {"numero": len(pasajes), "letras": sum(len(p) for p in pasajes)},
        "control": {"alta": _instante(ahora)},
    }
    if recogido.get("huella"):
        documento["pasajes"]["huella"] = recogido["huella"]
    return documento


# --- Estadísticas -----------------------------------------------------------------------


def id_estadistica(documento: Documento, cifra: Documento) -> str:
    clave = "|".join(str(x) for x in (
        documento["autoridad"], documento["id"], cifra["periodo_inicio"], cifra["periodo_fin"],
        cifra["pais"], cifra.get("categoria") or "", cifra.get("instalacion") or "",
        cifra["metrica"],
    ))  # fmt: skip
    return "EST-" + hashlib.sha256(clave.encode("utf-8")).hexdigest()[:16]


def estadistica(
    documento: Documento, cifra: Documento, metodo: str, ahora: datetime, version: str | None
) -> Documento:
    id_ = id_estadistica(documento, cifra)
    ambito: Documento = {"pais": cifra["pais"]}
    if cifra.get("categoria"):
        ambito["categoria"] = cifra["categoria"]
    if cifra.get("instalacion"):
        ambito["instalacion"] = " ".join(str(cifra["instalacion"]).split())
    if cifra.get("oaci"):
        ambito["oaci"] = cifra["oaci"]
    resultado: Documento = {
        "id": id_,
        "autoridad": documento["autoridad"],
        "pais_autoridad": documento["pais"],
        "documento": {
            "id": documento["id"], "tipo": documento["tipo"], "titulo": documento["titulo"],
            "enlace": documento["enlace"], "fecha": documento["fecha"],
        },
        "periodo": {"inicio": cifra["periodo_inicio"], "fin": cifra["periodo_fin"]},
        "ambito": ambito,
        "metrica": cifra["metrica"],
        "cifra": {"min": int(cifra["valor"]["min"]), "max": int(cifra["valor"]["max"])},
        "frase": " ".join(str(cifra["frase"]).split()[:MAX_PALABRAS]),
        "fuente": {"medio": documento["autoridad"], "fiabilidad": documento.get("fiabilidad", "A"),
                   "credibilidad": documento.get("credibilidad", 1)},
        "procedencia": {
            "cifra": {"origen": "oficial", "metodo": metodo, "fuentes": [documento["id"]]}
        },
        "control": {"alta": _instante(ahora)},
    }  # fmt: skip
    if metodo == "extractor":
        resultado["confianza"] = float(cifra["confianza"])
        resultado["procedencia"]["cifra"]["confianza"] = float(cifra["confianza"])
    if version:
        resultado["control"]["version_extractor"] = version
    return resultado


def guardar_estadisticas(
    almacen: Almacen, documento: Documento, cifras: list[Documento], metodo: str, ahora: datetime,
    version: str | None,
) -> tuple[list[str], list[str], int]:  # fmt: skip
    """Guarda las cifras válidas. Devuelve sus identificadores, los motivos de las demás y
    cuántas son nuevas o han cambiado."""
    ids, motivos, cambiadas = [], [], 0
    for cifra in cifras:
        try:
            registro_ = estadistica(documento, cifra, metodo, ahora, version)
            if (previo := almacen.estadistica_oficial(registro_["id"])) is not None:
                registro_["control"]["alta"] = previo["control"]["alta"]
            cambiadas += almacen.guardar_estadistica_oficial(registro_, ahora)
        except (DocumentoInvalido, KeyError, TypeError, ValueError) as error:
            motivos.append(f"cifra: {str(error)[:120]}")
            continue
        ids.append(registro_["id"])
    return sorted(set(ids)), motivos, cambiadas


# --- Sucesos ----------------------------------------------------------------------------


def cruzar(
    almacen: Almacen,
    documento: Documento,
    indice: int,
    suceso: Suceso,
    ahora: datetime,
    modelos: frozenset[str],
) -> Documento:
    """El cruce del suceso con los incidentes y, si no hay ninguno, el alta."""
    validada = suceso.validada
    resultado: Documento = {"datos": suceso.datos, "cruce": "sin_lugar"}
    if not validada.valor("inicio"):
        resultado["cruce"] = "sin_fecha"
        return resultado
    if validada.pais is None or validada.pais not in paises():
        return resultado
    ubicacion = detalle.ubicar_suceso(almacen, validada, prefijos_genericos())
    pseudo = detalle.pseudo_suceso(ubicacion, validada)
    if pseudo is None or not ubicacion.valida:
        return resultado
    if ubicacion.sitio is not None:
        resultado["punto"] = {
            "lat": round(ubicacion.sitio.lat, 5), "lon": round(ubicacion.sitio.lon, 5),
            "radio_km": ubicacion.sitio.radio_km,
        }  # fmt: skip
    activos = [i for i in almacen.incidentes() if incidentes.activo(i)]
    sin_punto = ubicacion.sitio is None
    hallados = [
        i["id"] for i in activos
        if i["lugar"]["pais"] == pseudo["lugar"]["pais"] and incidentes.encajan(i, pseudo)
    ]  # fmt: skip
    if len(hallados) == 1:
        return {**resultado, "cruce": "existente", "incidente": hallados[0]}
    if len(hallados) > 1:
        return {**resultado, "cruce": "varios", "motivos": sorted(hallados)[:MAX_MOTIVOS]}
    if documento["tipo"] not in TIPOS_ALTA:
        # Informes de investigación, cierres y sentencias aportan a los incidentes que ya hay;
        # no dan de alta ninguno.
        return {**resultado, "cruce": "sin_incidente"}
    if sin_punto and ubicacion.nivel == "pais":
        # Sin lugar más preciso que el país no se da de alta: no se podría cruzar con nada.
        return {**resultado, "cruce": "sin_lugar"}
    if not validada.titulo_es or not validada.titulo_en:
        return {**resultado, "cruce": "no_valido", "motivos": ["sin título"]}
    try:
        nuevo = detalle.alta(almacen, documento, indice, validada, ubicacion, ahora, modelos)
        almacen.guardar_incidente(nuevo, ahora, modelos)
    except (DocumentoInvalido, KeyError, ValueError) as error:
        return {**resultado, "cruce": "no_valido", "motivos": [str(error)[:200]]}
    return {**resultado, "cruce": "nuevo", "incidente": nuevo["id"]}


# --- Respuestas ---------------------------------------------------------------------------


def procesar(
    almacen: Almacen,
    recogido: Documento,
    respuesta: dict[str, Any],
    ahora: datetime,
    modo: coste.Modo,
    lote: bool,
    modelos: frozenset[str],
) -> Documento:
    """Anota el coste, valida lo extraído y guarda el documento con lo que sale de él."""
    uso = coste.Uso.de_respuesta(respuesta.get("usage", {}))
    almacen.registrar_llamada({
        "fecha": ahora.strftime("%Y-%m-%dT%H:%M:%SZ"), "modo": modo.value,
        "candidato": recogido["id"], "lote": lote, "entrada": uso.entrada, "salida": uso.salida,
        "escritura_cache": uso.escritura_cache, "lectura_cache": uso.lectura_cache,
        "coste": uso.coste(lote),
    })  # fmt: skip
    documento = documento_base(recogido, ahora)
    if (previo := almacen.documento_oficial(documento["id"])) is not None:
        documento["control"]["alta"] = previo["control"]["alta"]
    documento["control"].update({"extraido": _instante(ahora), "metodo": "extractor",
                                 "version_extractor": ficha_oficial.VERSION})  # fmt: skip
    motivos: list[str] = []
    try:
        leida = ficha_oficial.leer_respuesta(respuesta)
    except ficha.RespuestaInvalida as error:
        documento.update({"estado": "sin_datos", "descartados": [str(error)]})
        almacen.guardar_documento_oficial(documento, ahora)
        return documento
    motivos += leida["ilegibles"]
    texto = "\n\n".join(recogido["pasajes"])
    fecha = date.fromisoformat(recogido["fecha"])
    cifras = []
    for cifra in leida["cifras"]:
        motivo = validar_cifra(cifra, texto, fecha)
        if motivo:
            motivos.append(f"cifra {cifra.get('valor')}: {motivo}")
        else:
            cifras.append(cifra)
    ids, malas, _ = guardar_estadisticas(almacen, documento, cifras, "extractor", ahora,
                                      ficha_oficial.VERSION)  # fmt: skip
    motivos += malas
    sucesos = []
    for indice, bruto in enumerate(leida["sucesos"], 1):
        suceso, descartes = validar_suceso(bruto, texto, recogido["pais"], fecha, ahora)
        motivos += [f"suceso {indice}, {m}" for m in descartes]
        if not suceso.datos:
            continue
        sucesos.append(cruzar(almacen, documento, indice, suceso, ahora, modelos))
    documento["sucesos"] = sucesos
    documento["estadisticas"] = ids
    if motivos:
        documento["descartados"] = motivos[:MAX_MOTIVOS]
    documento["estado"] = "extraido" if sucesos or ids else "sin_datos"
    almacen.guardar_documento_oficial(documento, ahora)
    return documento


@dataclass
class Extraidos:
    documentos: list[str] = field(default_factory=list)
    parada: Parada | None = None
    motivo: str = ""


def extraer(
    almacen: Almacen,
    cliente: Servicio,
    recogidos: list[Documento],
    ahora: datetime,
    modo: coste.Modo,
    modelos: frozenset[str],
    plazo: Plazo | None = None,
) -> Extraidos:
    """Llamadas directas hasta la primera parada (límite de gasto, plazo o error)."""
    hechos = Extraidos()
    for recogido in recogidos:
        gastado = almacen.gastado(
            modo.value, coste.dia(ahora) if modo is coste.Modo.HORARIO else None
        )
        try:
            if plazo is not None:
                plazo.comprobar()
            coste.comprobar(gastado, peor_caso(recogido), modo)
            respuesta = cliente.mensaje(cuerpo(recogido))
        except TiempoAgotado as error:
            hechos.parada, hechos.motivo = Parada.TIEMPO, str(error)
            break
        except coste.LimiteGasto as error:
            hechos.parada, hechos.motivo = Parada.LIMITE_GASTO, str(error)
            break
        except ErrorTemporal as error:
            hechos.parada, hechos.motivo = Parada.SERVICIO_CAIDO, str(error)
            break
        except LlamadaFallida as error:
            hechos.parada, hechos.motivo = Parada.ERROR, str(error)
            break
        procesar(almacen, recogido, respuesta, ahora, modo, False, modelos)
        hechos.documentos.append(recogido["id"])
    return hechos


def recortar(almacen: Almacen, recogidos: list[Documento], modo: coste.Modo) -> list[Documento]:
    """Los que caben en lo que queda del límite del modo, en el peor caso de un lote."""
    queda = coste.limite(modo) - almacen.gastado(modo.value)
    elegidos, previsto = [], 0.0
    for recogido in recogidos:
        caso = peor_caso(recogido, lote=True)
        if previsto + caso > queda:
            break
        elegidos.append(recogido)
        previsto += caso
    return elegidos


def enviar_lote(cliente: ServicioLotes, recogidos: list[Documento]) -> dict[str, Any]:
    return cliente.crear_lote(
        [{"custom_id": id_lote(r["id"]), "params": cuerpo(r)} for r in recogidos]
    )


def esperar_lote(
    cliente: ServicioLotes,
    lote: dict[str, Any],
    reloj: Callable[[], datetime] = lambda: datetime.now(UTC),
    dormir: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    inicio = reloj()
    while lote.get("processing_status") != "ended":
        if reloj() - inicio > MAX_ESPERA_LOTE:
            raise LlamadaFallida("el lote no terminó en 24 horas")
        dormir(ESPERA_LOTE_S)
        lote = cliente.lote(lote["id"])
    return lote


def procesar_resultados(
    almacen: Almacen,
    resultados: list[dict[str, Any]],
    recogidos: list[Documento],
    ahora: datetime,
    modelos: frozenset[str],
    modo: coste.Modo = coste.Modo.DETALLE,
) -> dict[str, int]:
    """Los resultados de un lote terminado, con los documentos que lo formaron."""
    por_id = {id_lote(r["id"]): r for r in recogidos}
    procesados = fallidos = 0
    for resultado in resultados:
        recogido = por_id.get(resultado.get("custom_id", ""))
        if recogido is None or resultado.get("result", {}).get("type") != "succeeded":
            fallidos += 1
            continue
        procesar(almacen, recogido, resultado["result"]["message"], ahora, modo, True, modelos)
        procesados += 1
    return {"procesados": procesados, "fallidos": fallidos}
