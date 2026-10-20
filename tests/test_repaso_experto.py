"""El repaso de todo lo publicado con el experto (recogida/control_fichas.repaso_experto,
docs/control_fichas.md): por lotes, con su presupuesto aparte de los topes de cada día y del mes,
por el camino normal (uniones y correcciones con su cita y su motivo) y sin repetir lo que ya
decidió; y el lugar de la instalación que el titular nombra por su tipo y su ciudad
(proceso/lugar_preciso.py)."""

import contextlib
import copy
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from almacen.base import Almacen
from modelo import coste
from proceso import lugar_preciso
from proceso.noticias import nomenclator
from recogida import control_fichas
from tests import ejemplos
from tests.test_control_fichas import (
    ServicioLotes,
    _base,
    _nuremberg_alemana,
    _nuremberg_griega,
)

EXPERTO = "modelo-experto-de-prueba"


class LotesDelExperto(ServicioLotes):
    """El experto por lotes: sus respuestas llevan su modelo."""

    modelo = EXPERTO

    def mensaje(self, cuerpo: dict[str, Any]) -> dict[str, Any]:
        return {**super().mensaje(cuerpo), "model": EXPERTO}


class ConExperto:
    """El servicio del modelo base, que nunca se llama en el repaso: solo da el experto."""

    def __init__(self) -> None:
        self.experto_ = LotesDelExperto()

    def mensaje(self, cuerpo: dict[str, Any]) -> dict[str, Any]:
        raise AssertionError("el repaso con el experto no llama al modelo base")

    def experto(self) -> LotesDelExperto:
        return self.experto_


@pytest.fixture(autouse=True)
def sin_descargas(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(control_fichas, "descargar", lambda enlaces, plazo: {})
    monkeypatch.setattr(control_fichas, "paginas_de", lambda enlaces, plazo: {})


def _base_de(almacen: Almacen) -> control_fichas.Base:
    return control_fichas.Base(
        abrir=lambda: almacen, guardar=lambda a: None, cerrojo=contextlib.nullcontext
    )


def test_repaso_con_el_experto_por_el_camino_normal_y_con_su_presupuesto() -> None:
    almacen = _base(_nuremberg_alemana(), _nuremberg_griega())
    servicio = ConExperto()
    resultado = control_fichas.repaso_experto(
        _base_de(almacen), lambda: servicio, dormir=lambda s: None, grupos=[]
    )
    # Dos lotes del experto: los pares y después las fichas.
    assert len(servicio.experto_.lotes) == 2
    assert resultado.unidos == ["EODI-2026-09516 -> EODI-2026-09515"]
    queda = almacen.incidente("EODI-2026-09515")
    assert queda is not None and queda["drones"]["numero"] == "desconocido"
    assert queda["control"]["modelos"]["drones"] == EXPERTO
    # Con su motivo en el historial.
    assert any(
        str((h.get("nuevo") or {}).get("motivo", "")).startswith(control_fichas.PREFIJO_UNION)
        for h in almacen.historial("EODI-2026-09515")
    )
    llamadas = [ll for ll in almacen.llamadas() if ll["modo"] == "repaso_experto"]
    assert llamadas and all(ll["lote"] for ll in llamadas)
    gastado = almacen.gastado(coste.Modo.REPASO_EXPERTO.value)
    assert gastado > 0
    # Fuera del tope diario del experto y del total del mes.
    dia = coste.dia(datetime.now(UTC))
    assert almacen.gastado_modelo(EXPERTO, dia) == 0.0
    assert coste.del_mes(almacen, datetime.now(UTC), EXPERTO).total == 0.0
    # Lo ya decidido con las mismas fuentes no se repite.
    decisiones = almacen.controles()
    assert decisiones["verificacion:EODI-2026-09515"].get("repaso_experto")
    otra = control_fichas.repaso_experto(
        _base_de(almacen), lambda: servicio, dormir=lambda s: None, grupos=[]
    )
    assert len(servicio.experto_.lotes) == 2 and otra.llamadas == 0


def test_el_repaso_se_para_en_su_presupuesto(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(coste, "LIMITE_REPASO_EXPERTO_USD", 0.0)
    almacen = _base(_nuremberg_alemana(), _nuremberg_griega())
    servicio = ConExperto()
    resultado = control_fichas.repaso_experto(
        _base_de(almacen), lambda: servicio, dormir=lambda s: None, grupos=[]
    )
    assert servicio.experto_.lotes == [] and resultado.parada == "limite_gasto"


def test_lo_que_no_cabe_en_el_peor_caso_va_en_el_lote_siguiente(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """El peor caso reserva más de lo que se gasta: lo que no cabe en un lote va en el siguiente,
    con el presupuesto que queda de verdad."""
    monkeypatch.setattr(control_fichas, "_peor_lote", lambda peticion, modelo=None: 1.0)
    monkeypatch.setattr(coste, "LIMITE_REPASO_EXPERTO_USD", 1.5)
    almacen = _base(_nuremberg_alemana(), _nuremberg_griega())
    servicio = ConExperto()
    servicio.experto_.decision = "distinto"
    resultado = control_fichas.repaso_experto(
        _base_de(almacen), lambda: servicio, dormir=lambda s: None, grupos=[]
    )
    # El par y después cada ficha en su lote.
    assert [len(lote) for lote in servicio.experto_.lotes] == [1, 1, 1]
    assert resultado.parada is None and resultado.verificadas == 2


def test_sin_experto_por_lotes_no_hace_nada() -> None:
    almacen = _base(_nuremberg_alemana())
    resultado = control_fichas.repaso_experto(
        _base_de(almacen), lambda: object(), dormir=lambda s: None, grupos=[]
    )
    assert resultado.errores == ["sin experto por lotes"] and resultado.llamadas == 0


def _de_constanza(id_: str, dias: int) -> dict[str, Any]:
    d = copy.deepcopy(_nuremberg_griega())
    d["id"] = id_
    inicio = datetime(2026, 10, 13, 12, 30, tzinfo=UTC) + timedelta(days=dias)
    d["tiempo"] = {"inicio": ejemplos.instante(inicio.strftime("%Y-%m-%dT%H:%MZ"), "aproximada")}
    return d


def test_los_grupos_comparan_las_fichas_a_menos_de_tres_dias() -> None:
    almacen = _base(
        _de_constanza("EODI-2026-09601", -11),
        _de_constanza("EODI-2026-09602", -9),
        _de_constanza("EODI-2026-09603", 0),
    )
    ahora, resultado = datetime.now(UTC), control_fichas.Resultado()
    llamador = control_fichas.Llamador(almacen, None, coste.Modo.CONTROL, ahora, None, resultado)
    ctx = control_fichas.Contexto(
        almacen, ahora, frozenset(), llamador, resultado, None, None, almacen.controles()
    )
    grupo = [["EODI-2026-09601", "EODI-2026-09602", "EODI-2026-09603", "EODI-2026-09999"]]
    pares = control_fichas.pares_de_grupos(ctx, grupo)
    assert [(a["id"], b["id"]) for a, b, _ in pares] == [("EODI-2026-09601", "EODI-2026-09602")]


def test_grupos_de_la_configuracion() -> None:
    grupos = control_fichas.grupos_del_repaso()
    assert ["EODI-2026-00057", "EODI-2026-00236"] in grupos
    assert any("EODI-2026-00207" in g for g in grupos)


# --- La instalación que el titular nombra por su tipo y su ciudad ---------------------------------
def _en_el_pais(pais: str, titulo_en: str, titulo_es: str) -> dict[str, Any]:
    d = ejemplos.incidente_minimo()
    d["lugar"] = {"pais": pais, "nivel": "pais"}
    d["titulo"] = {"es": titulo_es, "en": titulo_en}
    return d


@pytest.mark.parametrize(
    ("pais", "en", "es", "sitio"),
    [
        # Una pista sin código OACI no hace dudar del aeropuerto (EODI-2026-00055).
        ("PL", "Delays at Krakow airport due to possible drone sighting",
         "Retrasos en el aeropuerto de Cracovia por avistamiento de posible dron", "EPKK"),
        # El puerto, por su tipo y su ciudad (EODI-2026-00207).
        ("RO", "Drone explodes at Port of Constanța", "Dron explota en el Puerto de Constanza",
         "puerto:way/1201737129"),
        # El aeropuerto con la ciudad en su nombre (EODI-2026-00050).
        ("GR", "Drone intercepted near Alexandroupoli airport by Greek fighter jets",
         "Dron interceptado cerca del aeropuerto de Alexandrópolis por cazas griegos", "LGAL"),
    ],
)  # fmt: skip
def test_la_instalacion_del_titular_por_su_ciudad(pais: str, en: str, es: str, sitio: str) -> None:
    nom = nomenclator()
    hallado = lugar_preciso.instalacion_del_titulo(_en_el_pais(pais, en, es), nom)
    assert hallado is not None and hallado.id == sitio
    nuevo = lugar_preciso.precisar(_en_el_pais(pais, en, es), nom, datetime.now(UTC))
    assert nuevo is not None and nuevo["lugar"]["nivel"] == "instalacion"


@pytest.mark.parametrize(
    ("pais", "en", "es"),
    [
        # Dos aeropuertos: ninguno.
        ("FR", "Two possible drones fly over the surroundings of Paris airports Roissy and "
         "Le Bourget", "Dos posibles drones sobrevuelan los alrededores de los aeropuertos "
         "parisinos de Roissy y Le Bourget"),
        ("PL", "NATO jets scrambled and two airports shut in Poland after attack on Ukraine",
         "Cazas de la OTAN despegan y dos aeropuertos cierran en Polonia tras un ataque en "
         "Ucrania"),
        # Dos aeropuertos con el nombre de la ciudad: ninguno.
        ("PL", "Drones shot down force Warsaw airport to close",
         "Drones derribados obligan a cerrar el aeropuerto de Varsovia"),
        # Una base sin nombre ni ciudad.
        ("DE", "Drone shot down over military base in Saxony-Anhalt",
         "Dron derribado sobre base militar en Sajonia-Anhalt"),
    ],
)  # fmt: skip
def test_sin_una_sola_instalacion_no_hay_lugar(pais: str, en: str, es: str) -> None:
    assert lugar_preciso.instalacion_del_titulo(_en_el_pais(pais, en, es), nomenclator()) is None
