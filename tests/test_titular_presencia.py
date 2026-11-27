"""El titular dice del dron lo mismo que la presencia, con la misma lectura en la regla que lo
ajusta al guardar y en la auditoría AJ (proceso/titulares.postura), y la presencia no se
confirma con un dron que es solo una amenaza o una capacidad (proceso/declaraciones)."""

import pytest

from proceso import auditoria_fichas, declaraciones, titulares
from tests import ejemplos

# Los titulares publicados el 27 de noviembre de 2026 con la presencia confirmada y la duda lejos
# del dron, y lo que queda tras la regla. El inglés ya había perdido la duda; el español no.
CONFIRMADAS = [
    ("EODI-2025-00095", "es", "Cierre del espacio aéreo de Aalborg por sospecha de dron",
     "Cierre del espacio aéreo de Aalborg por un dron"),
    ("EODI-2025-00299", "es", "Posible caída de dron en la costa rumana durante ataque a Ucrania",
     "Caída de dron en la costa rumana durante ataque a Ucrania"),
    ("EODI-2026-00041", "es",
     "Cierre del aeropuerto de Helsinki por sospecha de actividad de drones",
     "Cierre del aeropuerto de Helsinki por actividad de drones"),
    ("EODI-2026-00903", "en", "Suspected airspace violation by drones in eastern Poland",
     "Airspace violation by drones in eastern Poland"),
    ("EODI-2026-00719", "es", "Alerta RO-Alert por posible incursión de drones en Iași, Rumanía",
     "Alerta RO-Alert por incursión de drones en Iași, Rumanía"),
]  # fmt: skip


@pytest.mark.parametrize(("id_", "idioma", "antes", "despues"), CONFIRMADAS)
def test_la_duda_lejos_del_dron_sale_con_la_presencia_confirmada(
    id_: str, idioma: str, antes: str, despues: str
) -> None:
    assert titulares.postura(antes, idioma) == titulares.DUDA, id_
    assert not titulares.coherente(antes, "confirmada", idioma)
    assert titulares.ajustar(antes, "confirmada", idioma) == despues
    assert titulares.coherente(despues, "confirmada", idioma)


def test_lo_que_no_es_duda_del_dron_se_queda() -> None:
    # La sospecha es del espionaje y lo no identificado es el dueño: el dron se afirma.
    husum = "Avistamientos de drones sobre la base aérea de Husum despiertan sospechas de espionaje"
    assert titulares.postura(husum, "es") == titulares.AFIRMA
    assert titulares.ajustar(husum, "confirmada", "es") == husum
    vilna = "Drone disrupts Vilnius airport with owner unidentified"
    assert titulares.ajustar(vilna, "confirmada", "en") == vilna
    # Un titular que no nombra el dron vale con cualquier presencia (EODI-2026-01008).
    ludza = "Letonia activa una alerta por amenaza aérea en la región de Ludza"
    assert titulares.postura(ludza, "es") == titulares.NO_LO_NOMBRA
    assert titulares.ajustar(ludza, "confirmada", "es") == ludza


def test_el_dron_no_identificado_se_afirma_y_sin_presencia_es_posible() -> None:
    # EODI-2026-00819: presencia no confirmada y «por un dron no identificado».
    es = "Avión aborta el aterrizaje en el aeropuerto de Varsovia por un dron no identificado"
    en = "Plane aborts landing at Warsaw airport over unidentified drone"
    assert titulares.postura(es, "es") == titulares.AFIRMA
    assert titulares.ajustar(es, "no_confirmada", "es") == (
        "Avión aborta el aterrizaje en el aeropuerto de Varsovia por un posible dron "
        "no identificado"
    )
    assert titulares.ajustar(en, "no_confirmada", "en") == (
        "Plane aborts landing at Warsaw airport over possible unidentified drone"
    )
    # Un objeto no identificado sigue siendo duda.
    assert titulares.postura("Un objeto no identificado sobre el puerto", "es") == titulares.DUDA


def test_con_la_presencia_descartada_el_titular_no_afirma_el_dron() -> None:
    # EODI-2025-00164: la UKAB vio que la traza era la de un F-15.
    lakenheath = (
        "Drone sightings at RAF Lakenheath and Mildenhall prompt a police helicopter search"
    )
    assert not titulares.coherente(lakenheath, "descartada", "en")
    assert titulares.ajustar(lakenheath, "descartada", "en") == (
        "Possible drone sightings at RAF Lakenheath and Mildenhall prompt a police "
        "helicopter search"
    )
    # Lo que dice que no lo era vale tal cual.
    for titulo, idioma in (
        ("False drone alarm at NATO base Geilenkirchen", "en"),
        ("Falsa alarma de dron en la base OTAN de Geilenkirchen", "es"),
        ("Cierre del aeropuerto de Sofía por un aviso de dron que la policía descarta", "es"),
    ):
        assert titulares.postura(titulo, idioma) == titulares.NIEGA
        assert titulares.ajustar(titulo, "descartada", idioma) == titulo


def test_la_auditoria_aj_ve_el_titular_que_dice_otra_cosa_que_la_presencia() -> None:
    documento = ejemplos.incidente_minimo()
    documento["presencia_dron"] = "confirmada"
    documento["titulo"] = {
        "es": "Cierre del espacio aéreo de Aalborg por sospecha de dron",
        "en": "Aalborg airspace closure due to drone",
    }
    assert auditoria_fichas.auditar([documento])["AJ"] == [documento["id"]]
    documento["titulo"]["es"] = "Cierre del espacio aéreo de Aalborg por un dron"
    assert auditoria_fichas.auditar([documento])["AJ"] == []
    documento["presencia_dron"] = "no_confirmada"
    assert auditoria_fichas.auditar([documento])["AJ"] == [documento["id"]]
    documento["titulo"] = {"es": "Alerta aérea en Ludza", "en": "Air alert in Ludza"}
    assert auditoria_fichas.auditar([documento])["AJ"] == []


@pytest.mark.parametrize(
    "frase",
    [
        # EODI-2026-01014, el ejército de Estonia el 27/11/2026: una amenaza, no un dron.
        "Estonian military officials confirmed that NATO allied fighter aircraft were also "
        "scrambled in response to the reported drone threat.",
        # EODI-2026-00862, el Gobierno búlgaro: lo que el país no puede hacer, no un dron que hubo.
        "Bulgaria nu dispune în prezent de capacitatea tehnică și militară necesară pentru a "
        "detecta eficient și a doborî dronele",
        "La policía activó el protocolo ante la amenaza de drones",
    ],
)
def test_la_amenaza_o_la_capacidad_no_atribuyen_el_dron(frase: str) -> None:
    assert not declaraciones.atribuye_dron(frase)


@pytest.mark.parametrize(
    "frase",
    [
        "Ministrul Radu Oprea a spus că în spațiul aerian național au pătruns două drone.",
        # «draudžiamoje» (lituano, «prohibida») no es una amenaza.
        "Viešojo saugumo tarnyba Vilniuje fiksavo 3 draudžiamus dronų skrydžius oro uosto "
        "apylinkėse",
        "Two Russian missiles and a Russian drone have fallen in Poland",
    ],
)
def test_el_dron_que_hubo_se_sigue_atribuyendo(frase: str) -> None:
    assert declaraciones.atribuye_dron(frase)


def test_el_control_pone_el_titular_decidido_a_la_ficha_que_nada_vuelve_a_guardar() -> None:
    from recogida import control_fichas

    documento = ejemplos.incidente_minimo()
    documento["presencia_dron"] = "no_confirmada"
    documento["titulo"] = {"es": "Dron sobre el puerto", "en": "Drone over the port"}
    nuevo, motivos = control_fichas.con_titulo_y_presencia_decididos(documento)
    assert nuevo["titulo"] == {"es": "Posible dron sobre el puerto",
                               "en": "Possible drone over the port"}  # fmt: skip
    assert motivos == ["titular según la presencia y la revisión a mano"]
    # Lo que ya está decidido no cambia: guardar otra vez no da otro titular.
    assert control_fichas.con_titulo_y_presencia_decididos(nuevo) == (nuevo, [])
