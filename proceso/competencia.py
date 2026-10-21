"""Dos autoridades oficiales que se contradicen: prevalece la competente.

Regla (docs/metodologia.md, «Autoridades que se contradicen»; configuracion/
competencia_autoridades.json): cuando una autoridad competente sobre el espacio aéreo (gestor de
navegación aérea, autoridad de aviación civil, fuerzas armadas) o sobre la investigación (policía,
fiscalía, organismo investigador) confirma el suceso y otra que no lo es (el gestor del
aeropuerto) lo niega, prevalece la competente: el incidente sigue confirmado y la negación queda
en el historial, con su fecha y su fuente, seguida del paso que lo deja confirmado con el motivo.
Si la que niega es la competente, el desmentido vale como siempre.

Caso: EODI-2026-00293, Bruselas 12/09/2026. skeyes, el control aéreo belga, detectó el dron a
simple vista y con sus equipos; Brussels Airport dijo no haber recibido ningún aviso. El
observatorio lo había dejado desmentido por el aeropuerto.

Las declaraciones nuevas traen su categoría (proceso/declaraciones.py); las fuentes ya guardadas
solo el nombre de la autoridad («skeyes (declaración oficial citada en brf.be)»), que se reconoce
con las listas de la configuración.
"""

import copy
import json
import re
from collections.abc import Mapping
from functools import cache
from pathlib import Path
from typing import Any

from esquema import Documento
from proceso.estados import Estado, error_reversion

RUTA = Path(__file__).resolve().parent.parent / "configuracion" / "competencia_autoridades.json"
_CITADA = " (declaración oficial citada en "


@cache
def _configuracion() -> dict[str, Any]:
    datos: dict[str, Any] = json.loads(RUTA.read_text(encoding="utf-8"))
    return datos


def _patron(nombres: list[str]) -> re.Pattern[str]:
    """Los nombres como trozos del nombre de la autoridad: las siglas en mayúsculas, palabra
    entera y tal cual («BEA», no «Bearn»); lo demás, desde el principio de una palabra y sin
    distinguir mayúsculas («Polis» vale para «Polisen»)."""
    trozos = []
    for nombre in nombres:
        escapado = re.escape(nombre)
        if nombre.isupper() and len(nombre) <= 6:
            trozos.append(rf"(?-i:(?<!\w){escapado}(?!\w))")
        else:
            trozos.append(rf"(?<!\w){escapado}")
    return re.compile("|".join(trozos), re.IGNORECASE)


@cache
def _competentes() -> re.Pattern[str]:
    return _patron(list(_configuracion()["competentes"]))


@cache
def _ceden() -> re.Pattern[str]:
    return _patron(list(_configuracion()["ceden"]))


def autoridad(fuente: Mapping[str, Any]) -> str:
    """El nombre de la autoridad de una declaración: el medio sin «(declaración oficial…)»."""
    return str(fuente.get("medio", "")).split(_CITADA, 1)[0].strip()


def es_competente(nombre: str, categoria: str | None = None) -> bool:
    """Competente sobre el espacio aéreo o sobre la investigación."""
    if categoria:
        return categoria in _configuracion()["categorias_competentes"]
    return bool(_competentes().search(nombre))


def cede(nombre: str, categoria: str | None = None) -> bool:
    """La autoridad no es competente sobre el espacio aéreo ni la investigación (el gestor del
    aeropuerto): su negación no deshace lo que confirma una competente."""
    if categoria:
        return categoria in _configuracion()["categorias_que_ceden"]
    return bool(_ceden().search(nombre)) and not _competentes().search(nombre)


def confirmacion_que_prevalece(
    incidente: Documento, categorias: Mapping[str, str] | None = None
) -> Documento | None:
    """La fuente de la autoridad competente que dejó el incidente confirmado, o None. Solo si
    está confirmado (no atribuido: la regla no toca las atribuciones). `categorias`: la categoría
    de las declaraciones que se aplican ahora, por el identificador de su fuente."""
    if incidente["estado"]["actual"] != Estado.CONFIRMADO:
        return None
    categorias = categorias or {}
    fuentes: dict[str, Documento] = {f["id"]: f for f in incidente["fuentes"]}
    for paso in reversed(incidente["estado"]["historial"]):
        if paso["estado"] != Estado.CONFIRMADO:
            continue
        fuente = fuentes.get(str(paso.get("fuente_id")))
        if fuente is None or not fuente.get("es_autoridad"):
            continue
        if es_competente(autoridad(fuente), categorias.get(fuente["id"])):
            return fuente
    return None


def motivo() -> dict[str, str]:
    """El motivo del paso que deja el incidente confirmado. Sin los nombres de las autoridades,
    que van en su lengua y sin traducir: quién es cada una lo dicen las fuentes de los pasos."""
    return {
        "es": (
            "Prevalece la autoridad competente sobre el espacio aéreo o la investigación, que "
            "confirmó el dron; la del aeropuerto lo negó y su negación queda en el historial."
        ),
        "en": (
            "The authority competent for the airspace or the investigation, which confirmed "
            "the drone, prevails; the airport's authority denied it and its denial stays in the "
            "history."
        ),
    }


def anotar_negacion(
    incidente: Documento, niega: Documento, prevalece: Documento
) -> Documento | None:
    """El incidente con la negación de una autoridad que cede en su historial (desmentido, con
    su fecha y su fuente) y, detrás, el paso que lo deja confirmado por la competente, con el
    motivo. Si esa autoridad ya tiene su negación en el historial, el incidente igual (una
    noticia más que la repite no añade pasos). None si la máquina de estados no lo permite."""
    resultado = copy.deepcopy(incidente)
    fuentes = {f["id"]: f for f in resultado["fuentes"]}
    nombre = autoridad(niega)
    for paso in resultado["estado"]["historial"]:
        anterior = fuentes.get(str(paso.get("fuente_id")))
        if paso["estado"] == Estado.DESMENTIDO and anterior and autoridad(anterior) == nombre:
            return resultado
    if error_reversion(niega, prevalece) is not None:
        return None
    historial = resultado["estado"]["historial"]
    historial.append({"estado": Estado.DESMENTIDO.value, "fecha": copy.deepcopy(niega["fecha"]),
                      "fuente_id": niega["id"]})  # fmt: skip
    historial.append({
        "estado": Estado.CONFIRMADO.value,
        "fecha": copy.deepcopy(niega["fecha"]),
        "fuente_id": prevalece["id"],
        "motivo": motivo(),
    })  # fmt: skip
    resultado["estado"]["actual"] = Estado.CONFIRMADO.value
    resultado["control"].pop("motivo_desmentido", None)
    return resultado


def motivo_sin_negacion() -> dict[str, str]:
    """El motivo del paso que deja confirmado un incidente cuyo «desmentido» no negaba nada."""
    return {
        "es": (
            "La frase del desmentido no niega el suceso ni el dron (habla del peligro, de quién "
            "está detrás o de que no se encontró): sigue confirmado por la autoridad que lo "
            "confirmó, y la frase queda en el historial."
        ),
        "en": (
            "The denial's wording does not deny the event or the drone (it speaks of the danger, "
            "of who is behind it or of it not being found): it stays confirmed by the authority "
            "that confirmed it, and the wording stays in the history."
        ),
    }


def corregir_desmentido(incidente: Documento) -> tuple[Documento, Documento] | None:
    """Las fichas ya guardadas con un desmentido que no vale (proceso/declaraciones.niega y la
    regla de competencia): el incidente otra vez confirmado, con el paso de la autoridad que lo
    confirmó y su motivo detrás del desmentido (que queda en el historial), y esa fuente. None
    si el desmentido vale.

    - La frase no niega nada: «è prematuro correlare l'episodio a una azione di Mosca»
      (EODI-2025-00206, la prefectura de Brest), «няма проблем».
    - Lo niega una autoridad que cede y lo confirmó una competente (EODI-2025-00124, Sofía: la
      aviación civil búlgara frente al director del aeropuerto)."""
    from proceso import declaraciones

    if incidente["estado"]["actual"] != Estado.DESMENTIDO:
        return None
    fuentes: dict[str, Documento] = {f["id"]: f for f in incidente["fuentes"]}
    historial = incidente["estado"]["historial"]
    niega = fuentes.get(str(historial[-1].get("fuente_id")))
    if niega is None or not niega.get("es_autoridad"):
        return None
    confirmantes = [
        fuentes[str(p.get("fuente_id"))] for p in historial
        if p["estado"] in (Estado.CONFIRMADO, Estado.ATRIBUIDO)
        and str(p.get("fuente_id")) in fuentes
        and declaraciones.de_autoridad(fuentes[str(p.get("fuente_id"))])
    ]  # fmt: skip
    if not confirmantes:
        return None
    competentes = [f for f in confirmantes if es_competente(autoridad(f))]
    if not declaraciones.niega(str(niega.get("frase_origen") or "")):
        prevalece, texto = (competentes or confirmantes)[-1], motivo_sin_negacion()
    elif cede(autoridad(niega)) and competentes:
        prevalece, texto = competentes[-1], motivo()
    else:
        return None
    resultado = copy.deepcopy(incidente)
    pasos = resultado["estado"]["historial"]
    fecha = max((niega["fecha"], prevalece["fecha"]), key=lambda f: str(f["valor"]))
    pasos.append({"estado": Estado.CONFIRMADO.value, "fecha": copy.deepcopy(fecha),
                  "fuente_id": prevalece["id"], "motivo": texto})  # fmt: skip
    resultado["estado"]["actual"] = Estado.CONFIRMADO.value
    resultado["control"].pop("motivo_desmentido", None)
    return resultado, prevalece
