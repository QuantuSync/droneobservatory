"""La red de seguridad de la publicación (exportacion/version_buena.py, docs/cerrojo.md): una ficha
que la auditoría marca en P, R, V, W o X sale en su última versión buena; sin ella, como en la
publicación anterior; si nunca se publicó, no sale. Nada de esto para la publicación."""

import copy
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from almacen.base import Almacen
from esquema import Documento
from exportacion import publicar, version_buena
from proceso import auditoria_fichas, protegido
from recogida import vigilancia, visitas
from tests import ejemplos
from tests.ejemplos import VOCABULARIO_MODELOS
from tests.test_cerrojo import ficha, version_mala

AHORA = datetime(2026, 10, 13, 14, 17, tzinfo=UTC)
ID = "EODI-2026-09600"
TITULO_BUENO = {"es": "Dron sobre el aeropuerto de Núremberg", "en": "Drone over Nuremberg airport"}
TITULO_MALO = {"es": "Posible dron en Núremberg", "en": "Possible drone in Nuremberg"}


# El cierre publicado: 30 minutos en la versión buena, 45 en la que marca la auditoría.
BUENO, MALO = 30, 45


def _con_cierre(documento: Documento, minutos: int) -> Documento:
    documento = copy.deepcopy(documento)
    documento["consecuencias"] = {
        "cierre": {"valor": "si", "minutos": {"min": minutos, "max": minutos}}
    }
    return documento


def _base(minutos: int) -> Almacen:
    """Una ficha mínima que se publica (sin punto, en su región)."""
    almacen = Almacen.abrir()
    documento = ejemplos.incidente_minimo()
    documento["id"] = ID
    documento["lugar"] = {"pais": "BE", "nivel": "region", "region": "Limburg"}
    almacen.guardar_incidente(_con_cierre(documento, minutos), AHORA, VOCABULARIO_MODELOS)
    return almacen


def _cambiar(almacen: Almacen, minutos: int) -> None:
    documento = almacen.incidente(ID)
    assert documento is not None
    almacen.guardar_incidente(_con_cierre(documento, minutos), AHORA, VOCABULARIO_MODELOS)


def _publicada(directorio: Path) -> Documento | None:
    for nombre, lista in version_buena.LISTAS.items():
        datos = json.loads((directorio / nombre).read_text(encoding="utf-8"))
        for entrada in datos[lista]:
            if version_buena._id(entrada) == ID:
                return dict(entrada)
    return None


def _minutos(entrada: Documento | None) -> Any:
    assert entrada is not None
    return (entrada.get("properties") or entrada)["consecuencias"]["cierre"]["minutos"]["max"]


@pytest.mark.parametrize("comprobacion", protegido.AUDITORIA)
def test_la_ficha_marcada_sale_en_su_ultima_version_buena(
    comprobacion: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    salida = tmp_path / "publicacion"
    almacen = _base(BUENO)
    monkeypatch.setattr(version_buena, "marcadas", lambda *_: {})
    publicar.publicar(almacen, AHORA, salida)
    assert _minutos(_publicada(salida)) == BUENO
    # La base cambia y la auditoría la marca: sale lo de antes.
    _cambiar(almacen, MALO)
    monkeypatch.setattr(version_buena, "marcadas", lambda *_: {ID: [comprobacion]})
    publicar.publicar(almacen, AHORA, salida)
    assert _minutos(_publicada(salida)) == BUENO
    (sustituida,) = (almacen.cursor(version_buena.CURSOR) or {})["sustituidas"]
    assert sustituida["id"] == ID and sustituida["comprobaciones"] == [comprobacion]
    assert sustituida["origen"] == version_buena.BUENA
    assert "consecuencias" in sustituida["diferencias"]
    # Sin marca vuelve a salir lo de la base, y esa pasa a ser la versión buena.
    monkeypatch.setattr(version_buena, "marcadas", lambda *_: {})
    publicar.publicar(almacen, AHORA, salida)
    assert _minutos(_publicada(salida)) == MALO


@pytest.mark.parametrize(
    ("comprobacion", "entrada"),
    [
        ("P", ID),
        ("R", f"{ID} presencia_dron: confirmada ≠ no_confirmada"),
        ("V", f"EODI-2026-09601→{ID}"),
        ("W", f"{ID} inicio"),
        ("X", f"{ID} lugar"),
    ],
)  # fmt: skip
def test_cada_comprobacion_marca_la_ficha_publicada(
    comprobacion: str, entrada: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    resultado: dict[str, list[str]] = {c: [] for c in auditoria_fichas.COMPROBACIONES}
    resultado[comprobacion] = [entrada]
    monkeypatch.setattr(auditoria_fichas, "auditar", lambda *_a, **_k: resultado)
    assert version_buena.marcadas(Almacen.abrir(), AHORA) == {ID: [comprobacion]}


def test_la_auditoria_real_marca_un_cambio_sin_permiso() -> None:
    # X: el número de drones cambia sin fuente nueva, en «observar» (pasa y se apunta).
    almacen = Almacen.abrir()
    almacen.guardar_incidente(ficha(ID), AHORA, VOCABULARIO_MODELOS)
    documento = almacen.incidente(ID)
    assert documento is not None
    almacen.guardar_incidente(version_mala(documento, "drones"), AHORA, VOCABULARIO_MODELOS)
    assert "X" in version_buena.marcadas(almacen, datetime.now(UTC)).get(ID, [])


def _entrada(titulo: dict[str, str]) -> Documento:
    return {"type": "Feature", "id": ID, "geometry": None, "properties": {"id": ID,
            "titulo": titulo}}  # fmt: skip


def test_sin_version_buena_sale_como_en_la_publicacion_anterior() -> None:
    generados = {publicar.INCIDENTES: {"features": [_entrada(TITULO_MALO)]}}
    anteriores: dict[str, Documento | None] = {
        publicar.INCIDENTES: {"features": [_entrada(TITULO_BUENO)]}
    }
    salida, buenas, (s,) = version_buena.sustituir(generados, anteriores, {ID: ["X"]}, {})
    assert salida[publicar.INCIDENTES]["features"] == [_entrada(TITULO_BUENO)]
    assert s["origen"] == version_buena.ANTERIOR and ID not in buenas


def test_la_que_nunca_se_publico_no_sale_y_se_apunta() -> None:
    generados = {publicar.INCIDENTES: {"features": [_entrada(TITULO_MALO)]}}
    salida, _, (s,) = version_buena.sustituir(generados, {}, {ID: ["W"]}, {})
    assert salida[publicar.INCIDENTES]["features"] == []
    assert s["origen"] == version_buena.NINGUNA


def test_la_version_buena_puede_estar_en_el_otro_fichero() -> None:
    # Una ficha con punto que pierde el punto: su versión buena vuelve al mapa.
    sin_punto: Documento = {"id": ID, "titulo": TITULO_MALO}
    generados: dict[str, Documento] = {publicar.INCIDENTES: {"features": []},
                 publicar.SIN_UBICACION: {"incidentes": [sin_punto]}}  # fmt: skip
    buenas = {ID: {"fichero": publicar.INCIDENTES, "entrada": _entrada(TITULO_BUENO)}}
    salida, _, (s,) = version_buena.sustituir(generados, {}, {ID: ["R"]}, buenas)
    assert salida[publicar.INCIDENTES]["features"] == [_entrada(TITULO_BUENO)]
    assert salida[publicar.SIN_UBICACION]["incidentes"] == []
    assert s["origen"] == version_buena.BUENA


def test_si_la_red_falla_se_publica_lo_de_la_base(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def falla(*_: Any) -> dict[str, list[str]]:
        raise RuntimeError("auditoría rota")

    monkeypatch.setattr(version_buena, "marcadas", falla)
    salida = tmp_path / "publicacion"
    publicar.publicar(_base(MALO), AHORA, salida)
    assert _minutos(_publicada(salida)) == MALO
    monkeypatch.setattr(version_buena, "marcadas", lambda *_: {ID: ["X"]})
    monkeypatch.setattr(version_buena, "sustituir", falla)
    publicar.publicar(_base(BUENO), AHORA, salida)
    assert _minutos(_publicada(salida)) == BUENO


def test_la_vigilancia_abre_la_incidencia_con_la_ficha_la_comprobacion_y_la_diferencia() -> None:
    estado = {"cerrojo": {"modo": "observar", "version_anterior": [{
        "id": ID, "comprobaciones": ["X"], "origen": "buena",
        "diferencias": {"titulo": ['{"es": "Dron"}', '{"es": "Posible dron"}']},
    }]}}  # fmt: skip
    (problema,) = vigilancia.problemas_del_cerrojo(estado)
    assert problema["id"] == "version_anterior" and "version_anterior" in vigilancia.SIN_GRACIA
    assert ID in problema["frase"] and "(X;" in problema["frase"]
    assert "titulo" in problema["frase"] and "Posible dron" in problema["frase"]


def test_el_resumen_cuenta_las_fichas_en_su_version_anterior() -> None:
    lineas = visitas.lineas_cerrojo(
        {"modo": "aplicar", "retenidos": [], "guardados_fallidos": [], "version_anterior": [ID]}
    )
    assert "  Fichas publicadas en su versión anterior: 1" in lineas
    assert f"  - {ID}" in lineas
