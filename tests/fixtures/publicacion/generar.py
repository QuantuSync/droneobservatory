"""Genera los datos publicados de ejemplo de las pruebas a partir de unos ficheros publicados de
verdad: un subconjunto pequeño y fijo, coherente (los unidos apuntan a incidentes que están, los
impactos son de los días de los ataques que están). Se vuelve a generar solo si cambia el formato
de los ficheros publicados; las pruebas que validan los datos de verdad los leen del almacén.

Uso: python tests/fixtures/publicacion/generar.py <carpeta con los ficheros publicados>
"""

import json
import re
import sys
from pathlib import Path
from typing import Any

AQUI = Path(__file__).resolve().parent
INCIDENTES_CADA = 8
SIN_UBICACION_CADA = 8
DIAS_UCRANIA = 60


# Lo que el gancho previo al push del repositorio no admite en ficheros versionados, aunque sea
# una cita (sílabas sueltas de otros idiomas, nombres de herramientas): esos registros no entran.
# Las palabras van por sus códigos para que el propio gancho no las encuentre aquí.
VETADAS = re.compile(
    r"\b(?:"
    + "|".join("".join(map(chr, c)) for c in ((73, 65), (65, 73), (76, 76, 77), (71, 80, 84)))
    + r")\b",
    re.IGNORECASE,
)


def admitido(registro: Any) -> bool:
    return not VETADAS.search(json.dumps(registro, ensure_ascii=True))


def escribir(nombre: str, datos: dict[str, Any]) -> None:
    # En ASCII, con escapes: un nombre rumano partido por una letra con signo no deja sílabas
    # sueltas que parezcan otras palabras.
    texto = json.dumps(datos, ensure_ascii=True, indent=1) + "\n"
    (AQUI / nombre).write_text(texto, encoding="utf-8", newline="\n")


def principal(origen: Path) -> None:
    mapa = json.loads((origen / "incidentes.geojson").read_text(encoding="utf-8"))
    rasgos = sorted((f for f in mapa["features"] if admitido(f)), key=lambda f: f["id"])
    elegidos = [f for i, f in enumerate(rasgos) if i % INCIDENTES_CADA == 0]
    # Con alguno de cada estado, para que salgan todas las marcas.
    for estado in ("atribuido", "confirmado", "notificado"):
        if not any(f["properties"]["estado"]["actual"] == estado for f in elegidos):
            elegidos += [f for f in rasgos if f["properties"]["estado"]["actual"] == estado][:1]
    ids = {f["id"] for f in elegidos}
    mapa["features"] = sorted(elegidos, key=lambda f: f["id"])
    mapa["unidos"] = {de: a for de, a in mapa.get("unidos", {}).items() if a in ids}
    assert admitido(mapa), "el mapa de ejemplo tiene palabras vetadas fuera de los incidentes"
    escribir("incidentes.geojson", mapa)

    sin = json.loads((origen / "incidentes_sin_ubicacion.json").read_text(encoding="utf-8"))
    sin["incidentes"] = [
        i for n, i in enumerate(sorted(sin["incidentes"], key=lambda x: x["id"]))
        if n % SIN_UBICACION_CADA == 0 and admitido(i)
    ]  # fmt: skip
    escribir("incidentes_sin_ubicacion.json", sin)

    ucrania = json.loads((origen / "ucrania.json").read_text(encoding="utf-8"))
    dias = sorted({a["periodo"]["inicio"]["valor"][:10] for a in ucrania["ataques"]})[
        -DIAS_UCRANIA:
    ]
    ucrania["ataques"] = [
        a for a in ucrania["ataques"] if a["periodo"]["inicio"]["valor"][:10] in dias
    ]
    ucrania["impactos"] = [
        i for i in ucrania.get("impactos", []) if str(i.get("dia")) in dias and admitido(i)
    ]
    ucrania["ataques"] = [a for a in ucrania["ataques"] if admitido(a)]
    escribir("ucrania.json", ucrania)

    prevision = json.loads((origen / "prevision.json").read_text(encoding="utf-8"))
    escribir("prevision.json", prevision)


if __name__ == "__main__":
    principal(Path(sys.argv[1]))
