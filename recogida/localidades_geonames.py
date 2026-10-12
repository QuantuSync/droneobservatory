"""Genera el nomenclátor de localidades europeas desde GeoNames (CC BY 4.0).

Localidades de más de 1000 habitantes de los países europeos de la recogida y
de sus territorios de fuera del continente, con el país del que dependen
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
# Territorios fuera del continente que GeoNames trata como países y que son suelo europeo
# del país del que dependen: sus localidades van con ese país. Canarias, Ceuta, Melilla,
# Azores y Madeira ya son de España y Portugal en GeoNames, y las localidades de las bases
# británicas de Chipre, del Reino Unido.
TERRITORIOS = {
    "GP": "FR", "MQ": "FR", "GF": "FR", "RE": "FR", "YT": "FR", "MF": "FR",
    "GI": "GB", "GL": "DK", "SJ": "NO",
}  # fmt: skip
# Región de las localidades de cada territorio: el territorio entero (su número de GeoNames,
# de región o de país, y sus nombres), porque es lo que dicen las fuentes («en Guadeloupe»,
# «in Greenland»); Svalbard y Jan Mayen, por separado. Clave: país de GeoNames o país y
# región de primer nivel.
REGIONES_TERRITORIO: dict[str, tuple[str, tuple[str, ...]]] = {
    "GP": ("6690363", ("Guadeloupe", "Guadalupe", "Guadalupa")),
    "MQ": ("6690603", ("Martinique", "Martinica")),
    "GF": ("6690605", ("Guyane", "Guyane française", "French Guiana", "Guayana Francesa",
                       "Französisch-Guayana", "Guiana Francese", "Guiana Francesa")),
    "RE": ("6690283", ("La Réunion", "Réunion", "Reunión", "Riunione")),
    "YT": ("1024031", ("Mayotte", "Maore")),
    "MF": ("3578421", ("Saint-Martin", "Collectivité de Saint-Martin", "San Martín")),
    "GI": ("2411586", ("Gibraltar",)),
    "GL": ("3425505", ("Greenland", "Grønland", "Kalaallit Nunaat", "Groenlandia", "Grönland",
                       "Groenland", "Gronelândia")),
    "SJ.21": ("7521757", ("Svalbard", "Spitsbergen", "Spitzbergen")),
    "SJ.22": ("3041964", ("Jan Mayen",)),
}  # fmt: skip
# Las bases británicas de Chipre (zonas de GeoNames): Akrotiri al oeste de esta longitud,
# Dhekelia al este.
LON_ENTRE_BASES = 33.3
BASE_OESTE = (
    "8306813",
    ("Akrotiri", "Akrotiri Sovereign Base Area", "Western Sovereign Base Area"),
)
BASE_ESTE = ("8306814", ("Dhekelia", "Dhekelia Sovereign Base Area", "Eastern Sovereign Base Area"))
# Una localidad del Reino Unido al este de esta longitud está en Chipre.
LON_MIN_CHIPRE = 30.0


def pais_padre(codigo: str) -> str:
    """El país de la recogida de un país de GeoNames: el suyo o el del que depende."""
    return TERRITORIOS.get(codigo, codigo)


def region_territorio(codigo: str, region: str, lon: float) -> tuple[str, tuple[str, ...]] | None:
    """La región (número de GeoNames y nombres) de una localidad de un territorio de fuera
    del continente, o None si no es de ninguno."""
    if codigo == "GB" and lon > LON_MIN_CHIPRE:
        return BASE_OESTE if lon < LON_ENTRE_BASES else BASE_ESTE
    return REGIONES_TERRITORIO.get(f"{codigo}.{region}") or REGIONES_TERRITORIO.get(codigo)


def radio(poblacion: int) -> float:
    return next(r for minimo, r in RADIOS if poblacion >= minimo)


def palabras_vocabulario(config: dict[str, Any]) -> set[str]:
    """Palabras del vocabulario de noticias: no pueden ser nombres de localidad."""
    listas = [config["excluir"], *config["senales"].values(), *config["tipo_de_lugar"].values()]
    listas += list(config["palabras_dron"].values())
    return {normalizar(p) for lista in listas for p in lista}


def generar(texto: str, paises: set[str], vocabulario: set[str]) -> dict[str, Any]:
    localidades: dict[str, dict[str, Any]] = {}
    duenos: dict[str, tuple[bool, int, str]] = {}
    for linea in texto.splitlines():
        c = linea.split("\t")
        if len(c) <= C_POBLACION or pais_padre(c[C_PAIS]) not in paises:
            continue
        if omitido(c[C_NOMBRE]):
            continue
        # Un nombre compartido entre el continente y un territorio de fuera es de la
        # localidad del continente, aunque sea menor: las noticias hablan mucho más de ella
        # («Saint-Denis» es la de Seine-Saint-Denis, no la de La Reunión, que queda en
        # localidades_pequenas.json.gz y sale cuando la ficha dice la región).
        habitantes = int(c[C_POBLACION] or 0)
        prioridad = (c[C_PAIS] not in TERRITORIOS, habitantes)
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
            if normal not in duenos or duenos[normal][:2] < prioridad:
                duenos[normal] = (*prioridad, c[C_ID])
        if validos:
            localidades[c[C_ID]] = {
                "nombre": c[C_NOMBRE],
                "pais": pais_padre(c[C_PAIS]),
                "lat": round(float(c[C_LAT]), DECIMALES),
                "lon": round(float(c[C_LON]), DECIMALES),
                "radio_km": radio(habitantes),
                "alias": validos,
            }
    for id_, datos in localidades.items():
        datos["alias"] = [a for a in datos["alias"] if duenos[normalizar(a)][2] == id_]
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
