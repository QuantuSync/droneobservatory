"""Las autoridades y los datos de otro país (2 de noviembre de 2026).

- «Ministerul Apărării» es el Ministerio de Defensa de Moldavia y, en la prensa rumana, también el
  de Rumanía: la web lo escribía siempre como el rumano, también en las fichas de Moldavia
  (EODI-2026-00728, Viișoara). Ahora se escribe con el país que dice la declaración, el del medio
  oficial o el de la ficha (proceso/autoridades.con_pais), y la ficha rumana sigue rumana.
- Una frase que habla de otro país no fija ningún dato de la ficha: «Două drone au pătruns în
  spațiul aerian al României» le daba a 00728 dos drones, los del suceso de Iași (00719).
- La auditoría lo cuenta en la letra Y.
"""

import copy
from typing import Any

from exportacion import citas
from proceso import atribucion, auditoria_fichas, autoridades, validacion_ficha
from proceso import control_fichas as reglas
from recogida import avisos
from recogida import control_fichas as control
from tests.test_avisos import AHORA, CONFIG

# EODI-2026-00728, tal como la guarda la base el 2 de noviembre (fuentes leídas en timpul.md).
FRASE_728 = (
    "Ministerul Apărării a anunțat că drona a părăsit spațiul aerian al Republicii Moldova la ora "
    "18:12, în proximitatea localității Viișoara, raionul Edineț"
)
FRASE_CLICK = "Două drone au pătruns în spațiul aerian al României"


def _fuente(id_: str, medio: str, frase: str, autoridad: bool = True) -> dict[str, Any]:
    return {
        "id": id_,
        "medio": medio,
        "frase_origen": frase,
        "es_autoridad": autoridad,
        "fiabilidad": "B" if autoridad else "C",
        "idioma": "ro",
        "enlace": "https://www.timpul.md/articol/drona",
        "publica": True,
        "fecha": {"valor": "2026-10-31T16:30Z", "precision": "minuto"},
    }


def ficha_728() -> dict[str, Any]:
    return {
        "id": "EODI-2026-00728",
        "tipo": "sobrevuelo",
        "estado": {"actual": "confirmado", "historial": []},
        "presencia_dron": "confirmada",
        "titulo": {
            "es": "Dron sobrevuela el espacio aéreo del norte de Moldavia cerca de Viișoara",
            "en": "Drone overflies northern Moldova airspace near Viișoara",
        },
        "tiempo": {"inicio": {"valor": "2026-10-31T15:50Z", "precision": "minuto"}},
        "lugar": {
            "pais": "MD",
            "localidad": "Viișoara",
            "region": "Edineț",
            "nivel": "localidad",
            "suceso": "Viișoara",
            "radio_km": 3.0,
            "punto": {"lat": 48.09527, "lon": 27.04498},
        },
        "drones": {"numero": {"min": 1, "max": 1}},
        "consecuencias": {"cierre": {"valor": "desconocido"}},
        "pruebas": {"dron_estatal": True, "entrada_exterior": True, "evidencia": []},
        "fuentes": [
            _fuente(
                "gdelt-6d7a568da0829a3b",
                "timpul.md",
                "Cea de-a doua dronă care a pătruns "
                "neautorizat în spațiul aerian al Republicii Moldova",
                False,
            ),
            _fuente(
                "revisada-bf38ca0a3f505197-declaracion-1",
                "Ministerul Apărării (declaración oficial citada en timpul.md)",
                FRASE_728,
            ),
            _fuente("gdelt-18581caa2e93781d", "click.ro", FRASE_CLICK, False),
        ],
    }


def ficha_rumana() -> dict[str, Any]:
    """EODI-2025-00241 (Tulcea y Galați): «Ministerul Apărării Naționale», citada en jurnalul.ro."""
    return {
        "id": "EODI-2025-00241",
        "lugar": {"pais": "RO", "region": "Tulcea", "nivel": "region"},
        "fuentes": [
            _fuente(
                "revisada-953c98a011f89a92-declaracion-1",
                "Ministerul Apărării Naționale (declaración oficial citada en jurnalul.ro)",
                "Două drone au păstruns în spațiul aerian românesc, una în județul Tulcea "
                "și una în Galați, a anunțat marți dimineața Ministerul Apărării Naționale.",
            )
        ],
    }


# --- Autoridades --------------------------------------------------------------------------------
def test_00728_escribe_el_ministerio_de_moldavia() -> None:
    doc = autoridades.con_pais(ficha_728())
    medio = doc["fuentes"][1]["medio"]
    assert medio == "Ministerul Apărării (MD) (declaración oficial citada en timpul.md)"
    assert autoridades.de_la_fuente(medio, "es") == (
        "el Ministerio de Defensa de Moldavia (Ministerul Apărării)"
    )
    assert autoridades.de_la_fuente(medio, "en") == (
        "the Moldovan Ministry of Defence (Ministerul Apărării)"
    )
    assert "Rumanía" not in autoridades.de_la_fuente(medio, "es")


def test_la_ficha_rumana_sigue_rumana() -> None:
    doc = autoridades.con_pais(ficha_rumana())
    medio = doc["fuentes"][0]["medio"]
    assert medio == "Ministerul Apărării Naționale (declaración oficial citada en jurnalul.ro)"
    assert autoridades.de_la_fuente(medio, "es") == (
        "el Ministerio de Defensa Nacional de Rumanía (Ministerul Apărării Naționale)"
    )
    # «Ministerul Apărării» suelto en una ficha rumana es el rumano.
    ro = ficha_rumana()
    ro["fuentes"][0]["medio"] = "Ministerul Apărării (declaración oficial citada en digi24.ro)"
    ro["fuentes"][0]["frase_origen"] = "o dronă a intrat în spațiul aerian al României"
    medio = autoridades.con_pais(ro)["fuentes"][0]["medio"]
    assert autoridades.de_la_fuente(medio, "es") == (
        "el Ministerio de Defensa Nacional de Rumanía (Ministerul Apărării)"
    )


def test_la_declaracion_que_dice_su_pais_manda_sobre_la_ficha() -> None:
    # La ficha es de Moldavia, pero la frase dice «MApN»: es el ministerio rumano (EODI-2026-00313).
    doc = ficha_728()
    doc["fuentes"][1]["frase_origen"] = (
        "Sistemul de supraveghere radar al MApN a detectat, luni, o țintă aeriană la est de Sulina"
    )
    assert autoridades.con_pais(doc)["fuentes"][1]["medio"].startswith("Ministerul Apărării (RO)")
    assert (
        autoridades.pais_de(
            "Ministerul Apărării", "Ministerul Apărării de la Chișinău a anunțat", "x", "RO"
        )
        == "RO"
    )
    assert (
        autoridades.pais_de(
            "Ministerul Apărării", "al Ministerului Apărării al Republicii Moldova", "x", "RO"
        )
        == "MD"
    )


def test_el_medio_oficial_da_el_pais() -> None:
    # «Forsvaret» de configuracion/fuentes_oficiales.json es el danés, aunque la ficha sea noruega.
    assert autoridades.pais_de("Forsvaret", "", "Forsvaret", "NO") == "DK"
    assert autoridades.pais_de("Forsvaret", "", "nrk.no", "NO") == "NO"


def test_sin_pais_de_la_lista_el_nombre_neutro() -> None:
    doc = ficha_728()
    doc["lugar"]["pais"] = "UA"
    medio = autoridades.con_pais(doc)["fuentes"][1]["medio"]
    assert medio.startswith("Ministerul Apărării (declaración")
    assert autoridades.de_la_fuente(medio, "es") == "el Ministerio de Defensa (Ministerul Apărării)"


def test_con_pais_no_cambia_dos_veces() -> None:
    una = autoridades.con_pais(ficha_728())
    assert autoridades.con_pais(copy.deepcopy(una)) == una


def test_la_exportacion_publica_el_nombre_con_su_pais() -> None:
    publico = ficha_728()
    citas.con_traducciones(publico, {})
    assert publico["fuentes"][1]["medio"].startswith("Ministerul Apărării (MD)")
    # Está en la tabla: no se manda a traducir.
    assert "Ministerul Apărării (MD)" not in (publico.get("autoridades") or {})


def test_el_aviso_escribe_el_ministerio_de_moldavia() -> None:
    doc = ficha_728()
    doc["tiempo"] = {"inicio": {"valor": "2026-10-10T08:04Z", "precision": "minuto"}}
    for f in doc["fuentes"]:
        f["fecha"] = {"valor": "2026-10-10T08:30Z", "precision": "minuto"}
    doc["fuentes"] = [doc["fuentes"][1]]
    aviso = avisos.clasificar(doc, CONFIG, AHORA)
    assert aviso is not None
    texto = str(avisos.mensaje(aviso, doc, CONFIG, "drones-moldova")["message"])
    assert "el Ministerio de Defensa de Moldavia (Ministerul Apărării)" in texto
    assert "the Moldovan Ministry of Defence (Ministerul Apărării)" in texto
    assert "Rumanía" not in texto and "Romanian" not in texto
    # El documento interno no se toca.
    assert doc["fuentes"][0]["medio"].startswith("Ministerul Apărării (declaración")


def test_las_corregidas_que_senalo_la_auditoria() -> None:
    assert autoridades.escrita("Torkild Fogde, National Police Chief", "es") == (
        "el jefe de la Policía Nacional de Dinamarca, Thorkild Fogde"
    )
    assert autoridades.pais_escrito("Royal Gibraltar Police") == "GB"
    assert (
        autoridades.pais_de(
            "Luftfartsvæsnet", "Luftrummet over Landvetter er lukket", "bt.dk", "SE"
        )
        == "SE"
    )
    assert (
        autoridades.pais_de(
            "Innenriksdepartementet", "Innenriksminister Kimmo Kohvakka sier", "nrk.no", "FI"
        )
        == "FI"
    )


def test_cada_nombre_de_varios_paises_tiene_su_entrada_suelta() -> None:
    for nombre, paises in autoridades.por_pais().items():
        suelta = autoridades._datos()["autoridades"][nombre]
        # Los rumanos no nombran país sueltos: Rumanía y Moldavia los escriben igual.
        if "RO" in paises or "MD" in paises:
            assert "pais" not in suelta, nombre
        assert len(paises) >= 2, nombre
        for pais, entrada in paises.items():
            assert entrada["es"] and entrada["en"], (nombre, pais)
            assert autoridades.pais_escrito(f"{nombre} ({pais})") == pais


# --- Datos de otro país -------------------------------------------------------------------------
def test_una_frase_de_rumania_no_es_de_moldavia() -> None:
    assert atribucion.de_otro_pais(FRASE_CLICK, "MD") == "RO"
    assert (
        atribucion.de_otro_pais(
            "după ce două drone venite dinspre Republica Moldova au pătruns în spațiul aerian al "
            "României",
            "MD",
        )
        == "RO"
    )
    assert atribucion.de_otro_pais(FRASE_728, "MD") is None
    assert atribucion.de_otro_pais(FRASE_CLICK, "RO") is None
    # Ni el país de donde viene el dron ni de quién es algo sacan la frase de la ficha.
    assert (
        atribucion.de_otro_pais("drona a intrat din Ucraina în spațiul aerian național", "MD")
        is None
    )
    assert atribucion.de_otro_pais("spadł obiekt należący do wojsk norweskich", "PL") is None
    assert atribucion.de_otro_pais("Nava sub pavilion maltez a fost atacată", "BG") is None
    assert atribucion.de_otro_pais("all'aeroporto di Monaco di Baviera", "DE") is None
    assert atribucion.de_otro_pais("Two drones violated Romanian airspace", "MD") == "RO"


def _verificacion_728() -> dict[str, Any]:
    """La verificación de 00728 de las 06:17 del 2 de noviembre."""
    return {
        "datos": {
            "drones": [
                {"max": 2, "min": 2},
                "gdelt-18581caa2e93781d",
                "după ce două drone venite dinspre Republica Moldova au pătruns în "
                "spațiul aerian al României",
            ],
            "lugar": [
                {"nivel": "localidad", "nombre": "Viișoara"},
                "gdelt-6d7a568da0829a3b",
                "a părăsit teritoriul aerian al țării la ora 18:12, în apropierea "
                "localității Viișoara, raionul Edineț",
            ],
            "presencia": [
                "confirmada",
                "gdelt-6d7a568da0829a3b",
                "cea de-a doua dronă a pătruns în spațiul aerian național la ora 17:50",
            ],
        },
        "huella": "7b7ffa06954c3dcd",
    }


def test_el_control_no_fija_los_drones_de_rumania_en_00728() -> None:
    vigente = control._verificada_vigente(_verificacion_728(), ficha_728())
    assert vigente.valor("drones") is None
    assert vigente.valor("lugar") == {"nivel": "localidad", "nombre": "Viișoara"}
    assert vigente.valor("presencia") == "confirmada"
    corregida = reglas.aplicar(ficha_728(), vigente, False, None)
    assert corregida.incidente["drones"]["numero"] == {"min": 1, "max": 1}


def test_la_extraccion_no_toma_un_dato_de_otro_pais() -> None:
    validada = validacion_ficha.Validada(titulo_es="t", titulo_en="t")
    validada.campos = {
        "pais": {"valor": "MD", "fuente": 1, "frase": "Republicii Moldova", "confianza": 1.0},
        "drones": {
            "valor": {"min": 2, "max": 2},
            "fuente": 2,
            "frase": FRASE_CLICK,
            "confianza": 0.9,
        },
        "localidad": {"valor": "Viișoara", "fuente": 1, "frase": FRASE_728, "confianza": 0.9},
    }
    validacion_ficha._sin_otro_pais(validada)
    assert "drones" not in validada.campos
    assert "localidad" in validada.campos
    assert "drones: la frase habla de otro país (RO)" in validada.motivos


# --- Auditoría, letra Y -------------------------------------------------------------------------
def test_la_auditoria_cuenta_autoridad_y_dato_de_otro_pais() -> None:
    assert auditoria_fichas.de_otro_pais(ficha_728(), _verificacion_728()) == []
    # Con los dos drones de Rumanía en la ficha, cuenta el dato.
    con_dos = ficha_728()
    con_dos["drones"] = {"numero": {"min": 2, "max": 2}}
    assert auditoria_fichas.de_otro_pais(con_dos, _verificacion_728()) == ["drones"]
    # Una autoridad rumana en una ficha de Moldavia sin frase que nombre Rumanía.
    mala = ficha_728()
    mala["fuentes"][1]["medio"] = (
        "Ministerul Apărării Naționale (declaración oficial citada en timpul.md)"
    )
    assert auditoria_fichas.de_otro_pais(mala) == ["autoridad Ministerul Apărării Naționale"]
    # La misma con una frase que nombra Rumanía, justificada.
    mala["fuentes"][1]["frase_origen"] = "drona a intrat apoi în spațiul aerian al României"
    assert auditoria_fichas.de_otro_pais(mala) == []
    resultado = auditoria_fichas.auditar(
        [con_dos], verificaciones={con_dos["id"]: _verificacion_728()}
    )
    assert resultado["Y"] == ["EODI-2026-00728 drones"]


def test_el_trayecto_por_otro_pais_no_hace_la_frase_de_otro_pais() -> None:
    # EODI-2026-00277 (Rumanía): la Y la marcaba por el paso del dron por Moldavia (4/11/2026).
    from proceso import atribucion

    trayecto = (
        "Potrivit unui comunicat de presă emis de MApN, drona a traversat spațiul aerian al "
        "Ucrainei și al Republicii Moldova"
    )
    assert atribucion.de_otro_pais(trayecto, "RO") is None
    # Pasar por el país de la ficha es estar en él: la frase sigue siendo de Moldavia.
    moldavia = (
        "O dronă Shahed a traversat spațiul aerian al Republicii Moldova. A venit din Ucraina și "
        "a zburat spre România"
    )
    assert atribucion.de_otro_pais(moldavia, "MD") is None
    # Entrar en otro país sí es de otro país.
    assert (
        atribucion.de_otro_pais("Două drone au pătruns în spațiul aerian al României", "MD") == "RO"
    )


def test_la_puerta_quita_la_autoridad_de_otro_pais_sin_cita() -> None:
    # Desde el 14 de noviembre de 2026 la letra Y se corrige (recogida/control_fichas
    # .sin_autoridades_de_otro_pais): la declaración rumana sin frase que nombre Rumanía en una
    # ficha de Moldavia deja de ser oficial y la auditoría no la cuenta.
    from recogida import control_fichas

    mala = ficha_728()
    mala["fuentes"][1]["medio"] = (
        "Ministerul Apărării Naționale (declaración oficial citada en timpul.md)"
    )
    mala["fuentes"][1]["id"] = "revisada-prueba-declaracion-1"
    mala["fuentes"][1].update(es_autoridad=True, publica=True)
    instante = {"valor": "2026-11-14T10:17Z", "precision": "minuto"}
    mala["estado"]["historial"] = [
        {"estado": "notificado", "fecha": instante, "fuente_id": "gdelt-6d7a568da0829a3b"},
        {"estado": "confirmado", "fecha": instante, "fuente_id": "revisada-prueba-declaracion-1"},
    ]
    nueva, cambios = control_fichas.sin_autoridades_de_otro_pais(mala, instante)
    assert cambios and cambios[0].startswith("autoridad de otro país sin cita (Y)")
    assert nueva["fuentes"][1]["es_autoridad"] is False
    assert auditoria_fichas.de_otro_pais(nueva) == []
    # La de su país, o la de otro con su cita, se queda como estaba.
    assert control_fichas.sin_autoridades_de_otro_pais(ficha_728(), instante) == (ficha_728(), [])
