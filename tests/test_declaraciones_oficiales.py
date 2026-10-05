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


def test_la_revision_de_titulares_guarda_con_su_motivo() -> None:
    almacen, id_ = _almacen()
    documento = _incidente(almacen, id_)
    documento["titulo"] = {
        "es": "Drones rusos sobre el aeropuerto de Copenhague",
        "en": "Russian drones over Copenhagen airport",
    }
    almacen.guardar_incidente(documento, AHORA, MODELOS)
    cambiados, fallidos = oficiales.titulares(almacen, DESPUES, MODELOS)
    assert (cambiados, fallidos) == (1, [])
    assert _incidente(almacen, id_)["titulo"] == {
        "es": "Drones sobre el aeropuerto de Copenhague",
        "en": "Drones over Copenhagen airport",
    }
    motivos = [c["nuevo"].get("motivo") for c in almacen.historial(id_) if c["nuevo"]]
    assert oficiales.MOTIVO_TITULAR in motivos
    assert oficiales.titulares(almacen, DESPUES + timedelta(hours=1), MODELOS) == (0, [])
