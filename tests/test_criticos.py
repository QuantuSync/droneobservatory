"""Lo crítico no espera y nada en juego queda colgado (20 de octubre de 2026, incidencias de los
recorridos en producción y del caso crítico sin experto):

- un par o una verificación que espera al experto y ya no está en juego (una de sus fichas se unió
  a otra) no retiene ninguna ficha ni cuenta como caso crítico esperando;
- un caso crítico va directo al experto aunque el tope de su modo esté agotado, en el control y
  en la extracción de la recogida horaria;
- de madrugada, lo crítico no espera al lote;
- la publicación no enlaza a una ficha retenida;
- la presencia revisada a mano se mantiene aunque el extractor elija otra frase de la misma
  fuente."""

import copy
from datetime import datetime, timedelta
from typing import Any

import pytest

from almacen.base import Almacen
from exportacion import publicar
from modelo import coste, ficha
from proceso import extraccion
from recogida import control_fichas, revisados
from tests import test_control_fichas as tcf
from tests import test_modelos as tm
from tests.ejemplos import VOCABULARIO_MODELOS as MODELOS_CONTROL
from tests.test_extraccion import AHORA, MODELOS, almacen, ficha_ejemplo

PAR = "par:EODI-2026-09515|EODI-2026-09516"
__all__ = ["almacen"]  # el almacén de cada prueba (fixture de tests/test_extraccion.py)


@pytest.fixture(autouse=True)
def dos_modelos(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EODI_MODELO_BASE", tm.BASE)
    monkeypatch.setenv("EODI_MODELO_EXPERTO", tm.EXPERTO)


@pytest.fixture(autouse=True)
def sin_descargas(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(control_fichas, "descargar", lambda enlaces, plazo: {})


def _gasto(
    almacen: Almacen, dolares: float, modo: str, modelo: str, escalada: bool,
    momento: datetime = tcf.AHORA,
) -> None:  # fmt: skip
    almacen.registrar_llamada({
        "fecha": momento.strftime("%Y-%m-%dT%H:%M:%SZ"), "modo": modo, "candidato": "x",
        "lote": False, "entrada": 0, "salida": 0, "escritura_cache": 0, "lectura_cache": 0,
        "coste": dolares, "modelo": modelo, "escalada": escalada,
    })  # fmt: skip


def test_un_par_que_ya_no_esta_en_juego_no_retiene_ni_espera(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Como EODI-2025-00438|00444: el par crítico espera (desde el 7 de noviembre de 2026, con el
    # tope mensual agotado) y retiene la ficha nueva; después la regla de fusión une la otra a ella.
    almacen = tm._par_de_nuremberg_con_gasto(0.0)
    monkeypatch.setenv(coste.VARIABLE_TOPE_MENSUAL, "0")
    tcf._ejecutar(almacen, tm.ServicioControl("dudoso", "mismo"), tcf.AHORA + timedelta(minutes=10))
    monkeypatch.delenv(coste.VARIABLE_TOPE_MENSUAL)
    assert PAR in [c["clave"] for c in control_fichas.criticos_esperando(almacen)]
    otra = almacen.incidente("EODI-2026-09515")
    assert otra is not None
    almacen.guardar_incidente(
        {**otra, "fusionado_en": "EODI-2026-09516"}, tcf.AHORA, MODELOS_CONTROL
    )
    # El par ya no cuenta; lo que espera de la ficha que queda, sí (sigue en juego: con el mes
    # agotado, su filtro de entrada).
    claves = [c["clave"] for c in control_fichas.criticos_esperando(almacen)]
    assert claves and PAR not in claves
    assert all(c.endswith(":EODI-2026-09516") for c in claves)
    # Al día siguiente el experto la verifica y la ficha sale; el par no se vuelve a pedir.
    servicio = tm.ServicioControl("distinto", "distinto")
    resultado = tcf._ejecutar(almacen, servicio, tcf.AHORA + timedelta(days=1))
    assert "comparar" not in servicio.pedidas
    assert "EODI-2026-09516" not in resultado.retenidos
    assert "EODI-2026-09516" not in control_fichas.retenidos(almacen)
    assert control_fichas.criticos_esperando(almacen) == []
    # La decisión no se borra: queda como estaba.
    assert almacen.controles("par:")[PAR]["decision"] == "dudoso"


def test_el_gasto_del_dia_del_control_ya_no_frena_al_par_critico() -> None:
    # Más de lo que era el tope diario del control: desde el 7 de noviembre de 2026 no frena.
    almacen = tm._par_de_nuremberg_con_gasto(0.0)
    _gasto(almacen, 1.0, "control", tm.BASE, False)
    servicio = tm.ServicioControl("dudoso", "mismo")
    resultado = tcf._ejecutar(almacen, servicio, tcf.AHORA + timedelta(minutes=10))
    assert resultado.parada != "limite_gasto" and resultado.esperan_experto == []
    decision = almacen.controles("par:")[PAR]
    assert decision["decision"] == "mismo" and decision["modelo"] == tm.EXPERTO
    # Lo leyó el base y lo decidió el experto (el gasto del modo sube).
    dia = coste.dia(tcf.AHORA)
    assert almacen.gastado("control", dia) > 1.0
    assert almacen.gastado_experto_en("control", dia) > 0


def test_el_gasto_del_dia_de_la_horaria_ya_no_frena_a_nadie(almacen: Almacen) -> None:
    # Más de lo que era el tope diario de la horaria: desde el 7 de noviembre de 2026 no frena; el
    # crítico que esperaba y el otro se extraen.
    peticion = tm._peticion(almacen)
    candidato = peticion.candidato["id"]
    extraccion.anotar_espera(almacen, candidato, ["critico: cierre de aeropuerto"],
                             AHORA - timedelta(hours=2), True, critico=True)  # fmt: skip
    _gasto(almacen, 1.0, "horario", tm.BASE, False, AHORA)
    otra = extraccion.Peticion(**{**peticion.__dict__, "candidato": {
        **peticion.candidato, "id": "otro"}})  # fmt: skip
    cliente = tm.Cliente(ficha_ejemplo(**tm.SIN_CITA), ficha_ejemplo())
    hechas = extraccion.extraer(
        almacen, cliente, [otra, peticion], AHORA, coste.Modo.HORARIO, MODELOS
    )
    assert cliente.pedidas == [tm.BASE, tm.EXPERTO, tm.BASE, tm.EXPERTO]
    assert hechas.escalados == ["otro", candidato] and hechas.parada is None
    assert candidato not in extraccion.esperan_experto(almacen)
    assert control_fichas.criticos_esperando(almacen) == []


def test_con_el_mes_agotado_el_candidato_critico_sigue_esperando(
    almacen: Almacen, monkeypatch: pytest.MonkeyPatch,
) -> None:  # fmt: skip
    # Sin reserva crítica desde el 7 de noviembre de 2026: con el tope mensual agotado, tampoco lo
    # crítico se llama; sigue esperando.
    peticion = tm._peticion(almacen)
    candidato = peticion.candidato["id"]
    extraccion.anotar_espera(almacen, candidato, ["critico: cierre de aeropuerto"],
                             AHORA - timedelta(hours=2), True, critico=True)  # fmt: skip
    monkeypatch.setenv(coste.VARIABLE_TOPE_MENSUAL, "0")
    cliente = tm.Cliente(ficha_ejemplo(**tm.SIN_CITA), ficha_ejemplo())
    hechas = extraccion.extraer(almacen, cliente, [peticion], AHORA, coste.Modo.HORARIO, MODELOS)
    assert cliente.pedidas == [] and hechas.esperan == [candidato]
    assert extraccion.esperan_experto(almacen)[candidato]["critico"]


def test_de_madrugada_lo_critico_no_espera_al_lote() -> None:
    servicio = tcf.Servicio("mismo")
    cuerpo = {
        "max_tokens": 500,
        "system": [{"type": "text", "text": "x"}],
        "messages": [{"role": "user", "content": "Ficha A: x"}],
    }
    peticion = control_fichas.Peticion("par", PAR, cuerpo, 500, {"critico": True})
    respuestas = control_fichas.Respuestas()
    gasto = control_fichas.directas_criticas(
        servicio, [peticion], respuestas, tcf.AHORA, coste.Modo.CONTROL, 1.0
    )
    leida = respuestas.leidas[PAR]
    assert servicio.pedidas == ["comparar"] and leida is not None and leida["decision"] == "mismo"
    assert gasto > 0 and respuestas.llamadas_directas[0]["lote"] is False
    # Sin sitio en el tope del modo: sin el base, al experto (escalar_lote).
    sin_sitio = control_fichas.Respuestas()
    control_fichas.directas_criticas(
        servicio, [peticion], sin_sitio, tcf.AHORA, coste.Modo.CONTROL, 0.0
    )
    assert sin_sitio.leidas[PAR] is None
    assert sin_sitio.motivos[PAR][0].startswith("critico_sin_base")


def test_la_publicacion_no_enlaza_a_una_ficha_retenida() -> None:
    nota = {"es": "x", "en": "x"}
    incidente = {"id": "EODI-2025-00066", "relacionados": [
        {"id": "EODI-2025-00080", "separado_de": "EODI-2025-00066", "nota": nota},
        {"id": "EODI-2025-00444", "separado_de": "EODI-2025-00066", "nota": nota},
    ]}  # fmt: skip
    limpio = publicar.sin_retenidos(incidente, frozenset({"EODI-2025-00444"}))
    assert [r["id"] for r in limpio["relacionados"]] == ["EODI-2025-00080"]
    solo = {**incidente, "relacionados": incidente["relacionados"][1:]}
    assert "relacionados" not in publicar.sin_retenidos(solo, frozenset({"EODI-2025-00444"}))
    assert publicar.sin_retenidos(incidente, frozenset()) is incidente


def test_la_presencia_revisada_se_mantiene_si_el_extractor_cambia_de_frase() -> None:
    # Como EODI-2026-00515 el 20 de octubre de 2026: schwaebische.de da otra frase y una
    # declaración da el dron por confirmado.
    documento = tcf._nuremberg_alemana()
    documento["fuentes"][1]["frase_origen"] = "Mögliche Drohne stört Flugbetrieb"
    revision: dict[str, Any] = {
        "incidente": documento["id"],
        "presencia": {"valor": "no_confirmada", "cita": tcf.NO_HALLADO},
        "motivo": {"es": "x", "en": "x"},
    }
    instante = {"valor": "2026-10-20T00:17Z", "precision": "minuto"}
    # Sin el enlace no hay de dónde sacar la cita: no se aplica.
    assert revisados.con_titular(documento, revision, instante)["presencia_dron"] == "confirmada"
    revision["presencia"]["enlace"] = tcf.SCHWAEBISCHE
    nuevo = revisados.con_titular(documento, revision, instante)
    assert nuevo["presencia_dron"] == "no_confirmada"
    revisada = [f for f in nuevo["fuentes"] if f["frase_origen"] == tcf.NO_HALLADO]
    assert len(revisada) == 1 and revisada[0]["enlace"] == tcf.SCHWAEBISCHE
    afirmadas = [a for a in nuevo["afirmaciones"] if a["campo"] == "presencia_dron"]
    assert afirmadas == [{"campo": "presencia_dron", "valor": "no_confirmada",
                          "fuente_id": revisada[0]["id"], "confianza_extraccion": 1.0}]  # fmt: skip
    # Una segunda pasada no cambia nada ni añade otra fuente.
    assert revisados.con_titular(copy.deepcopy(nuevo), revision, instante) == nuevo


def test_la_revision_de_nuremberg_lleva_el_enlace_de_su_cita() -> None:
    revision = next(
        t for t in revisados.cargar()["titulares"] if t["incidente"] == "EODI-2026-00515"
    )
    assert revision["presencia"]["enlace"].startswith("https://schwaebische.de/")


def test_las_fichas_del_experto_sin_base_se_leen() -> None:
    # La respuesta del experto se lee como la del base (ficha.leer_respuesta).
    assert ficha.leer_respuesta(tm._respuesta(ficha_ejemplo(), tm.EXPERTO))
