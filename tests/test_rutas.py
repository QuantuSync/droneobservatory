"""Rutas de los drones sobre Ucrania: mensajes de seguimiento de la Fuerza Aérea, pistas de
NEPTUN, reconstrucción, comprobación contra NEPTUN y la línea recta (copia fija de las noches del
4 y el 5 de octubre de 2026, tests/fixtures/rutas/comprobacion.json.gz), noches terminadas,
esquemas y exportación."""

import gzip
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from proceso.rutas import (
    calculo,
    esquema,
    geometria,
    incursiones,
    mensajes,
    neptun,
    noches,
    reconstruccion,
)
from recogida import rutas

COPIA = Path(__file__).parent / "fixtures" / "rutas" / "comprobacion.json.gz"


def copia() -> dict[str, Any]:
    datos: dict[str, Any] = json.loads(gzip.decompress(COPIA.read_bytes()))
    return datos


def sin_frontera(lat: float, lon: float) -> float:
    return 1000.0


# --- Mensajes de la Fuerza Aérea --------------------------------------------------------------


@pytest.mark.parametrize(
    ("texto", "nivel", "rumbo", "destino"),
    [
        ("🛵 БпЛА на півночі Сумщини, курс - південно-західний.", "parte", 225.0, None),
        ("🛵 Сумщина: БпЛА повз Білопілля ➡️ курсом на захід.", "localidad", 270.0, None),
        ("🛵 Група БпЛА з Чорного моря ➡️ на Одещину.", "mar", None, "UA-51"),
        ("🛵  Дніпропетровщина: БпЛА курсом на Павлоград зі сходу.", "region", 270.0, "UA-12"),
        ("🏍 Реактивні БпЛА повз Бровари в напрямку Києва.", "localidad", None, "UA-30"),
    ],
)
def test_lee_zona_rumbo_y_destino(
    texto: str, nivel: str, rumbo: float | None, destino: str | None
) -> None:
    [aviso] = mensajes.leer(texto)
    assert aviso.zona is not None and aviso.zona.nivel == nivel
    assert aviso.rumbo == rumbo
    assert (aviso.destino.region if aviso.destino else None) == destino


def test_tipo_de_dron_del_mensaje() -> None:
    assert mensajes.leer("🏍 Реактивний БпЛА курсом на Одесу.")[0].tipo == "reaccion"
    assert mensajes.leer("🛵 Група ударних БпЛА на півночі Сумщини")[0].grupo


def test_lo_que_no_son_drones_no_da_avisos() -> None:
    assert mensajes.leer("🚀Ракети на Дніпропетровщині ➡️ курсом на північний захід!") == []
    assert (
        mensajes.leer("Група крилатих ракет на Миколаївщині у північно-західному напрямку!") == []
    )


def test_de_una_parte_de_la_region_no_sale_un_rumbo() -> None:
    [aviso] = mensajes.leer("🏍 Реактивний БпЛА з півночі Дніпропетровщини курсом на Полтавщину.")
    assert aviso.rumbo is None
    assert aviso.destino is not None and aviso.destino.region == "UA-53"


# --- NEPTUN -------------------------------------------------------------------------------------


def test_pistas_de_neptun_con_su_rastro() -> None:
    upsert = {
        "type": "upsert",
        "data": {
            "id": "trk_1",
            "type": "uav",
            "lat": 49.06,
            "lon": 33.42,
            "heading": 22,
            "updatedAt": "2026-10-05T20:06:09Z",
            "uncertaintyKm": 28,
            "trail": [{"lat": 49.0, "lon": 33.4, "t": "2026-10-05T19:05:02Z"}],
        },
    }
    otro = {
        "type": "upsert",
        "data": {
            "id": "trk_2",
            "type": "fpv",
            "lat": 47.0,
            "lon": 35.0,
            "updatedAt": "2026-10-05T20:00:00Z",
        },
    }
    [pista] = neptun.pistas([upsert, otro])
    assert pista["id"] == "trk_1"
    assert [p["t"] for p in pista["puntos"]] == ["2026-10-05T19:05:02Z", "2026-10-05T20:06:09Z"]
    assert pista["puntos"][1]["incertidumbre_km"] == 28


# --- Noches y reconstrucción --------------------------------------------------------------------


def test_la_noche_va_de_mediodia_a_mediodia() -> None:
    assert noches.noche_de(datetime(2026, 10, 6, 11, 59, tzinfo=UTC)) == "2026-10-05"
    assert noches.noche_de(datetime(2026, 10, 6, 12, 0, tzinfo=UTC)) == "2026-10-06"


def noche_de_prueba() -> dict[str, Any]:
    def mensaje(id_: int, hora: str, texto: str) -> dict[str, Any]:
        return {
            "id": id_,
            "fecha": f"2026-10-05T{hora}:00Z",
            "avisos": [a.documento() for a in mensajes.leer(texto)],
        }

    return {
        "noche": "2026-10-05",
        "kpszsu": [
            mensaje(1, "19:00", "🛵 БпЛА на півночі Сумщини, курс - південно-західний."),
            mensaje(2, "19:40", "🛵 Сумщина: БпЛА повз Конотоп ➡️ курсом на захід."),
            mensaje(3, "20:30", "🛵 БпЛА на Чернігівщині повз Ніжин курсом на Київ."),
        ],
        "neptun": {"horas_con_datos": 0, "pistas": []},
    }


def test_los_avisos_se_enlazan_si_caben_en_el_tiempo_y_siguen_la_direccion() -> None:
    tramos = reconstruccion.tramos_fuerza_aerea(noche_de_prueba())
    enlaces = [t for t in tramos if t["clase"] == "enlace"]
    assert len(enlaces) == 2
    assert all(t["mensajes"] for t in tramos)
    assert any(t["clase"] == "hacia_destino" for t in tramos)


def test_un_aviso_demasiado_lejos_para_el_tiempo_no_se_enlaza() -> None:
    a = reconstruccion.Nodo(
        0, 1, datetime(2026, 10, 5, 19, tzinfo=UTC), 51.9, 34.3, 10, "ataque", 225.0, None, None, ""
    )
    b = reconstruccion.Nodo(
        1,
        2,
        datetime(2026, 10, 5, 19, 30, tzinfo=UTC),
        46.5,
        30.7,
        10,
        "ataque",
        None,
        None,
        None,
        "",
    )
    reconstruccion.enlazar([a, b])
    assert a.sucesores == []


def test_la_reconstruccion_historica_no_mejora_a_la_linea_recta_y_no_se_publica() -> None:
    """Lo comprobado el 7 de octubre de 2026 con las dos noches con NEPTUN: con las zonas que
    sitúan el dron (sin regiones enteras), la reconstrucción con la Fuerza Aérea queda más lejos
    de NEPTUN que la línea recta. Así que no se publican rutas reconstruidas, solo las de NEPTUN.
    Si un cambio del método la hiciera pasar, esta prueba avisa para revisar la decisión."""
    datos = copia()
    resultados = [
        calculo.comprobar_noche(n["noche"], n["ataque"], rutas.frontera_km) for n in datos["noches"]
    ]
    resumen = calculo.resumen_comprobacion([r for r in resultados if r is not None])
    assert len(resumen["noches"]) == 2
    assert not resumen["pasa"], resumen
    assert resumen["mediana_reconstruccion_km"] > resumen["mediana_recta_km"]
    entrada = datos["noches"][0]
    sin_neptun = {**entrada["noche"], "neptun": {"horas_con_datos": 0, "pistas": []}}
    assert (
        calculo.noche_publica(sin_neptun, entrada["ataque"], sin_frontera, resumen["pasa"]) is None
    )


def test_ninguna_ruta_de_un_ataque_en_curso() -> None:
    noche = noche_de_prueba()
    assert not calculo.cerrada(noche, datetime(2026, 10, 6, 11, 0, tzinfo=UTC))
    noche["kpszsu"].append({"id": 9, "fecha": "2026-10-06T11:30:00Z", "avisos": []})
    assert not calculo.cerrada(noche, datetime(2026, 10, 6, 12, 30, tzinfo=UTC))
    assert calculo.cerrada(noche, datetime(2026, 10, 6, 13, 31, tzinfo=UTC))


def test_lo_publicado_cumple_su_esquema_y_lleva_la_atribucion_de_neptun() -> None:
    datos = copia()
    entrada = datos["noches"][0]
    documento = calculo.noche_publica(entrada["noche"], entrada["ataque"], sin_frontera, True)
    assert documento is not None and documento["fuente"] == "neptun"
    assert documento["atribucion"]["enlace"] == "https://neptun.in.ua/"
    esquema.validar("noche", documento)
    sin_neptun = {**entrada["noche"], "neptun": {"horas_con_datos": 0, "pistas": []}}
    reconstruida = calculo.noche_publica(sin_neptun, entrada["ataque"], sin_frontera, True)
    assert reconstruida is not None and reconstruida["fuente"] == "fuerza_aerea"
    esquema.validar("noche", reconstruida)
    # Si la reconstrucción no pasa la comprobación, una noche sin NEPTUN no publica nada.
    assert calculo.noche_publica(sin_neptun, entrada["ataque"], sin_frontera, False) is None


def test_la_franja_tiene_anchura() -> None:
    tramo = geometria.Tramo(50.0, 30.0, 10.0, 50.0, 31.0, 20.0)
    assert tramo.contiene(50.05, 30.5)
    assert not tramo.contiene(51.0, 30.5)
    assert len(geometria.poligono(tramo)) > 4


# --- Incursiones ----------------------------------------------------------------------------------


def test_velocidad_necesaria_entre_avistamientos() -> None:
    a = {"lat": 45.0, "lon": 28.0, "radio_km": 2.0, "minuto": 0.0, "margen_min": 2.0}
    lejos = {"lat": 46.0, "lon": 28.0, "radio_km": 2.0, "minuto": 15.0, "margen_min": 2.0}
    rapido = incursiones.velocidad_entre(a, lejos)
    assert rapido is not None and rapido["decide"] == "reaccion"
    cerca = {"lat": 45.1, "lon": 28.0, "radio_km": 2.0, "minuto": 30.0, "margen_min": 2.0}
    lento = incursiones.velocidad_entre(a, cerca)
    assert lento is not None and lento["decide"] is None  # una velocidad baja no dice hélice
    casi_a_la_vez = {"lat": 46.0, "lon": 28.0, "radio_km": 2.0, "minuto": 5.0, "margen_min": 30}
    assert incursiones.velocidad_entre(a, casi_a_la_vez) is None


def test_el_paso_horario_deja_los_ataques_por_noche(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from tests import base_prueba

    monkeypatch.setenv(rutas.VARIABLE_DATOS, str(tmp_path))
    rutas.paso_horario(base_prueba.base_prueba())
    datos = json.loads((tmp_path / rutas.ATAQUES).read_text(encoding="utf-8"))
    assert datos and all("zonas" in v and "impactos" in v for v in datos.values())


def test_la_exportacion_lleva_las_rutas_con_su_origen(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from exportacion import semanal

    datos = copia()
    entrada = datos["noches"][0]
    sin_neptun = {**entrada["noche"], "neptun": {"horas_con_datos": 0, "pistas": []}}
    documento = calculo.noche_publica(sin_neptun, entrada["ataque"], sin_frontera, True)
    assert documento is not None
    carpeta = tmp_path / "publicar" / "noches"
    carpeta.mkdir(parents=True)
    (carpeta / f"{documento['noche']}.json").write_text(json.dumps(documento), encoding="utf-8")
    monkeypatch.setenv(rutas.VARIABLE_DATOS, str(tmp_path))
    noches_, grupos = semanal.rutas_exportables()
    semanal._comprobar("rutas_noches.jsonl", noches_, semanal.validador_propio("ruta_noche"))
    semanal._comprobar("rutas_grupos.jsonl", grupos, semanal.validador_propio("ruta_grupo"))
    enlace = next(t for t in noches_[0]["tramos"] if t["clase"] == "enlace")
    assert enlace["procedencia"]["extremos"]["origen"] == "oficial"
    assert enlace["procedencia"]["tramo"]["origen"] == "calculado"
