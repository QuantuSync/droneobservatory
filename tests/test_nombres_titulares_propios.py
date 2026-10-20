"""Titulares y nombres publicados sin palabras repetidas, sin nombres propios traducidos y sin un
buque como lugar (20 de octubre de 2026: «distrito de Distrito de Ștefan Vodă», «Seville I
prison», «Picasent», «Chelsea 3, Bulgaria»)."""

from typing import Any

from proceso import nombres_lugar, zona
from tests.test_fichas_buques_fechas import chelsea


def _incidente(pais: str, lugar: dict[str, Any], titulo: dict[str, str], **otros: Any) -> Any:
    return {"id": "EODI-2026-99999", "lugar": {"pais": pais, **lugar}, "titulo": titulo, **otros}


def test_el_titular_no_alarga_un_nombre_que_ya_dice() -> None:
    documento = _incidente(
        "MD",
        {"nivel": "localidad", "localidad": "Volintiri", "region": "Ștefan Vodă"},
        {
            "es": "Hallan restos de un dron en Volintiri, distrito de Ștefan Vodă",
            "en": "Drone fragments found in Volintiri, Ștefan Vodă district",
        },
    )
    titulo = nombres_lugar.titulo_corregido(documento)
    assert titulo == documento["titulo"]
    assert all(nombres_lugar.palabra_repetida(t) is None for t in titulo.values())


def test_palabra_repetida() -> None:
    assert nombres_lugar.palabra_repetida("en el distrito de Distrito de Ștefan Vodă") == (
        "distrito de"
    )
    assert nombres_lugar.palabra_repetida("Ștefan Vodă District district") == "District"
    assert nombres_lugar.palabra_repetida("Possible drones over Eemshaven") is None


def test_la_ciudad_no_se_traduce_dentro_del_nombre_de_una_instalacion() -> None:
    documento = _incidente(
        "ES",
        {"nivel": "instalacion", "suceso": "Centro Penitenciario de Sevilla (Sevilla I)"},
        {
            "es": "Posible dron sobrevuela la prisión de Sevilla I en Alcalá de Guadaíra",
            "en": "Possible drone flies over Sevilla I prison in Alcalá de Guadaíra",
        },
        objetivo={"categoria": "otra", "nombre": "Centro Penitenciario Sevilla I"},
    )
    assert nombres_lugar.titulo_corregido(documento) == documento["titulo"]
    assert nombres_lugar.objetivo(documento["objetivo"], "ES") == {
        "es": "Centro penitenciario Sevilla I",
        "en": "Sevilla I prison",
    }
    # La ciudad sola sí se escribe con su exónimo.
    assert nombres_lugar.corregir_texto("Drones over Sevilla airport", {}, "en") == (
        "Drones over Seville airport"
    )


def test_en_espana_el_nombre_oficial_que_escribe_la_fuente() -> None:
    assert nombres_lugar.lugar("Picassent", "ES") == {"es": "Picassent", "en": "Picassent"}
    assert nombres_lugar.lugar("Sevilla", "ES") == {"es": "Sevilla", "en": "Seville"}
    documento = _incidente(
        "ES",
        {"nivel": "instalacion", "localidad": "Picassent"},
        {
            "es": "Interceptan un dron con móviles de contrabando en la cárcel de Picassent",
            "en": "Drone carrying contraband phones intercepted at Picassent prison, Spain",
        },
    )
    assert nombres_lugar.titulo_corregido(documento) == documento["titulo"]
    assert nombres_lugar.nombres_publicos(documento)["localidad"] == {
        "es": "Picassent",
        "en": "Picassent",
    }


def test_un_buque_en_el_objetivo_no_es_la_localidad() -> None:
    documento = chelsea()
    documento["lugar"] = {"pais": "BG", "nivel": "region", "suceso": "mar Negro",
                          "region": "mar Negro"}  # fmt: skip
    documento["objetivo"] = {"categoria": "otra", "nombre": "Chelsea 3"}
    nombres = nombres_lugar.nombres_publicos(documento)
    assert "Chelsea" not in nombres["lugar"]["es"]
    assert nombres.get("localidad", {}).get("es") != "Chelsea 3"
    # Con la localidad de la ficha puesta al buque, tampoco.
    nombres = nombres_lugar.nombres_publicos(chelsea())
    assert "Chelsea" not in nombres["lugar"]["es"]


def test_con_punto_en_tierra_manda_el_punto() -> None:
    # Un dron en el puerto de Constanza cuyas fuentes citan un petrolero en el mar: la zona sale
    # del punto, no del atajo del mar.
    documento = chelsea()
    documento.pop("zona")
    documento["lugar"] = {"pais": "RO", "nivel": "localidad", "localidad": "Constanța",
                          "punto": {"lat": 44.17, "lon": 28.64}}  # fmt: skip
    sin_buque = {**documento, "titulo": {"es": "Dron en Constanza", "en": "Drone in Constanța"},
                 "fuentes": []}  # fmt: skip
    assert zona.clasificar(documento) == zona.clasificar(sin_buque)


def test_la_ciudad_dentro_del_nombre_de_un_aeropuerto_no_se_traduce() -> None:
    texto = "Avistamiento de drones sobre el aeropuerto de Maastricht Aachen"
    assert nombres_lugar.corregir_texto(texto, {}, "es") == texto
    assert nombres_lugar.formas_ajenas(texto, "es") == []
    # Sola, sí: «Aachen» → «Aquisgrán».
    assert nombres_lugar.corregir_texto("Drones sobre Aachen", {}, "es") == "Drones sobre Aquisgrán"
    assert nombres_lugar.corregir_texto("Drones close Hannover airport", {}, "en") == (
        "Drones close Hanover airport"
    )


def test_posible_repetido() -> None:
    from proceso import titulares

    assert (
        titulares.ajustar("Possible possible drone crash on Romanian coast", "no_confirmada", "en")
        == "Possible drone crash on Romanian coast"
    )
