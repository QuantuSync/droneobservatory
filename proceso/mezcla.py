"""Drones a reacción de cada ataque, con la frase del parte ya guardada.

La Fuerza Aérea de Ucrania cuenta a veces aparte los drones a reacción dentro de la frase del
lanzamiento («173 ударними БпЛА типу Shahed (понад 50 із них - реактивні)»). El analizador los
guarda desde `parte-fuerza-aerea/4` (`lanzados.reactivos`), pero la recogida solo relee los partes
de las últimas 48 horas: este paso completa los ataques ya guardados con su propia frase, una
vez, y guarda solo lo que cambia, con su motivo en el historial. Nada se borra: un ataque cuya
frase no da la cifra se queda como estaba.
"""

import copy
from datetime import datetime
from typing import TYPE_CHECKING

from recogida import parte

if TYPE_CHECKING:
    from almacen.base import Almacen

MOTIVO = (
    "drones a reacción que el parte cuenta aparte en la frase del lanzamiento (proceso/mezcla.py), "
    "leídos de la frase ya guardada"
)


def completar_reactivos(almacen: "Almacen", ahora: datetime) -> int:
    """Añade `lanzados.reactivos` a los ataques cuya frase guardada da la cifra. Devuelve
    cuántos ha cambiado."""
    cambiados = 0
    for ataque in almacen.ataques_ucrania():
        if ataque.get("sentido") != "RU_UA" or "reactivos" in (ataque.get("lanzados") or {}):
            continue
        frases = [
            f.get("frase_origen", "")
            for f in ataque.get("fuentes", [])
            if "kpszsu" in f.get("id", "")
        ]
        lanzados = ataque.get("lanzados") or {}
        hallado = next(
            (r for frase in frases if (r := parte.reactivos(frase, lanzados.get("total")))), None
        )
        if hallado is None:
            continue
        nuevo = copy.deepcopy(ataque)
        nuevo["lanzados"] = {**lanzados, "reactivos": hallado}
        almacen.guardar_ataque_ucrania(nuevo, ahora)
        almacen.anotar_motivo(
            "ataques_ucrania", ataque["id"], {"lanzados": lanzados},
            {"lanzados": nuevo["lanzados"]}, MOTIVO,
        )  # fmt: skip
        cambiados += 1
    return cambiados
