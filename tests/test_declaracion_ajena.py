"""Una declaración citada no pone en boca de una autoridad una frase que no es suya.

EODI-2026-00362 (dron hallado en la mina de Gałczyce, Polonia, 12 de marzo de 2026) publicaba la
fuente gdelt-f1d6a873ded9547d-declaracion-1, «Ministerstwo Obrony Narodowej (declaración oficial
citada en se.pl)», con la frase «O sprawie poinformowano prokuraturę oraz Ministerstwo Obrony
Narodowej»: es el periódico contando que se informó al Ministerio; el Ministerio no dijo nada. El
extractor la devolvió como declaración del Ministerio y `declaraciones.validas` solo comprobaba
que la frase estuviera en el texto. Desde el PR 483 ya no sostenía el estado (la autoridad es
quien recibe el aviso), pero seguía publicada como declaración del Ministerio.

Las frases son las de la base y la web del 22/11/2026. De las 931 declaraciones citadas de las
fichas vigentes, 9 ponen a la autoridad como quien recibe el aviso o el caso, o solo cuentan que
investiga, sin darle la palabra.
"""

import copy

import pytest

from esquema import Documento
from proceso import auditoria_fichas, decidir, declaraciones, protegido
from recogida import control_fichas
from tests import ejemplos
from tests.test_calidad_datos_3 import inc

ENLACE_SE = (
    "https://se.pl/poznan/na-terenie-kopalni-znaleziono-drona-teren-zabezpieczaja-policjanci-"
    "aa-LXVy-CxKN-sh5V.html"
)
MON = "O sprawie poinformowano prokuraturę oraz Ministerstwo Obrony Narodowej"
POLICJA = (
    "W czwartek, 12 marca Wielkopolska Policja poinformowała o odnalezieniu na terenie kopalni w "
    "miejscowości Galczyce (pow. koniński) drona."
)

# (ficha, quien declara según la ficha, motivo, frase): las 9 de la base del 22/11/2026.
AJENAS = [
    ("EODI-2026-00362", "Ministerstwo Obrony Narodowej", "receptor", MON),
    ("EODI-2026-00418", "Poliția de Frontieră și Forțele Navale Române", "receptor",
     "Poliția de Frontieră și Forțele Navale Române au fost notificate oficial."),
    ("EODI-2026-00098", "Poliția de Frontieră a Republicii Moldova", "receptor",
     "Poliția de Frontieră a Republicii Moldova a fost alertată de către autoritățile din "
     "Ucraina cu privire la survolarea spațiului aerian moldovenesc"),
    ("EODI-2026-00131", "Bundespolizei", "receptor",
     "La policía fue alertada para investigar el incidente, aunque el objeto no volvió a ser "
     "visto."),
    ("EODI-2026-00144", "Euskirchener Polizei", "receptor",
     "Der Fall sei an die Euskirchener Polizei übergeben worden, die die Ermittlungen "
     "aufgenommen habe."),
    ("EODI-2025-00371", "Politie Mechelen", "receptor",
     "L'appareil endommagé a été remis à la police, qui a ouvert une enquête."),
    ("EODI-2026-00144", "Polizeidienststelle Euskirchen", "investiga",
     "Die Polizeidienststelle Euskirchen habe mittlerweile die Ermittlungen aufgenommen."),
    ("EODI-2025-00192", "Bayerisches Landeskriminalamt", "investiga",
     "Das Bayerische Landeskriminalamt (LKA) ermittelt."),
    ("EODI-2026-00937", "Żandarmeria wojskowa de Italia", "investiga",
     "Zdarzenie bada włoska żandarmeria wojskowa."),
]  # fmt: skip
# Frases reales en que la autoridad sí habla, aunque la avisaran o investigue.
SUYAS = [
    ("EODI-2026-00032", "Viešojo saugumo tarnyba",
     "Apie įvykį nedelsiant informuotos atsakingos tarnybos"),
    ("EODI-2026-00118", "Ministerul Apărării Naționale",
     "Ministerul Apărării Naționale a transmis că a fost informat joi, în jurul orei 8:30, "
     "despre prezența unui fragment de dronă aeriană"),
    ("EODI-2026-00263", "Poliția",
     "Poliția spune că a fost sesizată în jurul orei 05:40, după ce drona a fost observată la "
     "mică distanță"),
    ("EODI-2025-00287", "Verteidigungsministerium",
     "Das Verteidigungsministerium in Brüssel hat die Einleitung einer Untersuchung "
     "angekündigt."),
    ("EODI-2025-00287", "Ministry of Defense",
     "The Belgian local media made it known by quoting the Ministry of Defense that is "
     "investigating the accident."),
    ("EODI-2025-00030", "Københavns Politi",
     "Sagen efterforskes, og vi udtaler os ikke nærmere om verserende efterforskninger"),
    ("EODI-2025-00048", "Bundespolizei",
     "Wie die Bundespolizei mitteilt, wurde sie auf den Drohnenflug aufmerksam, konnte den "
     "Piloten in der Nähe der Baustelle antreffen und anschließend den Einsatzkräften der Polizei "
     "Bremen übergeben."),
    ("EODI-2026-00362", "Wielkopolska Policja", POLICJA),
    ("EODI-2026-00952", "Ministerul Apărării al Finlandei",
     "Ministerul Apărării de la Helsinki a informat aliații NATO despre incident."),
]  # fmt: skip


def _declaracion(id_: str, autoridad: str, frase: str, medio: str = "se.pl") -> Documento:
    return {
        **ejemplos.fuente(id_, "B"),
        "enlace": ENLACE_SE,
        "medio": f"{autoridad} (declaración oficial citada en {medio})",
        "fecha": ejemplos.instante("2026-03-12T12:00Z", "aproximada"),
        "es_autoridad": True,
        "frase_origen": frase,
    }


def galczyce() -> Documento:
    """EODI-2026-00362 como se publicaba el 22/11/2026: confirmado y con la presencia confirmada,
    con la declaración atribuida al Ministerio y la cita revisada de la policía."""
    documento = inc("EODI-2026-00362", "2026-03-12T00:00Z", "dia", "Gałczyce", (52.2, 18.3), "PL")
    documento["objetivo"] = {"categoria": "otra", "nombre": "kopalnia Gałczyce"}
    documento["fuentes"][0] = {
        **ejemplos.fuente("gdelt-2b1529ba7983d3a8", "C"),
        "medio": "wnp.pl",
        "fecha": ejemplos.instante("2026-03-12T10:00Z", "aproximada"),
        "frase_origen": "pracownik kopalni ujawnił Bezzałogowy Statek Powietrzny typu Dron",
    }
    documento["fuentes"] += [
        {**ejemplos.fuente("gdelt-f1d6a873ded9547d", "C"), "enlace": ENLACE_SE, "medio": "se.pl",
         "fecha": ejemplos.instante("2026-03-12T12:00Z", "aproximada"),
         "frase_origen": 'Na terenie kopalni znaleziono drona. "Teren zabezpieczają policjanci"'},
        _declaracion("gdelt-f1d6a873ded9547d-declaracion-1", "Ministerstwo Obrony Narodowej", MON),
        _declaracion("revisada-6f06963e96b3eb5e-declaracion-1", "Wielkopolska Policja", POLICJA),
    ]  # fmt: skip
    documento["estado"] = {
        "actual": "confirmado",
        "historial": [
            {"estado": "notificado", "fecha": documento["fuentes"][0]["fecha"],
             "fuente_id": documento["fuentes"][0]["id"]},
            {"estado": "confirmado", "fecha": documento["fuentes"][2]["fecha"],
             "fuente_id": "gdelt-f1d6a873ded9547d-declaracion-1"},
        ],
    }  # fmt: skip
    documento["presencia_dron"] = "confirmada"
    return documento


@pytest.mark.parametrize(("id_", "autoridad", "motivo", "frase"), AJENAS)
def test_las_frases_que_no_son_de_quien_las_dice(
    id_: str, autoridad: str, motivo: str, frase: str
) -> None:
    assert declaraciones.no_es_quien_habla(frase, autoridad) == motivo, id_
    fuente = _declaracion(f"gdelt-x-{id_}-declaracion-1", autoridad, frase)
    assert declaraciones.atribuida_a_quien_no_habla(fuente) == motivo


@pytest.mark.parametrize(("id_", "autoridad", "frase"), SUYAS)
def test_las_frases_en_que_la_autoridad_habla(id_: str, autoridad: str, frase: str) -> None:
    assert declaraciones.no_es_quien_habla(frase, autoridad) is None, id_


def test_el_documento_propio_y_la_cita_revisada_no_se_tocan() -> None:
    # La nota de la Bundesanwaltschaft (EODI-2026-00276) y las citas revisadas a mano.
    oficial = _declaracion("oficial-de-bundesanwaltschaft-2026-09-18-wunstorf-declaracion-1",
                           "Bundesanwaltschaft",
                           "Nach dem Fund von Drohnenteilen nahe dem Bundeswehr-Fliegerhorst "
                           "Wunstorf prüft die Bundesanwaltschaft einen möglichen Zusammenhang "
                           "mit dem Drohnenvorfall am Flughafen Leipzig.")  # fmt: skip
    assert declaraciones.atribuida_a_quien_no_habla(oficial) is None
    revisada = _declaracion("revisada-abc-declaracion-1", "Ministerstwo Obrony Narodowej", MON)
    assert declaraciones.atribuida_a_quien_no_habla(revisada) is None
    # Una fuente que no es una declaración citada.
    articulo = {**ejemplos.fuente("gdelt-abc", "C"), "medio": "se.pl", "frase_origen": MON}
    assert declaraciones.atribuida_a_quien_no_habla(articulo) is None


def test_la_extraccion_no_la_guarda() -> None:
    texto = f"{POLICJA} {MON}. Teren zabezpieczają policjanci."
    ministerio = {"fuente": 1, "afirma": "incidente", "frase": MON,
                  "autoridad": "Ministerstwo Obrony Narodowej"}  # fmt: skip
    policja = {"fuente": 1, "afirma": "drones", "frase": POLICJA,
               "autoridad": "Wielkopolska Policja"}  # fmt: skip
    assert declaraciones.validas_de_noticia([ministerio, policja], [texto]) == [policja]
    # Las declaraciones revisadas a mano solo pasan por `validas`.
    assert len(declaraciones.validas([ministerio, policja], [texto])) == 2


def test_galczyce_se_quita_y_se_reconfirma_en_la_misma_pasada() -> None:
    guardado = galczyce()
    assert auditoria_fichas.declaracion_ajena(guardado)
    assert auditoria_fichas.auditar([guardado])["AE"] == ["EODI-2026-00362"]
    sin, cambios = control_fichas.sin_declaraciones_ajenas(guardado)
    assert [f["id"] for f in sin["fuentes"]] == [
        "gdelt-2b1529ba7983d3a8", "gdelt-f1d6a873ded9547d",
        "revisada-6f06963e96b3eb5e-declaracion-1",
    ]  # fmt: skip
    assert len(cambios) == 1
    assert "Ministerstwo Obrony Narodowej" in cambios[0] and MON in cambios[0]
    # Al guardar (decidir.aplicar), la cita de la policía lo vuelve a confirmar: no baja.
    nuevo = decidir.aplicar(copy.deepcopy(sin))
    assert nuevo["estado"]["actual"] == "confirmado"
    assert nuevo["estado"]["historial"][-1]["fuente_id"] == (
        "revisada-6f06963e96b3eb5e-declaracion-1"
    )
    assert nuevo["presencia_dron"] == "confirmada"
    assert not auditoria_fichas.declaracion_ajena(nuevo)
    assert not auditoria_fichas.estado_sin_frase_que_reconozca(nuevo)
    # El cerrojo deja pasar el cambio: el estado y la presencia no cambian.
    veredicto = protegido.juzgar(
        guardado, nuevo, ["recogida.control_fichas.reglas_deterministas"], lambda fuente: ""
    )
    assert veredicto.retenidos == []
    # Una segunda pasada no cambia nada.
    assert control_fichas.sin_declaraciones_ajenas(nuevo) == (nuevo, [])
