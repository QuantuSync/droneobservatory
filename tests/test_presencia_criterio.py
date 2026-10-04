"""Criterio de presencia del dron, titulares coherentes y un incidente por noche de cierre.

El caso de referencia es EODI-2025-00092, el aeropuerto de Lieja: Skeyes cerró el tráfico tras
el aviso de un dron el sábado 8 de noviembre de 2025 y, de nuevo, el domingo 9 por la noche.
"""

from datetime import UTC, datetime
from typing import Any

from almacen.base import Almacen
from esquema import Documento
from proceso import incidentes, presencia, titulares
from proceso.noticias import Articulo, Candidato, filtro, nomenclator, repeticion
from proceso.validaciones import errores_presencia, validar_incidente
from recogida import criterio_presencia
from tests import ejemplos
from tests.ejemplos import VOCABULARIO_MODELOS
from tests.test_calidad_datos_3 import inc

AHORA = datetime(2026, 10, 3, 20, tzinfo=UTC)
LIEJA = ("Aéroport de Liège-Bierset", (50.637, 5.443), "BE")


def lieja(id_: str, inicio: str, precision: str = "hora", **fuente: Any) -> Documento:
    documento = inc(id_, inicio, precision, *LIEJA)
    documento["consecuencias"] = {"cierre": {"valor": "si"}}
    documento["tipo"] = "interrupcion_aeroportuaria"
    documento["presencia_dron"] = "no_confirmada"
    documento["fuentes"][0].update(fuente)
    return documento


# --- Titulares ------------------------------------------------------------------------


def test_titulares_que_no_dicen_lo_mismo_que_la_presencia() -> None:
    # Afirman el dron con la presencia sin confirmar, o lo dan por posible con ella confirmada.
    assert not titulares.coherente(
        "Drones sobre el aeropuerto de Lieja interrumpen el tráfico aéreo", "no_confirmada", "es"
    )
    assert not titulares.coherente("Posibles drones cierran el aeropuerto", "confirmada", "es")
    assert not titulares.coherente("Objeto no identificado obliga a cerrar X", "confirmada", "es")
    assert not titulares.coherente("Possible drone over the base", "confirmada", "en")
    assert titulares.coherente("Cierre del aeropuerto de Lieja", "no_confirmada", "es")
    assert titulares.coherente("Drones over Liège Airport", "confirmada", "en")
    assert titulares.coherente("Posible dron sobre la base", "no_confirmada", "es")


def test_el_titular_se_ajusta_a_la_presencia() -> None:
    casos = [
        ("Drones sobre el aeropuerto de Lieja interrumpen el tráfico aéreo", "no_confirmada",
         "Posibles drones sobre el aeropuerto de Lieja interrumpen el tráfico aéreo"),
        ("Un dron obliga a cerrar el aeropuerto de Palma", "no_confirmada",
         "Un posible dron obliga a cerrar el aeropuerto de Palma"),
        ("Cierre del aeropuerto por avistamientos de drones", "no_confirmada",
         "Cierre del aeropuerto por avistamientos de posibles drones"),
        ("Posibles drones sobre la base aérea de Volkel", "confirmada",
         "Drones sobre la base aérea de Volkel"),
        ("Objeto no identificado obliga a cerrar el aeropuerto", "confirmada",
         "Dron obliga a cerrar el aeropuerto"),
    ]  # fmt: skip
    for titulo, valor, esperado in casos:
        assert titulares.ajustar(titulo, valor, "es") == esperado
        assert titulares.coherente(esperado, valor, "es")
    assert titulares.ajustar("Drones over Liège Airport", "no_confirmada", "en") == (
        "Possible drones over Liège Airport"
    )
    assert titulares.ajustar("Possible drones close the airport", "confirmada", "en") == (
        "Drones close the airport"
    )
    # Si el titular ya duda del dron con otra palabra, no se añade «posible»; si se añadió, sobra.
    for titulo, limpio in (
        ("Objeto sospechoso en Agigea, posiblemente un posible dron",
         "Objeto sospechoso en Agigea, posiblemente un dron"),
        ("Cierre del espacio aéreo de Aalborg por sospecha de posible dron",
         "Cierre del espacio aéreo de Aalborg por sospecha de dron"),
    ):  # fmt: skip
        assert not titulares.coherente(titulo, "no_confirmada", "es")
        assert titulares.ajustar(titulo, "no_confirmada", "es") == limpio
        assert titulares.coherente(limpio, "no_confirmada", "es")
    assert titulares.ajustar("Unidentified possible drones near Dublin Airport", "no_confirmada",
                             "en") == "Unidentified drones near Dublin Airport"  # fmt: skip
    # Descartada: el titular no se toca.
    assert titulares.ajustar("Drones sobre X", "descartada", "es") == "Drones sobre X"


# --- Criterio de presencia ----------------------------------------------------------------


def test_un_cierre_por_dron_confirma_la_presencia_con_la_frase_de_la_fuente() -> None:
    documento = lieja(
        "EODI-2025-00092", "2025-11-09T19:00Z",
        frase_origen="Vliegverkeer luchthaven Luik stilgelegd na melding drone",
    )  # fmt: skip
    documento["titulo"] = {"es": "Posibles drones sobre el aeropuerto de Lieja",
                           "en": "Possible drones over Liège Airport"}  # fmt: skip
    resultado = presencia.aplicar(documento)
    assert resultado["presencia_dron"] == "confirmada"
    [afirmacion] = [a for a in resultado["afirmaciones"] if a["campo"] == "presencia_dron"]
    assert afirmacion["fuente_id"] == documento["fuentes"][0]["id"]
    assert resultado["titulo"]["es"] == "Drones sobre el aeropuerto de Lieja"
    assert validar_incidente(resultado, AHORA, VOCABULARIO_MODELOS) == []


def test_una_intervencion_policial_por_dron_confirma_la_presencia() -> None:
    # Caso de Alta: «Politiet rykker til … etter melding om at det flyr en drone».
    documento = lieja(
        "EODI-2025-00054", "2025-11-17T15:00Z",
        frase_origen="Politiet rykker til Amtmannsneset etter melding om at det flyr en drone",
    )  # fmt: skip
    documento["consecuencias"] = {"cierre": {"valor": "desconocido"}}
    documento["tipo"] = "sobrevuelo"
    documento["respuesta"] = {"medidas": ["patrulla"]}
    assert presencia.aplicar(documento)["presencia_dron"] == "confirmada"
    # Sin medida registrada también: la frase dice que la policía acude por el dron.
    documento["respuesta"] = {"medidas": ["ninguna_conocida"]}
    assert presencia.aplicar(documento)["presencia_dron"] == "confirmada"
    documento["fuentes"][0]["frase_origen"] = "Vecinos vieron un dron sobre el aeropuerto"
    assert presencia.aplicar(documento)["presencia_dron"] == "no_confirmada"


def test_una_detencion_por_volar_un_dron_confirma_la_presencia() -> None:
    # Caso de Bardufoss: «Dos turistas detenidos por volar un dron cerca del aeropuerto».
    documento = lieja(
        "EODI-2025-00013", "2025-09-28T12:00Z",
        frase_origen="To turister innbrakt etter mistanke om ulovlig droneflyvning.",
    )  # fmt: skip
    documento["consecuencias"] = {"cierre": {"valor": "desconocido"}}
    documento["tipo"] = "sobrevuelo"
    assert presencia.aplicar(documento)["presencia_dron"] == "confirmada"


def test_si_la_fuente_lo_deja_abierto_el_cierre_no_confirma() -> None:
    documento = lieja(
        "EODI-2025-00092", "2025-11-09T19:00Z",
        frase_origen="Aéroport fermé après le signalement d'un objet non identifié",
    )  # fmt: skip
    assert presencia.aplicar(documento)["presencia_dron"] == "no_confirmada"
    sin_cierre = lieja("EODI-2025-00093", "2025-11-09T19:00Z",
                       frase_origen="Drones gezien boven de luchthaven")  # fmt: skip
    sin_cierre["consecuencias"] = {"cierre": {"valor": "desconocido"}}
    assert presencia.aplicar(sin_cierre)["presencia_dron"] == "no_confirmada"


def test_la_validacion_falla_si_la_fuente_oficial_atribuye_el_dron_y_no_esta_confirmado() -> None:
    documento = ejemplos.incidente_completo()
    documento["presencia_dron"] = "no_confirmada"
    [error] = errores_presencia(documento)
    assert error.ruta == "presencia_dron"
    # Si la autoridad lo deja abierto, no confirmado es lo correcto.
    for fuente in documento["fuentes"]:
        fuente["frase_origen"] = "Possibly a drone was seen near the runway"
    assert errores_presencia(documento) == []


# --- Un incidente por noche de cierre -------------------------------------------------


def test_dos_cierres_del_mismo_sitio_en_noches_distintas_no_se_funden() -> None:
    sabado = lieja("EODI-2025-00092", "2025-11-08T19:00Z")
    domingo = lieja("EODI-2025-00400", "2025-11-09T19:00Z")
    assert incidentes.cierres_de_noches_distintas(sabado, domingo)
    assert not incidentes.encajan(sabado, domingo)
    # La misma noche (la madrugada es de la noche anterior), sí.
    madrugada = lieja("EODI-2025-00401", "2025-11-09T00:30Z")
    assert incidentes.encajan(sabado, madrugada)
    # Con el día escrito, también noches distintas.
    assert not incidentes.encajan(lieja("EODI-2025-00402", "2025-11-08T00:00Z", "dia"), domingo)


def test_un_cierre_que_se_repite_no_se_funde_en_el_de_la_noche_anterior() -> None:
    # Lieja: el cierre del sábado (con hora) y el del domingo, con la fecha de publicación y una
    # fuente que dice «opnieuw stilgelegd».
    sabado = lieja("EODI-2025-00092", "2025-11-08T19:00Z")
    domingo = lieja(
        "EODI-2025-00408",
        "2025-11-09T19:30Z",
        "aproximada",
        frase_origen="Vliegverkeer luchthaven Luik opnieuw stilgelegd na melding drone",
    )
    domingo["fuentes"][0]["fecha"] = ejemplos.instante("2025-11-09T19:30Z", "aproximada")
    assert incidentes.repite_un_cierre_anterior(sabado, domingo)
    assert not incidentes.encajan(sabado, domingo)
    # Sin palabra de repetición, la fecha de publicación casa con la víspera (como antes).
    domingo["fuentes"][0]["frase_origen"] = "Vliegverkeer luchthaven Luik stilgelegd na melding"
    assert incidentes.encajan(sabado, domingo)


def test_la_revision_deshace_la_fusion_de_dos_cierres_de_noches_distintas() -> None:
    almacen = Almacen.abrir()
    sabado = lieja("EODI-2025-00092", "2025-11-08T19:00Z")
    domingo = lieja(
        "EODI-2025-00408",
        "2025-11-09T19:30Z",
        "aproximada",
        frase_origen="Vliegverkeer luchthaven Luik opnieuw stilgelegd na melding drone",
    )
    domingo["fuentes"][0]["fecha"] = ejemplos.instante("2025-11-09T19:30Z", "aproximada")
    for documento in (sabado, domingo):
        almacen.guardar_incidente(documento, AHORA, VOCABULARIO_MODELOS)
    # Una fusión hecha con las reglas anteriores.
    nuevo, aportadas = incidentes.absorber(sabado, domingo, AHORA)
    almacen.guardar_incidente(nuevo, AHORA, VOCABULARIO_MODELOS)
    almacen.guardar_incidente({**domingo, "fusionado_en": sabado["id"]}, AHORA, VOCABULARIO_MODELOS)
    almacen.registrar_fusion("2025-11-10T00:00Z", domingo["id"], sabado["id"], "prueba", aportadas)
    assert incidentes.revisar_fusiones(almacen, AHORA, VOCABULARIO_MODELOS) == ["EODI-2025-00408"]
    vuelto = almacen.incidente("EODI-2025-00408")
    assert vuelto is not None and "fusionado_en" not in vuelto
    assert incidentes.revisar_fusiones(almacen, AHORA, VOCABULARIO_MODELOS) == []


def test_la_repeticion_se_mide_desde_el_suceso() -> None:
    sitio = nomenclator().lugares["EBLG"]
    # Primera noticia el domingo a las 09:00 sobre el cierre del sábado a las 19:00.
    candidato = Candidato(
        "CAND-20251109T0900-EBLG-aeropuerto", "aeropuerto", sitio,
        datetime(2025, 11, 9, 9, tzinfo=UTC), datetime(2025, 11, 9, 10, 30, tzinfo=UTC), "dia",
        ["https://a.be/1"],
    )  # fmt: skip
    opnieuw = Articulo(
        "https://b.be/2", "b.be", datetime(2025, 11, 9, 19, 30, tzinfo=UTC),
        "Vliegverkeer luchthaven Luik opnieuw stilgelegd na melding drone", "nl",
    )  # fmt: skip
    # Desde la primera noticia van 10 h 30 min: no abre otro.
    assert not repeticion(candidato, opnieuw, filtro())
    # Desde el suceso (sábado a las 19:00), 24 h 30 min: es otro cierre.
    candidato.suceso = datetime(2025, 11, 8, 19, tzinfo=UTC)
    assert repeticion(candidato, opnieuw, filtro())
    tercer = Articulo(
        "https://c.be/3", "c.be", datetime(2025, 11, 9, 22, 30, tzinfo=UTC),
        "Survols de drones : l'aéroport de Liège perturbé pour le troisième jour consécutif",
        "fr",
    )  # fmt: skip
    assert repeticion(candidato, tercer, filtro())


def test_la_correccion_se_aplica_una_vez() -> None:
    almacen = Almacen.abrir()
    documento = lieja(
        "EODI-2025-00092", "2025-11-08T19:00Z",
        frase_origen="Vliegverkeer luchthaven Luik stilgelegd na melding drone",
    )  # fmt: skip
    almacen.guardar_incidente(documento, AHORA, VOCABULARIO_MODELOS)
    resumen = criterio_presencia.aplicar(almacen, AHORA, VOCABULARIO_MODELOS)
    assert resumen["version"] == criterio_presencia.VERSION
    assert criterio_presencia.aplicar(almacen, AHORA, VOCABULARIO_MODELOS) == {}


def test_la_presencia_publicada_lleva_la_cita_de_la_fuente_que_la_justifica() -> None:
    from exportacion.afirmaciones import afirmaciones_publicas

    documento = lieja(
        "EODI-2025-00092", "2025-11-09T19:00Z",
        frase_origen="Vliegverkeer luchthaven Luik stilgelegd na melding drone",
    )  # fmt: skip
    resultado = presencia.aplicar(documento)
    [publica] = [a for a in afirmaciones_publicas(resultado) if a["campo"] == "presencia_dron"
                 and a["valor"] == "confirmada"]  # fmt: skip
    assert publica["cita"] == "Vliegverkeer luchthaven Luik stilgelegd na melding drone"
    otras = [a for a in afirmaciones_publicas(resultado) if a["campo"] != "presencia_dron"]
    assert all("cita" not in a for a in otras)
