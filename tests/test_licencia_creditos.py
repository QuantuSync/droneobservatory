"""Créditos de los datos abiertos (recogida/licencia.py, configuracion/licencia_datos.json): el
autor con su ORCID, la cita de los datos vivos (con el DOI de la versión archivada más reciente)
y la dirección viajan dentro de cada fichero publicado, en los metadatos de cada objeto y en la
exportación semanal."""

import json
from datetime import UTC, datetime

import pytest

from recogida import licencia
from tests.conftest import CORREO_PRUEBA

ORCID = "https://orcid.org/0009-0008-5179-2534"


DOI = "https://doi.org/10.48320/F2CA4AE9-B2D3-4B0F-8F58-6CFBDE30D39F"
NOVIEMBRE = datetime(2026, 11, 4, 9, 17, tzinfo=UTC)


def test_cita_de_los_datos_vivos_con_el_doi_archivado() -> None:
    # Las versiones mensuales se retiraron el 3/11/2026: ningún fichero dice «Versión AAAA-MM».
    assert licencia.cita(NOVIEMBRE) == {
        "es": "Alaniz Pintos, L. (2026). European Observatory of Drone Incidents. Datos vivos a la "
        "fecha de actualización de este fichero. https://droneobservatory.eu. Licencia CC BY 4.0. "
        f"Para citar los datos, use la versión archivada más reciente: {DOI}",
        "en": "Alaniz Pintos, L. (2026). European Observatory of Drone Incidents. Live data as of "
        "this file's update date. https://droneobservatory.eu. Licence CC BY 4.0. To cite the "
        f"data, use the latest archived version: {DOI}",
    }


def test_el_doi_es_el_de_la_version_archivada_mas_reciente() -> None:
    versiones = json.loads(licencia.ARCHIVADAS.read_text(encoding="utf-8"))["versiones"]
    assert licencia.doi_archivado() == versiones[0]["doi"]
    assert "Versi" not in json.dumps(licencia.cargar()["cita"]).replace("versión archivada", "")


def test_el_fichero_publicado_lleva_autor_orcid_licencia_cita_y_direccion() -> None:
    datos = licencia.con_licencia(b'{"ataques": []}', NOVIEMBRE)
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
    assert "Datos vivos a la fecha de actualización" in miembro["cita"]["es"]
    assert miembro["cita"]["es"].endswith(DOI)


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
    creditos = licencia.creditos(NOVIEMBRE)
    assert creditos["titulo"] == "European Observatory of Drone Incidents"
    assert creditos["autor"]["orcid"] == ORCID
    assert creditos["licencia"] == {
        "nombre": "CC BY 4.0",
        "url": "https://creativecommons.org/licenses/by/4.0/",
    }
    assert creditos["direccion"] == "https://droneobservatory.eu/"
    assert creditos["cita"]["en"].endswith(
        f"To cite the data, use the latest archived version: {DOI}"
    )
