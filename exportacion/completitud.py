"""Completitud de una versión exportada: qué parte de los incidentes trae cada campo, y de
qué origen, y cuántos hay de cada nivel de detalle.

Sale de la versión exportada (los ficheros cifrados y su manifiesto), no de la base: es lo que
recibe AEGIS. Comprueba las huellas antes de contar. Cuenta los incidentes activos (ni
fundidos ni retirados). Un campo está lleno si el incidente trae un valor: «desconocido»
(ninguna fuente lo dice), el falso o la lista vacía que pone la regla sin fuentes y lo que
quedó sin respaldo no cuentan como llenos.

Uso: python -m exportacion.completitud <carpeta de la versión>   (con EODI_CLAVE_AGE)
"""

import argparse
import gzip
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from almacen import cifrado
from esquema import Esquema, recorrer
from exportacion import procedencia as origenes
from proceso.incidentes import activo

HOJAS_DE_VALOR = frozenset({"min", "max", "valor", "precision", "lat", "lon"})
ORIGENES = origenes.RANGO[:-1]  # deducido aún no se usa


class VersionInvalida(ValueError):
    pass


def leer_version(directorio: Path) -> tuple[dict[str, Any], dict[str, bytes]]:
    """El manifiesto y cada fichero en claro, con las huellas comprobadas."""
    manifiesto = json.loads((directorio / "manifiesto.json").read_text(encoding="utf-8"))
    ficheros = {}
    for entrada in manifiesto["ficheros"]:
        cifrado_ = (directorio / entrada["cifrado"]["nombre"]).read_bytes()
        if hashlib.sha256(cifrado_).hexdigest() != entrada["cifrado"]["sha256"]:
            raise VersionInvalida(f"{entrada['cifrado']['nombre']}: huella distinta")
        claro = gzip.decompress(cifrado.descifrar_datos(cifrado_))
        if hashlib.sha256(claro).hexdigest() != entrada["sha256"]:
            raise VersionInvalida(f"{entrada['nombre']}: huella en claro distinta")
        ficheros[entrada["nombre"]] = claro
    return manifiesto, ficheros


def campos_del_esquema() -> list[str]:
    """Las rutas de valor del incidente según el esquema (sin los bloques de registro)."""
    rutas = set()
    for ruta, _marca, _interno in recorrer(Esquema.INCIDENTE):
        partes = ruta.split(".")
        if "[]" in ruta or partes[0] in origenes.META_INCIDENTE:
            continue
        if partes[-1] in HOJAS_DE_VALOR and len(partes) > 1:
            continue
        rutas.add(ruta)
    # Un objeto con hijos no es un valor, salvo los que se tratan como uno solo.
    return sorted(
        r
        for r in rutas
        if r in origenes.HOJAS or not any(o.startswith(f"{r}.") for o in rutas)
        if not any(r.startswith(f"{h}.") for h in origenes.HOJAS)
    )


def lleno(incidente: dict[str, Any], ruta: str) -> bool:
    marca = incidente["procedencia"].get(ruta, {})
    return (
        origenes.leer(incidente, ruta) is not None
        and not marca.get("desconocido")
        and "sin_respaldo" not in marca
    )


def tabla(incidentes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    filas = []
    for ruta in campos_del_esquema():
        llenos = [i for i in incidentes if lleno(i, ruta)]
        por_origen = Counter(i["procedencia"][ruta]["origen"] for i in llenos)
        filas.append({"campo": ruta, "llenos": len(llenos), "por_origen": dict(por_origen),
                      "sin_respaldo": sum("sin_respaldo" in i["procedencia"].get(ruta, {})
                                          for i in incidentes)})  # fmt: skip
    return filas


def _porcentaje(n: int, total: int) -> str:
    return f"{100 * n / total:.1f} %" if total else "—"


def markdown(manifiesto: dict[str, Any], incidentes: list[dict[str, Any]]) -> str:
    activos = [i for i in incidentes if activo(i)]
    total = len(activos)
    lineas = [
        f"Versión {manifiesto['version']}: {len(incidentes)} incidentes exportados, {total} "
        "activos (ni fundidos ni retirados); los porcentajes son sobre los activos.",
        "",
        "| Campo | Lleno | " + " | ".join(ORIGENES) + " | Sin respaldo |",
        "| --- | ---: | " + " | ".join("---:" for _ in ORIGENES) + " | ---: |",
    ]
    for fila in tabla(activos):
        celdas = [f"{fila['por_origen'].get(o, 0)}" for o in ORIGENES]
        lineas.append(
            f"| `{fila['campo']}` | {_porcentaje(fila['llenos'], total)} ({fila['llenos']}) | "
            + " | ".join(celdas)
            + f" | {fila['sin_respaldo']} |"
        )
    niveles = Counter(i["nivel_detalle"] for i in activos)
    lineas += ["", "| Nivel de detalle | Incidentes | % |", "| --- | ---: | ---: |"]
    for nivel in origenes.NIVELES:
        lineas.append(f"| {nivel} | {niveles.get(nivel, 0)} | "
                      f"{_porcentaje(niveles.get(nivel, 0), total)} |")  # fmt: skip
    return "\n".join(lineas) + "\n"


def principal(argumentos: list[str] | None = None) -> int:
    opciones = argparse.ArgumentParser(description=__doc__)
    opciones.add_argument("version", type=Path)
    args = opciones.parse_args(argumentos)
    manifiesto, ficheros = leer_version(args.version)
    incidentes = [json.loads(x) for x in ficheros["incidentes.jsonl"].splitlines()]
    sys.stdout.write(markdown(manifiesto, incidentes))
    return 0


if __name__ == "__main__":
    sys.exit(principal())
