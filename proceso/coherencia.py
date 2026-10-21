"""Fechas coherentes en lo que enseña la ficha, sin tocar el estado ni las fuentes.

Cada paso del historial lleva la fecha de la fuente que lo dio, y el inicio del suceso sale de la
ficha. A veces la ficha enseñaba fechas que se contradicen (repaso del 13 de octubre de 2026):

- «Notificado» el 26 de agosto y «Confirmado» el 15 de julio (EODI-2026-00202): el aviso lleva
  la fecha de la noticia que encontró la recogida, aunque la fuente que confirma (el informe de
  UKAB del 15 de julio) es anterior. Un paso nunca es posterior al siguiente: toma la fecha y la
  fuente del siguiente, que ya da el estado anterior por alcanzado (quien confirma también avisa;
  quien atribuye también confirma). Solo si el siguiente implica el anterior: un desmentido no
  confirma. Si no lo implica (un «Desmentido» fechado antes que el «Confirmado» al que sigue,
  EODI-2025-00124, Sofía), el siguiente toma la fecha del anterior y cada paso conserva su fuente:
  el «Confirmado» de la aviación civil no puede salir de la frase del director del aeropuerto que
  lo niega.
- Un suceso que empieza al día siguiente de su primer aviso (EODI-2025-00001: noticias del 27 de
  diciembre y fecha del suceso el 28). Si el inicio es solo un día o una fecha aproximada, pasa al
  día del primer aviso; un inicio con hora (lo da una autoridad) no se toca.

Solo se aplica a lo que se publica (exportacion/geojson.py); la base y la exportación para AEGIS
no cambian. `contradicciones` es la revisión que comprueba la prueba sobre los datos publicados.
"""

import copy
from datetime import datetime, timedelta
from itertools import pairwise

from esquema import Documento

# Un aviso anterior a un inicio con hora es posible (el cierre del aeropuerto por la mañana y el
# derribo por la noche, unidos en un incidente: EODI-2026-00072), pero no de más de un día.
MARGEN_INICIO = timedelta(hours=24)
PRECISIONES_SIN_HORA = frozenset({"dia", "aproximada"})


def _instante(fecha: Documento) -> datetime:
    return datetime.fromisoformat(str(fecha["valor"]).replace("Z", "+00:00"))


def _dia(fecha: Documento) -> str:
    return str(fecha["valor"])[:10]


# El orden de los estados que se implican: quien confirma también avisa, quien atribuye también
# confirma. Todo paso implica el aviso.
_RANGO = {"notificado": 0, "confirmado": 1, "atribuido": 2}


def implica(siguiente: str, paso: str) -> bool:
    """El estado `siguiente` da por alcanzado el estado `paso` (su fuente vale para los dos)."""
    if paso == "notificado":
        return True
    return paso in _RANGO and siguiente in _RANGO and _RANGO[siguiente] >= _RANGO[paso]


def coherente(documento: Documento) -> Documento:
    """El documento (copia) con las fechas del historial y del inicio sin contradicciones."""
    salida = copy.deepcopy(documento)
    historial = (salida.get("estado") or {}).get("historial") or []
    # De delante atrás: un paso que no implica el anterior y lleva una fecha anterior toma la
    # del anterior, con su propia fuente (un desmentido no confirma).
    for paso, siguiente in pairwise(historial):
        if not implica(siguiente["estado"], paso["estado"]) and _instante(
            siguiente["fecha"]
        ) < _instante(paso["fecha"]):
            siguiente["fecha"] = copy.deepcopy(paso["fecha"])
    # De atrás adelante: un paso no puede ser posterior al siguiente. La fuente del siguiente ya
    # da el estado anterior por alcanzado (quien confirma también avisa).
    for indice in range(len(historial) - 2, -1, -1):
        paso, siguiente = historial[indice], historial[indice + 1]
        if _instante(siguiente["fecha"]) < _instante(paso["fecha"]):
            paso["fecha"] = copy.deepcopy(siguiente["fecha"])
            if "fuente_id" in siguiente:
                paso["fuente_id"] = siguiente["fuente_id"]
    inicio = (salida.get("tiempo") or {}).get("inicio")
    if historial and inicio and inicio.get("precision") in PRECISIONES_SIN_HORA:
        aviso = historial[0]["fecha"]
        if _dia(aviso) < _dia(inicio):
            salida["tiempo"]["inicio"] = {"valor": f"{_dia(aviso)}T00:00Z", "precision": "dia"}
            fin = salida["tiempo"].get("fin")
            if fin is not None and _instante(fin) < _instante(salida["tiempo"]["inicio"]):
                del salida["tiempo"]["fin"]
    return salida


def contradicciones(propiedades: Documento) -> list[str]:
    """Las fechas que la ficha enseñaría contradiciéndose."""
    salida = []
    historial = (propiedades.get("estado") or {}).get("historial") or []
    for anterior, paso in pairwise(historial):
        if _instante(paso["fecha"]) < _instante(anterior["fecha"]):
            salida.append(f"«{paso['estado']}» fechado antes que «{anterior['estado']}»")
    if historial and historial[-1]["estado"] != propiedades.get("estado", {}).get("actual"):
        salida.append("el estado actual no es el último paso del historial")
    tiempo = propiedades.get("tiempo") or {}
    inicio, fin = tiempo.get("inicio"), tiempo.get("fin")
    if inicio and fin and _instante(fin) < _instante(inicio):
        salida.append("el fin es anterior al inicio")
    if inicio and historial:
        aviso = historial[0]["fecha"]
        limite = _instante(inicio) - MARGEN_INICIO
        if inicio.get("precision") in PRECISIONES_SIN_HORA:
            if _dia(aviso) < _dia(inicio):
                salida.append("el primer aviso es de un día anterior al suceso")
        elif (aviso.get("precision") == "dia" and _dia(aviso) < limite.strftime("%Y-%m-%d")) or (
            aviso.get("precision") != "dia" and _instante(aviso) < limite
        ):
            salida.append("el primer aviso es de más de un día antes del suceso")
    return salida
