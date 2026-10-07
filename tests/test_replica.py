"""Réplica en otra ubicación (almacen/replica.py) y copia horaria del archivo con las rutas
(recogida/seguimiento_archivo.py), con almacenes S3 en memoria."""

import gzip
import hashlib
import io
import json
import tarfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pyrage
import pytest

from almacen import copias, replica
from recogida import seguimiento_archivo
from tests.s3_falso import S3Falso

AHORA = datetime(2026, 10, 7, 14, 47, tzinfo=UTC)
CREDENCIALES = copias.Credenciales("id", "secreto")
IDENTIDAD = pyrage.x25519.Identity.generate()
DESTINATARIO = str(IDENTIDAD.to_public())


def cliente(destino: copias.Destino) -> tuple[copias.Copias, S3Falso]:
    s3 = S3Falso(destino.bucket)
    s3.existe_bucket = True
    return copias.Copias(destino, CREDENCIALES, s3, lambda _s: None), s3


@pytest.fixture
def almacenes() -> tuple[copias.Copias, copias.Copias, copias.Copias, S3Falso]:
    base, _ = cliente(copias.cargar_destino())
    archivo, _ = cliente(replica.destino_archivo())
    destino, s3 = cliente(replica.destino_replica(replica.cargar()))
    return base, archivo, destino, s3


def test_la_replica_esta_en_otra_ubicacion_y_es_privada() -> None:
    configuracion = replica.cargar()
    assert configuracion["ubicacion"] != copias.cargar_destino().ubicacion
    assert configuracion["ubicacion"] != replica.destino_archivo().ubicacion
    assert configuracion["destinatario_age"].startswith("age1")
    assert "público" not in configuracion["descripcion"].split(".")[0]


def test_replica_base_tal_cual_y_archivo_cifrado(
    almacenes: tuple[copias.Copias, copias.Copias, copias.Copias, S3Falso], tmp_path: Path
) -> None:
    base, archivo, destino, s3 = almacenes
    base.subir("base/horaria/2026-10-07T133000Z.db.age", b"base cifrada")
    archivo.subir("seguimiento/neptun/2026/10/neptun-2026-10-07T12.jsonl.gz", b"hora 12")
    archivo.subir("rutas/ultima.tar.gz", b"rutas v1")
    hechos = replica.replicar(base, archivo, destino, DESTINATARIO, AHORA)
    assert (hechos["base"], hechos["archivo"]) == (1, 2)
    assert s3.objetos["base/horaria/2026-10-07T133000Z.db.age"][0] == b"base cifrada"
    clave = "archivo/seguimiento/neptun/2026/10/neptun-2026-10-07T12.jsonl.gz.age"
    cifrado, meta = s3.objetos[clave]
    assert cifrado != b"hora 12"
    assert pyrage.decrypt(cifrado, [IDENTIDAD]) == b"hora 12"
    assert meta[replica.META_CLARO] == hashlib.sha256(b"hora 12").hexdigest()
    # Otra pasada no sube nada; las rutas cambiadas se sustituyen.
    puts = sum(1 for m, _ in s3.peticiones if m == "PUT")
    assert replica.replicar(base, archivo, destino, DESTINATARIO, AHORA)["archivo"] == 0
    assert sum(1 for m, _ in s3.peticiones if m == "PUT") == puts
    archivo.subir("rutas/ultima.tar.gz", b"rutas v2")
    assert replica.replicar(base, archivo, destino, DESTINATARIO, AHORA)["sustituidos"] == 1


def test_si_el_origen_se_vacia_la_replica_no_borra(
    almacenes: tuple[copias.Copias, copias.Copias, copias.Copias, S3Falso],
) -> None:
    base, archivo, destino, s3 = almacenes
    base.subir("base/horaria/2026-10-07T133000Z.db.age", b"x")
    base.subir("base/diaria/2026-10-07.db.age", b"x")
    replica.replicar(base, archivo, destino, DESTINATARIO, AHORA)
    base.borrar("base/horaria/2026-10-07T133000Z.db.age")
    base.borrar("base/diaria/2026-10-07.db.age")
    replica.replicar(base, archivo, destino, DESTINATARIO, AHORA + timedelta(hours=1))
    assert "base/diaria/2026-10-07.db.age" in s3.objetos
    # Pasada la retención de su nivel (y si no es la última de él), sí se poda.
    base.subir("base/horaria/2026-10-10T133000Z.db.age", b"y")
    replica.replicar(base, archivo, destino, DESTINATARIO, AHORA + timedelta(days=3))
    assert "base/horaria/2026-10-07T133000Z.db.age" not in s3.objetos


def test_restaurar_de_la_replica_comprueba_la_huella(
    almacenes: tuple[copias.Copias, copias.Copias, copias.Copias, S3Falso],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    base, archivo, destino, s3 = almacenes
    archivo.subir("seguimiento/indices/2026-10-06.json", b'{"dia": "2026-10-06"}')
    replica.replicar(base, archivo, destino, DESTINATARIO, AHORA)
    monkeypatch.setenv("EODI_CLAVE_AGE", str(IDENTIDAD))
    objeto = "archivo/seguimiento/indices/2026-10-06.json.age"
    resultado = replica.restaurar(destino, objeto, tmp_path / "indice.json")
    assert (tmp_path / "indice.json").read_bytes() == b'{"dia": "2026-10-06"}'
    assert resultado["sha256"] == hashlib.sha256(b'{"dia": "2026-10-06"}').hexdigest()
    s3.objetos[objeto][1][replica.META_CLARO] = "0" * 64
    with pytest.raises(OSError, match="huella"):
        replica.restaurar(destino, objeto, tmp_path / "otro.json")


# --- Copia horaria del archivo y rutas ------------------------------------------------------
class S3Archivo(S3Falso):
    def __init__(self) -> None:
        super().__init__("droneobservatory-archivo")
        self.existe_bucket = True


def copia_archivo(s3: S3Archivo) -> seguimiento_archivo.Copia:
    def enviar(peticion: object) -> seguimiento_archivo.RespuestaS3:
        r = s3(peticion)  # type: ignore[arg-type]
        return seguimiento_archivo.RespuestaS3(r.estado, r.cabeceras, r.cuerpo)

    return seguimiento_archivo.Copia(
        seguimiento_archivo.cargar_destino(), seguimiento_archivo.Credenciales("id", "s"), enviar
    )


def test_la_copia_del_archivo_es_horaria_y_lleva_las_rutas(tmp_path: Path) -> None:
    datos, rutas = tmp_path / "seguimiento", tmp_path / "rutas"
    hora = datos / "neptun" / "2026" / "10"
    hora.mkdir(parents=True)
    (hora / "neptun-2026-10-07T12.jsonl").write_text('{"via": "ws"}\n', encoding="utf-8")
    (hora / "neptun-2026-10-07T14.jsonl").write_text('{"via": "ws"}\n', encoding="utf-8")
    (rutas / "noches").mkdir(parents=True)
    (rutas / "noches" / "2026-10-06.json.gz").write_bytes(gzip.compress(b"{}"))
    s3 = S3Archivo()
    copia = copia_archivo(s3)
    resultado = seguimiento_archivo.ciclo(datos, AHORA, copia, rutas)
    # La hora 12, ya cerrada, del día en curso está en la copia; la 14, abierta, no.
    assert "seguimiento/neptun/2026/10/neptun-2026-10-07T12.jsonl.gz" in s3.objetos
    assert not any("T14" in c for c in s3.objetos)
    assert resultado["rutas"] == "ultima, diaria 2026-10-07"
    with tarfile.open(fileobj=io.BytesIO(s3.objetos["rutas/ultima.tar.gz"][0])) as paquete:
        assert paquete.getnames() == ["noches/2026-10-06.json.gz"]
    # Sin cambios, nada nuevo; con las rutas cambiadas, solo la última.
    assert seguimiento_archivo.ciclo(datos, AHORA, copia, rutas)["rutas"] == "sin cambios"
    (rutas / "comprobacion.json").write_text(json.dumps({"ok": True}), encoding="utf-8")
    assert seguimiento_archivo.ciclo(datos, AHORA, copia, rutas)["rutas"] == "ultima"
    assert seguimiento_archivo.empaquetar_rutas(rutas) == seguimiento_archivo.empaquetar_rutas(
        rutas
    )


def test_restaurar_un_dia_entero_identico(tmp_path: Path) -> None:
    datos, rutas = tmp_path / "seguimiento", tmp_path / "rutas"
    hora = datos / "neptun" / "2026" / "10"
    hora.mkdir(parents=True)
    for h in (10, 11):
        (hora / f"neptun-2026-10-06T{h}.jsonl").write_text(f'{{"h": {h}}}\n', encoding="utf-8")
    s3 = S3Archivo()
    copia = copia_archivo(s3)
    seguimiento_archivo.ciclo(datos, AHORA, copia, rutas)
    assert "seguimiento/indices/2026-10-06.json" in s3.objetos
    destino = tmp_path / "restaurado"
    resultado = seguimiento_archivo.restaurar_claves(
        copia, seguimiento_archivo.claves_dia(copia, AHORA.date() - timedelta(days=1)), destino
    )
    assert resultado == {"bajado": 3}
    for original in [*sorted(datos.rglob("*.jsonl.gz")), datos / "indices" / "2026-10-06.json"]:
        copia_local = destino / original.relative_to(datos)
        assert copia_local.read_bytes() == original.read_bytes()
