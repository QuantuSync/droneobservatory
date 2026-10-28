"""Noticias retrospectivas (docs/control_fichas.md, «Noticias retrospectivas»): una noticia que
cuenta un suceso anterior no se publica con la fecha de su publicación. Va al experto con la
pregunta de la fecha y de si es el suceso de una ficha anterior del mismo sitio, sin ventana de
días, y se retiene hasta que la fecha está respaldada. Los casos son las fichas de Leipzig
(EODI-2026-00663 y 00499, ataque del 4 de agosto de 2026) y Wunstorf (00666, hallazgo del 15 de
septiembre) tal como entraron el 8, el 21 y el 22 de octubre de 2026."""

import copy
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from almacen.base import Almacen
from proceso import auditoria_fichas, fechas
from proceso import control_fichas as reglas
from recogida import control_fichas
from tests import ejemplos
from tests.ejemplos import VOCABULARIO_MODELOS

FICHAS: dict[str, dict[str, Any]] = json.loads(
    (Path(__file__).parent / "fixtures" / "retrospectivas.json").read_text(encoding="utf-8")
)
LEIPZIG, WUNSTORF = "EODI-2026-00134", "EODI-2026-00276"


def _ficha(id_: str) -> dict[str, Any]:
    return copy.deepcopy(FICHAS[id_])


def _con_frase(frase: str, idioma: str, dia: str = "2026-10-22") -> dict[str, Any]:
    ficha = _ficha("EODI-2026-00663")
    ficha["tiempo"]["inicio"]["valor"] = f"{dia}T08:00Z"
    ficha["fuentes"][0].update(frase_origen=frase, idioma=idioma)
    return ficha


def test_la_noticia_de_agosto_publicada_en_octubre_es_retrospectiva() -> None:
    # avaz.ba, 22 de octubre: «…na aerodromu Lajpcig/Hale u Njemačkoj u augustu…».
    assert fechas.retrospectiva(_ficha("EODI-2026-00663")) == "augustu"
    assert auditoria_fichas.auditar([_ficha("EODI-2026-00663")], [])["N"] == ["EODI-2026-00663"]


@pytest.mark.parametrize(
    ("frase", "idioma"),
    [
        ("the attempted drone attack at Leipzig airport last month", "en"),
        ("Der Drohnenangriff vom letzten Monat auf den Flughafen", "de"),
        ("el ataque con drones del mes pasado en el aeropuerto", "es"),
        ("l'attaque de drone du mois dernier", "fr"),
    ],
)
def test_un_pasado_lejano_sin_dia_es_retrospectivo(frase: str, idioma: str) -> None:
    assert fechas.retrospectiva(_con_frase(frase, idioma)) is not None


@pytest.mark.parametrize(
    ("frase", "idioma"),
    [
        # «mai» en rumano es «más» (diez de las catorce fichas que marcaba N el 25 de octubre).
        ("Republica Moldova, tot mai des survolată de drone", "ro"),
        ("A drone was seen near the airport this morning", "en"),
        # El mes anterior en los primeros días del mes es el de la víspera.
        ("Drohne in der Nacht zum 1. November gesichtet, Ende Oktober", "de"),
    ],
)
def test_lo_de_ese_dia_no_es_retrospectivo(frase: str, idioma: str) -> None:
    dia = "2026-11-02" if idioma == "de" else "2026-10-22"
    assert fechas.retrospectiva(_con_frase(frase, idioma, dia)) is None


def test_la_noticia_sin_palabra_del_pasado_pregunta_si_hay_ficha_anterior_del_sitio() -> None:
    # freiepresse.de, 8 de octubre: «Der Anschlagsversuch … auf dem Flughafen Leipzig/Halle»: ni
    # un mes ni un pasado, pero la ficha del ataque del 4 de agosto es del mismo aeropuerto.
    leipzig, nueva = _ficha(LEIPZIG), _ficha("EODI-2026-00499")
    assert fechas.retrospectiva(nueva) is None
    assert (
        reglas.pide_fecha(nueva, [leipzig, nueva]) == f"ficha anterior del mismo sitio: {LEIPZIG}"
    )
    assert reglas.pide_fecha(nueva, [nueva]) is None
    # Wunstorf: el hallazgo del 15 de septiembre está a 200 m del Fliegerhorst, sin su nombre.
    wunstorf, otra = _ficha(WUNSTORF), _ficha("EODI-2026-00666")
    assert reglas.previas_del_sitio(otra, [wunstorf, otra]) == [wunstorf]
    assert reglas.pide_fecha(otra, [wunstorf, otra]) is not None


def test_una_fecha_ya_comprobada_no_pregunta() -> None:
    nueva = _ficha("EODI-2026-00499")
    nueva["tiempo"]["origen_inicio"] = {"tipo": "explicita", "motivo": "«el 8 de octubre»"}
    assert reglas.pide_fecha(nueva, [_ficha(LEIPZIG), nueva]) is None


def _comprobar(respuesta: dict[str, Any], candidatas: tuple[str, ...] = (LEIPZIG,)) -> Any:
    texto = FICHAS["EODI-2026-00663"]["fuentes"][0]["frase_origen"]
    fuentes = [("gdelt-20473be3d01e762b", texto)]
    publicacion = datetime(2026, 10, 21, 23, 0, tzinfo=UTC)
    base = {
        "retrospectiva": True,
        "misma_que": "",
        "fecha": "",
        "precision": "",
        "fuente": 0,
        "frase": "",
        "motivo_es": "m",
        "motivo_en": "m",
    }
    return reglas.comprobar_retrospectiva(
        {**base, **respuesta}, fuentes, list(candidatas), publicacion
    )


def test_el_experto_une_la_noticia_a_la_ficha_del_suceso() -> None:
    assert _comprobar({"misma_que": LEIPZIG})["decision"] == "mismo"
    # Una ficha que no se le mandó no vale.
    assert _comprobar({"misma_que": "EODI-2026-00001"}) is None


def test_la_fecha_del_experto_necesita_su_frase_literal() -> None:
    frase = "u Njemačkoj u augustu"
    mes = _comprobar({"fecha": "2026-08", "precision": "mes", "fuente": 1, "frase": frase})
    # Sin precisión de mes en el esquema: el día 1, «aproximada».
    assert mes["inicio"] == {"valor": "2026-08-01T00:00Z", "precision": "aproximada"}
    dia = _comprobar({"fecha": "2026-08-04", "precision": "dia", "fuente": 1, "frase": frase})
    assert dia["inicio"] == {"valor": "2026-08-04T00:00Z", "precision": "dia"}
    assert _comprobar({"fecha": "2026-08-04", "fuente": 1, "frase": "el 4 de agosto"}) is None
    # Una fecha que no es anterior a la noticia no es la de un suceso anterior.
    assert _comprobar({"fecha": "2026-10-25", "fuente": 1, "frase": frase}) is None
    assert _comprobar({"retrospectiva": False})["decision"] == "no_retrospectiva"


def test_la_ficha_con_la_fecha_o_la_marca_ya_no_pregunta() -> None:
    nueva = _ficha("EODI-2026-00663")
    decision = _comprobar({"fecha": "2026-08", "fuente": 1, "frase": "u Njemačkoj u augustu"})
    fechada = reglas.con_fecha_retrospectiva(nueva, decision)
    assert fechada["tiempo"]["inicio"]["valor"] == "2026-08-01T00:00Z"
    assert fechada["tiempo"]["origen_inicio"]["tipo"] == "explicita"
    assert reglas.pide_fecha(fechada, [fechada]) is None
    marcada = reglas.con_fecha_retrospectiva(nueva, {"decision": "no_retrospectiva"})
    assert marcada["tiempo"]["inicio"] == nueva["tiempo"]["inicio"]
    assert fechas.retrospectiva(marcada) is None and reglas.pide_fecha(marcada, [marcada]) is None


def _ejecutar(almacen: Almacen, ahora: datetime) -> control_fichas.Resultado:
    return control_fichas.ejecutar(almacen, ahora, VOCABULARIO_MODELOS, "horaria", None)


def _previa(id_: str) -> dict[str, Any]:
    """La ficha anterior del sitio, mínima: su lugar, su instalación y su fecha comprobada."""
    ficha = {**ejemplos.incidente_minimo(), "id": id_}
    ficha.update({c: copy.deepcopy(FICHAS[id_][c]) for c in ("lugar", "objetivo", "tiempo")})
    return ficha


def test_sin_fecha_respaldada_no_se_publica_ni_a_las_seis_horas() -> None:
    ahora = datetime(2026, 10, 24, 0, 17, tzinfo=UTC)
    almacen = Almacen.abrir()
    almacen.guardar_incidente(_previa(LEIPZIG), ahora, VOCABULARIO_MODELOS)
    _ejecutar(almacen, ahora)  # primera pasada: lo que había se da por visto
    for id_ in ("EODI-2026-00663", "EODI-2026-00499"):
        almacen.guardar_incidente(_ficha(id_), ahora, VOCABULARIO_MODELOS)
    _ejecutar(almacen, ahora + timedelta(hours=1))
    assert control_fichas.retenidos(almacen) >= {"EODI-2026-00663", "EODI-2026-00499"}
    tarde = _ejecutar(almacen, ahora + timedelta(hours=8))
    # Sin el experto, ninguna sale: tampoco la que solo comparte el aeropuerto (hasta el 28 de
    # octubre de 2026 salía a las 6 horas; ahora espera al filtro de entrada).
    assert "EODI-2026-00663" in tarde.retenidos
    assert "EODI-2026-00663" in control_fichas.retenidos(almacen)
    assert "EODI-2026-00499" in tarde.retenidos and not tarde.liberados
