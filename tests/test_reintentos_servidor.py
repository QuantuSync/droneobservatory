"""Reintentos de las unidades del servidor (servidor/reintentos.sh)."""

import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
SERVIDOR = RAIZ / "servidor"


def _variables() -> dict[str, str]:
    texto = (SERVIDOR / "configuracion.sh").read_text(encoding="utf-8")
    return dict(re.findall(r'^(UNIDAD\w*)="([^"]+)"', texto, re.M))


def _tabla() -> dict[str, str]:
    texto = (SERVIDOR / "reintentos.sh").read_text(encoding="utf-8")
    bloque = texto.split("REINTENTOS=(", 1)[1].split("\n)", 1)[0]
    filas = re.findall(r'^\s*"([^"|]+)\|([^"]*)"', bloque, re.M)
    variables = _variables()
    return {variables.get(u.strip("${}"), u): resto for u, resto in filas}


def test_cada_servicio_por_temporizador_tiene_reintentos_salvo_el_paso_a_solo_disco() -> None:
    instalar = (SERVIDOR / "instalar.sh").read_text(encoding="utf-8")
    variables = _variables()
    con_temporizador = {
        variables[v] for v in re.findall(r'"/etc/systemd/system/\$(UNIDAD\w*)\.timer"', instalar)
    }
    con_temporizador |= {
        variables[v] for v in re.findall(r'^unidad_satelite "\$(UNIDAD\w*)"', instalar, re.M)
    }
    con_temporizador.add(variables["UNIDAD_VISITAS"])
    tabla = _tabla()
    faltan = con_temporizador - set(tabla) - {variables["UNIDAD_BASE_SOLO_DISCO"]}
    assert not faltan
    assert variables["UNIDAD_BASE_SOLO_DISCO"] not in tabla


def test_la_recogida_solo_se_repite_con_un_fallo_que_no_publica() -> None:
    fila = _tabla()["eodi-recogida"]
    espera, ventana, arranques, extra = fila.split("|")
    assert (espera, ventana, arranques) == ("10min", "50min", "3")
    assert "RestartPreventExitStatus=$SALIDA_AVISO" in extra
    assert "RestartMaxDelaySec=15min" in extra


@pytest.mark.skipif(sys.platform == "win32", reason="el script es para Linux")
def test_escribe_los_complementos(tmp_path: Path) -> None:
    entorno = {**os.environ, "EODI_SYSTEMD_DIR": str(tmp_path)}
    subprocess.run(["bash", str(SERVIDOR / "reintentos.sh")], env=entorno, check=True)
    recogida = (tmp_path / "eodi-recogida.service.d" / "reintentos.conf").read_text()
    assert "Restart=on-failure" in recogida
    assert "RestartSec=10min" in recogida
    assert "RestartPreventExitStatus=2" in recogida
    assert "StartLimitBurst=3" in recogida
    reserva = (tmp_path / "eodi-reserva.timer.d" / "reintentos.conf").read_text()
    assert "Persistent=true" in reserva
    assert not (tmp_path / "eodi-base-solo-disco.service.d").exists()
