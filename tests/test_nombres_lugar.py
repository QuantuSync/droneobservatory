"""Nombres de lugar en español y en inglés (proceso/nombres_lugar.py, recogida/nombres_wikidata.py):
los casos de Chipre que dieron pie a la regla, los territorios, las instalaciones en otro idioma,
los titulares y la búsqueda horaria en Wikidata (que nunca impide publicar)."""

import json
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from esquema import Documento
from proceso import nombres_lugar
from recogida import nombres_wikidata

AHORA = datetime(2026, 10, 13, 15, 0, tzinfo=UTC)


def incidente(pais: str, **lugar: Any) -> Documento:
    objetivo = lugar.pop("objetivo", None)
    documento: Documento = {
        "id": "EODI-2026-09999",
        "titulo": lugar.pop("titulo", {"es": "Dron", "en": "Drone"}),
        "lugar": {"pais": pais, **lugar},
    }
    if objetivo is not None:
        documento["objetivo"] = objetivo
    return documento


@pytest.fixture(autouse=True)
def sin_cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(nombres_lugar.VARIABLE_CACHE, str(tmp_path / "cache.json"))
    nombres_lugar.olvidar_cache()


def test_pafos_en_espanol_y_paphos_en_ingles() -> None:
    doc = incidente(
        "CY",
        localidad="Paphos",
        punto={"lat": 34.72, "lon": 32.49},
        objetivo={"categoria": "aeropuerto", "nombre": "Διεθνής Αερολιμένας Πάφου", "oaci": "LCPH"},
        titulo={
            "es": "Drones sobre Chipre obligan a evacuar el aeropuerto de Paphos",
            "en": "Drones over Cyprus force evacuation of Paphos airport",
        },
    )
    nombres = nombres_lugar.nombres_publicos(doc)
    assert nombres["objetivo"] == {
        "es": "Aeropuerto de Pafos",
        "en": "Paphos International Airport",
    }
    assert nombres["lugar"] == {"es": "Pafos, Chipre", "en": "Paphos, Cyprus"}
    titulo = nombres_lugar.titulo_corregido(doc)
    assert titulo["es"] == "Drones sobre Chipre obligan a evacuar el aeropuerto de Pafos"
    assert titulo["en"] == "Drones over Cyprus force evacuation of Paphos airport"


def test_el_objetivo_en_otro_idioma_antes_que_la_ciudad() -> None:
    # EODI-2025-00136 publicaba «Suspendidos los vuelos en Brussels Airport…» en español: la forma
    # general «Brussels» → «Bruselas» se aplicaba antes y el nombre del objetivo ya no casaba.
    doc = incidente(
        "BE",
        localidad="Zaventem",
        punto={"lat": 50.90093, "lon": 4.4858},
        objetivo={"categoria": "aeropuerto", "nombre": "Brussels Airport", "oaci": "EBBR"},
        titulo={
            "es": "Suspendidos los vuelos en Brussels Airport por un posible dron",
            "en": "Flights suspended at Brussels Airport over possible drone sighting",
        },
    )
    titulo = nombres_lugar.titulo_corregido(doc)
    assert titulo["es"] == "Suspendidos los vuelos en el aeropuerto de Bruselas por un posible dron"
    assert titulo["en"] == "Flights suspended at Brussels Airport over possible drone sighting"
    assert nombres_lugar.problemas_texto(titulo["es"], "es") == []
    # Lo ya publicado a medio corregir también sale bien al publicar otra vez.
    doc["titulo"] = {
        **doc["titulo"],
        "es": "Suspendidos los vuelos en Bruselas Airport por un posible dron",
    }
    assert nombres_lugar.titulo_corregido(doc)["es"] == titulo["es"]


def test_larnaca_sin_localidad_lleva_la_ciudad_de_su_aeropuerto() -> None:
    doc = incidente(
        "CY",
        punto={"lat": 34.87, "lon": 33.62},
        objetivo={
            "categoria": "aeropuerto",
            "nombre": "Διεθνής Αερολιμένας Λάρνακας - Γλαύκος Κληρίδης",
            "oaci": "LCLK",
        },
        titulo={"es": "Drone interrumpe el tráfico en el aeropuerto de Larnaca", "en": "x"},
    )
    nombres = nombres_lugar.nombres_publicos(doc)
    assert nombres["objetivo"] == {
        "es": "Aeropuerto de Lárnaca",
        "en": "Larnaca International Airport",
    }
    assert nombres["lugar"] == {"es": "Lárnaca, Chipre", "en": "Larnaca, Cyprus"}
    assert (
        nombres_lugar.titulo_corregido(doc)["es"]
        == "Dron interrumpe el tráfico en el aeropuerto de Lárnaca"
    )


def test_akrotiri_es_base_britanica_en_chipre_y_el_pais_de_los_datos_no_cambia() -> None:
    doc = incidente(
        "GB",
        localidad="RAF Akrotiri",
        punto={"lat": 34.59, "lon": 32.99},
        objetivo={"categoria": "base_militar", "nombre": "RAF Akrotiri"},
    )
    nombres = nombres_lugar.nombres_publicos(doc)
    assert nombres["lugar"] == {
        "es": "RAF Akrotiri (base británica), Chipre",
        "en": "RAF Akrotiri (British base), Cyprus",
    }
    assert nombres["pais_geografico"] == "CY"
    assert doc["lugar"]["pais"] == "GB"


@pytest.mark.parametrize(
    ("pais", "punto", "esperado"),
    [
        (
            "GB",
            {"lat": 36.14, "lon": -5.35},
            {"es": "Gibraltar (Reino Unido)", "en": "Gibraltar (United Kingdom)"},
        ),
        ("FR", {"lat": -21.1, "lon": 55.5}, {"es": "Reunión (Francia)", "en": "Réunion (France)"}),
        (
            "DK",
            {"lat": 76.53, "lon": -68.7},
            {"es": "Groenlandia (Dinamarca)", "en": "Greenland (Denmark)"},
        ),
        (
            "NO",
            {"lat": 78.22, "lon": 15.6},
            {"es": "Svalbard (Noruega)", "en": "Svalbard (Norway)"},
        ),
        ("ES", {"lat": 28.5, "lon": -13.86}, {"es": "España", "en": "Spain"}),
    ],
)
def test_territorios_con_su_dependencia(pais: str, punto: Documento, esperado: Documento) -> None:
    assert nombres_lugar.nombres_publicos(incidente(pais, punto=punto))["lugar"] == esperado


def test_gibraltar_con_localidad_no_se_repite() -> None:
    doc = incidente("GB", localidad="Gibraltar", punto={"lat": 36.14, "lon": -5.35})
    assert nombres_lugar.nombres_publicos(doc)["lugar"]["es"] == "Gibraltar (Reino Unido)"


def test_reunion_con_localidad() -> None:
    doc = incidente("FR", localidad="Saint-Pierre", punto={"lat": -21.34, "lon": 55.48})
    assert nombres_lugar.nombres_publicos(doc)["lugar"] == {
        "es": "Saint-Pierre, Reunión (Francia)",
        "en": "Saint-Pierre, Réunion (France)",
    }


INSTALACIONES = [
    ("aeropuerto", "Flughafen München", "EDDM", "DE", "Aeropuerto de Múnich", "Munich Airport"),
    (
        "aeropuerto",
        "Aéroport de Liège-Bierset",
        "EBLG",
        "BE",
        "Aeropuerto de Lieja",
        "Liège Airport",
    ),
    (
        "base_militar",
        "Vliegbasis Gilze-Rijen",
        "EHGR",
        "NL",
        "Base aérea de Gilze-Rijen",
        "Gilze-Rijen Air Base",
    ),
    (
        "base_militar",
        "Luchtmachtbasis Kleine Brogel",
        None,
        "BE",
        "Base aérea de Kleine Brogel",
        "Kleine Brogel Air Base",
    ),
    ("puerto", "Portul Constanța", None, "RO", "Puerto de Constanza", "Port of Constanța"),
    (
        "aeropuerto",
        "Letiště Václava Havla Praha",
        "LKPR",
        "CZ",
        "Aeropuerto de Praga",
        "Václav Havel Airport Prague",
    ),
]


@pytest.mark.parametrize(("categoria", "nombre", "oaci", "pais", "es", "en"), INSTALACIONES)
def test_instalaciones_en_cada_version(
    categoria: str, nombre: str, oaci: str | None, pais: str, es: str, en: str
) -> None:
    objetivo = {"categoria": categoria, "nombre": nombre, **({"oaci": oaci} if oaci else {})}
    assert nombres_lugar.objetivo(objetivo, pais) == {"es": es, "en": en}


def test_nunca_otro_alfabeto_ni_transliteracion() -> None:
    # Un nombre en cirílico que no está en ninguna tabla no se enseña: la ficha cae en el país.
    doc = incidente(
        "BG", localidad="Неизвестно село", objetivo={"categoria": "otro", "nombre": "Неизвестно"}
    )
    nombres = nombres_lugar.nombres_publicos(doc)
    assert "localidad" not in nombres and "objetivo" not in nombres
    assert nombres["lugar"] == {"es": "Bulgaria", "en": "Bulgaria"}


def test_descripciones_de_la_ficha_fuera() -> None:
    assert nombres_lugar.lugar("Tudora (raionul Ștefan Vodă)", "MD") == {
        "es": "Tudora",
        "en": "Tudora",
    }
    assert nombres_lugar.lugar("Rēzekne, depósito de petróleo", "LV") == {
        "es": "Rēzekne",
        "en": "Rēzekne",
    }
    assert nombres_lugar.lugar("Warschau", "PL") == {"es": "Varsovia", "en": "Warsaw"}
    assert nombres_lugar.lugar("entre Radiany y Sewerynów", "PL") == {
        "es": "entre Radiany y Sewerynów",
        "en": "between Radiany and Sewerynów",
    }
    # Una descripción en español de un lugar de fuera de España no pasa a la versión inglesa.
    assert nombres_lugar.lugar("Cuartel de los dragones y su campo", "DK") is None
    # «Biala» es una aldea búlgara, no la forma sin tilde de Bielsko-Biała.
    assert nombres_lugar.lugar("Biala", "BG") == {"es": "Biala", "en": "Biala"}


def test_titulares_con_la_forma_de_cada_version() -> None:
    doc = incidente("ES", objetivo={"categoria": "aeropuerto", "nombre": "x", "oaci": "LEPA"})
    doc["titulo"] = {
        "es": "Dron obliga a cerrar el aeropuerto de Palma de Mallorca",
        "en": "Drone at Warszawa",
    }
    titulo = nombres_lugar.titulo_corregido(doc)
    assert titulo["es"] == "Dron obliga a cerrar el aeropuerto de Palma de Mallorca"
    assert titulo["en"] == "Drone at Warsaw"


def test_revision_de_lo_visible() -> None:
    assert nombres_lugar.problemas_texto("Διεθνής Αερολιμένας Πάφου", "es")
    assert nombres_lugar.problemas_texto("Flughafen München", "es")
    assert nombres_lugar.problemas_texto("aeropuerto de Paphos", "es")
    assert nombres_lugar.problemas_texto("Aeropuerto de Pafos", "en")
    assert nombres_lugar.problemas_texto("Paphos International Airport", "en") == []
    publicado = {
        "titulo": {"es": "Dron en Pafos", "en": "Drone in Paphos"},
        "lugar": {"pais": "CY", "localidad": "Paphos"},
        "nombres": {"lugar": {"es": "Chipre", "en": "Cyprus"}},
    }
    assert nombres_lugar.problemas(publicado) == [
        "Lugar: solo el país aunque se conoce la localidad"
    ]


# --- Búsqueda horaria en Wikidata -------------------------------------------------------------
class WikidataFalso:
    def __init__(self, fallar: bool = False) -> None:
        self.peticiones: list[str] = []
        self.fallar = fallar

    def __call__(self, peticion: urllib.request.Request) -> Any:
        self.peticiones.append(peticion.full_url)
        if self.fallar:
            raise TimeoutError("sin respuesta")
        if "wbsearchentities" in peticion.full_url:
            # Solo vale lo que se llama exactamente así: Q3 es otra cosa con el mismo comienzo.
            texto = "Novo Selo Inventado" if "Novo" in peticion.full_url else "Aldea Inventada"
            return {
                "search": [
                    {"id": "Q1", "match": {"type": "label", "text": texto}},
                    {"id": "Q3", "match": {"type": "label", "text": f"{texto} University"}},
                    {"id": "Q2", "match": {"type": "alias", "text": texto}},
                ]
            }
        return {
            "entities": {
                "Q1": {
                    "labels": {"en": {"value": "Elsewhere"}},
                    "claims": {"P17": [], "P625": [{}]},
                },
                "Q2": {
                    "labels": {"es": {"value": "Nueva Aldea"}, "en": {"value": "New Village"}},
                    "claims": {
                        "P17": [{"mainsnak": {"datavalue": {"value": {"id": "Q219"}}}}],
                        "P625": [{}],
                    },
                },
            }
        }


def test_lo_que_falta_se_busca_y_se_guarda(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ruta = tmp_path / "cache.json"
    falso = WikidataFalso()
    docs = [incidente("BG", localidad="Novo Selo Inventado")]
    assert nombres_wikidata.completar(docs, AHORA, ruta, falso) == 1
    guardado = json.loads(ruta.read_text(encoding="utf-8"))
    assert guardado["BG:novo selo inventado"]["es"] == "Nueva Aldea"
    monkeypatch.setenv(nombres_lugar.VARIABLE_CACHE, str(ruta))
    nombres_lugar.olvidar_cache()
    assert nombres_lugar.lugar("Novo Selo Inventado", "BG") == {
        "es": "Nueva Aldea",
        "en": "New Village",
    }
    # Ya buscado: no se vuelve a pedir.
    assert nombres_wikidata.completar(docs, AHORA, ruta, falso) == 0


def test_sin_wikidata_no_falla_y_se_publica_con_la_regla(tmp_path: Path) -> None:
    ruta = tmp_path / "cache.json"
    docs = [incidente("BG", localidad="Novo Selo Inventado")]
    assert nombres_wikidata.completar(docs, AHORA, ruta, WikidataFalso(fallar=True)) == 0
    assert not ruta.exists()
    assert nombres_lugar.nombres_publicos(docs[0])["lugar"] == {
        "es": "Novo Selo Inventado, Bulgaria",
        "en": "Novo Selo Inventado, Bulgaria",
    }


def test_tope_de_busquedas(tmp_path: Path) -> None:
    docs = [
        incidente("BG", localidad=f"Aldea Inventada {i}")
        for i in range(nombres_wikidata.MAX_BUSQUEDAS + 5)
    ]
    falso = WikidataFalso()
    nombres_wikidata.ESPERA_S, espera = 0.0, nombres_wikidata.ESPERA_S
    try:
        assert (
            nombres_wikidata.completar(docs, AHORA, tmp_path / "c.json", falso)
            == nombres_wikidata.MAX_BUSQUEDAS
        )
    finally:
        nombres_wikidata.ESPERA_S = espera


def test_tablas_validas() -> None:
    manual = nombres_lugar.manual()
    generado = nombres_lugar.generado()
    assert manual["flanco_este"] and generado["aeropuertos"] and generado["localidades"]
    for codigo, pais in manual["paises"].items():
        assert pais["es"] and pais["en"], codigo
    for nombre, valor in manual["textos"].items():
        assert valor is None or (valor["es"] and valor["en"]), nombre
    # Ningún nombre de las tablas sale mal escrito en su versión.
    for entrada in [*generado["localidades"].values(), *manual["localidades"]]:
        for idioma in nombres_lugar.IDIOMAS:
            assert nombres_lugar.latino_puro(entrada[idioma]), entrada


def test_tildes_como_signo_aparte() -> None:
    # Algunas fuentes escriben «César» con la «e» y la tilde sueltas (NFD).
    import unicodedata

    nombre = unicodedata.normalize("NFD", "Aeropuerto César Manrique Lanzarote")
    assert nombres_lugar.objetivo({"categoria": "aeropuerto", "nombre": nombre}, "ES") == {
        "es": "Aeropuerto de Lanzarote",
        "en": "Lanzarote Airport",
    }
    assert nombres_lugar.lugar(unicodedata.normalize("NFD", "Lárnaca"), "CY") == {
        "es": "Lárnaca",
        "en": "Larnaca",
    }


def test_autoridades_en_cada_version() -> None:
    from proceso import autoridades

    medio = "Bundesregierung (declaración oficial citada en come-on.de)"
    assert autoridades.de_la_fuente(medio, "es") == "el Gobierno federal alemán (Bundesregierung)"
    assert (
        autoridades.de_la_fuente(medio, "en") == "the German Federal Government (Bundesregierung)"
    )
    assert autoridades.de_la_fuente("Tráfico aéreo medido (adsb.lol)", "en") == (
        "Measured air traffic (adsb.lol)"
    )
    assert autoridades.escrita("Министерство на отбраната", "es") == (
        "el Ministerio de Defensa de Bulgaria"
    )
    # Desconocida y sin traducción en la ficha: sin nombre, también en alfabeto latino (la regla
    # de la web; tests/test_avisos_autoridades.py).
    assert autoridades.escrita("Ministerstvo obrany SR", "en") == "an authority"
    assert autoridades.escrita("Неизвестно ведомство", "en") == "an authority"


def test_las_traducciones_escriben_los_lugares_como_la_ficha() -> None:
    """EODI-2026-00050: las traducciones de las citas decían «Alexandrópolis», «Alexandroupolis»
    o «Alejandrópolis» según la fuente; la ficha dice Alejandrópolis en español y Alexandroupoli
    en inglés (el aeropuerto LGAL revisado a mano). Solo se cambian los lugares de la ficha."""
    from exportacion import citas

    nombres = nombres_lugar.nombres_publicos(
        {"pais": "GR", "objetivo": {"categoria": "aeropuerto", "oaci": "LGAL"}}
    )
    assert nombres["localidad"] == {"es": "Alejandrópolis", "en": "Alexandroupoli"}
    publico: Documento = {
        "nombres": nombres,
        "fuentes": [
            {
                "traduccion": {
                    "es": "Un dron cerca de Alexandrópolis; otro en Byala.",
                    "en": "A drone near Alexandroupolis; another in Byala.",
                }
            }
        ],
        "afirmaciones_publicas": [{"cita_traduccion": {"en": "Seen over Alejandrópolis."}}],
    }
    citas.con_sus_lugares(publico)
    assert publico["fuentes"][0]["traduccion"] == {
        "es": "Un dron cerca de Alejandrópolis; otro en Byala.",
        "en": "A drone near Alexandroupoli; another in Byala.",
    }
    assert publico["afirmaciones_publicas"][0]["cita_traduccion"] == {
        "en": "Seen over Alexandroupoli."
    }


def test_el_aeropuerto_de_la_ciudad_se_llama_igual_en_las_dos_versiones() -> None:
    """EODI-2026-00322: «Aeropuerto de Hamburgo-Fuhlsbüttel» frente a «Hamburg Airport». Con
    dos aeropuertos en la ciudad, el español tomaba la etiqueta de Wikidata aunque el inglés
    fuera solo «Hamburg Airport»; ahora los dos nombran el aeropuerto de la ciudad."""

    def fila(oaci: str, item: str, en: str, es: str) -> dict[str, str]:
        return {"icao": oaci, "item": item, "en": en, "es": es, "cen": "Hamburg", "ces": "Hamburgo"}

    tabla = nombres_wikidata.aeropuertos(
        [
            fila("EDDH", "Q27706", "Hamburg Airport", "Aeropuerto de Hamburgo-Fuhlsbüttel"),
            fila(
                "EDHI", "Q1", "Hamburg Finkenwerder Airport", "Aeropuerto de Hamburgo-Finkenwerder"
            ),
        ]
    )
    assert tabla["EDDH"]["aeropuerto"] == {"es": "Aeropuerto de Hamburgo", "en": "Hamburg Airport"}
    # El otro sigue con su nombre propio en las dos versiones.
    assert tabla["EDHI"]["aeropuerto"]["es"] == "Aeropuerto de Hamburgo-Finkenwerder"
    assert nombres_lugar._aeropuerto("EDDH")["aeropuerto"]["es"] == "Aeropuerto de Hamburgo"
