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
- `recalcular`: las decisiones sin aplicar de un grupo, otra vez comprobadas con las reglas de
  ahora (`ajustar`), sin llamar al experto;
- `muestra`: los cambios de un grupo elegidos al azar con una semilla, para leerlos en su fuente;
  el resultado se escribe en un fichero (`bien` de cada uno);
- `aplicar`: solo con el muestreo aprobado del grupo (las muestras que tocan, el azar de la
  semilla y como mucho una mal) y por el camino normal, con el motivo en el historial: la unión
  (queda la más antigua), el día que da una frase, la retirada de una ficha sin fecha conocida o
  que es un resumen, el lugar en el país y las autoridades no oficiales. Las separaciones y los
  datos corregidos con su frase se escriben como propuestas para configuracion/
  incidentes_revisados.json («separar», «datos», «titulares» y «retirar», que la recogida aplica
  cada hora), ya en la forma que la recogida aplica (`propuesta_dato`); las que no se pueden
  aplicar quedan en «descartadas» con su razón;
- `llevar`: añade las propuestas de un grupo aplicado a configuracion/incidentes_revisados.json
  (las que ya están no se repiten), para el PR que las publica.

Una ficha de la referencia o revisada a mano nunca se une, se retira, se separa ni cambia de día,
de lugar o de autoridad por el repaso: el cambio queda como propuesta para revisar
(`para_revisar`). Las correcciones de la presencia que contradicen lo que ya decidió una
autoridad, una rectificación o una revisión a mano no se proponen (`errores_fuera`).
"""

import contextlib
import functools
import hashlib
import json
import logging
import random
import re
import textwrap
import time
from collections.abc import Callable, Iterable, Iterator
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from almacen.base import Almacen
from esquema import Documento
from modelo import coste
from modelo import entrada as peticiones
from proceso import control_fichas as reglas
from proceso import decidir as decide
from proceso import incidentes, presencia, referencia
from proceso.focos_termicos import distancia_km
from proceso.presencia import REVISADOS, TABLA_MOTIVOS
from recogida import control_fichas, entrada
from recogida.plazo import Plazo

registro = logging.getLogger(__name__)

PREFIJO = "repaso_entrada:"
PREFIJO_MUESTREO = "repaso_entrada_muestreo:"
GRUPOS = ("a", "b", "c", "d")
# Muestras que se leen en su fuente antes de aplicar un grupo; con 2 o más mal no se aplica.
MUESTRA = {"a": 15, "b": 10, "c": 10, "d": 15}
MAX_MAL = 1
HILOS = 4
POR_TANDA = 12
# La recogida horaria toma el cerrojo hacia el minuto 17 y publica hacia el 35: el repaso no lo
# toma entre estos minutos. Empieza en el 10 porque guardar la base (con su copia) tarda hasta
# dos minutos y el cerrojo tiene que estar suelto antes del 15.
VENTANA_RECOGIDA = (10, 45)
# Una unión es imposible (mismo_imposible) si las noticias de una ficha son todas de antes del día
# firme de la otra (con este margen por la hora local), o si las dos tienen un lugar preciso a más
# de esta distancia. Muestreo del grupo a del 28 de octubre de 2026: el aeropuerto de Vilna del 25
# y del 26 de septiembre (EODI-2025-00060 y 00004) y dos drones de la misma noche en Moldavia,
# en Hîrbovăț y en Orhei (EODI-2026-00168 y 00636), salían unidos.
MARGEN_DIA_H = 3
DISTANCIA_MAX_KM = 25.0
PRECISOS = frozenset({"localidad", "instalacion"})

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


def _ultima_noticia(incidente: Documento) -> datetime | None:
    fechas = [incidentes._leer_instante(f["fecha"]) for f in incidente.get("fuentes", [])
              if f.get("fecha")]  # fmt: skip
    return max(fechas) if fechas else None


def mismo_imposible(incidente: Documento, otra: Documento) -> str | None:
    """Por qué las dos fichas no pueden ser el mismo suceso, o None: las noticias de una son
    todas de antes del día firme de la otra, sus lugares precisos están a más de
    DISTANCIA_MAX_KM o son de países distintos (cada país cuenta su incursión: el Shahed que
    cruzó Moldavia y cayó en Rumanía, EODI-2026-00171 y 00106)."""
    if incidente["lugar"]["pais"] != otra["lugar"]["pais"]:
        return f"países distintos ({incidente['lugar']['pais']} y {otra['lugar']['pais']})"
    for una, dos in ((incidente, otra), (otra, incidente)):
        if not entrada.fecha_firme(una):
            continue
        dia = reglas.instante(una).replace(hour=0, minute=0, second=0, microsecond=0)
        ultima = _ultima_noticia(dos)
        if ultima is not None and ultima < dia - timedelta(hours=MARGEN_DIA_H):
            return f"las noticias de {dos['id']} son de antes del {dia.date().isoformat()}"
    a, b = incidente["lugar"], otra["lugar"]
    if {a.get("nivel"), b.get("nivel")} <= PRECISOS and "punto" in a and "punto" in b:
        km = distancia_km(a["punto"]["lat"], a["punto"]["lon"], b["punto"]["lat"],
                          b["punto"]["lon"])  # fmt: skip
        if km > DISTANCIA_MAX_KM:
            return f"lugares a {km:.0f} km"
    return None


# --- Fichas protegidas --------------------------------------------------------------------

# Lo que el repaso no aplica nunca en una ficha protegida: queda como propuesta para revisar.
# EODI-2026-00625 (Ceuta), de la referencia con la fecha imprecisa a propósito, se retiró el 29 de
# octubre de 2026 y estuvo 25 minutos fuera de la web.
NO_EN_PROTEGIDAS = (UNIR, RETIRAR, SEPARAR, DIA, LUGAR, AUTORIDAD)
REFERENCIA = referencia.DIRECTORIO / "fichas.json"
# Lo que queda para revisar en cualquier ficha: una separación (la de EODI-2026-00292 del grupo c
# era el balance de un ministro, y la de 2025-00036 del grupo d sacaba una parte que ya es la
# ficha 2025-00084; propuesta_separar no sabe con qué ficha coincide cada parte).
SIEMPRE_PARA_REVISAR = (SEPARAR,)


@dataclass(frozen=True)
class Protegidas:
    """Las fichas protegidas (`ids`) y los valores comprobados de las de la referencia
    (`referencia`: por id, el valor de cada dato)."""

    ids: frozenset[str]
    referencia: dict[str, dict[str, Any]] = field(default_factory=dict, hash=False)


@functools.cache
def protegidas(revisados: Path = REVISADOS, ruta_referencia: Path = REFERENCIA) -> Protegidas:
    """Las fichas de la referencia (comprobadas contra el texto completo de sus fuentes) y las
    revisadas a mano: las que nombra cualquier entrada de configuracion/incidentes_revisados.json
    (también los dos lados de una unión o de unos «distintos»)."""
    fichas = json.loads(ruta_referencia.read_text(encoding="utf-8"))["fichas"]
    valores = {
        str(f["id"]): {c: (v or {}).get("valor") for c, v in (f.get("valores") or {}).items()}
        for f in fichas
    }
    ids = set(valores)
    datos = json.loads(revisados.read_text(encoding="utf-8"))
    for entradas in datos.values():
        if not isinstance(entradas, list):
            continue
        for e in entradas:
            ids.update(
                re.findall(
                    r"EODI-\d{4}-\d{5}",
                    json.dumps(
                        {
                            k: v
                            for k, v in e.items()
                            if k in ("incidente", "incidentes", "registros")
                        }
                    ),
                )
            )
    return Protegidas(frozenset(ids), valores)


def presencia_fuera(error: Documento, incidente: Documento) -> str | None:
    """Por qué una corrección de la presencia no se propone, o None: ya es la de la ficha, la
    presencia la decidió una rectificación de una autoridad («no_acreditada»,
    presencia_historial) o una revisión a mano, o baja una confirmación que una autoridad atribuye
    a drones, lo dice en su documento o confirma con pruebas físicas (proceso/presencia.py). En el
    grupo d del 29 de octubre de 2026 el experto contradijo así la referencia de Copenhague y
    Aalborg (no acreditada, EODI-2025-00154 y 00228) y la de Loviisa (confirmada, 2026-00040)."""
    actual = incidente.get("presencia_dron")
    correcto = str(error.get("correcto") or "").strip()
    if correcto == actual:
        return "es la presencia que ya tiene la ficha"
    if actual == "no_acreditada" or incidente.get("presencia_historial"):
        return "la presencia la decidió la rectificación de una autoridad"
    if incidente["id"] in presencia.presencias_revisadas():
        return "presencia revisada a mano"
    if actual == "confirmada" and (
        presencia.atribuida_por_autoridad(incidente)
        or presencia.documento_oficial_decide(incidente)
        or presencia.pruebas_fisicas_confirmadas(incidente)
    ):
        return "una autoridad confirma el dron (proceso/presencia.py)"
    return None


def drones_fuera(error: Documento, incidente: Documento) -> str | None:
    """Por qué una corrección del número de drones no se propone, o None: el número ya cabe en el
    intervalo de la ficha (EODI-2025-00192, «bis zu zehn Drohnen» con la ficha en 2-10)."""
    numero = (incidente.get("drones") or {}).get("numero")
    valor = _NUMERO.match(str(error.get("correcto") or ""))
    if not isinstance(numero, dict) or valor is None:
        return None
    minimo, maximo = int(valor.group(1)), int(valor.group(2) or valor.group(1))
    if numero.get("min", 0) <= minimo and maximo <= numero.get("max", 0):
        return "el número ya cabe en el intervalo de la ficha"
    return None


# El tipo que el repaso no quita: la interrupción sale del cierre del aeropuerto con su cita y la
# incursión, de la autoridad que dice que el dron entró desde fuera; se corrigen ahí.
TIPOS_QUE_NO_SE_QUITAN = {
    "interrupcion_aeroportuaria": "la interrupción sale del cierre del aeropuerto con su cita",
    "incursion": "la incursión sale de la autoridad que dice que el dron entró desde fuera",
}


def tipo_fuera(error: Documento, incidente: Documento) -> str | None:
    """Por qué una corrección del tipo no se propone, o None: quita la interrupción de un
    aeropuerto o una incursión (TIPOS_QUE_NO_SE_QUITAN). En Brønnøysund (EODI-2025-00094) el
    experto decía que ninguna fuente hablaba de cierre, y una lo cuenta; en Moldavia
    (2026-00372) bajaba a sobrevuelo los cinco drones que el ejército dice que cruzaron su
    espacio aéreo."""
    correcto = str(error.get("correcto") or "").strip()
    actual = incidente.get("tipo")
    if actual in TIPOS_QUE_NO_SE_QUITAN and correcto != actual:
        return TIPOS_QUE_NO_SE_QUITAN[str(actual)]
    return None


def _errores_ajustados(
    decision: Documento, incidente: Documento, valores: dict[str, Any]
) -> tuple[list[Documento], list[Documento]]:
    """(errores que se proponen, errores fuera con su razón)."""
    quedan, fuera = [], []
    for error in decision.get("errores") or []:
        razon = None
        if error.get("dato") == "presencia":
            razon = presencia_fuera(error, incidente)
        elif error.get("dato") == "drones":
            razon = drones_fuera(error, incidente)
        elif error.get("dato") == "tipo":
            razon = tipo_fuera(error, incidente)
        if razon is None:
            dato = str(error.get("dato"))
            bien = valores.get({"presencia": "presencia_dron"}.get(dato, dato))
            if bien is not None:
                razon = f"contradice la referencia ({bien})"
        if razon is None:
            quedan.append(error)
        else:
            fuera.append({**error, "razon": razon})
    return quedan, fuera


def ajustar(decision: Documento, incidente: Documento, otra: Documento | None,
            protegidas_: Protegidas | None = None) -> Documento:  # fmt: skip
    """La decisión con las comprobaciones del repaso: una autoridad solo deja de ser oficial si
    es de otro país (la que no tiene una frase con su país se queda: Skeyes en Lieja,
    EODI-2025-00092), una unión imposible (mismo_imposible) no vale, las correcciones de la
    presencia que contradicen a una autoridad o a la referencia no se proponen y en una ficha
    protegida (protegidas) lo que la cambia queda para revisar."""
    protegidas_ = protegidas() if protegidas_ is None else protegidas_
    nueva = dict(decision)
    for viejo in ("para_revisar", "errores_fuera"):
        nueva.pop(viejo, None)
    if "errores_fuera" in decision:
        nueva["errores"] = list(decision.get("errores") or []) + [
            {k: v for k, v in e.items() if k != "razon"} for e in decision["errores_fuera"]
        ]
    fuera = nueva.get("autoridades_fuera") or {}
    de_otro = {n: m for n, m in fuera.items() if "otro país" in str(m)}
    if de_otro != fuera:
        nueva["autoridades_sin_pais"] = {n: m for n, m in fuera.items() if n not in de_otro}
        nueva["autoridades_fuera"] = de_otro
    if nueva.get("mismo") and otra is not None:
        imposible = mismo_imposible(incidente, otra)
        if imposible:
            mismo = nueva.pop("mismo")
            nueva["invalida"] = f"no es el mismo suceso que {mismo}: {imposible}"
    es_protegida = incidente["id"] in protegidas_.ids or (
        otra is not None and otra["id"] in protegidas_.ids
    )
    quedan, fuera = _errores_ajustados(
        nueva, incidente, protegidas_.referencia.get(incidente["id"], {})
    )
    if fuera:
        nueva["errores"], nueva["errores_fuera"] = quedan, fuera
    pasos = cambios(nueva, incidente)
    revisar = NO_EN_PROTEGIDAS if es_protegida else SIEMPRE_PARA_REVISAR
    if any(p in revisar for p in pasos):
        nueva["para_revisar"] = [p for p in pasos if p in revisar]
        pasos = [p for p in pasos if p not in revisar]
    nueva["cambios"] = pasos
    return nueva


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


@contextlib.contextmanager
def cerrojo_fuera_de_la_recogida(
    base: control_fichas.Base, reloj: Callable[[], datetime], dormir: Callable[[float], None]
) -> Iterator[None]:
    """El cerrojo de la base, fuera de los minutos de la recogida también después de tomarlo: si
    otro lo tenía y se ha entrado en la ventana mientras se esperaba, se suelta y se espera
    (28 de octubre de 2026: se tomó a las 18:10 y se guardó a las 18:12)."""
    while True:
        esperar_ventana(reloj, dormir)
        with base.cerrojo():
            desde, hasta = VENTANA_RECOGIDA
            if not desde <= reloj().minute < hasta:
                yield
                return
        registro.info("repaso de entrada: cerrojo tomado dentro de la ventana; se suelta")


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


def _por_decidir(decision: Documento, incidente: Documento, solo: list[str] | None) -> bool:
    """Sin decisión con la huella de ahora; o, si se dan las fichas (`solo`), decidida con una
    pregunta anterior y sin aplicar: se vuelve a preguntar con la de ahora."""
    if decision.get("huella") != entrada.huella(incidente):
        return True
    return (
        solo is not None
        and decision.get("version") != peticiones.VERSION_REPASO
        and not decision.get("aplicada")
    )


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
                      and _por_decidir(decisiones.get(clave(d["id"])) or {}, d, solo)]  # fmt: skip
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
        with cerrojo_fuera_de_la_recogida(base, reloj, dormir):
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
        otra = por_id.get(str(decision.get("mismo"))) if decision.get("mismo") else None
        nuevas[clave(incidente["id"])] = ajustar({
            **decision, "version": peticiones.VERSION_REPASO, "fecha": _iso(ahora),
            "grupo": grupo_de(incidente), "huella": entrada.huella(incidente),
            "conjunto": len(pregunta.elegidas),
        }, incidente, otra)  # fmt: skip
    return nuevas, llamadas


def recalcular(
    base: control_fichas.Base, grupo: str, reloj: Callable[[], datetime] | None = None,
    dormir: Callable[[float], None] | None = None,
) -> int:  # fmt: skip
    """Vuelve a comprobar (ajustar) las decisiones sin aplicar del grupo con las reglas de ahora,
    sin preguntar otra vez al experto. Devuelve cuántas cambian. Después hace falta otro
    muestreo: la huella del grupo cambia."""
    reloj = reloj or (lambda: datetime.now(UTC))
    dormir = dormir or time.sleep
    with cerrojo_fuera_de_la_recogida(base, reloj, dormir):
        almacen = base.abrir()
        nuevas: dict[str, Documento] = {}
        for k, decision in almacen.controles(PREFIJO).items():
            if decision.get("grupo") != grupo or decision.get("aplicada"):
                continue
            incidente = almacen.incidente(k.removeprefix(PREFIJO))
            if incidente is None:
                continue
            mismo = decision.get("mismo")
            otra = almacen.incidente(str(mismo)) if mismo else None
            nueva = ajustar(decision, incidente, otra)
            if nueva != decision:
                nuevas[k] = nueva
        if nuevas:
            almacen.guardar_controles(nuevas, _iso(reloj()))
            base.guardar(almacen)
        base.soltar(almacen)
    registro.info("repaso de entrada %s: %d decisiones recalculadas", grupo, len(nuevas))
    return len(nuevas)


# --- Muestra ------------------------------------------------------------------------------


def con_cambios(decisiones: dict[str, Documento], grupo: str,
                tanda: Iterable[str] | None = None) -> dict[str, Documento]:  # fmt: skip
    """Las decisiones del grupo que cambian algo y aún no se han aplicado, por id; solo las de la
    tanda si se da (las fichas de un grupo se aplican por tandas)."""
    solo = None if tanda is None else set(tanda)
    return {
        k.removeprefix(PREFIJO): d
        for k, d in sorted(decisiones.items())
        if d.get("grupo") == grupo
        and d.get("cambios")
        and not d.get("aplicada")
        and (solo is None or k.removeprefix(PREFIJO) in solo)
    }


def huella_grupo(elegidas: dict[str, Documento]) -> str:
    texto = json.dumps({i: (d.get("huella"), d.get("cambios"), d.get("errores"))
                        for i, d in elegidas.items()},
                       sort_keys=True, ensure_ascii=False)  # fmt: skip
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()[:16]


def muestra(decisiones: dict[str, Documento], grupo: str, semilla: int,
            tanda: Iterable[str] | None = None) -> list[str]:  # fmt: skip
    """Las fichas del muestreo de un grupo (o de su tanda): al azar con la semilla, las que tocan
    (todas si son menos)."""
    elegidas = sorted(con_cambios(decisiones, grupo, tanda))
    return sorted(random.Random(semilla).sample(elegidas, min(MUESTRA[grupo], len(elegidas))))


def plantilla(decisiones: dict[str, Documento], grupo: str, semilla: int,
              tanda: Iterable[str] | None = None) -> Documento:  # fmt: skip
    """El fichero del muestreo para rellenar: cada ficha con lo que cambia y su frase."""
    solo = None if tanda is None else sorted(tanda)
    elegidas = con_cambios(decisiones, grupo, solo)
    return {
        "grupo": grupo, "semilla": semilla, "huella": huella_grupo(elegidas), "tanda": solo,
        "revisadas": [
            {"id": i, "cambios": elegidas[i]["cambios"], "bien": None, "nota": "",
             "decision": {k: elegidas[i].get(k) for k in (
                 "mismo", "motivo_mismo", "otro_dia", "frase_fecha", "frase_lugar",
                 "autoridades_fuera", "fecha_desconocida", "resumen", "partes", "errores",
                 "motivo_es")}}
            for i in muestra(decisiones, grupo, semilla, solo)
        ],
    }  # fmt: skip


class MuestreoNoAprobado(RuntimeError):
    pass


def aprobado(muestreo: Documento, decisiones: dict[str, Documento], grupo: str) -> None:
    """Lanza MuestreoNoAprobado si el muestreo no deja aplicar el grupo: otro grupo, decisiones
    cambiadas desde el muestreo, una muestra que no es la de la semilla, alguna sin leer o dos o
    más mal."""
    tanda = muestreo.get("tanda")
    elegidas = con_cambios(decisiones, grupo, tanda)
    if muestreo.get("grupo") != grupo:
        raise MuestreoNoAprobado(f"el muestreo es del grupo {muestreo.get('grupo')}")
    if muestreo.get("huella") != huella_grupo(elegidas):
        raise MuestreoNoAprobado("las decisiones del grupo cambiaron desde el muestreo")
    revisadas = muestreo.get("revisadas") or []
    ids = sorted(str(r.get("id")) for r in revisadas)
    if ids != muestra(decisiones, grupo, int(muestreo.get("semilla", -1)), tanda):
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
        default_factory=lambda: {
            s: [] for s in ("separar", "datos", "titulares", "retirar", "descartadas")
        }
    )
    sin_aplicar: list[str] = field(default_factory=list)

    def texto(self) -> str:
        return (f"unidas={len(self.unidas)} dias={len(self.dias)} "
                f"retiradas={len(self.retiradas)} corregidas={len(self.corregidas)} "
                f"separar={len(self.propuestas['separar'])} datos={len(self.propuestas['datos'])} "
                f"titulares={len(self.propuestas['titulares'])} "
                f"descartadas={len(self.propuestas['descartadas'])} "
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


# Las propuestas del 28 de octubre de 2026 (grupos a y b) traían el tipo «interrupción» y la
# presencia como «datos», que la recogida no aplica, y valores libres («derribo», «1 dron
# confirmado; un segundo…»): había que reescribirlas a mano. Ahora salen en la forma que se aplica.
PRESENCIAS = ("confirmada", "no_confirmada", "no_acreditada")
_NUMERO = re.compile(r"^\s*(\d+)\s*(?:(?:-|–|a|to)\s*(\d+))?\s*$")
MAX_PALABRAS_CITA = 25


def _descartada(base: Documento, razon: str) -> tuple[str, Documento]:
    return "descartadas", {**base, "razon": razon}


def propuesta_dato(incidente: Documento, decision: Documento,
                   error: Documento) -> tuple[str, Documento]:  # fmt: skip
    """(sección de configuracion/incidentes_revisados.json, entrada) de un dato corregido, o
    («descartadas», entrada con su razón) si no se puede aplicar tal cual."""
    enlaces = {f["id"]: f.get("enlace") for f in incidente.get("fuentes", [])}
    dato, valor = str(error["dato"]), str(error["correcto"]).strip()
    frase = str(error.get("frase") or "").strip()
    motivo = f"repaso de entrada con el experto: {decision.get('motivo_es', '')}"[:300]
    base: Documento = {
        "incidente": incidente["id"], "campo": dato, "valor": valor, "cita": frase,
        "enlace": enlaces.get(error.get("fuente_id")),
        "pais": (incidente.get("lugar") or {}).get("pais"), "motivo": motivo,
    }  # fmt: skip
    if not base["enlace"] or not frase:
        return _descartada(base, "sin la fuente o sin la frase que lo dice")
    if len(frase.split()) > MAX_PALABRAS_CITA:
        return _descartada(base, f"la cita pasa de {MAX_PALABRAS_CITA} palabras")
    if dato == "tipo":
        if valor == "interrupcion_aeroportuaria":
            return "datos", {**base, "campo": "cierre", "valor": "si"}
        if valor in decide.TIPOS_REVISABLES:
            return "datos", base
        return _descartada(base, f"«{valor}» no es un tipo de la ficha")
    if dato == "drones":
        numero = _NUMERO.match(valor)
        if numero is None:
            return _descartada(base, "el número de drones no es un número ni un intervalo")
        minimo = int(numero.group(1))
        maximo = int(numero.group(2) or minimo)
        if minimo < 1 or maximo < minimo:
            return _descartada(base, "el intervalo de drones no vale")
        return "datos", {**base, "valor": {"min": minimo, "max": maximo}}
    if dato == "presencia":
        if valor not in PRESENCIAS:
            return _descartada(base, f"«{valor}» no es una presencia de la ficha")
        return "titulares", {
            "incidente": incidente["id"],
            "presencia": {"valor": valor, "cita": frase, "enlace": base["enlace"]},
            "motivo": {"es": motivo, "en": f"entry review: {decision.get('motivo_en', '')}"[:300]},
        }
    return _descartada(base, "el estado lo decide proceso/decidir.py con las pruebas de la ficha: "
                             "se corrige con su cita en «citas»")  # fmt: skip


def propuestas_datos(incidente: Documento, decision: Documento) -> list[tuple[str, Documento]]:
    return [propuesta_dato(incidente, decision, e) for e in decision.get("errores") or []]


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
        if control_fichas.unir(ctx.almacen, conserva, une, texto[:300], ctx.ahora,
                               ctx.modelos) is None:  # fmt: skip
            hecho.sin_aplicar.append(f"{incidente['id']}: dada por distinta de {otra['id']}")
            return False
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
        for seccion, propuesta in propuestas_datos(incidente, decision):
            hecho.propuestas[seccion].append(propuesta)
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
    with cerrojo_fuera_de_la_recogida(base, reloj, dormir):
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
        for id_, decision in con_cambios(decisiones, grupo, muestreo.get("tanda")).items():
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


# --- Llevar las propuestas a la configuración -----------------------------------------------


def _clave_propuesta(seccion: str, propuesta: Documento) -> tuple[str, ...]:
    if seccion == "datos":
        return (str(propuesta["incidente"]), str(propuesta["campo"]))
    return (str(propuesta["incidente"]),)


def llevar(propuestas: dict[str, list[Documento]], ruta: Path = REVISADOS) -> dict[str, int]:
    """Añade las propuestas a configuracion/incidentes_revisados.json, al final de su sección y sin
    tocar el resto del fichero; las que ya tienen entrada (el mismo incidente, y el mismo dato en
    «datos») no se repiten. Devuelve cuántas añade por sección."""
    texto = ruta.read_text(encoding="utf-8")
    datos = json.loads(texto)
    añadidas: dict[str, int] = {}
    for seccion in ("retirar", "titulares", "separar", "datos"):
        tiene = {_clave_propuesta(seccion, e) for e in datos.get(seccion, [])}
        nuevas: list[Documento] = []
        for propuesta in propuestas.get(seccion, []):
            clave_ = _clave_propuesta(seccion, propuesta)
            if clave_ not in tiene:
                tiene.add(clave_)
                nuevas.append({k: v for k, v in propuesta.items() if v is not None})
        añadidas[seccion] = len(nuevas)
        if not nuevas:
            continue
        inicio = re.search(rf'\n  "{seccion}": \[', texto)
        if inicio is None:
            raise ValueError(f"sin la sección «{seccion}» en {ruta}")
        fin = texto.index("\n  ]", inicio.end())
        bloque = ",\n".join(textwrap.indent(json.dumps(e, ensure_ascii=False, indent=2), "    ")
                            for e in nuevas)  # fmt: skip
        separador = ",\n" if datos.get(seccion) else "\n"
        texto = texto[:fin] + separador + bloque + texto[fin:]
    nuevo = json.loads(texto)
    for seccion, cuantas in añadidas.items():
        assert len(nuevo.get(seccion, [])) == len(datos.get(seccion, [])) + cuantas, seccion
    ruta.write_text(texto, encoding="utf-8", newline="")
    return añadidas


# --- Orden --------------------------------------------------------------------------------


def principal(base: control_fichas.Base, fabrica: Callable[[], Any] | None, accion: str,
              grupo: str, ruta: Path | None, semilla: int, tope_s: float,
              tanda: Path | None = None) -> int:  # fmt: skip
    """decidir | muestra (escribe la plantilla en `ruta`) | aplicar (lee el muestreo de `ruta` y
    escribe las propuestas junto a él) | llevar (las propuestas escritas junto a `ruta`, a
    configuracion/incidentes_revisados.json) | estado."""
    if accion == "llevar":
        assert ruta is not None
        hecho = json.loads(ruta.with_name(f"aplicado_{grupo}.json").read_text(encoding="utf-8"))
        print(json.dumps(llevar(hecho["propuestas"]), ensure_ascii=False))
        return 0
    if accion == "decidir":
        if fabrica is None:
            return 1
        solo = None if tanda is None else json.loads(tanda.read_text(encoding="utf-8"))
        print(decidir_grupo(base, fabrica, grupo, tope_s, solo=solo).texto())
        return 0
    if accion == "recalcular":
        print(f"recalculadas={recalcular(base, grupo)}")
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
        solo = None if tanda is None else json.loads(tanda.read_text(encoding="utf-8"))
        ruta.write_text(json.dumps(plantilla(decisiones, grupo, semilla, solo),
                                   ensure_ascii=False, indent=1), encoding="utf-8")  # fmt: skip
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
