"""La auditoría de las fichas vigentes a mano (proceso/auditoria_fichas.py), sobre una copia de la
base: no escribe nada ni llama a nada. Imprime el recuento de cada comprobación con sus fichas.

    python -m recogida.auditoria_fichas [--base /ruta/eodi.sqlite] [--json]
"""

import argparse
import json
import sqlite3
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

from almacen.base import Almacen
from proceso import auditoria_fichas


def copia(origen: Path, destino: Path) -> Path:
    """Una copia coherente de la base, leída en solo lectura (la recogida puede estar guardando)."""
    fuente = sqlite3.connect(f"file:{origen}?mode=ro", uri=True)
    copia_ = sqlite3.connect(destino)
    fuente.backup(copia_)
    copia_.close()
    fuente.close()
    return destino


def principal(argumentos: list[str] | None = None) -> int:
    opciones = argparse.ArgumentParser(description=__doc__)
    opciones.add_argument("--base", type=Path, default=Path.home() / "base" / "eodi.sqlite")
    opciones.add_argument("--json", action="store_true", help="los identificadores en JSON")
    args = opciones.parse_args(argumentos)
    with TemporaryDirectory() as temporal:
        almacen = Almacen.abrir(copia(args.base, Path(temporal) / "eodi.sqlite"))
        resultado = auditoria_fichas.auditar(almacen.incidentes())
    if args.json:
        print(json.dumps(resultado, ensure_ascii=False, indent=1))
    else:
        print(auditoria_fichas.texto(resultado, limite=1000))
    return 0


if __name__ == "__main__":
    sys.exit(principal())
