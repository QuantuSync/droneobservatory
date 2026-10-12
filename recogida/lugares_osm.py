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
# Cajas (lat mínima, lon mínima, lat máxima, lon máxima) del suelo europeo: el continente
# con Islandia, Azores, Chipre, Ceuta y Melilla, y aparte los territorios de fuera del
# continente que cuentan como su país. Los países de fuera se descartan por el prefijo OACI.
CAJAS = (
    "(34,-32,72,45)",  # Europa
    "(27.5,-18.5,33.3,-13.3)",  # Canarias y Madeira
    "(76,5,81,35)",  # Svalbard
    "(59,-74,84,-11)",  # Groenlandia
    "(15.8,-61.9,16.6,-60.9)",  # Guadalupe
    "(14.3,-61.3,14.95,-60.75)",  # Martinica
    "(18.0,-63.2,18.15,-62.95)",  # San Martín
    "(2,-54.7,6,-51.5)",  # Guayana Francesa
    "(-21.5,55.1,-20.8,55.9)",  # Reunión
    "(-13.1,44.95,-12.6,45.35)",  # Mayotte
)


def _en_cajas(filtro: str) -> str:
    return "(" + "".join(f"{filtro}{caja};" for caja in CAJAS) + ");"


CONSULTAS = {
    "aeropuerto": _en_cajas('nwr["aeroway"="aerodrome"]["icao"]["iata"]'),
    "base": _en_cajas('nwr["aeroway"="aerodrome"]["military"="airfield"]["name"]')[:-2]
    + _en_cajas('nwr["aeroway"="aerodrome"]["aerodrome:type"="military"]["name"]')[1:],
    "nuclear": _en_cajas('nwr["power"="plant"]["plant:source"="nuclear"]["name"]'),
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
# Bielorrusia y Turquía quedan fuera. Los territorios de fuera del continente van con el
# país del que dependen: Canarias (GC) y Ceuta y Melilla (GE) con España, Gibraltar (LX)
# con el Reino Unido, Groenlandia (BG) con Dinamarca, Svalbard (EN) con Noruega, y las
# Antillas francesas (TF), la Guayana (SO) y Reunión (FME) con Francia.
PREFIJOS_OACI = {
    "EB": "BE", "ED": "DE", "ET": "DE", "EE": "EE", "EF": "FI", "EG": "GB", "EH": "NL",
    "EI": "IE", "EK": "DK", "EL": "LU", "EN": "NO", "EP": "PL", "ES": "SE", "EV": "LV",
    "EY": "LT", "LA": "AL", "LB": "BG", "LC": "CY", "LD": "HR", "LE": "ES", "LF": "FR",
    "LG": "GR", "LH": "HU", "LI": "IT", "LJ": "SI", "LK": "CZ", "LM": "MT", "LN": "MC",
    "LO": "AT", "LP": "PT", "LQ": "BA", "LR": "RO", "LS": "CH", "LU": "MD", "LW": "MK",
    "LX": "GB", "LY": "RS", "LZ": "SK", "BI": "IS", "BK": "XK", "GC": "ES", "GE": "ES",
    "BG": "DK", "TF": "FR", "SO": "FR", "FME": "FR",
}  # fmt: skip
# Montenegro comparte el prefijo LY con Serbia; Mayotte, el FMC con las Comoras; las bases
# británicas de Chipre (Akrotiri y Kingsfield, en Dhekelia), el LC con Chipre.
OACI_PAIS = {
    "LYPG": "ME", "LYTV": "ME", "LYBT": "ME", "FMCZ": "FR", "LCRA": "GB", "LCRE": "GB",
}  # fmt: skip
# Lugares sin OACI cuyo aeropuerto más cercano es de otro país: el aeródromo de Dhekelia
# está en la base británica, pero su aeropuerto más cercano es el de Lárnaca.
PAIS_ELEMENTO = {"base:way/82850335": "GB"}
# Lugares de los territorios de fuera del continente completados a mano: nombres con que
# los citan las noticias y que OpenStreetMap no trae («RAF Akrotiri», «Thule Air Base»),
# ciudades limpias (las sacadas del nombre dejan palabras sueltas como «North» o «Saint»,
# que casarían con cualquier titular), el tipo de Pituffik (base militar) y los que la
# consulta no recoge porque no tienen código IATA (Kourou, Svea) o no son un aeródromo
# (el Centro Espacial Guayanés, un puerto espacial que se toma como base por su protección
# militar). Coordenadas de OpenStreetMap y OurAirports. Los alias se
# añaden a los de OpenStreetMap; los demás campos los sustituyen.
A_MANO: dict[str, dict[str, Any]] = {
    "GCLP": {
        "alias": ["Aeropuerto de Gran Canaria", "Gran Canaria Airport", "Flughafen Gran Canaria",
                  "Aéroport de Gran Canaria", "Aeroporto di Gran Canaria", "Aeropuerto de Gando"],
        "ciudades": ["Gran Canaria", "Gando"],
    },
    "GCTS": {"ciudades": ["Tenerife Sur", "Tenerife South", "Reina Sofía"]},
    "GCXO": {"ciudades": ["Tenerife Norte", "Tenerife North", "Los Rodeos"]},
    "GCRR": {"ciudades": ["Lanzarote", "César Manrique"]},
    "GCFV": {"ciudades": ["Fuerteventura"]},
    "GCLA": {"ciudades": ["La Palma"]},
    "GCGM": {"ciudades": ["La Gomera", "Gomera"]},
    "GCHI": {"ciudades": ["El Hierro", "Hierro"]},
    "GEML": {"ciudades": ["Melilla"]},
    "LPPD": {
        "alias": ["Aeroporto de Ponta Delgada", "Ponta Delgada Airport",
                  "Aeropuerto de Ponta Delgada"],
        "ciudades": ["Ponta Delgada", "João Paulo II"],
    },
    "LPLA": {
        "alias": ["Base Aérea das Lajes", "Base Aérea N.º 4", "Lajes Field", "Lajes Air Base"],
        "ciudades": ["Lajes", "Terceira"],
    },
    "LPHR": {"ciudades": ["Horta", "Faial"]},
    "LPPI": {"alias": ["Pico Airport"], "ciudades": ["Pico"]},
    "LPAZ": {"ciudades": ["Santa Maria"]},
    "LPSJ": {"ciudades": ["São Jorge"]},
    "LPGR": {"ciudades": ["Graciosa"]},
    "LPFL": {"ciudades": ["Flores"]},
    "LPCR": {"ciudades": ["Corvo"]},
    "LPMA": {
        "alias": ["Aeroporto do Funchal", "Funchal Airport", "Aeropuerto de Madeira"],
        "ciudades": ["Madeira", "Funchal", "Cristiano Ronaldo"],
    },
    "LPPS": {"ciudades": ["Porto Santo"]},
    "LXGB": {
        "alias": ["Gibraltar Airport", "Gibraltar International Airport", "Aeropuerto de Gibraltar",
                  "Flughafen Gibraltar", "Aéroport de Gibraltar"],
        "ciudades": ["Gibraltar"],
    },
    "LCRA": {
        "alias": ["RAF Akrotiri", "Akrotiri Air Base", "Base aérea de Akrotiri"],
        "ciudades": ["Akrotiri"],
    },
    "LCRE": {"alias": ["Kingsfield Air Base"], "ciudades": ["Kingsfield", "Dhekelia"]},
    "base:way/82850335": {"ciudades": ["Dhekelia"]},
    "ENSB": {
        "alias": ["Longyearbyen lufthavn", "Longyearbyen Airport", "Flughafen Longyearbyen",
                  "Aéroport de Longyearbyen", "Aeropuerto de Longyearbyen"],
        "ciudades": ["Longyearbyen", "Longyear", "Svalbard"],
    },
    "ENSA": {
        "tipo": "aeropuerto", "nombre": "Svea flyplass", "alias": ["Svea flyplass", "Svea Airport"],
        "ciudades": ["Svea"], "lat": 77.89658, "lon": 16.72116, "radio_km": 5.0, "oaci": "ENSA",
        "pais": "NO",
    },
    "BGGH": {"alias": ["Nuuk Lufthavn", "Nuuk International Airport"], "ciudades": ["Nuuk"]},
    "BGSF": {"alias": ["Sondrestrom Air Base"], "ciudades": ["Kangerlussuaq"]},
    "BGTL": {
        "tipo": "base",
        "alias": ["Thule Air Base", "Thule Airbase", "Base aérienne de Thulé", "Pituffik"],
        "ciudades": ["Pituffik", "Thule"],
    },
    "BGKK": {"ciudades": ["Kulusuk"]},
    "BGNO": {"ciudades": ["Station Nord"]},
    "base:way/64787419": {"ciudades": ["Ikkatteq", "Ikateq"]},
    "TFFR": {
        "alias": ["Aéroport de Pointe-à-Pitre", "Aéroport Pôle Caraïbes"],
        "ciudades": ["Pointe-à-Pitre", "Guadeloupe", "Maryse Condé", "Le Raizet"],
    },
    "TFFA": {"ciudades": ["Désirade", "La Désirade"]},
    "TFFB": {"ciudades": ["Baillif", "Basse-Terre"]},
    "TFFC": {"ciudades": ["Saint-François"]},
    "TFFM": {"ciudades": ["Marie-Galante"]},
    "TFFS": {"ciudades": ["Les Saintes", "Terre-de-Haut"]},
    "TFFF": {
        "alias": ["Aéroport de Fort-de-France", "Aéroport du Lamentin"],
        "ciudades": ["Martinique", "Aimé Césaire", "Le Lamentin", "Fort-de-France"],
    },
    "TFFG": {"ciudades": ["Grand-Case", "Grand Case", "Saint-Martin"]},
    "SOCA": {
        "alias": ["Aéroport de Cayenne", "Aéroport de Cayenne-Rochambeau"],
        "ciudades": ["Cayenne", "Félix Éboué", "Rochambeau", "Matoury"],
    },
    "SOGS": {"ciudades": ["Grand-Santi"]},
    "SOOG": {"ciudades": ["Saint-Georges-de-l'Oyapock", "Oyapock"]},
    "SOOM": {"ciudades": ["Saint-Laurent-du-Maroni"]},
    "SOOK": {
        "tipo": "aeropuerto", "nombre": "Aéroport de Kourou",
        "alias": ["Aéroport de Kourou", "Aérodrome de Kourou", "Kourou Airport"],
        "ciudades": ["Kourou"], "lat": 5.17582, "lon": -52.69424, "radio_km": 5.0, "oaci": "SOOK",
        "pais": "FR",
    },
    "base:relation/8090912": {
        "tipo": "base", "nombre": "Centre Spatial Guyanais",
        "alias": ["Centre Spatial Guyanais", "Guiana Space Centre", "Guiana Space Center",
                  "Centre spatial de Kourou", "Base spatiale de Kourou", "Kourou Spaceport",
                  "Centro Espacial Guayanés", "Centro Espacial de Kourou",
                  "Weltraumbahnhof Kourou", "Raumfahrtzentrum Guayana"],
        "ciudades": ["Kourou"], "lat": 5.21238, "lon": -52.77388, "radio_km": 10.0,
        "pais": "FR",
    },
    "base:way/784937893": {"ciudades": ["Rochambeau", "BA 367"]},
    "FMEE": {
        "alias": ["Aéroport Roland-Garros", "Aéroport Roland Garros", "Aéroport de Gillot",
                  "Aéroport de Saint-Denis"],
        "ciudades": ["Roland Garros", "Roland-Garros", "Gillot"],
    },
    "FMEP": {"ciudades": ["Pierrefonds"]},
    "FMCZ": {
        "alias": ["Aéroport de Dzaoudzi", "Aéroport de Mayotte", "Dzaoudzi Pamandzi Airport"],
        "ciudades": ["Marcel Henry", "Dzaoudzi", "Pamandzi", "Mayotte"],
    },
}  # fmt: skip
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
    return OACI_PAIS.get(oaci) or PREFIJOS_OACI.get(oaci[:3]) or PREFIJOS_OACI.get(oaci[:2])


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


def _descompuesto(valor: Any) -> Any:
    """Textos en forma descompuesta (NFD). Algunas herramientas de texto no reconocen letras
    como «ș» dentro de una palabra y parten el nombre («Timișoara»); descompuesto, «s» sigue
    siendo letra. Es el mismo texto Unicode y la búsqueda normaliza igual."""
    if isinstance(valor, str):
        return unicodedata.normalize("NFD", valor)
    if isinstance(valor, list):
        return [_descompuesto(v) for v in valor]
    if isinstance(valor, dict):
        return {k: _descompuesto(v) for k, v in valor.items()}
    return valor


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
            entrada["pais"] = PAIS_ELEMENTO.get(clave, entrada["pais"])
            lugares[clave] = entrada
            if tipo == "aeropuerto":
                aeropuertos.append(entrada)
    for clave, extra in A_MANO.items():
        if clave in lugares:
            sitio = lugares[clave]
            sitio.update({k: v for k, v in extra.items() if k != "alias"})
            sitio["alias"] += [a for a in extra.get("alias", []) if a not in sitio["alias"]]
        elif "nombre" in extra:
            lugares[clave] = dict(extra)
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
        "lugares": {clave: _descompuesto(v) for clave, v in sorted(lugares.items())},
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
