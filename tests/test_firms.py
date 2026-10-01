"""Recogida de NASA FIRMS sin red: lectura de los CSV, ficheros en disco, ventana de 3 horas,
histórico reanudable, clave fuera de los registros y fallos que no paran la recogida."""

import gzip
import logging
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest

from almacen.base import Almacen
from proceso import focos_termicos as ft
from recogida import firms, horaria
from recogida.descarga import Descargador, Respuesta
from recogida.estado import LEIDA, NO_LEIDA

CLAVE = "0123456789abcdef0123456789abcdef"
AHORA = datetime(2026, 9, 30, 18, 20, tzinfo=UTC)
# CSV recortados de respuestas reales de la API de área (VIIRS SP y NRT, MODIS SP).
FIXTURES = Path(__file__).parent / "fixtures" / "firms"

VIIRS_SP = (FIXTURES / "viirs_noaa20_sp.csv").read_bytes()
VIIRS_NRT = (FIXTURES / "viirs_noaa21_nrt.csv").read_bytes()
MODIS_SP = (FIXTURES / "modis_sp.csv").read_bytes()
VACIO_VIIRS = VIIRS_NRT.splitlines(keepends=True)[0]

# Objetivos atacados con drones que tienen que caer dentro del rectángulo descargado.
OBJETIVOS = {
    "Ust-Luga": (59.68, 28.32),
    "Primorsk": (60.36, 28.66),
    "Kirishi": (59.45, 32.02),
    "Tuapse": (44.10, 39.08),
    "Novorossiysk": (44.72, 37.80),
    "Volgogrado": (48.51, 44.60),
    "Sarátov": (51.45, 45.94),
    "Kstovo": (56.10, 44.16),
    "Riazán": (54.56, 39.75),
    "Nizhnekamsk": (55.63, 51.82),
    "Ufá": (54.82, 56.07),
    "Perm": (58.01, 56.25),
    "Oremburgo": (51.77, 55.10),
    "Engels": (51.44, 46.09),
    "Sebastopol (Crimea)": (44.62, 33.53),
    "Odesa": (46.48, 30.72),
    "Leópolis": (49.84, 24.03),
    "Uzhgorod": (48.62, 22.30),
    "Chisináu (Moldavia)": (47.01, 28.86),
    "Galați (Rumanía)": (45.44, 28.05),
}


# --- Lectura ---------------------------------------------------------------------------


def test_lee_un_csv_viirs_sp() -> None:
    focos = firms.leer_csv(VIIRS_SP, "VIIRS_NOAA20_SP")
    assert len(focos) == 3
    primero = focos[0]
    assert (primero.lat, primero.lon) == (55.25854, 38.74166)
    assert primero.instante == datetime(2025, 8, 10, 1, 2, tzinfo=UTC)
    assert (primero.satelite, primero.instrumento) == ("NOAA-20", "VIIRS")
    assert (primero.confianza, primero.frp, primero.fuente) == ("n", 0.88, "VIIRS_NOAA20_SP")
    assert focos[1].instante == datetime(2025, 8, 10, 23, 18, tzinfo=UTC)
    assert focos[2].baja_confianza() and not focos[1].baja_confianza()


def test_lee_un_csv_viirs_nrt_sin_columna_de_tipo() -> None:
    (foco,) = firms.leer_csv(VIIRS_NRT, "VIIRS_NOAA21_NRT")
    assert foco.satelite == "NOAA-21"
    assert foco.instante == datetime(2025, 8, 10, 0, 11, tzinfo=UTC)


def test_lee_un_csv_modis_y_salta_filas_que_no_entiende() -> None:
    focos = firms.leer_csv(MODIS_SP, "MODIS_SP")
    assert [(f.satelite, f.instrumento, f.confianza) for f in focos] == [
        ("Aqua", "MODIS", "69"),
        ("Terra", "MODIS", "25"),
    ]
    # MODIS: por debajo de 30 es baja confianza.
    assert [f.baja_confianza() for f in focos] == [False, True]


def test_satelite_de_cada_producto_viirs() -> None:
    fila = VIIRS_NRT
    assert firms.leer_csv(fila, "VIIRS_SNPP_NRT")[0].satelite == "Suomi NPP"
    assert firms.leer_csv(fila, "VIIRS_NOAA20_NRT")[0].satelite == "NOAA-20"


# --- Ficheros en disco ------------------------------------------------------------------


def test_una_respuesta_de_varios_dias_se_guarda_por_dia(tmp_path: Path) -> None:
    datos = firms.Datos(tmp_path)
    focos = datos.guardar_respuesta("VIIRS_NOAA20_SP", date(2025, 8, 10), 3, VIIRS_SP)
    assert focos == 3
    for dia in ("2025-08-10", "2025-08-11", "2025-08-12"):
        assert (tmp_path / "VIIRS_NOAA20_SP" / "2025" / f"{dia}.csv.gz").exists()
    # El día sin focos tiene fichero, con la cabecera: así consta como descargado.
    vacio = gzip.decompress((tmp_path / "VIIRS_NOAA20_SP/2025/2025-08-12.csv.gz").read_bytes())
    assert vacio.startswith(b"latitude,longitude,") and vacio.count(b"\n") == 1
    del_dia = datos.focos(date(2025, 8, 10))
    assert del_dia is not None and len(del_dia) == 2
    assert datos.focos(date(2025, 8, 13)) is None


def test_con_zonas_solo_se_leen_los_focos_de_alrededor(tmp_path: Path) -> None:
    datos = firms.Datos(tmp_path, zonas=[(51.45, 45.94)])
    datos.guardar_respuesta("VIIRS_NOAA20_SP", date(2025, 8, 10), 1, VIIRS_SP)
    datos.guardar_respuesta("MODIS_SP", date(2025, 8, 10), 1, MODIS_SP)
    focos = datos.focos(date(2025, 8, 10)) or []
    assert sorted((f.fuente, f.lat) for f in focos) == [
        ("MODIS_SP", 51.4487), ("MODIS_SP", 51.4588), ("VIIRS_NOAA20_SP", 51.4512),
    ]  # fmt: skip


def test_la_cache_de_dias_esta_acotada(tmp_path: Path) -> None:
    datos = firms.Datos(tmp_path)
    for n in range(firms.DIAS_EN_MEMORIA + 5):
        datos.focos(date(2025, 1, 1) + timedelta(days=n))
    assert len(datos._cache) == firms.DIAS_EN_MEMORIA


def test_de_cada_producto_vale_el_sp_si_existe(tmp_path: Path) -> None:
    datos = firms.Datos(tmp_path)
    dia = date(2025, 8, 10)
    datos.guardar_respuesta("VIIRS_NOAA20_NRT", dia, 1, VIIRS_NRT)
    assert {f.fuente for f in datos.focos(dia) or []} == {"VIIRS_NOAA20_NRT"}
    datos.guardar_respuesta("VIIRS_NOAA20_SP", dia, 1, VIIRS_SP)
    datos.guardar_respuesta("MODIS_SP", dia, 1, MODIS_SP)
    assert {f.fuente for f in datos.focos(dia) or []} == {"VIIRS_NOAA20_SP", "MODIS_SP"}


@pytest.mark.parametrize(("nombre", "punto"), sorted(OBJETIVOS.items()))
def test_los_objetivos_caen_dentro_del_rectangulo(nombre: str, punto: tuple[float, float]) -> None:
    assert firms.CAJA.contiene(*punto), nombre


def test_la_url_lleva_el_rectangulo_los_dias_y_la_fecha() -> None:
    url = firms.url_area(CLAVE, "MODIS_NRT", date(2026, 9, 29), 2)
    assert url == (
        f"https://firms.modaps.eosdis.nasa.gov/api/area/csv/{CLAVE}/MODIS_NRT/"
        "22,43,60,61/2/2026-09-29"
    )


# --- Recogida horaria -------------------------------------------------------------------


class Transporte:
    """Doble de la red: responde según la fuente de la URL y anota las URL pedidas."""

    def __init__(self, fallar: set[str] | None = None, codigo: int = 200) -> None:
        self.urls: list[str] = []
        self.fallar = fallar or set()
        self.codigo = codigo

    def __call__(self, url: str, cabeceras: dict[str, str], limite_s: float) -> Respuesta:
        self.urls.append(url)
        if any(f"/{f}/" in url for f in self.fallar):
            return self.codigo, {}, b"Invalid MAP_KEY."
        if "data_availability" in url:
            return 200, {}, DISPONIBILIDAD
        if "mapkey_status" in url:
            return 200, {}, b'{"current_transactions": 10}'
        return 200, {}, VIIRS_NRT if "VIIRS" in url else MODIS_SP


def descargador(transporte: Transporte) -> Descargador:
    return Descargador(transporte=transporte, dormir=lambda _: None, reintentos=1, pausa_minima_s=0)


def test_cada_tres_horas_descarga_los_dos_ultimos_dias_nrt(tmp_path: Path) -> None:
    datos, red = firms.Datos(tmp_path), Transporte()
    lectura = firms.recoger(datos, AHORA, CLAVE, descargador(red))
    assert lectura.descargada and lectura.ultima_correcta == AHORA
    assert sorted(u.split("/")[7] for u in red.urls) == sorted(firms.FUENTES_NRT)
    assert {u.split("/", 9)[-1] for u in red.urls} == {"2/2026-09-29"}
    assert datos.tiene("MODIS_NRT", date(2026, 9, 30))
    # Dos horas después no toca; a las tres, sí.
    red.urls.clear()
    assert not firms.recoger(datos, AHORA + timedelta(hours=2), CLAVE, descargador(red)).descargada
    assert red.urls == []
    assert firms.recoger(datos, AHORA + timedelta(hours=3), CLAVE, descargador(red)).descargada


def test_un_fallo_no_actualiza_la_ultima_correcta_y_se_reintenta(tmp_path: Path) -> None:
    datos = firms.Datos(tmp_path)
    with pytest.raises(firms.FirmsNoDisponible):
        firms.recoger(datos, AHORA, CLAVE, descargador(Transporte({"MODIS_NRT"})))
    assert "ultima_correcta" not in datos.control()
    # La siguiente ejecución, una hora después, vuelve a intentarlo.
    red = Transporte()
    assert firms.recoger(datos, AHORA + timedelta(hours=1), CLAVE, descargador(red)).descargada
    assert len(red.urls) == len(firms.FUENTES_NRT)


def test_sin_clave_no_se_descarga(tmp_path: Path) -> None:
    with pytest.raises(firms.FirmsNoDisponible, match="EODI_FIRMS_MAP_KEY"):
        firms.recoger(firms.Datos(tmp_path), AHORA, None, descargador(Transporte()))


# --- La clave no sale ---------------------------------------------------------------------


def test_redactar_cambia_la_clave() -> None:
    assert firms.redactar(f"https://x/{CLAVE}/MODIS", CLAVE) == "https://x/***/MODIS"
    assert firms.redactar("sin clave", None) == "sin clave"


@pytest.mark.parametrize("codigo", [200, 403, 500])
def test_los_errores_no_llevan_la_clave(tmp_path: Path, codigo: int) -> None:
    red = Transporte(set(firms.FUENTES_NRT), codigo)
    with pytest.raises(firms.FirmsNoDisponible) as error:
        firms.recoger(firms.Datos(tmp_path), AHORA, CLAVE, descargador(red))
    assert CLAVE not in str(error.value)
    assert "***" in str(error.value)
    # La excepción original, con la URL, no queda encadenada.
    assert error.value.__cause__ is None and error.value.__context__ is None


def test_el_registro_de_la_recogida_no_lleva_la_clave(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setenv(firms.VARIABLE_CLAVE, CLAVE)
    monkeypatch.setenv(firms.VARIABLE_DATOS, str(tmp_path))
    red = Transporte(set(firms.FUENTES_NRT), 500)
    monkeypatch.setattr(firms, "descargador", lambda plazo=None: descargador(red))
    almacen = Almacen.abrir()
    with caplog.at_level(logging.DEBUG):
        estado = horaria.paso_firms(almacen, AHORA)
    assert estado.estado == NO_LEIDA
    assert "firms no se lee" in caplog.text
    assert CLAVE not in caplog.text


# --- Un fallo de FIRMS no para la recogida ---------------------------------------------------


def test_un_error_inesperado_de_firms_queda_en_aviso(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setenv(firms.VARIABLE_CLAVE, CLAVE)
    monkeypatch.setenv(firms.VARIABLE_DATOS, str(tmp_path))

    def roto(*_: object) -> firms.Lectura:
        raise OSError(f"disco lleno al guardar {CLAVE}")

    def cruce_roto(*_: object) -> ft.Resumen:
        raise ValueError("fallo del cruce")

    monkeypatch.setattr(firms, "recoger", roto)
    monkeypatch.setattr(ft, "evaluar_todos", cruce_roto)
    estado = horaria.paso_firms(Almacen.abrir(), AHORA)
    assert estado.estado == NO_LEIDA
    assert "cruce con firms fallido" in caplog.text
    assert CLAVE not in caplog.text


def test_firms_correcto_queda_leido_con_su_ultima_lectura(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(firms.VARIABLE_CLAVE, CLAVE)
    monkeypatch.setenv(firms.VARIABLE_DATOS, str(tmp_path))
    monkeypatch.setattr(firms, "descargador", lambda plazo=None: descargador(Transporte()))
    estado = horaria.paso_firms(Almacen.abrir(), AHORA)
    assert estado.estado == LEIDA
    assert estado.ultimo_dato == AHORA


# --- Histórico ---------------------------------------------------------------------------

DISPONIBILIDAD = b"""data_id,min_date,max_date
MODIS_NRT,2026-07-01,2026-10-01
MODIS_SP,2000-11-01,2026-06-30
VIIRS_NOAA20_NRT,2026-07-01,2026-10-01
VIIRS_NOAA20_SP,2018-04-01,2026-06-30
VIIRS_NOAA21_NRT,2024-01-17,2026-10-01
VIIRS_SNPP_NRT,2026-07-01,2026-10-01
VIIRS_SNPP_SP,2012-01-20,2026-06-30
LANDSAT_NRT,2022-06-20,2026-10-01
"""


def test_el_plan_usa_sp_y_sigue_con_nrt_donde_sp_no_llega() -> None:
    cubiertas = {
        "MODIS_SP": (date(2000, 11, 1), date(2022, 10, 7)),
        "MODIS_NRT": (date(2022, 10, 8), date(2022, 10, 12)),
        "VIIRS_NOAA21_NRT": (date(2022, 10, 10), date(2022, 10, 12)),
    }
    tramos = firms.plan(cubiertas, date(2022, 10, 1))
    assert tramos == [
        firms.Tramo("VIIRS_NOAA21_NRT", date(2022, 10, 10), 3),
        firms.Tramo("MODIS_SP", date(2022, 10, 1), 5),
        firms.Tramo("MODIS_SP", date(2022, 10, 6), 2),
        firms.Tramo("MODIS_NRT", date(2022, 10, 8), 5),
    ]


def test_el_historico_es_reanudable(tmp_path: Path) -> None:
    datos, red = firms.Datos(tmp_path), Transporte()
    reloj = iter(range(10**6))
    ahora = datetime(2022, 10, 25, tzinfo=UTC)
    # Una tanda corta: se corta por tiempo y deja tramos pendientes.
    hechos, quedan = firms.historico(
        datos, CLAVE, descargador(red), ahora, tope_s=3, dormir=lambda _: None,
        reloj=lambda: float(next(reloj)),
    )  # fmt: skip
    assert hechos > 0 and quedan > 0
    assert datos.control()["historico"]["terminado"] is False
    # La siguiente sigue donde lo dejó y no vuelve a pedir lo descargado.
    red.urls.clear()
    hechos2, quedan2 = firms.historico(datos, CLAVE, descargador(red), ahora, dormir=lambda _: None)
    pedidas = [u for u in red.urls if "/area/" in u]
    assert hechos2 == len(pedidas) == quedan
    assert quedan2 == 0 and datos.control()["historico"]["terminado"] is True
    # Del 1 al 23 de octubre (los dos últimos días son de la recogida horaria): SP de tres
    # productos. NOAA-21 aún no existía.
    assert {u.split("/")[7] for u in pedidas} <= {"VIIRS_SNPP_SP", "VIIRS_NOAA20_SP", "MODIS_SP"}
    assert datos.tiene("MODIS_SP", date(2022, 10, 1))
    assert datos.tiene("MODIS_SP", date(2022, 10, 23))


def test_el_resumen_no_lleva_la_clave(tmp_path: Path) -> None:
    datos = firms.Datos(tmp_path)
    datos.guardar_respuesta("MODIS_SP", date(2025, 8, 10), 1, MODIS_SP)
    resumen = firms.resumen(datos)
    assert resumen["fuentes"]["MODIS_SP"]["dias"] == 1
    assert CLAVE not in str(resumen)


def test_vacio_tiene_solo_la_cabecera() -> None:
    assert VACIO_VIIRS.startswith(b"latitude")
