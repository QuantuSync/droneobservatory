"""Auditoría de las fichas vigentes (proceso/auditoria_fichas.py) y los arreglos que mide: la cita
de autoridad vacía (EODI-2026-00648, «… Komendy Stołecznej Policji przekazała»), el objetivo
«otra» que es la localidad (Józefów), el aeropuerto que nombra el titular con el punto de la
ciudad (EODI-2026-00131, Berlín; EODI-2026-00322, Hamburgo), el aviso cuando una comprobación
sube y su línea en el resumen diario."""

import copy
from datetime import UTC, datetime
from typing import Any

import pytest

from proceso import auditoria_fichas, declaraciones, incidentes, lugar_preciso, presencia
from proceso import control_fichas as reglas
from proceso.noticias import nomenclator
from recogida import silencio, visitas
from tests import ejemplos

AHORA = datetime(2026, 10, 21, 4, 0, tzinfo=UTC)
VACIA = "Podinsp. Marta Sulowska z Komendy Stołecznej Policji przekazała"
GAZETA = (
    'Podinsp. Marta Sulowska z Komendy Stołecznej Policji przekazała "Wyborczej", że pracownicy '
    "Wojskowego Instytutu Technicznego Uzbrojenia z Zielonki utracili łączność z maszyną "
    "ćwiczebną, co doprowadziło do jej upadku na działkę w Józefowie. Według policji "
    "przedstawiciele instytutu szybko dotarli na miejsce."
)
CONTENIDO = (
    "pracownicy Wojskowego Instytutu Technicznego Uzbrojenia z Zielonki utracili łączność z "
    "maszyną ćwiczebną, co doprowadziło do jej upadku na działkę w Józefowie."
)


@pytest.mark.parametrize(
    "frase",
    [
        VACIA,
        f'{VACIA} "Wyborczej"',
        "The police said:",
        "Die Polizei bestätigte",
        "Le porte-parole de la gendarmerie a déclaré",
        "Il portavoce ha dichiarato",
        "El portavoz de la Guardia Civil declaró",
        "Rzecznik policji oznajmił",
        "Ein Sprecher der Bundespolizei erklärte",
    ],
)
def test_una_cita_que_solo_dice_quien_habla_no_afirma_nada(frase: str) -> None:
    assert declaraciones.sin_afirmacion(frase)


@pytest.mark.parametrize(
    "frase",
    [
        "Drones were seen over the base, the police said.",
        "La policía dijo que vio drones",
        "A police spokesperson said three drones were seen",
        "Stołeczna policja uspokaja, że to nie rosyjski dron",
        "Wie die Bundespolizei mitteilt, sorgte ein rätselhaftes Flugobjekt für Aufregung.",
        CONTENIDO,
    ],
)
def test_una_cita_con_contenido_si_afirma(frase: str) -> None:
    assert not declaraciones.sin_afirmacion(frase)


def test_el_extractor_guarda_lo_que_dijo_o_nada() -> None:
    """La declaración partida («… przekazała») se queda con lo que sigue en el texto; si el texto
    no trae nada detrás, no vale."""
    (valida,) = declaraciones.validas([{"fuente": 1, "frase": VACIA}], [GAZETA])
    assert valida["frase"] == CONTENIDO
    assert declaraciones.validas([{"fuente": 1, "frase": VACIA}], [VACIA + "."]) == []


def _jozefow() -> dict[str, Any]:
    """Como EODI-2026-00648: confirmado por una declaración de la policía con la cita vacía, y el
    objetivo «otra» con el nombre de la localidad."""
    d = ejemplos.incidente_minimo()
    d["id"] = "EODI-2026-09648"
    d["titulo"] = {
        "es": "Dron de prácticas de un instituto militar polaco cae en Józefów, cerca de Varsovia",
        "en": "Training drone from a Polish military institute falls in Józefów, near Warsaw",
    }
    d["lugar"] = {"pais": "PL", "nivel": "localidad", "localidad": "Józefów",
                  "suceso": "Józefowie", "punto": {"lat": 52.137, "lon": 21.236},
                  "radio_km": 5.0}  # fmt: skip
    d["objetivo"] = {"categoria": "otra", "nombre": "Józefów"}
    d["presencia_dron"] = "confirmada"
    noticia = {
        **ejemplos.fuente("gdelt-gazeta", "C"),
        "frase_origen": "dron spadł na jedną z działek w Józefowie",
    }
    policia = {
        **ejemplos.fuente("gdelt-gazeta-declaracion-1", "B", es_autoridad=True),
        "medio": "Komenda Stołecznej Policji (declaración oficial citada en wiadomosci.gazeta.pl)",
        "frase_origen": VACIA,
        "campos_respaldados": ["estado", "presencia_dron"],
    }  # fmt: skip
    d["fuentes"] = [noticia, policia]
    d["estado"] = {
        "actual": "confirmado",
        "historial": [
            {"estado": "notificado", "fecha": ejemplos.instante("2026-10-20T22:45Z"),
             "fuente_id": "gdelt-gazeta"},
            {"estado": "confirmado", "fecha": ejemplos.instante("2026-10-20T22:45Z"),
             "fuente_id": "gdelt-gazeta-declaracion-1"},
        ],
    }  # fmt: skip
    d["afirmaciones"] = [declaraciones.afirmacion_presencia("gdelt-gazeta-declaracion-1")]
    return d


def test_una_cita_vacia_no_confirma_estado_ni_presencia() -> None:
    documento = _jozefow()
    policia = documento["fuentes"][1]
    assert declaraciones.cita_vacia(policia)
    assert not declaraciones.de_autoridad(policia)
    assert not reglas.oficial(policia)
    bajado = reglas.bajar_estado(documento, ejemplos.instante("2026-10-21T04:00Z"))
    assert bajado is not None and bajado["estado"]["actual"] == "notificado"
    sin = presencia.quitar_por_cita_vacia(documento)
    assert sin["presencia_dron"] == "no_confirmada"
    assert not any(a["valor"] == "confirmada" for a in sin["afirmaciones"])
    # Con lo que dijo la policía, la cita vuelve a valer.
    con = copy.deepcopy(documento)
    con["fuentes"][1]["frase_origen"] = CONTENIDO
    assert reglas.bajar_estado(con, ejemplos.instante("2026-10-21T04:00Z")) is None
    assert presencia.quitar_por_cita_vacia(con) is con


def test_el_objetivo_otra_con_el_nombre_de_la_localidad_no_es_una_instalacion() -> None:
    documento = _jozefow()
    assert incidentes.objetivo_es_la_localidad(documento["objetivo"], documento["lugar"])
    assert not incidentes.objetivo_es_la_localidad(
        {"categoria": "otra", "nombre": "Penitenciaría de Vught"}, {"localidad": "Vught"}
    )
    assert not incidentes.objetivo_es_la_localidad(
        {"categoria": "aeropuerto", "nombre": "Berlin"}, {"localidad": "Berlin"}
    )


def test_la_auditoria_cuenta_cada_fallo() -> None:
    documento = _jozefow()
    resultado = auditoria_fichas.auditar(
        [documento, {**ejemplos.incidente_minimo(), "retirado": {}}]
    )
    assert resultado["A"] == [documento["id"]]
    assert resultado["C"] == [documento["id"]]
    assert set(resultado) == set(auditoria_fichas.COMPROBACIONES)
    assert auditoria_fichas.cabecera(documento) == documento["titulo"]["es"]
    sin = {k: v for k, v in documento.items() if k != "objetivo"}
    sin["fuentes"] = [
        *documento["fuentes"][:1],
        {**documento["fuentes"][1], "frase_origen": CONTENIDO},
    ]
    limpio = auditoria_fichas.auditar([sin])
    assert limpio["A"] == [] and limpio["C"] == []


@pytest.mark.parametrize(
    ("titulo", "pais", "punto", "objetivo", "oaci"),
    [
        ("Suspensión temporal en el aeropuerto de Berlín tras detectar un posible dron", "DE",
         {"lat": 52.52437, "lon": 13.41053}, "Berlin", "EDDB"),
        ("Alarma de posible dron interrumpe brevemente el tráfico aéreo en el aeropuerto de "
         "Hamburgo", "DE", {"lat": 53.55073, "lon": 9.99302}, "Hamburg", "EDDH"),
    ],
)  # fmt: skip
def test_el_aeropuerto_del_titular_con_el_punto_de_la_ciudad(
    titulo: str, pais: str, punto: dict[str, float], objetivo: str, oaci: str
) -> None:
    """EODI-2026-00131 y 00322: el titular nombra el aeropuerto y la ficha tenía el punto de la
    ciudad (del candidato) y un objetivo «otra» con el nombre de la ciudad."""
    documento = ejemplos.incidente_minimo()
    documento["titulo"] = {"es": titulo, "en": titulo}
    documento["lugar"] = {"pais": pais, "nivel": "instalacion", "punto": punto, "radio_km": 20.0,
                          "geocodificacion": "candidato"}  # fmt: skip
    documento["objetivo"] = {"categoria": "otra", "nombre": objetivo}
    nuevo = lugar_preciso.precisar(documento, nomenclator(), AHORA)
    assert nuevo is not None
    assert nuevo["objetivo"]["categoria"] == "aeropuerto" and nuevo["objetivo"]["oaci"] == oaci
    # Un punto que dio una autoridad no se mueve.
    oficial = copy.deepcopy(documento)
    oficial["lugar"]["geocodificacion"] = "oficial"
    assert lugar_preciso.precisar(oficial, nomenclator(), AHORA) is None


def test_avisa_si_una_comprobacion_sube() -> None:
    medidas = silencio.Medidas(
        ultima_alta="2026-10-21T03:00:00Z",
        auditoria={"2026-10-20": {"A": 5, "C": 2}, "2026-10-21": {"A": 5, "C": 3}},
    )
    casos = silencio.avisos(medidas, AHORA)
    assert list(casos) == ["auditoria:C:2026-10-21"]
    titulo, texto = casos["auditoria:C:2026-10-21"]
    assert titulo == silencio.TITULO_AUDITORIA and "2 fichas el 2026-10-20, 3 hoy" in texto
    igual = silencio.Medidas(ultima_alta="2026-10-21T03:00:00Z",
                             auditoria={"2026-10-21": {"A": 5, "C": 3}})  # fmt: skip
    assert silencio.avisos(igual, AHORA) == {}


def test_el_resumen_lleva_la_auditoria() -> None:
    dias = {"2026-10-20": {"A": 5, "C": 2}, "2026-10-21": {"A": 4, "C": 2}}
    assert visitas.lineas_auditoria(dias) == ["  Auditoría de fichas: A 4 (-1), C 2"]
    assert visitas.lineas_auditoria({}) == []
