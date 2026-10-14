"""Los avisos de ntfy y el resumen diario escriben las autoridades con la regla de la web: la
tabla revisada, la traducción que viaja con la ficha publicada o «una autoridad» / «an
authority»; nunca el nombre en otra lengua (proceso/autoridades.py)."""

import json
from pathlib import Path
from typing import Any

from proceso import autoridades
from recogida import avisos, visitas
from tests.test_avisos import AHORA, CONFIG, fuente, incidente

POLICIA = "Komenda Wojewódzka Policji w Lublinie"
TRADUCIDA = {"es": "la Comandancia Provincial de Policía de Lublin",
             "en": "the Lublin Provincial Police Headquarters"}  # fmt: skip
DECLARACION = f"{POLICIA} (declaración oficial citada en wiadomosci.pl)"


def test_la_tabla_va_primero() -> None:
    assert autoridades.escrita("Aalborg Lufthavn", "es") == "el aeropuerto de Aalborg"
    assert autoridades.escrita("Armata Națională", "en") == (
        "the Moldovan National Army (Armata Națională)"
    )


def test_despues_la_traduccion_de_la_ficha_y_si_no_una_autoridad() -> None:
    traducidas = {POLICIA: TRADUCIDA}
    assert autoridades.escrita(POLICIA, "es", traducidas) == TRADUCIDA["es"]
    assert autoridades.escrita(POLICIA, "en", traducidas) == TRADUCIDA["en"]
    # Sin traducción, aunque vaya en alfabeto latino: nunca el nombre en otra lengua.
    assert autoridades.escrita(POLICIA, "es") == "una autoridad"
    assert autoridades.escrita(POLICIA, "en") == "an authority"
    assert autoridades.escrita("Областна дирекция на МВР - Варна", "en") == "an authority"


def test_de_la_fuente_declaracion_y_medio_con_dominio() -> None:
    assert autoridades.de_la_fuente(DECLARACION, "es", {POLICIA: TRADUCIDA}) == TRADUCIDA["es"]
    assert autoridades.de_la_fuente(DECLARACION, "en") == "an authority"
    # Un periódico sale tal cual, como en la web.
    assert autoridades.de_la_fuente("novinite.com", "es") == "novinite.com"


def test_un_titular_con_el_nombre_original_lo_escribe_traducido() -> None:
    titulo = f"{POLICIA} confirma un dron sobre Lublin"
    assert autoridades.en_texto(titulo, "es", {POLICIA: TRADUCIDA}) == (
        f"{TRADUCIDA['es']} confirma un dron sobre Lublin"
    )
    assert autoridades.en_texto("Un dron sobre Lublin", "es") == "Un dron sobre Lublin"


def _aviso_de(doc: dict[str, Any]) -> str:
    aviso = avisos.clasificar(doc, CONFIG, AHORA)
    assert aviso is not None
    return str(avisos.mensaje(aviso, doc, CONFIG, "drones-poland")["message"])


def test_el_aviso_escribe_la_autoridad_en_cada_idioma() -> None:
    doc = incidente(lugar={"pais": "PL", "localidad": "Lublin"},
                    fuentes=[fuente(DECLARACION, "B", True)])  # fmt: skip
    con = _aviso_de({**doc, "autoridades": {POLICIA: TRADUCIDA}})
    es, _, en = con.split("\n")
    assert f"Fuente: {TRADUCIDA['es']}." in es and f"Source: {TRADUCIDA['en']}." in en
    sin = _aviso_de(doc)
    assert "Fuente: una autoridad." in sin and "Source: an authority." in sin
    assert POLICIA not in con and POLICIA not in sin


def _publicar(carpeta: Path) -> None:
    rasgo = {"type": "Feature", "id": "EODI-2026-00500", "geometry": None, "properties": {
        "id": "EODI-2026-00500", "autoridades": {POLICIA: TRADUCIDA},
        "titulo": {"es": f"{POLICIA} confirma un dron", "en": "Police confirm a drone"},
    }}  # fmt: skip
    (carpeta / "incidentes.geojson").write_text(json.dumps({"features": [rasgo]}),
                                                encoding="utf-8")  # fmt: skip
    (carpeta / "incidentes_sin_ubicacion.json").write_text(json.dumps({"incidentes": []}),
                                                           encoding="utf-8")  # fmt: skip


def test_los_avisos_leen_las_traducciones_de_la_ficha_publicada(tmp_path: Path) -> None:
    _publicar(tmp_path)
    internos = avisos.con_autoridades({"EODI-2026-00500": incidente(), "otro": {}}, tmp_path)
    assert internos["EODI-2026-00500"]["autoridades"] == {POLICIA: TRADUCIDA}
    assert "autoridades" not in internos["otro"]


def test_el_resumen_diario_escribe_la_autoridad_traducida(tmp_path: Path) -> None:
    _publicar(tmp_path)
    assert visitas.titulos_publicados(tmp_path) == {
        "EODI-2026-00500": f"{TRADUCIDA['es']} confirma un dron"
    }
