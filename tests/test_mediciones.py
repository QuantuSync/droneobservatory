"""Mediciones en la base y en lo publicado, sin red: tablas nuevas, afirmaciones de la fuente
medida, lista cerrada de campos públicos, condiciones (Open-Meteo con su caché y su cupo, sol y
luna), días procesados en disco, cola de días y fallos que no paran la recogida horaria."""

import gzip
import io
import json
import tarfile
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from almacen.base import Almacen, DocumentoInvalido
from esquema import Esquema, Visibilidad, rutas_por_visibilidad
from exportacion.campos import CAMPOS_PUBLICOS_INCIDENTE
from exportacion.geojson import con_afirmaciones, exportar
from exportacion.proyeccion import rutas
from proceso import astronomia, condiciones, mediciones, trafico, vuelos
from recogida import adsb, meteo
from recogida import mediciones as paso
from recogida import trafico as procesado
from recogida.estado import CON_AVISO, LEIDA, NO_LEIDA
from tests import ejemplos
from tests.ejemplos import AHORA, VOCABULARIO_MODELOS
from tests.test_interrupciones import DIA, entorno, incidente, lector
from tests.test_trafico import abridor

FIXTURES = Path(__file__).parent / "fixtures" / "trafico"
PUBLICAS = rutas_por_visibilidad(Esquema.INCIDENTE)


class SinFin:
    def agotado(self) -> bool:
        return False


def guardar(almacen: Almacen, documento: dict[str, Any]) -> None:
    almacen.guardar_incidente(documento, AHORA, VOCABULARIO_MODELOS)


# --- Base -------------------------------------------------------------------------------


def test_el_cierre_medido_entra_con_su_fuente_y_sus_afirmaciones() -> None:
    almacen = Almacen.abrir()
    guardar(almacen, incidente())
    resumen = mediciones.evaluar_trafico(almacen, entorno(lector()), AHORA, SinFin())  # type: ignore[arg-type]
    assert resumen.cierres == 1 and resumen.cambiados == 1
    medido = almacen.trafico_aereo()["EODI-2025-00002"]
    assert medido["cierre"]["resultado"] == "cierre_medido"
    fuente = almacen.fuentes()[medido["fuente_id"]]
    assert (fuente["medio"], fuente["fiabilidad"], fuente["enlace"]) == (
        "Tráfico aéreo medido (adsb.lol)",
        "B",
        "https://github.com/adsblol/x/2025-09-22",
    )
    afirmaciones = {a["campo"]: a for a in almacen.afirmaciones("EODI-2025-00002")}
    assert afirmaciones["cierre_minutos"]["valor"] == {"min": 255, "max": 255}
    assert afirmaciones["vuelos_desviados"]["valor"] == {"min": 12, "max": 12}
    assert {(a["origen"], a["metodo"], a["credibilidad"]) for a in afirmaciones.values()} == {
        ("medido", "regla", 2)
    }
    assert almacen.trafico_aereo()["EODI-2025-00002"]["regla"] == {
        "nombre": "trafico_aereo",
        "version": "1.0.0",
    }


def test_una_evaluacion_sin_cambios_no_se_repite_ni_engorda_el_historial() -> None:
    almacen = Almacen.abrir()
    guardar(almacen, incidente())
    contexto = entorno(lector())
    mediciones.evaluar_trafico(almacen, contexto, AHORA, SinFin())  # type: ignore[arg-type]
    despues = AHORA + timedelta(hours=1)
    resumen = mediciones.evaluar_trafico(almacen, contexto, despues, SinFin())  # type: ignore[arg-type]
    assert resumen.evaluados == 0
    assert len(almacen.historial("EODI-2025-00002")) == 2  # alta del incidente y del tráfico


def test_los_incidentes_se_evaluan_antes_que_las_interrupciones(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    almacen = Almacen.abrir()
    guardar(almacen, incidente())
    vistos: list[int] = []

    def anomalias(almacen: Almacen, *_: Any) -> int:
        vistos.append(len(almacen.trafico_aereo()))
        return 0

    monkeypatch.setattr(mediciones, "anomalias_nuevas", anomalias)
    mediciones.evaluar_trafico(almacen, entorno(lector()), AHORA, SinFin())  # type: ignore[arg-type]
    assert vistos == [1]


def test_las_medidas_se_validan_contra_el_esquema() -> None:
    almacen = Almacen.abrir()
    malo = ejemplos.trafico_aereo()
    malo["cierre"]["resultado"] = "cerrado"
    with pytest.raises(DocumentoInvalido):
        almacen.guardar_trafico_aereo("EODI-2025-00001", malo)
    with pytest.raises(DocumentoInvalido):
        almacen.guardar_condiciones("EODI-2025-00001", {"origen": "prensa"})


def test_cobertura_y_gnss_diaria_solo_admiten_filas_nuevas() -> None:
    almacen = Almacen.abrir()
    fila = {"oaci": "EKCH", "dia": "2025-09-22", "vistos": 694, "nivel": "alta"}
    assert almacen.guardar_coberturas("trafico-1.0.0", [fila]) == 1
    assert almacen.guardar_coberturas("trafico-1.0.0", [{**fila, "vistos": 1}]) == 0
    assert almacen.coberturas("EKCH")[0]["vistos"] == 694
    assert (
        almacen.guardar_gnss_diaria("trafico-1.0.0", "2025-09-22", [("841f059ffffffff", 30, 5)])
        == 1
    )
    assert almacen.dias_gnss("trafico-1.0.0") == {"2025-09-22"}


def test_gnss_diaria_guarda_las_celdas_con_interferencia() -> None:
    almacen = Almacen.abrir()
    datos = lector()
    datos.dias[DIA].gnss_dia = [
        ("841f059ffffffff", 40, 6),
        ("841f237ffffffff", 40, 1),
        ("841f05dffffffff", 5, 5),
    ]
    contexto = entorno(datos)
    mediciones.gnss_nuevas(almacen, contexto, SinFin())  # type: ignore[arg-type]
    filas = [f for f in almacen.gnss_diaria("2025-09-22")]
    assert [(f["celda"], f["aeronaves"], f["degradadas"]) for f in filas] == [
        ("841f059ffffffff", 40, 6)
    ]


# --- Lo publicado ---------------------------------------------------------------------


def test_los_campos_publicos_del_trafico_son_publicos_en_el_esquema() -> None:
    nuevos = {r for r in CAMPOS_PUBLICOS_INCIDENTE if r.startswith("trafico_aereo")}
    assert nuevos <= PUBLICAS[Visibilidad.PUBLICO]
    for interno in (
        "trafico_aereo.respuesta_militar",
        "trafico_aereo.interferencia_gnss",
        "trafico_aereo.cierre.cobertura",
        "condiciones",
    ):
        assert interno not in CAMPOS_PUBLICOS_INCIDENTE
        assert interno in PUBLICAS[Visibilidad.INTERNO]


def publicado(almacen: Almacen) -> dict[str, Any]:
    incidentes, _ = mediciones.con_mediciones(almacen.incidentes(), [], almacen)
    return exportar(incidentes, AHORA, VOCABULARIO_MODELOS)


def test_el_cierre_medido_sale_en_la_web_sin_lo_interno() -> None:
    almacen = Almacen.abrir()
    guardar(almacen, incidente())
    mediciones.evaluar_trafico(almacen, entorno(lector()), AHORA, SinFin())  # type: ignore[arg-type]
    (feature,) = publicado(almacen)["features"]
    bloque = feature["properties"]["trafico_aereo"]
    assert set(rutas(bloque)) <= {
        r.removeprefix("trafico_aereo.") for r in CAMPOS_PUBLICOS_INCIDENTE
    }
    assert bloque["cierre"] == {
        "resultado": "cierre_medido",
        "aeropuerto": "EKCH",
        "inicio": {"valor": "2025-09-22T18:24Z", "precision": "minuto"},
        "fin": {"valor": "2025-09-22T22:39Z", "precision": "minuto"},
        "duracion_min": 255,
        "vuelos_desviados": 12,
        "vuelos_en_espera": 0,
        "difiere_de_declarado": True,
    }
    assert "respuesta_militar" not in bloque and "condiciones" not in feature["properties"]
    # Quién dice qué: la medida junto a lo declarado.
    medios = {
        a["medio"]
        for a in feature["properties"]["afirmaciones_publicas"]
        if a["campo"] == "consecuencias.vuelos_desviados"
    }
    assert "Tráfico aéreo medido (adsb.lol)" in medios


@pytest.mark.parametrize(
    "resultado", ["sin_interrupcion", "cobertura_insuficiente", "no_aplicable"]
)
def test_sin_cierre_medido_no_se_publica_nada_del_trafico(resultado: str) -> None:
    documento = ejemplos.incidente_completo()
    documento["trafico_aereo"] = {**ejemplos.trafico_aereo(), "cierre": {"resultado": resultado}}
    publicado_ = con_afirmaciones(documento)
    assert publicado_ is not None and "trafico_aereo" not in publicado_


def test_un_cierre_con_cobertura_insuficiente_no_se_publica() -> None:
    documento = ejemplos.incidente_completo()
    bloque = ejemplos.trafico_aereo()
    bloque["cierre"]["cobertura"]["nivel"] = "insuficiente"
    documento["trafico_aereo"] = bloque
    publicado_ = con_afirmaciones(documento)
    assert publicado_ is not None and "trafico_aereo" not in publicado_


# --- Condiciones ---------------------------------------------------------------------


HORARIO: dict[str, list[Any]] = {
    "temperature_2m": [10.0 + h / 10 for h in range(24)],
    "wind_speed_10m": [5.0] * 23 + [9.0],
    "wind_direction_10m": [270.0] * 24,
    "wind_speed_850hPa": [16.0] * 24,
    "temperature_850hPa": [None] * 24,
}


def test_condiciones_a_la_hora_y_rango_del_dia() -> None:
    superficie, niveles = condiciones.meteorologia(HORARIO, 18)
    assert superficie["temperatura_c"] == 11.8 and superficie["viento_10m_ms"] == 5.0
    assert niveles["850"] == {"viento_ms": 16.0, "direccion": None, "temperatura_c": None}
    superficie, _ = condiciones.meteorologia(HORARIO, None)
    assert superficie["viento_10m_ms"] == [5.0, 9.0]
    assert superficie["direccion_10m"] is None  # una dirección no tiene rango


def test_condiciones_de_un_incidente_con_metar_y_astronomia() -> None:
    aeropuertos = {a.oaci: a for a in vuelos.cargar_aeropuertos()}
    from tests.test_interrupciones import METARES

    bloque = mediciones.condiciones_incidente(
        incidente(),
        aeropuertos,
        lambda puntos, dia, clave: [HORARIO],
        lambda e, d: METARES[e],
        "c" * 64,
        AHORA,
    )
    assert bloque is not None
    lugar = bloque["lugar"]
    assert lugar["metar"]["texto"].startswith("EKCH 221820Z")
    assert lugar["astronomia"]["luz"] == "noche"
    assert bloque["origen"] == "medido" and bloque["origen_lugar"] == "punto"
    Almacen.abrir().guardar_condiciones("EODI-2025-00002", bloque)


def test_sin_cupo_de_open_meteo_las_condiciones_esperan() -> None:
    aeropuertos = {a.oaci: a for a in vuelos.cargar_aeropuertos()}
    bloque = mediciones.condiciones_incidente(
        incidente(), aeropuertos, lambda p, d, c: [None], lambda e, d: [], "c" * 64, AHORA
    )
    assert bloque is None


def test_zonas_de_lanzamiento_y_regiones_de_un_ataque() -> None:
    ataque = ejemplos.ataque_completo()
    ataque["zonas_lanzamiento"] = ["Приморсько-Ахтарськ", "Курська обл", "мис Чауда", "Каспію"]
    lanzamiento, impacto = condiciones.puntos_ataque(ataque)
    assert [n for n, _, _ in lanzamiento] == ["Primorsko-Ajtarsk", "Cabo Chauda (Crimea)"]
    assert impacto and all(isinstance(lat, float) for _, lat, _ in impacto)
    bloque = mediciones.condiciones_ataque(
        ataque, lambda p, d, c: [HORARIO] * len(p), "d" * 64, AHORA
    )
    assert bloque is not None and len(bloque["lanzamiento"]) == 2
    assert bloque["lanzamiento"][0]["momento"]["valor"] == "2025-10-05T15:00Z"


class DescargaFalsa:
    def __init__(self) -> None:
        self.urls: list[str] = []

    def contenido(self, url: str, valido: Any) -> bytes:
        self.urls.append(url)
        lugares = len(url.split("latitude=")[1].split("&")[0].split("%2C"))
        uno = {"hourly": {"time": ["2025-09-22T00:00"], "wind_speed_10m": [5.0]}}
        return json.dumps(uno if lugares == 1 else [uno] * lugares).encode()


def test_open_meteo_con_cache_y_cupo(tmp_path: Path) -> None:
    descarga = DescargaFalsa()
    cliente = meteo.Cliente(tmp_path, descarga, tope=3)  # type: ignore[arg-type]
    puntos = [(55.618, 12.656), (46.05, 38.17)]
    assert all(h is not None for h in cliente.horas(puntos, DIA, meteo.VIENTO, "guerra"))
    assert len(descarga.urls) == 1 and cliente.gastadas == 2
    cliente.horas(puntos, DIA, meteo.VIENTO, "guerra")  # de la caché
    assert len(descarga.urls) == 1
    # 21 variables cuentan como 2,1 llamadas: no caben en lo que queda del cupo.
    assert cliente.horas([(50.0, 10.0)], DIA, meteo.SUPERFICIE + meteo.PRESION, "incidente") == [
        None
    ]
    assert meteo.unidades(meteo.SUPERFICIE + meteo.PRESION, 1) == pytest.approx(2.1)


def test_sol_y_luna() -> None:
    copenhague = astronomia.condiciones(55.618, 12.656, datetime(2025, 9, 22, 18, 30, tzinfo=UTC))
    assert copenhague["luz"] == "noche"
    assert isinstance(copenhague["luna_iluminada"], float) and copenhague["luna_iluminada"] < 0.05
    mediodia = astronomia.elevacion_sol(51.48, 0.0, datetime(2025, 9, 22, 11, 53, tzinfo=UTC))
    assert mediodia == pytest.approx(38.5, abs=0.3)  # 90° − 51,48° en el equinoccio
    _, llena = astronomia.luna(52.0, 0.0, datetime(2025, 10, 7, 3, 48, tzinfo=UTC))
    assert llena > 0.99
    assert astronomia.luz(-3.0) == "crepusculo"


# --- Días procesados en disco ------------------------------------------------------------


def tar(documentos: list[dict[str, Any]]) -> bytes:
    salida = io.BytesIO()
    with tarfile.open(fileobj=salida, mode="w") as t:
        for d in documentos:
            crudo = gzip.compress(json.dumps(d).encode())
            info = tarfile.TarInfo(f"./traces/{d['icao'][-2:]}/trace_full_{d['icao']}.json")
            info.size = len(crudo)
            t.addfile(info, io.BytesIO(crudo))
    return salida.getvalue()


class MetarFalso:
    def contenido(self, url: str, valido: Any) -> bytes:
        return (
            b"station,valid,metar\n"
            b"EKCH,2025-09-22 18:20,EKCH 221820Z AUTO 25007KT 9999 NCD 10/05 Q1018\n"
        )


def test_un_dia_procesado_se_lee_de_disco(tmp_path: Path) -> None:
    from tests.test_trafico import abridor, documento

    etiqueta = adsb.etiqueta(DIA, adsb.PROD)
    contenido = tar([documento(i) for i in ("47875c", "4ab562", "48c2a7", "3e8e96", "781e1f")])
    resumen = procesado.procesar_dia(
        tmp_path, DIA, abridor({f"2025/{etiqueta}.tar": contenido}), lambda: MetarFalso()
    )
    assert resumen["movimientos"] == {"D": 1, "G": 1, "H": 2, "L": 3, "V": 1}
    assert resumen["metar"] is True and resumen["militares"] == 1
    assert set(resumen["bytes_ficheros"]) == {
        "gnss_dia.csv.gz",
        "gnss_hora.csv.gz",
        "militares.jsonl.gz",
        "movimientos.jsonl.gz",
        "trazas.txt.gz",
    }
    dias = procesado.Dias(tmp_path)
    assert dias.procesados() == [DIA]
    leido = dias(DIA)
    assert leido is not None and leido.publicacion == etiqueta
    assert [f[1] for f in leido.movimientos["EKCH"]] == ["L", "D", "G", "H", "V", "H"] or sorted(
        f[1] for f in leido.movimientos["EKCH"]
    ) == ["D", "G", "H", "H", "L", "V"]
    assert leido.militares is None  # no se guarda en memoria: se lee al pedirlo
    assert leido.detalle("militares")[0]["tipo"] == "A400"
    assert leido.detalle("gnss_dia") and leido.detalle("gnss_hora")
    assert paso.Metares(tmp_path)("EKCH", trafico.inicio_dia(DIA), trafico.inicio_dia(DIA) + 86400)


def test_cola_de_dias_recientes_e_historicos(tmp_path: Path) -> None:
    zonas = {
        "incidentes": [
            {
                "id": "EODI-2025-00001",
                "dia": "2025-09-22",
                "dias": ["2025-09-22", "2025-09-23"],
                "prioritario": True,
            },
            {"id": "EODI-2025-00002", "dia": "2025-06-01", "prioritario": False},
        ]
    }
    procesado.escribir_json(tmp_path / procesado.ZONAS, zonas)
    hoy = date(2026, 10, 1)
    cola = procesado.cola(tmp_path, hoy)
    assert cola[0] == date(2026, 9, 30)
    assert len([d for d in cola if d >= hoy - timedelta(days=35)]) == 35
    resto = [d for d in cola if d < hoy - timedelta(days=35)]
    assert resto[:5] == [
        date(2025, 9, 22),
        date(2025, 9, 15),
        date(2025, 9, 8),
        date(2025, 9, 1),
        date(2025, 8, 25),
    ]
    assert date(2025, 6, 1) in resto
    # La ventana del primero pasa de medianoche: el día siguiente y su línea base también.
    assert {date(2025, 9, 23), date(2025, 9, 16), date(2025, 8, 26)} <= set(resto)


def test_un_dia_sin_publicar_se_da_por_perdido_a_los_tres_dias(tmp_path: Path) -> None:
    hoy = date(2026, 10, 1)
    procesado.anotar_sin_publicar(tmp_path, date(2026, 9, 29), hoy)
    assert date(2026, 9, 29) in procesado.cola(tmp_path, hoy)
    procesado.anotar_sin_publicar(tmp_path, date(2026, 5, 6), hoy)
    assert date(2026, 5, 6) not in procesado.cola(tmp_path, hoy)
    assert procesado.Dias(tmp_path).perdidos == {date(2026, 5, 6)}


def test_pendientes_sigue_si_un_dia_no_esta_publicado(tmp_path: Path) -> None:
    hechos = procesado.pendientes(
        tmp_path,
        60,
        datetime(2026, 10, 1, 4, tzinfo=UTC),
        abridor({}),
    )
    assert hechos == 0


# --- La recogida horaria no se rompe ----------------------------------------------------


def test_un_fallo_del_trafico_no_para_la_recogida(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    almacen = Almacen.abrir()

    def falla(*_: Any) -> Any:
        raise RuntimeError("disco lleno")

    monkeypatch.setattr(mediciones, "evaluar_trafico", falla)
    estado = paso.paso_trafico(almacen, AHORA, tmp_path)
    assert estado.estado == NO_LEIDA


def test_sin_dias_procesados_recientes_el_trafico_queda_con_aviso(tmp_path: Path) -> None:
    almacen = Almacen.abrir()
    procesado.escribir_json(
        tmp_path / procesado.CONTROL, {"ultimo_correcto": "2026-09-27T04:00:00Z"}
    )
    estado = paso.paso_trafico(almacen, datetime(2026, 10, 1, 9, tzinfo=UTC), tmp_path)
    assert estado.estado == CON_AVISO
    assert (tmp_path / procesado.ZONAS).exists()
    estado = paso.paso_trafico(almacen, datetime(2026, 9, 27, 9, tzinfo=UTC), tmp_path)
    assert estado.estado == LEIDA


def test_un_fallo_de_open_meteo_no_para_la_recogida(tmp_path: Path) -> None:
    almacen = Almacen.abrir()
    guardar(almacen, incidente())

    class Roto:
        gastadas = 0

        def horas(self, *_: Any) -> Any:
            raise OSError("sin red")

    estado = paso.paso_condiciones(almacen, AHORA, tmp_path, tmp_path, Roto())
    assert estado.estado == NO_LEIDA
