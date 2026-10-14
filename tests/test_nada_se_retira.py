"""Nada publicado se retira ni se rebaja sin el experto, y un «no es incidente» con señales de
que lo es se escala aunque el modelo base esté seguro (docs/modelos.md)."""

from datetime import timedelta
from typing import Any

import pytest

from almacen.base import Almacen
from modelo import coste, ficha
from modelo.cliente import LlamadaFallida
from proceso import escalado, extraccion
from tests import test_control_fichas as tcf
from tests.test_extraccion import AHORA, MODELOS, TEXTO, campo, ficha_ejemplo
from tests.test_modelos import BASE, EXPERTO, Cliente, ServicioControl, _leida, _peticion

# EODI-2026-00489: el ataque con drones del 6 de octubre de 2026 a dos buques en la zona
# económica exclusiva de Bulgaria. El modelo base lo dio, con seguridad, por «no es incidente».
BIALA = (
    "Drone strikes hit two ships off Bulgaria. A cargo ship has sunk and a second vessel has "
    "caught fire after drone strikes in Bulgaria's exclusive economic zone. Two crew members "
    "are missing.",
    "След ударите с дронове на два търговски кораба в Изключителната икономическа зона "
    "един от тях потъна, а двама моряци са в неизвестност.",
)
NO_ES = {"es_incidente": campo(False, "Drone strikes hit two ships", 0.8)}


def _no_es(**cambios: Any) -> dict[str, Any]:
    return ficha_ejemplo(**(NO_ES | cambios))


def _gastado_el_experto(almacen: Almacen, cuando: str = "2025-09-24T01:00:00Z") -> None:
    almacen.registrar_llamada({
        "fecha": cuando, "modo": "control", "candidato": "x", "lote": False,
        "entrada": 0, "salida": 0, "escritura_cache": 0, "lectura_cache": 0,
        "coste": coste.LIMITE_EXPERTO_DIARIO_USD, "modelo": EXPERTO, "escalada": True,
    })  # fmt: skip


class ExpertoCaido(Cliente):
    """El experto da error."""

    def experto(self) -> "Cliente | None":
        otro = super().experto()

        def falla(cuerpo: dict[str, Any]) -> dict[str, Any]:
            raise LlamadaFallida("experto caído")

        if otro is not None:
            otro.mensaje = falla  # type: ignore[method-assign]
        return otro


@pytest.fixture(autouse=True)
def dos_modelos(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EODI_MODELO_BASE", BASE)
    monkeypatch.setenv("EODI_MODELO_EXPERTO", EXPERTO)


@pytest.fixture
def almacen() -> Any:
    a = Almacen.abrir()
    yield a
    a.cerrar()


def _publicada(almacen: Almacen) -> tuple[extraccion.Peticion, str]:
    """Un candidato con su ficha publicada (la decidió el experto: es un cierre)."""
    peticion = _peticion(almacen)
    cliente = Cliente(ficha_ejemplo(), ficha_ejemplo(presencia_dron=campo(
        "confirmada", "observeret tre til fire store droner")))  # fmt: skip
    hechas = extraccion.extraer(almacen, cliente, [peticion], AHORA, coste.Modo.HORARIO, MODELOS)
    (id_,) = hechas.incidentes
    assert id_ is not None
    incidente = almacen.incidente(id_)
    assert incidente is not None and incidente["presencia_dron"] == "confirmada"
    return peticion, id_


def _sigue_publicada(almacen: Almacen, id_: str, presencia: str = "confirmada") -> None:
    incidente = almacen.incidente(id_)
    assert incidente is not None
    assert "retirado" not in incidente and incidente["presencia_dron"] == presencia


# --- La 00489 y las señales --------------------------------------------------------------------


def test_la_00489_se_escala_aunque_el_base_este_seguro() -> None:
    motivos = escalado.motivos_ficha(_leida(_no_es()), BIALA)
    assert {"senal: hundimiento", "senal: desaparecidos"} <= set(motivos)


def test_la_00489_la_decide_el_experto_y_se_publica(almacen: Almacen) -> None:
    peticion = _peticion(almacen)
    peticion = extraccion.Peticion(**{**peticion.__dict__, "fuentes": [
        ficha.FuenteTexto(f.medio, f.fecha, f.idioma, f.titular, f"{BIALA[0]} {TEXTO}")
        for f in peticion.fuentes
    ]})  # fmt: skip
    cliente = Cliente(_no_es(), ficha_ejemplo())
    hechas = extraccion.extraer(almacen, cliente, [peticion], AHORA, coste.Modo.HORARIO, MODELOS)
    assert cliente.pedidas == [BASE, EXPERTO]
    assert hechas.escalados == [peticion.candidato["id"]] and hechas.incidentes[0] is not None
    (extraida,) = almacen.extracciones(peticion.candidato["id"])
    assert "senal: hundimiento" in extraida["escalado"]


@pytest.mark.parametrize(
    ("senal", "texto"),
    [
        ("hundimiento", "Un pesquero se hundió tras el impacto de un dron."),
        ("victimas", "Zwei Todesopfer nach dem Drohnenangriff auf den Hafen."),
        ("victimas", "Двама загинали след атаката с дрон."),
        ("desaparecidos", "Trois marins sont portés disparus après l'attaque d'un drone."),
        ("heridos", "Doi oameni au fost răniți de resturile unei drone."),
        ("heridos", "Three people were injured by drone debris."),
        ("danos", "Dron uszkodził dach budynku w Przewodowie."),
        ("danos", "Drone debris damaged a warehouse near the port."),
        ("cierre_aeropuerto", "Lotnisko w Rzeszowie zamknięte z powodu drona."),
        ("cierre_aeropuerto", "Flughafen München geschlossen nach Drohnensichtung."),
        ("cierre_aeropuerto", "The airport was closed for two hours after a drone sighting."),
        ("incursion", "Drona a încălcat spațiul aerian al României."),
        ("incursion", "A Russian drone violated Polish airspace overnight."),
        ("incursion", "Нарушение на въздушното пространство от дрон."),
    ],
)
def test_cada_senal_escala_un_no_es_incidente(senal: str, texto: str) -> None:
    motivos = escalado.motivos_ficha(_leida(_no_es()), (texto,))
    assert f"senal: {senal}" in motivos


def test_una_fuente_oficial_escala_un_no_es_incidente() -> None:
    assert escalado.fuente_oficial("mon.gov.pl", "https://www.gov.pl/web/obrona-narodowa/x")
    assert escalado.fuente_oficial("Københavns Politi", "https://via.ritzau.dk/x")
    assert escalado.fuente_oficial("mapn.ro", "https://www.mapn.ro/cpresa/x")
    assert not escalado.fuente_oficial("novinite.com", "https://www.novinite.com/articles/1")
    texto = ("Ein Drohnenflug über dem Gelände wurde gemeldet.",)
    assert escalado.motivos_ficha(_leida(_no_es()), texto, oficial=True) == [
        "senal: fuente oficial"
    ]


def test_sin_senales_un_no_es_incidente_seguro_no_se_escala() -> None:
    texto = ("Ein Hobbypilot ließ seine Drohne über dem Stadtpark fliegen; alles blieb ruhig.",)
    assert escalado.motivos_ficha(_leida(_no_es()), texto) == []


# --- Una ficha publicada no se retira ni se rebaja sin el experto ------------------------------


def test_retirar_una_ficha_publicada_lo_decide_el_experto(almacen: Almacen) -> None:
    peticion, id_ = _publicada(almacen)
    cliente = Cliente(_no_es(), _no_es())
    hechas = extraccion.extraer(almacen, cliente, [peticion], AHORA, coste.Modo.HORARIO, MODELOS)
    assert cliente.pedidas == [BASE, EXPERTO] and hechas.escalados
    extraida = almacen.extracciones(peticion.candidato["id"])[-1]
    assert f"publicada: {id_} retirada por «no es incidente»" in extraida["escalado"]
    incidente = almacen.incidente(id_)
    assert incidente is not None and "retirado" in incidente


@pytest.mark.parametrize("caso", ["tope", "fallo"])
def test_sin_experto_la_ficha_publicada_se_queda_como_estaba(almacen: Almacen, caso: str) -> None:
    peticion, id_ = _publicada(almacen)
    if caso == "tope":
        _gastado_el_experto(almacen)
        cliente: Cliente = Cliente(_no_es(), _no_es())
    else:
        cliente = ExpertoCaido(_no_es(), _no_es())
    hechas = extraccion.extraer(almacen, cliente, [peticion], AHORA, coste.Modo.HORARIO, MODELOS)
    assert hechas.esperan == [peticion.candidato["id"]]
    _sigue_publicada(almacen, id_)
    espera = extraccion.esperan_experto(almacen)[peticion.candidato["id"]]
    assert espera["por"] == caso
    assert f"publicada: {id_} retirada por «no es incidente»" in espera["motivos"]


def test_rebajar_la_presencia_de_una_ficha_publicada_se_escala(almacen: Almacen) -> None:
    peticion, id_ = _publicada(almacen)
    _gastado_el_experto(almacen)
    rebaja = ficha_ejemplo(
        cierre=campo("no", "Københavns Lufthavn var lukket"),
        presencia_dron=campo("descartada", "observeret tre til fire"),
    )
    motivos = escalado.motivos_ficha(_leida(rebaja), (peticion.fuentes[0].texto,),
                                     publicada=almacen.incidente(id_))  # fmt: skip
    assert f"publicada: {id_} rebaja la presencia (confirmada -> descartada)" in motivos
    assert f"publicada: {id_} pierde el cierre" in motivos
    extraccion.extraer(almacen, Cliente(rebaja, rebaja), [peticion], AHORA, coste.Modo.HORARIO,
                       MODELOS)  # fmt: skip
    _sigue_publicada(almacen, id_)


def test_un_lote_del_base_no_retira_y_el_candidato_se_repite_con_el_experto(
    almacen: Almacen,
) -> None:
    peticion, id_ = _publicada(almacen)
    # La respuesta de un lote es del base y llega sin escalar.
    extraccion.procesar_respuesta(
        almacen, peticion, {**_respuesta_base(_no_es())}, AHORA, coste.Modo.HISTORICO, True,
        MODELOS,
    )  # fmt: skip
    _sigue_publicada(almacen, id_)
    ultima = almacen.extracciones(peticion.candidato["id"])[-1]
    assert "ficha" not in ultima and "ficha_base" in ultima and ultima["incidente"] == id_
    assert extraccion.necesita_extraccion(almacen, peticion.candidato)
    # Una reconstrucción no lee la ficha del base: la publicada sigue.
    extraccion.reconstruir(almacen, AHORA, MODELOS)
    _sigue_publicada(almacen, id_)
    # En la recogida siguiente se escala siempre, aunque el base diga ya otra cosa.
    luego = AHORA + timedelta(hours=1)
    cliente = Cliente(ficha_ejemplo(), _no_es())
    hechas = extraccion.extraer(almacen, cliente, [peticion], luego, coste.Modo.HORARIO, MODELOS)
    assert cliente.pedidas == [BASE, EXPERTO] and hechas.escalados
    incidente = almacen.incidente(id_)
    assert incidente is not None and "retirado" in incidente
    assert peticion.candidato["id"] not in extraccion.esperan_experto(almacen)


def test_una_ficha_del_base_que_no_valida_no_retira_la_publicada(almacen: Almacen) -> None:
    peticion, id_ = _publicada(almacen)
    sin_pais = ficha_ejemplo(
        pais=campo(None),
        lugar_suceso=campo(None),
        presencia_dron=campo("confirmada", "observeret tre til fire store droner"),
    )
    extraccion.procesar_respuesta(
        almacen, peticion, _respuesta_base(sin_pais), AHORA, coste.Modo.HISTORICO, True, MODELOS
    )
    _sigue_publicada(almacen, id_)
    ultima = almacen.extracciones(peticion.candidato["id"])[-1]
    assert ultima["conservada"][0].startswith(f"publicada: {id_} retirada")


def test_sin_experto_configurado_todo_sigue_como_antes(
    almacen: Almacen, monkeypatch: pytest.MonkeyPatch
) -> None:
    peticion, id_ = _publicada(almacen)
    monkeypatch.delenv("EODI_MODELO_EXPERTO")
    extraccion.procesar_respuesta(
        almacen, peticion, _respuesta_base(_no_es()), AHORA, coste.Modo.HISTORICO, True, MODELOS
    )
    incidente = almacen.incidente(id_)
    assert incidente is not None and "retirado" in incidente


def _respuesta_base(datos: dict[str, Any]) -> dict[str, Any]:
    from tests.test_modelos import _respuesta

    return _respuesta(datos, BASE)


# --- Control: una unión que retira una ficha publicada -----------------------------------------


def test_unir_dos_fichas_publicadas_lo_decide_el_experto() -> None:
    almacen = tcf._base(tcf._nuremberg_alemana(), tcf._nuremberg_griega())
    tcf._ejecutar(almacen, None)  # primera pasada: las dos quedan publicadas
    servicio = ServicioControl("mismo", "mismo")
    tcf._ejecutar(almacen, servicio, tcf.AHORA + timedelta(minutes=10), alcance="repaso")
    decision = almacen.controles("par:")["par:EODI-2026-09515|EODI-2026-09516"]
    assert decision["decision"] == "mismo" and decision["modelo"] == EXPERTO
    assert decision["escalado"] == ["publicada: la unión retira EODI-2026-09516"]


def test_sin_tope_del_experto_las_dos_fichas_publicadas_siguen() -> None:
    almacen = tcf._base(tcf._nuremberg_alemana(), tcf._nuremberg_griega())
    tcf._ejecutar(almacen, None)
    _gastado_el_experto(almacen, tcf.AHORA.strftime("%Y-%m-%dT%H:%M:%SZ"))
    resultado = tcf._ejecutar(almacen, ServicioControl("mismo", "mismo"),
                              tcf.AHORA + timedelta(minutes=10), alcance="repaso")  # fmt: skip
    clave = "par:EODI-2026-09515|EODI-2026-09516"
    assert clave in resultado.esperan_experto and not resultado.unidos
    assert almacen.controles("par:")[clave]["decision"] == "dudoso"
    for id_ in ("EODI-2026-09515", "EODI-2026-09516"):
        incidente = almacen.incidente(id_)
        assert incidente is not None and "fusionado_en" not in incidente


# --- Revisión, una sola vez, de las decisiones del base -----------------------------------------


def test_las_decisiones_del_base_se_repasan_una_vez_con_las_reglas_nuevas(
    almacen: Almacen,
) -> None:
    peticion = _peticion(almacen)
    # El base lo dio por «no es incidente» con seguridad, sin escalar, antes de la regla nueva.
    extraccion.procesar_respuesta(
        almacen, peticion, _respuesta_base(_no_es()), AHORA, coste.Modo.HORARIO, False, MODELOS
    )
    candidato_id = peticion.candidato["id"]
    assert not extraccion.necesita_extraccion(almacen, peticion.candidato)
    # Su titular habla del cierre del aeropuerto («lufthavnen lukket»).
    marcados = extraccion.revisar_decisiones_base(almacen, None, AHORA, desde="2000-01-01")
    assert marcados == [candidato_id]
    assert extraccion.esperan_experto(almacen)[candidato_id]["motivos"] == [
        "senal: cierre_aeropuerto"
    ]
    assert candidato_id in extraccion.en_revision(almacen)
    assert extraccion.necesita_extraccion(almacen, peticion.candidato)
    assert not extraccion.espera_experto(almacen, candidato_id, AHORA)
    # Una sola vez.
    assert extraccion.revisar_decisiones_base(almacen, None, AHORA, desde="2000-01-01") == []
    # La recogida siguiente lo repite con el experto, y vale lo suyo.
    cliente = Cliente(_no_es(), ficha_ejemplo())
    hechas = extraccion.extraer(almacen, cliente, [peticion], AHORA, coste.Modo.HORARIO, MODELOS)
    assert cliente.pedidas == [BASE, EXPERTO] and hechas.incidentes[0] is not None
    assert candidato_id not in extraccion.esperan_experto(almacen)
