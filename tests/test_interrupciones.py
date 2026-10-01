"""Cobertura, línea base, interrupciones, desvíos, exclusión meteorológica con METAR reales y
evaluación de un incidente, sin red. Los días son sintéticos: un aeropuerto con un movimiento
cada 3 minutos y los mismos vuelos cada semana, como un horario de verano."""

import csv
import gzip
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from almacen.base import Almacen
from proceso import mediciones, metar, trafico, vuelos
from recogida import referencia
from tests import ejemplos

FIXTURES = Path(__file__).parent / "fixtures" / "trafico"
DIA = date(2025, 9, 22)
AHORA = datetime(2025, 9, 23, 9, 17, tzinfo=UTC)
CIERRE = (datetime(2025, 9, 22, 18, 27, tzinfo=UTC), datetime(2025, 9, 22, 22, 37, tzinfo=UTC))


def instante(texto: str) -> float:
    return datetime.fromisoformat(texto).replace(tzinfo=UTC).timestamp()


def dia_sintetico(
    dia: date, hueco: tuple[datetime, datetime] | None = None, desviados: int = 0, paso: int = 180
) -> trafico.DiaTrafico:
    """Un movimiento cada 3 minutos de 04:00 a 23:57 en EKCH, alternando llegadas y salidas,
    con el mismo indicativo para la misma hora todas las semanas. En el hueco no hay
    movimientos; las primeras `desviados` llegadas del hueco aterrizan en Malmö."""
    inicio = trafico.inicio_dia(dia)
    filas: dict[str, list[list[Any]]] = {"EKCH": [], "ESMS": []}
    desviadas = 0
    por_hora = 3600 // paso
    for k in range(4 * por_hora, 24 * por_hora):
        t = inicio + k * paso
        tipo = "L" if k % 2 else "D"
        fila = ["EKCH", tipo, t, f"{k:06x}", f"SAS{k}", "A20N", 1]
        if hueco and hueco[0].timestamp() <= t <= hueco[1].timestamp():
            if tipo == "L" and desviadas < desviados:
                filas["ESMS"].append(["ESMS", "L", t + 1200, f"{k:06x}", f"SAS{k}", "A20N", 1])
                desviadas += 1
            continue
        filas["EKCH"].append(fila)
    return trafico.DiaTrafico(
        dia, f"v{dia}", f"https://github.com/adsblol/x/{dia}", filas, [], [], []
    )


class Lector:
    def __init__(self, dias: dict[date, trafico.DiaTrafico]) -> None:
        self.dias = dias

    def __call__(self, dia: date) -> trafico.DiaTrafico | None:
        return self.dias.get(dia)


def lector(semanas: int = 4, hueco: bool = True, desviados: int = 12) -> Lector:
    dias = {DIA: dia_sintetico(DIA, CIERRE if hueco else None, desviados)}
    dias[DIA + timedelta(days=1)] = dia_sintetico(DIA + timedelta(days=1))
    for k in range(1, semanas + 1):
        for extra in (0, 1):
            d = DIA - timedelta(weeks=k) + timedelta(days=extra)
            dias[d] = dia_sintetico(d)
    return Lector(dias)


def siempre(_: date) -> bool:
    return True


def leer_metares() -> dict[str, list[metar.Metar]]:
    resultado: dict[str, list[metar.Metar]] = {}
    with (FIXTURES / "metar.csv").open(encoding="utf-8") as f:
        for fila in csv.DictReader(f):
            hora = datetime.strptime(fila["valid"], "%Y-%m-%d %H:%M").replace(tzinfo=UTC)
            resultado.setdefault(fila["station"], []).append(metar.leer(hora, fila["metar"]))
    return resultado


METARES = leer_metares()


# --- Línea base e interrupciones -------------------------------------------------------


def test_cierre_de_copenhague_con_su_hora_medida() -> None:
    inicio = trafico.inicio_dia(DIA)
    (cierre,) = trafico.interrupciones("EKCH", inicio, inicio + 86400, lector(), siempre) or []
    assert cierre.precision == "movimientos"
    assert trafico.instante(cierre.inicio) == "2025-09-22T18:24Z"
    assert trafico.instante(cierre.fin) == "2025-09-22T22:39Z"
    assert cierre.duracion_min == 255
    assert cierre.semanas_base == 4
    # 85 franjas de 3 minutos sin movimientos: la mitad llegadas.
    assert cierre.llegadas_perdidas + cierre.salidas_perdidas == pytest.approx(83, abs=3)


def test_los_desvios_salen_de_los_vuelos_que_aterrizan_en_otro_aeropuerto() -> None:
    inicio = trafico.inicio_dia(DIA)
    (cierre,) = (
        trafico.interrupciones("EKCH", inicio, inicio + 86400, lector(desviados=12), siempre) or []
    )
    assert cierre.desvios == 12
    assert cierre.desvios_base == 0


def test_un_dia_normal_no_tiene_interrupciones() -> None:
    inicio = trafico.inicio_dia(DIA)
    assert (
        trafico.interrupciones("EKCH", inicio, inicio + 86400, lector(hueco=False), siempre) == []
    )


def test_sin_dos_semanas_de_linea_base_no_se_evalua() -> None:
    inicio = trafico.inicio_dia(DIA)
    assert (
        trafico.interrupciones("EKCH", inicio, inicio + 86400, lector(semanas=1), siempre) is None
    )


def test_un_dia_que_falta_en_la_ventana_deja_la_evaluacion_pendiente() -> None:
    datos = lector()
    del datos.dias[DIA]
    inicio = trafico.inicio_dia(DIA)
    assert trafico.interrupciones("EKCH", inicio, inicio + 86400, datos, siempre) is None


def test_un_avion_suelto_en_mitad_del_cierre_no_parte_el_hueco() -> None:
    # Como en Copenhague: el tráfico se para a las 18:26, un avión aterriza a las 19:25 y el
    # tráfico vuelve a las 22:38.
    base = datetime(2025, 9, 22, tzinfo=UTC).timestamp()
    tiempos = [base + 17 * 3600 + k * 180 for k in range(29)]  # hasta las 18:24
    tiempos += [base + 18 * 3600 + 26 * 60, base + 19 * 3600 + 25 * 60]
    tiempos += [base + 22 * 3600 + 38 * 60 + k * 180 for k in range(20)]
    a_t, b_t = base + 18.5 * 3600, base + 22.5 * 3600
    inicio, fin, precision = trafico._bordes(tiempos, a_t, b_t, sueltos=4)
    assert (trafico.instante(inicio), trafico.instante(fin), precision) == (
        "2025-09-22T18:26Z",
        "2025-09-22T22:38Z",
        "movimientos",
    )


def test_una_ventana_que_pasa_de_medianoche_se_recorta_a_los_dias_procesados() -> None:
    datos = lector()
    del datos.dias[DIA + timedelta(days=1)]
    contexto = entorno(datos)
    inicio = trafico.inicio_dia(DIA)
    assert mediciones.recortar(contexto, DIA, inicio + 20 * 3600, inicio + 27 * 3600) == (
        inicio + 20 * 3600,
        inicio + 86400,
    )
    # Con el día siguiente procesado, la ventana sigue entera.
    assert mediciones.recortar(entorno(lector()), DIA, inicio + 20 * 3600, inicio + 27 * 3600) == (
        inicio + 20 * 3600,
        inicio + 27 * 3600,
    )


def test_la_linea_base_se_calcula_franja_a_franja() -> None:
    datos = lector()
    # Al día siguiente solo le queda una semana de línea base: sus franjas no cuentan.
    for k in (2, 3, 4):
        del datos.dias[DIA + timedelta(days=1) - timedelta(weeks=k)]
    inicio = trafico.inicio_dia(DIA) + 20 * 3600
    base = trafico.linea_base("EKCH", inicio, 32, datos, siempre)
    assert base is not None
    serie, semanas = base
    assert semanas == 4
    assert serie.movimientos[0] > 0 and serie.movimientos[-1] == 0.0


def test_tramos_bajos() -> None:
    base = [10.0] * 10
    # Dos franjas bajas, una intermedia a la mitad y otra baja: un solo tramo.
    vista = [10, 10, 1, 0, 5, 0, 10, 10, 10, 10]
    assert trafico.tramos_bajos([float(v) for v in vista], base) == [(2, 5)]
    # Una franja baja sola con poca base no es una interrupción.
    assert trafico.tramos_bajos([0.0, 4.0], [4.0, 4.0]) == []


# --- Exclusión meteorológica con METAR reales -------------------------------------------


def test_lectura_de_metar_reales() -> None:
    ekch = METARES["EKCH"][3]
    assert (ekch.viento_dir, ekch.viento_kt, ekch.visibilidad_m, ekch.techo_ft) == (
        250,
        7.0,
        9999,
        None,
    )
    (essa,) = METARES["ESSA"]
    assert (essa.visibilidad_m, essa.techo_ft, essa.fenomenos) == (700, 600, ["-SN"])
    (efhk,) = METARES["EFHK"]
    assert efhk.visibilidad_m == 900 and "FG" in efhk.fenomenos and efhk.techo_ft == 200


@pytest.mark.parametrize(
    ("estacion", "motivos"),
    [
        ("EDJA", ["tormenta"]),
        ("ENBN", ["tormenta"]),
        ("ESSA", ["nieve_o_engelamiento"]),
        ("EFHK", ["niebla"]),
        ("EDDG", []),  # niebla en bancos (BCFG): no cierra
    ],
)
def test_motivos_meteorologicos(estacion: str, motivos: list[str]) -> None:
    assert metar.motivos(METARES[estacion][0]) == motivos


def test_el_tiempo_no_explica_el_cierre_de_copenhague() -> None:
    assert metar.explica(METARES["EKCH"], CIERRE[0] - timedelta(hours=1), CIERRE[1]) == []


def test_viento_y_pista_cerrada_por_nieve() -> None:
    hora = datetime(2025, 1, 1, tzinfo=UTC)
    assert metar.motivos(metar.leer(hora, "ENXX 010020Z 24038G52KT 9999 FEW020 M02/M06 Q0980")) == [
        "viento"
    ]
    assert "pista_contaminada" in metar.motivos(
        metar.leer(hora, "ENXX 010020Z 24010KT 9999 R/SNOCLO Q0980")
    )


def test_una_interrupcion_con_tormenta_queda_explicada() -> None:
    inicio = trafico.inicio_dia(DIA)
    tormenta = metar.leer(CIERRE[0] - timedelta(minutes=10), METARES["EDJA"][0].texto)
    (cierre,) = (
        trafico.interrupciones(
            "EKCH", inicio, inicio + 86400, lector(), siempre, lambda o, a, b: [tormenta]
        )
        or []
    )
    assert (
        cierre.motivos_meteorologicos == ["techo", "tormenta"]
        or "tormenta" in cierre.motivos_meteorologicos
    )


# --- Cobertura ----------------------------------------------------------------------------


def test_niveles_de_cobertura() -> None:
    ref = trafico.Referencia(800.0, "eurocontrol")
    assert trafico.nivel_cobertura(700, ref)[1] == "alta"
    assert trafico.nivel_cobertura(500, ref)[1] == "media"
    assert trafico.nivel_cobertura(300, ref)[1] == "insuficiente"
    assert trafico.nivel_cobertura(300, None)[1] == "insuficiente"
    propia = trafico.Referencia(300.0, "mediana_propia")
    assert trafico.nivel_cobertura(290, propia)[1] == "media"
    assert trafico.nivel_cobertura(100, propia)[1] == "insuficiente"
    assert (
        trafico.nivel_cobertura(15, trafico.Referencia(15.0, "mediana_propia"))[1] == "insuficiente"
    )


def test_cobertura_con_la_mediana_de_la_propia_serie_si_no_hay_referencia() -> None:
    cobertura = trafico.cobertura("EKCH", DIA, lector(hueco=False), lambda o, d: None)
    assert cobertura is not None and cobertura.referencia is not None
    assert cobertura.referencia.origen == "mediana_propia"
    assert cobertura.nivel == "media"


def test_referencia_de_eurocontrol_y_su_estimacion(tmp_path: Path) -> None:
    filas = [
        "YEAR,MONTH_NUM,MONTH_MON,FLT_DATE,APT_ICAO,APT_NAME,STATE_NAME,FLT_DEP_1,FLT_ARR_1,FLT_TOT_1"
    ]
    for k in range(28):
        d = date(2025, 8, 4) + timedelta(days=k)
        filas.append(f"2025,08,AUG,{d},EKCH,Copenhagen,Denmark,400,{400 + k},{800 + k}")
    destino = referencia.ruta(tmp_path, 2025)
    destino.parent.mkdir(parents=True)
    destino.write_bytes(gzip.compress("\n".join(filas).encode()))
    refs = referencia.Referencias(tmp_path)
    assert refs("EKCH", date(2025, 8, 4)) == trafico.Referencia(800.0, "eurocontrol")
    estimada = refs("EKCH", date(2025, 9, 22))  # lunes: lunes 11, 18, 25 de agosto y 1 sept
    assert estimada is not None and estimada.origen == "eurocontrol_estimada"
    assert refs("LEMD", date(2025, 8, 4)) is None


# --- Incidente ------------------------------------------------------------------------------


def incidente(inicio: str = "2025-09-22T18:30Z", precision: str = "hora") -> dict[str, Any]:
    documento = ejemplos.incidente_minimo()
    documento["tiempo"] = {
        "inicio": {"valor": inicio, "precision": precision},
        "fin": {"valor": "2025-09-22T23:00Z", "precision": "hora"},
    }
    documento["tipo"] = "interrupcion_aeroportuaria"
    documento["objetivo"] = {"categoria": "aeropuerto", "oaci": "EKCH"}
    documento["lugar"] = {"pais": "DK", "punto": {"lat": 55.618, "lon": 12.656}, "radio_km": 3}
    documento["consecuencias"] = {
        "cierre": {"valor": "si"},
        "vuelos_desviados": {"min": 35, "max": 35},
    }
    return documento


def entorno(
    datos: Lector, referencia_: float | None = 350.0, perdidos: set[date] | None = None
) -> mediciones.Entorno:
    return mediciones.Entorno(
        lector=datos,
        procesados=sorted(datos.dias),
        perdidos=perdidos or set(),
        referencias=lambda o, d: (
            None if referencia_ is None else trafico.Referencia(referencia_, "eurocontrol")
        ),
        metares=lambda o, a, b: [m for m in METARES.get(o, []) if a <= m.hora.timestamp() <= b],
        resumen=lambda d: {"procesado": "2025-09-23T04:00:00Z"} if d in datos.dias else None,
        aeropuertos={a.oaci: a for a in vuelos.cargar_aeropuertos()},
    )


def test_cierre_medido_del_incidente() -> None:
    documento = mediciones.evaluar_incidente(incidente(), entorno(lector()), AHORA)
    assert documento is not None
    cierre = documento["cierre"]
    assert cierre["resultado"] == "cierre_medido"
    assert (cierre["inicio"]["valor"], cierre["fin"]["valor"]) == (
        "2025-09-22T18:24Z",
        "2025-09-22T22:39Z",
    )
    assert cierre["vuelos_desviados"] == 12
    assert cierre["cobertura"]["nivel"] == "alta"
    assert cierre["diferencias"] == ["vuelos_desviados"] and cierre["difiere_de_declarado"] is True
    assert documento["origen"] == "medido" and documento["metodo"] == "regla"
    assert documento["datos"] == [
        "https://github.com/adsblol/x/2025-09-22",
        "https://github.com/adsblol/x/2025-09-23",
    ]


def test_con_cobertura_insuficiente_no_se_interpreta_el_hueco() -> None:
    documento = mediciones.evaluar_incidente(
        incidente(), entorno(lector(), referencia_=5000.0), AHORA
    )
    assert documento is not None
    assert documento["cierre"]["resultado"] == "cobertura_insuficiente"
    assert "inicio" not in documento["cierre"]


def test_un_dia_que_adsblol_no_publico_deja_el_cierre_sin_datos() -> None:
    datos = lector()
    del datos.dias[DIA]
    documento = mediciones.evaluar_incidente(incidente(), entorno(datos, perdidos={DIA}), AHORA)
    assert documento is not None and documento["cierre"]["resultado"] == "sin_datos"
    assert documento["respuesta_militar"]["resultado"] == "sin_datos"


def test_un_dia_aun_no_procesado_deja_el_incidente_pendiente() -> None:
    datos = lector()
    del datos.dias[DIA]
    assert mediciones.evaluar_incidente(incidente(), entorno(datos), AHORA) is None


def test_con_solo_el_dia_se_busca_en_el_dia_entero() -> None:
    documento = mediciones.evaluar_incidente(
        incidente("2025-09-22T00:00Z", "dia"), entorno(lector()), AHORA
    )
    assert documento is not None and documento["cierre"]["resultado"] == "cierre_medido"
    assert documento["ventana"]["inicio"]["valor"] == "2025-09-22T00:00Z"


def test_con_solo_el_dia_un_bajon_corto_no_casa() -> None:
    # Un aeropuerto con un movimiento por minuto y 20 minutos sin tráfico.
    corto = (datetime(2025, 9, 22, 9, 0, tzinfo=UTC), datetime(2025, 9, 22, 9, 20, tzinfo=UTC))
    datos = Lector({d: dia_sintetico(d, paso=60) for d in lector(hueco=False).dias})
    datos.dias[DIA] = dia_sintetico(DIA, corto, paso=60)
    documento = incidente("2025-09-22T00:00Z", "dia")
    resultado = mediciones.evaluar_incidente(documento, entorno(datos), AHORA)
    assert resultado is not None and resultado["cierre"]["resultado"] == "sin_interrupcion"
    # Con hora, el mismo bajón casa.
    documento = incidente("2025-09-22T09:00Z", "hora")
    documento["tiempo"]["fin"] = {"valor": "2025-09-22T09:30Z", "precision": "minuto"}
    resultado = mediciones.evaluar_incidente(documento, entorno(datos), AHORA)
    assert resultado is not None and resultado["cierre"]["resultado"] == "cierre_medido"


def test_el_dia_siguiente_sin_cobertura_no_tumba_la_medida() -> None:
    datos = lector()
    siguiente = DIA + timedelta(days=1)
    datos.dias[siguiente] = trafico.DiaTrafico(siguiente, "v", "https://github.com/adsblol/x/s", {})
    resultado = mediciones.evaluar_incidente(incidente(), entorno(datos), AHORA)
    assert resultado is not None and resultado["cierre"]["resultado"] == "cierre_medido"


def test_de_madrugada_no_hay_trafico_que_interrumpir() -> None:
    # Como en Oslo: el incidente es de 00:30 a 02:00, cuando no hay vuelos programados.
    documento = incidente("2025-09-22T00:30Z", "hora")
    documento["tiempo"]["fin"] = {"valor": "2025-09-22T02:00Z", "precision": "hora"}
    resultado = mediciones.evaluar_incidente(documento, entorno(lector()), AHORA)
    assert resultado is not None
    cierre = resultado["cierre"]
    assert cierre["resultado"] == "sin_trafico_esperado"
    assert cierre["indicios"]["base_ventana"] == 0


def test_sin_interrupcion_guarda_los_indicios_de_la_ventana() -> None:
    documento = incidente("2025-09-22T12:00Z", "hora")
    documento["tiempo"]["fin"] = {"valor": "2025-09-22T13:00Z", "precision": "hora"}
    resultado = mediciones.evaluar_incidente(documento, entorno(lector()), AHORA)
    assert resultado is not None and resultado["cierre"]["resultado"] == "sin_interrupcion"
    assert resultado["cierre"]["indicios"]["vistos_ventana"] >= 19


def test_un_incidente_lejos_de_un_aeropuerto_regular_no_tiene_cierre() -> None:
    documento = incidente()
    documento["objetivo"] = {"categoria": "base_militar"}
    resultado = mediciones.evaluar_incidente(documento, entorno(lector()), AHORA)
    assert resultado is not None and resultado["cierre"] == {"resultado": "no_aplicable"}
    assert resultado["interferencia_gnss"]["resultado"] == "medida"


def test_diferencias_con_lo_declarado() -> None:
    cierre = {"duracion_min": 250, "vuelos_desviados": 31}
    assert (
        mediciones.diferencias(
            cierre, {"cierre": {"valor": "si", "minutos": {"min": 240, "max": 240}}}
        )
        == []
    )
    assert mediciones.diferencias(
        cierre, {"cierre": {"valor": "si", "minutos": {"min": 60, "max": 60}}}
    ) == ["duracion"]
    assert mediciones.diferencias(cierre, {"cierre": {"valor": "no"}}) == ["cierre"]


def test_solo_un_hueco_real_largo_es_anomalia_candidata() -> None:
    def interrupcion(minutos: int, perdidos: float, precision: str) -> trafico.Interrupcion:
        return trafico.Interrupcion(
            "EKCH", 0.0, minutos * 60.0, precision, 0, 0, perdidos, 0.0, 0, 0.0, 0, 0.0, 0, 0.0, 4
        )

    assert mediciones.significativa(interrupcion(65, 12, "movimientos"))
    assert not mediciones.significativa(interrupcion(16, 10, "movimientos"))  # corta
    assert not mediciones.significativa(interrupcion(45, 6, "movimientos"))  # pequeña
    # Solo bajó: perdió 80 de una base de 200.
    baja = interrupcion(150, 200, "franjas")
    baja.llegadas_vistas = 120
    assert not mediciones.significativa(baja)
    # Casi parado aunque con algún movimiento suelto (Múnich, 3 de octubre de 2025).
    assert mediciones.significativa(interrupcion(135, 97, "franjas"))


def test_anomalias_casadas_y_candidatas() -> None:
    almacen = Almacen.abrir()
    datos = lector()
    contexto = entorno(datos)
    contexto.aeropuertos = {
        "EKCH": contexto.aeropuertos["EKCH"],
        "ESMS": contexto.aeropuertos["ESMS"],
    }
    plazo = type("P", (), {"agotado": staticmethod(lambda: False)})()
    assert mediciones.anomalias_nuevas(almacen, contexto, [incidente()], AHORA, plazo) == 1
    (anomalia,) = almacen.anomalias("2025-09-22")
    assert anomalia["estado"] == "casada" and anomalia["incidentes"] == ["EODI-2025-00002"]
    otra = Almacen.abrir()
    mediciones.anomalias_nuevas(otra, contexto, [], AHORA, plazo)
    assert [a["estado"] for a in otra.anomalias("2025-09-22")] == ["candidata"]


def test_la_linea_base_compara_la_misma_hora_local_tras_el_cambio_de_hora() -> None:
    # 29 de octubre de 2025 (horario de invierno) frente al 22 (aún de verano): las 05:00 UTC
    # de ahora son las 04:00 UTC de hace una semana.
    inicio = datetime(2025, 10, 29, 5, tzinfo=UTC).timestamp()
    base = trafico.semana_anterior("EHAM", inicio, 1)
    assert datetime.fromtimestamp(base, UTC) == datetime(2025, 10, 22, 4, tzinfo=UTC)
    assert trafico.semana_anterior("EHAM", inicio, 0 + 1) != inicio - 7 * 86400
    # Sin cambio de hora en el medio, ni en Turquía.
    assert trafico.semana_anterior("EHAM", inicio + 7 * 86400, 1) == inicio
    assert trafico.semana_anterior("LTFM", inicio, 1) == inicio - 7 * 86400
