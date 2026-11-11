"""Lo protegido: la lista única de lo que ya está decidido en una ficha y el cerrojo que lo guarda.

Toda escritura de una ficha pasa por `Almacen.guardar_incidente`, que llama aquí después de
`rectificaciones.mantener` y `decidir.aplicar` y antes de escribir. Nada de esto tiene fichero de
configuración propio: se calcula de lo que ya existe.

- **Nivel manual**: las fichas revisadas a mano (configuracion/incidentes_revisados.json) y las del
  conjunto de referencia (tests/referencia/fichas.json). Solo cambian por una revisión a mano o
  por una rectificación oficial nueva. El titular y el estado se guardan si los fija una revisión;
  la presencia, el lugar, los drones, el inicio y el cierre, además, si los dice una frase
  (`DE_FRASE`); el tipo, el objetivo y la retirada, siempre.
- **Nivel con cita**: en cualquier ficha publicada, los datos decididos con la frase de una fuente
  (proceso/decididos.py) y el estado y la presencia que decide una autoridad. Solo cambian si una
  fuente de un artículo que la ficha no tenía trae una frase literal que dice el valor nuevo
  (`fuente_nueva_con_frase`).
- **Nivel publicada**: la retirada de cualquier ficha publicada. Solo pasa si viene de una decisión
  explícita (`por_decision`): nunca de un fallo al guardar o rehacer (docs/cerrojo.md).
- **Uniones prohibidas**: los pares que no se unen (`distintos`, partes de una separación, los
  distintos del experto, los relacionados). Se miran entre grupos enteros: todas las fichas que
  cuelgan de la destinataria contra todas las de la absorbida, así que ni una cadena de uniones ni
  una renumeración las saltan.
- **Fichas del nivel manual que se funden**: sin par prohibido, solo las une una revisión a mano.
- **Reaperturas**: una ficha fundida deja de estarlo solo por una revisión a mano o una separación.

Una frase respalda un dato solo si lo dice (`dice_el_dato`): el número en los drones, la hora en un
inicio con hora. Lo que no dice ninguna frase se puede corregir. El titular y el estado siguen a la
presencia, los drones, el lugar y el inicio: si se retiene uno de ellos, también (`SIGUEN_A`).

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
import re
import sys
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import date, timedelta
from functools import cache
from pathlib import Path
from typing import Any

from esquema import Documento
from proceso import control_fichas as reglas
from proceso import (
    decididos,
    decidir,
    declaraciones,
    incidentes,
    rectificaciones,
    suceso,
    textos_dron,
)

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
# Las retiradas de una regla explícita que pasan por `extraccion.retirar`: se reconocen por los dos
# pasos más cercanos, no por cualquier paso de la pila (un fallo dentro de una reconstrucción no es
# la decisión de retirar una copia). Las tres de la noche del 1 al 2 de noviembre de 2026: el alta
# que salía solo del parte ucraniano (EODI-2026-00482), la alta oficial cuyo día no está en su frase
# (EODI-2024-00002) y la copia numerada de más al reconstruir (EODI-2026-00254). Con una autoridad
# en la ficha, ni estas bastan: piden una revisión a mano o una fuente nueva con su frase.
DECISIONES_RETIRADA_DIRECTAS = (
    ("proceso.extraccion.retirar", "proceso.incursiones.retirar"),
    ("proceso.extraccion.retirar", "proceso.extraccion_oficial.revalidar_altas"),
    ("proceso.extraccion.retirar", "proceso.extraccion.reconstruir"),
)  # fmt: skip
# Las fichas que nunca salieron en la web (las retiene el filtro de entrada): su retirada a las 6
# horas sin fecha verificable no quita nada publicado (recogida/control_fichas.resolver_sin_fecha).
DECISIONES_SIN_PUBLICAR = ("recogida.control_fichas.resolver_sin_fecha",)
# Una fuente no cuenta un suceso posterior a su publicación: margen en días para la zona horaria y
# las fechas aproximadas de publicación (EODI-2026-00079: una nota del 17 de febrero de 2026 acabó
# en una ficha del 11 de agosto).
MARGEN_FUENTE_ANTERIOR = 2
# Las comprobaciones de la auditoría que miran lo protegido (proceso/auditoria_fichas.py).
AUDITORIA = ("P", "R", "V", "W", "X")

DATOS_MANUAL = (
    "estado", "presencia_dron", "tipo", "objetivo", "lugar", "inicio", "drones", "modelo",
    "cierre", "titulo", "retirado",
)  # fmt: skip
# Las afirmaciones que dicen cada dato (además de las de decididos para el resto).
CAMPOS_AFIRMACION = {
    **decididos._CAMPOS_AFIRMACION,
    "estado": ("estado",),
    "presencia_dron": ("presencia_dron",),
    "tipo": ("tipo",),
    "objetivo": ("objetivo_nombre", "objetivo_categoria", "objetivo_conocido"),
    "modelo": ("modelo_dron",),
    "titulo": (),
}
# La comprobación de toda la versión: una fuente publicada antes del día del suceso.
COHERENCIA = "fuente_anterior"
# Lo que deja el titular tal como está decidido: si lo justificado cambia, el titular lo sigue.
TITULO_SIGUE_A = ("presencia_dron", "drones", "lugar", "objetivo", "tipo")
# Si se retiene uno de estos, el titular y el estado se quedan como estaban: son su resumen
# (con la presencia retenida pasaría «Posible dron…» en EODI-2025-00178, 00472 y EODI-2026-00694).
# El cierre y el modelo también (EODI-2026-00725: «con restricciones del espacio aéreo» seguía a un
# cierre que ninguna frase da; «Un dron Gerbera…» nombra el modelo).
SIGUEN_A = ("presencia_dron", "drones", "lugar", "inicio", "cierre", "modelo")
SEGUIDORES = ("titulo", "estado")
# Los datos con un valor que se puede buscar en la frase: una frase que no lo dice no los respalda.
DE_FRASE = ("drones", "inicio", "presencia_dron", "lugar", "cierre", "modelo")
RESPALDO_FIRME = ("revision", "rectificacion")
# Una hora escrita: 10:26, 22.30, 7h15, 22 Uhr, klokken 14. No una fecha (11.03.2026).
_HORA = re.compile(
    r"(?<![\d.:])(?:[01]?\d|2[0-3])[.:h][0-5]\d(?![.\d])"
    r"|(?<!\d)\d{1,2}\s?(?:uhr|val\b|pm\b|am\b|h\b|hours?\b|godz)"
    r"|(?:klokken|kl\.|ora|godz\.?)\s?\d",
    re.IGNORECASE,
)
_PALABRAS_NUMERO = {
    palabra.casefold(): numero
    for tabla in textos_dron.NUMEROS.values()
    for palabra, numero in tabla.items()
}


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
    "modelo": lambda d: (d.get("drones") or {}).get("modelo") or None,
    COHERENCIA: lambda d: fuentes_anteriores(d),
}


def valor(documento: Documento, dato: str) -> Any:
    return _VALORES[dato](documento)


def huella(dato: str, documento: Documento) -> str:
    """La huella del valor de un dato: la misma en el cerrojo y en la auditoría X."""
    texto = json.dumps(valor(documento, dato), sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(texto.encode()).hexdigest()[:12]


def fuentes_anteriores(documento: Documento) -> list[str]:
    """Las fuentes publicadas más de `MARGEN_FUENTE_ANTERIOR` días antes del día del suceso: una
    nota no cuenta lo que aún no ha pasado. Si las hay, la ficha junta dos sucesos (EODI-2026-00079,
    una nota del 17 de febrero de 2026 en una ficha del 11 de agosto, 2 de noviembre de 2026)."""
    inicio = str((((documento.get("tiempo") or {}).get("inicio")) or {}).get("valor") or "")[:10]
    if len(inicio) != 10:
        return []
    try:
        limite = date.fromisoformat(inicio) - timedelta(days=MARGEN_FUENTE_ANTERIOR)
    except ValueError:
        return []
    salida = []
    for fuente in documento.get("fuentes", []):
        publicada = str((fuente.get("fecha") or {}).get("valor") or "")[:10]
        try:
            if len(publicada) == 10 and date.fromisoformat(publicada) < limite:
                salida.append(str(fuente.get("id")))
        except ValueError:
            continue
    return sorted(salida)


def _distinto(dato: str, antes: Any, despues: Any) -> bool:
    if dato == "lugar":
        # Rellenar lo que no estaba (una localidad) no cambia lo decidido.
        return any(v is not None and despues.get(c) != v for c, v in antes.items())
    if dato == "modelo" and antes and despues:
        # Otra redacción del mismo modelo («витлов самолет» y «безпилотен летателен апарат тип
        # "витлов самолет"», EODI-2025-00068) no lo cambia.
        uno, otro = (re.sub(r"[\W_]+", "", str(v).casefold()) for v in (antes, despues))
        return not (uno in otro or otro in uno)
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
def valores_de_referencia() -> dict[str, dict[str, Any]]:
    """{ficha: {dato: valor}} del conjunto de referencia, comprobado contra sus fuentes."""
    referencia = json.loads(FICHAS_REFERENCIA.read_text(encoding="utf-8"))
    return {
        str(f["id"]): {dato: v.get("valor") for dato, v in f["valores"].items()}
        for f in referencia["fichas"]
    }


def _fijado_en_referencia(guardado: Documento, dato: str) -> bool:
    """La ficha tiene ese valor del dato en el conjunto de referencia: también un «sin dato», que
    ninguna frase dice (EODI-2026-00515, un dron que nadie encontró)."""
    if dato not in ("estado", "presencia_dron", "drones"):
        return False
    esperado = valores_de_referencia().get(str(guardado["id"]), {}).get(dato)
    if isinstance(esperado, int):
        esperado = {"min": esperado, "max": esperado}
    return esperado is not None and esperado == valor(guardado, dato)


@cache
def fichas_manuales() -> frozenset[str]:
    """Las fichas revisadas a mano y las del conjunto de referencia."""
    revisadas = json.loads(suceso.REVISADOS.read_text(encoding="utf-8"))
    ids: set[str] = set()
    for seccion in revisadas.values():
        if isinstance(seccion, list):
            for entrada in seccion:
                ids |= _ids_de(entrada)
    return frozenset(ids) | frozenset(valores_de_referencia())


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


def _numeros_de(frase: str) -> set[int]:
    """Los números que dice una frase, en cifras o con palabras (hasta doce: textos_dron)."""
    numeros = {int(n) for n in re.findall(r"(?<![\d.,:])\d{1,4}(?![\d:])", frase)}
    palabras = re.findall(r"[^\W\d_]+", frase.casefold())
    return numeros | {_PALABRAS_NUMERO[p] for p in palabras if p in _PALABRAS_NUMERO}


def dice_el_dato(dato: str, frase: str, dicho: Any) -> bool:
    """La frase dice ese valor del dato: una frase sin número no respalda un número, ni una sin hora
    una hora (EODI-2026-00714, «multiple drones»; EODI-2026-00013, una hora que ninguna fuente da).
    Un dron no se puede exigir con palabras: en la frase, en singular, no hay número que buscar."""
    if not frase:
        return False
    if dato == "drones":
        if not isinstance(dicho, dict):
            return False
        extremos = {dicho.get("min"), dicho.get("max")}
        # Un intervalo lo dice la frase que da sus dos extremos: «9 drone» no dice «de 9 a 19»
        # (EODI-2026-00744, un balance mensual con 19 violaciones del espacio aéreo).
        return extremos == {1} or extremos <= _numeros_de(frase)
    if dato == "inicio" and dicho.get("precision") != "dia":
        return bool(_HORA.search(frase))
    if dato == "modelo":
        # El modelo lo dice la frase que lo nombra (Shahed, Gerbera, Geran-2...).
        nombre = re.sub(r"[\W_]+", "", str(dicho or "").casefold())
        return bool(nombre) and nombre in re.sub(r"[\W_]+", "", frase.casefold())
    return True


def _frase_de(documento: Documento, fuente_id: Any) -> str:
    return next(
        (str(f.get("frase_origen") or "") for f in documento.get("fuentes", [])
         if f.get("id") == fuente_id), "",
    )  # fmt: skip


def _lo_dice_una_frase(guardado: Documento, dato: str) -> bool:
    """Una fuente de la ficha afirma ese valor del dato con una frase que lo dice. El inicio lo da
    también la fuente de `origen_inicio`."""
    if dato not in DE_FRASE:
        return True
    campos = CAMPOS_AFIRMACION.get(dato, ())
    afirmaciones = guardado.get("afirmaciones", [])
    fuentes = [
        a.get("fuente_id")
        for a in afirmaciones
        if a.get("campo") in campos
        and (dato != "presencia_dron" or a.get("valor") == valor(guardado, dato))
    ]
    if dato == "inicio":
        origen = (guardado.get("tiempo") or {}).get("origen_inicio") or {}
        fuentes.append(origen.get("fuente_id"))
    dicho = valor(guardado, dato)
    return any(dice_el_dato(dato, _frase_de(guardado, f), dicho) for f in fuentes)


def _cierre_dicho(documento: Documento) -> bool:
    """Alguna frase de una fuente que afirma el cierre nombra un cierre, una suspensión o un
    desvío (proceso/presencia.CIERRE_EN_FRASE). Sin afirmación del cierre, la de cualquier
    fuente."""
    from proceso import presencia

    ids = {a.get("fuente_id") for a in documento.get("afirmaciones", []) if a.get("campo") in
           ("cierre", "cierre_minutos")}  # fmt: skip
    fuentes = [f for f in documento.get("fuentes", []) if not ids or f.get("id") in ids]
    return any(presencia.CIERRE_EN_FRASE.search(str(f.get("frase_origen") or "")) for f in fuentes)


def _fijado_a_mano(guardado: Documento, dato: str) -> bool:
    """Una revisión a mano fija ese dato en la ficha (cualquier sección de las revisiones)."""
    if dato == "inicio" and str(guardado["id"]) in decidir._inicios_revisados():
        return True
    return _hay_revision(guardado, dato)


def _respaldado(guardado: Documento, dato: str) -> bool:
    """El dato de una ficha manual que el cerrojo guarda: lo que fija una revisión y lo que dice una
    frase. El titular y el estado no tienen frase propia: sin revisión siguen a lo retenido
    (`SIGUEN_A`)."""
    if _fijado_a_mano(guardado, dato) or _fijado_en_referencia(guardado, dato):
        return True
    return dato not in SEGUIDORES and _lo_dice_una_frase(guardado, dato)


def candidatos(guardado: Documento, nuevo: Documento, publicada: bool = True) -> list[Cambio]:
    """Los cambios de `nuevo` a lo protegido de `guardado`, antes de mirar si tienen
    justificación. El alta y lo ya retirado o fundido no entran.

    Con `publicada` falso (una ficha nueva que sigue en el filtro de entrada,
    `Almacen.en_el_filtro`) solo cuenta el nivel manual: lo que fija una revisión. Lo decidido
    «con cita» se protege cuando la ficha ha salido; antes, el filtro corregía el día o el lugar y
    el cerrojo se lo devolvía (EODI-2026-00728 y 00765, noviembre de 2026)."""
    if not incidentes.activo(guardado):
        return []
    manual = str(guardado["id"]) in fichas_manuales()
    cambios: dict[str, Cambio] = {}
    for dato in DATOS_MANUAL if manual else ():
        antes, despues = valor(guardado, dato), valor(nuevo, dato)
        # En el filtro de entrada, solo lo que fija una revisión o la referencia: lo que «dice
        # una frase» es justo lo que el filtro comprueba (EODI-2026-00728, del nivel manual: 3
        # correcciones del filtro retenidas).
        fijo = (
            _respaldado(guardado, dato)
            if publicada
            else _fijado_a_mano(guardado, dato) or _fijado_en_referencia(guardado, dato)
        )
        if _distinto(dato, antes, despues) and fijo:
            cambios[dato] = Cambio(dato, MANUAL, antes, despues)
    if not publicada:
        return list(cambios.values())
    for dato in decididos.juicios(nuevo, guardado):
        if dato not in cambios and _lo_dice_una_frase(guardado, dato):
            cambios[dato] = Cambio(dato, CON_CITA, valor(guardado, dato), valor(nuevo, dato))
    # El modelo de dron que nombra la frase de una fuente, en cualquier ficha publicada: el mismo
    # criterio que el número (EODI-2025-00261 volvía a Shahed tras su revisión, 1/11/2026).
    antes, despues = valor(guardado, "modelo"), valor(nuevo, "modelo")
    if (
        "modelo" not in cambios
        and antes
        and _distinto("modelo", antes, despues)
        and _lo_dice_una_frase(guardado, "modelo")
    ):
        cambios["modelo"] = Cambio("modelo", CON_CITA, antes, despues)
    # Un cierre nuevo lo dice una frase que nombra el cierre: una alerta a la población no cierra
    # nada (EODI-2026-00725, «O avertizare RO-Alert a fost transmisă... pentru județul Suceava»).
    antes, despues = valor(guardado, "cierre"), valor(nuevo, "cierre")
    if (
        "cierre" not in cambios
        and despues.get("valor") == "si"
        and antes.get("valor") != "si"
        and not _cierre_dicho(nuevo)
    ):
        cambios["cierre"] = Cambio("cierre", CON_CITA, antes, despues)
    # Una fuente publicada antes del día del suceso que la versión guardada no tenía: la versión
    # nueva junta dos sucesos (EODI-2026-00079). Solo la deshace una revisión.
    anteriores = set(fuentes_anteriores(nuevo)) - set(fuentes_anteriores(guardado))
    if anteriores:
        cambios[COHERENCIA] = Cambio(COHERENCIA, PUBLICADA, [], sorted(anteriores))
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
    """Una revisión a mano fija ese dato y `nuevo` trae su valor: un cambio a otro valor va contra
    la revisión, no sale de ella (EODI-2025-00472, EODI-2026-00728)."""
    if not _hay_revision(nuevo, dato):
        return False
    id_ = str(nuevo["id"])
    if dato == "presencia_dron":
        return decidir.presencias_revisadas()[id_] == nuevo.get("presencia_dron")
    if dato == "titulo" and id_ in decidir._titulos_revisados():
        revisado = decidir._titulos_revisados()[id_]
        return all(valor(nuevo, dato).get(c) == revisado.get(c) for c in ("es", "en"))
    if dato == "drones":
        return bool(decidir.revisiones(nuevo)["drones"].get("valor") == valor(nuevo, dato))
    if dato == "modelo":
        return bool(decidir.revisiones(nuevo)["modelo"].get("valor") == valor(nuevo, dato))
    return True


def _hay_revision(nuevo: Documento, dato: str) -> bool:
    """Una revisión a mano fija ese dato. El inicio de «titulares» y el objetivo revisado no los
    pone `decidir` en todos los caminos: el primero solo pasa por la revisión (aquí no cuenta) y el
    segundo, si trae el valor revisado."""
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


def dice_el_valor_nuevo(dato: str, fuente: Documento, nuevo: Documento) -> bool:
    """La fuente nueva dice el valor al que cambia el dato, no solo algo de ese dato: una fuente
    nueva de EODI-2026-00694 no daba hora y la presencia y el inicio cambiaban a peor. Lo que no
    tiene valor que leer en la frase (un sin dato, una hora de publicación) no lo dice nadie."""
    if dato == "retirado":
        return True
    campos = CAMPOS_AFIRMACION.get(dato, ())
    suyas = [
        a
        for a in nuevo.get("afirmaciones", [])
        if a.get("campo") in campos and a.get("fuente_id") == fuente.get("id")
    ]
    dicho = valor(nuevo, dato)
    if dato in ("estado", "presencia_dron", "tipo"):
        return any(a.get("valor") == dicho for a in suyas)
    if not suyas and not set(campos) & set(fuente.get("campos_respaldados", [])):
        return False
    if dato == "cierre" and isinstance(dicho.get("minutos"), dict):
        # Los minutos son {min, max}: la frase tiene que dar los dos extremos.
        minutos = dicho["minutos"]
        extremos = {minutos.get("min"), minutos.get("max")}
        return extremos <= _numeros_de(str(fuente.get("frase_origen") or ""))
    if dato == "cierre" and dicho.get("valor") == "si":
        from proceso import presencia

        return bool(presencia.CIERRE_EN_FRASE.search(str(fuente.get("frase_origen") or "")))
    if dato == "inicio" and dicho.get("precision") == decididos.PRECISIONES[0]:
        return False
    return dice_el_dato(dato, str(fuente.get("frase_origen") or ""), dicho)


def fuente_nueva_con_frase(
    dato: str, guardado: Documento, nuevo: Documento, texto_de: Callable[[Documento], str],
) -> bool:  # fmt: skip
    """Una fuente de un artículo nuevo dice el valor nuevo del dato con una frase literal en lo
    guardado de ese artículo (`texto_de`: titular y frases de su extracción)."""
    for fuente in fuentes_nuevas(guardado, nuevo):
        frase = str(fuente.get("frase_origen") or "")
        if (
            frase
            and dice_el_valor_nuevo(dato, fuente, nuevo)
            and reglas.frase_valida(frase, texto_de(fuente))
        ):
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


# Las funciones de `proceso/extraccion.py` que retiran una ficha (retirar, retirar_del_candidato,
# retirar_por_veredicto): no son una extracción.
RETIRAR = "proceso.extraccion.retirar"


def por_revision(pasos: Iterable[str]) -> bool:
    """Guarda una revisión a mano (recogida/revisados.py), y no una extracción lanzada desde ella:
    la parte de una separación que rehace el extractor no es lo que dijo la revisión."""
    for paso in pasos:
        if paso.startswith(RETIRAR):
            # Quien retira no extrae: `extraccion.retirar` solo pone la marca que le piden. La
            # revisión «reextraer» que retira la ficha que sigue mezclando dos sucesos lo hace
            # con él, y el cerrojo la tomaba por una extracción: en «aplicar» no retiraba una
            # ficha del nivel manual (se vio al pasar las pruebas a «aplicar», 10/11/2026).
            continue
        if paso.startswith("proceso.extraccion."):
            return False
        if paso.startswith("recogida.revisados."):
            return True
    return False


# Quién puede volver a publicar una ficha retirada además de una revisión a mano: la
# reextracción de los retirados sin país, que se pide a mano (recogida/revision.py).
DECISIONES_REPOSICION = ("recogida.revision.reextraer",)


def por_reposicion(pasos: Iterable[str]) -> bool:
    """Quien guarda puede volver a publicar una ficha retirada: una revisión a mano
    (recogida/revisados.py, `_reponer`) o la reextracción pedida a mano."""
    pasos = list(pasos)
    return por_revision(pasos) or any(p.startswith(DECISIONES_REPOSICION) for p in pasos)


# Deshacer una unión (proceso/incidentes.revertir): la ficha que queda pierde las fuentes de la
# absorbida y lo que la unión le copió.
DESHACER_UNION = "proceso.incidentes.revertir"


def por_union_deshecha(pasos: Iterable[str]) -> bool:
    """Guarda `incidentes.revertir`: lo que cambia en la ficha que queda es lo que la unión le
    trajo, que se va con la absorbida. Sin esto el cerrojo le retenía la presencia, el estado o el
    número de drones del otro suceso y, para sostenerlos, le devolvía las fuentes que citaban: la
    unión quedaba deshecha a medias. Que la absorbida pueda volver lo decide aparte la reapertura
    (una revisión, una separación)."""
    return DESHACER_UNION in list(pasos)


# La primera extracción de la parte de una separación con su día y su descripción
# (proceso/extraccion.guardar_parte_separada).
PARTE_SEPARADA = "proceso.extraccion.guardar_parte_separada"


def por_parte_separada(pasos: Iterable[str]) -> bool:
    """Guarda la primera extracción de la parte de una separación, hecha solo con su suceso. La
    ficha mezclada tenía datos «decididos con cita» por frases que cuentan los dos sucesos, y el
    cerrojo se los devolvía a la parte: EODI-2026-00770 (Leipzig/Halle) no podía dejar los dos
    drones ni el titular del sábado y el domingo, y cada separación acababa en revisiones a mano."""
    return PARTE_SEPARADA in list(pasos)


def por_decision(pasos: Iterable[str]) -> bool:
    """La retirada sale de una decisión explícita (`DECISIONES_RETIRADA`, o los dos pasos más
    cercanos de `DECISIONES_RETIRADA_DIRECTAS`, o una ficha que nunca se publicó)."""
    pasos = list(pasos)
    return (
        any(paso.startswith(DECISIONES_RETIRADA) for paso in pasos)
        or tuple(pasos[:2]) in DECISIONES_RETIRADA_DIRECTAS
        or sin_publicar(pasos)
    )


def sin_publicar(pasos: Iterable[str]) -> bool:
    """La retirada es de una ficha que el filtro de entrada nunca dejó salir en la web."""
    return any(paso.startswith(DECISIONES_SIN_PUBLICAR) for paso in pasos)


def juzgar(
    guardado: Documento, nuevo: Documento, pasos: list[str],
    texto_de: Callable[[Documento], str], publicada: bool = True,
) -> Veredicto:  # fmt: skip
    """Reparte los cambios a lo protegido en retenidos y permitidos, dato a dato. `publicada`: la
    ficha no está en el filtro de entrada (`candidatos`)."""
    veredicto = Veredicto()
    pendientes = candidatos(guardado, nuevo, publicada)
    if not pendientes:
        return veredicto
    revision = por_revision(pasos)
    rectificada = rectificacion_nueva(guardado, nuevo)
    deshecha = por_union_deshecha(pasos)
    separada = por_parte_separada(pasos)
    justificados: set[str] = set()

    def razon(cambio: Cambio) -> str | None:
        if (
            separada
            and cambio.dato not in (COHERENCIA, "retirado")
            and not _fijado_a_mano(guardado, cambio.dato)
        ):
            # La primera extracción de la parte de una separación con su suceso: lo que la ficha
            # mezclada tenía «decidido con cita» era de los dos sucesos. Lo revisado a mano, no.
            return "separacion"
        if deshecha:
            # La ficha que queda devuelve lo que la unión le trajo. Si la reapertura de la
            # absorbida no pasa (`Almacen._cerrojo_reapertura`), esta vuelve a como estaba.
            return "union_deshecha"
        # La revisión del cierre fija si lo hubo: no da permiso para perder su duración. Ni la
        # del inicio para perder su fin (EODI-2026-00077, 3/11/2026: una reextracción le quitó el
        # fin y pasó como «revisión»).
        pierde = (
            cambio.dato == "cierre" and cambio.antes["minutos"] and not cambio.despues["minutos"]
        ) or (cambio.dato == "inicio" and cambio.antes.get("fin") and not cambio.despues.get("fin"))
        if cambio.dato == COHERENCIA:
            return "revision" if revision else None
        if revision or (_revisado(nuevo, cambio.dato) and not pierde):
            return "revision"
        if rectificada and cambio.dato in ("presencia_dron", "titulo"):
            return "rectificacion"
        if cambio.nivel == PUBLICADA and por_decision(pasos):
            return "decision"
        if cambio.dato == "retirado" and sin_publicar(pasos):
            return "sin_publicar"
        if cambio.dato == "titulo" and justificados & set(TITULO_SIGUE_A):
            return "sigue_a_lo_justificado"
        if cambio.nivel == CON_CITA and fuente_nueva_con_frase(
            cambio.dato, guardado, nuevo, texto_de
        ):
            return "fuente_nueva"
        return None

    # El titular y el estado, los últimos: siguen a lo que se retiene o a lo que cambia justificado.
    for cambio in sorted(pendientes, key=lambda c: (c.dato in SEGUIDORES, c.dato == "titulo")):
        motivo = razon(cambio)
        arrastrado = cambio.dato in SEGUIDORES and motivo not in RESPALDO_FIRME and any(
            r.dato in SIGUEN_A for r in veredicto.retenidos
        )  # fmt: skip
        if motivo is None or arrastrado:
            veredicto.retenidos.append(cambio)
        else:
            justificados.add(cambio.dato)
            veredicto.permitidos.append((cambio, motivo))
    # Sin revisión ni frase no son candidatos, pero tampoco cambian solos si su dato se queda.
    if any(r.dato in SIGUEN_A for r in veredicto.retenidos):
        vistos = {c.dato for c in pendientes}
        for dato in SEGUIDORES:
            antes, despues = valor(guardado, dato), valor(nuevo, dato)
            if dato not in vistos and antes != despues and incidentes.activo(guardado):
                veredicto.retenidos.append(Cambio(dato, CON_CITA, antes, despues))
    return veredicto


def _tipo_guardado(resultado: Documento, guardado: Documento) -> None:
    resultado["tipo"] = guardado.get("tipo")
    if "origen_demostrado_por" in guardado:
        resultado["origen_demostrado_por"] = guardado["origen_demostrado_por"]
    else:
        resultado.pop("origen_demostrado_por", None)


def _cierre_guardado(resultado: Documento, guardado: Documento) -> None:
    """El cierre de `resultado`, como en la guardada: si no tenía ninguno, sin él. Con un cierre
    nuevo retenido en una ficha sin cierre quedaba un cierre vacío, lo retenido no validaba y el
    cerrojo se quedaba con la versión guardada entera: la unión que traía ese cierre dejaba a la
    que queda sin las fuentes de la otra, y se reintentaba en cada pasada."""
    if "cierre" in (guardado.get("consecuencias") or {}):
        return
    consecuencias = {
        k: v for k, v in (resultado.get("consecuencias") or {}).items() if k != "cierre"
    }
    if consecuencias or "consecuencias" in guardado:
        resultado["consecuencias"] = consecuencias
    else:
        resultado.pop("consecuencias", None)


def conservar(nuevo: Documento, guardado: Documento, cambios: Iterable[Cambio]) -> Documento:
    """`nuevo` con el valor de `guardado` en cada dato retenido, con sus afirmaciones. Una retirada
    retenida deja la versión publicada entera."""
    cambios = list(cambios)
    if any(cambio.dato in ("retirado", COHERENCIA) for cambio in cambios):
        return copy.deepcopy(guardado)
    resultado = copy.deepcopy(nuevo)
    fuentes = {f.get("id") for f in resultado.get("fuentes", [])}
    for cambio in cambios:
        dato = cambio.dato
        if dato in decididos.DATOS:
            decididos._poner(resultado, guardado, dato)
            if dato == "cierre":
                _cierre_guardado(resultado, guardado)
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
        elif dato == "modelo":
            drones = {k: v for k, v in (resultado.get("drones") or {}).items() if k != "modelo"}
            if modelo := (guardado.get("drones") or {}).get("modelo"):
                drones["modelo"] = modelo
            resultado["drones"] = drones
            resultado["afirmaciones"] = [
                *(a for a in resultado.get("afirmaciones", []) if a.get("campo") != "modelo_dron"),
                *(copy.deepcopy(a) for a in guardado.get("afirmaciones", [])
                  if a.get("campo") == "modelo_dron" and a.get("fuente_id") in fuentes),
            ]  # fmt: skip
    return _con_fuentes_citadas(resultado, guardado)


def _citadas(nodo: Any) -> set[str]:
    """Los identificadores de fuente que cita una parte del documento (cualquier «fuente_id»)."""
    if isinstance(nodo, dict):
        ids = {nodo["fuente_id"]} if isinstance(nodo.get("fuente_id"), str) else set()
        return ids.union(*(_citadas(v) for v in nodo.values()))
    if isinstance(nodo, list):
        return set().union(*(_citadas(v) for v in nodo))
    return set()


def _con_fuentes_citadas(resultado: Documento, guardado: Documento) -> Documento:
    """Lo conservado cita las fuentes de la versión guardada: las que la versión nueva ya no trae
    se recuperan de la guardada. Una relectura rehace la ficha con las fuentes de su candidato y
    deja fuera las de una revisión a mano: EODI-2026-00622, 7 de noviembre de 2026, el estado
    conservado citaba «revisada-…-declaracion-1», lo retenido no validaba y la escritura pasaba,
    con la fecha revisada perdida."""
    tiene = {f.get("id") for f in resultado.get("fuentes", [])}
    faltan = _citadas({k: v for k, v in resultado.items() if k != "fuentes"}) - tiene
    if faltan:
        resultado["fuentes"] = [
            *resultado.get("fuentes", []),
            *(copy.deepcopy(f) for f in guardado.get("fuentes", []) if f.get("id") in faltan),
        ]
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
    # Lo dice la definición (proceso/suceso.veredicto) con sus reglas en su orden: una revisión
    # que las separó, lo que el experto dio por distinto (salvo la nota de una noche y sus
    # alertas, que son el mismo suceso aunque lo dijera) y las partes de una separación. Los
    # países y los cierres no se miran aquí, por grupos: los miran quien une (`unir`,
    # `fusionar`) y quien deshace (`revisar_fusiones`) con las dos fichas delante.
    dicho = suceso.veredicto(propio, ajeno, prohibidos)
    if dicho.relacion != suceso.DISTINTOS:
        return None
    if dicho.regla == suceso.REGLA_REVISION:
        return "revision" if suceso.separados_por_revision(propio, ajeno) else "partes"
    return "prohibido" if dicho.regla == suceso.REGLA_EXPERTO else None


def pares_a_mano(almacen: Any) -> list[frozenset[str]]:
    return [*suceso.uniones_a_mano(almacen), *suceso.grupos_unidos_a_mano()]


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

    prohibidos = suceso.distintos_del_experto(almacen) | revisados.pares_de_partes(almacen)
    a_mano = pares_a_mano(almacen)
    queda = almacen.incidente(destino)
    par = frozenset((str(absorbido["id"]), destino))
    if queda is not None and not any(par <= grupo for grupo in a_mano):
        # La que queda contaría un suceso anterior a la publicación de una fuente de la que se
        # funde: son dos sucesos (EODI-2026-00079, del 17/2, fundida en la del 11/8/2026).
        juntas = {**queda, "fuentes": [*absorbido.get("fuentes", [])]}
        if fuentes_anteriores(juntas):
            return {"uno": str(absorbido["id"]), "otro": destino, "motivo": COHERENCIA}
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

    prohibidos = suceso.distintos_del_experto(almacen) | revisados.pares_de_partes(almacen)
    if par_prohibido(documento, otro, prohibidos, ()) is not None:
        return True
    # O la definición da las dos por sucesos distintos (otro país con una autoridad del suyo,
    # dos cierres de noches distintas): deshacer esa unión es lo que toca.
    propio = {k: v for k, v in documento.items() if k != "fusionado_en"}
    dicho = suceso.veredicto_en(almacen, propio, otro, frozenset(), vigente=True)
    return dicho.relacion == suceso.DISTINTOS


# Los datos que se deducen de otros: el tipo sale del cierre, el lugar y el objetivo
# (incidentes.con_tipo); el titular, de lo que resume (decidir_titulo).
DEDUCIDOS_DE = {"tipo": ("cierre", "lugar", "objetivo"), "titulo": TITULO_SIGUE_A}


def fijado_por_revision(actual: Documento, dato: str) -> bool:
    """El valor que tiene ahora la ficha en `dato` lo fija una revisión a mano o una rectificación
    oficial, o sale, por las reglas, de datos que fija una revisión: lo que cambió antes ya no es
    lo que se publica (EODI-2026-00079, 3/11/2026: el cierre «si» revisado con la cita de la Neue
    Presse coincidía con el de un cambio malo del 2/11 y X la dejaba fuera de la publicación)."""
    try:
        if _revisado(actual, dato):
            return True
        if dato in ("presencia_dron", "titulo") and rectificaciones.rectificado(actual):
            return True
        bases = DEDUCIDOS_DE.get(dato, ())
        if not any(_hay_revision(actual, b) for b in bases):
            return False
        if dato == "tipo":
            return bool(
                incidentes.con_tipo(copy.deepcopy(actual)).get("tipo") == actual.get("tipo")
            )
        return bool(decidir.decidir_titulo(actual) == actual.get("titulo"))
    except (KeyError, TypeError, ValueError):
        return False


def cambios_sin_permiso(
    cambios: Iterable[Documento],
    permitidos: frozenset[tuple[str, str, str]],
    actuales: dict[str, Documento] | None = None,
    primeras: dict[str, str] | None = None,
) -> list[str]:
    """X: «<id> <dato>» de los cambios guardados a algo protegido sin justificación apuntada
    (`permitidos`: (ficha, dato, huella) de las claves `permitido:`). Con el cerrojo en «aplicar»
    debe ser una lista vacía; cualquier otra cosa es un agujero.

    Con `primeras` ({ficha: desde cuándo está publicada}, `Almacen.primeras_publicaciones`), un
    cambio hecho antes de que la ficha saliera en la web se mira como lo miró el cerrojo: solo lo
    que fija una revisión (`candidatos` con `publicada` falso). Sin esto, la corrección del filtro
    de entrada a una ficha nueva contaba como cambio sin permiso y la puerta no la dejaba salir
    en 48 horas (EODI-2026-00778, 11 de noviembre de 2026).

    Con `actuales` ({ficha: documento de ahora}), solo cuenta lo que la ficha aún tiene: no un
    cambio que otro posterior ya deshizo (una revisión, el control: EODI-2026-00719 y 00022, 3/11),
    ni uno que vuelve al valor de antes de la ventana, ni un dato cuyo valor actual fija una
    revisión o una rectificación (`fijado_por_revision`), ni los datos de una ficha que ya no se
    publica (retirada o fundida), salvo la retirada misma."""
    lista = list(cambios)
    salida: set[str] = set()
    al_empezar: dict[tuple[str, str], str] = {}
    for cambio in lista:
        if cambio.get("tabla", "incidentes") != "incidentes":
            continue
        anterior, nuevo = cambio.get("anterior") or {}, cambio.get("nuevo") or {}
        if not anterior or not nuevo or "id" not in anterior:
            continue
        id_ = str(anterior["id"])
        publicada = primeras is None or (
            id_ in primeras and str(cambio.get("fecha") or "9") >= primeras[id_]
        )
        for propuesto in candidatos(anterior, nuevo, publicada):
            marca = huella(propuesto.dato, nuevo)
            al_empezar.setdefault((id_, propuesto.dato), huella(propuesto.dato, anterior))
            if (id_, propuesto.dato, marca) in permitidos:
                continue
            if actuales is not None:
                actual = actuales.get(id_)
                if actual is None or huella(propuesto.dato, actual) != marca:
                    continue
                if marca == al_empezar[(id_, propuesto.dato)]:
                    continue
                if not incidentes.activo(actual) and propuesto.dato != "retirado":
                    continue
                if fijado_por_revision(actual, propuesto.dato):
                    continue
            salida.add(f"{id_} {propuesto.dato}")
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
