"""Criterio de presencia del dron, titulares coherentes y un incidente por noche de cierre.

El caso de referencia es EODI-2025-00092, el aeropuerto de Lieja: Skeyes cerró el tráfico tras
el aviso de un dron el sábado 8 de noviembre de 2025 y, de nuevo, el domingo 9 por la noche.
"""

from datetime import UTC, datetime
from typing import Any

import pytest

from almacen.base import Almacen
from esquema import Documento
from proceso import declaraciones, incidentes, presencia, titulares
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


def test_un_cierre_por_dron_que_cuenta_la_prensa_no_confirma_la_presencia() -> None:
    # Desde el 21 de octubre de 2026 una medida de la autoridad (cierre, cazas, patrulla,
    # detención) no es atribución: solo la confirma una autoridad que dice que fue un dron.
    documento = lieja(
        "EODI-2025-00092", "2025-11-09T19:00Z",
        frase_origen="Vliegverkeer luchthaven Luik stilgelegd na melding drone",
    )  # fmt: skip
    documento["titulo"] = {"es": "Posibles drones sobre el aeropuerto de Lieja",
                           "en": "Possible drones over Liège Airport"}  # fmt: skip
    resultado = presencia.aplicar(documento)
    assert resultado["presencia_dron"] == "no_confirmada"
    assert [a for a in resultado.get("afirmaciones", []) if a["campo"] == "presencia_dron"] == []
    assert validar_incidente(resultado, AHORA, VOCABULARIO_MODELOS) == []


def test_la_actuacion_de_la_autoridad_no_confirma_la_presencia() -> None:
    # Alta (EODI-2025-00054, «Politiet rykker til … etter melding om at det flyr en drone»),
    # Bardufoss (EODI-2025-00013, detenidos), Lanzarote (EODI-2025-00399), Luxemburgo
    # (EODI-2026-00038) y Múnich (EODI-2025-00012, vuelos desviados): lo cuenta la prensa.
    alta = lieja(
        "EODI-2025-00054", "2025-11-17T15:00Z",
        frase_origen="Politiet rykker til Amtmannsneset etter melding om at det flyr en drone",
    )  # fmt: skip
    alta["consecuencias"] = {"cierre": {"valor": "desconocido"}}
    alta["tipo"] = "sobrevuelo"
    alta["respuesta"] = {"medidas": ["patrulla"]}
    bardufoss = lieja(
        "EODI-2025-00013", "2025-09-28T12:00Z",
        frase_origen="To turister innbrakt etter mistanke om ulovlig droneflyvning.",
    )  # fmt: skip
    lanzarote = lieja("EODI-2025-00399", "2025-08-13T19:30Z",
                      frase_origen="causó la paralización de todas las operaciones")  # fmt: skip
    luxemburgo = lieja(
        "EODI-2026-00038", "2026-09-23T19:00Z",
        frase_origen="Zweimal wurde der Flughafen Luxemburg wegen Drohnen gesperrt",
    )  # fmt: skip
    munich = lieja(
        "EODI-2025-00012", "2025-05-02T12:00Z",
        frase_origen="Eine Drohne wurde im Umfeld des Flughafens gesichtet.",
    )  # fmt: skip
    munich["consecuencias"] = {"cierre": {"valor": "desconocido"},
                               "vuelos_desviados": {"min": 3, "max": 3}}  # fmt: skip
    for documento in (alta, bardufoss, lanzarote, luxemburgo, munich):
        # Antes la actuación la confirmaba (por_actuacion la sigue encontrando).
        assert presencia.por_actuacion(documento) is not None, documento["id"]
        assert presencia.aplicar(documento)["presencia_dron"] == "no_confirmada", documento["id"]


def _confirmada(documento: Documento, fuente: str) -> Documento:
    """La presencia confirmada por esa fuente, como la dejaron el extractor o una regla anterior."""
    documento["presencia_dron"] = "confirmada"
    documento["afirmaciones"] = [*documento.get("afirmaciones", []),
                                 declaraciones.afirmacion_presencia(fuente)]  # fmt: skip
    return documento


def _autoridad(documento: Documento, medio: str, frase: str) -> str:
    """Una declaración oficial citada en la noticia de la ficha."""
    noticia = documento["fuentes"][0]
    citada = {**noticia, "id": f"{noticia['id']}-declaracion-1", "es_autoridad": True,
              "medio": f"{medio} (declaración oficial citada en {noticia['medio']})",
              "frase_origen": frase}  # fmt: skip
    documento["fuentes"] = [*documento["fuentes"], citada]
    return str(citada["id"])


BRUSELAS = "Luchtverkeer op Brussels Airport kort stilgelegd na dronemelding."


def test_confirmada_sin_autoridad_que_lo_atribuya_queda_sin_confirmar() -> None:
    # c) Solo la prensa: EODI-2025-00199, Bruselas (la confirmó la regla de presencia del PR 77
    # por el cierre que contaba la noticia).
    bruselas = lieja("EODI-2025-00199", "2025-11-04T19:00Z", frase_origen=BRUSELAS)
    bruselas = _confirmada(bruselas, bruselas["fuentes"][0]["id"])
    assert presencia.sin_base(bruselas)
    quitada = presencia.quitar_sin_base(bruselas)
    assert quitada["presencia_dron"] == "no_confirmada"
    assert [a for a in quitada["afirmaciones"] if a["campo"] == "presencia_dron"] == []
    assert validar_incidente(quitada, AHORA, VOCABULARIO_MODELOS) == []
    # b) Hay autoridad, pero solo actúa: EODI-2025-00049, Bucarest (la confirmó el extractor con
    # la declaración «incidente» de la CNAB sobre la suspensión de los aterrizajes).
    bucarest = lieja("EODI-2025-00049", "2025-10-01T18:00Z",
                     frase_origen="Dronă semnalată în apropierea aeroportului Otopeni")  # fmt: skip
    citada = _autoridad(bucarest, "Compania Națională Aeroporturi Bucureşti",
                        "au fost suspendate temporar aterizările, iar aeronavele aflate în zonă "
                        "au fost dirijate către puncte de aşteptare")  # fmt: skip
    bucarest = _confirmada(bucarest, citada)
    assert presencia.quitar_sin_base(bucarest)["presencia_dron"] == "no_confirmada"
    # La autoridad que dice que fue un dron la sostiene.
    _autoridad(bruselas, "Skeyes", "Een drone werd waargenomen boven de luchthaven")
    assert presencia.quitar_sin_base(bruselas) is bruselas


def test_la_regla_no_decide_las_dudosas() -> None:
    # e) La Bundeswehr afirma los drones según el extractor, pero su cita no los nombra
    # (EODI-2025-00340, Múnich).
    munich = lieja("EODI-2025-00340", "2025-10-02T20:18Z",
                   frase_origen="Drohnensichtungen am Flughafen München")  # fmt: skip
    citada = _autoridad(
        munich, "Bundeswehr", "Das bestätigte eine Sprecherin des operativen Führungskommandos"
    )
    munich = _confirmada(munich, citada)
    assert presencia.sin_base(munich)
    assert presencia.dudosa_por(munich, {citada: {"afirma": "drones"}})
    assert not presencia.dudosa_por(munich, {citada: {"afirma": "incidente"}})
    singerei = lieja(
        "EODI-2025-00312",
        "2025-11-20T08:00Z",
        frase_origen="Dronă militară de tip Gerbera a fost găsită pe un câmp.",
    )
    singerei["pruebas"] = {"dron_estatal": True, "entrada_exterior": True,
                           "evidencia": ["restos"]}  # fmt: skip
    assert not presencia.dudosa_por(singerei, {})


def test_los_restos_que_solo_cuenta_la_prensa_no_confirman() -> None:
    # EODI-2025-00312, Sîngerei: el Gerbera hallado en un campo solo lo cuenta la prensa.
    almacen = Almacen.abrir()
    gerbera = "Dronă militară de tip Gerbera a fost găsită pe un câmp."
    singerei = lieja("EODI-2025-00312", "2025-11-20T08:00Z", frase_origen=gerbera)
    singerei["pruebas"] = {"dron_estatal": True, "entrada_exterior": True,
                           "evidencia": ["restos"]}  # fmt: skip
    singerei = _confirmada(singerei, singerei["fuentes"][0]["id"])
    assert presencia.sin_base(singerei)
    assert presencia.motivo_sin_base(singerei) == presencia.MOTIVO_PRUEBAS_PRENSA
    almacen.guardar_incidente(singerei, AHORA, VOCABULARIO_MODELOS)
    presencia.revisar(almacen, AHORA, VOCABULARIO_MODELOS)
    guardado = almacen.incidente("EODI-2025-00312")
    assert guardado is not None and guardado["presencia_dron"] == "no_confirmada"
    motivos = [h["nuevo"].get("motivo") for h in almacen.historial("EODI-2025-00312")]
    assert presencia.MOTIVO_PRUEBAS_PRENSA in motivos


def test_la_revision_quita_la_presencia_sin_base_con_su_motivo() -> None:
    almacen = Almacen.abrir()
    bruselas = lieja("EODI-2025-00199", "2025-11-04T19:00Z", frase_origen=BRUSELAS)
    almacen.guardar_incidente(_confirmada(bruselas, bruselas["fuentes"][0]["id"]), AHORA,
                              VOCABULARIO_MODELOS)  # fmt: skip
    assert presencia.revisar(almacen, AHORA, VOCABULARIO_MODELOS) == ([], [])
    guardado = almacen.incidente("EODI-2025-00199")
    assert guardado is not None and guardado["presencia_dron"] == "no_confirmada"
    motivos = [h["nuevo"].get("motivo") for h in almacen.historial("EODI-2025-00199")]
    assert presencia.MOTIVO_SIN_BASE in motivos
    # La pasada siguiente no vuelve a confirmarla.
    presencia.revisar(almacen, AHORA, VOCABULARIO_MODELOS)
    guardado = almacen.incidente("EODI-2025-00199")
    assert guardado is not None and guardado["presencia_dron"] == "no_confirmada"


def test_un_cierre_por_otra_causa_no_confirma_el_dron() -> None:
    # Vilna, globos: «Μετά τα drones τα... αερόστατα: Κλειστό το αεροδρόμιο του Βίλνιους».
    documento = lieja(
        "EODI-2025-00112", "2025-10-21T19:00Z",
        frase_origen="Μετά τα drones τα... αερόστατα: Κλειστό το αεροδρόμιο του Βίλνιους",
    )  # fmt: skip
    assert presencia.aplicar(documento)["presencia_dron"] == "no_confirmada"
    documento["fuentes"][0]["frase_origen"] = (
        "potenziell größerer Drohnen im Luftraum von Luxemburg gesichtet worden"
    )
    assert presencia.aplicar(documento)["presencia_dron"] == "no_confirmada"


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

    documento = lieja("EODI-2025-00092", "2025-11-09T19:00Z")
    citada = _autoridad(documento, "Skeyes", "Het luchtruim werd gesloten door een drone")
    resultado = presencia.aplicar(_confirmada(documento, citada))
    [publica] = [a for a in afirmaciones_publicas(resultado) if a["campo"] == "presencia_dron"
                 and a["valor"] == "confirmada"]  # fmt: skip
    assert publica["cita"] == "Het luchtruim werd gesloten door een drone"
    otras = [a for a in afirmaciones_publicas(resultado) if a["campo"] != "presencia_dron"]
    assert all("cita" not in a for a in otras)


@pytest.mark.parametrize(
    ("titulo", "presencia", "esperado"),
    [
        # EODI-2026-00698 y EODI-2026-00322 (28 de octubre de 2026): traducidos de «o dronă» y
        # «eine Drohne».
        ("Una dron entra en el espacio aéreo de Rumanía cerca de Sulina y despegan cazas",
         "confirmada",
         "Un dron entra en el espacio aéreo de Rumanía cerca de Sulina y despegan cazas"),
        ("Una posible dron interrumpe brevemente las operaciones del aeropuerto de Hamburgo",
         "no_confirmada",
         "Un posible dron interrumpe brevemente las operaciones del aeropuerto de Hamburgo"),
        ("Alerta por la dron rusa estrellada", "confirmada", "Alerta por el dron ruso estrellada"),
        ("Hallazgo de la dron cerca de la base", "confirmada",
         "Hallazgo del dron cerca de la base"),
        ("Las drones misteriosas sobre Kleine-Brogel", "confirmada",
         "Los drones misteriosos sobre Kleine-Brogel"),
        # Lo que no acompaña al dron no cambia.
        ("Una posible incursión de dron en la base aérea", "confirmada",
         "Una posible incursión de dron en la base aérea"),
        ("Drones sobre la planta de la Armada", "confirmada",
         "Drones sobre la planta de la Armada"),
    ],
)  # fmt: skip
def test_el_dron_es_masculino(titulo: str, presencia: str, esperado: str) -> None:
    assert titulares.ajustar(titulo, presencia, "es") == esperado
    assert titulares.concuerda(esperado, "es")
    assert titulares.ajustar("A drone over the base", "confirmada", "en") == "A drone over the base"
