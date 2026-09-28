"""Genera las cajas de coordenadas de los países europeos desde Nominatim (OpenStreetMap).

La validación del extractor comprueba que unas coordenadas caen dentro de la
caja del país que cita la fuente. Una caja es más ancha que el país, así que
solo descarta errores gruesos (un aeropuerto de Dinamarca situado en Italia).
Datos © colaboradores de OpenStreetMap, bajo licencia ODbL.

Se ejecuta a mano, rara vez; el resultado se revisa y se versiona.

Uso: python -m recogida.paises_osm
"""

import argparse
import json
import sys
from pathlib import Path

from proceso.noticias import configuracion
from recogida.descarga import AGENTE_EODI, Descargador

DESTINO = Path(__file__).resolve().parent.parent / "configuracion" / "paises_europa.json"
NOMINATIM = "https://nominatim.openstreetmap.org/search?format=json&limit=1&country="
# La política de uso de Nominatim pide como mucho una petición por segundo.
PAUSA_S = 1.5
DECIMALES = 3
# Territorios lejanos que ensanchan la caja hasta hacerla inútil (Francia de ultramar,
# Portugal con Azores y Madeira, España con Canarias, Noruega con Svalbard): se usa la
# caja de la parte europea continental más las islas cercanas.
CAJAS_FIJAS = {
    "FR": [41.3, 51.1, -5.2, 9.6],
    "PT": [36.9, 42.2, -9.6, -6.2],
    "ES": [35.9, 43.8, -9.3, 4.4],
    "NO": [57.9, 71.2, 4.6, 31.1],
    "NL": [50.7, 53.6, 3.3, 7.3],
    "DK": [54.5, 57.8, 8.0, 15.2],
    "GB": [49.8, 60.9, -8.7, 1.8],
}


def principal(argumentos: list[str] | None = None) -> int:
    opciones = argparse.ArgumentParser(description=__doc__)
    opciones.add_argument("--destino", type=Path, default=DESTINO)
    args = opciones.parse_args(argumentos)
    descargador = Descargador(
        pausas_por_sitio={"nominatim.openstreetmap.org": PAUSA_S}, agente=AGENTE_EODI
    )
    cajas: dict[str, list[float]] = {}
    for iso in sorted(set(configuracion()["paises"].values())):
        if iso in CAJAS_FIJAS:
            cajas[iso] = CAJAS_FIJAS[iso]
            continue
        texto = descargador.texto(NOMINATIM + iso.lower(), lambda t: t.startswith("["))
        resultados = json.loads(texto)
        if not resultados:
            print(f"{iso}: sin resultado", file=sys.stderr)
            continue
        caja = [round(float(v), DECIMALES) for v in resultados[0]["boundingbox"]]
        cajas[iso] = caja
    datos = {
        "descripcion": (
            "Caja de coordenadas de cada país europeo: [lat mínima, lat máxima, lon mínima, "
            "lon máxima]. De Nominatim (OpenStreetMap, ODbL), salvo los países con territorios "
            "lejanos, que llevan la caja de su parte europea."
        ),
        "cajas": cajas,
    }
    args.destino.write_text(
        json.dumps(datos, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n"
    )
    print(f"{len(cajas)} países")
    return 0


if __name__ == "__main__":
    sys.exit(principal())
