"""Exportación semanal, formato 1.9.0: lo que vive fuera de la base (exportacion/seguimiento.py).
Los mensajes de seguimiento de la Fuerza Aérea, las pistas de NEPTUN como estimación con su
atribución, las rutas reconstruidas de todas las noches con su incertidumbre, los cierres medidos,
las comprobaciones, y las alertas de alerts.in.ua fuera."""

import gzip
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pyrage
import pytest

from almacen.base import Almacen
from exportacion import seguimiento, semanal
from recogida import rutas
from recogida import seguimiento as servicio_seguimiento
from tests import ejemplos
from tests.ejemplos import AHORA, VOCABULARIO_MODELOS
from tests.test_rutas import copia

NUEVOS = {
    "fuerza_aerea_seguimiento.jsonl": "fuerza_aerea_mensaje",
    "neptun_pistas.jsonl": "neptun_pista",
    "rutas_reconstruidas.jsonl": "ruta_reconstruida",
    "cierres_medidos.jsonl": "cierre_medido",
    "prevision_validacion.json": "prevision_validacion",
    "tipo_dron_validacion.json": "tipo_dron_validacion",
    "barrera_titulares.json": "barrera_titulares",
}


def lineas(contenido: bytes) -> list[Any]:
    return [json.loads(x) for x in contenido.decode("utf-8").splitlines() if x.strip()]


@pytest.fixture
def carpetas(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Path]:
    """Las carpetas de los servicios del servidor: una noche estructurada con mensajes de la
    Fuerza Aérea, una hora del flujo de NEPTUN (con un misil, que no es dron) y una de alertas."""
    datos_rutas = tmp_path / "rutas"
    datos_seguimiento = tmp_path / "seguimiento"
    publicacion = tmp_path / "publicacion"
    entrada = copia()["noches"][0]
    noche = {**entrada["noche"], "version_kpszsu": "seguimiento-kpszsu-1.0.0"}
    (datos_rutas / "noches").mkdir(parents=True)
    (datos_rutas / "noches" / f"{noche['noche']}.json.gz").write_bytes(
        gzip.compress(json.dumps(noche, ensure_ascii=False).encode("utf-8"), mtime=0)
    )
    (datos_rutas / "ataques.json").write_text(
        json.dumps({noche["noche"]: entrada["ataque"]}), encoding="utf-8"
    )
    (datos_rutas / "comprobacion.json").write_text(
        json.dumps({"pasa": False, "criterio": "c", "mediana_reconstruccion_km": 62.1,
                    "mediana_recta_km": 62.2, "noches": [
                        {"noche": noche["noche"], "puntos": 60, "distancias": [1.0]}]}),
        encoding="utf-8",
    )  # fmt: skip
    hora = datos_seguimiento / "neptun" / "2026" / "10"
    hora.mkdir(parents=True)
    flujo = [
        {"type": "upsert", "data": {
            "id": "trk_1", "type": "uav", "title": "БпЛА", "lat": 49.06, "lon": 33.42,
            "heading": 22, "updatedAt": "2026-10-05T20:06:09Z", "uncertaintyKm": 10,
            "confidenceLevel": "medium", "sourceCount": 3, "positionQuality": "approx",
            "count": 2, "trail": [{"lat": 49.0, "lon": 33.4, "t": "2026-10-05T19:05:02Z"}]}},
        {"type": "upsert", "data": {
            "id": "trk_2", "type": "missile", "lat": 47.0, "lon": 35.0,
            "updatedAt": "2026-10-05T20:00:00Z"}},
    ]  # fmt: skip
    (hora / "neptun-2026-10-05T20.jsonl").write_text(
        "".join(json.dumps({"via": "ws", "crudo": json.dumps(m)}) + "\n" for m in flujo),
        encoding="utf-8",
    )
    alertas = datos_seguimiento / "alertas_tabla" / "2026" / "10"
    alertas.mkdir(parents=True)
    (alertas / "alertas_tabla-2026-10-08T07.jsonl").write_text(
        json.dumps({"fuente": "alerts.in.ua", "id": 1, "alerta": {"location_title": "X"}}) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setenv(rutas.VARIABLE_DATOS, str(datos_rutas))
    monkeypatch.setenv("EODI_SEGUIMIENTO_DATOS", str(datos_seguimiento))
    monkeypatch.setenv(seguimiento.VARIABLE_PUBLICACION, str(publicacion))
    return {"rutas": datos_rutas, "seguimiento": datos_seguimiento, "publicacion": publicacion}


def poblado() -> Almacen:
    almacen = Almacen.abrir()
    almacen.guardar_incidente(ejemplos.incidente_minimo(), AHORA, VOCABULARIO_MODELOS)
    return almacen


def test_sin_las_carpetas_del_servidor_los_ficheros_nuevos_salen_vacios_y_validan(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(rutas.VARIABLE_DATOS, str(tmp_path / "no"))
    monkeypatch.setenv("EODI_SEGUIMIENTO_DATOS", str(tmp_path / "no"))
    monkeypatch.setenv(seguimiento.VARIABLE_PUBLICACION, str(tmp_path / "no"))
    ficheros = {f.nombre: f for f in semanal.generar(poblado())}
    for nombre, esquema_ in NUEVOS.items():
        assert ficheros[nombre].esquema == f"esquema/exportacion/{esquema_}.schema.json"
        assert ficheros[ficheros[nombre].esquema].registros == 1
    assert ficheros["neptun_pistas.jsonl"].contenido == b""
    assert json.loads(ficheros["prevision_validacion.json"].contenido)["disponible"] is False


def test_los_mensajes_de_la_fuerza_aerea_llevan_zonas_y_direcciones_con_su_origen(
    carpetas: dict[str, Path],
) -> None:
    mensajes = seguimiento.fuerza_aerea(carpetas["rutas"])
    assert mensajes
    semanal._comprobar("f", mensajes, semanal.validador_propio("fuerza_aerea_mensaje"))
    primero = mensajes[0]
    assert primero["enlace"] == f"https://t.me/kpszsu/{primero['id']}"
    assert primero["procedencia"]["avisos"]["origen"] == "oficial"
    assert primero["procedencia"]["zonas"]["origen"] == "deducido"
    assert any(a.get("zona") for m in mensajes for a in m["avisos"])


def test_las_pistas_de_neptun_son_estimacion_no_radar_y_llevan_su_atribucion(
    carpetas: dict[str, Path],
) -> None:
    [pista] = seguimiento.neptun_pistas(carpetas["seguimiento"])
    semanal._comprobar("n", [pista], semanal.validador_propio("neptun_pista"))
    assert pista["id"] == "trk_1"  # el misil no es un dron
    assert pista["procedencia"]["origen"] == "deducido"
    assert pista["procedencia"]["estimacion"] is True and pista["procedencia"]["radar"] is False
    assert pista["atribucion"]["enlace"] == "https://neptun.in.ua/"
    ultimo = pista["puntos"][-1]
    assert ultimo == {
        "t": "2026-10-05T20:06:09Z", "lat": 49.06, "lon": 33.42, "rumbo": 22, "numero": 2,
        "incertidumbre_km": 10, "confianza": "medium", "calidad_posicion": "approx",
        "confirmaciones": 3,
    }  # fmt: skip


def test_las_rutas_de_todas_las_noches_salen_como_deducido_con_su_incertidumbre(
    carpetas: dict[str, Path],
) -> None:
    lista = seguimiento.rutas_reconstruidas(carpetas["rutas"], datetime(2026, 10, 12, tzinfo=UTC))
    assert len(lista) == 1
    semanal._comprobar("r", lista, semanal.validador_propio("ruta_reconstruida"))
    [ruta] = lista
    assert ruta["publicada"] is False
    assert ruta["procedencia"]["origen"] == "deducido"
    assert all(t["precision_km"] > 0 for t in ruta["tramos"])
    assert ruta["validacion"]["pasa"] is False
    assert "distancias" not in ruta["validacion"]["noche"]
    # Una noche aún abierta en el corte no sale.
    assert (
        seguimiento.rutas_reconstruidas(carpetas["rutas"], datetime(2026, 1, 1, tzinfo=UTC)) == []
    )


def test_la_version_lleva_terceros_y_deja_fuera_las_alertas_de_alerts_in_ua(
    carpetas: dict[str, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    identidad = pyrage.x25519.Identity.generate()
    ficheros = semanal.generar(poblado())
    contenido = semanal.empaquetar(
        ficheros, "2026.10.12.1", "2026-10-12T00:00:00Z", AHORA, str(identidad.to_public())
    )
    manifiesto = json.loads(contenido[semanal.MANIFIESTO])
    assert manifiesto["version"] == "2026.10.12.1"
    assert [e["fuente"] for e in manifiesto["excluidos"]] == ["alerts.in.ua"]
    assert any(t["enlace"] == "https://neptun.in.ua/" for t in manifiesto["terceros"])
    for fichero in ficheros:
        if not fichero.nombre.startswith("esquema/"):
            assert b"alerts.in.ua" not in fichero.contenido, fichero.nombre
    assert servicio_seguimiento.directorio_datos() == carpetas["seguimiento"]


def test_la_barrera_da_el_veredicto_de_cada_incidente_activo() -> None:
    almacen = poblado()
    datos = seguimiento.barrera_titulares(almacen, almacen.incidentes())
    semanal._comprobar("b", [datos], semanal.validador_propio("barrera_titulares"))
    assert [v["incidente"] for v in datos["veredictos"]] == [i["id"] for i in almacen.incidentes()]
