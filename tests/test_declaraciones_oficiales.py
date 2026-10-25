"""Declaraciones leídas en la página oficial de la autoridad (recogida/declaraciones_oficiales.py)
y titulares de acuerdo con el estado.

Las frases de configuracion/declaraciones_oficiales.json se comprueban contra sus copias y contra
la regla de atribución de siempre; el lector se prueba con el incidente de ejemplo (Copenhague)."""

import json
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest

from almacen.base import Almacen
from esquema import Documento
from proceso import atribucion, declaraciones
from proceso.validaciones import validar_incidente
from recogida import declaraciones_oficiales as oficiales
from tests.test_extraccion import AHORA, MODELOS, extraer_ejemplo

DESPUES = AHORA + timedelta(hours=1)
ENLACE = "https://politi.dk/koebenhavns-politi/nyhedsliste/droner-over-lufthavnen"
COPIA = [
    "Københavns Politi kan nu bekræfte, at dronerne over Københavns Lufthavn blev styret fra "
    "Rusland.",
    "The police continue to investigate the case together with PET.",
]
GOBIERNOS_SIN_ATRIBUCION = [
    # Polonia, 11 de septiembre de 2025: «Fakty wskazują» (los hechos indican) es una expresión de
    # duda de la regla; la otra frase de Polonia sí atribuye.
    ("Rosja", "Fakty wskazują, że odpowiedzialność spada jednoznacznie na Rosję."),
    # Ministro federal del Interior en el Bundestag, 10 de septiembre de 2026: «möglich».
    (
        "Russland",
        "Das Benennen der Täter heißt, dass im Fall Leipzig eindeutig eine Zuweisung an Russland "
        "möglich und notwendig war.",
    ),
    # Constanza, 5 de junio de 2026: evaluaciones preliminares, una hipótesis.
    (
        "Rusia",
        "Evaluările preliminare indică ipoteza unei drone controlate de Federa\u021bia Rus\u0103.",
    ),
]


def _entrada(**cambios: Any) -> Documento:
    return {
        "id": "dk-politi-2025-09-23-autoria", "incidente": "", "copia": "dk-politi",
        "fecha": "2025-09-23T10:00Z", "precision": "minuto", "idioma": "da",
        "autoridad": "Københavns Politi", "pais": "DK", "categoria": "policia",
        "afirma": "autoria", "autor": "Rusland", "autor_tipo": "estado", "autor_pais": "RU",
        "cita_literal": True,
        "frase": "Københavns Politi kan nu bekræfte, at dronerne over Københavns Lufthavn blev "
                 "styret fra Rusland.",
        **cambios,
    }  # fmt: skip


@pytest.fixture
def carpeta(tmp_path: Path) -> Path:
    copia = {"enlace": ENLACE, "editor": "Københavns Politi", "publicado": "2025-09-23",
             "copiado": "2025-09-24", "nota": "", "texto": COPIA}  # fmt: skip
    (tmp_path / "dk-politi.json").write_text(json.dumps(copia), encoding="utf-8")
    oficiales.copia.cache_clear()
    return tmp_path


def _confirma(id_: str) -> Documento:
    """La misma autoridad, en la misma página, afirma los drones: el incidente queda confirmado."""
    entrada = _entrada(
        id="dk-politi-2025-09-23-droner", incidente=id_, afirma="drones",
        frase="Københavns Politi kan nu bekræfte, at dronerne over Københavns Lufthavn blev "
              "styret fra Rusland.",
    )  # fmt: skip
    for clave in ("autor", "autor_tipo", "autor_pais"):
        entrada.pop(clave)
    return entrada


def _almacen() -> tuple[Almacen, str]:
    almacen = Almacen.abrir()
    id_ = extraer_ejemplo(almacen)
    assert id_ is not None
    return almacen, str(id_)


def _incidente(almacen: Almacen, id_: str) -> Documento:
    documento = almacen.incidente(id_)
    assert documento is not None
    return documento


# --- Las declaraciones del fichero --------------------------------------------------------


@pytest.mark.parametrize("entrada", oficiales.cargar(), ids=lambda e: e["id"])
def test_cada_frase_esta_literalmente_en_su_copia_fechada(entrada: Documento) -> None:
    assert oficiales.literal(entrada)
    copia = oficiales.copia(entrada["copia"])
    assert copia["enlace"].startswith("https://")
    assert copia["copiado"] >= copia["publicado"]
    assert len(entrada["frase"].split()) <= declaraciones.MAX_PALABRAS_FRASE


@pytest.mark.parametrize(
    "entrada", [e for e in oficiales.cargar() if e["afirma"] == "autoria"], ids=lambda e: e["id"]
)
def test_cada_autoria_del_fichero_pasa_la_regla_de_siempre(entrada: Documento) -> None:
    decision = atribucion.evaluar(
        entrada["autor"], entrada["frase"], entrada["autor_tipo"], entrada["autor_pais"],
        literal=entrada["cita_literal"], declarantes=[entrada["autoridad"]],
    )  # fmt: skip
    assert decision.clase == {"tipo": "estado", "pais": "RU"}
    assert entrada["categoria"] in atribucion.CATEGORIAS
    assert "citada_en" not in entrada


def test_las_citadas_en_prensa_nunca_atribuyen() -> None:
    for entrada in oficiales.cargar():
        if "citada_en" in entrada:
            assert entrada["afirma"] != "autoria"
            assert entrada["cita_literal"] is False


@pytest.mark.parametrize(("autor", "frase"), GOBIERNOS_SIN_ATRIBUCION)
def test_las_frases_con_duda_de_esos_mismos_gobiernos_no_atribuyen(autor: str, frase: str) -> None:
    assert atribucion.evaluar(autor, frase, "estado", "RU", literal=True).clase is None


def test_el_nombre_oficial_de_rusia_en_rumano_y_en_sueco() -> None:
    assert atribucion.menciona("îi aparține Federației Ruse", "RU")
    assert atribucion.estado_nombrado("Federa\u021bia Rus\u0103") == "RU"
    assert atribucion.estado_nombrado("Ryssland") == "RU"
    assert atribucion.menciona("en rysk drönare", "RU")
    assert atribucion.menciona("ett ryskt signalspaningsfartyg", "RU")


def test_la_duda_en_sueco_no_atribuye() -> None:
    frase = "Försvarsmakten utesluter inte att drönaren kan ha varit rysk."
    assert atribucion.evaluar("Ryssland", frase, "estado", "RU", literal=True).clase is None
    assert atribucion.es_investigacion("Försvarsmakten utreder händelsen.")


# --- El lector ------------------------------------------------------------------------------


def test_una_autoria_literal_en_la_pagina_oficial_atribuye_con_su_paso_y_su_fuente(
    carpeta: Path,
) -> None:
    almacen, id_ = _almacen()
    antes = _incidente(almacen, id_)
    assert antes["estado"]["actual"] == "notificado"
    entradas = (_confirma(id_), _entrada(incidente=id_))
    resumen = oficiales.aplicar(almacen, DESPUES, MODELOS, entradas, carpeta)
    assert resumen.atribuidos == [id_]
    nuevo = _incidente(almacen, id_)
    assert validar_incidente(nuevo, DESPUES, MODELOS) == []
    assert nuevo["estado"]["actual"] == "atribuido"
    assert nuevo["atribucion"] == {
        "actor": "Rusland", "autoridad": "Københavns Politi",
        "fecha": {"valor": "2025-09-23T10:00Z", "precision": "minuto"},
        "tipo": "estado", "pais": "RU",
    }  # fmt: skip
    # Primero confirma y después atribuye, cada paso con su fuente.
    *_, confirmado, paso = nuevo["estado"]["historial"]
    assert confirmado["estado"] == "confirmado"
    assert confirmado["fuente_id"] == "oficial-dk-politi-2025-09-23-droner"
    assert paso["estado"] == "atribuido"
    fuente = next(f for f in nuevo["fuentes"] if f["id"] == paso["fuente_id"])
    assert fuente["enlace"] == ENLACE
    assert fuente["medio"] == "Københavns Politi"
    assert fuente["fiabilidad"] == "A"
    assert fuente["idioma"] == "da"
    assert fuente["frase_origen"] == _entrada()["frase"]
    # Las fuentes anteriores no cambian y el cambio queda anotado con su motivo.
    assert nuevo["fuentes"][: len(antes["fuentes"])] == antes["fuentes"]
    motivos = [c["nuevo"].get("motivo") for c in almacen.historial(id_) if c["nuevo"]]
    assert oficiales.MOTIVO in motivos
    # Ya aplicada, la siguiente recogida no cambia nada.
    otra = oficiales.aplicar(almacen, DESPUES + timedelta(hours=1), MODELOS, entradas, carpeta)
    assert otra.aplicadas == []
    assert _incidente(almacen, id_) == nuevo


def test_lo_que_la_autoridad_investiga_va_a_la_ficha_sin_cambiar_el_estado(carpeta: Path) -> None:
    almacen, id_ = _almacen()
    entrada = _entrada(
        id="dk-politi-2025-09-23-efterforskning", incidente=id_, afirma="incidente",
        frase="The police continue to investigate the case together with PET.",
    )  # fmt: skip
    for clave in ("autor", "autor_tipo", "autor_pais"):
        entrada.pop(clave)
    oficiales.aplicar(almacen, DESPUES, MODELOS, (entrada,), carpeta)
    nuevo = _incidente(almacen, id_)
    assert nuevo["estado"]["actual"] == "confirmado"
    assert [i["cita"] for i in nuevo["investigacion"]] == [entrada["frase"]]


def test_una_frase_que_no_esta_en_la_copia_no_se_aplica(carpeta: Path) -> None:
    almacen, id_ = _almacen()
    antes = _incidente(almacen, id_)
    entrada = _entrada(incidente=id_, frase="Rusland står bag dronerne over lufthavnen.")
    resumen = oficiales.aplicar(almacen, DESPUES, MODELOS, (entrada,), carpeta)
    assert resumen.sin_frase == [entrada["id"]]
    assert _incidente(almacen, id_) == antes


def test_una_autoridad_de_otro_pais_no_cambia_el_incidente(carpeta: Path) -> None:
    almacen, id_ = _almacen()
    antes = _incidente(almacen, id_)
    oficiales.aplicar(almacen, DESPUES, MODELOS, (_entrada(incidente=id_, pais="SE"),), carpeta)
    assert _incidente(almacen, id_) == antes


def test_una_cita_de_prensa_no_atribuye_y_lleva_la_marca_de_declaracion_citada(
    carpeta: Path,
) -> None:
    almacen, id_ = _almacen()
    entrada = _entrada(incidente=id_, citada_en="dr.dk", cita_literal=False)
    oficiales.aplicar(almacen, DESPUES, MODELOS, (_confirma(id_), entrada), carpeta)
    nuevo = _incidente(almacen, id_)
    assert nuevo["estado"]["actual"] == "confirmado"
    assert "atribucion" not in nuevo
    fuente = nuevo["fuentes"][-1]
    assert fuente["id"].endswith(oficiales.MARCA_CITADA)
    assert fuente["medio"] == "Københavns Politi (declaración oficial citada en dr.dk)"
    assert fuente["fiabilidad"] == "B"


def test_se_aplica_al_incidente_en_que_esta_fundido(carpeta: Path) -> None:
    almacen, id_ = _almacen()
    fundido = {**_incidente(almacen, id_), "id": "EODI-2025-00999", "fusionado_en": id_}
    fundido.pop("episodio", None)
    almacen.guardar_incidente(fundido, DESPUES, MODELOS)
    entradas = (_confirma("EODI-2025-00999"), _entrada(incidente="EODI-2025-00999"))
    oficiales.aplicar(almacen, DESPUES, MODELOS, entradas, carpeta)
    assert _incidente(almacen, id_)["estado"]["actual"] == "atribuido"
    assert "atribucion" not in _incidente(almacen, "EODI-2025-00999")


def test_una_union_de_antes_devuelve_la_confirmacion_del_registro_unido(carpeta: Path) -> None:
    """EODI-2025-00122 (Palma, 19 de octubre de 2025): la EODI-2025-00160, confirmada por Aena, se
    unió en ella antes del 14 de octubre de 2026; la que quedó tenía la fuente y seguía
    notificada."""
    almacen, id_ = _almacen()
    oficiales.aplicar(almacen, DESPUES, MODELOS, (_confirma(id_),), carpeta)
    confirmado = _incidente(almacen, id_)
    assert confirmado["estado"]["actual"] == "confirmado"
    primero, *_ = confirmado["estado"]["historial"]
    destino = {
        **confirmado, "id": "EODI-2025-00998",
        "estado": {"actual": "notificado", "historial": [primero]},
    }  # fmt: skip
    almacen.guardar_incidente(destino, DESPUES, MODELOS)
    unido = {**confirmado, "fusionado_en": "EODI-2025-00998"}
    unido.pop("episodio", None)
    almacen.guardar_incidente(unido, DESPUES, MODELOS)
    # Con la fuente de la autoridad, el guardado ya la confirma (proceso/decidir.py, la autoridad
    # que cuenta lo ocurrido) y la recuperación de la unión no tiene nada que hacer.
    assert oficiales.uniones(almacen, DESPUES + timedelta(hours=1), MODELOS) == []
    nuevo = _incidente(almacen, "EODI-2025-00998")
    assert nuevo["estado"]["actual"] == "confirmado"
    autoridades = {f["id"] for f in nuevo["fuentes"] if f.get("es_autoridad")}
    assert nuevo["estado"]["historial"][-1]["fuente_id"] in autoridades
    # Ya hecho, no cambia nada.
    assert oficiales.uniones(almacen, DESPUES + timedelta(hours=2), MODELOS) == []
    assert _incidente(almacen, "EODI-2025-00998") == nuevo


def test_la_declaracion_del_unido_pasa_a_la_que_queda() -> None:
    """EODI-2026-00108 (Auvere): la noticia de cbsnews.com pasó al unirse EODI-2026-00333 (4 de
    octubre de 2026), pero la declaración de la KAPO que contaba se leyó después en el unido y no
    pasó; el 21 de octubre la ficha se quedó sin ninguna autoridad y pasó a «posible dron»."""
    from datetime import UTC, datetime

    from tests import ejemplos

    ahora = datetime(2025, 11, 5, tzinfo=UTC)
    almacen = Almacen.abrir()
    noticia = {
        **ejemplos.fuente("gdelt-ae54", "C"),
        "frase_origen": "Estonia and Latvia say Russian drones hit their NATO territory",
    }
    declaracion = {
        **ejemplos.fuente("gdelt-ae54-declaracion-1", "B", es_autoridad=True),
        "enlace": noticia["enlace"],
        "medio": "Estonia's Internal Security Service (declaración oficial citada en cbsnews.com)",
        "frase_origen": "Estonia's Internal Security Service said a drone entered the country "
        "from Russia and slammed into the chimney of a power station",
        "campos_respaldados": ["estado", "presencia_dron"],
    }
    otra = {**ejemplos.fuente("gdelt-otra", "C"), "frase_origen": "Droon tabas Auvere korstent"}
    destino = ejemplos.incidente_minimo()
    destino.update(id="EODI-2026-00108", lugar={"punto": {"lat": 59.35, "lon": 27.94},
                                                "radio_km": 3, "pais": "EE"},
                   fuentes=[otra, noticia])  # fmt: skip
    destino["estado"]["historial"][0]["fuente_id"] = "gdelt-otra"
    destino["presencia_dron"] = "no_confirmada"
    almacen.guardar_incidente(destino, ahora, MODELOS)
    unido = {**ejemplos.incidente_minimo(), "id": "EODI-2026-00333",
             "lugar": destino["lugar"], "fuentes": [noticia, declaracion],
             "fusionado_en": "EODI-2026-00108"}  # fmt: skip
    unido["estado"]["historial"][0]["fuente_id"] = "gdelt-ae54"
    almacen.guardar_incidente(unido, ahora, MODELOS)
    assert oficiales.declaraciones_que_faltan(destino, unido) == [declaracion]
    assert oficiales.uniones(almacen, ahora + timedelta(hours=1), MODELOS) == ["EODI-2026-00108"]
    queda = almacen.incidente("EODI-2026-00108")
    assert queda is not None
    assert "gdelt-ae54-declaracion-1" in {f["id"] for f in queda["fuentes"]}
    assert queda["estado"]["actual"] == "confirmado"
    assert queda["presencia_dron"] == "confirmada"
    # Ya hecho, no cambia nada; y una noticia que no está en la que queda no vuelve.
    assert oficiales.uniones(almacen, ahora + timedelta(hours=2), MODELOS) == []
    sin_noticia = {**destino, "fuentes": [otra]}
    assert oficiales.declaraciones_que_faltan(sin_noticia, unido) == []


def test_la_autoria_vuelve_si_una_union_dejo_la_fuente_sin_atribucion(carpeta: Path) -> None:
    """EODI-2026-00211, atribuida por la Presidencia de Rumanía, se unió el 14 de octubre de 2026
    en la EODI-2026-00187: la que quedó recibió las fuentes oficiales, no la atribución."""
    almacen, id_ = _almacen()
    entradas = (_confirma(id_), _entrada(incidente=id_))
    oficiales.aplicar(almacen, DESPUES, MODELOS, entradas, carpeta)
    atribuido = _incidente(almacen, id_)
    *pasos, _ = atribuido["estado"]["historial"]
    sin_atribucion = {**atribuido, "estado": {"actual": "confirmado", "historial": pasos}}
    sin_atribucion.pop("atribucion")
    almacen.guardar_incidente(sin_atribucion, DESPUES, MODELOS)
    resumen = oficiales.aplicar(almacen, DESPUES + timedelta(hours=1), MODELOS, entradas, carpeta)
    assert resumen.atribuidos == [id_]
    nuevo = _incidente(almacen, id_)
    assert nuevo["estado"]["actual"] == "atribuido" and nuevo["atribucion"]["pais"] == "RU"
    ids = [f["id"] for f in nuevo["fuentes"]]
    assert len(ids) == len(set(ids))
    # Y después ya no cambia nada.
    otra = oficiales.aplicar(almacen, DESPUES + timedelta(hours=2), MODELOS, entradas, carpeta)
    assert otra.atribuidos == [] and _incidente(almacen, id_) == nuevo


# --- Titulares ------------------------------------------------------------------------------


def _con_titulo(es: str, en: str, estado: str = "confirmado") -> Documento:
    return {"titulo": {"es": es, "en": en}, "estado": {"actual": estado}, "fuentes": []}


@pytest.mark.parametrize(
    ("es", "en", "es_nuevo", "en_nuevo"),
    [
        (
            "Dron que explotó en el Puerto de Constanza fue controlado por Rusia",
            "Drone that exploded in Constanza Port was controlled by Russia",
            "Dron que explotó en el Puerto de Constanza",
            "Drone that exploded in Constanza Port",
        ),
        (
            "Drones turcos violan el espacio aéreo griego sobre el Egeo",
            "Turkish drones violate Greek airspace over the Aegean",
            "Drones violan el espacio aéreo griego sobre el Egeo",
            "Drones violate Greek airspace over the Aegean",
        ),
        (
            "Un posible dron marroquí causa retraso en vuelos a Melilla",
            "A Moroccan possible drone causes flight delays to Melilla",
            "Un posible dron causa retraso en vuelos a Melilla",
            "A possible drone causes flight delays to Melilla",
        ),
        (
            "Ataque con dron respaldado por Irán contra la base de Dhekelia",
            "Iranian-backed drone strike on Dhekelia base",
            "Ataque con dron contra la base de Dhekelia",
            "Drone strike on Dhekelia base",
        ),
        (
            "Dron ruso se estrella en un campo en el este de Polonia",
            "Russian drone crashes in field in eastern Poland",
            "Dron se estrella en un campo en el este de Polonia",
            "Drone crashes in field in eastern Poland",
        ),
    ],
)
def test_un_titular_sin_atribucion_no_dice_la_nacionalidad_ni_el_autor(
    es: str, en: str, es_nuevo: str, en_nuevo: str
) -> None:
    documento = _con_titulo(es, en)
    assert atribucion.titulo_segun_atribucion(documento) == {"es": es_nuevo, "en": en_nuevo}
    # Aplicada otra vez, no cambia.
    documento["titulo"] = {"es": es_nuevo, "en": en_nuevo}
    assert atribucion.titulo_segun_atribucion(documento) == documento["titulo"]


def test_la_nacionalidad_de_un_lugar_y_la_direccion_de_entrada_se_quedan() -> None:
    titulo = {
        "es": "Dron cruza el espacio aéreo de Lituania desde Bielorrusia",
        "en": "Drone crosses Lithuanian airspace from Belarus",
    }
    assert atribucion.titulo_segun_atribucion(_con_titulo(**titulo)) == titulo
    griego = {"es": "Drones sobre el espacio aéreo griego", "en": "Drones over Greek airspace"}
    assert atribucion.titulo_segun_atribucion(_con_titulo(**griego)) == griego


def test_un_atribuido_puede_decirlo() -> None:
    titulo = {
        "es": "Dron ruso se aproxima al portaaviones Charles de Gaulle en Malmö",
        "en": "Russian drone approaches Charles de Gaulle aircraft carrier in Malmö",
    }
    documento = _con_titulo(**titulo, estado="atribuido")
    assert atribucion.titulo_segun_atribucion(documento) == titulo


def test_el_titular_sin_atribucion_sale_al_guardar_y_la_revision_no_lo_toca() -> None:
    # Un solo sitio decide el titular (proceso/decidir.py): sale bien al guardar y la revisión
    # horaria de titulares no tiene nada que cambiar (antes lo cambiaba y otra regla lo devolvía).
    almacen, id_ = _almacen()
    documento = _incidente(almacen, id_)
    documento["titulo"] = {
        "es": "Drones rusos sobre el aeropuerto de Copenhague",
        "en": "Russian drones over Copenhagen airport",
    }
    almacen.guardar_incidente(documento, AHORA, MODELOS)
    assert _incidente(almacen, id_)["titulo"] == {
        "es": "Posibles drones sobre el aeropuerto de Copenhague",
        "en": "Possible drones over Copenhagen airport",
    }
    assert oficiales.titulares(almacen, DESPUES, MODELOS) == (0, [])
    assert oficiales.titulares(almacen, DESPUES + timedelta(hours=1), MODELOS) == (0, [])
