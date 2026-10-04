"""Genera configuracion/ciudades_luces.json: las ciudades cuyo brillo nocturno se mide.

Del nomenclátor de la capa de guerra (configuracion/nomenclator_guerra.json.gz): en Ucrania
(con Crimea y lo ocupado, que llevan su código ucraniano) las ciudades de POBLACION_UA
habitantes o más y, en cada región que no tenga ninguna, la mayor; en Rusia, las de POBLACION_RU
o más dentro de la caja de los pasos que cubren Ucrania (recogida/luces.CAJA), sin Kaliningrado.
Una ciudad a menos de SEPARACION_KM de otra mayor ya elegida se deja fuera: cae en su radio o en
su fondo (barrios y ciudades dormitorio de Moscú o de Kyiv).

    python -m recogida.ciudades_luces
"""

import gzip
import json
import sys
from pathlib import Path
from typing import Any

from proceso.focos_termicos import distancia_km
from recogida.luces import CAJA, CIUDADES

NOMENCLATOR = (
    Path(__file__).resolve().parent.parent / "configuracion" / "nomenclator_guerra.json.gz"
)
POBLACION_UA = 100_000
POBLACION_RU = 200_000
SEPARACION_KM = 30.0
EXCLUIDAS_RU = frozenset({"RU-KGD"})


def elegir(localidades: list[dict[str, Any]]) -> list[dict[str, Any]]:
    oeste, sur, este, norte = CAJA
    candidatas = []
    mayores_por_region: dict[str, dict[str, Any]] = {}
    for loc in localidades:
        poblacion = loc.get("poblacion") or 0
        if loc["pais"] == "UA":
            actual = mayores_por_region.get(loc["region"])
            if actual is None or poblacion > (actual.get("poblacion") or 0):
                mayores_por_region[loc["region"]] = loc
            if poblacion >= POBLACION_UA:
                candidatas.append(loc)
        elif (
            loc["pais"] == "RU"
            and poblacion >= POBLACION_RU
            and loc["region"] not in EXCLUIDAS_RU
            and oeste <= loc["lon"] <= este
            and sur <= loc["lat"] <= norte
        ):
            candidatas.append(loc)
    con_ciudad = {c["region"] for c in candidatas if c["pais"] == "UA"}
    candidatas += [m for r, m in mayores_por_region.items() if r not in con_ciudad]
    elegidas: list[dict[str, Any]] = []
    for loc in sorted(candidatas, key=lambda c: -(c.get("poblacion") or 0)):
        if any(
            distancia_km(loc["lat"], loc["lon"], e["lat"], e["lon"]) < SEPARACION_KM
            for e in elegidas
        ):
            continue
        elegidas.append(loc)
    return [
        {
            "id": loc["id"],
            "nombre": loc["nombre"],
            "nombre_latino": (loc.get("nombres", {}).get("la") or [loc["nombre"]])[0],
            "region": loc["region"],
            "lat": round(loc["lat"], 5),
            "lon": round(loc["lon"], 5),
            "radio_km": loc.get("radio_km", 3.0),
            "poblacion": loc.get("poblacion"),
        }
        for loc in sorted(elegidas, key=lambda c: (c["region"], c["id"]))
    ]


def principal() -> int:
    with gzip.open(NOMENCLATOR, "rt", encoding="utf-8") as fichero:
        nomenclator = json.load(fichero)
    ciudades = elegir(nomenclator["localidades"])
    documento = {
        "version_esquema": "1.0.0",
        "descripcion": (
            "Ciudades cuyo brillo nocturno se mide (proceso/luces.py), generadas por "
            "recogida/ciudades_luces.py desde el nomenclátor de la capa de guerra."
        ),
        "ciudades": ciudades,
    }
    with open(CIUDADES, "w", encoding="utf-8", newline="\n") as fichero:
        json.dump(documento, fichero, ensure_ascii=False, indent=1)
        fichero.write("\n")
    print(f"{len(ciudades)} ciudades")
    return 0


if __name__ == "__main__":
    sys.exit(principal())
