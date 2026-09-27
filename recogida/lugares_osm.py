"""Genera el vocabulario inicial de lugares europeos desde OpenStreetMap.

Aeropuertos con código OACI e IATA, aeródromos militares y centrales nucleares
con nombre, con sus coordenadas y los nombres con que los citan las noticias.
Datos © colaboradores de OpenStreetMap, bajo licencia ODbL
(https://www.openstreetmap.org/copyright): el fichero generado lo indica.

Se ejecuta a mano, rara vez; el resultado se revisa y se versiona. Después el
vocabulario crece a mano con los lugares que aparezcan en las noticias.

Uso: python -m recogida.lugares_osm
"""

import argparse
import json
import math
import re
import sys
import time
import unicodedata
from pathlib import Path
from typing import Any
from urllib.parse import quote

from recogida.descarga import Descargador

DESTINO = Path(__file__).resolve().parent.parent / "configuracion" / "lugares_europa.json"
OVERPASS = "https://overpass-api.de/api/interpreter"
# Europa con Islandia, Azores y Chipre; los países de fuera se descartan por el prefijo OACI.
CAJA = "(34,-32,72,45)"
CONSULTAS = {
    "aeropuerto": f'nwr["aeroway"="aerodrome"]["icao"]["iata"]{CAJA};',
    "base": f'(nwr["aeroway"="aerodrome"]["military"="airfield"]["name"]{CAJA};'
    f'nwr["aeroway"="aerodrome"]["aerodrome:type"="military"]["name"]{CAJA};);',
    "nuclear": f'nwr["power"="plant"]["plant:source"="nuclear"]["name"]{CAJA};',
}
# El servidor público pide no encadenar consultas pesadas: 30 s entre una y otra.
PAUSA_OVERPASS_S = 30
# Radio del objetivo para la regla de fusión: un aeropuerto grande o una base
# ocupan unos 3 km de lado; 5 km cubren el recinto y su entorno inmediato. Una
# central nuclear ocupa menos de 1 km: 2 km.
RADIO_KM = {"aeropuerto": 5.0, "base": 5.0, "nuclear": 2.0}
# Un lugar sin OACI toma el país del aeropuerto europeo más cercano si está a menos
# de 150 km; más lejos es probable que esté fuera de Europa.
DISTANCIA_PAIS_KM = 150.0
RADIO_TIERRA_KM = 6371.0
DECIMALES = 5
MIN_LETRAS_CIUDAD = 4

# Prefijos OACI de los países europeos. Ucrania va en la capa de guerra; Rusia,
# Bielorrusia y Turquía quedan fuera.
PREFIJOS_OACI = {
    "EB": "BE", "ED": "DE", "ET": "DE", "EE": "EE", "EF": "FI", "EG": "GB", "EH": "NL",
    "EI": "IE", "EK": "DK", "EL": "LU", "EN": "NO", "EP": "PL", "ES": "SE", "EV": "LV",
    "EY": "LT", "LA": "AL", "LB": "BG", "LC": "CY", "LD": "HR", "LE": "ES", "LF": "FR",
    "LG": "GR", "LH": "HU", "LI": "IT", "LJ": "SI", "LK": "CZ", "LM": "MT", "LN": "MC",
    "LO": "AT", "LP": "PT", "LQ": "BA", "LR": "RO", "LS": "CH", "LU": "MD", "LW": "MK",
    "LX": "GI", "LY": "RS", "LZ": "SK", "BI": "IS", "BK": "XK",
}  # fmt: skip
# Montenegro comparte el prefijo LY con Serbia.
OACI_PAIS = {"LYPG": "ME", "LYTV": "ME", "LYBT": "ME"}
IDIOMAS_NOMBRE = (
    "en", "de", "fr", "es", "it", "pl", "nl", "pt", "sv", "da", "no", "fi", "cs", "ro",
    "hu", "el", "bg", "hr", "sk", "sl", "lt", "lv", "et", "uk", "ru",
)  # fmt: skip
# Palabras genéricas que se quitan de un nombre para quedarse con la ciudad.
GENERICAS = re.compile(
    r"\b(?:international|internacional|internazionale|national|nationaal|airport|aeropuerto|aeroporto"
    r"|aéroport|aeroport|flughafen|flugplatz|lotnisko|luchthaven|lufthavn|flygplats|lentoasema"
    r"|letiště|letisko|repülőtér|zračna|luka|aerodrom|aerodrome|airfield|air|base|basis|militar"
    r"|military|fliegerhorst|station|raf|nas|kernkraftwerk|nuclear|power|plant|centrale|nucléaire"
    r"|jądrowa|elektrownia|kärnkraftverk|de|del|di|da|du|la|le|am|im|bei|of|the|and|y|e|et|und"
    r"|regional|city|municipal)\b",
    re.IGNORECASE,
)


def distancia_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distancia de círculo máximo (fórmula del haverseno)."""
    f1, f2 = math.radians(lat1), math.radians(lat2)
    df, dl = f2 - f1, math.radians(lon2 - lon1)
    a = math.sin(df / 2) ** 2 + math.cos(f1) * math.cos(f2) * math.sin(dl / 2) ** 2
    return 2 * RADIO_TIERRA_KM * math.asin(math.sqrt(a))


def sin_acentos(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", texto) if not unicodedata.combining(c))


def pais_oaci(oaci: str) -> str | None:
    return OACI_PAIS.get(oaci) or PREFIJOS_OACI.get(oaci[:2])


def nombres(etiquetas: dict[str, str]) -> list[str]:
    claves = ["name", "official_name", "alt_name", "short_name"]
    claves += [f"name:{i}" for i in IDIOMAS_NOMBRE]
    vistos: list[str] = []
    for clave in claves:
        for nombre in etiquetas.get(clave, "").split(";"):
            nombre = nombre.strip()
            # «Airport» a secas no nombra ningún aeropuerto.
            if not any(c.isalpha() for c in GENERICAS.sub(" ", nombre)):
                continue
            if nombre and nombre not in vistos:
                vistos.append(nombre)
    return vistos


def ciudades(etiquetas: dict[str, str]) -> list[str]:
    """Lo que queda del nombre inglés y del principal sin palabras genéricas, por tramos, y la
    última palabra de cada tramo: «Adolfo Suárez Madrid-Barajas Airport» da «Adolfo Suárez
    Madrid», «Madrid» y «Barajas». Solo casan si el titular nombra además el tipo de lugar."""
    resultado: list[str] = []
    for nombre in (etiquetas.get("name:en", ""), etiquetas.get("name", "")):
        resto = GENERICAS.sub(" ", nombre)
        for trozo in re.split(r"[-–/(),„“”\"]", resto):
            palabras = [p for p in trozo.split() if p[0].isupper() and len(p) >= MIN_LETRAS_CIUDAD]
            for candidata in (" ".join(palabras), palabras[-1] if palabras else ""):
                if candidata and candidata not in resultado:
                    resultado.append(candidata)
    return resultado


def lugar(elemento: dict[str, Any], tipo: str) -> dict[str, Any] | None:
    etiquetas: dict[str, str] = elemento.get("tags", {})
    centro = elemento.get("center", elemento)
    if "lat" not in centro:
        return None
    lista = nombres(etiquetas)
    if not lista:
        return None
    oaci = etiquetas.get("icao", "").strip().upper()
    entrada: dict[str, Any] = {
        "tipo": tipo,
        "nombre": lista[0],
        "alias": lista,
        "ciudades": ciudades(etiquetas),
        "lat": round(float(centro["lat"]), DECIMALES),
        "lon": round(float(centro["lon"]), DECIMALES),
        "radio_km": RADIO_KM[tipo],
    }
    if re.fullmatch(r"[A-Z]{4}", oaci):
        entrada["oaci"] = oaci
        entrada["pais"] = pais_oaci(oaci)
    return entrada


def generar(datos: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Vocabulario a partir de las respuestas de Overpass por tipo."""
    lugares: dict[str, dict[str, Any]] = {}
    aeropuertos: list[dict[str, Any]] = []
    for tipo in ("aeropuerto", "base", "nuclear"):
        for elemento in datos[tipo]["elements"]:
            entrada = lugar(elemento, tipo)
            if entrada is None:
                continue
            if entrada.get("pais") is None and "oaci" in entrada:
                continue  # OACI de fuera de Europa
            if "pais" not in entrada:
                cercano = min(
                    aeropuertos,
                    key=lambda a: distancia_km(a["lat"], a["lon"], entrada["lat"], entrada["lon"]),
                    default=None,
                )
                if (
                    cercano is None
                    or distancia_km(cercano["lat"], cercano["lon"], entrada["lat"], entrada["lon"])
                    > DISTANCIA_PAIS_KM
                ):
                    continue
                entrada["pais"] = cercano["pais"]
            clave = entrada.get("oaci") or f"{tipo}:{elemento['type']}/{elemento['id']}"
            if clave in lugares:
                continue
            lugares[clave] = entrada
            if tipo == "aeropuerto":
                aeropuertos.append(entrada)
    return {
        "version_esquema": "1.0.0",
        "descripcion": (
            "Lugares europeos para agrupar noticias: aeropuertos con código OACI, aeródromos "
            "militares y centrales nucleares, con coordenadas, radio del objetivo y los nombres "
            "con que los citan las noticias. «ciudades» solo casan si el titular nombra además el "
            "tipo de lugar. Crece a mano con el uso."
        ),
        "licencia": "Datos © colaboradores de OpenStreetMap, ODbL 1.0: "
        "https://www.openstreetmap.org/copyright",
        "lugares": dict(sorted(lugares.items())),
    }


def descargar(descargador: Descargador) -> dict[str, dict[str, Any]]:
    datos: dict[str, dict[str, Any]] = {}
    for i, (tipo, consulta) in enumerate(CONSULTAS.items()):
        if i:
            time.sleep(PAUSA_OVERPASS_S)
        peticion = quote(f"[out:json][timeout:190];{consulta}out center tags;", safe="")
        texto = descargador.texto(f"{OVERPASS}?data={peticion}", lambda t: t.lstrip()[:1] == "{")
        datos[tipo] = json.loads(texto)
    return datos


def principal(argumentos: list[str] | None = None) -> int:
    opciones = argparse.ArgumentParser(description=__doc__)
    opciones.add_argument(
        "--desde", type=Path, help="directorio con <tipo>.json ya descargados, sin consultar"
    )
    args = opciones.parse_args(argumentos)
    if args.desde:
        datos = {
            tipo: json.loads((args.desde / f"{tipo}.json").read_text(encoding="utf-8"))
            for tipo in CONSULTAS
        }
    else:
        datos = descargar(Descargador())
    vocabulario = generar(datos)
    DESTINO.write_text(
        json.dumps(vocabulario, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n"
    )
    return 0


if __name__ == "__main__":
    sys.exit(principal())
