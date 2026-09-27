"""Ejecución horaria de punta a punta con un repositorio git local y un canal falso."""

import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import pyrage
import pytest

from almacen import remoto
from almacen.base import Almacen
from almacen.cifrado import VARIABLE_CLAVE, abrir_cifrada, guardar_cifrada
from exportacion import publicar
from recogida import horaria
from recogida.cache import CachePaginas
from tests.telegram_falso import CanalFalso, descargador
from tests.test_fuerza_aerea import canal


@pytest.fixture
def entorno(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[str, CanalFalso, Path]:
    monkeypatch.setenv(VARIABLE_CLAVE, str(pyrage.x25519.Identity.generate()))
    desnudo = tmp_path / "datos.git"
    desnudo.mkdir()
    subprocess.run(["git", "init", "--quiet", "--bare"], cwd=desnudo, check=True)
    falso = canal()
    monkeypatch.setattr(horaria, "Descargador", lambda: descargador(falso))
    monkeypatch.setattr(horaria, "CachePaginas", lambda: CachePaginas(tmp_path / "cache"))
    salida = tmp_path / "publicacion"
    monkeypatch.setattr(horaria, "publicar", lambda a, ahora: publicar.publicar(a, ahora, salida))
    return desnudo.as_uri(), falso, salida


def subir_base(repositorio: str, tmp_path: Path, ultimo_id: int) -> None:
    almacen = Almacen.abrir()
    almacen.guardar_cursor("fuerza_aerea_ua", {"ultimo_id": ultimo_id})
    ruta = tmp_path / "inicial.age"
    guardar_cifrada(almacen.conexion, ruta)
    remoto.subir(ruta, "autor@ejemplo.org", repositorio)


def base_remota(repositorio: str, tmp_path: Path) -> Almacen:
    ruta = tmp_path / "bajada.age"
    assert remoto.descargar(ruta, repositorio)
    return Almacen(abrir_cifrada(ruta))


def test_sin_base_remota_no_hace_nada(entorno: tuple[str, CanalFalso, Path]) -> None:
    repositorio, falso, _ = entorno
    assert horaria.principal(["--correo", "a@b.org", "--repositorio", repositorio]) == 1
    assert falso.pedidas == []


def test_recoge_publica_y_sube(entorno: tuple[str, CanalFalso, Path], tmp_path: Path) -> None:
    repositorio, _, salida = entorno
    subir_base(repositorio, tmp_path, ultimo_id=1)
    assert horaria.principal(["--correo", "a@b.org", "--repositorio", repositorio]) == 0
    almacen = base_remota(repositorio, tmp_path)
    assert len(almacen.ataques_ucrania()) == 3
    assert almacen.cursor("fuerza_aerea_ua") == {
        "ultimo_id": 7,
        "fecha": "2026-09-23T05:07:00+00:00",
    }
    ucrania = json.loads((salida / publicar.UCRANIA).read_text(encoding="utf-8"))
    assert [a["id"] for a in ucrania["ataques"]] == [
        "EODI-UA-2026-0001",
        "EODI-UA-2026-0002",
        "EODI-UA-2026-0003",
    ]
    geojson = json.loads((salida / publicar.INCIDENTES).read_text(encoding="utf-8"))
    assert geojson == {"type": "FeatureCollection", "features": []}


def test_canal_no_verificado_termina_en_rojo_sin_leer(
    entorno: tuple[str, CanalFalso, Path], tmp_path: Path
) -> None:
    repositorio, falso, _ = entorno
    falso.verificado = False
    subir_base(repositorio, tmp_path, ultimo_id=1)
    salida = horaria.principal(["--correo", "a@b.org", "--repositorio", repositorio])
    assert salida == horaria.SALIDA_FUENTE_NO_VERIFICADA
    assert base_remota(repositorio, tmp_path).ataques_ucrania() == []


def test_publicar_solo_informa_de_lo_que_cambia(tmp_path: Path) -> None:
    almacen = Almacen.abrir()
    ahora = datetime(2026, 9, 28, tzinfo=UTC)
    primera = publicar.publicar(almacen, ahora, tmp_path)
    assert sorted(p.name for p in primera) == [publicar.INCIDENTES, publicar.UCRANIA]
    assert publicar.publicar(almacen, ahora, tmp_path) == []
    assert b"\r\n" not in (tmp_path / publicar.UCRANIA).read_bytes()
