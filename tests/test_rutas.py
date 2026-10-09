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
    recorridos,
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
    # El recorrido unido de cada grupo, calculado por su regla, sin lo que es solo de dibujo.
    unido = noches_[0]["recorridos"][0]
    assert unido["procedencia"] == {
        "origen": "calculado",
        "metodo": recorridos.VERSION,
        "fuentes": [],
    }
    assert "franjas" not in unido and "flechas" not in unido


# --- Recorridos unidos por grupo ----------------------------------------------------------------


def t(hora: str) -> str:
    return f"2026-10-05T{hora}:00Z"


def pista(id_: str, puntos: list[tuple[str, float, float, float]], **extra: Any) -> dict[str, Any]:
    return {
        "id": id_,
        "tipo": "uav",
        "titulo": extra.pop("titulo", "БпЛА"),
        "puntos": [
            {"t": t, "lat": lat, "lon": lon, "incertidumbre_km": radio, **extra}
            for t, lat, lon, radio in puntos
        ],
    }


def test_un_grupo_es_una_linea_desde_que_aparece_hasta_que_desaparece() -> None:
    """NEPTUN parte el vuelo de un grupo en pistas cortas; si la segunda solo puede seguir a la
    primera, se unen en una línea, con la flecha al final apuntando hacia donde iba."""
    a = pista("a", [(t("20:00"), 51.0, 34.0, 4), (t("20:10"), 50.8, 33.7, 4)])
    b = pista("b", [(t("20:14"), 50.75, 33.6, 4), (t("20:30"), 50.5, 33.2, 4)])
    trozos = recorridos.trozos_neptun([a, b])
    recorridos.enlazar(trozos)
    lista, grupo_de = recorridos.recorridos(trozos)
    assert len(lista) == 1 and grupo_de == [1, 1]
    unico = lista[0]
    assert len(unico["lineas"]) == 1
    assert unico["lineas"][0][0] == [34.0, 51.0] and unico["lineas"][0][-1] == [33.2, 50.5]
    assert 200 <= unico["flechas"][0]["rumbo"] <= 250  # hacia el suroeste
    assert unico["pistas"] == ["a", "b"]


def test_si_no_se_sabe_cual_sigue_no_se_une() -> None:
    a = pista("a", [(t("20:00"), 51.0, 34.0, 4), (t("20:10"), 50.8, 33.7, 4)])
    b = pista("b", [(t("20:14"), 50.75, 33.6, 4), (t("20:30"), 50.5, 33.2, 4)])
    c = pista("c", [(t("20:15"), 50.76, 33.62, 4), (t("20:31"), 50.5, 33.3, 4)])
    trozos = recorridos.trozos_neptun([a, b, c])
    recorridos.enlazar(trozos)
    # De un solo aparato salen dos pistas posibles: no se sabe cuál es la suya, no se une ninguna.
    assert all(not t.sucesores for t in trozos)


def test_un_grupo_que_se_divide_se_bifurca() -> None:
    a = pista("a", [(t("20:00"), 51.0, 34.0, 4), (t("20:10"), 50.8, 33.7, 4)], numero=2)
    b = pista("b", [(t("20:14"), 50.75, 33.6, 4), (t("20:30"), 50.5, 33.2, 4)])
    c = pista("c", [(t("20:15"), 50.76, 33.62, 4), (t("20:31"), 50.45, 33.5, 4)])
    trozos = recorridos.trozos_neptun([a, b, c])
    recorridos.enlazar(trozos)
    lista, _ = recorridos.recorridos(trozos)
    assert len(lista) == 1 and lista[0]["division"] and len(lista[0]["lineas"]) == 2


def test_un_aviso_de_region_entera_enlaza_pero_no_se_dibuja() -> None:
    """Una pista que solo dice la región entera une el recorrido de antes con el de después,
    pero la línea pasa de largo por ella y la franja nunca es una mancha de media región."""
    a = pista("a", [(t("20:00"), 51.0, 34.0, 4), (t("20:10"), 50.8, 33.7, 4)])
    region = pista(
        "r",
        [(t("20:12"), 50.6, 33.5, 70), (t("20:25"), 50.4, 33.1, 70)],
        titulo="БпЛА — по області",
    )
    b = pista("b", [(t("20:30"), 50.3, 32.9, 4), (t("20:40"), 50.2, 32.6, 4)])
    trozos = recorridos.trozos_neptun([a, region, b])
    recorridos.enlazar(trozos)
    lista, grupo_de = recorridos.recorridos(trozos)
    assert grupo_de == [1, 1, 1]
    linea = lista[0]["lineas"][0]
    assert [50.6, 33.5] not in [[lat, lon] for lon, lat in linea]
    assert lista[0]["precision_km"]["max"] <= recorridos.ANCHO_MAX_KM
    # La franja nunca pasa del ancho máximo a cada lado de la línea.
    assert geometria.distancia_km(*_mas_lejano(lista[0])) <= recorridos.ANCHO_MAX_KM + 1


def _mas_lejano(recorrido: dict[str, Any]) -> tuple[float, float, float, float]:
    """El punto de la franja más lejos de la línea y el punto de la línea más cercano a él."""
    linea = recorrido["lineas"][0]
    peor = (0.0, 0.0, 0.0, 0.0)
    distancia = -1.0
    for lon, lat in recorrido["franjas"][0]:
        cerca = min(linea, key=lambda p: geometria.distancia_km(lat, lon, p[1], p[0]))
        d = geometria.distancia_km(lat, lon, cerca[1], cerca[0])
        if d > distancia:
            distancia, peor = d, (lat, lon, cerca[1], cerca[0])
    return peor


def test_la_noche_publicada_lleva_los_recorridos_ordenados_por_aparatos() -> None:
    datos = copia()
    entrada = datos["noches"][0]
    documento = calculo.noche_publica(entrada["noche"], entrada["ataque"], sin_frontera, True)
    assert documento is not None
    lista = documento["recorridos"]
    assert lista and [r["grupo"] for r in lista] == list(range(1, len(lista) + 1))
    aparatos = [r["aparatos"] or 1 for r in lista]
    assert aparatos == sorted(aparatos, reverse=True)
    assert all(r["longitud_km"] >= recorridos.LONGITUD_MIN_KM for r in lista)
    assert all("franja" not in t for t in documento["tramos"])


def test_apagadas_en_la_web_no_se_suben_y_se_retiran(tmp_path: Path) -> None:
    """Con el interruptor apagado se calculan y se guardan, pero no se suben: lo subido antes se
    retira del almacén público. Al encenderlo se vuelve a subir todo."""
    noches_ = tmp_path / "publicar" / "noches"
    noches_.mkdir(parents=True)
    (noches_ / "2026-10-05.json").write_text("{}", encoding="utf-8")
    (tmp_path / "publicar" / "indice.json").write_text("{}", encoding="utf-8")
    (tmp_path / rutas.SUBIDOS).write_text(
        json.dumps({"rutas/indice.json": "a", "rutas/noches/2026-10-05.json": "b"}),
        encoding="utf-8",
    )
    subidos: list[str] = []
    borrados: list[str] = []

    def subir(objeto: str, cuerpo: bytes, tipo: str, cache: str) -> bool:
        subidos.append(objeto)
        return True

    def borrar(objeto: str) -> bool:
        borrados.append(objeto)
        return True

    assert rutas._subir_cambios(tmp_path, subir, borrar, publicar=False) == 0
    assert subidos == [] and sorted(borrados) == [
        "rutas/indice.json",
        "rutas/noches/2026-10-05.json",
    ]
    assert (noches_ / "2026-10-05.json").exists()
    assert rutas._subir_cambios(tmp_path, subir, borrar, publicar=True) == 2
    assert sorted(subidos) == ["rutas/indice.json", "rutas/noches/2026-10-05.json"]


def test_el_interruptor_de_la_web_esta_apagado() -> None:
    assert rutas.en_la_web() is False


def test_el_indice_solo_sube_si_han_subido_todas_sus_noches(tmp_path: Path) -> None:
    """Si falla la subida de una noche, el índice no se sube: la web nunca lee un índice que nombra
    una noche que no está en el almacén. En la siguiente pasada sube lo que faltaba y el índice."""
    noches_ = tmp_path / "publicar" / "noches"
    noches_.mkdir(parents=True)
    (noches_ / "2026-10-05.json").write_text('{"a": 1}', encoding="utf-8")
    (noches_ / "2026-10-06.json").write_text('{"b": 2}', encoding="utf-8")
    (tmp_path / "publicar" / "indice.json").write_text('{"i": 1}', encoding="utf-8")
    subidos: list[str] = []
    falla = {"rutas/noches/2026-10-06.json"}

    def subir(objeto: str, cuerpo: bytes, tipo: str, cache: str) -> bool:
        if objeto in falla:
            return False
        subidos.append(objeto)
        return True

    assert rutas._subir_cambios(tmp_path, subir, None, publicar=True) == 1
    assert subidos == ["rutas/noches/2026-10-05.json"]
    falla.clear()
    assert rutas._subir_cambios(tmp_path, subir, None, publicar=True) == 2
    assert subidos[1:] == ["rutas/noches/2026-10-06.json", "rutas/indice.json"]
