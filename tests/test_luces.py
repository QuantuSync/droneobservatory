"""Apagones vistos desde el espacio: medida de la luz nocturna (proceso/luces.py), ataques
contra la energía, nubes y evaluación (recogida/luces.py), base, publicación, lista cerrada de
campos y exportación. Sin red: recortes reales pequeños de VIIRS (tests/fixtures/luces) y
series construidas aquí."""

import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from almacen.base import Almacen
from esquema import Documento, Esquema, validador, validador_definicion
from exportacion import procedencia
from exportacion.campos import CAMPOS_PUBLICOS_ATAQUE
from exportacion.proyeccion import fuera_de_lista
from exportacion.ucrania import exportar_ucrania
from proceso import luces
from recogida import luces as recogida_luces
from tests import ejemplos

FIXTURES = Path(__file__).parent / "fixtures" / "luces"
JARKOV = luces.Ciudad("katotth:UA63120270010096107", "Харків", "UA-63", 49.99232, 36.23101, 15.0)


# --- Medida de una ciudad ------------------------------------------------------------------


def _rejilla(lat0: float, lon0: float, n: int = 120, paso: float = 0.01) -> tuple[Any, Any]:
    lats = lat0 + (np.arange(n) - n / 2) * paso
    lons = lon0 + (np.arange(n) - n / 2) * paso * 1.5
    lon, lat = np.meshgrid(lons, lats)
    return lat.astype(np.float32), lon.astype(np.float32)


def _granulo(brillo_ciudad: float, fondo: float) -> dict[str, Any]:
    lat, lon = _rejilla(JARKOV.lat, JARKOV.lon)
    d = luces.distancias_km(lat, lon, JARKOV)
    radiancia = np.where(d <= 10, brillo_ciudad, fondo).astype(np.float32) / luces.NANO
    forma = lat.shape
    return {
        "lat": lat,
        "lon": lon,
        "radiancia": radiancia,
        "calidad": np.zeros(forma, dtype=np.uint8),
        "cenit_satelite": np.full(forma, 20.0, dtype=np.float32),
        "cenit_luna": np.full(forma, 70.0, dtype=np.float32),
        "cenit_sol": np.full(forma, 120.0, dtype=np.float32),
    }


def _medir(granulo: dict[str, Any], ciudad: luces.Ciudad = JARKOV) -> Documento | None:
    return luces.medir_ciudad(
        ciudad,
        granulo["lat"],
        granulo["lon"],
        granulo["radiancia"],
        granulo["calidad"],
        granulo["cenit_satelite"],
        granulo["cenit_luna"],
        granulo["cenit_sol"],
    )


def test_brillo_es_el_exceso_sobre_el_fondo() -> None:
    medida = _medir(_granulo(brillo_ciudad=12.0, fondo=2.0))
    assert medida is not None
    # Dentro del radio de 15 km: dos tercios del área (10 km) a 12 y el resto al fondo.
    assert medida["fondo"] == pytest.approx(2.0)
    assert 3.0 < medida["brillo"] < 5.5
    # La Luna sube el fondo y la ciudad por igual: el exceso no cambia.
    con_luna = _medir(_granulo(brillo_ciudad=15.0, fondo=5.0))
    assert con_luna is not None
    assert con_luna["brillo"] == pytest.approx(medida["brillo"], rel=1e-3)


def test_pixeles_de_mala_calidad_no_cuentan() -> None:
    granulo = _granulo(12.0, 2.0)
    granulo["calidad"][:, :] = 1  # pobre (luz parásita corregida): vale
    assert _medir(granulo) is not None
    granulo["calidad"][:, :] = 2  # sin calibrar
    assert _medir(granulo) is None


def test_ciudad_cortada_por_el_borde_del_granulo_no_vale() -> None:
    granulo = _granulo(12.0, 2.0)
    for clave in (
        "lat",
        "lon",
        "radiancia",
        "calidad",
        "cenit_satelite",
        "cenit_luna",
        "cenit_sol",
    ):
        granulo[clave] = granulo[clave][55:, :]
    assert _medir(granulo) is None


def test_ciudad_fuera_del_granulo() -> None:
    lejos = luces.Ciudad("x", "x", "UA-30", 10.0, 10.0, 7.0)
    assert _medir(_granulo(12.0, 2.0), lejos) is None


def test_validez_de_una_noche() -> None:
    buena = {
        "brillo": 5.0, "fondo": 1.0, "pixeles": 500, "cobertura": 0.9, "cenit_satelite": 30.0,
        "cenit_sol": 120.0, "nubes_pct": 10.0,
    }  # fmt: skip
    assert luces.valida(buena)
    assert not luces.valida({**buena, "nubes_pct": 80.0})
    assert not luces.valida({**buena, "nubes_pct": None})
    assert not luces.valida({**buena, "cenit_satelite": 65.0})
    assert not luces.valida({**buena, "cenit_sol": 100.0})
    assert not luces.valida({**buena, "fondo": 9.0})
    # Una ciudad cortada por el borde del gránulo.
    assert not luces.valida({**buena, "cobertura": 0.04})
    assert not luces.valida(None)


def test_el_mejor_paso_es_el_mas_vertical() -> None:
    pasos = [{"cenit_satelite": 50.0, "brillo": 1.0}, {"cenit_satelite": 12.0, "brillo": 2.0}]
    assert luces.mejor(pasos) == {"cenit_satelite": 12.0, "brillo": 2.0}
    assert luces.mejor([]) is None


# --- Recortes reales de VIIRS --------------------------------------------------------------


def _real(nombre: str) -> dict[str, Any]:
    with np.load(FIXTURES / nombre) as datos:
        return {k: datos[k] for k in datos.files}


@pytest.mark.skipif(not (FIXTURES / "jarkov_2024-03-20.npz").exists(), reason="sin recorte")
def test_recorte_real_de_jarkov_antes_y_despues_del_22_de_marzo_de_2024() -> None:
    antes = _medir(_real("jarkov_2024-03-20.npz"))
    despues = _medir(_real("jarkov_2024-03-23.npz"))
    assert antes is not None and despues is not None
    origen = json.loads((FIXTURES / "origen.json").read_text(encoding="utf-8"))
    assert origen["noches"]["2024-03-20"]["brillo"] == pytest.approx(antes["brillo"], rel=1e-3)
    assert origen["noches"]["2024-03-23"]["brillo"] == pytest.approx(despues["brillo"], rel=1e-3)
    # La ciudad entera sin electricidad (documentado): se ve como pérdida de más de la mitad.
    assert 1 - despues["brillo"] / antes["brillo"] >= luces.UMBRAL_PERDIDA


# --- Regla del ataque ----------------------------------------------------------------------

INICIO, FIN = date(2024, 3, 21), date(2024, 3, 22)


def _serie(referencia: float, despues: dict[int, float | None]) -> dict[date, float | None]:
    serie: dict[date, float | None] = {}
    for k in range(1, luces.DIAS_REFERENCIA + 1):
        # Unas noches sin dato (nubes) y algo de ruido.
        serie[INICIO - timedelta(days=k)] = (
            None if k % 3 == 0 else referencia * (1 + 0.05 * (k % 2))
        )
    for k, valor in despues.items():
        serie[INICIO + timedelta(days=k)] = valor
    return serie


def test_ventanas_de_noches() -> None:
    referencia = luces.noches_referencia(INICIO)
    assert referencia[0] == INICIO - timedelta(days=luces.DIAS_REFERENCIA)
    assert referencia[-1] == INICIO - timedelta(days=1)
    despues = luces.noches_despues(INICIO, FIN)
    assert despues[0] == INICIO and despues[-1] == FIN + timedelta(days=luces.DIAS_DESPUES)


def test_perdida_por_encima_del_umbral() -> None:
    resultado = luces.evaluar(_serie(5.0, {1: 0.5, 2: 1.5, 3: None, 5: 4.8}), INICIO, FIN)
    # Mediana de las noches de referencia con dato (5 y 5,25).
    assert resultado.referencia == pytest.approx(5.125)
    maxima = resultado.maxima
    assert maxima is not None and maxima[0] == INICIO + timedelta(days=1)
    assert maxima[1] == pytest.approx(1 - 0.5 / 5.125, abs=1e-4)
    assert resultado.perdida_luz
    assert resultado.noches_con_perdida() == [
        INICIO + timedelta(days=1),
        INICIO + timedelta(days=2),
    ]


def test_sin_perdida_o_ciudad_ya_apagada_o_sin_referencia() -> None:
    assert not luces.evaluar(_serie(5.0, {1: 3.5, 2: 3.0}), INICIO, FIN).perdida_luz
    # Una ciudad ya casi a oscuras: su ruido es del orden de la señal.
    assert not luces.evaluar(_serie(0.3, {1: 0.03, 2: 0.03}), INICIO, FIN).perdida_luz
    # Una sola noche oscura no basta: suele ser una nube que el modelo no ve.
    sola = luces.evaluar(_serie(5.0, {1: 0.5, 2: 4.9, 4: 5.1}), INICIO, FIN)
    assert sola.noches_con_perdida() == [INICIO + timedelta(days=1)] and not sola.perdida_luz
    sin_referencia = {INICIO - timedelta(days=2): 5.0, INICIO + timedelta(days=1): 0.1}
    resultado = luces.evaluar(sin_referencia, INICIO, FIN)
    assert resultado.referencia is None and not resultado.perdida_luz


def test_region_suma_sus_ciudades_las_mismas_noches() -> None:
    a = _serie(4.0, {1: 0.4, 2: 0.8})
    b = _serie(2.0, {1: 0.2, 2: 0.4})
    b[INICIO - timedelta(days=4)] = None
    noches = luces.noches_referencia(INICIO) + luces.noches_despues(INICIO, FIN)
    suma = luces.serie_de_region({"a": a, "b": b}, ["a", "b"], noches)
    assert suma[INICIO - timedelta(days=4)] is None
    assert suma[INICIO + timedelta(days=1)] == pytest.approx(0.6)
    assert luces.evaluar(suma, INICIO, FIN).perdida_luz


def test_documento_valida_con_el_esquema() -> None:
    resultado = luces.evaluar(_serie(5.0, {1: 0.5, 2: 1.0}), INICIO, FIN)
    zona = {"zona": "region", "region": "UA-63"}
    documento = luces.documento(zona, resultado, INICIO, FIN)
    assert documento is not None
    assert documento["perdida_pct"] == 90 and documento["origen"] == "medido"
    assert not list(validador_definicion("perdida_luz").iter_errors(documento))
    sin = luces.evaluar(_serie(5.0, {1: 4.0}), INICIO, FIN)
    assert luces.documento(zona, sin, INICIO, FIN) is None


# --- Ataques contra la energía ----------------------------------------------------------


def _ataque(id_: str, sentido: str, inicio: str, fin: str) -> Documento:
    return {
        "id": id_,
        "sentido": sentido,
        "periodo": {
            "inicio": {"valor": inicio, "precision": "minuto"},
            "fin": {"valor": fin, "precision": "minuto"},
        },
    }


def test_ataques_de_energia_por_mensajes_e_impactos() -> None:
    publicacion = {
        "ataques": [
            _ataque("EODI-UA-2024-0100", "RU_UA", "2024-03-21T17:00Z", "2024-03-22T05:00Z"),
            _ataque("EODI-UA-2024-0101", "RU_UA", "2024-03-24T17:00Z", "2024-03-25T05:00Z"),
            _ataque("EODI-UA-2024-0900", "UA_RU", "2024-03-21T17:00Z", "2024-03-22T05:00Z"),
        ],
        "impactos": [
            {
                "id": "EODI-IG-2024-00001",
                "ataque": "EODI-UA-2024-0101",
                "region": "UA-46",
                "categorias_objetivo": ["energia"],
            },
            {
                "id": "EODI-IG-2024-00002",
                "ataque": "EODI-UA-2024-0100",
                "region": "UA-12",
                "categorias_objetivo": ["residencial"],
            },
        ],
    }
    mensajes = [
        ("UA-63", datetime(2024, 3, 22, 7, 30, tzinfo=UTC)),  # balance de la mañana
        ("UA-63", datetime(2024, 3, 23, 9, 0, tzinfo=UTC)),  # fuera de las 18 h siguientes
        ("RU-BEL", datetime(2024, 3, 22, 1, 0, tzinfo=UTC)),
    ]
    ataques = recogida_luces.ataques_de_energia(publicacion, mensajes)
    por_id = {a.id: a.regiones for a in ataques}
    assert por_id == {
        "EODI-UA-2024-0100": ("UA-63",),
        "EODI-UA-2024-0101": ("UA-46",),
        "EODI-UA-2024-0900": ("RU-BEL",),
    }


def test_mensajes_de_energia_de_los_canales(tmp_path: Path) -> None:
    carpeta = tmp_path / "kharkivoda"
    carpeta.mkdir()
    lineas = [
        {
            "id": 1,
            "fecha": "2024-03-22T06:10:00Z",
            "texto": (
                "Внаслідок атаки ударних БпЛА пошкоджено об'єкт енергетичної "
                "інфраструктури, частина міста знеструмлена."
            ),
        },
        {"id": 2, "fecha": "2024-03-22T06:20:00Z", "texto": "Збито два ударні БпЛА над містом."},
    ]
    (carpeta / "2024-03.jsonl").write_text(
        "\n".join(json.dumps(x, ensure_ascii=False) for x in lineas) + "\n", encoding="utf-8"
    )
    canales = [{"canal": "kharkivoda", "region": "UA-63"}, {"canal": "GeneralStaffZSU"}]
    mensajes = recogida_luces.mensajes_de_energia(tmp_path, canales)
    assert mensajes == [("UA-63", datetime(2024, 3, 22, 6, 10, tzinfo=UTC))]


# --- Nubes y series ----------------------------------------------------------------------


def test_nubes_por_meses_con_cache_y_tope(tmp_path: Path) -> None:
    pedidos: list[str] = []

    def obtener(url: str) -> bytes:
        pedidos.append(url)
        horas = [f"2024-03-{d:02d}T{h:02d}:00" for d in range(1, 32) for h in range(24)]
        return json.dumps(
            {"hourly": {"time": horas, "cloud_cover": [h % 100 for h in range(len(horas))]}}
        ).encode()

    nubes = recogida_luces.Nubes(tmp_path, obtener, tope=3.0, hoy=date(2026, 10, 3))
    # 23:31 UTC → la hora en punto más cercana es la medianoche del día siguiente.
    assert nubes.en(JARKOV, "2024-03-22T23:20Z") == float((21 * 24 + 23) % 100)
    assert nubes.en(JARKOV, "2024-03-10T01:05Z") == float((9 * 24 + 1) % 100)
    assert len(pedidos) == 1 and "cloud_cover" in pedidos[0]
    # Otro mes no cabe en el tope de esta ejecución; el ya guardado se lee del disco.
    assert nubes.en(JARKOV, "2024-04-10T01:05Z") is None
    otra = recogida_luces.Nubes(tmp_path, obtener, tope=0.0, hoy=date(2026, 10, 3))
    assert otra.en(JARKOV, "2024-03-10T01:05Z") == float((9 * 24 + 1) % 100)


def test_series_validas_y_evaluacion_de_un_ataque(tmp_path: Path) -> None:
    ciudades = [JARKOV, luces.Ciudad("c2", "Чугуїв", "UA-63", 49.83, 36.69, 5.0)]
    datos = tmp_path / "luces"
    (datos / "noches").mkdir(parents=True)
    ataque = recogida_luces.AtaqueEnergia(
        "EODI-UA-2024-0100", "RU_UA", datetime(2024, 3, 21, 17, tzinfo=UTC),
        datetime(2024, 3, 22, 5, tzinfo=UTC), ("UA-63",),
    )  # fmt: skip
    for noche in recogida_luces.noches_de(INICIO, FIN):
        despues = noche >= INICIO + timedelta(days=1) and noche <= INICIO + timedelta(days=3)
        medida = {
            "brillo": 0.4 if despues else 5.0, "fondo": 1.0, "pixeles": 600, "cobertura": 0.95,
            "cenit_satelite": 20.0, "cenit_luna": 90.0, "cenit_sol": 120.0,
            "hora": f"{noche.isoformat()}T23:30Z", "luna_pct": 10.0,
        }  # fmt: skip
        documento = {
            "noche": noche.isoformat(),
            "ciudades": {JARKOV.id: medida, "c2": {**medida, "brillo": 2.0}},
        }
        (datos / "noches" / f"{noche.isoformat()}.json").write_text(
            json.dumps(documento), encoding="utf-8"
        )

    class SinNubes:
        def en(self, ciudad: luces.Ciudad, hora: str) -> float:
            return 5.0

    serie = recogida_luces.series(
        datos, recogida_luces.noches_de(INICIO, FIN), ciudades, SinNubes()
    )
    documentos = recogida_luces.evaluar_ataque(ataque, ciudades, serie)
    zonas = {(d["zona"], d.get("ciudad", {}).get("nombre")) for d in documentos}
    assert ("ciudad", "Харків") in zonas and ("region", None) in zonas
    assert ("ciudad", "Чугуїв") not in zonas  # no pierde luz
    for documento in documentos:
        assert not list(validador_definicion("perdida_luz").iter_errors(documento))


def test_noches_pendientes_de_la_mas_reciente_a_la_mas_antigua(tmp_path: Path) -> None:
    (tmp_path / "noches").mkdir()
    (tmp_path / "noches" / "2024-03-20.json").write_text("{}")
    necesarias = [date(2024, 3, d) for d in (19, 20, 21)] + [date(2023, 12, 1), date(2026, 10, 3)]
    pendientes = recogida_luces.noches_pendientes(
        tmp_path, necesarias, datetime(2026, 10, 3, 12, tzinfo=UTC)
    )
    assert pendientes == [date(2024, 3, 21), date(2024, 3, 19)]


def test_eleccion_de_granulos_por_ciudad() -> None:
    contorno_a = [[52.0, 52.0, 47.0, 47.0], [30.0, 40.0, 40.0, 30.0]]  # centro 49,5 / 35
    contorno_b = [[53.0, 53.0, 48.0, 48.0], [33.0, 43.0, 43.0, 33.0]]  # centro 50,5 / 38
    asignadas = recogida_luces.elegir_granulos({"a": contorno_a, "b": contorno_b}, [JARKOV])
    # Los dos la contienen: se mide en los dos y vale la medida más vertical.
    assert sorted(asignadas) == ["a", "b"]
    assert recogida_luces.dentro(contorno_a, 49.99, 36.23)
    assert not recogida_luces.dentro(contorno_a, 55.0, 36.23)


# --- Validación ----------------------------------------------------------------------------


def test_casos_de_validacion_con_ciudades_conocidas() -> None:
    casos = recogida_luces.casos_validacion()
    ids = {c.id for c in recogida_luces.cargar_ciudades()}
    apagones = [c for c in casos if c["tipo"] == "apagon"]
    assert len(apagones) >= 12 and len([c for c in casos if c["tipo"] == "control"]) >= 6
    for caso in casos:
        assert set(caso["ciudades"]) <= ids, caso["id"]
        assert date.fromisoformat(caso["inicio"]) <= date.fromisoformat(caso["fin"])
        if caso["tipo"] == "apagon":
            assert caso["fuentes"], caso["id"]


def test_controles_automaticos_fuera_de_los_ataques() -> None:
    serie: dict[str, dict[date, float | None]] = {
        JARKOV.id: {date(2024, 1, 1) + timedelta(days=k): 5.0 for k in range(120)}
    }
    ataque = recogida_luces.AtaqueEnergia(
        "EODI-UA-2024-0100", "RU_UA", datetime(2024, 2, 1, 17, tzinfo=UTC),
        datetime(2024, 2, 2, 5, tzinfo=UTC), ("UA-63",),
    )  # fmt: skip
    perdidas = recogida_luces.controles_automaticos([JARKOV], serie, [ataque])
    assert perdidas and all(r.maxima is not None and r.maxima[1] == 0 for r in perdidas)
    validacion = recogida_luces.validar([], [JARKOV], serie, [ataque])
    assert validacion["controles_automaticos"]["falsos_positivos"] == 0


# --- Base, publicación, lista cerrada y exportación ------------------------------------


def _ataque_completo() -> Documento:
    return ejemplos.ataque_completo()


def test_incorporar_guardar_y_publicar(tmp_path: Path) -> None:
    almacen = Almacen.abrir()
    ataque = _ataque_completo()
    ahora = datetime(2026, 10, 3, tzinfo=UTC)
    almacen.guardar_ataque_ucrania(ataque, ahora)
    resultados = {
        "version": luces.VERSION,
        "ataques": {ataque["id"]: [ejemplos.perdida_luz(), ejemplos.perdida_luz("region")]},
    }
    (tmp_path / recogida_luces.RESULTADOS).write_text(json.dumps(resultados), encoding="utf-8")
    assert recogida_luces.incorporar(almacen, tmp_path) == 1
    assert recogida_luces.incorporar(almacen, tmp_path) == 0
    con = luces.con_luces(almacen.ataques_ucrania(), almacen.luces_nocturnas())
    publicacion = exportar_ucrania(con, ahora)
    publico = publicacion["ataques"][0]
    assert len(publico["perdida_luz"]) == 2
    assert publico["perdida_luz"][0]["origen"] == "medido"
    assert not fuera_de_lista(publicacion["ataques"], CAMPOS_PUBLICOS_ATAQUE)
    # Un ataque que deja de tener pérdida se queda sin ninguna.
    (tmp_path / recogida_luces.RESULTADOS).write_text(
        json.dumps({"version": luces.VERSION, "ataques": {}}), encoding="utf-8"
    )
    assert recogida_luces.incorporar(almacen, tmp_path) == 1
    sin = luces.con_luces(almacen.ataques_ucrania(), almacen.luces_nocturnas())
    assert "perdida_luz" not in sin[0]


def test_lista_cerrada_de_campos_publicos_de_la_perdida_de_luz() -> None:
    esperados = {
        "perdida_luz", "perdida_luz[].zona", "perdida_luz[].region", "perdida_luz[].ciudad",
        "perdida_luz[].ciudad.id", "perdida_luz[].ciudad.nombre", "perdida_luz[].ciudad.punto",
        "perdida_luz[].ciudad.punto.lat", "perdida_luz[].ciudad.punto.lon",
        "perdida_luz[].perdida_pct", "perdida_luz[].noche", "perdida_luz[].noches",
        "perdida_luz[].referencia", "perdida_luz[].referencia.desde",
        "perdida_luz[].referencia.hasta", "perdida_luz[].referencia.noches",
        "perdida_luz[].referencia.brillo", "perdida_luz[].brillo", "perdida_luz[].origen",
    }  # fmt: skip
    assert {c for c in CAMPOS_PUBLICOS_ATAQUE if c.startswith("perdida_luz")} == esperados
    # Un campo que no está en la lista no sale.
    ataque = {**_ataque_completo(), "perdida_luz": [{**ejemplos.perdida_luz(), "interno": 1}]}
    fuera = fuera_de_lista([ataque], CAMPOS_PUBLICOS_ATAQUE)
    assert [c for c in fuera if c.startswith("perdida_luz")] == ["perdida_luz[].interno"]


def test_esquema_del_ataque_admite_la_perdida_de_luz() -> None:
    ataque = {**_ataque_completo(), "perdida_luz": [ejemplos.perdida_luz()]}
    assert not list(validador(Esquema.ATAQUE_UCRANIA).iter_errors(ataque))
    roto = {**ejemplos.perdida_luz(), "origen": "prensa"}
    assert list(validador(Esquema.ATAQUE_UCRANIA).iter_errors({**ataque, "perdida_luz": [roto]}))


def test_exportacion_la_marca_como_medida() -> None:
    ataque = {**_ataque_completo(), "perdida_luz": [ejemplos.perdida_luz()]}
    exportado = procedencia.exportar_ataque(ataque)
    assert exportado["procedencia"]["perdida_luz"] == {
        "origen": "medido",
        "metodo": "regla",
        "fuentes": [],
    }


def test_huellas_muestreadas_y_vecinas() -> None:
    inicio = datetime(2024, 3, 21, 22, tzinfo=UTC)
    granulos = [
        recogida_luces.Granulo(
            f"g{i}", f"geo{i}", f"sdr{i}", 1, 1, inicio + timedelta(seconds=85 * i)
        )
        for i in range(30)
    ]
    primera = recogida_luces.a_leer(granulos, {})
    assert primera == list(range(0, 30, 3))
    dentro = [[50.0, 50.0, 46.0, 46.0], [30.0, 36.0, 36.0, 30.0]]
    fuera = [[10.0, 10.0, 5.0, 5.0], [100.0, 106.0, 106.0, 100.0]]
    conocidos = {f"g{i}": (dentro if i == 12 else fuera) for i in primera}
    assert recogida_luces.a_leer(granulos, conocidos) == [10, 11, 13, 14]


def test_noche_medida_en_dos_veces(tmp_path: Path) -> None:
    (tmp_path / "noches").mkdir()
    parcial = {
        "noche": "2024-03-20",
        "granulos": ["a"],
        "pedidas": ["c1"],
        "ciudades": {"c1": {"brillo": 1.0}},
    }
    (tmp_path / "noches" / "2024-03-20.json").write_text(json.dumps(parcial))
    ahora = datetime(2026, 10, 3, 12, tzinfo=UTC)
    noche = [date(2024, 3, 20)]
    assert recogida_luces.noches_pendientes(tmp_path, noche, ahora, ["c1"]) == []
    assert recogida_luces.noches_pendientes(tmp_path, noche, ahora, ["c1", "c2"]) == noche
    assert recogida_luces.faltan_en(parcial, ["c1", "c2"]) == {"c2"}
    nuevo = {
        "noche": "2024-03-20",
        "granulos": ["b"],
        "pedidas": ["c2"],
        "ciudades": {"c2": {"brillo": 2.0}},
    }
    unida = recogida_luces.unir(parcial, nuevo)
    assert unida["pedidas"] == ["c1", "c2"] and set(unida["ciudades"]) == {"c1", "c2"}
    assert unida["granulos"] == ["a", "b"]


def test_la_exportacion_semanal_lleva_la_perdida_de_luz_medida() -> None:
    from exportacion import semanal
    from tests.test_exportacion_semanal import lineas, poblado, por_nombre

    almacen = poblado()
    ataque_id = ejemplos.ataque_completo()["id"]
    almacen.guardar_luces_nocturnas(
        ataque_id, {"version": luces.VERSION, "perdidas": [ejemplos.perdida_luz()]}
    )
    ficheros = por_nombre(semanal.generar(almacen))
    ataques = {a["id"]: a for a in lineas(ficheros["ucrania_ataques.jsonl"])}
    exportado = ataques[ataque_id]
    assert exportado["perdida_luz"] == [ejemplos.perdida_luz()]
    assert exportado["procedencia"]["perdida_luz"]["origen"] == "medido"


# --- Alumbrado reducido de forma permanente ----------------------------------------------


def _serie_mensual(valores: dict[str, float], noches_por_mes: int = 6) -> dict[date, float | None]:
    """Una serie con `noches_por_mes` noches válidas en cada mes («AAAA-MM») con ese brillo."""
    serie: dict[date, float | None] = {}
    for mes, valor in valores.items():
        primero = date.fromisoformat(f"{mes}-01")
        for k in range(noches_por_mes):
            serie[primero + timedelta(days=3 * k)] = valor
            serie[primero + timedelta(days=3 * k + 1)] = None  # una noche nublada entre medias
    return serie


def test_alumbrado_reducido_desde_el_primer_mes_medido() -> None:
    serie = _serie_mensual({"2024-03": 0.3, "2024-04": 0.32, "2024-05": 0.28, "2024-06": 0.3})
    alumbrado = luces.alumbrado_reducido(serie)
    assert alumbrado is not None
    assert alumbrado.al_menos and alumbrado.desde == date(2024, 3, 1)
    assert alumbrado.ultimo_mes_por_encima is None
    assert alumbrado.actual.brillo == pytest.approx(0.3)
    assert alumbrado.antiguo.brillo == pytest.approx(0.3) and alumbrado.antiguo.noches == 10
    assert alumbrado.noches == 24


def test_alumbrado_un_mes_de_nieve_no_rompe_la_racha() -> None:
    # Enero con nieve: la ciudad refleja su luz y sube por encima del mínimo un mes suelto.
    serie = _serie_mensual({"2025-11": 0.3, "2025-12": 0.3, "2026-01": 1.1, "2026-02": 0.3})
    alumbrado = luces.alumbrado_reducido(serie)
    assert alumbrado is not None and alumbrado.al_menos


def test_alumbrado_desde_que_deja_de_pasar_del_minimo() -> None:
    serie = _serie_mensual(
        {"2024-03": 2.0, "2024-04": 2.1, "2024-05": 0.3, "2024-06": 0.25, "2024-07": 0.3}
    )
    alumbrado = luces.alumbrado_reducido(serie)
    assert alumbrado is not None
    assert not alumbrado.al_menos and alumbrado.desde == date(2024, 5, 1)
    assert alumbrado.ultimo_mes_por_encima == "2024-04"
    assert alumbrado.antiguo.brillo == pytest.approx(2.0)
    documento = luces.documento_alumbrado(JARKOV, alumbrado)
    assert documento["desde"] == "2024-05-01" and documento["ultimo_mes_por_encima"] == "2024-04"
    assert documento["actual"]["noches"] == 10 and documento["origen"] == "medido"


def test_alumbrado_no_en_ciudades_iluminadas_ni_con_pocas_noches() -> None:
    assert luces.alumbrado_reducido(_serie_mensual({"2024-03": 2.0, "2024-04": 1.8})) is None
    # Con menos de dos niveles de noches no se dice nada.
    assert luces.alumbrado_reducido(_serie_mensual({"2024-03": 0.2}, noches_por_mes=8)) is None


def test_alumbrado_en_el_fichero_publico() -> None:
    meses = ("2024-03", "2024-04", "2024-05", "2024-06")
    serie = {JARKOV.id: _serie_mensual(dict.fromkeys(meses, 0.3))}
    otra = luces.Ciudad("c2", "Чугуїв", "UA-63", 49.83, 36.69, 5.0)
    serie["c2"] = _serie_mensual(dict.fromkeys(meses, 3.0))
    ciudades = recogida_luces.alumbrado([JARKOV, otra], serie)
    assert [c["ciudad"]["nombre"] for c in ciudades] == ["Харків"]
    publico = recogida_luces.documento_de_alumbrado(ciudades, datetime(2026, 10, 4, tzinfo=UTC))
    assert publico["referencia_minima"] == luces.BRILLO_REFERENCIA_MIN


def test_apagon_documentado_cuenta_para_el_ataque_de_ese_dia() -> None:
    publicacion = {
        "ataques": [
            # La noche del 27 al 28: casi todo el día 28 cae en este.
            _ataque("EODI-UA-2024-0227", "RU_UA", "2024-11-27T16:00Z", "2024-11-28T11:57Z"),
            _ataque("EODI-UA-2024-0228", "RU_UA", "2024-11-28T16:30Z", "2024-11-29T07:00Z"),
            _ataque("EODI-UA-2024-1418", "UA_RU", "2024-11-28T06:00Z", "2024-11-28T20:30Z"),
        ],
        "impactos": [],
    }
    ataques = recogida_luces.ataques_de_energia(publicacion, [], [(date(2024, 11, 28), "UA-56")])
    assert [(a.id, a.regiones) for a in ataques] == [("EODI-UA-2024-0227", ("UA-56",))]
    casos = [
        {"tipo": "apagon", "inicio": "2024-11-28", "ciudades": [JARKOV.id, "otra"]},
        {"tipo": "control", "inicio": "2024-07-01", "ciudades": [JARKOV.id]},
    ]
    assert recogida_luces.apagones_documentados(casos, [JARKOV]) == [(date(2024, 11, 28), "UA-63")]


def test_alumbrado_se_sube_al_almacen(tmp_path: Path) -> None:
    subidos: list[tuple[str, str, str]] = []

    def subir(objeto: str, cuerpo: bytes, tipo: str, cache: str) -> bool:
        subidos.append((objeto, tipo, cache))
        assert json.loads(cuerpo)["ciudades"] == []
        return True

    assert not recogida_luces.subir_alumbrado(tmp_path, subir)
    documento = recogida_luces.documento_de_alumbrado([], datetime(2026, 10, 4, tzinfo=UTC))
    (tmp_path / recogida_luces.ALUMBRADO).write_text(json.dumps(documento), encoding="utf-8")
    assert recogida_luces.subir_alumbrado(tmp_path, subir)
    assert subidos == [("luces/alumbrado.json", "application/json", "public, max-age=3600")]
