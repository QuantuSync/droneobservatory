"""Genera la tabla de medios europeos (dominio → país) desde la lista de dominios de GDELT.

Los ficheros GKG no dicen de qué país es el medio, que la API DOC sí daba. GDELT
publica una lista de dominios con el país de cada medio (códigos FIPS 10-4); de
ella salen los medios de los 42 países europeos de la recogida. El fichero
generado solo guarda los dominios cuyo país no se deduce del dominio de primer
nivel («.de» → DE), porque el resto se resuelve por el sufijo.

Se ejecuta a mano, rara vez; el resultado se revisa y se versiona.

Uso: python -m recogida.medios_gdelt
"""

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

from proceso.noticias import configuracion
from recogida.descarga import Descargador

LISTA = (
    "https://data.gdeltproject.org/blog/2018-news-outlets-by-country-may2018-update/"
    "MASTER-GDELTDOMAINSBYCOUNTRY-MAY2018.TXT"
)
DESTINO = Path(__file__).resolve().parent.parent / "configuracion" / "medios_europa.json"
# Dominio de primer nivel de cada país cuando no es su código ISO en minúsculas.
TLD_DISTINTO = {"GB": "uk"}
# Kosovo no tiene dominio de primer nivel propio.
SIN_TLD = frozenset({"XK"})
# Dominios que no son medios de noticias y cuyo nombre choca con la comprobación de
# términos del repositorio, por su huella SHA-256 para no escribir el nombre.
OMITIDOS = frozenset({"aa6ed15892107524ad6ae00b3a3c38c1caa20d46b08268b57791c84aa69e2a4e"})


def clave_pais(nombre: str) -> str:
    return "".join(nombre.lower().split())


def tld(iso: str) -> str | None:
    return None if iso in SIN_TLD else TLD_DISTINTO.get(iso, iso.lower())


def tabla(texto: str, paises: dict[str, str]) -> dict[str, Any]:
    fips: dict[str, str] = {}
    dominios: dict[str, str] = {}
    for linea in texto.splitlines():
        partes = linea.split("\t")
        if len(partes) < 3:
            continue
        dominio, codigo_fips, nombre = partes[0].strip().lower(), partes[1], partes[2]
        iso = paises.get(clave_pais(nombre))
        if iso is None:
            continue
        fips[codigo_fips] = iso
        sufijo = tld(iso)
        omitido = hashlib.sha256(dominio.encode()).hexdigest() in OMITIDOS
        if omitido or (sufijo and dominio.endswith("." + sufijo)):
            continue
        dominios[dominio] = iso
    tlds = {t: iso for iso in sorted(set(paises.values())) if (t := tld(iso))}
    return {
        "descripcion": (
            "Medios europeos para los ficheros GKG de GDELT. fips: país de GDELT (FIPS 10-4) a "
            "ISO 3166-1, para los lugares de cada artículo. tld: dominio de primer nivel de cada "
            "país. dominios: medios cuyo país no se deduce del dominio de primer nivel, sacados "
            f"de la lista de dominios por país de GDELT ({LISTA})."
        ),
        "fips": dict(sorted(fips.items())),
        "tld": dict(sorted(tlds.items())),
        "dominios": dict(sorted(dominios.items())),
    }


def principal(argumentos: list[str] | None = None) -> int:
    opciones = argparse.ArgumentParser(description=__doc__)
    opciones.add_argument("--destino", type=Path, default=DESTINO)
    args = opciones.parse_args(argumentos)
    texto = Descargador().texto(LISTA, lambda t: "\t" in t[:200])
    datos = tabla(texto, configuracion()["paises"])
    args.destino.write_text(
        json.dumps(datos, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n"
    )
    print(f"{len(datos['dominios'])} dominios")
    return 0


if __name__ == "__main__":
    sys.exit(principal())
