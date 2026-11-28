"""El servicio de rutas lee el archivo del seguimiento de una vista coherente (28 de noviembre de
2026), la misma copia que la exportación desde el PR 491: la hora que el compresor pasa a
`.jsonl.gz` mientras se lee no se pierde ni se lee dos veces, y la línea a medio escribir de la
hora en curso no rompe la noche."""

import gzip
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from exportacion import seguimiento
from proceso.rutas import noches
from recogida import rutas, seguimiento_archivo

NOCHE = "2026-10-05"
AHORA = datetime(2026, 10, 6, 13, tzinfo=UTC)


def _linea(pista: str, hora: str, lat: float) -> bytes:
    crudo = {"type": "upsert", "data": {
        "id": pista, "type": "uav", "lat": lat, "lon": 33.4,
        "updatedAt": f"2026-10-05T{hora}Z",
    }}  # fmt: skip
    return json.dumps({"via": "ws", "crudo": json.dumps(crudo)}).encode() + b"\n"


def _archivo(raiz: Path) -> tuple[Path, Path]:
    """Una hora cerrada sin comprimir (20 h), otra ya comprimida (19 h) y la hora en curso (21 h)
    con su última línea a medio escribir."""
    mes = raiz / "neptun" / "2026" / "10"
    mes.mkdir(parents=True)
    (mes / "neptun-2026-10-05T19.jsonl.gz").write_bytes(
        gzip.compress(_linea("trk_1", "19:10:00", 49.0))
    )
    cerrada = mes / "neptun-2026-10-05T20.jsonl"
    cerrada.write_bytes(_linea("trk_1", "20:10:00", 49.1) + _linea("trk_1", "20:40:00", 49.2))
    en_curso = mes / "neptun-2026-10-05T21.jsonl"
    en_curso.write_bytes(_linea("trk_1", "21:05:00", 49.3) + b'{"via": "ws", "cru')
    (raiz / "kpszsu" / "historico").mkdir(parents=True)
    return cerrada, en_curso


def _puntos(documento: dict[str, Any]) -> list[str]:
    return [p["t"] for pista in documento["neptun"]["pistas"] for p in pista["puntos"]]


def test_las_rutas_no_se_rompen_con_la_linea_a_medio_escribir(tmp_path: Path) -> None:
    _, en_curso = _archivo(tmp_path / "seguimiento")
    # Antes: la línea a medio escribir de la hora en curso rompía la noche.
    with pytest.raises(json.JSONDecodeError):
        noches.estructurar(tmp_path / "seguimiento", NOCHE)
    hecho = rutas.estructurar(tmp_path / "seguimiento", tmp_path / "rutas", False, AHORA)
    assert hecho["noches"] == 1
    documento = json.loads(gzip.decompress((tmp_path / "rutas" / "noches" / f"{NOCHE}.json.gz")
                                           .read_bytes()))  # fmt: skip
    assert _puntos(documento) == [
        "2026-10-05T19:10:00Z", "2026-10-05T20:10:00Z", "2026-10-05T20:40:00Z",
        "2026-10-05T21:05:00Z",
    ]  # fmt: skip
    # El original no se toca y la vista no queda en la carpeta de las rutas.
    assert en_curso.read_bytes().endswith(b'"cru')
    assert sorted(p.name for p in (tmp_path / "rutas").iterdir()) == ["noches"]


def test_las_rutas_aguantan_la_compresion_de_la_hora_mientras_leen(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # La carrera de la exportación del 22/11/2026, en el servicio de rutas: el compresor del
    # archivo actúa entre el listado y la lectura de la hora cerrada.
    cerrada, _ = _archivo(tmp_path / "seguimiento")
    leer = Path.read_bytes
    comprimida: list[Path] = []

    def leer_mientras_comprime(ruta: Path) -> bytes:
        if ruta == cerrada and not comprimida:
            comprimida.append(ruta)
            seguimiento_archivo.comprimir(ruta)
        return leer(ruta)

    monkeypatch.setattr(Path, "read_bytes", leer_mientras_comprime)
    vista = seguimiento.vista_coherente(tmp_path / "seguimiento", tmp_path / "copia")
    monkeypatch.undo()
    assert comprimida and not cerrada.exists()
    documento = noches.estructurar(vista, NOCHE)
    # Cada punto una vez: ni perdido ni leído dos veces.
    assert _puntos(documento) == [
        "2026-10-05T19:10:00Z", "2026-10-05T20:10:00Z", "2026-10-05T20:40:00Z",
        "2026-10-05T21:05:00Z",
    ]  # fmt: skip


def test_la_vista_lleva_el_historico_del_canal(tmp_path: Path) -> None:
    datos = tmp_path / "seguimiento"
    _archivo(datos)
    historico = datos / "kpszsu" / "historico" / "kpszsu-historico-2026-10.jsonl.gz"
    historico.write_bytes(gzip.compress(b'{"id": 1, "fecha": "2026-10-05T19:00:00Z"}\n'))
    vista = seguimiento.vista_coherente(datos, tmp_path / "copia")
    copia = vista / "kpszsu" / "historico" / historico.name
    assert copia.read_bytes() == historico.read_bytes()
    assert list(noches.noches_del_archivo(vista)) == list(noches.noches_del_archivo(datos))
