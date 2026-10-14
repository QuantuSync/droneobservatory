"""Copias archivadas de las fuentes y enlaces caídos (recogida/archivo_web.py, tabla
copias_archivadas): sin red, con Internet Archive y los medios simulados."""

import json
import sqlite3
import time
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from almacen.base import Almacen
from recogida import archivo_web as aw

AHORA = datetime(2026, 10, 13, 9, 0, tzinfo=UTC)
ENLACE = "https://news.example.md/ro/story/62650046"
COPIA = f"https://web.archive.org/web/20260909192419/{ENLACE}"


def _instante(momento: datetime) -> str:
    return momento.strftime("%Y-%m-%dT%H:%M:%SZ")


def _comprobacion(estado: str, momento: datetime, motivo: str = "") -> dict[str, Any]:
    return aw.Comprobacion(estado, motivo).documento(momento)


# --- Comprobación de enlaces ---------------------------------------------------------------


@pytest.mark.parametrize(
    ("original", "destino", "portada"),
    [
        ("https://a.ro/stiri/dron-123", "https://a.ro/", True),
        ("https://a.ro/stiri/dron-123", "https://a.ro/ro/", True),
        ("https://a.ro/stiri/dron-123", "https://a.ro/404?u=x", True),
        ("https://a.ro/stiri/dron-123", "https://a.ro/stiri/dron-123", False),
        ("https://a.ro/stiri/dron-123", "https://www.a.ro/stiri/dron-123-actualizada", False),
        ("https://a.ro/", "https://a.ro/", False),
    ],
)
def test_redireccion_a_la_portada(original: str, destino: str, portada: bool) -> None:
    assert aw.es_portada(original, destino) is portada


def test_caido_solo_tras_dos_fallos_separados_una_hora() -> None:
    uno = _comprobacion(aw.FALLO, AHORA - timedelta(hours=2), aw.NO_ENCONTRADO)
    assert not aw.caido([uno])
    seguido = _comprobacion(aw.FALLO, AHORA - timedelta(hours=1, minutes=50), aw.NO_ENCONTRADO)
    assert not aw.caido([uno, seguido])
    despues = _comprobacion(aw.FALLO, AHORA, aw.SIN_DOMINIO)
    assert aw.caido([uno, despues])
    # Un bloqueo (403 a los centros de datos) no dice nada del artículo.
    assert not aw.caido([uno, _comprobacion(aw.BLOQUEADO, AHORA)])
    # Vuelve a responder: deja de estar caído.
    assert not aw.caido([uno, despues, _comprobacion(aw.VIVO, AHORA + timedelta(days=7))])


# --- Internet Archive ----------------------------------------------------------------------


def _ia(
    respuestas: Callable[[str], tuple[int, dict[str, str], bytes]],
) -> tuple[aw.InternetArchive, list[str]]:
    pedidas: list[str] = []

    def transporte(url: str, _limite: float) -> tuple[int, dict[str, str], bytes]:
        pedidas.append(url)
        return respuestas(url)

    return aw.InternetArchive(transporte, dormir=lambda _s: None), pedidas


def _disponible(marca: str, estado: str = "200") -> bytes:
    cercana = {"available": True, "url": f"http://web.archive.org/web/{marca}/{ENLACE}",
               "timestamp": marca, "status": estado}  # fmt: skip
    return json.dumps({"archived_snapshots": {"closest": cercana}}).encode()


def test_copia_mas_cercana_a_la_fecha_de_la_fuente() -> None:
    internet, pedidas = _ia(lambda _u: (200, {}, _disponible("20260909192419")))
    copia = internet.copia_cercana(ENLACE, datetime(2026, 9, 10, tzinfo=UTC))
    assert copia == {"enlace": COPIA, "fecha": "2026-09-09T19:24:19Z"}
    assert "timestamp=20260910000000" in pedidas[0]
    assert len(pedidas) == 1


def test_una_copia_de_un_error_no_vale_y_el_indice_solo_si_falla() -> None:
    def respuestas(url: str) -> tuple[int, dict[str, str], bytes]:
        if url.startswith(aw.CDX):
            return (
                200,
                {},
                json.dumps([["timestamp", "statuscode"], ["20250101120000", "200"]]).encode(),
            )
        return 200, {}, _disponible("20260101000000", "404")

    internet, pedidas = _ia(respuestas)
    assert internet.copia_cercana(ENLACE, AHORA) is None
    assert len(pedidas) == 1
    copia = internet.copia_cercana(ENLACE, AHORA, indice=True)
    assert copia is not None and copia["fecha"] == "2025-01-01T12:00:00Z"


def test_internet_archive_que_no_responde_corta_la_ronda() -> None:
    internet, pedidas = _ia(lambda _u: (429, {}, b""))
    with pytest.raises(aw.ArchivoNoResponde):
        internet.copia_cercana(ENLACE, AHORA)
    assert len(pedidas) == aw.CORTES_PARA_PARAR


def test_pedir_archivo_da_la_copia_hecha() -> None:
    destino = {"X-Destino": f"https://web.archive.org/web/20261013090102/{ENLACE}"}
    internet, pedidas = _ia(lambda _u: (200, destino, b""))
    assert internet.pedir_archivo(ENLACE) == {
        "enlace": f"https://web.archive.org/web/20261013090102/{ENLACE}",
        "fecha": "2026-10-13T09:01:02Z",
    }
    assert pedidas == [aw.GUARDAR + ENLACE]


# --- Tareas y ronda -------------------------------------------------------------------------


def test_tareas_de_una_ronda() -> None:
    hace = AHORA - timedelta(hours=3)
    estado: dict[str, dict[str, Any]] = {
        "https://a/nuevo": {"fecha": "2026-10-12T00:00:00Z"},
        "https://a/fallo": {"fecha": "2026-10-01T00:00:00Z", "buscada": _instante(hace),
                            "comprobaciones": [_comprobacion(aw.FALLO, hace, aw.NO_ENCONTRADO)]},
        "https://a/viejo": {"fecha": "2026-01-01T00:00:00Z", "copia": {"enlace": COPIA},
                            "comprobaciones": [_comprobacion(aw.VIVO, AHORA - timedelta(days=8))]},
        "https://a/vivo": {"fecha": "2026-10-10T00:00:00Z", "buscada": _instante(hace),
                           "comprobaciones": [_comprobacion(aw.VIVO, hace)]},
        "https://a/pedido": {"fecha": "2026-10-10T00:00:00Z", "buscada": _instante(hace),
                             "pedido": _instante(AHORA - timedelta(minutes=30)),
                             "comprobaciones": [_comprobacion(aw.VIVO, hace)]},
    }  # fmt: skip
    tareas = aw.tareas(estado, AHORA)
    assert tareas.comprobar == ["https://a/nuevo", "https://a/fallo", "https://a/viejo"]
    assert tareas.buscar == ["https://a/nuevo"]
    assert tareas.pedir == ["https://a/vivo"]


def _publicacion(carpeta: Path, enlaces: list[str]) -> None:
    fecha = {"valor": "2026-09-10T08:00:00Z", "precision": "minuto"}
    fuentes = [{"id": f"f{i}", "enlace": e, "fecha": fecha} for i, e in enumerate(enlaces)]
    geo = {
        "type": "FeatureCollection",
        "features": [{"type": "Feature", "properties": {"fuentes": fuentes}}],
    }
    (carpeta / "incidentes.geojson").write_text(json.dumps(geo), encoding="utf-8")
    (carpeta / "incidentes_sin_ubicacion.json").write_text(
        json.dumps({"incidentes": []}), encoding="utf-8"
    )


@pytest.mark.parametrize("lenta_s", [0.0, 0.3])
def test_ronda_completa_y_lo_que_va_a_la_base(tmp_path: Path, lenta_s: float) -> None:
    """Con comprobaciones lentas (lenta_s), el enlace vivo se pide igual: las peticiones de
    archivo esperan a las comprobaciones, que van en otros hilos."""
    publicacion, datos = tmp_path / "pub", tmp_path / "datos"
    publicacion.mkdir()
    vivo, muerto = "https://a.ro/stiri/vivo-1", "https://b.md/ro/story/1"
    _publicacion(publicacion, [vivo, muerto])

    def respuestas(url: str) -> tuple[int, dict[str, str], bytes]:
        if url.startswith(aw.GUARDAR):
            return 200, {"X-Destino": f"https://web.archive.org/web/20261013090000/{vivo}"}, b""
        if "b.md" in url:
            return 200, {}, _disponible("20260911000000")
        return 200, {}, b'{"archived_snapshots": {}}'

    internet, _ = _ia(respuestas)
    reloj = [AHORA]
    estados = {
        vivo: aw.Comprobacion(aw.VIVO, "", 200),
        muerto: aw.Comprobacion(aw.FALLO, aw.NO_ENCONTRADO, 404),
    }

    def comprobador(enlace: str) -> aw.Comprobacion:
        time.sleep(lenta_s)
        return estados[enlace]

    recuento = aw.ronda(
        publicacion,
        datos,
        1,
        archivo=internet,
        comprobador=comprobador,
        reloj=lambda: reloj[0],
    )
    assert recuento["nuevos"] == 2
    assert recuento["copias_encontradas"] == 1 and recuento["archivados"] == 1
    estado = aw.leer_estado(datos)
    assert estado[vivo]["copia"]["fecha"] == "2026-10-13T09:00:00Z"
    assert not aw.caido(estado[muerto]["comprobaciones"])
    # Una hora después, el segundo fallo lo da por caído.
    reloj[0] = AHORA + timedelta(hours=1, minutes=5)
    aw.ronda(
        publicacion,
        datos,
        1,
        archivo=internet,
        comprobador=estados.__getitem__,
        reloj=lambda: reloj[0],
    )
    estado = aw.leer_estado(datos)
    assert aw.caido(estado[muerto]["comprobaciones"])
    assert aw.resumen(datos)["caidos_con_copia"] == 1

    almacen = Almacen.abrir()
    assert aw.paso_horario(almacen, reloj[0], datos) == 2
    assert aw.paso_horario(almacen, reloj[0], datos) == 0
    vigentes = almacen.copias_archivadas()
    assert vigentes[muerto] == {
        "caido": True,
        "copia": {
            "enlace": f"https://web.archive.org/web/20260911000000/{muerto}",
            "fecha": "2026-09-11T00:00:00Z",
        },
    }
    # Sin la carpeta del servicio, la recogida no apunta nada y sigue.
    assert aw.paso_horario(almacen, reloj[0], tmp_path / "no-existe") == 0


def test_la_tabla_no_admite_cambios_ni_borrados() -> None:
    almacen = Almacen.abrir()
    almacen.guardar_copias_archivadas({ENLACE: {"caido": True}}, "2026-10-13T09:00:00Z")
    almacen.guardar_copias_archivadas({ENLACE: {"caido": False}}, "2026-10-13T10:00:00Z")
    assert almacen.copias_archivadas() == {ENLACE: {"caido": False}}
    for orden in ("UPDATE copias_archivadas SET fecha = 'x'", "DELETE FROM copias_archivadas"):
        with pytest.raises(sqlite3.IntegrityError):
            almacen.conexion.execute(orden)


def test_fuentes_publicadas_con_su_copia() -> None:
    fuentes = [{"id": "a", "enlace": ENLACE}, {"id": "b", "enlace": "https://otro/x"}]
    copias = {ENLACE: {"caido": True, "copia": {"enlace": COPIA, "fecha": "2026-09-09T19:24:19Z"}}}
    [incidente] = aw.con_copias_archivadas([{"id": "EODI-2026-00001", "fuentes": fuentes}], copias)
    assert incidente["fuentes"][0]["copia_archivada"]["enlace"] == COPIA
    assert incidente["fuentes"][0]["enlace_caido"] is True
    assert incidente["fuentes"][1] == {"id": "b", "enlace": "https://otro/x"}
    assert fuentes[0] == {"id": "a", "enlace": ENLACE}


def test_un_pedido_que_tarda_no_es_un_corte() -> None:
    def lento(_url: str) -> tuple[int, dict[str, str], bytes]:
        raise TimeoutError

    internet, pedidas = _ia(lento)
    for _ in range(aw.CORTES_PARA_PARAR + 1):
        assert internet.pedir_archivo(ENLACE) is None
    assert internet.recuentos["pedidos_en_curso"] == aw.CORTES_PARA_PARAR + 1
    assert len(pedidas) == aw.CORTES_PARA_PARAR + 1


def test_el_indice_caido_no_corta_la_ronda() -> None:
    def respuestas(url: str) -> tuple[int, dict[str, str], bytes]:
        if url.startswith(aw.CDX):
            return 503, {}, b"Temporarily Offline"
        return 200, {}, b'{"archived_snapshots": {}}'

    internet, _ = _ia(respuestas)
    for _ in range(aw.CORTES_PARA_PARAR + 1):
        assert internet.copia_cercana(ENLACE, AHORA, indice=True) is None
    assert internet.recuentos["indice_sin_respuesta"] == aw.CORTES_PARA_PARAR + 1
