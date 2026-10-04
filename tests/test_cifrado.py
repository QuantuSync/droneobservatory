import gzip
import os
import sqlite3
from pathlib import Path

import pyrage
import pytest

from almacen.base import Almacen
from almacen.cifrado import (
    VARIABLE_CLAVE,
    ClaveAusente,
    abrir_cifrada,
    cargar_clave_local,
    cifrar,
    descifrar,
    guardar_cifrada,
)
from tests import ejemplos
from tests.ejemplos import AHORA, VOCABULARIO_MODELOS


@pytest.fixture
def clave_efimera(monkeypatch: pytest.MonkeyPatch) -> str:
    clave = str(pyrage.x25519.Identity.generate())
    monkeypatch.setenv(VARIABLE_CLAVE, clave)
    return clave


def _almacen_poblado() -> Almacen:
    almacen = Almacen.abrir()
    almacen.guardar_incidente(ejemplos.incidente_completo(), AHORA, VOCABULARIO_MODELOS)
    return almacen


@pytest.mark.usefixtures("clave_efimera")
def test_ida_y_vuelta_conserva_datos_y_triggers(tmp_path: Path) -> None:
    ruta = tmp_path / "eodi.sqlite.age"
    guardar_cifrada(_almacen_poblado().conexion, ruta)

    recuperado = Almacen(abrir_cifrada(ruta))
    assert recuperado.incidente("EODI-2025-00001") == ejemplos.incidente_completo()
    with pytest.raises(sqlite3.IntegrityError):
        recuperado.conexion.execute("DELETE FROM incidentes")


@pytest.mark.usefixtures("clave_efimera")
def test_el_cifrado_no_contiene_texto_en_claro() -> None:
    cifrado = cifrar(_almacen_poblado().conexion)
    assert cifrado.startswith(b"age-encryption.org/")
    for claro in (b"SQLite format", b"EODI-2025-00001", b"Kastrup"):
        assert claro not in cifrado


def test_otra_clave_no_descifra(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(VARIABLE_CLAVE, str(pyrage.x25519.Identity.generate()))
    cifrado = cifrar(_almacen_poblado().conexion)
    monkeypatch.setenv(VARIABLE_CLAVE, str(pyrage.x25519.Identity.generate()))
    with pytest.raises(pyrage.DecryptError):
        descifrar(cifrado)


def test_sin_clave_falla(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(VARIABLE_CLAVE, raising=False)
    with pytest.raises(ClaveAusente):
        cifrar(_almacen_poblado().conexion)


def test_la_clave_no_se_escribe_en_disco(clave_efimera: str, tmp_path: Path) -> None:
    ruta = tmp_path / "eodi.sqlite.age"
    guardar_cifrada(_almacen_poblado().conexion, ruta)
    assert [p.name for p in tmp_path.iterdir()] == [ruta.name]
    assert clave_efimera.encode() not in ruta.read_bytes()


def test_admite_el_fichero_de_identidad_completo(monkeypatch: pytest.MonkeyPatch) -> None:
    identidad = pyrage.x25519.Identity.generate()
    fichero = f"# destinatario: {identidad.to_public()}\n\n{identidad}\n"
    monkeypatch.setenv(VARIABLE_CLAVE, fichero)
    conexion = descifrar(cifrar(_almacen_poblado().conexion))
    assert Almacen(conexion).incidente("EODI-2025-00001") is not None


def test_clave_local_solo_si_falta_la_variable(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    ruta = tmp_path / "clave_age.txt"
    ruta.write_text("desde-fichero", encoding="utf-8")
    monkeypatch.setenv(VARIABLE_CLAVE, "desde-variable")
    cargar_clave_local(ruta)
    assert os.environ[VARIABLE_CLAVE] == "desde-variable"
    monkeypatch.delenv(VARIABLE_CLAVE)
    cargar_clave_local(ruta)
    assert os.environ[VARIABLE_CLAVE] == "desde-fichero"


def test_se_comprime_antes_de_cifrar_y_se_leen_las_bases_sin_comprimir(
    clave_efimera: str,
) -> None:
    almacen = _almacen_poblado()
    crudo = almacen.conexion.serialize()
    comprimido = cifrar(almacen.conexion)
    assert len(comprimido) < len(crudo)
    identidad = pyrage.x25519.Identity.from_str(clave_efimera)
    antiguo = pyrage.encrypt(crudo, [identidad.to_public()])
    # La de antes del 4 de octubre de 2026, comprimida con gzip.
    con_gzip = pyrage.encrypt(gzip.compress(crudo, 6, mtime=0), [identidad.to_public()])
    # Mismo contenido (la copia a una base en memoria sin tope reescribe la cabecera).
    contenido = list(almacen.conexion.iterdump())
    for cifrado in (comprimido, antiguo, con_gzip):
        assert list(descifrar(cifrado).iterdump()) == contenido
    # La de ahora va con xz, que ocupa menos que gzip.
    assert pyrage.decrypt(comprimido, [identidad])[:6] == b"\xfd7zXZ\x00"
    assert len(comprimido) < len(con_gzip)
