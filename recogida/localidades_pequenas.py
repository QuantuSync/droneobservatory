"""Genera el nomenclátor de localidades pequeñas desde GeoNames (CC BY 4.0).

Todas las localidades pobladas de los países de la recogida que no están ya en
`configuracion/localidades_europa.json` (las de 1000 habitantes o más): aldeas, pedanías y
barrios con nombre, con sus nombres alternativos. Y, de las que sí están, los nombres que
allí se quedó una homónima más poblada (el Grindu de Tulcea solo conserva allí «Pisica»,
porque «Grindu» es del de Ialomița). Se descartan los lugares históricos,
abandonados, destruidos o que son parte de otra localidad (códigos PPLH, PPLQ, PPLW, PPLX
y PPLCH de GeoNames).

Solo se usan para situar el lugar del suceso que da la ficha del extractor, ya limitado
a su país (`proceso/ubicacion.py`), nunca para situar un titular: entre medio millón de
aldeas, casi cualquier palabra de un titular es el nombre de alguna. Medido con los 50 000
titulares de la base: de los 550 668 nombres nuevos de una palabra, 2428 salen en
minúscula en algún titular (son palabras corrientes: «para», «guerra», «strike») y de los
que salen solo con mayúscula casi todos son personas, organizaciones, regiones o ciudades
de fuera («Merz», «Reuters», «Bayern», «Moscou»).

Nombres que no se guardan, además de los que ya descarta el nomenclátor de localidades
(palabras del vocabulario de noticias, palabras omitidas y nombres de países):

- los nombres de regiones de primer nivel de cualquier país de la recogida («Bayern»):
  una aldea que se llame como una región casi nunca es de lo que habla la fuente;
- los de ciudades de 15 000 habitantes o más de fuera de los países de la recogida
  («Moscou», «Odesa», «Engels»);
- las palabras que salen en minúscula en titulares de medios del mismo país que la
  localidad: son palabras corrientes en su idioma. Por país y no en general: «grindų»
  («suelos» en lituano) se normaliza como «grindu», que es un pueblo de Tulcea.

Un nombre que llevan varias localidades pequeñas del mismo país no se resuelve solo: al
buscarlo hace falta la región para distinguirlas. Un nombre que también es de una
localidad de 1000 habitantes o más se guarda, pero al situar se prueba antes la grande:
la pequeña solo sale si la grande no vale (es de otra región que la que da la ficha, como
el Grindu de Ialomița para un dron caído en Tulcea).

Datos de GeoNames (https://www.geonames.org), CC BY 4.0.

Uso: python -m recogida.localidades_pequenas --paises <carpeta con XX.zip de GeoNames>
    --regiones admin1CodesASCII.txt --ciudades cities15000.zip --base <db.age local>
"""

import argparse
import collections
import gzip
import io
import json
import re
import sys
import zipfile
from pathlib import Path
from typing import Any

from almacen.base import Almacen
from almacen.cifrado import abrir_cifrada, cargar_clave_local
from proceso.fronteras import es_nombre_de_pais, paises
from proceso.noticias import configuracion, normalizar
from recogida.instalaciones_osm import omitido
from recogida.localidades_geonames import (
    C_ALTERNATIVOS,
    C_ASCII,
    C_ID,
    C_LAT,
    C_LON,
    C_NOMBRE,
    C_PAIS,
    C_POBLACION,
    DECIMALES,
    MAX_LETRAS,
    MIN_LETRAS,
    palabras_vocabulario,
)
from recogida.localidades_geonames import DESTINO as LOCALIDADES

DESTINO = Path(__file__).resolve().parent.parent / "configuracion" / "localidades_pequenas.json.gz"
C_CLASE, C_CODIGO, C_REGION = 6, 7, 10
POBLADO = "P"
# Históricos, abandonados, destruidos, parte de otra localidad, históricos de capital.
CODIGOS_EXCLUIDOS = frozenset({"PPLH", "PPLQ", "PPLW", "PPLX", "PPLCH"})
# Una ciudad de fuera de la recogida pesa más que una aldea con su nombre desde este tamaño.
MIN_CIUDAD_FUERA = 15_000
_ESCRITURA = re.compile(r"^[\w\s'’.-]+$")
_PALABRA = re.compile(r"[^\W\d_][\w'’-]*")
NIVEL_COMPRESION = 9


def palabras_en_minuscula(titulares: list[tuple[str | None, str]]) -> dict[str, set[str]]:
    """Por país del medio, las palabras que salen en minúscula en sus titulares."""
    palabras: dict[str, set[str]] = collections.defaultdict(set)
    for pais, titular in titulares:
        if pais:
            palabras[pais] |= {normalizar(p) for p in _PALABRA.findall(titular) if p[0].islower()}
    return palabras


def ciudades_de_fuera(texto: str, propios: set[str]) -> set[str]:
    nombres: set[str] = set()
    for linea in texto.splitlines():
        c = linea.split("\t")
        if len(c) <= C_POBLACION or c[C_PAIS] in propios:
            continue
        if int(c[C_POBLACION] or 0) >= MIN_CIUDAD_FUERA:
            nombres |= {
                normalizar(n) for n in (c[C_NOMBRE], c[C_ASCII], *c[C_ALTERNATIVOS].split(","))
            }
    return nombres


def regiones(texto: str, propios: set[str]) -> tuple[dict[str, str], set[str]]:
    """Código de región («RO.37») a su número de GeoNames, y los nombres de las regiones."""
    numeros: dict[str, str] = {}
    nombres: set[str] = set()
    for linea in texto.splitlines():
        partes = linea.split("\t")
        if len(partes) >= len(("codigo", "nombre", "ascii", "numero")) and partes[0][:2] in propios:
            numeros[partes[0]] = partes[3]
            nombres |= {normalizar(partes[1]), normalizar(partes[2])}
    return numeros, nombres


def generar(
    filas: list[list[str]],
    ya_estan: dict[str, set[str]],
    alias_grandes: set[str],
    excluir: dict[str, set[str]],
    numeros_region: dict[str, str],
    corrientes: dict[str, set[str]],
) -> dict[str, Any]:
    recuentos: collections.Counter[str] = collections.Counter()
    localidades: dict[str, list[Any]] = {}
    for c in filas:
        if c[C_CLASE] != POBLADO or c[C_CODIGO] in CODIGOS_EXCLUIDOS:
            continue
        # De una localidad que ya está, solo los nombres que allí no tiene.
        propios = ya_estan.get(c[C_ID], set())
        validos: list[str] = []
        for nombre in dict.fromkeys(
            n.strip() for n in (c[C_NOMBRE], c[C_ASCII], *c[C_ALTERNATIVOS].split(","))
        ):
            normal = normalizar(nombre)
            if not MIN_LETRAS <= len(normal) <= MAX_LETRAS or not _ESCRITURA.match(nombre):
                continue
            if omitido(nombre) or normal in validos or normal in propios:
                continue
            motivo = next((m for m, nombres in excluir.items() if normal in nombres), None)
            if motivo is None and es_nombre_de_pais(normal):
                motivo = "pais"
            if motivo is None and normal in corrientes.get(c[C_PAIS], set()):
                motivo = "palabra_corriente"
            if motivo is not None:
                recuentos[motivo] += 1
                continue
            validos.append(normal)
            recuentos["compartido_con_grande"] += normal in alias_grandes
        if validos:
            localidades[f"loc:{c[C_ID]}"] = [
                c[C_NOMBRE], c[C_PAIS], round(float(c[C_LAT]), DECIMALES),
                round(float(c[C_LON]), DECIMALES),
                numeros_region.get(f"{c[C_PAIS]}.{c[C_REGION]}"), validos,
            ]  # fmt: skip
    # Nombres de varias localidades pequeñas de un mismo país: solo se resuelven con la región.
    por_pais: collections.Counter[tuple[str, str]] = collections.Counter(
        (datos[1], a) for datos in localidades.values() for a in datos[5]
    )
    recuentos["ambiguos_en_su_pais"] = sum(1 for n in por_pais.values() if n > 1)
    return {
        "version_esquema": "1.0.0",
        "descripcion": (
            "Localidades pobladas de menos de 1000 habitantes (las que no están en "
            "localidades_europa.json) y, de las que están, los nombres que allí tiene una "
            "homónima más poblada; con sus nombres normalizados, para situar el lugar del "
            "suceso de una ficha dentro de su país. Cada una: [nombre, país, lat, lon, número "
            "de GeoNames de su región, nombres]. exclusiones: cuántos nombres se descartan por "
            "cada regla (recogida/localidades_pequenas.py)."
        ),
        "licencia": "Datos de GeoNames (https://www.geonames.org), CC BY 4.0",
        "exclusiones": dict(sorted(recuentos.items())),
        "localidades": dict(sorted(localidades.items(), key=lambda x: int(x[0][4:]))),
    }


def _texto_zip(ruta: Path, nombre: str) -> str:
    with zipfile.ZipFile(io.BytesIO(ruta.read_bytes())) as comprimido:
        return comprimido.read(nombre).decode("utf-8")


def principal(argumentos: list[str] | None = None) -> int:
    opciones = argparse.ArgumentParser(description=__doc__)
    opciones.add_argument("--paises", type=Path, required=True, help="carpeta con XX.zip")
    opciones.add_argument("--regiones", type=Path, required=True)
    opciones.add_argument("--ciudades", type=Path, required=True, help="cities15000.zip")
    opciones.add_argument("--base", type=Path, required=True, help="base cifrada local")
    args = opciones.parse_args(argumentos)
    propios = set(paises())
    cargar_clave_local()
    almacen = Almacen(abrir_cifrada(args.base))
    titulares = [(a.get("pais"), str(a["titular"])) for a in almacen.articulos()]
    grandes = json.loads(LOCALIDADES.read_text(encoding="utf-8"))["localidades"]
    numeros_region, nombres_region = regiones(args.regiones.read_text(encoding="utf-8"), propios)
    excluir = {
        "vocabulario": palabras_vocabulario(configuracion()),
        "region": nombres_region,
        "ciudad_de_fuera": ciudades_de_fuera(_texto_zip(args.ciudades, "cities15000.txt"), propios),
    }
    filas = [
        linea.split("\t")
        for pais in sorted(propios)
        if (args.paises / f"{pais}.zip").exists()
        for linea in _texto_zip(args.paises / f"{pais}.zip", f"{pais}.txt").splitlines()
    ]
    alias_grandes = {normalizar(a) for datos in grandes.values() for a in datos[5]}
    ya_estan = {
        i.removeprefix("loc:"): {normalizar(a) for a in datos[5]} for i, datos in grandes.items()
    }
    datos = generar(
        filas, ya_estan, alias_grandes, excluir, numeros_region, palabras_en_minuscula(titulares)
    )
    texto = json.dumps(datos, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    DESTINO.write_bytes(gzip.compress(texto, NIVEL_COMPRESION, mtime=0))
    print(len(datos["localidades"]), "localidades;", datos["exclusiones"])
    return 0


if __name__ == "__main__":
    sys.exit(principal())
