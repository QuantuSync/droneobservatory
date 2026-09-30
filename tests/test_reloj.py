"""Reloj de la recogida sin red ni esperas: órdenes falsas y reloj falso."""

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from recogida import reloj
from recogida.reloj import Actions, OrdenFallida

# Un turno que arranca justo después de un lanzamiento, como el de relevo.
INICIO = datetime(2026, 9, 30, 15, 18, tzinfo=UTC)
PROPIA = "500"


class Tiempo:
    """Reloj falso: dormir avanza la hora sin esperar de verdad."""

    def __init__(self, ahora: datetime = INICIO) -> None:
        self.ahora = ahora
        self.esperas: list[float] = []

    def __call__(self) -> datetime:
        return self.ahora

    def dormir(self, segundos: float) -> None:
        self.esperas.append(segundos)
        self.ahora += timedelta(seconds=segundos)


class Github:
    """Órdenes falsas: responde las ejecuciones preparadas y anota lo lanzado con su hora."""

    def __init__(self, tiempo: Tiempo | None = None) -> None:
        self.tiempo = tiempo or Tiempo()
        self.ejecuciones: dict[str, list[dict[str, object]]] = {reloj.RECOGIDA: [], reloj.RELOJ: []}
        self.lanzados: list[tuple[str, datetime]] = []
        self.fallos: list[str] = []
        self.ordenes: list[list[str]] = []

    def __call__(self, argumentos: list[str]) -> str:
        self.ordenes.append(argumentos)
        if self.fallos and " ".join(argumentos).startswith(self.fallos[0]):
            self.fallos.pop(0)
            raise OrdenFallida("HTTP 502")
        if argumentos[:2] == ["workflow", "run"]:
            assert argumentos[3:] == ["--ref", reloj.RAMA]
            self.lanzados.append((argumentos[2], self.tiempo.ahora))
            return ""
        assert argumentos[:3] == ["run", "list", "--workflow"]
        return json.dumps(self.ejecuciones[argumentos[3]])

    def actions(self) -> Actions:
        return Actions(self, self.tiempo.dormir, PROPIA)


def ejecucion(id_: int, estado: str) -> dict[str, object]:
    return {"databaseId": id_, "status": estado}


# --- Horas ----------------------------------------------------------------------------


def test_un_turno_de_relevo_lanza_cinco_recogidas_en_su_minuto() -> None:
    horas = reloj.lanzamientos(INICIO)
    assert [f"{h:%H:%M:%S}" for h in horas] == [
        "16:17:00",
        "17:17:00",
        "18:17:00",
        "19:17:00",
        "20:17:00",
    ]


def test_un_turno_que_arranca_en_el_minuto_justo_lanza_ya() -> None:
    en_punto = INICIO.replace(minute=reloj.MINUTO_LANZAMIENTO)
    assert reloj.lanzamientos(en_punto)[0] == en_punto


def test_ningun_turno_pasa_de_su_duracion() -> None:
    # Arrancado por el respaldo a media hora: el último lanzamiento cae dentro del turno.
    inicio = INICIO.replace(minute=47, second=20)
    horas = reloj.lanzamientos(inicio)
    assert horas[0] == inicio.replace(hour=16, minute=reloj.MINUTO_LANZAMIENTO, second=0)
    assert horas[-1] - inicio <= reloj.DURACION_TURNO
    assert horas[-1] + reloj.ENTRE_LANZAMIENTOS - inicio > reloj.DURACION_TURNO


def test_el_turno_cabe_en_las_seis_horas_de_un_trabajo() -> None:
    assert timedelta(hours=6) > reloj.DURACION_TURNO


# --- Turno ----------------------------------------------------------------------------


def test_el_turno_lanza_cada_hora_y_despues_el_relevo() -> None:
    github = Github()
    assert reloj.turno(github.actions(), github.tiempo, github.tiempo.dormir) == 0
    horas = reloj.lanzamientos(INICIO)
    assert github.lanzados == [
        *[(reloj.RECOGIDA, hora) for hora in horas],
        # El relevo sale con el último lanzamiento: le queda casi una hora hasta el suyo.
        (reloj.RELOJ, horas[-1]),
    ]
    hasta_el_primero = (horas[0] - INICIO).total_seconds()
    entre_dos = reloj.ENTRE_LANZAMIENTOS.total_seconds()
    assert github.tiempo.esperas == [hasta_el_primero, *[entre_dos] * (len(horas) - 1)]


def test_con_una_recogida_en_cola_o_en_marcha_no_lanza_otra() -> None:
    github = Github()
    github.ejecuciones[reloj.RECOGIDA] = [ejecucion(1, "in_progress")]
    assert not reloj.lanzar_recogida(github.actions())
    github.ejecuciones[reloj.RECOGIDA] = [ejecucion(1, "queued"), ejecucion(2, "completed")]
    assert not reloj.lanzar_recogida(github.actions())
    assert github.lanzados == []
    github.ejecuciones[reloj.RECOGIDA] = [ejecucion(1, "completed")]
    assert reloj.lanzar_recogida(github.actions())
    assert [w for w, _ in github.lanzados] == [reloj.RECOGIDA]


def test_un_tropiezo_de_la_api_se_reintenta() -> None:
    github = Github()
    github.fallos = ["workflow run"] * (reloj.INTENTOS - 1)
    assert reloj.lanzar_recogida(github.actions())
    assert github.tiempo.esperas == [reloj.ESPERA_ENTRE_INTENTOS_S] * (reloj.INTENTOS - 1)


def test_si_no_se_sabe_si_hay_una_recogida_se_lanza_igual() -> None:
    github = Github()
    github.fallos = ["run list"] * reloj.INTENTOS
    assert reloj.lanzar_recogida(github.actions())


def test_una_recogida_sin_lanzar_no_para_el_turno() -> None:
    github = Github()
    github.fallos = ["workflow run"] * reloj.INTENTOS
    assert reloj.turno(github.actions(), github.tiempo, github.tiempo.dormir) == 0
    # Falla el primer lanzamiento; los demás y el relevo salen.
    esperados = len(reloj.lanzamientos(INICIO)) - 1
    assert [w for w, _ in github.lanzados] == [reloj.RECOGIDA] * esperados + [reloj.RELOJ]


def test_un_relevo_sin_lanzar_deja_el_turno_en_rojo() -> None:
    github = Github()
    github.fallos = [f"workflow run {reloj.RELOJ}"] * reloj.INTENTOS
    assert reloj.turno(github.actions(), github.tiempo, github.tiempo.dormir) == 1
    assert reloj.RELOJ not in [w for w, _ in github.lanzados]


# --- Guardia --------------------------------------------------------------------------


def test_a_demanda_siempre_arranca_un_turno() -> None:
    github = Github()
    github.ejecuciones[reloj.RELOJ] = [ejecucion(1, "in_progress")]
    assert reloj.guardia(github.actions(), "workflow_dispatch")
    assert github.ordenes == []


def test_el_respaldo_programado_solo_arranca_si_no_hay_otro_reloj() -> None:
    github = Github()
    # La propia ejecución del respaldo no cuenta.
    github.ejecuciones[reloj.RELOJ] = [ejecucion(int(PROPIA), "in_progress")]
    assert reloj.guardia(github.actions(), reloj.EVENTO_PROGRAMADO)
    for estado in ("in_progress", "queued", "pending"):
        github.ejecuciones[reloj.RELOJ] = [
            ejecucion(int(PROPIA), "in_progress"),
            ejecucion(1, estado),
        ]
        assert not reloj.guardia(github.actions(), reloj.EVENTO_PROGRAMADO)


def test_el_respaldo_no_arranca_si_no_puede_saber_si_hay_otro_reloj() -> None:
    github = Github()
    github.fallos = ["run list"] * reloj.INTENTOS
    assert not reloj.guardia(github.actions(), reloj.EVENTO_PROGRAMADO)


def test_la_guardia_escribe_su_salida_para_el_workflow(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    salidas = tmp_path / "salidas"
    monkeypatch.setenv(reloj.VARIABLE_SALIDAS, str(salidas))
    assert reloj.principal(["guardia", "--evento", "workflow_dispatch"]) == 0
    assert salidas.read_text(encoding="utf-8") == f"{reloj.SALIDA_ARRANCAR}=true\n"
