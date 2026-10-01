"""Respuestas parlamentarias (Bundestag, Tweede Kamer, Parlamento británico), sin red."""

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest

from recogida import detalle, parlamentos
from recogida.descarga import Descargador, DescargaFallida

FIXTURES = Path(__file__).parent / "fixtures" / "detalle"
AHORA = datetime(2026, 10, 1, 12, tzinfo=UTC)
CLAVE_PRUEBA = "CLAVE.DePrueba123"


def leer(nombre: str) -> bytes:
    return (FIXTURES / nombre).read_bytes()


def json_de(nombre: str) -> dict[str, object]:
    datos: dict[str, object] = json.loads(leer(nombre))
    return datos


def texto_de(nombre: str) -> str:
    documentos = json_de(nombre)["documents"]
    assert isinstance(documentos, list)
    return str(documentos[0]["text"])


Ruta = tuple[str, dict[str, str]]


class Transporte:
    """Responde según la ruta y los parámetros; robots.txt da 404. Registra cabeceras."""

    def __init__(self, respuestas: list[tuple[str, dict[str, str], bytes]]) -> None:
        self.respuestas = respuestas
        self.pedidas: list[tuple[str, dict[str, str]]] = []

    def __call__(
        self, url: str, cabeceras: dict[str, str], limite: float
    ) -> tuple[int, dict[str, str], bytes]:
        self.pedidas.append((url, dict(cabeceras)))
        assert "EODI-bot" in cabeceras["User-Agent"]
        partes = urlsplit(url)
        consulta = {k: v[0] for k, v in parse_qs(partes.query).items()}
        for ruta, parametros, cuerpo in self.respuestas:
            if (partes.netloc + partes.path).endswith(ruta) and all(
                consulta.get(k) == v for k, v in parametros.items()
            ):
                return 200, {}, cuerpo
        return 404, {}, b""


def descargador(transporte: Transporte) -> Descargador:
    return Descargador(transporte=transporte, dormir=lambda _: None, agente="EODI-bot/1.0")


# --- Bundestag --------------------------------------------------------------------------


def test_la_clave_de_dip_se_lee_de_la_ayuda_en_cada_ejecucion() -> None:
    transporte = Transporte([("help-api", {}, leer("parl_dip_ayuda.json"))])
    assert parlamentos.clave_dip(descargador(transporte)) == CLAVE_PRUEBA


def test_sin_clave_en_la_ayuda_no_se_sigue() -> None:
    transporte = Transporte([("help-api", {}, b'{"data": {"content": ["sin clave"]}}')])
    with pytest.raises(parlamentos.SinClave):
        parlamentos.clave_dip(descargador(transporte))


def test_de_la_kleine_anfrage_solo_la_respuesta_del_gobierno() -> None:
    respuesta = parlamentos.respuesta_kleine_anfrage(texto_de("parl_dip_antwort_21_8140.json"))
    # Ni la exposición de los diputados ni la pregunta numerada.
    assert "Seit einem Vorfall am Flughafen Leipzig" not in respuesta
    assert "Wie viele Dienstposten" not in respuesta
    assert "Die Bundesregierung hat die Fähigkeiten zur Drohnendetektion" in respuesta
    assert "auf 300" in respuesta


def test_de_la_drucksache_semanal_solo_el_bloque_de_la_pregunta_y_su_respuesta() -> None:
    texto = texto_de("parl_dip_sf_21_4657.json")
    bloque = parlamentos.respuesta_escrita(texto, "52")
    assert bloque is not None and bloque.startswith("Antwort des Parlamentarischen Staatssekretärs")
    assert "Lagebild" in bloque and "Otto Strauß" not in bloque
    assert "Wie viele Vorfälle" not in bloque
    assert parlamentos.respuesta_escrita(texto, "99") is None


def test_de_la_pregunta_oral_la_respuesta_del_anexo_del_plenarprotokoll() -> None:
    respuesta = parlamentos.respuesta_oral(texto_de("parl_dip_pp_21_33.json"), "65")
    assert respuesta is not None and respuesta.startswith("Antwort des Parl. Staatssekretärs")
    assert "152 Drohnenbehinderungen" in " ".join(respuesta.split())
    assert "Wegwerf" not in respuesta and "Fachkräfte" not in respuesta


def transporte_dip() -> Transporte:
    return Transporte(
        [
            ("help-api", {}, leer("parl_dip_ayuda.json")),
            (
                "/api/v1/vorgang",
                {"f.deskriptor": "Unbemanntes Fluggerät"},
                leer("parl_dip_vorgang.json"),
            ),
            ("/api/v1/vorgang", {}, b'{"numFound": 0, "documents": [], "cursor": "a"}'),
            (
                "/api/v1/vorgangsposition",
                {"f.vorgang": "338837"},
                leer("parl_dip_posiciones_338837.json"),
            ),
            (
                "/api/v1/vorgangsposition",
                {"f.vorgang": "332718"},
                leer("parl_dip_posiciones_332718.json"),
            ),
            (
                "/api/v1/vorgangsposition",
                {"f.vorgang": "326997"},
                leer("parl_dip_posiciones_326997.json"),
            ),
            (
                "/api/v1/drucksache-text",
                {"f.dokumentnummer": "21/8140"},
                leer("parl_dip_antwort_21_8140.json"),
            ),
            (
                "/api/v1/drucksache-text",
                {"f.dokumentnummer": "21/4657"},
                leer("parl_dip_sf_21_4657.json"),
            ),
            (
                "/api/v1/plenarprotokoll-text",
                {"f.dokumentnummer": "21/33"},
                leer("parl_dip_pp_21_33.json"),
            ),
        ]
    )


FUENTE_DIP = {"id": "bundestag_dip", "tipo": "bundestag_dip"}


def test_dip_de_principio_a_fin_sin_red(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    transporte = transporte_dip()
    with caplog.at_level(logging.DEBUG):
        cuantos = parlamentos.recolector_dip(
            FUENTE_DIP, tmp_path, descargador(transporte), AHORA, True
        )
    assert cuantos == 3
    documentos = {d["id"]: d for d in detalle.documentos_recogidos(tmp_path)}
    assert set(documentos) == {
        "bundestag_dip:338837",
        "bundestag_dip:332718",
        "bundestag_dip:326997",
    }
    oral = documentos["bundestag_dip:326997"]
    assert (oral["tipo"], oral["autoridad"], oral["pais"], oral["fiabilidad"]) == (
        "respuesta_parlamentaria",
        "Bundesregierung",
        "DE",
        "A",
    )
    assert oral["fecha"] == "2025-10-15" and oral["enlace"].endswith("21033.pdf#P.3628")
    assert any("152 Drohnenbehinderungen" in p for p in oral["pasajes"])
    # La clave va solo en la cabecera, nunca en la dirección ni en el registro.
    con_clave = [c for u, c in transporte.pedidas if "/api/v1/" in u]
    assert con_clave and all(c["Authorization"] == f"ApiKey {CLAVE_PRUEBA}" for c in con_clave)
    assert all(CLAVE_PRUEBA not in u for u, _ in transporte.pedidas)
    assert CLAVE_PRUEBA not in caplog.text
    assert CLAVE_PRUEBA not in (tmp_path / "documentos" / "bundestag_dip.json").read_text(
        encoding="utf-8"
    )


def test_dip_sin_historico_no_vuelve_a_pedir_lo_guardado(tmp_path: Path) -> None:
    parlamentos.recolector_dip(FUENTE_DIP, tmp_path, descargador(transporte_dip()), AHORA, True)
    transporte = transporte_dip()
    assert (
        parlamentos.recolector_dip(FUENTE_DIP, tmp_path, descargador(transporte), AHORA, False) == 0
    )
    assert not any("vorgangsposition" in u for u, _ in transporte.pedidas)
    # La ventana reciente filtra por fecha de actualización.
    assert any("f.aktualisiert.start=2026-08-02" in u for u, _ in transporte.pedidas)


def test_robots_que_lo_prohibe_para_el_recolector(tmp_path: Path) -> None:
    transporte = transporte_dip()
    transporte.respuestas.insert(0, ("robots.txt", {}, b"User-agent: *\nDisallow: /\n"))
    with pytest.raises(DescargaFallida):
        parlamentos.recolector_dip(FUENTE_DIP, tmp_path, descargador(transporte), AHORA, True)
    assert not any("help-api" in u for u, _ in transporte.pedidas)


# --- Tweede Kamer ---------------------------------------------------------------------


def test_de_las_respuestas_escritas_solo_los_bloques_antwoord() -> None:
    texto = (
        "Antwoord van Staatssecretaris Coenradie (Justitie en Veiligheid) (ontvangen\n"
        "7 februari 2025).\n\nVraag 1\nBent u bekend met het bericht «Drones vliegen boven PI"
        " in Vught»?\n\nAntwoord 1\nJa.\n\nVraag 2\nHoeveel drones zijn op 23 december 2024 "
        "boven de PI Vught geconstateerd?\n\nAntwoord 2\nEr zijn meerdere drones gesignaleerd."
    )
    respuestas = parlamentos.respuestas_tk(texto, "Antwoord schriftelijke vragen")
    assert respuestas == "Ja.\n\nEr zijn meerdere drones gesignaleerd."
    assert parlamentos.autoridad_tk(texto) == "Rijksoverheid (Justitie en Veiligheid)"
    carta = "BRIEF VAN DE MINISTER EN STAATSSECRETARIS VAN\nDEFENSIE\nHet afgelopen weekend..."
    assert parlamentos.respuestas_tk(carta, "Brief regering") == carta
    assert (
        parlamentos.autoridad_tk("BRIEF VAN DE MINISTER VAN DEFENSIE\n")
        == "Rijksoverheid (Defensie)"
    )


def test_la_consulta_busca_respuestas_y_cartas_con_drone_en_el_asunto() -> None:
    consulta = parse_qs(urlsplit(parlamentos.consulta_tk("2024-01-01")).query)["$filter"][0]
    assert "Soort eq 'Antwoord schriftelijke vragen'" in consulta
    assert "Soort eq 'Brief regering'" in consulta
    assert "contains(tolower(Onderwerp),'drone')" in consulta and "Datum ge 2024-01-01" in consulta


def test_tweede_kamer_de_principio_a_fin_sin_red(tmp_path: Path) -> None:
    documentos = json_de("parl_tk_documentos.json")["value"]
    assert isinstance(documentos, list)
    respuestas: list[tuple[str, dict[str, str], bytes]] = [
        ("/OData/v4/2.0/Document", {}, leer("parl_tk_documentos.json"))
    ]
    for d in documentos:
        respuestas.append((f"Document({d['Id']})/resource", {}, leer("parl_tk_2025D05422.pdf")))
    transporte = Transporte(respuestas)
    fuente = {"id": "tweede_kamer", "tipo": "tweede_kamer"}
    assert parlamentos.recolector_tk(fuente, tmp_path, descargador(transporte), AHORA, True) == len(
        documentos
    )
    vught = next(
        d for d in detalle.documentos_recogidos(tmp_path) if d["id"] == "tweede_kamer:2025D05422"
    )
    assert vught["autoridad"] == "Rijksoverheid (Justitie en Veiligheid)"
    assert (vught["fecha"], vught["idioma"]) == ("2025-02-07", "nl")
    assert vught["enlace"].endswith("/resource")
    assert vught["pasajes"] and not any("Bent u bekend" in p for p in vught["pasajes"])


# --- Reino Unido ------------------------------------------------------------------------


def test_relevante_si_relaciona_drones_con_instalaciones_o_avistamientos() -> None:
    pregunta = json_de("parl_uk_pregunta.json")["value"]
    assert isinstance(pregunta, dict) and parlamentos.relevante_uk(pregunta)
    assert not parlamentos.relevante_uk(
        {"heading": "Members: Correspondence", "questionText": "regarding USAF Lakenheath"}
    )
    assert not parlamentos.relevante_uk(
        {"heading": "Drones: Delivery", "questionText": "drone delivery of parcels"}
    )


def test_uk_de_principio_a_fin_sin_red(tmp_path: Path) -> None:
    busqueda = json_de("parl_uk_busqueda.json")
    resultados = busqueda["results"]
    assert isinstance(resultados, list)
    # La búsqueda devuelve una pregunta de drones contestada: la de la respuesta completa.
    pregunta = json_de("parl_uk_pregunta.json")
    pagina = json.dumps({"totalResults": 1, "results": [pregunta]}).encode()
    transporte = Transporte(
        [
            ("/writtenquestions/questions", {"searchTerm": "drone", "skip": "0"}, pagina),
            (
                "/writtenquestions/questions",
                {"skip": "0"},
                json.dumps({"totalResults": 0, "results": []}).encode(),
            ),
            ("/writtenquestions/questions/1843693", {}, leer("parl_uk_pregunta.json")),
        ]
    )
    fuente = {"id": "uk_parlamento", "tipo": "uk_parlamento"}
    assert parlamentos.recolector_uk(fuente, tmp_path, descargador(transporte), AHORA, True) == 1
    (documento,) = detalle.documentos_recogidos(tmp_path)
    assert documento["id"] == "uk_parlamento:HL11210"
    assert documento["autoridad"] == "UK Government (Ministry of Defence)"
    assert documento["fecha"] == "2025-11-04"
    assert documento["enlace"] == (
        "https://questions-statements.parliament.uk/written-questions/detail/2025-10-21/HL11210"
    )
    assert any("187 drone sightings" in p for p in documento["pasajes"])
    # Solo la respuesta: la pregunta del lord no está en los pasajes.
    assert not any("To ask His Majesty" in p for p in documento["pasajes"])
    assert any("tabledWhenFrom=2024-01-01" in u for u, _ in transporte.pedidas)


def test_una_pagina_que_falla_corta_solo_su_termino() -> None:
    pagina = json.dumps({"totalResults": 1, "results": [json_de("parl_uk_pregunta.json")]}).encode()
    transporte = Transporte([("/writtenquestions/questions", {"searchTerm": "drones"}, pagina)])
    d = Descargador(
        transporte=transporte, dormir=lambda _: None, agente="EODI-bot/1.0", reintentos=0
    )
    preguntas = parlamentos.preguntas_uk(d, "2024-01-01")
    assert [p["uin"] for p in preguntas] == ["HL11210"]
