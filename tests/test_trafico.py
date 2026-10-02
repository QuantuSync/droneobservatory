"""Archivo de adsb.lol sin red: localización del día, lectura en flujo y del formato, filtro por
zonas, movimientos (aterrizajes, despegues, frustradas, esperas y desvíos), aeronaves militares
e interferencia GNSS, con fragmentos reales recortados del 22 de septiembre de 2025 (el cierre
de Copenhague)."""

import gzip
import io
import itertools
import json
import tarfile
import urllib.error
from datetime import UTC, date, datetime
from email.message import Message
from pathlib import Path
from typing import Any

import pytest

from proceso import aeronaves, espera, gnss, trafico, vuelos
from recogida import adsb
from recogida import trafico as procesado

FIXTURES = Path(__file__).parent / "fixtures" / "trafico"
DIA = date(2025, 9, 22)


def documento(icao: str) -> dict[str, Any]:
    datos: dict[str, Any] = json.loads(
        (FIXTURES / f"traza_{icao}.json").read_text(encoding="utf-8")
    )
    return datos


def traza(icao: str) -> vuelos.Traza:
    return adsb.leer_traza(documento(icao), procesado.CAJA_LECTURA)


@pytest.fixture(scope="module")
def indice() -> vuelos.Indice:
    return vuelos.Indice(vuelos.cargar_aeropuertos())


def movimientos(icao: str, indice: vuelos.Indice) -> list[vuelos.Movimiento]:
    t = traza(icao)
    return vuelos.analizar(t, indice, aeronaves.es_ifr(t.tipo, t.categoria, t.marcas))


def hora(t: float) -> str:
    return datetime.fromtimestamp(t, UTC).strftime("%H:%M")


# --- Formato de las trazas ------------------------------------------------------------


def test_lee_la_traza_de_readsb_con_sus_datos_arrastrados() -> None:
    t = traza("47875c")
    assert (t.icao, t.tipo, t.marcas, t.categoria) == ("47875c", "B738", 0, "A3")
    assert t.t == sorted(t.t) and len(set(t.t)) == len(t.t)
    # El NIC, el NACp y el indicativo solo vienen en algunos puntos: se arrastran. El avión
    # llega como NOZ948 y sale, tras la escala, como NOZ949.
    assert all(n is not None for n in t.nic[len(t) // 2 :])
    assert [c for i, c in enumerate(t.indicativo) if c and c != t.indicativo[i - 1]] == [
        "NOZ948",
        "NOZ949",
    ]


def test_los_puntos_repetidos_con_el_mismo_instante_se_quitan() -> None:
    d = documento("4ab562")
    d["trace"] = d["trace"][:5] + d["trace"][:5]
    assert len(adsb.leer_traza(d)) == 5


def test_la_caja_recorta_los_puntos() -> None:
    d = documento("47875c")
    lejos = (0.0, 0.0, 1.0, 1.0)
    assert len(adsb.leer_traza(d, lejos)) == 0
    assert adsb.toca_caja(d, 8.0, 54.0, 16.0, 58.0)
    assert not adsb.toca_caja(d, 0.0, 0.0, 1.0, 1.0)


# --- Localización y lectura en flujo -------------------------------------------------------


class Respuesta(io.BytesIO):
    def __init__(self, contenido: bytes) -> None:
        super().__init__(contenido)
        self.headers = Message()
        self.headers["Content-Length"] = str(len(contenido))


def abridor(ficheros: dict[str, bytes]) -> adsb.Abridor:
    def abrir(url: str, metodo: str, desde: int = 0) -> Respuesta:
        nombre = url.rsplit("/", 1)[1]
        anio = url.split("globe_history_")[1].split("/")[0]
        clave = f"{anio}/{nombre}"
        if clave not in ficheros:
            raise urllib.error.HTTPError(url, 404, "no", Message(), None)
        return Respuesta(ficheros[clave][desde:])

    return abrir


def tar_de(documentos: list[dict[str, Any]]) -> bytes:
    salida = io.BytesIO()
    with tarfile.open(fileobj=salida, mode="w") as tar:
        for nombre, contenido in [("./README.txt", b"adsb.lol"), ("./heatmap/00.bin.ttf", b"x")]:
            info = tarfile.TarInfo(nombre)
            info.size = len(contenido)
            tar.addfile(info, io.BytesIO(contenido))
        for d in documentos:
            crudo = gzip.compress(json.dumps(d).encode())
            info = tarfile.TarInfo(f"./traces/{d['icao'][-2:]}/trace_full_{d['icao']}.json")
            info.size = len(crudo)
            tar.addfile(info, io.BytesIO(crudo))
    return salida.getvalue()


def test_usa_prod_partido_en_trozos_y_los_lee_seguidos() -> None:
    contenido = tar_de([documento("47875c"), documento("4ab562")])
    etiqueta = adsb.etiqueta(DIA, adsb.PROD)
    mitad = len(contenido) // 2
    ficheros = {
        f"2025/{etiqueta}.tar.aa": contenido[:mitad],
        f"2025/{etiqueta}.tar.ab": contenido[mitad:],
    }
    publicacion = adsb.localizar(DIA, abridor(ficheros))
    assert publicacion.etiqueta == "v2025.09.22-planes-readsb-prod-0"
    assert publicacion.bytes == len(contenido)
    assert publicacion.pagina.endswith(
        "/globe_history_2025/releases/tag/v2025.09.22-planes-readsb-prod-0"
    )
    flujo = adsb.Encadenado(publicacion.urls, abridor(ficheros))
    leidos = list(adsb.documentos(io.BufferedReader(flujo)))
    assert [d["icao"] for d in leidos] == ["47875c", "4ab562"]
    assert flujo.bytes == len(contenido)


def test_staging_solo_si_es_claramente_mayor_y_prod_tmp_si_no_hay_prod() -> None:
    p, s, tmp = (adsb.etiqueta(DIA, x) for x in (adsb.PROD, adsb.STAGING, adsb.PROD_TMP))
    parecidos = {f"2025/{p}.tar": b"a" * 100, f"2025/{s}.tar": b"a" * 105}
    assert adsb.localizar(DIA, abridor(parecidos)).etiqueta == p
    mayor = {f"2025/{p}.tar": b"a" * 100, f"2025/{s}.tar": b"a" * 200}
    assert adsb.localizar(DIA, abridor(mayor)).etiqueta == s
    assert adsb.localizar(DIA, abridor({f"2025/{tmp}.tar": b"a"})).etiqueta == tmp


def test_un_dia_sin_publicar_lo_dice() -> None:
    with pytest.raises(adsb.SinPublicar):
        adsb.localizar(DIA, abridor({}))


def test_un_dia_de_diciembre_puede_estar_en_el_repositorio_del_ano_siguiente() -> None:
    dia = date(2024, 12, 30)
    etiqueta = adsb.etiqueta(dia, adsb.PROD)
    publicacion = adsb.localizar(dia, abridor({f"2025/{etiqueta}.tar": b"a"}))
    assert publicacion.anio_repositorio == 2025


# --- Movimientos ---------------------------------------------------------------------------


def test_aterrizaje_y_despegue_en_copenhague(indice: vuelos.Indice) -> None:
    movs = movimientos("47875c", indice)
    assert [(m.tipo, m.oaci, hora(m.t)) for m in movs] == [
        ("L", "EKCH", "17:03"),
        ("D", "EKCH", "17:50"),
    ]
    assert all(m.ifr and m.indicativo == "NOZ948" for m in movs)


def test_frustrada_en_copenhague_al_empezar_el_cierre_y_aterrizaje_en_malmo(
    indice: vuelos.Indice,
) -> None:
    movs = movimientos("4ab562", indice)
    assert [(m.tipo, m.oaci, hora(m.t)) for m in movs] == [
        ("G", "EKCH", "18:28"),
        ("L", "ESMS", "18:52"),
    ]


def test_esperas_y_desvio_a_billund(indice: vuelos.Indice) -> None:
    movs = movimientos("48c2a7", indice)
    esperas = [m for m in movs if m.tipo == "H"]
    assert [(m.oaci, hora(m.t), hora(m.fin or 0)) for m in esperas] == [
        ("EKCH", "18:39", "18:48"),
        ("EKCH", "18:49", "19:14"),
    ]
    (desvio,) = [m for m in movs if m.tipo == "V"]
    assert (desvio.oaci, desvio.otro) == ("EKCH", "EKBI")
    assert [(m.oaci, hora(m.t)) for m in movs if m.tipo == "L"] == [("EKBI", "19:48")]


def test_salida_de_oslo_sin_cobertura_a_ras_de_pista(indice: vuelos.Indice) -> None:
    # En Gardermoen adsb.lol no ve las salidas por debajo de unos miles de pies: el primer
    # punto ya va subiendo y alejándose. Cuenta como despegue, con la hora estimada.
    t = traza("4ac996")
    assert t.alt[0] is not None and t.alt[0] - indice.por_oaci["ENGM"].elev_ft > vuelos.MUY_BAJO_FT
    (despegue,) = [m for m in vuelos.analizar(t, indice, True) if m.tipo == "D"]
    assert (despegue.oaci, hora(despegue.t)) == ("ENGM", "03:57")


def test_llegada_a_atenas_sin_cobertura_a_ras_de_pista(indice: vuelos.Indice) -> None:
    t = traza("89611f")
    (llegada,) = [m for m in vuelos.analizar(t, indice, True) if m.tipo == "L"]
    assert (llegada.oaci, hora(llegada.t)) == ("LGAV", "16:56")


def test_un_avion_que_sigue_alto_no_cuenta_como_llegada_estimada(indice: vuelos.Indice) -> None:
    d = documento("89611f")
    # Recortado antes de bajar de 10 000 pies: el tramo acaba lejos y alto.
    d["trace"] = [p for p in d["trace"] if isinstance(p[3], int) and p[3] > 10000]
    t = adsb.leer_traza(d)
    assert [m for m in vuelos.analizar(t, indice, True) if m.tipo == "L"] == []


def test_una_escala_sin_cobertura_en_tierra_no_es_una_frustrada(indice: vuelos.Indice) -> None:
    # NOZ948 no tiene puntos en tierra en Copenhague: baja, desaparece 40 minutos y vuelve a
    # subir. Sin el corte por escala, la bajada y la subida parecerían una frustrada.
    t = traza("47875c")
    assert not any(t.suelo)
    assert [m.tipo for m in vuelos.analizar(t, indice, True)] == ["L", "D"]
    assert len(list(vuelos.tramos(t))) == 2


def test_la_fila_de_cada_movimiento() -> None:
    m = vuelos.Movimiento("EKCH", "V", 1758566934.4, "48c2a7", "RYR1EE", "B38M", True, otro="EKBI")
    assert m.fila() == ["EKCH", "V", 1758566934, "48c2a7", "RYR1EE", "B38M", 1, "EKBI"]


# --- Esperas: el método de traffic ---------------------------------------------------------


def test_la_red_da_lo_mismo_que_el_modelo_original() -> None:
    # Valores de los modelos ONNX de traffic (calculados con numpy al exportar los pesos).

    def giro(total: float) -> list[float]:
        return [total * k / 29 for k in range(30)]

    assert espera.probabilidad(giro(360)) == pytest.approx(0.98027194, abs=1e-6)
    assert espera.probabilidad(giro(-360)) == pytest.approx(0.98370623, abs=1e-6)
    assert espera.probabilidad(giro(180)) == pytest.approx(0.00270974, abs=1e-6)
    assert espera.probabilidad(giro(0)) < 1e-4


def test_un_hipodromo_es_espera_y_un_giro_no() -> None:
    tiempos = [float(s) for s in range(0, 1200, 5)]
    # Tramos rectos de un minuto y virajes de 180° en un minuto.
    rumbos = []
    for s in tiempos:
        fase = s % 240
        rumbos.append(
            (
                0
                if fase < 60
                else 3 * (fase - 60)
                if fase < 120
                else 180
                if fase < 180
                else 180 + 3 * (fase - 180)
            )
            % 360
        )
    assert espera.detectar(tiempos, rumbos)
    assert espera.detectar(tiempos, [90.0] * len(tiempos)) == []


# --- Aeronaves militares -------------------------------------------------------------------


def test_militar_por_la_marca_o_por_un_tipo_solo_militar() -> None:
    assert aeronaves.es_militar("A400", 0)
    assert aeronaves.es_militar("A332", 1)
    assert not aeronaves.es_militar("A332", 0)
    assert aeronaves.clase("E3TF") is aeronaves.Clase.RADAR
    assert aeronaves.clase("K35R") is aeronaves.Clase.CISTERNA
    assert aeronaves.clase("P8") is aeronaves.Clase.PATRULLA_MARITIMA
    assert aeronaves.clase("EUFI") is aeronaves.Clase.CAZA
    assert aeronaves.clase("Q9") is aeronaves.Clase.DRON
    assert aeronaves.clase(None, "A7") is aeronaves.Clase.HELICOPTERO
    assert not aeronaves.es_ifr("A400", "A4", 1)
    assert not aeronaves.es_ifr("C172", "A1", 0)
    assert aeronaves.es_ifr("B738", "A3", 0)


def test_respuesta_militar_alrededor_de_un_punto() -> None:
    t = traza("3e8e96")
    datos = procesado.militar(t)
    assert datos is not None and datos["clase"] == "transporte"
    lat, lon = t.lat[0], t.lon[0]
    resultado = trafico.respuesta_militar(lat, lon, t.t[0] - 60, t.t[-1], [datos])
    assert resultado["aeronaves"] == 1
    assert resultado["tipos"] == ["A400"]
    assert resultado["distancia_min_km"] < 1
    assert resultado["ausencia_no_concluyente"] is True
    lejos = trafico.respuesta_militar(lat + 5, lon, t.t[0], t.t[-1], [datos])
    assert lejos["aeronaves"] == 0


# --- Interferencia GNSS ---------------------------------------------------------------


def test_umbral_de_posicion_degradada() -> None:
    assert gnss.degradada(6, 9) and gnss.degradada(8, 7)
    assert not gnss.degradada(7, 8)


def test_aeronave_con_la_posicion_degradada_en_todas_sus_celdas() -> None:
    celdas = gnss.celdas_hora(traza("781e1f"), procesado.CAJA, gnss.Celdas())
    assert celdas and all(celdas.values())
    sanas = gnss.celdas_hora(traza("47875c"), procesado.CAJA, gnss.Celdas())
    assert sanas and not any(sanas.values())


def test_una_sola_aeronave_degradada_no_tine_la_celda() -> None:
    recuento = gnss.Recuento()
    recuento.sumar(gnss.celdas_hora(traza("781e1f"), procesado.CAJA, gnss.Celdas()))
    (celda, n, malas) = recuento.filas_dia()[0]
    assert (n, malas) == (1, 1)
    assert gnss.proporcion(n, malas) == 0.0
    assert gnss.nivel(30, 1, gnss.MINIMO_DIA) == "sin_interferencia"
    assert gnss.nivel(30, 5, gnss.MINIMO_DIA) == "alta"
    assert gnss.nivel(30, 2, gnss.MINIMO_DIA) == "media"
    assert gnss.nivel(10, 9, gnss.MINIMO_DIA) == "cobertura_insuficiente"
    assert len(celda) == 15


def test_interferencia_en_la_celda_del_incidente_y_sus_vecinas() -> None:
    celda = gnss.celda_de(55.6, 12.6)
    vecina = next(c for c in gnss.vecinas(celda) if c != celda)
    hora0 = int(datetime(2025, 9, 22, 18, tzinfo=UTC).timestamp() // 3600)
    filas = [(hora0, celda, 12, 5), (hora0, vecina, 3, 3), (hora0 + 5, celda, 50, 50)]
    resultado = trafico.interferencia(55.6, 12.6, hora0 * 3600, hora0 * 3600 + 3600, filas)
    assert resultado["propia"] == {
        "aeronaves": 12,
        "degradadas": 5,
        "proporcion": 0.333,
        "nivel": "alta",
    }
    assert resultado["vecinas"]["nivel"] == "cobertura_insuficiente"


# --- Trazas filtradas por zonas ----------------------------------------------------------


def test_zonas_de_las_trazas() -> None:
    aeropuertos = vuelos.cargar_aeropuertos()
    zonas = procesado.Zonas(aeropuertos, [(60.0, 5.0)], ["EKYT"])
    assert zonas.dentro(55.62, 12.65)  # Copenhague
    assert zonas.dentro(60.3, 5.0)  # a 33 km del incidente
    assert not zonas.dentro(56.5, 3.0)  # mar del Norte


def test_las_trazas_filtradas_se_leen_igual_que_se_escribieron() -> None:
    t = traza("47875c")
    zonas = procesado.Zonas(vuelos.cargar_aeropuertos(), [])
    lineas = procesado.lineas_trazas(t, zonas)
    assert lineas[0] == "#47875c,B738,0,A3"
    ((cabecera, puntos),) = list(procesado.leer_trazas("\n".join(lineas)))
    assert cabecera == "47875c,B738,0,A3" and len(puntos) == len(lineas) - 1
    tiempos = [p[0] for p in puntos]
    assert all(b - a >= procesado.PASO_CERCA_S for a, b in itertools.pairwise(tiempos))
    # Solo por debajo de 10 000 pies (en unidades de 25 pies) o en tierra.
    assert all(p[3] == "S" or p[3] is None or p[3] * 25 < procesado.TECHO_CERCA_FT for p in puntos)
    primero = next(i for i in range(len(t)) if round(t.t[i]) == puntos[0][0])
    assert puntos[0][1:3] == [round(t.lat[primero] * 1e4), round(t.lon[primero] * 1e4)]


def test_proceso_de_un_dia_en_memoria() -> None:
    resultado = procesado.procesar_documentos(
        [documento(i) for i in ("47875c", "4ab562", "48c2a7", "3e8e96", "781e1f")],
        vuelos.cargar_aeropuertos(),
        procesado.Zonas(vuelos.cargar_aeropuertos(), []),
        None,
    )
    tipos = sorted(m.tipo for m in resultado.movimientos)
    assert tipos == ["D", "G", "H", "H", "L", "L", "L", "V"]
    assert [m["tipo"] for m in resultado.militares] == ["A400"]
    assert resultado.trazas == resultado.trazas_europa == 5


def test_una_traza_danada_se_salta_sin_tumbar_el_dia() -> None:
    salida = io.BytesIO()
    with tarfile.open(fileobj=salida, mode="w") as tar:
        for nombre, contenido in [
            (
                "./traces/aa/trace_full_0000aa.json",
                gzip.compress(b'{"icao": "0000aa", "trace": []}'),
            ),
            ("./traces/bb/trace_full_0000bb.json", gzip.compress(b"{}")[:12] + b"roto" * 10),
            (
                "./traces/cc/trace_full_0000cc.json",
                gzip.compress(b'{"icao": "0000cc", "trace": []}'),
            ),
        ]:
            info = tarfile.TarInfo(nombre)
            info.size = len(contenido)
            tar.addfile(info, io.BytesIO(contenido))
    salida.seek(0)
    ilegibles: list[str] = []
    leidos = [d["icao"] for d in adsb.documentos(salida, ilegibles)]
    assert leidos == ["0000aa", "0000cc"]
    assert ilegibles == ["./traces/bb/trace_full_0000bb.json"]


class Cortada(Respuesta):
    """Una respuesta cuya conexión se corta tras `corte` bytes."""

    def __init__(self, contenido: bytes, corte: int) -> None:
        super().__init__(contenido[:corte])


def test_una_conexion_cortada_se_reanuda_desde_donde_iba() -> None:
    contenido = tar_de([documento("47875c"), documento("4ab562")])
    peticiones: list[int] = []

    def abrir(url: str, metodo: str, desde: int = 0) -> Respuesta:
        peticiones.append(desde)
        # La primera conexión se corta a mitad; la reanudación llega entera.
        return Cortada(contenido[desde:], 5000) if desde == 0 else Respuesta(contenido[desde:])

    esperas: list[float] = []
    flujo = adsb.Encadenado(["https://x/v.tar"], abrir, (len(contenido),), esperas.append)
    leidos = [d["icao"] for d in adsb.documentos(io.BufferedReader(flujo))]
    assert leidos == ["47875c", "4ab562"]
    assert peticiones == [0, 5000] and flujo.bytes == len(contenido)
    assert esperas == [adsb.ESPERA_REANUDACION_S]


def test_una_descarga_que_no_llega_entera_falla() -> None:
    contenido = tar_de([documento("47875c")])

    def abrir(url: str, metodo: str, desde: int = 0) -> Respuesta:
        return Cortada(contenido[desde:], 1000)

    esperas: list[float] = []
    flujo = adsb.Encadenado(["https://x/v.tar"], abrir, (len(contenido) + 10**9,), esperas.append)
    with pytest.raises(adsb.LecturaIncompleta):
        while flujo.read(1 << 16):
            pass
    # Las reanudaciones esperan cada vez el doble.
    assert esperas == [2.0, 4.0, 8.0, 16.0, 32.0]


def test_si_prod_no_se_lee_entero_se_usa_staging(tmp_path: Path) -> None:
    contenido = tar_de([documento("47875c")])
    prod, staging = adsb.etiqueta(DIA, adsb.PROD), adsb.etiqueta(DIA, adsb.STAGING)
    # El prod dice pesar más de lo que entrega (como el del 15 de octubre de 2025).
    ficheros = {f"2025/{prod}.tar": contenido, f"2025/{staging}.tar": contenido}
    base = abridor(ficheros)

    def abrir(url: str, metodo: str, desde: int = 0) -> Respuesta:
        respuesta: Respuesta = base(url, metodo, desde)
        if prod in url and metodo == "HEAD":
            respuesta.headers.replace_header("Content-Length", str(len(contenido) + 10**6))
        return respuesta

    assert [p.etiqueta for p in adsb.publicaciones(DIA, abrir)] == [prod, staging]
    resumen = procesado.procesar_dia(tmp_path, DIA, abrir, lambda: MetarVacio())
    assert resumen["publicacion"] == staging


class MetarVacio:
    def contenido(self, url: str, valido: Any) -> bytes:
        return b"station,valid,metar\n"
