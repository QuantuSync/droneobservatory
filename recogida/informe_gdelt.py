"""Informe interno de las noticias de GDELT: artículos y candidatos por mes y una muestra.

La muestra son 10 candidatos elegidos al azar con semilla fija, con los titulares y
enlaces de sus artículos, para comprobar a mano que la agrupación tiene sentido.

Uso en local, con la base de la rama estado:
    python -m recogida.informe_gdelt
Uso en una prueba sin base (recoge los últimos días en memoria):
    python -m recogida.informe_gdelt --dias 7 --horas 5
"""

import argparse
import random
import sys
import time
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory

from almacen import remoto
from almacen.base import Almacen
from almacen.cifrado import abrir_cifrada, cargar_clave_local
from recogida import gdelt, historico_gdelt

# Semilla fija para que la muestra sea reproducible; su valor no importa.
SEMILLA_MUESTRA = 1
TAMANO_MUESTRA = 10


def informe(almacen: Almacen) -> str:
    articulos = almacen.articulos()
    candidatos = almacen.candidatos()
    por_mes_a = Counter(a["fecha"][:7] for a in articulos)
    por_mes_c = Counter(c["inicio"][:7] for c in candidatos)
    replicas: Counter[str] = Counter()
    for a in articulos:
        replicas[a["fecha"][:7]] += a["replicas"]
    lineas = ["| Mes | Artículos | Réplicas | Candidatos |", "| --- | ---: | ---: | ---: |"]
    for mes in sorted(set(por_mes_a) | set(por_mes_c)):
        lineas.append(f"| {mes} | {por_mes_a[mes]} | {replicas[mes]} | {por_mes_c[mes]} |")
    lineas.append(f"| Total | {len(articulos)} | {sum(replicas.values())} | {len(candidatos)} |")
    titulares = {a["url"]: a["titular"] for a in articulos}
    elegidos = random.Random(SEMILLA_MUESTRA).sample(
        candidatos, min(TAMANO_MUESTRA, len(candidatos))
    )
    lineas += ["", "Muestra:", ""]
    for candidato in sorted(elegidos, key=lambda c: c["id"]):
        lineas.append(
            f"- **{candidato['id']}** ({candidato['tipo']}, {candidato['inicio']} a "
            f"{candidato['ultimo']}, {len(candidato['articulos'])} artículos)"
        )
        lineas += [f"  - {titulares.get(url, '')} — {url}" for url in candidato["articulos"]]
    return "\n".join(lineas) + "\n"


def principal(argumentos: list[str] | None = None) -> int:
    opciones = argparse.ArgumentParser(description=__doc__)
    opciones.add_argument("--dias", type=int, help="recoge en memoria los últimos N días")
    opciones.add_argument("--horas", type=float, default=float("inf"))
    args = opciones.parse_args(argumentos)
    if args.dias:
        almacen = Almacen.abrir()
        ahora = datetime.now(UTC).replace(minute=0, second=0, microsecond=0)
        limite = time.monotonic() + args.horas * 3600
        historico_gdelt.recorrer(
            almacen, gdelt.descargador(), ahora, limite, desde=ahora - timedelta(days=args.dias)
        )
        sys.stdout.write(informe(almacen))
        return 0
    cargar_clave_local()
    with TemporaryDirectory() as temporal:
        ruta = Path(temporal) / remoto.FICHERO
        if not remoto.descargar(ruta, remoto.REPOSITORIO):
            return 1
        sys.stdout.write(informe(Almacen(abrir_cifrada(ruta))))
    return 0


if __name__ == "__main__":
    sys.exit(principal())
