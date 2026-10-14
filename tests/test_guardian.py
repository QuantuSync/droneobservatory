"""Guardián del sistema (recogida/guardian.py): qué recogidas fallan por el sistema, cuándo se
relanza la recogida y cuándo se reinicia, el tope de un reinicio cada 6 horas, la recogida tras
un arranque, la limpieza del disco, y lo que de él ven la vigilancia y el resumen diario."""

import os
import sys
from collections.abc import Sequence
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from recogida import guardian, vigilancia, visitas

AHORA = datetime(2026, 10, 14, 9, 0, tzinfo=UTC)


def _entradas(*recogidas: tuple[int, Sequence[str]]) -> list[dict[str, Any]]:
    """Diario inventado: (minutos antes de AHORA, mensajes) por recogida."""
    entradas = []
    for minutos, mensajes in recogidas:
        marca = str(int((AHORA - timedelta(minutes=minutos)).timestamp() * 1e6))
        entradas += [{"MESSAGE": m, "__REALTIME_TIMESTAMP": marca} for m in mensajes]
    return entradas


SIN_DEV_NULL = (
    "eodi-recogida.service: Failed to set up standard input: No such file or directory",
    "eodi-recogida.service: Failed at step STDIN spawning /usr/bin/env: No such file",
    "eodi-recogida.service: Failed with result 'exit-code'.",
)
DE_FUENTE = (
    "Starting eodi-recogida.service - Recogida horaria del EODI...",
    "ERROR horaria: nada publicado: la base no responde",
    "eodi-recogida.service: Main process exited, code=exited, status=1/FAILURE",
    "eodi-recogida.service: Failed with result 'exit-code'.",
)
BUENA = (
    "Starting eodi-recogida.service - Recogida horaria del EODI...",
    "estado.json publicado en el almacén",
    "eodi-recogida.service: Deactivated successfully.",
    "Finished eodi-recogida.service - Recogida horaria del EODI.",
)
SIN_MEMORIA = ("eodi-recogida.service: Failed with result 'oom-kill'.",)


class Ordenes:
    """Ejecutor falso: apunta las órdenes y responde con un código fijo."""

    def __init__(self, codigo: int = 0, salida: str = "") -> None:
        self.ordenes: list[list[str]] = []
        self.codigo, self.salida = codigo, salida

    def __call__(self, orden: Sequence[str]) -> tuple[int, str]:
        self.ordenes.append(list(orden))
        return self.codigo, self.salida


def test_distingue_los_fallos_del_sistema_de_los_de_una_fuente() -> None:
    lista = guardian.recogidas(
        _entradas((90, BUENA), (60, DE_FUENTE), (35, SIN_DEV_NULL), (10, SIN_MEMORIA))
    )
    assert [(r.correcta, r.sistema) for r in lista] == [
        (True, False),
        (False, False),
        (False, True),
        (False, True),
    ]
    assert lista[2].motivo == "Failed to set up standard"
    assert lista[3].motivo == "result 'oom-kill'"
    assert len(guardian.fallos_de_sistema(lista)) == 2


def test_una_buena_o_un_fallo_de_fuente_corta_la_racha() -> None:
    for ultimas in [((35, SIN_DEV_NULL), (10, BUENA)), ((35, SIN_DEV_NULL), (10, DE_FUENTE))]:
        assert guardian.fallos_de_sistema(guardian.recogidas(_entradas(*ultimas))) == []
    assert guardian.fallos_de_sistema(guardian.recogidas(_entradas((10, SIN_DEV_NULL)))) == []


def test_relanza_la_recogida_si_acaba_de_reparar_y_reinicia_si_vuelve_a_fallar(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(guardian, "ESTADO", tmp_path / "estado.json")
    entradas = _entradas((35, SIN_DEV_NULL), (10, SIN_DEV_NULL))
    estado: dict[str, Any] = {}

    pasada = guardian.Pasada(ahora=AHORA)
    pasada.reparado("/dev/null", "/dev/null no existía: recreado")
    ordenes = Ordenes()
    guardian.ultimo_recurso(pasada, estado, entradas, ordenes)
    assert ["systemctl", "start", "--no-block", "eodi-recogida.service"] in ordenes.ordenes
    assert not any(o[:2] == ["systemctl", "reboot"] for o in ordenes.ordenes)

    # La misma racha en la pasada siguiente, sin reparar nada más: espera a la relanzada.
    pasada = guardian.Pasada(ahora=AHORA)
    ordenes = Ordenes()
    guardian.ultimo_recurso(pasada, estado, entradas, ordenes)
    assert ordenes.ordenes == [] and pasada.reparaciones == []

    # Si la relanzada vuelve a fallar por el sistema, reinicia.
    entradas += _entradas((1, SIN_DEV_NULL))
    pasada = guardian.Pasada(ahora=AHORA)
    ordenes = Ordenes()
    guardian.ultimo_recurso(pasada, estado, entradas, ordenes)
    assert ["systemctl", "reboot"] in ordenes.ordenes
    assert estado["recogida_pendiente"] is True
    assert len(estado["reinicios"]) == 1
    assert pasada.sin_arreglar == []


def test_reinicia_como_mucho_una_vez_cada_6_horas(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(guardian, "ESTADO", tmp_path / "estado.json")
    entradas = _entradas((35, SIN_MEMORIA), (10, SIN_MEMORIA))
    hace = AHORA - timedelta(hours=5)
    estado: dict[str, Any] = {"reinicios": [{"hora": guardian._iso(hace), "motivo": "x"}]}
    pasada = guardian.Pasada(ahora=AHORA)
    ordenes = Ordenes()
    guardian.ultimo_recurso(pasada, estado, entradas, ordenes)
    assert ordenes.ordenes == []
    assert [p["id"] for p in pasada.sin_arreglar] == ["reinicio"]

    estado["reinicios"][0]["hora"] = guardian._iso(AHORA - timedelta(hours=7))
    pasada = guardian.Pasada(ahora=AHORA)
    guardian.ultimo_recurso(pasada, estado, entradas, ordenes)
    assert ["systemctl", "reboot"] in ordenes.ordenes


def test_solo_cuentan_las_recogidas_de_este_arranque() -> None:
    entradas = _entradas((35, SIN_MEMORIA), (10, SIN_MEMORIA))
    pasada = guardian.Pasada(ahora=AHORA)
    ordenes = Ordenes()
    guardian.ultimo_recurso(pasada, {}, entradas, ordenes, desde=AHORA - timedelta(minutes=5))
    assert ordenes.ordenes == [] and pasada.reparaciones == []


def test_el_simulacro_no_reinicia_ni_gasta_el_reinicio() -> None:
    estado: dict[str, Any] = {}
    pasada = guardian.Pasada(ahora=AHORA)
    ordenes = Ordenes()
    guardian.ultimo_recurso(
        pasada, estado, guardian.simulacro_entradas(AHORA), ordenes, simulacro=True
    )
    assert ordenes.ordenes == []
    assert estado["reinicios"] == [] and estado["simulacro"]
    assert "SIMULACRO" in pasada.reparaciones[0]["frase"]


def test_tras_un_arranque_lanza_la_recogida_pendiente_una_sola_vez() -> None:
    estado: dict[str, Any] = {"arranque": "viejo", "recogida_pendiente": True}
    ordenes = Ordenes(codigo=3, salida="inactive")
    pasada = guardian.Pasada(ahora=AHORA)
    guardian.tras_arranque(pasada, estado, "nuevo", AHORA - timedelta(minutes=30), ordenes)
    assert ["systemctl", "start", "--no-block", "eodi-recogida.service"] in ordenes.ordenes
    assert "recogida_pendiente" not in estado and estado["arranque"] == "nuevo"

    ordenes = Ordenes(codigo=3, salida="inactive")
    guardian.tras_arranque(pasada, estado, "nuevo", None, ordenes)
    assert ordenes.ordenes == []


def test_tras_un_arranque_con_publicacion_reciente_no_lanza_nada() -> None:
    estado: dict[str, Any] = {"arranque": "viejo"}
    ordenes = Ordenes(codigo=3, salida="inactive")
    pasada = guardian.Pasada(ahora=AHORA)
    guardian.tras_arranque(pasada, estado, "nuevo", AHORA - timedelta(minutes=40), ordenes)
    assert ordenes.ordenes == [] and estado["arranques"] == [guardian._iso(AHORA)]
    # Con la hora del arranque, se anota esa y no la de la pasada.
    hace = AHORA - timedelta(minutes=3)
    guardian.tras_arranque(pasada, estado, "tercero", AHORA, ordenes, hora=hace)
    assert estado["arranques"][-1] == guardian._iso(hace)
    # Tras un arranque desde fuera con la recogida parada hace horas, sí.
    guardian.tras_arranque(pasada, estado, "otro", AHORA - timedelta(hours=2), ordenes)
    assert ["systemctl", "start", "--no-block", "eodi-recogida.service"] in ordenes.ordenes


def test_el_disco_solo_se_limpia_por_encima_del_90(tmp_path: Path) -> None:
    pip = tmp_path / ".cache" / "pip" / "http"
    pip.mkdir(parents=True)
    (pip / "trozo").write_bytes(b"x" * 1000)
    datos = tmp_path / "datos" / "trafico"
    datos.mkdir(parents=True)
    (datos / "dia.json").write_text("{}")

    pasada = guardian.Pasada(ahora=AHORA)
    guardian.limpiar_disco(pasada, Ordenes(), lambda: 80.0, tmp_path)
    assert pasada.reparaciones == [] and (pip / "trozo").exists()

    usos = iter([95.0, 70.0])
    ordenes = Ordenes()
    guardian.limpiar_disco(pasada, ordenes, lambda: next(usos), tmp_path)
    assert not (tmp_path / ".cache" / "pip" / "http").exists()
    assert (tmp_path / ".cache" / "pip").is_dir()
    assert (datos / "dia.json").exists()
    assert ["apt-get", "clean"] in ordenes.ordenes
    assert pasada.reparaciones[0]["correcto"] and "70.0 %" in pasada.reparaciones[0]["frase"]


def test_temporales_viejos_solo_del_usuario_y_de_mas_de_un_dia(tmp_path: Path) -> None:
    viejo, nuevo = tmp_path / "viejo", tmp_path / "nuevo"
    viejo.write_text("x")
    nuevo.write_text("x")
    hace_dos_dias = AHORA.timestamp() - 2 * 86400
    os.utime(viejo, (hace_dos_dias, hace_dos_dias))
    uid = viejo.stat().st_uid
    lista = guardian.temporales_viejos([tmp_path], uid, AHORA.timestamp(), timedelta(days=1))
    assert lista == [viejo]
    assert (
        guardian.temporales_viejos([tmp_path], uid + 1, AHORA.timestamp(), timedelta(days=1)) == []
    )


def test_sshd_que_responde_no_se_toca_y_el_que_no_se_reinicia() -> None:
    pasada = guardian.Pasada(ahora=AHORA)
    ordenes = Ordenes()
    guardian.reparar_ssh(pasada, ordenes, lambda: True)
    assert pasada.reparaciones == []
    respuestas = iter([False, False, True])
    guardian.reparar_ssh(pasada, ordenes, lambda: next(respuestas), lambda _s: None)
    assert ["systemctl", "restart", "ssh.socket", "ssh.service"] in ordenes.ordenes
    assert pasada.reparaciones[0]["correcto"]


@pytest.mark.skipif(sys.platform == "win32", reason="dispositivos de Linux")
def test_dispositivo_correcto_reconoce_dev_null() -> None:
    assert guardian.dispositivo_correcto(os.lstat("/dev/null"), 1, 3)
    assert not guardian.dispositivo_correcto(os.lstat("/dev/null"), 1, 5)
    assert not guardian.dispositivo_correcto(None, 1, 3)


def test_el_registro_guarda_30_dias(tmp_path: Path) -> None:
    ruta = tmp_path / "estado.json"
    viejo = guardian._iso(AHORA - timedelta(days=40))
    estado: dict[str, Any] = {
        "reparaciones": [{"hora": viejo, "id": "x", "frase": "x", "correcto": True}],
        "arranques": [viejo, guardian._iso(AHORA)],
    }
    pasada = guardian.Pasada(ahora=AHORA)
    pasada.reparado("/tmp", "/tmp tenía permisos 755: carpeta de root con permisos 1777")
    guardian.escribir_estado(estado, pasada, ruta)
    leido = guardian.leer_estado(ruta)
    assert [r["id"] for r in leido["reparaciones"]] == ["/tmp"]
    assert leido["arranques"] == [guardian._iso(AHORA)]
    assert leido["ultima_pasada"] == guardian._iso(AHORA)


def test_la_vigilancia_ve_lo_que_el_guardian_no_arregla_y_si_se_para() -> None:
    reciente = guardian._iso(AHORA - timedelta(minutes=4))
    assert vigilancia.problemas_del_guardian({"ultima_pasada": reciente}, AHORA) == []
    sin = {"ultima_pasada": reciente, "sin_arreglar": [{"id": "sshd", "frase": "sshd caído"}]}
    assert [p["id"] for p in vigilancia.problemas_del_guardian(sin, AHORA)] == ["guardian"]
    viejo = {"ultima_pasada": guardian._iso(AHORA - timedelta(minutes=25))}
    assert [p["id"] for p in vigilancia.problemas_del_guardian(viejo, AHORA)] == ["guardian_parado"]
    assert [p["id"] for p in vigilancia.problemas_del_guardian({}, AHORA)] == ["guardian_parado"]


def test_el_resumen_cuenta_las_reparaciones_y_los_arranques_del_dia(tmp_path: Path) -> None:
    ruta = tmp_path / "estado.json"
    estado: dict[str, Any] = {"arranques": ["2026-10-13T22:40:00Z", "2026-10-12T10:00:00Z"]}
    pasada = guardian.Pasada(ahora=datetime(2026, 10, 13, 22, 36, tzinfo=UTC))
    pasada.reparado("/dev/null", "/dev/null no existía: recreado con mknod (1,3, 666)")
    guardian.escribir_estado(estado, pasada, ruta)
    lineas = visitas.lineas_guardian(visitas.guardian_del_dia(ruta, date(2026, 10, 14)))
    assert lineas[0] == "  Guardián del sistema: 1 reparaciones"
    assert lineas[1].startswith("  - 00:36 /dev/null no existía")
    assert lineas[2] == "  Arranques del servidor: 1 (00:40)"
    assert visitas.lineas_guardian(visitas.guardian_del_dia(tmp_path / "no", date.today())) == [
        "  Guardián del sistema: sin registro"
    ]
