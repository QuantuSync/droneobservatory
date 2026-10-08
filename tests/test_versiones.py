"""Versiones citables de los datos abiertos (recogida/versiones.py): una al mes, con su huella,
su licencia y su cita; una versión publicada nunca se sobrescribe ni se borra, y la comprobación
diaria ve cualquier cambio o falta."""

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from almacen import copias
from recogida import versiones
from tests.s3_falso import S3Falso

AHORA = datetime(2026, 10, 1, 2, 35, tzinfo=UTC)
ORIGEN = "https://droneobservatory.eu/datos/"


class Web:
    """Lo que sirve la web en /datos: el resumen y los ficheros descargables."""

    def __init__(self) -> None:
        self.actualizado = "2026-10-01T02:17Z"
        self.cambiar_una_vez = False
        self.pedidas: list[str] = []

    def __call__(self, url: str) -> bytes:
        self.pedidas.append(url)
        nombre = url.removeprefix(ORIGEN)
        if nombre == "resumen.json":
            if self.cambiar_una_vez and len(self.pedidas) > 1:
                self.cambiar_una_vez = False
                self.actualizado = "2026-10-01T03:17Z"
            return json.dumps(
                {"actualizado": self.actualizado, "incidentes": [{"id": "a"}, {"id": "b"}]}
            ).encode()
        if nombre.endswith(".csv"):
            return f"id,titulo\nEODI-2026-00001,{self.actualizado}\n".encode()
        return json.dumps({"licencia": {"nombre": "CC BY 4.0"}, "datos": nombre}).encode()


@pytest.fixture
def almacen() -> tuple[copias.Copias, S3Falso]:
    destino = copias.Destino(
        "nbg1", "https://nbg1.your-objectstorage.com", "droneobservatory-almacen", "", {}
    )
    s3 = S3Falso(destino.bucket)
    s3.existe_bucket = True
    return copias.Copias(destino, copias.Credenciales("id", "s"), s3, lambda _s: None), s3


def test_publica_la_version_del_mes_con_huellas_licencia_y_cita(
    almacen: tuple[copias.Copias, S3Falso],
) -> None:
    cliente, s3 = almacen
    hecho = versiones.generar(cliente, AHORA, Web(), dormir=lambda _s: None)
    assert hecho["hecho"] == "publicada" and hecho["version"] == "2026-10"
    conf = versiones.configuracion()
    for nombre in conf["ficheros"]:
        cuerpo, meta = s3.objetos[f"versiones/2026-10/{nombre}"]
        assert meta["x-amz-meta-licencia"] == "CC BY 4.0"
        assert meta["x-amz-meta-sha256"] == hashlib.sha256(cuerpo).hexdigest()
    # metadatos.json, el último en subir.
    subidas = [clave for metodo, clave in s3.peticiones if metodo == "PUT"]
    assert subidas[-2:] == ["versiones/2026-10/metadatos.json", "versiones/indice.json"]
    metadatos = json.loads(s3.objetos["versiones/2026-10/metadatos.json"][0])
    assert metadatos["incidentes"] == 2
    assert metadatos["licencia"]["nombre"] == "CC BY 4.0"
    assert metadatos["direccion"] == "https://droneobservatory.eu/datos/versiones/2026-10/"
    assert metadatos["cita"]["es"] == (
        "European Observatory of Drone Incidents (2026). Datos abiertos, versión 2026-10. "
        "droneobservatory.eu/datos/versiones/2026-10/. Licencia CC BY 4.0."
    )
    assert metadatos["cita"]["en"].startswith(
        "European Observatory of Drone Incidents (2026). Open"
    )
    for nombre, descrito in metadatos["ficheros"].items():
        cuerpo = s3.objetos[f"versiones/2026-10/{nombre}"][0]
        assert descrito == {"bytes": len(cuerpo), "sha256": hashlib.sha256(cuerpo).hexdigest()}
    indice = json.loads(s3.objetos["versiones/indice.json"][0])
    assert [v["version"] for v in indice["versiones"]] == ["2026-10"]
    assert indice["versiones"][0]["metadatos_sha256"] == hecho["metadatos_sha256"]


def test_una_version_publicada_no_se_vuelve_a_subir(
    almacen: tuple[copias.Copias, S3Falso],
) -> None:
    cliente, s3 = almacen
    versiones.generar(cliente, AHORA, Web(), dormir=lambda _s: None)
    antes = dict(s3.objetos)
    s3.peticiones.clear()
    web = Web()
    web.actualizado = "2026-10-15T10:17Z"
    hecho = versiones.generar(cliente, AHORA.replace(day=15), web, dormir=lambda _s: None)
    assert hecho["hecho"] == "ya_publicada"
    assert [m for m, _ in s3.peticiones] == ["HEAD"] and web.pedidas == []
    assert s3.objetos == antes
    # La regla también en el código: nada borra en versiones/.
    fuente = Path(versiones.__file__).read_text(encoding="utf-8")
    assert ".borrar(" not in fuente and "DELETE" not in fuente


def test_un_intento_a_medias_no_esta_publicado_y_se_repite(
    almacen: tuple[copias.Copias, S3Falso],
) -> None:
    cliente, s3 = almacen
    cliente.subir("versiones/2026-10/incidentes.geojson", b"a medias")
    hecho = versiones.generar(cliente, AHORA, Web(), dormir=lambda _s: None)
    assert hecho["hecho"] == "publicada"
    assert s3.objetos["versiones/2026-10/incidentes.geojson"][0] != b"a medias"


def test_los_ficheros_son_de_una_misma_version_de_los_datos(
    almacen: tuple[copias.Copias, S3Falso],
) -> None:
    cliente, s3 = almacen
    web = Web()
    web.cambiar_una_vez = True
    esperas: list[float] = []
    versiones.generar(cliente, AHORA, web, dormir=esperas.append)
    assert esperas == [60.0]
    metadatos = json.loads(s3.objetos["versiones/2026-10/metadatos.json"][0])
    assert metadatos["datos_actualizados"] == "2026-10-01T03:17Z"
    csv = s3.objetos["versiones/2026-10/incidentes.csv"][0]
    assert b"03:17Z" in csv


def test_sin_licencia_no_se_publica(almacen: tuple[copias.Copias, S3Falso]) -> None:
    cliente, s3 = almacen

    def sin_licencia(url: str) -> bytes:
        if url.endswith("resumen.json"):
            return b'{"actualizado": "x", "incidentes": []}'
        return b"id\n1\n" if url.endswith(".csv") else b'{"features": []}'

    with pytest.raises(versiones.VersionInvalida):
        versiones.generar(cliente, AHORA, sin_licencia, dormir=lambda _s: None)
    assert "versiones/2026-10/metadatos.json" not in s3.objetos


def test_la_comprobacion_ve_cambios_faltas_y_resubidas(
    almacen: tuple[copias.Copias, S3Falso], tmp_path: Path
) -> None:
    cliente, s3 = almacen
    ruta = tmp_path / "versiones.json"
    resultado = versiones.mensual(cliente, ruta, AHORA, Web())
    assert resultado["publicadas"] == ["2026-10"] and resultado["problemas"] == []
    assert resultado["completa"] is True  # el día 1, bajando todo
    registro = json.loads(ruta.read_text(encoding="utf-8"))
    etiquetas = registro["etiquetas"]
    assert versiones.comprobar(cliente, etiquetas) == []
    # Se vuelve a subir el mismo contenido: la etiqueta cambia.
    clave = "versiones/2026-10/ucrania.csv"
    cuerpo, meta = s3.objetos[clave]
    s3.objetos[clave] = (cuerpo, dict(meta))
    assert versiones.comprobar(cliente, etiquetas) == ["2026-10: ucrania.csv se ha vuelto a subir"]
    # Otro contenido.
    s3.objetos[clave] = (
        b"otro",
        {**meta, "x-amz-meta-sha256": hashlib.sha256(b"otro").hexdigest()},
    )
    assert versiones.comprobar(cliente, etiquetas) == ["2026-10: ucrania.csv ha cambiado"]
    assert versiones.comprobar(cliente, etiquetas, completa=True) == [
        "2026-10: ucrania.csv ha cambiado"
    ]
    # Borrado.
    del s3.objetos[clave]
    assert versiones.comprobar(cliente, etiquetas) == ["2026-10: falta ucrania.csv"]
    # metadatos.json cambiado.
    s3.objetos[clave] = (cuerpo, meta)
    m_clave = "versiones/2026-10/metadatos.json"
    m_cuerpo, m_meta = s3.objetos[m_clave]
    nuevo = m_cuerpo.replace(b'"incidentes": 2', b'"incidentes": 3')
    s3.objetos[m_clave] = (
        nuevo,
        {**m_meta, "x-amz-meta-sha256": hashlib.sha256(nuevo).hexdigest()},
    )
    assert versiones.comprobar(cliente, etiquetas) == ["2026-10: metadatos.json ha cambiado"]


def test_la_vigilancia_avisa_si_el_dia_1_no_se_genera() -> None:
    sin_nada: dict[str, object] = {}
    temprano = datetime(2026, 11, 1, 3, 0, tzinfo=UTC)
    tarde = datetime(2026, 11, 1, 7, 0, tzinfo=UTC)
    assert versiones.problemas_para_vigilancia(sin_nada, temprano) == []
    [frase] = versiones.problemas_para_vigilancia(sin_nada, tarde)
    assert "2026-11" in frase and "no se ha generado" in frase
    al_dia = {"publicadas": ["2026-11", "2026-10"], "comprobada": "2026-11-01T02:40:00Z"}
    assert versiones.problemas_para_vigilancia(al_dia, tarde) == []
    viejo = {**al_dia, "comprobada": "2026-10-28T02:40:00Z"}
    assert "no se comprueban" in versiones.problemas_para_vigilancia(viejo, tarde)[0]
    cambiada = {**al_dia, "problemas": ["2026-10: ucrania.csv ha cambiado"]}
    assert "ha cambiado" in versiones.problemas_para_vigilancia(cambiada, tarde)[0]
