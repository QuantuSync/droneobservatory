"""Seguimiento barato de las rectificaciones oficiales de la presencia del dron.

Lo que cambia y cómo se enseña está en proceso/rectificaciones.py; aquí, de dónde salen y quién
decide (docs/rectificaciones.md):

- **Revisadas a mano** (`configuracion/rectificaciones_oficiales.json`): la declaración oficial,
  literal, con su enlace, su fecha y el texto en español y en inglés que enseña la ficha.
- **En cada recogida horaria**: las fuentes de los incidentes ya publicados que suenan a
  retractación o a cierre oficial de una investigación, en cualquier idioma («no evidence»,
  «cannot confirm», «investigation closed», «was a helicopter»…, `senales_rectificacion.json`) y
  son al menos de un día después del suceso. Como mucho `MAX_POR_PASADA` por recogida.
- **Una vez al mes**: los titulares guardados de después de cada incidente con la presencia
  confirmada de más de un mes que nombran su lugar y suenan a rectificación; el modelo base dice
  cuáles merecen la pregunta, con un tope de `TOPE_MENSUAL_USD` por pasada.
- **Cada día, desde la segunda lectura** (docs/segunda_lectura.md): lo mismo sobre todo lo
  publicado con la presencia confirmada, no confirmada o no acreditada de al menos un día, con el
  modelo secundario. Lo que elige entra en la misma cola que lo de la búsqueda mensual (`encolar`)
  y el experto lo paga con el modo «segunda_lectura» (0,30 dólares al día, nunca de la reserva).

Todo pasa por el experto antes de cambiar nada (nunca se rebaja una presencia sin él): sin experto
configurado, o con su tope del día agotado, se espera a la recogida siguiente y la ficha sigue como
estaba. La decisión del experto se guarda (control de las fichas, clave `rectificacion:…`) y no se
repite. El cambio a «no acreditado» no genera aviso. Nada de esto impide publicar ni retirar: el
paso va aislado, con su tope de tiempo, y un fallo solo queda en el registro.
"""

import argparse
import hashlib
import json
import logging
import re
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from functools import cache
from pathlib import Path
from typing import Any

from almacen.base import Almacen, DocumentoInvalido
from esquema import Documento
from modelo import coste, modelos
from modelo import rectificacion as peticion
from modelo.cliente import LlamadaFallida
from modelo.control import RespuestaInvalida, leer, letras
from proceso import rectificaciones
from proceso.incidentes import activo
from proceso.presencia import TABLA_MOTIVOS
from recogida import revisados
from recogida.plazo import Plazo, TiempoAgotado

registro = logging.getLogger(__name__)
RUTA = Path(__file__).resolve().parent.parent / "configuracion" / "rectificaciones_oficiales.json"
PREFIJO = "rectificacion:"
CURSOR_MENSUAL = "rectificaciones:mensual"
TOPE_S = 150
# Llamadas al experto por recogida horaria con lo detectado (las revisadas a mano van siempre).
MAX_POR_PASADA = 4
# Una fuente del mismo día del suceso que lo deja abierto no rectifica nada: la presencia ya la
# decidió la ficha. Desde un día después.
DIAS_DESDE_EL_SUCESO = 1
# Búsqueda mensual: incidentes confirmados de más de un mes, titulares por incidente y tope.
DIAS_MENSUAL = 30
TOPE_MENSUAL_USD = 0.30
MOTIVO_ESCALADO = "publicada: rectificación oficial de la presencia"
# Lo que entra en la cola desde el barrido diario de la segunda lectura.
ORIGEN_SEGUNDA = "segunda_lectura"
# Lo que desmiente una autoridad en una ficha atribuida por otra, desde la verificación de las
# fichas (recogida/control_fichas.py): lo paga el modo de las rectificaciones.
ORIGEN_VERIFICACION = "verificacion"
# Presencias que puede rectificar el barrido diario y antigüedad mínima (días).
PRESENCIAS_DIARIAS = frozenset({"confirmada", "no_confirmada", "no_acreditada"})
_FECHA = re.compile(r"^\d{4}-\d{2}-\d{2}$")


@cache
def cargar(ruta: Path = RUTA) -> dict[str, Any]:
    datos: dict[str, Any] = json.loads(ruta.read_text(encoding="utf-8"))
    return datos


@dataclass
class Propuesta:
    clave: str
    incidente: str
    origen: str  # revisada, recogida o mensual
    fuente: Documento
    texto: str
    esperado: str | None = None
    revision: Documento | None = None
    # Lo que eligió la segunda lectura lo paga el experto con su modo (modelo/coste.py).
    modo: coste.Modo = coste.Modo.RECTIFICACIONES


@dataclass
class Hechos:
    aplicadas: list[str] = field(default_factory=list)
    rechazadas: list[str] = field(default_factory=list)
    esperan: list[str] = field(default_factory=list)
    sin_guardar: list[str] = field(default_factory=list)
    detectadas: int = 0
    mensual: Documento = field(default_factory=dict)
    gasto_experto: float = 0.0

    def texto(self) -> str:
        return (
            f"aplicadas {self.aplicadas}, rechazadas {len(self.rechazadas)}, esperan al experto "
            f"{len(self.esperan)}, detectadas {self.detectadas}, sin guardar {self.sin_guardar}, "
            f"experto {self.gasto_experto:.4f} USD"
            + (f", mensual {self.mensual}" if self.mensual else "")
        )


def _iso(momento: datetime) -> str:
    return momento.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _instante(momento: datetime) -> Documento:
    return {"valor": momento.astimezone(UTC).strftime("%Y-%m-%dT%H:%MZ"), "precision": "minuto"}


def _leer(valor: str) -> datetime:
    return datetime.fromisoformat(valor.replace("Z", "+00:00"))


def huella(texto: str) -> str:
    return hashlib.sha256(" ".join(texto.split()).encode("utf-8")).hexdigest()[:16]


def ficha(incidente: Documento) -> dict[str, Any]:
    """Lo que ve el experto de la ficha publicada."""
    nombres = incidente.get("nombres") or {}
    cierre = ((incidente.get("consecuencias") or {}).get("cierre") or {}).get("valor")
    return {
        "id": incidente["id"],
        "titular": (incidente.get("titulo") or {}).get("es", ""),
        "inicio": incidente["tiempo"]["inicio"]["valor"],
        "pais": (incidente.get("lugar") or {}).get("pais", ""),
        "lugar": (nombres.get("lugar") or {}).get("es") or incidente["lugar"].get("localidad", ""),
        "objetivo": (incidente.get("objetivo") or {}).get("nombre", ""),
        "estado": incidente["estado"]["actual"],
        "presencia del dron": incidente.get("presencia_dron"),
        "cierre": cierre or "desconocido",
    }


# --- De dónde salen las propuestas --------------------------------------------------------


def revisadas(almacen: Almacen) -> list[Propuesta]:
    """Las rectificaciones revisadas a mano, con la fuente oficial que llevan."""
    resultado = []
    for entrada in cargar().get("rectificaciones", []):
        incidente = revisados._vivo(almacen, entrada["incidente"])
        if incidente is None:
            continue
        fuente = revisados.fuente_de_cita(entrada["fuente"], incidente)
        resultado.append(Propuesta(
            clave=f"revisada:{entrada['incidente']}:{fuente['id']}",
            incidente=incidente["id"], origen="revisada", fuente=fuente,
            texto=" ".join([entrada["fuente"]["frase"], entrada.get("contexto", "")]).strip(),
            esperado=entrada["tipo"], revision=entrada,
        ))  # fmt: skip
    return resultado


def _publicadas(almacen: Almacen) -> list[Documento]:
    """Los incidentes vigentes cuya presencia puede rectificarse (no los ya descartados)."""
    return [
        i for i in almacen.incidentes()
        if activo(i) and i.get("presencia_dron") in ("confirmada", "no_confirmada", "no_acreditada")
    ]  # fmt: skip


def detectadas(almacen: Almacen, decididas: set[str]) -> list[Propuesta]:
    """Las fuentes de los incidentes publicados que suenan a rectificación oficial y aún no ha
    visto el experto, de las más recientes a las más antiguas. La de una autoridad cuenta desde
    el primer día («an investigation showed no drone was detected on radar and that the object
    was likely a balloon», la Marechaussee el mismo día del cierre de Schiphol, EODI-2025-00203),
    y también la que desmintió el incidente aunque no suene a rectificación (EODI-2025-00357,
    «Ces recherches n'avaient permis de retrouver aucun drone»): el experto lee si niega el dron.
    """
    resultado = []
    for incidente in _publicadas(almacen):
        desde = _leer(incidente["tiempo"]["inicio"]["valor"]) + timedelta(DIAS_DESDE_EL_SUCESO)
        historial = incidente.get("presencia_historial") or []
        citadas = {p["fuente_id"] for p in historial}
        rectificada = len(historial) > 1
        if rectificada:
            # Lo de antes de la última rectificación (y de su mismo día) ya está decidido.
            desde = max(desde, _leer(historial[-1]["fecha"]["valor"]) + timedelta(1))
        pasos = incidente["estado"]["historial"]
        desmiente = (
            str(pasos[-1].get("fuente_id"))
            if incidente["estado"]["actual"] == "desmentido"
            else None
        )
        for fuente in incidente["fuentes"]:
            clave = f"fuente:{incidente['id']}:{fuente['id']}"
            autoridad = bool(fuente.get("es_autoridad")) and not rectificada
            if (
                clave in decididas
                or fuente["id"] in citadas
                or (_leer(fuente["fecha"]["valor"]) < desde and not autoridad)
            ):
                continue
            frase = str(fuente.get("frase_origen") or "")
            if rectificaciones.senal(frase) is None and not (
                autoridad and fuente["id"] == desmiente
            ):
                continue
            resultado.append(Propuesta(clave, incidente["id"], "recogida", fuente, frase))
    resultado.sort(key=lambda p: (p.fuente["fecha"]["valor"], p.clave), reverse=True)
    return resultado


# --- El experto ---------------------------------------------------------------------------


class Experto:
    """Las llamadas directas al experto, dentro de su tope del día (nunca de la reserva crítica:
    una rectificación puede esperar a la recogida siguiente y no quita sitio a lo urgente)."""

    def __init__(self, almacen: Almacen, fabrica: Callable[[], Any] | None, ahora: datetime,
                 plazo: Plazo | None, hechos: Hechos) -> None:  # fmt: skip
        self.almacen, self.fabrica, self.ahora = almacen, fabrica, ahora
        self.plazo, self.hechos = plazo, hechos
        self._cliente: Any = None
        self.parado: str | None = None

    def cliente(self) -> Any:
        if self._cliente is None and self.fabrica is not None and modelos.experto():
            servicio = self.fabrica()
            experto = getattr(servicio, "experto", None)
            self._cliente = experto() if callable(experto) else None
        return self._cliente

    def llamar(self, cuerpo: dict[str, Any], clave: str,
               modo: coste.Modo = coste.Modo.RECTIFICACIONES) -> dict[str, Any] | None:  # fmt: skip
        """La respuesta leída del experto, o None si hoy no puede (queda esperando). Lo que
        marcó la segunda lectura cabe además en su modo; si no, espera sin parar lo demás."""
        if self.parado:
            return None
        cliente = self.cliente()
        if cliente is None:
            self.parado = "sin experto"
            return None
        modelo = str(getattr(cliente, "modelo", "") or modelos.experto())
        previsto = coste.peor_caso(letras(cuerpo), peticion.MAX_SALIDA, modelo=modelo,
                                   esfuerzo=peticion.ESFUERZO)  # fmt: skip
        try:
            if self.plazo is not None:
                self.plazo.comprobar()
            dia = coste.dia(self.ahora)
            mes = coste.del_mes(self.almacen, self.ahora, modelo)
            if modo == coste.Modo.SEGUNDA_LECTURA:
                try:
                    coste.comprobar_segunda(
                        self.almacen.gastado_modelo(modelo, dia),
                        self.almacen.gastado_experto_en(modo.value, dia), previsto, self.ahora,
                        mes,
                    )  # fmt: skip
                except coste.LimiteGasto:
                    return None
            coste.comprobar_experto(self.almacen.gastado_modelo(modelo, dia), previsto,
                                    critico=False, mes=mes)  # fmt: skip
            respuesta = cliente.mensaje(cuerpo)
        except (coste.LimiteGasto, TiempoAgotado) as error:
            self.parado = str(error)[:200]
            return None
        except LlamadaFallida as error:
            self.parado = f"experto: {str(error)[:150]}"
            return None
        uso = coste.Uso.de_mensaje(respuesta)
        gasto = uso.coste()
        self.almacen.registrar_llamada({
            "fecha": _iso(self.ahora), "modo": modo.value,
            "candidato": (PREFIJO + clave)[:200], "lote": False, "entrada": uso.entrada,
            "salida": uso.salida, "escritura_cache": uso.escritura_cache,
            "lectura_cache": uso.lectura_cache, "coste": gasto, "modelo": uso.modelo,
            "escalada": True,
        })  # fmt: skip
        self.hechos.gasto_experto += gasto
        try:
            return leer(respuesta)
        except RespuestaInvalida:
            return {}


def decidir(experto: Experto, propuesta: Propuesta, incidente: Documento) -> Documento | None:
    """La decisión del experto sobre la propuesta, comprobada; None si espera."""
    fuente = propuesta.fuente
    cuerpo = peticion.cuerpo(ficha(incidente), str(fuente.get("medio", "")),
                             fuente["fecha"]["valor"][:10], str(fuente.get("idioma") or ""),
                             propuesta.texto)  # fmt: skip
    respuesta = experto.llamar(cuerpo, propuesta.clave, propuesta.modo)
    if respuesta is None:
        return None
    tipo, motivo = rectificaciones.decision_valida(respuesta, propuesta.texto, propuesta.esperado)
    return {
        "origen": propuesta.origen,
        "incidente": propuesta.incidente,
        "fuente_id": fuente["id"],
        "huella": huella(propuesta.texto),
        "esperado": propuesta.esperado,
        "fecha": _iso(experto.ahora),
        "version": peticion.VERSION,
        "motivo_escalado": MOTIVO_ESCALADO,
        "tipo": tipo,
        "motivo": motivo,
        "respuesta": respuesta,
    }


# --- Aplicar ------------------------------------------------------------------------------


def _fecha_de(decision: Documento, propuesta: Propuesta) -> Documento:
    revision = propuesta.revision or {}
    dia = str(revision.get("fecha_declaracion") or (decision.get("respuesta") or {}).get("fecha")
              or "")  # fmt: skip
    if _FECHA.match(dia):
        return {"valor": f"{dia}T00:00Z", "precision": "dia"}
    return dict(propuesta.fuente["fecha"])


def _textos(decision: Documento, propuesta: Propuesta) -> tuple[Documento, Documento]:
    """Quién y qué dijo, en español y en inglés: los revisados a mano, si los hay; si no, los
    del experto."""
    revision = propuesta.revision or {}
    respuesta = decision.get("respuesta") or {}
    quien = revision.get("quien") or {"es": respuesta["quien_es"], "en": respuesta["quien_en"]}
    motivo = revision.get("motivo") or {"es": respuesta["motivo_es"], "en": respuesta["motivo_en"]}
    return quien, motivo


def aplicar(almacen: Almacen, propuesta: Propuesta, decision: Documento, ahora: datetime,
            vocabulario: frozenset[str], hechos: Hechos) -> None:  # fmt: skip
    incidente = revisados._vivo(almacen, propuesta.incidente)
    if incidente is None or rectificaciones.aplicada(incidente, PREFIJO + propuesta.clave):
        return
    quien, motivo = _textos(decision, propuesta)
    anterior = (propuesta.revision or {}).get("anterior") or {}
    nuevo = rectificaciones.aplicar(
        incidente, str(decision["tipo"]), propuesta.fuente, _fecha_de(decision, propuesta), quien,
        motivo, PREFIJO + propuesta.clave, anterior.get("quien"), anterior.get("valor"),
    )  # fmt: skip
    if nuevo is incidente:
        return
    nuevo = {**nuevo, "control": {**nuevo["control"], "ultima_actualizacion": _instante(ahora)}}
    try:
        almacen.guardar_incidente(nuevo, ahora, vocabulario)
    except DocumentoInvalido as error:
        registro.warning("rectificación sin guardar en %s: %s", incidente["id"], str(error)[:300])
        hechos.sin_guardar.append(incidente["id"])
        return
    campos = ("presencia_dron", "presencia_historial", "titulo", "fuentes")
    antes = {c: incidente.get(c) for c in campos if incidente.get(c) != nuevo.get(c)}
    if antes:
        texto = (f"rectificación oficial ({decision['tipo']}, {propuesta.origen}, decidida por el "
                 f"experto): {quien['es']}, {motivo['es']}")  # fmt: skip
        almacen.anotar_motivo(TABLA_MOTIVOS, incidente["id"], antes,
                              {c: nuevo.get(c) for c in antes}, texto)  # fmt: skip
    if antes.keys() & {"presencia_dron", "presencia_historial"}:
        hechos.aplicadas.append(f"{incidente['id']} {decision['tipo']}")


def cambio_revisado(decision: Documento, propuesta: Propuesta) -> bool:
    """La revisión a mano cambió desde que decidió el experto: otro texto, u otro tipo esperado
    que la decisión no cumple (las decisiones de antes del 26 de octubre de 2026 no guardaban el
    tipo esperado: la de Auvere, leída «ninguna» cuando se esperaba «parcial», se vuelve a
    preguntar al revisarla como cierre_sin_cambio)."""
    if decision.get("huella") != huella(propuesta.texto):
        return True
    if "esperado" in decision:
        return bool(decision["esperado"] != propuesta.esperado)
    return decision.get("tipo") != propuesta.esperado


def revisar(almacen: Almacen, experto: Experto, propuestas: list[Propuesta], ahora: datetime,
            vocabulario: frozenset[str], hechos: Hechos, nuevas_max: int | None = None
            ) -> None:  # fmt: skip
    """Pide al experto lo que aún no ha decidido (como mucho `nuevas_max`) y aplica lo que
    aceptó, también lo aceptado antes que no se pudo guardar."""
    decisiones = almacen.controles(PREFIJO)
    nuevas: dict[str, Documento] = {}
    for propuesta in propuestas:
        incidente = revisados._vivo(almacen, propuesta.incidente)
        if incidente is None:
            continue
        decision = decisiones.get(PREFIJO + propuesta.clave)
        if (
            decision is not None
            and propuesta.origen == "revisada"
            and cambio_revisado(decision, propuesta)
        ):
            decision = None  # la revisión a mano cambió el texto o el tipo: se vuelve a preguntar
        if decision is None:
            if nuevas_max is not None and len(nuevas) >= nuevas_max:
                continue
            decision = decidir(experto, propuesta, incidente)
            if decision is None:
                hechos.esperan.append(propuesta.clave)
                continue
            nuevas[PREFIJO + propuesta.clave] = decision
            if decision.get("tipo") not in rectificaciones.TIPOS:
                hechos.rechazadas.append(f"{propuesta.clave}: {decision.get('motivo')}")
        if decision.get("tipo") in rectificaciones.TIPOS:
            aplicar(almacen, _con_frase(propuesta, decision), decision, ahora, vocabulario, hechos)
    if nuevas:
        almacen.guardar_controles(nuevas, _iso(ahora))


# --- Búsqueda mensual ---------------------------------------------------------------------


def _nombres(incidente: Documento) -> list[str]:
    """Cómo pueden nombrar las noticias el lugar del incidente."""
    nombres = incidente.get("nombres") or {}
    candidatos = [
        (incidente.get("objetivo") or {}).get("nombre"),
        (incidente.get("objetivo") or {}).get("oaci"),
        incidente["lugar"].get("localidad"),
        *((nombres.get("objetivo") or {}).values()),
        *((nombres.get("localidad") or {}).values()),
    ]
    return sorted({str(n).casefold() for n in candidatos if n and len(str(n)) >= 4})


def nombran_el_lugar(incidente: Documento, articulos: list[Documento],
                     dias_desde_el_suceso: int) -> list[Documento]:  # fmt: skip
    """Los artículos posteriores al suceso (desde `dias_desde_el_suceso` días después) que no son
    fuentes del incidente y nombran su lugar en el titular (la selección del barrido; la reutiliza
    la búsqueda de declaraciones de la segunda lectura)."""
    inicio = _leer(incidente["tiempo"]["inicio"]["valor"])
    nombres = _nombres(incidente)
    tiene = {f.get("enlace") for f in incidente["fuentes"]}
    posterior = (inicio + timedelta(dias_desde_el_suceso)).strftime("%Y-%m-%dT%H:%M")
    return [
        a for a in articulos
        if a["fecha"] >= posterior and a["url"] not in tiene
        and any(n in str(a["titular"]).casefold() for n in nombres)
    ]  # fmt: skip


def titulares_mensuales(
    almacen: Almacen, ahora: datetime, desde: str,
    presencias: frozenset[str] = frozenset({"confirmada"}), dias: int = DIAS_MENSUAL,
) -> dict[str, list[Documento]]:  # fmt: skip
    """Por incidente confirmado de más de un mes, los titulares guardados desde `desde` y desde
    un día después del suceso que nombran su lugar y suenan a rectificación. El barrido diario de
    la segunda lectura pide otras presencias y otra antigüedad (`presencias`, `dias`)."""
    filas = almacen._conexion.execute(
        "SELECT url, medio, fecha, idioma, titular FROM articulos WHERE fecha >= ? ORDER BY fecha",
        (desde,),
    ).fetchall()
    articulos = [
        dict(zip(("url", "medio", "fecha", "idioma", "titular"), f, strict=True)) for f in filas
        if rectificaciones.senal(str(f[4])) is not None
    ]  # fmt: skip
    limite = ahora - timedelta(dias)
    resultado: dict[str, list[Documento]] = {}
    for incidente in almacen.incidentes():
        if not activo(incidente) or incidente.get("presencia_dron") not in presencias:
            continue
        inicio = _leer(incidente["tiempo"]["inicio"]["valor"])
        if inicio > limite:
            continue
        elegidos = nombran_el_lugar(incidente, articulos, DIAS_DESDE_EL_SUCESO)
        if elegidos:
            resultado[incidente["id"]] = elegidos[-peticion.MAX_TITULARES :]
    return resultado


def fuente_de_articulo(articulo: Documento, frase: str) -> Documento:
    cita = {"enlace": articulo["url"], "medio": articulo["medio"],
            "fecha": str(articulo["fecha"])[:10], "idioma": articulo.get("idioma") or "und",
            "frase": frase}  # fmt: skip
    return revisados.fuente_de_cita(cita, {"fuentes": []})


def mensual(almacen: Almacen, ahora: datetime, fabrica: Callable[[], Any] | None,
            plazo: Plazo | None) -> Documento:  # fmt: skip
    """La pasada del mes, si no se ha hecho: el modelo base elige, entre los titulares de cada
    incidente, los que merecen la pregunta al experto, dentro de `TOPE_MENSUAL_USD`. Lo elegido
    queda en el cursor y lo decide el experto en las recogidas siguientes."""
    mes = ahora.strftime("%Y-%m")
    cursor = almacen.cursor(CURSOR_MENSUAL) or {}
    if cursor.get("mes") == mes or fabrica is None:
        return {}
    desde = str(cursor.get("fecha") or (ahora - timedelta(days=400)).strftime("%Y-%m-%d"))[:10]
    por_incidente = titulares_mensuales(almacen, ahora, desde)
    from recogida.control_fichas import Llamador, Resultado

    resultado = Resultado()
    llamador = Llamador(almacen, fabrica, coste.Modo.RECTIFICACIONES, ahora, plazo, resultado)
    llamador.tope = almacen.gastado(coste.Modo.RECTIFICACIONES.value, coste.dia(ahora)) + (
        TOPE_MENSUAL_USD
    )
    pendientes = list(cursor.get("pendientes") or [])
    por_id = {i["id"]: i for i in almacen.incidentes()}
    vistos = 0
    for id_, articulos in sorted(por_incidente.items()):
        cuerpo = peticion.cuerpo_mensual(
            ficha(por_id[id_]),
            [(str(a["medio"]), str(a["fecha"])[:10], str(a["titular"])) for a in articulos],
        )
        leida = llamador.llamar(cuerpo, peticion.MAX_SALIDA_MENSUAL, f"{CURSOR_MENSUAL}:{id_}")
        if leida is None:
            if llamador.parado:
                break
            continue
        vistos += 1
        for numero in leida.get("titulares") or []:
            if isinstance(numero, int) and 1 <= numero <= len(articulos):
                articulo = articulos[numero - 1]
                pendientes.append({"incidente": id_, **{k: articulo[k] for k in articulo}})
    completa = llamador.resultado.parada is None
    nuevo = {
        "mes": mes if completa else cursor.get("mes"),
        "fecha": ahora.strftime("%Y-%m-%d") if completa else cursor.get("fecha"),
        "incidentes": len(por_incidente),
        "vistos": vistos,
        "pendientes": pendientes,
        "gasto": round(resultado.gasto, 6),
        "parada": llamador.resultado.parada,
    }
    almacen.guardar_cursor(CURSOR_MENSUAL, nuevo)
    return {k: nuevo[k] for k in ("mes", "incidentes", "vistos", "gasto", "parada")} | {
        "elegidos": len(pendientes)
    }


def de_la_busqueda(almacen: Almacen) -> list[Propuesta]:
    """Lo que eligió la búsqueda mensual (y el barrido diario de la segunda lectura)."""
    resultado = []
    for elegido in (almacen.cursor(CURSOR_MENSUAL) or {}).get("pendientes") or []:
        texto = str(elegido["titular"])
        fuente = fuente_de_articulo(elegido, str(elegido["titular"]))
        modo = (coste.Modo.SEGUNDA_LECTURA if elegido.get("origen") == ORIGEN_SEGUNDA
                else coste.Modo.RECTIFICACIONES)  # fmt: skip
        resultado.append(Propuesta(f"mensual:{elegido['incidente']}:{fuente['id']}",
                                   elegido["incidente"], "mensual", fuente, texto,
                                   modo=modo))  # fmt: skip
    return resultado


def clave_titular(elegido: Documento) -> str:
    """La clave con que el experto decide un titular elegido (la de `de_la_busqueda`)."""
    fuente = fuente_de_articulo(elegido, str(elegido["titular"]))
    return f"mensual:{elegido['incidente']}:{fuente['id']}"


def encolar(almacen: Almacen, elegidos: list[Documento], origen: str = ORIGEN_SEGUNDA) -> list[str]:
    """Lo que eligió el barrido diario de la segunda lectura (o lo que desmiente una autoridad,
    desde la verificación de las fichas), a la misma cola que lo de la búsqueda mensual, sin lo
    que ya está en ella ni lo que el experto ya decidió. Devuelve las claves nuevas."""
    cursor = dict(almacen.cursor(CURSOR_MENSUAL) or {})
    pendientes = list(cursor.get("pendientes") or [])
    en_cola = {clave_titular(p) for p in pendientes}
    decididas = {c.removeprefix(PREFIJO) for c in almacen.controles(PREFIJO + "mensual:")}
    nuevas = []
    for elegido in elegidos:
        clave = clave_titular(elegido)
        if clave in en_cola or clave in decididas:
            continue
        pendientes.append({**elegido, "origen": origen})
        en_cola.add(clave)
        nuevas.append(clave)
    if nuevas:
        almacen.guardar_cursor(CURSOR_MENSUAL, {**cursor, "pendientes": pendientes})
    return nuevas


# --- Paso de la recogida horaria -------------------------------------------------------------


def _fabrica() -> Callable[[], Any] | None:
    from recogida.control_fichas import _fabrica as fabrica

    return fabrica()


def _con_frase(propuesta: Propuesta, decision: Documento | None) -> Propuesta:
    """La fuente de un titular de la búsqueda lleva la frase que dio el experto."""
    if propuesta.origen != "mensual" or not decision or not decision.get("tipo"):
        return propuesta
    frase = str((decision.get("respuesta") or {}).get("frase") or "")
    # Literal y dentro del límite de la frase de una fuente: sus primeras palabras.
    frase = " ".join(frase.split()[: rectificaciones.MAX_PALABRAS_FRASE])
    if not frase:
        return propuesta
    fuente = {**propuesta.fuente, "frase_origen": frase}
    return Propuesta(propuesta.clave, propuesta.incidente, propuesta.origen, fuente,
                     propuesta.texto, propuesta.esperado, propuesta.revision)  # fmt: skip


def _con_texto(propuesta: Propuesta, paginas: dict[str, str]) -> Propuesta:
    texto = paginas.get(str(propuesta.fuente.get("enlace")), "")
    if not texto:
        return propuesta
    return Propuesta(
        propuesta.clave, propuesta.incidente, propuesta.origen, propuesta.fuente,
        f"{propuesta.texto} {texto}", propuesta.esperado, propuesta.revision,
    )  # fmt: skip


def ejecutar(
    almacen: Almacen, ahora: datetime, vocabulario: frozenset[str],
    fabrica: Callable[[], Any] | None, plazo: Plazo | None = None,
    leer_paginas: Callable[[list[str]], dict[str, str]] | None = None,
) -> Hechos:  # fmt: skip
    """Las revisadas a mano, siempre; lo elegido por la búsqueda mensual y lo detectado en las
    fuentes, como mucho `MAX_POR_PASADA` preguntas nuevas al experto; y la búsqueda del mes."""
    hechos = Hechos()
    experto = Experto(almacen, fabrica, ahora, plazo, hechos)
    decididas = {c.removeprefix(PREFIJO) for c in almacen.controles(PREFIJO)}
    revisar(almacen, experto, revisadas(almacen), ahora, vocabulario, hechos)
    detectadas_ = detectadas(almacen, set())
    hechos.detectadas = sum(1 for p in detectadas_ if p.clave not in decididas)
    propuestas = [*de_la_busqueda(almacen), *detectadas_]
    por_leer = [p for p in propuestas if p.clave not in decididas][:MAX_POR_PASADA]
    paginas = leer_paginas([str(p.fuente.get("enlace")) for p in por_leer]) if (
        leer_paginas and por_leer
    ) else {}  # fmt: skip
    propuestas = [_con_texto(p, paginas) for p in propuestas]
    revisar(almacen, experto, propuestas, ahora, vocabulario, hechos, MAX_POR_PASADA)
    try:
        hechos.mensual = mensual(almacen, ahora, fabrica, plazo)
    except TiempoAgotado:
        hechos.mensual = {"parada": "tiempo"}
    if experto.parado:
        registro.info("rectificaciones: el experto no puede ahora (%s)", experto.parado)
    registro.info("rectificaciones oficiales: %s", hechos.texto())
    return hechos


def _leer_paginas(plazo: Plazo) -> Callable[[list[str]], dict[str, str]]:
    from recogida.control_fichas import descargar

    return lambda enlaces: descargar(enlaces, plazo)


def paso_horario(almacen: Almacen, ahora: datetime, vocabulario: frozenset[str]) -> Hechos:
    """Paso de la recogida horaria, con su tope de tiempo."""
    plazo = Plazo(TOPE_S)
    return ejecutar(almacen, ahora, vocabulario, _fabrica(), plazo, _leer_paginas(plazo))


def principal(argumentos: list[str] | None = None) -> int:
    """`python -m recogida.rectificaciones senales --base <db>`: las fuentes que se mandarían al
    experto, sin llamar a nada ni cambiar la base."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("orden", choices=["senales"])
    parser.add_argument("--base", required=True, type=Path)
    args = parser.parse_args(argumentos)
    import sqlite3

    almacen = Almacen(sqlite3.connect(f"file:{args.base}?mode=ro", uri=True))
    decididas = {c.removeprefix(PREFIJO) for c in almacen.controles(PREFIJO)}
    for p in detectadas(almacen, decididas):
        senal = rectificaciones.senal(p.texto)
        print(f"{p.incidente}\t{p.fuente['fecha']['valor'][:10]}\t{p.fuente.get('medio')}\t"
              f"«{senal}»\t{p.texto[:160]}")  # fmt: skip
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    sys.exit(principal())
