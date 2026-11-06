"""Una parte separada que es el suceso de otra ficha (`coincide_con`) se une a esa ficha, y queda
esa: la que ya se publicaba, con su dirección y sus datos revisados con cita. El 6 de noviembre de
2026 la separación de EODI-2026-00756 (Letonia) dio de alta la parte del martes como
EODI-2026-00760, con 6 fuentes, 2 drones, el Geran del domingo y el día 1; la unión con
EODI-2026-00746 (el dron del martes, 2 fuentes, 1 dron revisado) eligió por número de fuentes y
00746 quedó dentro de 00760."""

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from almacen.base import Almacen
from recogida import publicacion, revisados
from tests.test_sucesos_mezclados import (  # noqa: F401  (el accesorio se usa por su nombre)
    AHORA,
    MODELOS,
    VILNA,
    _extractor_falso,
    _fuente,
    _incidente,
    vilna,
)

WP = "https://wiadomosci.wp.pl/incydenty-nad-lotwa"
MOTIVO = "Juntaba el domingo y el martes"
# La pasada de la recogida que aplicó la separación de 00756.
LV = datetime(2026, 11, 6, 9, 17, tzinfo=UTC)


def _letonia(almacen: Almacen, ahora: Any) -> None:
    """00746 publicada desde el 3 de noviembre; 00760 dada de alta en la pasada de `ahora`, con
    más fuentes (las notas del 5 de noviembre que cuentan los dos días)."""
    martes = _incidente("EODI-2026-00746", [
        _fuente("m1", WP + "-martes", "2026-11-03T02:00:00Z", "rozbił się bezzałogowiec"),
        _fuente("m2", "https://lsm.lv/balvi", "2026-11-03T06:00:00Z", "Balvu novadā"),
    ], "2026-11-02T22:00Z")  # fmt: skip
    nueva = _incidente("EODI-2026-00760", [
        _fuente(f"n{n}", f"https://medio{n}.pl/dwa-drony", "2026-11-05T07:15:00Z", "dwa drony")
        for n in range(6)
    ], "2026-11-01T00:00Z")  # fmt: skip
    almacen.guardar_incidente(martes, ahora, MODELOS)  # su alta: el 3 de noviembre
    nueva["control"]["alta"] = {"valor": ahora.strftime("%Y-%m-%dT%H:%MZ"), "precision": "minuto"}
    almacen.guardar_incidente(nueva, ahora, MODELOS)


def test_la_ficha_nueva_no_le_quita_la_direccion_a_la_publicada() -> None:
    almacen = Almacen.abrir()
    _letonia(almacen, LV)
    unidos = revisados.unir_grupo(
        almacen, ["EODI-2026-00760", "EODI-2026-00746"], MOTIVO, LV, MODELOS
    )
    assert unidos == 1
    nueva, martes = almacen.incidente("EODI-2026-00760"), almacen.incidente("EODI-2026-00746")
    assert nueva is not None and nueva["fusionado_en"] == "EODI-2026-00746"
    assert martes is not None and "fusionado_en" not in martes
    # Con sus fuentes y su día: el martes, no el domingo de la nueva.
    assert len(martes["fuentes"]) == 8
    assert martes["tiempo"]["inicio"]["valor"].startswith("2026-11-02")


def test_la_union_hecha_al_reves_se_deshace() -> None:
    """Como quedó en producción: 00746 dentro de 00760. Con `conserva` (la ficha con la que
    coincide la parte), la unión se deshace y se hace al revés; una segunda pasada no cambia."""
    almacen = Almacen.abrir()
    _letonia(almacen, LV)
    revisados.unir_grupo(
        almacen, ["EODI-2026-00760", "EODI-2026-00746"], MOTIVO, LV, MODELOS,
        conserva="EODI-2026-00760",
    )  # fmt: skip
    mal = almacen.incidente("EODI-2026-00746")
    assert mal is not None and mal["fusionado_en"] == "EODI-2026-00760"
    despues = LV + timedelta(days=3)
    assert revisados.unir_grupo(
        almacen, ["EODI-2026-00760", "EODI-2026-00746"], MOTIVO, despues, MODELOS,
        conserva="EODI-2026-00746",
    ) == 1  # fmt: skip
    nueva, martes = almacen.incidente("EODI-2026-00760"), almacen.incidente("EODI-2026-00746")
    assert nueva is not None and nueva["fusionado_en"] == "EODI-2026-00746"
    assert martes is not None and "fusionado_en" not in martes
    assert len(martes["fuentes"]) == 8
    antes = {i["id"]: i for i in almacen.incidentes()}
    assert revisados.unir_grupo(
        almacen, ["EODI-2026-00760", "EODI-2026-00746"], MOTIVO, despues + timedelta(hours=1),
        MODELOS, conserva="EODI-2026-00746",
    ) == 0  # fmt: skip
    assert {i["id"]: i for i in almacen.incidentes()} == antes


def test_queda_la_ficha_con_datos_revisados(monkeypatch: pytest.MonkeyPatch) -> None:
    """Las dos publicadas antes: queda la que tiene datos revisados con cita (van por
    identificador; la absorbida los perdería), aunque tenga menos fuentes."""
    almacen = Almacen.abrir()
    _letonia(almacen, LV - timedelta(days=1))
    monkeypatch.setattr(revisados, "_con_datos_revisados", lambda d: d["id"] == "EODI-2026-00746")
    revisados.unir_grupo(almacen, ["EODI-2026-00760", "EODI-2026-00746"], MOTIVO, LV, MODELOS)
    nueva = almacen.incidente("EODI-2026-00760")
    assert nueva is not None and nueva["fusionado_en"] == "EODI-2026-00746"
    # Sin datos revisados en ninguna, la regla de siempre (más fuentes).
    otro = Almacen.abrir()
    _letonia(otro, LV - timedelta(days=1))
    monkeypatch.setattr(revisados, "_con_datos_revisados", lambda d: False)
    revisados.unir_grupo(otro, ["EODI-2026-00760", "EODI-2026-00746"], MOTIVO, LV, MODELOS)
    martes = otro.incidente("EODI-2026-00746")
    assert martes is not None and martes["fusionado_en"] == "EODI-2026-00760"


def test_la_parte_que_ya_tiene_ficha_vuelve_a_ella(
    vilna: Almacen,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Separación ya hecha con la parte del derribo dada de alta (00180) y la ficha que ya tenía
    el suceso (00179) fundida dentro de ella: la pasada siguiente lo deja al revés, y 00007 se
    enlaza con 00179."""
    monkeypatch.setattr(revisados, "_extraer", _extractor_falso([]))
    revisados.separar(vilna, AHORA, MODELOS, cliente=object())
    # Para dejarla al revés, como quedó 00746 en producción.
    monkeypatch.setattr(revisados, "VUELTA_DESDE", "2026-10-01T00:00Z")
    revisados.unir_grupo(
        vilna, ["EODI-2026-00180", "EODI-2026-00179"], MOTIVO, AHORA, MODELOS,
        conserva="EODI-2026-00180",
    )  # fmt: skip
    derribo = vilna.incidente("EODI-2026-00179")
    assert derribo is not None and derribo["fusionado_en"] == "EODI-2026-00180"
    # Una fusión de antes de VUELTA_DESDE no se toca: ya se publica así (00262 en 00636).
    monkeypatch.setattr(revisados, "VUELTA_DESDE", "2026-11-06T00:00Z")
    revisados.separar(vilna, AHORA + timedelta(hours=1), MODELOS, cliente=object())
    derribo = vilna.incidente("EODI-2026-00179")
    assert derribo is not None and derribo["fusionado_en"] == "EODI-2026-00180"
    monkeypatch.setattr(revisados, "VUELTA_DESDE", "2026-10-01T00:00Z")
    revisados.separar(vilna, AHORA + timedelta(hours=2), MODELOS, cliente=object())
    derribo, parte = vilna.incidente("EODI-2026-00179"), vilna.incidente("EODI-2026-00180")
    assert derribo is not None and "fusionado_en" not in derribo
    assert parte is not None and parte["fusionado_en"] == "EODI-2026-00179"
    cierre = vilna.incidente("EODI-2026-00007")
    assert cierre is not None
    assert [r["id"] for r in cierre["relacionados"]] == ["EODI-2026-00179"]


def test_la_parte_extraida_despues_se_une_en_la_misma_pasada(
    vilna: Almacen,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sin extractor en la separación (o pasado su tope), la parte la extrae el extractor de la
    horaria; `unir_coincidentes`, que la horaria llama después, la une ya en esa pasada."""
    revisados.separar(vilna, AHORA, MODELOS, cliente=None)
    (nuevo,) = [c for c in vilna.candidatos() if c.get("separado_de")]
    assert vilna.incidente("EODI-2026-00180") is None
    _extractor_falso([])(vilna, None, nuevo, AHORA)
    assert revisados.unir_coincidentes(vilna, AHORA, MODELOS) == 1
    parte = vilna.incidente("EODI-2026-00180")
    assert parte is not None and parte["fusionado_en"] == "EODI-2026-00179"


def test_aviso_de_ficha_publicada_que_pasa_a_404() -> None:
    antes = {"EODI-2026-00746": ["confirmado"], "EODI-2026-00756": ["confirmado"],
             "EODI-2026-00700": ["confirmado"]}  # fmt: skip
    ahora = {"EODI-2026-00756": ["confirmado"], "EODI-2026-00760": ["confirmado"]}
    # 00746 redirige a la ficha que queda: no da 404. 00700 ni se publica ni redirige.
    assert publicacion.sin_direccion(antes, ahora, {"EODI-2026-00746"}) == ["EODI-2026-00700"]
    assert publicacion.sin_direccion(antes, {**ahora, "EODI-2026-00700": []},
                                     {"EODI-2026-00746"}) == []  # fmt: skip


def test_la_separacion_de_letonia_conserva_00746() -> None:
    """La revisión del 6 de noviembre de 2026: la parte del martes coincide con 00746."""
    (revision,) = [r for r in revisados.cargar()["separar"] if r["incidente"] == "EODI-2026-00756"]
    assert [p.get("coincide_con") for p in revision["partes"]] == [None, "EODI-2026-00746"]
    assert VILNA  # el accesorio de Vilna sigue siendo el de test_sucesos_mezclados
