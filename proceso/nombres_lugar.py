"""Los nombres de lugar de la web, en español y en inglés.

La web tiene dos idiomas. Todo nombre de lugar sale en su forma española habitual en la versión
española (Pafos, Lárnaca, Varsovia, Bucarest, Kiev) y en la inglesa en la versión inglesa (Paphos,
Larnaca, Warsaw, Bucharest, Kyiv). Sin forma propia, el nombre local en alfabeto latino tal como lo
escribe la prensa. Nunca una transliteración académica, nunca el alfabeto original y nunca un
tercer idioma. Los aeropuertos, «Aeropuerto de X» / «X Airport» (o su nombre inglés habitual,
«Paphos International Airport»); las bases, por su nombre corriente en prensa (RAF Akrotiri).

De dónde salen, por orden (manda lo primero que se encuentra):
1. configuracion/nombres_lugar.json, revisado a mano: textos tal como los guarda la ficha
   («Portul Constanța», «Kardam (Dobrich), junto al antiguo paso…»), aeropuertos, localidades,
   mares, países y territorios.
2. configuracion/nombres_lugar_wikidata.json.gz, generado de Wikidata
   (recogida/nombres_wikidata.py): aeropuertos y bases por código OACI y localidades por su
   número de GeoNames.
3. La caché de lo buscado en Wikidata cada hora (EODI_NOMBRES_CACHE).
4. La regla: un nombre en alfabeto latino sin palabras de otro idioma se deja como está; si no, la
   localidad del aeropuerto o el país. Nunca impide publicar.

`nombres_publicos` da lo que se publica de cada incidente (el campo `nombres` de los ficheros de
la web) y `titulo_corregido` el titular con esos nombres; `problemas` es la revisión que comprueba
cualquier texto visible (la usan la publicación, para no sacar nada mal escrito, y las pruebas
sobre los datos publicados).
"""

import gzip
import json
import os
import re
import unicodedata
from collections import defaultdict
from collections.abc import Iterable
from datetime import datetime
from functools import cache
from pathlib import Path
from typing import Any

from esquema import Documento

CONFIGURACION = Path(__file__).resolve().parent.parent / "configuracion"
MANUAL = CONFIGURACION / "nombres_lugar.json"
GENERADO = CONFIGURACION / "nombres_lugar_wikidata.json.gz"
VARIABLE_CACHE = "EODI_NOMBRES_CACHE"
IDIOMAS = ("es", "en")


# Un nombre en las dos versiones de la web: {"es": …, "en": …}.
Bilingue = dict[str, str]


# --- Escritura -------------------------------------------------------------------------------
def _escrituras(texto: str) -> set[str]:
    """Las escrituras de las letras del texto: LATIN, GREEK, CYRILLIC…"""
    return {unicodedata.name(c, "?").split(" ")[0] for c in texto if c.isalpha()}


def latino_puro(texto: str) -> bool:
    """Si todas las letras son del alfabeto latino (y hay alguna)."""
    escrituras = _escrituras(texto)
    return escrituras == {"LATIN"}


def escritura_conocida(texto: str) -> bool:
    """Si el texto va entero en alfabeto latino, griego o cirílico."""
    escrituras = _escrituras(texto)
    return len(escrituras) == 1 and escrituras <= {"LATIN", "GREEK", "CYRILLIC"}


def clave(texto: str) -> str:
    """Para comparar nombres: sin tildes, en minúsculas, sin guiones ni signos."""
    plano = unicodedata.normalize("NFKD", texto)
    plano = "".join(c for c in plano if not unicodedata.combining(c)).casefold()
    plano = plano.replace("ł", "l").replace("ø", "o").replace("đ", "d").replace("ß", "ss")
    return " ".join(re.findall(r"\w+", plano))


_PREFIJOS_ETIQUETA = re.compile(
    r"^(?:Ciudad de|ciudad de|City of|Municipio de|municipio de|Distrito municipal de|Comune di)\s+"
)
_SUFIJOS_ETIQUETA = re.compile(
    r"\s+(?:city|City|Municipality|municipality|Municipal Unit|district|eldership|Town|town)$"
)


_ACLARACIONES = frozenset({
    "city", "ciudad", "town", "municipality", "municipio", "comune", "gemeinde", "village",
    "pueblo", "localidad", "settlement", "commune",
})  # fmt: skip


def _aclaracion(texto: str) -> str:
    """El paréntesis que aclara qué es o de qué país es («(city)», «(Portugal)») se quita; el
    que forma parte del nombre («Frankfurt (Oder)», «Halle (Saale)») se queda."""
    contenido = clave(texto.strip("() "))
    paises = {clave(n) for p in (manual().get("paises") or {}).values() for n in (p["es"], p["en"])}
    return "" if contenido in _ACLARACIONES or contenido in paises else texto


def limpiar_etiqueta(etiqueta: str) -> str:
    """«Ciudad de Sevilla» → «Sevilla», «Faro (Portugal)» → «Faro», «Seville city» → «Seville»."""
    etiqueta = re.sub(r"\s*\([^)]*\)", lambda m: _aclaracion(m.group(0)), etiqueta).strip()
    etiqueta = _PREFIJOS_ETIQUETA.sub("", etiqueta)
    etiqueta = _SUFIJOS_ETIQUETA.sub("", etiqueta)
    return " ".join(etiqueta.split())


# --- Tablas ----------------------------------------------------------------------------------
def _leer(ruta: Path) -> Documento:
    try:
        crudo = gzip.decompress(ruta.read_bytes()) if ruta.suffix == ".gz" else ruta.read_bytes()
        datos = json.loads(crudo.decode("utf-8"))
    except (OSError, ValueError):
        return {}
    return datos if isinstance(datos, dict) else {}


def ruta_cache() -> Path:
    return Path(os.environ.get(VARIABLE_CACHE) or Path.home() / ".eodi" / "nombres_lugar.json")


def clave_cache(pais: str, nombre: str) -> str:
    return f"{pais}:{clave(nombre)}"


@cache
def _cache() -> Documento:
    return _leer(ruta_cache())


def olvidar_cache() -> None:
    _cache.cache_clear()


@cache
def manual() -> Documento:
    return _leer(MANUAL)


@cache
def generado() -> Documento:
    return _leer(GENERADO)


def _bilingue(valor: Any) -> Bilingue | None:
    if isinstance(valor, dict) and all(isinstance(valor.get(i), str) and valor[i] for i in IDIOMAS):
        return {"es": valor["es"], "en": valor["en"]}
    return None


@cache
def _localidades() -> tuple[dict[tuple[str, str], Bilingue], dict[str, list[tuple[str, Bilingue]]]]:
    """(país, clave de una forma) -> nombre, y clave -> [(país, nombre)] para buscar fuera del
    país del incidente (un lugar del país vecino que nombra la ficha). Lo manual manda."""
    por_pais: dict[tuple[str, str], Bilingue] = {}
    global_: dict[str, list[tuple[str, Bilingue]]] = defaultdict(list)
    entradas = list((generado().get("localidades") or {}).values())
    entradas += list(manual().get("localidades") or [])
    for entrada in entradas:
        nombre = _bilingue(entrada)
        pais = entrada.get("pais", "")
        if nombre is None:
            continue
        for forma in {*entrada.get("formas", []), nombre["es"], nombre["en"]}:
            k = clave(forma)
            if not k:
                continue
            por_pais[(pais, k)] = nombre
            global_[k] = [(p, n) for p, n in global_[k] if p != pais] + [(pais, nombre)]
    return por_pais, dict(global_)


@cache
def _mares() -> dict[str, Bilingue]:
    salida: dict[str, Bilingue] = {}
    for entrada in manual().get("mares") or []:
        nombre = _bilingue(entrada)
        if nombre is not None:
            for forma in {*entrada.get("formas", []), nombre["es"], nombre["en"]}:
                salida[clave(forma)] = nombre
    return salida


def nfc(texto: str) -> str:
    """Las fuentes escriben a veces las tildes como signo aparte («César» con la «e» y la tilde
    sueltas): para comparar con las tablas, siempre en su forma compuesta."""
    return unicodedata.normalize("NFC", texto)


def _nfc_documento(valor: Any) -> Any:
    if isinstance(valor, str):
        return nfc(valor)
    if isinstance(valor, list):
        return [_nfc_documento(v) for v in valor]
    if isinstance(valor, dict):
        return {k: _nfc_documento(v) for k, v in valor.items()}
    return valor


def _nfc_incidente(incidente: Documento) -> Documento:
    """El incidente con el lugar, el objetivo y el titular en forma compuesta."""
    return {
        **incidente,
        **{
            c: _nfc_documento(incidente[c])
            for c in ("lugar", "objetivo", "titulo")
            if c in incidente
        },
    }


@cache
def _textos() -> dict[str, Any]:
    return {nfc(k): v for k, v in (manual().get("textos") or {}).items()}


def textos() -> dict[str, Any]:
    return _textos()


def pais_escrito(codigo: str) -> Bilingue:
    nombre = _bilingue((manual().get("paises") or {}).get(codigo))
    return nombre or {"es": codigo, "en": codigo}


# --- Palabras de otro idioma ------------------------------------------------------------------
@cache
def _ajenas() -> dict[str, re.Pattern[str]]:
    """Por idioma de la página, las palabras que delatan un nombre en otro idioma: las de un
    tercer idioma valen para las dos versiones; las inglesas, para la española, y al revés."""
    palabras = manual().get("palabras_ajenas") or {}
    terceras = list(palabras.get("tercer_idioma", []))
    salida = {}
    for idioma, otro in (("es", "ingles"), ("en", "espanol")):
        lista = sorted({*terceras, *palabras.get(otro, [])}, key=len, reverse=True)
        cuerpo = "|".join(re.escape(p) for p in lista) or "(?!)"
        salida[idioma] = re.compile(rf"(?<!\w)(?:{cuerpo})(?!\w)")
    return salida


@cache
def _formas_ajenas() -> dict[str, dict[str, str]]:
    """Por idioma, las formas de nombre de ciudad que no son de esa versión, con la que toca:
    en la española, «Paphos» → «Pafos», «Warschau» → «Varsovia»; en la inglesa, «Varsovia» →
    «Warsaw». Generadas con la tabla de Wikidata (formas_ajenas) y las de la tabla manual."""
    generadas = generado().get("formas_ajenas") or {}
    salida: dict[str, dict[str, str]] = {i: dict(generadas.get(i) or {}) for i in IDIOMAS}
    duenos = dict(generadas.get("paises") or {})
    # Los países: el nombre del otro idioma y los nombres locales («România», «Deutschland»).
    for pais in (manual().get("paises") or {}).values():
        for forma in [pais["en"], *pais.get("formas", [])]:
            if forma != pais["es"] and forma not in pais.get("validas_es", []):
                salida["es"][forma] = pais["es"]
        for forma in [pais["es"], *pais.get("formas", [])]:
            if forma != pais["en"] and forma not in pais.get("validas_en", []):
                salida["en"][forma] = pais["en"]
    # Las ciudades revisadas a mano (Kiev, Constanza, Moscú…): sus otras formas, si no son el
    # nombre de ninguna localidad en esa versión.
    locales = list((generado().get("localidades") or {}).values()) + list(
        manual().get("localidades") or []
    )
    validos = {i: {e[i] for e in locales} for i in IDIOMAS}
    for entrada in manual().get("localidades") or []:
        for forma in {*entrada.get("formas", []), entrada["es"], entrada["en"]}:
            if len(forma) < 4 or not latino_puro(forma):
                continue
            for idioma in IDIOMAS:
                if forma != entrada[idioma] and forma not in validos[idioma]:
                    salida[idioma][forma] = entrada[idioma]
                    duenos[forma] = entrada["pais"]
    for idioma in IDIOMAS:
        salida[idioma].update((manual().get("formas_ajenas") or {}).get(idioma) or {})
    _DUENOS.clear()
    _DUENOS.update(duenos)
    return salida


# País de la ciudad de cada forma ajena (lo rellena _formas_ajenas).
_DUENOS: dict[str, str] = {}


def _alternativas(formas: Iterable[str]) -> re.Pattern[str]:
    lista = sorted(set(formas), key=len, reverse=True)
    cuerpo = "|".join(re.escape(f) for f in lista) or "(?!)"
    return re.compile(rf"(?<![\w-])(?:{cuerpo})(?![\w-])")


@cache
def _patron_formas(idioma: str) -> re.Pattern[str]:
    return _alternativas(_formas_ajenas()[idioma])


def palabras_ajenas(texto: str, idioma: str) -> list[str]:
    return _ajenas()[idioma].findall(texto)


def formas_ajenas(texto: str, idioma: str, pais: str | None = None) -> list[str]:
    """Las formas de nombre de ciudad del texto que no son de la versión `idioma`. Con `pais`
    (el del lugar), solo las de ciudades de ese país: «Biala» es una aldea búlgara, no la forma
    sin tilde de Bielsko-Biała."""
    tabla = _formas_ajenas()[idioma]
    return [
        m.group(0)
        for m in _patron_formas(idioma).finditer(texto)
        if not _ya_dice(texto, m.start(), tabla[m.group(0)])
        and (pais is None or _DUENOS.get(m.group(0), pais) == pais)
    ]


def _aceptable(texto: str, idioma: str) -> bool:
    return latino_puro(texto) and not palabras_ajenas(texto, idioma)


# --- Lugares ---------------------------------------------------------------------------------
# Lo que la ficha añade al nombre («Tudora (raionul Ștefan Vodă)», «Rēzekne, depósito de
# petróleo», «Unos 10 km al ONO de Sfântu Gheorghe»): fuera, queda el nombre.
_DISTANCIA = re.compile(r"^(?:a\s+)?unos?\s+\d+(?:[.,]\d+)?\s*km\s+al\s+\w+\s+de\s+", re.I)
_ENTRE = re.compile(r"^entre\s+(.+?)\s+y\s+(.+?)(?:\s*[,(].*)?$", re.I)
_CORTE = re.compile(r"\s*(?:\(|,|/|;|\s[–—-]\s).*$")


# Palabras propias del español (no de otras lenguas latinas): en un lugar de fuera de España
# delatan una descripción que escribió la ficha («Regimiento de Dragones de Jutlandia»), no el
# nombre del lugar («Cuhureștii de Jos», «Marche-en-Famenne» sí son nombres).
_ESPANOL = re.compile(
    r"(?<![\w'’-])(?:y|los|las|junto|cerca|entre|hacia|donde|unos|unas|segundo|tercer|primer|"
    r"explosión|extrarradio|restos|regimiento|cuartel|aeropuerto|base aérea|distrito|municipio|"
    r"provincia|región|frente)(?![\w'’-])",
    re.IGNORECASE,
)


def nombre_base(texto: str) -> str:
    texto = _DISTANCIA.sub("", texto.strip())
    return _CORTE.sub("", texto).strip(" .«»\"'")


# «Puerto de X», «Port of X», «Aeropuerto de X»: el nombre genérico de una instalación.
_GENERICO = re.compile(
    r"^(?:puerto|aeropuerto|base aérea|base|central|port|airport|air base|harbour|harbor)"
    r"(?:\s+(?:de|del|of|de la))?\s+(?P<x>.+)$",
    re.IGNORECASE,
)


def traduccion_inventada(base: str, escrito: Bilingue) -> bool:
    """Un nombre de instalación traducido que no lleva su nombre propio: «Puerto de Ems» por
    «Eemshaven» (Wikidata, 20 de octubre de 2026). Los nombres propios de puertos, aeropuertos,
    bases y centrales no se traducen (Eemshaven, Schiphol); los exónimos de las ciudades salen
    de las tablas."""
    palabras = set(clave(base).split())
    for texto in escrito.values():
        generico = _GENERICO.match(texto)
        if generico and not set(clave(generico.group("x")).split()) <= palabras:
            return True
    return False


def _en_tablas(base: str, pais: str, en_otro_pais: bool = False) -> Bilingue | None:
    k = clave(base)
    if not k:
        return None
    por_pais, global_ = _localidades()
    if (pais, k) in por_pais:
        return por_pais[(pais, k)]
    if k in _mares():
        return _mares()[k]
    guardado = _cache().get(clave_cache(pais, base))
    escrito = _bilingue(guardado) if isinstance(guardado, dict) else None
    if escrito is not None and not traduccion_inventada(base, escrito):
        return escrito
    if en_otro_pais and len(global_.get(k, [])) == 1:
        return global_[k][0][1]
    return None


def lugar(texto: str | None, pais: str) -> Bilingue | None:
    """Un nombre de lugar de la ficha (localidad, región, otro lugar) en los dos idiomas, o None
    si no se puede escribir bien (una descripción, otro alfabeto sin nombre conocido)."""
    if not texto:
        return None
    texto = nfc(texto)
    escritos = textos()
    if texto in escritos:
        return _bilingue(escritos[texto])
    entre = _ENTRE.match(texto)
    if entre:
        a, b = lugar(entre.group(1), pais), lugar(entre.group(2), pais)
        if a is not None and b is not None:
            return {"es": f"entre {a['es']} y {b['es']}", "en": f"between {a['en']} and {b['en']}"}
    base = nombre_base(texto)
    if base in escritos:
        return _bilingue(escritos[base])
    encontrado = _en_tablas(base, pais)
    if encontrado is not None:
        return encontrado
    if not base or not base[0].isupper():
        return None
    if all(_aceptable(base, i) for i in IDIOMAS) and not (pais != "ES" and _ESPANOL.search(base)):
        return {"es": base, "en": base}
    return None


@cache
def _instalaciones() -> list[tuple[re.Pattern[str], Bilingue]]:
    """Patrones de nombre de instalación en otro idioma y cómo se escriben («Flughafen X» →
    «Aeropuerto de X» / «X Airport»), de la tabla manual."""
    salida = []
    for entrada in manual().get("instalaciones") or []:
        plantilla = _bilingue(entrada.get("plantilla"))
        if plantilla is not None:
            salida.append((re.compile(entrada["patron"]), plantilla))
    return salida


def _aeropuerto(oaci: str) -> Documento:
    entrada = dict((generado().get("aeropuertos") or {}).get(oaci) or {})
    entrada.update((manual().get("aeropuertos") or {}).get(oaci) or {})
    return entrada


def ciudad_de_aeropuerto(oaci: str | None) -> Bilingue | None:
    return _bilingue(_aeropuerto(oaci).get("ciudad")) if oaci else None


def _instalacion(nombre: str, pais: str) -> tuple[Bilingue, Bilingue] | None:
    """Un nombre de instalación en otro idioma («Flughafen X», «Vliegbasis X», «X lufthavn»):
    cómo se escribe en cada versión y el lugar que nombra (X)."""
    for patron, plantilla in _instalaciones():
        encontrado = patron.match(nombre)
        if encontrado:
            sitio_ = lugar(nombre_base(encontrado.group("x").strip()), pais)
            if sitio_ is not None:
                escrito: Bilingue = {
                    "es": plantilla["es"].format(x=sitio_["es"]),
                    "en": plantilla["en"].format(x=sitio_["en"]),
                }
                return escrito, sitio_
    return None


def objetivo(datos: Documento | None, pais: str) -> Bilingue | None:
    """El nombre del aeropuerto, la base o la instalación, o None si no se puede escribir bien
    (la ficha enseña entonces el titular)."""
    if not datos:
        return None
    nombre = nfc(str(datos.get("nombre") or ""))
    escritos = textos()
    if nombre in escritos:
        return _bilingue(escritos[nombre])
    oaci = datos.get("oaci")
    if oaci:
        entrada = _aeropuerto(oaci)
        ciudad = _bilingue(entrada.get("ciudad"))
        clases = (
            ("base", "aeropuerto")
            if datos.get("categoria") == "base_militar"
            else ("aeropuerto", "base")
        )
        for clase in clases:
            escrito = _bilingue(entrada.get(clase))
            if escrito is not None:
                if clase == "aeropuerto" and clases[0] == "base" and ciudad is not None:
                    escrito = {
                        "es": f"Base aérea de {ciudad['es']}",
                        "en": f"{ciudad['en']} Air Base",
                    }
                # «Liege Airport» → «Liège Airport», «Hannover Airport» → «Hanover Airport»: el
                # nombre de la ciudad como en el resto de la página.
                return {
                    "es": corregir_texto(escrito["es"], {}, "es"),
                    "en": corregir_texto(escrito["en"], {}, "en"),
                }
    instalacion = _instalacion(nombre, pais)
    if instalacion is not None:
        return instalacion[0]
    if not nombre:
        return None
    sitio = lugar(nombre, pais)
    if sitio is not None and nombre_base(nombre) == nombre:
        return sitio
    return None


# --- Territorios -----------------------------------------------------------------------------
def territorio(incidente: Documento) -> Documento | None:
    """El territorio fuera del país en que pasó (Gibraltar, Akrotiri, Reunión, Svalbard…): por el
    punto, dentro de su caja, o por el nombre del lugar; solo si el país de los datos es el suyo."""
    lugar_ = incidente.get("lugar") or {}
    pais = lugar_.get("pais", "")
    punto = lugar_.get("punto")
    nombres = [lugar_.get(c) for c in ("localidad", "region", "suceso")]
    nombres.append((incidente.get("objetivo") or {}).get("nombre"))
    claves = [clave(str(n)) for n in nombres if n]
    for codigo, datos in (manual().get("territorios") or {}).items():
        if datos.get("pais") != pais and codigo != pais:
            continue
        caja = datos.get("caja")
        if punto and caja:
            oeste, sur, este, norte = caja
            if oeste <= punto["lon"] <= este and sur <= punto["lat"] <= norte:
                return {"codigo": codigo, **datos}
            continue
        formas = [clave(f) for f in datos.get("formas", [])]
        if codigo == pais or any(
            f and re.search(rf"\b{re.escape(f)}\b", k) for f in formas for k in claves
        ):
            return {"codigo": codigo, **datos}
    return None


def _con_pais(sitio: Bilingue | None, pais: str, terr: Documento | None) -> Bilingue:
    if terr is None:
        nombre = pais_escrito(pais)
        if sitio is None or clave(sitio["es"]) == clave(nombre["es"]):
            return nombre
        return {i: f"{sitio[i]}, {nombre[i]}" for i in IDIOMAS}
    padre = pais_escrito(terr["pais"])
    propio = _bilingue(terr) or padre
    if terr.get("forma") == "base":
        geografico = pais_escrito(terr["geografico"])
        etiqueta = _bilingue(terr.get("etiqueta")) or {"es": "base", "en": "base"}
        nombre_sitio = sitio or propio
        return {i: f"{nombre_sitio[i]} ({etiqueta[i]}), {geografico[i]}" for i in IDIOMAS}
    entero = {i: f"{propio[i]} ({padre[i]})" for i in IDIOMAS}
    if sitio is None or clave(sitio["es"]) == clave(propio["es"]):
        return entero
    return {i: f"{sitio[i]}, {entero[i]}" for i in IDIOMAS}


def lugar_con_pais(sitio_: Bilingue | None, incidente: Documento) -> Bilingue:
    """Lo que dice la fila «Lugar»: «Pafos, Chipre», «RAF Akrotiri (base británica), Chipre»,
    «Gibraltar (Reino Unido)», «Saint-Denis, Reunión (Francia)»."""
    pais = (incidente.get("lugar") or {}).get("pais", "")
    return _con_pais(sitio_, pais, territorio(incidente))


def sitio(incidente: Documento) -> Bilingue | None:
    """La localidad (o el lugar concreto) que va delante del país en «Lugar»: la de la ficha; si
    no la hay, la ciudad del aeropuerto, el lugar que nombra el objetivo o, sin punto, la región."""
    lugar_ = incidente.get("lugar") or {}
    pais = lugar_.get("pais", "")
    objetivo_ = incidente.get("objetivo") or {}
    nombre_objetivo = str(objetivo_.get("nombre") or "")
    instalacion = _instalacion(nombre_objetivo, pais)
    raf = re.match(r"^(?:RAF|Royal Air Force(?: Station)?)\s+(.+)$", nombre_objetivo)
    escrito = textos().get(nombre_objetivo)
    # Un objetivo que es solo el nombre de un lugar («Mechernich», «Doel», «Chilia Veche»).
    simple = (
        nombre_objetivo
        if nombre_objetivo and nombre_base(nombre_objetivo) == nombre_objetivo
        else None
    )
    en_localidad = _instalacion(nombre_base(str(lugar_.get("localidad") or "")), pais)
    candidatos = [
        lugar(lugar_.get("localidad"), pais),
        en_localidad[1] if en_localidad is not None else None,
        _bilingue(escrito.get("sitio")) if isinstance(escrito, dict) else None,
        ciudad_de_aeropuerto(objetivo_.get("oaci")),
        _en_tablas(nombre_objetivo, pais, en_otro_pais=False),
        instalacion[1] if instalacion is not None else None,
        lugar(raf.group(1), pais) if raf else None,
        lugar(simple, pais) if simple and escrito is None and not objetivo_.get("oaci") else None,
    ]
    if "punto" not in lugar_ and incidente.get("lon") is None:
        candidatos.append(lugar(lugar_.get("region"), pais))
    return next((c for c in candidatos if c is not None), None)


def nombres_publicos(incidente: Documento) -> Documento:
    """El campo `nombres` publicado: «lugar» (lo que dice la fila «Lugar», con el país o el
    territorio), «localidad», «objetivo», «region», «otros» y «anteriores» (en el orden de la
    ficha; null donde no se puede escribir) y, si no es el de los datos, «pais_geografico»."""
    incidente = _nfc_incidente(incidente)
    lugar_ = incidente.get("lugar") or {}
    pais = lugar_.get("pais", "")
    terr = territorio(incidente)
    sitio_ = sitio(incidente)
    salida: Documento = {"lugar": lugar_con_pais(sitio_, incidente)}
    if sitio_ is not None:
        salida["localidad"] = sitio_
    nombre_objetivo = objetivo(incidente.get("objetivo"), pais)
    if nombre_objetivo is not None:
        salida["objetivo"] = nombre_objetivo
    region = lugar(lugar_.get("region"), pais)
    if region is not None:
        salida["region"] = region
    otros = lugar_.get("otros_lugares") or []
    if otros:
        salida["otros"] = [lugar(o.get("nombre"), pais) for o in otros]
    anteriores = lugar_.get("historial") or []
    if anteriores:
        salida["anteriores"] = [
            lugar((h.get("anterior") or {}).get("localidad"), pais) for h in anteriores
        ]
    if terr is not None:
        salida["pais_geografico"] = terr.get("geografico") or terr["codigo"]
    return salida


# --- Titulares -------------------------------------------------------------------------------
def _cambios(incidente: Documento, idioma: str) -> dict[str, str]:
    """Formas que hay que cambiar en el titular, además de las ajenas generales: las de los
    lugares del propio incidente (el nombre de la ficha por el de la tabla)."""
    cambios: dict[str, str] = {}
    lugar_ = incidente.get("lugar") or {}
    pais = lugar_.get("pais", "")
    pares = [(lugar_.get("localidad"), lugar(lugar_.get("localidad"), pais))]
    pares.append((lugar_.get("region"), lugar(lugar_.get("region"), pais)))
    pares += [
        (o.get("nombre"), lugar(o.get("nombre"), pais)) for o in lugar_.get("otros_lugares") or []
    ]
    # El objetivo con su nombre en otro idioma («Alta lufthavn», «Flughafen München»).
    objetivo_ = incidente.get("objetivo") or {}
    nombre_objetivo = objetivo_.get("nombre")
    escrito_objetivo = objetivo(objetivo_, pais) if nombre_objetivo else None
    if (
        nombre_objetivo
        and escrito_objetivo is not None
        and escrito_objetivo[idioma] != nombre_objetivo
        and problemas_texto(str(nombre_objetivo), idioma, pais)
    ):
        destino = escrito_objetivo[idioma]
        if idioma == "es" and re.match(
            r"^(?:Aeropuerto|Base|Central|Puerto|Muelle|Estación)\b", destino
        ):
            destino = destino[0].lower() + destino[1:]
            cambios[f"de {nombre_objetivo}"] = f"del {destino}"
            cambios[f"en {nombre_objetivo}"] = f"en el {destino}"
        cambios[str(nombre_objetivo)] = destino
    for original, escrito in pares:
        if not original or escrito is None:
            continue
        base = nombre_base(str(original))
        otro = "en" if idioma == "es" else "es"
        for forma in {base, escrito[otro]}:
            if forma and forma != escrito[idioma] and len(forma) >= 4 and forma[0].isupper():
                cambios[forma] = escrito[idioma]
    return cambios


def _sustituir(tabla: dict[str, str]) -> Any:
    """La sustitución de una forma por la que toca, salvo si el texto ya la dice bien ahí
    («Palma de Mallorca» no pasa a «Palma de Mallorca de Mallorca»)."""

    def sustituir(encontrado: re.Match[str]) -> str:
        destino = tabla[encontrado.group(0)]
        return (
            encontrado.group(0)
            if _ya_dice(encontrado.string, encontrado.start(), destino)
            else destino
        )

    return sustituir


def _ya_dice(texto: str, inicio: int, destino: str) -> bool:
    """Si el texto ya dice `destino` entero en esa posición («Palma de Mallorca»; no «Drone»
    por «Dron»)."""
    fin = inicio + len(destino)
    return texto.startswith(destino, inicio) and (fin == len(texto) or not texto[fin].isalnum())


def corregir_texto(texto: str, cambios: dict[str, str], idioma: str | None = None) -> str:
    """El texto con cada forma ajena cambiada por la de la página (y, con `idioma`, también las
    formas ajenas generales de las ciudades conocidas)."""
    if idioma is not None:
        texto = _patron_formas(idioma).sub(_sustituir(_formas_ajenas()[idioma]), texto)
    if not cambios:
        return texto
    return _alternativas(cambios).sub(_sustituir(cambios), texto)


def titulo_corregido(incidente: Documento) -> Documento:
    incidente = _nfc_incidente(incidente)
    titulo = incidente.get("titulo") or {}
    return {
        i: corregir_texto(str(titulo[i]), _cambios(incidente, i), i)
        if i in IDIOMAS and isinstance(titulo.get(i), str)
        else titulo.get(i)
        for i in titulo
    }


# --- Revisión de lo visible -----------------------------------------------------------------
def problemas_texto(texto: str, idioma: str, pais: str | None = None) -> list[str]:
    """Lo que está mal en un texto visible de la página en `idioma`."""
    texto = nfc(texto)
    salida = []
    otras = _escrituras(texto) - {"LATIN"}
    if otras:
        salida.append(f"otro alfabeto ({', '.join(sorted(otras))})")
    for palabra in palabras_ajenas(texto, idioma):
        salida.append(f"palabra de otro idioma «{palabra}»")
    for forma in dict.fromkeys(formas_ajenas(texto, idioma, pais)):
        salida.append(f"«{forma}» en vez de «{_formas_ajenas()[idioma][forma]}»")
    return salida


def problemas(propiedades: Documento) -> list[str]:
    """Revisión de los nombres y titulares publicados de un incidente (las propiedades de los
    ficheros publicados): lo que la ficha enseñaría mal escrito en una de las dos versiones."""
    salida = []
    nombres = propiedades.get("nombres") or {}
    lugar_ = propiedades.get("lugar") or {}
    textos_visibles: list[tuple[str, Any]] = [("titulo", propiedades.get("titulo"))]
    for campo in ("lugar", "localidad", "objetivo", "region"):
        textos_visibles.append((f"nombres.{campo}", nombres.get(campo)))
    for i, otro in enumerate(nombres.get("otros") or []):
        textos_visibles.append((f"nombres.otros[{i}]", otro))
    for i, otro in enumerate(nombres.get("anteriores") or []):
        textos_visibles.append((f"nombres.anteriores[{i}]", otro))
    for campo, valor in textos_visibles:
        if not isinstance(valor, dict):
            continue
        for idioma in IDIOMAS:
            if isinstance(valor.get(idioma), str):
                pais = None if campo == "titulo" else lugar_.get("pais")
                salida += [
                    f"{campo}.{idioma}: {p}" for p in problemas_texto(valor[idioma], idioma, pais)
                ]
    localidad = str(lugar_.get("localidad") or "")
    sabido = localidad[:1].isupper() or (propiedades.get("objetivo") or {}).get("oaci")
    if sabido and "localidad" not in nombres:
        salida.append("Lugar: solo el país aunque se conoce la localidad")
    if lugar_.get("pais") != "ES":
        for campo in ("localidad", "objetivo", "region"):
            valor = nombres.get(campo) or {}
            if isinstance(valor.get("en"), str) and _ESPANOL.search(valor["en"]):
                salida.append(f"nombres.{campo}.en: en español «{valor['en']}»")
    return salida


def sin_resolver(
    incidentes: Iterable[Documento], cache_: Documento, antes_de: datetime
) -> list[tuple[str, str]]:
    """(país, nombre) de los lugares de los incidentes que no están en las tablas ni en la caché
    (o que no se encontraron hace más de una semana), para buscarlos en Wikidata."""
    vistos: dict[tuple[str, str], None] = {}
    limite = antes_de.strftime("%Y-%m-%dT%H:%MZ")
    for incidente in incidentes:
        lugar_ = incidente.get("lugar") or {}
        pais = lugar_.get("pais", "")
        nombres = [lugar_.get("localidad"), lugar_.get("region")]
        nombres += [o.get("nombre") for o in lugar_.get("otros_lugares") or []]
        objetivo_ = incidente.get("objetivo") or {}
        if not objetivo_.get("oaci"):
            nombres.append(objetivo_.get("nombre"))
        for nombre in nombres:
            if not nombre or nfc(str(nombre)) in textos():
                continue
            nombre = nfc(str(nombre))
            base = nombre_base(str(nombre))
            if not base or not base[0].isupper() or _en_tablas(base, pais, en_otro_pais=False):
                continue
            if any(p.match(base) for p, _ in _instalaciones()):
                continue
            guardado = cache_.get(clave_cache(pais, base))
            if isinstance(guardado, dict) and (
                _bilingue(guardado) or str(guardado.get("buscado", "")) > limite
            ):
                continue
            vistos[(pais, base)] = None
    return list(vistos)
