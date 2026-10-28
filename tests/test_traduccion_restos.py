"""Traducciones con restos en inglés: no se guardan y, si ya estaban guardadas, la cita se vuelve a
pedir (EODI-2026-00689: «…y uno de ellos se hundió, according to»)."""

import json
from datetime import UTC, datetime
from typing import Any

from almacen.base import Almacen
from proceso import validaciones
from recogida import control_fichas

FRASE = "Two cargo ships were hit by drones overnight, and one was sunk, Bulgarian officials said."
MALA = {"idioma": "en", "es": "Dos buques de carga fueron alcanzados por drones durante la noche, "
        "y uno de ellos se hundió, according to", "en": FRASE}  # fmt: skip
BUENA = {"idioma": "en", "es": "Dos buques de carga fueron alcanzados por drones durante la noche "
         "y uno de ellos se hundió, según las autoridades búlgaras.", "en": FRASE}  # fmt: skip


def test_los_restos_en_ingles_se_ven() -> None:
    assert validaciones.restos_sin_traducir("en", MALA["es"]) == "according to"
    assert validaciones.restos_sin_traducir("ro", "El ministro said que…") == "said"
    assert validaciones.restos_sin_traducir("en", BUENA["es"]) is None
    # Una cita que ya estaba en español queda como la escribió su fuente.
    assert validaciones.restos_sin_traducir("es", "según dijo, «as reported»") is None


def test_la_guardada_con_restos_no_cuenta_y_se_reemplaza() -> None:
    almacen = Almacen.abrir()
    huella = control_fichas.huella_texto(FRASE)
    almacen._conexion.execute(
        "INSERT INTO traducciones (huella, fecha, documento) VALUES (?, ?, ?)",
        (huella, "2026-10-27T06:17:03Z", json.dumps(MALA)),
    )
    assert huella not in almacen.traducciones()
    # Otra mala no se guarda; la buena reemplaza a la mala.
    assert almacen.guardar_traducciones({huella: MALA}, "2026-10-28T08:17:00Z") == 0
    assert almacen.guardar_traducciones({huella: BUENA}, "2026-10-28T08:17:00Z") == 1
    assert almacen.traducciones()[huella]["es"] == BUENA["es"]
    # Una buena no cambia.
    otra = {**BUENA, "es": "Otra traducción."}
    assert almacen.guardar_traducciones({huella: otra}, "2026-10-28T09:17:00Z") == 0
    assert almacen.traducciones()[huella]["es"] == BUENA["es"]


def test_el_control_no_guarda_la_respuesta_con_restos() -> None:
    huella = control_fichas.huella_texto(FRASE)
    peticion = control_fichas.peticiones_traduccion({huella: ("en", FRASE)}, set())[0]
    guardadas: dict[str, Any] = {}

    class Guardar:
        def guardar_traducciones(self, nuevas: dict[str, Any], _fecha: str) -> int:
            guardadas.update(nuevas)
            return len(nuevas)

    class Ctx:
        almacen = Guardar()
        ahora = datetime(2026, 10, 28, tzinfo=UTC)
        resultado = control_fichas.Resultado()

    respuesta = {"traducciones": [{"n": 1, "es": MALA["es"], "en": FRASE}]}
    control_fichas.procesar_traduccion(Ctx(), peticion, respuesta)  # type: ignore[arg-type]
    assert guardadas == {}
