"""Al unir dos fichas, las revisiones a mano de la absorbida pasan a la que queda; si las dos tienen
revisado el mismo dato con valores distintos, la unión se retiene y no se hace.

Las revisiones van por el número de la ficha (configuracion/incidentes_revisados.json). El 6 de
noviembre de 2026 EODI-2026-00746 (el dron del martes en Letonia, con 1 dron y sin modelo
revisados con la cita de wp.pl) quedó dentro de EODI-2026-00760, que no los veía: la web enseñó 2
drones, el Geran del domingo y el día 1."""

import sqlite3
from collections.abc import Iterator
from datetime import timedelta
from typing import Any

import pytest

from almacen.base import Almacen
from proceso import decidir, incidentes
from recogida import revisados
from tests.test_parte_coincidente import LV, MOTIVO
from tests.test_sucesos_mezclados import _fuente, _incidente

MARTES, NUEVA = "EODI-2026-00746", "EODI-2026-00760"
MODELOS = frozenset({"Geran-2"})
WP = (
    "https://wiadomosci.wp.pl/incydenty-nad-lotwa-wojsko-ujawnilo-pochodzenie-dronow-"
    "7347630134045120a"
)
# Las dos revisiones de 00746, tal como están en incidentes_revisados.json.
REVISIONES_746 = {
    "drones": {
        "incidente": MARTES, "campo": "drones", "valor": {"min": 1, "max": 1},
        "cita": "Z kolei bezzałogowiec wykryty we wtorek po północy mógł należeć do Ukrainy.",
        "enlace": WP, "pais": "LV", "motivo": "el martes entró un dron",
    },
    "modelo": {
        "incidente": MARTES, "campo": "modelo", "valor": None,
        "cita": "Nie ujawniono, jaki był model bezzałogowca.", "enlace": WP, "pais": "LV",
        "motivo": "del dron del martes no se dijo el modelo",
    },
}  # fmt: skip


def _ficha(id_: str, fuentes: list[dict[str, Any]], inicio: str, drones: Any) -> dict[str, Any]:
    documento = _incidente(id_, fuentes, inicio)
    # Balvi (Letgalia), junto a la frontera con Rusia.
    documento["lugar"] = {"punto": {"lat": 57.1313, "lon": 27.2658}, "radio_km": 5.0, "pais": "LV"}
    documento["titulo"] = {"es": "Dron en Letonia", "en": "Drone in Latvia"}
    documento["drones"] = drones
    return documento


@pytest.fixture
def letonia(monkeypatch: pytest.MonkeyPatch) -> Iterator[Almacen]:
    """00746 publicada desde el 3 de noviembre, con sus revisiones; 00760 dada de alta el 6, con
    6 fuentes, 2 drones y el Geran."""
    monkeypatch.setattr(decidir, "_revisiones_de_datos", lambda: {MARTES: REVISIONES_746})
    monkeypatch.setattr(decidir, "_titulares_revisados", lambda: {})
    almacen = Almacen.abrir()
    martes = _ficha(MARTES, [
        _fuente("m1", WP, "2026-11-03T02:00:00Z", "rozbił się bezzałogowiec"),
        _fuente("m2", "https://lsm.lv/balvi", "2026-11-03T06:00:00Z", "Balvu novadā"),
    ], "2026-11-02T22:00Z", {"numero": {"min": 1, "max": 1}})  # fmt: skip
    nueva = _ficha(NUEVA, [
        _fuente(f"n{n}", f"https://medio{n}.pl/dwa-drony", "2026-11-05T07:15:00Z", "dwa drony")
        for n in range(6)
    ], "2026-11-01T00:00Z", {"numero": {"min": 2, "max": 2}, "modelo": "Geran-2"})  # fmt: skip
    almacen.guardar_incidente(martes, LV, MODELOS)
    nueva["control"]["alta"] = {"valor": LV.strftime("%Y-%m-%dT%H:%MZ"), "precision": "minuto"}
    almacen.guardar_incidente(nueva, LV, MODELOS)
    yield almacen
    almacen.cerrar()


def test_la_que_queda_toma_las_revisiones_de_la_absorbida(letonia: Almacen) -> None:
    """Como el 6 de noviembre de 2026: 00746 dentro de 00760. La que queda enseña 1 dron y sin
    modelo, lo revisado con la cita de wp.pl, no 2 drones y el Geran."""
    assert revisados.unir_grupo(letonia, [NUEVA, MARTES], MOTIVO, LV, MODELOS, conserva=NUEVA) == 1
    martes, nueva = letonia.incidente(MARTES), letonia.incidente(NUEVA)
    assert martes is not None and martes["fusionado_en"] == NUEVA
    assert nueva is not None and "fusionado_en" not in nueva
    assert nueva["drones"]["numero"] == {"min": 1, "max": 1}
    assert "modelo" not in nueva["drones"]
    assert decidir.revision_de(nueva, "drones") == REVISIONES_746["drones"]
    # Y si la unión se deshace, la que vuelve las tiene otra vez como suyas.
    incidentes.revertir(letonia, MARTES, LV + timedelta(hours=1), MODELOS)
    vuelta = letonia.incidente(MARTES)
    assert vuelta is not None and "fusionado_en" not in vuelta
    assert decidir.revision_de(vuelta, "drones") == REVISIONES_746["drones"]
    assert decidir.fundidas_en(NUEVA) == []


def test_tambien_al_volver_a_abrir_la_base(letonia: Almacen, tmp_path: Any) -> None:
    """Las fusiones vigentes se leen al abrir la base: la siguiente recogida también las ve."""
    revisados.unir_grupo(letonia, [NUEVA, MARTES], MOTIVO, LV, MODELOS, conserva=NUEVA)
    ruta = tmp_path / "eodi.sqlite"
    copia = sqlite3.connect(ruta)
    letonia.conexion.backup(copia)
    copia.close()
    otra = Almacen.abrir(ruta)
    assert decidir.fundidas_en(NUEVA) == [MARTES]
    nueva = otra.incidente(NUEVA)
    assert nueva is not None
    assert decidir.decidir_datos(nueva)["drones"]["numero"] == {"min": 1, "max": 1}
    otra.cerrar()


def test_con_el_mismo_dato_revisado_distinto_la_union_se_retiene(
    letonia: Almacen, monkeypatch: pytest.MonkeyPatch
) -> None:
    """00760 con su propia revisión de 2 drones: no se sabe a cuál hacer caso, y no se unen."""
    dos = {**REVISIONES_746["drones"], "incidente": NUEVA, "valor": {"min": 2, "max": 2},
           "enlace": "https://medio0.pl/dwa-drony", "cita": "dwa drony"}  # fmt: skip
    monkeypatch.setattr(
        decidir, "_revisiones_de_datos", lambda: {MARTES: REVISIONES_746, NUEVA: {"drones": dos}}
    )
    assert decidir.revisiones_en_conflicto(MARTES, NUEVA) == ["drones"]
    antes = {i["id"]: i for i in letonia.incidentes()}
    fallidos: list[str] = []
    monkeypatch.setattr(revisados, "cargar", lambda: {"unir": [
        {"registros": [NUEVA, MARTES], "motivo": MOTIVO, "conserva": NUEVA}
    ]})  # fmt: skip
    assert revisados.unir(letonia, LV, MODELOS, fallidos) == 0
    assert len(fallidos) == 1 and "retenida" in fallidos[0] and "drones" in fallidos[0]
    assert {i["id"]: i for i in letonia.incidentes()} == antes
    # La unión por reglas (mismo sitio y misma ventana) tampoco se hace.
    assert incidentes.revisiones_distintas(MARTES, NUEVA) == ["drones"]


def test_el_mismo_valor_revisado_en_las_dos_no_retiene(
    letonia: Almacen, monkeypatch: pytest.MonkeyPatch
) -> None:
    igual = {**REVISIONES_746["drones"], "incidente": NUEVA, "cita": "otra cita, mismo dato"}
    monkeypatch.setattr(
        decidir, "_revisiones_de_datos", lambda: {MARTES: REVISIONES_746, NUEVA: {"drones": igual}}
    )
    assert decidir.revisiones_en_conflicto(MARTES, NUEVA) == []
    assert revisados.unir_grupo(letonia, [NUEVA, MARTES], MOTIVO, LV, MODELOS, conserva=NUEVA) == 1


def test_la_presencia_revisada_de_la_absorbida_tambien_pasa(
    letonia: Almacen, monkeypatch: pytest.MonkeyPatch
) -> None:
    """«titulares» va también por número de ficha: la presencia revisada pasa igual."""
    monkeypatch.setattr(decidir, "_revisadas_propias", lambda: {MARTES: "no_confirmada"})
    revisados.unir_grupo(letonia, [NUEVA, MARTES], MOTIVO, LV, MODELOS, conserva=NUEVA)
    assert decidir.presencias_revisadas().get(NUEVA) == "no_confirmada"
    assert MARTES in decidir.presencias_revisadas()
