"""El titular lo decide un solo sitio (proceso/decidir.decidir_titulo): una prueba por causa de los
titulares que oscilaban o se publicaban mal el 22-23 de octubre de 2026, con la ficha real."""

import copy
import json

import pytest

from esquema import Documento
from proceso import atribucion, decidir, referencia, titulares

GENTILICIO_EN = ("Russian", "Ukrainian", "Turkish")


def _copia(id_: str) -> Documento:
    ruta = referencia.DIRECTORIO / "fichas" / f"{id_}.json"
    documento: Documento = json.loads(ruta.read_text(encoding="utf-8"))
    return documento


def _ficha(id_: str, titulo: dict[str, str], enlace: str, pais: str) -> Documento:
    """Lo que el titular necesita de una ficha: su fuente, su país, su estado y su presencia."""
    return {
        "id": id_,
        "titulo": titulo,
        "fuentes": [{"id": "f1", "enlace": enlace, "frase_origen": ""}],
        "lugar": {"pais": pais, "nivel": "region"},
        "estado": {"actual": "notificado", "historial": []},
        "presencia_dron": "no_confirmada",
    }


def _sin_atribucion(es: str, en: str) -> dict[str, str]:
    return atribucion.titulo_sin_atribucion({"titulo": {"es": es, "en": en}, "fuentes": []})


def test_la_revision_a_mano_pasa_por_la_presencia_y_la_atribucion() -> None:
    # Tulcea (2025-00378): la revisión a mano del titular entraba tal cual al guardar y ganaba a
    # la atribución y a la presencia; cada hora se publicaba «Drones rusos…» sin atribución.
    tulcea = _copia("EODI-2025-00378")
    tulcea["titulo"] = {
        "es": "Drones rusos cerca de la frontera en Tulcea: dos F-16 despegan de la base de Borcea",
        "en": "Russian drones near the border in Tulcea: two F-16s take off from Borcea air base",
    }
    decidido = decidir.aplicar(tulcea)
    assert decidido["presencia_dron"] == "no_confirmada"
    assert decidido["titulo"] == {
        "es": "Posibles drones cerca de la frontera en Tulcea: dos F-16 despegan de la base de "
        "Borcea",
        "en": "Possible drones near the border in Tulcea: two F-16s take off from Borcea air base",
    }


def test_el_titular_decidido_no_cambia_con_las_demas_reglas() -> None:
    # Sin vaivén: guardar otra vez, ajustar a la presencia o quitar la atribución dejan el mismo.
    decidido = decidir.aplicar(_copia("EODI-2025-00378"))
    assert decidir.aplicar(copy.deepcopy(decidido))["titulo"] == decidido["titulo"]
    assert titulares.ajustar_incidente(decidido)["titulo"] == decidido["titulo"]
    assert atribucion.titulo_segun_atribucion(decidido) == decidido["titulo"]


def test_la_nacionalidad_del_espacio_aereo_se_queda() -> None:
    # 2026-00650: «Ukrainian airspace» perdía «Ukrainian» y el titular sugería espacio rumano.
    assert _sin_atribucion(
        "Alerta RO-Alert en Tulcea por posibles drones detectados en el espacio aéreo ucraniano",
        "RO-Alert issued in Tulcea over possible drones detected in Ukrainian airspace",
    ) == {
        "es": "Alerta RO-Alert en Tulcea por posibles drones detectados en el espacio aéreo "
        "ucraniano",
        "en": "RO-Alert issued in Tulcea over possible drones detected in Ukrainian airspace",
    }


def test_la_nacionalidad_de_una_persona_se_queda() -> None:
    # 2026-00222 (Vilna): «Ukrainian citizen» pasó a «Citizen»; la persona no es el autor del dron.
    titulo = _sin_atribucion(
        "Un ciudadano ucraniano detenido por volar un dron cerca del aeropuerto de Vilna",
        "Ukrainian citizen detained for flying a drone near Vilnius airport",
    )
    assert titulo["es"].startswith("Un ciudadano ucraniano")
    assert titulo["en"].startswith("Ukrainian citizen")


def test_la_nacionalidad_del_dron_se_quita_en_los_dos_idiomas() -> None:
    # 2026-00668 (Egeo): «Turkish» se quitaba del inglés y «turcos» se quedaba en español.
    titulo = _sin_atribucion(
        "Posibles drones y aviones turcos entran sin autorización en el FIR de Atenas",
        "Possible Turkish drones and aircraft enter Athens FIR without authorization",
    )
    assert titulo == {
        "es": "Posibles drones y aviones entran sin autorización en el FIR de Atenas",
        "en": "Possible drones and aircraft enter Athens FIR without authorization",
    }
    rusos = _sin_atribucion(
        "Drones militares rusos sobre Tulcea", "Russian Shahed drones over Tulcea"
    )
    assert rusos == {"es": "Drones militares sobre Tulcea", "en": "Shahed drones over Tulcea"}


def test_un_titular_solo_afirma_drones_que_nombra_una_cita() -> None:
    # 2026-00668: la cita guardada hablaba de ocho aeronaves; el titular se rehace con la cita
    # que nombra los drones (cinco UAV según el Estado Mayor), sin su país y con la presencia.
    enlace = (
        "https://inewsgr.com/441/synechizoun-oi-tourkikes-voltes-sto-aigaio-machitika-"
        "kataskopeftiko-kai-drones-ston-elliniko-enaerio-choro.htm"
    )
    egeo = _ficha(
        "EODI-2026-00668",
        {
            "es": "Posibles drones y aviones turcos entran sin autorización en el FIR de Atenas "
            "sobre el Egeo",
            "en": "Possible drones and aircraft enter Athens FIR over the Aegean without "
            "authorization",
        },
        enlace,
        "GR",
    )
    titulo = decidir.decidir_titulo(egeo)
    assert titulo == {
        "es": "Cinco posibles drones y tres aviones entran sin autorización en el FIR de Atenas "
        "sobre el mar Egeo",
        "en": "Five possible drones and three aircraft enter the Athens FIR over the Aegean Sea "
        "without authorization",
    }
    revision = decidir.revision_de(egeo, "titulo")
    assert revision is not None and "UAV" in revision["cita"]
    assert not any(g in titulo["en"] for g in GENTILICIO_EN)
    assert "turc" not in titulo["es"]


def test_ningun_otro_paso_escribe_el_titular() -> None:
    # Los pasos que antes rehacían el titular (el control, la revisión a mano, la barrera, las
    # declaraciones oficiales) lo piden a decidir.py o lo dejan para el guardado.
    from pathlib import Path

    raiz = Path(__file__).resolve().parent.parent
    for fichero in ("recogida/control_fichas.py", "recogida/revisados.py", "recogida/barrera.py",
                    "recogida/declaraciones_oficiales.py"):  # fmt: skip
        texto = (raiz / fichero).read_text(encoding="utf-8")
        assert "titulo_segun_atribucion(" not in texto, fichero
        assert "titulares.ajustar_incidente(" not in texto, fichero


def test_k_cuenta_el_dato_que_cambia_y_vuelve_cada_hora() -> None:
    # Tulcea (2025-00378): cada recogida, la atribución quitaba «rusos» y se quedaba el titular
    # viejo; el inicio de Aalborg (2025-00238) iba y volvía entre dos pasos. Un arreglo deshecho
    # una sola vez (la zona de 2026-00019) no cuenta.
    from proceso import auditoria_fichas

    viejo, sin = {"es": "Drones rusos"}, {"es": "Drones"}
    cambios = [
        {"entidad_id": "EODI-2025-00378", "tabla": "incidentes_motivos",
         "anterior": {"titulo": viejo}, "nuevo": {"titulo": sin, "motivo": "atribución"}}
        for _ in range(4)
    ] + [
        {"entidad_id": "EODI-2025-00238", "tabla": "incidentes",
         "anterior": {"tiempo": a, "control": 1}, "nuevo": {"tiempo": b, "control": 2}}
        for a, b in [(55, 95), (95, 55)] * 2
    ] + [
        {"entidad_id": "EODI-2026-00019", "tabla": "incidentes",
         "anterior": {"zona": a}, "nuevo": {"zona": b}}
        for a, b in [("frontera", None), (None, "frontera")]
    ]  # fmt: skip
    assert auditoria_fichas.oscilan(cambios) == {
        "EODI-2025-00238": ["tiempo"],
        "EODI-2025-00378": ["titulo"],
    }
    resultado = auditoria_fichas.auditar([], cambios)
    assert resultado["K"] == []  # ninguna vigente entre los documentos


def test_k_no_cuenta_dos_veces_el_mismo_cambio_del_mismo_instante() -> None:
    # EODI-2026-00312 (27-28 de octubre de 2026): la zona pasó de 7 a 6 km con zona-1.1.0 y quedó
    # apuntada dos veces en el mismo segundo (la ficha y el motivo de la regla); luego volvió a
    # 7 con datos nuevos y pasó a «ataque». Son dos vueltas, no tres.
    from proceso import auditoria_fichas

    siete, seis = {"distancia_km": 7, "grupo": "frontera"}, {"distancia_km": 6, "grupo": "frontera"}
    ataque = {"grupo": "frontera", "motivo": "ataque"}
    cambios = [
        {"entidad_id": "EODI-2026-00312", "tabla": "incidentes", "fecha": fecha,
         "anterior": {"zona": a}, "nuevo": {"zona": b, **extra}}
        for fecha, a, b, extra in [
            ("2026-10-27T22:30:32Z", siete, seis, {}),
            ("2026-10-27T22:30:32Z", siete, seis, {"motivo": "grupo recalculado"}),
            ("2026-10-28T00:22:19Z", seis, siete, {}),
            ("2026-10-28T00:30:26Z", siete, ataque, {}),
        ]
    ]  # fmt: skip
    assert auditoria_fichas.oscilan(cambios) == {}
    # El mismo cambio en otro instante sí cuenta.
    otra = [{**cambios[1], "fecha": "2026-10-28T01:30:00Z"}]
    assert auditoria_fichas.oscilan([*cambios, *otra]) == {"EODI-2026-00312": ["zona"]}


def test_k_no_cuenta_los_titulares_intermedios_de_un_guardado() -> None:
    # EODI-2025-00043, 1 de noviembre de 2026: a las 05:27 una extracción nueva puso el titular sin
    # «Posible» y a las 11:30:27 la revisión lo devolvió. En ese mismo segundo, decidir y la
    # atribución anotaron titulares intermedios que nunca se guardaron: contaban otras dos vueltas.
    from proceso import auditoria_fichas

    posible, breve, sin = ({"es": "Posible dron cerca del aeropuerto de Riga"},
                           {"es": "Dron cerca del aeropuerto de Riga detiene los vuelos"},
                           {"es": "Dron cerca del aeropuerto de Riga"})  # fmt: skip
    id_ = "EODI-2025-00043"
    cambios = [
        {"entidad_id": id_, "tabla": tabla, "fecha": fecha, "anterior": {"titulo": a},
         "nuevo": {"titulo": b, **({"motivo": "regla"} if tabla != "incidentes" else {})}}
        for tabla, fecha, a, b in [
            ("incidentes", "2026-11-01T05:27:20Z", posible, breve),
            ("incidentes_motivos", "2026-11-01T05:27:20Z", posible, breve),
            ("incidentes", "2026-11-01T11:30:27Z", breve, posible),
            ("incidentes_motivos", "2026-11-01T11:30:27Z", sin, posible),
            ("incidentes_motivos", "2026-11-01T11:30:27Z", breve, sin),
        ]
    ]  # fmt: skip
    assert auditoria_fichas.oscilan(cambios) == {}
    # Un dato que de verdad va y vuelve en los guardados sigue contando.
    vueltas = [{**cambios[i % 2 * 2], "fecha": f"2026-11-01T{12 + i}:00:00Z"} for i in range(4)]
    assert auditoria_fichas.oscilan([*cambios, *vueltas]) == {id_: ["titulo"]}


# --- Los otros datos que oscilaban cada hora (22-23 de octubre de 2026) ----------------------


def test_la_fecha_oficial_no_pisa_el_inicio_revisado_a_mano() -> None:
    # Aalborg (2025-00238): la nota de balance de Rigspolitiet ponía las 21:00 (hora) y la
    # revisión devolvía las 21:40 (minuto) con la cita de ekstrabladet.dk, cada hora.
    from proceso import detalle

    tiempo = {
        "inicio": {"valor": "2025-09-25T21:40Z", "precision": "minuto"},
        "fin": {"valor": "2025-09-25T22:35Z", "precision": "minuto"},
        "duracion_min": 55,
        "origen_inicio": {"tipo": "explicita", "fuente_id": "revisada-59d1dccf850734f9"},
    }
    oficial = {"valor": "2025-09-25T21:00Z", "precision": "hora"}
    fuente = {
        "id": "detalle-169323e15cc02cc6",
        "medio": "Rigspolitiet",
        "enlace": "https://politi.dk",
    }
    assert detalle.inicio_oficial(tiempo, oficial, fuente) == tiempo


def test_la_revision_del_cierre_conserva_su_duracion_citada() -> None:
    # Hannover (2025-00001): la revisión «hubo cierre» borraba los 210 minutos que el control
    # lee en la cita («für dreieinhalb Stunden») y el control los volvía a poner.
    hannover = _ficha(
        "EODI-2025-00001",
        {"es": "Drones en Hannover", "en": "Drones in Hanover"},
        "https://ndr.de/nachrichten/niedersachsen/hannover_weser-leinegebiet/weihnachts-flieger-"
        "ausgebremst-drohnen-am-flughafen-hannover,drohnen-238.html",
        "DE",
    )
    hannover["consecuencias"] = {"cierre": {"valor": "si", "minutos": {"min": 210, "max": 210}}}
    hannover["tiempo"] = {"inicio": {"valor": "2025-12-26T19:50Z", "precision": "minuto"}}
    decidido = decidir.decidir_datos(hannover)
    assert decidido["consecuencias"]["cierre"] == {
        "valor": "si", "minutos": {"min": 210, "max": 210}
    }  # fmt: skip


def test_lo_revisado_a_mano_no_lo_quita_el_control() -> None:
    # Tarragona (2025-00404): la revisión pone la cárcel de Mas d'Enric y el control la quitaba
    # por llamarse como la localidad; Akrotiri (2026-00268): la ubicación oficial ponía la base
    # como localidad y la revisión de datos, la península.
    from recogida import revisados

    assert revisados.objetivo_revisado("EODI-2025-00404") == {
        "categoria": "otra", "nombre": "Centre Penitenciari Mas d'Enric"
    }  # fmt: skip
    akrotiri = _ficha(
        "EODI-2026-00268", {"es": "Dron", "en": "Drone"},
        "https://cyprus-mail.com/2026/03/02/govt-monitoring-situation-after-akrotiri-drone-strike",
        "GB",
    )  # fmt: skip
    assert (decidir.revision_de(akrotiri, "lugar") or {})["valor"] == {"localidad": "Akrotiri"}


def test_varios_gentilicios_se_quitan_juntos() -> None:
    # Letonia (2026-00756/00757, 5 de noviembre de 2026): quitar solo el primero de «ruso y
    # ucraniano» dejaba «Drones y ucraniano…» y «Russian and drones…».
    assert _sin_atribucion(
        "Drones ruso y ucraniano violan el espacio aéreo de Letonia",
        "Russian and Ukrainian drones violate Latvian airspace",
    ) == {
        "es": "Drones violan el espacio aéreo de Letonia",
        "en": "Drones violate Latvian airspace",
    }
    assert _sin_atribucion(
        "Drones rusos y ucranianos entran en Letonia; uno cae en el este del país",
        "Russian and Ukrainian drones enter Latvia; one crashes in the east of the country",
    ) == {
        "es": "Drones entran en Letonia; uno cae en el este del país",
        "en": "Drones enter Latvia; one crashes in the east of the country",
    }
    assert _sin_atribucion(
        "Dos drones entran en el espacio aéreo de Letonia, uno probablemente ruso y otro ucraniano",
        "Two drones enter Latvian airspace, one probably Russian and the other Ukrainian",
    ) == {
        "es": "Dos drones entran en el espacio aéreo de Letonia",
        "en": "Two drones enter Latvian airspace",
    }
    # Lo que no es del dron se queda: «ataques rusos y ucranianos» no lleva dron.
    assert _sin_atribucion("Ataques rusos y ucranianos", "Russian and Ukrainian attacks") == {
        "es": "Ataques rusos y ucranianos",
        "en": "Russian and Ukrainian attacks",
    }


@pytest.mark.parametrize(
    ("es", "en", "es_queda", "en_queda"),
    [
        # EODI-2026-00760 (6 de noviembre de 2026): el reparto entre comas dejaba la segunda
        # («Dos drones, violan»), y «one … and one …» no se reconocía.
        ("Dos drones, uno ruso y otro ucraniano, violan el espacio aéreo de Letonia",
         "Two drones, one likely Russian and one Ukrainian, violate Latvian airspace",
         "Dos drones violan el espacio aéreo de Letonia", "Two drones violate Latvian airspace"),
        ("Dos drones, uno probablemente ruso y el otro ucraniano, entran en Letonia",
         "Two drones, one probably Russian and the other Ukrainian, enter Latvia",
         "Dos drones entran en Letonia", "Two drones enter Latvia"),
        ("Dos drones, una presuntamente bielorrusa y otra rusa, cruzan a Lituania",
         "Two drones, one allegedly Belarusian and another Russian, cross into Lithuania",
         "Dos drones cruzan a Lituania", "Two drones cross into Lithuania"),
        ("Dos drones cruzan a Polonia, uno ruso o uno bielorruso",
         "Two drones cross into Poland, one Russian or one Belarusian",
         "Dos drones cruzan a Polonia", "Two drones cross into Poland"),
        # Una coma que no encierra el reparto se queda.
        ("Dos drones, uno ruso y otro ucraniano, violan el espacio aéreo de Letonia, "
         "según el ejército",
         "Two drones, one Russian and one Ukrainian, violate Latvian airspace, army says",
         "Dos drones violan el espacio aéreo de Letonia, según el ejército",
         "Two drones violate Latvian airspace, army says"),
    ],
)  # fmt: skip
def test_el_reparto_sale_con_sus_comas(es: str, en: str, es_queda: str, en_queda: str) -> None:
    assert _sin_atribucion(es, en) == {"es": es_queda, "en": en_queda}


def test_la_coma_suelta_de_un_titular_guardado_sale() -> None:
    # EODI-2026-00760 guardó «Dos drones, violan…» antes del arreglo.
    assert _sin_atribucion(
        "Dos drones, violan el espacio aéreo de Letonia", "Two drones, violate Latvian airspace"
    ) == {
        "es": "Dos drones violan el espacio aéreo de Letonia",
        "en": "Two drones violate Latvian airspace",
    }
    # Las comas que emparejan un inciso o separan dos frases se quedan.
    for es, en in (
        ("Posible dron, probablemente un globo, cierra 45 minutos una pista de Schiphol",
         "Possible drone, probably a balloon, closes a Schiphol runway for 45 minutes"),
        ("Un dron sobrevuela el sur de Moldavia, de Lesnaia hacia Săiți",
         "A drone flies over southern Moldova, from Lesnaia towards Săiți"),
        ("Dron explota en Galați, Rumania rechaza activar Artículo 4 de la OTAN",
         "Drone explodes in Galați, Romania refuses to trigger NATO Article 4"),
        ("Drones, aviones y cazas sobre Letonia", "Drones, planes and fighters over Latvia"),
    ):  # fmt: skip
        assert _sin_atribucion(es, en) == {"es": es, "en": en}


def test_lo_que_no_es_un_reparto_se_queda() -> None:
    # Ni la nacionalidad del espacio aéreo ni «uno» que no reparte gentilicios.
    assert _sin_atribucion(
        "Dos drones entran en el espacio aéreo ucraniano, uno cae en Moldavia",
        "Two drones enter Ukrainian airspace, one crashes in Moldova",
    ) == {
        "es": "Dos drones entran en el espacio aéreo ucraniano, uno cae en Moldavia",
        "en": "Two drones enter Ukrainian airspace, one crashes in Moldova",
    }
    assert _sin_atribucion("Ataques rusos y ucranianos", "Russian and Ukrainian attacks") == {
        "es": "Ataques rusos y ucranianos",
        "en": "Russian and Ukrainian attacks",
    }
