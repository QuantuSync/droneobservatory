"""Copias de seguridad de la base en el almacén de objetos, contra un S3 falso: sin red."""

import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pyrage
import pytest

from almacen import copias, sitio
from almacen.cifrado import VARIABLE_CLAVE
from tests.s3_falso import S3Falso

DESTINO = copias.cargar_destino()
LUNES = datetime(2026, 10, 5, 3, 17, tzinfo=UTC)


@pytest.fixture
def s3() -> S3Falso:
    return S3Falso(DESTINO.bucket)


@pytest.fixture
def cliente(s3: S3Falso) -> copias.Copias:
    return copias.Copias(DESTINO, copias.Credenciales("id", "secreto"), s3, lambda _s: None)


@pytest.fixture
def clave(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(VARIABLE_CLAVE, str(pyrage.x25519.Identity.generate()))


def base_de_prueba(ruta: Path, filas: int = 50) -> Path:
    conexion = sqlite3.connect(ruta)
    conexion.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, texto TEXT, dato BLOB)")
    conexion.executemany(
        "INSERT INTO t (texto, dato) VALUES (?, ?)",
        [(f"fila {i} ñ", bytes([i % 256]) * 10) for i in range(filas)],
    )
    conexion.commit()
    conexion.close()
    return ruta


def test_configuracion_privada_y_retencion_del_encargo() -> None:
    assert DESTINO.bucket != "droneobservatory-almacen"  # el público
    assert DESTINO.retencion == {
        copias.HORARIA: timedelta(hours=48),
        copias.DIARIA: timedelta(days=30),
        copias.SEMANAL: timedelta(days=365),
    }


def test_la_primera_del_dia_y_de_la_semana_va_tambien_a_esos_niveles(
    cliente: copias.Copias, s3: S3Falso, tmp_path: Path
) -> None:
    cifrada = tmp_path / "db.age"
    cifrada.write_bytes(b"uno")
    subidas = cliente.guardar(cifrada, LUNES)["subidas"]
    assert isinstance(subidas, list)
    assert sorted(subidas) == [
        "base/diaria/2026-10-05.db.age",
        "base/horaria/2026-10-05T031700Z.db.age",
        "base/semanal/2026-W41.db.age",
    ]
    cifrada.write_bytes(b"dos")
    hecho = cliente.guardar(cifrada, LUNES + timedelta(hours=1))
    assert hecho["subidas"] == ["base/horaria/2026-10-05T041700Z.db.age"]
    # La diaria es la primera del día: no se sustituye.
    assert s3.objetos["base/diaria/2026-10-05.db.age"][0] == b"uno"


def test_poda_cada_nivel_con_su_retencion_y_nunca_la_ultima(
    cliente: copias.Copias, s3: S3Falso, tmp_path: Path
) -> None:
    cifrada = tmp_path / "db.age"
    cifrada.write_bytes(b"x")
    inicio = LUNES - timedelta(days=400)
    momento = inicio
    while momento <= LUNES:
        for nivel, clave in copias.claves(DESTINO, momento).items():
            if nivel == copias.HORARIA and LUNES - momento > timedelta(days=4):
                continue
            s3.objetos[clave] = (b"x", {})
        momento += timedelta(hours=6)
    borradas = cliente.podar(LUNES)
    assert borradas
    restantes = cliente.copias()
    for nivel, cuando, _objeto in restantes:
        assert LUNES - cuando <= DESTINO.retencion[nivel]
    horarias = [c for c in restantes if c[0] == copias.HORARIA]
    assert len(horarias) == 9  # 48 h cada 6 h, con los dos extremos
    assert len([c for c in restantes if c[0] == copias.DIARIA]) == 30
    assert 52 <= len([c for c in restantes if c[0] == copias.SEMANAL]) <= 53
    # Si solo queda una copia caducada de un nivel, se conserva.
    s3.objetos.clear()
    viejo = copias.claves(DESTINO, LUNES - timedelta(days=90))[copias.DIARIA]
    s3.objetos[viejo] = (b"x", {})
    assert cliente.podar(LUNES) == []


def test_restaurada_igual_en_contenido_a_la_original(
    cliente: copias.Copias, tmp_path: Path, clave: None
) -> None:
    original = base_de_prueba(tmp_path / "original.sqlite")
    cifrada = sitio.cifrar_fichero(original, tmp_path / "db.age")
    cliente.guardar(cifrada, LUNES)
    restaurada = tmp_path / "restaurada.sqlite"
    hecho = cliente.restaurar(restaurada)
    assert hecho["objeto"] == "base/horaria/2026-10-05T031700Z.db.age"
    assert sitio.huella_fichero(restaurada) == sitio.huella_fichero(original)


def test_una_copia_alterada_no_se_restaura(
    cliente: copias.Copias, s3: S3Falso, tmp_path: Path, clave: None
) -> None:
    cifrada = sitio.cifrar_fichero(base_de_prueba(tmp_path / "o.sqlite"), tmp_path / "db.age")
    cliente.guardar(cifrada, LUNES)
    clave_objeto = "base/horaria/2026-10-05T031700Z.db.age"
    cuerpo, meta = s3.objetos[clave_objeto]
    # Cambia de verdad el último byte (sustituirlo por uno fijo no lo cambia si ya era ese).
    s3.objetos[clave_objeto] = (cuerpo[:-1] + bytes([cuerpo[-1] ^ 1]), meta)
    with pytest.raises(OSError, match="huella"):
        cliente.restaurar(tmp_path / "r.sqlite")


def test_listado_por_paginas_y_reintento_tras_un_fallo_del_servicio(
    s3: S3Falso, tmp_path: Path
) -> None:
    s3.por_pagina = 2
    cliente = copias.Copias(DESTINO, copias.Credenciales("id", "s"), s3, lambda _s: None)
    for horas in range(5):
        clave = copias.claves(DESTINO, LUNES + timedelta(hours=horas))[copias.HORARIA]
        s3.objetos[clave] = (b"x", {})
    s3.fallos_pendientes = 1
    assert len(cliente.copias()) == 5
    assert cliente.ultima() == "base/horaria/2026-10-05T071700Z.db.age"


def test_preparar_crea_el_bucket_privado(cliente: copias.Copias, s3: S3Falso) -> None:
    assert cliente.preparar() == "bucket creado (200)"
    assert cliente.preparar() == "el bucket ya existe"
    assert cliente.anonimo_rechazado("base/cualquiera")


def test_credenciales_del_fichero(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(copias.VARIABLE_ID, raising=False)
    monkeypatch.delenv(copias.VARIABLE_SECRETO, raising=False)
    fichero = tmp_path / "almacen.env"
    fichero.write_text("# copia\nALMACEN_ID=abc\nALMACEN_SECRETO='def'\n", encoding="utf-8")
    monkeypatch.setenv(copias.VARIABLE_CREDENCIALES, str(fichero))
    assert copias.Credenciales.cargar() == copias.Credenciales("abc", "def")


def test_nombres_de_las_copias() -> None:
    claves = copias.claves(DESTINO, LUNES)
    for nivel, clave in claves.items():
        leido = copias.nivel_y_momento(clave, DESTINO.prefijo)
        assert leido is not None and leido[0] == nivel
    assert copias.nivel_y_momento("base/otra-cosa.txt", DESTINO.prefijo) is None
