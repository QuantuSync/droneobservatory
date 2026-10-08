"""Datos publicados en el almacén (recogida/publicacion.py), exportación semanal en el almacén
privado (almacen/exportaciones.py) y paso de la base a solo disco (almacen/solo_disco.py), sin
red."""

import gzip
import hashlib
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from almacen import copias, exportaciones, replica, sitio, solo_disco
from recogida import almacen_publico, publicacion
from tests.s3_falso import S3Falso

AHORA = datetime(2026, 10, 7, 14, 33, tzinfo=UTC)


class AlmacenPublico:
    """Doble de almacen_publico.subir: guarda cada objeto con sus cabeceras."""

    def __init__(self, falla: str = "") -> None:
        self.objetos: dict[str, tuple[bytes, dict[str, Any]]] = {}
        self.falla = falla

    def __call__(
        self, _almacen: object, objeto: str, cuerpo: bytes, *_: object, **kw: Any
    ) -> tuple[bool, str]:
        if self.falla and self.falla in objeto:
            return False, "HTTP 500"
        self.objetos[objeto] = (cuerpo, kw)
        return True, "subido"

    def leer(self, url: str) -> bytes:
        clave = url.split("/", 3)[3]
        cuerpo, kw = self.objetos[clave]
        return gzip.decompress(cuerpo) if kw.get("codificacion") == "gzip" else cuerpo


def publicados(carpeta: Path, ucrania: str = '{"ataques": []}') -> Path:
    carpeta.mkdir(parents=True, exist_ok=True)
    (carpeta / "incidentes.geojson").write_text('{"features": []}', encoding="utf-8")
    (carpeta / "ucrania.json").write_text(ucrania, encoding="utf-8")
    (carpeta / "prevision.json").write_text("{}", encoding="utf-8")
    (carpeta / "correcciones.json").write_text("{}", encoding="utf-8")
    return carpeta


def test_sube_lo_cambiado_el_manifiesto_al_final_y_la_instantanea_del_dia(tmp_path: Path) -> None:
    carpeta = publicados(tmp_path / "pub")
    almacen = AlmacenPublico()
    correcto, registro, cambiado = publicacion.subir(
        carpeta, AHORA, "id", "s", {}, almacen_publico.cargar(), almacen
    )
    assert correcto and cambiado
    assert list(almacen.objetos)[4] == "publicacion/manifiesto.json"
    cuerpo, kw = almacen.objetos["publicacion/ucrania.json"]
    subido = gzip.decompress(cuerpo)
    # Con la licencia dentro, como primer miembro, y en los metadatos del objeto.
    documento = json.loads(subido)
    assert list(documento) == ["licencia", "ataques"] and documento["ataques"] == []
    assert documento["licencia"]["nombre"] == "CC BY 4.0"
    assert documento["licencia"]["cita"]["en"].startswith("European Observatory of Drone Incidents")
    assert kw["metadatos"]["x-amz-meta-licencia"] == "CC BY 4.0"
    assert kw["metadatos"]["x-amz-meta-sha256"] == hashlib.sha256(subido).hexdigest()
    assert registro["ficheros"]["ucrania.json"]["sha256"] == hashlib.sha256(subido).hexdigest()
    assert "publicacion/historial/2026-10-07/ucrania.json.gz" in almacen.objetos
    assert registro["historial"] == "2026-10-07"
    # Lo que sirve el almacén es idéntico a la carpeta.
    assert publicacion.comparar(carpeta, almacen_publico.cargar(), almacen.leer) == []
    # Sin cambios, no se sube nada ni se pide reconstruir la web.
    almacen.objetos.clear()
    correcto, registro2, cambiado = publicacion.subir(
        carpeta, AHORA + timedelta(hours=1), "id", "s", registro, almacen_publico.cargar(), almacen
    )
    assert correcto and not cambiado and almacen.objetos == {}
    # Un cambio sube solo ese fichero y el manifiesto; el día siguiente, otra instantánea.
    publicados(carpeta, '{"ataques": [1]}')
    _, _, cambiado = publicacion.subir(
        carpeta, AHORA + timedelta(days=1), "id", "s", registro2, almacen_publico.cargar(), almacen
    )
    assert cambiado
    assert "publicacion/incidentes.geojson" not in almacen.objetos
    assert "publicacion/historial/2026-10-08/manifiesto.json" in almacen.objetos


def test_si_un_fichero_no_sube_no_se_sube_el_manifiesto(tmp_path: Path) -> None:
    carpeta = publicados(tmp_path / "pub")
    almacen = AlmacenPublico(falla="ucrania.json")
    correcto, registro, _ = publicacion.subir(
        carpeta, AHORA, "id", "s", {}, almacen_publico.cargar(), almacen
    )
    assert not correcto and registro == {}
    assert "publicacion/manifiesto.json" not in almacen.objetos


def test_comparar_detecta_una_diferencia(tmp_path: Path) -> None:
    carpeta = publicados(tmp_path / "pub")
    almacen = AlmacenPublico()
    publicacion.subir(carpeta, AHORA, "id", "s", {}, almacen_publico.cargar(), almacen)
    (carpeta / "ucrania.json").write_text('{"otro": 1}', encoding="utf-8")
    assert publicacion.comparar(carpeta, almacen_publico.cargar(), almacen.leer) == ["ucrania.json"]


# --- Exportación semanal en el almacén privado ------------------------------------------------
def cliente(destino: copias.Destino) -> tuple[copias.Copias, S3Falso]:
    s3 = S3Falso(destino.bucket)
    s3.existe_bucket = True
    return copias.Copias(destino, copias.Credenciales("id", "s"), s3, lambda _s: None), s3


def version(carpeta: Path) -> Path:
    carpeta.mkdir()
    cifrado = b"cifrado"
    (carpeta / "incidentes.jsonl.gz.age").write_bytes(cifrado)
    manifiesto = {
        "version": "2026.10.12",
        "ficheros": [{"nombre": "incidentes.jsonl", "cifrado": {
            "nombre": "incidentes.jsonl.gz.age", "bytes": 7,
            "sha256": hashlib.sha256(cifrado).hexdigest(),
        }}],
    }  # fmt: skip
    (carpeta / "manifiesto.json").write_text(json.dumps(manifiesto), encoding="utf-8")
    return carpeta


def test_la_exportacion_se_sube_sin_sobrescribir_y_se_lee_comprobada(tmp_path: Path) -> None:
    c, s3 = cliente(exportaciones.destino())
    origen = version(tmp_path / "v")
    exportaciones.subir(c, origen, "2026.10.12")
    claves = [clave for metodo, clave in s3.peticiones if metodo == "PUT"]
    assert claves[-1] == "exportaciones/2026.10.12/manifiesto.json"
    assert exportaciones.versiones(c) == ["2026.10.12"]
    with pytest.raises(exportaciones.ExportacionExistente):
        exportaciones.subir(c, origen, "2026.10.12")
    leida = tmp_path / "leida"
    exportaciones.bajar(c, "2026.10.12", leida)
    assert (leida / "incidentes.jsonl.gz.age").read_bytes() == b"cifrado"
    # Un fichero cambiado en el bucket no pasa.
    s3.objetos["exportaciones/2026.10.12/incidentes.jsonl.gz.age"] = (b"otro", {})
    with pytest.raises(exportaciones.ExportacionIncompleta):
        exportaciones.bajar(c, "2026.10.12", tmp_path / "otra")


# --- Paso a solo disco ------------------------------------------------------------------------
def test_solo_disco_comprueba_la_copia_y_la_segunda_copia(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    origen, _ = cliente(copias.cargar_destino())
    segunda, _ = cliente(replica.destino_replica(replica.cargar()))
    clave = f"base/horaria/{AHORA - timedelta(minutes=30):%Y-%m-%dT%H%M%SZ}.db.age"
    origen.subir(clave, b"copia")
    monkeypatch.setattr(
        copias.Copias, "restaurar", lambda self, destino, objeto: {"tamano": 1, "objeto": objeto}
    )
    correcto, hecho = solo_disco.comprobar(origen, segunda, tmp_path, AHORA)
    assert not correcto and "segunda copia no tiene" in hecho[-1]
    # Basta una copia reciente en Helsinki, aunque aún no sea la de la última recogida.
    anterior = f"base/horaria/{AHORA - timedelta(minutes=90):%Y-%m-%dT%H%M%SZ}.db.age"
    segunda.subir(anterior, b"copia")
    correcto, hecho = solo_disco.comprobar(origen, segunda, tmp_path, AHORA)
    assert correcto, hecho
    # Una copia de hace más de 2 horas no vale.
    assert not solo_disco.comprobar(origen, segunda, tmp_path, AHORA + timedelta(hours=3))[0]


def test_el_interruptor_de_la_copia_secundaria(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(sitio.VARIABLE_SECUNDARIA, "no")
    assert sitio.copia_secundaria() == sitio.SIN_SECUNDARIA
    monkeypatch.setenv(sitio.VARIABLE_SECUNDARIA, "cualquier cosa")
    assert sitio.copia_secundaria() == sitio.CON_SECUNDARIA


def test_espejo_en_un_repositorio_git_local_con_sus_etiquetas(tmp_path: Path) -> None:
    import subprocess

    c, _ = cliente(exportaciones.destino())
    exportaciones.subir(c, version(tmp_path / "v"), "2026.10.12")
    repositorio = tmp_path / "espejo"
    assert exportaciones.espejo(c, repositorio) == ["2026.10.12"]
    assert exportaciones.espejo(c, repositorio) == []
    etiquetas = subprocess.run(
        ["git", "tag", "--list"], cwd=repositorio, capture_output=True, text=True, check=True
    ).stdout.split()
    assert etiquetas == ["eodi-2026.10.12"]
    fichero = repositorio / "exportaciones" / "2026.10.12" / "incidentes.jsonl.gz.age"
    assert fichero.read_bytes() == b"cifrado"
