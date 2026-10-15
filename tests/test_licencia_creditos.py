"""Créditos de los datos abiertos (recogida/licencia.py, configuracion/licencia_datos.json): el
autor con su ORCID, la cita recomendada con la versión y la dirección viajan dentro de cada fichero
publicado, en los metadatos de cada objeto y en la exportación semanal."""

import json
from datetime import UTC, datetime

import pytest

from recogida import licencia
from tests.conftest import CORREO_PRUEBA

ORCID = "https://orcid.org/0009-0008-5179-2534"


def test_cita_recomendada_con_la_version() -> None:
    assert licencia.cita("2026-11") == {
        "es": "Alaniz Pintos, L. (2026). European Observatory of Drone Incidents. Versión 2026-11. "
        "https://droneobservatory.eu. Licencia CC BY 4.0.",
        "en": "Alaniz Pintos, L. (2026). European Observatory of Drone Incidents. Version 2026-11. "
        "https://droneobservatory.eu. Licence CC BY 4.0.",
    }


def test_la_version_de_los_datos_vivos_es_el_mes_en_utc() -> None:
    assert licencia.version_actual(datetime(2027, 1, 1, 0, 5, tzinfo=UTC)) == "2027-01"


def test_el_fichero_publicado_lleva_autor_orcid_licencia_cita_y_direccion() -> None:
    datos = licencia.con_licencia(b'{"ataques": []}', "2026-11")
    documento = json.loads(datos)
    assert list(documento) == ["licencia", "ataques"]
    miembro = documento["licencia"]
    assert miembro["autor"] == {
        "nombre": "Lucas Alaniz Pintos",
        "firma": {"es": "Dr. Lucas Alaniz Pintos", "en": "Lucas Alaniz Pintos, PhD"},
        "orcid": ORCID,
        "correo": CORREO_PRUEBA,
    }
    assert miembro["nombre"] == "CC BY 4.0"
    assert miembro["fuente"] == "https://droneobservatory.eu/"
    assert "Versión 2026-11" in miembro["cita"]["es"]


def test_sin_la_variable_el_autor_va_sin_correo(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(licencia.VARIABLE_CORREO)
    assert "correo" not in licencia.autor()
    assert licencia.autor()["orcid"] == ORCID


def test_cabeceras_solo_ascii() -> None:
    cabeceras = licencia.cabeceras()
    assert cabeceras["x-amz-meta-autor"] == "Lucas Alaniz Pintos"
    assert cabeceras["x-amz-meta-orcid"] == ORCID
    for valor in cabeceras.values():
        valor.encode("ascii")


def test_creditos_de_un_conjunto() -> None:
    creditos = licencia.creditos("2026-10")
    assert creditos["titulo"] == "European Observatory of Drone Incidents"
    assert creditos["autor"]["orcid"] == ORCID
    assert creditos["licencia"] == {
        "nombre": "CC BY 4.0",
        "url": "https://creativecommons.org/licenses/by/4.0/",
    }
    assert creditos["direccion"] == "https://droneobservatory.eu/"
    assert creditos["cita"]["en"].endswith(
        "Version 2026-10. https://droneobservatory.eu. Licence CC BY 4.0."
    )
