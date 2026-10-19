"""Genera el nomenclátor de cárceles (configuracion/carceles_europa.json) desde OpenStreetMap.

Los centros penitenciarios (`amenity=prison`) de cada país, con su nombre y los de OpenStreetMap
(`name`, `official_name`, `alt_name`, `short_name` y los de cada idioma), más los nombres con que
los citan las noticias (ALIAS) y las localidades que, junto a una palabra de cárcel («cárcel de
Córdoba», «presó de Picassent»), los nombran (CIUDADES). Quedan fuera los centros de menores, los
de internamiento de extranjeros, los de inserción social, las cárceles antiguas y lo que no tiene
nombre. Datos © colaboradores de OpenStreetMap, ODbL.

Uso (la consulta, guardada antes con Overpass):
    python -m recogida.carceles_osm consulta_ES.json [consulta_XX.json ...]

Consulta de Overpass de un país:
    [out:json];area["ISO3166-1"="ES"][admin_level=2]->.a;nwr["amenity"="prison"](area.a);
    out center tags;
"""

import argparse
import json
import re
from pathlib import Path
from typing import Any

from proceso.focos_termicos import distancia_km
from recogida.instalaciones_osm import nombres

DESTINO = Path(__file__).resolve().parent.parent / "configuracion" / "carceles_europa.json"
TIPO = "carcel"
RADIO_KM = 1.0
# Lo que no es una cárcel de adultos en servicio.
FUERA = re.compile(
    r"menor|reeducaci|educatiu|educaci[oó]n e internamiento|internamiento de|inserci[oó]n social|"
    r"\bCIS\b|\bCIE\b|C\.I\.M\.I|adingabe|antigu|antiga|construcci[oó]n|m[oó]dulo|madres|"
    r"socioeducativo|destacamento|barneratze|CIEMI",
    re.IGNORECASE,
)
# Repetidos en OpenStreetMap o con el nombre de su localidad («Langraiz» es Nanclares de la Oca;
# el centro es Araba/Zaballa).
EXCLUIDOS = frozenset({"way/799711200", "way/262482880"})
# Un punto a menos de esto de otro centro ya leído es el mismo centro dibujado dos veces.
MISMO_CENTRO_KM = 0.5
# Nombres con que la prensa cita cada centro (por el identificador de OpenStreetMap).
ALIAS = {
    "way/70998662": ["Sevilla I", "Sevilla 1", "prisión de Sevilla I", "cárcel de Sevilla I"],
    "way/270550662": ["Sevilla II", "Sevilla 2"],
    "way/170625228": ["Brians 1", "Brians I", "Can Brians 1"],
    "way/170625229": ["Brians 2", "Brians II"],
    "way/268666551": ["Mas d'Enric", "Mas d’Enric", "Mas Enric"],
    "way/151543877": ["cárcel de Picassent", "prisión de Picassent", "Valencia I"],
    "way/304362329": ["Centro Penitenciario de Córdoba", "cárcel de Córdoba", "prisión de Córdoba"],
    "way/338333191": ["Quatre Camins"],
    "relation/7658081": ["Lledoners"],
    "way/222747993": ["Madrid V"],
    "way/162757051": ["cárcel de Alhaurín de la Torre", "prisión de Alhaurín de la Torre"],
}
# Localidades que nombran el centro junto a una palabra de cárcel.
CIUDADES = {
    "way/70998662": ["Sevilla", "Alcalá de Guadaíra"],
    "way/270550662": ["Morón de la Frontera"],
    "way/170625228": ["Sant Esteve Sesrovires"],
    "way/268666551": ["El Catllar", "Tarragona"],
    "way/151543877": ["Picassent"],
    "way/304362329": ["Córdoba"],
    "way/162757051": ["Alhaurín de la Torre", "Málaga"],
    "way/222747993": ["Soto del Real"],
    "way/149589610": [],
}


def lugar(elemento: dict[str, Any], iso: str) -> tuple[str, dict[str, Any]] | None:
    etiquetas = elemento.get("tags", {})
    principal = etiquetas.get("name") or etiquetas.get("official_name")
    clave = f"{elemento['type']}/{elemento['id']}"
    if not principal or FUERA.search(principal) or clave in EXCLUIDOS:
        return None
    centro = elemento.get("center") or elemento
    # Un nombre que es el de su localidad («Soto del Real») no nombra la cárcel solo: va en
    # las ciudades, que necesitan la palabra «cárcel».
    localidades = {c.casefold() for c in CIUDADES.get(clave, [])}
    todos = [
        n
        for n in dict.fromkeys([*nombres(etiquetas), *ALIAS.get(clave, [])])
        if n.casefold() not in localidades
    ]
    return f"{TIPO}:{clave}", {
        "tipo": TIPO,
        "nombre": principal,
        "alias": todos,
        "ciudades": CIUDADES.get(clave, []),
        "lat": round(float(centro["lat"]), 5),
        "lon": round(float(centro["lon"]), 5),
        "radio_km": RADIO_KM,
        "pais": iso,
    }


def _mismo_nombre(uno: str, otro: str) -> bool:
    """«C.P. Ocaña I» y «Centro Penitenciario Ocaña I» son el mismo centro."""

    def forma(n: str) -> str:
        return " ".join(n.casefold().replace("c.p.", "centro penitenciario").split())

    return forma(uno) == forma(otro)


def generar(consultas: dict[str, dict[str, Any]]) -> dict[str, Any]:
    lugares: dict[str, dict[str, Any]] = {}
    for iso, datos in sorted(consultas.items()):
        # Las áreas antes que los puntos: el mismo centro dibujado como punto y como área vale
        # por su área.
        elementos = sorted(datos.get("elements", []), key=lambda e: e["type"] == "node")
        for elemento in elementos:
            hallado = lugar(elemento, iso)
            if hallado is None:
                continue
            id_, sitio = hallado
            if elemento["type"] == "node" and any(
                _mismo_nombre(sitio["nombre"], o["nombre"])
                and distancia_km(sitio["lat"], sitio["lon"], o["lat"], o["lon"]) < MISMO_CENTRO_KM
                for o in lugares.values()
            ):
                continue
            lugares[id_] = sitio
    return {
        "version_esquema": "1.0.0",
        "descripcion": (
            "Cárceles (centros penitenciarios de adultos) por país, con coordenadas, radio del "
            "objetivo, sus nombres de OpenStreetMap y los que usa la prensa (recogida/"
            "carceles_osm.py). Completa lugares_europa.json e instalaciones_europa.json."
        ),
        "licencia": "Datos © colaboradores de OpenStreetMap, ODbL 1.0: "
        "https://www.openstreetmap.org/copyright",
        "lugares": dict(sorted(lugares.items())),
    }


def principal(argumentos: list[str] | None = None) -> int:
    analizador = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    analizador.add_argument("consultas", nargs="+", type=Path, help="consulta_XX.json")
    args = analizador.parse_args(argumentos)
    consultas = {
        ruta.stem.rsplit("_", 1)[-1].upper(): json.loads(ruta.read_text(encoding="utf-8"))
        for ruta in args.consultas
    }
    texto = json.dumps(generar(consultas), ensure_ascii=False, indent=1) + "\n"
    DESTINO.write_bytes(texto.encode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(principal())
