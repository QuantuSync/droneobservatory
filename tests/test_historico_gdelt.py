"""Histórico de GDELT sin red: tramos, lectura con tope, parciales en git local e incorporación."""

import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from almacen import remoto
from almacen.base import Almacen
from recogida import gdelt, historico_gdelt
from recogida.descarga import Descargador
from tests.test_gdelt import TITULAR, GdeltFalso, articulo, descargador, fila

DESDE = datetime(2025, 9, 23, 10, tzinfo=UTC)


def test_tramos_iguales_y_contiguos() -> None:
    lista = historico_gdelt.tramos(DESDE, DESDE + timedelta(hours=1, minutes=15), 2)
    assert lista == [
        {"desde": "2025-09-23T10:00:00Z", "hasta": "2025-09-23T10:45:00Z"},
        {"desde": "2025-09-23T10:45:00Z", "hasta": "2025-09-23T11:15:00Z"},
    ]
    # Nunca más de 20 trabajos ni más trabajos que franjas.
    assert len(historico_gdelt.tramos(DESDE, DESDE + timedelta(days=30), 50)) == 20
    assert len(historico_gdelt.tramos(DESDE, DESDE + timedelta(minutes=30), 5)) == 2


def falso_con_franjas(n: int) -> GdeltFalso:
    falso = GdeltFalso("20250923120000")
    for i in range(n):
        franja = DESDE + gdelt.FRANJA * i
        nombre = f"{franja:%Y%m%d%H%M%S}"
        falso.poner(nombre, [], "ingles")
        falso.poner(nombre, [fila(i, TITULAR, nombre), fila(100 + i, "Stort droneshow", nombre)])
    return falso


def test_lee_el_tramo_y_se_queda_con_lo_que_pasa_el_filtro() -> None:
    falso = falso_con_franjas(3)
    tramo = historico_gdelt.leer_tramo(
        descargador(falso), DESDE, DESDE + gdelt.FRANJA * 3, float("inf")
    )
    assert (tramo.recuentos.franjas, tramo.recuentos.recibidos) == (3, 6)
    assert tramo.recuentos.descartados == 3
    assert len(tramo.articulos) == 3
    assert (tramo.fallidas, tramo.cortado_en) == ([], None)


def test_se_corta_al_agotar_el_tiempo_y_lo_dice() -> None:
    falso = falso_con_franjas(3)
    tiempos = iter([0.0, 0.0, 2.0])
    tramo = historico_gdelt.leer_tramo(
        descargador(falso), DESDE, DESDE + gdelt.FRANJA * 3, 1.0, lambda: next(tiempos)
    )
    assert tramo.recuentos.franjas == 2
    assert tramo.cortado_en == "2025-09-23T10:30:00Z"


def test_una_franja_que_no_responde_se_reintenta_y_queda_anotada() -> None:
    falso = falso_con_franjas(1)
    falso.caido = True
    tramo = historico_gdelt.leer_tramo(
        Descargador(falso, dormir=lambda _: None, pausa_minima_s=0, reintentos=0),
        DESDE,
        DESDE + gdelt.FRANJA,
        float("inf"),
    )
    assert tramo.fallidas == ["2025-09-23T10:00:00Z"]


def test_serializa_y_deserializa() -> None:
    tramo = historico_gdelt.Tramo(articulos=[articulo(1, TITULAR, 10)])
    tramo.recuentos.franjas = 4
    datos = historico_gdelt.serializar(tramo, DESDE, DESDE + gdelt.FRANJA * 4)
    cabecera, articulos = historico_gdelt.deserializar(datos)
    assert cabecera["franjas"] == 4
    assert articulos == tramo.articulos


def test_incorpora_en_orden_de_fecha_con_replicas_entre_tramos() -> None:
    almacen = Almacen.abrir()
    # El segundo tramo trae una réplica del primero: se detecta aunque lleguen desordenados.
    lotes = [[articulo(2, TITULAR + " - TV2", 9)], [articulo(1, TITULAR, 10)]]
    recuentos = historico_gdelt.incorporar(almacen, lotes)
    assert (recuentos.nuevos, recuentos.replicas) == (1, 1)
    assert [a["replicas"] for a in almacen.articulos()] == [1]


def test_cobertura_suma_los_tramos() -> None:
    cabeceras = [
        {"desde": "b", "hasta": "c", "franjas": 2, "ausentes": 1, "filas": 5,
         "fallidas": ["x"], "cortado_en": None},
        {"desde": "a", "hasta": "b", "franjas": 3, "ausentes": 0, "filas": 7,
         "fallidas": [], "cortado_en": "y"},
    ]  # fmt: skip
    resumen = historico_gdelt.cobertura(cabeceras)
    assert (resumen["desde"], resumen["hasta"], resumen["franjas"]) == ("a", "c", 5)
    assert (resumen["fallidas"], resumen["cortados"]) == (["x"], ["y"])


# --- Parciales en un repositorio git local ------------------------------------------


@pytest.fixture
def repositorio(tmp_path: Path) -> str:
    desnudo = tmp_path / "datos.git"
    desnudo.mkdir()
    subprocess.run(["git", "init", "--quiet", "--bare"], cwd=desnudo, check=True)
    return desnudo.as_uri()


def test_parciales_de_varios_trabajos(repositorio: str, tmp_path: Path) -> None:
    remoto.reiniciar_parciales("autor@ejemplo.org", "1", repositorio)
    for i in range(2):
        origen = tmp_path / f"p{i}"
        origen.write_bytes(f"parcial {i}".encode())
        assert remoto.subir_parcial(origen, f"{i}.age", "autor@ejemplo.org", repositorio) == 1
    copiados = remoto.descargar_parciales(tmp_path / "bajados", repositorio)
    assert [c.read_bytes() for c in copiados] == [b"parcial 0", b"parcial 1"]
    # Un recorrido nuevo empieza sin parciales.
    remoto.reiniciar_parciales("autor@ejemplo.org", "2", repositorio)
    assert remoto.descargar_parciales(tmp_path / "otra", repositorio) == []


def test_si_otro_trabajo_escribe_a_la_vez_se_reintenta(
    repositorio: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    remoto.reiniciar_parciales("autor@ejemplo.org", "1", repositorio)
    origen = tmp_path / "p"
    origen.write_bytes(b"mio")
    real = remoto._git
    empujes = {"n": 0}

    def git(*argumentos: str, directorio: Path | None = None, **entorno: str) -> str:
        if argumentos[0] == "push" and empujes["n"] == 0:
            # Otro trabajo sube justo antes que este.
            empujes["n"] += 1
            otro = tmp_path / "otro"
            otro.write_bytes(b"suyo")
            monkeypatch.setattr(remoto, "_git", real)
            remoto.subir_parcial(otro, "otro.age", "autor@ejemplo.org", repositorio)
            monkeypatch.setattr(remoto, "_git", git)
        return real(*argumentos, directorio=directorio, **entorno)

    monkeypatch.setattr(remoto, "_git", git)
    esperas: list[float] = []
    intentos = remoto.subir_parcial(origen, "mio.age", "autor@ejemplo.org", repositorio,
                                    esperas.append)  # fmt: skip
    assert intentos == 2
    assert esperas == [remoto.ESPERA_PARCIAL_S]
    nombres = [c.name for c in remoto.descargar_parciales(tmp_path / "b", repositorio)]
    assert nombres == ["mio.age", "otro.age"]
