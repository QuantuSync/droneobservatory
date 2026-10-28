"""Rectificaciones oficiales de la presencia del dron (proceso/rectificaciones.py,
recogida/rectificaciones.py, docs/rectificaciones.md): no acreditado y descartado con su
historial, correcciones parciales, lo rectificado que la recogida no deshace, el experto siempre
antes de cambiar nada, la detección en cada recogida y la búsqueda del mes con su tope."""

import copy
import json
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import pytest

from almacen.base import Almacen
from esquema import Esquema, validador
from exportacion import procedencia
from modelo import coste
from proceso import rectificaciones, titulares
from recogida import avisos, revisados, visitas
from recogida import rectificaciones as seguimiento
from tests import ejemplos
from tests.ejemplos import VOCABULARIO_MODELOS

AHORA = datetime(2026, 10, 15, 12, 0, tzinfo=UTC)
ID = "EODI-2025-00154"
EXPERTO = "proveedor-sonnet-5-5"
BASE = "proveedor-haiku-5-5"
RIGS = (
    "I enkelte efterforskninger har det hverken kunnet påvises eller afvises, at der har været "
    "tale om droner."
)


def _copenhague() -> dict[str, Any]:
    """Como EODI-2025-00154: el cierre del aeropuerto de Copenhague del 22 de septiembre de 2025,
    confirmado por la policía que atribuyó el cierre a drones."""
    d = ejemplos.incidente_minimo()
    d["id"] = ID
    d["tipo"] = "interrupcion_aeroportuaria"
    d["titulo"] = {"es": "Drones cierran el aeropuerto de Copenhague",
                   "en": "Drones close Copenhagen Airport"}  # fmt: skip
    d["tiempo"] = {"inicio": ejemplos.instante("2025-09-22T20:00Z", "hora")}
    d["lugar"] = {"punto": {"lat": 55.62, "lon": 12.65}, "radio_km": 5, "pais": "DK",
                  "localidad": "Kastrup"}  # fmt: skip
    d["objetivo"] = {"categoria": "aeropuerto", "nombre": "Københavns Lufthavn", "oaci": "EKCH"}
    d["consecuencias"] = {"cierre": {"valor": "si", "minutos": {"min": 240, "max": 240}}}
    noticia = {**ejemplos.fuente("N1", "C"), "fecha": ejemplos.instante("2025-09-22T20:15Z"),
               "frase_origen": "Lufthavnen er lukket ned, grundet to til tre droner"}  # fmt: skip
    politi = {**noticia, "id": "N1-declaracion-1", "fiabilidad": "B", "es_autoridad": True,
              "medio": "Københavns Politi (declaración oficial citada en tv2.dk)"}  # fmt: skip
    tardia = {**ejemplos.fuente("N2", "C"), "fecha": ejemplos.instante("2026-06-25T11:45Z"),
              "enlace": "https://ekstrabladet.dk/politi",
              "frase_origen": "Politiet har hverken kunnet bevise eller afvise, at der var "
                              "droner over Københavns Lufthavn 22. september 2025."}  # fmt: skip
    d["fuentes"] = [noticia, politi, tardia]
    d["estado"] = {"actual": "confirmado", "historial": [
        {"estado": "notificado", "fecha": noticia["fecha"], "fuente_id": "N1"},
        {"estado": "confirmado", "fecha": noticia["fecha"], "fuente_id": "N1-declaracion-1"},
    ]}  # fmt: skip
    d["presencia_dron"] = "confirmada"
    d["afirmaciones"] = [
        {"campo": "presencia_dron", "valor": "confirmada", "fuente_id": "N1-declaracion-1",
         "confianza_extraccion": 0.95},
        {"campo": "cierre", "valor": "si", "fuente_id": "N1", "confianza_extraccion": 0.95},
        {"campo": "cierre_minutos", "valor": {"min": 240, "max": 240}, "fuente_id": "N1",
         "confianza_extraccion": 0.9},
    ]  # fmt: skip
    return d


REVISADA: dict[str, Any] = {
    "incidente": ID,
    "tipo": "no_acreditada",
    "fecha_declaracion": "2026-06-25",
    "fuente": {
        "enlace": "https://politi.dk/rigspolitiet/nyhedsliste/2026/06/25", "medio": "politi.dk",
        "fecha": "2026-06-25", "idioma": "da", "frase": RIGS, "oficial": True,
        "declaracion": {"autoridad": "Rigspolitiet", "pais": "DK", "categoria": "policia",
                        "afirma": "incidente"},
    },
    "contexto": "Københavns Politi har i dag fremlagt resultaterne af efterforskningen.",
    "quien": {"es": "la policía danesa (Rigspolitiet)", "en": "the Danish National Police"},
    "motivo": {"es": "al cerrar la investigación: no se ha podido probar ni descartar",
               "en": "on closing the investigation: neither proven nor ruled out"},
    "anterior": {"quien": {"es": "la policía de Copenhague", "en": "Copenhagen Police"}},
}  # fmt: skip


def _respuesta(datos: dict[str, Any], modelo: str = EXPERTO) -> dict[str, Any]:
    return {"stop_reason": "end_turn", "model": modelo,
            "content": [{"type": "text", "text": json.dumps(datos, ensure_ascii=False)}],
            "usage": {"input_tokens": 1500, "output_tokens": 300}}  # fmt: skip


def _decision(tipo: str = "no_acreditada", frase: str = RIGS, **cambios: Any) -> dict[str, Any]:
    return {"tipo": tipo, "mismo_suceso": True, "autoridad_oficial": True, "frase": frase,
            "fecha": "2026-06-25", "quien_es": "la policía de Copenhague",
            "quien_en": "Copenhagen Police", "motivo_es": "cerró la investigación sin pruebas",
            "motivo_en": "closed the investigation without evidence", "confianza": 0.9,
            **cambios}  # fmt: skip


NINGUNA = {"tipo": "ninguna", "mismo_suceso": True, "autoridad_oficial": False, "frase": "",
           "fecha": "", "quien_es": "", "quien_en": "", "motivo_es": "", "motivo_en": "",
           "confianza": 0.9}  # fmt: skip


class Cliente:
    """El servicio de modelos: el base responde `base`; su experto, `respuestas` en orden (y,
    cuando se acaban, que no ve ninguna rectificación)."""

    def __init__(self, respuestas: list[dict[str, Any]], base: list[dict[str, Any]] | None = None,
                 con_experto: bool = True) -> None:  # fmt: skip
        self.respuestas, self.base = list(respuestas), list(base or [])
        self.con_experto = con_experto
        self.pedidas: list[dict[str, Any]] = []
        self.pedidas_base: list[dict[str, Any]] = []
        self.modelo = BASE

    def mensaje(self, cuerpo: dict[str, Any]) -> dict[str, Any]:
        self.pedidas_base.append(cuerpo)
        return _respuesta(self.base.pop(0), BASE)

    def experto(self) -> Any:
        if not self.con_experto:
            return None
        padre = self

        class Experto:
            modelo = EXPERTO

            def mensaje(self, cuerpo: dict[str, Any]) -> dict[str, Any]:
                padre.pedidas.append(cuerpo)
                return _respuesta(padre.respuestas.pop(0) if padre.respuestas else NINGUNA)

        return Experto()


@pytest.fixture(autouse=True)
def modelos(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    monkeypatch.setenv("EODI_MODELO_BASE", BASE)
    monkeypatch.setenv("EODI_MODELO_EXPERTO", EXPERTO)
    datos: dict[str, Any] = {"rectificaciones": [copy.deepcopy(REVISADA)]}
    monkeypatch.setattr(seguimiento, "cargar", lambda: datos)
    return datos


@pytest.fixture
def almacen() -> Any:
    a = Almacen.abrir()
    a.guardar_incidente(_copenhague(), AHORA, VOCABULARIO_MODELOS)
    yield a
    a.cerrar()


def _pasar(almacen: Almacen, cliente: Cliente | None, ahora: datetime = AHORA) -> Any:
    fabrica = (lambda: cliente) if cliente is not None else None
    return seguimiento.ejecutar(almacen, ahora, VOCABULARIO_MODELOS, fabrica)


# --- Lo que cambia y cómo queda ----------------------------------------------------------


def test_copenhague_no_acreditado_con_su_secuencia(almacen: Almacen) -> None:
    cliente = Cliente([_decision()])
    hechos = _pasar(almacen, cliente)
    assert hechos.aplicadas == [f"{ID} no_acreditada"] and not hechos.sin_guardar
    d = almacen.incidente(ID)
    assert d is not None
    assert d["presencia_dron"] == "no_acreditada"
    # El incidente y su efecto se mantienen.
    assert d["estado"]["actual"] == "confirmado"
    assert d["consecuencias"]["cierre"] == {"valor": "si", "minutos": {"min": 240, "max": 240}}
    assert d["tipo"] == "interrupcion_aeroportuaria"
    # La secuencia: confirmado por la policía de Copenhague y no acreditado tras la investigación.
    semilla, paso = d["presencia_historial"]
    assert semilla == {
        "valor": "confirmada", "fecha": ejemplos.instante("2025-09-22T20:15Z"),
        "fuente_id": "N1-declaracion-1",
        "quien": {"es": "la policía de Copenhague", "en": "Copenhagen Police"},
    }  # fmt: skip
    assert paso["valor"] == "no_acreditada" and paso["fecha"]["valor"] == "2026-06-25T00:00Z"
    assert paso["quien"] == REVISADA["quien"] and paso["motivo"] == REVISADA["motivo"]
    oficial = next(f for f in d["fuentes"] if f["id"] == paso["fuente_id"])
    assert oficial["frase_origen"] == RIGS and oficial["es_autoridad"]
    # El titular da el dron como posible.
    assert d["titulo"]["es"] == "Posibles drones cierran el aeropuerto de Copenhague"
    assert titulares.coherente(d["titulo"]["en"], "no_acreditada", "en")
    # Lo decidió el experto, y la decisión queda guardada.
    assert len(cliente.pedidas) == 1 and not cliente.pedidas_base
    assert RIGS in cliente.pedidas[0]["messages"][0]["content"]
    (decision,) = almacen.controles(seguimiento.PREFIJO).values()
    assert decision["tipo"] == "no_acreditada" and decision["origen"] == "revisada"


def test_la_recogida_siguiente_no_repite_ni_pregunta(almacen: Almacen) -> None:
    _pasar(almacen, Cliente([_decision()]))
    antes = almacen.incidente(ID)
    cliente = Cliente([])
    hechos = _pasar(almacen, cliente)
    assert hechos.aplicadas == [] and cliente.pedidas == []
    # La fuente de ekstrabladet (del día de la rectificación) ya no se manda al experto.
    assert hechos.detectadas == 0
    assert almacen.incidente(ID) == antes


def test_una_extraccion_nueva_no_deshace_lo_rectificado(almacen: Almacen) -> None:
    _pasar(almacen, Cliente([_decision()]))
    rectificado = almacen.incidente(ID)
    assert rectificado is not None
    # La ficha vuelve a salir del extractor sin historial, confirmada y sin la fuente oficial.
    nueva = _copenhague()
    nueva["titulo"] = {"es": "Drones cierran el aeropuerto de Copenhague y desvían vuelos",
                       "en": "Drones close Copenhagen Airport and divert flights"}  # fmt: skip
    almacen.guardar_incidente(nueva, AHORA, VOCABULARIO_MODELOS)
    d = almacen.incidente(ID)
    assert d is not None
    assert d["presencia_dron"] == "no_acreditada"
    assert d["presencia_historial"] == rectificado["presencia_historial"]
    assert {p["fuente_id"] for p in d["presencia_historial"]} <= {f["id"] for f in d["fuentes"]}
    assert d["titulo"]["es"].startswith("Posibles drones")


def test_sin_experto_no_se_rebaja_nada(almacen: Almacen, monkeypatch: pytest.MonkeyPatch) -> None:
    antes = almacen.incidente(ID)
    hechos = _pasar(almacen, Cliente([], con_experto=False))
    assert hechos.aplicadas == [] and hechos.esperan
    monkeypatch.delenv("EODI_MODELO_EXPERTO")
    hechos = _pasar(almacen, Cliente([]))
    assert hechos.aplicadas == [] and almacen.incidente(ID) == antes
    assert almacen.controles(seguimiento.PREFIJO) == {}


def test_con_el_tope_del_experto_agotado_espera(almacen: Almacen) -> None:
    almacen.registrar_llamada({
        "fecha": "2026-10-15T01:00:00Z", "modo": "horario", "candidato": "x", "lote": False,
        "entrada": 0, "salida": 0, "escritura_cache": 0, "lectura_cache": 0,
        "coste": coste.LIMITE_EXPERTO_DIARIO_USD, "modelo": EXPERTO, "escalada": True,
    })  # fmt: skip
    cliente = Cliente([_decision()])
    hechos = _pasar(almacen, cliente)
    # No usa la reserva crítica: espera a la recogida siguiente.
    assert hechos.aplicadas == [] and cliente.pedidas == [] and hechos.esperan


@pytest.mark.parametrize(
    ("cambios", "motivo"),
    [
        ({"autoridad_oficial": False}, "autoridad oficial"),
        ({"mismo_suceso": False}, "otro suceso"),
        ({"frase": "La policía no vio nada."}, "literal"),
        ({"confianza": 0.5}, "seguro"),
        ({"tipo": "descartada"}, "no como no_acreditada"),
        ({"tipo": "ninguna"}, "no ve una rectificación"),
    ],
)
def test_lo_que_no_vale_del_experto(almacen: Almacen, cambios: dict[str, Any], motivo: str) -> None:
    hechos = _pasar(almacen, Cliente([_decision(**cambios)]))
    d = almacen.incidente(ID)
    assert d is not None and d["presencia_dron"] == "confirmada"
    assert "presencia_historial" not in d
    assert hechos.rechazadas and motivo in hechos.rechazadas[0]


def test_descartado_si_la_autoridad_dice_que_era_otra_cosa() -> None:
    d = _copenhague()
    fuente = {
        **ejemplos.fuente("UKAB", "A", es_autoridad=True),
        "frase_origen": "they had actually sighted a fast-moving object (an F15)",
    }
    nuevo = rectificaciones.aplicar(
        d, "descartada", fuente, ejemplos.instante("2025-06-26T00:00Z", "dia"),
        {"es": "el UK Airprox Board", "en": "the UK Airprox Board"},
        {"es": "era un F-15", "en": "it was an F-15"}, "rectificacion:prueba",
    )  # fmt: skip
    assert nuevo["presencia_dron"] == "descartada"
    assert [p["valor"] for p in nuevo["presencia_historial"]] == ["confirmada", "descartada"]
    assert nuevo["estado"] == d["estado"] and nuevo["consecuencias"] == d["consecuencias"]
    assert rectificaciones.errores(nuevo) == []


def test_la_ficha_ya_rebajada_sin_historial_parte_del_valor_de_antes() -> None:
    # EODI-2025-00228 (Aalborg): una revisión a mano la dejó «no acreditada» sin decir quién ni
    # cuándo. La rectificación de la policía de Jutlandia del Norte (25 de junio de 2026) añade el
    # historial: el primer paso es el valor de antes (`anterior.valor`), no el ya rebajado.
    d = {**_copenhague(), "presencia_dron": "no_acreditada"}
    fuente = {
        **ejemplos.fuente("TV2NORD", "A", es_autoridad=True),
        "frase_origen": "Politikredsen kan hverken påvise eller afvise, hvorvidt der har været "
                        "tale om droneaktivitet.",
    }  # fmt: skip
    quien = {"es": "la Policía de Jutlandia del Norte (Nordjyllands Politi)",
             "en": "the North Jutland Police (Nordjyllands Politi)"}  # fmt: skip
    motivo = {"es": "al cerrar la investigación", "en": "on closing the investigation"}
    sin = rectificaciones.aplicar(
        d, "no_acreditada", fuente, ejemplos.instante("2026-06-25T00:00Z", "dia"), quien, motivo,
        "rectificacion:prueba",
    )  # fmt: skip
    assert [p["valor"] for p in sin["presencia_historial"]] == ["no_acreditada", "no_acreditada"]
    nuevo = rectificaciones.aplicar(
        d, "no_acreditada", fuente, ejemplos.instante("2026-06-25T00:00Z", "dia"), quien, motivo,
        "rectificacion:prueba", None, "confirmada",
    )  # fmt: skip
    assert [p["valor"] for p in nuevo["presencia_historial"]] == ["confirmada", "no_acreditada"]
    assert nuevo["presencia_historial"][-1]["quien"] == quien
    assert nuevo["presencia_historial"][-1]["fecha"]["valor"] == "2026-06-25T00:00Z"
    assert rectificaciones.errores(nuevo) == []


def test_revisadas_de_aalborg_y_las_descartadas_con_su_autoridad() -> None:
    # Las rebajadas sin fecha ni autoridad del cierre (auditoría P, 27 de octubre de 2026).
    datos = json.loads(seguimiento.RUTA.read_text(encoding="utf-8"))
    revisadas = {r["incidente"]: r for r in datos["rectificaciones"]}
    for id_ in ("EODI-2025-00228", "EODI-2025-00238", "EODI-2025-00112", "EODI-2025-00225",
                "EODI-2025-00352", "EODI-2026-00007", "EODI-2026-00064"):  # fmt: skip
        assert revisadas[id_]["anterior"]["valor"] in ("confirmada", "no_confirmada")
    assert revisadas["EODI-2025-00228"]["fecha_declaracion"] == "2026-06-25"
    # «keine Drohne bestätigen können» no dice que fuera otra cosa: no acreditada, no descartada.
    assert revisadas["EODI-2025-00352"]["tipo"] == "no_acreditada"


def test_la_correccion_parcial_se_anota_sin_cambiar_el_valor(
    almacen: Almacen, modelos: dict[str, Any]
) -> None:
    parcial = copy.deepcopy(REVISADA)
    parcial["tipo"] = "parcial"
    parcial["fuente"]["frase"] = "Later bleek dat het om een politiehelikopter ging."
    modelos["rectificaciones"] = [parcial]
    _pasar(almacen, Cliente([_decision("parcial", "Later bleek dat het om een politiehelikopter "
                                                  "ging.")]))  # fmt: skip
    d = almacen.incidente(ID)
    assert d is not None and d["presencia_dron"] == "confirmada"
    semilla, nota = d["presencia_historial"]
    assert nota["parcial"] is True and nota["valor"] == "confirmada" == semilla["valor"]
    assert d["titulo"]["es"] == "Drones cierran el aeropuerto de Copenhague"


def test_la_investigacion_cerrada_sin_cambio_se_anota_sin_tocar_presencia_ni_estado(
    almacen: Almacen, modelos: dict[str, Any]
) -> None:
    # Auvere (EODI-2026-00108), 23 de octubre de 2026: la Fiscalía de Estonia cierra la
    # investigación sin determinar el origen del dron; el dron y el impacto siguen probados.
    cierre = copy.deepcopy(REVISADA)
    cierre["tipo"] = "cierre_sin_cambio"
    modelos["rectificaciones"] = [cierre]
    antes = almacen.incidente(ID)
    assert antes is not None
    _pasar(almacen, Cliente([_decision("cierre_sin_cambio")]))
    d = almacen.incidente(ID)
    assert d is not None and d["presencia_dron"] == antes["presencia_dron"] == "confirmada"
    assert d["estado"] == antes["estado"]
    semilla, nota = d["presencia_historial"]
    assert nota["cierre"] is True and "parcial" not in nota
    assert nota["valor"] == semilla["valor"] == "confirmada"
    assert nota["fecha"]["valor"].startswith("2026-06-25")
    assert set(nota["quien"]) == set(nota["motivo"]) == {"es", "en"}
    assert rectificaciones.vigente(d) == "confirmada" and not rectificaciones.rectificado(d)
    assert rectificaciones.errores(d) == []
    assert d["titulo"]["es"] == "Drones cierran el aeropuerto de Copenhague"


def test_el_tipo_revisado_que_cambia_se_vuelve_a_preguntar() -> None:
    propuesta = seguimiento.Propuesta(
        "revisada:x", ID, "revisada", {"id": "f"}, "texto", esperado="cierre_sin_cambio"
    )
    antigua = {"huella": seguimiento.huella("texto"), "tipo": None}
    assert seguimiento.cambio_revisado(antigua, propuesta)
    leida = {**antigua, "tipo": "cierre_sin_cambio"}
    assert not seguimiento.cambio_revisado(leida, propuesta)
    guardada = {**antigua, "esperado": "cierre_sin_cambio"}
    assert not seguimiento.cambio_revisado(guardada, propuesta)
    assert seguimiento.cambio_revisado({**guardada, "esperado": "parcial"}, propuesta)
    assert seguimiento.cambio_revisado({**leida, "huella": "otra"}, propuesta)


def test_la_fuente_oficial_que_llega_despues_entra_sin_repetir_el_paso(almacen: Almacen,
                                                                        modelos: dict[str, Any]
                                                                        ) -> None:  # fmt: skip
    # Primero la noticia que cita a la policía (detección de la recogida) y después la
    # declaración oficial revisada a mano: un solo paso, y la fuente oficial en la ficha.
    revisada = modelos["rectificaciones"]
    modelos["rectificaciones"] = []
    frase = "Politiet har hverken kunnet bevise eller afvise"
    _pasar(almacen, Cliente([_decision(frase=frase)]))
    modelos["rectificaciones"] = revisada
    hechos = _pasar(almacen, Cliente([_decision()]))
    d = almacen.incidente(ID)
    assert d is not None and d["presencia_dron"] == "no_acreditada"
    assert [p["valor"] for p in d["presencia_historial"]] == ["confirmada", "no_acreditada"]
    assert any(f["frase_origen"] == RIGS for f in d["fuentes"])
    assert hechos.aplicadas == []


def test_errores_del_historial() -> None:
    d = _copenhague()
    d["presencia_historial"] = [
        {"valor": "confirmada", "fecha": ejemplos.instante("2025-09-22T20:15Z"),
         "fuente_id": "N1-declaracion-1"},
        {"valor": "no_acreditada", "fecha": ejemplos.instante("2026-06-25T00:00Z", "dia"),
         "fuente_id": "no-esta"},
        {"valor": "confirmada", "parcial": True, "fecha": ejemplos.instante("2026-07-01T00:00Z"),
         "fuente_id": "N1"},
    ]  # fmt: skip
    errores = rectificaciones.errores(d)
    assert any("no-esta" in e for e in errores)
    assert any("(parcial o cierre) cambia el valor" in e for e in errores)
    assert any("acaba en no_acreditada" in e for e in errores)


# --- Detección en la recogida y búsqueda del mes -----------------------------------------


@pytest.mark.parametrize(
    "texto",
    [
        "Politiet har hverken kunnet bevise eller afvise, at der var droner",
        "Danish police find no proof drones caused Copenhagen airport shutdown",
        "We cannot confirm that there has been drone activity",
        "the helicopter crew had misidentified the lights of a fast-moving F-15",
        "Later bleek dat het om een politiehelikopter ging",
        "Die Ermittlungen wurden eingestellt",
        "L'enquête a été classée sans suite",
        "La investigación fue archivada",
        "Śledztwo zostało umorzone",
        "Расследование прекращено",
    ],
)
def test_senales_en_varios_idiomas(texto: str) -> None:
    assert rectificaciones.senal(texto) is not None


def test_senales_que_no_son() -> None:
    assert rectificaciones.senal("Drones cierran el aeropuerto de Copenhague") is None
    assert rectificaciones.senal("Police confirm drone sighting over the base") is None


def test_la_recogida_manda_al_experto_lo_que_suena_a_rectificacion(
    almacen: Almacen, modelos: dict[str, Any]
) -> None:
    modelos["rectificaciones"] = []
    frase = "Politiet har hverken kunnet bevise eller afvise"
    cliente = Cliente([_decision(frase=frase, fecha="2026-06-25")])
    hechos = _pasar(almacen, cliente)
    assert hechos.detectadas == 1 and len(cliente.pedidas) == 1
    d = almacen.incidente(ID)
    assert d is not None and d["presencia_dron"] == "no_acreditada"
    assert d["presencia_historial"][-1]["fuente_id"] == "N2"
    assert d["presencia_historial"][-1]["quien"]["en"] == "Copenhagen Police"


def test_una_fuente_del_mismo_dia_no_se_manda(almacen: Almacen, modelos: dict[str, Any]) -> None:
    modelos["rectificaciones"] = []
    d = _copenhague()
    d["fuentes"] = [f for f in d["fuentes"] if f["id"] != "N2"]
    d["fuentes"][0]["frase_origen"] = "Politiet kan ikke bekræfte, at det var droner"
    almacen.guardar_incidente(d, AHORA, VOCABULARIO_MODELOS)
    cliente = Cliente([])
    hechos = _pasar(almacen, cliente)
    assert hechos.detectadas == 0 and cliente.pedidas == []


def test_la_autoridad_que_lo_niega_el_mismo_dia_va_al_experto(
    almacen: Almacen, modelos: dict[str, Any]
) -> None:
    # EODI-2025-00203, Schiphol: la Marechaussee dijo el mismo día que no hubo dron en el radar y
    # que el objeto era probablemente un globo. Una noticia del mismo día sigue sin mandarse.
    modelos["rectificaciones"] = []
    d = _copenhague()
    d["fuentes"] = [f for f in d["fuentes"] if f["id"] != "N2"]
    d["fuentes"][1]["medio"] = (
        "Royal Netherlands Marechaussee (declaración oficial citada en kyivindependent.com)"
    )
    d["fuentes"][1]["frase_origen"] = (
        "an investigation showed no drone was detected on radar and that the object was likely a "
        "balloon."
    )
    almacen.guardar_incidente(d, AHORA, VOCABULARIO_MODELOS)
    (propuesta,) = seguimiento.detectadas(almacen, set())
    assert propuesta.fuente["id"] == "N1-declaracion-1"


def test_como_mucho_unas_pocas_preguntas_por_recogida(modelos: dict[str, Any]) -> None:
    modelos["rectificaciones"] = []
    almacen = Almacen.abrir()
    for n in range(seguimiento.MAX_POR_PASADA + 3):
        d = _copenhague()
        d["id"] = f"EODI-2025-{n + 100:05d}"
        almacen.guardar_incidente(d, AHORA, VOCABULARIO_MODELOS)
    cliente = Cliente([])
    hechos = _pasar(almacen, cliente)
    assert len(cliente.pedidas) == seguimiento.MAX_POR_PASADA
    assert hechos.detectadas == seguimiento.MAX_POR_PASADA + 3
    hechos = _pasar(almacen, cliente)
    assert len(cliente.pedidas) == seguimiento.MAX_POR_PASADA + 3
    hechos = _pasar(almacen, cliente)
    assert len(cliente.pedidas) == seguimiento.MAX_POR_PASADA + 3 and hechos.detectadas == 0


def test_busqueda_mensual_con_el_base_y_su_tope(almacen: Almacen, modelos: dict[str, Any]) -> None:
    modelos["rectificaciones"] = []
    d = almacen.incidente(ID)
    assert d is not None
    d["fuentes"] = [f for f in d["fuentes"] if f["id"] != "N2"]
    almacen.guardar_incidente(d, AHORA, VOCABULARIO_MODELOS)
    titular = "Danish police find no proof drones caused Københavns Lufthavn shutdown"
    for url, texto in [
        ("https://reuters.example/no-proof", titular),
        ("https://otro.example/x", "Drones over Københavns Lufthavn again"),
    ]:
        almacen.guardar_articulo({"url": url, "medio": url.split("/")[2], "fecha":
                                  "2026-06-25T12:00Z", "idioma": "en", "titular": texto,
                                  "titular_normalizado": texto.lower()})  # fmt: skip
    cliente = Cliente([_decision(frase="find no proof drones caused")], base=[{"titulares": [1]}])
    hechos = _pasar(almacen, cliente)
    # El base elige el titular; el experto lo decide en la misma recogida o en la siguiente.
    assert len(cliente.pedidas_base) == 1 and "no proof" in str(cliente.pedidas_base[0])
    assert "Drones over" not in str(cliente.pedidas_base[0])
    assert hechos.mensual["elegidos"] == 1
    hechos = _pasar(almacen, cliente)
    d = almacen.incidente(ID)
    assert d is not None and d["presencia_dron"] == "no_acreditada"
    paso = d["presencia_historial"][-1]
    fuente = next(f for f in d["fuentes"] if f["id"] == paso["fuente_id"])
    assert fuente["frase_origen"] == "find no proof drones caused"
    # Una sola pasada al mes.
    _pasar(almacen, cliente)
    assert len(cliente.pedidas_base) == 1
    cursor = almacen.cursor(seguimiento.CURSOR_MENSUAL)
    assert cursor is not None and cursor["mes"] == "2026-10"
    assert cursor["gasto"] <= seguimiento.TOPE_MENSUAL_USD


def test_la_busqueda_mensual_no_pasa_del_tope(almacen: Almacen, modelos: dict[str, Any]) -> None:
    modelos["rectificaciones"] = []
    almacen.registrar_llamada({
        "fecha": "2026-10-15T01:00:00Z", "modo": coste.Modo.RECTIFICACIONES.value,
        "candidato": "x", "lote": False, "entrada": 0, "salida": 0, "escritura_cache": 0,
        "lectura_cache": 0, "coste": coste.LIMITE_RECTIFICACIONES_USD, "modelo": BASE,
        "escalada": False,
    })  # fmt: skip
    texto = "Danish police find no proof drones caused Københavns Lufthavn shutdown"
    almacen.guardar_articulo({"url": "https://r.example/a", "medio": "r.example",
                              "fecha": "2026-06-25T12:00Z", "idioma": "en", "titular": texto,
                              "titular_normalizado": texto.lower()})  # fmt: skip
    cliente = Cliente([], base=[{"titulares": [1]}])
    hechos = seguimiento.mensual(almacen, AHORA, lambda: cliente, None)
    assert cliente.pedidas_base == [] and hechos["parada"] == "limite_gasto"
    # Sin completar, la pasada se repite en la recogida siguiente.
    assert (almacen.cursor(seguimiento.CURSOR_MENSUAL) or {}).get("mes") is None


# --- Avisos y exportación ------------------------------------------------------------------


def test_la_rectificacion_no_genera_aviso(almacen: Almacen) -> None:
    _pasar(almacen, Cliente([_decision()]))
    d = almacen.incidente(ID)
    assert d is not None
    config = {"paises": {"DK": {"tema": "drones-dk", "otan": True}}, "ventana_horas": 10**6}
    assert avisos.clasificar(d, config, AHORA) is None
    sin = _copenhague()
    assert avisos.clasificar(sin, config, AHORA) is not None


def test_el_resumen_diario_cuenta_las_rectificaciones(tmp_path: Path) -> None:
    ruta = tmp_path / "eodi.sqlite"
    almacen = Almacen.abrir(ruta)
    almacen.guardar_incidente(_copenhague(), AHORA, VOCABULARIO_MODELOS)
    _pasar(almacen, Cliente([_decision()]))
    almacen.cerrar()
    assert visitas.rectificaciones_del_dia(ruta, AHORA.date()) == [(ID, "no_acreditada")]
    assert visitas.rectificaciones_del_dia(ruta, date(2026, 10, 14)) == []
    datos = visitas.Datos(
        dia=AHORA.date(), visitas=None, anterior=None, media7=None,
        suscriptores=visitas.Suscriptores(None, None, None, 0, []), nuevos=[], avisos=(0, 0),
        recogidas=(24, 0, 0), problemas=[], rectificaciones=[(ID, "no_acreditada")],
    )  # fmt: skip
    texto = visitas.texto_resumen(datos)
    assert f"RECTIFICACIONES OFICIALES DE LA PRESENCIA: 1\n  {ID}: no acreditada" in texto


def test_la_exportacion_da_el_origen_de_lo_rectificado(almacen: Almacen) -> None:
    _pasar(almacen, Cliente([_decision()]))
    d = almacen.incidente(ID)
    assert d is not None
    _, origen = procedencia.procedencia_incidente(d, procedencia.Fichas(almacen))
    paso = d["presencia_historial"][-1]
    assert origen["presencia_dron"]["fuentes"] == [paso["fuente_id"]]
    assert set(origen["presencia_historial"]["fuentes"]) == {
        p["fuente_id"] for p in d["presencia_historial"]
    }


def test_revisadas_de_verdad_validan() -> None:
    """Las rectificaciones revisadas a mano del repositorio: tipo conocido, textos en los dos
    idiomas y la frase dentro del texto que ve el experto."""
    revisadas = json.loads(seguimiento.RUTA.read_text(encoding="utf-8"))["rectificaciones"]
    assert {r["incidente"] for r in revisadas} >= {"EODI-2025-00154", "EODI-2025-00164"}
    for entrada in revisadas:
        assert entrada["tipo"] in rectificaciones.TIPOS
        assert entrada["quien"]["es"] and entrada["quien"]["en"]
        assert entrada["motivo"]["es"] and entrada["motivo"]["en"]
        # Leída en la página de la autoridad o citada por un medio de fiabilidad A o B (Auvere;
        # B desde el 27 de octubre de 2026: t-online, 15min con BNS y Focus).
        citada = (entrada["fuente"].get("citada_en") or {}).get("fiabilidad") in ("A", "B")
        assert entrada["fuente"]["declaracion"] and (entrada["fuente"]["oficial"] or citada)
        assert len(entrada["fecha_declaracion"]) == 10
        # La fuente que se añade a la ficha valida (su frase, como mucho 25 palabras: el
        # 16 de octubre de 2026 las tres primeras no se guardaron por eso).
        fuente = revisados.fuente_de_cita(entrada["fuente"], ejemplos.incidente_minimo())
        assert not list(validador(Esquema.FUENTE).iter_errors(fuente)), entrada["incidente"]
    assert revisados.PREFIJO_REVISADA


def test_el_registro_dice_que_rechazo_el_experto_y_por_que(almacen: Almacen) -> None:
    # EODI-2026-00064 (Sofía, 27 de octubre de 2026): el registro solo decía «rechazadas 1», y
    # hubo que leer la base para saber cuál y por qué.
    hechos = _pasar(almacen, Cliente([_decision(confianza=0.6)]))
    assert f"revisada:{ID}:" in hechos.texto() and "no está seguro (0.60)" in hechos.texto()


def test_la_rectificacion_de_sofia_manda_lo_que_era() -> None:
    # La policía búlgara dijo que no había dron y qué era: un aficionado que fotografiaba aviones
    # con una radio y una cámara (descartada). Con la frase y «otras señales no se confirman»,
    # el experto lo leyó no_acreditada con 0,60 y se rechazó: el texto que ve lleva lo que era.
    datos = json.loads(seguimiento.RUTA.read_text(encoding="utf-8"))
    (sofia,) = [r for r in datos["rectificaciones"] if r["incidente"] == "EODI-2026-00064"]
    assert sofia["tipo"] == "descartada"
    assert "Гранична полиция" in sofia["contexto"] and "фотоапарт" in sofia["contexto"]
    assert "не се потвърждават" not in sofia["contexto"]


def _con_semilla(quien: dict[str, str], medio: str, revision: str | None = None) -> dict[str, Any]:
    d = _copenhague()
    d["fuentes"][1]["medio"] = medio
    paso: dict[str, Any] = {"valor": "confirmada", "fecha": d["fuentes"][1]["fecha"],
                            "fuente_id": "N1-declaracion-1", "quien": quien}  # fmt: skip
    if revision:
        paso["revision"] = revision
    d["presencia_historial"] = [paso]
    return d


def test_el_quien_de_la_semilla_sale_de_la_tabla_de_hoy() -> None:
    # EODI-2025-00228: la semilla guardó «la unidad de aviones de transporte…», el nombre que
    # daba la tabla antes del PR 330. Al publicar se escribe con la tabla de hoy.
    viejo = {"es": "la unidad de aviones de transporte de la Fuerza Aérea danesa "
                   "(Flyvevåbnets afdeling for transportfly)",
             "en": "the Royal Danish Air Force transport wing "
                   "(Flyvevåbnets afdeling for transportfly)"}  # fmt: skip
    medio = "Flyvevåbnets afdeling for transportfly (declaración oficial citada en ekstrabladet.dk)"
    d = _con_semilla(viejo, medio)
    nuevo = rectificaciones.con_quien_de_hoy(d)
    assert nuevo["presencia_historial"][0]["quien"] == {
        "es": "el Ala de Transporte Aéreo de Aalborg de la Fuerza Aérea danesa "
              "(Flyvevåbnets afdeling for transportfly)",
        "en": "the Royal Danish Air Force's Air Transport Wing Aalborg "
              "(Flyvevåbnets afdeling for transportfly)",
    }  # fmt: skip
    assert d["presencia_historial"][0]["quien"] == viejo  # el guardado no se toca
    # El paso de una rectificación (con su revisión), una autoridad que no está en la tabla y un
    # medio se quedan como se guardaron.
    for otro in (
        _con_semilla(viejo, medio, "rectificacion:revisada:x"),
        _con_semilla(viejo, "Una autoridad nueva (declaración oficial citada en tv2.dk)"),
        _con_semilla(viejo, "tv2.dk"),
    ):
        assert rectificaciones.con_quien_de_hoy(otro) is otro
