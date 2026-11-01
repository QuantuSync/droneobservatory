"""Lo protegido: la lista única de lo que ya está decidido en una ficha y el cerrojo que lo guarda.

Toda escritura de una ficha pasa por `Almacen.guardar_incidente`, que llama aquí después de
`rectificaciones.mantener` y `decidir.aplicar` y antes de escribir. Nada de esto tiene fichero de
configuración propio: se calcula de lo que ya existe.

- **Nivel manual**: las fichas revisadas a mano (configuracion/incidentes_revisados.json) y las del
  conjunto de referencia (tests/referencia/fichas.json). Sus datos publicados solo cambian por una
  revisión a mano o por una rectificación oficial nueva.
- **Nivel con cita**: en cualquier ficha publicada, los datos decididos con la frase de una fuente
  (proceso/decididos.py) y el estado y la presencia que decide una autoridad. Solo cambian si una
  fuente de un artículo que la ficha no tenía trae una frase literal (`fuente_nueva_con_frase`).
- **Nivel publicada**: la retirada de cualquier ficha publicada. Solo pasa si viene de una decisión
  explícita (`por_decision`): nunca de un fallo al guardar o rehacer (docs/cerrojo.md).
- **Uniones prohibidas**: los pares que no se unen (`distintos`, partes de una separación, los
  distintos del experto, los relacionados). Se miran entre grupos enteros: todas las fichas que
  cuelgan de la destinataria contra todas las de la absorbida, así que ni una cadena de uniones ni
  una renumeración las saltan.
- **Fichas del nivel manual que se funden**: sin par prohibido, solo las une una revisión a mano.
- **Reaperturas**: una ficha fundida deja de estarlo solo por una revisión a mano o una separación.

El texto completo de los artículos no se guarda (recogida/control_fichas.paginas_de: solo en
memoria). La comprobación literal es la de `control_fichas.frase_valida`, la misma del filtro de
entrada (recogida/entrada._frase), contra lo que sí queda guardado de ese artículo: su titular
(tabla `articulos`) y las frases de su última extracción, que `validacion_ficha` comprobó literales
en el texto al extraer (tabla `extracciones`).

`configuracion/cerrojo.json` dice el modo: en «observar» se apunta lo que se habría retenido y se
guarda todo como antes; en «aplicar» se conserva el valor anterior, dato a dato, con su afirmación.
Cada caso queda en la tabla del control de las fichas: `retenido:` lo que no pasó (o no habría
pasado), `permitido:` el cambio a un dato protegido que pasó con su justificación (la auditoría X
los compara con el historial) y `cerrojo_fallo:` un fallo del propio cerrojo, que nunca para la
recogida (docs/cerrojo.md).
"""

import copy
import hashlib
import json
import sys
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from functools import cache
from pathlib import Path
from typing import Any

from esquema import Documento
from proceso import control_fichas as reglas
from proceso import decididos, decidir, declaraciones, incidentes, rectificaciones

RAIZ = Path(__file__).resolve().parent.parent
CONFIGURACION = RAIZ / "configuracion" / "cerrojo.json"
FICHAS_REFERENCIA = RAIZ / "tests" / "referencia" / "fichas.json"

OBSERVAR, APLICAR = "observar", "aplicar"
PASO_RENUMERAR = "recogida.control_fichas.conservar_la_mas_antigua"
MANUAL, CON_CITA, PUBLICADA = "manual", "con_cita", "publicada"
PREFIJO_RETENIDO, PREFIJO_PERMITIDO = "retenido:", "permitido:"
PREFIJO_FALLO = "cerrojo_fallo:"
# Una versión nueva de una ficha publicada que no se pudo guardar (proceso/extraccion.py): la clave
# lleva la ficha y la fecha; se quedó la versión publicada.
PREFIJO_GUARDADO_FALLIDO = "guardado_fallido:"
# Veces seguidas que falla la misma ficha para abrir una incidencia (recogida/vigilancia.py).
FALLOS_SEGUIDOS = 3
# Quién puede retirar una ficha publicada: las decisiones explícitas. La barrera de titulares a las
# 6 horas, el repaso de entrada con decisión, una revisión a mano y el veredicto de que no es un
# suceso. Un fallo al guardar o rehacer no retira nunca (proceso/extraccion.conservar_publicada).
DECISIONES_RETIRADA = (
    "recogida.barrera.", "recogida.repaso_entrada.", "recogida.revisados.",
    "proceso.extraccion.retirar_por_veredicto",
)  # fmt: skip
# Las comprobaciones de la auditoría que miran lo protegido (proceso/auditoria_fichas.py).
AUDITORIA = ("P", "R", "V", "W", "X")

DATOS_MANUAL = (
    "estado", "presencia_dron", "tipo", "objetivo", "lugar", "inicio", "drones", "cierre",
    "titulo", "retirado",
)  # fmt: skip
# Las afirmaciones que dicen cada dato (además de las de decididos para el resto).
CAMPOS_AFIRMACION = {
    **decididos._CAMPOS_AFIRMACION,
    "estado": ("estado",),
    "presencia_dron": ("presencia_dron",),
    "tipo": ("tipo",),
    "objetivo": ("objetivo_nombre", "objetivo_categoria", "objetivo_conocido"),
    "titulo": (),
}
# Lo que deja el titular tal como está decidido: si lo justificado cambia, el titular lo sigue.
TITULO_SIGUE_A = ("presencia_dron", "drones", "lugar", "objetivo", "tipo")


@dataclass(frozen=True)
class Cambio:
    dato: str
    nivel: str
    antes: Any
    despues: Any


@dataclass
class Veredicto:
    """Lo que el cerrojo decide de una versión nueva de la ficha."""

    retenidos: list[Cambio] = field(default_factory=list)
    permitidos: list[tuple[Cambio, str]] = field(default_factory=list)
    union: Documento | None = None


def modo(ruta: Path = CONFIGURACION) -> str:
    """El modo del cerrojo. Lo que no sea «aplicar» es observar."""
    try:
        valor = json.loads(ruta.read_text(encoding="utf-8")).get("modo")
    except (OSError, ValueError, AttributeError):
        return OBSERVAR
    return APLICAR if valor == APLICAR else OBSERVAR


# --- Los datos, comparables ------------------------------------------------------------------


def _objetivo(documento: Documento) -> Any:
    objetivo = documento.get("objetivo")
    if not objetivo:
        return None
    return {c: objetivo.get(c) for c in ("categoria", "oaci") if objetivo.get(c)}


def _lugar(documento: Documento) -> Documento:
    lugar = documento.get("lugar") or {}
    punto = lugar.get("punto") or {}
    return {
        "pais": lugar.get("pais"),
        "nivel": lugar.get("nivel"),
        "localidad": str(lugar.get("localidad") or "").casefold() or None,
        "lat": round(punto["lat"], 2) if "lat" in punto else None,
        "lon": round(punto["lon"], 2) if "lon" in punto else None,
    }


def _inicio(documento: Documento) -> Documento:
    tiempo = documento.get("tiempo") or {}
    inicio, fin = tiempo.get("inicio") or {}, tiempo.get("fin") or {}
    return {"valor": inicio.get("valor"), "precision": inicio.get("precision"),
            "fin": fin.get("valor")}  # fmt: skip


def _cierre(documento: Documento) -> Documento:
    cierre = (documento.get("consecuencias") or {}).get("cierre") or {}
    return {"valor": cierre.get("valor"), "minutos": cierre.get("minutos")}


_VALORES: dict[str, Callable[[Documento], Any]] = {
    "estado": lambda d: (d.get("estado") or {}).get("actual"),
    "presencia_dron": lambda d: d.get("presencia_dron"),
    "tipo": lambda d: d.get("tipo"),
    "objetivo": _objetivo,
    "lugar": _lugar,
    "inicio": _inicio,
    "drones": lambda d: (d.get("drones") or {}).get("numero", "desconocido"),
    "cierre": _cierre,
    "titulo": lambda d: {c: v for c, v in (d.get("titulo") or {}).items() if c in ("es", "en")},
    "retirado": lambda d: "retirado" in d,
}


def valor(documento: Documento, dato: str) -> Any:
    return _VALORES[dato](documento)


def huella(dato: str, documento: Documento) -> str:
    """La huella del valor de un dato: la misma en el cerrojo y en la auditoría X."""
    texto = json.dumps(valor(documento, dato), sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(texto.encode()).hexdigest()[:12]


def _distinto(dato: str, antes: Any, despues: Any) -> bool:
    if dato == "lugar":
        # Rellenar lo que no estaba (una localidad) no cambia lo decidido.
        return any(v is not None and despues.get(c) != v for c, v in antes.items())
    return bool(antes != despues)


# --- Quién está protegido --------------------------------------------------------------------


def _ids_de(entrada: Any) -> set[str]:
    if not isinstance(entrada, dict):
        return set()
    ids = {str(entrada["incidente"])} if isinstance(entrada.get("incidente"), str) else set()
    for clave in ("registros", "incidentes"):
        if isinstance(entrada.get(clave), list):
            ids |= {str(i) for i in entrada[clave]}
    return ids


@cache
def fichas_manuales() -> frozenset[str]:
    """Las fichas revisadas a mano y las del conjunto de referencia."""
    revisadas = json.loads(incidentes.REVISADOS.read_text(encoding="utf-8"))
    ids: set[str] = set()
    for seccion in revisadas.values():
        if isinstance(seccion, list):
            for entrada in seccion:
                ids |= _ids_de(entrada)
    referencia = json.loads(FICHAS_REFERENCIA.read_text(encoding="utf-8"))
    return frozenset(ids | {str(f["id"]) for f in referencia["fichas"]})


def _autoridad(documento: Documento, fuente_id: str | None) -> bool:
    return any(
        f.get("id") == fuente_id and declaraciones.de_autoridad(f)
        for f in documento.get("fuentes", [])
    )


def _decidido_por_autoridad(guardado: Documento, dato: str) -> bool:
    if dato == "estado":
        return _autoridad(guardado, decidir.decidir_estado(guardado).fuente_id)
    confirmada = guardado.get("presencia_dron") == "confirmada"
    decision = decidir.decidir_presencia(guardado, confirmada=confirmada)
    return decision.regla == "rectificacion" or _autoridad(guardado, decision.fuente_id)


def candidatos(guardado: Documento, nuevo: Documento) -> list[Cambio]:
    """Los cambios de `nuevo` a lo protegido de `guardado`, antes de mirar si tienen
    justificación. Solo de una ficha publicada: el alta y lo ya retirado o fundido no entran."""
    if not incidentes.activo(guardado):
        return []
    manual = str(guardado["id"]) in fichas_manuales()
    cambios: dict[str, Cambio] = {}
    for dato in DATOS_MANUAL if manual else ():
        antes, despues = valor(guardado, dato), valor(nuevo, dato)
        if _distinto(dato, antes, despues):
            cambios[dato] = Cambio(dato, MANUAL, antes, despues)
    for dato in decididos.juicios(nuevo, guardado):
        if dato not in cambios:
            cambios[dato] = Cambio(dato, CON_CITA, valor(guardado, dato), valor(nuevo, dato))
    for dato in ("estado", "presencia_dron"):
        antes, despues = valor(guardado, dato), valor(nuevo, dato)
        if dato not in cambios and antes != despues and _decidido_por_autoridad(guardado, dato):
            cambios[dato] = Cambio(dato, CON_CITA, antes, despues)
    if "retirado" in nuevo and "retirado" not in cambios:
        # El repaso retiró fichas que contaba una autoridad (EODI-2026-00181, 29/10/2026): esas no
        # las retira ni una decisión automática. Las demás, solo una decisión explícita: un fallo
        # técnico retiró EODI-2026-00130 y EODI-2026-00302 (1/11/2026).
        autoridad = any(declaraciones.de_autoridad(f) for f in guardado.get("fuentes", []))
        cambios["retirado"] = Cambio("retirado", CON_CITA if autoridad else PUBLICADA, False, True)
    return list(cambios.values())


# --- Qué lo justifica ------------------------------------------------------------------------


def _revisado(nuevo: Documento, dato: str) -> bool:
    """Una revisión a mano fija ese dato y `decidir.aplicar` ya ha puesto su valor. El inicio de
    «titulares» y el objetivo revisado no los pone `decidir` en todos los caminos: el primero solo
    pasa por la revisión (aquí no cuenta) y el segundo, si trae el valor revisado."""
    id_ = str(nuevo["id"])
    if dato == "presencia_dron":
        return id_ in decidir.presencias_revisadas()
    if dato == "titulo":
        return id_ in decidir._titulos_revisados() or "titulo" in decidir.revisiones(nuevo)
    if dato == "objetivo":
        from recogida import revisados

        if "objetivo" in decidir.revisiones(nuevo):
            return True
        revisado = revisados.objetivo_revisado(id_)
        objetivo = nuevo.get("objetivo") or {}
        return revisado is not None and all(
            objetivo.get(c) == revisado[c] for c in ("categoria", "nombre") if c in revisado
        )
    return dato in decidir.revisiones(nuevo)


def rectificacion_nueva(guardado: Documento, nuevo: Documento) -> bool:
    """`nuevo` trae un paso de `presencia_historial` que la guardada no tenía."""
    previos = guardado.get("presencia_historial") or []
    return any(
        p not in previos and not rectificaciones.es_nota(p)
        for p in nuevo.get("presencia_historial") or []
    )


def _articulo(fuente: Documento) -> str:
    return str(fuente.get("id", "")).partition("-declaracion-")[0]


def fuentes_nuevas(guardado: Documento, nuevo: Documento) -> list[Documento]:
    """Las fuentes de `nuevo` de un artículo que la guardada no tenía: otra declaración sacada del
    mismo artículo no es una fuente nueva (EODI-2025-00043, 1 de noviembre de 2026)."""
    enlaces = {f.get("enlace") for f in guardado.get("fuentes", [])}
    articulos = {_articulo(f) for f in guardado.get("fuentes", [])}
    return [
        f
        for f in nuevo.get("fuentes", [])
        if f.get("enlace") not in enlaces and _articulo(f) not in articulos
    ]


def fuente_nueva_con_frase(
    dato: str, guardado: Documento, nuevo: Documento, texto_de: Callable[[Documento], str],
) -> bool:  # fmt: skip
    """Una fuente de un artículo nuevo respalda el dato con una frase literal en lo guardado de
    ese artículo (`texto_de`: titular y frases de su extracción)."""
    campos = CAMPOS_AFIRMACION.get(dato, ())
    for fuente in fuentes_nuevas(guardado, nuevo):
        dice = dato == "retirado" or set(campos) & set(fuente.get("campos_respaldados", [])) or any(
            a.get("campo") in campos and a.get("fuente_id") == fuente.get("id")
            for a in nuevo.get("afirmaciones", [])
        )  # fmt: skip
        frase = str(fuente.get("frase_origen") or "")
        if dice and frase and reglas.frase_valida(frase, texto_de(fuente)):
            return True
    return False


def pila() -> list[str]:
    """Quién guarda: los pasos de la pila fuera del almacén y de este módulo, del más cercano al
    más lejano (como mucho 6, «módulo.función»)."""
    salida: list[str] = []
    marco = sys._getframe(1)
    while marco is not None and len(salida) < 6:
        modulo = str(marco.f_globals.get("__name__", ""))
        if modulo not in ("almacen.base", __name__):
            salida.append(f"{modulo}.{marco.f_code.co_name}")
        marco = marco.f_back  # type: ignore[assignment]
    return salida


def por_revision(pasos: Iterable[str]) -> bool:
    """Guarda una revisión a mano (recogida/revisados.py), y no una extracción lanzada desde ella:
    la parte de una separación que rehace el extractor no es lo que dijo la revisión."""
    for paso in pasos:
        if paso.startswith("proceso.extraccion."):
            return False
        if paso.startswith("recogida.revisados."):
            return True
    return False


def por_decision(pasos: Iterable[str]) -> bool:
    """La retirada sale de una decisión explícita (`DECISIONES_RETIRADA`)."""
    return any(paso.startswith(DECISIONES_RETIRADA) for paso in pasos)


def juzgar(
    guardado: Documento, nuevo: Documento, pasos: list[str],
    texto_de: Callable[[Documento], str],
) -> Veredicto:  # fmt: skip
    """Reparte los cambios a lo protegido en retenidos y permitidos, dato a dato."""
    veredicto = Veredicto()
    pendientes = candidatos(guardado, nuevo)
    if not pendientes:
        return veredicto
    revision = por_revision(pasos)
    rectificada = rectificacion_nueva(guardado, nuevo)
    justificados: set[str] = set()

    def razon(cambio: Cambio) -> str | None:
        # La revisión del cierre fija si lo hubo: no da permiso para perder su duración.
        pierde = (
            cambio.dato == "cierre" and cambio.antes["minutos"] and not cambio.despues["minutos"]
        )
        if revision or (_revisado(nuevo, cambio.dato) and not pierde):
            return "revision"
        if rectificada and cambio.dato in ("presencia_dron", "titulo"):
            return "rectificacion"
        if cambio.nivel == PUBLICADA and por_decision(pasos):
            return "decision"
        if cambio.dato == "titulo" and justificados & set(TITULO_SIGUE_A):
            return "sigue_a_lo_justificado"
        if cambio.nivel == CON_CITA and fuente_nueva_con_frase(
            cambio.dato, guardado, nuevo, texto_de
        ):
            return "fuente_nueva"
        return None

    # El titular, el último: sigue a los datos que cambian con justificación.
    for cambio in sorted(pendientes, key=lambda c: c.dato == "titulo"):
        motivo = razon(cambio)
        if motivo is None:
            veredicto.retenidos.append(cambio)
        else:
            justificados.add(cambio.dato)
            veredicto.permitidos.append((cambio, motivo))
    return veredicto


def _tipo_guardado(resultado: Documento, guardado: Documento) -> None:
    resultado["tipo"] = guardado.get("tipo")
    if "origen_demostrado_por" in guardado:
        resultado["origen_demostrado_por"] = guardado["origen_demostrado_por"]
    else:
        resultado.pop("origen_demostrado_por", None)


def conservar(nuevo: Documento, guardado: Documento, cambios: Iterable[Cambio]) -> Documento:
    """`nuevo` con el valor de `guardado` en cada dato retenido, con sus afirmaciones. Una retirada
    retenida deja la versión publicada entera."""
    cambios = list(cambios)
    if any(cambio.dato == "retirado" for cambio in cambios):
        return copy.deepcopy(guardado)
    resultado = copy.deepcopy(nuevo)
    fuentes = {f.get("id") for f in resultado.get("fuentes", [])}
    for cambio in cambios:
        dato = cambio.dato
        if dato in decididos.DATOS:
            decididos._poner(resultado, guardado, dato)
            if dato == "cierre":
                # El tipo sigue al cierre: con cierre, «interrupción» (proceso/incidentes.con_tipo).
                _tipo_guardado(resultado, guardado)
        elif dato == "estado":
            resultado["estado"] = copy.deepcopy(guardado["estado"])
            control = resultado["control"]
            control.pop("motivo_desmentido", None)
            if motivo := (guardado.get("control") or {}).get("motivo_desmentido"):
                control["motivo_desmentido"] = motivo
        elif dato == "presencia_dron":
            resultado["presencia_dron"] = guardado.get("presencia_dron")
            resultado["afirmaciones"] = [
                *(a for a in resultado.get("afirmaciones", []) if a.get("campo") != dato),
                *(copy.deepcopy(a) for a in guardado.get("afirmaciones", [])
                  if a.get("campo") == dato and a.get("fuente_id") in fuentes),
            ]  # fmt: skip
        elif dato == "tipo":
            _tipo_guardado(resultado, guardado)
        elif dato == "objetivo":
            if "objetivo" in guardado:
                resultado["objetivo"] = copy.deepcopy(guardado["objetivo"])
            else:
                resultado.pop("objetivo", None)
        elif dato == "titulo":
            resultado["titulo"] = copy.deepcopy(guardado["titulo"])
    return resultado


# --- Uniones ---------------------------------------------------------------------------------


def raiz_de(id_: str, enlaces: dict[str, str]) -> str:
    """La ficha en que acaba la cadena de uniones de `id_`."""
    vistos = {id_}
    while id_ in enlaces and enlaces[id_] not in vistos:
        id_ = enlaces[id_]
        vistos.add(id_)
    return id_


def colgados_de(id_: str, enlaces: dict[str, str]) -> set[str]:
    """`id_` y todas las fichas que cuelgan de ella, directa o encadenadamente."""
    hijos: dict[str, list[str]] = {}
    for hijo, padre in enlaces.items():
        hijos.setdefault(padre, []).append(hijo)
    grupo, pendientes = {id_}, [id_]
    while pendientes:
        for hijo in hijos.get(pendientes.pop(), []):
            if hijo not in grupo:
                grupo.add(hijo)
                pendientes.append(hijo)
    return grupo


def grupos(absorbido: str, destino: str, enlaces: dict[str, str]) -> tuple[set[str], set[str]]:
    """Las dos partes de una unión: lo que cuelga de la absorbida y todo lo que hay en el grupo de
    la destinataria (sin las de la absorbida, si ya colgaba de ese grupo)."""
    sin_el = {h: p for h, p in enlaces.items() if h != absorbido}
    propio = colgados_de(absorbido, sin_el)
    ajeno = colgados_de(raiz_de(destino, sin_el), sin_el) - propio
    return propio, ajeno


def par_prohibido(
    uno: Documento, otro: Documento, prohibidos: frozenset[frozenset[str]],
    a_mano: Iterable[frozenset[str]],
) -> str | None:  # fmt: skip
    """Por qué no se unen dos fichas sueltas, o None. Una unión hecha a mano manda sobre la marca
    anterior (EODI-2026-00527 en EODI-2026-00263, la separación del 20/10/2026)."""
    par = frozenset((str(uno["id"]), str(otro["id"])))
    if any(par <= grupo for grupo in a_mano):
        return None
    propio = {k: v for k, v in uno.items() if k != "fusionado_en"}
    ajeno = {k: v for k, v in otro.items() if k != "fusionado_en"}
    if incidentes.separados_por_revision(propio, ajeno):
        return "revision"
    if par in prohibidos:
        return "prohibido"
    if incidentes.de_partes_separadas(propio, ajeno):
        return "partes"
    return None


def pares_a_mano(almacen: Any) -> list[frozenset[str]]:
    datos = json.loads(incidentes.REVISADOS.read_text(encoding="utf-8"))
    return [*incidentes.uniones_a_mano(almacen),
            *(frozenset(g["registros"]) for g in datos.get("unir", []))]  # fmt: skip


def union_prohibida(
    almacen: Any, absorbido: Documento, destino: str, renumerada: bool = False
) -> Documento | None:
    """El par prohibido que juntaría marcar `absorbido` como fundida en `destino`, mirando los dos
    grupos enteros. `renumerada`: la destinataria acaba de dejar de colgar de la absorbida (la
    renumeración que conserva la ficha más antigua): es el mismo grupo con otro número."""
    enlaces = almacen.enlaces_de_fusion()
    actual = enlaces.get(str(absorbido["id"]))
    if renumerada or (actual and raiz_de(actual, enlaces) == raiz_de(destino, enlaces)):
        return None
    propio, ajeno = grupos(str(absorbido["id"]), destino, enlaces)
    from recogida import revisados

    prohibidos = incidentes.distintos_del_experto(almacen) | revisados.pares_de_partes(almacen)
    a_mano = pares_a_mano(almacen)
    documentos = {i: almacen.incidente(i) for i in propio | ajeno}
    documentos[str(absorbido["id"])] = absorbido
    for uno in sorted(propio):
        for otro in sorted(ajeno):
            a, b = documentos.get(uno), documentos.get(otro)
            if a is None or b is None:
                continue
            motivo = par_prohibido(a, b, prohibidos, a_mano)
            if motivo is not None:
                return {"uno": uno, "otro": otro, "motivo": motivo}
    return None


def union_de_manual(
    almacen: Any, guardado: Documento, destino: str, renumerada: bool = False
) -> Documento | None:
    """La unión que haría desaparecer una ficha publicada del nivel manual sin par prohibido (la
    simulación del 1 de noviembre de 2026 unió así EODI-2025-00043 en EODI-2026-00048), o None.
    Mira la ficha que se funde: la que queda, si es manual, conserva dato a dato lo decidido, y
    recibir un duplicado no le quita nada. Una unión a mano anterior manda, como en los pares."""
    id_ = str(guardado["id"])
    if renumerada or id_ not in fichas_manuales() or not incidentes.activo(guardado):
        return None
    par = frozenset((id_, destino))
    if any(par <= grupo for grupo in pares_a_mano(almacen)):
        return None
    return {"uno": id_, "otro": destino, "motivo": "manual"}


def por_renumeracion(pasos: Iterable[str]) -> bool:
    """La ficha más antigua de un grupo vuelve a ser la que queda: el mismo grupo con otro número
    (recogida/control_fichas.conservar_la_mas_antigua), no una reapertura."""
    return PASO_RENUMERAR in pasos


def es_separacion(almacen: Any, documento: Documento, destino: str) -> bool:
    """Deshacer la unión de `documento` con `destino` separa un par que no se une: revisión,
    partes de una separación, distintos del experto o relacionados. Aquí no cuenta una unión a
    mano: que dos fichas se unieran es justo lo que esa separación deshace."""
    otro = almacen.incidente(destino)
    if otro is None:
        return False
    from recogida import revisados

    prohibidos = incidentes.distintos_del_experto(almacen) | revisados.pares_de_partes(almacen)
    return par_prohibido(documento, otro, prohibidos, ()) is not None


def cambios_sin_permiso(
    cambios: Iterable[Documento], permitidos: frozenset[tuple[str, str, str]]
) -> list[str]:
    """X: «<id> <dato>» de los cambios guardados a algo protegido sin justificación apuntada
    (`permitidos`: (ficha, dato, huella) de las claves `permitido:`). Con el cerrojo en «aplicar»
    debe ser una lista vacía; cualquier otra cosa es un agujero."""
    salida: set[str] = set()
    for cambio in cambios:
        if cambio.get("tabla", "incidentes") != "incidentes":
            continue
        anterior, nuevo = cambio.get("anterior") or {}, cambio.get("nuevo") or {}
        if not anterior or not nuevo or "id" not in anterior:
            continue
        for propuesto in candidatos(anterior, nuevo):
            clave = (str(anterior["id"]), propuesto.dato, huella(propuesto.dato, nuevo))
            if clave not in permitidos:
                salida.add(f"{anterior['id']} {propuesto.dato}")
    return sorted(salida)


def fallos_seguidos(controles: dict[str, Documento]) -> dict[str, int]:
    """{ficha: fallos seguidos}, de las claves `guardado_fallido:<ficha>:<fecha>`: cuenta desde el
    último guardado bueno de esa ficha, apuntado con `resuelto`."""
    seguidos: dict[str, int] = {}
    orden = sorted(controles.items(), key=lambda c: (str(c[1].get("fecha")), c[0]))
    for clave, apunte in orden:
        ficha = clave.split(":")[1]
        seguidos[ficha] = 0 if apunte.get("resuelto") else seguidos.get(ficha, 0) + 1
    return {ficha: cuenta for ficha, cuenta in seguidos.items() if cuenta}


def permitidos(controles: dict[str, Documento]) -> frozenset[tuple[str, str, str]]:
    """(ficha, dato, huella) de las claves `permitido:<ficha>:<dato>:<huella>`."""
    resultado = set()
    for clave in controles:
        partes = clave.split(":")
        if len(partes) == 4:
            resultado.add((partes[1], partes[2], partes[3]))
    return frozenset(resultado)
