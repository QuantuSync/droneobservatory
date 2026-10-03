"""Detección en directo de cierres de aeropuerto, sin red: señal, estados de un aviso, huecos de
la fuente, respaldo automático, lectura del formato readsb, círculos y ficheros públicos."""

import gzip
import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from exportacion.campos import CAMPOS_PUBLICOS_AVISO_DIRECTO
from exportacion.proyeccion import fuera_de_lista
from proceso import directo, metar, trafico, vuelos
from recogida import directo as servicio
from recogida import directo_horaria, estado, salud

DIA = date(2025, 9, 22)
CERO = trafico.inicio_dia(DIA)


def hora(h: float) -> float:
    return CERO + h * 3600


def base_constante(por_franja: float = 4.0) -> directo.Bases:
    """Línea base de `por_franja` llegadas y otras tantas salidas cada 15 minutos, todo el día."""

    def calcular(oaci: str, dia: date) -> directo.BaseDia:
        llegadas = [por_franja] * trafico.FRANJAS_DIA
        return directo.BaseDia(oaci, dia, llegadas, list(llegadas), 4, {"SAS652": [18.4 * 3600]})

    return directo.Bases(calcular)


class Movimientos(directo.Vivos):
    """Movimientos ya reconstruidos: lo que dejaría `Vivos` con las posiciones de cada minuto."""

    def __init__(self, tiempos: list[float], filas: list[list[Any]] | None = None) -> None:
        super().__init__(())
        self.tiempos = sorted(tiempos)
        self.extra = filas or []
        self.ahora = 0.0

    def movimientos(self, oaci: str) -> list[float]:
        return [t for t in self.tiempos if t <= self.ahora - directo.POSTERIOR_S]

    def todas(self) -> list[list[Any]]:
        return [f for f in self.extra if f[2] <= self.ahora]


def cada(desde: float, hasta: float, paso_s: float) -> list[float]:
    resultado, t = [], desde
    while t < hasta:
        resultado.append(t)
        t += paso_s
    return resultado


def reproducir(
    vivos: Movimientos,
    detector: directo.Detector,
    desde: float,
    hasta: float,
) -> list[tuple[float, str]]:
    """Ciclos de un minuto; devuelve (minuto, estado) cada vez que cambia el del aviso."""
    cambios: list[tuple[float, str]] = []
    anterior = ""
    t = desde
    while t <= hasta:
        vivos.ahora = t
        detector.evaluar(["EKCH"], t, vivos)
        actual = detector.avisos[-1].estado if detector.avisos else ""
        if actual != anterior:
            cambios.append((t, actual))
            anterior = actual
        t += directo.PASO_S
    return cambios


# --- Señal y estados -------------------------------------------------------------------------

# Tráfico normal (32 movimientos por hora) salvo un cierre de 18:00 a 20:00.
PASO = 112.5
CIERRE = cada(hora(12), hora(18), PASO) + cada(hora(20), hora(23), PASO)


def test_un_cierre_se_detecta_en_minutos_y_se_reanuda() -> None:
    vivos = Movimientos(CIERRE)
    detector = directo.Detector(base_constante())
    cambios = reproducir(vivos, detector, hora(15), hora(22))
    assert [e for _, e in cambios] == [directo.POSIBLE, directo.REANUDADA]
    detectado, _ = cambios[0]
    aviso = detector.avisos[0]
    # Último movimiento a las 17:58:07; los 12 movimientos esperados llegan en 22,5 minutos,
    # más el retraso de asentamiento.
    assert hora(18) - 2 * PASO <= aviso.inicio <= hora(18) - PASO
    retraso_min = (detectado - hora(18)) / 60
    assert 20 <= retraso_min <= 32
    assert aviso.reanudado == hora(20)
    assert aviso.esperados == pytest.approx(65, abs=2)
    assert aviso.vistos <= 1
    assert 31 <= aviso.llegadas_perdidas <= 33 and 31 <= aviso.salidas_perdidas <= 33


def test_un_dia_normal_no_da_avisos() -> None:
    vivos = Movimientos(cada(hora(12), hora(23), PASO))
    detector = directo.Detector(base_constante())
    assert reproducir(vivos, detector, hora(15), hora(22)) == []


def test_un_movimiento_suelto_dentro_del_cierre_no_lo_corta() -> None:
    vivos = Movimientos([*CIERRE, hora(18.8)])
    detector = directo.Detector(base_constante())
    cambios = reproducir(vivos, detector, hora(15), hora(22))
    assert cambios[0][1] == directo.POSIBLE
    assert detector.avisos[0].reanudado == hora(20)


def test_sin_trafico_esperado_no_hay_senal() -> None:
    # De madrugada (base 0) no se puede distinguir un cierre.
    vivos = Movimientos(cada(hora(12), hora(18), PASO))
    detector = directo.Detector(base_constante(0.0))
    assert reproducir(vivos, detector, hora(15), hora(22)) == []


def test_con_cobertura_baja_en_el_momento_no_hay_senal() -> None:
    # Se ve un tercio de lo esperado en las tres horas previas: los receptores no ven bien.
    vivos = Movimientos(cada(hora(12), hora(18), 3 * PASO))
    detector = directo.Detector(base_constante())
    assert reproducir(vivos, detector, hora(15), hora(22)) == []
    assert detector.motivos["EKCH"] in ("cobertura_baja", "sin_hueco")


def test_el_mal_tiempo_explica_el_hueco() -> None:
    niebla = metar.leer(
        datetime(2025, 9, 22, 17, 50, tzinfo=UTC), "EKCH 221750Z 00000KT 0100 FG VV001"
    )

    def metares(oaci: str, desde: float, hasta: float) -> list[metar.Metar]:
        return [niebla] if desde <= niebla.hora.timestamp() <= hasta else []

    vivos = Movimientos(CIERRE)
    detector = directo.Detector(base_constante(), metares)
    assert reproducir(vivos, detector, hora(15), hora(22)) == []
    assert detector.motivos["EKCH"] in ("meteorologia", "sin_hueco")


def test_un_hueco_de_la_fuente_nunca_abre_un_aviso() -> None:
    vivos = Movimientos(CIERRE)

    def hueco(oaci: str, desde: float, hasta: float) -> bool:
        return desde < hora(20) and hasta > hora(18)

    detector = directo.Detector(base_constante(), hueco_fuente=hueco)
    assert reproducir(vivos, detector, hora(15), hora(22)) == []


def test_la_evidencia_cuenta_esperas_y_desvios_de_los_vuelos_habituales() -> None:
    filas = [
        ["EKCH", "H", round(hora(18.3)), "4ac9e1", "SAS652", "A20N", 1, round(hora(18.5)), 55.6,
         12.8],
        ["ESMS", "L", round(hora(18.9)), "4ac9e1", "SAS652", "A20N", 1],
        ["EKBI", "L", round(hora(19.5)), "4bbbbb", "RYR1EE", "B738", 1],
    ]  # fmt: skip
    vivos = Movimientos(CIERRE, filas)
    detector = directo.Detector(base_constante())
    reproducir(vivos, detector, hora(15), hora(19.6))
    aviso = detector.avisos[0]
    assert aviso.esperas == 1
    assert aviso.desvios == 1  # SAS652 aterriza habitualmente en EKCH a esa hora


def test_confirmacion_por_un_incidente_y_primera_noticia() -> None:
    aviso = directo.Aviso("EKCH", hora(18.4), hora(18.8), directo.POSIBLE, 20.0, 0)
    incidente = {
        "id": "EODI-2025-00154",
        "objetivo": {"oaci": "EKCH"},
        "tiempo": {"inicio": {"valor": "2025-09-22T18:26Z", "precision": "minuto"}},
        "fuentes": [
            {"fiabilidad": "A", "fecha": {"valor": "2025-09-22T19:30Z", "precision": "minuto"}},
            {"fiabilidad": "C", "fecha": {"valor": "2025-09-22T19:05Z", "precision": "minuto"}},
            {"fiabilidad": "C", "fecha": {"valor": "2025-09-22T00:00Z", "precision": "dia"}},
        ],
    }
    otro = {**incidente, "id": "x", "objetivo": {"oaci": "ENGM"}}
    assert directo.confirmar(aviso, [otro, incidente])
    assert aviso.estado == directo.CONFIRMADO
    assert aviso.confirmacion == {
        "tipo": "oficial",
        "incidente": "EODI-2025-00154",
        "hora": "2025-09-22T19:05Z",
    }
    assert aviso.ventaja_min == 17  # 18:48 frente a 19:05


def test_un_incidente_de_otro_dia_no_confirma() -> None:
    aviso = directo.Aviso("EKCH", hora(18.4), hora(18.8), directo.POSIBLE, 20.0, 0)
    incidente = {
        "id": "x",
        "objetivo": {"oaci": "EKCH"},
        "tiempo": {"inicio": {"valor": "2025-09-25T18:26Z", "precision": "minuto"}},
        "fuentes": [],
    }
    assert not directo.confirmar(aviso, [incidente])
    assert aviso.estado == directo.POSIBLE


def test_un_aviso_reanudado_se_publica_doce_horas_y_uno_abierto_caduca_al_dia() -> None:
    detector = directo.Detector(base_constante())
    reanudado = directo.Aviso(
        "EKCH", hora(1), hora(1.5), directo.REANUDADA, 9, 0, reanudado=hora(2)
    )
    abierto = directo.Aviso("EDDM", hora(1), hora(1.5), directo.POSIBLE, 9, 0)
    detector.avisos = [reanudado, abierto]
    detector._caducar(hora(13.9))
    assert len(detector.avisos) == 2
    detector._caducar(hora(14.1))
    assert detector.avisos == [abierto]
    detector._caducar(hora(25.6))
    assert detector.avisos == []


def test_el_aviso_se_guarda_y_se_recupera_igual() -> None:
    aviso = directo.Aviso(
        "EKCH", hora(18.4), hora(18.8), directo.CONFIRMADO, 20.5, 1, 9, 10, 3, 4,
        reanudado=hora(22.6), confirmacion={"tipo": "incidente", "incidente": "x", "hora": None},
        primera_noticia=hora(19.1), factor=0.95,
    )  # fmt: skip
    copia = directo.Aviso.de_documento(json.loads(json.dumps(aviso.documento())))
    assert copia.documento() == aviso.documento()


# --- Movimientos reconstruidos de las posiciones -----------------------------------------------


def aeropuerto_prueba() -> vuelos.Aeropuerto:
    return vuelos.Aeropuerto("EKCH", "Copenhagen Kastrup", "DK", 55.618, 12.656, 17, True, True)


def test_una_llegada_vista_cada_minuto_se_asienta_tras_desaparecer() -> None:
    vivos = directo.Vivos((aeropuerto_prueba(),))
    t0 = hora(18)
    # Aproximación desde el oeste, de 6000 pies a la pista, en 8 minutos; luego en tierra.
    for k in range(9):
        alt = None if k == 8 else 6000.0 - 750 * k
        p = directo.Posicion(
            "4ac9e1", t0 + 60 * k, 55.618, 12.656 - 0.08 * (8 - k), alt, k == 8, 150.0, 90.0,
            -700.0, "SAS652", "A20N", "A3",
        )  # fmt: skip
        vivos.anadir([p])
        vivos.actualizar(t0 + 60 * k)
    assert vivos.movimientos("EKCH") == []  # todavía no asentado
    for k in range(9, 20):
        vivos.actualizar(t0 + 60 * k)
    llegadas = vivos.movimientos("EKCH")
    assert len(llegadas) == 1
    assert t0 + 6 * 60 <= llegadas[0] <= t0 + 8 * 60
    assert vivos.filas[0][1] == "L" and vivos.filas[0][4] == "SAS652"


def test_un_avion_alto_sobre_el_aeropuerto_no_entra_en_la_traza() -> None:
    vivos = directo.Vivos((aeropuerto_prueba(),))
    vivos.anadir([directo.Posicion("4ac9e1", hora(18), 55.618, 12.656, 35000.0, False, 450.0)])
    assert vivos.aeronaves["4ac9e1"].puntos == []


def test_una_espera_en_vivo() -> None:
    vivos = directo.Vivos((aeropuerto_prueba(),))
    t0 = hora(18)
    for k in range(12):
        # Circuito de unos 10 km sobre Øresund a 7000 pies.
        lat = 55.75 + (0.04 if (k // 2) % 2 else 0.0)
        p = directo.Posicion(
            "4ac9e1", t0 + 60 * k, lat, 12.80, 7000.0, False, 220.0, 0.0, 0.0, "SAS652"
        )
        vivos.anadir([p])
        vivos.actualizar(t0 + 60 * k)
    assert len(vivos.esperas) == 1
    assert vivos.esperas[0][:2] == ["EKCH", "H"]


# --- Fuente: formato readsb, respaldo y círculos --------------------------------------------------

RESPUESTA = {
    "now": 1758566400000,
    "ac": [
        {"hex": "4ac9e1", "flight": "SAS652  ", "t": "A20N", "category": "A3", "lat": 55.6,
         "lon": 12.7, "alt_baro": 1500, "gs": 140.2, "track": 220.5, "baro_rate": -640,
         "seen_pos": 1.5, "dbFlags": 0},
        {"hex": "4bbbbb", "lat": 55.62, "lon": 12.65, "alt_baro": "ground", "gs": 12,
         "seen_pos": 3},
        {"hex": "~2a0001", "lat": 55.6, "lon": 12.6, "alt_baro": 900, "seen_pos": 1},
        {"hex": "4ccccc", "lat": 55.6, "lon": 12.6, "alt_baro": 900, "seen_pos": 400},
        {"hex": "4ddddd", "alt_baro": 900, "seen_pos": 1},
    ],
}  # fmt: skip


def test_la_respuesta_readsb_da_las_posiciones_recientes() -> None:
    ahora, lista = servicio.leer_respuesta(gzip.compress(json.dumps(RESPUESTA).encode()))
    assert ahora == 1758566400.0
    posiciones = [p for a in lista if (p := servicio.posicion(a, ahora)) is not None]
    assert [p.icao for p in posiciones] == ["4ac9e1", "4bbbbb"]
    primera, segunda = posiciones
    assert primera.indicativo == "SAS652" and primera.t == ahora - 1.5 and primera.vz == -640
    assert segunda.suelo and segunda.alt is None


class Red:
    """Responde por sitio: una excepción hace fallar la petición."""

    def __init__(self, principal_falla: bool) -> None:
        self.principal_falla = principal_falla
        self.pedidas: list[str] = []

    def pedir(self, url: str) -> bytes:
        self.pedidas.append(url)
        if "adsb.lol" in url and self.principal_falla:
            raise OSError("caída")
        return json.dumps(RESPUESTA).encode()


CIRCULOS = [
    servicio.Circulo(55.6, 12.6, 200, ("EKCH",)),
    servicio.Circulo(48.3, 11.8, 200, ("EDDM",)),
]


def test_con_la_principal_bien_no_se_toca_el_respaldo() -> None:
    red = Red(principal_falla=False)
    lector = servicio.Lector(red.pedir, dormir=lambda s: None)
    lectura = lector.leer(CIRCULOS, 0.0)
    assert lectura.fuente == "adsb_lol" and not lectura.fallidos
    assert all("adsb.lol" in u for u in red.pedidas)
    assert len(lectura.posiciones) == 4


def test_si_falla_la_principal_el_ciclo_se_pide_al_respaldo_y_luego_se_queda_en_el() -> None:
    red = Red(principal_falla=True)
    esperas: list[float] = []
    lector = servicio.Lector(red.pedir, dormir=esperas.append)
    for ciclo in range(servicio.FALLOS_PARA_RESPALDO):
        lectura = lector.leer(CIRCULOS, 60.0 * ciclo)
        assert lectura.fuente == "adsb_fi" and not lectura.fallidos
    assert lector.en_respaldo
    # Espera creciente en los reintentos (2 y 4 s) y pausa entre peticiones.
    assert 2.0 in esperas and 4.0 in esperas
    red.pedidas.clear()
    lector.leer(CIRCULOS, 200.0)
    assert not any("adsb.lol" in u for u in red.pedidas)
    # Pasados 10 minutos se prueba la principal con una sola petición; si responde, se vuelve.
    red.principal_falla = False
    red.pedidas.clear()
    lectura = lector.leer(
        CIRCULOS, 60.0 * servicio.FALLOS_PARA_RESPALDO + servicio.PRUEBA_PRINCIPAL_S
    )
    assert lectura.fuente == "adsb_lol" and not lector.en_respaldo


def test_el_tope_diario_de_reintentos_corta_los_reintentos(tmp_path: Path) -> None:
    from recogida import reintentos

    tope = reintentos.TopeDiario(tmp_path, tope=1)
    red = Red(principal_falla=True)
    lector = servicio.Lector(red.pedir, dormir=lambda s: None, tope=tope)
    lector.leer(CIRCULOS[:1], 0.0)
    del_lol = [u for u in red.pedidas if "adsb.lol" in u]
    assert len(del_lol) == 2  # el primer intento y un solo reintento


def test_los_circulos_cubren_todos_los_aeropuertos_con_su_zona() -> None:
    aeropuertos = [a for a in vuelos.cargar_aeropuertos() if a.regular and a.grande]
    lista = servicio.circulos(aeropuertos)
    cubiertos = {o for c in lista for o in c.aeropuertos}
    assert cubiertos == {a.oaci for a in aeropuertos}
    por_oaci = {a.oaci: a for a in aeropuertos}
    for c in lista:
        assert c.radio_nm <= servicio.RADIO_MAXIMO_NM
        for oaci in c.aeropuertos:
            a = por_oaci[oaci]
            distancia_nm = vuelos.distancia_km(c.lat, c.lon, a.lat, a.lon) / servicio.KM_POR_NM
            assert distancia_nm + vuelos.EXTREMO_RADIO_KM / servicio.KM_POR_NM <= c.radio_nm
    # Un círculo junta muchos aeropuertos: menos de una petición por cada cuatro.
    assert len(lista) * 4 < len(aeropuertos)


# --- Ficheros públicos y estado -------------------------------------------------------------


def test_directo_json_solo_lleva_campos_de_la_lista_cerrada() -> None:
    detector = directo.Detector(base_constante())
    detector.avisos = [
        directo.Aviso("EKCH", hora(18.4), hora(18.8), directo.POSIBLE, 20.0, 0,
                      motivos_meteorologicos=["niebla"], fuente="adsb_lol", factor=0.9),
    ]  # fmt: skip
    documento = servicio.documento_publico(
        detector, {"EKCH": aeropuerto_prueba()}, hora(19), "adsb_lol", 120
    )
    assert documento["version"] == 1 and documento["generado"] == "2025-09-22T19:00Z"
    assert not fuera_de_lista(documento["avisos"], CAMPOS_PUBLICOS_AVISO_DIRECTO)
    aviso = documento["avisos"][0]
    assert aviso["nombre"] == "Copenhagen Kastrup" and aviso["pais"] == "DK"
    assert "factor" not in aviso and "motivos_meteorologicos" not in aviso


def test_la_confirmacion_de_la_recogida_horaria_llega_al_aviso(tmp_path: Path) -> None:
    aviso = directo.Aviso("EKCH", hora(18.4), hora(18.8), directo.POSIBLE, 20.0, 0)
    (tmp_path / servicio.AVISOS).write_text(json.dumps({"avisos": [aviso.documento()]}))
    incidente = {
        "id": "EODI-2025-00154",
        "objetivo": {"oaci": "EKCH"},
        "tiempo": {"inicio": {"valor": "2025-09-22T18:26Z", "precision": "minuto"}},
        "fuentes": [
            {"fiabilidad": "C", "fecha": {"valor": "2025-09-22T19:05Z", "precision": "minuto"}}
        ],
    }

    class Base:
        def incidentes(self) -> list[dict[str, Any]]:
            return [incidente]

    momento = datetime(2025, 9, 22, 19, 17, tzinfo=UTC)
    assert directo_horaria.paso_horario(Base(), momento, tmp_path) == 1  # type: ignore[arg-type]
    hallado = json.loads((tmp_path / servicio.CONFIRMACIONES).read_text())
    assert hallado["avisos"][aviso.id]["confirmacion"]["tipo"] == "incidente"
    assert hallado["avisos"][aviso.id]["primera_noticia"] == "2025-09-22T19:05Z"


def test_estado_json_lleva_la_deteccion_en_directo() -> None:
    fin = datetime(2026, 10, 3, 9, 30, tzinfo=UTC)
    registro = {"ultimo_ciclo_correcto": "2026-10-03T09:28Z", "fuente": "adsb_lol"}
    documento = estado.componer(fin, fin, 0, {}, None, 17, directo=registro, con_directo=True)
    assert documento["directo"] == {
        "estado": "en_marcha",
        "ultimo_ciclo_correcto": "2026-10-03T09:28Z",
    }
    respaldo = {**registro, "fuente": "adsb_fi"}
    assert estado.estado_directo(respaldo, fin)["estado"] == "con_respaldo"
    assert estado.estado_directo(registro, fin + timedelta(minutes=15))["estado"] == "parado"
    assert estado.estado_directo(None, fin) == {"estado": "parado", "ultimo_ciclo_correcto": None}
    assert "directo" not in estado.componer(fin, fin, 0, {}, None, 17)


def test_la_vigilancia_avisa_si_la_deteccion_en_directo_se_para() -> None:
    ahora = datetime(2026, 10, 3, 9, 30, tzinfo=UTC)
    al_dia, frase = salud.diagnostico_directo(
        {"generado": "2026-10-03T09:29Z", "fuente": "adsb_lol"}, ahora
    )
    assert al_dia and "hace 1 min" in frase
    al_dia, frase = salud.diagnostico_directo({"generado": "2026-10-03T08:50Z"}, ahora)
    assert not al_dia and "más de 30 min" in frase
    assert not salud.diagnostico_directo(None, ahora)[0]


# --- Mapa diario de interferencia GPS ---------------------------------------------------------


def test_el_mapa_de_interferencia_gps_solo_lleva_campos_de_la_lista_cerrada(tmp_path: Path) -> None:
    from exportacion.campos import CAMPOS_PUBLICOS_GNSS
    from recogida import gnss_publico
    from recogida import trafico as procesado

    datos = tmp_path / "trafico"
    carpeta = procesado.directorio_dia(datos, DIA)
    carpeta.mkdir(parents=True)
    filas = (
        "celda,aeronaves,degradadas\n"
        "841f051ffffffff,120,15\n841f059ffffffff,40,1\n841f05bffffffff,8,8\n"
    )
    (carpeta / "gnss_dia.csv.gz").write_bytes(gzip.compress(filas.encode()))
    (carpeta / procesado.RESUMEN).write_text("{}")
    subidos: dict[str, tuple[bytes, str | None]] = {}

    def subir(
        objeto: str, cuerpo: bytes, tipo: str, cache: str | None, codificacion: str | None
    ) -> bool:
        subidos[objeto] = (cuerpo, codificacion)
        return True

    publicador = gnss_publico.Publicador(datos, tmp_path / "directo", subir)
    assert publicador.publicar_pendientes() == 1
    assert set(subidos) == {"gnss/dia/2025-09-22.json", "gnss/mes/2025-09.json", "gnss/indice.json"}
    cuerpo, codificacion = subidos["gnss/dia/2025-09-22.json"]
    assert codificacion == "gzip"
    dia = json.loads(gzip.decompress(cuerpo))
    assert not fuera_de_lista([dia], CAMPOS_PUBLICOS_GNSS)
    # La celda de 8 aeronaves no llega al mínimo de 20 en el día.
    assert [c["h3"] for c in dia["celdas"]] == ["841f051ffffffff", "841f059ffffffff"]
    alta, sin = dia["celdas"]
    assert alta["proporcion"] == pytest.approx(14 / 120, abs=1e-4) and alta["nivel"] == "alta"
    assert sin["proporcion"] == 0 and sin["nivel"] == "sin"
    assert len(alta["contorno"]) == 6
    assert dia["resumen"] == {
        "celdas": 2, "celdas_media": 0, "celdas_alta": 1, "aeronaves": 160, "degradadas": 16,
        "proporcion": round(14 / 160, 4), "nivel": "media",
    }  # fmt: skip
    indice = json.loads(gzip.decompress(subidos["gnss/indice.json"][0]))
    assert indice["dias"] == ["2025-09-22"] and indice["meses"] == ["2025-09"]
    assert not fuera_de_lista([indice], CAMPOS_PUBLICOS_GNSS)
    # Lo publicado no se vuelve a subir.
    subidos.clear()
    assert publicador.publicar_pendientes() == 0 and not subidos


def test_un_campo_nuevo_en_el_mapa_gps_no_sale_sin_estar_en_la_lista() -> None:
    from recogida import gnss_publico

    publicador = gnss_publico.Publicador(Path("."), Path("."), lambda *a: True)
    with pytest.raises(ValueError, match="lista cerrada"):
        publicador._subir("dia/x.json", {"celdas": [{"h3": "x", "icao": "4ac9e1"}]}, "")


def test_la_subida_lleva_la_compresion_en_la_cabecera() -> None:
    import urllib.request

    from recogida import almacen_publico

    enviadas: list[urllib.request.Request] = []

    def enviar(peticion: urllib.request.Request, tope: float) -> int:
        enviadas.append(peticion)
        return 200

    almacen = almacen_publico.cargar()
    correcto, _ = almacen_publico.subir(
        almacen, "gnss/indice.json", b"x", "id", "secreto", "application/json", "public",
        enviar, codificacion="gzip",
    )  # fmt: skip
    assert correcto
    assert enviadas[0].get_header("Content-encoding") == "gzip"


# --- Búsqueda dirigida de los avisos en directo ---------------------------------------------------


def test_un_aviso_lanza_la_busqueda_de_noticias_por_franjas(tmp_path: Path) -> None:
    from proceso.noticias import Articulo
    from recogida import busqueda_dirigida, gdelt

    directo_datos = tmp_path / "directo"
    directo_datos.mkdir()
    aviso = directo.Aviso("EKCH", hora(18.4), hora(18.8), directo.POSIBLE, 20.0, 0)
    (directo_datos / "avisos.json").write_text(json.dumps({"avisos": [aviso.documento()]}))
    leidas: list[datetime] = []

    def leer_franja(franja: datetime) -> list[Articulo]:
        leidas.append(franja)
        if franja == datetime(2025, 9, 22, 19, 0, tzinfo=UTC):
            titular = "Droner over Københavns Lufthavn: lukket"
            return [Articulo("https://dr.dk/x", "dr.dk", franja, titular, "da")]
        return []

    ahora = datetime(2025, 9, 22, 20, 0, tzinfo=UTC)
    recuentos = busqueda_dirigida.buscar_directo(
        tmp_path / "busqueda", directo_datos, leer_franja, ahora
    )
    assert recuentos["avisos"] == 1 and recuentos["con_noticias"] == 1
    # Desde una hora antes del comienzo (17:24 → 17:15) hasta la última franja publicada.
    assert leidas[0] == datetime(2025, 9, 22, 17, 15, tzinfo=UTC)
    assert leidas[-1] == ahora - gdelt.FRANJA
    hallados = list((tmp_path / "busqueda" / busqueda_dirigida.HALLADOS).glob("*.json"))
    contenido = json.loads(hallados[0].read_text())
    assert contenido["anomalia"]["oaci"] == "EKCH" and contenido["anomalia"]["directo"]
    assert [a["url"] for a in contenido["articulos"]] == ["https://dr.dk/x"]
    # En la siguiente pasada solo se leen las franjas nuevas, y la versión cambia.
    leidas.clear()
    busqueda_dirigida.buscar_directo(
        tmp_path / "busqueda", directo_datos, leer_franja, ahora + gdelt.FRANJA
    )
    assert leidas == [ahora]
    assert json.loads(hallados[0].read_text())["version"] != contenido["version"]


def test_la_recogida_pasa_el_registro_del_directo_a_estado_json() -> None:
    raiz = Path(__file__).resolve().parent.parent
    recogida = (raiz / "servidor" / "recogida.sh").read_text(encoding="utf-8")
    orden = recogida.split("-m recogida.estado")[1].split("; then")[0].split()
    assert orden[orden.index("--directo") + 1] == '"$DIRECTO_REGISTRO"'
    configuracion = (raiz / "servidor" / "configuracion.sh").read_text(encoding="utf-8")
    assert 'DIRECTO_REGISTRO="$SECRETOS/directo.json"' in configuracion
    instalar = (raiz / "servidor" / "instalar.sh").read_text(encoding="utf-8")
    assert "Restart=always" in instalar and "$CLON/servidor/directo.sh" in instalar


# --- Días reales recortados del archivo -------------------------------------------------------
#
# Posiciones a 45 km del aeropuerto (las trazas filtradas del archivo diario de adsb.lol, con
# tres horas y media antes de la ventana), los aterrizajes y despegues del aeropuerto de los
# días de su línea base y los METAR del día (tests/fixtures/directo/).

RECORTES = Path(__file__).parent / "fixtures" / "directo"


def recorte(nombre: str) -> dict[str, Any]:
    datos: dict[str, Any] = json.loads(
        gzip.decompress((RECORTES / f"{nombre}.json.gz").read_bytes())
    )
    return datos


def reproducir_recorte(
    datos: dict[str, Any], metares_extra: list[metar.Metar] | None = None
) -> tuple[directo.Detector, list[directo.Aviso]]:
    oaci = datos["oaci"]
    dias = {
        date.fromisoformat(d): trafico.DiaTrafico(date.fromisoformat(d), "", "", {oaci: filas})
        for d, filas in datos["base"].items()
    }
    bases = directo.Bases(
        lambda o, d: directo.base_dia(o, d, lambda x: dias.get(x), lambda x: True)
    )
    lista = [
        metar.leer(datetime.strptime(h, "%Y-%m-%d %H:%M").replace(tzinfo=UTC), texto)
        for h, texto in datos["metar"]
    ] + (metares_extra or [])

    def metares(o: str, desde: float, hasta: float) -> list[metar.Metar]:
        return [m for m in lista if desde <= m.hora.timestamp() <= hasta]

    vivos = directo.Vivos(vuelos.cargar_aeropuertos())
    detector = directo.Detector(bases, metares)
    cero = trafico.inicio_dia(date.fromisoformat(datos["dia"]))
    por_ciclo: dict[int, list[directo.Posicion]] = {}
    for icao, t, lat, lon, alt, gs, rumbo, tipo, categoria, marcas in datos["posiciones"]:
        p = directo.Posicion(
            icao, float(t), lat, lon, None if alt in ("S", None) else float(alt), alt == "S",
            gs, rumbo, None, None, tipo, categoria, marcas,
        )  # fmt: skip
        por_ciclo.setdefault(int(p.t // directo.PASO_S) + 1, []).append(p)
    nuevos: list[directo.Aviso] = []
    ciclo = int((cero + (datos["desde_h"] - 3.5) * 3600) // directo.PASO_S)
    while ciclo * directo.PASO_S <= cero + datos["hasta_h"] * 3600:
        ahora = float(ciclo * directo.PASO_S)
        vivos.anadir(por_ciclo.get(ciclo, []))
        vivos.actualizar(ahora)
        if ahora >= cero + datos["desde_h"] * 3600:
            nuevos += detector.evaluar([oaci], ahora, vivos)
        ciclo += 1
    return detector, nuevos


def test_dia_real_cierre_de_copenhague_detectado_en_minutos_y_reanudado() -> None:
    _, avisos = reproducir_recorte(recorte("cierre_ekch"))
    assert len(avisos) == 1
    aviso = avisos[0]
    # Cierre oficial 18:26–22:20 UTC; primer aterrizaje tras la reapertura, 22:38.
    assert hora(18.3) <= aviso.inicio <= hora(18.5)
    assert aviso.detectado - hora(18 + 26 / 60) <= 40 * 60
    assert aviso.estado == directo.REANUDADA
    assert aviso.reanudado is not None and hora(22.3) <= aviso.reanudado <= hora(22.9)
    assert aviso.esperados > 100 and aviso.vistos <= 2


def test_dia_real_normal_en_copenhague_sin_avisos() -> None:
    _, avisos = reproducir_recorte(recorte("normal_ekch"))
    assert avisos == []


def test_dia_real_con_mal_tiempo_no_da_aviso() -> None:
    # El mismo día de Copenhague con una tormenta en el METAR de las 18:20: el hueco lo explica
    # el tiempo y no hay aviso.
    tormenta = metar.leer(
        datetime(2025, 9, 22, 18, 20, tzinfo=UTC), "EKCH 221820Z 24030G48KT 2000 +TSRA BKN008CB"
    )
    _, avisos = reproducir_recorte(recorte("cierre_ekch"), [tormenta])
    assert avisos == []


def test_dia_real_con_cobertura_baja_sin_avisos() -> None:
    # Palma: los receptores no ven los aviones bajos sobre la isla.
    detector, avisos = reproducir_recorte(recorte("cobertura_lepa"))
    assert avisos == []
    assert detector.motivos["LEPA"] in ("cobertura_baja", "sin_hueco", "poco_trafico_previo")


def test_los_circulos_que_la_principal_no_da_se_piden_al_respaldo_en_el_mismo_ciclo() -> None:
    pedidas: list[str] = []

    def pedir(url: str) -> bytes:
        pedidas.append(url)
        if "adsb.lol" in url and "48.300" in url:
            raise OSError("429")
        return json.dumps(RESPUESTA).encode()

    tres = [*CIRCULOS, servicio.Circulo(41.3, 2.1, 250, ("LEBL",))]
    lector = servicio.Lector(pedir, dormir=lambda s: None)
    lectura = lector.leer(tres, 0.0)
    assert lectura.fuente == "adsb_lol" and not lectura.fallidos
    assert lectura.respaldados == 1
    assert [u for u in pedidas if "adsb.fi" in u] == [pedidas[-1]]
    assert len(lectura.posiciones) == 6


def test_si_cae_el_trafico_de_toda_europa_es_la_fuente_y_no_hay_avisos() -> None:
    # Treinta aeropuertos con el mismo hueco a la vez (un día del archivo a medias o la fuente
    # caída): ninguno abre aviso.
    aeropuertos = [f"E{n:03d}" for n in range(30)]

    class Todos(Movimientos):
        def movimientos(self, oaci: str) -> list[float]:
            return super().movimientos("EKCH")

    vivos = Todos(CIERRE)
    detector = directo.Detector(base_constante())
    t = hora(15)
    while t <= hora(22):
        vivos.ahora = t
        detector.evaluar(aeropuertos, t, vivos)
        t += directo.PASO_S
    assert detector.avisos == []
    assert set(detector.motivos.values()) <= {"fuente", "sin_hueco", "poco_trafico_previo"}


def test_un_dia_incompleto_de_la_linea_base_no_cuenta() -> None:
    dia = date(2026, 8, 30)
    incompleto = dia - timedelta(weeks=3)
    candidatos = [f"E{n:03d}" for n in range(10)]

    def coberturas(oaci: str, d: date) -> str:
        if d == incompleto:
            return trafico.INSUFICIENTE
        return trafico.MEDIA if oaci == "E009" else trafico.ALTA

    bases = base_constante()
    assert directo.vigilables(dia, candidatos, coberturas, bases) == candidatos[:9]
