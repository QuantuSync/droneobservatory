"""Las zonas de lanzamiento se escriben en el idioma de la web (configuracion/
zonas_lanzamiento_nombres.json, campos es y en): ninguna sale en cirílico en la versión española
ni en la inglesa."""

import json
import re
from pathlib import Path

from proceso import zonas_lanzamiento

CIRILICO = re.compile("[\u0400-\u04ff]")
TABLA = Path(__file__).resolve().parent.parent / "configuracion" / "zonas_lanzamiento_nombres.json"


def test_cada_zona_normalizada_tiene_su_nombre_en_espanol_y_en_ingles() -> None:
    datos = json.loads(TABLA.read_text(encoding="utf-8"))
    for grupo in ("zonas", "direcciones"):
        for entrada in datos[grupo]:
            for idioma in ("es", "en"):
                nombre = entrada.get(idioma)
                assert isinstance(nombre, str) and nombre.strip(), (entrada["nombre"], idioma)
                assert not CIRILICO.search(nombre), (entrada["nombre"], idioma)


def test_lo_que_publica_la_normalizacion_esta_en_la_tabla() -> None:
    datos = json.loads(TABLA.read_text(encoding="utf-8"))
    conocidas = {e["nombre"] for g in ("zonas", "direcciones") for e in datos[g]}
    partes = ["Брянськ", "Приморсько-Ахтарськ - рф", "ТОТ АР Крим – Гвардійське", "Курська обл.",
              "Міллерове", "Азовського моря"]
    zonas, _ = zonas_lanzamiento.normalizar_lista(partes)
    assert zonas and set(zonas) <= conocidas
