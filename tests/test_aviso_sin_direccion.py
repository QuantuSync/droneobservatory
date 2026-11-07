"""Aviso por el tema privado (el del resumen diario) cuando una ficha que estaba en la web deja de
llevar a una ficha: una vez por ficha, con su número y, si la hay, la ficha a la que redirige. Una
que redirige (308) a una ficha publicada no es un 404 y no se avisa (recogida/publicacion.py)."""

import json
import sqlite3
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from recogida import almacen_publico, publicacion

AHORA = datetime(2026, 11, 7, 20, 36, tzinfo=UTC)


def _base(ruta: Path, documentos: list[dict[str, Any]]) -> Path:
    conexion = sqlite3.connect(ruta)
    conexion.execute("CREATE TABLE incidentes (id TEXT PRIMARY KEY, documento TEXT)")
    for documento in documentos:
        conexion.execute(
            "INSERT INTO incidentes VALUES (?, ?)", (documento["id"], json.dumps(documento))
        )
    conexion.commit()
    conexion.close()
    return ruta


def _avisador(enviados: list[str], falla: bool = False) -> Callable[[], Callable[[str], None]]:
    def avisar(texto: str) -> None:
        if falla:
            raise OSError("ntfy no responde")
        enviados.append(texto)

    return lambda: avisar


def test_una_vez_por_ficha_con_la_ficha_a_la_que_redirige(tmp_path: Path) -> None:
    base = _base(tmp_path / "eodi.sqlite", [
        # Como 00746 el 6 de noviembre de 2026, pero unida a una que no se publica.
        {"id": "EODI-2026-00746", "fusionado_en": "EODI-2026-00760"},
        {"id": "EODI-2026-00700", "retirado": {"motivo": "no es un suceso con dron"}},
    ])  # fmt: skip
    enviados: list[str] = []
    perdidas = ["EODI-2026-00700", "EODI-2026-00746", "EODI-2026-00799"]
    avisadas = publicacion.avisar_sin_direccion(perdidas, {}, base, AHORA, _avisador(enviados))
    assert sorted(avisadas) == perdidas
    assert len(enviados) == 3
    unida = next(t for t in enviados if t.startswith("EODI-2026-00746"))
    assert "404" in unida and "Redirige a EODI-2026-00760" in unida
    retirada = next(t for t in enviados if t.startswith("EODI-2026-00700"))
    assert "Retirada: no es un suceso con dron" in retirada
    sola = next(t for t in enviados if t.startswith("EODI-2026-00799"))
    assert "no consta como retirada" in sola
    # Una sola vez: la publicación siguiente no vuelve a avisar.
    otra = publicacion.avisar_sin_direccion(perdidas, avisadas, base, AHORA, _avisador(enviados))
    assert otra == avisadas and len(enviados) == 3


def test_sin_aviso_privado_o_si_falla_no_se_anota(tmp_path: Path) -> None:
    base = tmp_path / "no-existe.sqlite"
    assert (
        publicacion.avisar_sin_direccion(["EODI-2026-00700"], {}, base, AHORA, lambda: None) == {}
    )
    enviados: list[str] = []
    fallida = _avisador(enviados, falla=True)
    assert publicacion.avisar_sin_direccion(["EODI-2026-00700"], {}, base, AHORA, fallida) == {}
    # Sin la base, el aviso sale igual, con solo el número.
    assert publicacion.avisar_sin_direccion(
        ["EODI-2026-00700"], {}, base, AHORA, _avisador(enviados)
    ) == {"EODI-2026-00700": "2026-11-07T20:36:00Z"}  # fmt: skip
    assert enviados and enviados[0].startswith("EODI-2026-00700")


def _publicados(carpeta: Path, ids: list[str], unidos: dict[str, str]) -> Path:
    carpeta.mkdir(parents=True, exist_ok=True)
    rasgos = [{"properties": {"id": i, "estado": "confirmado"}} for i in ids]
    (carpeta / "incidentes.geojson").write_text(
        json.dumps({"features": rasgos, "unidos": unidos}), encoding="utf-8"
    )
    return carpeta


def test_en_la_publicacion_un_308_no_avisa_y_un_404_si(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """La recogida publica: 00760 pasa a redirigir a 00746 (308, no se avisa); 00700 ya no está
    (404, se avisa); 00650, que redirigía a 00700, tampoco lleva ya a ninguna ficha (se avisa).
    Con la copia de reserva no se avisa (tiene su propio registro)."""
    monkeypatch.setenv(almacen_publico.VARIABLE_ID, "id")
    monkeypatch.setenv(almacen_publico.VARIABLE_SECRETO, "s")
    monkeypatch.setenv("EODI_BASE", str(_base(tmp_path / "eodi.sqlite", [
        {"id": "EODI-2026-00650", "fusionado_en": "EODI-2026-00700"},
        {"id": "EODI-2026-00700", "retirado": {"motivo": "no verificable"}},
        {"id": "EODI-2026-00760", "fusionado_en": "EODI-2026-00746"},
    ])))  # fmt: skip
    monkeypatch.setattr(publicacion, "subir", lambda *a, **k: (True, {"ficheros": {}}, False))
    enviados: list[str] = []
    monkeypatch.setattr(publicacion, "_avisador_privado", _avisador(enviados))
    registro = tmp_path / "publicacion.json"
    registro.write_text(json.dumps({
        "web": {"incidentes": {i: ["confirmado"] for i in
                               ("EODI-2026-00700", "EODI-2026-00746", "EODI-2026-00760")}},
        "redirigidas": ["EODI-2026-00650"],
    }), encoding="utf-8")  # fmt: skip
    carpeta = _publicados(
        tmp_path / "pub", ["EODI-2026-00746"], {"EODI-2026-00760": "EODI-2026-00746"}
    )
    assert (
        publicacion.principal(["subir", "--carpeta", str(carpeta), "--registro", str(registro)])
        == 0
    )
    assert sorted(t.split()[0] for t in enviados) == ["EODI-2026-00650", "EODI-2026-00700"]
    assert any("Redirige a EODI-2026-00700" in t for t in enviados)
    guardado = json.loads(registro.read_text(encoding="utf-8"))
    assert sorted(guardado["avisadas_404"]) == ["EODI-2026-00650", "EODI-2026-00700"]
    assert guardado["redirigidas"] == ["EODI-2026-00760"]
    # La hora siguiente (la web aún sin reconstruir, 00700 sigue en su lista; 00650 otra vez entre
    # las que redirigían): ya avisadas, nada nuevo.
    assert "EODI-2026-00700" in guardado["web"]["incidentes"]
    registro.write_text(
        json.dumps({**guardado, "redirigidas": ["EODI-2026-00650"]}), encoding="utf-8"
    )
    assert (
        publicacion.principal(["subir", "--carpeta", str(carpeta), "--registro", str(registro)])
        == 0
    )
    assert len(enviados) == 2
    # La copia de reserva no avisa.
    otro = tmp_path / "reserva.json"
    otro.write_text(json.dumps({"web": {"incidentes": {"EODI-2026-00701": []}}}), encoding="utf-8")
    monkeypatch.setattr(almacen_publico, "cargar_reserva", lambda: object())
    assert publicacion.principal(
        ["subir", "--carpeta", str(carpeta), "--registro", str(otro), "--reserva"]
    ) == 0  # fmt: skip
    assert len(enviados) == 2
