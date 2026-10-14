#!/usr/bin/env python3
"""Ayudante de borrado del servidor: la única forma en que una sesión borra algo en él.

El 13 de octubre de 2026 una sesión que limpiaba sus ficheros de prueba borró /dev/null y dejó el
servidor sin SSH ni servicios. Desde entonces las sesiones no usan rm en el servidor: borran con
este ayudante, que solo borra dentro de las carpetas de trabajo del observatorio y se niega con
cualquier otra ruta (docs/operacion.md, «Cómo se borra en el servidor»).

Se puede borrar dentro de (nunca la carpeta raíz misma):

- /home/eodi, salvo lo que no es de las sesiones: la base (base/), los datos (datos/), los
  secretos (.eodi/), el clon del observatorio (droneobservatory/) y los navegadores
  (.cache/ms-playwright/);
- /home/operador;
- /tmp y /var/tmp.

Las rutas se resuelven antes de comprobarlas (sin «..» ni enlaces que lleven fuera); un enlace se
borra él, no aquello a lo que apunta. Una carpeta se borra entera sin seguir enlaces.

Uso: sudo python3 /home/eodi/droneobservatory/servidor/borrar.py [--ensayo] <ruta> [<ruta>...]
     (operador no puede leer /home/eodi: con sudo; las rutas permitidas son las mismas)
     sudo -u eodi python3 ... (para lo del usuario eodi)
Código 0 si se borró todo; 1 si se negó o falló alguna (las demás sí se borran); 2 sin rutas.
"""

import argparse
import os
import shutil
import sys
from pathlib import Path

PERMITIDAS = (Path("/home/eodi"), Path("/home/operador"), Path("/tmp"), Path("/var/tmp"))
PROTEGIDAS = (
    Path("/home/eodi/base"),
    Path("/home/eodi/datos"),
    Path("/home/eodi/.eodi"),
    Path("/home/eodi/droneobservatory"),
    Path("/home/eodi/.cache/ms-playwright"),
)


def _dentro(ruta: Path, carpeta: Path) -> bool:
    return ruta == carpeta or carpeta in ruta.parents


def resolver(texto: str) -> Path:
    """La ruta absoluta real, sin seguir el último enlace (un enlace se borra él)."""
    ruta = Path(os.path.abspath(texto))
    return Path(os.path.realpath(ruta.parent)) / ruta.name


def motivo_para_negarse(
    ruta: Path,
    permitidas: tuple[Path, ...] | None = None,
    protegidas: tuple[Path, ...] | None = None,
) -> str | None:
    """None si se puede borrar; si no, por qué no."""
    permitidas = PERMITIDAS if permitidas is None else permitidas
    protegidas = PROTEGIDAS if protegidas is None else protegidas
    if not any(_dentro(ruta, c) and ruta != c for c in permitidas):
        carpetas = ", ".join(str(c) for c in permitidas)
        return f"fuera de las carpetas de trabajo del observatorio ({carpetas})"
    for protegida in protegidas:
        if _dentro(ruta, protegida) or _dentro(protegida, ruta):
            return f"{protegida} no se borra nunca (ni nada dentro ni lo que la contiene)"
    return None


def borrar(ruta: Path) -> None:
    if ruta.is_dir() and not ruta.is_symlink():
        shutil.rmtree(ruta)
    else:
        ruta.unlink()


def principal(argumentos: list[str] | None = None) -> int:
    opciones = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    opciones.add_argument("--ensayo", action="store_true", help="dice lo que borraría")
    opciones.add_argument("rutas", nargs="*")
    args = opciones.parse_args(argumentos)
    if not args.rutas:
        opciones.print_usage(sys.stderr)
        return 2
    codigo = 0
    for texto in args.rutas:
        ruta = resolver(texto)
        motivo = motivo_para_negarse(ruta)
        if motivo:
            print(f"NO se borra {ruta}: {motivo}", file=sys.stderr)
            codigo = 1
            continue
        if not ruta.exists() and not ruta.is_symlink():
            print(f"no existe {ruta}")
            continue
        if args.ensayo:
            print(f"se borraría {ruta}")
            continue
        try:
            borrar(ruta)
        except OSError as error:
            print(f"no se pudo borrar {ruta}: {error}", file=sys.stderr)
            codigo = 1
            continue
        print(f"borrado {ruta}")
    return codigo


if __name__ == "__main__":
    sys.exit(principal())
