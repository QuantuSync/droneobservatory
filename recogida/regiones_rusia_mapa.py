"""Genera el contorno de las regiones rusas para la capa de guerra de la web
(web/public/mapa/rusia-regiones.geojson) desde Natural Earth (dominio público).

Solo las regiones que nombran los partes del Ministerio de Defensa ruso
(configuracion/regiones_rusia.json) con código ruso: Crimea, Sebastopol y lo ocupado de
Ucrania llevan su código ucraniano y su contorno está en ucrania-regiones.geojson. Contornos
simplificados (Douglas-Peucker, 0,02°, unos 2 km) y coordenadas con dos decimales, como el de
Ucrania: para colorear regiones por intensidad basta y el fichero queda pequeño.

Se ejecuta a mano, rara vez; el resultado se revisa y se versiona.

Uso: python -m recogida.regiones_rusia_mapa --desde ne_10m_admin_1_states_provinces.geojson
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any

RAIZ = Path(__file__).resolve().parent.parent
DESTINO = RAIZ / "web" / "public" / "mapa" / "rusia-regiones.geojson"
NOMBRES = RAIZ / "web" / "src" / "i18n" / "regionesRusia.ts"
# Natural Earth da el mismo nombre a Moscú ciudad y a su óblast.
CORRECCIONES = {
    "RU-MOW": {"es": "Moscú (ciudad)", "en": "Moscow (city)"},
    "RU-MOS": {"es": "Moscú (región)", "en": "Moscow Oblast"},
    "RU-SPE": {"es": "San Petersburgo", "en": "Saint Petersburg"},
    "RU-LEN": {"es": "Leningrado (región)", "en": "Leningrad Oblast"},
}
VOCABULARIO = RAIZ / "configuracion" / "regiones_rusia.json"
TOLERANCIA = 0.02
DECIMALES = 2
MIN_PUNTOS = 4

Punto = tuple[float, float]


def _distancia(p: Punto, a: Punto, b: Punto) -> float:
    (x, y), (x1, y1), (x2, y2) = p, a, b
    dx, dy = x2 - x1, y2 - y1
    if dx == dy == 0:
        return float(((x - x1) ** 2 + (y - y1) ** 2) ** 0.5)
    t = max(0.0, min(1.0, ((x - x1) * dx + (y - y1) * dy) / (dx * dx + dy * dy)))
    return float(((x - x1 - t * dx) ** 2 + (y - y1 - t * dy) ** 2) ** 0.5)


def simplificar(puntos: list[Punto], tolerancia: float = TOLERANCIA) -> list[Punto]:
    """Douglas-Peucker sin recursión."""
    if len(puntos) < 3:
        return puntos
    conservar = [False] * len(puntos)
    conservar[0] = conservar[-1] = True
    pila = [(0, len(puntos) - 1)]
    while pila:
        inicio, fin = pila.pop()
        mayor, indice = 0.0, -1
        for i in range(inicio + 1, fin):
            d = _distancia(puntos[i], puntos[inicio], puntos[fin])
            if d > mayor:
                mayor, indice = d, i
        if mayor > tolerancia and indice > 0:
            conservar[indice] = True
            pila += [(inicio, indice), (indice, fin)]
    return [p for p, c in zip(puntos, conservar, strict=True) if c]


def anillo(crudo: list[list[float]]) -> list[list[float]] | None:
    puntos = simplificar([(float(x), float(y)) for x, y, *_ in crudo])
    redondeados: list[list[float]] = []
    for x, y in puntos:
        punto = [round(x, DECIMALES), round(y, DECIMALES)]
        if not redondeados or redondeados[-1] != punto:
            redondeados.append(punto)
    if len(redondeados) < MIN_PUNTOS:
        return None
    if redondeados[0] != redondeados[-1]:
        redondeados.append(redondeados[0])
    return redondeados


def regiones(datos: dict[str, Any], codigos: set[str]) -> dict[str, Any]:
    rasgos = []
    for rasgo in datos["features"]:
        iso = rasgo["properties"].get("iso_3166_2") or ""
        if iso not in codigos:
            continue
        geometria = rasgo["geometry"]
        poligonos = (
            [geometria["coordinates"]] if geometria["type"] == "Polygon"
            else geometria["coordinates"]
        )  # fmt: skip
        salida = []
        for poligono in poligonos:
            exterior = anillo(poligono[0])
            if exterior is None:
                continue
            huecos = [h for h in (anillo(x) for x in poligono[1:]) if h is not None]
            salida.append([exterior, *huecos])
        if salida:
            rasgos.append({
                "type": "Feature",
                "geometry": {"type": "MultiPolygon", "coordinates": salida},
                "properties": {"iso": iso},
            })  # fmt: skip
    return {
        "type": "FeatureCollection",
        "features": sorted(rasgos, key=lambda r: r["properties"]["iso"]),
    }


def nombres(datos: dict[str, Any], codigos: set[str]) -> dict[str, dict[str, str]]:
    resultado: dict[str, dict[str, str]] = {}
    for rasgo in datos["features"]:
        p = rasgo["properties"]
        iso = p.get("iso_3166_2") or ""
        if iso in codigos:
            resultado[iso] = CORRECCIONES.get(iso) or {
                "es": p.get("name_es") or p["name"], "en": p.get("name_en") or p["name"],
            }  # fmt: skip
    return dict(sorted(resultado.items()))


def modulo_nombres(tabla: dict[str, dict[str, str]]) -> str:
    lineas = [
        "// Nombres de las regiones rusas de la capa de guerra (Natural Earth, dominio público).",
        "// Generado por recogida/regiones_rusia_mapa.py: no se edita a mano.",
        "",
    ]
    for idioma in ("es", "en"):
        constante = f"REGIONES_RUSIA_{idioma.upper()}"
        lineas.append(f"export const {constante}: Record<string, string> = {{")
        lineas += [
            f'  "{c}": {json.dumps(n[idioma], ensure_ascii=False)},' for c, n in tabla.items()
        ]
        lineas += ["};", ""]
    return "\n".join(lineas)


def principal(argumentos: list[str] | None = None) -> int:
    opciones = argparse.ArgumentParser(description=__doc__)
    opciones.add_argument("--desde", type=Path, required=True)
    opciones.add_argument("--salida", type=Path, default=DESTINO)
    args = opciones.parse_args(argumentos)
    codigos = {
        c for c in json.loads(VOCABULARIO.read_text(encoding="utf-8"))["regiones"]
        if c.startswith("RU-")
    }  # fmt: skip
    datos = json.loads(args.desde.read_text(encoding="utf-8"))
    resultado = regiones(datos, codigos)
    NOMBRES.write_text(modulo_nombres(nombres(datos, codigos)), encoding="utf-8", newline="\n")
    texto = json.dumps(resultado, separators=(",", ":"))
    args.salida.write_text(texto + "\n", encoding="utf-8", newline="\n")
    faltan = sorted(codigos - {r["properties"]["iso"] for r in resultado["features"]})
    print(f"{len(resultado['features'])} regiones, {len(texto) // 1024} KB; sin contorno: {faltan}")
    return 0


if __name__ == "__main__":
    sys.exit(principal())
