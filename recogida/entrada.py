"""Filtro de entrada de las fichas nuevas y su medida a las 24 horas (docs/control_fichas.md,
«Filtro de entrada»).

Ninguna ficha nueva se publica sin que el experto la haya comparado con todo lo que puede ser el
mismo suceso, y sin que su fecha, su lugar y sus autoridades salgan de una frase de una fuente. El
conjunto de comparación no se elige por distancia: todas las fichas activas del mismo país de los
30 días anteriores a los 3 posteriores a su inicio y a su primera noticia; si el lugar es vago
(mar, frontera, región o país), también las de los países vecinos y ribereños. Con la respuesta:

- el mismo suceso que una de la lista: se une por el camino de las uniones del control, antes de
  publicarse (queda la más antigua);
- un suceso de otro día, con la frase que lo da: la ficha toma ese día y vuelve a pasar por el
  filtro con él;
- la fecha sin frase: la ficha no se publica hasta que una fuente la dé;
- el lugar sin frase: se publica solo el país;
- una autoridad sin frase, o de otro país sin que la frase lo diga: su declaración no se publica
  como oficial.

Sin decisión no sale: si el experto no responde o no cabe en su cupo, la ficha espera a la
recogida siguiente, y la espera cuenta como caso crítico (la vigilancia abre la incidencia a las
6 horas). Cupo propio: modo «entrada», 3 dólares al día (modelo/coste.py).

24 horas después de publicarse, cada ficha que pasó el filtro vuelve al experto con el conjunto
ampliado (lo llegado después) y la pregunta de si hay un error en la fecha, el lugar, el número,
la autoridad o es un duplicado; lo que encuentra con su frase se corrige y queda contado para el
resumen diario («Fichas nuevas de ayer: N; con error a las 24 h: M»)."""

import copy
import logging
import re
import unicodedata
from datetime import UTC, datetime, timedelta
from typing import Any

from almacen.base import Almacen
from esquema import Documento
from modelo import control, coste
from modelo import entrada as peticiones
from modelo.cliente import LlamadaFallida
from proceso import control_fichas as reglas
from proceso import fechas, fronteras, incidentes, noticias
from recogida import control_fichas
from recogida.plazo import Plazo, TiempoAgotado

registro = logging.getLogger(__name__)

PREFIJO = "entrada:"
PREFIJO_MEDIDA = "medida:"
DIAS_ANTES = 30
DIAS_DESPUES = 3
MAX_CONJUNTO = 40
# Dos fichas con su día sacado de una frase y a más de estos días no se unen sin revisión.
DIAS_FIRMES = 2
MEDIDA_TRAS = timedelta(hours=24)
# Las medidas no pasan de 7 días: lo publicado antes del filtro no se mide.
MEDIDA_HASTA = timedelta(days=7)
MAX_MEDIDAS_POR_PASADA = 6
# Tiempo del filtro y de la medida en cada recogida horaria, aparte del tope del control.
TOPE_S = 480.0
PUBLICAR, UNIDA, RETENER, ESPERA = "publicar", "unida", "retener", "dudoso"
FUERA_DE_PAIS = frozenset({"NATO", "OTAN", "EU", "UE"})

# Los países que se miran también cuando el lugar es vago: los vecinos por tierra (y por un
# estrecho) y los ribereños de cada mar.
MARES: dict[str, frozenset[str]] = {
    "negro": frozenset({"BG", "RO", "UA", "TR", "GE", "MD"}),
    "baltico": frozenset({"SE", "FI", "EE", "LV", "LT", "PL", "DE", "DK", "RU"}),
    "norte": frozenset({"GB", "NO", "DK", "DE", "NL", "BE", "FR"}),
    "mediterraneo": frozenset(
        {"ES", "FR", "MC", "IT", "MT", "SI", "HR", "BA", "ME", "AL", "GR", "TR", "CY"}
    ),
}
VECINOS: dict[str, frozenset[str]] = {
    p: frozenset(v.split())
    for p, v in {
        "PT": "ES", "ES": "PT FR AD", "FR": "ES AD MC IT CH DE LU BE GB",
        "BE": "FR LU DE NL GB", "NL": "BE DE GB", "LU": "BE FR DE",
        "DE": "DK NL BE LU FR CH AT CZ PL", "DK": "DE SE NO", "NO": "SE FI RU DK GB",
        "SE": "NO FI DK", "FI": "SE NO RU EE", "EE": "LV RU FI", "LV": "EE LT BY RU",
        "LT": "LV BY PL RU", "PL": "DE CZ SK UA BY LT RU", "CZ": "DE PL SK AT",
        "SK": "CZ PL UA HU AT", "AT": "DE CZ SK HU SI IT CH LI", "CH": "DE FR IT AT LI",
        "IT": "FR CH AT SI SM VA MT", "SI": "IT AT HU HR", "HR": "SI HU RS BA ME",
        "HU": "AT SK UA RO RS HR SI", "RO": "HU UA MD BG RS", "MD": "RO UA",
        "BG": "RO RS MK GR TR", "GR": "AL MK BG TR CY", "CY": "GR TR", "IE": "GB",
        "GB": "IE FR BE NL NO", "UA": "PL SK HU RO MD BY RU", "RS": "HU RO BG MK ME BA HR",
        "BA": "HR RS ME", "ME": "HR BA RS AL", "AL": "ME MK GR", "MK": "RS BG GR AL",
        "MT": "IT", "TR": "BG GR GE", "GE": "TR RU", "BY": "PL LT LV UA RU",
    }.items()
}  # fmt: skip


def clave(id_: str) -> str:
    return f"{PREFIJO}{id_}"


def clave_medida(id_: str) -> str:
    return f"{PREFIJO_MEDIDA}{id_}"


def huella(incidente: Documento) -> str:
    """Lo que, si cambia, pide otra decisión: las fuentes y la fecha."""
    return f"{reglas.huella_fuentes(incidente)}|{incidente['tiempo']['inicio']['valor']}"


def _iso(momento: datetime) -> str:
    return momento.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _leer(texto: str) -> datetime:
    return datetime.fromisoformat(texto.replace("Z", "+00:00"))


# --- El conjunto de comparación -----------------------------------------------------------


def vago(incidente: Documento) -> bool:
    """El lugar no sitúa el suceso en un país solo: el mar, una frontera, una región o el país."""
    lugar = incidente["lugar"]
    zona = incidente.get("zona") or {}
    return (
        lugar.get("nivel") in {"pais", "region"}
        or "punto" not in lugar
        or zona.get("grupo") == "frontera"
    )


def paises(incidente: Documento) -> frozenset[str]:
    """El país de la ficha y, con el lugar vago, sus vecinos y los ribereños de sus mares."""
    pais = str(incidente["lugar"]["pais"])
    if not vago(incidente):
        return frozenset({pais})
    mares = [m for m in MARES.values() if pais in m]
    return frozenset({pais}) | VECINOS.get(pais, frozenset()) | frozenset().union(*mares)


def _referencias(incidente: Documento) -> list[datetime]:
    return [reglas.instante(incidente), reglas.primera_noticia(incidente)]


def conjunto(incidente: Documento, activos: list[Documento]) -> list[Documento]:
    """Las fichas activas que pueden contar el mismo suceso, sin mirar la distancia: de sus
    países (paises), de 30 días antes a 3 después de su inicio o de su primera noticia, salvo las
    que una revisión separó. Si son más de MAX_CONJUNTO, las del mismo tipo y las más cercanas en
    el tiempo."""
    referencias = _referencias(incidente)
    validos = paises(incidente)
    elegidas = []
    for otra in activos:
        if otra["id"] == incidente["id"] or otra["lugar"]["pais"] not in validos:
            continue
        momento = reglas.instante(otra)
        if not any(
            r - timedelta(days=DIAS_ANTES) <= momento <= r + timedelta(days=DIAS_DESPUES)
            for r in referencias
        ):
            continue
        if reglas.separados(incidente, otra):
            continue
        elegidas.append(otra)

    def orden(otra: Documento) -> tuple[int, float, str]:
        distancia = min(abs((reglas.instante(otra) - r).total_seconds()) for r in referencias)
        return (0 if otra.get("tipo") == incidente.get("tipo") else 1, distancia, otra["id"])

    return sorted(elegidas, key=orden)[:MAX_CONJUNTO]


def resumen(otra: Documento) -> dict[str, Any]:
    """Una ficha del conjunto en una línea: id, fecha, lugar, titular, tipo y una frase."""
    vista = reglas.vista(otra)
    frase = next(
        (
            str(f.get("frase_origen") or "")
            for f in control_fichas._publicas(otra)
            if f.get("frase_origen")
        ),
        "",
    )
    return {
        "id": otra["id"],
        "fecha": vista["inicio"],
        "lugar": vista["lugar"],
        "tipo": otra.get("tipo", ""),
        "titular": vista["titular"],
        "frase": " ".join(frase.split())[:200],
    }


def autoridades_de(incidente: Documento) -> dict[str, list[str]]:
    """Las autoridades cuyas declaraciones cita la ficha: nombre -> ids de sus fuentes."""
    return reglas.declaraciones_de(incidente)


def _normal(texto: str) -> str:
    return " ".join(unicodedata.normalize("NFC", texto).casefold().split())


# --- La respuesta comprobada --------------------------------------------------------------

_DIA = re.compile(r"^\s*(\d{4}-\d{2}-\d{2})\s*$")


def _frase(numero: Any, frase: Any, fuentes: list[tuple[str, str]]) -> tuple[str, str] | None:
    """(id de la fuente, frase) si la frase está, literal, en el texto de esa fuente."""
    texto = " ".join(str(frase or "").split())
    if not isinstance(numero, int) or not 1 <= numero <= len(fuentes):
        return None
    if _normal(texto) in {"", peticiones.NO}:
        return None
    id_, contenido = fuentes[numero - 1]
    return (id_, texto) if reglas.frase_valida(texto, contenido) else None


def permitidos(incidente: Documento) -> frozenset[str]:
    """Los países de las autoridades que la ficha publica sin más: el suyo, el del dron
    atribuido y la OTAN o la UE."""
    atribuido = (incidente.get("atribucion") or {}).get("pais")
    return frozenset({str(incidente["lugar"]["pais"]), *([str(atribuido)] if atribuido else [])})


def decidir(
    respuesta: dict[str, Any], fuentes: list[tuple[str, str]], ids_conjunto: list[str],
    incidente: Documento,
) -> dict[str, Any]:  # fmt: skip
    """Lo que vale de la respuesta del experto, comprobado: el id del mismo suceso (si está en la
    lista), el día de otro día (con su frase), si la fecha y el lugar tienen frase, y las
    autoridades que no se publican como declaración oficial (sin frase, o de otro país sin que su
    frase diga ese país)."""
    decision: dict[str, Any] = {
        "motivo_es": str(respuesta.get("motivo_es") or "")[:300],
        "motivo_en": str(respuesta.get("motivo_en") or "")[:300],
        "duda": bool(respuesta.get("duda")),
        "dudosas": [str(i) for i in respuesta.get("dudosas") or [] if str(i) in ids_conjunto],
    }
    mismo = str(respuesta.get("mismo_suceso") or "").strip()
    if mismo and _normal(mismo) != peticiones.NINGUNA:
        if mismo in ids_conjunto:
            decision["mismo"] = mismo
            decision["motivo_mismo"] = str(respuesta.get("motivo_mismo") or "")[:300]
        else:
            decision["invalida"] = f"«{mismo[:40]}» no está en la lista"
    fecha = _frase(respuesta.get("fecha_fuente"), respuesta.get("fecha_frase"), fuentes)
    decision["frase_fecha"] = list(fecha) if fecha else None
    dia = _DIA.match(str(respuesta.get("fecha_suceso") or ""))
    actual = incidente["tiempo"]["inicio"]["valor"][:10]
    if respuesta.get("otro_dia") is True and fecha and dia and dia[1] != actual:
        try:
            datetime.strptime(dia[1], "%Y-%m-%d")
            decision["otro_dia"] = {"dia": dia[1], "fuente_id": fecha[0], "frase": fecha[1]}
        except ValueError:
            pass
    lugar = _frase(respuesta.get("lugar_fuente"), respuesta.get("lugar_frase"), fuentes)
    decision["frase_lugar"] = list(lugar) if lugar else None
    citadas = autoridades_de(incidente)
    respondidas = {
        _normal(str(a.get("nombre") or "")): a
        for a in respuesta.get("autoridades") or [] if isinstance(a, dict)
    }  # fmt: skip
    validos = permitidos(incidente) | FUERA_DE_PAIS
    sin_publicar: dict[str, str] = {}
    paises_: dict[str, str] = {}
    for nombre in citadas:
        dada = respondidas.get(_normal(nombre))
        if dada is None:
            sin_publicar[nombre] = "sin respuesta"
            continue
        pais = str(dada.get("pais") or "").strip().upper()
        con_frase = _frase(dada.get("fuente"), dada.get("frase"), fuentes)
        if con_frase is None or not pais:
            sin_publicar[nombre] = "ninguna frase la nombra con su país"
            continue
        paises_[nombre] = pais
        if pais not in validos and not _pais_en_la_frase(pais, con_frase[1]):
            sin_publicar[nombre] = f"de otro país ({pais}) sin que la frase lo diga"
    decision["autoridades"] = paises_
    decision["autoridades_fuera"] = sin_publicar
    return decision


def fecha_firme(incidente: Documento) -> bool:
    """El inicio sale de una frase con su día (no es la fecha de publicación ni aproximado)."""
    inicio = incidente["tiempo"]["inicio"]
    origen = incidente["tiempo"].get("origen_inicio") or {}
    con_dia = inicio.get("precision") in ("dia", "hora", "minuto")
    return con_dia and origen.get("tipo") not in ("publicacion", None)


def fecha_aproximada(incidente: Documento) -> bool:
    """La fecha es la de publicación o aproximada: sin una frase que la dé, no se publica."""
    origen = incidente["tiempo"].get("origen_inicio") or {}
    return incidente["tiempo"]["inicio"].get("precision") == "aproximada" or (
        origen.get("tipo") == "publicacion"
    )


def fechas_distintas(incidente: Documento, otra: Documento) -> str | None:
    """Las dos fichas tienen fechas firmes a más de DIAS_FIRMES días: el texto de las dos fechas,
    o None. Un mismo suceso con dos días firmes tan separados casi siempre son dos sucesos (en la
    prueba del 28 de octubre de 2026, el ataque a buques frente a Bulgaria del 12 de octubre,
    EODI-2026-00512, salía unido al del 6, EODI-2026-00489)."""
    if not (fecha_firme(incidente) and fecha_firme(otra)):
        return None
    a, b = reglas.instante(incidente), reglas.instante(otra)
    if abs((a - b).total_seconds()) <= DIAS_FIRMES * 86400:
        return None
    return f"{a.date().isoformat()} y {b.date().isoformat()}"


def _pais_en_la_frase(pais: str, frase: str) -> bool:
    """La frase nombra el país (el principio de su nombre en alguna lengua de Natural Earth:
    «bulgar» vale para «Bulgarian officials»)."""
    texto = noticias.normalizar(frase)
    return any(n[:5] in texto for n in fronteras.nombres_del_pais(pais) if len(n) >= 5)


def sin_frase(decision: dict[str, Any]) -> list[str]:
    """Lo que la respuesta no respalda con una frase."""
    faltan = []
    if not decision.get("frase_fecha"):
        faltan.append("fecha")
    if not decision.get("frase_lugar"):
        faltan.append("lugar")
    if decision.get("autoridades_fuera"):
        faltan.append("autoridad")
    return faltan


# --- Lo que se hace con la decisión -------------------------------------------------------


def con_dia(incidente: Documento, dia: str, fuente_id: str, frase: str) -> Documento:
    """La ficha con el día del suceso que da la frase (sin hora: precisión de día)."""
    tiempo = {k: v for k, v in (incidente.get("tiempo") or {}).items() if k not in {"fin"}}
    tiempo["inicio"] = {"valor": f"{dia}T00:00Z", "precision": "dia"}
    tiempo["origen_inicio"] = {
        "tipo": fechas.EXPLICITA,
        "fuente_id": fuente_id,
        "motivo": f"filtro de entrada: «{frase}»"[:300],
    }
    return {**incidente, "tiempo": tiempo}


def corregida(incidente: Documento, decision: dict[str, Any]) -> tuple[Documento, list[str]]:
    """La ficha sin lo que no tiene frase: el lugar, a nivel de país; las declaraciones de las
    autoridades fuera, no oficiales (y el estado que daban, de vuelta a notificado). Devuelve la
    ficha y los cambios (vacío si no cambia)."""
    nuevo = copy.deepcopy(incidente)
    cambios = []
    if not decision.get("frase_lugar") and nuevo["lugar"].get("nivel") != "pais":
        nuevo["lugar"] = {"pais": nuevo["lugar"]["pais"], "nivel": "pais"}
        nuevo.pop("objetivo", None)
        cambios.append("lugar sin frase: solo el país")
    nuevo, propios = reglas.sin_oficiales(
        nuevo, decision.get("autoridades_fuera") or {}, _instante_de(incidente)
    )
    cambios += propios
    if not cambios:
        return incidente, []
    return incidentes.aplicar_reglas(nuevo), cambios


def _instante_de(incidente: Documento) -> Documento:
    return dict(incidente["control"].get("ultima_actualizacion") or incidente["control"]["alta"])


# --- El paso ------------------------------------------------------------------------------


class Experto:
    """Las llamadas del filtro: siempre al experto, con el cupo del modo «entrada»."""

    def __init__(self, ctx: control_fichas.Contexto, plazo: Plazo) -> None:
        self.ctx = ctx
        self.plazo = plazo
        self.llamador = control_fichas.Llamador(
            ctx.almacen, ctx.llamador.fabrica, coste.Modo.ENTRADA, ctx.ahora, plazo, ctx.resultado
        )
        self.motivo_espera = ""

    def llamar(self, cuerpo: dict[str, Any], max_salida: int, clave_: str) -> dict[str, Any] | None:
        """La respuesta leída, o None (y el motivo en `motivo_espera`)."""
        self.motivo_espera = ""
        almacen, ahora = self.ctx.almacen, self.ctx.ahora
        if self.llamador.fabrica is None:
            self.motivo_espera = "sin servicio"
            return None
        try:
            servicio = self.llamador.servicio()
            experto = getattr(servicio, "experto", None)
            cliente = experto() if callable(experto) else None
            if cliente is None:
                self.motivo_espera = "sin experto configurado"
                return None
            esfuerzo = (cuerpo.get("output_config") or {}).get("effort")
            previsto = coste.peor_caso(control.letras(cuerpo), max_salida,
                                       modelo=str(getattr(cliente, "modelo", "")),
                                       esfuerzo=esfuerzo)  # fmt: skip
            gastado = almacen.gastado_experto_en(coste.Modo.ENTRADA.value, coste.dia(ahora))
            coste.comprobar_cupo(
                gastado, previsto, coste.Modo.ENTRADA, coste.del_mes(almacen, ahora)
            )
            self.plazo.comprobar()
            respuesta = cliente.mensaje(cuerpo)
        except coste.LimiteGasto as error:
            self.motivo_espera = f"cupo: {str(error)[:120]}"
            return None
        except TiempoAgotado:
            self.motivo_espera = "tiempo de la pasada agotado"
            return None
        except LlamadaFallida as error:
            self.motivo_espera = f"el experto falló: {str(error)[:120]}"
            return None
        except Exception as error:
            self.motivo_espera = f"error: {repr(error)[:120]}"
            return None
        leida = self.llamador._anotar(respuesta, clave_, escalada=True)
        if leida is None:
            self.motivo_espera = "respuesta sin leer"
        return leida


def _textos(incidente: Documento, plazo: Plazo) -> dict[str, str]:
    enlaces = [str(f["enlace"]) for f in control_fichas._publicas(incidente) if f.get("enlace")]
    if plazo.agotado():
        return {}
    return control_fichas.descargar(list(dict.fromkeys(enlaces))[:6], plazo)


def preguntar(
    experto: Experto, incidente: Documento, activos: list[Documento], clave_: str
) -> tuple[dict[str, Any] | None, list[Documento], control_fichas.FuentesDeFicha]:
    """La decisión comprobada del experto sobre la ficha (None si no respondió), el conjunto y
    sus fuentes. Si duda, o si no da frase para la fecha, el lugar o una autoridad, se le vuelve a
    preguntar con las fuentes de las candidatas más cercanas."""
    almacen = experto.ctx.almacen
    elegidas = conjunto(incidente, activos)
    ids = [c["id"] for c in elegidas]
    fuentes = control_fichas.fuentes_de_ficha(almacen, incidente, _textos(incidente, experto.plazo))
    citadas = list(autoridades_de(incidente))
    vista = reglas.vista(incidente)
    resumenes = [resumen(c) for c in elegidas]
    cuerpo = peticiones.cuerpo_entrada(vista, fuentes.bloques, citadas, resumenes)
    leida = experto.llamar(cuerpo, peticiones.MAX_SALIDA_ENTRADA, clave_)
    if leida is None:
        return None, elegidas, fuentes
    decision = decidir(leida, fuentes.comprobar, ids, incidente)
    por_id = {c["id"]: c for c in elegidas}

    def choque(d: dict[str, Any]) -> str | None:
        return fechas_distintas(incidente, por_id[d["mismo"]]) if "mismo" in d else None

    if decision.get("duda") or sin_frase(decision) or decision.get("invalida") or choque(decision):
        dudosas = [*decision.get("dudosas", []), *([decision["mismo"]] if "mismo" in decision
                                                    else []), *ids]  # fmt: skip
        contexto = {
            i: control_fichas.fuentes_de_ficha(almacen, por_id[i], {}).bloques
            for i in list(dict.fromkeys(dudosas))[: peticiones.MAX_CANDIDATAS_CONTEXTO]
        }
        cuerpo = peticiones.cuerpo_entrada(vista, fuentes.bloques, citadas, resumenes, contexto)
        otra = experto.llamar(cuerpo, peticiones.MAX_SALIDA_ENTRADA, clave_ + ":contexto")
        if otra is not None:
            decision = {**decidir(otra, fuentes.comprobar, ids, incidente), "repetida": True}
    fechas = choque(decision)
    if fechas:
        # Con las fuentes de las dos delante sigue diciendo que es el mismo: no se une ni se
        # publica; lo decide una revisión.
        mismo = decision.pop("mismo")
        decision["invalida"] = f"el mismo suceso que {mismo} con fechas firmes distintas ({fechas})"
    return decision, elegidas, fuentes


def _activos(almacen: Almacen) -> list[Documento]:
    return [i for i in almacen.incidentes() if incidentes.activo(i)]


def pasar(experto: Experto, incidente: Documento, previa: Documento | None) -> Documento:
    """Pasa una ficha nueva por el filtro y devuelve la decisión que se guarda."""
    ctx = experto.ctx
    clave_ = clave(incidente["id"])
    base: Documento = {"version": peticiones.VERSION_ENTRADA, "fecha": _iso(ctx.ahora)}
    cambios: list[str] = []
    for vuelta in range(2):
        activos = _activos(ctx.almacen)
        decision, elegidas, _ = preguntar(experto, incidente, activos, clave_)
        base["huella"] = huella(incidente)
        base["conjunto"] = len(elegidas)
        if decision is None:
            desde = (previa or {}).get("desde") or _iso(ctx.ahora)
            return {**base, "decision": ESPERA, "critico": True, "desde": desde,
                    "espera_experto": _iso(ctx.ahora + coste.ESPERA_REINTENTO),
                    "motivo": experto.motivo_espera, "cambios": cambios}  # fmt: skip
        if "mismo" in decision:
            otra = next(c for c in elegidas if c["id"] == decision["mismo"])
            conserva, une = reglas.mas_antiguo(otra, incidente)
            motivo = f"filtro de entrada: {decision.get('motivo_mismo') or decision['motivo_es']}"
            if control_fichas.unir(ctx.almacen, conserva, une, motivo, ctx.ahora,
                                   ctx.modelos) is None:  # fmt: skip
                motivo = f"el mismo que {otra['id']}, dados por distintos: propuesta"
                return {**base, **decision, "decision": RETENER, "cambios": cambios,
                        "motivo": motivo}  # fmt: skip
            ctx.resultado.unidos.append(f"{une['id']}→{conserva['id']}")
            return {**base, **decision, "decision": UNIDA, "conserva": conserva["id"],
                    "une": une["id"], "cambios": cambios}  # fmt: skip
        if "otro_dia" in decision and vuelta == 0:
            dia = decision["otro_dia"]
            nuevo_dia = datetime.strptime(dia["dia"], "%Y-%m-%d").replace(tzinfo=UTC)
            distancia = abs((nuevo_dia - reglas.instante(incidente)).total_seconds())
            if fecha_firme(incidente) and distancia > DIAS_FIRMES * 86400:
                # Un día sacado de una frase no se cambia por otro lejano sin revisión (prueba del
                # 28 de octubre de 2026: el 12 de octubre de EODI-2026-00512 pasaba al 6 por «o
                # săptămână după ce atacurile au dus la scufundarea», que no da ningún día).
                return {**base, **decision, "decision": RETENER, "cambios": cambios,
                        "motivo": f"otro día ({dia['dia']}) lejos de una fecha firme"}  # fmt: skip
            nuevo = incidentes.aplicar_reglas(
                con_dia(incidente, dia["dia"], dia["fuente_id"], dia["frase"])
            )
            if control_fichas._guardar(
                ctx, incidente, nuevo, f"filtro de entrada: día {dia['dia']}"
            ):
                cambios.append(f"día {dia['dia']}: «{dia['frase']}»")
                incidente = ctx.almacen.incidente(incidente["id"]) or nuevo
                continue
            return {**base, **decision, "decision": RETENER, "cambios": cambios,
                    "motivo": "el día que da la frase no se pudo guardar"}  # fmt: skip
        if decision.get("invalida"):
            return {**base, **decision, "decision": RETENER, "cambios": cambios,
                    "motivo": decision["invalida"]}  # fmt: skip
        nuevo, propios = corregida(incidente, decision)
        if propios and not control_fichas._guardar(
            ctx, incidente, nuevo, "filtro de entrada: " + "; ".join(propios)
        ):
            return {**base, **decision, "decision": RETENER, "cambios": cambios + propios,
                    "motivo": "la corrección no se pudo guardar"}  # fmt: skip
        cambios += propios
        if propios:
            ctx.resultado.corregidos.setdefault(incidente["id"], []).append(
                "filtro de entrada: " + "; ".join(propios)
            )
            actual = ctx.almacen.incidente(incidente["id"])
            base["huella"] = huella(actual) if actual else base["huella"]
        if not decision.get("frase_fecha") and fecha_aproximada(incidente):
            return {**base, **decision, "decision": RETENER, "cambios": cambios,
                    "motivo": "ninguna frase da la fecha del suceso"}  # fmt: skip
        return {**base, **decision, "decision": PUBLICAR, "cambios": cambios}
    return {**base, "decision": RETENER, "cambios": cambios,
            "motivo": "la fecha cambió dos veces"}  # fmt: skip


def vigente(decision: Documento | None, incidente: Documento) -> bool:
    """La decisión sigue valiendo para la ficha tal como está."""
    return decision is not None and decision.get("huella") == huella(incidente)


def pendiente(decision: Documento | None, incidente: Documento, ahora: datetime) -> bool:
    """La ficha tiene que (volver a) pasar por el filtro ahora."""
    if not vigente(decision, incidente):
        return True
    assert decision is not None
    if decision.get("decision") == ESPERA:
        return ahora >= _leer(str(decision.get("espera_experto") or _iso(ahora)))
    return False


def motivo_retencion(decision: Documento | None, incidente: Documento) -> str | None:
    """Por qué el filtro no deja publicar la ficha nueva, o None si la deja."""
    if decision is None:
        return "sin pasar por el filtro de entrada"
    if not vigente(decision, incidente):
        return "filtro de entrada: la ficha cambió desde la decisión"
    if decision.get("decision") == PUBLICAR:
        return None
    if decision.get("decision") == ESPERA:
        return f"filtro de entrada: espera al experto ({decision.get('motivo', '')})"[:200]
    return f"filtro de entrada: {decision.get('motivo', 'retenida')}"[:200]


def filtrar(ctx: control_fichas.Contexto, vistos: set[str], plazo: Plazo | None = None) -> int:
    """Pasa por el filtro cada ficha nueva (activa y aún no publicada) que lo necesita. Devuelve
    cuántas pasa."""
    experto = Experto(ctx, plazo or Plazo(TOPE_S))
    pasadas = 0
    for incidente in sorted(_activos(ctx.almacen), key=lambda d: d["id"]):
        id_ = incidente["id"]
        if id_ in vistos:
            continue
        actual = ctx.almacen.incidente(id_)
        if actual is None or not incidentes.activo(actual):
            continue
        previa = ctx.decision(clave(id_))
        if not pendiente(previa, actual, ctx.ahora):
            continue
        decision = pasar(experto, actual, previa)
        ctx.nuevas[clave(id_)] = decision
        pasadas += 1
        registro.info("filtro de entrada %s: %s%s", id_, decision["decision"],
                      f" ({decision.get('motivo')})" if decision.get("motivo") else "")  # fmt: skip
        if decision["decision"] == ESPERA:
            ctx.resultado.esperan_experto.append(clave(id_))
    return pasadas


# --- La medida a las 24 horas -------------------------------------------------------------


def comprobar_medida(
    respuesta: dict[str, Any], fuentes: list[tuple[str, str]], ids_conjunto: list[str]
) -> list[dict[str, Any]]:
    """Los errores que la medida respalda: un duplicado de la lista, o un dato con su frase (o
    sin ninguna, si el error es justo que no la tiene)."""
    errores = []
    for error in respuesta.get("errores") or []:
        if not isinstance(error, dict) or error.get("dato") not in peticiones.DATOS_MEDIDA:
            continue
        dato = str(error["dato"])
        if dato == "duplicado":
            otro = str(error.get("duplicado_de") or "").strip()
            if otro in ids_conjunto:
                errores.append({"dato": dato, "duplicado_de": otro})
            continue
        con_frase = _frase(error.get("fuente"), error.get("frase"), fuentes)
        sin_ninguna = not str(error.get("frase") or "").strip() and error.get("fuente") == 0
        if con_frase is None and not sin_ninguna:
            continue
        entrada = {"dato": dato, "correcto": str(error.get("correcto") or "")[:80]}
        if con_frase:
            entrada.update(fuente_id=con_frase[0], frase=con_frase[1])
        errores.append(entrada)
    return errores


def corregir_medida(
    ctx: control_fichas.Contexto, incidente: Documento, errores: list[dict[str, Any]],
    elegidas: list[Documento],
) -> list[str]:  # fmt: skip
    """Lo que la medida encontró, corregido por el camino normal: el duplicado se une; el día que
    da una frase se toma; el lugar o la autoridad sin respaldo dejan de publicarse. El número de
    drones queda anotado para la verificación del control."""
    hechos: list[str] = []
    for error in errores:
        if error["dato"] == "duplicado":
            otra = next((c for c in elegidas if c["id"] == error["duplicado_de"]), None)
            if otra is None or not incidentes.activo(otra):
                continue
            conserva, une = reglas.mas_antiguo(otra, incidente)
            motivo = "medida a las 24 horas: el mismo suceso"
            if control_fichas.unir(ctx.almacen, conserva, une, motivo, ctx.ahora,
                                   ctx.modelos) is None:  # fmt: skip
                continue
            ctx.resultado.unidos.append(f"{une['id']}→{conserva['id']}")
            hechos.append(f"unida {une['id']}→{conserva['id']}")
            return hechos
    actual = incidente
    for error in errores:
        if error["dato"] == "fecha" and error.get("frase") and _DIA.match(error["correcto"]):
            nuevo = incidentes.aplicar_reglas(
                con_dia(actual, error["correcto"].strip(), error["fuente_id"], error["frase"])
            )
            if control_fichas._guardar(ctx, actual, nuevo, "medida a las 24 horas: día"):
                hechos.append(f"día {error['correcto']}")
                actual = ctx.almacen.incidente(actual["id"]) or nuevo
    sin = {
        "frase_lugar": None if any(e["dato"] == "lugar" for e in errores) else ["", ""],
        "autoridades_fuera": {
            n: "medida a las 24 horas"
            for n in autoridades_de(actual)
            if any(e["dato"] == "autoridad" for e in errores)
        },
    }
    nuevo, propios = corregida(actual, sin)
    motivo = "medida a las 24 horas: " + "; ".join(propios)
    if propios and control_fichas._guardar(ctx, actual, nuevo, motivo):
        hechos += propios
    return hechos


def medir(ctx: control_fichas.Contexto, publicadas: dict[str, str],
          plazo: Plazo | None = None) -> int:  # fmt: skip
    """La medida de las fichas que pasaron el filtro y llevan 24 horas publicadas
    (`publicadas`: id -> cuándo se publicó). Devuelve cuántas mide."""
    experto = Experto(ctx, plazo or Plazo(TOPE_S))
    medidas = 0
    activos = _activos(ctx.almacen)
    for incidente in activos:
        id_ = incidente["id"]
        decision = ctx.decision(clave(id_))
        cuando = publicadas.get(id_)
        if decision is None or decision.get("decision") != PUBLICAR or cuando is None:
            continue
        edad = ctx.ahora - _leer(cuando)
        previa = ctx.decision(clave_medida(id_))
        if edad < MEDIDA_TRAS or edad > MEDIDA_HASTA or (previa and "errores" in previa):
            continue
        if medidas >= MAX_MEDIDAS_POR_PASADA:
            break
        elegidas = conjunto(incidente, activos)
        fuentes = control_fichas.fuentes_de_ficha(ctx.almacen, incidente, {})
        cuerpo = peticiones.cuerpo_medida(reglas.vista(incidente), fuentes.bloques,
                                          list(autoridades_de(incidente)),
                                          [resumen(c) for c in elegidas])  # fmt: skip
        leida = experto.llamar(cuerpo, peticiones.MAX_SALIDA_MEDIDA, clave_medida(id_))
        if leida is None:
            break
        errores = comprobar_medida(leida, fuentes.comprobar, [c["id"] for c in elegidas])
        hechos = corregir_medida(ctx, incidente, errores, elegidas) if errores else []
        ctx.nuevas[clave_medida(id_)] = {
            "version": peticiones.VERSION_MEDIDA, "fecha": _iso(ctx.ahora), "publicada": cuando,
            "errores": errores, "corregido": hechos, "motivo_es": leida.get("motivo_es", ""),
        }  # fmt: skip
        medidas += 1
        registro.info("medida a las 24 horas %s: %d errores%s", id_, len(errores),
                      f" ({'; '.join(hechos)})" if hechos else "")  # fmt: skip
        activos = _activos(ctx.almacen)
    return medidas


# --- Para el resumen diario ---------------------------------------------------------------

DIAS_ESTADO = 3


def estado_por_dia(almacen: Almacen, ahora: datetime, anterior: Documento) -> Documento:
    """Por día de publicación: las fichas nuevas que pasaron el filtro, las ya medidas y las que
    tenían un error a las 24 horas. Para ~/.eodi/control.json y el resumen de las 08:00."""
    cursor = almacen.cursor(control_fichas.CURSOR) or {}
    publicadas: dict[str, str] = cursor.get("vistos", {})
    entradas = almacen.controles(PREFIJO)
    medidas = almacen.controles(PREFIJO_MEDIDA)
    dias: Documento = {}
    for clave_, decision in entradas.items():
        id_ = clave_.removeprefix(PREFIJO)
        cuando = publicadas.get(id_)
        if decision.get("decision") != PUBLICAR or not cuando:
            continue
        dia = dias.setdefault(cuando[:10], {"nuevas": [], "medidas": [], "con_error": []})
        dia["nuevas"].append(id_)
        medida = medidas.get(clave_medida(id_))
        if medida is not None and "errores" in medida:
            dia["medidas"].append(id_)
            if medida["errores"]:
                dia["con_error"].append(id_)
    desde = coste.dia(ahora - timedelta(days=DIAS_ESTADO))
    todos = {**{d: v for d, v in anterior.items() if d >= desde}, **dias}
    return {d: {k: sorted(v) for k, v in todos[d].items()} for d in sorted(todos) if d >= desde}
