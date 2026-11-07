"""Dos modelos (docs/modelos.md): tarifas, peticiones adaptadas, reglas de escalado, tope del
experto, esperas, modelo por campo, lotes de citas y gasto por modelo en el resumen."""

import json
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest

from almacen.base import Almacen
from exportacion.citas import huella_texto
from modelo import coste, ficha, modelos
from proceso import escalado, extraccion
from recogida import control_fichas, visitas
from tests import test_control_fichas as tcf
from tests.ejemplos import VOCABULARIO_MODELOS as MODELOS_CONTROL
from tests.test_extraccion import (
    AHORA,
    MODELOS,
    TEXTO,
    a_servicio,
    campo,
    candidato_con_articulos,
    ficha_ejemplo,
)

BASE = "proveedor-haiku-5-5"
EXPERTO = "proveedor-sonnet-5-5"
ANTERIOR = "proveedor-haiku-4-5-20251001"
CUERPO = {
    "max_tokens": 1500,
    "temperature": 0.0,
    "system": [{"type": "text", "text": "x", "cache_control": {"type": "ephemeral"}}],
    "output_config": {"format": {"type": "json_schema", "schema": {}}, "effort": "medium"},
    "messages": [{"role": "user", "content": "y"}],
}


@pytest.fixture(autouse=True)
def dos_modelos(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EODI_MODELO_BASE", BASE)
    monkeypatch.setenv("EODI_MODELO_EXPERTO", EXPERTO)


# --- Tarifas y peticiones ------------------------------------------------------------------


def test_los_modelos_nuevos_no_llevan_temperatura_y_razonan_con_margen() -> None:
    nuevo = modelos.adaptar(CUERPO, BASE)
    assert "temperature" not in nuevo and nuevo["model"] == BASE
    assert nuevo["output_config"]["effort"] == "medium"
    assert nuevo["max_tokens"] == 1500 + 8000
    assert nuevo["system"][0]["cache_control"] == {"type": "ephemeral"}
    # La original no cambia.
    assert CUERPO["temperature"] == 0.0 and CUERPO["max_tokens"] == 1500


def test_el_experto_marca_la_cache_y_el_anterior_sigue_como_antes() -> None:
    # Desde el 19 de octubre de 2026 el experto también usa la caché (docs/modelos.md).
    experto = modelos.adaptar(CUERPO, EXPERTO)
    assert experto["system"][0]["cache_control"] == {"type": "ephemeral"}
    assert "temperature" not in experto
    assert experto["max_tokens"] == 1500 + 4000
    anterior = modelos.adaptar(CUERPO, ANTERIOR)
    assert anterior["temperature"] == 0.0 and "effort" not in anterior["output_config"]
    assert anterior["max_tokens"] == 1500
    assert anterior["system"][0]["cache_control"] == {"type": "ephemeral"}


def test_cada_llamada_se_cobra_con_la_tarifa_de_su_modelo() -> None:
    millon = 1_000_000
    assert modelos.coste(BASE, millon // 10, 0) == pytest.approx(0.01)
    assert modelos.coste(BASE, 0, millon) == pytest.approx(0.50)
    # Más de 100.000 tokens de entrada: toda la petición a la tarifa larga.
    assert modelos.coste(BASE, 200_000, 10_000) == pytest.approx(0.1 + 0.025)
    assert modelos.coste(EXPERTO, millon, millon) == pytest.approx(12.0)
    assert modelos.coste(EXPERTO, 0, 0, escritura_cache=millon) == pytest.approx(2.5)
    assert modelos.coste(EXPERTO, 0, 0, lectura_cache=millon) == pytest.approx(0.2)
    assert modelos.coste(ANTERIOR, millon, millon) == pytest.approx(6.0)
    assert modelos.coste(BASE, 0, millon, lote=True) == pytest.approx(0.25)
    uso = coste.Uso.de_mensaje(
        {"model": EXPERTO, "usage": {"input_tokens": 1000, "output_tokens": 1000}}
    )
    assert uso.coste() == pytest.approx(0.012)
    # Sin modelo en la respuesta, el base.
    assert coste.Uso(1000, 1000).coste() == pytest.approx(0.0006)


def test_el_peor_caso_cuenta_el_razonamiento_del_modelo() -> None:
    sin = coste.peor_caso(0, 1500, modelo=ANTERIOR)
    con = coste.peor_caso(0, 1500, modelo=BASE, esfuerzo="high")
    assert sin == pytest.approx(1500 * 5 / 1e6)
    assert con == pytest.approx((1500 + 12000) * 0.5 / 1e6)


def test_sin_tope_del_dia_solo_frena_el_tope_mensual(monkeypatch: pytest.MonkeyPatch) -> None:
    # Desde el 7 de noviembre de 2026 (modelo único): ni tope diario del experto ni reserva
    # crítica; lo gastado en el día no frena nada.
    assert coste.comprobar_experto(1.48, 0.05) is coste.Tramo.NORMAL
    assert coste.comprobar_experto(25.0, 0.05, critico=True) is coste.Tramo.NORMAL
    coste.comprobar_al_ritmo(25.0, 0.05, AHORA)
    coste.comprobar_segunda(25.0, 5.0, 0.05, AHORA)
    coste.comprobar_cupo(25.0, 0.05, coste.Modo.ENTRADA)
    coste.comprobar_control_experto(25.0, 0.05)
    coste.comprobar(25.0, 0.05, coste.Modo.HORARIO)
    # Con el mes agotado, nada pasa: tampoco lo crítico ni la recogida horaria.
    mes = coste.Mes(AHORA, total=149.99)
    with pytest.raises(coste.LimiteGasto):
        coste.comprobar_experto(0.0, 0.05, critico=True, mes=mes)
    with pytest.raises(coste.LimiteGasto):
        coste.comprobar(0.0, 0.05, coste.Modo.HORARIO, mes)
    with pytest.raises(coste.LimiteGasto):
        coste.comprobar_cupo(0.0, 0.05, coste.Modo.ENTRADA, mes)
    assert coste.comprobar_experto(0.0, 0.005, mes=mes) is coste.Tramo.NORMAL
    # El tope mensual lo cambia su variable.
    monkeypatch.setenv(coste.VARIABLE_TOPE_MENSUAL, "100")
    with pytest.raises(coste.LimiteGasto):
        coste.comprobar_experto(0.0, 0.05, mes=coste.Mes(AHORA, total=99.99))
    # Los trabajos de una sola vez conservan su presupuesto total.
    with pytest.raises(coste.LimiteGasto):
        coste.comprobar(coste.LIMITE_HISTORICO_USD, 0.05, coste.Modo.HISTORICO)
    assert coste.reparto_experto(0.23) == {"normal": 0.23, "reserva": 0.0}
    assert coste.reparto_experto(1.7) == {"normal": 1.5, "reserva": pytest.approx(0.2)}


def test_la_espera_del_critico_es_hasta_la_recogida_siguiente_y_la_normal_hasta_el_dia() -> None:
    assert coste.espera_experto(AHORA, critico=True) == (
        (AHORA + timedelta(minutes=50)).strftime("%Y-%m-%dT%H:%M:%SZ")
    )
    # La normal, hasta la misma hora del día siguiente (su tope ya se renovó a las 00:00 UTC).
    assert coste.espera_experto(AHORA, critico=False) == (
        (AHORA + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    )
    # Una espera anotada con un tope menor que el de ahora vence en cuanto el tope sube (las de
    # 0,30, 1,00 o 1,50 USD del tope diario del experto, de antes del modelo único del 7 de
    # noviembre de 2026, y las de antes del 15 de octubre sin tope); con el de ahora, a su hora.
    tope = coste.TOPE_ESPERA_USD
    assert coste.espera_vencida("2999-01-01T00:00:00Z", "2026-10-15T04:00:00Z", 0.10)
    assert coste.espera_vencida("2999-01-01T00:00:00Z", "2026-10-15T04:00:00Z", None)
    assert coste.espera_vencida("2999-01-01T00:00:00Z", "2026-10-15T04:00:00Z", 1.0)
    assert coste.espera_vencida("2999-01-01T00:00:00Z", "2026-11-07T04:00:00Z", 1.50)
    assert not coste.espera_vencida("2999-01-01T00:00:00Z", "2026-10-15T04:00:00Z", tope)
    assert coste.espera_vencida("2026-10-15T03:00:00Z", "2026-10-15T04:00:00Z", tope)


def test_dos_esperas_normales_de_horas_distintas_vencen_a_horas_distintas() -> None:
    # El 20 de octubre de 2026 todas las esperas vencían a las 00:00 y se comían el tope de la
    # madrugada.
    temprana = coste.espera_experto(AHORA.replace(hour=3, minute=17), critico=False)
    tardia = coste.espera_experto(AHORA.replace(hour=17, minute=17), critico=False)
    assert temprana != tardia
    assert temprana.endswith("T03:17:00Z") and tardia.endswith("T17:17:00Z")
    tope = coste.TOPE_ESPERA_USD
    entre = (AHORA + timedelta(days=1)).replace(hour=10).strftime("%Y-%m-%dT%H:%M:%SZ")
    assert coste.espera_vencida(temprana, entre, tope)
    assert not coste.espera_vencida(tardia, entre, tope)


def test_lo_critico_para_el_gasto_del_experto() -> None:
    assert escalado.es_critico(["publicada: EODI-2026-00001 retirada por «no es incidente»"])
    assert escalado.es_critico(["critico: dron confirmado"])
    assert escalado.es_critico(["contradiccion: presencia"])
    assert escalado.es_critico(["senal: hundimiento"])
    assert not escalado.es_critico(["poca_seguridad: drones"], ("Drone seen near a park",), "DE")
    # Víctimas, desaparecidos o daños en las fuentes.
    assert escalado.es_critico([], ("11 sailors missing as drones sink cargo ship",))
    # Una base militar en un país de la OTAN o en Moldavia, por su nombre o por su categoría.
    texto = ("Drone spotted over Mihail Kogălniceanu air base",)
    assert escalado.es_critico(["duplicado_dudoso: x"], texto, "RO")
    assert not escalado.es_critico(["duplicado_dudoso: x"], texto, "UA")
    assert escalado.es_critico([], (), "MD", "base_militar")
    # Las expresiones de «criticos» no escalan por sí solas un «no es incidente».
    no_es = {"es_incidente": {"valor": False, "confianza": 0.9}}
    assert escalado.motivos_senales(no_es, ("Exercise at Ramstein air base",)) == []


# --- Reglas de escalado ----------------------------------------------------------------------


def _leida(datos: dict[str, Any]) -> dict[str, Any]:
    return ficha.leer_respuesta(_respuesta(datos, BASE))


def _respuesta(datos: dict[str, Any], modelo: str) -> dict[str, Any]:
    return {
        "model": modelo, "stop_reason": "end_turn",
        "content": [{"type": "thinking", "thinking": ""},
                    {"type": "text", "text": json.dumps(a_servicio(datos), ensure_ascii=False)}],
        "usage": {"input_tokens": 1000, "output_tokens": 500},
    }  # fmt: skip


TEXTOS = (f"Droner over Københavns Lufthavn. {TEXTO}",)
# Un dato sin su frase en las fuentes: escala siempre (no es opcional).
SIN_CITA = {"drones": campo({"min": 2, "max": 2}, "mange droner over byen")}


def test_un_cierre_de_aeropuerto_es_critico() -> None:
    motivos = escalado.motivos_ficha(_leida(ficha_ejemplo()), TEXTOS)
    assert "critico: cierre de aeropuerto" in motivos


def test_lo_que_no_es_incidente_con_seguridad_no_se_escala() -> None:
    datos = ficha_ejemplo(es_incidente=campo(False, "Droner over", 0.95))
    assert escalado.motivos_ficha(_leida(datos), ("Droner over byen i aftes.",)) == []
    # Salvo con una señal de que lo es: aquí, el aeropuerto cerrado (tests/test_nada_se_retira.py).
    assert escalado.motivos_ficha(_leida(datos), TEXTOS) == ["senal: cierre_aeropuerto"]


def test_poca_seguridad_y_dato_sin_cita() -> None:
    datos = ficha_ejemplo(
        cierre=campo("no", "Københavns Lufthavn var lukket"),
        drones=campo({"min": 2, "max": 10}, "mange droner over byen", 0.5),
        pais=campo("DK", "Københavns Lufthavn", 0.5),
    )
    motivos = escalado.motivos_ficha(_leida(datos), TEXTOS)
    assert "poca_seguridad: pais" in motivos and "sin_cita: drones" in motivos
    # La poca seguridad del número de drones no escala (docs/modelos.md).
    assert "poca_seguridad: drones" not in motivos


def test_lo_critico_solo_no_escala_y_lo_opcional_va_al_ritmo() -> None:
    # Medido el 19 de octubre de 2026 con los 553 casos: lo crítico sin otro motivo no mejora la
    # ficha con el experto; marca el caso (la reserva) pero no lo escala.
    assert not escalado.escala(["critico: cierre de aeropuerto"])
    assert escalado.escala(["critico: cierre de aeropuerto", "sin_cita: drones"])
    assert escalado.opcionales(["poca_seguridad: tipo", "critico: incursión en PL"])
    assert not escalado.opcionales(["poca_seguridad: tipo", "sin_cita: lugar_suceso"])
    assert not escalado.opcionales(["critico: cierre de aeropuerto"])


def test_incursion_en_un_pais_de_la_otan_o_en_moldavia() -> None:
    for pais, critico in (("PL", True), ("MD", True), ("CH", False)):
        datos = ficha_ejemplo(
            tipo=campo("incursion", "Københavns Lufthavn"),
            pais=campo(pais, "Københavns Lufthavn"),
            cierre=campo("no", "Københavns Lufthavn"),
        )
        motivos = escalado.motivos_ficha(_leida(datos), TEXTOS)
        assert (f"critico: incursión en {pais}" in motivos) is critico


def test_la_comparacion_dudosa_o_incoherente_se_escala() -> None:
    assert escalado.motivos_comparacion({"decision": "dudoso"})
    assert escalado.motivos_comparacion(
        {"decision": "mismo", "mismo_dia": True, "mismo_sitio": False, "varios_sucesos": False}
    )
    assert not escalado.motivos_comparacion(
        {"decision": "distinto", "mismo_dia": False, "mismo_sitio": True, "varios_sucesos": False}
    )
    # Mismo día y mismo sitio, separados porque una fuente cita otro suceso: no está claro.
    assert escalado.motivos_comparacion(
        {"decision": "distinto", "mismo_dia": True, "mismo_sitio": True, "varios_sucesos": True}
    ) == ["duplicado_dudoso: mismo día y mismo sitio, pero separados"]


# --- Extracción con escalado ----------------------------------------------------------------


class Cliente:
    """Cliente falso con su experto: cada uno devuelve su ficha con su modelo."""

    def __init__(self, base: dict[str, Any], experto: dict[str, Any] | None) -> None:
        self.base, self.datos_experto = base, experto
        self.modelo = BASE
        self.pedidas: list[str] = []

    def mensaje(self, cuerpo: dict[str, Any]) -> dict[str, Any]:
        self.pedidas.append(self.modelo)
        return _respuesta(self.base, self.modelo)

    def experto(self) -> "Cliente | None":
        if self.datos_experto is None:
            return None
        otro = Cliente(self.datos_experto, None)
        otro.modelo = EXPERTO
        otro.pedidas = self.pedidas
        return otro


@pytest.fixture
def almacen() -> Any:
    a = Almacen.abrir()
    yield a
    a.cerrar()


def _peticion(almacen: Almacen) -> extraccion.Peticion:
    candidato = candidato_con_articulos(almacen)
    peticion = extraccion.preparar(almacen, candidato, None)
    return extraccion.Peticion(**{**peticion.__dict__, "fuentes": [
        ficha.FuenteTexto(f.medio, f.fecha, f.idioma, f.titular, TEXTO) for f in peticion.fuentes
    ]})  # fmt: skip


def test_si_se_escala_vale_la_ficha_del_experto_y_cada_dato_dice_su_modelo(
    almacen: Almacen,
) -> None:
    peticion = _peticion(almacen)
    experto = ficha_ejemplo(drones=campo({"min": 3, "max": 3}, "tre til fire store droner"))
    cliente = Cliente(ficha_ejemplo(**SIN_CITA), experto)
    hechas = extraccion.extraer(almacen, cliente, [peticion], AHORA, coste.Modo.HORARIO, MODELOS)
    assert cliente.pedidas == [BASE, EXPERTO]
    assert hechas.escalados == [peticion.candidato["id"]]
    (id_,) = hechas.incidentes
    incidente = almacen.incidente(str(id_))
    assert incidente is not None
    (extraida,) = almacen.extracciones(peticion.candidato["id"])
    assert extraida["campos"]["drones"]["valor"] == {"min": 3, "max": 3}
    assert set(incidente["control"]["modelos"].values()) == {EXPERTO}
    assert extraida["modelo"] == EXPERTO
    assert "critico: cierre de aeropuerto" in extraida["escalado"]
    por_modelo = {f["modelo"]: f for f in almacen.llamadas_por_modelo("2000", "3000")}
    assert por_modelo[BASE]["escaladas"] == 0 and por_modelo[EXPERTO]["escaladas"] == 1
    assert por_modelo[EXPERTO]["coste"] == pytest.approx(0.002 + 0.005)


def _gasto_experto(almacen: Almacen, dolares: float, modo: str = "horario") -> None:
    # El experto del control lleva su cupo propio (coste.comprobar_control_experto): el gasto que
    # cuenta contra su tope es el de los demás modos.
    almacen.registrar_llamada({
        "fecha": AHORA.strftime("%Y-%m-%dT%H:%M:%SZ"), "modo": modo, "candidato": "x",
        "lote": False, "entrada": 0, "salida": 0, "escritura_cache": 0, "lectura_cache": 0,
        "coste": dolares, "modelo": EXPERTO, "escalada": True,
    })  # fmt: skip


def test_el_experto_no_cuenta_contra_el_tope_de_la_recogida(almacen: Almacen) -> None:
    # El 14 de octubre de 2026 la recogida llevaba 0,26 de 0,30 USD y el experto no cabía en su
    # tope aunque él tenía margen: ahora su gasto va solo contra el suyo.
    _gasto_experto(almacen, 0.10, "horario")
    assert almacen.gastado("horario", AHORA.strftime("%Y-%m-%d")) == 0.0
    peticion = _peticion(almacen)
    cliente = Cliente(ficha_ejemplo(**SIN_CITA), ficha_ejemplo())
    hechas = extraccion.extraer(almacen, cliente, [peticion], AHORA, coste.Modo.HORARIO, MODELOS)
    assert cliente.pedidas == [BASE, EXPERTO] and hechas.esperan == []


def test_un_caso_critico_usa_la_reserva_cuando_el_tope_se_agota(almacen: Almacen) -> None:
    _gasto_experto(almacen, coste.LIMITE_EXPERTO_DIARIO_USD)
    peticion = _peticion(almacen)
    cliente = Cliente(ficha_ejemplo(**SIN_CITA), ficha_ejemplo())
    hechas = extraccion.extraer(almacen, cliente, [peticion], AHORA, coste.Modo.HORARIO, MODELOS)
    # El cierre de aeropuerto es crítico: no espera.
    assert cliente.pedidas == [BASE, EXPERTO]
    assert hechas.escalados == [peticion.candidato["id"]] and hechas.esperan == []


def test_con_el_mes_agotado_nada_se_llama_ni_lo_critico_y_el_candidato_se_retiene(
    almacen: Almacen, monkeypatch: pytest.MonkeyPatch,
) -> None:  # fmt: skip
    # Desde el 7 de noviembre de 2026 solo frena el tope mensual: al 100 % el trabajo nuevo se
    # retiene (sin ficha ni a medias) y se hace cuando vuelve a haber presupuesto.
    peticion = _peticion(almacen)
    monkeypatch.setenv(coste.VARIABLE_TOPE_MENSUAL, "0")
    cliente = Cliente(ficha_ejemplo(**SIN_CITA), ficha_ejemplo())
    hechas = extraccion.extraer(almacen, cliente, [peticion], AHORA, coste.Modo.HORARIO, MODELOS)
    assert cliente.pedidas == [] and hechas.incidentes == []
    assert hechas.parada is extraccion.Parada.LIMITE_GASTO
    assert almacen.incidentes() == [] and almacen.extracciones(peticion.candidato["id"]) == []
    # Un caso crítico que ya esperaba tampoco pasa: sigue esperando.
    extraccion.anotar_espera(almacen, peticion.candidato["id"], ["critico: x"], AHORA, False,
                             critico=True)  # fmt: skip
    despues = AHORA + timedelta(hours=1)
    otra = extraccion.extraer(almacen, cliente, [peticion], despues, coste.Modo.HORARIO, MODELOS)
    assert cliente.pedidas == [] and otra.incidentes == []
    assert peticion.candidato["id"] in extraccion.esperan_experto(almacen)
    # Con presupuesto otra vez, se extrae y se publica.
    monkeypatch.delenv(coste.VARIABLE_TOPE_MENSUAL)
    manana = AHORA + timedelta(days=1)
    luego = extraccion.extraer(almacen, cliente, [peticion], manana, coste.Modo.HORARIO, MODELOS)
    assert cliente.pedidas == [BASE, EXPERTO] and luego.escalados == [peticion.candidato["id"]]
    assert peticion.candidato["id"] not in extraccion.esperan_experto(almacen)


def test_sin_experto_configurado_no_se_escala(almacen: Almacen) -> None:
    peticion = _peticion(almacen)
    cliente = Cliente(ficha_ejemplo(), None)
    hechas = extraccion.extraer(almacen, cliente, [peticion], AHORA, coste.Modo.HORARIO, MODELOS)
    assert cliente.pedidas == [BASE] and hechas.incidentes[0] is not None
    incidente = almacen.incidente(str(hechas.incidentes[0]))
    assert incidente is not None and set(incidente["control"]["modelos"].values()) == {BASE}


# --- Una autoridad que habla en la noticia sin declaración en la ficha ----------------------

# Como en EODI-2026-00146 (Melilla, 22 de septiembre de 2026): la noticia cuenta lo que dijo la
# Delegación del Gobierno y la ficha del base no traía ninguna declaración.
DICE_LA_POLICIA = "Københavns Politi bekræfter, at der var droner over lufthavnen."
SIN_CIERRE = {
    "cierre": campo("no", "Københavns Lufthavn var lukket"),
    "presencia_dron": campo("no_confirmada", "observeret tre til fire store droner"),
}


def test_la_autoridad_que_habla_en_la_noticia_se_escala_si_la_ficha_no_trae_su_declaracion() -> (
    None
):
    textos = (f"{TEXTO} {DICE_LA_POLICIA}",)
    motivos = escalado.motivos_ficha(_leida(ficha_ejemplo(**SIN_CIERRE)), textos)
    assert motivos == ["declaracion: habla «politi» y la ficha no trae su declaración"]
    assert escalado.opcionales(motivos) and not escalado.es_critico(motivos)
    # En otras lenguas y con la autoridad del Gobierno en un territorio.
    for texto, autoridad in (
        ("La Delegación del Gobierno en Melilla reconoció los dos incidentes.",
         "delegacion del gobierno"),
        ("De Spaanse regeringsdelegatie in Melilla benadrukt dat de drone het luchtruim niet "
         "was binnengedrongen.", "regeringsdelegatie"),
        ("Ein Sprecher der Bundespolizei sagte, die Drohne sei verschwunden.", "bundespolizei"),
    ):  # fmt: skip
        assert escalado.autoridad_citada((texto,)) == autoridad
    # La autoridad y el verbo, en la misma frase; un testigo no es una autoridad.
    assert escalado.autoridad_citada(("The government. Witnesses said a drone flew.",)) is None
    assert escalado.autoridad_citada((TEXTO,)) is None


def test_con_su_declaracion_en_la_ficha_o_sin_suceso_no_se_escala_por_la_autoridad() -> None:
    textos = (f"{TEXTO} {DICE_LA_POLICIA}",)
    leida = _leida(ficha_ejemplo(**SIN_CIERRE))
    leida["declaraciones"] = [{"autoridad": "Københavns Politi", "afirma": "drones"}]
    assert not [m for m in escalado.motivos_ficha(leida, textos) if m.startswith("declaracion")]
    no_es = _leida(ficha_ejemplo(es_incidente=campo(False, "Droner over", 0.95)))
    assert escalado.motivos_ficha(no_es, ("Droner over byen i aftes.",)) == []


def _peticion_con(almacen: Almacen, texto: str) -> extraccion.Peticion:
    peticion = _peticion(almacen)
    return extraccion.Peticion(**{**peticion.__dict__, "fuentes": [
        ficha.FuenteTexto(f.medio, f.fecha, f.idioma, f.titular, texto) for f in peticion.fuentes
    ]})  # fmt: skip


def test_la_autoridad_citada_la_decide_el_experto_si_puede(almacen: Almacen) -> None:
    peticion = _peticion_con(almacen, f"{TEXTO} {DICE_LA_POLICIA}")
    cliente = Cliente(ficha_ejemplo(**SIN_CIERRE), ficha_ejemplo(**SIN_CIERRE))
    hechas = extraccion.extraer(almacen, cliente, [peticion], AHORA, coste.Modo.HORARIO, MODELOS)
    assert cliente.pedidas == [BASE, EXPERTO] and hechas.escalados == [peticion.candidato["id"]]
    (extraida,) = almacen.extracciones(peticion.candidato["id"])
    assert extraida["escalado"][0].startswith("declaracion")


def test_el_gasto_del_dia_no_frena_al_experto_con_la_autoridad_citada(almacen: Almacen) -> None:
    # Más de lo que eran el tope diario del experto y su reserva crítica: ya no frena (solo el tope
    # mensual, desde el 7 de noviembre de 2026).
    _gasto_experto(almacen, 2.5)
    peticion = _peticion_con(almacen, f"{TEXTO} {DICE_LA_POLICIA}")
    cliente = Cliente(ficha_ejemplo(**SIN_CIERRE), ficha_ejemplo(**SIN_CIERRE))
    hechas = extraccion.extraer(almacen, cliente, [peticion], AHORA, coste.Modo.HORARIO, MODELOS)
    assert cliente.pedidas == [BASE, EXPERTO] and hechas.esperan == []
    assert hechas.escalados == [peticion.candidato["id"]]
    assert hechas.incidentes and hechas.incidentes[0] is not None
    assert peticion.candidato["id"] not in extraccion.esperan_experto(almacen)


def test_la_poca_seguridad_va_al_experto_aunque_el_dia_vaya_gastado(almacen: Almacen) -> None:
    dudosa = ficha_ejemplo(**SIN_CIERRE, pais=campo("DK", "Københavns Lufthavn", 0.5))
    peticion = _peticion(almacen)
    cliente = Cliente(dudosa, ficha_ejemplo(**SIN_CIERRE))
    hechas = extraccion.extraer(almacen, cliente, [peticion], AHORA, coste.Modo.HORARIO, MODELOS)
    assert cliente.pedidas == [BASE, EXPERTO] and hechas.escalados == [peticion.candidato["id"]]
    # El antiguo margen de los escalados dentro del tope del día ya no existe: también la decide.
    _gasto_experto(almacen, 1.40, "horario")
    otra = extraccion.Peticion(**{**peticion.__dict__, "candidato": {
        **peticion.candidato, "id": "otro"}})  # fmt: skip
    cliente = Cliente(dudosa, ficha_ejemplo(**SIN_CIERRE))
    hechas = extraccion.extraer(almacen, cliente, [otra], AHORA, coste.Modo.HORARIO, MODELOS)
    assert cliente.pedidas == [BASE, EXPERTO] and hechas.esperan == []
    assert hechas.escalados == ["otro"]
    assert hechas.incidentes and hechas.incidentes[0] is not None


# --- Control: pares dudosos y esperas -------------------------------------------------------


class ServicioControl(tcf.Servicio):
    """El servicio falso del control con modelo y experto."""

    def __init__(self, decision: str, experto: str | None) -> None:
        super().__init__(decision)
        self.modelo = BASE
        self.decision_experto = experto

    def mensaje(self, cuerpo: dict[str, Any]) -> dict[str, Any]:
        respuesta = super().mensaje(cuerpo)
        return {**respuesta, "model": self.modelo}

    def experto(self) -> "ServicioControl | None":
        if self.decision_experto is None:
            return None
        otro = ServicioControl(self.decision_experto, None)
        otro.modelo = EXPERTO
        otro.pedidas = self.pedidas
        return otro


def test_un_par_dudoso_lo_decide_el_experto() -> None:
    almacen = tcf._base(tcf._nuremberg_alemana(), tcf._nuremberg_griega())
    servicio = ServicioControl("dudoso", "mismo")
    resultado = tcf._ejecutar(almacen, servicio, alcance="repaso")
    assert resultado.escaladas >= 1
    decision = almacen.controles("par:")["par:EODI-2026-09515|EODI-2026-09516"]
    assert decision["decision"] == "mismo" and decision["modelo"] == EXPERTO
    assert decision["escalado"] == ["duplicado_dudoso: el modelo base no lo sabe"]


def _par_de_nuremberg_con_gasto(dolares: float) -> Almacen:
    almacen = tcf._base(tcf._nuremberg_alemana())
    tcf._ejecutar(almacen, None)  # primera pasada: lo que había se da por visto
    almacen.guardar_incidente(tcf._nuremberg_griega(), tcf.AHORA, MODELOS_CONTROL)
    almacen.registrar_llamada({
        "fecha": tcf.AHORA.strftime("%Y-%m-%dT%H:%M:%SZ"), "modo": "horario", "candidato": "x",
        "lote": False, "entrada": 0, "salida": 0, "escritura_cache": 0, "lectura_cache": 0,
        "coste": dolares, "modelo": EXPERTO, "escalada": True,
    })  # fmt: skip
    return almacen


def test_un_par_critico_lo_decide_el_experto_con_la_reserva_sin_esperar() -> None:
    almacen = _par_de_nuremberg_con_gasto(coste.LIMITE_EXPERTO_DIARIO_USD)
    resultado = tcf._ejecutar(
        almacen, ServicioControl("dudoso", "mismo"), tcf.AHORA + timedelta(minutes=10)
    )
    assert resultado.esperan_experto == []
    assert almacen.controles("par:")["par:EODI-2026-09515|EODI-2026-09516"]["decision"] == "mismo"


def test_un_par_dudoso_espera_cuando_se_esperaba_con_el_tope_anterior() -> None:
    # Las esperas anotadas con un tope menor que el de ahora vencen al subir el tope.
    almacen = _par_de_nuremberg_con_gasto(0.0)
    clave = "par:EODI-2026-09515|EODI-2026-09516"
    almacen.guardar_controles({clave: {
        "decision": "dudoso", "huella": "x", "fecha": "2026-10-15T00:17:01Z",
        "desde": "2026-10-15T00:17:01Z", "espera_experto": "2999-01-01T00:00:00Z",
        "tope_experto": 0.10,
        "escalado": ["duplicado_dudoso: mismo día y mismo sitio, pero separados"],
    }}, "2026-10-15T00:17:01Z")  # fmt: skip
    tcf._ejecutar(almacen, ServicioControl("dudoso", "mismo"), tcf.AHORA + timedelta(minutes=10))
    assert almacen.controles("par:")[clave]["decision"] == "mismo"


def test_un_par_viejo_que_esperaba_vuelve_en_la_recogida_sin_esperar_a_la_madrugada() -> None:
    # Las dos fichas ya vistas (no son nuevas en la recogida horaria) y su par esperando al
    # experto desde la pasada de madrugada, con el tope de antes.
    almacen = tcf._base(tcf._nuremberg_alemana(), tcf._nuremberg_griega())
    tcf._ejecutar(almacen, ServicioControl("distinto", None))
    tcf._ejecutar(almacen, ServicioControl("distinto", None), tcf.AHORA + timedelta(hours=1))
    clave = "par:EODI-2026-09515|EODI-2026-09516"
    almacen.guardar_controles({clave: {
        "decision": "dudoso", "huella": "x", "fecha": "2026-10-15T01:50:07Z",
        "desde": "2026-10-15T01:50:07Z", "espera_experto": "2999-01-01T00:00:00Z",
        "tope_experto": 0.10, "escalado": ["duplicado_dudoso: el modelo base no lo sabe"],
    }}, "2026-10-15T01:50:07Z")  # fmt: skip
    tarde = tcf.AHORA + timedelta(hours=30)
    tcf._ejecutar(almacen, ServicioControl("dudoso", "mismo"), tarde)
    assert almacen.controles("par:")[clave]["decision"] == "mismo"


def test_un_par_critico_con_el_mes_agotado_espera_y_retiene_la_ficha_nueva(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Desde el 7 de noviembre de 2026 no hay reserva crítica: con el tope mensual agotado
    # tampoco pasa lo crítico; el par espera y la ficha nueva sigue retenida.
    almacen = _par_de_nuremberg_con_gasto(0.0)
    monkeypatch.setenv(coste.VARIABLE_TOPE_MENSUAL, "0")
    servicio = ServicioControl("dudoso", "mismo")
    resultado = tcf._ejecutar(almacen, servicio, tcf.AHORA + timedelta(minutes=10))
    clave = "par:EODI-2026-09515|EODI-2026-09516"
    # Pasadas 7 horas sigue retenida (no se publica mal) y el par no se da por distinto.
    tarde = tcf._ejecutar(almacen, None, tcf.AHORA + timedelta(hours=7))
    assert "EODI-2026-09516" in tarde.retenidos
    assert almacen.controles("par:").get(clave, {}).get("decision") in (None, "dudoso")
    assert resultado.escaladas == 0
    # Con presupuesto otra vez, decide y la ficha se une.
    monkeypatch.delenv(coste.VARIABLE_TOPE_MENSUAL)
    manana = tcf.AHORA + timedelta(days=1)
    tcf._ejecutar(almacen, ServicioControl("dudoso", "mismo"), manana)
    assert almacen.controles("par:")[clave]["decision"] == "mismo"


# --- Citas de cada hora por lote --------------------------------------------------------------


def test_las_citas_nuevas_van_en_un_lote_que_recoge_la_recogida_siguiente() -> None:
    almacen = tcf._base(tcf._nuremberg_alemana())
    servicio = tcf.ServicioLotes()
    tcf._ejecutar(almacen, servicio)
    assert servicio.lotes and control_fichas.lotes_pendientes(almacen)
    assert huella_texto(tcf.NO_HALLADO) not in almacen.traducciones()
    tcf._ejecutar(almacen, servicio, tcf.AHORA + timedelta(hours=1))
    assert control_fichas.lotes_pendientes(almacen) == []
    assert almacen.traducciones()
    assert any(ll["lote"] and ll["modo"] == "control" for ll in almacen.llamadas())


# --- Resumen de las 08:00 -------------------------------------------------------------------


def test_el_resumen_dice_llamadas_y_gasto_de_cada_modelo(tmp_path: Path) -> None:
    almacen = Almacen.abrir()
    for modelo, escalada, gasto in ((BASE, False, 0.01), (BASE, False, 0.02),
                                    (EXPERTO, True, 0.03)):  # fmt: skip
        almacen.registrar_llamada({
            "fecha": "2026-10-13T10:00:00Z", "modo": "horario", "candidato": "x", "lote": False,
            "entrada": 0, "salida": 0, "escritura_cache": 0, "lectura_cache": 0, "coste": gasto,
            "modelo": modelo, "escalada": escalada,
        })  # fmt: skip
    ruta = tmp_path / "control.json"
    control_fichas.escribir_estado(ruta, control_fichas.Resultado(), almacen, tcf.AHORA)
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    assert datos["modelos"]["2026-10-13"]["experto"] == {
        "llamadas": 1,
        "escaladas": 1,
        "coste": 0.03,
    }
    control = visitas.control_del_dia(ruta, tcf.AHORA.date())
    assert control is not None
    (linea,) = visitas.lineas_modelos(control["modelos"])
    # Sin las líneas del escalado ni del experto (desde el 7 de noviembre de 2026).
    assert linea == (
        "  Modelos: modelo base 2 llamadas, 0,0300 USD; modelo experto 1 llamadas, "
        "0,0300 USD; total 0,0600 USD"
    )
    assert not hasattr(visitas, "lineas_experto")
    assert "proveedor" not in linea and "haiku" not in linea.lower()
    # El gasto del experto en su tope normal y en la reserva crítica, por día UTC. El tope normal
    # del 13 de octubre: el diario, porque su parte del mes da de sobra para los días que quedan.
    assert datos["experto"]["2026-10-13"] == {
        "normal": 0.03, "reserva": 0.0,
        "limite": pytest.approx(coste.LIMITE_EXPERTO_DIARIO_USD, abs=1e-6), "reserva_limite": 0.5,
    }  # fmt: skip


def test_los_criticos_que_esperan_a_las_6_horas_abren_incidencia(tmp_path: Path) -> None:
    from datetime import datetime

    from recogida import vigilancia

    control = {
        "experto": {"normal": 1.0, "reserva": 0.5, "limite": 1.0, "reserva_limite": 0.5},
        "criticos_esperando": [{"clave": "par:EODI-2026-00532|EODI-2026-00539",
                                "desde": "2026-10-15T00:17:01Z"}],
    }  # fmt: skip
    temprano = datetime.fromisoformat("2026-10-15T05:00:00+00:00")
    assert vigilancia.problemas_del_experto(control, temprano) == []
    tarde = datetime.fromisoformat("2026-10-15T06:30:00+00:00")
    (problema,) = vigilancia.problemas_del_experto(control, tarde)
    assert problema["id"] == "experto_critico" and "EODI" not in problema["frase"]


def test_sin_modelos_configurados_todo_es_el_modelo_anterior(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("EODI_MODELO_BASE")
    monkeypatch.delenv("EODI_MODELO_EXPERTO")
    monkeypatch.setenv("EODI_EXTRACTOR_MODELO", ANTERIOR)
    assert modelos.base() == ANTERIOR and modelos.experto() == ""
    assert control_fichas.papel(ANTERIOR) == "base"


# --- Un solo modelo (desde el 7 de noviembre de 2026) ----------------------------------------


def test_con_el_modelo_unico_base_y_experto_son_el_mismo_y_nada_se_escala(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Con dos modelos distintos (Haiku de base y Sonnet de experto), se escala.
    assert modelos.escala(BASE) and modelos.escala(None)
    assert not modelos.escala(EXPERTO)
    monkeypatch.setenv("EODI_MODELO", EXPERTO)
    assert modelos.base() == EXPERTO and modelos.experto() == EXPERTO
    assert modelos.extraccion() == EXPERTO
    assert not modelos.escala(EXPERTO) and not modelos.escala(None)
    assert control_fichas.papel(EXPERTO) == "unico"


def test_el_interruptor_devuelve_la_extraccion_al_modelo_base_de_antes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("EODI_MODELO", EXPERTO)
    monkeypatch.setenv("EODI_EXTRACCION_HAIKU", "1")
    assert modelos.extraccion() == BASE
    # Lo demás sigue con el modelo único, y la extracción con Haiku escala como antes.
    assert modelos.base() == EXPERTO and modelos.escala(BASE)
    monkeypatch.setenv("EODI_EXTRACCION_HAIKU", "0")
    assert modelos.extraccion() == EXPERTO


def test_con_el_modelo_unico_la_extraccion_no_repite_la_llamada(
    almacen: Almacen, monkeypatch: pytest.MonkeyPatch,
) -> None:  # fmt: skip
    monkeypatch.setenv("EODI_MODELO", EXPERTO)
    peticion = _peticion(almacen)
    # Una ficha que con dos modelos se escalaría (una frase que no está en su fuente).
    cliente = Cliente(ficha_ejemplo(**SIN_CITA), ficha_ejemplo())
    cliente.modelo = EXPERTO
    hechas = extraccion.extraer(almacen, cliente, [peticion], AHORA, coste.Modo.HORARIO, MODELOS)
    assert cliente.pedidas == [EXPERTO]
    assert hechas.escalados == [] and hechas.esperan == []
    (extraida,) = almacen.extracciones(peticion.candidato["id"])
    assert extraida["modelo"] == EXPERTO and "escalado" not in extraida
    por_modelo = {f["modelo"]: f for f in almacen.llamadas_por_modelo("2000", "3000")}
    assert por_modelo[EXPERTO]["llamadas"] == 1 and por_modelo[EXPERTO]["escaladas"] == 0
