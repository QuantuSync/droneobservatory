"""Imágenes de antes y después (recogida/satelite.py) y lectura de ventanas de COG
(recogida/cog.py), sin red: recortes reales pequeños de Sentinel-2 sobre Kirishi
(tests/fixtures/satelite) y un GeoTIFF en teselas escrito aquí."""

import io
import json
import struct
import zlib
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from PIL import Image

from esquema import Documento
from recogida import cog, satelite
from recogida.rango import FicheroRemoto, Lector

FIXTURES = Path(__file__).parent / "fixtures" / "satelite"


def _png(nombre: str) -> np.ndarray[Any, Any]:
    return np.asarray(Image.open(FIXTURES / nombre))


# --- Nubes sobre el recorte ---------------------------------------------------------------


def test_recorte_real_despejado_y_nublado() -> None:
    despejado = satelite.medir_nubes(_png("scl_despejada.png"))
    nublado = satelite.medir_nubes(_png("scl_nublada.png"))
    assert despejado.despejada and despejado.nubes <= satelite.MAXIMO_NUBE
    assert not nublado.despejada and nublado.nubes > 0.5


def test_nubes_cuenta_sombra_y_cirro_y_sin_dato() -> None:
    scl = np.full((10, 10), 4, dtype=np.uint8)  # vegetación
    scl[0, :2] = satelite.SOMBRA_NUBE
    scl[1, :1] = satelite.CIRRO
    medida = satelite.medir_nubes(scl)
    assert medida.nubes == pytest.approx(0.03)
    assert medida.despejada
    scl[2, :3] = satelite.SIN_DATO
    assert not satelite.medir_nubes(scl).despejada


def test_ajuste_fijo_igual_para_todas() -> None:
    tci = _png("tci_despejada.png")
    ajustada = satelite.ajustar(tci)
    assert ajustada.shape == tci.shape
    # Aclara los tonos medios y deja los extremos.
    assert int(satelite.ajustar(np.array([0], dtype=np.uint8))[0]) == 0
    assert int(satelite.ajustar(np.array([255], dtype=np.uint8))[0]) == 255
    assert int(satelite.ajustar(np.array([60], dtype=np.uint8))[0]) > 60
    # La misma curva: el mismo valor de entrada da siempre el mismo de salida.
    assert np.array_equal(satelite.ajustar(tci), ajustada)


def test_jpeg_sin_metadatos() -> None:
    cuerpo = satelite.jpeg(_png("tci_despejada.png"))
    imagen = Image.open(io.BytesIO(cuerpo))
    assert imagen.format == "JPEG"
    assert not imagen.getexif()


# --- COG por rangos ----------------------------------------------------------------------


def _tiff_en_teselas(
    datos: np.ndarray[Any, Any], tesela: int, x0: float, y0: float, paso: float
) -> bytes:
    """GeoTIFF clásico en teselas, DEFLATE con predictor horizontal, como los de sentinel-cogs."""
    alto, ancho, muestras = datos.shape
    filas, columnas = -(-alto // tesela), -(-ancho // tesela)
    teselas = []
    for ty in range(filas):
        for tx in range(columnas):
            bloque = np.zeros((tesela, tesela, muestras), dtype=np.uint8)
            trozo = datos[ty * tesela : (ty + 1) * tesela, tx * tesela : (tx + 1) * tesela]
            bloque[: trozo.shape[0], : trozo.shape[1]] = trozo
            diferencias = np.diff(bloque.astype(np.int16), axis=1, prepend=0).astype(np.uint8)
            teselas.append(zlib.compress(diferencias.tobytes()))
    n = len(teselas)
    cabecera = 8
    ifd_tam = 2 + 14 * 12 + 4
    extra = cabecera + ifd_tam
    datos_extra = b""

    def fuera(contenido: bytes) -> int:
        nonlocal datos_extra
        pos = extra + len(datos_extra)
        datos_extra += contenido
        return pos

    bits = fuera(struct.pack(f"<{muestras}H", *([8] * muestras))) if muestras > 1 else 8
    escala = fuera(struct.pack("<3d", paso, paso, 0.0))
    enlace = fuera(struct.pack("<6d", 0, 0, 0, x0, y0, 0))
    offsets_pos = fuera(b"\0" * 4 * n)
    cuentas_pos = fuera(struct.pack(f"<{n}I", *[len(t) for t in teselas]))
    inicio_teselas = extra + len(datos_extra)
    offsets = []
    pos = inicio_teselas
    for t in teselas:
        offsets.append(pos)
        pos += len(t)
    datos_extra = (
        datos_extra[: offsets_pos - extra]
        + struct.pack(f"<{n}I", *offsets)
        + datos_extra[offsets_pos - extra + 4 * n :]
    )
    entradas: list[tuple[int, int, int, int]] = [
        (256, 3, 1, ancho),
        (257, 3, 1, alto),
        (258, 3, muestras, bits),
        (259, 3, 1, 8),
        (262, 3, 1, 2 if muestras == 3 else 1),
        (277, 3, 1, muestras),
        (284, 3, 1, 1),
        (317, 3, 1, 2),
        (322, 3, 1, tesela),
        (323, 3, 1, tesela),
        (324, 4, n, offsets_pos if n > 1 else offsets[0]),
        (325, 4, n, cuentas_pos if n > 1 else len(teselas[0])),
        (33550, 12, 3, escala),
    ]
    entradas.append((33922, 12, 6, enlace))
    ifd = struct.pack("<H", len(entradas))
    for etiqueta, tipo, cuenta, valor in sorted(entradas):
        ifd += struct.pack("<HHII", etiqueta, tipo, cuenta, valor)
    ifd += struct.pack("<I", 0)
    cuerpo = b"II*\x00" + struct.pack("<I", 8) + ifd
    cuerpo = cuerpo.ljust(extra, b"\0") + datos_extra + b"".join(teselas)
    return cuerpo


def _lector_de(contenido: bytes) -> Any:
    pedidos: list[tuple[int, int]] = []

    def leer(inicio: int, fin: int) -> bytes:
        pedidos.append((inicio, fin))
        return contenido[inicio:fin]

    return leer, pedidos


def test_ventana_de_cog_lee_solo_sus_teselas() -> None:
    rng = np.random.default_rng(1)
    imagen = rng.integers(0, 255, size=(300, 300, 3), dtype=np.uint8)
    contenido = _tiff_en_teselas(imagen, 64, 500000.0, 6600000.0, 10.0)
    leer, pedidos = _lector_de(contenido)
    cabecera = cog.leer_cabecera(leer)
    assert (cabecera.ancho, cabecera.alto, cabecera.muestras) == (300, 300, 3)
    assert cabecera.x0 == 500000.0 and cabecera.y0 == 6600000.0
    ventana = cog.leer_ventana(leer, cabecera, 70, 10, 40, 30)
    assert np.array_equal(ventana, imagen[10:40, 70:110])
    # La cabecera y una sola tesela (la ventana cae en la tesela 1 de la primera fila).
    assert len([p for p in pedidos if p[0] >= 1000]) == 1


def test_ventana_fuera_de_la_imagen_queda_sin_dato() -> None:
    imagen = np.full((64, 64, 1), 7, dtype=np.uint8)
    leer, _ = _lector_de(_tiff_en_teselas(imagen, 64, 0.0, 0.0, 20.0))
    cabecera = cog.leer_cabecera(leer)
    ventana = cog.leer_ventana(leer, cabecera, 50, 50, 30, 30)
    assert ventana[0, 0, 0] == 7 and ventana[-1, -1, 0] == 0


def test_caja_en_metros_a_ventana() -> None:
    imagen = np.zeros((128, 128, 1), dtype=np.uint8)
    leer, _ = _lector_de(_tiff_en_teselas(imagen, 64, 1000.0, 5000.0, 20.0))
    cabecera = cog.leer_cabecera(leer)
    assert cog.ventana_de_caja(cabecera, 1200.0, 4000.0, 1600.0, 4800.0) == (10, 10, 20, 40)


@pytest.mark.parametrize(
    ("lat", "lon", "huso", "x", "y"),
    [
        # Meridiano central: x = 500 000 m.
        (0.0, 33.0, 36, 500000.0, 0.0),
        # Valores de referencia de pyproj (EPSG:32636 y 32637).
        (59.49, 32.078, 36, 447784.61, 6594977.83),
        (50.0, 36.23, 37, 301495.57, 5542307.81),
    ],
)
def test_utm(lat: float, lon: float, huso: int, x: float, y: float) -> None:
    calculado = cog.a_utm(lat, lon, huso)
    assert calculado[0] == pytest.approx(x, abs=0.05)
    assert calculado[1] == pytest.approx(y, abs=0.05)


def test_zona_utm() -> None:
    assert cog.zona_utm(32636) == (36, True)
    assert cog.zona_utm(32737) == (37, False)
    with pytest.raises(ValueError):
        cog.zona_utm(4326)


def test_fichero_remoto_por_bloques() -> None:
    contenido = bytes(range(256)) * 40
    leer, pedidos = _lector_de(contenido)
    fichero = FicheroRemoto(leer, len(contenido), bloque=1000, bloques_en_memoria=2)
    fichero.seek(990)
    assert fichero.read(20) == contenido[990:1010]
    fichero.seek(995)
    assert fichero.read(10) == contenido[995:1005]
    assert pedidos == [(0, 1000), (1000, 2000)]
    fichero.seek(-5, 2)
    assert fichero.read(100) == contenido[-5:]


def test_lector_reintenta_lo_temporal_y_no_lo_definitivo() -> None:
    respuestas = [(503, b""), (206, b"abc")]
    lector = Lector(lambda url, cab, tope: respuestas.pop(0), dormir=lambda s: None)
    assert lector.obtener("https://x/y", 0, 3) == b"abc"
    lector = Lector(lambda url, cab, tope: (403, b""), dormir=lambda s: None)
    with pytest.raises(Exception, match="HTTP 403"):
        lector.obtener("https://x/y")
    assert lector.peticiones == 1


# --- Pareja de antes y después ---------------------------------------------------------


def _item(id_: str, fecha: str, nubes: float = 10.0) -> Documento:
    return {
        "id": id_,
        "properties": {"datetime": fecha, "eo:cloud_cover": nubes, "proj:code": "EPSG:32636"},
        "assets": {
            "visual": {"href": f"https://cogs/{id_}/TCI.tif"},
            "scl": {"href": f"https://cogs/{id_}/SCL.tif"},
        },
    }


class Archivo:
    """Doble del catálogo STAC y de las imágenes: las SCL son los recortes reales."""

    def __init__(self, items: list[Documento], nubladas: set[str]) -> None:
        self.items = items
        self.nubladas = nubladas
        self.busquedas: list[Documento] = []

    def buscar(self, cuerpo: Documento) -> Documento:
        self.busquedas.append(cuerpo)
        desde, hasta = (
            datetime.fromisoformat(x.replace("Z", "+00:00")) for x in cuerpo["datetime"].split("/")
        )
        elegidos = [
            i
            for i in self.items
            if desde
            <= datetime.fromisoformat(i["properties"]["datetime"].replace("Z", "+00:00"))
            <= hasta
        ]
        descendente = cuerpo["sortby"][0]["direction"] == "desc"
        elegidos.sort(key=lambda i: i["properties"]["datetime"], reverse=descendente)
        return {"features": elegidos}


def _con_bandas(monkeypatch: pytest.MonkeyPatch, archivo: Archivo) -> None:
    despejada = _png("scl_despejada.png")
    nublada = _png("scl_nublada.png")
    tci = _png("tci_despejada.png")

    def leer_banda(lector: Lector, url: str, recorte: satelite.Recorte, epsg: int) -> Any:
        escena = url.split("/")[3]
        if url.endswith("SCL.tif"):
            return (nublada if escena in archivo.nubladas else despejada)[:, :, None]
        return tci

    monkeypatch.setattr(satelite, "leer_banda", leer_banda)


def _objetivo() -> satelite.Objetivo:
    return satelite.Objetivo(
        id="EODI-IG-2025-02569",
        recorte=satelite.Recorte(59.49, 32.078, 4000),
        antes_hasta=datetime(2025, 9, 13, 17, tzinfo=UTC),
        despues_desde=datetime(2025, 9, 14, 7, tzinfo=UTC),
        foco=True,
    )


def test_pareja_elige_la_ultima_despejada_antes_y_la_primera_despues(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    archivo = Archivo(
        [
            _item("S2B_36VVL_20250901_0_L2A", "2025-09-01T09:20:00Z"),
            _item("S2C_36VVL_20250911_1_L2A", "2025-09-11T09:14:10Z"),
            _item("S2A_36VVL_20250913_0_L2A", "2025-09-13T09:20:00Z", nubes=5.0),
            _item("S2A_36VVL_20250916_0_L2A", "2025-09-16T09:20:00Z", nubes=2.0),
            _item("S2C_36VVM_20251001_0_L2A", "2025-10-01T09:13:57Z", nubes=70.0),
        ],
        # La escena con poca nube en la escena entera tiene el recorte cubierto, y la de mucha
        # nube lo tiene limpio: decide el recorte.
        nubladas={"S2A_36VVL_20250913_0_L2A", "S2A_36VVL_20250916_0_L2A"},
    )
    _con_bandas(monkeypatch, archivo)
    subidos: dict[str, bytes] = {}

    def subir(objeto: str, cuerpo: bytes, tipo: str, cache: str) -> bool:
        subidos[objeto] = cuerpo
        return True

    entrada = satelite.procesar(
        _objetivo(), {}, archivo.buscar, Lector(), subir, datetime(2025, 10, 5, tzinfo=UTC)
    )
    assert entrada["antes"]["escena"] == "S2C_36VVL_20250911_1_L2A"
    assert entrada["despues"]["escena"] == "S2C_36VVM_20251001_0_L2A"
    assert entrada["antes"]["objeto"] == (
        "satelite/EODI-IG-2025-02569/antes-20250911-S2C_36VVL_20250911_1_L2A.jpg"
    )
    assert set(subidos) == {entrada["antes"]["objeto"], entrada["despues"]["objeto"]}
    # La imagen de antes nunca es posterior al inicio del ataque.
    assert archivo.busquedas[0]["datetime"].endswith("2025-09-13T17:00:00Z")


def test_pareja_a_medias_se_completa_con_una_imagen_nueva(monkeypatch: pytest.MonkeyPatch) -> None:
    archivo = Archivo(
        [
            _item("S2C_36VVL_20250911_1_L2A", "2025-09-11T09:14:10Z"),
            _item("S2A_36VVL_20250916_0_L2A", "2025-09-16T09:20:00Z"),
        ],
        nubladas={"S2A_36VVL_20250916_0_L2A"},
    )
    _con_bandas(monkeypatch, archivo)
    ahora = datetime(2025, 9, 20, tzinfo=UTC)
    entrada = satelite.procesar(_objetivo(), {}, archivo.buscar, Lector(), lambda *a: True, ahora)
    assert entrada["antes"] is not None and entrada.get("despues") is None
    assert entrada["despues_buscado_hasta"] == "2025-09-20T00:00:00Z"
    # Llega una escena despejada: la siguiente ejecución solo mira desde lo ya visto.
    archivo.items.append(_item("S2C_36VVM_20251001_0_L2A", "2025-10-01T09:13:57Z"))
    busquedas = len(archivo.busquedas)
    entrada = satelite.procesar(
        _objetivo(), entrada, archivo.buscar, Lector(), lambda *a: True, ahora + timedelta(days=15)
    )
    assert entrada["despues"]["escena"] == "S2C_36VVM_20251001_0_L2A"
    assert len(archivo.busquedas) == busquedas + 1
    assert archivo.busquedas[-1]["datetime"].startswith("2025-09-20T00:00:00Z")


def test_un_recorte_distinto_rehace_la_pareja(monkeypatch: pytest.MonkeyPatch) -> None:
    archivo = Archivo([_item("S2C_36VVL_20250911_1_L2A", "2025-09-11T09:14:10Z")], set())
    _con_bandas(monkeypatch, archivo)
    previa = {"recorte": {"lat": 1.0, "lon": 1.0, "lado_m": 100}, "antes": {"escena": "vieja"}}
    entrada = satelite.procesar(
        _objetivo(),
        previa,
        archivo.buscar,
        Lector(),
        lambda *a: True,
        datetime(2025, 9, 20, tzinfo=UTC),
    )
    assert entrada["antes"]["escena"] == "S2C_36VVL_20250911_1_L2A"


def _impacto(nivel: str = "instalacion", categoria: str = "refineria") -> Documento:
    return {
        "id": "EODI-IG-2025-02569",
        "lugar": {
            "nivel": nivel,
            "categoria": categoria,
            "punto": {"lat": 59.47997, "lon": 32.07409},
            "radio_km": 3.0,
        },
        "fecha": {"valor": "2025-09-14T06:54Z", "precision": "minuto"},
    }


PERIODO = (datetime(2025, 9, 13, 17, tzinfo=UTC), datetime(2025, 9, 14, 6, tzinfo=UTC))


def test_objetivo_instalacion_con_focos_centra_entre_los_dos() -> None:
    focos = [{"lat": 59.50229, "lon": 32.08706}, {"lat": 59.50515, "lon": 32.08325}]
    objetivo = satelite.objetivo_de_impacto(_impacto(), PERIODO, True, focos)
    assert objetivo is not None
    assert 59.48 < objetivo.recorte.lat < 59.505
    assert objetivo.recorte.lado_m >= satelite.LADO_M["refineria"]
    assert objetivo.antes_hasta == PERIODO[0]
    assert objetivo.despues_desde == datetime(2025, 9, 14, 6, 54, tzinfo=UTC)


def test_objetivo_localidad_solo_con_foco() -> None:
    assert satelite.objetivo_de_impacto(_impacto("localidad"), PERIODO, False, []) is None
    focos = [{"lat": 47.55, "lon": 34.37}]
    objetivo = satelite.objetivo_de_impacto(_impacto("localidad"), PERIODO, True, focos)
    assert objetivo is not None and (objetivo.recorte.lat, objetivo.recorte.lon) == (47.55, 34.37)
    assert objetivo.recorte.lado_m == 3000


def test_orden_primero_los_de_foco() -> None:
    a = satelite.objetivo_de_impacto(_impacto(), PERIODO, False, [])
    b = satelite.objetivo_de_impacto(
        _impacto("localidad"), PERIODO, True, [{"lat": 1.0, "lon": 1.0}]
    )
    assert a is not None and b is not None
    assert satelite.ordenar([a, b])[0] is b


def test_indice_publico_con_atribucion_de_copernicus() -> None:
    control: dict[str, Documento] = {
        "EODI-IG-2025-02569": {
            "recorte": {"lat": 59.5, "lon": 32.08, "lado_m": 4000},
            "antes": {
                "fecha": "2024-12-30T09:14:10Z",
                "escena": "a",
                "objeto": "o",
                "nubes_recorte": 0,
            },
            "despues": {
                "fecha": "2025-10-01T09:13:57Z",
                "escena": "b",
                "objeto": "p",
                "nubes_recorte": 0,
            },
            "antes_buscado": True,
            "lugar": "Kirishi refinery",
        },
        "EODI-IG-2025-00001": {"recorte": {"lat": 1, "lon": 1, "lado_m": 3000}, "antes": None},
    }
    indice = satelite.indice(control, datetime(2025, 10, 2, tzinfo=UTC))
    assert list(indice["parejas"]) == ["EODI-IG-2025-02569"]
    assert indice["atribucion"] == "Contains modified Copernicus Sentinel data 2024-2025"
    assert "antes_buscado" not in indice["parejas"]["EODI-IG-2025-02569"]
    # El nombre del lugar va al índice, para la lista de la web.
    assert indice["parejas"]["EODI-IG-2025-02569"]["lugar"] == "Kirishi refinery"


def test_escena_de_item_del_catalogo() -> None:
    escena = satelite.escena_de_item(_item("S2C_36VVL_20250911_1_L2A", "2025-09-11T09:14:10.5Z"))
    assert escena is not None and escena.epsg == 32636
    assert satelite.escena_de_item({"id": "x", "properties": {}, "assets": {}}) is None


def test_origen_de_los_recortes() -> None:
    origen = json.loads((FIXTURES / "origen.json").read_text(encoding="utf-8"))
    assert "Copernicus Sentinel" in origen["descripcion"]


def test_de_una_misma_toma_va_primero_el_huso_de_la_imagen_de_antes() -> None:
    otra = satelite.escena_de_item(_item("S2A_37TDJ_20260426_0_L2A", "2026-04-26T08:40:00Z"))
    misma = satelite.escena_de_item(_item("S2A_36TYP_20260426_0_L2A", "2026-04-26T08:40:01Z"))
    despues = satelite.escena_de_item(_item("S2B_36TYP_20260429_0_L2A", "2026-04-29T08:40:00Z"))
    assert otra is not None and misma is not None and despues is not None
    orden = satelite.mismo_huso_primero([otra, misma, despues], "S2C_36TYP_20260315_0_L2A")
    assert [e.id for e in orden] == [misma.id, otra.id, despues.id]


def test_objetivos_que_deja_la_recogida_horaria(tmp_path: Path) -> None:
    objetivo = satelite.Objetivo(
        id="EODI-IG-2025-02569",
        recorte=satelite.Recorte(59.5, 32.08, 4000),
        antes_hasta=datetime(2025, 9, 30, 17, 0, tzinfo=UTC),
        despues_desde=datetime(2025, 10, 1, 6, 30, tzinfo=UTC),
        foco=True,
        lugar="Kirishi refinery",
    )
    ruta = tmp_path / satelite.OBJETIVOS
    ruta.write_text(
        json.dumps({"objetivos": [satelite.documento_de_objetivo(objetivo)]}), encoding="utf-8"
    )
    assert satelite.cargar_objetivos(ruta) == [objetivo]
    assert satelite.cargar_objetivos(tmp_path / "otro.json") is None
