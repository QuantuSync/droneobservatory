"""Motor de deducción: catálogo, envolventes, reglas, combinación, zona de despegue, deriva,
horizonte de radar, incrementalidad, relieve, esquema y validación. Sin red."""

import json
import math
import re
import struct
import zlib
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from almacen.base import Almacen, DocumentoInvalido
from esquema import validador_definicion
from proceso.deduccion import (
    capacidades,
    catalogo,
    deriva,
    geo,
    horizonte,
    motor,
    reglas,
    validacion,
    zona_despegue,
)
from proceso.deduccion.catalogo import Catalogo
from proceso.deduccion.reglas import Caso, Origen, Sitio
from recogida import deduccion, dem, estado
from tests import ejemplos

AHORA = datetime(2026, 10, 2, 9, 0, tzinfo=UTC)

# --- Catálogo de prueba -----------------------------------------------------------------


def _campos_vacios() -> dict[str, Any]:
    real = json.loads(catalogo.CATALOGO.read_text(encoding="utf-8"))
    return {c: {"datos": [], "sin_fuente": True} for c in real["campos"]}


def _dato(valor: Any, unidad: str, fuente: str = "X1", **extra: Any) -> dict[str, Any]:
    if isinstance(valor, tuple):
        dato: dict[str, Any] = {"unidad": unidad, "fuente": fuente, "cita": "cita"}
        if valor[0] is not None:
            dato["min"] = valor[0]
        if valor[1] is not None:
            dato["max"] = valor[1]
    else:
        dato = {"valor": valor, "unidad": unidad, "fuente": fuente, "cita": "cita"}
    return {**dato, **extra}


def modelo(id_: str, clase: str, tipo: Any = "multirrotor", **campos: Any) -> dict[str, Any]:
    vacios = _campos_vacios()
    for campo, datos in campos.items():
        lista = datos if isinstance(datos, list) else [datos]
        vacios[campo] = {"datos": lista, "sin_fuente": False}
    return {
        "id": id_,
        "nombre": id_.upper(),
        "otros_nombres": [],
        "pais": "X",
        "fabricante": "X",
        "tipo_aeronave": tipo,
        "clase": clase,
        "campos": vacios,
    }


def clase(id_: str, tipo: str, propulsion: str, tamano: str, corto: bool) -> dict[str, Any]:
    return {
        "id": id_,
        "nombre": id_,
        "descripcion": id_,
        "tipo_aeronave": tipo,
        "propulsion": propulsion,
        "tamano": tamano,
        "corto_alcance": corto,
        "clase_esquema": None,
        "aegis": [],
        "equivalencia_aegis": "sin_equivalente",
    }


def fuentes(**prioridades: str) -> dict[str, Any]:
    lista = {"X1": "normal", "X2": "normal", **prioridades}
    return {
        "version": "1.0.0",
        "version_esquema": "1.0.0",
        "descripcion": "prueba",
        "fuentes": {
            i: {
                "titulo": i,
                "url": f"https://ejemplo.org/{i}",
                "fecha": None,
                "consultada": "2026-10-02",
                "tipo": "fabricante",
                "prioridad": p,
            }
            for i, p in lista.items()
        },
    }


def zonas() -> dict[str, Any]:
    return {
        "version": "1.0.0",
        "version_esquema": "1.0.0",
        "descripcion": "prueba",
        "zonas": [
            {
                "id": "base_a",
                "nombre": "Base A",
                "raices": ["база"],
                "tipo": "aerodromo",
                "punto": {"lat": 50.0, "lon": 40.0, "fuente": "X1", "cita": "50, 40"},
                "uso": [{"fuente": "X1", "cita": "lanzamientos"}],
            },
            {
                "id": "zona_b",
                "nombre": "Zona B",
                "raices": ["зона"],
                "tipo": "zona",
                "punto": None,
                "uso": [],
            },
        ],
    }


def pequeno(**extra: Any) -> dict[str, Any]:
    campos = {
        "alcance": _dato(20, "km"),
        "autonomia": _dato(30, "min"),
        "velocidad_maxima": _dato(15, "m/s"),
        "viento_maximo": _dato(10, "m/s"),
        "temperatura": _dato((-10, 40), "°C"),
        "enlace_alcance": _dato(10, "km"),
        "techo": _dato(120, "m"),
        "navegacion": {"texto": "GNSS", "fuente": "X1", "cita": "GNSS"},
        "luces": {"texto": "luces delanteras", "fuente": "X1", "cita": "luces"},
    }
    campos.update(extra)
    return modelo("mini", "pequeno", **campos)


def largo(**extra: Any) -> dict[str, Any]:
    campos = {
        "alcance": _dato(2000, "km"),
        "velocidad_crucero": _dato((40, 50), "m/s"),
        "velocidad_maxima": _dato(50, "m/s"),
        "altura_tipica": _dato((100, 3000), "m"),
        "navegacion": {"texto": "antena CRPA", "fuente": "X1", "cita": "CRPA"},
    }
    campos.update(extra)
    return modelo("ataque", "largo", "ala_fija", **campos)


def construir(*modelos: dict[str, Any], prioridades: dict[str, str] | None = None) -> Catalogo:
    real = json.loads(catalogo.CATALOGO.read_text(encoding="utf-8"))
    clases_usadas = {m["clase"] for m in modelos}
    todas = [
        clase("pequeno", "multirrotor", "electrica", "pequeno", True),
        clase("grande", "multirrotor", "electrica", "grande", True),
        clase("largo", "ala_fija", "combustion", "grande", False),
    ]
    documento = {
        "version": "9.9.9",
        "version_esquema": "1.0.0",
        "descripcion": "prueba",
        "campos": real["campos"],
        "clases": [c for c in todas if c["id"] in clases_usadas],
        "modelos": list(modelos),
    }
    return catalogo.construir(documento, fuentes(**(prioridades or {})), zonas())


def condiciones(
    viento_10m: float, viento_100m: float | None = None, temperatura: float = 15.0, **niveles: float
) -> dict[str, Any]:
    superficie = {
        "viento_10m_ms": viento_10m,
        "direccion_10m": 270.0,
        "viento_100m_ms": viento_100m if viento_100m is not None else viento_10m,
        "direccion_100m": 270.0,
        "temperatura_c": temperatura,
        "precipitacion_mm": 0.0,
    }
    return {
        "lugar": {
            "lat": 55.6,
            "lon": 12.6,
            "momento": {"precision": "hora", "valor": "2025-09-22T18:00Z"},
            "superficie": superficie,
            "niveles": {k: {"viento_ms": v, "direccion": 270.0} for k, v in niveles.items()},
        }
    }


def efectos(evidencias: list[reglas.Evidencia], nombre: str) -> dict[str, str]:
    return {e.clase: e.efecto for e in evidencias if e.clase == nombre}


# --- Catálogo real ---------------------------------------------------------------------


@pytest.fixture(scope="module")
def real() -> Catalogo:
    return catalogo.cargar()


def _datos(real_json: dict[str, Any]) -> Iterator[tuple[str, str, dict[str, Any]]]:
    for m in real_json["modelos"]:
        for campo, contenido in m.get("campos", {}).items():
            for dato in contenido["datos"]:
                yield m["id"], campo, dato


def test_el_catalogo_real_valida_y_tiene_clases_y_zonas(real: Catalogo) -> None:
    assert len(real.modelos) >= 40
    assert len(real.clases) >= 10
    assert all(c.modelos for c in real.clases.values())
    assert any(z.lat is not None for z in real.zonas)


def test_ninguna_cifra_sin_fuente_ni_cita() -> None:
    documento = json.loads(catalogo.CATALOGO.read_text(encoding="utf-8"))
    lista = json.loads(catalogo.FUENTES.read_text(encoding="utf-8"))["fuentes"]
    for id_, campo, dato in _datos(documento):
        assert dato["fuente"] in lista, (id_, campo)
        assert dato.get("cita"), (id_, campo)
    for m in documento["modelos"]:
        for campo, contenido in m.get("campos", {}).items():
            # Vacío solo si está marcado sin fuente; nunca un valor de relleno.
            assert contenido["sin_fuente"] == (not contenido["datos"]), (m["id"], campo)


def test_rangos_coherentes(real: Catalogo) -> None:
    for m in real.modelos.values():
        for campo, v in m.numeros.items():
            if v.minimo is not None and v.maximo is not None:
                assert v.minimo <= v.maximo, (m.id, campo)
            if campo != "temperatura" and v.minimo is not None:
                assert v.minimo >= 0, (m.id, campo)


def test_las_fuentes_de_prioridad_baja_solo_dan_estimaciones_debiles(real: Catalogo) -> None:
    debiles = {i for i, f in real.fuentes.items() if f["prioridad"] == "baja"}
    assert "P2" in debiles
    for m in real.modelos.values():
        for campo, v in m.numeros.items():
            if v.fuentes and set(v.fuentes) <= debiles:
                assert v.debil, (m.id, campo)
    # Y una cota débil no sirve para descartar.
    parodiya = real.modelos["parodiya"]
    assert parodiya.valor("velocidad_maxima").debil
    assert capacidades.de_clase(
        real, "senuelo_largo_alcance", capacidades.velocidad_max_ms
    ).sin_dato == ("parodiya",)


def test_las_referencias_genericas_son_derivadas(real: Catalogo) -> None:
    for id_ in ("ref_multirrotor_pesado_carga", "ref_ala_fija_reconocimiento_mediana"):
        modelo_ = real.modelos[id_]
        assert modelo_.derivado_de
        assert all(v.derivado for v in modelo_.numeros.values() if not v.vacio)


def test_las_clases_casan_con_el_esquema_y_con_el_vocabulario_de_aegis(real: Catalogo) -> None:
    vocabulario = json.loads(
        (catalogo.CONFIGURACION / "vocabulario_aegis.json").read_text(encoding="utf-8")
    )
    esquema_clases = {"multirrotor_pequeno", "ala_fija", "ataque_largo_alcance", None}
    assert set(vocabulario["clases_deduccion"]) == set(real.clases)
    for c in real.clases.values():
        assert c.clase_esquema in esquema_clases
        entrada = vocabulario["clases_deduccion"][c.id]
        assert entrada["aegis"] == list(c.aegis)
        assert entrada["clase_esquema"] == c.clase_esquema
        assert set(c.aegis) <= set(vocabulario["aegis"]["clases_dron"]["valores"])


def test_primorsko_ajtarsk_no_lleva_la_coordenada_de_yeysk(real: Catalogo) -> None:
    zonas_ = {z.id: z for z in real.zonas}
    base = zonas_["primorsko_akhtarsk_aerodromo"]
    assert base.lat is not None and 46.0 < base.lat < 46.1
    yeysk = zonas_["yeysk"]
    assert yeysk.lat is not None and abs(yeysk.lat - 46.676) < 0.01
    assert [z.id for z in real.zonas_de("Приморсько-Ахтарськ")][:1] == [
        "primorsko_akhtarsk_aerodromo"
    ]


def test_una_cifra_sin_fuente_conocida_no_se_admite() -> None:
    con_fuente_rara = pequeno(alcance=_dato(20, "km", fuente="Z9"))
    with pytest.raises(catalogo.CatalogoInvalido, match="fuente desconocida"):
        construir(con_fuente_rara)


def test_un_modelo_sin_todos_sus_campos_no_se_admite() -> None:
    incompleto = pequeno()
    del incompleto["campos"]["rcs"]
    with pytest.raises(catalogo.CatalogoInvalido, match="faltan campos"):
        construir(incompleto)


def test_unidades_que_se_convierten_sin_redondear() -> None:
    cat = construir(
        pequeno(velocidad_maxima=_dato(54, "km/h"), alcance=_dato(500, "m"), mtow=_dato(249, "g"))
    )
    m = cat.modelos["mini"]
    assert m.valor("velocidad_maxima").maximo == pytest.approx(15.0)
    assert m.valor("alcance").maximo == pytest.approx(0.5)
    assert m.valor("mtow").maximo == pytest.approx(0.249)


# --- Envolventes ---------------------------------------------------------------------


def test_envolvente_minimo_de_minimos_y_maximo_de_maximos() -> None:
    otro = modelo(
        "otro",
        "pequeno",
        alcance=_dato(35, "km"),
        autonomia=[_dato(20, "min"), _dato(40, "min", fuente="X2")],
    )
    cat = construir(pequeno(), otro)
    assert (
        cat.envolvente("pequeno", "alcance").minimo,
        cat.envolvente("pequeno", "alcance").maximo,
    ) == (20, 35)
    autonomia = cat.envolvente("pequeno", "autonomia")
    assert (autonomia.minimo, autonomia.maximo) == (20, 40)
    assert autonomia.fuentes == ("X1", "X2")


def test_una_cota_abierta_deja_la_clase_sin_ese_extremo() -> None:
    abierto = modelo("abierto", "pequeno", alcance=_dato((75, None), "km"))
    cat = construir(pequeno(), abierto)
    envolvente = cat.envolvente("pequeno", "alcance")
    assert envolvente.minimo == 20 and envolvente.maximo is None
    # Para descartar no sirve; para decir que puede, sí (un modelo con dato llega).
    cota = capacidades.de_clase(cat, "pequeno", capacidades.alcance_aire_km)
    assert cota.valor == 20 and not cota.sirve


def test_el_alcance_se_deduce_de_la_autonomia_y_la_velocidad() -> None:
    sin_alcance = pequeno()
    sin_alcance["campos"]["alcance"] = {"datos": [], "sin_fuente": True}
    cat = construir(sin_alcance)
    cota = capacidades.alcance_aire_km(cat.modelos["mini"])
    assert cota.deducida and cota.valor == pytest.approx(30 * 60 * 15 / 1000)


def test_las_clases_reales_exportan_su_envolvente(real: Catalogo) -> None:
    datos = catalogo.clases_con_envolvente(real)
    assert {c["id"] for c in datos["clases"]} == set(real.clases)
    sub250 = next(c for c in datos["clases"] if c["id"] == "multirrotor_consumo_sub250")
    assert sub250["envolvente"]["viento_maximo"]["max"] == pytest.approx(10.7)
    assert sub250["envolvente"]["viento_maximo"]["unidad"] == "m/s"


# --- R1: distancia ------------------------------------------------------------------


def test_r1_guerra_descarta_lo_que_no_llega_y_admite_lo_que_si() -> None:
    cat = construir(pequeno(), largo())
    caso = Caso(id="i", tipo="impacto", lat=50.0, lon=36.0, condiciones=condiciones(5.0))
    caso.origenes = [Origen("base_a", 300.0)]
    resultado = reglas.r1_distancia_guerra(cat, caso)
    assert efectos(resultado, "pequeno") == {"pequeno": reglas.DESCARTA}
    assert efectos(resultado, "largo") == {"largo": reglas.COMPATIBLE}


def test_r1_guerra_sin_viento_no_descarta() -> None:
    cat = construir(pequeno())
    caso = Caso(id="i", tipo="impacto", lat=50.0, lon=36.0)
    caso.origenes = [Origen("base_a", 300.0)]
    assert reglas.r1_distancia_guerra(cat, caso) == []


def test_r1_guerra_el_viento_a_favor_alarga_el_alcance() -> None:
    cat = construir(pequeno())
    caso = Caso(id="i", tipo="impacto", lat=50.0, lon=36.0, condiciones=condiciones(10.0))
    # 20 km en calma + 10 m/s durante 30 min = 38 km; con el 10 % de margen, 41,8 km.
    caso.origenes = [Origen("base_a", 40.0)]
    assert efectos(reglas.r1_distancia_guerra(cat, caso), "pequeno") == {
        "pequeno": reglas.COMPATIBLE
    }
    caso.origenes = [Origen("base_a", 43.0)]
    assert efectos(reglas.r1_distancia_guerra(cat, caso), "pequeno") == {"pequeno": reglas.DESCARTA}


def test_r1_guerra_un_modelo_sin_dato_impide_el_descarte() -> None:
    sin_datos = modelo("misterio", "pequeno")
    cat = construir(pequeno(), sin_datos)
    caso = Caso(id="i", tipo="impacto", lat=50.0, lon=36.0, condiciones=condiciones(5.0))
    caso.origenes = [Origen("base_a", 300.0)]
    assert reglas.r1_distancia_guerra(cat, caso) == []


def test_r1_europa_sin_entrada_declarada_solo_condiciona(monkeypatch: pytest.MonkeyPatch) -> None:
    cat = construir(pequeno(), largo())
    monkeypatch.setattr(geo, "exterior", lambda *a: geo.Exterior(120.0, "SE", 100.0, 122.2))
    caso = Caso(
        id="i", tipo="incidente", pais="DK", lat=55.6, lon=12.6, condiciones=condiciones(3.0)
    )
    evidencias, conclusiones, _ = reglas.r1_distancia_europa(cat, caso)
    assert efectos(evidencias, "pequeno") == {"pequeno": reglas.CONDICION}
    assert efectos(evidencias, "largo") == {"largo": reglas.COMPATIBLE}
    assert conclusiones[0]["conclusion"] == "despegue_cercano_o_largo_alcance"


def test_r1_europa_con_entrada_confirmada_descarta(monkeypatch: pytest.MonkeyPatch) -> None:
    cat = construir(pequeno())
    monkeypatch.setattr(geo, "exterior", lambda *a: geo.Exterior(120.0, "BY", None, None))
    caso = Caso(
        id="i",
        tipo="incidente",
        pais="LT",
        lat=55.0,
        lon=24.0,
        condiciones=condiciones(3.0),
        entrada_exterior=True,
        entrada_confirmada=True,
    )
    evidencias, _, _ = reglas.r1_distancia_europa(cat, caso)
    assert efectos(evidencias, "pequeno") == {"pequeno": reglas.DESCARTA}


def test_r1_europa_cerca_de_la_frontera_es_compatible(monkeypatch: pytest.MonkeyPatch) -> None:
    cat = construir(pequeno())
    monkeypatch.setattr(geo, "exterior", lambda *a: geo.Exterior(2.0, "BY", None, None))
    caso = Caso(
        id="i", tipo="incidente", pais="LT", lat=55.0, lon=24.0, condiciones=condiciones(3.0)
    )
    evidencias, conclusiones, _ = reglas.r1_distancia_europa(cat, caso)
    assert efectos(evidencias, "pequeno") == {"pequeno": reglas.COMPATIBLE}
    assert conclusiones == []


def test_distancias_al_exterior_con_los_poligonos_reales() -> None:
    # Aeropuerto de Copenhague: Suecia al otro lado del Øresund, costa a pie de pista.
    medido = geo.exterior("DK", 55.6093, 12.6379)
    assert medido.pais_extranjero == "SE"
    assert medido.tierra_extranjera_km is not None and 10 < medido.tierra_extranjera_km < 25
    assert medido.costa_km is not None and medido.costa_km < 5
    # Kursk está fuera de Ucrania: cota inferior positiva de lo que vuela un dron ucraniano.
    assert 80 < geo.distancia_a_pais_km("UA", 51.73, 36.19) < 140


# --- R2: meteorología -----------------------------------------------------------------


def test_r2_viento_descarta_con_margen_y_no_sin_el() -> None:
    cat = construir(pequeno())
    # Límite 10 m/s: descarta si 10 m/s menos 2 de error pasan de 12,5.
    fuerte = Caso(id="i", tipo="incidente", condiciones=condiciones(15.0))
    justo = Caso(id="i", tipo="incidente", condiciones=condiciones(14.0))
    assert reglas.DESCARTA in {
        e.efecto for e in reglas.r2_meteorologia(cat, fuerte) if e.clase == "pequeno"
    }
    assert {e.efecto for e in reglas.r2_meteorologia(cat, justo) if e.clase == "pequeno"} == {
        reglas.COMPATIBLE
    }


def test_r2_sin_limite_de_viento_no_dice_nada_de_un_multirrotor() -> None:
    sin_limite = pequeno()
    sin_limite["campos"]["viento_maximo"] = {"datos": [], "sin_fuente": True}
    sin_limite["campos"]["temperatura"] = {"datos": [], "sin_fuente": True}
    cat = construir(sin_limite)
    assert (
        reglas.r2_meteorologia(cat, Caso(id="i", tipo="incidente", condiciones=condiciones(30.0)))
        == []
    )


def test_r2_ala_fija_sin_limite_usa_su_velocidad_frente_al_viento() -> None:
    cat = construir(largo())
    # Crucero máximo 50 m/s: hace falta más de 64,5 m/s en su banda (100-3000 m).
    # El viento flojo de 10 m no cuenta: la banda empieza a 100 m.
    fuerte = condiciones(5.0, 70.0, **{"925": 70.0, "850": 70.0, "700": 70.0})
    caso = Caso(id="i", tipo="incidente", condiciones=fuerte)
    caso.duracion_min = 30
    evidencia = [e for e in reglas.r2_meteorologia(cat, caso) if e.clase == "largo"]
    assert evidencia[0].efecto == reglas.DESCARTA
    assert evidencia[0].datos["limite_deducido"] is True
    caso.duracion_min = None
    sin_permanencia = next(e for e in reglas.r2_meteorologia(cat, caso) if e.clase == "largo")
    assert sin_permanencia.efecto == reglas.CONDICION


def test_r2_temperatura_fuera_del_intervalo_con_margen() -> None:
    cat = construir(pequeno())
    helado = Caso(id="i", tipo="incidente", condiciones=condiciones(2.0, temperatura=-25.0))
    frio = Caso(id="i", tipo="incidente", condiciones=condiciones(2.0, temperatura=-15.0))
    assert reglas.DESCARTA in {e.efecto for e in reglas.r2_meteorologia(cat, helado)}
    assert reglas.DESCARTA not in {e.efecto for e in reglas.r2_meteorologia(cat, frio)}


# --- R3 a R8 ---------------------------------------------------------------------------


def test_r3_permanencia_larga_es_condicion_nunca_descarte() -> None:
    cat = construir(pequeno())
    largo_ = reglas.r3_autonomia(cat, Caso(id="i", tipo="incidente", duracion_min=180))
    corto = reglas.r3_autonomia(cat, Caso(id="i", tipo="incidente", duracion_min=20))
    assert [e.efecto for e in largo_] == [reglas.CONDICION]
    assert [e.efecto for e in corto] == [reglas.COMPATIBLE]
    assert reglas.r3_autonomia(cat, Caso(id="i", tipo="incidente")) == []


def test_r4_velocidad_oficial_descarta_y_la_de_prensa_solo_condiciona() -> None:
    cat = construir(pequeno())
    oficial = Caso(id="i", tipo="incidente", velocidad_ms=(30.0, 35.0), velocidad_oficial=True)
    prensa = Caso(id="i", tipo="incidente", velocidad_ms=(30.0, 35.0))
    lenta = Caso(id="i", tipo="incidente", velocidad_ms=(5.0, 8.0), velocidad_oficial=True)
    assert [e.efecto for e in reglas.r4_velocidad(cat, oficial)] == [reglas.DESCARTA]
    assert [e.efecto for e in reglas.r4_velocidad(cat, prensa)] == [reglas.CONDICION]
    assert [e.efecto for e in reglas.r4_velocidad(cat, lenta)] == [reglas.COMPATIBLE]
    assert reglas.velocidad_entre((55.0, 12.0, 0.0), (55.0, 12.0, 60.0)) is None
    v = reglas.velocidad_entre((55.0, 12.0, 0.0), (55.009, 12.0, 100.0))
    assert v is not None and 9 < v < 11


def test_r5_radar_solo_con_seccion_radar_con_fuente() -> None:
    sin_rcs = construir(pequeno())
    con_rcs = construir(pequeno(rcs=_dato(0.001, "m2")))
    caso = Caso(id="i", tipo="incidente", deteccion_radar=True)
    assert reglas.r5_radar(sin_rcs, caso) == []
    assert [e.efecto for e in reglas.r5_radar(con_rcs, caso)] == [reglas.DESCARTA]


def test_r6_sitios_a_la_vez_lejos_piden_varios_equipos() -> None:
    cat = construir(pequeno())
    caso = Caso(
        id="a",
        tipo="incidente",
        lat=55.0,
        lon=12.0,
        inicio=0.0,
        fin=1800.0,
        condiciones=condiciones(5.0),
    )
    sitios = [Sitio("a", 55.0, 12.0, 1.0, 0.0, 1800.0), Sitio("b", 56.0, 12.0, 1.0, 0.0, 1800.0)]
    evidencia = reglas.r6_simultaneidad(cat, caso, sitios)
    assert [e.efecto for e in evidencia] == [reglas.CONDICION]
    # El mismo sitio otro día no dice nada: el mismo equipo pudo volver.
    otro_dia = [sitios[0], Sitio("b", 56.0, 12.0, 1.0, 86400.0, 88200.0)]
    assert reglas.r6_simultaneidad(cat, caso, otro_dia) == []


def test_r7_la_descripcion_suma_o_resta_pero_no_descarta() -> None:
    cat = construir(pequeno(), largo())
    caso = Caso(id="i", tipo="incidente", textos=["a small quadcopter with lights"], luces="si")
    evidencia = reglas.r7_descripcion(cat, caso)
    assert {e.efecto for e in evidencia} <= {reglas.A_FAVOR, reglas.EN_CONTRA}
    assert reglas.A_FAVOR in {e.efecto for e in evidencia if e.clase == "pequeno"}
    assert reglas.EN_CONTRA in {e.efecto for e in evidencia if e.clase == "largo"}
    sonido = reglas.r7_descripcion(cat, Caso(id="i", tipo="incidente", textos=["звук мопеда"]))
    assert reglas.A_FAVOR in {e.efecto for e in sonido if e.clase == "largo"}


def test_r7_nombrar_un_modelo_lo_apoya() -> None:
    cat = construir(pequeno(), largo())
    evidencia = reglas.r7_descripcion(
        cat, Caso(id="i", tipo="incidente", textos=["un ATAQUE cayó"])
    )
    assert any(e.clase == "largo" and e.datos.get("modelo") == "ataque" for e in evidencia)


def test_r8_gnss_anota_sin_descartar() -> None:
    cat = construir(pequeno(), largo())
    evidencia = reglas.r8_gnss(cat, Caso(id="i", tipo="incidente", gnss="alta"))
    por_clase = {e.clase: e.datos["afectada"] for e in evidencia}
    assert por_clase == {"pequeno": "afectada", "largo": "resistente"}
    assert {e.efecto for e in evidencia} == {reglas.ANOTACION}
    assert reglas.r8_gnss(cat, Caso(id="i", tipo="incidente", gnss="sin_interferencia")) == []


# --- Combinación -------------------------------------------------------------------------


def test_conflicto_entre_viento_y_testigo_queda_indeterminado() -> None:
    cat = construir(pequeno(), largo())
    caso = Caso(
        id="i", tipo="incidente", condiciones=condiciones(16.0, 16.0), textos=["a small quadcopter"]
    )
    resultado = motor.combinar(
        cat, reglas.r2_meteorologia(cat, caso) + reglas.r7_descripcion(cat, caso)
    )
    assert {"clase": "pequeno", "motivo": "conflicto"} in resultado["indeterminadas"]
    conflicto = resultado["conflictos"][0]
    assert conflicto["clase"] == "pequeno"
    assert conflicto["descartan"][0]["regla"] == "meteorologia"
    assert conflicto["apoyan"][0]["regla"] == "descripcion"


def test_si_todas_las_clases_quedan_descartadas_se_declara_el_conflicto() -> None:
    cat = construir(pequeno())
    caso = Caso(id="i", tipo="incidente", condiciones=condiciones(20.0))
    resultado = motor.combinar(cat, reglas.r2_meteorologia(cat, caso))
    assert resultado["descartadas"] == []
    assert resultado["conflictos"][0]["motivo"] == "ninguna_clase_compatible"


def test_sin_datos_la_clase_es_indeterminada_y_nunca_compatible_de_relleno() -> None:
    cat = construir(pequeno())
    resultado = motor.combinar(cat, [])
    assert resultado["compatibles"] == []
    assert resultado["indeterminadas"] == [{"clase": "pequeno", "motivo": "sin_datos"}]


def test_el_bloque_valida_contra_el_esquema() -> None:
    cat = construir(pequeno(), largo())
    caso = Caso(
        id="i",
        tipo="incidente",
        pais="DK",
        lat=55.6093,
        lon=12.6379,
        radio_km=2.0,
        condiciones=condiciones(4.0),
        duracion_min=60,
        textos=["quadcopter"],
    )
    documento = motor.evaluar_incidente(cat, caso, [])
    documento["huella"] = "b" * 64
    documento["evaluado"] = motor.instante(AHORA)
    errores = list(validador_definicion("deduccion").iter_errors(documento))
    assert errores == []
    assert documento["origen"] == "deducido" and documento["metodo"] == "regla"
    assert {"nombre": "distancia", "version": "1.0.0"} in documento["reglas"]


def test_la_base_rechaza_un_bloque_que_no_valida() -> None:
    almacen = Almacen.abrir()
    malo = {**ejemplos.deduccion(), "origen": "medido"}
    with pytest.raises(DocumentoInvalido):
        almacen.guardar_deduccion("EODI-2025-00001", "incidente", malo)
    assert almacen.guardar_deduccion("EODI-2025-00001", "incidente", ejemplos.deduccion())
    # Solo la hora: no cambia nada.
    otra_hora = {
        **ejemplos.deduccion(),
        "evaluado": {"precision": "minuto", "valor": "2025-09-24T10:00Z"},
    }
    assert not almacen.guardar_deduccion("EODI-2025-00001", "incidente", otra_hora)


# --- Zona de despegue, deriva y horizonte ------------------------------------------------


def test_zona_de_despegue_en_calma_es_un_circulo_y_con_viento_se_desplaza() -> None:
    calma = zona_despegue.poligono_local(10.0, 30.0, (0.0, 0.0))
    radio = 10.0 * 3.6 * 0.5
    assert all(math.hypot(x, y) == pytest.approx(radio, rel=1e-6) for x, y in calma)
    # Viento hacia el este: la zona de despegue se va al oeste (sube contra el viento).
    con_viento = zona_despegue.poligono_local(10.0, 30.0, (5.0, 0.0))
    centro_x = sum(x for x, _ in con_viento) / len(con_viento)
    assert centro_x == pytest.approx(-5.0 * 3.6 * 0.5, rel=0.05)
    # Con más viento que velocidad propia, el incidente queda en el borde (envolvente con él).
    arrastre = zona_despegue.poligono_local(5.0, 30.0, (10.0, 0.0))
    assert (0.0, 0.0) in arrastre


def test_zona_de_despegue_cruza_tierra_mar_y_otro_pais() -> None:
    cat = construir(pequeno())
    zona = zona_despegue.calcular(cat, "pequeno", "DK", 55.6093, 12.6379, (0.0, 0.0))
    assert isinstance(zona, zona_despegue.Zona)
    assert zona.fracciones["mar"] > 0.2
    assert zona.fracciones["pais"] > 0.2
    assert abs(sum(zona.fracciones.values()) - 1.0) < 1e-6


def _lugar_con_viento(velocidad: float, de_donde: float) -> dict[str, Any]:
    return {
        "lat": 47.0,
        "lon": 28.0,
        "momento": {"precision": "hora", "valor": "2025-11-25T03:00Z"},
        "superficie": {},
        "niveles": {
            n: {"viento_ms": velocidad, "direccion": de_donde} for n in ("925", "850", "700")
        },
    }


def test_deriva_a_sotavento_es_compatible_y_contra_el_viento_no(real: Catalogo) -> None:
    # Punto en Moldavia a unos 20 km al oeste de la frontera ucraniana.
    lat, lon = 46.85, 29.6
    punto = geo.punto_mas_cercano("UA", lat, lon)
    assert punto is not None
    rumbo = geo.rumbo(punto[0], punto[1], lat, lon)
    # Viento que sopla hacia donde está el punto (viene del lado contrario).
    a_favor = deriva.evaluar(
        real, "senuelo_largo_alcance", lat, lon, _lugar_con_viento(10.0, (rumbo + 180.0) % 360.0)
    )
    en_contra = deriva.evaluar(
        real, "senuelo_largo_alcance", lat, lon, _lugar_con_viento(10.0, rumbo)
    )
    flojo = deriva.evaluar(real, "senuelo_largo_alcance", lat, lon, _lugar_con_viento(1.0, rumbo))
    assert a_favor is not None and en_contra is not None and flojo is not None
    assert a_favor.resultado == deriva.COMPATIBLE
    assert en_contra.resultado == deriva.NO_COMPATIBLE
    assert flojo.resultado == deriva.INDETERMINADO
    sin_direccion = deriva.evaluar(real, "senuelo_largo_alcance", lat, lon, None)
    assert sin_direccion is not None and sin_direccion.resultado == deriva.INDETERMINADO
    # Lejos de la guerra (Bruselas) no es un cruce: no se evalúa.
    assert deriva.evaluar(real, "senuelo_largo_alcance", 50.9, 4.48, None) is None


def test_horizonte_en_llano_solo_por_la_curvatura() -> None:
    def llano(lat: float, lon: float) -> float:
        return 0.0

    calculado = horizonte.calcular(llano, 50.0, 10.0)
    assert calculado is not None and len(calculado["sectores"]) == horizonte.SECTORES
    perfil = calculado["sectores"][0]["perfil"]
    # En llano solo tapa la curvatura: nada hasta el horizonte de la antena (unos 16 km) y unos
    # metros más allá (a 30 km, (30 - 16)² / (2 · 8495) km, unos 12 m).
    por_distancia = {p["distancia_km"]: p["oculto_bajo_m"] for p in perfil}
    assert por_distancia[1.0] == 0 and por_distancia[10.0] == 0
    assert 5 < por_distancia[30.0] < 20


def test_horizonte_con_una_loma_tapa_lo_que_hay_detras() -> None:
    def loma(lat: float, lon: float) -> float:
        # Una loma de 100 m a 2 km al norte del radar.
        d = geo.distancia_km(50.0, 10.0, lat, lon)
        norte = lat > 50.0 and abs(lon - 10.0) < 0.01
        return 100.0 if norte and 1.8 < d < 2.2 else 0.0

    calculado = horizonte.calcular(loma, 50.0, 10.0)
    assert calculado is not None
    norte = {p["distancia_km"]: p["oculto_bajo_m"] for p in calculado["sectores"][0]["perfil"]}
    sur = {p["distancia_km"]: p["oculto_bajo_m"] for p in calculado["sectores"][18]["perfil"]}
    # Detrás de la loma, a 10 km, queda oculto por debajo de unos 85·5 = 425 m.
    assert 350 < norte[10.0] < 500
    assert sur[10.0] < 10
    assert horizonte.calcular(lambda a, b: None, 50.0, 10.0) is None


# --- Relieve: lector de teselas ---------------------------------------------------------


def _tiff_flotante(valores: list[list[float]]) -> bytes:
    """Un GeoTIFF mínimo como los de Copernicus: un bloque, DEFLATE y predictor 3."""
    alto, ancho = len(valores), len(valores[0])
    filas = []
    for fila in valores:
        crudo = b"".join(struct.pack(">f", v) for v in fila)
        planos = bytes(crudo[4 * i + b] for b in range(4) for i in range(ancho))
        dif = bytearray(planos)
        for i in range(len(dif) - 1, 0, -1):
            dif[i] = (dif[i] - dif[i - 1]) & 0xFF
        filas.append(bytes(dif))
    bloque = zlib.compress(b"".join(filas))
    etiquetas: list[tuple[int, int, int, bytes]] = []

    def corto(etiqueta: int, valor: int) -> None:
        etiquetas.append((etiqueta, 3, 1, struct.pack("<HH", valor, 0)))

    def largo_(etiqueta: int, valor: int) -> None:
        etiquetas.append((etiqueta, 4, 1, struct.pack("<I", valor)))

    corto(256, ancho)
    corto(257, alto)
    corto(258, 32)
    corto(259, 8)
    corto(317, 3)
    corto(339, 3)
    corto(278, alto)
    extra = b""
    cabecera_ifd = 8
    n = 11
    datos_ini = cabecera_ifd + 2 + 12 * n + 4
    escala = struct.pack("<3d", 0.5, 0.5, 0.0)
    enlace = struct.pack("<6d", 0.0, 0.0, 0.0, 10.0, 51.0, 0.0)
    largo_(273, datos_ini + len(escala) + len(enlace))
    largo_(279, len(bloque))
    etiquetas.append((33550, 12, 3, struct.pack("<I", datos_ini)))
    etiquetas.append((33922, 12, 6, struct.pack("<I", datos_ini + len(escala))))
    extra = escala + enlace + bloque
    etiquetas.sort()
    ifd = (
        struct.pack("<H", len(etiquetas))
        + b"".join(struct.pack("<HHI", e, t, c) + v for e, t, c, v in etiquetas)
        + struct.pack("<I", 0)
    )
    return b"II*\x00" + struct.pack("<I", cabecera_ifd) + ifd + extra


def test_el_lector_de_teselas_deshace_el_predictor_de_coma_flotante(tmp_path: Path) -> None:
    valores = [[1.5, 2.5, 3.5], [10.0, 20.0, 30.0], [100.0, -5.25, 7.0]]
    tesela = dem.leer_tiff(_tiff_flotante(valores))
    assert (tesela.ancho, tesela.alto) == (3, 3)
    assert list(tesela.valores) == [v for fila in valores for v in fila]
    # Centro del primer píxel: medio paso desde la esquina.
    assert tesela.elevacion(51.0 - 0.25, 10.25) == pytest.approx(1.5)

    pedidas: list[str] = []

    def descargar(url: str) -> bytes | None:
        pedidas.append(url)
        return _tiff_flotante(valores) if "N50_00_E010_00" in url else None

    relieve = dem.Relieve(tmp_path, descargar)
    assert relieve(50.75, 10.25) == pytest.approx(1.5)
    assert relieve(50.75, 10.25) == pytest.approx(1.5)
    assert relieve(30.5, -20.5) is None
    assert relieve(30.5, -20.5) is None
    # Cada tesela se pide una vez: las que no existen quedan anotadas.
    assert len(pedidas) == 2
    assert dem.nombre(-0.5, -0.5) == "S01_00_W001_00"


# --- Ejecución incremental y paso horario ---------------------------------------------


def _incidente() -> dict[str, Any]:
    """El incidente completo como está en la base (sin lo que añade la exportación)."""
    documento = ejemplos.incidente_completo()
    for campo in ("procedencia", "nivel_detalle", "deduccion"):
        del documento[campo]
    return documento


def _base_minima() -> Almacen:
    almacen = Almacen.abrir()
    almacen.guardar_incidente(_incidente(), ejemplos.AHORA, ejemplos.VOCABULARIO_MODELOS)
    ataque = ejemplos.ataque_completo()
    del ataque["deduccion"]
    almacen.guardar_ataque_ucrania(ataque, ejemplos.AHORA)
    almacen.guardar_impacto_guerra(ejemplos.impacto_guerra())
    return almacen


class SinRelieve:
    descargas = 0

    def __call__(self, lat: float, lon: float) -> float | None:
        return None

    def disco_mb(self) -> float:
        return 0.0


def test_el_calculo_es_incremental_y_la_horaria_lo_incorpora(tmp_path: Path) -> None:
    almacen = _base_minima()
    primero = deduccion.calcular(almacen, tmp_path, AHORA, relieve=SinRelieve())  # type: ignore[arg-type]
    calculados = {k: v for k, v in primero["cuentas"].items() if k.endswith("_calculados")}
    assert calculados and not any(k.endswith("_sin_cambios") for k in primero["cuentas"])
    segundo = deduccion.calcular(almacen, tmp_path, AHORA, relieve=SinRelieve())  # type: ignore[arg-type]
    assert not any(k.endswith("_calculados") for k in segundo["cuentas"])
    # Todo de nuevo con --todo.
    tercero = deduccion.calcular(almacen, tmp_path, AHORA, todo=True, relieve=SinRelieve())  # type: ignore[arg-type]
    assert any(k.endswith("_calculados") for k in tercero["cuentas"])
    cambiados = deduccion.incorporar(almacen, tmp_path)
    assert cambiados.get("incidente") == 1
    assert deduccion.incorporar(almacen, tmp_path) == {}
    resumen = almacen.cursor(deduccion.CURSOR)
    assert resumen is not None and resumen["validacion"]["fallos_graves"] == 0
    assert set(almacen.deducciones()) >= {_incidente()["id"]}


def test_un_cambio_de_version_del_catalogo_recalcula_todo(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    almacen = _base_minima()
    deduccion.calcular(almacen, tmp_path, AHORA, relieve=SinRelieve())  # type: ignore[arg-type]
    real = catalogo.cargar()
    monkeypatch.setattr(real, "version", "9.0.0")
    otra = deduccion.calcular(almacen, tmp_path, AHORA, relieve=SinRelieve())  # type: ignore[arg-type]
    assert not any(k.endswith("_sin_cambios") for k in otra["cuentas"])


def test_un_fallo_del_motor_no_rompe_la_horaria(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    def falla(*a: Any, **k: Any) -> Any:
        raise RuntimeError("roto")

    monkeypatch.setattr(deduccion, "incorporar", falla)
    deduccion.paso_horario(Almacen.abrir())
    assert "deducción no incorporada" in caplog.text


def test_estado_json_lleva_la_ultima_deduccion(tmp_path: Path) -> None:
    registro = tmp_path / "deduccion.json"
    registro.write_text(json.dumps({"ultima_correcta": "2026-10-02T09:05Z"}), encoding="utf-8")
    salida = tmp_path / "estado.json"
    estado.principal(
        [
            "--inicio",
            "2026-10-02T09:17:00Z",
            "--codigo",
            "0",
            "--salida",
            str(salida),
            "--minuto",
            "17",
            "--deduccion",
            str(registro),
        ]
    )
    assert json.loads(salida.read_text(encoding="utf-8"))["ultima_deduccion"] == "2026-10-02T09:05Z"
    sin = tmp_path / "sin.json"
    estado.principal(
        [
            "--inicio",
            "2026-10-02T09:17:00Z",
            "--codigo",
            "0",
            "--salida",
            str(sin),
            "--minuto",
            "17",
        ]
    )
    assert "ultima_deduccion" not in json.loads(sin.read_text(encoding="utf-8"))


# --- Validación ------------------------------------------------------------------------


def test_los_casos_de_validacion_tienen_fuente_y_clase_del_catalogo(real: Catalogo) -> None:
    casos = validacion.cargar()
    assert len(casos["casos"]) >= 20
    for caso in casos["casos"]:
        assert caso["fuentes"] and all(re.match(r"^https?://", f["url"]) for f in caso["fuentes"])
        assert all(f.get("cita") for f in caso["fuentes"])
        assert set(caso["clases_reales"]) <= set(real.clases)
        if not caso["clases_reales"]:
            assert caso.get("nota")


def test_resultado_de_un_caso() -> None:
    deduccion_ = {"compatibles": [{"clase": "a"}], "descartadas": [{"clase": "b"}]}
    assert validacion.resultado_de(deduccion_, ["a"]) == validacion.ACIERTO
    assert validacion.resultado_de(deduccion_, ["b"]) == validacion.FALLO_GRAVE
    assert validacion.resultado_de(deduccion_, ["c"]) == validacion.INDETERMINADO
    assert validacion.resultado_de(deduccion_, ["a", "b"]) == validacion.ACIERTO


def test_la_validacion_real_no_tiene_fallos_graves_sin_meteo(real: Catalogo) -> None:
    resultado = validacion.validar(real, validacion.cargar(), None, {})
    assert resultado["fallos_graves"] == 0
    assert (
        resultado["evaluados"]
        + sum(1 for d in resultado["detalle"] if d["resultado"] == "excluido")
        == resultado["casos"]
    )
