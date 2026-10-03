"""Motor de deducción 1.1.0 en Europa: hora y duración de mejor origen, viento de esa hora,
deriva hora a hora con solo el día, dirección de entrada (declarada y deducida) y lectores de las
fuentes oficiales españolas y portuarias. Sin red."""

import json
import math
from datetime import UTC, date, datetime
from typing import Any

from proceso.deduccion import catalogo, deriva, direccion, geo, motor, zona_despegue
from recogida import deduccion, oficiales
from tests import ejemplos


def _incidente() -> dict[str, Any]:
    documento = ejemplos.incidente_minimo()
    documento["lugar"] = {"punto": {"lat": 54.6349, "lon": 25.2876}, "radio_km": 5.0, "pais": "LT"}
    documento["tiempo"] = {"inicio": ejemplos.instante("2025-10-24T00:00Z", "dia")}
    return documento


def test_el_caso_usa_la_hora_y_la_duracion_de_mejor_origen() -> None:
    mejor = {
        "tiempo": {"inicio": ejemplos.instante("2025-10-24T18:42Z"), "duracion_min": 95},
        "origen": "medido",
        "regla": "cierre_medido",
    }
    caso = motor.caso_de_incidente(_incidente(), None, None, [], mejor)
    assert caso.precision == "minuto" and caso.duracion_min == 95
    assert caso.inicio == datetime(2025, 10, 24, 18, 42, tzinfo=UTC).timestamp()
    assert caso.origen_inicio == "medido"
    # Sin mejor origen, el de la base.
    assert motor.caso_de_incidente(_incidente(), None, None).precision == "dia"


def test_las_frases_de_una_autoridad_dan_la_entrada_y_la_descripcion() -> None:
    frases = [
        ("oficial_citado", "F1-declaracion-1",
         "the drone entered the country's airspace from neighbouring Belarus", "en"),
        ("prensa", "F2", "a large drone with fixed wings", "en"),
    ]  # fmt: skip
    caso = motor.caso_de_incidente(_incidente(), None, None, [], None, frases)
    assert caso.entrada_desde is not None and caso.entrada_desde["pais"] == "BY"
    assert caso.entrada_confirmada and caso.entrada_exterior
    assert "a large drone with fixed wings" in caso.textos
    # La prensa sola no declara la entrada.
    solo_prensa = [("prensa", "F2", "the drone entered from Belarus", "en")]
    assert (
        motor.caso_de_incidente(_incidente(), None, None, [], None, solo_prensa).entrada_desde
        is None
    )


def _lugar(velocidad: float, desde: float) -> dict[str, Any]:
    niveles = {
        n: {"viento_ms": velocidad, "direccion": desde} for n in ("1000", "925", "850", "700")
    }
    return {"superficie": {"viento_10m_ms": velocidad, "direccion_10m": desde,
                           "viento_100m_ms": velocidad, "direccion_100m": desde},
            "niveles": niveles}  # fmt: skip


def test_deriva_hora_a_hora_solo_decide_si_todas_las_horas_coinciden() -> None:
    real = catalogo.cargar()
    # Punto en Rumanía a unos 60 km al oeste de Ucrania: el viento del este lo lleva hasta allí.
    lat, lon = 47.6, 26.3
    origen = geo.punto_mas_cercano("UA", lat, lon)
    assert origen is not None
    rumbo = geo.rumbo(origen[0], origen[1], lat, lon)
    a_favor = _lugar(12.0, (rumbo + 180.0) % 360.0)
    en_contra = _lugar(12.0, rumbo)
    todas = deriva.evaluar_horas(real, "senuelo_largo_alcance", lat, lon, [a_favor] * 24)
    assert todas is not None and todas.resultado != deriva.NO_COMPATIBLE
    assert todas.datos["horas"] == 24
    contrarias = deriva.evaluar_horas(real, "senuelo_largo_alcance", lat, lon, [en_contra] * 24)
    assert contrarias is not None and contrarias.resultado == deriva.NO_COMPATIBLE
    mezcla = deriva.evaluar_horas(real, "senuelo_largo_alcance", lat, lon,
                                  [a_favor] * 12 + [en_contra] * 12)  # fmt: skip
    # Con solo el día pudo ser a cualquier hora: basta una hora a sotavento.
    assert mezcla is not None and mezcla.resultado == deriva.COMPATIBLE
    assert mezcla.datos["por_resultado"][deriva.COMPATIBLE] == 12
    flojo = _lugar(0.5, 90.0)
    sin_decidir = deriva.evaluar_horas(real, "senuelo_largo_alcance", lat, lon,
                                       [en_contra] * 12 + [flojo] * 12)  # fmt: skip
    assert sin_decidir is not None and sin_decidir.resultado == deriva.INDETERMINADO


def test_direccion_declarada_apunta_al_pais_de_entrada() -> None:
    # Vilna: Bielorrusia está al este y al sur, a unos 30 km.
    entrada = direccion.declarada(54.6349, 25.2876, "BY", "oficial_citado", "F1", "frase")
    assert entrada is not None and entrada["tipo"] == "declarada"
    assert 60 <= entrada["desde_grados"] <= 200
    assert entrada["distancia_km"] < 50


def test_direccion_deducida_por_sectores_de_la_zona_de_despegue() -> None:
    real = catalogo.cargar()
    # Copenhague con viento del oeste: la zona de despegue queda a barlovento (al oeste).
    lat, lon = 55.618, 12.656
    viento = (6.0, 0.0)  # hacia el este (este, norte) en m/s: sopla del oeste
    zona = zona_despegue.calcular(real, "multirrotor_consumo", "DK", lat, lon, viento)
    assert isinstance(zona, zona_despegue.Zona)
    documento = {**zona.documento(), "viento_medido": True}
    resultado = direccion.deducida(real, lat, lon, [documento])
    assert resultado is not None and resultado["tipo"] == "deducida"
    assert math.isclose(sum(resultado["sectores"]), 1.0, abs_tol=1e-6)
    if "desde_grados" in resultado:
        assert 180 <= resultado["desde_grados"] <= 360
    # Sin viento medido no se deduce nada.
    assert direccion.deducida(real, lat, lon, [{**documento, "viento_medido": False}]) is None


def test_el_viento_de_la_hora_del_caso_y_las_horas_del_dia(monkeypatch: Any) -> None:
    pedidos: list[date] = []

    def horario(lat: float, lon: float, dia: date) -> dict[str, list[Any]]:
        pedidos.append(dia)
        horas = [f"{dia.isoformat()}T{h:02d}:00" for h in range(24)]
        return {"time": horas, **{v: [5.0] * 24 for v in ("wind_speed_10m", "wind_speed_100m")},
                **{v: [270.0] * 24
                   for v in ("wind_direction_10m", "wind_direction_100m")}}  # fmt: skip

    con_hora = motor.caso_de_incidente(_incidente(), None, None, [], {
        "tiempo": {"inicio": ejemplos.instante("2025-10-24T18:42Z")},
        "origen": "medido"})  # fmt: skip
    deduccion.con_viento_de_su_hora(con_hora, horario)
    assert con_hora.condiciones is not None
    assert con_hora.condiciones["lugar"]["momento"]["precision"] == "hora"
    # Con solo el día y entrada desde fuera en un país de la OTAN: las 24 horas del día local.
    solo_dia = motor.caso_de_incidente(_incidente(), None, None)
    solo_dia.entrada_exterior = True
    deduccion.con_viento_de_su_hora(solo_dia, horario)
    assert len(solo_dia.lugares_horas) == 24
    assert set(pedidos) == {date(2025, 10, 23), date(2025, 10, 24)}


# --- Fuentes oficiales: RSS y Atom -----------------------------------------------------

ATOM = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom"><title>Notas</title>
<entry><title>Neutralizado un dron en las inmediaciones de la base</title>
<link href="../../gabinete/notasPrensa/2026/10/DGC-261002-dron.html"/>
<published>2026-10-02T09:19:48Z</published><summary>Un dron fue detectado</summary></entry>
</feed>"""


def test_el_lector_de_notas_oficiales_lee_atom_con_enlaces_relativos() -> None:
    fuente = {"id": "mde_es", "medio": "Ministerio de Defensa", "pais": "ES", "idioma": "es",
              "tipo": "rss",
              "url": "https://www.defensa.gob.es/comun/rssChannel/rssNotasPrensa.xml"}  # fmt: skip
    assert oficiales.es_canal(ATOM)
    notas = oficiales.leer_rss(ATOM, fuente)
    assert len(notas) == 1
    assert notas[0].enlace == ("https://www.defensa.gob.es/gabinete/notasPrensa/2026/10/"
                               "DGC-261002-dron.html")  # fmt: skip
    assert notas[0].fecha == datetime(2026, 10, 2, 9, 19, 48, tzinfo=UTC)
    assert notas[0].texto == "Un dron fue detectado"


def test_las_fuentes_oficiales_espanolas_y_portuarias_estan_en_la_recogida() -> None:
    fuentes = {f["id"]: f for f in oficiales.fuentes()}
    for id_ in ("aesa", "mde_es", "puertos_del_estado", "csn_sucesos", "valenciaport"):
        assert fuentes[id_]["pais"] == "ES" and fuentes[id_]["tipo"] == "rss"
    for id_ in ("port_gdansk", "tallinna_sadam", "koge_havn"):
        assert fuentes[id_]["tipo"] == "rss"


def test_la_configuracion_del_barrido_tiene_sus_fuentes_y_su_ritmo() -> None:
    from recogida import catalogo_vivo

    configuracion = json.loads(catalogo_vivo.CONFIGURACION.read_text(encoding="utf-8"))
    por_id = {f["id"]: f for f in configuracion["fuentes"]}
    assert por_id["war_sanctions"]["ritmo"] == "diario"
    assert por_id["propios"]["ritmo"] == "diario"
    assert all(f["ritmo"] == "semanal" for i, f in por_id.items()
               if i not in {"war_sanctions", "propios"})  # fmt: skip
    tipos = {f["tipo"] for f in por_id.values()}
    assert {"fabricante", "inteligencia", "lista_oficial", "autoridad", "analisis_tecnico",
            "prensa_tecnica", "propios"} <= tipos  # fmt: skip
