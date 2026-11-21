"""La presencia del dron solo se confirma con una frase de autoridad que lo afirma.

EODI-2026-00821 (RAF Lakenheath, 13 de noviembre de 2026) quedó con la presencia confirmada y el
titular «Drones sobre la base de RAF Lakenheath, en Suffolk» con dos declaraciones que no afirman
ningún dron: la Fuerza Aérea de EE. UU. «responded to "suspected unauthorised drone activity"» y el
Ministerio de Defensa británico cuenta que «had responded to reports of unauthorised drone
activity». El suceso sigue confirmado (una autoridad lo reconoce); la presencia, no.

Las frases son las publicadas en las fichas (droneobservatory.eu/datos/incidentes, 21/11/2026).
"""

import copy

import pytest

from esquema import Documento
from proceso import auditoria_fichas, control_fichas, decidir, declaraciones, presencia
from tests import ejemplos
from tests.test_calidad_datos_3 import inc

USAF = (
    'US Air Force personnel at the RAF Lakenheath base in Britain responded to "suspected '
    'unauthorised drone activity" on Friday evening'
)
MOD = (
    "Britain's Ministry of Defence said US Air Force Security Forces personnel had responded to "
    "reports of unauthorised drone activity and that the situation had been"
)

# Frases de autoridad reales que afirman el dron: la regla las sigue confirmando.
AFIRMAN = [
    # EODI-2026-00084, Ministerul Apărării Naționale: un dron entró.
    "a drone entered Romanian airspace, the Ministry of National Defence reports on Friday.",
    # EODI-2026-00140, Nacionālie bruņotie spēki: derribado.
    "Nacionālie bruņotie spēki informē, ka 14. augustā Balvu novada Rugāju apkārtnē tika notriekts "
    "Ukrainas bezpilota lidaparāts, kas Latvijas gaisa telpā no Baltkrievijas teritorijas ielidoja",
    # EODI-2026-00661, Policja: recuperado.
    "Wieczorem policja poinformowała o odnalezieniu w miejscowości Wydrza, w gminie Grębów na "
    "Podkarpaciu, drona.",
    # EODI-2026-00183, Guardia Civil: localizado.
    "La Guardia Civil ha informado de la localización de un dron que penetró en la zona "
    "restringida",
    # EODI-2025-00122, ENAIRE: el aeropuerto cierra por un dron.
    "El avistamiento de un dron ha obligado a interrumpir temporalmente las operaciones en el "
    "aeropuerto de Palma la tarde de este domingo, ha informado Enaire.",
    # EODI-2026-00245, Försvarsmakten: visto.
    "Under besöket av det franska hangarfartyget Charles de Gaulle observerade ett av "
    "Försvarsmaktens fartyg att en drönare lyfte från ett ryskt signalspaningsfartyg i Öresund.",
    # EODI-2025-00051, Defensie (NL): visto («gesignaleerd»).
    "meerdere drones zijn gesignaleerd in het luchtruim rond het vliegveld. Dat meldt demissionair "
    "defensieminister Ruben Brekelmans.",
    # EODI-2025-00092, Skeyes: el verbo pasivo ya da el dron por visto.
    "Das teilte die Flugsicherung Skeyes mit. Die Drohne wurde gegen 19 Uhr gemeldet.",
    # EODI-2026-00593, la OTAN: los cazas despegan por un dron en el espacio aéreo lituano.
    "Possiamo confermare che due Eurofighter italiani sono decollati oggi in risposta a un drone "
    "nello spazio aereo lituano",
    # EODI-2026-00864, Ministerul Apărării (MD): «drone semnalate» que cayeron.
    "Ministerul Apărării a anunțat că cinci din cele șapte drone semnalate au avut impact la sol.",
    # EODI-2026-00864, Poliția (MD): los avisos y, después, los drones que sobrevolaron.
    "Poliția a înregistrat mai multe sesizări din municipiul Chișinău și raioanele Orhei și "
    "Florești, după ce două drone au survolat spațiul aerian al țării.",
    # EODI-2026-00123 y 00864: «de tip Shahed» no es un aviso.
    "Ministerul Afacerilor Externe al Republica Moldova condamnă ferm survolarea neautorizată a "
    "spațiului aerian național de către un aparat de zbor fără pilot, de tip Shahed",
    # EODI-2025-00013: la sospecha es sobre las personas, no sobre el dron.
    "To turister innbrakt etter mistanke om ulovlig droneflyvning.",
]

# Frases de autoridad reales que no afirman el dron: avisos, sospecha o respuesta.
NO_AFIRMAN = [
    USAF,  # EODI-2026-00821
    MOD,  # EODI-2026-00821
    # EODI-2025-00072, Brussels Airport.
    "Il n'y a actuellement pas de vols au départ de ou à l'arrivée à Brussels Airport en raison "
    "de signalements de drones",
    # EODI-2025-00344, Theo Francken.
    "Afgelopen nacht drie meldingen van drones boven Kleine Brogel, groter type op grotere hoogte.",
    # EODI-2026-00500, Politiet.
    "Politiet har torsdag rykket ut til Nato-kaia i Sørreisa etter melding om droneflyvning.",
    # EODI-2026-00077, aeropuerto de Sofía.
    'В неделя вечер са постъпили три сигнала за дронове на Летище "Васил Левски", потвърдиха от '
    "пресцентъра на аерогарата за ФОКУС.",
    # EODI-2025-00183, Naviair.
    "Vi har en begrundet mistanke om droneaktivitet ved Aalborg Lufthavn og har derfor lukket for "
    "starter- og landinger",
    # EODI-2025-00060, Lietuvos oro uostai.
    "Mūsų turimomis žiniomis, sprendimą lėmė galimai pastebėtas dronas",
    # EODI-2025-00043, Rīgas lidosta.
    "Rīgas lidosta šodien plkst. 14.20 sniedza atbildīgajiem dienestiem informāciju par iespējamu "
    "bezpilota lidaparāta atrašanos lidojumu ierobežojumu zonā",
    # EODI-2026-00055, Policja.
    "Policja potwierdziła nam, że jeden z pilotów zgłosił obecność obiektu przypominającego drona.",
    # EODI-2026-00725, MApN.
    "în urma notificării transmise de către Statul Major al Fortelor Aeriene / MApN despre "
    "posibilitatea pătrunderii unei drone în spațiul aerian național",
    # En las lenguas de las fuentes: avisos y sospecha.
    "Die Polizei reagierte auf Hinweise auf eine Drohne über dem Gelände",
    "Policja otrzymała zgłoszenie o dronie nad lotniskiem",
    "Poliția a primit sesizări despre o dronă deasupra aeroportului",
    "La police est intervenue après des signalements de drones au-dessus de la base",
    "La Guardia Civil recibió avisos de un dron sobre la prisión",
    "Policija gavo pranešimų apie droną virš oro uosto",
    "Politiet modtog anmeldelser om droner over havnen",
    "De politie kreeg meldingen over een drone boven de kazerne",
    "I carabinieri sono intervenuti dopo le segnalazioni di un drone sopra la base",
    "Die Bundeswehr meldete verdächtige Drohnenflüge über dem Truppenübungsplatz",
    "Policja zbada podejrzaną aktywność dronów nad lotniskiem",
    "The army responded to drone activity over the base",
]


@pytest.mark.parametrize("frase", AFIRMAN)
def test_la_frase_que_afirma_el_dron_lo_confirma(frase: str) -> None:
    assert declaraciones.atribuye_dron(frase), frase


@pytest.mark.parametrize("frase", NO_AFIRMAN)
def test_avisos_sospecha_o_respuesta_no_confirman_el_dron(frase: str) -> None:
    assert not declaraciones.atribuye_dron(frase), frase
    # El suceso sí lo reconocen: sostienen el estado «confirmado».
    if frase in (USAF, MOD):
        assert declaraciones.habla_del_suceso(frase)


def lakenheath() -> Documento:
    """EODI-2026-00821 como se publicó: confirmado, presencia confirmada por las dos frases."""
    documento = inc("EODI-2026-00821", "2026-11-13T21:15Z", "hora", "RAF Lakenheath",
                    (52.409, 0.561), "GB", fuentes=1)  # fmt: skip
    documento["objetivo"] = {"categoria": "base_militar", "nombre": "RAF Lakenheath"}
    documento["tipo"] = "sobrevuelo"
    documento["fuentes"][0]["frase_origen"] = (
        'US Air Force personnel at an air base in the UK have responded to "suspected '
        'unauthorised drone activity"'
    )
    for numero, (autoridad, frase) in enumerate(
        (("US Air Force", USAF), ("Ministry of Defence", MOD)), 1
    ):
        documento["fuentes"].append({
            **ejemplos.fuente(f"gdelt-00821-declaracion-{numero}", "B"),
            "fecha": ejemplos.instante("2026-11-14T02:45Z", "aproximada"),
            "medio": f"{autoridad} (declaración oficial citada en rnz.co.nz)",
            "es_autoridad": True,
            "frase_origen": frase,
        })  # fmt: skip
    documento["estado"] = {
        "actual": "confirmado",
        "historial": [
            {"estado": "notificado", "fecha": documento["fuentes"][0]["fecha"],
             "fuente_id": documento["fuentes"][0]["id"]},
            {"estado": "confirmado", "fecha": documento["fuentes"][1]["fecha"],
             "fuente_id": "gdelt-00821-declaracion-1"},
        ],
    }  # fmt: skip
    documento["presencia_dron"] = "confirmada"
    documento["afirmaciones"] = [
        declaraciones.afirmacion_presencia("gdelt-00821-declaracion-1"),
        declaraciones.afirmacion_presencia("gdelt-00821-declaracion-2"),
    ]
    documento["titulo"] = {"es": "Drones sobre la base de RAF Lakenheath, en Suffolk",
                           "en": "Drones over RAF Lakenheath in Suffolk"}  # fmt: skip
    return documento


def test_lakenheath_el_suceso_confirmado_y_la_presencia_no() -> None:
    documento = lakenheath()
    assert presencia.sin_base(documento)
    assert not presencia.atribuida_por_autoridad(documento)
    decision = decidir.decidir_presencia(documento, confirmada=True)
    assert (decision.valor, decision.regla) == ("no_confirmada", "sin_autoridad")
    resultado = decidir.aplicar(copy.deepcopy(documento), confirmada=True)
    assert resultado["estado"]["actual"] == "confirmado"
    assert resultado["presencia_dron"] == "no_confirmada"
    # El titular sigue a la presencia: no afirma «Drones sobre…».
    assert resultado["titulo"]["es"].startswith("Posibles drones")
    assert resultado["titulo"]["en"].startswith("Possible drones")
    # El estado lo siguen sosteniendo las declaraciones que reconocen el suceso.
    assert control_fichas.estado_sin_respaldo(documento) is None


def test_lakenheath_la_regla_la_corrige_con_su_motivo_y_su_frase() -> None:
    documento = lakenheath()
    # No es dudosa: las citas nombran el dron, solo que como sospecha y como avisos.
    conocidas = {
        f"gdelt-00821-declaracion-{n}": {"afirma": "drones", "frase": f}
        for n, f in ((1, USAF), (2, MOD))
    }
    assert not presencia.dudosa_por(documento, conocidas)
    corregido = presencia.quitar_sin_base(documento)
    assert corregido["presencia_dron"] == "no_confirmada"
    assert not [a for a in corregido["afirmaciones"] if a["valor"] == "confirmada"]
    motivo = presencia.motivo_sin_base(documento)
    assert motivo.startswith(presencia.MOTIVO_RESERVA)
    assert "suspected unauthorised drone activity" in motivo
    assert "reports of unauthorised drone activity" in motivo


def test_la_cita_que_no_nombra_el_dron_sigue_siendo_dudosa() -> None:
    documento = lakenheath()
    documento["fuentes"][1]["frase_origen"] = "Das bestätigte eine Sprecherin der Bundeswehr."
    conocidas = {"gdelt-00821-declaracion-1": {"afirma": "drones"}}
    assert presencia.dudosa_por(documento, conocidas)


def test_auditoria_ab_presencia_confirmada_sin_frase_que_afirme() -> None:
    documento = lakenheath()
    assert auditoria_fichas.confirmada_sin_frase_que_afirme(documento)
    resultado = auditoria_fichas.auditar([documento])
    assert resultado["AB"] == ["EODI-2026-00821"]
    corregido = decidir.aplicar(copy.deepcopy(documento), confirmada=True)
    assert not auditoria_fichas.confirmada_sin_frase_que_afirme(corregido)
    # Con una frase de autoridad que afirma el dron sigue confirmada y no cuenta en AB.
    documento["fuentes"][2]["frase_origen"] = AFIRMAN[0]
    assert decidir.decidir_presencia(documento, confirmada=True).valor == "confirmada"
    assert not auditoria_fichas.confirmada_sin_frase_que_afirme(documento)


def test_el_cerrojo_deja_pasar_la_correccion() -> None:
    # La presencia de 00821 no la decide ninguna autoridad que afirme el dron: bajarla no es un
    # cambio a algo protegido, y el titular la sigue.
    from proceso import protegido

    guardado = lakenheath()
    nuevo = decidir.aplicar(presencia.quitar_sin_base(copy.deepcopy(guardado)), confirmada=True)
    assert nuevo["presencia_dron"] == "no_confirmada"
    veredicto = protegido.juzgar(guardado, nuevo, ["proceso.presencia.revisar"], lambda fuente: "")
    assert veredicto.retenidos == []
