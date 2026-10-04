"""Pendientes de la revisión de presencia de dron (docs/informe_errores_datos.md, bloque 6):
repeticiones medidas con la hora de la fuente, el cierre de una pista como cierre y la altura de
los encuentros de la UK Airprox Board en el motor de deducción."""

from datetime import UTC, datetime

from proceso import presencia
from proceso.deduccion import catalogo as catalogo_
from proceso.deduccion import motor, reglas
from proceso.noticias import Articulo, Candidato, filtro, nomenclator, repeticion
from proceso.validaciones import validar_incidente
from tests.ejemplos import VOCABULARIO_MODELOS
from tests.test_calidad_datos_3 import inc

AHORA = datetime(2026, 10, 4, 12, tzinfo=UTC)


def _candidato(oaci: str, suceso: datetime, primera: datetime) -> Candidato:
    candidato = Candidato(
        f"CAND-{primera:%Y%m%dT%H%M}-{oaci}-aeropuerto", "aeropuerto",
        nomenclator().lugares[oaci], primera, primera, "hora", ["https://a.nl/1"],
    )  # fmt: skip
    candidato.suceso = suceso
    return candidato


def test_otra_noche_en_volkel_se_separa() -> None:
    # EODI-2025-00066: el suceso, el viernes 21 de noviembre de 2025 a las 19:00; las noticias
    # del domingo 23 cuentan otra noche.
    candidato = _candidato("EHVK", datetime(2025, 11, 21, 19, tzinfo=UTC),
                           datetime(2025, 11, 22, 13, tzinfo=UTC))  # fmt: skip
    for hora, titular in [
        (datetime(2025, 11, 23, 9, 45, tzinfo=UTC),
         "Another mystery drone sighted over the Netherlands' Volkel Air Base"),
        (datetime(2025, 11, 23, 11, 30, tzinfo=UTC),
         "Wéér drones bij vliegbasis Volkel: 'Hoofdkwartier dag en nacht bezig'"),
    ]:  # fmt: skip
        assert repeticion(candidato, Articulo(f"https://b.nl/{hora:%H%M}", "b.nl", hora,
                                              titular, "en"), filtro())  # fmt: skip


def test_la_reapertura_de_la_misma_noche_no_se_separa() -> None:
    # EODI-2025-00136: «rond middernacht opnieuw even gesloten», publicado a las 06:30 tras el
    # cierre de las 21:45: la misma noche.
    candidato = _candidato("EBBR", datetime(2025, 11, 12, 21, 45, tzinfo=UTC),
                           datetime(2025, 11, 13, 1, tzinfo=UTC))  # fmt: skip
    articulo = Articulo(
        "https://c.be/1", "c.be", datetime(2025, 11, 13, 6, 30, tzinfo=UTC),
        "LIVE. Luchthaven Zaventem rond middernacht opnieuw even gesloten door mogelijke drone",
        "nl",
    )  # fmt: skip
    assert not repeticion(candidato, articulo, filtro())


def test_el_cierre_de_una_pista_es_un_cierre_y_confirma_la_presencia() -> None:
    # EODI-2025-00058, Schiphol (aex.ru).
    documento = inc("EODI-2025-00058", "2025-07-26T18:00Z", "hora",
                    "Luchthaven Schiphol", (52.327, 4.758), "NL")  # fmt: skip
    documento.update(
        tipo="sobrevuelo", presencia_dron="no_confirmada",
        consecuencias={"cierre": {"valor": "desconocido"}},
        objetivo={"categoria": "aeropuerto", "nombre": "Luchthaven Schiphol", "oaci": "EHAM"},
        titulo={"es": "Posibles drones cierran una pista del aeropuerto de Ámsterdam Schiphol",
                "en": "Possible drones close runway at Amsterdam Schiphol Airport"},
    )  # fmt: skip
    documento["fuentes"][0]["frase_origen"] = (
        "Аэропорт Схипхол приостанавливал работу взлетно-посадочной полосы из-за дрона."
    )
    con_cierre = presencia.cierre_de_pista(documento)
    assert con_cierre["consecuencias"]["cierre"]["valor"] == "si"
    assert con_cierre["tipo"] == "interrupcion_aeroportuaria"
    resultado = presencia.aplicar(documento)
    assert resultado["presencia_dron"] == "confirmada"
    assert resultado["titulo"]["es"].startswith("Drones cierran una pista")
    assert validar_incidente(resultado, AHORA, VOCABULARIO_MODELOS) == []


def _encuentro(pies: int, referencia: str = "sin_referencia") -> dict[str, object]:
    return {
        "id": "UKAB-2018203", "pais": "GB",
        "altitud": {"pies": pies, "referencia": referencia, "texto": f"{pies}ft"},
        "instante": {"valor": "2018-09-01T10:00Z", "precision": "minuto"},
        "posicion": {"punto": {"lat": 52.0, "lon": -1.0}},
        "objeto": {"clasificacion": "Drone"},
    }  # fmt: skip


def test_la_altura_oficial_de_un_encuentro_descarta_las_clases_que_no_llegan() -> None:
    catalogo = catalogo_.cargar()
    alto = motor.caso_de_encuentro(_encuentro(20000, "nivel_vuelo"))
    assert alto is not None and alto.altura_oficial
    assert alto.altura_m == (6096.0, 6096.0)
    descartadas = {e.clase for e in reglas.r9_altura(catalogo, alto) if e.efecto == reglas.DESCARTA}
    assert "ala_fija_tactica_electrica" in descartadas
    bajo = motor.caso_de_encuentro(_encuentro(300))
    assert bajo is not None
    assert not [e for e in reglas.r9_altura(catalogo, bajo) if e.efecto == reglas.DESCARTA]
    resultado = motor.evaluar_encuentro(catalogo, alto)
    assert any(d["clase"] == "ala_fija_tactica_electrica" for d in resultado["descartadas"])


def test_la_altura_de_la_prensa_no_descarta() -> None:
    catalogo = catalogo_.cargar()
    caso = reglas.Caso(id="EODI-2025-00001", tipo="incidente", altura_m=(6096.0, 6096.0))
    assert not [e for e in reglas.r9_altura(catalogo, caso) if e.efecto == reglas.DESCARTA]
