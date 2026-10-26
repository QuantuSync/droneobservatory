"""Rectificaciones oficiales de la presencia del dron.

El incidente ocurrió aunque después se rectifique la causa: si un aeropuerto cerró, cerró. Una
rectificación oficial cambia la presencia del dron, nunca el incidente ni su efecto (el cierre,
los desvíos, la duración), y nada desaparece del mapa:

- no_acreditada: una autoridad oficial cierra su investigación sin pruebas del dron, o retira su
  afirmación sin decir que fuera otra cosa («We cannot confirm that there has been drone
  activity», la policía de Copenhague el 25 de junio de 2026). No encontrar pruebas no es
  demostrar que no hubo dron: nunca es descartada;
- descartada: la autoridad dice que era otra cosa (un avión, un helicóptero);
- corrección parcial: la autoridad rectifica un episodio y mantiene los demás. Se anota en el
  historial y no cambia el valor;
- investigación cerrada sin cambiar la presencia (cierre_sin_cambio, desde el 26 de octubre de
  2026): la autoridad cierra o archiva su investigación y no cambia lo que se sabía del dron (no
  lo retira ni dice que fuera otra cosa; por ejemplo, no puede determinar su origen). Se anota en
  el historial con `cierre` y tampoco cambia el valor ni el estado.

Solo cambia la presencia una autoridad oficial, nunca un periodista ni la comunidad OSINT (eso
puede quedar como contexto en la ficha, en sus fuentes), y nunca sin el experto
(recogida/rectificaciones.py). Cada paso queda en `presencia_historial` con su fecha, su fuente,
quién lo declara y su motivo, en español y en inglés; el primero es el valor que había, con la
fuente con que se declaró. El historial solo crece.

Lo rectificado no lo deshace la recogida: `mantener` (lo llama `Almacen.guardar_incidente` con la
versión guardada) conserva el historial y sus fuentes y vuelve a poner el valor vigente aunque una
extracción o una regla traigan otro.
"""

import copy
import json
import re
from functools import cache
from pathlib import Path
from typing import Any

from esquema import Documento
from proceso import autoridades, titulares

CONFIRMADA, NO_CONFIRMADA = "confirmada", "no_confirmada"
NO_ACREDITADA, DESCARTADA = "no_acreditada", "descartada"
RECTIFICADOS = frozenset({NO_ACREDITADA, DESCARTADA})
PARCIAL = "parcial"
CIERRE_SIN_CAMBIO = "cierre_sin_cambio"
# Lo que puede decidir una rectificación: los dos valores, la nota parcial y el cierre de la
# investigación sin cambio de la presencia.
TIPOS = (NO_ACREDITADA, DESCARTADA, PARCIAL, CIERRE_SIN_CAMBIO)
# Los que se anotan en el historial con el valor vigente, sin cambiarlo.
SIN_CAMBIO = frozenset({PARCIAL, CIERRE_SIN_CAMBIO})
CONFIANZA_RECTIFICACION = 1.0
# La frase de una fuente tiene como mucho 25 palabras (esquema, comun: frase_origen).
MAX_PALABRAS_FRASE = 25
SENALES = Path(__file__).resolve().parent.parent / "configuracion" / "senales_rectificacion.json"


def es_nota(paso: Documento) -> bool:
    """El paso es una nota que no cambia el valor: una corrección parcial o una investigación
    cerrada sin cambiar la presencia."""
    return bool(paso.get("parcial") or paso.get("cierre"))


def pasos_de_valor(documento: Documento) -> list[Documento]:
    """Los pasos del historial que dan un valor (sin las notas, es_nota)."""
    return [p for p in documento.get("presencia_historial") or [] if not es_nota(p)]


def vigente(documento: Documento) -> str | None:
    """El valor de la presencia que deja el historial (el último paso que no es una nota), o None
    si el incidente no tiene rectificaciones."""
    pasos = pasos_de_valor(documento)
    return str(pasos[-1]["valor"]) if pasos else None


def rectificado(documento: Documento) -> bool:
    """La presencia viene de una rectificación oficial (no_acreditada o descartada)."""
    return vigente(documento) in RECTIFICADOS


def _fecha_clave(fuente: Documento) -> tuple[str, str]:
    return (str(fuente["fecha"]["valor"]), str(fuente["id"]))


def _quien(fuente: Documento) -> Documento:
    medio = str(fuente.get("medio", ""))
    return {
        "es": autoridades.de_la_fuente(medio, "es"),
        "en": autoridades.de_la_fuente(medio, "en"),
    }


def semilla(incidente: Documento, quien: Documento | None = None) -> Documento:
    """El primer paso del historial: el valor que había y la fuente con que se declaró (la
    autoridad más temprana que lo afirma; si no la hay, la primera fuente que lo afirma o la
    primera del incidente)."""
    valor = str(incidente.get("presencia_dron") or NO_CONFIRMADA)
    fuentes = {f["id"]: f for f in incidente["fuentes"]}
    afirmantes = [
        fuentes[a["fuente_id"]] for a in incidente.get("afirmaciones", [])
        if a.get("campo") == "presencia_dron" and a.get("valor") == valor
        and a.get("fuente_id") in fuentes
    ]  # fmt: skip
    oficiales = [f for f in afirmantes if f.get("es_autoridad")]
    elegida = min(oficiales or afirmantes or list(fuentes.values()), key=_fecha_clave)
    paso: Documento = {
        "valor": valor,
        "fecha": copy.deepcopy(elegida["fecha"]),
        "fuente_id": elegida["id"],
    }
    # Quién lo declaró: la autoridad (la revisada a mano o la de la fuente). Un medio no declara.
    if quien:
        paso["quien"] = dict(quien)
    elif elegida.get("es_autoridad"):
        paso["quien"] = _quien(elegida)
    return paso


def paso_de(
    tipo: str, fecha: Documento, fuente_id: str, quien: Documento, motivo: Documento,
    revision: str, valor_actual: str,
) -> Documento:  # fmt: skip
    """El paso de una rectificación. La parcial y el cierre sin cambio llevan el valor vigente y
    no lo cambian."""
    paso: Documento = {
        "valor": valor_actual if tipo in SIN_CAMBIO else tipo,
        "fecha": copy.deepcopy(fecha),
        "fuente_id": fuente_id,
        "quien": {"es": quien["es"], "en": quien["en"]},
        "motivo": {"es": motivo["es"], "en": motivo["en"]},
        "revision": revision,
    }
    if tipo == PARCIAL:
        paso["parcial"] = True
    elif tipo == CIERRE_SIN_CAMBIO:
        paso["cierre"] = True
    return paso


def aplicada(incidente: Documento, revision: str) -> bool:
    return any(p.get("revision") == revision for p in incidente.get("presencia_historial") or [])


def aplicar(
    incidente: Documento, tipo: str, fuente: Documento, fecha: Documento, quien: Documento,
    motivo: Documento, revision: str, semilla_quien: Documento | None = None,
) -> Documento:  # fmt: skip
    """El incidente con la rectificación añadida (el mismo si ya la tiene): la fuente si le
    falta, el historial (con el valor que había delante, si es el primer paso), la presencia, su
    afirmación y el titular coherente. El estado, el cierre y lo demás no se tocan."""
    if tipo not in TIPOS:
        raise ValueError(f"rectificación desconocida: {tipo}")
    if aplicada(incidente, revision):
        return incidente
    if tipo not in SIN_CAMBIO and tipo == vigente(incidente):
        # Otra fuente que dice lo mismo (la declaración oficial que llega después de la noticia
        # que la contaba): no es un paso nuevo, pero la fuente queda en la ficha con su afirmación.
        if fuente["id"] in {f["id"] for f in incidente["fuentes"]}:
            return incidente
        resultado = copy.deepcopy(incidente)
        resultado["fuentes"].append(copy.deepcopy(fuente))
        resultado["afirmaciones"] = [*resultado.get("afirmaciones", []), {
            "campo": "presencia_dron", "valor": tipo, "fuente_id": fuente["id"],
            "confianza_extraccion": CONFIANZA_RECTIFICACION,
        }]  # fmt: skip
        return resultado
    resultado = copy.deepcopy(incidente)
    if fuente["id"] not in {f["id"] for f in resultado["fuentes"]}:
        resultado["fuentes"].append(copy.deepcopy(fuente))
    historial = list(resultado.get("presencia_historial") or [])
    if not historial:
        historial.append(semilla(incidente, semilla_quien))
    actual = vigente({"presencia_historial": historial}) or str(resultado.get("presencia_dron"))
    historial.append(paso_de(tipo, fecha, fuente["id"], quien, motivo, revision, actual))
    resultado["presencia_historial"] = historial
    if tipo not in SIN_CAMBIO:
        resultado["presencia_dron"] = tipo
        afirmacion = {
            "campo": "presencia_dron",
            "valor": tipo,
            "fuente_id": fuente["id"],
            "confianza_extraccion": CONFIANZA_RECTIFICACION,
        }
        afirmaciones = list(resultado.get("afirmaciones", []))
        if afirmacion not in afirmaciones:
            afirmaciones.append(afirmacion)
        resultado["afirmaciones"] = afirmaciones
    return titulares.ajustar_incidente(resultado)


def mantener(nuevo: Documento, anterior: Documento | None) -> Documento:
    """La versión que se va a guardar con lo rectificado de la guardada: el historial (los pasos
    de la guardada y, detrás, los nuevos), las fuentes que cita y el valor vigente de la
    presencia, con su afirmación y el titular coherente. La misma si no hay nada que conservar."""
    previo = list((anterior or {}).get("presencia_historial") or [])
    propio = list(nuevo.get("presencia_historial") or [])
    if not previo and not propio:
        return nuevo
    historial = previo + [p for p in propio if p not in previo]
    resultado = nuevo
    if historial != propio:
        resultado = {**resultado, "presencia_historial": historial}
    citadas = {p["fuente_id"] for p in historial}
    tiene = {f["id"] for f in resultado["fuentes"]}
    faltan = [
        f for f in (anterior or {}).get("fuentes", []) if f["id"] in citadas - tiene
    ]  # fmt: skip
    if faltan:
        resultado = {**resultado, "fuentes": [*resultado["fuentes"], *copy.deepcopy(faltan)]}
    valor = vigente(resultado)
    if valor is None or resultado.get("presencia_dron") == valor:
        return resultado
    ultimo = next(p for p in reversed(historial) if not es_nota(p))
    afirmacion = {
        "campo": "presencia_dron",
        "valor": valor,
        "fuente_id": ultimo["fuente_id"],
        "confianza_extraccion": CONFIANZA_RECTIFICACION,
    }
    afirmaciones = list(resultado.get("afirmaciones", []))
    if afirmacion not in afirmaciones:
        afirmaciones.append(afirmacion)
    resultado = {**resultado, "presencia_dron": valor, "afirmaciones": afirmaciones}
    return titulares.ajustar_incidente(resultado)


def errores(documento: Documento) -> list[str]:
    """Coherencia del historial: cada paso cita una fuente del incidente, las notas (parciales y
    cierres sin cambio) llevan el valor vigente y el último paso que no es una nota es la
    presencia del incidente."""
    historial = documento.get("presencia_historial")
    if not historial:
        return []
    fuentes = {f.get("id") for f in documento.get("fuentes", []) if isinstance(f, dict)}
    resultado = [
        f"presencia_historial: la fuente {p.get('fuente_id')} no está en el incidente"
        for p in historial
        if p.get("fuente_id") not in fuentes
    ]
    actual = None
    for paso in historial:
        if es_nota(paso):
            if actual is not None and paso.get("valor") != actual:
                resultado.append("presencia_historial: una nota (parcial o cierre) cambia el valor")
        else:
            actual = paso.get("valor")
    if actual is not None and documento.get("presencia_dron") != actual:
        resultado.append(
            f"presencia_historial acaba en {actual} y la presencia es "
            f"{documento.get('presencia_dron')}"
        )
    return resultado


# --- Señales de una rectificación en las fuentes (recogida/rectificaciones.py) ---------------


@cache
def _senales(ruta: Path = SENALES) -> re.Pattern[str]:
    datos: dict[str, Any] = json.loads(ruta.read_text(encoding="utf-8"))
    expresiones = [e for lista in datos["expresiones"].values() for e in lista]
    return re.compile(r"(?<!\w)(?:" + "|".join(expresiones) + r")(?!\w)", re.IGNORECASE)


def senal(texto: str) -> str | None:
    """La expresión del texto que suena a rectificación o a cierre oficial de una investigación
    («no evidence», «cannot confirm», «investigation closed», «was a helicopter», en las lenguas
    del observatorio), o None. Solo decide qué se manda al experto: nunca cambia nada."""
    encontrada = _senales().search(" ".join(texto.split()))
    return encontrada.group(0) if encontrada else None


# --- Respuesta del experto -------------------------------------------------------------------


def _normal(texto: str) -> str:
    return " ".join(str(texto).split()).casefold()


def decision_valida(respuesta: dict[str, Any], texto: str, esperado: str | None = None
                    ) -> tuple[str | None, str]:  # fmt: skip
    """Lo que vale de la respuesta del experto: el tipo de rectificación (no_acreditada,
    descartada, parcial o cierre_sin_cambio) y por qué, o None con el motivo por el que no vale.
    Solo vale si es el mismo suceso, la declaración es de una autoridad oficial, su frase está
    literal en el texto mandado, la seguridad llega a 0,7 y, si la rectificación estaba revisada,
    el tipo coincide."""
    tipo = str(respuesta.get("tipo") or "")
    if tipo not in TIPOS:
        return None, f"el experto no ve una rectificación ({tipo or 'sin tipo'})"
    if not respuesta.get("mismo_suceso"):
        return None, "el experto dice que habla de otro suceso"
    if not respuesta.get("autoridad_oficial"):
        return None, "el experto dice que no lo declara una autoridad oficial"
    frase = str(respuesta.get("frase") or "")
    if not frase.strip() or _normal(frase) not in _normal(texto):
        return None, "la frase del experto no está literal en el texto"
    try:
        confianza = float(respuesta.get("confianza", 0))
    except (TypeError, ValueError):
        confianza = 0.0
    if confianza < 0.7:
        return None, f"el experto no está seguro ({confianza:.2f})"
    if esperado is not None and tipo != esperado:
        return None, f"el experto lo lee como {tipo}, no como {esperado}"
    for campo in ("quien_es", "quien_en", "motivo_es", "motivo_en"):
        if not str(respuesta.get(campo) or "").strip():
            return None, f"falta {campo}"
    return tipo, "aceptada por el experto"
