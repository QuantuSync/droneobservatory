"""La presencia del dron no se confirma con avisos, sospechas ni respuestas en ninguna lengua.

EODI-2026-00821 (RAF Lakenheath) volvió el 28 de noviembre de 2026 a «dron confirmado» con una
frase griega de inewsgr.com, «στις 13 Νοεμβρίου καταγράφηκαν αναφορές για μη εξουσιοδοτημένη
δραστηριότητα drones στη RAF Lakenheath» («se registraron avisos de actividad no autorizada de
drones»), el mismo «reports of» que la regla ya no aceptaba en inglés. Fallaba por dos cosas: la
lista de avisos no tenía «αναφορές» (ni el serbio «prijave», el checo «hlášení», el húngaro
«bejelentés»…), y entre el aviso y el dron había cuatro palabras porque el griego pone la
actividad delante del dron. Desde entonces, además de las listas, la frase que no está en inglés
solo confirma el dron si su traducción inglesa guardada también lo afirma, y sin traducción espera.

Las frases de las fichas son las publicadas en droneobservatory.eu/datos (28/11/2026).
"""

import copy

import pytest

from almacen.base import Almacen
from esquema import Documento
from exportacion import citas
from proceso import auditoria_fichas, decidir, declaraciones, presencia
from recogida import control_fichas
from tests import ejemplos
from tests.test_presencia_reserva import lakenheath

GRIEGA = (
    "στις 13 Νοεμβρίου καταγράφηκαν αναφορές για μη εξουσιοδοτημένη δραστηριότητα drones στη "
    "RAF Lakenheath"
)
GRIEGA_EN = "on 13 November reports of unauthorised drone activity were recorded at RAF Lakenheath"
# EODI-2026-01027 (aeropuerto de Colonia/Bonn), dw.com en ucraniano, sin traducción guardada.
UCRANIANA = (
    "Представниця аеропорту повідомила, що близько 22:00 у небі над територією летовища "
    "помітили невідомий дрон."
)
UCRANIANA_EN = (
    "An airport spokeswoman said that an unknown drone was spotted in the sky above the airport "
    "grounds at around 22:00."
)

# Avisos, sospechas y respuestas en las lenguas que faltaban.
NO_AFIRMAN = [
    GRIEGA,
    # EODI-2025-00094, la policía de Nordland en novosti.rs: «recibimos avisos de un dron».
    "Primili smo prijave o dronu u vazduhu, ali nijednog pilota nismo identifikovali",
    "Policie obdržela hlášení o neoprávněné činnosti dronů nad letištěm",
    "A rendőrség bejelentéseket kapott drónokról a repülőtér felett",
    "A polícia recebeu denúncias de drones sobre o aeroporto",
    "Policija je primila dojave o dronu iznad zračne luke",
    "Полицията получи сигнали за дронове над летището",
    "Poliisi sai ilmoituksia drooneista lentokentän yllä",
    "Η αστυνομία έλαβε καταγγελίες για ύποπτα drones πάνω από τη βάση",
    "Policija je prejela prijave o dronu nad letališčem",
    "Policia mori njoftime për dron mbi aeroport",
    "Η Πολεμική Αεροπορία ανταποκρίθηκε σε δραστηριότητα drones κοντά στη βάση",
    "Vojska je reagovala na aktivnost dronova kod baze",
]
# Lo que sí lo afirma en esas lenguas: visto, detectado, sobrevoló.
AFIRMAN = [
    UCRANIANA,
    "Nad letištěm byl spatřen dron, uvedla policie.",
    "A rendőrség szerint drónt észleltek a repülőtér felett.",
    "Um drone foi avistado sobre o aeroporto, informou a ANA.",
    "Policija je potvrdila da je dron preletio iznad zračne luke.",
    "Над летището е забелязан дрон, съобщи полицията.",
    "Lentokentän yllä havaittiin drooni, kertoi poliisi.",
    "Ένα drone εντοπίστηκε πάνω από το αεροδρόμιο, ανακοίνωσε η αστυνομία.",
    "Dron je zaznan nad letališčem, je sporočila policija.",
]


@pytest.mark.parametrize("frase", NO_AFIRMAN)
def test_avisos_y_sospechas_en_otras_lenguas_no_confirman(frase: str) -> None:
    assert not declaraciones.atribuye_dron(frase), frase


@pytest.mark.parametrize("frase", AFIRMAN)
def test_lo_que_se_vio_en_otras_lenguas_sigue_confirmando(frase: str) -> None:
    assert declaraciones.atribuye_dron(frase), frase


def _fuente(frase: str, idioma: str, traduccion: str | None = None) -> Documento:
    fuente = {
        **ejemplos.fuente("gdelt-00001-declaracion-1", "B"),
        "medio": "Ministry of Defence (declaración oficial citada en inewsgr.com)",
        "es_autoridad": True,
        "idioma": idioma,
        "frase_origen": frase,
    }
    if traduccion is not None:
        fuente["traduccion"] = {"en": traduccion, "es": traduccion}
    return fuente


@pytest.mark.parametrize(
    ("traduccion", "reserva"),
    [
        (GRIEGA_EN, True),
        ("We received reports of a drone in the air, but we did not identify any pilot", True),
        ("the possible presence of a drone over the base", True),
        (UCRANIANA_EN, False),
        # Ni el dron sin identificar, ni una palabra que la regla no conoce, ni el dron negado
        # (EODI-2026-01000, 00777, 00648) son una reserva: eso lo dice la frase original.
        ("as a result of the observation of an unidentified drone", False),
        ("three unmanned aerial vehicles entered Latvian airspace", False),
        ("this is not a Russian drone, but a training machine of the Military Institute", False),
    ],
)
def test_la_reserva_en_la_traduccion(traduccion: str, reserva: bool) -> None:
    assert declaraciones.reserva_en_ingles(traduccion) is reserva


def test_la_frase_en_otra_lengua_confirma_con_su_traduccion(traducciones_reales: None) -> None:
    # La original griega con una lista que no la cazara: la traducción la caza igual.
    afirma = "Ένα drone εντοπίστηκε πάνω από τη βάση"
    assert declaraciones.afirma_el_dron(_fuente(afirma, "el", "A drone was spotted over the base"))
    assert not declaraciones.afirma_el_dron(_fuente(afirma, "el", GRIEGA_EN))
    # Sin traducción, espera.
    sin = _fuente(UCRANIANA, "uk")
    assert not declaraciones.afirma_el_dron(sin)
    assert declaraciones.espera_traduccion(sin)
    assert declaraciones.afirma_el_dron(_fuente(UCRANIANA, "uk", UCRANIANA_EN))
    # En inglés, como antes: la frase y nada más.
    assert declaraciones.afirma_el_dron(_fuente("A drone was spotted over the base", "en"))
    assert not declaraciones.espera_traduccion(_fuente("A drone was spotted over the base", "en"))


def test_la_traduccion_se_busca_en_la_tabla_del_almacen(traducciones_reales: None) -> None:
    almacen = Almacen.abrir()
    fuente = _fuente(UCRANIANA, "uk")
    assert declaraciones.traduccion_inglesa(fuente) is None
    clave = citas.huella_texto(UCRANIANA)
    assert clave == declaraciones.huella_texto(UCRANIANA)
    almacen.guardar_traducciones(
        {clave: {"es": "Una portavoz dijo que se vio un dron desconocido.", "en": UCRANIANA_EN}},
        "2026-11-28T12:00Z",
    )
    assert declaraciones.traduccion_inglesa(fuente) == UCRANIANA_EN
    assert declaraciones.afirma_el_dron(fuente)


def _lakenheath_griega() -> Documento:
    """00821 como volvió a confirmada el 28/11: las dos frases inglesas y la griega."""
    documento = lakenheath()
    documento["fuentes"].append(
        {**_fuente(GRIEGA, "el", GRIEGA_EN), "id": "gdelt-497a329d9c320721-declaracion-3"}
    )
    documento["afirmaciones"].append(
        declaraciones.afirmacion_presencia("gdelt-497a329d9c320721-declaracion-3")
    )
    return documento


def test_lakenheath_no_vuelve_a_confirmada_con_la_frase_griega(traducciones_reales: None) -> None:
    documento = _lakenheath_griega()
    decision = decidir.decidir_presencia(documento, confirmada=True)
    assert decision.valor == "no_confirmada"
    resultado = decidir.aplicar(copy.deepcopy(documento), confirmada=True)
    assert resultado["presencia_dron"] == "no_confirmada"
    es = "Posibles drones sobre la base de RAF Lakenheath, en Suffolk"
    assert resultado["titulo"]["es"] == es
    assert resultado["titulo"]["en"] == "Possible drones over RAF Lakenheath in Suffolk"
    assert not presencia.atribuida_por_autoridad(documento)


def test_auditoria_ab_falla_con_la_frase_en_otra_lengua(traducciones_reales: None) -> None:
    documento = _lakenheath_griega()
    assert auditoria_fichas.auditar([documento])["AB"] == ["EODI-2026-00821"]
    # Aunque la lista de avisos no conociera la palabra griega: la traducción lo dice.
    documento["fuentes"][-1]["frase_origen"] = "Ένα drone εντοπίστηκε πάνω από τη βάση"
    assert auditoria_fichas.confirmada_sin_frase_que_afirme(documento)
    # Y sin traducción tampoco la sostiene.
    del documento["fuentes"][-1]["traduccion"]
    assert auditoria_fichas.confirmada_sin_frase_que_afirme(documento)


def test_espera_la_traduccion_y_el_control_la_sube_al_tenerla(traducciones_reales: None) -> None:
    documento = lakenheath()
    documento["fuentes"] = [*documento["fuentes"][:1], _fuente(UCRANIANA, "uk")]
    documento["afirmaciones"] = []
    decision = decidir.decidir_presencia(documento)
    assert (decision.valor, decision.regla) == ("no_confirmada", decidir.ESPERA_TRADUCCION)
    documento["presencia_dron"] = "no_confirmada"
    assert control_fichas.subida_con_su_traduccion(documento) is None
    documento["fuentes"][1]["traduccion"] = {"en": UCRANIANA_EN, "es": UCRANIANA_EN}
    assert control_fichas.subida_con_su_traduccion(documento) == "Ministry of Defence"
    nuevo, motivos = control_fichas.con_titulo_y_presencia_decididos(documento)
    assert nuevo["presencia_dron"] == "confirmada"
    assert motivos[0].startswith("presencia confirmada: la traducción inglesa")
    # Nunca sube por una frase inglesa ni desde «descartada».
    documento["fuentes"][1]["idioma"] = "en"
    assert control_fichas.subida_con_su_traduccion(documento) is None
    documento["fuentes"][1]["idioma"] = "uk"
    documento["presencia_dron"] = "descartada"
    assert control_fichas.subida_con_su_traduccion(documento) is None
