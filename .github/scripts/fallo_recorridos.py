"""Qué falló en una ejecución del workflow «recorridos»: la preparación o la web.

Lee de la entrada los trabajos de la ejecución, uno por línea en JSON (lo que da
`gh api repos/<repo>/actions/runs/<id>/attempts/<n>/jobs --paginate --jq '.jobs[]'`), y escribe:

- «web» si algún recorrido falló en el paso de los recorridos (la web no pasó una prueba, o no
  respondió a tiempo);
- «preparacion» si los que fallaron lo hicieron antes: al descargar la imagen de Playwright, al
  instalar las dependencias, o en la puesta en marcha del trabajo;
- nada si no falló ninguno.

Los trabajos «destino» e «incidencia» no son recorridos y no cuentan.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Iterable
from typing import Any

NO_SON_RECORRIDOS = {"destino", "incidencia"}
FALLOS = {"failure", "cancelled", "timed_out"}
PASO_DE_LA_WEB = "Recorridos"


def fase_del_fallo(trabajo: dict[str, Any]) -> str | None:
    """«web», «preparacion» o None si el trabajo no falló."""
    if trabajo.get("name") in NO_SON_RECORRIDOS or trabajo.get("conclusion") not in FALLOS:
        return None
    for paso in trabajo.get("steps") or []:
        if paso.get("conclusion") in FALLOS:
            return "web" if str(paso.get("name", "")).startswith(PASO_DE_LA_WEB) else "preparacion"
    # Sin paso fallido: el trabajo murió antes de su primer paso (máquina, red, tiempo agotado).
    return "preparacion"


def fase(trabajos: Iterable[dict[str, Any]]) -> str:
    fases = {fase_del_fallo(t) for t in trabajos} - {None}
    if "web" in fases:
        return "web"
    return "preparacion" if fases else ""


def main() -> None:
    trabajos = [json.loads(linea) for linea in sys.stdin if linea.strip()]
    print(fase(trabajos))


if __name__ == "__main__":
    main()
