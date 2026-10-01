"""Genera el nomenclátor de la capa de guerra: localidades e instalaciones de Ucrania y de la
Rusia europea, con sus nombres en ucraniano, ruso y transliteración latina.

Fuentes:

- Ucrania: el codificador oficial de unidades administrativas y territoriales (КАТОТТГ,
  Ministerio de Desarrollo de Comunidades y Territorios, mindev.gov.ua), que da cada
  localidad con su nombre oficial en ucraniano, su óblast, su distrito (район) y su
  comunidad (громада), pero no sus coordenadas. Las coordenadas salen de OpenStreetMap
  (etiqueta `katotth` del nodo de la localidad, o mismo nombre en el mismo óblast) y, si
  no está, de GeoNames (mismo nombre en el mismo óblast). Un nombre que llevan varias
  localidades del óblast se resuelve por cercanía al centro de su comunidad; si no hay
  forma de saber cuál es cuál, la localidad queda sin coordenadas y no entra.
- Rusia europea: GeoNames, con los nombres en cirílico de sus nombres alternativos y la
  región (admin1) y el distrito (admin2) de cada localidad.
- Instalaciones de los dos países: OpenStreetMap (refinerías, depósitos de combustible,
  centrales, subestaciones de 220 kV o más, puertos, aeródromos, estaciones y playas de
  vías, plantas industriales y bases), con nombre, categoría, coordenadas y región.

Crimea, Sebastopol y las partes ocupadas de Donetsk, Luhansk, Zaporiyia y Jersón llevan
siempre el código ISO 3166-2 de Ucrania: así vienen en el codificador ucraniano y así se
les asigna región a las instalaciones (por el contorno de los óblasts).

Cada punto se comprueba contra el contorno de su óblast (web/public/mapa/
ucrania-regiones.geojson, con un margen de 10 km por lo simplificado del contorno); el que
cae fuera no entra. Los nombres que coinciden con un país, una región o una institución no
se guardan como nombre de localidad.

Datos: КАТОТТГ (datos abiertos del Gobierno de Ucrania); GeoNames (CC BY 4.0);
© colaboradores de OpenStreetMap (ODbL).

Se ejecuta a mano, rara vez; el resultado se revisa y se versiona comprimido.

Uso: python -m recogida.nomenclator_guerra --katotth kodifikator.xlsx --geonames-ua UA.zip
    --geonames-ru RU.zip --admin2 admin2Codes.txt --osm-lugares lugares_ua.json
    --osm-instalaciones inst_ua.json inst_ru_1.json ...
"""

import argparse
import gzip
import io
import json
import math
import re
import sys
import xml.etree.ElementTree as ET
import zipfile
from collections import defaultdict
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from proceso.lugares_guerra import (
    CATEGORIAS_INSTALACION,
    PROHIBIDOS,
    Contornos,
    normalizar,
    radio_localidad,
    transliterar,
)

RAIZ = Path(__file__).resolve().parent.parent
DESTINO = RAIZ / "configuracion" / "nomenclator_guerra.json.gz"
REGIONES_UA = RAIZ / "configuracion" / "regiones_ucrania.json"
VERSION = 1
DECIMALES = 5
# Distancia máxima de una localidad al centro de su comunidad: las comunidades más grandes
# miden unos 50 km de lado.
MAX_KM_CENTRO_COMUNIDAD = 45.0
# Columnas de GeoNames.
G_ID, G_NOMBRE, G_ASCII, G_ALT, G_LAT, G_LON, G_CLASE, G_CODIGO, G_PAIS = 0, 1, 2, 3, 4, 5, 6, 7, 8
G_ADMIN1, G_ADMIN2, G_POBLACION = 10, 11, 14
# Históricos, abandonados, destruidos, secciones de otra localidad.
CODIGOS_EXCLUIDOS = frozenset({"PPLH", "PPLQ", "PPLW", "PPLX", "PPLCH"})
# Categorías del codificador: ciudad, ciudad con estatus especial, asentamiento, aldea.
CATEGORIA_KATOTTH = {"M": "ciudad", "K": "ciudad", "X": "asentamiento", "C": "aldea"}

ADMIN1_UA = {
    "01": "UA-71", "02": "UA-74", "03": "UA-77", "04": "UA-12", "05": "UA-14", "06": "UA-26",
    "07": "UA-63", "08": "UA-65", "09": "UA-68", "10": "UA-35", "11": "UA-43", "12": "UA-30",
    "13": "UA-32", "14": "UA-09", "15": "UA-46", "16": "UA-48", "17": "UA-51", "18": "UA-53",
    "19": "UA-56", "20": "UA-40", "21": "UA-59", "22": "UA-61", "23": "UA-05", "24": "UA-07",
    "25": "UA-21", "26": "UA-23", "27": "UA-18",
}  # fmt: skip
# Rusia europea y los Urales (los ataques con drones han llegado a Tiumén y Ekaterimburgo).
ADMIN1_RU = {
    "01": "RU-AD", "06": "RU-ARK", "07": "RU-AST", "08": "RU-BA", "09": "RU-BEL", "10": "RU-BRY",
    "12": "RU-CE", "13": "RU-CHE", "16": "RU-CU", "17": "RU-DA", "19": "RU-IN", "21": "RU-IVA",
    "22": "RU-KB", "23": "RU-KGD", "24": "RU-KL", "25": "RU-KLU", "27": "RU-KC", "28": "RU-KR",
    "33": "RU-KIR", "34": "RU-KO", "37": "RU-KOS", "38": "RU-KDA", "40": "RU-KGN", "41": "RU-KRS",
    "42": "RU-LEN", "43": "RU-LIP", "45": "RU-ME", "46": "RU-MO", "47": "RU-MOS", "48": "RU-MOW",
    "49": "RU-MUR", "50": "RU-NEN", "51": "RU-NIZ", "52": "RU-NGR", "55": "RU-ORE", "56": "RU-ORL",
    "57": "RU-PNZ", "60": "RU-PSK", "61": "RU-ROS", "62": "RU-RYA", "65": "RU-SAM", "66": "RU-SPE",
    "67": "RU-SAR", "68": "RU-SE", "69": "RU-SMO", "70": "RU-STA", "71": "RU-SVE", "72": "RU-TAM",
    "73": "RU-TA", "76": "RU-TUL", "77": "RU-TVE", "78": "RU-TYU", "80": "RU-UD", "81": "RU-ULY",
    "83": "RU-VLA", "84": "RU-VGG", "85": "RU-VLG", "86": "RU-VOR", "88": "RU-YAR", "90": "RU-PER",
}  # fmt: skip

_UCRANIANAS = re.compile(r"[іїєґІЇЄҐ]")
_RUSAS = re.compile(r"[ыэъёЫЭЪЁ]")
_CIRILICO = re.compile(r"^[Ѐ-ӿ'’ʼ\- .()0-9]+$")
_LATINO = re.compile(r"^[A-Za-z'’\- .]+$")


# --- Lectura de ficheros ---------------------------------------------------------------


def leer_xlsx(ruta: Path) -> list[list[str | None]]:
    """Filas de la primera hoja de un .xlsx, con la biblioteca estándar."""
    ns = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    with zipfile.ZipFile(ruta) as libro:
        compartidas: list[str] = []
        if "xl/sharedStrings.xml" in libro.namelist():
            raiz = ET.fromstring(libro.read("xl/sharedStrings.xml"))
            for si in raiz.findall("m:si", ns):
                compartidas.append("".join(t.text or "" for t in si.iter(f"{{{ns['m']}}}t")))
        hoja = ET.fromstring(libro.read("xl/worksheets/sheet1.xml"))
    filas: list[list[str | None]] = []
    for fila in hoja.iter(f"{{{ns['m']}}}row"):
        celdas: dict[int, str | None] = {}
        for celda in fila.findall("m:c", ns):
            referencia = celda.get("r", "")
            columna = 0
            for letra in re.match(r"[A-Z]+", referencia).group(0):  # type: ignore[union-attr]
                columna = columna * 26 + ord(letra) - 64
            valor = celda.find("m:v", ns)
            texto = valor.text if valor is not None else None
            if texto is not None and celda.get("t") == "s":
                texto = compartidas[int(texto)]
            elif celda.get("t") == "inlineStr":
                texto = "".join(t.text or "" for t in celda.iter(f"{{{ns['m']}}}t"))
            celdas[columna - 1] = texto
        if celdas:
            filas.append([celdas.get(i) for i in range(max(celdas) + 1)])
    return filas


def lineas_geonames(ruta: Path) -> Iterator[list[str]]:
    with zipfile.ZipFile(ruta) as comprimido:
        nombre = ruta.stem + ".txt"
        with comprimido.open(nombre) as crudo:
            for linea in io.TextIOWrapper(crudo, encoding="utf-8"):
                yield linea.rstrip("\n").split("\t")


# --- Utilidades ------------------------------------------------------------------------


def distancia_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    f1, f2 = math.radians(lat1), math.radians(lat2)
    df, dl = f2 - f1, math.radians(lon2 - lon1)
    a = math.sin(df / 2) ** 2 + math.cos(f1) * math.cos(f2) * math.sin(dl / 2) ** 2
    return 2 * 6371.0088 * math.asin(math.sqrt(a))


def idioma_del_nombre(nombre: str) -> str | None:
    if _LATINO.match(nombre):
        return "la"
    if not _CIRILICO.match(nombre):
        return None
    if _UCRANIANAS.search(nombre):
        return "uk"
    if _RUSAS.search(nombre):
        return "ru"
    return "cy"


def limpio(nombre: str) -> str:
    return " ".join(nombre.replace("’", "'").replace("ʼ", "'").split())


def nombres_por_idioma(lista: list[str]) -> dict[str, list[str]]:
    """Agrupa los nombres por idioma: uk, ru, cy (cirílico sin letras propias de ninguno de
    los dos, que se declina en los dos) y la (latino). Fuera los prohibidos y los cortos."""
    grupos: dict[str, list[str]] = defaultdict(list)
    for crudo in lista:
        nombre = limpio(crudo)
        if len(nombre) < 3 or normalizar(nombre) in PROHIBIDOS:
            continue
        idioma = idioma_del_nombre(nombre)
        if idioma is not None and nombre not in grupos[idioma]:
            grupos[idioma].append(nombre)
    return dict(grupos)


# --- Ucrania ----------------------------------------------------------------------------


def codigos_oblast(filas: list[list[str | None]]) -> dict[str, str]:
    """Código del primer nivel del codificador → ISO 3166-2, por el nombre oficial."""
    regiones = json.loads(REGIONES_UA.read_text(encoding="utf-8"))["regiones"]
    por_nombre = {normalizar(v["nombre"]): iso for iso, v in regiones.items()}
    # El codificador da «Автономна Республіка Крим», «Вінницька», «Київ»…; la configuración,
    # «Вінницька область».
    resultado: dict[str, str] = {}
    for fila in filas:
        if len(fila) < 7 or fila[5] not in {"O", "K"} or not fila[0] or fila[1]:
            continue
        nombre = normalizar(str(fila[6]))
        iso = por_nombre.get(nombre) or por_nombre.get(f"{nombre} область")
        if iso is None:
            raise SystemExit(f"óblast sin código ISO: {fila[6]}")
        resultado[str(fila[0])] = iso
    return resultado


# Distritos de Kyiv y de Sebastopol, que el codificador no desglosa (son ciudades con estatus
# especial, sin niveles inferiores).
DISTRITOS_ESPECIALES = {
    "UA80000000000093317": ("Голосіївський", "Дарницький", "Деснянський", "Дніпровський",
                            "Оболонський", "Печерський", "Подільський", "Святошинський",
                            "Солом'янський", "Шевченківський"),
    "UA85000000000065278": ("Балаклавський", "Гагарінський", "Ленінський", "Нахімовський"),
}  # fmt: skip


def distritos_urbanos(ruta: Path) -> list[dict[str, str]]:
    """Distritos de las ciudades (categoría B del codificador): «Київський район» en un
    mensaje de la administración de Járkov es un barrio de Járkov, no un distrito rural."""
    filas = leer_xlsx(ruta)
    oblasts = codigos_oblast(filas)
    resultado = [
        {"nombre": limpio(str(f[6])), "ciudad": f"katotth:{f[3]}", "region": oblasts[str(f[0])]}
        for f in filas
        if len(f) > 6 and f[5] == "B" and f[3]
    ]
    for ciudad, nombres in DISTRITOS_ESPECIALES.items():
        region = oblasts[ciudad]
        resultado += [
            {"nombre": n, "ciudad": f"katotth:{ciudad}", "region": region} for n in nombres
        ]
    return resultado


def katotth(ruta: Path) -> list[dict[str, Any]]:
    filas = leer_xlsx(ruta)
    oblasts = codigos_oblast(filas)
    nombres: dict[str, str] = {}
    localidades = []
    for fila in filas:
        if len(fila) < 7 or not fila[0] or not str(fila[0]).startswith("UA"):
            continue
        niveles = [str(c) if c else None for c in fila[:5]]
        codigo = next(c for c in reversed(niveles) if c)
        nombres[codigo] = str(fila[6])
        categoria = CATEGORIA_KATOTTH.get(str(fila[5]))
        if categoria is None:
            continue
        localidades.append({
            "katotth": codigo,
            "nombre": limpio(str(fila[6])),
            "categoria": categoria,
            "region": oblasts[str(fila[0])],
            "raion": nombres.get(niveles[1] or "") if fila[5] != "K" else None,
            "hromada": nombres.get(niveles[2] or "") if fila[5] != "K" else None,
        })  # fmt: skip
    return localidades


def geonames_ua(ruta: Path) -> dict[tuple[str, str], list[dict[str, Any]]]:
    """(región, nombre normalizado) → lugares poblados de GeoNames con ese nombre."""
    indice: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for fila in lineas_geonames(ruta):
        if fila[G_CLASE] != "P" or fila[G_CODIGO] in CODIGOS_EXCLUIDOS:
            continue
        region = ADMIN1_UA.get(fila[G_ADMIN1])
        if region is None:
            continue
        lugar: dict[str, Any] = {
            "geonames": int(fila[G_ID]),
            "lat": float(fila[G_LAT]),
            "lon": float(fila[G_LON]),
            "poblacion": int(fila[G_POBLACION] or 0),
            "nombres": [fila[G_NOMBRE], fila[G_ASCII], *fila[G_ALT].split(",")],
        }
        for nombre in {normalizar(n) for n in lugar["nombres"] if n}:
            indice[(region, nombre)].append(lugar)
    return indice


def osm_lugares(ruta: Path | None) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    """Nodos de localidades de OpenStreetMap: por código del codificador y todos."""
    if ruta is None:
        return {}, []
    elementos = json.loads(ruta.read_text(encoding="utf-8"))["elements"]
    por_codigo: dict[str, dict[str, Any]] = {}
    todos = []
    for e in elementos:
        etiquetas = e.get("tags", {})
        lugar = {
            "osm": f"node/{e['id']}",
            "lat": e["lat"],
            "lon": e["lon"],
            "poblacion": int(re.sub(r"\D", "", etiquetas.get("population", "")) or 0),
            "nombres": [
                v for k, v in etiquetas.items()
                if k in {"name", "name:uk", "name:ru", "name:en", "old_name", "old_name:uk",
                         "old_name:ru", "alt_name", "official_name"} for v in [v]
            ],
            "katotth": etiquetas.get("katotth"),
        }  # fmt: skip
        todos.append(lugar)
        if lugar["katotth"]:
            por_codigo[lugar["katotth"]] = lugar
    return por_codigo, todos


def localidades_ucrania(
    lista: list[dict[str, Any]],
    gn: dict[tuple[str, str], list[dict[str, Any]]],
    osm_codigo: dict[str, dict[str, Any]],
    osm_todos: list[dict[str, Any]],
    contornos: Contornos,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    cuentas: dict[str, int] = defaultdict(int)
    osm_por_nombre: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for lugar in osm_todos:
        region = contornos.region_de(lugar["lat"], lugar["lon"], "UA")
        if region is None:
            continue
        for nombre in {normalizar(n) for n in lugar["nombres"]}:
            osm_por_nombre[(region, nombre)].append(lugar)

    def candidatos(loc: dict[str, Any]) -> list[dict[str, Any]]:
        clave = (loc["region"], normalizar(loc["nombre"]))
        vistos: dict[tuple[float, float], dict[str, Any]] = {}
        for lugar in [*osm_por_nombre.get(clave, []), *gn.get(clave, [])]:
            # Un mismo lugar en OSM y en GeoNames: a menos de 2 km es el mismo.
            if not any(distancia_km(lugar["lat"], lugar["lon"], a, b) < 2 for a, b in vistos):
                vistos[(lugar["lat"], lugar["lon"])] = lugar
        return list(vistos.values())

    situadas: dict[str, dict[str, Any]] = {}
    pendientes = []
    for loc in lista:
        directo = osm_codigo.get(loc["katotth"])
        if directo is not None:
            situadas[loc["katotth"]] = {**loc, **_punto(directo), "origen_punto": "osm_katotth"}
            cuentas["osm_katotth"] += 1
            continue
        lista_c = candidatos(loc)
        if len(lista_c) == 1:
            situadas[loc["katotth"]] = {**loc, **_punto(lista_c[0]), "origen_punto": "nombre"}
            cuentas["nombre_unico"] += 1
        else:
            pendientes.append((loc, lista_c))
    # Centro de cada comunidad: su localidad homónima ya situada (la comunidad se llama
    # como su centro: «Чугуївська» → Чугуїв).
    centros: dict[tuple[str, str], tuple[float, float]] = {}
    for loc in situadas.values():
        if loc.get("hromada") and _raiz(loc["hromada"]) == _raiz(loc["nombre"]):
            centros[(loc["region"], loc["hromada"])] = (loc["lat"], loc["lon"])
    for loc, lista_c in pendientes:
        centro = centros.get((loc["region"], loc.get("hromada") or ""))
        if not lista_c:
            cuentas["sin_punto"] += 1
            continue
        if centro is None:
            cuentas["ambigua_sin_centro"] += 1
            continue
        cercanos = sorted(lista_c, key=lambda c: distancia_km(*centro, c["lat"], c["lon"]))
        d0 = distancia_km(*centro, cercanos[0]["lat"], cercanos[0]["lon"])
        d1 = (
            distancia_km(*centro, cercanos[1]["lat"], cercanos[1]["lon"])
            if len(cercanos) > 1 else math.inf
        )  # fmt: skip
        # El más cercano, si está dentro de la comunidad y el siguiente claramente fuera.
        if d0 <= MAX_KM_CENTRO_COMUNIDAD and d1 > 2 * d0 + 5:
            situadas[loc["katotth"]] = {**loc, **_punto(cercanos[0]), "origen_punto": "comunidad"}
            cuentas["por_comunidad"] += 1
        else:
            cuentas["ambigua"] += 1
    resultado = []
    for loc in situadas.values():
        if not contornos.dentro(loc["region"], loc["lat"], loc["lon"]):
            cuentas["fuera_del_oblast"] += 1
            continue
        resultado.append(loc)
    return resultado, dict(cuentas)


def _raiz(nombre: str) -> str:
    """Raíz para comparar una comunidad con su centro: las seis primeras letras."""
    return normalizar(nombre).replace(" ", "")[:6]


def _punto(lugar: dict[str, Any]) -> dict[str, Any]:
    datos = {
        "lat": round(lugar["lat"], DECIMALES),
        "lon": round(lugar["lon"], DECIMALES),
        "poblacion": lugar.get("poblacion", 0),
        "alternativos": lugar["nombres"],
    }
    if "geonames" in lugar:
        datos["geonames"] = lugar["geonames"]
    if "osm" in lugar:
        datos["osm"] = lugar["osm"]
    return datos


# --- Rusia ----------------------------------------------------------------------------


def distritos_ru(ruta: Path) -> dict[str, str]:
    """Código admin2 de GeoNames («RU.09.123») → nombre del distrito, en latino."""
    resultado = {}
    for linea in ruta.read_text(encoding="utf-8").splitlines():
        partes = linea.split("\t")
        if partes[0].startswith("RU."):
            resultado[partes[0]] = partes[2]
    return resultado


def localidades_rusia(ruta: Path, distritos: dict[str, str]) -> list[dict[str, Any]]:
    resultado = []
    for fila in lineas_geonames(ruta):
        if fila[G_CLASE] != "P" or fila[G_CODIGO] in CODIGOS_EXCLUIDOS:
            continue
        region = ADMIN1_RU.get(fila[G_ADMIN1])
        if region is None or float(fila[G_LON]) > 70:
            continue
        nombres = [fila[G_NOMBRE], fila[G_ASCII], *fila[G_ALT].split(",")]
        cirilicos = [n for n in nombres if idioma_del_nombre(limpio(n)) in {"ru", "cy", "uk"}]
        if not cirilicos:
            continue
        # El nombre principal es el cirílico que mejor se transcribe al nombre latino de
        # GeoNames («Belgorod» → «Белгород», no la variante bielorrusa «Белгарад»); a igualdad, el
        # acabado en ь («Пермь» y no «Перм», que se transcriben igual).
        cirilicos.sort(
            key=lambda n: (
                _parecido(n, fila[G_ASCII]),
                idioma_del_nombre(n) != "ru",
                not n.endswith("ь"),
            )
        )
        poblacion = int(fila[G_POBLACION] or 0)
        resultado.append({
            "geonames": int(fila[G_ID]),
            "nombre": limpio(cirilicos[0]),
            "categoria": "ciudad" if fila[G_CODIGO].startswith("PPLA") or poblacion >= 10_000
            else "aldea",
            "region": region,
            "raion": distritos.get(f"RU.{fila[G_ADMIN1]}.{fila[G_ADMIN2]}"),
            "lat": round(float(fila[G_LAT]), DECIMALES),
            "lon": round(float(fila[G_LON]), DECIMALES),
            "poblacion": poblacion,
            "alternativos": nombres,
            "origen_punto": "geonames",
        })  # fmt: skip
    return resultado


def _parecido(cirilico: str, latino: str) -> int:
    """Distancia de edición entre la transcripción del nombre cirílico y el latino."""
    a, b = transliterar(normalizar(cirilico)), normalizar(latino)
    anterior = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        actual = [i]
        for j, y in enumerate(b, 1):
            actual.append(min(anterior[j] + 1, actual[j - 1] + 1, anterior[j - 1] + (x != y)))
        anterior = actual
    return anterior[-1]


# --- Instalaciones ------------------------------------------------------------------------


_REFINERIA = re.compile(r"НПЗ|нефтеперераб|нафтоперероб|refinery", re.IGNORECASE)
_DEPOSITO = re.compile(r"нефтебаз|нафтобаз|ЛПДС|НПС|ГСМ|ПММ|oil depot|fuel depot", re.IGNORECASE)
_DEPOSITO_ETIQUETA = frozenset({"oil", "fuel", "oil_storage", "fuel_depot", "tank_farm",
                                "petroleum_terminal"})  # fmt: skip


def categoria_instalacion(etiquetas: dict[str, str]) -> str | None:
    nombre = " ".join(v for k, v in etiquetas.items() if k.startswith(("name", "official_name")))
    industrial = etiquetas.get("industrial", "")
    if industrial == "refinery" or _REFINERIA.search(nombre):
        return "refineria"
    if industrial in _DEPOSITO_ETIQUETA or _DEPOSITO.search(nombre):
        return "deposito_combustible"
    if etiquetas.get("power") == "plant":
        return "central"
    if etiquetas.get("power") == "substation":
        return "subestacion"
    if etiquetas.get("aeroway") == "aerodrome" or etiquetas.get("military") == "airfield":
        return "aerodromo"
    if (
        etiquetas.get("landuse") == "port" or industrial == "port"
        or etiquetas.get("harbour") == "yes"
    ):  # fmt: skip
        return "puerto"
    if etiquetas.get("military") in {"base", "naval_base"}:
        return "militar"
    if etiquetas.get("railway") in {"station", "yard"}:
        return "ferrocarril"
    if (
        etiquetas.get("man_made") == "works"
        or industrial
        or etiquetas.get("landuse") == "industrial"
    ):
        return "industrial"
    return None


def instalaciones(
    rutas: list[Path], contornos: Contornos, rusia: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Instalaciones de OSM con región: en Ucrania (con Crimea y lo ocupado), por el contorno
    del óblast; en Rusia, la región de la localidad de GeoNames más cercana (a 30 km o menos)."""
    rejilla: dict[tuple[int, int], list[dict[str, Any]]] = defaultdict(list)
    for loc in rusia:
        rejilla[(int(loc["lat"] * 4), int(loc["lon"] * 4))].append(loc)

    def region_rusa(lat: float, lon: float) -> str | None:
        cerca = [
            loc for di in (-1, 0, 1) for dj in (-1, 0, 1)
            for loc in rejilla.get((int(lat * 4) + di, int(lon * 4) + dj), [])
        ]  # fmt: skip
        if not cerca:
            return None
        mejor = min(cerca, key=lambda c: distancia_km(lat, lon, c["lat"], c["lon"]))
        return mejor["region"] if distancia_km(lat, lon, mejor["lat"], mejor["lon"]) <= 30 else None

    vistos: set[str] = set()
    resultado = []
    for ruta in rutas:
        for e in json.loads(ruta.read_text(encoding="utf-8"))["elements"]:
            id_ = f"{e['type']}/{e['id']}"
            if id_ in vistos:
                continue
            vistos.add(id_)
            etiquetas = e.get("tags", {})
            centro = e.get("center", e)
            if "lat" not in centro:
                continue
            categoria = categoria_instalacion(etiquetas)
            if categoria is None:
                continue
            lat, lon = round(centro["lat"], DECIMALES), round(centro["lon"], DECIMALES)
            region = contornos.region_de(lat, lon, "UA")
            pais = "UA"
            if region is None:
                region, pais = region_rusa(lat, lon), "RU"
            if region is None:
                continue
            nombres = [
                v for k, v in sorted(etiquetas.items())
                if k in {"name", "name:uk", "name:ru", "name:en", "official_name",
                         "official_name:uk", "official_name:ru", "alt_name", "short_name",
                         "old_name"}
            ]  # fmt: skip
            grupos = nombres_por_idioma(nombres)
            if not grupos:
                continue
            entrada = {
                "osm": id_, "categoria": categoria, "pais": pais, "region": region,
                "lat": lat, "lon": lon, "radio_km": CATEGORIAS_INSTALACION[categoria],
                "nombres": grupos,
            }  # fmt: skip
            if re.fullmatch(r"[A-Z]{4}", etiquetas.get("icao", "")):
                entrada["oaci"] = etiquetas["icao"]
            resultado.append(entrada)
    return sorted(resultado, key=lambda i: i["osm"])


# --- Salida -----------------------------------------------------------------------------


def entrada_localidad(loc: dict[str, Any], pais: str) -> dict[str, Any]:
    nombres = nombres_por_idioma([loc["nombre"], *loc.get("alternativos", [])])
    entrada: dict[str, Any] = {
        "id": f"katotth:{loc['katotth']}" if "katotth" in loc else f"geonames:{loc['geonames']}",
        "nombre": loc["nombre"],
        "pais": pais,
        "region": loc["region"],
        "categoria": loc["categoria"],
        "lat": loc["lat"],
        "lon": loc["lon"],
        "radio_km": radio_localidad(loc["categoria"], loc.get("poblacion", 0)),
        "nombres": nombres,
        "origen_punto": loc["origen_punto"],
    }
    for clave in ("raion", "hromada", "poblacion"):
        if loc.get(clave):
            entrada[clave] = loc[clave]
    return entrada


def principal(argumentos: list[str] | None = None) -> int:
    opciones = argparse.ArgumentParser(description=__doc__)
    opciones.add_argument("--katotth", type=Path, required=True)
    opciones.add_argument("--geonames-ua", type=Path, required=True)
    opciones.add_argument("--geonames-ru", type=Path, required=True)
    opciones.add_argument("--admin2", type=Path, required=True)
    opciones.add_argument("--osm-lugares", type=Path)
    opciones.add_argument("--osm-instalaciones", type=Path, nargs="*", default=[])
    opciones.add_argument("--salida", type=Path, default=DESTINO)
    args = opciones.parse_args(argumentos)
    contornos = Contornos.cargar()
    lista = katotth(args.katotth)
    osm_codigo, osm_todos = osm_lugares(args.osm_lugares)
    ucrania, cuentas = localidades_ucrania(
        lista, geonames_ua(args.geonames_ua), osm_codigo, osm_todos, contornos
    )
    rusia = localidades_rusia(args.geonames_ru, distritos_ru(args.admin2))
    inst = instalaciones(args.osm_instalaciones, contornos, rusia)
    datos = {
        "version": VERSION,
        "fuentes": {
            "katotth": args.katotth.name,
            "licencias": "КАТОТТГ: datos abiertos del Gobierno de Ucrania (mindev.gov.ua); "
            "GeoNames, CC BY 4.0; © colaboradores de OpenStreetMap, ODbL.",
        },
        "localidades": [entrada_localidad(loc, "UA") for loc in ucrania]
        + [entrada_localidad(loc, "RU") for loc in rusia],
        "instalaciones": inst,
        "distritos_urbanos": distritos_urbanos(args.katotth),
    }
    args.salida.write_bytes(
        gzip.compress(
            json.dumps(datos, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(),
            9,
            mtime=0,
        )
    )
    resumen = {
        "codificador": len(lista),
        "ucrania_situadas": len(ucrania),
        **{f"ucrania_{k}": v for k, v in sorted(cuentas.items())},
        "rusia": len(rusia),
        "instalaciones": len(inst),
        "instalaciones_por_categoria": dict(
            sorted(
                {c: sum(i["categoria"] == c for i in inst) for c in CATEGORIAS_INSTALACION}.items()
            )
        ),
    }
    print(json.dumps(resumen, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(principal())
