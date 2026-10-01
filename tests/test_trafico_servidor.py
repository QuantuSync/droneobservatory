"""Cerrojos del procesado de adsb.lol en el servidor: tiene el suyo y nunca retiene el de la
recogida horaria. El script se prueba en Linux con un doble de Python; la configuración y las
unidades de systemd, en cualquier sistema."""

import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
SCRIPT = RAIZ / "servidor" / "trafico.sh"
LINUX = pytest.mark.skipif(sys.platform == "win32", reason="el script es para Linux")

# Doble de Python: anota lo que recibe y si el cerrojo de la recogida está libre mientras
# corre (lo intenta tomar sin esperar).
DOBLE_PYTHON = """#!/usr/bin/env bash
printf '%s\\n' "$*" "$EODI_TRAFICO_DATOS" > "$PRUEBA_VISTO"
if flock --nonblock "$PRUEBA_CERROJO_RECOGIDA" true; then
  echo libre >> "$PRUEBA_VISTO"
else
  echo ocupado >> "$PRUEBA_VISTO"
fi
"""


def test_el_script_solo_usa_su_cerrojo() -> None:
    texto = SCRIPT.read_text(encoding="utf-8")
    assert '"$CERROJO_TRAFICO"' in texto
    assert not re.search(r'"\$CERROJO"', texto)
    configuracion = (RAIZ / "servidor" / "configuracion.sh").read_text(encoding="utf-8")
    assert 'CERROJO_TRAFICO="$SECRETOS/trafico.lock"' in configuracion
    assert 'CERROJO="$SECRETOS/recogida.lock"' in configuracion


def test_la_unidad_va_con_prioridad_baja_y_su_propio_temporizador() -> None:
    instalar = (RAIZ / "servidor" / "instalar.sh").read_text(encoding="utf-8")
    unidad = instalar.split('cat > "/etc/systemd/system/$UNIDAD_TRAFICO.service"')[1].split("FIN")[
        1
    ]
    assert "ExecStart=/usr/bin/env bash $CLON/servidor/trafico.sh" in unidad
    assert "Nice=$TRAFICO_NICE" in unidad and "IOSchedulingClass=idle" in unidad
    assert "recogida.sh" not in unidad
    assert '"$UNIDAD_TRAFICO.timer"' in (RAIZ / "servidor" / "reconstruir.sh").read_text(
        encoding="utf-8"
    )


def test_el_paso_de_la_recogida_horaria_no_toma_el_cerrojo_del_procesado() -> None:
    for modulo in ("recogida/mediciones.py", "proceso/mediciones.py", "recogida/trafico.py"):
        texto = (RAIZ / modulo).read_text(encoding="utf-8")
        assert "flock" not in texto and "fcntl" not in texto


def preparar(tmp_path: Path) -> tuple[dict[str, str], Path]:
    clon = tmp_path / "clon"
    (clon / "servidor").mkdir(parents=True)
    for fichero in ("trafico.sh", "configuracion.sh"):
        (clon / "servidor" / fichero).write_text(
            (RAIZ / "servidor" / fichero).read_text(encoding="utf-8"), encoding="utf-8"
        )
    python = clon / ".venv" / "bin" / "python"
    python.parent.mkdir(parents=True)
    python.write_text(DOBLE_PYTHON, encoding="utf-8")
    python.chmod(0o755)
    secretos = tmp_path / "secretos"
    secretos.mkdir()
    visto = tmp_path / "visto.txt"
    entorno = {
        **os.environ,
        "EODI_CLON": str(clon),
        "EODI_SECRETOS": str(secretos),
        "EODI_TRAFICO_DATOS": str(tmp_path / "datos"),
        "PRUEBA_VISTO": str(visto),
        "PRUEBA_CERROJO_RECOGIDA": str(secretos / "recogida.lock"),
    }
    return entorno, visto


def lanzar(entorno: dict[str, str]) -> subprocess.CompletedProcess[str]:
    script = Path(entorno["EODI_CLON"]) / "servidor" / "trafico.sh"
    return subprocess.run(
        ["bash", str(script)], env=entorno, capture_output=True, text=True, check=False
    )


@LINUX
def test_procesa_sin_retener_el_cerrojo_de_la_recogida(tmp_path: Path) -> None:
    entorno, visto = preparar(tmp_path)
    resultado = lanzar(entorno)
    assert resultado.returncode == 0, resultado.stderr
    orden, datos, cerrojo = visto.read_text(encoding="utf-8").splitlines()
    assert orden == "-m recogida.trafico pendientes --tope-min 50"
    assert datos == str(tmp_path / "datos")
    assert cerrojo == "libre"


@LINUX
def test_procesa_aunque_la_recogida_horaria_este_en_marcha(tmp_path: Path) -> None:
    entorno, visto = preparar(tmp_path)
    cerrojo = entorno["PRUEBA_CERROJO_RECOGIDA"]
    resultado = subprocess.run(
        ["flock", cerrojo, "bash", "-c", f"bash {Path(entorno['EODI_CLON'])}/servidor/trafico.sh"],
        env=entorno,
        capture_output=True,
        text=True,
        check=False,
    )
    assert resultado.returncode == 0, resultado.stderr
    assert visto.read_text(encoding="utf-8").splitlines()[2] == "ocupado"


@LINUX
def test_no_se_lanza_si_el_procesado_anterior_sigue_en_marcha(tmp_path: Path) -> None:
    entorno, visto = preparar(tmp_path)
    propio = Path(entorno["EODI_SECRETOS"]) / "trafico.lock"
    resultado = subprocess.run(
        ["flock", str(propio), "bash", f"{entorno['EODI_CLON']}/servidor/trafico.sh"],
        env=entorno,
        capture_output=True,
        text=True,
        check=False,
    )
    assert resultado.returncode == 0
    assert "sigue en marcha" in resultado.stdout
    assert not visto.exists()
