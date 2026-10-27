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


def test_la_cita_revisada_de_la_autoridad_vuelve_a_confirmar() -> None:
    """EODI-2026-00648: la cita revisada de la policía llegó con la ficha aún confirmada por la
    cita vacía (sin paso propio en el historial) y el control la bajó a notificado; la cita
    revisada la vuelve a confirmar, una vez."""
    from recogida import revisados

    cita: dict[str, Any] = {
        "incidente": "EODI-2026-09648",
        "enlace": "https://wiadomosci.gazeta.pl/polska/jozefow.html",
        "medio": "wiadomosci.gazeta.pl",
        "fecha": "2026-10-20",
        "idioma": "pl",
        "frase": CONTENIDO,
        "declaracion": {"autoridad": "Komenda Stołeczna Policji", "pais": "PL",
                        "categoria": "policia", "afirma": "incidente"},
    }  # fmt: skip
    instante = ejemplos.instante("2026-10-21T06:00Z")
    con = revisados.con_citas(_jozefow(), [cita])
    assert con["estado"]["actual"] == "confirmado"
    bajado = reglas.bajar_estado(con, ejemplos.instante("2026-10-21T05:17Z"))
    assert bajado is not None and bajado["estado"]["actual"] == "notificado"
    vuelto = revisados.reconfirmar(bajado, [cita], instante)
    assert vuelto["estado"]["actual"] == "confirmado"
    paso = vuelto["estado"]["historial"][-1]
    assert paso["fuente_id"] == revisados.fuente_de_cita(cita, bajado)["id"]
    assert reglas.bajar_estado(vuelto, instante) is None
    assert revisados.reconfirmar(vuelto, [cita], instante) is vuelto
    # Una cita revisada sin declaración, o que niega el suceso, no confirma nada.
    prensa = {k: v for k, v in cita.items() if k != "declaracion"}
    assert revisados.reconfirmar(bajado, [prensa], instante) is bajado
    niega = {**cita, "declaracion": {**cita["declaracion"], "afirma": "niega_incidente"}}
    assert revisados.reconfirmar(bajado, [niega], instante) is bajado


def test_e_no_cuenta_como_atribucion_el_dron_negado() -> None:
    # EODI-2025-00203 (Schiphol): la Marechaussee dice que no se detectó ningún dron y que era un
    # globo. Sin confirmar, la auditoría no la contaba bien (nombraba el dron al negarlo).
    documento = _jozefow()
    documento["presencia_dron"] = "no_confirmada"
    documento["afirmaciones"] = [a for a in documento["afirmaciones"]
                                 if a["campo"] != "presencia_dron"]  # fmt: skip
    documento["fuentes"][1]["frase_origen"] = (
        "an investigation showed no drone was detected on radar and that the object was likely "
        "a balloon."
    )
    assert not presencia.atribuida_por_autoridad(documento)
    assert not auditoria_fichas._e(documento)
    documento["fuentes"][1]["frase_origen"] = "Een drone werd waargenomen boven de luchthaven."
    assert auditoria_fichas._e(documento)


def test_f_no_cuenta_la_fecha_de_la_propia_nota() -> None:
    # EODI-2025-00125 (Doel): el titular de DW lleva su propia fecha («10.11.2025»); el suceso
    # es del 9, que dice otra nota («ieri a tarda sera»). Riga (EODI-2025-00153) sí cuenta.
    documento = _jozefow()
    documento["lugar"]["pais"] = "BE"
    documento["tiempo"] = {
        "inicio": {"valor": "2025-11-09T20:00Z", "precision": "aproximada"},
        "origen_inicio": {"tipo": "publicacion", "motivo": "fecha de publicación"},
    }
    fuente = documento["fuentes"][0]
    fuente.update(fecha={"valor": "2025-11-10T01:45Z", "precision": "minuto"}, idioma="ru",
                  pais="DE", frase_origen="В Бельгии над АЭС Doel заметили три беспилотника – "
                  "DW – 10.11.2025")  # fmt: skip
    assert not auditoria_fichas._fecha_de_publicacion(documento)
    fuente.update(idioma="lv", pais="LV", frase_origen="2025. gada 13. janvārī Rīgas lidostā "
                  "notikušā bezpilota gaisa kuģu incidenta laikā")  # fmt: skip
    assert auditoria_fichas._fecha_de_publicacion(documento)


def test_e_avisa_si_una_misma_fuente_confirma_y_desmiente_en_la_web() -> None:
    # EODI-2025-00124 (Sofía): la web enseñaba «Confirmado» y «Desmentido» con la frase del
    # director del aeropuerto, porque las fechas coherentes le daban al paso confirmado la fuente
    # del desmentido (proceso/coherencia.py). Con la regla arreglada, cada paso lleva la suya.
    documento = _jozefow()
    aviacion, director = documento["fuentes"][0], documento["fuentes"][1]
    documento["estado"] = {"actual": "desmentido", "historial": [
        {"estado": "notificado", "fecha": aviacion["fecha"], "fuente_id": aviacion["id"]},
        {"estado": "confirmado", "fecha": {"valor": "2025-02-12T07:00Z", "precision": "minuto"},
         "fuente_id": aviacion["id"]},
        {"estado": "desmentido", "fecha": {"valor": "2025-02-12T06:30Z", "precision": "minuto"},
         "fuente_id": director["id"]},
    ]}  # fmt: skip
    assert not auditoria_fichas.misma_fuente_en_pasos_opuestos(documento)
    documento["estado"]["historial"][1]["fuente_id"] = director["id"]
    assert auditoria_fichas.misma_fuente_en_pasos_opuestos(documento)
    assert auditoria_fichas._e(documento)


def test_b_acepta_el_objetivo_revisado_a_mano() -> None:
    # Tulcea: el titular nombra la base de Borcea, de donde solo despegaron los F-16; la revisión
    # a mano, con su cita, deja la ficha sin objetivo.
    documento = ejemplos.incidente_minimo()
    documento["titulo"] = {
        "es": "Dos F-16 despegan de la base de Borcea",
        "en": "Two F-16s take off from Borcea air base",
    }
    documento.pop("objetivo", None)
    assert auditoria_fichas._b(documento)
    documento["id"] = "EODI-2025-00378"
    documento["fuentes"][0]["enlace"] = (
        "https://adevarul.ro/stiri-interne/evenimente/nou-atac-cu-drone-langa-frontiera-cu-romania-2418348.html"
    )
    assert not auditoria_fichas._b(documento)


def test_l_la_que_queda_sin_autoridad_cuando_la_unida_la_tenia() -> None:
    # EODI-2026-00108 (Auvere): la declaración de la KAPO se quedó en la unida.
    queda = {**ejemplos.incidente_minimo(), "id": "EODI-2026-00108",
             "fuentes": [ejemplos.fuente("gdelt-a", "C")]}  # fmt: skip
    unida = {**ejemplos.incidente_minimo(), "id": "EODI-2026-00333",
             "fusionado_en": "EODI-2026-00108",
             "fuentes": [ejemplos.fuente("gdelt-a-declaracion-1", "B",
                                         es_autoridad=True)]}  # fmt: skip
    assert auditoria_fichas.auditar([queda, unida])["L"] == ["EODI-2026-00108"]
    con = {**queda, "fuentes": [*queda["fuentes"], *unida["fuentes"]]}
    assert auditoria_fichas.auditar([con, unida])["L"] == []


def test_p_la_rebajada_sin_quien_ni_cuando() -> None:
    # EODI-2025-00228 (Aalborg): «no acreditada» por una revisión a mano, sin el cierre de la
    # investigación de la policía en su historial.
    sin = {**ejemplos.incidente_minimo(), "presencia_dron": "no_acreditada"}
    assert auditoria_fichas.auditar([sin])["P"] == [sin["id"]]
    fuente_id = sin["fuentes"][0]["id"]
    paso = {"valor": "no_acreditada", "fecha": ejemplos.instante("2026-06-25T00:00Z", "dia"),
            "fuente_id": fuente_id}  # fmt: skip
    semilla = {"valor": "confirmada", "fecha": ejemplos.instante("2025-09-24T21:15Z", "dia"),
               "fuente_id": fuente_id}  # fmt: skip
    sin_quien = {**sin, "presencia_historial": [semilla, paso]}
    assert auditoria_fichas.auditar([sin_quien])["P"] == [sin["id"]]
    quien = {"es": "la Policía de Jutlandia del Norte", "en": "the North Jutland Police"}
    con = {**sin, "presencia_historial": [semilla, {**paso, "quien": quien}]}
    assert auditoria_fichas.auditar([con])["P"] == []
    # Con la presencia sin rebajar no cuenta.
    assert auditoria_fichas.auditar([ejemplos.incidente_minimo()])["P"] == []


def test_m_el_lugar_revisado_con_el_punto_de_otro_sitio() -> None:
    # EODI-2026-00238: la revisión dice Rachelu (Luncavița) y el punto era el de Tulcea, a 40 km.
    from proceso import decidir

    documento = ejemplos.incidente_minimo()
    documento["id"] = "EODI-2026-00238"
    enlace = ("https://digi24.ro/stiri/actualitate/momentul-in-care-militarii-detoneaza-drona-cu-"
              "incarcatura-exploziva-descoperita-in-tulcea-3840077")  # fmt: skip
    documento["fuentes"] = [{**documento["fuentes"][0], "enlace": enlace}]
    documento["lugar"] = {"pais": "RO", "localidad": "Rachelu", "radio_km": 5,
                          "punto": {"lat": 45.1787, "lon": 28.80501}}  # fmt: skip
    assert auditoria_fichas.auditar([documento])["M"] == ["EODI-2026-00238"]
    decidido = decidir.decidir_datos(documento)
    assert decidido["lugar"]["nivel"] == "localidad"
    assert abs(decidido["lugar"]["punto"]["lon"] - 28.32) < 0.05
    assert auditoria_fichas.auditar([decidido])["M"] == []


def test_n_la_noticia_de_otro_mes_con_la_fecha_de_publicacion() -> None:
    # EODI-2026-00663: una noticia de octubre sobre los drones de Leipzig de septiembre.
    documento = ejemplos.incidente_minimo()
    documento["tiempo"] = {"inicio": ejemplos.instante("2026-10-20T00:00Z", "dia"),
                           "origen_inicio": {"tipo": "publicacion"}}  # fmt: skip
    frase = "Im September kreisten Drohnen über dem Flughafen Leipzig"
    fuente = {**documento["fuentes"][0], "idioma": "de", "frase_origen": frase}
    documento["fuentes"] = [fuente]
    assert auditoria_fichas.auditar([documento])["N"] == [documento["id"]]
    # Con el mes de la noticia, o en inglés «may», no cuenta.
    fuente["frase_origen"] = "Am 19. Oktober kreisten Drohnen über dem Flughafen Leipzig"
    assert auditoria_fichas.auditar([documento])["N"] == []
    documento["fuentes"] = [{**fuente, "idioma": "en", "frase_origen": "Drones may return"}]
    assert auditoria_fichas.auditar([documento])["N"] == []


def test_q_ninguna_fuente_legible() -> None:
    # EODI-2025-00278 (Taraclia): su única fuente, news.yam.md, da 404 y no tiene copia archivada.
    documento = ejemplos.incidente_minimo()
    enlace = documento["fuentes"][0]["enlace"]
    caida = {enlace: {"caido": True}}
    assert auditoria_fichas.auditar([documento], [], caida)["Q"] == [documento["id"]]
    # Con copia archivada, o sin resultado del archivo, se puede leer.
    con_copia = {enlace: {"caido": True, "copia": {"enlace": "https://web.archive.org/web/x"}}}
    assert auditoria_fichas.auditar([documento], [], con_copia)["Q"] == []
    assert auditoria_fichas.auditar([documento], [], {"https://otro": {"caido": True}})["Q"] == []
    # Otra fuente legible basta; sin la tabla no se mira; la retirada no cuenta.
    otra = {**documento["fuentes"][0], "id": "otra", "enlace": "https://ejemplo.org/otra"}
    assert auditoria_fichas.auditar([{**documento, "fuentes": [*documento["fuentes"], otra]}],
                                    [], caida)["Q"] == []  # fmt: skip
    assert auditoria_fichas.auditar([documento])["Q"] == []
    assert auditoria_fichas.auditar([{**documento, "retirado": {}}], [], caida)["Q"] == []
