"""Genera la región de primer nivel de cada localidad del nomenclátor desde GeoNames (CC BY 4.0).

Un nombre de localidad puede ser de varias (hay un Grindu en Tulcea y otro en
Ialomița) y el nomenclátor se queda con el de la más poblada. Cuando la ficha dice
en qué región ocurrió el suceso, la región de la localidad hallada permite
descartarla si es otra (`proceso/ubicacion.py`).

Por cada región, identificada por su número de GeoNames, su país y sus nombres
normalizados (`admin1CodesASCII.txt`); por cada localidad de
`configuracion/localidades_europa.json`, el número de su región (`cities1000`).

Datos de GeoNames (https://www.geonames.org), CC BY 4.0.

Uso: python -m recogida.regiones_geonames [--ciudades cities1000.zip]
    [--regiones admin1CodesASCII.txt]
"""

import argparse
import io
import json
import sys
import zipfile
from pathlib import Path
from typing import Any

from proceso.noticias import normalizar
from recogida.descarga import AGENTE_EODI, Descargador
from recogida.localidades_geonames import C_ID, C_PAIS
from recogida.localidades_geonames import DESTINO as LOCALIDADES
from recogida.localidades_geonames import FUENTE as CIUDADES

REGIONES = "https://download.geonames.org/export/dump/admin1CodesASCII.txt"
DESTINO = Path(__file__).resolve().parent.parent / "configuracion" / "regiones_localidades.json"
# Columna del código de región de primer nivel en cities1000.
C_REGION = 10
PREFIJO = "loc:"


def generar(ciudades: str, regiones: str, ids: set[str]) -> dict[str, Any]:
    # Código de región («RO.37») a su número de GeoNames; y por número, país y nombres.
    numeros: dict[str, str] = {}
    regiones_: dict[str, dict[str, Any]] = {}
    for linea in regiones.splitlines():
        partes = linea.split("\t")
        if len(partes) >= len(("codigo", "nombre", "ascii", "numero")):
            codigo, nombre, ascii_, numero = partes[:4]
            numeros[codigo] = numero
            regiones_[numero] = {
                "pais": codigo.split(".")[0],
                "nombres": sorted({normalizar(nombre), normalizar(ascii_)}),
            }
    de_localidad: dict[str, str] = {}
    for linea in ciudades.splitlines():
        c = linea.split("\t")
        if len(c) <= C_REGION or c[C_ID] not in ids:
            continue
        numero_region = numeros.get(f"{c[C_PAIS]}.{c[C_REGION]}")
        if numero_region is not None:
            de_localidad[PREFIJO + c[C_ID]] = numero_region
    usadas = set(de_localidad.values())
    return {
        "version_esquema": "1.0.0",
        "descripcion": (
            "Región de primer nivel de cada localidad del nomenclátor: regiones, número de "
            "GeoNames a país y nombres normalizados; localidades, identificador a número de "
            "su región."
        ),
        "licencia": "Datos de GeoNames (https://www.geonames.org), CC BY 4.0",
        "regiones": {k: v for k, v in sorted(regiones_.items()) if k in usadas},
        "localidades": dict(sorted(de_localidad.items())),
    }


def principal(argumentos: list[str] | None = None) -> int:
    opciones = argparse.ArgumentParser(description=__doc__)
    opciones.add_argument("--ciudades", type=Path, help="cities1000.zip ya descargado")
    opciones.add_argument("--regiones", type=Path, help="admin1CodesASCII.txt ya descargado")
    args = opciones.parse_args(argumentos)
    descargador = Descargador(agente=AGENTE_EODI)
    comprimido = (
        args.ciudades.read_bytes()
        if args.ciudades
        else descargador.contenido(CIUDADES, lambda c: c[:2] == b"PK")
    )
    with zipfile.ZipFile(io.BytesIO(comprimido)) as zip_:
        ciudades = zip_.read("cities1000.txt").decode("utf-8")
    regiones = (
        args.regiones.read_text(encoding="utf-8")
        if args.regiones
        else descargador.texto(REGIONES, lambda t: "\t" in t)
    )
    localidades = json.loads(LOCALIDADES.read_text(encoding="utf-8"))["localidades"]
    ids = {i.removeprefix(PREFIJO) for i in localidades}
    datos = generar(ciudades, regiones, ids)
    texto = json.dumps(datos, ensure_ascii=False, separators=(",", ":"))
    DESTINO.write_text(texto + "\n", encoding="utf-8", newline="\n")
    print(len(datos["localidades"]), "localidades,", len(datos["regiones"]), "regiones")
    return 0


if __name__ == "__main__":
    sys.exit(principal())
