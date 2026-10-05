"""Atribución de un incidente (proceso/atribucion.py), con la regla estricta: en la extracción,
en el proceso, en la validación y en la corrección de lo guardado (recogida/tipo_atribucion.py).

Las frases de los casos guardados son las de las declaraciones reales de la base: Chisináu
(noviembre de 2025 y septiembre de 2026), el aeropuerto rumano del 8 de septiembre de 2026, donde
el autor guardado era el propio prefecto, y el dron hallado junto a una base aérea alemana, donde
la fiscalía federal examina una posible relación con Leipzig.
"""

import copy
import json
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from almacen.base import Almacen
from esquema import Documento
from modelo import ficha
from proceso import atribucion
from proceso.atribucion import ACTOR_SIN_NOMBRE, Motivo, evaluar
from proceso.estados import errores_historial
from proceso.validaciones import validar_incidente
from recogida import tipo_atribucion
from tests import ejemplos
from tests.test_declaraciones import aplicar, declaracion
from tests.test_extraccion import AHORA, MODELOS

# Después de las fechas del ejemplo completo (octubre de 2025).
DESPUES = datetime(2026, 10, 4, 12, tzinfo=UTC)
CONFIRMA = ("drones", "Vi kan bekræfte, at der i aften er observeret droner")
LITERAL: dict[str, Any] = {"literal": True}


# --- Los cuatro casos guardados ----------------------------------------------------------


def test_chisinau_2025_la_noticia_cuenta_la_acusacion_sin_palabras_de_la_presidenta() -> None:
    frase = "Prezydent Maia Sandu oskarżyła Moskwę o próbę destabilizacji."
    decision = evaluar("Rusia", frase, declarantes=["Președintele Maia Sandu"])
    assert decision.clase is None and decision.motivo is Motivo.NO_LITERAL


def test_chisinau_2026_la_noticia_cuenta_que_las_autoridades_lo_llamaron_ruso() -> None:
    frase = "Молдавские власти сразу назвали аппарат «российским»"
    decision = evaluar("Rusia", frase, declarantes=["Autoritățile moldave"])
    assert decision.clase is None and decision.motivo is Motivo.NO_LITERAL


def test_aeropuerto_rumano_el_autor_guardado_es_el_propio_prefecto() -> None:
    frase = "The drone entered Romanian territory from the Republic of Moldova"
    assert atribucion.clasificar("Constantin Dolachi-Pelin", frase) is None
    # Aunque la frase fuese literal: no nombra a nadie como autor y no hay detención.
    decision = evaluar("Constantin Dolachi-Pelin", frase, "persona", "RO", **LITERAL)
    assert decision.clase is None and decision.motivo is Motivo.PERSONA


def test_base_aerea_alemana_examinar_una_posible_relacion_no_es_atribuir() -> None:
    fiscalia = (
        "prüft die Bundesanwaltschaft einen möglichen Zusammenhang mit dem Drohnenvorfall "
        "am Flughafen Leipzig"
    )
    assert evaluar("Russland", fiscalia, "estado", "RU", **LITERAL).motivo is Motivo.INVESTIGACION
    gobierno = "die Bundesregierung von einem russischen Anschlagsversuch ausging"
    decision = evaluar("Russland", gobierno, "estado", "RU", **LITERAL)
    assert decision.clase is None and decision.motivo is Motivo.DUDA


# --- Lo que no vale, en los idiomas de las fuentes -------------------------------------

NO_VALE = {
    "de": [
        "Die Bundesanwaltschaft ermittelt wegen des Drohnenflugs.",
        "Es wird geprüft, ob Russland hinter dem Vorfall steckt.",
        "Ein Zusammenhang mit Russland wird nicht ausgeschlossen.",
        "Russland könnte hinter dem Vorfall stecken.",
        "Es besteht der Verdacht, dass Russland verantwortlich ist.",
        "Vieles deutet auf Russland hin.",
        "Laut Sicherheitskreisen steckt Russland dahinter.",
    ],
    "ro": [
        "Autoritățile investighează originea dronei rusești.",
        "Nu este exclus ca drona să fie rusească.",
        "Drona ar putea fi rusească.",
        "Există suspiciuni că Rusia este responsabilă.",
        "Totul indică faptul că Rusia este responsabilă.",
        "Potrivit unor surse din securitate, drona era rusească.",
    ],
    "en": [
        "Police are investigating whether Russia was behind the flight.",
        "The ministry is examining a possible link to Russia.",
        "Officials do not rule out Russian involvement.",
        "The drone could be Russian.",
        "Russia is suspected of being behind the incident.",
        "Everything points to Russia.",
        "Security sources believe Russia is responsible.",
    ],
    "fr": [
        "Le parquet a ouvert une enquête sur ce drone russe.",
        "Le gouvernement n'exclut pas une piste russe.",
        "Le drone pourrait être russe.",
        "La Russie est soupçonnée d'être derrière l'incident.",
        "Tout indique que la Russie est responsable.",
    ],
    "pl": [
        "Prokuratura prowadzi śledztwo w sprawie rosyjskiego drona.",
        "Rząd nie wyklucza, że to rosyjski dron.",
        "To mógł być rosyjski dron.",
        "Podejrzewa się, że za incydentem stoi Rosja.",
        "Wszystko wskazuje na to, że to Rosja.",
    ],
    "lt": [
        "Policija tiria, ar dronas buvo rusiškas.",
        "Neatmetama, kad dronas atskrido iš Rusijos.",
        "Įtariama, kad už incidento stovi Rusija.",
        "Tikriausiai dronas atskrido iš Rusijos.",
    ],
    "nl": [
        "Het Openbaar Ministerie onderzoekt of Rusland erachter zit.",
        "Rusland zou erachter kunnen zitten.",
        "Er wordt vermoed dat Rusland verantwoordelijk is.",
        "Alles wijst op Rusland.",
        "Volgens bronnen zit Rusland erachter.",
    ],
    "uk": [
        "Поліція розслідує, чи був дрон російським.",
        "Не виключено, що дрон був російським.",
        "Дрон міг бути російським.",
        "Ймовірно, за інцидентом стоїть Росія.",
    ],
    "ru": [
        "Прокуратура проверяет, был ли беспилотник российским.",
        "Не исключено, что дрон был российским.",
        "Беспилотник мог быть российским.",
        "Предположительно, за инцидентом стоит Россия.",
        "По данным источников, дрон был российским.",
    ],
}


@pytest.mark.parametrize(
    ("idioma", "frase"), [(idioma, frase) for idioma, frases in NO_VALE.items() for frase in frases]
)
def test_lo_que_no_vale_no_atribuye_aunque_sea_literal(idioma: str, frase: str) -> None:
    decision = evaluar("Rusia", frase, "estado", "RU", **LITERAL)
    assert decision.clase is None, (idioma, frase)
    assert decision.motivo in {Motivo.INVESTIGACION, Motivo.DUDA}, (idioma, frase)


VALE = [
    "Rusia es responsable del ataque con drones contra el aeropuerto.",
    "It was a Russian drone.",
    "Die Bundesregierung macht Russland für den Angriff verantwortlich.",
    "Drona care a survolat aeroportul a fost o dronă rusească.",
    "To był rosyjski dron.",
]


@pytest.mark.parametrize("frase", VALE)
def test_una_afirmacion_expresa_y_literal_atribuye(frase: str) -> None:
    clase = evaluar("Rusia", frase, "estado", "RU", **LITERAL).clase
    assert clase == {"tipo": "estado", "pais": "RU"}


def test_sin_palabras_literales_de_la_autoridad_no_hay_atribucion() -> None:
    frase = "Rusia es responsable del ataque con drones contra el aeropuerto."
    assert evaluar("Rusia", frase, "estado", "RU").motivo is Motivo.NO_LITERAL
    assert evaluar("Rusia", frase, "estado", "RU", literal=False).motivo is Motivo.NO_LITERAL


def test_el_autor_nunca_es_la_autoridad_que_declara() -> None:
    frase = "El ministro Ion Popescu ha sido acusado por la fiscalía del vuelo del dron"
    decision = evaluar(
        "Ion Popescu", frase, "persona", None, literal=True, situacion="acusada",
        declarantes=["Ministrul Ion Popescu"],
    )  # fmt: skip
    assert decision.motivo is Motivo.DECLARANTE


# --- Personas ---------------------------------------------------------------------------


def test_una_persona_solo_si_la_autoridad_la_ha_detenido_acusado_o_condenado() -> None:
    frase = "La Fiscalía acusa a Ion Popescu, ciudadano ruso, de pilotar el dron"
    assert evaluar("Ion Popescu", frase, "persona", "RU", **LITERAL).motivo is Motivo.PERSONA
    clase = evaluar("Ion Popescu", frase, "persona", "RU", literal=True, situacion="acusada").clase
    assert clase == {"tipo": "persona", "pais": "RU"}


def test_si_la_autoridad_no_da_el_nombre_es_una_persona() -> None:
    frase = "La policía ha detenido a un hombre de 34 años, ciudadano ruso, por pilotar el dron"
    # La prensa da un nombre que la autoridad no dice: no se publica.
    clase = evaluar("Ivan Petrov", frase, "persona", "RU", literal=True, situacion="detenida").clase
    assert clase == {"tipo": "persona", "pais": "RU", "actor": ACTOR_SIN_NOMBRE}


def test_la_nacionalidad_solo_si_la_frase_la_dice() -> None:
    lugar = "La Fiscalía acusa a Ion Popescu, llegado desde Rusia, de pilotar el dron"
    clase = evaluar("Ion Popescu", lugar, "persona", "RU", literal=True, situacion="acusada").clase
    assert clase == {"tipo": "persona"}


# --- Reglas de la tabla -----------------------------------------------------------------


def test_palabra_entera() -> None:
    assert atribucion.menciona("un cetățean rus", "RU", solo_gentilicio=True)
    assert not atribucion.menciona("rustic drone", "RU")


def test_un_termino_ingles_no_casa_con_una_palabra_polaca() -> None:
    # «probe» (inglés) y «próbę» (polaco, normalizado «probe»): no es una investigación.
    assert atribucion.expresion_de_duda("oskarżyła Moskwę o próbę destabilizacji") is None


def test_la_tabla_cubre_las_banderas_de_la_web() -> None:
    europeos = {
        "AD", "AL", "AT", "BA", "BE", "BG", "CH", "CY", "CZ", "DE", "DK", "EE", "ES", "FI", "FR",
        "GB", "GR", "HR", "HU", "IE", "IS", "IT", "LI", "LT", "LU", "LV", "MC", "MD", "ME", "MK",
        "MT", "NL", "NO", "PL", "PT", "RO", "RS", "SE", "SI", "SK", "SM", "XK",
    }  # fmt: skip
    assert atribucion.paises() == europeos | {"RU", "BY", "UA", "TR", "VA", "IR"}


# --- La extracción y el proceso ---------------------------------------------------------


def test_la_ficha_pide_si_la_cita_es_literal_y_la_situacion_de_la_persona() -> None:
    declaraciones = ficha.ESQUEMA["properties"]["declaraciones"]["items"]
    requeridos = set(declaraciones["required"])
    assert {"autor_tipo", "autor_pais", "autor_situacion", "cita_literal"} <= requeridos
    assert declaraciones["properties"]["cita_literal"] == {"type": "boolean"}
    for texto in ("nunca si investiga", "posible", "nunca la autoridad que habla",
                  "detenida, acusada o condenada", "nunca la deduzcas del nombre"):  # fmt: skip
        assert texto in ficha.INSTRUCCIONES, texto


def test_una_autoria_literal_a_un_estado_atribuye() -> None:
    gobierno = declaracion(
        "autoria", "To była prowokacja rosyjskich dronów", "gobierno", autoridad="Premier RP",
        autor="Rusia", autor_tipo="estado", autor_pais="RU", cita_literal=True,
    )  # fmt: skip
    resultado = aplicar(declaracion(*CONFIRMA), gobierno)
    assert resultado["estado"]["actual"] == "atribuido"
    assert resultado["atribucion"]["tipo"] == "estado"
    assert resultado["atribucion"]["pais"] == "RU"


def test_la_fiscalia_que_acusa_atribuye() -> None:
    fiscalia = declaracion(
        "autoria", "Prokuratura oskarża Rosję o atak dronów na lotnisko", "fiscalia",
        autoridad="Prokuratura Krajowa", autor="Rosja", autor_tipo="estado", autor_pais="RU",
        cita_literal=True,
    )  # fmt: skip
    assert aplicar(declaracion(*CONFIRMA), fiscalia)["estado"]["actual"] == "atribuido"


def test_una_autoria_que_investiga_queda_en_confirmado_y_va_a_la_investigacion() -> None:
    fiscalia = declaracion(
        "autoria",
        "prüft die Bundesanwaltschaft einen möglichen Zusammenhang mit dem Drohnenvorfall",
        "fiscalia", autoridad="Bundesanwaltschaft", autor="Russland", autor_tipo="estado",
        autor_pais="RU", cita_literal=True,
    )  # fmt: skip
    resultado = aplicar(declaracion(*CONFIRMA), fiscalia)
    assert resultado["estado"]["actual"] == "confirmado"
    assert "atribucion" not in resultado
    [investigacion] = resultado["investigacion"]
    assert investigacion["autoridad"] == "Bundesanwaltschaft"
    assert investigacion["cita"].startswith("prüft die Bundesanwaltschaft")


def test_una_autoria_contada_por_la_prensa_no_atribuye() -> None:
    gobierno = declaracion(
        "autoria", "Prezydent Maia Sandu oskarżyła Moskwę o próbę destabilizacji.", "gobierno",
        autoridad="Președintele Maia Sandu", autor="Rusia", autor_tipo="estado", autor_pais="RU",
        cita_literal=False,
    )  # fmt: skip
    resultado = aplicar(declaracion(*CONFIRMA), gobierno)
    assert resultado["estado"]["actual"] == "confirmado"
    assert "atribucion" not in resultado


# --- La validación ----------------------------------------------------------------------


def _errores(documento: Documento) -> list[str]:
    errores = validar_incidente(documento, AHORA, MODELOS)
    return [e.mensaje for e in errores if e.ruta == "atribucion"]


def _con_frase(frase: str, **cambios: Any) -> Documento:
    documento = ejemplos.incidente_completo()
    autoridad = next(f for f in documento["fuentes"] if f["id"] == "F2")
    autoridad["frase_origen"] = frase
    documento["atribucion"] = {**documento["atribucion"], **cambios}
    return documento


def test_la_validacion_exige_el_tipo() -> None:
    documento = ejemplos.incidente_completo()
    del documento["atribucion"]["tipo"]
    assert _errores(documento) == ["atribución sin tipo de actor (estado o persona)"]


@pytest.mark.parametrize(
    "frase",
    [
        "El Gobierno investiga si Rusia está detrás del cierre",
        "El Gobierno no descarta que Rusia esté detrás del cierre",
        "Das Bundesinnenministerium prüft einen möglichen Zusammenhang mit Russland",
    ],
)
def test_la_validacion_rechaza_una_frase_con_duda_o_investigacion(frase: str) -> None:
    [error] = _errores(_con_frase(frase))
    assert error.startswith("la frase de la autoridad no afirma")


def test_la_validacion_rechaza_un_autor_que_coincide_con_quien_declara() -> None:
    documento = _con_frase(
        "El Gobierno nacional ha condenado a Ion Popescu por el vuelo",
        actor="Ion Popescu", autoridad="Ministrul Ion Popescu", tipo="persona",
    )  # fmt: skip
    documento["atribucion"].pop("pais")
    assert _errores(documento) == ["el autor (Ion Popescu) coincide con la autoridad que declara"]


def test_la_validacion_rechaza_un_pais_que_la_frase_no_dice() -> None:
    documento = ejemplos.incidente_completo()
    documento["atribucion"]["pais"] = "BY"
    assert len(_errores(documento)) == 1


def test_la_validacion_rechaza_una_nacionalidad_deducida() -> None:
    documento = _con_frase(
        "El Gobierno atribuye a Ion Popescu el vuelo sobre el aeropuerto",
        actor="Ion Popescu", tipo="persona", pais="RO",
    )  # fmt: skip
    assert len(_errores(documento)) == 1
    del documento["atribucion"]["pais"]
    assert _errores(documento) == []


def test_retirar_una_atribucion_solo_vale_con_motivo() -> None:
    documento = ejemplos.incidente_completo()
    fuentes = {f["id"]: f for f in documento["fuentes"]}
    estado = copy.deepcopy(documento["estado"])
    paso: Documento = {
        "estado": "confirmado",
        "fecha": {"valor": "2026-10-04T12:00Z", "precision": "minuto"},
        "fuente_id": "F2",
    }
    estado["historial"].append(paso)
    estado["actual"] = "confirmado"
    assert errores_historial(estado, fuentes) == ["retirada sin motivo: atribuido → confirmado"]
    paso["motivo"] = {"es": "Se retira la atribución.", "en": "Attribution withdrawn."}
    assert errores_historial(estado, fuentes) == []


# --- La corrección de lo guardado -------------------------------------------------------


def _guardado(actor: str, frase: str, id_: str = "EODI-2025-00001") -> Documento:
    """Un atribuido como los de antes de la regla estricta: sin tipo ni país."""
    documento = ejemplos.incidente_completo()
    documento["id"] = id_
    autoridad = next(f for f in documento["fuentes"] if f["id"] == "F2")
    autoridad["frase_origen"] = frase
    documento["titulo"] = {
        "es": "Drones rusos con explosivos sobre el aeropuerto",
        "en": "Russian drones with explosives over the airport",
    }
    documento["atribucion"] = {"actor": actor, "autoridad": "Gobierno",
                               "fecha": documento["atribucion"]["fecha"]}  # fmt: skip
    return documento


def _guardar_sin_validar(almacen: Almacen, documento: Documento) -> None:
    with almacen.conexion:
        almacen.conexion.execute(
            "INSERT INTO incidentes (id, tipo, estado, documento) VALUES (?, ?, ?, json(?))",
            (documento["id"], documento["tipo"], documento["estado"]["actual"],
             json.dumps(documento)),
        )  # fmt: skip


def _motivos(almacen: Almacen, id_: str) -> list[str]:
    cambios = almacen.historial(id_)
    return [c["nuevo"]["motivo"] for c in cambios if "motivo" in (c["nuevo"] or {})]


def test_la_correccion_retira_lo_guardado_sin_palabras_literales_con_su_motivo() -> None:
    almacen = Almacen.abrir()
    antes = _guardado("Rusia", "Prezydent oskarżyła Moskwę o prowokację")
    _guardar_sin_validar(almacen, antes)
    resumen = tipo_atribucion.aplicar(almacen, DESPUES, MODELOS)
    assert resumen["retirados"] == {"EODI-2025-00001": "no_literal"}
    nuevo = almacen.incidente("EODI-2025-00001")
    assert nuevo is not None
    assert nuevo["estado"]["actual"] == "confirmado"
    assert "atribucion" not in nuevo
    # El historial conserva el paso a atribuido y añade la retirada con su motivo.
    *_, atribuido, retirada = nuevo["estado"]["historial"]
    assert atribuido["estado"] == "atribuido"
    assert retirada["estado"] == "confirmado"
    assert retirada["motivo"] == tipo_atribucion.MOTIVOS[Motivo.NO_LITERAL]
    # El titular ya no dice la nacionalidad ni explosivos que ninguna autoridad dice.
    assert nuevo["titulo"] == {"es": "Drones sobre el aeropuerto", "en": "Drones over the airport"}
    assert nuevo["fuentes"] == antes["fuentes"]
    assert (
        _motivos(almacen, "EODI-2025-00001")[-1] == tipo_atribucion.MOTIVOS[Motivo.NO_LITERAL]["es"]
    )
    # Una vez por versión.
    assert tipo_atribucion.aplicar(almacen, DESPUES + timedelta(hours=1), MODELOS) == {}


def test_la_correccion_usa_el_motivo_revisado_y_deja_la_investigacion() -> None:
    almacen = Almacen.abrir()
    frase = "prüft die Bundesanwaltschaft einen möglichen Zusammenhang mit dem Drohnenvorfall"
    _guardar_sin_validar(almacen, _guardado("Russland", frase, "EODI-2026-00283"))
    resumen = tipo_atribucion.aplicar(almacen, DESPUES, MODELOS)
    assert resumen["retirados"] == {"EODI-2026-00283": "investigacion"}
    nuevo = almacen.incidente("EODI-2026-00283")
    assert nuevo is not None
    motivo = nuevo["estado"]["historial"][-1]["motivo"]
    assert motivo == tipo_atribucion.revisadas()["EODI-2026-00283"]
    assert motivo["es"].startswith(
        "Se retira la atribución: la autoridad examina una posible relación, no la afirma"
    )
    assert [i["cita"] for i in nuevo["investigacion"]] == [frase]


def test_la_correccion_devuelve_el_paso_que_la_primera_version_borro() -> None:
    almacen = Almacen.abrir()
    frase = "The drone entered Romanian territory from the Republic of Moldova"
    antes = _guardado("Constantin Dolachi-Pelin", frase, "EODI-2026-00015")
    _guardar_sin_validar(almacen, antes)
    # La primera versión dejó el incidente confirmado, sin el paso a atribuido.
    borrado = copy.deepcopy(antes)
    del borrado["atribucion"]
    borrado["estado"] = {"actual": "confirmado", "historial": antes["estado"]["historial"][:-1]}
    almacen.guardar_incidente(borrado, DESPUES, MODELOS)
    tipo_atribucion.aplicar(almacen, DESPUES, MODELOS)
    nuevo = almacen.incidente("EODI-2026-00015")
    assert nuevo is not None
    assert [p["estado"] for p in nuevo["estado"]["historial"]] == [
        "notificado", "confirmado", "atribuido", "confirmado",
    ]  # fmt: skip
    retirada = nuevo["estado"]["historial"][-1]["motivo"]
    assert retirada == tipo_atribucion.revisadas()["EODI-2026-00015"]
    # El nombre del prefecto no queda como autor en ningún sitio del incidente.
    assert "Dolachi" not in json.dumps(nuevo, ensure_ascii=False)
