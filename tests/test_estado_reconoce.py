"""El estado «confirmado» solo lo da una frase de autoridad que reconoce el suceso.

EODI-2026-00937 (alarma en la base de Sigonella, Sicilia, 20 de noviembre de 2026) pasó de
«notificado» a «confirmado» en la recogida de las 22:17 UTC del 21/11 con una sola declaración:
«Zdarzenie bada włoska żandarmeria wojskowa.» («El suceso lo investiga la policía militar
italiana»), una frase de wiadomosci.wp.pl que no atribuye ninguna palabra a la autoridad. El mismo
artículo dice «Incydent nie został oficjalnie potwierdzony przez władze bazy.» Que una autoridad
investigue, o que la avisen, no reconoce el suceso; un artículo que dice que no está confirmado
oficialmente no lo confirma.

Las frases son las de las fichas en la base y en la web (21/11/2026).
"""

import copy
from datetime import UTC, datetime

import pytest

from esquema import Documento
from proceso import auditoria_fichas, control_fichas, decidir, declaraciones
from tests import ejemplos
from tests.test_calidad_datos_3 import inc

BADA = "Zdarzenie bada włoska żandarmeria wojskowa."
ZANDARMERIA = "Żandarmeria wojskowa de Italia"
NO_CONFIRMADO = "Incydent nie został oficjalnie potwierdzony przez władze bazy."
ENLACE_WP = (
    "https://wiadomosci.wp.pl/dron-nad-strategiczna-baza-nato-alarm-na-sycylii-7353513421764608a"
)

# Frases de autoridad reales que reconocen el suceso (aunque no nombren el dron o digan que era
# otra cosa): siguen confirmando. (ficha, quien declara, frase)
RECONOCEN = [
    ("EODI-2025-00136", "Skeyes",
     "flight operations at the airport in Zaventem were suspended for about half an hour, "
     "Belgian air navigation service provider Skeyes confirmed."),
    ("EODI-2026-00163", "Heathrow Airport",
     "A Heathrow spokesperson said operations had been temporarily paused but have since "
     "resumed."),
    ("EODI-2026-00303", "Bundespolizei",
     "Es habe kein Flugzeug mehr abheben dürfen, erklärte ein Sprecher der Bundespolizei."),
    ("EODI-2026-00322", "Polizei Hamburg",
     "Für rund 15 Minuten seien am Samstagabend keine Starts und Landungen möglich gewesen, "
     "sagte ein Polizeisprecher."),
    ("EODI-2026-00511", "Polska Agencja Żeglugi Powietrznej",
     "Polska Agencja Żeglugi Powietrznej przekazała, że lotniska w Lublinie i Rzeszowie "
     "wstrzymały operacje lotnicze."),
    ("EODI-2026-00747", "Ministerul Apărării Naționale",
     "la ora 23.43 a fost transmis un mesaj RO-Alert."),
    ("EODI-2026-00111", "Ministerul Apărării Naționale",
     "Potrivit Ministerului Apărării Naționale, incidentul a fost detectat la ora 02.23."),
    # El resultado de una investigación sí reconoce el suceso.
    ("EODI-2025-00203", "Royal Netherlands Marechaussee",
     "an investigation showed no drone was detected on radar and that the object was likely a "
     "balloon."),
    ("EODI-2026-00923", "Ministerstwo Obrony Narodowej",
     "Polish Defence Minister Władysław Kosiniak-Kamysz confirmed that three objects had entered "
     "the country’s airspace"),
    # La autoridad que cuenta que avisó a otras, no la avisada.
    ("EODI-2026-00032", "Viešojo saugumo tarnyba",
     "Apie įvykį nedelsiant informuotos atsakingos tarnybos"),
    ("EODI-2025-00246", "Ministère de la Défense de Lituanie",
     "A vizsgálatok szerint a gép egy két kilogrammos robbanószerkezetet szállított, amelyet a "
     "hatóságok hatástalanítottak"),
    ("EODI-2026-00276", "Landeskriminalamt",
     "Das Landeskriminalamt (LKA) teilt auf Anfrage mit, der Drohnenfund sei seit "
     "Montagnachmittag bekannt."),
]  # fmt: skip

# Frases de autoridad reales que no reconocen el suceso: solo investiga, recibe el aviso, o la
# fuente dice que no está confirmado oficialmente. (ficha, quien declara, frase, por qué)
NO_RECONOCEN = [
    ("EODI-2026-00937", ZANDARMERIA, BADA, "investiga"),
    ("EODI-2025-00192", "Bayerisches Landeskriminalamt",
     "Das Bayerische Landeskriminalamt (LKA) ermittelt.", "investiga"),
    ("EODI-2025-00371", "Politie Mechelen",
     "L'appareil endommagé a été remis à la police, qui a ouvert une enquête.", "investiga"),
    ("EODI-2026-00278", "Gardaí",
     "Though the sighting is being taken seriously, Garda sources said the primary goal of the "
     "inquiry was to test the accuracy of the report.", "investiga"),
    ("EODI-2026-00362", "Ministerstwo Obrony Narodowej",
     "O sprawie poinformowano prokuraturę oraz Ministerstwo Obrony Narodowej", "receptor"),
    ("EODI-2025-00209", "Donald Tusk, Gobierno de Polonia",
     'The police are investigating the circumstances of the incident," Tusk wrote on X.',
     "investiga"),
    ("EODI-2025-00287", "Verteidigungsministerium",
     "Das Verteidigungsministerium in Brüssel hat die Einleitung einer Untersuchung angekündigt.",
     "investiga"),
    ("EODI-2026-00144", "Polizeidienststelle Euskirchen",
     "Die Polizeidienststelle Euskirchen habe mittlerweile die Ermittlungen aufgenommen.",
     "investiga"),
    ("EODI-2026-00098", "Poliția de Frontieră a Republicii Moldova",
     "Poliția de Frontieră a Republicii Moldova a fost alertată de către autoritățile din "
     "Ucraina cu privire la survolarea spațiului aerian moldovenesc", "receptor"),
    ("EODI-2026-00418", "Poliția de Frontieră și Forțele Navale Române",
     "Poliția de Frontieră și Forțele Navale Române au fost notificate oficial.", "receptor"),
    ("EODI-2026-00937", "wiadomosci.wp.pl", NO_CONFIRMADO, "no_oficial"),
]  # fmt: skip


@pytest.mark.parametrize(("ficha", "autoridad", "frase"), RECONOCEN)
def test_la_frase_que_reconoce_el_suceso_lo_confirma(
    ficha: str, autoridad: str, frase: str
) -> None:
    assert declaraciones.reconoce_suceso(frase, autoridad), ficha


@pytest.mark.parametrize(("ficha", "autoridad", "frase", "motivo"), NO_RECONOCEN)
def test_investigar_o_recibir_el_aviso_no_lo_confirma(
    ficha: str, autoridad: str, frase: str, motivo: str
) -> None:
    assert declaraciones.no_reconoce(frase, autoridad) == motivo, ficha


def test_no_confirmado_oficialmente_no_es_la_causa_ni_el_dron() -> None:
    assert declaraciones.no_confirmado_oficialmente(f"Alarm w bazie. {NO_CONFIRMADO}") == (
        NO_CONFIRMADO
    )
    assert declaraciones.no_confirmado_oficialmente("Ministerul Apărării nu confirmă incidentul")
    # EODI-2026-00669: lo que no está confirmado es la causa; EODI-2025-00055: el dron.
    assert declaraciones.no_confirmado_oficialmente(
        "Cauza incidentului nu a fost confirmată oficial."
    ) is None  # fmt: skip
    assert declaraciones.no_confirmado_oficialmente(
        "Munich Airport halts flights after unconfirmed drone sightings"
    ) is None  # fmt: skip


def sigonella() -> Documento:
    """EODI-2026-00937 como se publicó: confirmado por la frase de la żandarmeria."""
    documento = inc("EODI-2026-00937", "2026-11-20T00:00Z", "dia", "Sigonella",
                    (37.4, 14.92), "IT", fuentes=1)  # fmt: skip
    documento["objetivo"] = {"categoria": "base_militar", "nombre": "Sigonella"}
    documento["tipo"] = "sobrevuelo"
    documento["fuentes"][0]["frase_origen"] = "«Droni sulla base di Sigonella in Sicilia»."
    documento["fuentes"].append({
        **ejemplos.fuente("gdelt-fa74838fa189dcc3", "C"),
        "enlace": ENLACE_WP,
        "medio": "wiadomosci.wp.pl",
        "fecha": ejemplos.instante("2026-11-21T20:45Z", "aproximada"),
        "frase_origen": "W piątek ogłoszono alarm w strategicznej bazie lotniczej Sigonella na "
        "Sycylii po wykryciu drona w jej przestrzeni",
    })  # fmt: skip
    documento["fuentes"].append({
        **ejemplos.fuente("gdelt-fa74838fa189dcc3-declaracion-1", "B"),
        "enlace": ENLACE_WP,
        "medio": f"{ZANDARMERIA} (declaración oficial citada en wiadomosci.wp.pl)",
        "fecha": ejemplos.instante("2026-11-21T20:45Z", "aproximada"),
        "es_autoridad": True,
        "frase_origen": BADA,
    })  # fmt: skip
    documento["estado"] = {
        "actual": "confirmado",
        "historial": [
            {"estado": "notificado", "fecha": documento["fuentes"][0]["fecha"],
             "fuente_id": documento["fuentes"][0]["id"]},
            {"estado": "confirmado", "fecha": documento["fuentes"][2]["fecha"],
             "fuente_id": "gdelt-fa74838fa189dcc3-declaracion-1"},
        ],
    }  # fmt: skip
    documento["presencia_dron"] = "no_confirmada"
    return documento


def test_sigonella_la_regla_la_baja_con_su_motivo_y_su_frase() -> None:
    documento = sigonella()
    assert control_fichas.estado_sin_respaldo(documento) == "confirmado"
    bajado = control_fichas.bajar_estado(documento, ejemplos.instante("2026-11-22T00:17Z"))
    assert bajado is not None and bajado["estado"]["actual"] == "notificado"
    motivo = bajado["estado"]["historial"][-1]["motivo"]["es"]
    assert motivo.startswith("Ninguna fuente oficial da el estado «confirmado»")
    assert control_fichas.SIN_RECONOCER["es"] in motivo and BADA in motivo
    # Al guardar, decidir no la vuelve a confirmar.
    resultado = decidir.aplicar(copy.deepcopy(bajado))
    assert resultado["estado"]["actual"] == "notificado"
    # Hasta que la regla la baja, decidir sigue el paso guardado.
    assert decidir.decidir_estado(sigonella()).valor == "confirmado"
    # La presencia no la toca esta regla.
    assert resultado["presencia_dron"] == "no_confirmada"


def test_sigonella_la_declaracion_no_confirma_al_aplicarla() -> None:
    documento = sigonella()
    documento["estado"] = {
        "actual": "notificado",
        "historial": documento["estado"]["historial"][:1],
    }
    documento["fuentes"] = documento["fuentes"][:2]
    declaracion = {
        "autoridad": ZANDARMERIA, "pais": "IT", "categoria": "fuerzas_armadas",
        "afirma": "incidente", "autor": "", "autor_tipo": "", "autor_pais": "",
        "autor_situacion": "", "cita_literal": False, "fuente": 1, "frase": BADA,
    }  # fmt: skip
    resultado = declaraciones.aplicar(documento, [declaracion], [ENLACE_WP])
    assert resultado["estado"]["actual"] == "notificado"
    # La declaración entra como fuente (lo que investiga va a la ficha), sin confirmar.
    assert any(f["id"] == "gdelt-fa74838fa189dcc3-declaracion-1" for f in resultado["fuentes"])
    assert decidir.decidir_estado(resultado).valor == "notificado"


def test_el_articulo_que_dice_que_no_esta_confirmado_no_confirma() -> None:
    texto = (
        "W piątek ogłoszono alarm w strategicznej bazie lotniczej Sigonella. Policja wojskowa "
        f"potwierdziła alarm w bazie. {NO_CONFIRMADO}"
    )
    declaracion = {"fuente": 1, "afirma": "incidente",
                   "frase": "Policja wojskowa potwierdziła alarm w bazie."}  # fmt: skip
    assert declaraciones.validas([declaracion], [texto]) == []
    # La que niega el suceso o el dron sí vale.
    niega = {**declaracion, "afirma": "sin_drones"}
    assert declaraciones.validas([niega], [texto]) != []
    # En una ficha ya guardada: la frase de otra fuente del mismo artículo.
    documento = sigonella()
    documento["fuentes"][2]["frase_origen"] = "Policja wojskowa potwierdziła alarm w bazie."
    assert declaraciones.reconoce(documento["fuentes"][2])
    documento["fuentes"][1]["frase_origen"] = NO_CONFIRMADO
    assert not declaraciones.reconoce(documento["fuentes"][2], documento)


def test_otra_autoridad_que_reconoce_el_suceso_lo_sostiene() -> None:
    # EODI-2026-00515: el paso es de una frase que solo investiga, y otra autoridad lo reconoce
    # sin nombrar el dron.
    documento = sigonella()
    documento["fuentes"].append({
        **ejemplos.fuente("gdelt-otra-declaracion-1", "B"),
        "medio": "Bundespolizei (declaración oficial citada en merkur.de)",
        "es_autoridad": True,
        "frase_origen": "Wie die Bundespolizei mitteilt, sorgte ein rätselhaftes Flugobjekt für "
        "Aufregung.",
    })  # fmt: skip
    assert control_fichas.estado_sin_respaldo(documento) is None
    assert not auditoria_fichas.estado_sin_frase_que_reconozca(documento)


def test_auditoria_ac() -> None:
    documento = sigonella()
    assert auditoria_fichas.estado_sin_frase_que_reconozca(documento)
    assert auditoria_fichas.auditar([documento])["AC"] == ["EODI-2026-00937"]
    bajado = control_fichas.bajar_estado(documento, ejemplos.instante("2026-11-22T00:17Z"))
    assert bajado is not None
    assert not auditoria_fichas.estado_sin_frase_que_reconozca(bajado)
    # Con una frase de autoridad que reconoce el suceso, no cuenta.
    documento["fuentes"][2]["frase_origen"] = RECONOCEN[0][2]
    assert not auditoria_fichas.estado_sin_frase_que_reconozca(documento)


def test_el_cerrojo_deja_pasar_la_bajada() -> None:
    # El estado de 00937 no lo decide una autoridad que reconozca el suceso: bajarlo no es un
    # cambio a algo protegido.
    from proceso import protegido

    guardado = sigonella()
    bajado = control_fichas.bajar_estado(guardado, ejemplos.instante("2026-11-22T00:17Z"))
    assert bajado is not None
    nuevo = decidir.aplicar(copy.deepcopy(bajado))
    veredicto = protegido.juzgar(
        guardado, nuevo, ["recogida.control_fichas.reglas_deterministas"], lambda fuente: ""
    )
    assert veredicto.retenidos == []
    # Una confirmación que sí da una autoridad que reconoce el suceso sigue protegida.
    reconocida = sigonella()
    reconocida["fuentes"][2]["frase_origen"] = RECONOCEN[0][2]
    rebajada = copy.deepcopy(reconocida)
    rebajada["estado"] = {
        "actual": "notificado",
        "historial": [*reconocida["estado"]["historial"], {
            **reconocida["estado"]["historial"][0],
            "motivo": {"es": "prueba", "en": "test"},
        }],
    }  # fmt: skip
    retenidos = protegido.juzgar(reconocida, rebajada, ["prueba"], lambda f: "").retenidos
    assert [c.dato for c in retenidos] == ["estado"]


def test_la_rebaja_no_manda_aviso() -> None:
    from recogida import avisos

    config = avisos.configuracion()
    ahora = datetime(2026, 11, 22, 0, 30, tzinfo=UTC)
    # Confirmada, se avisaba (el aviso del 21/11).
    assert avisos.clasificar(sigonella(), config, ahora) is not None
    bajado = control_fichas.bajar_estado(sigonella(), ejemplos.instante("2026-11-22T00:17Z"))
    assert bajado is not None
    # Notificada y sin fuente oficial leída directamente: no se avisa.
    assert avisos.clasificar(bajado, config, ahora) is None


# --- Antes de bajar, el artículo original (revisión del 22/11/2026) ------------------------------
#
# Cuatro de las cinco fichas que la regla bajaba tenían en su artículo original una frase que el
# periódico atribuye a una autoridad y que reconoce el suceso; la ficha había guardado la débil.
# Oraciones literales de los artículos (leídos el 22/11/2026).
ARTICULO_RECONOCE = [
    ("EODI-2026-00362", "W czwartek, 12 marca Wielkopolska Policja poinformowała o odnalezieniu na "
     "terenie kopalni w miejscowości Galczyce (pow. koniński) drona."),
    ("EODI-2025-00371", "De Mechelaar is ook niet gebrevetteerd als dronepiloot, en dat is "
     'verplicht voor het gebruik van een toestel met dat gewicht", zegt Dirk Van de Sande van '
     "politiezone Rivierenland."),
    ("EODI-2025-00192", "„Die eingesetzten Polizeibeamten konnten bis zu zehn Drohnen feststellen, "
     "die den Bereich überflogen“, wird mitgeteilt."),
    ("EODI-2025-00192", "„Auch dort wurden drei Drohnen gesehen, die Fahndung verlief ohne "
     "Ergebnis“, teilen das LKA und die Generalstaatsanwaltschaft mit."),
    ("EODI-2026-00278", "AirNav, a State-owned company that provides air traffic control services "
     "to Irish airports, confirmed a report of a drone sighting had been made."),
]  # fmt: skip
# Oraciones que no valen: fuentes sin nombre, solo la investigación, el periódico que no cita a
# nadie, o una palabra de otra lengua que parece un verbo de decir.
ARTICULO_NO_RECONOCE = [
    ("EODI-2026-00278", "Though the sighting is being taken seriously, Garda sources said the "
     "primary goal of the inquiry was to test the accuracy of the report."),
    ("EODI-2026-00278", "Garda headquarters said it was aware of the reported sighting and was "
     "continuing to investigate it, alongside the Department of Defence and Defence Forces."),
    ("EODI-2026-00937", "L'allarme alla base americana di Sigonella, a quanto si apprende da fonti "
     "informate, è scattato ieri alle 17,50 dopo che droni quadricotteri a uso civile sono stati "
     "avvistati nella zona degli alloggi."),
    ("EODI-2026-00937", "Dochodzenie w sprawie incydentu prowadzą karabinierzy."),
    ("EODI-2025-00371", "Le propriétaire d'un drone qui avait fini sa course dans la cour d'une "
     "école secondaire de Malines a été retrouvé par la police locale."),
]  # fmt: skip
WP = (
    "W piątek ogłoszono alarm w strategicznej bazie lotniczej Sigonella na Sycylii po wykryciu "
    f"drona w jej przestrzeni. {BADA} {NO_CONFIRMADO} Według policji wojskowej dron przeleciał "
    "nad kwaterami."
)


@pytest.mark.parametrize(("ficha", "oracion"), ARTICULO_RECONOCE)
def test_la_frase_que_el_periodico_atribuye_a_la_autoridad_vale(ficha: str, oracion: str) -> None:
    assert declaraciones.frase_que_reconoce(f"Texto del periódico. {oracion}") == oracion, ficha


@pytest.mark.parametrize(("ficha", "oracion"), ARTICULO_NO_RECONOCE)
def test_fuentes_sin_nombre_o_la_investigacion_no_valen(ficha: str, oracion: str) -> None:
    assert declaraciones.frase_que_reconoce(oracion) is None, ficha


def test_el_articulo_que_dice_que_no_esta_confirmado_no_sostiene_nada() -> None:
    # Aunque traiga una frase atribuida: el artículo dice que nadie lo ha confirmado.
    assert declaraciones.frase_que_reconoce(WP) is None


def test_el_control_no_baja_si_el_articulo_lo_reconoce() -> None:
    from recogida import control_fichas as control

    documento = sigonella()
    enlaces = {f["enlace"] for f in documento["fuentes"]}
    # 00937: los artículos se leen y ninguno lo reconoce: se baja.
    assert control.articulo_que_lo_reconoce(documento, lambda e: dict.fromkeys(e, WP)) is None
    # Un artículo que no se pudo leer: no se baja (un fallo nunca baja nada).
    leidos = {e: WP for e in enlaces}
    leidos[ENLACE_WP] = ""
    sin_leer = control.articulo_que_lo_reconoce(documento, lambda e: leidos)
    assert sin_leer is not None and sin_leer.startswith("sin leer")
    # 00362: el artículo trae la frase de la policía: el estado se queda, con esa frase.
    policia = f"Na terenie kopalni znaleziono drona. {ARTICULO_RECONOCE[0][1]}"
    sostiene = control.articulo_que_lo_reconoce(documento, lambda e: dict.fromkeys(e, policia))
    assert sostiene is not None and "Wielkopolska Policja poinformowała" in sostiene


def test_la_extraccion_se_queda_con_la_frase_que_reconoce() -> None:
    # El extractor devolvió la frase débil de la policía; el artículo trae otra suya que reconoce
    # el suceso: se guarda esa.
    texto = (
        "Na terenie kopalni znaleziono drona. Sprawę bada Wielkopolska Policja. "
        f"{ARTICULO_RECONOCE[0][1]}"
    )
    declaracion = {"fuente": 1, "afirma": "drones", "autoridad": "Wielkopolska Policja",
                   "frase": "Sprawę bada Wielkopolska Policja."}  # fmt: skip
    [valida] = declaraciones.validas([declaracion], [texto])
    assert valida["frase"] == ARTICULO_RECONOCE[0][1]
    # Si la autoridad no es la de la frase que reconoce, no se cambia.
    otra = {**declaracion, "autoridad": "Ministerstwo Obrony Narodowej"}
    assert declaraciones.validas([otra], [texto])[0]["frase"] == otra["frase"]


def test_las_cuatro_fichas_tienen_su_cita_revisada() -> None:
    from recogida import revisados

    citas = {c["incidente"]: c for c in revisados.cargar()["citas"]}
    for ficha in ("EODI-2025-00192", "EODI-2025-00371", "EODI-2026-00278", "EODI-2026-00362"):
        cita = citas[ficha]
        assert declaraciones.reconoce_suceso(cita["frase"], cita["declaracion"]["autoridad"])
    assert "EODI-2026-00937" not in citas
