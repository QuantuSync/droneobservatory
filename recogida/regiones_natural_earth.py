"""Genera la tabla de regiones del lugar aproximado desde Natural Earth (dominio público).

Un incidente sin punto (publicacion/incidentes_sin_ubicacion.json) se pinta en el centro de la
región que nombra la fuente (web/src/datos/lugarAproximado.ts). Se guardan, de las regiones de
primer nivel de cada país del observatorio (los județe de Rumanía, los raioane de Moldavia, los
voivodatos de Polonia, los departamentos de Francia…), solo el punto de etiqueta de Natural
Earth y los nombres normalizados (minúsculas, sin acentos ni signos: «iasi», «яссы»), en todas
las formas que trae: el nombre, el local, los alternativos y los de cada idioma. Un nombre que en
el mismo país lleva a dos regiones lejanas no se guarda: no se sabe cuál es.

Fuente: ne_10m_admin_1_states_provinces.dbf (los atributos del shapefile, unos 15 MB), de
https://github.com/nvkelso/natural-earth-vector/tree/master/10m_cultural. Se descarga una vez,
no se versiona; el resultado, configuracion/regiones_aproximadas.json, sí.

Se ejecuta a mano, rara vez; el resultado se revisa y se versiona.

Uso: python -m recogida.regiones_natural_earth --desde ne_10m_admin_1_states_provinces.dbf
"""

import argparse
import json
import math
import struct
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path
from typing import Any

FUENTE = (
    "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/10m_cultural/"
    "ne_10m_admin_1_states_provinces.dbf"
)
DESTINO = Path(__file__).resolve().parent.parent / "configuracion" / "regiones_aproximadas.json"
DECIMALES = 3
# Los países del observatorio: los del punto de etiqueta de web/src/datos/lugarAproximado.ts.
PAISES = frozenset({
    "AD", "AL", "AM", "AT", "AX", "AZ", "BA", "BE", "BG", "BY", "CH", "CY", "CZ", "DE", "DK",
    "EE", "ES", "FI", "FO", "FR", "GB", "GE", "GG", "GR", "HR", "HU", "IE", "IM", "IS", "IT",
    "JE", "LI", "LT", "LU", "LV", "MC", "MD", "ME", "MK", "MT", "NL", "NO", "PL", "PT", "RO",
    "RS", "RU", "SE", "SI", "SK", "SM", "TR", "UA", "VA", "XK",
})  # fmt: skip
# Natural Earth da algunos países sin código ISO de dos letras: su código de tres.
POR_A3 = {"KOS": "XK", "NOR": "NO", "FRA": "FR", "ALD": "AX", "CYN": "CY"}
# Unidades que el observatorio cuenta dentro de otro país (como recogida/fronteras_natural_earth).
UNIDADES_DE = {"AX": "FI", "FO": "DK", "JE": "GB", "GG": "GB", "IM": "GB"}
# Los campos con nombres de la región.
CAMPOS_NOMBRE = (
    "name", "name_local", "woe_name", "gn_name", "gns_name", "name_en", "name_de", "name_es",
    "name_fr", "name_el", "name_hu", "name_it", "name_nl", "name_pl", "name_pt", "name_ru",
    "name_sv", "name_tr", "name_uk",
)  # fmt: skip
CAMPOS_VARIOS = ("name_alt",)
# Dos regiones del mismo país con el mismo nombre a menos de esto son la misma (la ciudad y su
# provincia en algunos países): vale la primera.
KM_MISMA = 40.0
MIN_LETRAS = 3
# Palabras que dicen qué clase de región es, en los nombres de Natural Earth y en las fuentes
# («județul Iași», «Iasi County», «Kreis Iasi», «Rîșcani, raionul», «Yaş ili»): un nombre sin
# ellas también vale. La web las quita igual del nombre que da la ficha.
GENERICOS = (
    "judetul", "judet", "raionul", "raion", "rajon", "county", "kreis", "okreg", "ili",
    "province", "provincia", "provincie", "region", "regione", "oblast", "voivodeship",
    "wojewodztwo", "department", "departement", "district", "landkreis", "bezirk", "kanton",
    "canton", "megye", "maakond", "apskritis", "novads", "fylke", "maakunta", "повіт", "уезд",
    "жудец", "район", "раион", "область", "округ", "περιφερεια", "νομος", "τζουντετς", "του",
    "της", "of", "the", "de", "del", "di", "du",
)  # fmt: skip


def normalizar(texto: str) -> str:
    """Como `normalizar` de web/src/datos/lugarAproximado.ts: minúsculas, sin signos diacríticos
    y con un solo espacio."""
    sin = "".join(c for c in unicodedata.normalize("NFD", texto) if not unicodedata.combining(c))
    return " ".join(sin.lower().split())


def leer_dbf(datos: bytes) -> list[dict[str, str]]:
    """Las filas de un fichero dBase III (los atributos de un shapefile), en UTF-8."""
    filas, cabecera, largo = struct.unpack("<IHH", datos[4:12])
    campos: list[tuple[str, int]] = []
    i = 32
    while datos[i] != 0x0D:
        nombre = datos[i : i + 11].split(b"\0")[0].decode("ascii")
        campos.append((nombre, datos[i + 16]))
        i += 32
    salida = []
    for n in range(filas):
        inicio = cabecera + n * largo
        if datos[inicio : inicio + 1] == b"*":
            continue
        posicion = inicio + 1
        fila = {}
        for nombre, ancho in campos:
            crudo = datos[posicion : posicion + ancho].rstrip(b"\0 ")
            fila[nombre] = crudo.decode("utf-8", "replace").strip()
            posicion += ancho
        salida.append(fila)
    return salida


def _pais(fila: dict[str, str]) -> str | None:
    codigo = fila.get("iso_a2") or ""
    if len(codigo) != 2 or not codigo.isalpha():
        codigo = POR_A3.get(fila.get("adm0_a3") or "", "")
    codigo = UNIDADES_DE.get(codigo, codigo)
    return codigo if codigo in PAISES else None


def _km(a: tuple[float, float], b: tuple[float, float]) -> float:
    f1, f2 = math.radians(a[1]), math.radians(b[1])
    h = (
        math.sin((f2 - f1) / 2) ** 2
        + math.cos(f1) * math.cos(f2) * math.sin(math.radians(b[0] - a[0]) / 2) ** 2
    )
    return 2 * 6371.0 * math.asin(math.sqrt(h))


def nombres_de(fila: dict[str, str]) -> list[str]:
    crudos = [fila.get(c, "") for c in CAMPOS_NOMBRE]
    for campo in CAMPOS_VARIOS:
        crudos += (fila.get(campo) or "").split("|")
    salida = []
    for crudo in crudos:
        normal = normalizar(crudo)
        for forma in (normal, sin_genericos(normal)):
            if sum(c.isalpha() for c in forma) >= MIN_LETRAS and forma not in salida:
                salida.append(forma)
    return salida


def sin_genericos(normal: str) -> str:
    """El nombre normalizado sin las palabras de clase de región ni las comas: «iasi, judetul»
    es «iasi». Como `sinGenericos` de web/src/datos/lugarAproximado.ts."""
    palabras = normal.replace(",", " ").split()
    return " ".join(p for p in palabras if p not in GENERICOS)


def tabla(filas: list[dict[str, str]]) -> list[list[Any]]:
    regiones: list[list[Any]] = []
    for fila in filas:
        pais = _pais(fila)
        if pais is None:
            continue
        try:
            punto = (
                round(float(fila["longitude"]), DECIMALES),
                round(float(fila["latitude"]), DECIMALES),
            )
        except ValueError:
            continue
        nombres = nombres_de(fila)
        if nombres:
            regiones.append([pais, punto[0], punto[1], nombres])
    # Un nombre que en el mismo país es de dos regiones lejanas no se sabe de cuál es: fuera.
    donde: dict[tuple[str, str], list[tuple[float, float]]] = defaultdict(list)
    for pais, lon, lat, nombres in regiones:
        for nombre in nombres:
            donde[(pais, nombre)].append((lon, lat))
    dudosos = {
        clave for clave, puntos in donde.items()
        if any(_km(puntos[0], p) > KM_MISMA for p in puntos[1:])
    }  # fmt: skip
    salida = []
    for pais, lon, lat, nombres in regiones:
        validos = [n for n in nombres if (pais, n) not in dudosos]
        if validos:
            salida.append([pais, lon, lat, validos])
    salida.sort(key=lambda r: (r[0], r[3][0]))
    return salida


def principal(argumentos: list[str] | None = None) -> int:
    lector = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    lector.add_argument("--desde", type=Path, required=True,
                        help=f"el .dbf de Natural Earth, descargado de {FUENTE}")  # fmt: skip
    lector.add_argument("--destino", type=Path, default=DESTINO)
    args = lector.parse_args(argumentos)
    regiones = tabla(leer_dbf(args.desde.read_bytes()))
    documento = {
        "version_esquema": "1.0.0",
        "descripcion": (
            "Regiones de primer nivel de los países del observatorio para el lugar aproximado: "
            "[país, longitud, latitud, nombres normalizados]. Generada con "
            "recogida/regiones_natural_earth.py."
        ),
        "licencia": "Natural Earth (https://www.naturalearthdata.com), dominio público",
        "fuente": FUENTE,
        "genericos": list(GENERICOS),
        "regiones": regiones,
    }
    texto = json.dumps(documento, ensure_ascii=False, separators=(",", ":"))
    # Una región por línea, para que los cambios se lean en un diff.
    texto = texto.replace(',"regiones":[[', ',"regiones":[\n[').replace("]],[", "]],\n[")
    args.destino.write_bytes((texto + "\n").encode("utf-8"))
    print(f"{len(regiones)} regiones en {args.destino}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(principal())
