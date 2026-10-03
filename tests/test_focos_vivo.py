"""Focos de calor de las últimas 24 horas (recogida/focos_vivo.py), sin red: los CSV de FIRMS
en disco son recortes reales pequeños (tests/fixtures/focos_vivo) o filas escritas aquí."""

import gzip
import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest

from proceso.focos_termicos import Foco
from recogida import firms, focos_vivo

FIXTURES = Path(__file__).parent / "fixtures" / "focos_vivo"
AHORA = datetime(2026, 10, 3, 9, 36, tzinfo=UTC)
CABECERA = (
    "latitude,longitude,bright_ti4,scan,track,acq_date,acq_time,satellite,instrument,"
    "confidence,version,bright_ti5,frp,daynight"
)


def _foco(lat: float, lon: float, cuando: datetime, frp: float = 2.0, confianza: str = "n") -> Foco:
    return Foco(lat, lon, cuando, "NOAA-21", "VIIRS", confianza, frp, "VIIRS_NOAA21_NRT")


def _fila(f: Foco) -> str:
    return (
        f"{f.lat},{f.lon},330.0,0.4,0.4,{f.instante:%Y-%m-%d},{f.instante:%H%M},N21,VIIRS,"
        f"{f.confianza},2.0NRT,290.0,{f.frp},N"
    )


def _escribir(directorio: Path, focos: list[Foco]) -> firms.Datos:
    datos = firms.Datos(directorio)
    por_dia: dict[date, list[Foco]] = {}
    for f in focos:
        por_dia.setdefault(f.instante.date(), []).append(f)
    dias = sorted(por_dia)
    if not dias:
        return datos
    dia = dias[0]
    while dia <= AHORA.date():
        filas = "".join(f"{_fila(f)}\n" for f in por_dia.get(dia, []))
        datos.guardar("VIIRS_NOAA21_NRT", dia, f"{CABECERA}\n{filas}".encode())
        dia += timedelta(days=1)
    return datos


def test_filtros_como_en_el_cruce(tmp_path: Path) -> None:
    antorcha = (59.5023, 32.0871)
    frente = (48.28, 37.17)
    focos = [
        # Antorcha de una refinería: un foco cada noche de los 30 días anteriores.
        *[_foco(*antorcha, AHORA - timedelta(days=d, hours=2), frp=1.5) for d in range(2, 31)],
        _foco(antorcha[0] + 0.001, antorcha[1], AHORA - timedelta(hours=3), frp=2.0),
        # La misma antorcha con una potencia anómala: cuenta.
        _foco(antorcha[0], antorcha[1] + 0.002, AHORA - timedelta(hours=4), frp=40.0),
        # Ciudad del frente: arde a diario en muchas celdas.
        *[
            _foco(
                frente[0] + 0.012 * (d % 6), frente[1] + 0.015 * (d % 5), AHORA - timedelta(days=d)
            )
            for d in range(2, 30)
        ],
        _foco(frente[0] + 0.005, frente[1] + 0.005, AHORA - timedelta(hours=5), frp=9.0),
        # Un foco nuevo en un sitio sin calor habitual, y otro de baja confianza.
        _foco(50.45, 30.52, AHORA - timedelta(hours=6), frp=12.0),
        _foco(50.10, 30.90, AHORA - timedelta(hours=7), confianza="l"),
        # Fuera de las 24 horas.
        _foco(50.20, 30.70, AHORA - timedelta(hours=30)),
        # Fuera de Ucrania y de Rusia: una quema en Rumanía, dentro de la zona de FIRMS.
        _foco(44.10, 26.10, AHORA - timedelta(hours=2), frp=30.0),
    ]
    datos = _escribir(tmp_path / "firms", focos)
    publicacion = {
        "impactos": [
            {
                "id": "EODI-IG-2026-03500",
                "fecha": {"valor": "2026-10-03T07:10Z", "precision": "minuto"},
                "lugar": {"punto": {"lat": 50.449, "lon": 30.523}, "radio_km": 7.0},
                "fuentes": [{"frase_origen": "Уражено об'єкт енергетики."}],
            }
        ]
    }
    documento, resumen = focos_vivo.generar(datos, tmp_path / "vivo", publicacion, AHORA)
    assert resumen.leidos == 5
    assert resumen.baja_confianza == 1
    assert resumen.habituales == 1
    assert resumen.frecuentes == 1
    # Por orden de hora: el de Kyiv (hace 6 h) y la antorcha con potencia anómala (hace 4 h).
    assert [f[:2] for f in documento["focos"]] == [[30.52, 50.45], [32.089, 59.502]]
    # El foco de Kyiv coincide con el impacto declarado y va resaltado.
    assert documento["focos"][0][4] == "EODI-IG-2026-03500"
    assert documento["focos"][1][4] is None
    assert documento["ultimo_foco"] == (AHORA - timedelta(hours=4)).strftime("%Y-%m-%dT%H:%MZ")
    assert documento["descartados"] == {
        "baja_confianza": 1,
        "fuentes_habituales": 1,
        "fuego_frecuente": 1,
    }


def test_emplazamiento_del_anio_descarta_la_antorcha_estacional() -> None:
    sitio = [_foco(59.5023, 32.0871, AHORA - timedelta(days=200 + d), frp=2.0) for d in range(10)]
    sitios = focos_vivo.emplazamientos(sitio)
    nuevo = _foco(59.5025, 32.0873, AHORA - timedelta(hours=1), frp=3.0)
    assert focos_vivo.en_emplazamiento(nuevo, sitios)
    fuerte = _foco(59.5025, 32.0873, AHORA - timedelta(hours=1), frp=30.0)
    assert not focos_vivo.en_emplazamiento(fuerte, sitios)
    lejos = _foco(59.60, 32.30, AHORA - timedelta(hours=1), frp=3.0)
    assert not focos_vivo.en_emplazamiento(lejos, sitios)


def test_partes_diarios_y_fpv_no_resaltan() -> None:
    publicacion = {
        "impactos": [
            {
                "id": "EODI-IG-2026-03501",
                "parte_diario": True,
                "fecha": {"valor": "2026-10-03T07:10Z", "precision": "minuto"},
                "lugar": {"punto": {"lat": 47.8, "lon": 35.1}, "radio_km": 3.0},
                "fuentes": [{"frase_origen": "x"}],
            }
        ]
    }
    impactos = focos_vivo.impactos_recientes(publicacion, AHORA - timedelta(days=3))
    assert impactos == []


def test_emplazamientos_en_cache_por_dia(tmp_path: Path) -> None:
    datos = _escribir(
        tmp_path / "firms",
        [_foco(59.5023, 32.0871, AHORA - timedelta(days=d)) for d in range(40, 60)],
    )
    directorio = tmp_path / "vivo"
    sitios = focos_vivo.cargar_emplazamientos(directorio, datos, AHORA.date())
    assert sum(e.focos for s in sitios.values() for e in s.values()) == 20
    ficheros = list(directorio.glob("emplazamientos-*.json.gz"))
    assert len(ficheros) == 1
    otra = focos_vivo.cargar_emplazamientos(
        directorio, firms.Datos(tmp_path / "vacio"), AHORA.date()
    )
    assert otra == sitios
    contenido = json.loads(gzip.decompress(ficheros[0].read_bytes()))
    assert contenido


@pytest.mark.skipif(not (FIXTURES / "kirishi.csv.gz").exists(), reason="sin recorte")
def test_antorcha_real_de_kirishi(tmp_path: Path) -> None:
    """Focos reales de VIIRS alrededor de la refinería de Kirishi: la antorcha permanente no
    sale como foco en vivo una noche sin ataque."""
    origen = json.loads((FIXTURES / "origen.json").read_text(encoding="utf-8"))
    focos = firms.leer_csv(
        gzip.decompress((FIXTURES / "kirishi.csv.gz").read_bytes()), "VIIRS_NOAA21_NRT"
    )
    noche = datetime.fromisoformat(origen["noche_control"]).replace(tzinfo=UTC)
    recientes = [f for f in focos if noche - timedelta(hours=24) <= f.instante <= noche]
    base = focos_vivo.Indice(f for f in focos if f.instante < noche - timedelta(hours=24))
    assert recientes
    elegidos, resumen = focos_vivo.seleccionar(recientes, base, {}, [])
    assert elegidos == []
    assert resumen.habituales + resumen.baja_confianza == len(recientes)


def test_territorio_ucrania_y_rusia_europea() -> None:
    territorio = focos_vivo.Territorio()
    assert territorio.contiene(50.45, 30.52)  # Kyiv
    assert territorio.contiene(44.95, 34.10)  # Simferópol
    assert territorio.contiene(59.5, 32.08)  # Kirishi
    assert not territorio.contiene(44.43, 26.10)  # Bucarest
    assert not territorio.contiene(53.9, 27.56)  # Minsk
    assert not territorio.contiene(47.0, 28.86)  # Chisináu
