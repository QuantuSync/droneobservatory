"""Genera las fronteras de los países europeos desde Natural Earth (dominio público).

La validación de la ubicación comprueba que el punto de un incidente cae dentro
del polígono del país del incidente (`proceso/fronteras.py`). Se guardan:

- los polígonos de cada país de la recogida, con las unidades que Natural Earth
  separa y que el observatorio cuenta dentro del país (Åland en Finlandia, las
  Feroe en Dinamarca, Jersey, Guernsey y Man en el Reino Unido, el norte de Chipre
  y las bases británicas en Chipre);
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
    "Dhekelia Sovereign Base Area": "CY",
    "Akrotiri Sovereign Base Area": "CY",
}
SIN_CODIGO = "-99"
# Nombre del país en un idioma: NAME_DE, NAME_ZHT. El vietnamita escribe los nombres con
# sílabas sueltas de dos o tres letras que son palabras corrientes en otros idiomas y
# darían falsos nombres de país: se omite.
IDIOMA = re.compile(r"^NAME_(?!VI$)[A-Z]{2,3}$")
CAMPOS_NOMBRE = ("NAME", "NAME_LONG", "ADMIN", "FORMAL_EN", "NAME_ALT", "NAME_CIAWF")


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
        todos |= nombres(propiedades)
        codigo = UNIDADES_DE.get(_codigo(propiedades), _codigo(propiedades))
        poligonos = _poligonos(feature["geometry"])
        if codigo in propios:
            propios[codigo] += poligonos
            if codigo == _codigo(propiedades):
                de_cada[codigo] |= nombres(propiedades)
            continue
        cerca = [p for p in poligonos if _toca_europa(p)]
        if cerca:
            vecinos.setdefault(codigo, []).extend(cerca)
    faltan = sorted(p for p, poligonos in propios.items() if not poligonos)
    if faltan:
        raise ValueError(f"países sin polígono en Natural Earth: {faltan}")
    return {
        "version_esquema": "1.0.0",
        "descripcion": (
            "Polígonos de los países de la recogida y de sus vecinos (escala 1:10 millones), "
            "[lon, lat] con 4 decimales; el primer anillo de cada polígono es el exterior y "
            "los demás, huecos. nombres_paises: los de todos los países del mundo, "
            "normalizados, para que no pasen por nombres de localidad. nombres_por_pais: los "
            "de cada país de la recogida, para saber si una fuente lo nombra."
        ),
        "licencia": "Natural Earth (https://www.naturalearthdata.com), dominio público",
        "paises": propios,
        "vecinos": dict(sorted(vecinos.items())),
        "nombres_paises": sorted(todos),
        "nombres_por_pais": {p: sorted(n) for p, n in sorted(de_cada.items())},
    }


def principal(argumentos: list[str] | None = None) -> int:
    opciones = argparse.ArgumentParser(description=__doc__)
    opciones.add_argument("--desde", type=Path, help="GeoJSON de Natural Earth ya descargado")
    args = opciones.parse_args(argumentos)
    if args.desde:
        texto = args.desde.read_text(encoding="utf-8")
    else:
        texto = Descargador(agente=AGENTE_EODI).texto(FUENTE, lambda t: t.startswith("{"))
    # Los de la recogida de noticias y los del nomenclátor (Gibraltar tiene su aeropuerto).
    paises = set(cajas_paises()) | set(configuracion()["paises"].values())
    paises |= {sitio.pais for sitio in nomenclator().lugares.values()}
    datos = generar(json.loads(texto), paises)
    texto_json = json.dumps(datos, ensure_ascii=False, separators=(",", ":"))
    DESTINO.write_text(texto_json + "\n", encoding="utf-8", newline="\n")
    print(len(datos["paises"]), "países,", len(datos["vecinos"]), "vecinos")
    return 0


if __name__ == "__main__":
    sys.exit(principal())
