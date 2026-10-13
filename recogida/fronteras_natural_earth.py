"""Genera las fronteras de los países europeos desde Natural Earth (dominio público).

La validación de la ubicación comprueba que el punto de un incidente cae dentro
del polígono del país del incidente (`proceso/fronteras.py`). Se guardan:

- los polígonos de cada país de la recogida, con las unidades que Natural Earth
  separa y que el observatorio cuenta dentro del país (Åland en Finlandia, las
  Feroe en Dinamarca, Jersey, Guernsey y Man en el Reino Unido, el norte de Chipre
  en Chipre) y los territorios fuera del continente que son suelo europeo de su país
  (Gibraltar y las bases británicas de Chipre en el Reino Unido, Groenlandia en
  Dinamarca, la parte francesa de San Martín en Francia), sin Clipperton;
- los polígonos de los demás países cuya caja toca Europa, para saber si un punto
  que no cae en su país está en el mar o en tierra de otro;
- los nombres de todos los países del mundo en los idiomas de Natural Earth, para
  que el nombre de un país no pase por el de una localidad.

Coordenadas redondeadas a 4 decimales (unos 11 m), muy por debajo del error de la
escala 1:10 millones.

Se ejecuta a mano, rara vez; el resultado se revisa y se versiona.

Uso: python -m recogida.fronteras_natural_earth [--desde ne_10m_admin_0_countries.geojson]
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

from proceso.noticias import configuracion, nomenclator, normalizar
from proceso.validacion_ficha import cajas_paises
from recogida.descarga import AGENTE_EODI, Descargador

FUENTE = (
    "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/"
    "ne_10m_admin_0_countries.geojson"
)
DESTINO = Path(__file__).resolve().parent.parent / "configuracion" / "fronteras_europa.json"
DECIMALES = 4
# Caja de Europa con sus vecinos (lon mínima, lat mínima, lon máxima, lat máxima): la de la
# recogida de noticias con margen hasta el norte de África, Oriente Próximo y el Cáucaso.
CAJA_EUROPA = (-32.0, 27.0, 45.0, 72.0)
# Unidades que Natural Earth separa y que el observatorio cuenta dentro de otro país.
UNIDADES_DE = {
    "AX": "FI",
    "FO": "DK",
    "JE": "GB",
    "GG": "GB",
    "IM": "GB",
    "Northern Cyprus": "CY",
    "Cyprus No Mans Area": "CY",
}
# Territorios fuera del continente que Natural Earth separa y que son suelo europeo de su
# país: Gibraltar y las bases soberanas de Akrotiri y Dhekelia (Reino Unido), Groenlandia
# (Dinamarca) y la parte francesa de San Martín. Los departamentos de ultramar franceses,
# Svalbard, Canarias, Ceuta, Melilla, Azores y Madeira ya van dentro de su país. Sus
# nombres cuentan como nombres de su país (nombres_por_pais).
TERRITORIOS = {
    "GI": "GB",
    "Dhekelia Sovereign Base Area": "GB",
    "Akrotiri Sovereign Base Area": "GB",
    "GL": "DK",
    "MF": "FR",
}
# Territorios que nombran un sitio, no una extensión grande: sus nombres no se bloquean
# como nombres de país («Gibraltar» y «Akrotiri» son también la ciudad y el pueblo).
# «Greenland» o «Saint-Martin» siguen sin situar nada, como el nombre de un país.
NOMBRES_QUE_SITUAN = frozenset(
    {"GI", "Dhekelia Sovereign Base Area", "Akrotiri Sovereign Base Area"}
)
# Fronteras con la posición de la Unión Europea: Natural Earth dibuja Crimea (con Sebastopol)
# dentro de Rusia; para el observatorio es Ucrania. Su polígono es el de Rusia que cae entero en
# esta caja [oeste, sur, este, norte] (la península; el resto de Rusia solo la roza en Tamán). El
# norte de Chipre ya va con Chipre (UNIDADES_DE), Transnistria con Moldavia y Abjasia y Osetia
# del Sur con Georgia: Natural Earth no las separa.
SEGUN_LA_UE = [("RU", "UA", (32.3, 44.2, 36.8, 46.3))]
# Partes de un país que quedan fuera del observatorio: Clipperton, en el Pacífico.
FUERA = frozenset({"Clipperton Island"})
SIN_CODIGO = "-99"
# Nombre del país en un idioma: NAME_DE, NAME_ZHT. El vietnamita escribe los nombres con
# sílabas sueltas de dos o tres letras que son palabras corrientes en otros idiomas y
# darían falsos nombres de país: se omite.
IDIOMA = re.compile(r"^NAME_(?!VI$)[A-Z]{2,3}$")
CAMPOS_NOMBRE = ("NAME", "NAME_LONG", "ADMIN", "FORMAL_EN", "NAME_ALT", "NAME_CIAWF")


DESCRIPCION = (
    "Polígonos de los países de la recogida y de sus vecinos (escala 1:10 millones), "
    "[lon, lat] con 4 decimales; el primer anillo de cada polígono es el exterior y "
    "los demás, huecos. Las fronteras siguen la posición de la Unión Europea: Crimea y "
    "Sebastopol son Ucrania, el norte de Chipre es Chipre, Transnistria es Moldavia y Abjasia "
    "y Osetia del Sur son Georgia. nombres_paises: los de todos los países del mundo, "
    "normalizados, para que no pasen por nombres de localidad. nombres_por_pais: los "
    "de cada país de la recogida, para saber si una fuente lo nombra."
)


def _codigo(propiedades: dict[str, Any]) -> str:
    codigo = str(propiedades["ISO_A2_EH"])
    if codigo == SIN_CODIGO:
        return str(propiedades["ADMIN"])
    return codigo


def _poligonos(geometria: dict[str, Any]) -> list[list[list[list[float]]]]:
    partes = geometria["coordinates"]
    lista = partes if geometria["type"] == "MultiPolygon" else [partes]
    return [
        [[[round(x, DECIMALES), round(y, DECIMALES)] for x, y in anillo] for anillo in poligono]
        for poligono in lista
    ]


def _toca_europa(poligono: list[list[list[float]]]) -> bool:
    lon_min, lat_min, lon_max, lat_max = CAJA_EUROPA
    return any(lon_min <= x <= lon_max and lat_min <= y <= lat_max for x, y in poligono[0])


def _en_caja(poligono: list[list[list[float]]], caja: tuple[float, float, float, float]) -> bool:
    oeste, sur, este, norte = caja
    return all(oeste <= x <= este and sur <= y <= norte for x, y in poligono[0])


def segun_la_ue(datos: dict[str, Any]) -> dict[str, Any]:
    """Los polígonos con las fronteras que reconoce la Unión Europea (SEGUN_LA_UE): Crimea, de
    Rusia a Ucrania. Repetirlo no cambia nada."""
    for de, a, caja in SEGUN_LA_UE:
        for grupo in ("paises", "vecinos"):
            if de not in datos[grupo]:
                continue
            mover = [p for p in datos[grupo][de] if _en_caja(p, caja)]
            if not mover:
                continue
            datos[grupo][de] = [p for p in datos[grupo][de] if not _en_caja(p, caja)]
            destino = "paises" if a in datos["paises"] else "vecinos"
            datos[destino].setdefault(a, []).extend(mover)
    return datos


def nombres(propiedades: dict[str, Any]) -> set[str]:
    """Nombres normalizados del país en todos los idiomas de Natural Earth."""
    crudos = [propiedades.get(c) for c in CAMPOS_NOMBRE]
    crudos += [v for k, v in propiedades.items() if IDIOMA.match(k)]
    return {normalizar(n) for n in crudos if isinstance(n, str) and normalizar(n)}


def generar(coleccion: dict[str, Any], paises: set[str]) -> dict[str, Any]:
    propios: dict[str, list[Any]] = {p: [] for p in sorted(paises)}
    vecinos: dict[str, list[Any]] = {}
    todos: set[str] = set()
    de_cada: dict[str, set[str]] = {p: set() for p in propios}
    for feature in coleccion["features"]:
        propiedades = feature["properties"]
        propio = _codigo(propiedades)
        if propio not in NOMBRES_QUE_SITUAN:
            todos |= nombres(propiedades)
        if propiedades.get("ADMIN") in FUERA:
            continue
        codigo = UNIDADES_DE.get(propio) or TERRITORIOS.get(propio) or propio
        poligonos = _poligonos(feature["geometry"])
        if codigo in propios:
            propios[codigo] += poligonos
            if codigo == propio or propio in TERRITORIOS:
                de_cada[codigo] |= nombres(propiedades)
            continue
        cerca = [p for p in poligonos if _toca_europa(p)]
        if cerca:
            vecinos.setdefault(codigo, []).extend(cerca)
    faltan = sorted(p for p, poligonos in propios.items() if not poligonos)
    if faltan:
        raise ValueError(f"países sin polígono en Natural Earth: {faltan}")
    return segun_la_ue(
        {
            "version_esquema": "1.0.0",
            "descripcion": DESCRIPCION,
            "licencia": "Natural Earth (https://www.naturalearthdata.com), dominio público",
            "paises": propios,
            "vecinos": dict(sorted(vecinos.items())),
            "nombres_paises": sorted(todos),
            "nombres_por_pais": {p: sorted(n) for p, n in sorted(de_cada.items())},
        }
    )


def principal(argumentos: list[str] | None = None) -> int:
    opciones = argparse.ArgumentParser(description=__doc__)
    opciones.add_argument("--desde", type=Path, help="GeoJSON de Natural Earth ya descargado")
    args = opciones.parse_args(argumentos)
    if args.desde:
        texto = args.desde.read_text(encoding="utf-8")
    else:
        texto = Descargador(agente=AGENTE_EODI).texto(FUENTE, lambda t: t.startswith("{"))
    # Los de la recogida de noticias y los del nomenclátor.
    paises = set(cajas_paises()) | set(configuracion()["paises"].values())
    paises |= {sitio.pais for sitio in nomenclator().lugares.values()}
    datos = generar(json.loads(texto), paises)
    texto_json = json.dumps(datos, ensure_ascii=False, separators=(",", ":"))
    DESTINO.write_text(texto_json + "\n", encoding="utf-8", newline="\n")
    print(len(datos["paises"]), "países,", len(datos["vecinos"]), "vecinos")
    return 0


if __name__ == "__main__":
    sys.exit(principal())
