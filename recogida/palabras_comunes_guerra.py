"""Genera configuracion/palabras_comunes_guerra.json: los nombres de localidad del nomenclátor
de la capa de guerra que son palabras corrientes en los mensajes de los canales («мирне»,
«перемога», «затока», «дружба»).

Una forma de una palabra del nomenclátor es corriente si sale en minúscula al menos
MIN_MINUSCULAS veces en los mensajes guardados por el lector (`recogida/canales_guerra.py`).
Con ella, el nombre solo cuenta como lugar si va precedido de su tipo de lugar («село Мирне»)
(proceso/lugares_guerra.py). Se vuelve a generar cuando crece el corpus o cambia el
nomenclátor; el resultado se revisa y se versiona.

Con --cache se añaden al corpus las páginas guardadas de otros canales (data/cache: la Fuerza
Aérea de Ucrania y el Ministerio de Defensa ruso, decenas de miles de mensajes en ucraniano y
en ruso).

Uso: python -m recogida.palabras_comunes_guerra [--datos DIR] [--cache data/cache]
"""

import argparse
import gzip
import json
import re
import sys
from collections import Counter
from pathlib import Path

from proceso.lugares_guerra import COMUNES, cargar, normalizar
from recogida.canales_guerra import Datos, cargar_canales, directorio_datos
from recogida.telegram import leer_pagina

MIN_MINUSCULAS = 3
_PALABRA = re.compile(r"[^\W\d_]+")


def minusculas(textos: list[str]) -> Counter[str]:
    """Cuántas veces sale cada palabra normalizada en minúscula."""
    cuenta: Counter[str] = Counter()
    for texto in textos:
        for m in _PALABRA.finditer(texto):
            palabra = m.group(0)
            if palabra[:1].islower():
                cuenta[normalizar(palabra)] += 1
    return cuenta


def comunes(textos: list[str], formas: set[str]) -> list[str]:
    cuenta = minusculas(textos)
    return sorted(f for f in formas if " " not in f and cuenta[f] >= MIN_MINUSCULAS)


def principal(argumentos: list[str] | None = None) -> int:
    opciones = argparse.ArgumentParser(description=__doc__)
    opciones.add_argument("--datos", type=Path)
    opciones.add_argument("--salida", type=Path, default=COMUNES)
    opciones.add_argument("--cache", type=Path)
    args = opciones.parse_args(argumentos)
    datos = Datos(args.datos or directorio_datos())
    textos = [p["texto"] for c in cargar_canales() for p in datos.ultimas(c.canal).values()]
    if args.cache is not None:
        for ruta in sorted(args.cache.glob("*/*.html.gz")):
            pagina = leer_pagina(gzip.decompress(ruta.read_bytes()).decode("utf-8"))
            textos += [p.texto for p in pagina.publicaciones]
    lista = comunes(textos, set(cargar().indice))
    args.salida.write_text(
        json.dumps(
            {
                "version_esquema": "1.0.0",
                "descripcion": "Nombres de localidad del nomenclátor de la capa de guerra que son "
                "palabras corrientes en los mensajes (salen en minúscula al menos "
                f"{MIN_MINUSCULAS} veces en {len(textos)} mensajes): solo valen como lugar "
                "precedidos de su tipo de lugar. Generado por recogida/palabras_comunes_guerra.py.",
                "palabras": lista,
            },
            ensure_ascii=False,
            indent=1,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(f"{len(lista)} palabras corrientes de {len(textos)} mensajes")
    return 0


if __name__ == "__main__":
    sys.exit(principal())
