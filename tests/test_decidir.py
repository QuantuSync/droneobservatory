"""Un solo sitio decide el estado y la presencia (proceso/decidir.py): una prueba por causa de las
discrepancias de estado y presencia de la referencia, con la ficha real como ejemplo."""

import copy
import json

from esquema import Documento
from proceso import decidir, referencia, validaciones
from proceso.presencia import REVISADOS
from recogida import revisados

INSTANTE = {"valor": "2026-10-21T15:00Z", "precision": "minuto"}


def _copia(id_: str) -> Documento:
    ruta = referencia.DIRECTORIO / "fichas" / f"{id_}.json"
    documento: Documento = json.loads(ruta.read_text(encoding="utf-8"))
    return documento


def _sin_revision(id_: str) -> tuple[Documento, list[Documento]]:
    """La ficha como estaba antes de sus citas revisadas (solo la noticia que la abrió) y esas
    citas de configuracion/incidentes_revisados.json."""
    documento = _copia(id_)
    citas = [c for c in revisados.cargar()["citas"] if c["incidente"] == id_]
    revisadas = {revisados.fuente_de_cita(c, documento)["id"] for c in citas}
    antes = copy.deepcopy(documento)
    antes["fuentes"] = [f for f in documento["fuentes"] if f["id"] not in revisadas]
    antes["afirmaciones"] = [
        a for a in documento.get("afirmaciones", []) if a["fuente_id"] not in revisadas
    ]
    antes["estado"] = {"actual": "notificado", "historial": documento["estado"]["historial"][:1]}
    antes.pop("atribucion", None)
    antes["presencia_dron"] = "no_confirmada"
    return antes, citas


def test_la_autoridad_que_cuenta_lo_ocurrido_confirma_el_suceso() -> None:
    # Geilenkirchen: la policía cuenta que fue a mirar y no vio ningún dron; el aviso ocurrió.
    geilenkirchen = _copia("EODI-2025-00225")
    assert geilenkirchen["estado"]["actual"] == "notificado"
    decision = decidir.decidir_estado(geilenkirchen)
    assert (decision.valor, decision.regla) == ("confirmado", "autoridad_lo_cuenta")
    aplicado = decidir.aplicar(geilenkirchen)
    assert aplicado["estado"]["historial"][-1]["fuente_id"] == decision.fuente_id
    # Schiphol: la Marechaussee concluye que era un globo; el suceso queda confirmado y la
    # presencia, descartada.
    schiphol = decidir.aplicar(_copia("EODI-2025-00203"))
    assert (schiphol["estado"]["actual"], schiphol["presencia_dron"]) == (
        "confirmado", "descartada",
    )  # fmt: skip


def test_el_desmentido_que_solo_niega_el_dron_no_desmiente_el_suceso() -> None:
    # Limburgo: «Ces recherches n'avaient permis de retrouver aucun drone».
    limburgo = _copia("EODI-2025-00357")
    assert limburgo["estado"]["actual"] == "desmentido"
    assert decidir.decidir_estado(limburgo).valor == "confirmado"
    # Vilna: el radar vio una bandada de pájaros; el tráfico se paró.
    vilna = _copia("EODI-2026-00007")
    assert vilna["estado"]["actual"] == "desmentido"
    assert decidir.aplicar(vilna)["estado"]["actual"] == "confirmado"


def test_la_cita_revisada_de_la_autoridad_confirma_o_atribuye() -> None:
    # Riga: el aeropuerto informa del aviso (cita revisada que afirma el incidente).
    riga, citas = _sin_revision("EODI-2025-00043")
    assert decidir.decidir_estado(riga).valor == "notificado"
    assert decidir.aplicar(revisados.con_citas(riga, citas))["estado"]["actual"] == "confirmado"
    # Varsovia: Tusk atribuye los drones a Rusia y el ejército confirma que los derribó.
    varsovia, citas = _sin_revision("EODI-2025-00233")
    resultado = decidir.aplicar(revisados.con_citas(varsovia, citas))
    assert resultado["estado"]["actual"] == "atribuido"
    assert resultado["atribucion"]["pais"] == "RU"
    assert resultado["presencia_dron"] == "confirmada"


def test_la_presencia_revisada_y_las_aeronaves_no_tripuladas() -> None:
    # Aalborg: Rigspolitiet cerró la investigación sin probarlo ni descartarlo.
    aalborg = _copia("EODI-2025-00228")
    decision = decidir.decidir_presencia(aalborg)
    assert (decision.valor, decision.regla) == ("no_acreditada", "revision")
    # Tulcea: el MApN detectó por radar «dos aeronaves no tripuladas».
    tulcea, citas = _sin_revision("EODI-2026-00488")
    assert decidir.aplicar(revisados.con_citas(tulcea, citas))["presencia_dron"] == "confirmada"


# --- Los demás datos (decidir_datos y el tipo), una prueba por causa --------------------------


def test_el_objetivo_toma_el_oaci_del_nomenclator_y_la_carcel_es_otra() -> None:
    # Kleine-Brogel: base aérea con OACI (EBBL) en el nomenclátor; la ficha no lo tenía.
    kleine_brogel = decidir.decidir_objetivo(_copia("EODI-2025-00080"))
    assert kleine_brogel is not None
    assert (kleine_brogel["categoria"], kleine_brogel["oaci"]) == ("aeropuerto", "EBBL")
    # Schiphol: el nombre de la ficha está dentro del del nomenclátor (Luchthaven Schiphol).
    schiphol = decidir.decidir_objetivo(_copia("EODI-2025-00203"))
    assert schiphol is not None and schiphol["oaci"] == "EHAM"
    # Mendizábal: una cárcel es «otra», no «gubernamental».
    carcel = decidir.decidir_objetivo(_copia("EODI-2026-00625"))
    assert carcel is not None and carcel["categoria"] == "otra"


def test_el_objetivo_que_nombra_el_titular() -> None:
    # Varsovia: el titular nombra el aeropuerto que cerró y la ficha no tenía objetivo.
    varsovia = decidir.decidir_objetivo(_copia("EODI-2025-00233"))
    assert varsovia is not None and varsovia["oaci"] == "EPWA"


def test_la_incursion_la_demuestra_una_autoridad() -> None:
    # Kleine-Brogel: confirmado, pero nadie dice de dónde venían los drones.
    assert decidir.aplicar(_copia("EODI-2025-00080"))["tipo"] == "sobrevuelo"
    # Moldavia: el Ministerio de Defensa cuenta que el Shahed sobrevoló su espacio aéreo.
    assert decidir.aplicar(_copia("EODI-2026-00112"))["tipo"] == "incursion"
    # Constanza: solo fuentes anónimas, sin autoridad.
    assert decidir.aplicar(_copia("EODI-2025-00395"))["tipo"] == "sobrevuelo"
    # Chelsea 3: un buque alcanzado en el mar; ninguna autoridad dice que estuviera en aguas
    # búlgaras.
    assert decidir.aplicar(_copia("EODI-2026-00512"))["tipo"] == "sobrevuelo"
    # Sulina (EODI-2026-00541): en el mar sí cuenta la autoridad que dice que el radar siguió al
    # dron en el espacio aéreo nacional.
    sulina = _copia("EODI-2026-00512")
    sulina["fuentes"][5]["frase_origen"] = (
        "Radarele au detectat o dronă în spațiul aerian național, la sud-est de Sulina."
    )
    assert decidir.aplicar(sulina)["tipo"] == "incursion"


def test_sin_dron_segun_la_autoridad_el_numero_es_desconocido() -> None:
    # Lakenheath: el UK Airprox Board concluye que el «dron» era un F-15.
    assert decidir.decidir_drones(_copia("EODI-2025-00164")) == "desconocido"


def test_las_revisiones_de_datos_con_su_cita() -> None:
    # Riga: el aeropuerto paró los vuelos unos minutos (cierre revisado): interrupción.
    assert decidir.aplicar(_copia("EODI-2025-00043"))["tipo"] == "interrupcion_aeroportuaria"
    # Sofía: el viernes por la noche, 7 de febrero, no el día de las noticias.
    sofia = decidir.decidir_datos(_copia("EODI-2025-00124"))
    assert sofia["tiempo"]["inicio"]["valor"].startswith("2025-02-07")
    # Dublín era el destino del avión: el dron estaba frente a la costa de Wicklow.
    wicklow = decidir.decidir_datos(_copia("EODI-2026-00278"))
    assert wicklow["lugar"]["localidad"] == "costa de Wicklow"
    # Una ficha con el mismo identificador y sin esas fuentes (una de prueba) no las toma.
    ajena = _copia("EODI-2025-00124")
    ajena["fuentes"] = []
    ajena["lugar"] = {**ajena["lugar"], "pais": "ES"}
    assert decidir.decidir_datos(ajena)["tiempo"] == ajena["tiempo"]


def test_cada_revision_de_datos_lleva_cita_y_enlace() -> None:
    datos = json.loads(REVISADOS.read_text(encoding="utf-8"))["datos"]
    for revision in datos:
        assert revision["campo"] in decidir.CAMPOS_REVISABLES
        assert revision["motivo"]
        if revision["valor"] != "desconocido":
            assert revision["cita"] and revision["enlace"].startswith("http"), revision
            assert len(revision["cita"].split()) <= 25, revision


def test_el_homonimo_lo_decide_la_fuente() -> None:
    # Józefów «w gminie Nieporęt»: el pueblo de Nieporęt, no la ciudad de junto a Otwock.
    jozefow = decidir.decidir_datos(_copia("EODI-2026-00648"))["lugar"]
    assert jozefow["localidad"] == "Józefów"
    assert abs(jozefow["punto"]["lat"] - 52.38) < 0.05


def test_la_presencia_revisada_manda_sobre_la_cita_revisada() -> None:
    # Tulcea: la cita revisada del MApN confirma la alerta; la revisión de la presencia, con el
    # radar sin entradas en el espacio aéreo nacional, dice que el dron no está confirmado.
    tulcea = _copia("EODI-2025-00378")
    tulcea["fuentes"] = [
        *tulcea["fuentes"],
        {
            **tulcea["fuentes"][0],
            "id": "revisada-94fd17f7c9b21fcd-declaracion-1",
            "es_autoridad": True,
            "campos_respaldados": ["estado", "presencia_dron"],
        },
    ]
    tulcea["afirmaciones"] = [
        *tulcea.get("afirmaciones", []),
        {
            "campo": "presencia_dron",
            "valor": "confirmada",
            "fuente_id": "revisada-94fd17f7c9b21fcd-declaracion-1",
        },
    ]
    decidido = decidir.aplicar(tulcea, frozenset(), True)
    assert decidido["presencia_dron"] == "no_confirmada"
    # Y se puede guardar: la revisión a mano, con su cita, manda sobre la frase de la autoridad.
    assert validaciones.errores_presencia(decidido) == []


def test_una_reextraccion_no_quita_el_punto_revisado() -> None:
    # Sulina: la reextracción de la 01:17 UTC del 23 de octubre de 2026 (noticias nuevas, el
    # experto en el lugar) dejó solo la región «Marea Neagră» y la ficha perdió su punto. El lugar
    # revisado manda con su nivel y su punto en cada guardado (decidir_datos).
    reextraida: Documento = {
        "id": "EODI-2026-00582",
        "lugar": {"nivel": "region", "pais": "RO", "region": "Marea Neagră",
                  "suceso": "Marea Neagră"},
        "fuentes": [{"id": "g1", "enlace": "https://ziare.com/drone/doborate-piloti-romani-2042065"}],
        "tiempo": {"inicio": {"valor": "2026-10-17T08:45Z", "precision": "aproximada"}},
    }  # fmt: skip
    lugar = decidir.decidir_datos(reextraida)["lugar"]
    assert (lugar["nivel"], lugar["localidad"]) == ("localidad", "Sulina")
    assert lugar["punto"] == {"lat": 45.15564, "lon": 29.65403}
    # Y la auditoría M no la marca.
    from proceso import auditoria_fichas

    assert not auditoria_fichas._m({**reextraida, "lugar": lugar})


def test_los_danos_revisados_cuentan_los_buques() -> None:
    # Mar Negro, noche del 12 al 13 de octubre de 2026: dos mercantes alcanzados, uno hundido. El
    # esquema no tiene un campo de buques; la frase de los daños los cuenta.
    ficha = {
        "id": "EODI-2026-00512",
        "lugar": {"pais": "BG"},
        "fuentes": [],
        "consecuencias": {"cierre": {"valor": "desconocido"}},
    }
    danos = decidir.decidir_datos(ficha)["consecuencias"]
    assert danos["cierre"] == {"valor": "desconocido"}
    assert danos["danos"]["nivel"] == "graves"
    assert "zwei Frachtschiffe" in danos["danos"]["frase"]
    otra = {**ficha, "id": "EODI-2026-00489"}
    assert "danos" not in decidir.decidir_datos(otra)["consecuencias"]
