"""Vigilancia del despliegue de la web (recogida/despliegue_web.py): producción en verde con el
último commit de main; si falla, un reintento; si sigue fallando, problema (incidencia)."""

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from recogida import despliegue_web as d

AHORA = datetime(2026, 10, 14, 9, 0, tzinfo=UTC)
SHA = "a240567" + "0" * 33
VIEJO = "c88ad07" + "0" * 33


def _d(estado: str, sha: str = SHA, minutos: int = 10) -> dict[str, Any]:
    creado = int((AHORA - timedelta(minutes=minutos)).timestamp() * 1000)
    return {"uid": f"dpl_{estado}_{minutos}", "state": estado, "created": creado,
            "meta": {"githubCommitSha": sha}}  # fmt: skip


def test_produccion_en_verde_o_en_marcha_no_es_problema() -> None:
    commit = AHORA - timedelta(hours=1)
    for estado in ("READY", "BUILDING", "QUEUED"):
        r = d.diagnosticar([_d(estado), _d("READY", VIEJO, 90)], SHA, commit, AHORA)
        assert not r.problema and not r.reintentar


def test_un_fallo_se_reintenta_y_dos_seguidos_son_problema() -> None:
    commit = AHORA - timedelta(hours=1)
    uno = d.diagnosticar([_d("ERROR", minutos=5), _d("READY", minutos=60)], SHA, commit, AHORA)
    assert uno.reintentar and not uno.problema
    dos = d.diagnosticar(
        [_d("ERROR", minutos=5), _d("ERROR", minutos=10), _d("READY", minutos=60)], SHA, commit,
        AHORA,
    )  # fmt: skip
    assert dos.problema and not dos.reintentar and "2 veces" in dos.frase
    # Un despliegue bueno entre medias corta la racha (como el de las 05:34 del 14 de octubre).
    racha = [_d("ERROR", minutos=5), _d("READY", minutos=7), _d("ERROR", minutos=9)]
    vuelta = d.diagnosticar(racha, SHA, commit, AHORA)
    assert not vuelta.problema and vuelta.reintentar


def test_commit_sin_despliegue_espera_20_minutos_y_luego_se_pide() -> None:
    lista = [_d("READY", VIEJO, 30)]
    assert not d.diagnosticar(lista, SHA, AHORA - timedelta(minutes=5), AHORA).reintentar
    tarde = d.diagnosticar(lista, SHA, AHORA - timedelta(minutes=40), AHORA)
    assert tarde.reintentar and not tarde.problema


def test_commit_que_no_toca_la_web_no_es_problema() -> None:
    r = d.diagnosticar([_d("CANCELED"), _d("READY", VIEJO, 60)], SHA, AHORA - timedelta(hours=1),
                       AHORA)  # fmt: skip
    assert not r.problema and not r.reintentar and "no toca la web" in r.frase


class Api:
    def __init__(self, despliegues: list[dict[str, Any]]) -> None:
        self.despliegues = despliegues
        self.llamadas: list[tuple[str, str, dict[str, Any] | None]] = []

    def __call__(self, metodo: str, ruta: str, cuerpo: dict[str, Any] | None) -> dict[str, Any]:
        self.llamadas.append((metodo, ruta, cuerpo))
        if ruta.startswith("/v6/deployments"):
            return {"deployments": self.despliegues}
        if ruta.startswith("/v9/projects/"):
            return {"link": {"type": "github", "repoId": 1390631598}}
        return {"id": "dpl_nuevo"}


def test_el_reintento_pide_un_despliegue_de_main(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("GITHUB_OUTPUT", str(tmp_path / "salida"))
    api = Api([_d("ERROR", minutos=5), _d("READY", minutos=60)])
    d.principal(["--sha", SHA], AHORA, api, lambda _s: AHORA - timedelta(hours=1))
    posts = [c for c in api.llamadas if c[0] == "POST"]
    assert posts and posts[0][2] is not None
    assert posts[0][2]["gitSource"] == {"type": "github", "repoId": 1390631598, "ref": "main"}
    salida = (tmp_path / "salida").read_text(encoding="utf-8")
    assert "problema_web=false" in salida and "dpl_nuevo" in salida


def test_dos_fallos_abren_incidencia_sin_mas_reintentos(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("GITHUB_OUTPUT", str(tmp_path / "salida"))
    api = Api([_d("ERROR", minutos=5), _d("ERROR", minutos=15)])
    d.principal(["--sha", SHA], AHORA, api, lambda _s: AHORA - timedelta(hours=1))
    assert not any(c[0] == "POST" for c in api.llamadas)
    assert "problema_web=true" in (tmp_path / "salida").read_text(encoding="utf-8")


def test_sin_token_no_falla(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_OUTPUT", str(tmp_path / "salida"))
    monkeypatch.delenv("VERCEL_TOKEN", raising=False)
    assert d.principal(["--sha", SHA], AHORA) == 0
    assert "problema_web=false" in (tmp_path / "salida").read_text(encoding="utf-8")
