"""La cita respalda el titular (proceso/cita_titular.py; docs/informe_revision_contenido.md,
bloque 1). Prueba fija: corre en la integración continua sobre los datos publicados de verdad
(el trabajo «datos-publicados», que los baja de donde los lee la web, con EODI_PUBLICACION) y,
en el resto de trabajos, sobre los datos de ejemplo (tests/fixtures/publicacion). La misma
comprobación deja sin publicar en cada recogida el incidente que no la pasa."""

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from exportacion.geojson import publicables
from proceso import cita_titular
from tests import ejemplos
from tests.ejemplos import VOCABULARIO_MODELOS

PUBLICACION = Path(
    os.environ.get("EODI_PUBLICACION")
    or Path(__file__).resolve().parent / "fixtures" / "publicacion"
)


def _publicados() -> list[dict[str, Any]]:
    mapa = json.loads((PUBLICACION / "incidentes.geojson").read_text(encoding="utf-8"))
    sin = json.loads((PUBLICACION / "incidentes_sin_ubicacion.json").read_text(encoding="utf-8"))
    publicados: list[dict[str, Any]] = [
        {**f["properties"], "id": f["id"]} for f in mapa["features"]
    ]
    return publicados + list(sin["incidentes"])


def test_ningun_titular_publicado_sin_respaldo() -> None:
    """Todo incidente publicado tiene una cita que nombra su país, su lugar o un nombre propio
    de su titular, o está revisado a mano y justificado."""
    fallan = [i["id"] for i in _publicados() if not cita_titular.publicable(i)]
    assert fallan == []


def test_los_justificados_llevan_motivo_en_los_dos_idiomas() -> None:
    datos = json.loads(cita_titular.REVISADOS.read_text(encoding="utf-8"))
    for entrada in datos.get("titular_justificado", []):
        assert entrada["motivo"]["es"] and entrada["motivo"]["en"]


def _incidente(titulo: str, frase: str, pais: str = "NL") -> dict[str, Any]:
    documento = ejemplos.incidente_minimo()
    documento["titulo"] = {"es": titulo, "en": titulo}
    documento["lugar"] = {"pais": pais}
    documento["fuentes"][0]["frase_origen"] = frase
    documento.pop("afirmaciones", None)
    return documento


@pytest.mark.parametrize(
    ("titulo", "frase", "pais"),
    [
        # Cirílico: «София» pasa al alfabeto latino como «sofija» y casa con «Sofía».
        ("Un dron bloquea seis vuelos en el aeropuerto de Sofía",
         "Собственикът на дрона, блокирал 6 полета на Летище София", "BG"),
        # Lo que la transliteración no alcanza va en nombres_equivalentes.json.
        ("Posible dron cierra una pista de Schiphol",
         "Аэропорт Схипхол приостанавливал работу взлетно-посадочной полосы из-за дрона.", "NL"),
        ("Dron obliga a cerrar el aeropuerto de Vilna",
         "dėl minėto drono teko laikinai stabdyti skrydžius Vilniaus oro uoste.", "LT"),
        ("Drones violan el espacio aéreo griego sobre el Egeo",
         "Οι παραβάσεις και παραβιάσεις σημειώθηκαν στο Βορειοανατολικό και Κεντρικό "
         "Αιγαίο.", "GR"),
    ],
)  # fmt: skip
def test_otra_escritura_y_otro_nombre_respaldan(titulo: str, frase: str, pais: str) -> None:
    assert cita_titular.respalda(_incidente(titulo, frase, pais))


def test_una_cita_de_otro_lugar_no_respalda() -> None:
    # Como EODI-2025-00094: el titular decía Geilenkirchen y la cita habla de otro aeropuerto.
    incidente = _incidente(
        "Drones cerca de la base aérea de Geilenkirchen causan desvío de vuelos",
        "Primili smo prijave o dronu u vazduhu", "NO",
    )  # fmt: skip
    assert not cita_titular.respalda(incidente)


def test_un_titular_sin_respaldo_no_se_publica() -> None:
    respaldado = _incidente(
        "Dron sobre el aeropuerto de Schiphol", "Een drone boven Schiphol legde het verkeer stil."
    )
    sin_respaldo = _incidente(
        "Dron sobre el aeropuerto de Schiphol", "Er was een drone gezien boven de luchthaven."
    )
    sin_respaldo["id"] = "EODI-2025-00099"
    ahora = datetime(2026, 1, 1, tzinfo=UTC)
    publicados = publicables([respaldado, sin_respaldo], ahora, VOCABULARIO_MODELOS)
    assert [i["id"] for i in publicados] == [respaldado["id"]]
