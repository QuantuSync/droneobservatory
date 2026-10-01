import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest

from almacen.base import TABLAS_CON_HISTORIAL, Almacen, DocumentoInvalido
from esquema import Documento
from tests import ejemplos
from tests.ejemplos import AHORA, VOCABULARIO_MODELOS, instante


@pytest.fixture
def almacen() -> Iterator[Almacen]:
    a = Almacen.abrir()
    yield a
    a.cerrar()


def guardar(almacen: Almacen, documento: Documento) -> None:
    almacen.guardar_incidente(documento, AHORA, VOCABULARIO_MODELOS)


def test_guarda_y_lee_el_incidente(almacen: Almacen) -> None:
    documento = ejemplos.incidente_completo()
    guardar(almacen, documento)
    assert almacen.incidente(documento["id"]) == documento
    assert almacen.incidente("EODI-2025-99999") is None


def test_documento_invalido_no_se_guarda(almacen: Almacen) -> None:
    documento = ejemplos.incidente_completo()
    documento["lugar"]["radio_km"] = 0
    with pytest.raises(DocumentoInvalido) as error:
        guardar(almacen, documento)
    assert any(e.ruta == "lugar.radio_km" for e in error.value.errores)
    assert almacen.incidentes() == []
    assert almacen.fuentes() == {}


def test_cada_cambio_queda_en_el_historial(almacen: Almacen) -> None:
    documento = ejemplos.incidente_minimo()
    guardar(almacen, documento)
    guardar(almacen, documento)  # sin cambios: no añade historial
    documento["estado"]["historial"].append(
        {"estado": "desmentido", "fecha": instante("2025-11-05T10:00Z"), "fuente_id": "F1"}
    )
    documento["estado"]["actual"] = "desmentido"
    documento["control"]["motivo_desmentido"] = "La autoridad aclara que eran aves"
    guardar(almacen, documento)

    historial = [h for h in almacen.historial(documento["id"]) if h["tabla"] == "incidentes"]
    assert [h["operacion"] for h in historial] == ["alta", "cambio"]
    assert historial[1]["anterior"]["estado"]["actual"] == "notificado"
    assert historial[1]["nuevo"]["estado"]["actual"] == "desmentido"
    # El desmentido sigue visible como desmentido.
    guardado = almacen.incidente(documento["id"])
    assert guardado is not None
    assert guardado["estado"]["actual"] == "desmentido"


def test_afirmaciones_contradictorias_se_guardan_todas(almacen: Almacen) -> None:
    documento = ejemplos.incidente_completo()
    guardar(almacen, documento)
    guardar(almacen, documento)
    valores = [a["valor"] for a in almacen.afirmaciones(documento["id"])]
    assert valores == [10, 20]


def test_fuente_comun_sin_campos_por_incidente(almacen: Almacen) -> None:
    guardar(almacen, ejemplos.incidente_completo())
    fuente = almacen.fuentes()["F1"]
    assert "credibilidad" not in fuente
    assert "campos_respaldados" not in fuente
    assert fuente["enlace"] == "https://ejemplo.org/nota/F1"


def test_capa_ucrania_y_episodio(almacen: Almacen) -> None:
    ataque = ejemplos.ataque_completo()
    almacen.guardar_ataque_ucrania(ataque, AHORA)
    almacen.guardar_episodio(ejemplos.episodio(), AHORA)
    assert almacen.ataques_ucrania() == [ataque]
    assert almacen.regiones_ucrania(ataque["id"]) == ataque["regiones"]
    assert almacen.episodios() == [ejemplos.episodio()]


def test_ataque_invalido_no_se_guarda(almacen: Almacen) -> None:
    ataque = ejemplos.ataque_completo()
    ataque["derribados"] = {"min": 90, "max": 10}
    with pytest.raises(DocumentoInvalido):
        almacen.guardar_ataque_ucrania(ataque, AHORA)
    assert almacen.ataques_ucrania() == []


def _poblar(almacen: Almacen) -> None:
    guardar(almacen, ejemplos.incidente_completo())
    almacen.guardar_ataque_ucrania(ejemplos.ataque_completo(), AHORA)
    almacen.guardar_episodio(ejemplos.episodio(), AHORA)
    almacen.guardar_foco_termico("EODI-2025-00001", ejemplos.foco_termico())
    almacen.guardar_focos_casados("EODI-2025-00001", [{"lat": 55.6, "lon": 12.6}])
    almacen.guardar_encuentro(ejemplos.encuentro(), AHORA)
    almacen.guardar_estadistica_oficial(ejemplos.estadistica_oficial(), AHORA)
    almacen.guardar_documento_oficial(ejemplos.documento_oficial(), AHORA)
    almacen.guardar_impacto_guerra(ejemplos.impacto_guerra())
    almacen.guardar_restriccion(ejemplos.restriccion())
    almacen.guardar_mensaje_guerra(
        "https://t.me/kharkivoda/31198",
        "ova_kharkiv",
        "2025-06-01T06:45:00Z",
        "h",
        "impactos",
        {"id": 31198},
    )


@pytest.mark.parametrize(
    "tabla",
    [*TABLAS_CON_HISTORIAL, "afirmaciones", "focos_casados", "historial", "mensajes_guerra"],
)
def test_delete_prohibido(almacen: Almacen, tabla: str) -> None:
    _poblar(almacen)
    with pytest.raises(sqlite3.IntegrityError, match=r"nada se borra|solo admite inserciones"):
        almacen.conexion.execute(f"DELETE FROM {tabla}")


@pytest.mark.parametrize("tabla", ["afirmaciones", "focos_casados", "historial"])
def test_update_prohibido_en_tablas_de_solo_insercion(almacen: Almacen, tabla: str) -> None:
    _poblar(almacen)
    with pytest.raises(sqlite3.IntegrityError):
        almacen.conexion.execute(f"UPDATE {tabla} SET id = id")


def test_insert_or_replace_no_esquiva_el_bloqueo(almacen: Almacen) -> None:
    _poblar(almacen)
    with pytest.raises(sqlite3.IntegrityError, match="nada se borra"):
        almacen.conexion.execute(
            "INSERT OR REPLACE INTO incidentes (id, tipo, estado, documento) "
            "VALUES ('EODI-2025-00001', 'sobrevuelo', 'notificado', '{}')"
        )


def test_persiste_en_disco(tmp_path: Path) -> None:
    ruta = tmp_path / "eodi.sqlite"
    a = Almacen.abrir(ruta)
    guardar(a, ejemplos.incidente_minimo())
    a.cerrar()
    b = Almacen.abrir(ruta)
    assert [i["id"] for i in b.incidentes()] == ["EODI-2025-00002"]
    b.cerrar()
