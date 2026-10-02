"""Reintentos entre ejecuciones: espera creciente y tope diario por sitio, sin red."""

from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest

from recogida import reintentos
from recogida.descarga import Descargador, DescargaFallida, Respuesta
from recogida.reintentos import TopeDiario

HOY = date(2026, 10, 2)


@pytest.mark.parametrize(
    ("fallos", "horas"), [(0, 0), (1, 1), (2, 2), (3, 4), (4, 8), (5, 16), (6, 24), (30, 24)]
)
def test_la_espera_crece_con_los_fallos_hasta_un_dia(fallos: int, horas: int) -> None:
    assert reintentos.espera_tras_fallos(fallos) == timedelta(hours=horas)


def test_un_rechazo_espera_el_dia_entero() -> None:
    assert reintentos.espera_tras_fallos(1, rechazo=True) == timedelta(hours=24)
    ahora = datetime(2026, 10, 2, 20, tzinfo=UTC)
    assert reintentos.siguiente_intento(ahora, 1, True) == ahora + timedelta(days=1)


def test_el_tope_diario_se_cuenta_por_sitio_y_dura_entre_ejecuciones(tmp_path: Path) -> None:
    tope = TopeDiario(tmp_path, tope=2, hoy=lambda: HOY)
    tope.anotar("favt.gov.ru")
    tope.anotar("favt.gov.ru")
    # Otra ejecución, otro objeto: lee lo anotado.
    otra = TopeDiario(tmp_path, tope=2, hoy=lambda: HOY)
    assert not otra.permite("favt.gov.ru")
    assert otra.permite("t.me")
    # Al día siguiente vuelve a empezar.
    manana = TopeDiario(tmp_path, tope=2, hoy=lambda: HOY + timedelta(days=1))
    assert manana.permite("favt.gov.ru")
    assert manana.usados("favt.gov.ru") == 0


def test_un_fichero_ilegible_no_para_la_descarga(tmp_path: Path) -> None:
    (tmp_path / "sitio.json").write_text("{roto", encoding="utf-8")
    tope = TopeDiario(tmp_path, hoy=lambda: HOY)
    assert tope.permite("sitio")
    sin_directorio = TopeDiario(tmp_path / "fichero.txt" / "x", hoy=lambda: HOY)
    (tmp_path / "fichero.txt").write_text("", encoding="utf-8")
    sin_directorio.anotar("sitio")  # no lanza
    assert sin_directorio.permite("sitio")


def test_el_tope_sale_del_entorno(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(reintentos.VARIABLE, raising=False)
    assert TopeDiario.desde_entorno() is None
    monkeypatch.setenv(reintentos.VARIABLE, str(tmp_path))
    tope = TopeDiario.desde_entorno()
    assert tope is not None
    assert tope.directorio == tmp_path


class Caido:
    """Un sitio que siempre responde 503."""

    def __init__(self) -> None:
        self.peticiones = 0

    def __call__(self, url: str, cabeceras: dict[str, str], limite_s: float) -> Respuesta:
        self.peticiones += 1
        return 503, {}, b""


def test_el_descargador_deja_de_reintentar_al_llegar_al_tope(tmp_path: Path) -> None:
    sitio, esperas = Caido(), list[float]()
    tope = TopeDiario(tmp_path, tope=6, hoy=lambda: HOY)
    descargador = Descargador(
        sitio, dormir=esperas.append, pausa_minima_s=0, reintentos=4, tope_diario=tope
    )
    with pytest.raises(DescargaFallida, match="tras 4 reintentos"):
        descargador.texto("https://caido.example/a", lambda _t: True)
    assert sitio.peticiones == 5
    # Espera creciente dentro de la ejecución.
    assert esperas == [5.0, 10.0, 20.0, 40.0]
    # Quedan 2 reintentos hoy: la siguiente ejecución hace 3 peticiones y para.
    with pytest.raises(DescargaFallida, match="tope diario"):
        descargador.texto("https://caido.example/b", lambda _t: True)
    assert sitio.peticiones == 8
    # Ya sin reintentos hoy: una sola petición.
    with pytest.raises(DescargaFallida, match="tope diario"):
        descargador.texto("https://caido.example/c", lambda _t: True)
    assert sitio.peticiones == 9
    assert tope.usados("caido.example") == 6
    assert descargador.recuentos["tope_diario"] == 2


def test_sin_tope_configurado_reintenta_como_siempre(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(reintentos.VARIABLE, raising=False)
    sitio = Caido()
    descargador = Descargador(sitio, dormir=lambda _s: None, pausa_minima_s=0, reintentos=2)
    assert descargador.tope_diario is None
    with pytest.raises(DescargaFallida):
        descargador.texto("https://caido.example/a", lambda _t: True)
    assert sitio.peticiones == 3
