"""Reinicio desde fuera por la API de Hetzner (recogida/reinicio_externo.py): cuándo se reinicia,
cuándo se espera, el tope de uno cada 6 horas, el simulacro y la prueba forzada."""

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from recogida import reinicio_externo as r

AHORA = datetime(2026, 10, 14, 9, 50, tzinfo=UTC)


def _salud(minutos: float) -> dict[str, Any]:
    return {"generado": (AHORA - timedelta(minutes=minutos)).strftime("%Y-%m-%dT%H:%M:%SZ")}


def test_decide_segun_el_silencio_y_el_ultimo_reinicio() -> None:
    nunca = None
    assert r.decidir(_salud(4), AHORA, nunca, lambda: False).accion == "nada"
    assert r.decidir(_salud(25), AHORA, nunca, lambda: False).accion == "aplazar"
    assert r.decidir(_salud(31), AHORA, nunca, lambda: False).accion == "reiniciar"
    hace_10 = AHORA - timedelta(minutes=10)
    assert r.decidir(_salud(90), AHORA, hace_10, lambda: False).accion == "aplazar"
    hace_2h = AHORA - timedelta(hours=2)
    assert r.decidir(_salud(150), AHORA, hace_2h, lambda: False).accion == "agotado"
    hace_7h = AHORA - timedelta(hours=7)
    assert r.decidir(_salud(31), AHORA, hace_7h, lambda: False).accion == "reiniciar"


def test_sin_salud_legible_solo_reinicia_si_sshd_tampoco_saluda() -> None:
    assert r.decidir(None, AHORA, None, lambda: True).accion == "nada"
    assert r.decidir(None, AHORA, None, lambda: False).accion == "reiniciar"


def test_forzar_reinicia_aunque_el_servidor_de_senales() -> None:
    assert r.decidir(_salud(1), AHORA, None, lambda: True, forzar=True).accion == "reiniciar"


class Api:
    def __init__(self, acciones: list[dict[str, Any]] | None = None) -> None:
        self.llamadas: list[tuple[str, str]] = []
        self.acciones = acciones or []

    def __call__(self, metodo: str, ruta: str, cuerpo: dict[str, Any] | None) -> dict[str, Any]:
        self.llamadas.append((metodo, ruta))
        if ruta.startswith("/servers?name="):
            ipv4 = {"ip": "192.0.2.10"}
            return {"servers": [{"id": 7, "status": "running", "public_net": {"ipv4": ipv4}}]}
        if ruta.startswith("/servers/7/actions?"):
            return {"actions": self.acciones}
        return {"action": {"id": 1}}


def _salidas(ruta: Path) -> dict[str, str]:
    return dict(linea.split("=", 1) for linea in ruta.read_text(encoding="utf-8").splitlines())


def test_reinicia_por_la_api_y_aplaza_la_incidencia(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("GITHUB_OUTPUT", str(tmp_path / "salida"))
    api = Api()
    r.principal([], AHORA, api, lambda: _salud(45), lambda _ip: False)
    assert ("POST", "/servers/7/actions/reboot") in api.llamadas
    assert _salidas(tmp_path / "salida")["aplazar"] == "true"


def test_el_simulacro_no_pide_nada(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_OUTPUT", str(tmp_path / "salida"))
    api = Api()
    r.principal(["--simulacro", "--forzar"], AHORA, api, lambda: _salud(2), lambda _ip: True)
    assert not any(m == "POST" for m, _ in api.llamadas)
    salidas = _salidas(tmp_path / "salida")
    assert salidas["reinicio"] == "reiniciar" and "SIMULACRO" in salidas["mensaje_reinicio"]


def test_un_reinicio_manual_reciente_tambien_cuenta(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("GITHUB_OUTPUT", str(tmp_path / "salida"))
    hace = (AHORA - timedelta(hours=3)).strftime("%Y-%m-%dT%H:%M:%SZ")
    api = Api([{"command": "reboot_server", "started": hace}, {"command": "create_image"}])
    r.principal([], AHORA, api, lambda: _salud(200), lambda _ip: False)
    assert not any(m == "POST" for m, _ in api.llamadas)
    assert _salidas(tmp_path / "salida")["aplazar"] == "false"


def test_la_prueba_forzada_no_se_lanza_entre_los_minutos_10_y_45() -> None:
    a_las_20 = AHORA.replace(minute=20)
    assert r.principal(["--forzar"], a_las_20, Api(), lambda: _salud(2), lambda _ip: True) == 1


def test_sin_token_no_falla(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_OUTPUT", str(tmp_path / "salida"))
    monkeypatch.delenv("HCLOUD_TOKEN", raising=False)
    assert r.principal([], AHORA, None, lambda: _salud(45)) == 0
    assert _salidas(tmp_path / "salida")["reinicio"] == "sin_token"
