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


def test_tope_diario_del_experto_y_reserva_critica() -> None:
    assert coste.LIMITE_EXPERTO_DIARIO_USD == 0.30
    assert coste.RESERVA_CRITICA_DIARIA_USD == 0.50
    assert coste.comprobar_experto(0.25, 0.04) is coste.Tramo.NORMAL
    with pytest.raises(coste.LimiteGasto):
        coste.comprobar_experto(0.28, 0.05)
    # Un caso crítico no espera: usa la reserva, hasta 0,80 USD en el día.
    assert coste.comprobar_experto(0.28, 0.05, critico=True) is coste.Tramo.RESERVA
    assert coste.comprobar_experto(0.2, 0.05, critico=True) is coste.Tramo.NORMAL
    with pytest.raises(coste.LimiteGasto):
        coste.comprobar_experto(0.78, 0.05, critico=True)
    assert coste.reparto_experto(0.23) == {"normal": 0.23, "reserva": 0.0}
    assert coste.reparto_experto(0.5) == {"normal": 0.3, "reserva": pytest.approx(0.2)}


def test_la_espera_del_critico_es_hasta_la_recogida_siguiente_y_la_normal_hasta_el_dia() -> None:
    assert coste.espera_experto(AHORA, critico=True) == (
        (AHORA + timedelta(minutes=50)).strftime("%Y-%m-%dT%H:%M:%SZ")
    )
    assert coste.espera_experto(AHORA, critico=False).endswith("T00:00:00Z")
    # Una espera anotada con un tope menor que el de ahora vence en cuanto el tope sube; con el
    # de ahora o uno mayor (el de 1,00 USD hasta el 19 de octubre de 2026), a su hora.
    assert coste.espera_vencida("2999-01-01T00:00:00Z", "2026-10-15T04:00:00Z", 0.10)
    assert not coste.espera_vencida("2999-01-01T00:00:00Z", "2026-10-15T04:00:00Z", None)
    assert not coste.espera_vencida("2999-01-01T00:00:00Z", "2026-10-15T04:00:00Z", 1.0)
    assert coste.espera_vencida("2026-10-15T03:00:00Z", "2026-10-15T04:00:00Z", 1.0)


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


def _gasto_experto(almacen: Almacen, dolares: float, modo: str = "control") -> None:
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


def test_sin_tope_ni_reserva_el_critico_se_reintenta_cada_recogida_y_no_bloquea_nada(
    almacen: Almacen,
) -> None:
    peticion = _peticion(almacen)
    _gasto_experto(almacen, coste.LIMITE_EXPERTO_DIARIO_USD + coste.RESERVA_CRITICA_DIARIA_USD)
    cliente = Cliente(ficha_ejemplo(**SIN_CITA), ficha_ejemplo())
    no_critica = ficha_ejemplo(
        cierre=campo("no", "Københavns Lufthavn var lukket"),
        presencia_dron=campo("no_confirmada", "observeret tre til fire store droner"),
    )
    otra = extraccion.Peticion(**{**peticion.__dict__, "candidato": {
        **peticion.candidato, "id": "otro"}})  # fmt: skip
    hechas = extraccion.extraer(almacen, cliente, [peticion], AHORA, coste.Modo.HORARIO, MODELOS)
    assert cliente.pedidas == [BASE]
    assert hechas.esperan == [peticion.candidato["id"]] and hechas.incidentes == []
    assert almacen.incidentes() == []
    espera = extraccion.esperan_experto(almacen)[peticion.candidato["id"]]
    assert espera["critico"] and espera["tope"] == coste.LIMITE_EXPERTO_DIARIO_USD
    assert extraccion.espera_experto(almacen, peticion.candidato["id"], AHORA)
    # No espera al día siguiente: vuelve en la recogida siguiente.
    assert not extraccion.espera_experto(
        almacen, peticion.candidato["id"], AHORA + timedelta(hours=1)
    )
    assert control_fichas.criticos_esperando(almacen)[0]["clave"] == peticion.candidato["id"]
    # Lo demás sigue: una ficha que no hay que escalar se publica.
    sencillo = Cliente(no_critica, ficha_ejemplo())
    otras = extraccion.extraer(almacen, sencillo, [otra], AHORA, coste.Modo.HORARIO, MODELOS)
    assert otras.incidentes and otras.incidentes[0] is not None
    # Al día siguiente se vuelve a intentar.
    manana = AHORA + timedelta(days=1)
    assert not extraccion.espera_experto(almacen, peticion.candidato["id"], manana)
    luego = extraccion.extraer(almacen, cliente, [peticion], manana, coste.Modo.HORARIO, MODELOS)
    assert luego.escalados == [peticion.candidato["id"]]
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


def test_sin_tope_del_experto_la_autoridad_citada_no_hace_esperar(almacen: Almacen) -> None:
    _gasto_experto(almacen, coste.LIMITE_EXPERTO_DIARIO_USD + coste.RESERVA_CRITICA_DIARIA_USD)
    peticion = _peticion_con(almacen, f"{TEXTO} {DICE_LA_POLICIA}")
    cliente = Cliente(ficha_ejemplo(**SIN_CIERRE), ficha_ejemplo(**SIN_CIERRE))
    hechas = extraccion.extraer(almacen, cliente, [peticion], AHORA, coste.Modo.HORARIO, MODELOS)
    # Vale la ficha del base, se publica y su llamada se anota una sola vez.
    assert cliente.pedidas == [BASE] and hechas.esperan == [] and hechas.escalados == []
    assert hechas.incidentes and hechas.incidentes[0] is not None
    assert peticion.candidato["id"] not in extraccion.esperan_experto(almacen)
    por_modelo = {f["modelo"]: f for f in almacen.llamadas_por_modelo("2000", "3000")}
    assert por_modelo[BASE]["llamadas"] == 1


def test_la_poca_seguridad_va_al_experto_al_ritmo_de_su_tope_y_si_no_vale_el_base(
    almacen: Almacen,
) -> None:
    dudosa = ficha_ejemplo(**SIN_CIERRE, pais=campo("DK", "Københavns Lufthavn", 0.5))
    peticion = _peticion(almacen)
    # A mediodía, con el experto por debajo de la mitad de su tope del día, la decide él.
    cliente = Cliente(dudosa, ficha_ejemplo(**SIN_CIERRE))
    hechas = extraccion.extraer(almacen, cliente, [peticion], AHORA, coste.Modo.HORARIO, MODELOS)
    assert cliente.pedidas == [BASE, EXPERTO] and hechas.escalados == [peticion.candidato["id"]]
    # Por encima del ritmo, vale la ficha del base: ni espera ni experto.
    _gasto_experto(almacen, 0.20, "horario")
    otra = extraccion.Peticion(**{**peticion.__dict__, "candidato": {
        **peticion.candidato, "id": "otro"}})  # fmt: skip
    cliente = Cliente(dudosa, ficha_ejemplo(**SIN_CIERRE))
    hechas = extraccion.extraer(almacen, cliente, [otra], AHORA, coste.Modo.HORARIO, MODELOS)
    assert cliente.pedidas == [BASE] and hechas.esperan == [] and hechas.escalados == []
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


def test_un_par_critico_sin_tope_ni_reserva_espera_y_retiene_la_ficha_nueva() -> None:
    almacen = _par_de_nuremberg_con_gasto(
        coste.LIMITE_EXPERTO_DIARIO_USD + coste.RESERVA_CRITICA_DIARIA_USD
    )
    servicio = ServicioControl("dudoso", "mismo")
    resultado = tcf._ejecutar(almacen, servicio, tcf.AHORA + timedelta(minutes=10))
    clave = "par:EODI-2026-09515|EODI-2026-09516"
    assert clave in resultado.esperan_experto
    decision = almacen.controles("par:")[clave]
    siguiente = (tcf.AHORA + timedelta(minutes=60)).strftime("%Y-%m-%dT%H:%M:%SZ")
    assert decision["decision"] == "dudoso" and decision["espera_experto"] == siguiente
    assert decision["critico"] and decision["tope_experto"] == coste.LIMITE_EXPERTO_DIARIO_USD
    assert clave in [c["clave"] for c in control_fichas.criticos_esperando(almacen)]
    # Pasadas 7 horas sigue retenida (no se publica mal) y el par no se da por distinto.
    tarde = tcf._ejecutar(almacen, None, tcf.AHORA + timedelta(hours=7))
    assert "EODI-2026-09516" in tarde.retenidos
    assert almacen.controles("par:")[clave]["decision"] == "dudoso"
    # Al día siguiente decide el experto y la ficha se une.
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


def test_el_resumen_dice_llamadas_escaladas_y_gasto_de_cada_modelo(tmp_path: Path) -> None:
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
    assert linea == (
        "  Modelos: modelo base 2 llamadas, 0,0300 USD; modelo experto 1 llamadas "
        "(1 escaladas), 0,0300 USD; total 0,0600 USD"
    )
    assert "proveedor" not in linea and "haiku" not in linea.lower()
    # El gasto del experto en su tope normal y en la reserva crítica, por día UTC. El tope normal
    # del 13 de octubre: su parte del mes (3,30 USD) entre los 19 días que quedaban.
    assert datos["experto"]["2026-10-13"] == {
        "normal": 0.03, "reserva": 0.0, "limite": pytest.approx(3.30 / 19, abs=1e-6),
        "reserva_limite": 0.5,
    }  # fmt: skip
    (experto,) = visitas.lineas_experto(control)
    assert experto == (
        "  Experto: tope normal 0,0300 de 0,17 USD; reserva crítica 0,0000 de 0,50 USD"
    )


def test_los_criticos_que_esperan_salen_en_el_resumen_y_a_las_6_horas_abren_incidencia(
    tmp_path: Path,
) -> None:
    from datetime import datetime

    from recogida import vigilancia

    control = {
        "experto": {"normal": 1.0, "reserva": 0.5, "limite": 1.0, "reserva_limite": 0.5},
        "criticos_esperando": [{"clave": "par:EODI-2026-00532|EODI-2026-00539",
                                "desde": "2026-10-15T00:17:01Z"}],
    }  # fmt: skip
    lineas = visitas.lineas_experto(control)
    assert lineas[1] == (
        "  Casos críticos esperando al experto: 1 (se reintentan en cada recogida)"
    )
    assert "EODI-2026-00532" in lineas[2]
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
