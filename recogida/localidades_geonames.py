"""Genera el nomenclátor de localidades europeas desde GeoNames (CC BY 4.0).

Localidades de más de 1000 habitantes de los países europeos de la recogida
(el fichero `cities1000` de GeoNames), con sus nombres alternativos. Solo se
usan cuando el titular no nombra ninguna instalación y trae una señal de
incidente: sitúan la noticia en una ciudad.

Para no confundir nombres de localidades con palabras corrientes:
- se omiten los nombres que son palabras del propio vocabulario de noticias
  («Police», en Polonia, es también «police»);
- si varias localidades comparten nombre, el nombre es de la más poblada.

Datos de GeoNames (https://www.geonames.org), CC BY 4.0.

Uso: python -m recogida.localidades_geonames [--desde cities1000.zip]
"""

import argparse
import io
import json
import re
import sys
import unicodedata
import zipfile
from pathlib import Path
from typing import Any

from proceso.noticias import configuracion, normalizar
from recogida.descarga import AGENTE_EODI, Descargador
from recogida.instalaciones_osm import omitido

FUENTE = "https://download.geonames.org/export/dump/cities1000.zip"
DESTINO = Path(__file__).resolve().parent.parent / "configuracion" / "localidades_europa.json"
DECIMALES = 5
MIN_LETRAS = 4
MAX_LETRAS = 40
# Radio de la localidad por habitantes: un pueblo cabe en 3 km, una ciudad media en 5,
# una grande en 10 y una capital de más de un millón en 20.
RADIOS = ((1_000_000, 20.0), (100_000, 10.0), (10_000, 5.0), (0, 3.0))
# Columnas del volcado de GeoNames.
C_ID, C_NOMBRE, C_ASCII, C_ALTERNATIVOS, C_LAT, C_LON = 0, 1, 2, 3, 4, 5
C_PAIS, C_POBLACION = 8, 14
_ESCRITURA = re.compile(r"^[\w\s'’.-]+$")


def radio(poblacion: int) -> float:
    return next(r for minimo, r in RADIOS if poblacion >= minimo)


def palabras_vocabulario(config: dict[str, Any]) -> set[str]:
    """Palabras del vocabulario de noticias: no pueden ser nombres de localidad."""
    listas = [config["excluir"], *config["senales"].values(), *config["tipo_de_lugar"].values()]
    listas += list(config["palabras_dron"].values())
    return {normalizar(p) for lista in listas for p in lista}


def generar(texto: str, paises: set[str], vocabulario: set[str]) -> dict[str, Any]:
    localidades: dict[str, dict[str, Any]] = {}
    duenos: dict[str, tuple[int, str]] = {}
    for linea in texto.splitlines():
        c = linea.split("\t")
        if len(c) <= C_POBLACION or c[C_PAIS] not in paises or omitido(c[C_NOMBRE]):
            continue
        poblacion = int(c[C_POBLACION] or 0)
        nombres = [c[C_NOMBRE], c[C_ASCII], *c[C_ALTERNATIVOS].split(",")]
        validos = []
        for nombre in dict.fromkeys(n.strip() for n in nombres):
            normal = normalizar(nombre)
            if not MIN_LETRAS <= len(normal) <= MAX_LETRAS or not _ESCRITURA.match(nombre):
                continue
            if normal in vocabulario or omitido(nombre):
                continue
            validos.append(nombre)
            # El nombre es de la localidad más poblada que lo lleva.
            if normal not in duenos or duenos[normal][0] < poblacion:
                duenos[normal] = (poblacion, c[C_ID])
        if validos:
            localidades[c[C_ID]] = {
                "nombre": c[C_NOMBRE],
                "pais": c[C_PAIS],
                "lat": round(float(c[C_LAT]), DECIMALES),
                "lon": round(float(c[C_LON]), DECIMALES),
                "radio_km": radio(poblacion),
                "alias": validos,
            }
    for id_, datos in localidades.items():
        datos["alias"] = [a for a in datos["alias"] if duenos[normalizar(a)][1] == id_]
    return {
        "version_esquema": "1.0.0",
        "descripcion": (
            "Localidades europeas de más de 1000 habitantes con sus nombres alternativos, "
            "para situar noticias que no nombran ninguna instalación. Un nombre compartido es "
            "de la localidad más poblada; se omiten los nombres que son palabras del "
            "vocabulario de noticias. Cada localidad: [nombre, país, lat, lon, radio_km, alias]."
        ),
        "licencia": "Datos de GeoNames (https://www.geonames.org), CC BY 4.0",
        "localidades": {
            f"loc:{id_}": [d["nombre"], d["pais"], d["lat"], d["lon"], d["radio_km"], d["alias"]]
            for id_, d in sorted(localidades.items(), key=lambda x: int(x[0]))
            if d["alias"]
        },
    }


def principal(argumentos: list[str] | None = None) -> int:
    opciones = argparse.ArgumentParser(description=__doc__)
    opciones.add_argument("--desde", type=Path, help="cities1000.zip ya descargado")
    args = opciones.parse_args(argumentos)
    if args.desde:
        contenido = args.desde.read_bytes()
    else:
        contenido = Descargador(agente=AGENTE_EODI).contenido(FUENTE, lambda c: c[:2] == b"PK")
    with zipfile.ZipFile(io.BytesIO(contenido)) as comprimido:
        texto = comprimido.read("cities1000.txt").decode("utf-8")
    config = configuracion()
    datos = generar(texto, set(config["paises"].values()), palabras_vocabulario(config))
    # En forma descompuesta, como el nomenclátor: algunas herramientas de texto no toman
    # como letra una «ș» dentro de una palabra y parten el nombre. Una localidad por línea.
    texto_json = json.dumps(datos, ensure_ascii=False, separators=(",", ":"))
    texto_json = unicodedata.normalize("NFD", texto_json).replace('],"loc:', '],\n"loc:')
    DESTINO.write_text(texto_json + "\n", encoding="utf-8", newline="\n")
    print(len(datos["localidades"]), "localidades")
    return 0


if __name__ == "__main__":
    sys.exit(principal())
