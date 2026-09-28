"""Genera el nomenclátor ampliado de instalaciones europeas desde OpenStreetMap.

Además de los aeropuertos con OACI, bases aéreas y centrales nucleares del
nomenclátor inicial (`lugares_osm.py`), las instalaciones de todas las
categorías del esquema, país a país: aeródromos y helipuertos, bases e
instalaciones militares, puertos, centrales eléctricas, subestaciones de alta
tensión, presas y estadios, con coordenadas y los nombres en todos los idiomas
que traiga OpenStreetMap. Datos © colaboradores de OpenStreetMap, ODbL.

Se ejecuta a mano, rara vez; el resultado se revisa y se versiona.

Uso: python -m recogida.instalaciones_osm [--desde <directorio con <país>.json>]
"""

import argparse
import hashlib
import json
import re
import sys
import time
import unicodedata
from pathlib import Path
from typing import Any
from urllib.parse import quote

from proceso.noticias import configuracion
from recogida.descarga import AGENTE_EODI, Descargador, DescargaFallida

DESTINO = Path(__file__).resolve().parent.parent / "configuracion" / "instalaciones_europa.json"
OVERPASS = "https://overpass-api.de/api/interpreter"
# El servidor público pide no encadenar consultas pesadas: 20 s entre países.
PAUSA_OVERPASS_S = 20
LIMITE_CONSULTA_S = 600.0
# Un servidor saturado responde 504: 5 reintentos con esperas de 30 s dobladas (hasta unos
# 15 minutos) dejan pasar un pico de carga.
REINTENTOS_OVERPASS = 5
ESPERA_OVERPASS_S = 30.0
DECIMALES = 5
# Radio del objetivo para la regla de fusión, por tipo: un aeródromo o una base ocupan
# unos 3 km de lado (5 km cubren el recinto y su entorno); un puerto, 3 km; una central,
# una presa o un estadio, menos de 1 km (2 km, como las centrales nucleares); un helipuerto
# o una subestación, unos cientos de metros (1 km).
RADIO_KM = {
    "aeropuerto": 5.0, "helipuerto": 1.0, "base": 5.0, "puerto": 3.0, "energia": 2.0,
    "subestacion": 1.0, "presa": 2.0, "estadio": 1.0,
}  # fmt: skip
# Tensiones de la red de transporte europea (220 kV o más): las subestaciones grandes.
TENSIONES = "220000|225000|275000|300000|330000|380000|400000|500000|750000"
# Las centrales solares y eólicas son miles de parques sin interés como objetivo.
SIN_FUENTES = "solar|wind"
CONSULTA = (
    'area["ISO3166-1"="{iso}"][admin_level=2]->.a;('
    'nwr["aeroway"="aerodrome"]["name"](area.a);'
    'nwr["aeroway"="heliport"]["name"](area.a);'
    'nwr["military"~"^(base|airfield|naval_base|barracks|range)$"]["name"](area.a);'
    'nwr["landuse"="port"]["name"](area.a);'
    'nwr["industrial"="port"]["name"](area.a);'
    'nwr["power"="plant"]["name"]["plant:source"!~"' + SIN_FUENTES + '"](area.a);'
    'nwr["power"="substation"]["name"]["voltage"~"' + TENSIONES + '"](area.a);'
    'nwr["waterway"="dam"]["name"](area.a);'
    'nwr["leisure"="stadium"]["name"](area.a);'
    ");"
)
MIN_LETRAS = 4
# Palabras que la comprobación de términos del repositorio rechaza, por su huella SHA-256
# en minúsculas para no escribirlas: un nombre que las contenga se omite.
PALABRAS_OMITIDAS = frozenset(
    {
        "32e83e92d45d71f69dcf9d214688f0375542108631b45d344e5df2eb91c11566",
        "26138d8a757dd1dc09df6301bc4a47f0a1f7f785a725ae72574c6862127a2201",
        "487b91042c7cf27a19e23ea8699f5f354b1a0c3af9e418138dc6150d830f970d",
        "053ea4804ef1bb33d4a3d6fb024a614b6d257cebc2bc7cd915da9c9522f37ffc",
        "c857d09db23e6822e3600bc06ad8d58f92ed62bc8efd81c753f77048662cb97d",
        "c70eca6b0f88f44d81a41311647e50fda1ac454ec04ffd442b0eb4743a993131",
    }
)


def tipo(etiquetas: dict[str, str]) -> str | None:
    if etiquetas.get("aeroway") == "aerodrome":
        return "base" if etiquetas.get("military") else "aeropuerto"
    if etiquetas.get("aeroway") == "heliport":
        return "helipuerto"
    if etiquetas.get("military"):
        return "base"
    if etiquetas.get("landuse") == "port" or etiquetas.get("industrial") == "port":
        return "puerto"
    if etiquetas.get("power") == "plant":
        return "nuclear" if etiquetas.get("plant:source") == "nuclear" else "energia"
    if etiquetas.get("power") == "substation":
        return "subestacion"
    if etiquetas.get("waterway") == "dam":
        return "presa"
    if etiquetas.get("leisure") == "stadium":
        return "estadio"
    return None


# Largo de las dos palabras omitidas que se buscan también dentro de otras.
LARGOS_DENTRO = (6, 9)


def omitido(nombre: str) -> bool:
    """El nombre tiene una palabra omitida, partiendo como la comprobación de términos: por
    cualquier carácter que no sea una letra ASCII, un número o «_», en la forma compuesta y
    en la descompuesta (una letra con cedilla parte la palabra en dos)."""
    formas = {nombre, unicodedata.normalize("NFD", nombre), unicodedata.normalize("NFC", nombre)}
    return any(
        hashlib.sha256(palabra.encode()).hexdigest() in PALABRAS_OMITIDAS
        for forma in formas
        for palabra in re.split(r"[^a-z0-9_]+", forma.lower())
    ) or any(
        # Las dos palabras largas se rechazan también dentro de otra (un municipio del Jura).
        hashlib.sha256(trozo.encode()).hexdigest() in PALABRAS_OMITIDAS
        for forma in formas
        for largo in LARGOS_DENTRO
        for trozo in (forma.lower()[k : k + largo] for k in range(len(forma) - largo + 1))
    )


def nombres(etiquetas: dict[str, str]) -> list[str]:
    """El nombre principal y los de todos los idiomas y variantes que trae OpenStreetMap."""
    claves = ["name", "official_name", "alt_name", "short_name", "int_name"]
    claves += sorted(k for k in etiquetas if k.startswith(("name:", "official_name:", "alt_name:")))
    vistos: list[str] = []
    for clave in claves:
        for nombre in etiquetas.get(clave, "").split(";"):
            nombre = " ".join(nombre.split())
            if len(nombre) >= MIN_LETRAS and nombre not in vistos and not omitido(nombre):
                vistos.append(nombre)
    return vistos


def lugar(elemento: dict[str, Any], iso: str) -> tuple[str, dict[str, Any]] | None:
    etiquetas: dict[str, str] = elemento.get("tags", {})
    centro = elemento.get("center", elemento)
    clase = tipo(etiquetas)
    lista = nombres(etiquetas)
    if clase is None or "lat" not in centro or not lista:
        return None
    oaci = etiquetas.get("icao", "").strip().upper()
    entrada: dict[str, Any] = {
        "tipo": clase,
        "nombre": lista[0],
        "alias": lista,
        "ciudades": [],
        "lat": round(float(centro["lat"]), DECIMALES),
        "lon": round(float(centro["lon"]), DECIMALES),
        "radio_km": RADIO_KM.get(clase, 2.0),
        "pais": iso,
    }
    if re.fullmatch(r"[A-Z]{4}", oaci):
        entrada["oaci"] = oaci
    return f"{clase}:{elemento['type']}/{elemento['id']}", entrada


def generar(por_pais: dict[str, dict[str, Any]], existentes: set[str]) -> dict[str, Any]:
    """Instalaciones sin repetir las del nomenclátor inicial (por su OACI o su elemento)."""
    lugares: dict[str, str] = {}
    for iso, datos in sorted(por_pais.items()):
        for elemento in datos.get("elements", []):
            resultado = lugar(elemento, iso)
            if resultado is None:
                continue
            clave, entrada = resultado
            # El nomenclátor inicial identifica sus lugares por OACI o por «tipo:elemento».
            elemento = clave.split(":", 1)[1]
            repetido = entrada.get("oaci") in existentes or any(
                f"{t}:{elemento}" in existentes for t in ("aeropuerto", "base", "nuclear")
            )
            if repetido or clave in lugares:
                continue
            # En forma descompuesta, como el nomenclátor inicial.
            lugares[clave] = unicodedata.normalize("NFD", json.dumps(entrada, ensure_ascii=False))
    return {
        "version_esquema": "1.0.0",
        "descripcion": (
            "Instalaciones europeas de las categorías del esquema, por país: aeródromos, "
            "helipuertos, bases militares, puertos, centrales, subestaciones de 220 kV o más, "
            "presas y estadios, con coordenadas, radio del objetivo y sus nombres en todos los "
            "idiomas de OpenStreetMap. Completa lugares_europa.json sin repetir sus lugares."
        ),
        "licencia": "Datos © colaboradores de OpenStreetMap, ODbL 1.0: "
        "https://www.openstreetmap.org/copyright",
        "lugares": {k: json.loads(v) for k, v in sorted(lugares.items())},
    }


def descargar(descargador: Descargador, paises: list[str], directorio: Path) -> None:
    """Una consulta por país; guarda cada respuesta para poder repetir sin consultar."""
    directorio.mkdir(parents=True, exist_ok=True)
    for i, iso in enumerate(paises):
        ruta = directorio / f"{iso}.json"
        en_curso = directorio / f"{iso}.en_curso"
        if ruta.exists() or en_curso.exists():
            continue
        en_curso.write_text("", encoding="utf-8")
        if i:
            time.sleep(PAUSA_OVERPASS_S)
        consulta = f"[out:json][timeout:600];{CONSULTA.format(iso=iso)}out center tags;"
        try:
            texto = descargador.texto(
                f"{OVERPASS}?data={quote(consulta, safe='')}", lambda t: t.lstrip()[:1] == "{"
            )
        except DescargaFallida:
            # Un país que no sale se deja para otra pasada: los demás siguen.
            en_curso.unlink()
            print(iso, "sin respuesta", flush=True)
            continue
        ruta.write_text(texto, encoding="utf-8")
        en_curso.unlink()
        print(iso, len(json.loads(texto).get("elements", [])), flush=True)


def principal(argumentos: list[str] | None = None) -> int:
    opciones = argparse.ArgumentParser(description=__doc__)
    opciones.add_argument("--desde", type=Path, required=True, help="directorio de respuestas")
    opciones.add_argument("--sin-descargar", action="store_true")
    # Overpass admite dos consultas a la vez por dirección: un segundo proceso puede recorrer
    # los países al revés y cada uno salta los que ya estén guardados.
    opciones.add_argument("--inverso", action="store_true", help="recorre los países al revés")
    args = opciones.parse_args(argumentos)
    paises = sorted(set(configuracion()["paises"].values()))
    if not args.sin_descargar:
        # Una consulta por país puede tardar minutos en el servidor: 10 minutos de límite.
        descargador = Descargador(
            agente=AGENTE_EODI,
            limite_s=LIMITE_CONSULTA_S,
            reintentos=REINTENTOS_OVERPASS,
            espera_inicial_s=ESPERA_OVERPASS_S,
        )
        descargar(descargador, paises[::-1] if args.inverso else paises, args.desde)
    por_pais = {
        iso: json.loads((args.desde / f"{iso}.json").read_text(encoding="utf-8"))
        for iso in paises
        if (args.desde / f"{iso}.json").exists()
    }
    inicial = json.loads((DESTINO.parent / "lugares_europa.json").read_text(encoding="utf-8"))[
        "lugares"
    ]
    existentes = set(inicial) | {str(v["oaci"]) for v in inicial.values() if v.get("oaci")}
    datos = generar(por_pais, existentes)
    DESTINO.write_text(
        json.dumps(datos, ensure_ascii=False, indent=0) + "\n", encoding="utf-8", newline="\n"
    )
    print(len(datos["lugares"]), "instalaciones")
    return 0


if __name__ == "__main__":
    sys.exit(principal())
