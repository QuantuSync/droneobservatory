"""Previsión y tendencias (proceso/prevision): la comprobación con el pasado sobre una copia
fija de los datos publicados, el esquema del fichero publicado y el registro inmutable."""

import json
import sqlite3
from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from almacen.base import Almacen
from esquema import Documento
from proceso import prevision
from proceso.prevision import datos as datos_prevision
from proceso.prevision import frontera, metodos, segunda_noche, semanal
from recogida import prevision as paso

RAIZ = Path(__file__).resolve().parent.parent
FIJOS = RAIZ / "tests" / "fixtures" / "prevision" / "datos.json.gz"
ESQUEMA = RAIZ / "esquema" / "prevision" / "1.0.0" / "prevision.schema.json"
# Los datos fijos son los publicados el 6 de octubre de 2026; se calcula a las 17:30 UTC.
AHORA = datetime(2026, 10, 6, 17, 30, tzinfo=UTC)
Calculado = tuple[Documento, list[Documento]]


@pytest.fixture(scope="module")
def datos() -> datos_prevision.Datos:
    return datos_prevision.leer_compactos(FIJOS)


@pytest.fixture(scope="module")
def calculado(datos: datos_prevision.Datos) -> Calculado:
    return prevision.calcular(datos, AHORA, [])


def validador() -> Draft202012Validator:
    return Draft202012Validator(json.loads(ESQUEMA.read_text(encoding="utf-8")))


# --- La comprobación con el pasado: lo que se publica mejora a su referencia --------------


def test_frontera_de_rumania_y_moldavia_mejora_a_sus_referencias(
    datos: datos_prevision.Datos,
) -> None:
    resultado = frontera.calcular(datos, date(2026, 10, 7), date(2026, 10, 3))
    for pais in ("RO", "MD"):
        comprobacion = resultado[pais]["comprobacion"]
        assert comprobacion["publicable"], comprobacion
        assert comprobacion["mejora_sobre_frecuencia"] >= frontera.MEJORA_MINIMA
        assert comprobacion["mejora_sobre_persistencia"] >= frontera.MEJORA_MINIMA
        assert comprobacion["mejora_cota"] > 0
        assert comprobacion["noches_con_dron"] >= frontera.NOCHES_CON_SUCESO_MINIMAS
        assert "probabilidad" in resultado[pais]


def test_frontera_no_publica_lo_que_no_mejora(datos: datos_prevision.Datos) -> None:
    """Polonia, Lituania y Letonia no mejoran a la frecuencia de siempre: no salen."""
    resultado = frontera.calcular(datos, date(2026, 10, 7), date(2026, 10, 3), ("PL", "LT", "LV"))
    for pais, documento in resultado.items():
        assert not documento["comprobacion"]["publicable"], pais
        assert "probabilidad" not in documento


def test_semana_publicada_mejora_a_sus_referencias(calculado: Calculado) -> None:
    documento, _ = calculado
    paises = {p["pais"]: p for p in documento["semana"]["paises"]}
    assert {"RO", "MD"} <= set(paises)
    for p in paises.values():
        c = p["comprobacion"]
        assert c["mejora_sobre_frecuencia"] >= semanal.MEJORA_MINIMA
        assert c["mejora_sobre_persistencia"] >= semanal.MEJORA_MINIMA
        assert c["mejora_cota"] > 0
        assert p["minimo"] <= p["esperado"] <= p["maximo"]


def test_rachas_comprobadas(calculado: Calculado) -> None:
    documento, _ = calculado
    rachas = documento["rachas"]
    assert rachas["comprobacion"]["publicable"]
    assert rachas["comprobacion"]["mejora_cota"] > 0
    # Tras marcar una racha, la semana siguiente trae más que lo normal.
    c = rachas["comprobacion"]
    assert c["incidentes_semana_siguiente"] > c["normal_semana_siguiente"]
    for racha in rachas["activas"]:
        assert racha["incidentes"] > racha["habitual"]
        assert racha["pais"] in rachas["graficas"]


def test_segunda_noche_no_se_publica_si_no_mejora(
    datos: datos_prevision.Datos, calculado: Calculado
) -> None:
    resultado = segunda_noche.calcular(datos, date(2026, 10, 5))
    documento, _ = calculado
    assert resultado["comprobacion"]["publicable"] is False
    assert "segunda_noche" not in documento


def test_ninguna_comprobacion_usa_datos_futuros(datos: datos_prevision.Datos) -> None:
    """Ajustar con noches hasta una fecha no cambia si se añaden noches posteriores."""
    s = frontera.serie(datos, "RO")
    antes = frontera.ajustar(s, date(2026, 3, 1))
    recortados = datos_prevision.Datos(
        tuple(i for i in datos.incidentes if i.noche <= date(2026, 3, 1)),
        {f: n for f, n in datos.noches.items() if f <= date(2026, 3, 1)},
        date(2026, 3, 1),
        datos.cajas,
    )
    despues = frontera.ajustar(frontera.serie(recortados, "RO"), date(2026, 3, 1))
    assert antes.pesos == pytest.approx(despues.pesos)


# --- El fichero publicado ---------------------------------------------------------------


def test_documento_cumple_su_esquema(calculado: Calculado) -> None:
    documento, _ = calculado
    errores = [e.message for e in validador().iter_errors(documento)]
    assert errores == []


def test_probabilidades_en_lenguaje_llano(calculado: Calculado) -> None:
    documento, _ = calculado
    for p in documento["frontera"]["paises"]:
        assert p["de_cada_10"] == round(p["probabilidad"] * 10)


def test_registra_la_noche_desde_las_17_y_la_semana_el_sabado(datos: datos_prevision.Datos) -> None:
    _, nuevas = prevision.calcular(datos, datetime(2026, 10, 6, 9, 17, tzinfo=UTC), [])
    assert nuevas == []
    _, nuevas = prevision.calcular(datos, AHORA, [])
    assert {e["id"] for e in nuevas} == {"frontera:RO:2026-10-07", "frontera:MD:2026-10-07"}
    sabado = datos_prevision.Datos(datos.incidentes, datos.noches, date(2026, 10, 10), datos.cajas)
    _, nuevas = prevision.calcular(sabado, datetime(2026, 10, 10, 0, 17, tzinfo=UTC), [])
    assert {e["id"] for e in nuevas if e["tipo"] == "semana"} == {
        "semana:MD:2026-10-12", "semana:RO:2026-10-12"
    }  # fmt: skip


# --- Una previsión ya publicada no cambia ------------------------------------------------


def test_previsión_registrada_no_cambia_en_el_documento(datos: datos_prevision.Datos) -> None:
    anterior = {
        "id": "frontera:RO:2026-10-07", "tipo": "frontera", "pais": "RO",
        "objetivo": "2026-10-07", "emitida": "2026-10-06T17:17Z", "probabilidad": 0.01,
        "metodo": "frontera-1.0.0",
    }  # fmt: skip
    documento, nuevas = prevision.calcular(datos, AHORA, [anterior])
    assert "frontera:RO:2026-10-07" not in {e["id"] for e in nuevas}
    registrada = next(e for e in documento["registro"] if e["id"] == anterior["id"])
    assert registrada == anterior


def test_la_tabla_no_admite_cambios_ni_borrados() -> None:
    almacen = Almacen.abrir()
    entrada = {
        "id": "frontera:MD:2026-10-07", "tipo": "frontera", "pais": "MD",
        "objetivo": "2026-10-07", "emitida": "2026-10-06T17:17Z", "probabilidad": 0.2,
        "metodo": "frontera-1.0.0",
    }  # fmt: skip
    assert almacen.registrar_previsiones([entrada]) == 1
    # Registrar otra vez el mismo id con otro valor no cambia nada.
    assert almacen.registrar_previsiones([{**entrada, "probabilidad": 0.9}]) == 0
    assert almacen.previsiones() == [entrada]
    with pytest.raises(sqlite3.IntegrityError, match="no cambia"):
        almacen.conexion.execute("UPDATE previsiones SET emitida = 'x'")
    with pytest.raises(sqlite3.IntegrityError, match="nada se borra"):
        almacen.conexion.execute("DELETE FROM previsiones")


def test_puntua_sin_tocar_la_prevision(datos: datos_prevision.Datos) -> None:
    entrada = {
        "id": "semana:RO:2026-09-14", "tipo": "semana", "pais": "RO", "objetivo": "2026-09-14",
        "emitida": "2026-09-12T00:17Z", "esperado": 3.0, "minimo": 0, "maximo": 8,
        "metodo": "semana-1.0.0",
    }  # fmt: skip
    puntuada = prevision.puntuar(entrada, datos)
    assert {k: puntuada[k] for k in entrada} == entrada
    assert puntuada["real"] == semanal.incidentes_de_semana(
        datos.incidentes, "RO", date(2026, 9, 14)
    )


# --- El paso de la recogida -------------------------------------------------------------


def test_paso_horario_escribe_y_registra(tmp_path: Path, datos: datos_prevision.Datos) -> None:
    for nombre in ("incidentes.geojson", "incidentes_sin_ubicacion.json", "ucrania.json"):
        (tmp_path / nombre).write_text(
            (RAIZ / "tests" / "fixtures" / "publicacion" / nombre).read_text(encoding="utf-8"),
            encoding="utf-8",
        )
    almacen = Almacen.abrir()
    assert paso.calcular(almacen, AHORA, tmp_path)
    documento = json.loads((tmp_path / paso.FICHERO).read_text(encoding="utf-8"))
    assert [e.message for e in validador().iter_errors(documento)] == []
    assert {e["id"] for e in almacen.previsiones()} == {e["id"] for e in documento["registro"]}


def test_un_fallo_deja_la_prevision_anterior(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    (tmp_path / paso.FICHERO).write_text('{"anterior": true}\n', encoding="utf-8")
    (tmp_path / "ucrania.json").write_text("no es json", encoding="utf-8")
    paso.paso_horario(Almacen.abrir(), AHORA, tmp_path)
    assert "previsión sin calcular" in caplog.text
    assert (tmp_path / paso.FICHERO).read_text(encoding="utf-8") == '{"anterior": true}\n'


# --- Métodos -----------------------------------------------------------------------------


def test_area_bajo_curva_con_empates() -> None:
    assert metodos.area_bajo_curva([0.1, 0.2, 0.3, 0.4], [0, 0, 1, 1]) == 1.0
    assert metodos.area_bajo_curva([0.5, 0.5], [0, 1]) == 0.5


def test_margen_binomial_negativa() -> None:
    media, minimo, maximo, _ = semanal.prevision([0, 1, 0, 2, 5, 3, 0, 1])
    assert minimo <= media <= maximo


def test_remuestreo_determinista() -> None:
    a = metodos.mejora_remuestreada([0.1, -0.05, 0.2, 0.0], [1, 1, 2, 3])
    b = metodos.mejora_remuestreada([0.1, -0.05, 0.2, 0.0], [1, 1, 2, 3])
    assert a == b


# --- Qué ha cambiado ------------------------------------------------------------------------


def test_cambios_comprobados_y_solo_lo_que_cambia(calculado: Calculado) -> None:
    documento, _ = calculado
    cambios = documento["cambios"]
    ambitos = {a["ambito"]: a for a in cambios["ambitos"]}
    assert set(ambitos) <= {"ucrania_objetivo", "europa_tipo"}
    for ambito in ambitos.values():
        c = ambito["comprobacion"]
        assert c["publicable"] and c["casos"] >= 10 and c["mejora_cota"] > 0
        for cambio in ambito["cambios"]:
            assert abs(cambio["reciente"] - cambio["habitual"]) >= 0.02
            assert (cambio["reciente"] > cambio["habitual"]) == (cambio["sentido"] == "sube")


def test_cambios_solo_con_canales_de_cobertura_constante(datos: datos_prevision.Datos) -> None:
    from proceso.prevision import cambios

    estables = cambios.canales_estables(datos)
    # Mykolaiv empieza en julio de 2026: un canal así no entra en la mezcla.
    assert "mykolaiv_ova" not in estables
    assert "odeskaODA" in estables
