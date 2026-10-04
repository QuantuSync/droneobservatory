"""Base en el disco del servidor: el interruptor, la escritura segura, la escritura doble, la
vuelta atrás y la igualdad de contenido. Sin red: la rama estado es un repositorio git local y el
almacén de objetos, uno falso."""

import json
import os
import sqlite3
from datetime import datetime
from pathlib import Path

import pytest

from almacen import copias, remoto, sitio
from almacen.base import Almacen
from almacen.cifrado import abrir_cifrada, guardar_cifrada
from exportacion import publicar
from recogida import horaria
from tests.telegram_falso import CanalFalso
from tests.test_horaria import base_remota, entorno, subir_base

__all__ = ["entorno"]


@pytest.fixture
def raiz(tmp_path: Path) -> Path:
    return Path(os.environ[sitio.VARIABLE_DIRECTORIO])


@pytest.fixture
def subidas(monkeypatch: pytest.MonkeyPatch) -> list[bytes]:
    """Las copias de seguridad que se guardarían en el almacén de objetos."""
    guardadas: list[bytes] = []

    def guardar(cifrada: Path, _momento: datetime) -> dict[str, object]:
        guardadas.append(cifrada.read_bytes())
        return {"subidas": ["falsa"]}

    monkeypatch.setattr(copias, "guardar", guardar)
    return guardadas


def disco(monkeypatch: pytest.MonkeyPatch, modo: str = sitio.DISCO) -> None:
    monkeypatch.setenv(sitio.VARIABLE_MODO, modo)


def base_en_disco(raiz: Path, cursor: int = 1) -> Path:
    almacen = Almacen.abrir()
    almacen.guardar_cursor("fuerza_aerea_ua", {"ultimo_id": cursor})
    return sitio.copiar_a_disco(almacen.conexion, raiz)


def cursor_en_disco(raiz: Path) -> object:
    almacen = Almacen(sqlite3.connect(raiz / sitio.NOMBRE))
    try:
        return almacen.cursor("fuerza_aerea_ua")
    finally:
        almacen.cerrar()


# --- El interruptor -----------------------------------------------------------------------


def test_sin_interruptor_el_modo_es_github(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv(sitio.VARIABLE_MODO)
    monkeypatch.setattr(sitio, "FICHERO_MODO", tmp_path / "no-existe")
    assert sitio.modo() == sitio.GITHUB


def test_el_interruptor_es_un_fichero_de_una_palabra(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv(sitio.VARIABLE_MODO)
    fichero = tmp_path / "base_modo"
    monkeypatch.setattr(sitio, "FICHERO_MODO", fichero)
    fichero.write_text("disco\n", encoding="utf-8")
    assert sitio.modo() == sitio.DISCO
    fichero.write_text("doble", encoding="utf-8")
    assert sitio.modo() == sitio.DOBLE
    fichero.write_text("dsico", encoding="utf-8")
    with pytest.raises(ValueError, match="desconocido"):
        sitio.modo()


# --- Lectura y escritura desde disco ------------------------------------------------------


def test_se_abre_desde_disco_en_wal_sin_cargarla_en_memoria(
    raiz: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    disco(monkeypatch)
    base_en_disco(raiz)
    almacen = sitio.abrir_base(tmp_path)
    assert isinstance(almacen, sitio.AlmacenEnDisco)
    fichero = almacen.conexion.execute("PRAGMA database_list").fetchone()[2]
    assert Path(fichero).parent == raiz / sitio.TRABAJO
    assert almacen.conexion.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
    assert almacen.cursor("fuerza_aerea_ua") == {"ultimo_id": 1}
    almacen.cerrar()
    assert list((raiz / sitio.TRABAJO).iterdir()) == []


def test_guardar_sustituye_la_base_y_conserva_la_anterior(
    raiz: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    disco(monkeypatch)
    base_en_disco(raiz, cursor=1)
    almacen = sitio.abrir_disco()
    antes = sitio.marca(almacen)
    assert sitio.sin_cambios(almacen, antes)
    almacen.guardar_cursor("fuerza_aerea_ua", {"ultimo_id": 2})
    assert not sitio.sin_cambios(almacen, antes)
    sitio.guardar_disco(almacen)
    almacen.cerrar()
    assert cursor_en_disco(raiz) == {"ultimo_id": 2}
    anterior = Almacen(sqlite3.connect(raiz / sitio.ANTERIOR))
    assert anterior.cursor("fuerza_aerea_ua") == {"ultimo_id": 1}
    anterior.cerrar()
    # La base guardada no queda en modo WAL: se lee sin ficheros auxiliares.
    assert sorted(p.name for p in raiz.iterdir() if p.is_file()) == [
        sitio.ANTERIOR,
        sitio.NOMBRE,
    ]
    if os.name == "posix":
        assert (raiz / sitio.NOMBRE).stat().st_mode & 0o777 == 0o600
        assert (raiz / sitio.TRABAJO).stat().st_mode & 0o777 == 0o700


def test_una_sesion_que_falla_no_deja_nada(raiz: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    disco(monkeypatch)
    base = base_en_disco(raiz, cursor=1)
    huella = sitio.huella_fichero(base)
    almacen = sitio.abrir_disco()
    almacen.guardar_cursor("fuerza_aerea_ua", {"ultimo_id": 99})
    almacen.cerrar()  # sin guardar: como una recogida que termina con error
    assert sitio.huella_fichero(base) == huella


def test_no_se_pisa_lo_que_otra_sesion_guardo_entretanto(
    raiz: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    disco(monkeypatch)
    base_en_disco(raiz, cursor=1)
    primera, segunda = sitio.abrir_disco(), sitio.abrir_disco()
    primera.guardar_cursor("fuerza_aerea_ua", {"ultimo_id": 2})
    sitio.guardar_disco(primera)
    segunda.guardar_cursor("fuerza_aerea_ua", {"ultimo_id": 3})
    with pytest.raises(sitio.BaseCambiada):
        sitio.guardar_disco(segunda)
    primera.cerrar()
    segunda.cerrar()
    assert cursor_en_disco(raiz) == {"ultimo_id": 2}


def test_en_disco_sin_fichero_no_se_empieza_una_base_vacia(
    raiz: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    disco(monkeypatch)
    with pytest.raises(sitio.BaseAusente):
        sitio.abrir_base(tmp_path)


@pytest.mark.skipif(os.name != "posix", reason="solo en Linux se pregunta por un proceso")
def test_se_borran_las_copias_de_trabajo_de_procesos_muertos(raiz: Path) -> None:
    carpeta = raiz / sitio.TRABAJO
    carpeta.mkdir(parents=True)
    muerta = carpeta / "999999999-abcd.sqlite"
    muerta.write_bytes(b"x")
    Path(f"{muerta}-wal").write_bytes(b"x")
    viva = carpeta / f"{os.getpid()}-abcd.sqlite"
    viva.write_bytes(b"x")
    assert sitio.limpiar_trabajo(carpeta) == [muerta.name]
    assert sorted(p.name for p in carpeta.iterdir()) == [viva.name]


# --- Cifrado de ficheros e igualdad de contenido ------------------------------------------


@pytest.mark.usefixtures("entorno")
def test_la_base_cifrada_desde_disco_la_lee_el_codigo_de_siempre(
    raiz: Path, tmp_path: Path
) -> None:
    base = base_en_disco(raiz, cursor=5)
    cifrada = sitio.cifrar_fichero(base, tmp_path / "db.age")
    assert Almacen(abrir_cifrada(cifrada)).cursor("fuerza_aerea_ua") == {"ultimo_id": 5}
    vuelta = sitio.descifrar_a_fichero(cifrada.read_bytes(), tmp_path / "vuelta.sqlite")
    assert sitio.huella_fichero(vuelta) == sitio.huella_fichero(base)
    # Y al revés: la base de la rama estado (en memoria y serializada) se descifra a disco.
    memoria = Almacen(abrir_cifrada(cifrada))
    guardar_cifrada(memoria.conexion, tmp_path / "rama.age")
    desde_rama = sitio.descifrar_a_fichero(
        (tmp_path / "rama.age").read_bytes(), tmp_path / "rama.sqlite"
    )
    assert sitio.huella_fichero(desde_rama) == sitio.huella_fichero(base)


def test_la_huella_cambia_con_el_contenido(raiz: Path) -> None:
    base = base_en_disco(raiz, cursor=1)
    antes = sitio.huella_fichero(base)
    conexion = sqlite3.connect(base)
    conexion.execute("UPDATE cursores SET documento = json('{\"ultimo_id\": 2}')")
    conexion.commit()
    conexion.close()
    assert sitio.huella_fichero(base) != antes


# --- La recogida horaria en cada modo -----------------------------------------------------


def test_horaria_en_disco_guarda_en_disco_y_deja_las_dos_copias(
    entorno: tuple[str, CanalFalso, Path],
    raiz: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    subidas: list[bytes],
) -> None:
    repositorio, _, salida = entorno
    disco(monkeypatch)
    base_en_disco(raiz, cursor=1)
    assert horaria.principal(["--correo", "a@b.org", "--repositorio", repositorio]) == 0
    assert cursor_en_disco(raiz) == {"ultimo_id": 7, "fecha": "2026-09-23T05:07:00+00:00"}
    ucrania = json.loads((salida / publicar.UCRANIA).read_text(encoding="utf-8"))
    assert len(ucrania["ataques"]) == 3
    # Copia de seguridad y copia secundaria en la rama, con el mismo contenido que el disco.
    assert len(subidas) == 1
    rama = base_remota(repositorio, tmp_path)
    assert rama.cursor("fuerza_aerea_ua") == cursor_en_disco(raiz)
    assert list((raiz / sitio.TRABAJO).iterdir()) == []


def test_en_disco_un_fallo_de_la_rama_o_de_la_copia_no_para_la_recogida(
    entorno: tuple[str, CanalFalso, Path],
    raiz: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repositorio, _, salida = entorno
    disco(monkeypatch)
    base_en_disco(raiz, cursor=1)

    def falla(*_: object) -> None:
        raise remoto.RemotoFallido("git push falló con código 1")

    monkeypatch.setattr(remoto, "subir", falla)
    monkeypatch.setattr(copias, "guardar", falla)
    assert horaria.principal(["--correo", "a@b.org", "--repositorio", repositorio]) == 0
    assert cursor_en_disco(raiz) == {"ultimo_id": 7, "fecha": "2026-09-23T05:07:00+00:00"}
    assert (salida / publicar.UCRANIA).exists()


def test_horaria_doble_manda_la_rama_y_el_disco_queda_igual(
    entorno: tuple[str, CanalFalso, Path],
    raiz: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    subidas: list[bytes],
) -> None:
    repositorio, _, _ = entorno
    disco(monkeypatch, sitio.DOBLE)
    subir_base(repositorio, tmp_path, ultimo_id=1)
    assert horaria.principal(["--correo", "a@b.org", "--repositorio", repositorio]) == 0
    rama = tmp_path / "rama.sqlite"
    assert sitio.base_de_github(rama, repositorio)
    assert sitio.huella_fichero(rama) == sitio.huella_fichero(raiz / sitio.NOMBRE)
    assert len(subidas) == 1


def test_en_doble_un_fallo_del_disco_no_cambia_nada(
    entorno: tuple[str, CanalFalso, Path],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repositorio, _, _ = entorno
    disco(monkeypatch, sitio.DOBLE)
    subir_base(repositorio, tmp_path, ultimo_id=1)

    def falla(*_: object) -> Path:
        raise OSError("disco lleno")

    monkeypatch.setattr(sitio, "copiar_a_disco", falla)
    assert horaria.principal(["--correo", "a@b.org", "--repositorio", repositorio]) == 0
    assert base_remota(repositorio, tmp_path).cursor("fuerza_aerea_ua") == {
        "ultimo_id": 7,
        "fecha": "2026-09-23T05:07:00+00:00",
    }


def test_vuelta_atras_con_el_interruptor(
    entorno: tuple[str, CanalFalso, Path],
    raiz: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    subidas: list[bytes],
) -> None:
    repositorio, falso, _ = entorno
    # Doble, después disco, y de nuevo github: cada recogida parte de lo que dejó la anterior.
    disco(monkeypatch, sitio.DOBLE)
    subir_base(repositorio, tmp_path, ultimo_id=1)
    assert horaria.principal(["--correo", "a@b.org", "--repositorio", repositorio]) == 0
    disco(monkeypatch, sitio.DISCO)
    assert horaria.principal(["--correo", "a@b.org", "--repositorio", repositorio]) == 0
    disco(monkeypatch, sitio.GITHUB)
    assert horaria.principal(["--correo", "a@b.org", "--repositorio", repositorio]) == 0
    almacen = base_remota(repositorio, tmp_path)
    assert len(almacen.ataques_ucrania()) == 3
    assert almacen.cursor("fuerza_aerea_ua") == {
        "ultimo_id": 7,
        "fecha": "2026-09-23T05:07:00+00:00",
    }
    assert falso.pedidas  # las tres recogidas leyeron el canal


def test_comparar_y_pasar_de_una_a_otra(
    entorno: tuple[str, CanalFalso, Path],
    raiz: Path,
    tmp_path: Path,
) -> None:
    repositorio, _, _ = entorno
    subir_base(repositorio, tmp_path, ultimo_id=4)
    assert sitio.principal(["desde-github", "--repositorio", repositorio]) == 0
    assert sitio.principal(["comparar", "--repositorio", repositorio]) == 0
    conexion = sqlite3.connect(raiz / sitio.NOMBRE)
    conexion.execute("UPDATE cursores SET documento = json('{\"ultimo_id\": 9}')")
    conexion.commit()
    conexion.close()
    assert sitio.principal(["comparar", "--repositorio", repositorio]) == 3
    assert sitio.principal(["a-github", "--repositorio", repositorio, "--correo", "a@b.org"]) == 0
    assert base_remota(repositorio, tmp_path).cursor("fuerza_aerea_ua") == {"ultimo_id": 9}
