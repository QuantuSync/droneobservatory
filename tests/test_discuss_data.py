"""Paquete trimestral para Discuss Data (exportacion/discuss_data.py y recogida/discuss_data.py):
los mismos datos que la descarga abierta, sin el bloque ODbL (que va aparte con su licencia), con
README, metodología, licencia, cita y registro de cambios; uno por trimestre, guardado en el
almacén privado, un solo aviso y nunca un fallo hacia fuera."""

import io
import json
import zipfile
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import pytest

from almacen import copias
from exportacion import discuss_data as paquete
from recogida import discuss_data
from tests.s3_falso import S3Falso

FECHA = date(2026, 10, 19)
AHORA = datetime(2026, 10, 19, 4, 30, tzinfo=UTC)
ORIGEN = "https://droneobservatory.eu/datos/"
LICENCIA = {"nombre": "CC BY 4.0", "url": "https://creativecommons.org/licenses/by/4.0/"}


def _incidente(codigo: str, pais: str, estado: str, trafico: bool = False) -> dict[str, Any]:
    propiedades: dict[str, Any] = {
        "id": codigo,
        "estado": {"actual": estado},
        "presencia_dron": "confirmada",
        "lugar": {"pais": pais, "radio_km": 5},
    }
    if trafico:
        propiedades["trafico_aereo"] = {"cierre": {"resultado": "cierre_medido"}}
    return propiedades


def _ficheros(estados: dict[str, str] | None = None) -> dict[str, bytes]:
    estados = estados or {"EODI-2025-00001": "confirmado", "EODI-2025-00002": "notificado"}
    rasgos = [
        {"type": "Feature", "id": c, "geometry": {"type": "Point", "coordinates": [2.0, 41.0]},
         "properties": _incidente(c, "ES", e, trafico=c.endswith("1"))}
        for c, e in estados.items()
    ]  # fmt: skip
    mapa = {"licencia": LICENCIA, "features": rasgos, "type": "FeatureCollection",
            "unidos": {"EODI-2025-00009": "EODI-2025-00001"}}  # fmt: skip
    aproximados = {
        "licencia": LICENCIA,
        "incidentes": [_incidente("EODI-2026-00003", "MD", "confirmado")],
    }
    filas = "".join(f"{c},{e}\r\n" for c, e in estados.items())
    return {
        "incidentes.geojson": json.dumps(mapa, ensure_ascii=False, separators=(",", ":")).encode(),
        "incidentes_sin_ubicacion.json": json.dumps(aproximados, separators=(",", ":")).encode(),
        "incidentes.csv": ("id,estado\r\n" + filas).encode(),
        "resumen.json": json.dumps({"actualizado": "2026-10-19T03:17Z"}).encode(),
    }


PAGINA = (
    "<html><body><header>menú</header><main id='contenido'><h1>Methodology and open data</h1>"
    "<nav><ul><li><a href='#que'>What</a></li></ul></nav>"
    + "".join(
        f"<section><h2>Part {n}</h2><p>Text <a href='/en/help'>help</a> {n}.</p>"
        f"<dl><dt>Term</dt><dd>Meaning</dd></dl></section>"
        for n in range(8)
    )
    + "</main><footer>pie</footer></body></html>"
)


def _construir(ficheros: dict[str, bytes], fecha: date = FECHA, anterior: Any = None) -> tuple[
    bytes, dict[str, Any]
]:  # fmt: skip
    return paquete.construir(
        ficheros, PAGINA, fecha, anterior=anterior, **discuss_data.entradas()
    )  # fmt: skip


def _contenido(datos: bytes) -> dict[str, bytes]:
    with zipfile.ZipFile(io.BytesIO(datos)) as z:
        return {n.split("/", 1)[1]: z.read(n) for n in z.namelist()}


def test_el_paquete_lleva_los_datos_de_la_web_sin_el_bloque_odbl() -> None:
    ficheros = _ficheros()
    datos, resumen = _construir(ficheros)
    contenido = _contenido(datos)
    assert resumen["nombre"] == "eodi-incidentes-2026-10-19.zip"
    assert resumen["incidentes"] == 3 and resumen["paises"] == 2
    assert contenido["data/incidents.csv"] == ficheros["incidentes.csv"]
    # Sin trafico_aereo, el fichero es el de la web byte a byte.
    assert (
        contenido["data/incidents_approximate_location.json"]
        == ficheros["incidentes_sin_ubicacion.json"]
    )
    mapa = json.loads(contenido["data/incidents.geojson"])
    assert all("trafico_aereo" not in f["properties"] for f in mapa["features"])
    assert mapa["unidos"] == {"EODI-2025-00009": "EODI-2025-00001"}
    trafico = json.loads(contenido["data/air_traffic_odbl.json"])
    assert trafico["licencia"]["nombre"] == "ODbL 1.0"
    assert list(trafico["trafico_aereo"]) == ["EODI-2025-00001"]
    assert set(contenido) == {
        "README.md", "METHODOLOGY.md", "LICENSE.md", "CITATION.cff", "CHANGELOG.md",
        "data/incidents.csv", "data/incidents.geojson",
        "data/incidents_approximate_location.json", "data/air_traffic_odbl.json",
    }  # fmt: skip


def test_el_readme_dice_corte_cifras_estados_avisos_licencias_y_cita() -> None:
    contenido = _contenido(_construir(_ficheros())[0])
    readme = contenido["README.md"].decode()
    for frase in (
        "2026-10-19T03:17Z", "Incidents: 3", "Countries: 2", "Spain (2)", "Moldova (1)",
        "notificado (reported)", "no_acreditada (not substantiated)", "descartada (ruled out)",
        "only with an official statement", "https://droneobservatory.eu/en/methodology",
        "drones-europe", "`drones-spain`", "`drones-moldova`", "/en/alerts", "ODbL 1.0",
        "OpenStreetMap", "version 2026-10-19, v. 1.0, Discuss Data",
    ):  # fmt: skip
        assert frase in readme, frase
    assert "CC-BY-4.0" in contenido["CITATION.cff"].decode()
    assert 'version: "1.0"' in contenido["CITATION.cff"].decode()
    assert 'date-released: "2026-10-19"' in contenido["CITATION.cff"].decode()
    assert "First version" in contenido["CHANGELOG.md"].decode()
    metodologia = contenido["METHODOLOGY.md"].decode()
    assert metodologia.splitlines()[2] == "# Methodology and open data"
    assert "menú" not in metodologia and "pie" not in metodologia and "What" not in metodologia
    assert "[help](https://droneobservatory.eu/en/help)" in metodologia
    assert "**Term**" in metodologia


def test_el_paquete_es_determinista() -> None:
    assert _construir(_ficheros())[0] == _construir(_ficheros())[0]


def test_registro_de_cambios_frente_al_anterior() -> None:
    anterior = paquete.leer_paquete(
        _construir(_ficheros({"EODI-2025-00001": "notificado", "EODI-2025-00009": "notificado"}))[0]
    )
    datos, _ = _construir(_ficheros(), date(2027, 1, 4), (FECHA, anterior))
    cambios = _contenido(datos)["CHANGELOG.md"].decode()
    assert "EODI-2025-00002" in cambios.split("### New incidents")[1].split("###")[0]
    assert "EODI-2025-00009: merged into EODI-2025-00001" in cambios
    assert "EODI-2025-00001: notificado → confirmado" in cambios


def test_falta_un_fichero_o_no_cuadra_el_csv() -> None:
    ficheros = _ficheros()
    with pytest.raises(paquete.PaqueteInvalido):
        _construir({**ficheros, "incidentes.csv": b"id,estado\r\n"})
    with pytest.raises(paquete.PaqueteInvalido):
        _construir({k: v for k, v in ficheros.items() if k != "resumen.json"})


def test_trimestre_y_nombre() -> None:
    assert paquete.trimestre(date(2026, 10, 19)) == "2026-T4"
    assert paquete.trimestre(date(2027, 1, 4)) == "2027-T1"
    assert paquete.fecha_de_nombre("discuss-data/eodi-incidentes-2027-01-04.zip") == date(
        2027, 1, 4
    )
    assert paquete.fecha_de_nombre("discuss-data/otra.zip") is None


# --- La pasada trimestral del servidor ---------------------------------------------------------


class Web:
    def __init__(self, ficheros: dict[str, bytes], caida: bool = False) -> None:
        self.ficheros, self.caida = ficheros, caida

    def __call__(self, url: str) -> bytes:
        if self.caida:
            raise OSError("la web no responde")
        if url == paquete.METODOLOGIA_EN:
            return PAGINA.encode()
        return self.ficheros[url.removeprefix(ORIGEN)]


@pytest.fixture
def almacen() -> tuple[copias.Copias, S3Falso]:
    destino = copias.Destino(
        "nbg1", "https://nbg1.your-objectstorage.com", "privado", "discuss-data/", {}
    )
    s3 = S3Falso(destino.bucket)
    s3.existe_bucket = True
    return copias.Copias(destino, copias.Credenciales("id", "s"), s3, lambda _s: None), s3


def test_trimestral_genera_guarda_y_avisa_una_vez(
    almacen: tuple[copias.Copias, S3Falso], tmp_path: Path
) -> None:
    cliente, _ = almacen
    avisos: list[str] = []
    ruta = tmp_path / "discuss_data.json"
    estado = discuss_data.trimestral(cliente, ruta, AHORA, avisos.append, Web(_ficheros()))
    assert estado["objeto"] == "discuss-data/eodi-incidentes-2026-10-19.zip"
    assert cliente.existe(estado["objeto"])
    assert len(avisos) == 1 and "eodi-incidentes-2026-10-19.zip" in avisos[0]
    assert "X-Amz-Signature=" in avisos[0] and "X-Amz-Expires=604800" in avisos[0]
    # La semana siguiente, nada nuevo: ni paquete ni aviso.
    otra = discuss_data.trimestral(
        cliente, ruta, datetime(2026, 10, 26, 4, tzinfo=UTC), avisos.append, Web(_ficheros())
    )
    assert otra["objeto"] == estado["objeto"] and len(avisos) == 1
    assert len(discuss_data.publicados(cliente)) == 1
    # El trimestre siguiente, otro paquete con su registro de cambios.
    enero = discuss_data.trimestral(
        cliente, ruta, datetime(2027, 1, 4, 4, tzinfo=UTC), avisos.append, Web(_ficheros())
    )
    assert enero["objeto"].endswith("eodi-incidentes-2027-01-04.zip") and len(avisos) == 2
    cambios = _contenido(cliente.bajar(enero["objeto"]))["CHANGELOG.md"].decode()
    assert "previous version (2026-10-19)" in cambios


def test_trimestral_solo_avisa_del_fallo_al_segundo_intento(
    almacen: tuple[copias.Copias, S3Falso], tmp_path: Path
) -> None:
    cliente, _ = almacen
    avisos: list[str] = []
    ruta = tmp_path / "discuss_data.json"
    caida = Web(_ficheros(), caida=True)
    primero = discuss_data.trimestral(cliente, ruta, AHORA, avisos.append, caida)
    assert primero["intentos_fallidos"] == 1 and avisos == []
    segundo = discuss_data.trimestral(cliente, ruta, AHORA, avisos.append, caida)
    assert segundo["intentos_fallidos"] == 2 and len(avisos) == 1 and "2 intentos" in avisos[0]
    discuss_data.trimestral(cliente, ruta, AHORA, avisos.append, caida)
    assert len(avisos) == 1
    # Cuando vuelve, se genera y se avisa del paquete.
    bien = discuss_data.trimestral(cliente, ruta, AHORA, avisos.append, Web(_ficheros()))
    assert bien["fallo"] is None and len(avisos) == 2


def test_trimestral_nunca_falla_hacia_fuera(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("EODI_SECRETOS", str(tmp_path))
    monkeypatch.setenv("EODI_ALMACEN_CREDENCIALES", str(tmp_path / "no-existe.env"))
    monkeypatch.delenv("ALMACEN_ID", raising=False)
    assert discuss_data.principal(["trimestral"]) == 0


# --- La cita del paquete: su propia versión, y la anterior como versión previa ----------------

DOI_10 = "10.48320/F2CA4AE9-B2D3-4B0F-8F58-6CFBDE30D39F"


def _cff(fecha: date) -> str:
    entradas = discuss_data.entradas()
    return paquete.citation_cff(
        fecha, entradas["licencia"], entradas["repositorio_cff"], entradas["archivadas"]
    )


def _bloques(cff: str) -> dict[str, str]:
    """Cada bloque de primer nivel del CFF, por su clave."""
    bloques: dict[str, str] = {}
    clave = ""
    for linea in cff.splitlines():
        if linea and not linea.startswith((" ", "#")):
            clave = linea.split(":", 1)[0]
        bloques[clave] = bloques.get(clave, "") + linea + "\n"
    return bloques


def test_el_paquete_de_enero_cita_su_version_y_menciona_la_anterior() -> None:
    fecha = date(2027, 1, 4)
    assert paquete.version_del_paquete(fecha, discuss_data.entradas()["archivadas"]).numero == "1.1"
    cff = _cff(fecha)
    bloques = _bloques(cff)
    assert bloques["version"] == 'version: "1.1"\n'
    assert bloques["date-released"] == 'date-released: "2027-01-04"\n'
    # El DOI de la 1.0 solo como versión previa: ni identificador, ni DOI, ni cita preferida suyos.
    assert DOI_10 in bloques["references"] and 'version: "1.0"' in bloques["references"]
    assert "Previous version of this dataset" in bloques["references"]
    for clave in ("identifiers", "doi"):
        assert clave not in bloques
    preferida = bloques["preferred-citation"]
    assert 'version: "1.1"' in preferida and 'date-released: "2027-01-04"' in preferida
    assert DOI_10 not in preferida and "doi:" not in preferida
    assert DOI_10 not in bloques["message"]
    assert "version 2027-01-04, v. 1.1, Discuss Data" in bloques["message"]
    assert cff.count(DOI_10) == 2  # doi y url de «references»


def test_el_paquete_ya_depositado_es_esa_version_con_su_doi() -> None:
    bloques = _bloques(_cff(date(2026, 11, 2)))
    assert bloques["version"] == 'version: "1.0"\n'
    assert bloques["doi"] == f"doi: {DOI_10}\n"
    assert "references" not in bloques
    assert f"doi: {DOI_10}" in bloques["preferred-citation"]
    assert f"https://doi.org/{DOI_10}" in bloques["message"]


def test_el_readme_del_paquete_cita_su_version_y_la_anterior() -> None:
    paquete_enero = _contenido(_construir(_ficheros(), fecha=date(2027, 1, 4))[0])
    readme = paquete_enero["README.md"].decode()
    citar = readme[readme.index("## How to cite") :]
    assert "version 2027-01-04, v. 1.1, Discuss Data" in citar
    assert f"Previous version: v. 1.0 (2026-11-02), https://doi.org/{DOI_10}" in citar
    assert citar.count(DOI_10) == 1


def test_numeracion_de_las_versiones() -> None:
    def archivada(version: str, fecha: str) -> dict[str, Any]:
        return {"version": version, "fecha": fecha, "doi": f"10.1/{version}"}

    lista = [archivada("1.1", "2027-01-04"), archivada("1.0", "2026-11-02")]
    assert paquete.version_del_paquete(date(2026, 10, 1), []).numero == "1.0"
    assert paquete.version_del_paquete(date(2027, 4, 1), lista).numero == "1.2"
    enero = paquete.version_del_paquete(date(2027, 1, 4), lista)
    assert (enero.numero, enero.propia, enero.anterior) == ("1.1", lista[0], lista[1])
