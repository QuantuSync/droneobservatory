"""La parte de una separación se extrae con su suceso (recogida/revisados.separar,
modelo/ficha.suceso_de_la_parte): EODI-2026-00770, Leipzig/Halle, el cierre de pista del sábado 7 y
el del domingo 8 de noviembre de 2026, contados en las mismas notas. La parte que conservaba el
identificador no perdía fuentes, no se volvía a extraer y seguía con los dos drones y el titular
de los dos días."""

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from almacen.base import Almacen
from modelo import ficha
from proceso import noticias
from recogida import revisados
from tests.test_sucesos_mezclados import _extractor_falso, _fuente, _incidente

AHORA = datetime(2026, 11, 9, 17, 17, tzinfo=UTC)
MODELOS: frozenset[str] = frozenset()
WELT = (
    "https://welt.de/regionales/sachsen/article6af1b0fd79e1656222c37306/"
    "drohnen-behindern-betrieb-am-flughafen-leipzig-halle.html"
)
CANDIDATO = "CAND-20261109T1215-EDDP-aeropuerto"


def _extractor_con_hora(llamadas: list[str], partes: dict[str, Any] | None = None) -> Any:
    """El extractor falso de las separaciones, con la extracción a la hora de la pasada, como la
    guarda el de verdad."""
    falso = _extractor_falso(llamadas)

    def extraer(almacen: Almacen, cliente: Any, candidato: Any, ahora: datetime) -> int:
        if partes is not None:
            partes[candidato["id"]] = candidato.get("parte")
        hechas = int(falso(almacen, cliente, candidato, ahora))
        ultima = almacen.extracciones(candidato["id"])[-1]
        almacen.guardar_extraccion(candidato["id"], ahora.strftime("%Y-%m-%dT%H:%MZ"), "ficha/5",
                                   "h", True, {"incidente": ultima.get("incidente"),
                                               "enviadas": candidato["articulos"]})  # fmt: skip
        return hechas

    return extraer


def _revision_real() -> dict[str, Any]:
    (revision,) = [r for r in revisados.cargar()["separar"] if r["incidente"] == "EODI-2026-00770"]
    return dict(revision)


@pytest.fixture
def leipzig(monkeypatch: pytest.MonkeyPatch) -> Almacen:
    revision = _revision_real()
    almacen = Almacen.abrir()
    titular = "Drohnen behindern Betrieb am Flughafen Leipzig/Halle"
    almacen.guardar_articulo({
        "url": WELT, "medio": "welt.de", "fecha": "2026-11-09T12:15:00Z", "idioma": "de",
        "titular": titular, "titular_normalizado": noticias.normalizar(titular),
        "lugares": ["EDDP"],
    })  # fmt: skip
    almacen.corregir_candidatos([{
        "id": CANDIDATO, "tipo": "aeropuerto", "lugar": "EDDP",
        "inicio": "2026-11-09T12:15:00Z", "ultimo": "2026-11-09T12:15:00Z", "precision": "dia",
        "articulos": [WELT],
    }], "prueba")  # fmt: skip
    nota = _fuente("gdelt-8b62f6dcf03854ba", WELT, "2026-11-09T12:15:00Z",
                   "Zwei Drohnen haben am Wochenende den Betrieb des Flughafens Leipzig/Halle "
                   "vorübergehend beeinträchtigt.")  # fmt: skip
    policia = _fuente("gdelt-8b62f6dcf03854ba-declaracion-1", WELT, "2026-11-09T12:15:00Z",
                      "Wie die Polizei mitteilte, wurde am Samstag und Sonntag jeweils eine der "
                      "beiden Landebahnen kurzzeitig gesperrt.")  # fmt: skip
    mezclada = _incidente("EODI-2026-00770", [nota, policia], "2026-11-07T00:00Z")
    mezclada["drones"] = {"numero": {"min": 2, "max": 2}}
    mezclada["control"]["candidato"] = CANDIDATO
    almacen.guardar_incidente(mezclada, AHORA - timedelta(hours=4), MODELOS)
    almacen.guardar_extraccion(CANDIDATO, "2026-11-09T13:17Z", "ficha/5", "h", True,
                               {"incidente": "EODI-2026-00770", "enviadas": [WELT]})  # fmt: skip
    monkeypatch.setattr(revisados, "cargar", lambda: {"unir": [], "separar": [revision]})
    return almacen


def test_las_dos_partes_de_leipzig_se_extraen_con_su_dia(
    leipzig: Almacen, monkeypatch: pytest.MonkeyPatch
) -> None:
    llamadas: list[str] = []
    partes: dict[str, Any] = {}
    monkeypatch.setattr(revisados, "_extraer", _extractor_con_hora(llamadas, partes))
    revisados.separar(leipzig, AHORA, MODELOS, cliente=object())
    # La que conserva el identificador no pierde fuentes (las dos notas cuentan los dos días) y
    # aun así se vuelve a extraer, ahora sabiendo que es la del sábado.
    assert CANDIDATO in llamadas
    assert partes[CANDIDATO]["fecha"] == "2026-11-07"
    (nuevo,) = [c for c in llamadas if c != CANDIDATO]
    assert partes[nuevo]["fecha"] == "2026-11-08"
    assert "domingo" in partes[nuevo]["descripcion"]
    # Una sola vez: la pasada siguiente no vuelve a llamar.
    revisados.separar(leipzig, AHORA + timedelta(hours=1), MODELOS, cliente=object())
    assert len(llamadas) == 2


def test_una_parte_ya_extraida_sin_su_dia_se_vuelve_a_extraer(
    leipzig: Almacen, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Separada sin el extractor (un ensayo, o con el código de antes): la pasada con el
    # extractor extrae las dos partes con su día.
    revisados.separar(leipzig, AHORA, MODELOS, cliente=None)
    llamadas: list[str] = []
    monkeypatch.setattr(revisados, "_extraer", _extractor_con_hora(llamadas))
    revisados.separar(leipzig, AHORA + timedelta(hours=1), MODELOS, cliente=object())
    assert len(llamadas) == 2 and CANDIDATO in llamadas


def test_un_reparto_anterior_no_lleva_parte(
    leipzig: Almacen, monkeypatch: pytest.MonkeyPatch
) -> None:
    llamadas: list[str] = []
    monkeypatch.setattr(revisados, "_extraer", _extractor_con_hora(llamadas))
    monkeypatch.setattr(revisados, "PARTE_DESDE", "2026-12-01T00:00Z")
    revisados.separar(leipzig, AHORA, MODELOS, cliente=object())
    # Como antes del cambio: la que conserva el identificador sin perder fuentes no se extrae.
    assert CANDIDATO not in llamadas
    assert not any(c.get("parte") for c in leipzig.candidatos())


def test_la_peticion_dice_de_que_suceso_es_la_ficha() -> None:
    fuentes = [ficha.FuenteTexto("welt.de", "2026-11-09", "de", "Drohnen behindern Betrieb", "")]
    parte = {"fecha": "2026-11-08", "descripcion": "otro dron el domingo"}
    con = ficha.contenido("Flughafen Leipzig/Halle (aeropuerto, DE, EDDP)", fuentes, parte)
    sin = ficha.contenido("Flughafen Leipzig/Halle (aeropuerto, DE, EDDP)", fuentes)
    assert "Suceso de esta ficha: solo el del 2026-11-08 (otro dron el domingo)" in con
    assert "Suceso de esta ficha" not in sin
    # Sin parte, la petición es la de siempre (las demás fichas no cambian).
    assert ficha.cuerpo("x", fuentes) == ficha.cuerpo("x", fuentes, None)
