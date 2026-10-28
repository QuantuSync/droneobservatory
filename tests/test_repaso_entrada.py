"""El repaso de todo lo publicado con la pregunta del filtro de entrada
(recogida/repaso_entrada.py): el conjunto de comparación de una ficha publicada, la retirada por
fecha desconocida, la separación de una ficha que junta varios sucesos y la de un resumen, su
presupuesto aparte y que nunca aplica sin un muestreo aprobado."""

import contextlib
import copy
from datetime import UTC, datetime
from typing import Any

import pytest

from almacen import base as almacen_base
from almacen.base import Almacen
from modelo import coste
from modelo import entrada as peticiones
from recogida import control_fichas, entrada
from recogida import repaso_entrada as repaso
from tests.ejemplos import VOCABULARIO_MODELOS
from tests.test_entrada import AHORA, _base, _ficha, _respuesta

# Fuera de los minutos de la recogida: el repaso no espera.
FUERA = datetime(2026, 10, 28, 15, 50, tzinfo=UTC)


def _respuesta_repaso(**cambios: Any) -> dict[str, Any]:
    base = {**_respuesta(), "fecha_desconocida": False, "varios_sucesos": False,
            "resumen": False, "partes": [], "errores": []}  # fmt: skip
    return {**base, **cambios}


def test_el_conjunto_de_una_ficha_publicada_es_el_del_filtro_sin_ella() -> None:
    ficha = _ficha("EODI-2025-00116", "DE", "2025-10-02T00:00Z", punto=(48.35, 11.78),
                   nivel="localidad")  # fmt: skip
    mismo_dia = _ficha("EODI-2025-00340", "DE", "2025-10-02T00:00Z", punto=(48.35, 11.78),
                       nivel="localidad")  # fmt: skip
    lejos = _ficha("EODI-2025-00001", "DE", "2025-06-01T00:00Z", punto=(52.5, 13.4),
                   nivel="localidad")  # fmt: skip
    otro_pais = _ficha("EODI-2025-00002", "AT", "2025-10-02T00:00Z", punto=(48.2, 16.4),
                       nivel="localidad")  # fmt: skip
    elegidas = entrada.conjunto(ficha, [ficha, mismo_dia, lejos, otro_pais])
    assert [c["id"] for c in elegidas] == ["EODI-2025-00340"]
    # Con el lugar en el país, también los vecinos.
    vaga = {**copy.deepcopy(ficha), "lugar": {"pais": "DE", "nivel": "pais"}}
    assert {c["id"] for c in entrada.conjunto(vaga, [vaga, mismo_dia, otro_pais])} == {
        "EODI-2025-00340", "EODI-2025-00002"}  # fmt: skip
    # Los grupos: la lista de sospechosas, la fecha aproximada, el lugar vago y el resto.
    assert repaso.grupo_de(ficha) == "a"
    assert repaso.grupo_de(_ficha("EODI-2026-00900", "RO", "2026-10-01T10:00Z", "aproximada",
                                  punto=(45.0, 29.0), nivel="localidad")) == "b"  # fmt: skip
    assert repaso.grupo_de(_ficha("EODI-2026-00901", "RO", "2026-10-01T00:00Z")) == "c"
    assert repaso.grupo_de(lejos) == "d"


def test_una_noticia_de_un_suceso_anterior_sin_su_dia_se_retira() -> None:
    ficha = _ficha("EODI-2026-00900", "RO", "2026-10-20T10:00Z", "aproximada",
                   frase="Drones have repeatedly entered Romanian airspace recently")  # fmt: skip
    fuentes = [("EODI-2026-00900-F1", ficha["fuentes"][0]["frase_origen"])]
    respuesta = _respuesta_repaso(fecha_frase="no", fecha_fuente=0, fecha_desconocida=True)
    decision = repaso.decidir(respuesta, fuentes, [], ficha)
    assert decision["fecha_desconocida"] and repaso.cambios(decision, ficha) == [repaso.RETIRAR]
    # Con la fecha firme (sacada de una frase) no se retira.
    firme = {**ficha, "tiempo": {"inicio": {"valor": "2026-10-19T00:00Z", "precision": "dia"},
                                 "origen_inicio": {"tipo": "explicita"}}}  # fmt: skip
    assert repaso.RETIRAR not in repaso.cambios(decision, firme)
    almacen = _base(ficha)
    ctx = _contexto(almacen)
    hecho = repaso.Aplicado()
    assert repaso.aplicar_una(ctx, ficha, {**decision, "cambios": [repaso.RETIRAR]}, hecho)
    retirada = almacen.incidente("EODI-2026-00900")
    assert retirada is not None and retirada["retirado"]["motivo"].startswith(
        "Fecha del suceso desconocida"
    )
    assert hecho.retiradas == ["EODI-2026-00900"]


def test_la_ficha_de_varios_sucesos_se_propone_separar_y_el_resumen_se_retira() -> None:
    ficha = _ficha("EODI-2025-00446", "BE", "2025-11-04T00:00Z",
                   frase="Drones were seen over Kleine-Brogel for three nights")  # fmt: skip
    segunda = {**copy.deepcopy(ficha["fuentes"][0]), "id": "EODI-2025-00446-F2",
               "enlace": "https://example.org/2",
               "frase_origen": "Drones over Doel on Monday"}  # fmt: skip
    ficha["fuentes"].append(segunda)
    fuentes = [(f["id"], f["frase_origen"]) for f in ficha["fuentes"]]
    partes = [{"fecha": "2025-11-02", "descripcion": "Kleine-Brogel", "fuentes": [1]},
              {"fecha": "2025-11-03", "descripcion": "Doel", "fuentes": [2]}]  # fmt: skip
    decision = repaso.decidir(_respuesta_repaso(varios_sucesos=True, partes=partes), fuentes,
                              [], ficha)  # fmt: skip
    assert repaso.cambios(decision, ficha) == [repaso.SEPARAR]
    propuesta = repaso.propuesta_separar(ficha, decision)
    assert propuesta["distintos"] is True
    assert [p["fuentes"] for p in propuesta["partes"]] == [["EODI-2025-00446-F1"],
                                                          ["EODI-2025-00446-F2"]]  # fmt: skip
    # Un balance sin un suceso de un día concreto no se separa: se retira.
    resumen = repaso.decidir(_respuesta_repaso(resumen=True), fuentes, [], ficha)
    assert repaso.cambios(resumen, ficha) == [repaso.RETIRAR]
    almacen = _base(ficha)
    hecho = repaso.Aplicado()
    repaso.aplicar_una(_contexto(almacen), ficha, {**resumen, "cambios": [repaso.RETIRAR]}, hecho)
    queda = almacen.incidente("EODI-2025-00446")
    assert queda is not None and queda["retirado"]["motivo"].startswith("Es un resumen")


def test_el_presupuesto_del_repaso_es_aparte() -> None:
    assert coste.limite(coste.Modo.REPASO_ENTRADA) == 40.00
    assert "repaso_entrada" in almacen_base.CUPOS_PROPIOS
    assert "repaso_entrada" in almacen_base.FUERA_DEL_MES
    assert not coste.diario(coste.Modo.REPASO_ENTRADA)
    almacen = Almacen.abrir()
    almacen.registrar_llamada({
        "fecha": "2026-10-28T15:50:00Z", "modo": "repaso_entrada", "candidato": "x",
        "lote": False, "entrada": 1000, "salida": 100, "escritura_cache": 0,
        "lectura_cache": 0, "coste": 5.0, "modelo": "proveedor-sonnet-5-5", "escalada": False,
    })  # fmt: skip
    assert almacen.gastado("repaso_entrada") == pytest.approx(5.0)
    # No cuenta en el experto del día ni en el filtro de entrada ni en el mes.
    assert almacen.gastado_experto_en(coste.Modo.ENTRADA.value, "2026-10-28") == 0.0
    assert almacen.gastado_modelo("proveedor-sonnet", "2026-10-28") == 0.0
    assert coste.del_mes(almacen, FUERA).total == 0.0
    # La pregunta es la del filtro, con las dos de más.
    assert "Repasas una ficha ya publicada" in peticiones.INSTRUCCIONES_REPASO
    assert {"varios_sucesos", "errores"} <= set(peticiones.ESQUEMA_REPASO["required"])


def _contexto(almacen: Almacen) -> control_fichas.Contexto:
    resultado = control_fichas.Resultado()
    llamador = control_fichas.Llamador(almacen, None, coste.Modo.REPASO_ENTRADA, AHORA, None,
                                       resultado)  # fmt: skip
    return control_fichas.Contexto(almacen, AHORA, VOCABULARIO_MODELOS, llamador, resultado,
                                   None, None, almacen.controles())  # fmt: skip


def _base_de(almacen: Almacen) -> control_fichas.Base:
    return control_fichas.Base(lambda: almacen, lambda a: None, contextlib.nullcontext)


def test_nunca_aplica_sin_un_muestreo_aprobado() -> None:
    fichas = [_ficha(f"EODI-2026-0090{n}", "RO", "2026-10-20T10:00Z", "aproximada")
              for n in range(3)]  # fmt: skip
    almacen = _base(*fichas)
    decisiones = {}
    for ficha in fichas:
        decision = {"grupo": "b", "huella": entrada.huella(ficha), "cambios": [repaso.RETIRAR],
                    "fecha_desconocida": True, "motivo_es": "recuerdo sin fecha"}  # fmt: skip
        decisiones[repaso.clave(ficha["id"])] = decision
    almacen.guardar_controles(decisiones, "2026-10-28T15:40:00Z")
    base = _base_de(almacen)

    def aplicar(muestreo: dict[str, Any]) -> repaso.Aplicado:
        return repaso.aplicar_grupo(base, "b", muestreo, VOCABULARIO_MODELOS, reloj=lambda: FUERA,
                                    dormir=lambda s: None)  # fmt: skip

    plantilla = repaso.plantilla(almacen.controles(repaso.PREFIJO), "b", 7)
    assert len(plantilla["revisadas"]) == 3
    # Sin leer, con otra muestra o con dos mal: no se aplica nada.
    with pytest.raises(repaso.MuestreoNoAprobado):
        aplicar(plantilla)
    leidas = copy.deepcopy(plantilla)
    for r in leidas["revisadas"]:
        r["bien"] = True
    otra = {**leidas, "revisadas": leidas["revisadas"][:2]}
    with pytest.raises(repaso.MuestreoNoAprobado):
        aplicar(otra)
    malas = copy.deepcopy(leidas)
    malas["revisadas"][0]["bien"] = malas["revisadas"][1]["bien"] = False
    with pytest.raises(repaso.MuestreoNoAprobado):
        aplicar(malas)
    assert all("retirado" not in (almacen.incidente(f["id"]) or {}) for f in fichas)
    # Con el muestreo aprobado se aplica, y lo aplicado ya no vuelve a salir.
    hecho = aplicar(leidas)
    assert sorted(hecho.retiradas) == [f["id"] for f in fichas]
    assert repaso.con_cambios(almacen.controles(repaso.PREFIJO), "b") == {}
    assert repaso.PREFIJO_MUESTREO + "b" in almacen.controles(repaso.PREFIJO_MUESTREO)


def _firme(ficha: dict[str, Any]) -> dict[str, Any]:
    return {**ficha, "tiempo": {**ficha["tiempo"], "origen_inicio": {"tipo": "explicita"}}}


def test_una_union_imposible_no_vale() -> None:
    # Vilna, 28 de octubre de 2026: el cierre del 26 de septiembre (día firme) no puede ser el que
    # contaban noticias del 25 (EODI-2025-00004 y 00060).
    viernes = _firme(_ficha("EODI-2025-00004", "LT", "2025-09-26T00:00Z", punto=(54.64, 25.29),
                            nivel="instalacion", publicada="2025-09-26T12:00Z"))  # fmt: skip
    jueves = _ficha("EODI-2025-00060", "LT", "2025-09-25T12:57Z", "aproximada",
                    punto=(54.64, 25.29), nivel="instalacion",
                    publicada="2025-09-25T15:00Z")  # fmt: skip
    assert "antes del 2025-09-26" in (repaso.mismo_imposible(viernes, jueves) or "")
    assert "antes del 2025-09-26" in (repaso.mismo_imposible(jueves, viernes) or "")
    decision = {"mismo": "EODI-2025-00060", "motivo_mismo": "el mismo cierre"}
    ajustada = repaso.ajustar(decision, viernes, jueves)
    assert "mismo" not in ajustada and ajustada["cambios"] == []
    assert ajustada["invalida"].startswith("no es el mismo suceso que EODI-2025-00060")
    # Moldavia, 30 de septiembre de 2026: Hîrbovăț y Orhei, la misma noche, a más de 25 km.
    orhei = _ficha("EODI-2026-00636", "MD", "2026-09-30T00:00Z", punto=(47.38, 28.82),
                   nivel="localidad")  # fmt: skip
    hirbovat = _ficha("EODI-2026-00168", "MD", "2026-09-30T00:00Z", punto=(46.86, 29.33),
                      nivel="localidad")  # fmt: skip
    assert "km" in (repaso.mismo_imposible(orhei, hirbovat) or "")
    # Ni dos países: el Shahed del 16 de agosto de 2026 en Moldavia y en Rumanía.
    galati = _ficha("EODI-2026-00106", "RO", "2026-08-16T00:00Z")
    etulia = _ficha("EODI-2026-00171", "MD", "2026-08-16T00:00Z")
    assert "países distintos" in (repaso.mismo_imposible(galati, etulia) or "")
    # El mismo aeropuerto el mismo día sí puede serlo.
    otra = _ficha("EODI-2025-00061", "LT", "2025-09-26T00:00Z", punto=(54.65, 25.30),
                  nivel="instalacion", publicada="2025-09-26T13:00Z")  # fmt: skip
    assert repaso.mismo_imposible(viernes, otra) is None
    assert repaso.ajustar(decision | {"mismo": otra["id"]}, viernes, otra)["cambios"] == [
        repaso.UNIR
    ]


def test_solo_deja_de_ser_oficial_la_autoridad_de_otro_pais() -> None:
    ficha = _ficha("EODI-2025-00092", "BE", "2025-11-08T18:00Z", "hora", punto=(50.64, 5.44),
                   nivel="instalacion")  # fmt: skip
    sin_pais = {"frase_lugar": ["x", "y"], "autoridades_fuera": {
        "Skeyes": "ninguna frase la nombra con su país"}}  # fmt: skip
    ajustada = repaso.ajustar(sin_pais, ficha, None)
    assert ajustada["autoridades_fuera"] == {} and repaso.AUTORIDAD not in ajustada["cambios"]
    assert ajustada["autoridades_sin_pais"] == sin_pais["autoridades_fuera"]
    de_otro = {"frase_lugar": ["x", "y"], "autoridades_fuera": {
        "Skeyes": "ninguna frase la nombra con su país",
        "Lettische Streitkräfte": "de otro país (LV) sin que la frase lo diga"}}  # fmt: skip
    ajustada = repaso.ajustar(de_otro, ficha, None)
    assert list(ajustada["autoridades_fuera"]) == ["Lettische Streitkräfte"]
    assert ajustada["cambios"] == [repaso.AUTORIDAD]


def test_recalcular_comprueba_lo_ya_decidido_sin_llamar() -> None:
    viernes = _firme(_ficha("EODI-2025-00004", "LT", "2025-09-26T00:00Z", punto=(54.64, 25.29),
                            nivel="instalacion", publicada="2025-09-26T12:00Z"))  # fmt: skip
    jueves = _ficha("EODI-2025-00060", "LT", "2025-09-25T12:57Z", "aproximada",
                    punto=(54.64, 25.29), nivel="instalacion",
                    publicada="2025-09-25T15:00Z")  # fmt: skip
    almacen = _base(viernes, jueves)
    guardada = almacen.incidente(viernes["id"])
    assert guardada is not None
    decision = {"grupo": "a", "huella": entrada.huella(guardada), "mismo": jueves["id"],
                "cambios": [repaso.UNIR], "motivo_mismo": "el mismo cierre"}  # fmt: skip
    almacen.guardar_controles({repaso.clave(viernes["id"]): decision}, "2026-10-28T17:00:00Z")
    antes = repaso.plantilla(almacen.controles(repaso.PREFIJO), "a", 1)
    assert repaso.recalcular(_base_de(almacen), "a", reloj=lambda: FUERA,
                             dormir=lambda s: None) == 1  # fmt: skip
    queda = almacen.controles(repaso.PREFIJO)[repaso.clave(viernes["id"])]
    assert queda["cambios"] == [] and "mismo" not in queda
    assert repaso.con_cambios(almacen.controles(repaso.PREFIJO), "a") == {}
    # El muestreo de antes ya no vale.
    assert antes["huella"] != repaso.plantilla(almacen.controles(repaso.PREFIJO), "a", 1)["huella"]
