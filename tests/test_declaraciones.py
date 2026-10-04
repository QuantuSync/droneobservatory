"""Declaraciones oficiales citadas por la prensa: una prueba por regla.

Las frases siguen las de los casos de 2025 (Copenhague, Múnich, Polonia, Gardermoen).
"""

import json
from datetime import timedelta
from typing import Any

from almacen.base import Almacen
from esquema import Documento
from modelo import coste, ficha
from proceso import declaraciones, extraccion, presencia
from proceso.validaciones import validar_incidente
from tests.test_extraccion import AHORA, MODELOS, a_servicio, extraer_ejemplo, ficha_ejemplo

TEXTO = (
    "Københavns Politi: Vi kan bekræfte, at der i aften er observeret droner over lufthavnen, "
    "og at lufthavnen er lukket. Politiet har modtaget flere anmeldelser om droner i Kastrup."
)


def declaracion(
    afirma: str, frase: str, categoria: str = "policia", **resto: Any
) -> dict[str, Any]:
    return {"autoridad": "Københavns Politi", "categoria": categoria, "afirma": afirma,
            "autor": "", "fuente": 1, "frase": frase, **resto}  # fmt: skip


def incidente() -> tuple[Documento, list[str]]:
    """El incidente tal como lo da la ficha, antes de las reglas de presencia (el cierre del
    ejemplo ya la confirmaría): así cada prueba mira solo lo que hacen las declaraciones."""
    almacen = Almacen.abrir()
    id_ = extraer_ejemplo(almacen)
    resultado = almacen.incidente(str(id_))
    assert resultado is not None
    resultado["presencia_dron"] = "no_confirmada"
    resultado["afirmaciones"] = [
        a for a in resultado["afirmaciones"]
        if a != declaraciones.afirmacion_presencia(a["fuente_id"])
    ]  # fmt: skip
    return resultado, [resultado["fuentes"][0]["enlace"]]


def aplicar(*lista: dict[str, Any]) -> Documento:
    base, enviadas = incidente()
    resultado = declaraciones.aplicar(base, list(lista), enviadas)
    assert validar_incidente(resultado, AHORA, MODELOS) == []
    return resultado


def test_la_autoridad_que_afirma_el_cierre_confirma() -> None:
    # El gestor aeroportuario cierra por el dron: la autoridad lo da por hecho.
    resultado = aplicar(declaracion(
        "incidente", "Der Flugbetrieb wurde am Donnerstagabend eingestellt", "aeropuerto",
        autoridad="Flughafen München",
    ))  # fmt: skip
    assert resultado["estado"]["actual"] == "confirmado"
    assert resultado["presencia_dron"] == "confirmada"
    citada = resultado["fuentes"][-1]
    assert (citada["fiabilidad"], citada["es_autoridad"]) == ("B", True)
    assert "declaración oficial citada" in citada["medio"]
    assert citada["enlace"] == resultado["fuentes"][0]["enlace"]


def test_drones_afirmados_por_las_fuerzas_armadas_confirman_la_presencia() -> None:
    resultado = aplicar(declaracion(
        "drones", "Siły Zbrojne RP zestrzeliły drony, które naruszyły polską przestrzeń powietrzną",
        "fuerzas_armadas", autoridad="Dowództwo Operacyjne RSZ",
    ))  # fmt: skip
    assert resultado["estado"]["actual"] == "confirmado"
    assert resultado["presencia_dron"] == "confirmada"


def test_el_aviso_de_dron_que_comunica_la_autoridad_confirma() -> None:
    for frase in (
        "Politiet har modtaget flere anmeldelser om droner i Kastrup",
        "Buvo gauta informacija, kad pastebėtas dronas",
    ):
        resultado = aplicar(declaracion("drones", frase))
        assert resultado["estado"]["actual"] == "confirmado", frase
        assert resultado["presencia_dron"] == "confirmada", frase
        assert any(f["id"].endswith("-declaracion-1") for f in resultado["fuentes"])


def test_sin_drones_descarta_la_presencia() -> None:
    resultado = aplicar(declaracion("sin_drones", "Ingen droner ved Gardermoen likevel"))
    assert resultado["presencia_dron"] == "descartada"


def test_negar_el_incidente_lo_desmiente() -> None:
    resultado = aplicar(declaracion(
        "niega_incidente", "Der har ikke været nogen droner eller lukning af lufthavnen"
    ))  # fmt: skip
    assert resultado["estado"]["actual"] == "desmentido"


def test_solo_un_gobierno_atribuye() -> None:
    confirma = declaracion("drones", "Vi kan bekræfte, at der i aften er observeret droner")
    policia = declaracion("autoria", "Det er en kapabel aktør", autor="Rusia")
    assert aplicar(confirma, policia)["estado"]["actual"] == "confirmado"
    gobierno = declaracion(
        "autoria", "To była prowokacja rosyjskich dronów", "gobierno",
        autoridad="Premier RP", autor="Rusia", cita_literal=True,
    )  # fmt: skip
    resultado = aplicar(confirma, gobierno)
    assert resultado["estado"]["actual"] == "atribuido"
    assert resultado["atribucion"]["actor"] == "Rusia"


def test_la_frase_tiene_que_estar_en_la_noticia() -> None:
    buena = declaracion("incidente", "vi kan bekræfte, at der i aften er observeret droner")
    inventada = declaracion("drones", "Politiet har fundet dronen")
    assert declaraciones.validas([buena, inventada], [TEXTO]) == [buena]


def test_la_ficha_trae_las_declaraciones_y_las_antiguas_se_leen_sin_ellas() -> None:
    salida = a_servicio(ficha_ejemplo())
    antigua = {"stop_reason": "end_turn",
               "content": [{"type": "text", "text": json.dumps(salida)}]}  # fmt: skip
    assert ficha.leer_respuesta(antigua)["declaraciones"] == []
    salida["declaraciones"] = [
        declaracion("incidente", "lufthavnen er lukket"),
        declaracion("incidente", "x", categoria="periodico"),
    ]
    nueva = {"stop_reason": "end_turn",
             "content": [{"type": "text", "text": json.dumps(salida)}]}  # fmt: skip
    assert [d["frase"] for d in ficha.leer_respuesta(nueva)["declaraciones"]] == [
        "lufthavnen er lukket"
    ]


# --- Presencia del dron: una autoridad que dice expresamente que hubo drones ----------------


def afirmaciones_de_presencia(incidente: Documento) -> list[Documento]:
    """Las que confirman la presencia (la ficha deja además la suya, de la noticia)."""
    return [
        a
        for a in incidente.get("afirmaciones", [])
        if a["campo"] == "presencia_dron" and a["valor"] == "confirmada"
    ]


def test_la_atribucion_oficial_que_habla_de_drones_confirma_la_presencia() -> None:
    # Caso de Chișinău: confirmado por un ministerio y atribuido por el gobierno.
    confirma = declaracion(
        "incidente", "Lufthavnen er lukket", "ministerio", autoridad="Ministerul de Interne"
    )
    atribuye = declaracion(
        "autoria", "Rusia es responsable de los drones que sobrevolaron el aeropuerto",
        "gobierno", autoridad="Guvernul Republicii Moldova", autor="Rusia", cita_literal=True,
    )  # fmt: skip
    resultado = aplicar(confirma, atribuye)
    assert resultado["estado"]["actual"] == "atribuido"
    assert resultado["presencia_dron"] == "confirmada"
    # La primera autoridad que lo da por hecho es la fuente de la presencia.
    [afirmacion] = afirmaciones_de_presencia(resultado)
    assert afirmacion["valor"] == "confirmada"
    assert afirmacion["fuente_id"].endswith("-declaracion-1")


def test_la_confirmacion_del_cierre_confirma_la_presencia_aunque_no_nombre_drones() -> None:
    # Caso de Lieja: «Das teilte die Flugsicherung Skeyes mit», sobre el cierre por un dron.
    for frase, autoridad in (
        ("El espacio aéreo se cerró durante una hora", "ENAIRE"),
        ("Das teilte die Flugsicherung Skeyes mit.", "Skeyes"),
    ):
        resultado = aplicar(declaracion("incidente", frase, "navegacion_aerea",
                                        autoridad=autoridad))  # fmt: skip
        assert resultado["estado"]["actual"] == "confirmado"
        assert resultado["presencia_dron"] == "confirmada"
        [afirmacion] = afirmaciones_de_presencia(resultado)
        assert afirmacion["fuente_id"].endswith("-declaracion-1")


def test_la_autoridad_que_cuenta_los_drones_al_confirmar_confirma_la_presencia() -> None:
    resultado = aplicar(declaracion(
        "incidente", "Lufthavnen er lukket på grund af to til tre droner", "policia"
    ))  # fmt: skip
    assert resultado["presencia_dron"] == "confirmada"


def test_el_aeropuerto_que_cierra_por_drones_confirma_la_presencia() -> None:
    resultado = aplicar(declaracion(
        "incidente", "Der Flugbetrieb wurde wegen Drohnen eingestellt", "aeropuerto",
        autoridad="Flughafen München",
    ))  # fmt: skip
    assert resultado["estado"]["actual"] == "confirmado"
    assert resultado["presencia_dron"] == "confirmada"


def test_la_autoridad_que_lo_deja_abierto_no_confirma_la_presencia() -> None:
    for frase in (
        "Vi har en begrundet mistanke om droneaktivitet ved lufthavnen",
        "Vi har ikke fået hverken be- eller afkræftet, om det var droner",
        "Policja potwierdziła, że pilot zgłosił obiekt przypominający drona",
        "Es handelte sich um ein nicht identifiziertes Flugobjekt",
        "Se investiga si se trataba de un dron",
        "Possibly a drone was seen near the runway",
    ):
        resultado = aplicar(declaracion("incidente", frase, "policia"))
        assert resultado["estado"]["actual"] == "confirmado", frase
        assert resultado["presencia_dron"] == "no_confirmada", frase
        assert afirmaciones_de_presencia(resultado) == [], frase


def test_la_noticia_que_cita_a_la_autoridad_tambien_puede_dejarlo_abierto() -> None:
    confirma = declaracion("incidente", "Der Flugbetrieb wurde eingestellt", "aeropuerto")
    assert declaraciones.confirma_dron(confirma)
    assert not declaraciones.confirma_dron(confirma, "Objet non identifié au-dessus de l'aéroport")


def test_el_desmentido_pesa_mas_que_la_frase_que_cuenta_los_drones() -> None:
    cuenta_drones = declaracion("incidente", "Fem droner fløj over basen", "policia")
    niega = declaracion(
        "niega_incidente", "Der har ikke været nogen droner", "fuerzas_armadas",
        autoridad="Forsvaret",
    )  # fmt: skip
    resultado = aplicar(cuenta_drones, niega)
    assert resultado["estado"]["actual"] == "desmentido"
    assert resultado["presencia_dron"] == "no_confirmada"
    descarta = declaracion("sin_drones", "Det var ingen droner", "fuerzas_armadas")
    assert aplicar(cuenta_drones, descarta)["presencia_dron"] == "descartada"


TEXTO_DECLARACION = "Københavns Politi: der blev observeret tre til fire store droner."


def extraer_con_declaracion(almacen: Almacen) -> str:
    """Un incidente extraído con una declaración de la policía que nombra los drones."""
    from tests import test_extraccion as te

    candidato = te.candidato_con_articulos(almacen)
    peticion = extraccion.preparar(almacen, candidato, None)
    peticion = extraccion.Peticion(
        **{**peticion.__dict__, "fuentes": [
            ficha.FuenteTexto(f.medio, f.fecha, f.idioma, f.titular,
                              f"{te.TEXTO} {TEXTO_DECLARACION}")
            for f in peticion.fuentes
        ]}
    )  # fmt: skip
    salida = a_servicio(ficha_ejemplo())
    salida["declaraciones"] = [declaracion(
        "incidente", "der blev observeret tre til fire store droner", pais="DK"
    )]  # fmt: skip
    respuesta = {**te.respuesta(ficha_ejemplo()),
                 "content": [{"type": "text", "text": json.dumps(salida)}]}  # fmt: skip
    id_ = extraccion.procesar_respuesta(
        almacen, peticion, respuesta, AHORA, coste.Modo.HISTORICO, True, MODELOS
    )
    assert id_ is not None
    return id_


def test_la_revision_confirma_la_presencia_de_lo_ya_guardado_con_su_fuente() -> None:
    almacen = Almacen.abrir()
    id_ = extraer_con_declaracion(almacen)
    nuevo = almacen.incidente(id_)
    assert nuevo is not None and nuevo["presencia_dron"] == "confirmada"
    # Como quedó con la regla anterior: la declaración, sin confirmar la presencia.
    anterior = {**nuevo, "presencia_dron": "no_confirmada",
                "afirmaciones": [a for a in nuevo["afirmaciones"]
                                 if a not in afirmaciones_de_presencia(nuevo)]}  # fmt: skip
    # Lo guardado antes del criterio ya no pasa la validación: entra tal cual en la tabla.
    with almacen._conexion:
        almacen._upsert("incidentes", {"id": id_, "tipo": anterior["tipo"],
                                       "estado": anterior["estado"]["actual"],
                                       "documento": json.dumps(anterior)})  # fmt: skip
    despues = AHORA + timedelta(hours=1)
    hechos, fallidos = presencia.revisar(almacen, despues, MODELOS)
    assert fallidos == []
    [cambio] = hechos
    assert cambio.incidente == id_
    assert cambio.fuente_id.endswith("-declaracion-1")
    assert "Københavns Politi" in cambio.motivo
    revisado = almacen.incidente(id_)
    assert revisado is not None and revisado["presencia_dron"] == "confirmada"
    assert revisado["control"]["ultima_actualizacion"]["valor"] == "2025-09-24T13:00Z"
    # El historial guarda el cambio con la afirmación y la fuente que lo provoca.
    filas = almacen.historial(id_)
    ultimo = [f for f in filas if f["tabla"] == "incidentes"][-1]
    assert ultimo["anterior"]["presencia_dron"] == "no_confirmada"
    assert afirmaciones_de_presencia(ultimo["nuevo"]) == [
        declaraciones.afirmacion_presencia(cambio.fuente_id)
    ]
    # Y el motivo, con los campos que cambian.
    motivo = [f for f in filas if f["tabla"] == presencia.TABLA_MOTIVOS][-1]
    assert motivo["anterior"]["presencia_dron"] == "no_confirmada"
    assert motivo["nuevo"]["presencia_dron"] == "confirmada"
    assert "criterio de presencia" in motivo["nuevo"]["motivo"]
    # Idempotente: otra pasada no cambia nada.
    assert presencia.revisar(almacen, despues, MODELOS) == ([], [])
