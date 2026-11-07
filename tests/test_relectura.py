"""Una lectura nueva no borra lo que una autoridad ya había dicho (proceso/relectura.py)."""

from typing import Any

import pytest

from almacen.base import Almacen
from modelo import coste
from proceso import extraccion, relectura
from tests.test_extraccion import AHORA, MODELOS, campo, ficha_ejemplo
from tests.test_modelos import EXPERTO, Cliente, _peticion
from tests.test_modelos import _respuesta as _respuesta_modelo

# EODI-2026-00766 (Vărăncău, Moldavia), tal como la trae news.yam.md de Ziarul de Gardă el 6 de
# noviembre de 2026: la autoridad va al final del párrafo, en la frase de los restos.
TEXTO_766 = (
    "O dronă a survolat neautorizat spațiul aerian al R. Moldova, pe 4 noiembrie, în zona "
    "localităților Camenca, din regiunea transnistreană, și Vărăncău, raionul Soroca. O zi mai "
    "târziu, fragmentele unei drone au fost depistate în extravilanul localității Gordinești, "
    "raionul Rezina. Acestea nu conțineau încărcătură explozivă, anunță Ministerul Apărării."
)
FRASE_MINISTERIO = "Acestea nu conțineau încărcătură explozivă, anunță Ministerul Apărării."
MINISTERIO = {
    "afirma": "drones", "autor": "", "autor_pais": "", "autor_situacion": "", "autor_tipo": "",
    "autoridad": "Ministerul Apărării", "categoria": "ministerio", "cita_literal": False,
    "frase": FRASE_MINISTERIO, "fuente": 1, "pais": "MD",
}  # fmt: skip
SURVOL = "O dronă a survolat neautorizat spațiul aerian al R. Moldova"


def _lectura_publicada_766() -> dict[str, Any]:
    """La lectura de producción (6 de noviembre de 2026, 15:17 UTC), la que se publicó."""
    return {
        "incidente": "EODI-2026-00766",
        "declaraciones": [MINISTERIO],
        "ficha": {
            "declaraciones": [MINISTERIO],
            "presencia_dron": campo("confirmada", FRASE_MINISTERIO, 0.85),
            "dron_estatal": campo(True, "fragmentele unei drone", 0.6),
            "entrada_exterior": campo(True, SURVOL, 0.7),
        },
    }


def _publicada_766() -> dict[str, Any]:
    return {
        "id": "EODI-2026-00766",
        "presencia_dron": "confirmada",
        "tipo": "incursion",
        "pruebas": {"dron_estatal": True, "entrada_exterior": True, "evidencia": ["restos"]},
        "fuentes": [
            {"id": "gdelt-a644224aecf0d04e", "es_autoridad": False, "frase_origen": SURVOL},
            {"id": "gdelt-a644224aecf0d04e-declaracion-1", "es_autoridad": True,
             "frase_origen": FRASE_MINISTERIO},
        ],
    }  # fmt: skip


def _lectura_nueva_766(**cambios: Any) -> dict[str, Any]:
    """La lectura del ensayo del 7 de noviembre de 2026: sin la declaración ni el entrar desde
    fuera, y la presencia sin confirmar."""
    return {
        "declaraciones": [],
        "presencia_dron": campo("no_confirmada", SURVOL, 0.6),
        "dron_estatal": campo(True, "fragmentele unei drone", 0.6),
        "entrada_exterior": campo(None),
        **cambios,
    }


def test_la_00766_conserva_la_declaracion_la_presencia_y_la_entrada() -> None:
    leida, motivos = relectura.conservar(
        _lectura_nueva_766(), _lectura_publicada_766(), _publicada_766(), (TEXTO_766,)
    )
    assert leida["declaraciones"] == [MINISTERIO]
    assert leida["presencia_dron"]["valor"] == "confirmada"
    assert leida["presencia_dron"]["frase"] == FRASE_MINISTERIO
    assert leida["entrada_exterior"]["valor"] is True
    assert len(motivos) == 3 and all(m.startswith(relectura.MOTIVO) for m in motivos)


def test_una_autoridad_en_contra_manda_sobre_lo_publicado() -> None:
    # Como el Ministerio de Defensa rumano en EODI-2026-00743: «dron no confirmado».
    contra = {**MINISTERIO, "afirma": "sin_drones", "frase": "nu conțineau încărcătură"}
    nueva = _lectura_nueva_766(declaraciones=[contra])
    leida, motivos = relectura.conservar(
        nueva, _lectura_publicada_766(), _publicada_766(), (TEXTO_766,)
    )
    assert leida == nueva and motivos == []
    # La autoridad que lo deja abierto, con la frase de su declaración, también.
    abierta = {**MINISTERIO, "afirma": "incidente"}
    nueva = _lectura_nueva_766(
        declaraciones=[abierta], presencia_dron=campo("no_confirmada", FRASE_MINISTERIO)
    )
    assert (
        relectura.conservar(nueva, _lectura_publicada_766(), _publicada_766(), (TEXTO_766,))[1]
        == []
    )


def test_si_la_frase_ya_no_esta_en_las_fuentes_no_se_conserva() -> None:
    texto = TEXTO_766.replace(", anunță Ministerul Apărării", "")
    nueva = _lectura_nueva_766()
    leida, _ = relectura.conservar(nueva, _lectura_publicada_766(), _publicada_766(), (texto,))
    assert leida["declaraciones"] == [] and leida["presencia_dron"]["valor"] == "no_confirmada"


def test_solo_lo_que_la_ficha_publicada_tiene_de_verdad() -> None:
    # Una publicada sin la fuente de autoridad, no confirmada y sin la entrada en sus pruebas.
    publicada = {**_publicada_766(), "presencia_dron": "no_confirmada", "pruebas": {}}
    publicada["fuentes"] = publicada["fuentes"][:1]
    nueva = _lectura_nueva_766()
    leida, motivos = relectura.conservar(nueva, _lectura_publicada_766(), publicada, (TEXTO_766,))
    assert leida == nueva and motivos == []


def test_sin_lectura_publicada_vale_la_nueva() -> None:
    nueva = _lectura_nueva_766()
    assert relectura.conservar(nueva, None, _publicada_766(), (TEXTO_766,)) == (nueva, [])
    lecturas = [{"incidente": "EODI-2026-00766", "ficha_base": {}}]
    assert relectura.lectura_publicada(lecturas, "EODI-2026-00766") is None


# --- Por la extracción, con la lectura del experto (la que ya no se escala) -------------------

POLICIA = {
    "autoridad": "Københavns Politi", "pais": "DK", "categoria": "policia", "afirma": "drones",
    "autor": "", "autor_tipo": "institucion", "autor_pais": "DK", "autor_situacion": "",
    "cita_literal": True, "fuente": 1, "frase": "observeret tre til fire store droner",
}  # fmt: skip


@pytest.fixture
def almacen() -> Any:
    a = Almacen.abrir()
    yield a
    a.cerrar()


def _leer(almacen: Almacen, peticion: extraccion.Peticion, respuesta: dict[str, Any]) -> str:
    cliente = Cliente(respuesta, None)
    cliente.modelo = EXPERTO
    hechas = extraccion.extraer(almacen, cliente, [peticion], AHORA, coste.Modo.HORARIO, MODELOS)
    assert cliente.pedidas == [EXPERTO]
    (id_,) = hechas.incidentes
    assert id_ is not None
    return id_


def test_una_relectura_no_rebaja_la_ficha_publicada(almacen: Almacen) -> None:
    peticion = _peticion(almacen)
    id_ = _leer(almacen, peticion, ficha_ejemplo(
        presencia_dron=campo("confirmada", "observeret tre til fire store droner"),
        declaraciones=[POLICIA],
    ))  # fmt: skip
    publicada = almacen.incidente(id_)
    assert publicada is not None and publicada["presencia_dron"] == "confirmada"
    # La relectura no trae la declaración de la policía ni la presencia.
    assert _leer(almacen, peticion, ficha_ejemplo()) == id_
    despues = almacen.incidente(id_)
    assert despues is not None and despues["presencia_dron"] == "confirmada"
    assert any(f.get("es_autoridad") for f in despues["fuentes"])
    ultima = almacen.extracciones(peticion.candidato["id"])[-1]
    assert any(m.startswith(relectura.MOTIVO) for m in ultima["motivos"])


def test_tambien_en_la_ficha_fundida_en_otra(almacen: Almacen) -> None:
    """EODI-2026-00766 está fundida en la 00748 desde el 6 de noviembre de 2026: su relectura
    también conserva lo que dijo la autoridad (vuelve a publicarse si se separa)."""
    peticion = _peticion(almacen)
    id_ = _leer(almacen, peticion, ficha_ejemplo(
        presencia_dron=campo("confirmada", "observeret tre til fire store droner"),
        declaraciones=[POLICIA],
    ))  # fmt: skip
    fundida = almacen.incidente(id_)
    assert fundida is not None
    almacen._escribir_incidente({**fundida, "fusionado_en": "EODI-2026-09999"})
    extraccion.procesar_respuesta(
        almacen, peticion, _respuesta_modelo(ficha_ejemplo(), EXPERTO), AHORA,
        coste.Modo.HORARIO, False, MODELOS,
    )  # fmt: skip
    ultima = almacen.extracciones(peticion.candidato["id"])[-1]
    assert any(m.startswith(relectura.MOTIVO) for m in ultima["motivos"])
