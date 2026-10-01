"""Regla de cruce de los impactos con los focos de FIRMS y su paso a la publicación."""

import copy
from datetime import UTC, date, datetime, timedelta

import pytest

from almacen.base import Almacen, DocumentoInvalido
from esquema import Documento, Esquema, Visibilidad, rutas_por_visibilidad
from exportacion.campos import CAMPOS_PUBLICOS_ATAQUE, CAMPOS_PUBLICOS_INCIDENTE
from exportacion.geojson import exportar
from exportacion.proyeccion import ExportacionInvalida, rutas
from exportacion.ucrania import exportar_ucrania
from proceso import focos_termicos as ft
from recogida.plazo import Plazo
from tests import ejemplos
from tests.ejemplos import AHORA, VOCABULARIO_MODELOS, instante

CAJA = ft.Caja(oeste=22.0, sur=43.0, este=60.0, norte=61.0)
# Una refinería: el punto del impacto, con precisión de instalación.
LAT, LON = 51.4508, 45.9447
INICIO = datetime(2025, 8, 9, 21, 0, tzinfo=UTC)
FIN = datetime(2025, 8, 10, 6, 0, tzinfo=UTC)
EVALUADO = datetime(2025, 8, 20, 12, 0, tzinfo=UTC)
# Unos 1,1 km por centésima de grado de latitud.
KM = 1 / 111.2


def impacto(radio_km: float | None = 2.0, **cambios: object) -> ft.Impacto:
    datos: dict[str, object] = {
        "id": "EODI-2025-00099", "inicio": INICIO, "fin": FIN,
        "lat": LAT, "lon": LON, "radio_km": radio_km,
    }  # fmt: skip
    datos.update(cambios)
    return ft.Impacto(**datos)  # type: ignore[arg-type]


def foco(
    cuando: datetime,
    km_norte: float = 0.0,
    frp: float = 50.0,
    confianza: str = "n",
    instrumento: str = "VIIRS",
) -> ft.Foco:
    return ft.Foco(
        lat=LAT + km_norte * KM,
        lon=LON,
        instante=cuando,
        satelite="NOAA-20" if instrumento == "VIIRS" else "Aqua",
        instrumento=instrumento,
        confianza=confianza,
        frp=frp,
        fuente="VIIRS_NOAA20_SP" if instrumento == "VIIRS" else "MODIS_SP",
    )


def pixeles(cuando: datetime, km_norte: float = 0.0, **cambios: object) -> list[ft.Foco]:
    """Dos píxeles vecinos del mismo paso: el segundo, 100 m más al norte."""
    return [
        foco(cuando, km_norte, **cambios),  # type: ignore[arg-type]
        foco(cuando, km_norte + 0.1, **cambios),  # type: ignore[arg-type]
    ]


def lector(focos: list[ft.Foco], sin_datos: set[date] | None = None) -> ft.Lector:
    """Todos los días tienen fichero (vacío si no hay focos), salvo los de `sin_datos`."""
    faltan = sin_datos or set()

    def leer(dia: date) -> list[ft.Foco] | None:
        if dia in faltan:
            return None
        return [f for f in focos if f.instante.date() == dia]

    return leer


def evaluar(focos: list[ft.Foco], imp: ft.Impacto | None = None) -> Documento:
    resultado = ft.evaluar(imp or impacto(), lector(focos), EVALUADO, CAJA)
    assert resultado is not None
    return resultado.documento


# --- Dentro y fuera del radio y de la ventana ------------------------------------------


def test_foco_dentro_del_radio_y_de_la_ventana_es_detectado() -> None:
    documento = evaluar([*pixeles(FIN + timedelta(hours=-3), km_norte=1.5, frp=80)])
    assert documento["resultado"] == "detectado"
    assert documento["primer_foco"] == instante("2025-08-10T03:00Z")
    assert documento["satelite"] == "NOAA-20" and documento["instrumento"] == "VIIRS"
    assert documento["distancia_km"] == 1.5
    assert documento["numero_focos"] == 2 and documento["frp_max_mw"] == 80
    assert documento["radio_km"] == 2.0


def test_foco_fuera_del_radio_no_cuenta() -> None:
    documento = evaluar([foco(FIN, km_norte=2.5)])
    assert documento["resultado"] == "no_detectado"
    assert documento["motivo"] == "sin_focos"


@pytest.mark.parametrize(
    ("cuando", "resultado"),
    [
        (INICIO - timedelta(minutes=1), "no_detectado"),
        (INICIO, "detectado"),
        (FIN + timedelta(hours=35), "detectado"),
        (FIN + timedelta(hours=36), "detectado"),
        (FIN + timedelta(hours=36, minutes=1), "no_detectado"),
    ],
)
def test_ventana_del_inicio_a_36_horas_tras_el_fin(cuando: datetime, resultado: str) -> None:
    assert evaluar([*pixeles(cuando)])["resultado"] == resultado


def test_el_primer_foco_es_el_mas_temprano_y_se_cuentan_todos() -> None:
    focos = [foco(FIN + timedelta(hours=12), km_norte=0.2), foco(FIN, km_norte=1.0)]
    documento = evaluar(focos)
    assert documento["primer_foco"] == instante("2025-08-10T06:00Z")
    assert documento["distancia_km"] == 1.0
    assert documento["numero_focos"] == 2


def test_un_foco_suelto_no_basta() -> None:
    documento = evaluar([foco(FIN, km_norte=1.0)])
    assert documento["resultado"] == "no_detectado"
    assert documento["motivo"] == "foco_aislado"


def test_radio_minimo_de_2_km_y_maximo_de_10() -> None:
    assert evaluar([*pixeles(FIN, km_norte=1.8)], impacto(0.5))["resultado"] == "detectado"
    assert evaluar([*pixeles(FIN, km_norte=9.5)], impacto(10.0))["resultado"] == "detectado"
    assert evaluar([foco(FIN, km_norte=5.5)], impacto(5.0))["resultado"] == "no_detectado"


# --- No evaluables ------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("imp", "motivo"),
    [
        (impacto(15.0), "sin_lugar_preciso"),
        (impacto(None, lat=None, lon=None), "sin_lugar_preciso"),
        (impacto(lat=52.5, lon=13.4), "fuera_de_zona"),
        (impacto(inicio=datetime(2022, 10, 20, tzinfo=UTC)), "sin_datos_firms"),
    ],
)
def test_no_evaluable(imp: ft.Impacto, motivo: str) -> None:
    documento = evaluar([foco(FIN)], imp)
    assert documento["resultado"] == "no_evaluable"
    assert documento["motivo"] == motivo


def test_region_sin_localidad_no_es_evaluable() -> None:
    region = ft.Impacto(id="EODI-UA-2025-0001/UA-63", inicio=INICIO, fin=FIN)
    assert evaluar([foco(FIN)], region)["motivo"] == "sin_lugar_preciso"


def test_sin_datos_de_algun_dia_de_la_ventana_queda_pendiente() -> None:
    assert ft.evaluar(impacto(), lector([], {FIN.date()}), EVALUADO, CAJA) is None


def test_con_pocos_dias_de_base_queda_pendiente() -> None:
    faltan = {(INICIO - timedelta(days=n)).date() for n in range(0, 12)}
    assert ft.evaluar(impacto(), lector([], faltan), EVALUADO, CAJA) is None


# --- Confianza ------------------------------------------------------------------------------


def test_baja_confianza_viirs_y_modis_no_cuenta() -> None:
    focos = [foco(FIN, confianza="l"), foco(FIN, confianza="29", instrumento="MODIS")]
    documento = evaluar(focos)
    assert documento["resultado"] == "no_detectado"
    assert documento["motivo"] == "solo_baja_confianza"
    assert documento["focos_en_ventana"] == 2


def test_modis_desde_30_cuenta() -> None:
    documento = evaluar([*pixeles(FIN, confianza="30", instrumento="MODIS")])
    assert documento["resultado"] == "detectado"
    assert (documento["satelite"], documento["instrumento"]) == ("Aqua", "MODIS")


# --- Línea base de las antorchas ------------------------------------------------------------


def antorcha(frp: float = 6.0, dias: int = 30, instrumento: str = "VIIRS") -> list[ft.Foco]:
    """La antorcha de la refinería, vista cada noche de la base."""
    return [
        foco(INICIO - timedelta(days=d), km_norte=0.3, frp=frp, instrumento=instrumento,
             confianza="n" if instrumento == "VIIRS" else "80")
        for d in range(1, dias + 1)
    ]  # fmt: skip


def test_la_antorcha_de_siempre_no_es_un_foco_detectado() -> None:
    documento = evaluar([*antorcha(), foco(FIN, km_norte=0.5, frp=9.0)])
    assert documento["resultado"] == "no_detectado"
    assert documento["motivo"] == "fuente_habitual"
    assert documento["linea_base"] == {"focos": 30, "dias": 30, "frp_max_mw": 6.0}


def test_la_antorcha_con_potencia_anomala_es_detectada() -> None:
    # Más de cuatro veces la mayor potencia de ese sitio en la base (6 MW).
    def resultado(frp: float) -> str:
        return str(evaluar([*antorcha(), *pixeles(FIN, km_norte=0.5, frp=frp)])["resultado"])

    assert resultado(24.5) == "detectado"
    assert resultado(23.9) == "no_detectado"


def test_un_foco_nuevo_junto_a_la_antorcha_es_detectado() -> None:
    # A 1,5 km de la antorcha (más que el píxel VIIRS y su error), con poca potencia.
    documento = evaluar([*antorcha(), *pixeles(FIN, km_norte=1.8, frp=4.0)])
    assert documento["resultado"] == "detectado"


def test_la_potencia_se_compara_con_el_mismo_instrumento() -> None:
    # La antorcha vista por MODIS da más potencia por píxel que por VIIRS: un foco VIIRS se
    # compara con la base VIIRS de ese sitio.
    base = [*antorcha(6.0), *antorcha(40.0, instrumento="MODIS")]
    assert evaluar([*base, *pixeles(FIN, km_norte=0.5, frp=30.0)])["resultado"] == "detectado"


def test_la_base_son_los_30_dias_anteriores() -> None:
    lejana = foco(INICIO - timedelta(days=31), km_norte=0.3, frp=6.0)
    assert evaluar([lejana, *pixeles(FIN, km_norte=0.3, frp=7.0)])["resultado"] == "detectado"


# --- Impactos de la base ------------------------------------------------------------------


def incidente_con_impacto(evidencia: list[str]) -> Documento:
    documento = ejemplos.incidente_minimo()
    documento["pruebas"] = {
        "dron_estatal": True, "entrada_exterior": True, "evidencia": evidencia,
    }  # fmt: skip
    return documento


def test_solo_los_incidentes_con_explosion_o_caida_son_impactos() -> None:
    assert ft.impacto_de_incidente(incidente_con_impacto(["rastreo"])) is None
    imp = ft.impacto_de_incidente(incidente_con_impacto(["caida"]))
    assert imp is not None
    # Solo inicio con precisión de hora: el fin es una hora después.
    assert imp.inicio == datetime(2025, 11, 4, 18, tzinfo=UTC)
    assert imp.fin == datetime(2025, 11, 4, 19, tzinfo=UTC)
    assert (imp.lat, imp.lon, imp.radio_km) == (50.9, 5.4, 10)
    retirado = incidente_con_impacto(["explosion"])
    retirado["retirado"] = {"fecha": instante("2025-11-05T10:00Z"), "motivo": "no lo era"}
    assert ft.impacto_de_incidente(retirado) is None


def test_un_incidente_sin_punto_es_impacto_sin_lugar() -> None:
    documento = incidente_con_impacto(["explosion"])
    documento["lugar"] = {"pais": "MD", "nivel": "region", "region": "Cahul"}
    documento["tiempo"] = {"inicio": instante("2025-11-04T00:00Z", "dia")}
    imp = ft.impacto_de_incidente(documento)
    assert imp is not None and imp.lat is None
    assert imp.fin == datetime(2025, 11, 5, tzinfo=UTC)


def test_las_regiones_con_impacto_de_un_ataque_ru_ua() -> None:
    ataque = ejemplos.ataque_completo()
    ataque["lugares_impacto"] = ["Харківська область", "Київ"]
    ataque["regiones"].append({"region": "UA-63"})
    ataque["regiones"] = [{"region": "UA-63"}, {"region": "UA-30"}, {"region": "UA-71"}]
    codigos = {"Харківська область": "UA-63", "Київ": "UA-30"}
    impactos = ft.impactos_de_ataque(ataque, codigos)
    assert [i.id for i in impactos] == ["EODI-UA-2025-0001/UA-30", "EODI-UA-2025-0001/UA-63"]
    assert all(i.lat is None for i in impactos)
    ataque["sentido"] = "UA_RU"
    assert ft.impactos_de_ataque(ataque, codigos) == []


# --- Base de datos ------------------------------------------------------------------------


def test_evaluar_todos_guarda_y_solo_anota_los_cambios() -> None:
    almacen = Almacen.abrir()
    focos = [*pixeles(FIN, km_norte=1.0)]
    resumen = ft.evaluar_todos(almacen, [impacto()], lector(focos), EVALUADO, CAJA)
    assert resumen.evaluados == 1 and resumen.resultados == {"detectado": 1}
    casado, _ = almacen.focos_casados("EODI-2025-00099")
    assert casado["distancia_km"] == 1.0 and casado["fuente"] == "VIIRS_NOAA20_SP"
    # Una hora después, con lo mismo: sin cambios y sin historial nuevo.
    resumen = ft.evaluar_todos(
        almacen, [impacto()], lector(focos), EVALUADO + timedelta(hours=1), CAJA
    )
    assert resumen.sin_cambios == 1
    historial = almacen.historial("EODI-2025-00099")
    assert [h["operacion"] for h in historial] == ["alta"]
    assert len(almacen.focos_casados("EODI-2025-00099")) == 2


def test_pasada_una_semana_del_cierre_no_se_vuelve_a_evaluar() -> None:
    almacen = Almacen.abrir()
    ft.evaluar_todos(almacen, [impacto()], lector([]), EVALUADO, CAJA)
    mas_tarde = FIN + timedelta(hours=36) + ft.REEVALUAR + timedelta(hours=1)
    resumen = ft.evaluar_todos(almacen, [impacto()], lector([foco(FIN)]), mas_tarde, CAJA)
    assert resumen.sin_cambios == 1
    assert almacen.focos_termicos()["EODI-2025-00099"]["resultado"] == "no_detectado"


def test_pendiente_no_se_guarda() -> None:
    almacen = Almacen.abrir()
    resumen = ft.evaluar_todos(almacen, [impacto()], lector([], {FIN.date()}), EVALUADO, CAJA)
    assert resumen.pendientes == 1 and almacen.focos_termicos() == {}


def test_una_evaluacion_invalida_no_se_guarda() -> None:
    almacen = Almacen.abrir()
    with pytest.raises(DocumentoInvalido):
        almacen.guardar_foco_termico("X", {"resultado": "quizas"})


# --- Publicación ----------------------------------------------------------------------------

VISIBILIDAD_INCIDENTE = rutas_por_visibilidad(Esquema.INCIDENTE)
VISIBILIDAD_ATAQUE = rutas_por_visibilidad(Esquema.ATAQUE_UCRANIA)
PUBLICOS = {
    "resultado", "primer_foco", "satelite", "instrumento", "distancia_km", "numero_focos",
}  # fmt: skip


def no_detectado() -> Documento:
    return {
        "resultado": "no_detectado",
        "motivo": "fuente_habitual",
        "radio_km": 2,
        "focos_en_ventana": 3,
        "linea_base": {"focos": 30, "dias": 30, "frp_max_mw": 6.0},
        "evaluado": instante("2025-10-04T00:17Z"),
    }


def test_el_foco_detectado_sale_solo_con_sus_campos_publicos() -> None:
    (feature, _) = exportar(
        [ejemplos.incidente_completo(), ejemplos.incidente_minimo()], AHORA, VOCABULARIO_MODELOS
    )["features"]
    publicado = feature["properties"]["foco_termico"]
    assert set(publicado) == PUBLICOS
    assert publicado["primer_foco"] == instante("2025-10-01T23:42Z")


@pytest.mark.parametrize("resultado", ["no_detectado", "no_evaluable"])
def test_lo_que_no_es_detectado_no_sale(resultado: str) -> None:
    incidente = ejemplos.incidente_completo()
    incidente["foco_termico"] = {**no_detectado(), "resultado": resultado}
    ataque = ejemplos.ataque_completo()
    ataque["regiones"][0]["foco_termico"] = {**no_detectado(), "resultado": resultado}
    (feature,) = exportar([incidente], AHORA, VOCABULARIO_MODELOS)["features"]
    assert "foco_termico" not in feature["properties"]
    (publicado,) = exportar_ucrania([ataque], AHORA)["ataques"]
    assert all("foco_termico" not in r for r in publicado["regiones"])


def test_el_foco_de_una_region_sale_en_ucrania_json() -> None:
    (ataque,) = exportar_ucrania([ejemplos.ataque_completo()], AHORA)["ataques"]
    assert set(ataque["regiones"][0]["foco_termico"]) == PUBLICOS


def test_la_lista_cerrada_tiene_los_campos_publicos_del_foco_y_ninguno_interno() -> None:
    for campos, prefijo, visibilidad in (
        (CAMPOS_PUBLICOS_INCIDENTE, "foco_termico", VISIBILIDAD_INCIDENTE),
        (CAMPOS_PUBLICOS_ATAQUE, "regiones[].foco_termico", VISIBILIDAD_ATAQUE),
    ):
        del_foco = {c for c in campos if c.startswith(prefijo + ".")}
        assert {c.removeprefix(prefijo + ".").split(".")[0] for c in del_foco} == PUBLICOS
        internos = {r for r in visibilidad[Visibilidad.INTERNO] if r.startswith(prefijo + ".")}
        assert {r.removeprefix(prefijo + ".").split(".")[0] for r in internos} == {
            "motivo", "frp_max_mw", "radio_km", "ventana", "focos_en_ventana", "linea_base",
            "fuentes_firms", "evaluado",
        }  # fmt: skip
        assert del_foco.isdisjoint(internos)


def test_un_campo_interno_del_foco_colado_no_sale() -> None:
    incidente = ejemplos.incidente_completo()
    incidente["foco_termico"]["frp_max_mw"] = 999.0
    coleccion = exportar([incidente], AHORA, VOCABULARIO_MODELOS)
    publicadas = {r for f in coleccion["features"] for r in rutas(f["properties"])}
    assert "foco_termico.frp_max_mw" not in publicadas
    assert publicadas <= CAMPOS_PUBLICOS_INCIDENTE


def test_con_focos_pone_cada_evaluacion_en_su_impacto_sin_tocar_la_base() -> None:
    incidente = ejemplos.incidente_minimo()
    ataque = ejemplos.ataque_completo()
    ataque["regiones"] = [{"region": "UA-63"}, {"region": "UA-71"}]
    original = copy.deepcopy(ataque)
    focos = {
        incidente["id"]: ejemplos.foco_termico(),
        f"{ataque['id']}/UA-71": no_detectado(),
    }
    (con_incidente,), (con_ataque,) = ft.con_focos([incidente], [ataque], focos)
    assert con_incidente["foco_termico"] == ejemplos.foco_termico()
    assert "foco_termico" not in con_ataque["regiones"][0]
    assert con_ataque["regiones"][1]["foco_termico"] == no_detectado()
    assert ataque == original and "foco_termico" not in incidente


def test_sin_tiempo_los_impactos_quedan_pendientes_para_la_hora_siguiente() -> None:
    almacen = Almacen.abrir()
    resumen = ft.evaluar_todos(almacen, [impacto()], lector([foco(FIN)]), EVALUADO, CAJA, Plazo(0))
    assert resumen.pendientes == 1 and almacen.focos_termicos() == {}


def test_mientras_llega_el_historico_se_reevalua_todo() -> None:
    almacen = Almacen.abrir()
    ft.evaluar_todos(almacen, [impacto()], lector([]), EVALUADO, CAJA)
    mas_tarde = FIN + timedelta(hours=36) + ft.REEVALUAR + timedelta(hours=1)
    focos = lector(pixeles(FIN))
    resumen = ft.evaluar_todos(almacen, [impacto()], focos, mas_tarde, CAJA, reevaluar_todo=True)
    assert resumen.evaluados == 1
    assert almacen.focos_termicos()["EODI-2025-00099"]["resultado"] == "detectado"


def test_la_ventana_de_un_impacto_reciente_puede_acabar_en_el_futuro() -> None:
    """Caso del 1 de octubre de 2026: un incidente del día anterior tenía la ventana abierta
    y la exportación lo rechazaba por fecha futura, y la recogida no publicaba."""
    incidente = ejemplos.incidente_completo()
    incidente["foco_termico"] = {
        **no_detectado(),
        "ventana": {
            "inicio": instante("2025-10-01T20:30Z"),
            "fin": instante(f"{AHORA + timedelta(hours=30):%Y-%m-%dT%H:%MZ}"),
        },
    }
    exportar([incidente], AHORA, VOCABULARIO_MODELOS)
    ataque = ejemplos.ataque_completo()
    ataque["regiones"][0]["foco_termico"]["ventana"]["fin"] = instante(
        f"{AHORA + timedelta(hours=30):%Y-%m-%dT%H:%MZ}"
    )
    exportar_ucrania([ataque], AHORA)
    # Cualquier otra fecha futura sigue siendo un error.
    incidente["foco_termico"]["evaluado"] = instante(
        f"{AHORA + timedelta(hours=1):%Y-%m-%dT%H:%MZ}"
    )
    with pytest.raises(ExportacionInvalida):
        exportar([incidente], AHORA, VOCABULARIO_MODELOS)


# --- Línea base del emplazamiento (antorchas estacionales, caso de Kirishi) -------------------


def _antorcha_del_ano(frp: float = 0.8) -> list[ft.Foco]:
    """La antorcha, 1,5 km al norte, vista en 6 noches de hace 3 a 8 meses y no en los 30
    días anteriores."""
    return [
        foco(INICIO - timedelta(days=dias), 1.5, frp=frp) for dias in (90, 100, 120, 150, 200, 240)
    ]


def test_antorcha_que_no_estaba_en_los_30_dias_no_es_un_impacto() -> None:
    # Dos pasos ven la antorcha con poca potencia: con la base de 30 días saldría detectado.
    ventana = [foco(INICIO + timedelta(hours=3), 1.5, frp=2.9),
               foco(INICIO + timedelta(hours=5), 1.5, frp=3.0)]  # fmt: skip
    documento = evaluar(_antorcha_del_ano() + ventana)
    assert documento["resultado"] == ft.NO_DETECTADO
    assert documento["motivo"] == ft.FUENTE_HABITUAL
    assert documento["linea_base"]["emplazamiento"] == {"focos": 6, "descartados": 2}


def test_antorcha_con_potencia_anomala_si_cuenta() -> None:
    ventana = [foco(INICIO + timedelta(hours=3), 1.5, frp=12.0),
               foco(INICIO + timedelta(hours=5), 1.5, frp=15.0)]  # fmt: skip
    assert evaluar(_antorcha_del_ano() + ventana)["resultado"] == ft.DETECTADO


def test_un_paso_con_tres_focos_es_un_incendio_aunque_el_sitio_ardiera_antes() -> None:
    # Un ataque anterior dejó potencias altas en el sitio: el percentil del año no sirve.
    incendio = [foco(INICIO + timedelta(hours=3), 1.5 + 0.1 * i, frp=3.0) for i in range(3)]
    assert evaluar(_antorcha_del_ano(frp=40.0) + incendio)["resultado"] == ft.DETECTADO


def test_lugar_sin_calor_en_el_ano_no_cambia() -> None:
    documento = evaluar(pixeles(INICIO + timedelta(hours=3)))
    assert documento["resultado"] == ft.DETECTADO
    assert "emplazamiento" not in documento["linea_base"]


def test_la_base_de_30_dias_toca_31_fechas_y_el_documento_vale() -> None:
    # La base empieza a la hora del inicio de hace 30 días: con fuego cada día (una antorcha)
    # hay focos en 31 fechas distintas. Así falló el cruce del 1 de octubre de 2026.
    madrugada = foco(INICIO - timedelta(hours=12), km_norte=0.3, frp=6.0)
    documento = evaluar([*antorcha(), madrugada])
    assert documento["linea_base"]["dias"] == 31
    Almacen.abrir().guardar_foco_termico("EODI-2025-00099", documento)
