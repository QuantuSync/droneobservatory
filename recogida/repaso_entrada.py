"""Repaso de todo lo publicado con la pregunta del filtro de entrada (docs/control_fichas.md,
«Repaso de entrada»).

Lo publicado antes del filtro de entrada (PR 335, 28 de octubre de 2026) no pasó por él, y ese
día se encontraron publicados duplicados, fechas de noticias retrospectivas y una autoridad de
otro país. Cada ficha publicada pasa por el experto como si fuera nueva, con su conjunto de
comparación (recogida/entrada.conjunto: mismo país, 30 días antes y 3 después de su inicio y de
su primera noticia, sin mirar la distancia; los vecinos si el lugar es vago) y la pregunta del
filtro, con dos más: ¿junta varios sucesos de días o lugares distintos? y ¿hay un error en el
número de drones, el tipo, el estado o la presencia?

Tres pasos, por grupos (`GRUPOS`: a, las sospechosas de una revisión; b, las de fecha
aproximada; c, las de lugar vago; d, el resto):

- `decidir`: llamadas directas al experto (no por lotes), con su presupuesto aparte (modo
  «repaso_entrada», 40 dólares: coste.LIMITE_REPASO_ENTRADA_USD). Las decisiones se guardan en
  el control (`repaso_entrada:<id>`, con la huella de la ficha) y el gasto en la base, con el
  cerrojo de la recogida y nunca entre los minutos 12 y 45 (la recogida horaria). Lo ya decidido
  con la misma huella no se repite;
- `muestra`: los cambios de un grupo elegidos al azar con una semilla, para leerlos en su fuente;
  el resultado se escribe en un fichero (`bien` de cada uno);
- `aplicar`: solo con el muestreo aprobado del grupo (las muestras que tocan, el azar de la
  semilla y como mucho una mal) y por el camino normal, con el motivo en el historial: la unión
  (queda la más antigua), el día que da una frase, la retirada de una ficha sin fecha conocida o
  que es un resumen, el lugar en el país y las autoridades no oficiales. Las separaciones y los
  datos corregidos con su frase se escriben como propuestas para configuracion/
  incidentes_revisados.json («separar», «datos» y «retirar», que la recogida aplica cada hora).
"""

import hashlib
import json
import logging
import random
import time
from collections.abc import Callable, Iterable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from almacen.base import Almacen
from esquema import Documento
from modelo import coste
from modelo import entrada as peticiones
from proceso import control_fichas as reglas
from proceso import incidentes
from proceso.presencia import TABLA_MOTIVOS
from recogida import control_fichas, entrada
from recogida.plazo import Plazo

registro = logging.getLogger(__name__)

PREFIJO = "repaso_entrada:"
PREFIJO_MUESTREO = "repaso_entrada_muestreo:"
GRUPOS = ("a", "b", "c", "d")
# Muestras que se leen en su fuente antes de aplicar un grupo; con 2 o más mal no se aplica.
MUESTRA = {"a": 15, "b": 10, "c": 10, "d": 10}
MAX_MAL = 1
HILOS = 4
POR_TANDA = 12
# La recogida horaria toma el cerrojo hacia el minuto 17 y publica hacia el 35: el repaso no lo
# toma entre estos minutos.
VENTANA_RECOGIDA = (12, 45)

UNIR, DIA, RETIRAR, SEPARAR, LUGAR, AUTORIDAD, DATO = (
    "unir", "dia", "retirar", "separar", "lugar", "autoridad", "dato"
)  # fmt: skip
MOTIVO_FECHA = {
    "es": "Fecha del suceso desconocida: la noticia cuenta un suceso anterior sin decir cuándo fue "
    "(repaso de entrada con el experto).",
    "en": "Unknown event date: the report tells of an earlier event without saying when it "
    "happened (entry review by the expert model).",
}
MOTIVO_RESUMEN = {
    "es": "Es un resumen o un balance sin un suceso de un día concreto (repaso de entrada con el "
    "experto).",
    "en": "It is a summary or a tally without an event on a given day (entry review by the "
    "expert model).",
}

# Grupo a: la lista de sospechosas de la revisión del 23 de octubre de 2026 (pares que pueden ser
# el mismo suceso, la frontera del Danubio, Bélgica, Dinamarca y fichas que resumen varios días).
SOSPECHOSAS: tuple[str, ...] = (
    "EODI-2025-00116",
    "EODI-2025-00340",
    "EODI-2025-00004",
    "EODI-2025-00060",
    "EODI-2026-00577",
    "EODI-2026-00578",
    "EODI-2025-00092",
    "EODI-2025-00408",
    "EODI-2025-00163",
    "EODI-2025-00049",
    "EODI-2025-00106",
    "EODI-2025-00034",
    "EODI-2025-00101",
    "EODI-2025-00460",
    "EODI-2025-00468",
    "EODI-2026-00261",
    "EODI-2026-00370",
    "EODI-2025-00042",
    "EODI-2025-00325",
    "EODI-2026-00098",
    "EODI-2026-00281",
    "EODI-2026-00497",
    "EODI-2026-00511",
    "EODI-2026-00136",
    "EODI-2026-00311",
    "EODI-2026-00151",
    "EODI-2026-00155",
    "EODI-2026-00111",
    "EODI-2026-00158",
    "EODI-2026-00106",
    "EODI-2026-00171",
    "EODI-2026-00230",
    "EODI-2026-00528",
    "EODI-2026-00193",
    "EODI-2026-00196",
    "EODI-2026-00244",
    "EODI-2026-00676",
    "EODI-2026-00682",
    "EODI-2026-00168",
    "EODI-2026-00636",
    "EODI-2025-00016",
    "EODI-2025-00072",
    "EODI-2025-00080",
    "EODI-2025-00091",
    "EODI-2025-00131",
    "EODI-2025-00198",
    "EODI-2025-00211",
    "EODI-2025-00223",
    "EODI-2025-00248",
    "EODI-2025-00335",
    "EODI-2025-00344",
    "EODI-2025-00445",
    "EODI-2025-00446",
    "EODI-2025-00291",
    "EODI-2025-00309",
    "EODI-2025-00383",
    "EODI-2025-00459",
    "EODI-2025-00141",
    "EODI-2026-00085",
    "EODI-2025-00263",
)


def clave(id_: str) -> str:
    return f"{PREFIJO}{id_}"


def _iso(momento: datetime) -> str:
    return momento.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def vago(incidente: Documento) -> bool:
    """El lugar es el país, una región o el mar (sin punto)."""
    lugar = incidente["lugar"]
    return lugar.get("nivel") in {"pais", "region", "mar"} or "punto" not in lugar


def grupo_de(incidente: Documento) -> str:
    """El grupo de una ficha publicada: el primero que le toca por orden."""
    if incidente["id"] in SOSPECHOSAS:
        return "a"
    if incidente["tiempo"]["inicio"].get("precision") == "aproximada":
        return "b"
    return "c" if vago(incidente) else "d"


def del_grupo(activos: Iterable[Documento], grupo: str) -> list[Documento]:
    return sorted((d for d in activos if grupo_de(d) == grupo), key=lambda d: d["id"])


# --- La decisión comprobada ---------------------------------------------------------------


def _ids_de(incidente: Documento, numeros: Any, fuentes: list[tuple[str, str]]) -> list[str]:
    """Las fuentes de la ficha (con sus declaraciones, que comparten enlace) de esos números."""
    enlaces = {f["id"]: f.get("enlace") for f in incidente.get("fuentes", [])}
    elegidas = {fuentes[n - 1][0] for n in numeros or []
                if isinstance(n, int) and 1 <= n <= len(fuentes)}  # fmt: skip
    suyos = {enlaces.get(i) for i in elegidas} - {None}
    return [f["id"] for f in incidente.get("fuentes", [])
            if f["id"] in elegidas or f.get("enlace") in suyos]  # fmt: skip


def decidir(
    respuesta: dict[str, Any], fuentes: list[tuple[str, str]], ids_conjunto: list[str],
    incidente: Documento,
) -> dict[str, Any]:  # fmt: skip
    """La respuesta comprobada: lo del filtro de entrada (entrada.decidir) y lo del repaso (la
    fecha desconocida, los varios sucesos con sus partes, el resumen y los errores de un dato con
    su frase)."""
    decision = entrada.decidir(respuesta, fuentes, ids_conjunto, incidente)
    decision["fecha_desconocida"] = bool(respuesta.get("fecha_desconocida")) and not decision.get(
        "frase_fecha"
    )
    decision["resumen"] = bool(respuesta.get("resumen"))
    partes = []
    for parte in respuesta.get("partes") or []:
        if not isinstance(parte, dict):
            continue
        ids = _ids_de(incidente, parte.get("fuentes"), fuentes)
        if ids:
            partes.append({"fecha": str(parte.get("fecha") or "")[:10],
                           "descripcion": str(parte.get("descripcion") or "")[:300],
                           "fuentes": ids})  # fmt: skip
    decision["partes"] = partes if bool(respuesta.get("varios_sucesos")) else []
    errores = []
    for error in respuesta.get("errores") or []:
        if not isinstance(error, dict) or error.get("dato") not in peticiones.DATOS_REPASO:
            continue
        con_frase = entrada._frase(error.get("fuente"), error.get("frase"), fuentes)
        if con_frase is None or not str(error.get("correcto") or "").strip():
            continue
        errores.append({"dato": error["dato"], "correcto": str(error["correcto"])[:80],
                        "fuente_id": con_frase[0], "frase": con_frase[1]})  # fmt: skip
    decision["errores"] = errores
    return decision


def cambios(decision: Documento, incidente: Documento) -> list[str]:
    """Lo que la decisión cambia en la ficha, en orden: una unión o una retirada no deja nada
    más; un día nuevo vuelve a pasar por el repaso con él."""
    if decision.get("invalida"):
        return []
    if decision.get("mismo"):
        return [UNIR]
    if decision.get("resumen") and len(decision.get("partes") or []) < 2:
        return [RETIRAR]
    if len(decision.get("partes") or []) >= 2:
        return [SEPARAR]
    if decision.get("otro_dia"):
        return [DIA]
    if (
        decision.get("fecha_desconocida")
        and not decision.get("frase_fecha")
        and entrada.fecha_aproximada(incidente)
    ):
        return [RETIRAR]
    hechos = []
    if not decision.get("frase_lugar") and incidente["lugar"].get("nivel") != "pais":
        hechos.append(LUGAR)
    if decision.get("autoridades_fuera"):
        hechos.append(AUTORIDAD)
    if decision.get("errores"):
        hechos.append(DATO)
    return hechos


# --- Decidir ------------------------------------------------------------------------------


@dataclass
class Resumen:
    decididas: int = 0
    llamadas: int = 0
    gasto: float = 0.0
    errores: list[str] = field(default_factory=list)
    parada: str = "ninguna"

    def texto(self) -> str:
        return (f"decididas={self.decididas} llamadas={self.llamadas} gasto={self.gasto:.4f} "
                f"parada={self.parada} errores={len(self.errores)}")  # fmt: skip


@dataclass
class _Pregunta:
    incidente: Documento
    elegidas: list[Documento]
    fuentes: control_fichas.FuentesDeFicha
    resumenes: list[dict[str, Any]]
    llamadas: list[Documento] = field(default_factory=list)


def esperar_ventana(reloj: Callable[[], datetime], dormir: Callable[[float], None]) -> None:
    """Espera, si hace falta, a que la recogida horaria haya publicado (minuto 45)."""
    ahora = reloj()
    desde, hasta = VENTANA_RECOGIDA
    if desde <= ahora.minute < hasta:
        espera = (hasta - ahora.minute) * 60 - ahora.second
        registro.info("repaso de entrada: espera %d s a que publique la recogida", espera)
        dormir(float(espera))


def _llamada(respuesta: dict[str, Any], clave_: str, ahora: datetime) -> Documento:
    """La llamada para anotar. Como las del repaso con el experto, no va como escalada: cuenta
    solo en su modo (Almacen.gastado), fuera del cupo del experto y del mes."""
    uso = coste.Uso.de_mensaje(respuesta)
    return {
        "fecha": _iso(ahora), "modo": coste.Modo.REPASO_ENTRADA.value, "candidato": clave_[:200],
        "lote": False, "entrada": uso.entrada, "salida": uso.salida,
        "escritura_cache": uso.escritura_cache, "lectura_cache": uso.lectura_cache,
        "coste": uso.coste(), "modelo": uso.modelo, "escalada": False,
    }  # fmt: skip


def _leer(respuesta: dict[str, Any]) -> dict[str, Any] | None:
    from modelo import control

    try:
        return control.leer(respuesta)
    except control.RespuestaInvalida:
        return None


def _preparar(almacen: Almacen, incidente: Documento, activos: list[Documento],
              plazo: Plazo) -> _Pregunta:  # fmt: skip
    elegidas = entrada.conjunto(incidente, activos)
    fuentes = control_fichas.fuentes_de_ficha(almacen, incidente, entrada._textos(incidente, plazo))
    return _Pregunta(incidente, elegidas, fuentes, [entrada.resumen(c) for c in elegidas])


def _cuerpo(almacen: Almacen, pregunta: _Pregunta, con_contexto: list[str] | None) -> Documento:
    vista = reglas.vista(pregunta.incidente)
    citadas = list(entrada.autoridades_de(pregunta.incidente))
    contexto = None
    if con_contexto is not None:
        por_id = {c["id"]: c for c in pregunta.elegidas}
        contexto = {i: control_fichas.fuentes_de_ficha(almacen, por_id[i], {}).bloques
                    for i in con_contexto if i in por_id}  # fmt: skip
    return peticiones.cuerpo_repaso(vista, pregunta.fuentes.bloques, citadas,
                                    pregunta.resumenes, contexto)  # fmt: skip


def decidir_grupo(
    base: control_fichas.Base, fabrica: Callable[[], Any], grupo: str, tope_s: float,
    reloj: Callable[[], datetime] | None = None, dormir: Callable[[float], None] | None = None,
    solo: list[str] | None = None,
) -> Resumen:  # fmt: skip
    """Decide (sin aplicar) las fichas publicadas del grupo que no tienen decisión con su huella
    de ahora, por tandas: cada tanda pregunta con hilos al experto y guarda sus decisiones y su
    gasto en la base con el cerrojo, fuera de los minutos de la recogida."""
    reloj = reloj or (lambda: datetime.now(UTC))
    dormir = dormir or time.sleep
    resumen = Resumen()
    servicio = fabrica()
    experto = getattr(servicio, "experto", None)
    cliente = experto() if callable(experto) else None
    if cliente is None:
        resumen.parada = "sin_experto"
        return resumen
    plazo = Plazo(tope_s)
    while not plazo.agotado():
        copia = base.abrir()
        activos = [d for d in copia.incidentes() if incidentes.activo(d)]
        decisiones = copia.controles(PREFIJO)
        pendientes = [d for d in del_grupo(activos, grupo)
                      if (solo is None or d["id"] in solo)
                      and (decisiones.get(clave(d["id"])) or {}).get("huella")
                      != entrada.huella(d)]  # fmt: skip
        disponible = coste.limite(coste.Modo.REPASO_ENTRADA) - copia.gastado(
            coste.Modo.REPASO_ENTRADA.value
        )
        if not pendientes:
            base.soltar(copia)
            break
        if disponible < 0.5:
            resumen.parada = "limite_gasto"
            base.soltar(copia)
            break
        tanda = pendientes[:POR_TANDA]
        preguntas = [_preparar(copia, d, activos, plazo) for d in tanda]
        nuevas, llamadas = _preguntar(copia, cliente, preguntas, reloj(), resumen)
        base.soltar(copia)
        esperar_ventana(reloj, dormir)
        with base.cerrojo():
            almacen = base.abrir()
            for llamada in llamadas:
                almacen.registrar_llamada(llamada)
            almacen.guardar_controles(nuevas, _iso(reloj()))
            base.guardar(almacen)
            base.soltar(almacen)
        resumen.decididas += len(nuevas)
        registro.info("repaso de entrada %s: %s", grupo, resumen.texto())
        if not nuevas:
            break
    if plazo.agotado():
        resumen.parada = "tiempo"
    return resumen


def _preguntar(
    almacen: Almacen, cliente: Any, preguntas: list[_Pregunta], ahora: datetime, resumen: Resumen
) -> tuple[dict[str, Documento], list[Documento]]:
    """Las decisiones de una tanda (dos vueltas: la segunda, con las fuentes de las candidatas,
    si duda o le falta una frase) y las llamadas que costaron."""
    llamadas: list[Documento] = []

    def una(cuerpo: Documento) -> dict[str, Any] | None:
        try:
            return dict(cliente.mensaje(cuerpo))
        except Exception as error:  # una llamada que falla deja la ficha para otra pasada
            resumen.errores.append(repr(error)[:200])
            return None

    def ronda(cuerpos: list[Documento]) -> list[dict[str, Any] | None]:
        with ThreadPoolExecutor(HILOS) as hilos:
            return list(hilos.map(una, cuerpos))

    primeras = ronda([_cuerpo(almacen, p, None) for p in preguntas])
    decisiones: dict[str, dict[str, Any]] = {}
    repetir: list[tuple[_Pregunta, list[str]]] = []
    for pregunta, respuesta in zip(preguntas, primeras, strict=True):
        if respuesta is None:
            continue
        id_ = pregunta.incidente["id"]
        llamadas.append(_llamada(respuesta, clave(id_), ahora))
        leida = _leer(respuesta)
        if leida is None:
            continue
        ids = [c["id"] for c in pregunta.elegidas]
        decision = decidir(leida, pregunta.fuentes.comprobar, ids, pregunta.incidente)
        decisiones[id_] = decision
        if decision.get("duda") or entrada.sin_frase(decision) or decision.get("invalida"):
            dudosas = [*decision.get("dudosas", []), *([decision["mismo"]]
                       if "mismo" in decision else []), *ids]  # fmt: skip
            repetir.append(
                (pregunta, list(dict.fromkeys(dudosas))[: peticiones.MAX_CANDIDATAS_CONTEXTO])
            )
    segundas = ronda([_cuerpo(almacen, p, ctx) for p, ctx in repetir])
    for (pregunta, _), respuesta in zip(repetir, segundas, strict=True):
        if respuesta is None:
            continue
        id_ = pregunta.incidente["id"]
        llamadas.append(_llamada(respuesta, clave(id_) + ":contexto", ahora))
        otra = _leer(respuesta)
        if otra is not None:
            ids = [c["id"] for c in pregunta.elegidas]
            decisiones[id_] = {
                **decidir(otra, pregunta.fuentes.comprobar, ids, pregunta.incidente),
                "repetida": True,
            }
    resumen.llamadas += len(llamadas)
    resumen.gasto += sum(float(ll["coste"]) for ll in llamadas)
    nuevas: dict[str, Documento] = {}
    for pregunta in preguntas:
        incidente = pregunta.incidente
        if incidente["id"] not in decisiones:
            continue
        decision = decisiones[incidente["id"]]
        por_id = {c["id"]: c for c in pregunta.elegidas}
        if "mismo" in decision:
            fechas = entrada.fechas_distintas(incidente, por_id[decision["mismo"]])
            if fechas:
                mismo = decision.pop("mismo")
                decision["invalida"] = f"el mismo suceso que {mismo} con fechas firmes ({fechas})"
        nuevas[clave(incidente["id"])] = {
            **decision, "version": peticiones.VERSION_REPASO, "fecha": _iso(ahora),
            "grupo": grupo_de(incidente), "huella": entrada.huella(incidente),
            "conjunto": len(pregunta.elegidas), "cambios": cambios(decision, incidente),
        }  # fmt: skip
    return nuevas, llamadas


# --- Muestra ------------------------------------------------------------------------------


def con_cambios(decisiones: dict[str, Documento], grupo: str) -> dict[str, Documento]:
    """Las decisiones del grupo que cambian algo y aún no se han aplicado, por id."""
    return {
        k.removeprefix(PREFIJO): d
        for k, d in sorted(decisiones.items())
        if d.get("grupo") == grupo and d.get("cambios") and not d.get("aplicada")
    }


def huella_grupo(elegidas: dict[str, Documento]) -> str:
    texto = json.dumps({i: (d.get("huella"), d.get("cambios")) for i, d in elegidas.items()},
                       sort_keys=True, ensure_ascii=False)  # fmt: skip
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()[:16]


def muestra(decisiones: dict[str, Documento], grupo: str, semilla: int) -> list[str]:
    """Las fichas del muestreo de un grupo: al azar con la semilla, las que tocan (todas si son
    menos)."""
    elegidas = sorted(con_cambios(decisiones, grupo))
    return sorted(random.Random(semilla).sample(elegidas, min(MUESTRA[grupo], len(elegidas))))


def plantilla(decisiones: dict[str, Documento], grupo: str, semilla: int) -> Documento:
    """El fichero del muestreo para rellenar: cada ficha con lo que cambia y su frase."""
    elegidas = con_cambios(decisiones, grupo)
    return {
        "grupo": grupo, "semilla": semilla, "huella": huella_grupo(elegidas),
        "revisadas": [
            {"id": i, "cambios": elegidas[i]["cambios"], "bien": None, "nota": "",
             "decision": {k: elegidas[i].get(k) for k in (
                 "mismo", "motivo_mismo", "otro_dia", "frase_fecha", "frase_lugar",
                 "autoridades_fuera", "fecha_desconocida", "resumen", "partes", "errores",
                 "motivo_es")}}
            for i in muestra(decisiones, grupo, semilla)
        ],
    }  # fmt: skip


class MuestreoNoAprobado(RuntimeError):
    pass


def aprobado(muestreo: Documento, decisiones: dict[str, Documento], grupo: str) -> None:
    """Lanza MuestreoNoAprobado si el muestreo no deja aplicar el grupo: otro grupo, decisiones
    cambiadas desde el muestreo, una muestra que no es la de la semilla, alguna sin leer o dos o
    más mal."""
    elegidas = con_cambios(decisiones, grupo)
    if muestreo.get("grupo") != grupo:
        raise MuestreoNoAprobado(f"el muestreo es del grupo {muestreo.get('grupo')}")
    if muestreo.get("huella") != huella_grupo(elegidas):
        raise MuestreoNoAprobado("las decisiones del grupo cambiaron desde el muestreo")
    revisadas = muestreo.get("revisadas") or []
    ids = sorted(str(r.get("id")) for r in revisadas)
    if ids != muestra(decisiones, grupo, int(muestreo.get("semilla", -1))):
        raise MuestreoNoAprobado("la muestra no es la de su semilla")
    if any(not isinstance(r.get("bien"), bool) for r in revisadas):
        raise MuestreoNoAprobado("hay muestras sin leer")
    malas = sum(1 for r in revisadas if r["bien"] is False)
    if malas > MAX_MAL:
        raise MuestreoNoAprobado(f"{malas} de {len(revisadas)} mal")


# --- Aplicar ------------------------------------------------------------------------------


@dataclass
class Aplicado:
    unidas: list[str] = field(default_factory=list)
    dias: list[str] = field(default_factory=list)
    retiradas: list[str] = field(default_factory=list)
    corregidas: list[str] = field(default_factory=list)
    propuestas: dict[str, list[Documento]] = field(
        default_factory=lambda: {"separar": [], "datos": [], "retirar": []}
    )
    sin_aplicar: list[str] = field(default_factory=list)

    def texto(self) -> str:
        return (f"unidas={len(self.unidas)} dias={len(self.dias)} "
                f"retiradas={len(self.retiradas)} corregidas={len(self.corregidas)} "
                f"separar={len(self.propuestas['separar'])} datos={len(self.propuestas['datos'])} "
                f"sin_aplicar={len(self.sin_aplicar)}")  # fmt: skip


def retirada(incidente: Documento, motivo: dict[str, str], ahora: datetime) -> Documento:
    """La ficha retirada de la publicación con su motivo (el registro se queda)."""
    nuevo = {k: v for k, v in incidente.items() if k != "episodio"}
    nuevo["retirado"] = {"fecha": control_fichas._instante(ahora),
                         "motivo": motivo["es"][:300], "motivo_en": motivo["en"][:300]}  # fmt: skip
    return nuevo


def propuesta_separar(incidente: Documento, decision: Documento) -> Documento:
    """La entrada de «separar» (docs/sucesos_mezclados.md) que propone la decisión."""
    return {
        "incidente": incidente["id"], "distintos": True,
        "motivo": {"es": decision.get("motivo_es") or "", "en": decision.get("motivo_en") or ""},
        "partes": [{"es_suceso": True, "fecha": p["fecha"], "pais": incidente["lugar"]["pais"],
                    "descripcion": p["descripcion"], "coincide_con": None,
                    "fuentes": p["fuentes"]} for p in decision["partes"]],
    }  # fmt: skip


def propuestas_datos(incidente: Documento, decision: Documento) -> list[Documento]:
    enlaces = {f["id"]: f.get("enlace") for f in incidente.get("fuentes", [])}
    return [{"incidente": incidente["id"], "campo": e["dato"], "valor": e["correcto"],
             "cita": e["frase"], "enlace": enlaces.get(e["fuente_id"]),
             "motivo": f"repaso de entrada con el experto: {decision.get('motivo_es', '')}"[:300]}
            for e in decision.get("errores") or []]  # fmt: skip


def aplicar_una(ctx: control_fichas.Contexto, incidente: Documento, decision: Documento,
                hecho: Aplicado) -> bool:  # fmt: skip
    """Aplica una decisión por el camino normal. Devuelve si cambió la ficha en la base."""
    motivo = f"repaso de entrada: {decision.get('motivo_es') or ''}"[:300]
    pasos = decision.get("cambios") or []
    if UNIR in pasos:
        otra = ctx.almacen.incidente(str(decision["mismo"]))
        if otra is None or not incidentes.activo(otra):
            hecho.sin_aplicar.append(f"{incidente['id']}: {decision['mismo']} ya no está activa")
            return False
        conserva, une = reglas.mas_antiguo(otra, incidente)
        texto = f"repaso de entrada: {decision.get('motivo_mismo') or decision.get('motivo_es')}"
        control_fichas.unir(ctx.almacen, conserva, une, texto[:300], ctx.ahora, ctx.modelos)
        hecho.unidas.append(f"{une['id']}→{conserva['id']}")
        return True
    if RETIRAR in pasos:
        motivo_r = MOTIVO_RESUMEN if decision.get("resumen") else MOTIVO_FECHA
        nuevo = retirada(incidente, motivo_r, ctx.ahora)
        if not control_fichas._guardar(ctx, incidente, nuevo, motivo_r["es"]):
            hecho.sin_aplicar.append(f"{incidente['id']}: retirada sin guardar")
            return False
        ctx.almacen.anotar_motivo(TABLA_MOTIVOS, incidente["id"],
                                  {"retirado": None}, {"retirado": nuevo["retirado"]},
                                  motivo_r["es"])  # fmt: skip
        hecho.retiradas.append(incidente["id"])
        hecho.propuestas["retirar"].append({"incidente": incidente["id"], "motivo": motivo_r})
        return True
    if SEPARAR in pasos:
        hecho.propuestas["separar"].append(propuesta_separar(incidente, decision))
        return False
    cambiada = False
    if DIA in pasos:
        dia = decision["otro_dia"]
        nuevo = incidentes.aplicar_reglas(
            entrada.con_dia(incidente, dia["dia"], dia["fuente_id"], dia["frase"])
        )
        if control_fichas._guardar(ctx, incidente, nuevo, f"{motivo} (día {dia['dia']})"):
            hecho.dias.append(f"{incidente['id']} {dia['dia']}")
            cambiada = True
    if LUGAR in pasos or AUTORIDAD in pasos:
        actual = ctx.almacen.incidente(incidente["id"]) or incidente
        nuevo, propios = entrada.corregida(actual, decision)
        texto = f"repaso de entrada: {'; '.join(propios)}"
        if propios and control_fichas._guardar(ctx, actual, nuevo, texto):
            hecho.corregidas.append(f"{incidente['id']}: {'; '.join(propios)}")
            cambiada = True
    if DATO in pasos:
        hecho.propuestas["datos"] += propuestas_datos(incidente, decision)
    return cambiada


def aplicar_grupo(
    base: control_fichas.Base, grupo: str, muestreo: Documento, modelos: frozenset[str],
    reloj: Callable[[], datetime] | None = None, dormir: Callable[[float], None] | None = None,
) -> Aplicado:  # fmt: skip
    """Aplica las decisiones del grupo, solo con su muestreo aprobado (aprobado), con el cerrojo
    de la recogida y fuera de sus minutos. Lanza MuestreoNoAprobado si no lo está."""
    reloj = reloj or (lambda: datetime.now(UTC))
    dormir = dormir or time.sleep
    copia = base.abrir()
    aprobado(muestreo, copia.controles(PREFIJO), grupo)
    base.soltar(copia)
    hecho = Aplicado()
    esperar_ventana(reloj, dormir)
    with base.cerrojo():
        almacen = base.abrir()
        ahora = reloj()
        decisiones = almacen.controles(PREFIJO)
        aprobado(muestreo, decisiones, grupo)
        resultado = control_fichas.Resultado()
        llamador = control_fichas.Llamador(almacen, None, coste.Modo.REPASO_ENTRADA, ahora, None,
                                           resultado)  # fmt: skip
        ctx = control_fichas.Contexto(almacen, ahora, modelos, llamador, resultado, None, None,
                                      almacen.controles())  # fmt: skip
        nuevas: dict[str, Documento] = {}
        for id_, decision in con_cambios(decisiones, grupo).items():
            incidente = almacen.incidente(id_)
            if incidente is None or not incidentes.activo(incidente):
                hecho.sin_aplicar.append(f"{id_}: ya no está activa")
                continue
            if decision.get("huella") != entrada.huella(incidente):
                hecho.sin_aplicar.append(f"{id_}: cambió desde la decisión")
                continue
            aplicar_una(ctx, incidente, decision, hecho)
            nuevas[clave(id_)] = {**decision, "aplicada": _iso(ahora)}
        nuevas[PREFIJO_MUESTREO + grupo] = {**muestreo, "aplicado": _iso(ahora)}
        almacen.guardar_controles(nuevas, _iso(ahora))
        base.guardar(almacen)
        base.soltar(almacen)
    registro.info("repaso de entrada %s aplicado: %s", grupo, hecho.texto())
    return hecho


# --- Orden --------------------------------------------------------------------------------


def principal(base: control_fichas.Base, fabrica: Callable[[], Any] | None, accion: str,
              grupo: str, ruta: Path | None, semilla: int, tope_s: float) -> int:  # fmt: skip
    """decidir | muestra (escribe la plantilla en `ruta`) | aplicar (lee el muestreo de `ruta` y
    escribe las propuestas junto a él) | estado."""
    if accion == "decidir":
        if fabrica is None:
            return 1
        print(decidir_grupo(base, fabrica, grupo, tope_s).texto())
        return 0
    copia = base.abrir()
    decisiones = copia.controles(PREFIJO)
    if accion == "estado":
        activos = [d for d in copia.incidentes() if incidentes.activo(d)]
        estado = {
            g: {"fichas": len(del_grupo(activos, g)),
                "decididas": sum(1 for d in decisiones.values() if d.get("grupo") == g),
                "con_cambios": len(con_cambios(decisiones, g))}
            for g in GRUPOS
        }  # fmt: skip
        estado["gasto"] = copia.gastado(coste.Modo.REPASO_ENTRADA.value)  # type: ignore[assignment]
        print(json.dumps(estado, ensure_ascii=False, indent=1))
        return 0
    assert ruta is not None
    if accion == "muestra":
        ruta.write_text(json.dumps(plantilla(decisiones, grupo, semilla), ensure_ascii=False,
                                   indent=1), encoding="utf-8")  # fmt: skip
        return 0
    from recogida.extractor import modelos_base

    muestreo = json.loads(ruta.read_text(encoding="utf-8"))
    modelos = modelos_base() | frozenset(copia.vocabulario("modelo_dron"))
    base.soltar(copia)
    try:
        hecho = aplicar_grupo(base, grupo, muestreo, modelos)
    except MuestreoNoAprobado as error:
        print(f"no se aplica: {error}")
        return 3
    salida = ruta.with_name(f"aplicado_{grupo}.json")
    salida.write_text(json.dumps(hecho.__dict__, ensure_ascii=False, indent=1), encoding="utf-8")
    print(hecho.texto())
    return 0
