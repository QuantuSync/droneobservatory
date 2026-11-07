"""Gasto de la API (docs/modelos.md, «Gasto»): tope mensual repartido por modos, tope del experto
al ritmo del mes, lote del experto de madrugada, saldo agotado y avisos al responsable."""

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from almacen.base import Almacen
from modelo import cliente, coste
from recogida import control_fichas, gasto_api

BASE = "proveedor-haiku-5-5"
EXPERTO = "proveedor-sonnet-5-5"
AHORA = datetime(2026, 10, 20, 12, tzinfo=UTC)


@pytest.fixture(autouse=True)
def dos_modelos(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("EODI_MODELO_BASE", BASE)
    monkeypatch.setenv("EODI_MODELO_EXPERTO", EXPERTO)
    monkeypatch.setenv(gasto_api.VARIABLE_ESTADO, str(tmp_path / "gasto_api.json"))
    monkeypatch.setenv(cliente.VARIABLE_SALDO, str(tmp_path / "saldo_api.json"))
    monkeypatch.delenv(coste.VARIABLE_TOPE_MENSUAL, raising=False)


def _llamada(almacen: Almacen, fecha: str, dolares: float, modo: str = "horario",
             modelo: str = BASE, escalada: bool = False) -> None:  # fmt: skip
    almacen.registrar_llamada({
        "fecha": fecha, "modo": modo, "candidato": "x", "lote": False, "entrada": 0,
        "salida": 0, "escritura_cache": 0, "lectura_cache": 0, "coste": dolares,
        "modelo": modelo, "escalada": escalada,
    })  # fmt: skip


# --- Tope mensual ----------------------------------------------------------------------------


def test_el_reparto_del_mes_suma_el_tope() -> None:
    assert sum(coste.REPARTO_MENSUAL_USD.values()) == pytest.approx(coste.TOPE_MENSUAL_USD)
    assert coste.parte_del_mes(coste.EXPERTO) == pytest.approx(
        coste.REPARTO_MENSUAL_USD[coste.EXPERTO]
    )


def test_el_tope_del_experto_es_el_diario_al_principio_de_mes() -> None:
    almacen = Almacen.abrir()
    noviembre = datetime(2026, 11, 1, 0, 30, tzinfo=UTC)
    assert coste.tope_experto(coste.del_mes(almacen, noviembre, EXPERTO)) == pytest.approx(
        coste.LIMITE_EXPERTO_DIARIO_USD
    )
    assert coste.tope_experto(None) == coste.LIMITE_EXPERTO_DIARIO_USD


def test_el_tope_del_experto_del_resumen_baja_si_su_parte_va_deprisa_pero_no_frena() -> None:
    almacen = Almacen.abrir()
    parte = coste.parte_del_mes(coste.EXPERTO)
    minimo = coste.MINIMO_EXPERTO_DIARIO_USD
    # Sin gasto, el 20 de octubre (12 días con hoy): el límite diario entero.
    assert coste.tope_experto(coste.del_mes(almacen, AHORA, EXPERTO)) == pytest.approx(
        coste.LIMITE_EXPERTO_DIARIO_USD
    )
    # Gastado lo justo para que queden el mínimo de los 11 días siguientes y 0,50 para hoy.
    _llamada(almacen, "2026-10-05T10:00:00Z", parte - minimo * 12, "horario", EXPERTO, True)
    mes = coste.del_mes(almacen, AHORA, EXPERTO)
    assert coste.tope_experto(mes) == pytest.approx(minimo, abs=1e-6)
    # Más deprisa aún: queda poco, y el tope es lo que le toca de cada día que queda.
    _llamada(almacen, "2026-10-06T10:00:00Z", minimo * 12 - 1.20, "horario", EXPERTO, True)
    mes = coste.del_mes(almacen, AHORA, EXPERTO)
    assert mes.experto_antes == pytest.approx(parte - 1.20)
    assert coste.tope_experto(mes) == pytest.approx(1.20 / 12, abs=1e-6)
    # Desde el 7 de noviembre de 2026 ese tope solo se informa: no frena (solo el mensual).
    assert coste.comprobar_experto(0.09, 0.02, mes=mes) is coste.Tramo.NORMAL
    assert coste.comprobar_experto(0.09, 0.02, critico=True, mes=mes) is coste.Tramo.NORMAL


def test_con_el_tope_mensual_agotado_no_trabaja_nadie() -> None:
    # Desde el 7 de noviembre de 2026: al 100 % el trabajo nuevo se retiene, también el de la
    # recogida horaria y lo crítico (ya no hay reserva).
    almacen = Almacen.abrir()
    _llamada(almacen, "2026-10-03T10:00:00Z", coste.TOPE_MENSUAL_USD)
    mes = coste.del_mes(almacen, AHORA)
    assert coste.mes_agotado(mes)
    for modo in (coste.Modo.CONTROL, coste.Modo.GUERRA, coste.Modo.RECTIFICACIONES,
                 coste.Modo.HORARIO, coste.Modo.ENTRADA):  # fmt: skip
        with pytest.raises(coste.LimiteGasto):
            coste.comprobar(0.0, 0.001, modo, mes)
    with pytest.raises(coste.LimiteGasto):
        coste.comprobar_experto(0.0, 0.01, mes=mes)
    with pytest.raises(coste.LimiteGasto):
        coste.comprobar_experto(0.0, 0.01, critico=True, mes=mes)
    with pytest.raises(coste.LimiteGasto):
        coste.comprobar_al_ritmo(0.0, 0.001, AHORA, mes)
    with pytest.raises(coste.LimiteGasto):
        coste.comprobar_cupo(0.0, 0.001, coste.Modo.SEGUNDA_BUSQUEDA, mes)
    with pytest.raises(coste.LimiteGasto):
        coste.comprobar_control_experto(0.0, 0.001, mes)
    # El mes siguiente empieza de cero.
    noviembre = datetime(2026, 11, 2, 12, tzinfo=UTC)
    assert not coste.mes_agotado(coste.del_mes(almacen, noviembre))


def test_el_tope_mensual_se_cambia_por_entorno(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(coste.VARIABLE_TOPE_MENSUAL, "20")
    assert coste.tope_mensual() == 20.0
    assert coste.parte_del_mes(coste.EXPERTO) == pytest.approx(
        coste.REPARTO_MENSUAL_USD[coste.EXPERTO] * 20 / coste.TOPE_MENSUAL_USD
    )


def test_el_experto_del_control_cuenta_como_el_control_y_no_tiene_cupo_del_dia() -> None:
    almacen = Almacen.abrir()
    _llamada(almacen, "2026-10-20T01:57:00Z", 0.05, "control", EXPERTO, True)
    assert almacen.gastado_modelo(EXPERTO, "2026-10-20") == 0.0
    assert almacen.gastado_experto_en("control", "2026-10-20") == pytest.approx(0.05)
    # Desde el 7 de noviembre de 2026 su cupo del día ya no frena: solo el tope mensual.
    coste.comprobar_control_experto(0.05, coste.LIMITE_CONTROL_EXPERTO_DIARIO_USD)
    # Cuenta como el control en el mes, no como el experto.
    mes = coste.del_mes(almacen, datetime(2026, 10, 21, 12, tzinfo=UTC), EXPERTO)
    assert mes.experto_antes == 0.0 and mes.modos_antes["control"] == pytest.approx(0.05)


# --- Saldo agotado ---------------------------------------------------------------------------


def _cliente_con(codigo: int, cuerpo: dict[str, Any]) -> cliente.Cliente:
    config = cliente.Configuracion("k", "https://x/m", "https://x/l", BASE, {"x-key": "{clave}"})

    def transporte(*_: Any) -> cliente.Respuesta:
        return codigo, {}, json.dumps(cuerpo).encode()

    return cliente.Cliente(config, transporte, dormir=lambda s: None)


def test_el_saldo_agotado_es_un_limite_de_gasto_y_queda_anotado(tmp_path: Path) -> None:
    sin_saldo = _cliente_con(400, {"error": {
        "type": "invalid_request_error",
        "message": "Your credit balance is too low to access the API.",
    }})  # fmt: skip
    with pytest.raises(cliente.ErrorSaldo) as error:
        sin_saldo.mensaje({"messages": []})
    # Para como con el tope (sin otro código de salida) y sigue siendo un error definitivo.
    assert isinstance(error.value, coste.LimiteGasto)
    assert isinstance(error.value, cliente.ErrorDefinitivo)
    anotado = json.loads((tmp_path / "saldo_api.json").read_text(encoding="utf-8"))
    assert anotado["desde"] and "credit balance" in anotado["motivo"]
    with pytest.raises(cliente.ErrorSaldo):
        _cliente_con(402, {"error": {"type": "billing_error", "message": ""}}).mensaje({})
    # Otro error definitivo no es de saldo.
    with pytest.raises(cliente.ErrorDefinitivo) as otro:
        _cliente_con(400, {"error": {"type": "invalid_request_error", "message": "x"}}).mensaje({})
    assert not isinstance(otro.value, cliente.ErrorSaldo)


# --- Avisos ----------------------------------------------------------------------------------


class Avisos:
    def __init__(self) -> None:
        self.enviados: list[tuple[str, str]] = []

    def __call__(self, titulo: str) -> Any:
        return lambda texto: self.enviados.append((titulo, texto))


def test_avisos_al_80_y_al_100_una_vez_al_mes(monkeypatch: pytest.MonkeyPatch) -> None:
    # Con un tope de 60 USD (el de antes del 28 de octubre de 2026), por la variable.
    monkeypatch.setenv(coste.VARIABLE_TOPE_MENSUAL, "60")
    almacen = Almacen.abrir()
    avisos = Avisos()
    _llamada(almacen, "2026-10-03T10:00:00Z", 42.0)
    assert gasto_api.revisar(almacen, AHORA, avisos) == []
    _llamada(almacen, "2026-10-04T10:00:00Z", 9.0)
    assert gasto_api.revisar(almacen, AHORA, avisos) == [gasto_api.TITULO_80]
    assert gasto_api.revisar(almacen, AHORA, avisos) == []
    _llamada(almacen, "2026-10-05T10:00:00Z", 12.0)
    assert gasto_api.revisar(almacen, AHORA, avisos) == [gasto_api.TITULO_100]
    assert gasto_api.revisar(almacen, AHORA, avisos) == []
    assert "51.00 de 60.00" in avisos.enviados[0][1]
    # En noviembre, de cero.
    _llamada(almacen, "2026-11-02T10:00:00Z", 54.0)
    noviembre = datetime(2026, 11, 2, 12, tzinfo=UTC)
    assert gasto_api.revisar(almacen, noviembre, avisos) == [gasto_api.TITULO_80]


def test_un_tope_nuevo_vuelve_a_avisar_al_80(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # El 19 de octubre de 2026 el aviso del 80 % ya constaba con el tope de antes: a 48 de 60 USD
    # no habría avisado. Un estado sin «tope» (el de antes del 25 de octubre) cuenta como nuevo.
    monkeypatch.setenv(coste.VARIABLE_TOPE_MENSUAL, "60")
    almacen = Almacen.abrir()
    avisos = Avisos()
    (tmp_path / "gasto_api.json").write_text(
        json.dumps({"mes": coste.mes(AHORA), "aviso_80": True}), encoding="utf-8"
    )
    _llamada(almacen, "2026-10-03T10:00:00Z", 49.0)
    assert gasto_api.revisar(almacen, AHORA, avisos) == [gasto_api.TITULO_80]
    assert gasto_api.revisar(almacen, AHORA, avisos) == []
    # Sube el tope: con 49 de 80 no toca; al pasar del 80 % del nuevo, avisa otra vez.
    monkeypatch.setenv(coste.VARIABLE_TOPE_MENSUAL, "80")
    assert gasto_api.revisar(almacen, AHORA, avisos) == []
    _llamada(almacen, "2026-10-04T10:00:00Z", 16.0)
    assert gasto_api.revisar(almacen, AHORA, avisos) == [gasto_api.TITULO_80]
    assert json.loads((tmp_path / "gasto_api.json").read_text(encoding="utf-8"))["tope"] == 80.0


def test_saldo_agotado_un_aviso_por_episodio(tmp_path: Path) -> None:
    almacen = Almacen.abrir()
    avisos = Avisos()
    with pytest.raises(cliente.ErrorSaldo):
        _cliente_con(402, {"error": {"type": "billing_error", "message": "x"}}).mensaje({})
    assert gasto_api.revisar(almacen, AHORA, avisos) == [gasto_api.TITULO_SALDO]
    assert avisos.enviados[0][0] == "Saldo de la API agotado: recargar"
    assert gasto_api.revisar(almacen, AHORA, avisos) == []
    # Recargado: una llamada después cierra el episodio; el siguiente vuelve a avisar.
    _llamada(almacen, "2999-01-01T00:00:00Z", 0.001)
    assert gasto_api.revisar(almacen, AHORA, avisos) == []
    assert json.loads((tmp_path / "saldo_api.json").read_text(encoding="utf-8")) == {}


def test_sin_token_de_ntfy_no_se_avisa_ni_se_anota() -> None:
    almacen = Almacen.abrir()
    _llamada(almacen, "2026-10-03T10:00:00Z", 0.9 * coste.TOPE_MENSUAL_USD)
    assert gasto_api.revisar(almacen, AHORA, lambda titulo: None) == []
    assert gasto_api.revisar(almacen, AHORA, Avisos()) == [gasto_api.TITULO_80]


# --- Lote del experto de madrugada -------------------------------------------------------------


class Experto:
    """Experto falso con lotes que terminan en el acto."""

    modelo = EXPERTO

    def __init__(self) -> None:
        self.lotes: list[list[dict[str, Any]]] = []
        self.directas = 0

    def _respuesta(self) -> dict[str, Any]:
        texto = json.dumps(
            {
                "decision": "mismo",
                "mismo_dia": True,
                "mismo_sitio": True,
                "varios_sucesos": False,
                "motivo_es": "x",
                "motivo_en": "x",
            }
        )
        return {"model": EXPERTO, "stop_reason": "end_turn",
                "content": [{"type": "text", "text": texto}],
                "usage": {"input_tokens": 1000, "output_tokens": 100}}  # fmt: skip

    def mensaje(self, cuerpo: dict[str, Any]) -> dict[str, Any]:
        self.directas += 1
        return self._respuesta()

    def crear_lote(self, peticiones: list[dict[str, Any]]) -> dict[str, Any]:
        self.lotes.append(peticiones)
        return {"id": "lote-1", "processing_status": "ended"}

    def lote(self, id_: str) -> dict[str, Any]:
        return {"id": id_, "processing_status": "ended"}

    def resultados_lote(self, lote: dict[str, Any]) -> list[dict[str, Any]]:
        return [{"custom_id": p["custom_id"],
                 "result": {"type": "succeeded", "message": self._respuesta()}}
                for p in self.lotes[-1]]  # fmt: skip


def test_de_madrugada_lo_no_critico_va_al_lote_del_experto_y_lo_critico_directo() -> None:
    experto = Experto()
    servicio = type("Servicio", (), {"experto": lambda self: experto})()
    cuerpo = {"system": [], "messages": [{"role": "user", "content": "Ficha A: x"}],
              "max_tokens": 500}  # fmt: skip
    normal = control_fichas.Peticion("par", "par:A|B", cuerpo, 500, {})
    critico = control_fichas.Peticion("par", "par:C|D", cuerpo, 500, {"critico": True})
    respuestas = control_fichas.Respuestas()
    for peticion in (normal, critico):
        respuestas.leidas[peticion.clave] = {"decision": "dudoso"}
    control_fichas.escalar_lote(
        servicio, Almacen.abrir(), [normal, critico], respuestas, AHORA, coste.Modo.CONTROL,
        dormir=lambda s: None, reloj=lambda: 0.0,
    )  # fmt: skip
    assert experto.directas == 1 and len(experto.lotes) == 1 and len(experto.lotes[0]) == 1
    por_lote = {ll["candidato"]: ll["lote"] for ll in respuestas.llamadas_experto}
    assert por_lote == {"par:A|B": True, "par:C|D": False}
    assert respuestas.leidas["par:A|B"] == respuestas.leidas["par:C|D"]
    assert respuestas.leidas["par:A|B"] is not None


def test_la_segunda_busqueda_ya_no_tiene_cupo_del_dia_ni_parte_del_mes() -> None:
    almacen = Almacen.abrir()
    modo = coste.Modo.SEGUNDA_BUSQUEDA
    # Desde el 7 de noviembre de 2026 solo frena el tope mensual: ni su límite del día ni su parte
    # del mes.
    mes = coste.del_mes(almacen, AHORA, EXPERTO)
    coste.comprobar_cupo(coste.LIMITE_SEGUNDA_BUSQUEDA_DIARIO_USD, 0.06, modo, mes)
    gastado = coste.parte_del_mes(modo) + 1.0
    _llamada(almacen, "2026-10-05T10:00:00Z", gastado, modo.value, EXPERTO, True)
    mes = coste.del_mes(almacen, AHORA, EXPERTO)
    # Lo que gasta sigue sin contar como el experto.
    assert mes.experto_antes == 0.0
    assert mes.modos_antes[modo.value] == pytest.approx(gastado)
    coste.comprobar_cupo(0.0, 0.11, modo, mes)
    # Con el tope mensual casi agotado, para.
    with pytest.raises(coste.LimiteGasto):
        coste.comprobar_cupo(0.0, coste.TOPE_MENSUAL_USD - gastado + 0.01, modo, mes)


def test_el_aviso_del_100_llega_cuando_ya_no_cabe_una_llamada_grande() -> None:
    almacen = Almacen.abrir()
    avisos = Avisos()
    _llamada(almacen, "2026-10-03T10:00:00Z", coste.TOPE_MENSUAL_USD - coste.MARGEN_AVISO_100_USD)
    assert gasto_api.revisar(almacen, AHORA, avisos) == [gasto_api.TITULO_100]
    _, texto = avisos.enviados[0]
    assert "se retiene sin publicarse" in texto and "leída a medias" in texto
    assert gasto_api.revisar(almacen, AHORA, avisos) == []
