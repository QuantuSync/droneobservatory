"""Aviso de silencio (recogida/silencio.py): un aviso único por caso, hasta que se resuelve."""

import json
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

import pytest

from almacen.base import Almacen
from modelo import cliente
from proceso import escalado
from recogida import silencio

AHORA = datetime(2026, 10, 20, 15, 30, tzinfo=UTC)
# El 20 de octubre de 2026 (día tranquilo): último incidente nuevo a las 10:24, última llamada de
# la extracción a las 14:17, ninguna espera.
TRANQUILO = silencio.Medidas(
    ultima_alta="2026-10-20T10:24:00Z", candidatas_24h=4, ultima_llamada="2026-10-20T14:17:03Z",
    candidatas_tras_llamada=0,
)  # fmt: skip


@pytest.fixture(autouse=True)
def estado(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv(silencio.VARIABLE_ESTADO, str(tmp_path / "silencio.json"))
    monkeypatch.setenv(cliente.VARIABLE_SALDO, str(tmp_path / "saldo_api.json"))


def test_un_dia_tranquilo_no_avisa() -> None:
    assert silencio.avisos(TRANQUILO, AHORA) == {}
    # De madrugada, tres horas sin llamadas y sin noticias nuevas tampoco.
    noche = silencio.Medidas(ultima_alta="2026-10-20T01:23:08Z", candidatas_24h=2,
                             ultima_llamada="2026-10-20T01:17:03Z")  # fmt: skip
    assert silencio.avisos(noche, datetime(2026, 10, 20, 5, 30, tzinfo=UTC)) == {}


def test_cada_caso_en_una_frase() -> None:
    medidas = silencio.Medidas(
        ultima_alta="2026-10-19T10:00:00Z", candidatas_24h=12,
        ultima_llamada="2026-10-20T11:00:00Z", candidatas_tras_llamada=5,
        esperas={
            "CAND-a": {"desde": "2026-10-20T08:00:00Z", "motivos": ["poca_seguridad: tipo"]},
            "CAND-b": {"desde": "2026-10-18T09:00:00Z",
                       "motivos": [f"{escalado.MOTIVO_DUDOSO}: el base lo descarta"]},
        },
    )  # fmt: skip
    casos = silencio.avisos(medidas, AHORA)
    assert casos["sin_incidentes"][1].startswith(
        "24 h sin incidentes nuevos con 12 noticias candidatas recogidas"
    )
    assert casos["esperas"][1] == (
        "2 candidatos esperando al experto por los topes de gasto desde 2026-10-18T09:00:00Z."
    )
    assert "más de 3 h sin llamar al modelo" in casos["sin_llamadas"][1]
    assert set(casos) == {"sin_incidentes", "esperas", "sin_llamadas", "dudoso:CAND-b"}


def _avisador(enviados: list[str]) -> Callable[[str], Callable[[str], None]]:
    return lambda titulo: enviados.append


def test_no_avisa_dos_veces_hasta_que_se_resuelve(monkeypatch: pytest.MonkeyPatch) -> None:
    almacen = Almacen.abrir()
    medidas = {"valor": silencio.Medidas(ultima_alta="2026-10-19T10:00:00Z", candidatas_24h=5)}
    monkeypatch.setattr(silencio, "medir", lambda *_: medidas["valor"])
    enviados: list[str] = []
    assert silencio.revisar(almacen, AHORA, _avisador(enviados)) == ["sin_incidentes"]
    assert silencio.revisar(almacen, AHORA, _avisador(enviados)) == []
    assert len(enviados) == 1
    # Se resuelve (un incidente nuevo) y, si vuelve a pasar, se avisa otra vez.
    medidas["valor"] = TRANQUILO
    assert silencio.revisar(almacen, AHORA, _avisador(enviados)) == []
    medidas["valor"] = silencio.Medidas(ultima_alta="2026-10-19T10:00:00Z", candidatas_24h=5)
    assert silencio.revisar(almacen, AHORA, _avisador(enviados)) == ["sin_incidentes"]


def test_sin_token_no_avisa_ni_anota(monkeypatch: pytest.MonkeyPatch) -> None:
    almacen = Almacen.abrir()
    monkeypatch.setattr(silencio, "medir", lambda *_: silencio.Medidas(
        ultima_alta="2026-10-19T10:00:00Z", candidatas_24h=5))  # fmt: skip
    assert silencio.revisar(almacen, AHORA, lambda titulo: None) == []
    assert not silencio.ruta_estado().exists()


def test_mide_de_la_base() -> None:
    almacen = Almacen.abrir()
    medidas = silencio.medir(almacen, AHORA)
    assert medidas.ultima_llamada is None and medidas.esperas == {}
    assert silencio.avisos(medidas, AHORA) == {}


def test_el_aviso_sin_incidentes_trae_lo_que_hace_falta_para_juzgarlo() -> None:
    medidas = silencio.Medidas(
        ultima_alta="2026-10-19T09:12:00Z", candidatas_24h=6,
        retenidos={"EODI-2026-00700": "verificación pendiente",
                   "EODI-2026-00701": "espera al modelo experto"},
        articulos_dias=(6, 20, 31, 18, 25, 40, 22, 19), candidatos_nuevos_24h=3, altas_24h=0,
        ultima_recogida="con_avisos", publicacion="reserva",
    )  # fmt: skip
    texto = silencio.avisos(medidas, AHORA)["sin_incidentes"][1]
    assert texto == (
        "24 h sin incidentes nuevos con 6 noticias candidatas recogidas (el último, "
        "2026-10-19T09:12:00Z). Retenidas por el control: 2 (EODI-2026-00700: verificación "
        "pendiente; EODI-2026-00701: espera al modelo experto). Artículos de drones en Europa: 6 "
        "en 24 h; mediana de los 7 días anteriores, 22. En 24 h: 3 candidatos nuevos y 0 fichas "
        "nuevas. Última recogida: código 2, con avisos. Publicación: reserva de Helsinki (el "
        "principal no respondió)."
    )
    # Sin datos del servidor, lo dice en vez de inventarlo.
    vacio = silencio.Medidas(ultima_alta="2026-10-19T09:12:00Z", candidatas_24h=6)
    assert silencio.avisos(vacio, AHORA)["sin_incidentes"][1].endswith(
        "Retenidas por el control: ninguna. Artículos de drones en Europa: sin dato. En 24 h: 0 "
        "candidatos nuevos y 0 fichas nuevas. Última recogida: sin dato. Publicación: sin dato."
    )


def test_mide_retenidas_recogida_y_publicacion_de_sus_ficheros(tmp_path: Path) -> None:
    def escribir(nombre: str, datos: object) -> None:
        (tmp_path / nombre).write_text(json.dumps(datos), encoding="utf-8")

    escribir(
        "control.json",
        {
            "retenidos": {
                "EODI-2026-00700": {
                    "desde": "2026-10-20T09:17:00Z",
                    "motivo": "verificación pendiente",
                }
            }
        },
    )
    escribir("estado.json", {"resultado": "correcta"})
    escribir("publicacion.json", {"subido": "2026-10-20T14:34:07Z"})
    escribir("publicacion_reserva.json", {"subido": "2026-10-20T13:34:44Z"})
    medidas = silencio.medir(Almacen.abrir(), AHORA)
    assert medidas.retenidos == {"EODI-2026-00700": "verificación pendiente"}
    assert medidas.ultima_recogida == "correcta" and medidas.publicacion == "principal"
    assert medidas.articulos_dias == (0,) * 8
    escribir("publicacion_reserva.json", {"subido": "2026-10-20T15:34:44Z"})
    assert silencio.medir(Almacen.abrir(), AHORA).publicacion == "reserva"
