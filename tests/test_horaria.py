"""Ejecución horaria de punta a punta con un repositorio git local y un canal falso."""

import dataclasses
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
from proceso.extraccion import Parada
from recogida import extractor, firms, fuerza_aerea, gdelt, horaria, mindef, oficiales
from recogida.cache import CachePaginas
from recogida.descarga import Descargador, Respuesta
from tests.telegram_falso import CanalFalso, descargador
from tests.test_fuerza_aerea import canal


@pytest.fixture
def entorno(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[str, CanalFalso, Path]:
    monkeypatch.setenv(VARIABLE_CLAVE, str(pyrage.x25519.Identity.generate()))
    desnudo = tmp_path / "datos.git"
    desnudo.mkdir()
    subprocess.run(["git", "init", "--quiet", "--bare"], cwd=desnudo, check=True)
    falso = canal()
    monkeypatch.setattr(horaria, "Descargador", lambda **_: descargador(falso))
    monkeypatch.setattr(horaria, "CachePaginas", lambda: CachePaginas(tmp_path / "cache"))
    monkeypatch.setattr(horaria, "FUENTES", (fuerza_aerea.FUENTE,))
    # GDELT sin red: una API que no devuelve artículos.
    monkeypatch.setattr(gdelt, "ejecutar", lambda almacen, descargador, ahora: gdelt.Recuentos())
    # Fuentes oficiales sin red.
    monkeypatch.setattr(
        oficiales, "ejecutar", lambda almacen, ahora, modelos, **_: oficiales.Recuentos()
    )
    salida = tmp_path / "publicacion"
    monkeypatch.setattr(horaria, "publicar", lambda a, ahora: publicar.publicar(a, ahora, salida))
    # La previsión, en la misma carpeta (nunca en publicacion/ del repositorio).
    monkeypatch.setattr(horaria, "DIRECTORIO", salida)
    # FIRMS sin red y sin clave: sus CSV, en una carpeta de la prueba.
    monkeypatch.setenv(firms.VARIABLE_DATOS, str(tmp_path / "firms"))
    monkeypatch.delenv(firms.VARIABLE_CLAVE, raising=False)
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
    assert salida == horaria.SALIDA_AVISO
    assert base_remota(repositorio, tmp_path).ataques_ucrania() == []


@pytest.mark.parametrize(
    ("resultado", "salida"),
    [
        # Servicio caído o límite de gasto: los candidatos esperan y no hay aviso.
        (extractor.Resultado(pendientes=9, parada=Parada.SERVICIO_CAIDO), 0),
        (extractor.Resultado(pendientes=9, parada=Parada.LIMITE_GASTO), 0),
        # Caída de más de seis horas o error que no se arregla solo.
        (
            extractor.Resultado(pendientes=9, parada=Parada.SERVICIO_CAIDO, en_rojo=True),
            horaria.SALIDA_AVISO,
        ),
        (
            extractor.Resultado(pendientes=9, parada=Parada.ERROR, en_rojo=True),
            horaria.SALIDA_AVISO,
        ),
    ],
)
def test_el_extractor_solo_deja_la_ejecucion_en_rojo_cuando_lo_pide(
    entorno: tuple[str, CanalFalso, Path],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    resultado: extractor.Resultado,
    salida: int,
) -> None:
    repositorio, _, _ = entorno
    monkeypatch.setattr(extractor, "horaria", lambda almacen, ahora, **_: resultado)
    subir_base(repositorio, tmp_path, ultimo_id=1)
    assert horaria.principal(["--correo", "a@b.org", "--repositorio", repositorio]) == salida
    # Con aviso o sin él, lo recogido está en la base subida.
    assert len(base_remota(repositorio, tmp_path).ataques_ucrania()) == 3


def test_una_fuente_que_agota_su_tope_es_un_aviso_y_no_frena_a_las_demas(
    entorno: tuple[str, CanalFalso, Path], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repositorio, falso, _ = entorno
    sin_tiempo = dataclasses.replace(fuerza_aerea.FUENTE, tope_s=0.0)
    monkeypatch.setattr(horaria, "FUENTES", (sin_tiempo,))
    pasos: list[str] = []

    def gdelt_falso(almacen: Almacen, descargador: Descargador, ahora: datetime) -> gdelt.Recuentos:
        pasos.append("gdelt")
        return gdelt.Recuentos()

    monkeypatch.setattr(gdelt, "ejecutar", gdelt_falso)
    subir_base(repositorio, tmp_path, ultimo_id=1)
    salida = horaria.principal(["--correo", "a@b.org", "--repositorio", repositorio])
    assert salida == horaria.SALIDA_AVISO
    assert falso.pedidas == []
    assert pasos == ["gdelt"]
    # El cursor no se mueve: la siguiente ejecución lee desde el mismo sitio.
    assert base_remota(repositorio, tmp_path).cursor("fuerza_aerea_ua") == {"ultimo_id": 1}


def test_un_canal_que_no_responde_es_un_aviso_y_no_tumba_la_ejecucion(
    entorno: tuple[str, CanalFalso, Path], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repositorio, _, salida_publicacion = entorno

    def caido(url: str, cabeceras: dict[str, str], limite_s: float) -> Respuesta:
        return 503, {}, b""

    monkeypatch.setattr(
        horaria,
        "Descargador",
        lambda **_: Descargador(caido, dormir=lambda _: None, pausa_minima_s=0, reintentos=0),
    )
    subir_base(repositorio, tmp_path, ultimo_id=1)
    salida = horaria.principal(["--correo", "a@b.org", "--repositorio", repositorio])
    assert salida == horaria.SALIDA_AVISO
    # Lo demás se hace: los ficheros públicos se generan igual.
    assert (salida_publicacion / publicar.UCRANIA).exists()


def test_fuentes_oficiales_sin_leer_por_tiempo_es_un_aviso(
    entorno: tuple[str, CanalFalso, Path], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repositorio, _, _ = entorno
    monkeypatch.setattr(
        oficiales, "ejecutar", lambda almacen, ahora, modelos, **_: oficiales.Recuentos(sin_leer=2)
    )
    subir_base(repositorio, tmp_path, ultimo_id=1)
    salida = horaria.principal(["--correo", "a@b.org", "--repositorio", repositorio])
    assert salida == horaria.SALIDA_AVISO
    assert len(base_remota(repositorio, tmp_path).ataques_ucrania()) == 3


@pytest.mark.parametrize("codigo", [500, 403])
def test_firms_caido_no_cambia_el_resultado_ni_la_publicacion(
    entorno: tuple[str, CanalFalso, Path],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    codigo: int,
) -> None:
    repositorio, _, salida_publicacion = entorno
    clave = "f" * 32
    monkeypatch.setenv(firms.VARIABLE_CLAVE, clave)

    def caido(url: str, cabeceras: dict[str, str], limite_s: float) -> Respuesta:
        return codigo, {}, b""

    monkeypatch.setattr(
        firms,
        "descargador",
        lambda plazo=None: Descargador(caido, dormir=lambda _: None, pausa_minima_s=0),
    )
    subir_base(repositorio, tmp_path, ultimo_id=1)
    estado = tmp_path / "estado.json"
    salida = horaria.principal(
        ["--correo", "a@b.org", "--repositorio", repositorio, "--estado", str(estado)]
    )
    assert salida == 0
    assert (salida_publicacion / publicar.UCRANIA).exists()
    assert len(base_remota(repositorio, tmp_path).ataques_ucrania()) == 3
    fuentes = json.loads(estado.read_text(encoding="utf-8"))
    assert fuentes["firms"] == {"id": "firms", "estado": "no_leida", "ultimo_dato": None}
    assert "firms no se lee" in caplog.text and clave not in caplog.text


def test_publicar_solo_informa_de_lo_que_cambia(tmp_path: Path) -> None:
    almacen = Almacen.abrir()
    ahora = datetime(2026, 9, 28, tzinfo=UTC)
    primera = publicar.publicar(almacen, ahora, tmp_path)
    assert sorted(p.name for p in primera) == [
        publicar.INCIDENTES, publicar.SIN_UBICACION, publicar.UCRANIA,
    ]  # fmt: skip
    assert publicar.publicar(almacen, ahora, tmp_path) == []
    assert b"\r\n" not in (tmp_path / publicar.UCRANIA).read_bytes()


def test_una_fuente_sin_cursor_no_impide_leer_las_demas(
    entorno: tuple[str, CanalFalso, Path], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repositorio, _, _ = entorno
    monkeypatch.setattr(horaria, "FUENTES", (fuerza_aerea.FUENTE, mindef.FUENTE))
    subir_base(repositorio, tmp_path, ultimo_id=1)
    salida = horaria.principal(["--correo", "a@b.org", "--repositorio", repositorio])
    assert salida == horaria.SALIDA_AVISO
    assert len(base_remota(repositorio, tmp_path).ataques_ucrania()) == 3
