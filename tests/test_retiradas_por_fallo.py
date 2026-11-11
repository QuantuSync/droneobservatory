"""Un fallo técnico nunca retira una ficha publicada. EODI-2026-00130 y EODI-2026-00302 salieron de
la web el 1 de noviembre de 2026 porque la extracción del experto, con los tres artículos de su
candidato, conservó afirmaciones de fuentes unidas que la versión nueva no llevaba: el guardado
falló y ese fallo acabó en una retirada."""

import copy
from collections.abc import Iterator
from datetime import timedelta
from types import SimpleNamespace
from typing import Any

import pytest

from almacen.base import Almacen, DocumentoInvalido
from esquema import Documento
from modelo import coste
from proceso import decididos, declaraciones, extraccion, no_es_suceso, protegido
from proceso.validacion_ficha import Validada
from proceso.validaciones import Error
from recogida import control_fichas, vigilancia, visitas
from tests.ejemplos import VOCABULARIO_MODELOS
from tests.test_cerrojo import base, ficha
from tests.test_control_fichas import AHORA as AHORA_CERROJO
from tests.test_decididos import _extraer, _peticion
from tests.test_extraccion import AHORA, MODELOS, campo, ficha_ejemplo, respuesta

UNIDA = "gdelt-unida"
EXPERTO = ["critico: dron confirmado"]


@pytest.fixture
def almacen() -> Iterator[Almacen]:
    a = Almacen.abrir()
    yield a
    a.cerrar()


def _ficha(almacen: Almacen, id_: str) -> Documento:
    incidente = almacen.incidente(id_)
    assert incidente is not None
    return incidente


def _publicada(almacen: Almacen) -> tuple[extraccion.Peticion, str]:
    peticion = _peticion(almacen)
    return peticion, _extraer(almacen, peticion, ficha_ejemplo())


def _con_fuente_unida(almacen: Almacen, id_: str, campos: tuple[str, ...]) -> None:
    """La ficha, como las reales: una fuente de otra ficha unida a ella, que el candidato no tiene,
    respalda también esos datos (la primera afirmación de cada uno es de una fuente del candidato,
    la que `decididos` mira para conservarlo)."""
    documento = copy.deepcopy(_ficha(almacen, id_))
    documento["fuentes"].append({
        **documento["fuentes"][0], "id": UNIDA, "enlace": "https://ejemplo.eu/unida",
    })  # fmt: skip
    for nombre in campos:
        propia = next(a for a in documento["afirmaciones"] if a["campo"] == nombre)
        documento["afirmaciones"].append({**propia, "fuente_id": UNIDA})
    almacen.guardar_incidente(documento, AHORA, MODELOS)


def _experto(
    almacen: Almacen, peticion: extraccion.Peticion, datos: dict[str, Any] | None = None,
    respuesta_: dict[str, Any] | None = None,
) -> str | None:  # fmt: skip
    """La respuesta del experto: la que vale aunque haya una ficha publicada, como en la segunda
    lectura que llevó a las dos fichas a la extracción."""
    return extraccion.procesar_respuesta(
        almacen, peticion, respuesta_ or respuesta(datos or ficha_ejemplo()),
        AHORA + timedelta(hours=1), coste.Modo.HORARIO, False, MODELOS, list(EXPERTO),
    )  # fmt: skip


def _fallos(almacen: Almacen) -> dict[str, Documento]:
    return almacen.controles(protegido.PREFIJO_GUARDADO_FALLIDO)


def _sigue(almacen: Almacen, id_: str) -> None:
    """Publicada y con el fallo apuntado: la ficha, el camino y el error."""
    assert "retirado" not in _ficha(almacen, id_)
    apuntes = list(_fallos(almacen).values())
    assert apuntes and all(a["ficha"] == id_ and a["camino"] and a["error"] for a in apuntes)


def _invalido(*_: Any) -> None:
    raise DocumentoInvalido(
        [Error("afirmaciones[13]", "la afirmación cita una fuente inexistente")]
    )


# --- El origen: las afirmaciones de fuentes que siguen en la ficha --------------------------------


def test_solo_se_conservan_las_afirmaciones_de_fuentes_que_siguen(almacen: Almacen) -> None:
    _, id_ = _publicada(almacen)
    _con_fuente_unida(almacen, id_, ("drones",))
    anterior = _ficha(almacen, id_)
    nuevo = copy.deepcopy(anterior)
    nuevo["fuentes"] = [f for f in nuevo["fuentes"] if f["id"] != UNIDA]
    nuevo["afirmaciones"] = [a for a in nuevo["afirmaciones"] if a["fuente_id"] != UNIDA]
    nuevo["drones"]["numero"] = "desconocido"
    conservacion = decididos.conservar(nuevo, anterior)
    assert conservacion.conservados == ["drones"]
    assert conservacion.incidente["drones"]["numero"] == anterior["drones"]["numero"]
    citadas = [a["fuente_id"] for a in conservacion.incidente["afirmaciones"]
               if a["campo"] == "drones"]  # fmt: skip
    assert citadas and UNIDA not in citadas


@pytest.mark.parametrize(
    ("caso", "campos", "cambio"),
    [
        ("EODI-2026-00130", ("drones",), {"drones": campo(None)}),
        ("EODI-2026-00302", ("drones", "cierre"), {"drones": campo(None), "cierre": campo(None)}),
    ],
)
def test_el_camino_real_de_las_dos_fichas(
    almacen: Almacen, caso: str, campos: tuple[str, ...], cambio: dict[str, Any]
) -> None:
    """Experto → _alta → conservar_decididos con afirmaciones de una fuente unida: ahora se guarda
    la versión nueva, sin esas afirmaciones, y nada falla."""
    peticion, id_ = _publicada(almacen)
    _con_fuente_unida(almacen, id_, campos)
    assert _experto(almacen, peticion, ficha_ejemplo(**cambio)) == id_, caso
    guardada = _ficha(almacen, id_)
    assert "retirado" not in guardada and not _fallos(almacen)
    assert all(a["fuente_id"] != UNIDA for a in guardada["afirmaciones"])
    assert guardada["drones"]["numero"] == {"min": 3, "max": 4}


# --- La regla: un fallo no retira, en cada camino ---------------------------------------------


def test_documento_invalido_en_la_extraccion(
    almacen: Almacen, monkeypatch: pytest.MonkeyPatch
) -> None:
    peticion, id_ = _publicada(almacen)
    antes = _ficha(almacen, id_)
    monkeypatch.setattr(almacen, "guardar_incidente", _invalido)
    assert _experto(almacen, peticion) == id_
    monkeypatch.undo()
    _sigue(almacen, id_)
    assert _ficha(almacen, id_) == antes
    ((clave, apunte),) = _fallos(almacen).items()
    assert clave.startswith(f"guardado_fallido:{id_}:") and apunte["camino"] == "extraccion"
    assert "fuente inexistente" in apunte["error"]


def test_cualquier_excepcion_al_guardar(almacen: Almacen, monkeypatch: pytest.MonkeyPatch) -> None:
    peticion, id_ = _publicada(almacen)

    def falla(*_: Any) -> None:
        raise RuntimeError("disco lleno")

    monkeypatch.setattr(almacen, "guardar_incidente", falla)
    assert _experto(almacen, peticion) == id_
    monkeypatch.undo()
    _sigue(almacen, id_)
    assert "disco lleno" in next(iter(_fallos(almacen).values()))["error"]


def test_una_excepcion_en_un_alta_nueva_sigue_subiendo(
    almacen: Almacen, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Sin ficha publicada no hay nada que conservar: el candidato se aparta como siempre."""
    peticion = _peticion(almacen)

    def falla(*_: Any) -> None:
        raise RuntimeError("disco lleno")

    monkeypatch.setattr(almacen, "guardar_incidente", falla)
    with pytest.raises(RuntimeError):
        _experto(almacen, peticion)
    monkeypatch.undo()
    assert not _fallos(almacen)


def test_un_lugar_que_no_vale(almacen: Almacen, monkeypatch: pytest.MonkeyPatch) -> None:
    peticion, id_ = _publicada(almacen)
    malo = SimpleNamespace(valida=False, motivo="lugar sin situar", sitio=None)
    monkeypatch.setattr(extraccion, "ubicar", lambda *_: malo)
    assert _experto(almacen, peticion) == id_
    _sigue(almacen, id_)
    assert "lugar sin situar" in next(iter(_fallos(almacen).values()))["error"]


def test_una_respuesta_ilegible_del_experto(almacen: Almacen) -> None:
    peticion, id_ = _publicada(almacen)
    assert (
        _experto(almacen, peticion, respuesta_={**respuesta(ficha_ejemplo()), "content": []}) == id_
    )
    _sigue(almacen, id_)


def test_una_ficha_del_experto_que_no_valida(almacen: Almacen) -> None:
    """El experto da el suceso por bueno pero sin país: no es una decisión de retirar."""
    peticion, id_ = _publicada(almacen)
    sin_pais = ficha_ejemplo(pais=campo(None), lugar_suceso=campo(None))
    assert _experto(almacen, peticion, sin_pais) == id_
    _sigue(almacen, id_)


def test_el_experto_que_dice_que_no_es_un_suceso_si_retira(
    almacen: Almacen, cerrojo_en_observar: None
) -> None:
    peticion, id_ = _publicada(almacen)
    no_es = ficha_ejemplo(es_incidente=campo(False, "Drone strikes hit two ships", 0.8))
    assert _experto(almacen, peticion, no_es) is None
    assert "retirado" in _ficha(almacen, id_) and not _fallos(almacen)


def test_el_veredicto_no_retira_la_ficha_que_cuenta_una_autoridad(almacen: Almacen) -> None:
    """En «aplicar», como producción: la ficha de ejemplo la cuenta la policía, y una ficha así no
    la retira una decisión automática (docs/cerrojo.md): se queda publicada y queda apuntado."""
    peticion, id_ = _publicada(almacen)
    no_es = ficha_ejemplo(es_incidente=campo(False, "Drone strikes hit two ships", 0.8))
    assert _experto(almacen, peticion, no_es) is None
    assert "retirado" not in _ficha(almacen, id_)
    assert any(clave.startswith(f"retenido:{id_}:retirado") for clave in almacen.controles())


def test_el_veredicto_de_las_fuentes_con_una_respuesta_ilegible_no_retira(
    almacen: Almacen, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Una categoría dudosa (análisis, entrevista) la decide el experto: sin su ficha, no retira."""
    peticion, id_ = _publicada(almacen)
    dudoso = SimpleNamespace(
        segura=False, documento=dict, motivo=lambda: "análisis", motivo_en=lambda: "analysis",
        motivo_escalado=lambda: "x",
    )  # fmt: skip
    monkeypatch.setattr(no_es_suceso, "de_fuentes", lambda *_: dudoso)
    assert (
        _experto(almacen, peticion, respuesta_={**respuesta(ficha_ejemplo()), "content": []}) == id_
    )
    _sigue(almacen, id_)


@pytest.mark.parametrize("rehacer", [False, True])
def test_reconstruir_con_un_fallo_al_guardar(
    almacen: Almacen, monkeypatch: pytest.MonkeyPatch, rehacer: bool
) -> None:
    _, id_ = _publicada(almacen)
    monkeypatch.setattr(almacen, "guardar_incidente", _invalido)
    assert extraccion.reconstruir(almacen, AHORA, MODELOS, rehacer=rehacer) == 0
    monkeypatch.undo()
    _sigue(almacen, id_)
    assert next(iter(_fallos(almacen).values()))["camino"] == "reconstruccion"


def test_reconstruir_con_una_ficha_que_ya_no_es_publicable(
    almacen: Almacen, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, id_ = _publicada(almacen)
    monkeypatch.setattr(extraccion, "revalidar", lambda validada, *_: Validada({}, []))
    monkeypatch.setattr(extraccion, "completar_pais", lambda *_: None)
    monkeypatch.setattr(extraccion, "recuperar_inicio", lambda *_: None)
    extraccion.reconstruir(almacen, AHORA, MODELOS)
    _sigue(almacen, id_)
    assert "no publicable" in next(iter(_fallos(almacen).values()))["error"]


# --- La retirada en el cerrojo ----------------------------------------------------------------


def _sin_autoridad() -> Documento:
    documento = ficha()
    documento["fuentes"] = documento["fuentes"][:1]
    documento["presencia_dron"] = "no_confirmada"
    documento["estado"] = {
        "actual": "notificado",
        "historial": documento["estado"]["historial"][:1],
    }
    documento["afirmaciones"] = [
        a for a in documento["afirmaciones"] if a["fuente_id"] == documento["fuentes"][0]["id"]
    ]
    return documento


def _retirada(documento: Documento) -> Documento:
    return {**documento, "retirado": {
        "fecha": {"valor": "2026-10-13T14:17Z", "precision": "minuto"}, "motivo": "un fallo",
    }}  # fmt: skip


@pytest.mark.parametrize("modo", [protegido.OBSERVAR, protegido.APLICAR])
def test_una_retirada_sin_decision_se_retiene(monkeypatch: pytest.MonkeyPatch, modo: str) -> None:
    monkeypatch.setattr(protegido, "modo", lambda: modo)
    almacen = base(_sin_autoridad())
    guardado = _ficha(almacen, "EODI-2026-09600")
    almacen.guardar_incidente(_retirada(guardado), AHORA_CERROJO, VOCABULARIO_MODELOS)
    ((clave, apunte),) = almacen.controles(protegido.PREFIJO_RETENIDO).items()
    assert ":retirado:" in clave and apunte["nivel"] == protegido.PUBLICADA
    assert apunte["modo"] == modo
    retirada = "retirado" in _ficha(almacen, "EODI-2026-09600")
    assert retirada is (modo == protegido.OBSERVAR)
    if modo == protegido.APLICAR:
        assert _ficha(almacen, "EODI-2026-09600") == guardado


@pytest.mark.parametrize("modo", [protegido.OBSERVAR, protegido.APLICAR])
def test_el_veredicto_si_retira_en_los_dos_modos(
    almacen: Almacen, monkeypatch: pytest.MonkeyPatch, modo: str
) -> None:
    monkeypatch.setattr(protegido, "modo", lambda: modo)
    monkeypatch.setattr(declaraciones, "de_autoridad", lambda _: False)
    monkeypatch.setattr(protegido, "fichas_manuales", frozenset)
    peticion, id_ = _publicada(almacen)
    no_es = ficha_ejemplo(es_incidente=campo(False, "Drone strikes hit two ships", 0.8))
    _experto(almacen, peticion, no_es)
    assert "retirado" in _ficha(almacen, id_)
    assert not almacen.controles(protegido.PREFIJO_RETENIDO)
    ((_, apunte),) = almacen.controles(f"{protegido.PREFIJO_PERMITIDO}{id_}:retirado").items()
    assert apunte["motivo"] == "decision"


@pytest.mark.parametrize(
    "paso",
    [
        "recogida.barrera.resolver",
        "recogida.repaso_entrada.retirar",
        "recogida.revisados.retirar",
        "proceso.extraccion.retirar_por_veredicto",
    ],
)
def test_cada_decision_explicita_pasa(paso: str) -> None:
    guardado = _sin_autoridad()
    veredicto = protegido.juzgar(guardado, _retirada(guardado), [paso], lambda _: "")
    assert not veredicto.retenidos
    ((cambio, motivo),) = veredicto.permitidos
    assert cambio.dato == "retirado" and motivo in ("decision", "revision")


@pytest.mark.parametrize(
    "paso",
    ["proceso.extraccion.reconstruir", "proceso.extraccion.retirar_del_candidato",
     "proceso.incursiones.retirar"],
)  # fmt: skip
def test_lo_demas_no_es_una_decision(paso: str) -> None:
    guardado = _sin_autoridad()
    veredicto = protegido.juzgar(guardado, _retirada(guardado), [paso], lambda _: "")
    assert [c.dato for c in veredicto.retenidos] == ["retirado"]


def test_la_ficha_de_una_autoridad_no_la_retira_ni_una_decision_automatica() -> None:
    """EODI-2026-00181, 29/10/2026: como hasta ahora, solo una revisión a mano."""
    guardado = ficha()
    veredicto = protegido.juzgar(
        guardado, _retirada(guardado), ["recogida.barrera.resolver"], lambda _: ""
    )
    assert [c.dato for c in veredicto.retenidos] == ["retirado"]


def test_lo_retenido_no_arrastra_afirmaciones_de_fuentes_ausentes() -> None:
    """El mismo defecto en el cerrojo en «aplicar»: la presencia guardada se conserva sin citar
    una fuente que la versión nueva no lleva."""
    guardado = ficha()
    nuevo = copy.deepcopy(guardado)
    nuevo["fuentes"] = nuevo["fuentes"][:1]
    nuevo["afirmaciones"] = [a for a in nuevo["afirmaciones"] if a["campo"] != "presencia_dron"]
    cambio = protegido.Cambio("presencia_dron", protegido.MANUAL, "confirmada", "no_confirmada")
    resultado = protegido.conservar(nuevo, guardado, [cambio])
    assert resultado["presencia_dron"] == "confirmada"
    assert not [a for a in resultado["afirmaciones"] if a["campo"] == "presencia_dron"]


# --- El resumen y la vigilancia ---------------------------------------------------------------


def test_el_resumen_lleva_los_guardados_fallidos() -> None:
    lineas = visitas.lineas_cerrojo({
        "modo": "observar", "retenidos": [], "guardados_fallidos": ["EODI-2026-00130"],
    })  # fmt: skip
    assert "  Guardados fallidos de fichas publicadas: 1" in lineas
    assert "  - EODI-2026-00130" in lineas
    assert "  Guardados fallidos de fichas publicadas: 0" in visitas.lineas_cerrojo(
        {"modo": "observar", "retenidos": []}
    )


def test_tres_fallos_seguidos_abren_incidencia_y_un_guardado_bueno_los_corta(
    almacen: Almacen, monkeypatch: pytest.MonkeyPatch
) -> None:
    peticion, id_ = _publicada(almacen)
    with monkeypatch.context() as parche:
        parche.setattr(almacen, "guardar_incidente", _invalido)
        for horas in (1, 2, 3):
            extraccion.reconstruir(almacen, AHORA + timedelta(hours=horas), MODELOS)
    estado = control_fichas.cerrojo_del_dia(almacen, AHORA + timedelta(hours=3), {})
    assert estado["fallos_repetidos"] == [id_]
    assert estado["guardados_fallidos"] == {coste.dia(AHORA + timedelta(hours=3)): [id_]}
    assert [p["id"] for p in vigilancia.problemas_del_cerrojo({"cerrojo": estado})] == [
        "guardado_fallido_repetido"
    ]
    # Sin identificadores: salud.json es público.
    frase = vigilancia.problemas_del_cerrojo({"cerrojo": estado})[0]["frase"]
    assert "EODI" not in frase
    extraccion.reconstruir(almacen, AHORA + timedelta(hours=4), MODELOS)
    assert not protegido.fallos_seguidos(_fallos(almacen))
    with monkeypatch.context() as parche:
        parche.setattr(almacen, "guardar_incidente", _invalido)
        extraccion.reconstruir(almacen, AHORA + timedelta(hours=5), MODELOS)
    assert protegido.fallos_seguidos(_fallos(almacen)) == {id_: 1}
    assert peticion.candidato["id"]


def test_dos_fallos_no_abren_incidencia() -> None:
    apuntes = {
        f"guardado_fallido:EODI-2026-00001:2026-11-0{d}T00:00:00Z": {"fecha": f"2026-11-0{d}"}
        for d in (1, 2)
    }
    assert protegido.fallos_seguidos(apuntes) == {"EODI-2026-00001": 2}
