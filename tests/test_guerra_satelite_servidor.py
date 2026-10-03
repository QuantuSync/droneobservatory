"""Guerra por satélite en el servidor: cada pieza (imágenes de Sentinel-2, luz nocturna y focos en
vivo) con su propio temporizador y su propio cerrojo, sin retener nunca el de la recogida
horaria. Los scripts se prueban en Linux con un doble de Python; lo demás, en cualquier
sistema."""

import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
LINUX = pytest.mark.skipif(sys.platform == "win32", reason="el script es para Linux")

PIEZAS = [
    # script, cerrojo, unidad, módulo, tope de la unidad
    (
        "satelite.sh",
        "CERROJO_SATELITE",
        "UNIDAD_SATELITE",
        "recogida.satelite",
        "SATELITE_TOPE_UNIDAD",
    ),
    ("luces.sh", "CERROJO_LUCES", "UNIDAD_LUCES", "recogida.luces", "LUCES_TOPE_UNIDAD"),
    (
        "focos_vivo.sh",
        "CERROJO_FOCOS_VIVO",
        "UNIDAD_FOCOS_VIVO",
        "recogida.focos_vivo",
        "FOCOS_VIVO_TOPE_UNIDAD",
    ),
]


@pytest.mark.parametrize(("script", "cerrojo", "unidad", "modulo", "tope"), PIEZAS)
def test_cada_pieza_con_su_cerrojo_y_su_temporizador(
    script: str, cerrojo: str, unidad: str, modulo: str, tope: str
) -> None:
    texto = (RAIZ / "servidor" / script).read_text(encoding="utf-8")
    assert f'"${cerrojo}"' in texto
    # El cerrojo de la recogida horaria, nunca retenido: como mucho se comprueba si está libre.
    usos = re.findall(r'.*"\$CERROJO".*', texto)
    assert all('flock --nonblock --shared "$CERROJO" true' in u for u in usos), usos
    assert "flock --nonblock" in texto
    assert f"-m {modulo}" in texto
    configuracion = (RAIZ / "servidor" / "configuracion.sh").read_text(encoding="utf-8")
    assert re.search(rf'^{cerrojo}="\$SECRETOS/\w+\.lock"$', configuracion, re.M)
    instalar = (RAIZ / "servidor" / "instalar.sh").read_text(encoding="utf-8")
    assert re.search(rf'unidad_satelite "\${unidad}"', instalar)
    llamada = instalar.split(f'unidad_satelite "${unidad}"')[1].split("\nunidad_satelite")[0]
    assert script in llamada and f'"${tope}"' in llamada
    reconstruir = (RAIZ / "servidor" / "reconstruir.sh").read_text(encoding="utf-8")
    assert reconstruir.count(f'"${unidad}.timer"') == 2


def test_las_unidades_van_con_prioridad_baja() -> None:
    instalar = (RAIZ / "servidor" / "instalar.sh").read_text(encoding="utf-8")
    plantilla = instalar.split("unidad_satelite() {")[1].split("\n}\n")[0]
    assert "Nice=$SATELITE_NICE" in plantilla and "IOSchedulingClass=idle" in plantilla
    assert "User=$USUARIO" in plantilla and "Persistent=true" in plantilla
    assert "MemoryMax=$SATELITE_MEMORIA_MAXIMA" in plantilla


def test_la_luz_nocturna_no_coincide_con_la_recogida() -> None:
    configuracion = (RAIZ / "servidor" / "configuracion.sh").read_text(encoding="utf-8")

    def valor(nombre: str) -> int:
        coincidencia = re.search(rf"^{nombre}=(\d+)$", configuracion, re.M)
        assert coincidencia is not None, nombre
        return int(coincidencia.group(1))

    # Empieza cuando la recogida ha publicado y su última noche empieza antes del minuto 12
    # de la hora siguiente (una noche tarda alrededor de un minuto).
    inicio, tope = valor("MINUTO_LUCES"), valor("LUCES_TOPE_MINUTOS")
    assert inicio > 40 and (inicio + tope) % 60 <= 10
    # Ninguna de las tres arranca entre los minutos 15 y 40 de la recogida horaria.
    for minuto in ("MINUTO_SATELITE", "MINUTO_LUCES", "MINUTO_FOCOS_VIVO"):
        assert not 15 <= valor(minuto) <= 40, minuto


def test_los_cerrojos_son_distintos() -> None:
    configuracion = (RAIZ / "servidor" / "configuracion.sh").read_text(encoding="utf-8")
    cerrojos = re.findall(r'^CERROJO\w*="(\$SECRETOS/\w+\.lock)"$', configuracion, re.M)
    assert len(cerrojos) == len(set(cerrojos))


def test_las_piezas_no_toman_ningun_cerrojo_en_python() -> None:
    for modulo in ("recogida/satelite.py", "recogida/luces.py", "recogida/focos_vivo.py"):
        texto = (RAIZ / modulo).read_text(encoding="utf-8")
        assert "flock" not in texto and "fcntl" not in texto


DOBLE_PYTHON = """#!/usr/bin/env bash
printf '%s\\n' "$*" > "$PRUEBA_VISTO"
if flock --nonblock "$PRUEBA_CERROJO_RECOGIDA" true; then
  echo libre >> "$PRUEBA_VISTO"
else
  echo ocupado >> "$PRUEBA_VISTO"
fi
"""


def _preparar(tmp_path: Path, script: str) -> tuple[dict[str, str], Path]:
    clon = tmp_path / "clon"
    (clon / "servidor").mkdir(parents=True)
    for fichero in (script, "configuracion.sh"):
        (clon / "servidor" / fichero).write_text(
            (RAIZ / "servidor" / fichero).read_text(encoding="utf-8"), encoding="utf-8"
        )
    python = clon / ".venv" / "bin" / "python"
    python.parent.mkdir(parents=True)
    python.write_text(DOBLE_PYTHON, encoding="utf-8")
    python.chmod(0o755)
    secretos = tmp_path / "secretos"
    secretos.mkdir()
    (secretos / "clave_age.txt").write_text("AGE-SECRET-KEY-FALSA\n", encoding="utf-8")
    (secretos / "almacen.env").write_text("ALMACEN_ID=x\nALMACEN_SECRETO=y\n", encoding="utf-8")
    entorno = {
        **os.environ,
        "EODI_CASA": str(tmp_path),
        "EODI_CLON": str(clon),
        "EODI_SECRETOS": str(secretos),
        "PRUEBA_VISTO": str(tmp_path / "visto.txt"),
        "PRUEBA_CERROJO_RECOGIDA": str(secretos / "recogida.lock"),
    }
    return entorno, clon


@LINUX
def test_los_focos_se_lanzan_con_la_recogida_en_marcha_sin_tocar_su_cerrojo(
    tmp_path: Path,
) -> None:
    entorno, clon = _preparar(tmp_path, "focos_vivo.sh")
    cerrojo = entorno["PRUEBA_CERROJO_RECOGIDA"]
    resultado = subprocess.run(
        ["flock", cerrojo, "bash", f"{clon}/servidor/focos_vivo.sh"],
        env=entorno,
        capture_output=True,
        text=True,
        check=False,
    )
    assert resultado.returncode == 0, resultado.stderr
    visto = (tmp_path / "visto.txt").read_text(encoding="utf-8").splitlines()
    # El doble no pudo tomar el cerrojo de la recogida: lo tenía esta, no el script.
    assert visto[-1] == "ocupado"


@LINUX
@pytest.mark.parametrize("script", ["satelite.sh", "luces.sh"])
def test_con_la_recogida_en_marcha_no_arrancan(tmp_path: Path, script: str) -> None:
    entorno, clon = _preparar(tmp_path, script)
    cerrojo = entorno["PRUEBA_CERROJO_RECOGIDA"]
    resultado = subprocess.run(
        ["flock", cerrojo, "bash", f"{clon}/servidor/{script}"],
        env=entorno,
        capture_output=True,
        text=True,
        check=False,
    )
    assert resultado.returncode == 0, resultado.stderr
    assert "sigue en marcha" in resultado.stdout
    assert not (tmp_path / "visto.txt").exists()


@LINUX
@pytest.mark.parametrize("script", ["satelite.sh", "luces.sh"])
def test_sin_recogida_en_marcha_arrancan_y_dejan_libre_su_cerrojo(
    tmp_path: Path, script: str
) -> None:
    entorno, clon = _preparar(tmp_path, script)
    resultado = subprocess.run(
        ["bash", f"{clon}/servidor/{script}"],
        env=entorno,
        capture_output=True,
        text=True,
        check=False,
    )
    assert resultado.returncode == 0, resultado.stderr
    visto = (tmp_path / "visto.txt").read_text(encoding="utf-8").splitlines()
    assert visto[-1] == "libre"
