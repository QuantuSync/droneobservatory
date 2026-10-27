"""Nombres de lugar en español y en inglés desde Wikidata.

Dos usos:

- `generar` (a mano, rara vez): escribe configuracion/nombres_lugar_wikidata.json.gz con el nombre
  español y el inglés de los aeropuertos y bases con código OACI del vocabulario
  (configuracion/lugares_europa.json, por la propiedad P239 de Wikidata) y de las localidades de
  configuracion/localidades_europa.json con radio de 5 km o más (por su número de GeoNames, P1566).
  Las etiquetas se limpian («Ciudad de Sevilla» → «Sevilla», «Aeropuerto Internacional de Pafos»
  → «Aeropuerto de Pafos») y una etiqueta de localidad solo se acepta si es uno de los nombres que
  GeoNames da a esa localidad: así no entra el municipio vecino que Wikidata enlaza por error. Lo
  dudoso se corrige a mano en configuracion/nombres_lugar.json, que manda sobre lo generado.
- `paso_horario` (cada hora, antes de publicar): los nombres de lugar de los incidentes que no
  están en ninguna de las dos tablas se buscan en Wikidata (wbsearchentities y wbgetentities,
  el elemento del mismo país) y se guardan en la caché (EODI_NOMBRES_CACHE). Lo que no se
  encuentra también se anota, y se vuelve a buscar pasada una semana. Con tope de tiempo y de
  consultas: nunca impide publicar; lo que no da tiempo a buscar se escribe con la regla de
  proceso/nombres_lugar.py (el nombre local en alfabeto latino, o la localidad o el país).

Datos de Wikidata (CC0) y de GeoNames (CC BY 4.0).

Uso: python -m recogida.nombres_wikidata generar
"""

import argparse
import gzip
import json
import logging
import re
import sys
import time
import urllib.parse
import urllib.request
from collections import defaultdict
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from proceso import nombres_lugar
from proceso.nombres_lugar import Bilingue, clave, latino_puro, limpiar_etiqueta

registro = logging.getLogger(__name__)

CONFIGURACION = Path(__file__).resolve().parent.parent / "configuracion"
DESTINO = CONFIGURACION / "nombres_lugar_wikidata.json.gz"
SPARQL = "https://query.wikidata.org/sparql"
API = "https://www.wikidata.org/w/api.php"
AGENTE = "EODI-bot/1.0 (+https://droneobservatory.eu)"
# Localidades que entran en la tabla: las de 5 km de radio o más (unas 9.700: ciudades y
# pueblos grandes). Las demás se escriben con su nombre local o se buscan al aparecer.
RADIO_MINIMO_KM = 5.0
TROZO = 400
# Búsqueda horaria: como mucho tantas consultas y tantos segundos, y lo no encontrado se vuelve
# a buscar pasada una semana.
MAX_BUSQUEDAS = 25
TOPE_S = 60.0
REINTENTO_NO_ENCONTRADO = timedelta(days=7)
ESPERA_S = 0.5
# Países del observatorio -> elemento de Wikidata (P17), para quedarse con el elemento del país.
PAISES_WIKIDATA = {
    "AD": "Q228", "AL": "Q222", "AT": "Q40", "BA": "Q225", "BE": "Q31", "BG": "Q219",
    "BY": "Q184", "CH": "Q39", "CY": "Q229", "CZ": "Q213", "DE": "Q183", "DK": "Q35",
    "EE": "Q191", "ES": "Q29", "FI": "Q33", "FR": "Q142", "GB": "Q145", "GR": "Q41",
    "HR": "Q224", "HU": "Q28", "IE": "Q27", "IS": "Q189", "IT": "Q38", "LI": "Q347",
    "LT": "Q37", "LU": "Q32", "LV": "Q211", "MC": "Q235", "MD": "Q217", "ME": "Q236",
    "MK": "Q221", "MT": "Q233", "NL": "Q55", "NO": "Q20", "PL": "Q36", "PT": "Q45",
    "RO": "Q218", "RS": "Q403", "RU": "Q159", "SE": "Q34", "SI": "Q215", "SK": "Q214",
    "SM": "Q238", "TR": "Q43", "UA": "Q212", "VA": "Q237", "XK": "Q1246",
}  # fmt: skip
# Idioma de la búsqueda por país (además del inglés).
IDIOMA_PAIS = {
    "AL": "sq", "AT": "de", "BE": "nl", "BG": "bg", "BY": "be", "CH": "de", "CY": "el",
    "CZ": "cs", "DE": "de", "DK": "da", "EE": "et", "ES": "es", "FI": "fi", "FR": "fr",
    "GR": "el", "HR": "hr", "HU": "hu", "IS": "is", "IT": "it", "LT": "lt", "LU": "fr",
    "LV": "lv", "MD": "ro", "ME": "sr", "MK": "mk", "MT": "mt", "NL": "nl", "NO": "nb",
    "PL": "pl", "PT": "pt", "RO": "ro", "RS": "sr", "RU": "ru", "SE": "sv", "SI": "sl",
    "SK": "sk", "TR": "tr", "UA": "uk",
}  # fmt: skip
# Etiquetas de las bases militares en inglés: lo que distingue el elemento de la base del
# aeropuerto civil con el mismo código OACI.
BASE_EN = re.compile(r"\b(?:Air Base|Airbase|Air Station|RAF|Air Force|Naval Air|Flying Base)\b")
COMARCA = re.compile(r"\b(?:District|Municipality|Region|County|Province|Capital|Oblast)\b", re.I)

Pedir = Callable[[urllib.request.Request], Any]


def _pedir(peticion: urllib.request.Request, tiempo_s: float = 120) -> Any:
    with urllib.request.urlopen(peticion, timeout=tiempo_s) as respuesta:
        return json.load(respuesta)


def sparql(consulta: str, pedir: Pedir = _pedir) -> list[dict[str, str]]:
    datos = urllib.parse.urlencode({"query": consulta, "format": "json"}).encode()
    peticion = urllib.request.Request(
        SPARQL,
        data=datos,
        headers={"User-Agent": AGENTE, "Accept": "application/sparql-results+json"},
    )
    for intento in range(4):
        try:
            filas = pedir(peticion)["results"]["bindings"]
            return [{k: v["value"] for k, v in fila.items()} for fila in filas]
        except Exception as error:  # el servicio de consultas se corta a veces: se reintenta
            if intento == 3:
                raise
            registro.warning("Wikidata: %r; se reintenta", error)
            time.sleep(10 * (intento + 1))
    return []


# --- Generar la tabla --------------------------------------------------------------------------
def _consulta_aeropuertos(oacis: list[str]) -> str:
    valores = " ".join(f'"{o}"' for o in oacis)
    return f"""SELECT ?icao ?item ?es ?en ?ciudad ?ces ?cen WHERE {{
 VALUES ?icao {{ {valores} }}
 ?item wdt:P239 ?icao .
 OPTIONAL {{ ?item rdfs:label ?es FILTER(lang(?es)="es") }}
 OPTIONAL {{ ?item rdfs:label ?en FILTER(lang(?en)="en") }}
 OPTIONAL {{ ?item wdt:P931 ?ciudad .
   OPTIONAL {{ ?ciudad rdfs:label ?ces FILTER(lang(?ces)="es") }}
   OPTIONAL {{ ?ciudad rdfs:label ?cen FILTER(lang(?cen)="en") }} }}
}}"""


def _consulta_localidades(ids: list[str]) -> str:
    valores = " ".join(f'"{i}"' for i in ids)
    return f"""SELECT ?gn ?item ?es ?en WHERE {{
 VALUES ?gn {{ {valores} }}
 ?item wdt:P1566 ?gn .
 OPTIONAL {{ ?item rdfs:label ?es FILTER(lang(?es)="es") }}
 OPTIONAL {{ ?item rdfs:label ?en FILTER(lang(?en)="en") }}
}}"""


def por_busqueda(
    datos: dict[str, list[Any]], ya: dict[str, Any], buscadas: dict[str, Any], pedir: Pedir
) -> dict[str, Any]:
    """Las ciudades de 10 km o más que faltan en la tabla (su número de GeoNames no está en
    Wikidata: Colonia, Zúrich, Palermo), buscadas por su nombre en su país. Vale si la etiqueta
    hallada es uno de sus nombres. `buscadas` guarda lo ya buscado para volver a generar."""
    salida: dict[str, Any] = {}
    for llave, (nombre, pais, _lat, _lon, radio, alias) in datos.items():
        gid = llave.split(":", 1)[1]
        if radio < 10 or gid in ya:
            continue
        if gid not in buscadas:
            try:
                buscadas[gid] = buscar(nombre, pais, pedir) or {}
            except Exception as error:
                registro.warning("%s sin buscar: %r", nombre, error)
                continue
            time.sleep(ESPERA_S)
        hallado = buscadas[gid]
        formas = _formas(nombre, alias)
        conocidas = {clave(f) for f in formas}
        if hallado and {clave(hallado["es"]), clave(hallado["en"])} & conocidas:
            salida[gid] = {"es": hallado["es"], "en": hallado["en"], "pais": pais, "formas": formas}
    return salida


def _ciudad(filas: list[dict[str, str]], etiqueta_en: str) -> Bilingue | None:
    """La ciudad a la que sirve el aeropuerto: la que nombra su etiqueta inglesa, si no la que
    no es una comarca, si no la primera."""
    ciudades = []
    for fila in filas:
        en = limpiar_etiqueta(fila.get("cen") or "")
        es = limpiar_etiqueta(fila.get("ces") or "") or en
        if en and latino_puro(en) and latino_puro(es):
            ciudades.append({"es": es, "en": en})
    if not ciudades:
        return None
    for ciudad in ciudades:
        if clave(ciudad["en"]) and clave(ciudad["en"]) in clave(etiqueta_en):
            return ciudad
    sin_comarca = [c for c in ciudades if not COMARCA.search(c["en"])]
    return (sin_comarca or ciudades)[0]


def _aeropuerto_es(etiqueta: str) -> str | None:
    """«Aeropuerto Internacional de Pafos» → «Aeropuerto de Pafos»."""
    etiqueta = limpiar_etiqueta(etiqueta)
    if not etiqueta.lower().startswith("aeropuerto") or not latino_puro(etiqueta):
        return None
    etiqueta = re.sub(r"^Aeropuerto\s+[Ii]nternacional\s+(?:de\s+)?", "Aeropuerto de ", etiqueta)
    return etiqueta[0].upper() + etiqueta[1:]


def aeropuertos(filas: list[dict[str, str]]) -> dict[str, Any]:
    """OACI -> {"aeropuerto": {es, en}, "base": {es, en}, "ciudad": {es, en}} a partir de las filas
    de Wikidata. En español, «Aeropuerto de <ciudad>» si es el único aeropuerto de su ciudad en la
    tabla o si el inglés es solo «<ciudad> Airport»; si la ciudad tiene varios, la etiqueta
    española limpia («Aeropuerto de Londres-Heathrow»)."""
    por_oaci: dict[str, dict[str, list[dict[str, str]]]] = defaultdict(lambda: defaultdict(list))
    for fila in filas:
        por_oaci[fila["icao"]][fila["item"]].append(fila)
    tabla: dict[str, Any] = {}
    for oaci, elementos in sorted(por_oaci.items()):
        entrada: dict[str, Any] = {"wikidata": sorted(i.rsplit("/", 1)[-1] for i in elementos)}
        for _item, filas_item in sorted(elementos.items()):
            en = limpiar_etiqueta(filas_item[0].get("en") or "")
            es = filas_item[0].get("es") or ""
            if not en or not latino_puro(en):
                continue
            ciudad = _ciudad(filas_item, en)
            if ciudad is not None and "ciudad" not in entrada:
                entrada["ciudad"] = ciudad
            if BASE_EN.search(en):
                es_base = re.sub(r"^Base A[ée]rea\b", "Base aérea", limpiar_etiqueta(es))
                if not (es_base.lower().startswith(("base", "raf ")) and latino_puro(es_base)):
                    es_base = en if en.startswith("RAF ") else ""
                entrada.setdefault("base", {"es": es_base, "en": en})
            else:
                entrada.setdefault("aeropuerto", {"es": _aeropuerto_es(es) or "", "en": en})
        if "aeropuerto" in entrada or "base" in entrada:
            tabla[oaci] = entrada
    # Ciudades con un solo aeropuerto en la tabla: «Aeropuerto de <ciudad>».
    cuantos: dict[str, int] = defaultdict(int)
    for entrada in tabla.values():
        if "ciudad" in entrada and "aeropuerto" in entrada:
            cuantos[entrada["ciudad"]["en"]] += 1
    for entrada in tabla.values():
        ciudad = entrada.get("ciudad")
        if ciudad is None:
            continue
        # «Málaga-Costa del Sol», «Toulouse-Blagnac»: sin «Airport», el nombre inglés de la ciudad.
        if "aeropuerto" in entrada and not re.search(
            r"\b(?:Airport|Aerodrome|Airfield|Airstrip)\b", entrada["aeropuerto"]["en"]
        ):
            entrada["aeropuerto"]["en"] = f"{ciudad['en']} Airport"
        # También si el inglés es solo «<ciudad> Airport»: las dos versiones nombran lo mismo
        # (salía «Aeropuerto de Hamburgo-Fuhlsbüttel» frente a «Hamburg Airport»).
        if "aeropuerto" in entrada and (
            cuantos[ciudad["en"]] == 1
            or not entrada["aeropuerto"]["es"]
            or entrada["aeropuerto"]["en"] == f"{ciudad['en']} Airport"
        ):
            entrada["aeropuerto"]["es"] = f"Aeropuerto de {ciudad['es']}"
        if "base" in entrada and not entrada["base"]["es"]:
            entrada["base"]["es"] = f"Base aérea de {ciudad['es']}"
    for oaci in list(tabla):
        for clase in ("aeropuerto", "base"):
            if clase in tabla[oaci] and not tabla[oaci][clase]["es"]:
                del tabla[oaci][clase]
        if "aeropuerto" not in tabla[oaci] and "base" not in tabla[oaci]:
            del tabla[oaci]
    return tabla


def _formas(nombre: str, alias: list[str]) -> list[str]:
    """Los nombres de la localidad que pueden salir en una fuente: los escritos en alfabeto
    latino, griego o cirílico que empiezan por mayúscula."""
    vistos: dict[str, str] = {}
    for forma in [nombre, *alias]:
        forma = forma.strip()
        if not forma or len(forma) > 40 or not forma[0].isupper():
            continue
        if not re.fullmatch(r"[\w\s'’.\-()]+", forma):
            continue
        if not nombres_lugar.escritura_conocida(forma):
            continue
        vistos.setdefault(clave(forma), forma)
    return sorted(vistos.values())


def localidades(filas: list[dict[str, str]], datos: dict[str, list[Any]]) -> dict[str, Any]:
    """Número de GeoNames -> {es, en, pais, formas}. Una etiqueta solo vale si es uno de los
    nombres de esa localidad en GeoNames; sin ninguna, no entra (se escribe con su nombre)."""
    tabla: dict[str, Any] = {}
    for fila in filas:
        gid = fila["gn"]
        if gid in tabla or f"loc:{gid}" not in datos:
            continue
        nombre, pais, _lat, _lon, _radio, alias = datos[f"loc:{gid}"][:6]
        formas = _formas(nombre, alias)
        es = limpiar_etiqueta(fila.get("es") or "")
        en = limpiar_etiqueta(fila.get("en") or "")
        # Si una de las dos etiquetas es el nombre de GeoNames de la localidad, el elemento es el
        # suyo y valen las dos; si no, Wikidata puede enlazar otro lugar («Lucentum» por
        # Alicante) y no se usa: queda el nombre local (y lo revisado a mano).
        if clave(nombre) not in {clave(es), clave(en)}:
            continue
        es = es if es and latino_puro(es) else ""
        en = en if en and latino_puro(en) else ""
        local = nombre if latino_puro(nombre) else ""
        es = es or en or local
        en = en or local or es
        tabla[gid] = {"es": es, "en": en, "pais": pais, "formas": formas}
    return dict(sorted(tabla.items(), key=lambda kv: int(kv[0])))


def formas_ajenas(
    tabla_localidades: dict[str, Any], datos: dict[str, list[Any]], radio_km: float = 10.0
) -> dict[str, Any]:
    """Por idioma de la página, las formas de las ciudades grandes que no son de esa versión y la
    que toca («Paphos» → «Pafos» en la española, «Varsovia» → «Warsaw» en la inglesa). Una forma
    que es el nombre español (o inglés) de cualquier localidad de la tabla no se toca, y tampoco
    la que llevaría a dos ciudades distintas. «paises»: el país de la ciudad de cada forma (en un
    lugar de otro país, la forma puede ser el nombre de otra localidad: «Biala» en Bulgaria)."""
    paises: dict[str, str] = {}
    nombres = {i: {e[i] for e in tabla_localidades.values()} for i in ("es", "en")}
    salida: dict[str, dict[str, str]] = {"es": {}, "en": {}}
    dudosas: dict[str, set[str]] = {"es": set(), "en": set()}
    for gid, entrada in tabla_localidades.items():
        if datos.get(f"loc:{gid}", [0] * 5)[4] < radio_km:
            continue
        for forma in {*entrada["formas"], entrada["es"], entrada["en"]}:
            if len(forma) < 4 or not forma[0].isupper() or not latino_puro(forma) or " " in forma:
                continue
            for idioma in ("es", "en"):
                if forma in nombres[idioma] or forma == entrada[idioma]:
                    continue
                anterior = salida[idioma].get(forma)
                if anterior is not None and anterior != entrada[idioma]:
                    dudosas[idioma].add(forma)
                salida[idioma][forma] = entrada[idioma]
                paises[forma] = entrada["pais"]
    resultado: dict[str, Any] = {
        i: dict(sorted((f, d) for f, d in salida[i].items() if f not in dudosas[i]))
        for i in ("es", "en")
    }
    resultado["paises"] = {
        f: paises[f] for f in sorted(set(resultado["es"]) | set(resultado["en"]))
    }
    return resultado


Filas = list[dict[str, str]]


def _consultar(filas: Path | None, pedir: Pedir) -> tuple[Filas, Filas]:
    """Las filas de Wikidata de los aeropuertos y de las localidades. Con `filas`, se guardan
    ahí (o se leen, si ya están) para volver a generar sin consultar."""
    if filas is not None and filas.exists():
        guardadas = json.loads(filas.read_text(encoding="utf-8"))
        return guardadas["aeropuertos"], guardadas["localidades"]
    lugares = json.loads((CONFIGURACION / "lugares_europa.json").read_text(encoding="utf-8"))
    oacis = sorted({v["oaci"] for v in lugares["lugares"].values() if v.get("oaci")})
    filas_a: list[dict[str, str]] = []
    for i in range(0, len(oacis), TROZO):
        filas_a += sparql(_consulta_aeropuertos(oacis[i : i + TROZO]), pedir)
        time.sleep(1)
    locs = _localidades_europa()
    ids = sorted(k.split(":", 1)[1] for k, v in locs.items() if v[4] >= RADIO_MINIMO_KM)
    filas_l: list[dict[str, str]] = []
    for i in range(0, len(ids), TROZO):
        filas_l += sparql(_consulta_localidades(ids[i : i + TROZO]), pedir)
        registro.info("localidades: %d de %d", min(i + TROZO, len(ids)), len(ids))
        time.sleep(1)
    if filas is not None:
        filas.write_text(
            json.dumps({"aeropuertos": filas_a, "localidades": filas_l}), encoding="utf-8"
        )
    return filas_a, filas_l


def _localidades_europa() -> dict[str, list[Any]]:
    datos = json.loads((CONFIGURACION / "localidades_europa.json").read_text(encoding="utf-8"))
    return dict(datos["localidades"])


def aplicar_manual(tabla_localidades: dict[str, Any], tabla_aeropuertos: dict[str, Any]) -> None:
    """Lo revisado a mano (localidades de nombres_lugar.json) manda también aquí: corrige las
    localidades generadas que nombra, la ciudad de sus aeropuertos y, con ella, el nombre
    español del aeropuerto («Aeropuerto de Resovia» → «Aeropuerto de Rzeszów»)."""
    revisadas: dict[tuple[str, str], Bilingue] = {}
    por_nombre: dict[str, list[Bilingue]] = defaultdict(list)
    for entrada in nombres_lugar.manual().get("localidades") or []:
        nombre: Bilingue = {"es": entrada["es"], "en": entrada["en"]}
        for forma in {*entrada.get("formas", []), entrada["es"], entrada["en"]}:
            revisadas[(entrada["pais"], clave(forma))] = nombre
        por_nombre[clave(entrada["en"])].append(nombre)
    for entrada in tabla_localidades.values():
        for forma in (entrada["en"], entrada["es"]):
            revisada = revisadas.get((entrada["pais"], clave(forma)))
            if revisada is not None:
                entrada.update(revisada)
                break
    for entrada in tabla_aeropuertos.values():
        ciudad = entrada.get("ciudad")
        if not ciudad or len(por_nombre.get(clave(ciudad["en"]), [])) != 1:
            continue
        nueva = por_nombre[clave(ciudad["en"])][0]
        aeropuerto = entrada.get("aeropuerto")
        if aeropuerto and aeropuerto["es"].startswith(f"Aeropuerto de {ciudad['es']}"):
            aeropuerto["es"] = (
                f"Aeropuerto de {nueva['es']}"
                + aeropuerto["es"][len(f"Aeropuerto de {ciudad['es']}") :]
            )
        base = entrada.get("base")
        if base and base["es"] == f"Base aérea de {ciudad['es']}":
            base["es"] = f"Base aérea de {nueva['es']}"
        entrada["ciudad"] = dict(nueva)


def generar(destino: Path = DESTINO, pedir: Pedir = _pedir, filas: Path | None = None) -> None:
    filas_a, filas_l = _consultar(filas, pedir)
    locs = _localidades_europa()
    tabla_localidades = localidades(filas_l, locs)
    buscadas_ruta = filas.with_suffix(".buscadas.json") if filas is not None else None
    buscadas = (
        json.loads(buscadas_ruta.read_text(encoding="utf-8"))
        if buscadas_ruta and buscadas_ruta.exists()
        else {}
    )
    tabla_localidades.update(por_busqueda(locs, tabla_localidades, buscadas, pedir))
    if buscadas_ruta is not None:
        buscadas_ruta.write_text(json.dumps(buscadas, ensure_ascii=False), encoding="utf-8")
    tabla_localidades = dict(sorted(tabla_localidades.items(), key=lambda kv: int(kv[0])))
    tabla_aeropuertos = aeropuertos(filas_a)
    aplicar_manual(tabla_localidades, tabla_aeropuertos)
    tabla = {
        "descripcion": (
            "Generado por recogida/nombres_wikidata.py (no se edita a mano: lo que haya que "
            "corregir va en nombres_lugar.json, que manda). Nombre español e inglés de los "
            "aeropuertos y bases con código OACI del vocabulario y de las localidades de 5 km de "
            "radio o más, con las formas con que las nombran las fuentes."
        ),
        "licencia": "Etiquetas de Wikidata (CC0); formas de GeoNames (CC BY 4.0)",
        "generado": datetime.now(UTC).strftime("%Y-%m-%d"),
        "aeropuertos": tabla_aeropuertos,
        "localidades": tabla_localidades,
        "formas_ajenas": formas_ajenas(tabla_localidades, locs),
    }
    # Comprimida, como localidades_pequenas.json.gz: son 1,6 MB de texto. Con mtime=0, el mismo
    # contenido da el mismo fichero.
    texto = json.dumps(tabla, ensure_ascii=False, indent=0) + "\n"
    destino.write_bytes(gzip.compress(texto.encode("utf-8"), mtime=0))


# --- Búsqueda de lo que falta (cada hora) -----------------------------------------------------
def _api(parametros: dict[str, str], pedir: Pedir, tiempo_s: float) -> Any:
    url = f"{API}?{urllib.parse.urlencode({**parametros, 'format': 'json'})}"
    peticion = urllib.request.Request(url, headers={"User-Agent": AGENTE})
    return pedir(peticion) if pedir is not _pedir else _pedir(peticion, tiempo_s)


def buscar(nombre: str, pais: str, pedir: Pedir = _pedir, tiempo_s: float = 8) -> Bilingue | None:
    """El nombre español e inglés de un lugar del país según Wikidata, o None. Busca el nombre en
    el idioma del país y en inglés y solo vale un elemento cuya etiqueta o alias es exactamente
    ese nombre («Vilniaus» no es la Universidad de Vilna), del país (P17) y con coordenadas
    (P625). Sin etiqueta española, el nombre local en alfabeto latino; sin él, el inglés."""
    qid_pais = PAISES_WIKIDATA.get(pais)
    if qid_pais is None:
        return None
    local = IDIOMA_PAIS.get(pais, "en")
    candidatos: list[str] = []
    for idioma in dict.fromkeys([local, "en"]):
        respuesta = _api(
            {"action": "wbsearchentities", "search": nombre, "language": idioma,
             "type": "item", "limit": "7"}, pedir, tiempo_s,
        )  # fmt: skip
        for resultado in respuesta.get("search", []):
            coincide = clave(str((resultado.get("match") or {}).get("text", ""))) == clave(nombre)
            if coincide and resultado["id"] not in candidatos:
                candidatos.append(resultado["id"])
    if not candidatos:
        return None
    entidades = _api(
        {"action": "wbgetentities", "ids": "|".join(candidatos[:14]), "props": "labels|claims",
         "languages": "|".join(dict.fromkeys(["es", "en", local]))}, pedir, tiempo_s,
    ).get("entities", {})  # fmt: skip
    for qid in candidatos[:14]:
        entidad = entidades.get(qid) or {}
        reclamaciones = entidad.get("claims") or {}
        paises = {
            ((r.get("mainsnak") or {}).get("datavalue") or {}).get("value", {}).get("id")
            for r in reclamaciones.get("P17", [])
        }
        if qid_pais not in paises or "P625" not in reclamaciones:
            continue
        etiquetas = entidad.get("labels") or {}
        en, es, propio = (
            limpiar_etiqueta((etiquetas.get(i) or {}).get("value", "")) for i in ("en", "es", local)
        )
        en, es, propio = (e if e and latino_puro(e) else "" for e in (en, es, propio))
        if not (en or es or propio):
            continue
        return {"es": es or propio or en, "en": en or propio or es}
    return None


def leer_cache(ruta: Path) -> dict[str, Any]:
    try:
        datos = json.loads(ruta.read_text(encoding="utf-8"))
        return datos if isinstance(datos, dict) else {}
    except (OSError, ValueError):
        return {}


def escribir_cache(ruta: Path, datos: dict[str, Any]) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    temporal = ruta.with_suffix(".tmp")
    temporal.write_text(
        json.dumps(datos, ensure_ascii=False, indent=1, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    temporal.replace(ruta)


def completar(
    incidentes: list[dict[str, Any]],
    ahora: datetime,
    ruta: Path | None = None,
    pedir: Pedir = _pedir,
    reloj: Callable[[], float] = time.monotonic,
) -> int:
    """Busca en Wikidata los nombres de lugar de los incidentes que no están en las tablas y los
    guarda en la caché. Devuelve cuántos ha buscado. Nunca lanza: un fallo deja el resto."""
    ruta = ruta or nombres_lugar.ruta_cache()
    cache = leer_cache(ruta)
    pendientes = nombres_lugar.sin_resolver(incidentes, cache, ahora - REINTENTO_NO_ENCONTRADO)
    inicio = reloj()
    hechos = 0
    for pais, nombre in pendientes[:MAX_BUSQUEDAS]:
        if reloj() - inicio > TOPE_S:
            break
        try:
            encontrado = buscar(nombre, pais, pedir)
        except Exception as error:
            registro.warning("Wikidata no responde (%r): se buscará en la próxima pasada", error)
            break
        cache[nombres_lugar.clave_cache(pais, nombre)] = {
            "nombre": nombre,
            "pais": pais,
            "buscado": ahora.strftime("%Y-%m-%dT%H:%MZ"),
            **({"es": encontrado["es"], "en": encontrado["en"]} if encontrado else {}),
        }
        hechos += 1
        time.sleep(ESPERA_S)
    if hechos:
        escribir_cache(ruta, cache)
        nombres_lugar.olvidar_cache()
    return hechos


def paso_horario(almacen: Any, ahora: datetime | None = None) -> int:
    """El paso de la recogida horaria: completa la caché con los incidentes de la base."""
    publicables = [
        i for i in almacen.incidentes() if "retirado" not in i and "fusionado_en" not in i
    ]
    return completar(publicables, ahora or datetime.now(UTC))


def principal(argumentos: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    analizador = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    analizador.add_argument("orden", choices=["generar"])
    analizador.add_argument(
        "--filas", type=Path, help="fichero donde guardar (o de donde leer) las filas de Wikidata"
    )
    args = analizador.parse_args(argumentos)
    generar(filas=args.filas)
    return 0


if __name__ == "__main__":
    sys.exit(principal())
