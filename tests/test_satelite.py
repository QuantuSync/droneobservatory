"""Imágenes de antes y después (recogida/satelite.py) y lectura de ventanas de COG
(recogida/cog.py), sin red: recortes reales pequeños de Sentinel-2 sobre Kirishi
(tests/fixtures/satelite) y un GeoTIFF en teselas escrito aquí."""

import io
import json
import struct
import zlib
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from PIL import Image

from esquema import Documento
from proceso import cambio
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
            "nir08": {"href": f"https://cogs/{id_}/B8A.tif"},
            "swir22": {"href": f"https://cogs/{id_}/B12.tif"},
        },
    }


class Archivo:
    """Doble del catálogo STAC y de las imágenes: las SCL son los recortes reales."""

    def __init__(self, items: list[Documento], nubladas: set[str]) -> None:
        self.items = items
        self.nubladas = nubladas
        self.busquedas: list[Documento] = []

    def buscar(self, cuerpo: Documento) -> Documento:
        if "ids" in cuerpo:
            return {"features": [i for i in self.items if i["id"] in cuerpo["ids"]]}
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


ANTES = "S2C_36VVL_20250911_1_L2A"
CON_CAMBIO = "S2C_36VVM_20250926_0_L2A"
SIN_CAMBIO = "S2B_36VVL_20250921_0_L2A"


def _bandas_reales(nombre: str) -> dict[str, cambio.Bandas]:
    datos = np.load(FIXTURES / f"cambio_{nombre}.npz")
    return {
        fecha: cambio.Bandas(
            scl=datos[f"{fecha}_scl"],
            b8a=datos[f"{fecha}_b8a"],
            b12=datos[f"{fecha}_b12"],
            rgb=datos[f"{fecha}_rgb"],
        )
        for fecha in ("antes", "despues")
    }


def _con_bandas(monkeypatch: pytest.MonkeyPatch, archivo: Archivo) -> None:
    """La SCL de cada escena para las nubes y sus bandas en la rejilla: la escena CON_CAMBIO es
    el después de una pareja real con quemado (EODI-IG-2025-02593); cualquier otra, su antes
    (sin cambio)."""
    despejada = _png("scl_despejada.png")
    nublada = _png("scl_nublada.png")
    reales = _bandas_reales("EODI-IG-2025-02593")

    def leer_banda(lector: Lector, url: str, recorte: satelite.Recorte, epsg: int) -> Any:
        escena = url.split("/")[3]
        return (nublada if escena in archivo.nubladas else despejada)[:, :, None]

    def bandas(lector: Lector, escena: satelite.Escena, recorte: satelite.Recorte) -> Any:
        return reales["despues" if escena.id == CON_CAMBIO else "antes"]

    monkeypatch.setattr(satelite, "leer_banda", leer_banda)
    monkeypatch.setattr(satelite, "bandas", bandas)


def _objetivo() -> satelite.Objetivo:
    return satelite.Objetivo(
        id="EODI-IG-2025-02569",
        recorte=satelite.Recorte(59.49, 32.078, 3000),
        antes_hasta=datetime(2025, 9, 13, 17, tzinfo=UTC),
        despues_desde=datetime(2025, 9, 14, 7, tzinfo=UTC),
        foco=True,
        lugar="Kirishi",
    )


def test_pareja_con_cambio_se_publica_y_sin_cambio_se_sigue_buscando(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    archivo = Archivo(
        [
            _item("S2B_36VVL_20250901_0_L2A", "2025-09-01T09:20:00Z"),
            _item(ANTES, "2025-09-11T09:14:10Z"),
            _item("S2A_36VVL_20250913_0_L2A", "2025-09-13T09:20:00Z", nubes=5.0),
            _item("S2A_36VVL_20250916_0_L2A", "2025-09-16T09:20:00Z", nubes=2.0),
            # Despejada, pero sin cambio: el humo tapaba aún el daño.
            _item(SIN_CAMBIO, "2025-09-21T09:20:00Z"),
            _item(CON_CAMBIO, "2025-09-26T09:13:57Z", nubes=70.0),
        ],
        nubladas={"S2A_36VVL_20250913_0_L2A", "S2A_36VVL_20250916_0_L2A"},
    )
    _con_bandas(monkeypatch, archivo)
    subidos: dict[str, bytes] = {}

    def subir(objeto: str, cuerpo: bytes, tipo: str, cache: str) -> bool:
        subidos[objeto] = cuerpo
        return True

    # Antes de la escena con cambio: nada que publicar, se sigue buscando.
    entrada = satelite.procesar(
        _objetivo(), {}, archivo.buscar, Lector(), subir, datetime(2025, 9, 25, tzinfo=UTC)
    )
    assert entrada["antes"]["escena"] == ANTES and "objeto" not in entrada["antes"]
    assert "despues" not in entrada and not entrada.get("sin_cambio")
    assert entrada["revisadas"] == [SIN_CAMBIO]
    assert subidos == {}
    # Con la escena con cambio: la pareja se publica con su contorno.
    entrada = satelite.procesar(
        _objetivo(), entrada, archivo.buscar, Lector(), subir, datetime(2025, 10, 5, tzinfo=UTC)
    )
    assert entrada["despues"]["escena"] == CON_CAMBIO
    assert entrada["cambio"]["principal"] >= cambio.UMBRAL_PRINCIPAL_HA
    assert len(entrada["cambio"]["contorno"]) >= 3
    lado = entrada["cambio"]["recorte"]["lado_m"]
    assert entrada["antes"]["objeto"] == (
        f"satelite/EODI-IG-2025-02569/antes-20250911-{ANTES}-{lado}.jpg"
    )
    assert set(subidos) == {entrada["antes"]["objeto"], entrada["despues"]["objeto"]}
    # La imagen de antes nunca es posterior al inicio del ataque.
    assert archivo.busquedas[0]["datetime"].endswith("2025-09-13T17:00:00Z")
    publico = satelite.indice({"EODI-IG-2025-02569": entrada}, datetime(2025, 10, 5, tzinfo=UTC))
    pareja = publico["parejas"]["EODI-IG-2025-02569"]
    assert pareja["cambio"]["hectareas"] > 0 and pareja["lugar"] == "Kirishi"


def test_sin_cambio_en_el_plazo_no_se_publica_y_se_retira(monkeypatch: pytest.MonkeyPatch) -> None:
    archivo = Archivo(
        [_item(ANTES, "2025-09-11T09:14:10Z"), _item(SIN_CAMBIO, "2025-09-21T09:20:00Z")], set()
    )
    _con_bandas(monkeypatch, archivo)
    # Una pareja de las primeras, publicada sin medir.
    previa = {
        "recorte": {"lat": 59.49, "lon": 32.078, "lado_m": 3000},
        "antes": {"escena": ANTES, "fecha": "2025-09-11T09:14:10Z", "objeto": "satelite/x/a.jpg"},
        "antes_buscado": True,
        "despues": {
            "escena": SIN_CAMBIO,
            "fecha": "2025-09-21T09:20:00Z",
            "objeto": "satelite/x/d.jpg",
        },
    }
    borrados: list[str] = []

    def borrar(objeto: str) -> bool:
        borrados.append(objeto)
        return True

    entrada = satelite.procesar(
        _objetivo(),
        previa,
        archivo.buscar,
        Lector(),
        lambda *a: True,
        datetime(2025, 11, 1, tzinfo=UTC),
        borrar,
    )
    assert entrada["sin_cambio"] is True and "cambio" not in entrada
    assert sorted(borrados) == ["satelite/x/a.jpg", "satelite/x/d.jpg"]
    publico = satelite.indice({"EODI-IG-2025-02569": entrada}, datetime(2025, 11, 1, tzinfo=UTC))
    assert publico["parejas"] == {}


def test_un_recorte_distinto_rehace_la_pareja(monkeypatch: pytest.MonkeyPatch) -> None:
    archivo = Archivo([_item(ANTES, "2025-09-11T09:14:10Z")], set())
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
    assert entrada["antes"]["escena"] == ANTES


def test_medida_del_cambio_con_parejas_reales() -> None:
    quemado = _bandas_reales("EODI-IG-2025-02593")
    medida = cambio.medir(quemado["antes"], quemado["despues"], (150, 150))
    assert medida.pasa and medida.principal == pytest.approx(16.56, abs=0.5)
    # La primavera reverdece todo el recorte: cambio de estación, no del ataque.
    estacion = _bandas_reales("EODI-IG-2025-02693")
    medida = cambio.medir(estacion["antes"], estacion["despues"], (150, 150))
    assert not medida.pasa and medida.exceso > 0
    # Dos fechas iguales: nada.
    nada = cambio.medir(quemado["antes"], quemado["antes"], (150, 150))
    assert nada.principal == 0 and not nada.pixeles


def test_reencuadre_en_la_mancha() -> None:
    # Una mancha pequeña en una esquina de un recorte de 3 km.
    pixeles = tuple((f, c) for f in range(20, 40) for c in range(240, 270))
    medida = cambio.Cambio(6.0, 0.0, 0.1, 0.0, 1.0, pixeles, 300, principal=6.0)
    fila, columna, lado = medida.reencuadre() or (0.0, 0.0, 0.0)
    assert (fila, columna) == (30.0, 255.0) and lado == 150.0
    nuevo = satelite.reencuadrado(satelite.Recorte(50.0, 30.0, 3000), medida)
    assert nuevo.lado_m == 1500 and nuevo.lat > 50.0 and nuevo.lon > 30.0
    # Centrada y grande: se queda como está.
    centrada = tuple((f, c) for f in range(100, 200) for c in range(100, 200))
    assert cambio.Cambio(100.0, 0.0, 1.0, 0.0, 1.0, centrada, 300).reencuadre() is None
    assert len(cambio.envolvente(centrada)) == 4


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
            "cambio": {
                "hectareas": 24.6,
                "principal": 16.6,
                "contorno": [[0.4, 0.4], [0.6, 0.4], [0.5, 0.6]],
                "recorte": {"lat": 59.5, "lon": 32.08, "lado_m": 4000},
            },
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


def test_tesela_de_16_bits_con_predictor() -> None:
    valores = np.array([[[1000], [1200], [900], [65000]]], dtype="<u2")
    diferencias = np.diff(valores, axis=1, prepend=np.zeros((1, 1, 1), dtype="<u2"))
    cabecera = cog.Cabecera(
        ancho=4, alto=1, muestras=1, tesela_ancho=4, tesela_alto=1, compresion=8, predictor=2,
        offsets=(0,), cuentas=(0,), x0=0.0, y0=0.0, paso_x=20.0, paso_y=20.0, bits=16,
    )  # fmt: skip
    tesela = cog.decodificar_tesela(zlib.compress(diferencias.astype("<u2").tobytes()), cabecera)
    assert tesela.dtype == np.uint16
    assert tesela[0, :, 0].tolist() == [1000, 1200, 900, 65000]


def test_borrar_del_almacen_firmado_y_lo_que_no_esta_vale() -> None:
    import urllib.error

    from recogida import almacen_publico

    almacen = almacen_publico.cargar()
    peticiones: list[Any] = []

    def enviar(peticion: Any, tope: float) -> int:
        peticiones.append(peticion)
        return 204

    correcto, _ = almacen_publico.borrar(almacen, "satelite/x/a.jpg", "id", "secreto", enviar)
    assert correcto and peticiones[0].get_method() == "DELETE"
    assert "Signature=" in peticiones[0].get_header("Authorization")

    def no_esta(peticion: Any, tope: float) -> int:
        raise urllib.error.HTTPError(peticion.full_url, 404, "no", {}, None)  # type: ignore[arg-type]

    assert almacen_publico.borrar(almacen, "satelite/x/a.jpg", "id", "secreto", no_esta)[0]
