"""Las autoridades siempre en el idioma de la página: las que no están en
configuracion/autoridades.json se traducen como las citas y viajan en la ficha publicada
(`autoridades`), con la marca de nombre para el modelo (proceso/autoridades.py)."""

from datetime import UTC, datetime
from typing import Any

from exportacion import citas
from proceso import autoridades
from recogida import control_fichas

ROMANIA = "Defense Ministry of Romania"


def _incidente() -> dict[str, Any]:
    return {
        "fuentes": [
            {"id": "a", "medio": "news.az", "idioma": "en", "frase_origen": "Three drones."},
            {
                "id": "a-declaracion-1",
                "medio": f"{ROMANIA} (declaración oficial citada en news.az)",
                "idioma": "en",
                "frase_origen": "Three drones.",
            },
            {
                "id": "b",
                "medio": (
                    "Ministerul Apărării Naționale (declaración oficial citada en realitatea.net)"
                ),
                "idioma": "ro",
                "frase_origen": "Trei drone.",
            },
            {
                "id": "c",
                "medio": "Канал обласної адміністрації",
                "idioma": "uk",
                "frase_origen": "Дрон.",
            },
        ],
        "atribucion": {"actor": "Rusia", "autoridad": "Romania"},
        "investigacion": [{"autoridad": "Fiscalía de Constanța", "fuente_id": "b", "cita": "x"}],
    }


def test_las_que_no_estan_en_la_tabla() -> None:
    faltan = dict(autoridades.por_traducir(_incidente()))
    # La de la tabla (el ministerio rumano) no; las demás, con el idioma de su fuente.
    assert "Ministerul Apărării Naționale" not in faltan
    assert "news.az" not in faltan
    assert faltan["Канал обласної адміністрації"] == "uk"
    assert faltan["Fiscalía de Constanța"] == "ro"


def test_la_ficha_lleva_la_traduccion_o_queda_pendiente() -> None:
    publico = _incidente()
    traducciones = {
        citas.huella_texto("Канал обласної адміністрації"): {
            "es": "el canal de la administración regional",
            "en": "the regional administration channel",
        }
    }
    faltan: dict[str, tuple[str, str]] = {}
    citas.con_autoridades(publico, traducciones, faltan)
    assert publico["autoridades"] == {
        "Канал обласної адміністрації": {
            "es": "el canal de la administración regional",
            "en": "the regional administration channel",
        }
    }
    assert faltan[citas.huella_texto("Fiscalía de Constanța")] == (
        "ro",
        autoridades.MARCA + "Fiscalía de Constanța",
    )
    assert all(citas.huella_texto(n) not in faltan for n in autoridades.tabla())


def test_el_control_las_traduce_con_la_marca_y_las_guarda_sin_ella() -> None:
    incidente = {**_incidente(), "id": "EODI-2026-09999"}
    pedidas = control_fichas.citas_de([incidente], {})
    huella = control_fichas.huella_texto("Fiscalía de Constanța")
    assert pedidas[huella] == ("ro", autoridades.MARCA + "Fiscalía de Constanța")
    # Una autoridad ya en español: su «es» es el nombre, sin la marca.
    peticion = control_fichas.peticiones_traduccion(
        {huella: ("es", autoridades.MARCA + "Fiscalía de Constanța")}, set()
    )[0]
    guardadas: dict[str, Any] = {}

    class Almacen:
        def guardar_traducciones(self, nuevas: dict[str, Any], _fecha: str) -> int:
            guardadas.update(nuevas)
            return len(nuevas)

    class Ctx:
        almacen = Almacen()
        ahora = datetime(2026, 10, 14, tzinfo=UTC)
        resultado = control_fichas.Resultado()

    respuesta = {"traducciones": [{"n": 1, "es": "", "en": "the Constanța Prosecutor's Office"}]}
    control_fichas.procesar_traduccion(Ctx(), peticion, respuesta)  # type: ignore[arg-type]
    assert guardadas[huella]["es"] == "Fiscalía de Constanța"
    assert guardadas[huella]["en"] == "the Constanța Prosecutor's Office"


def test_las_instrucciones_explican_la_marca() -> None:
    from modelo import control as peticiones

    assert "[autoridad]" in peticiones.INSTRUCCIONES_TRADUCIR
    assert autoridades.MARCA.strip() == "[autoridad]"
