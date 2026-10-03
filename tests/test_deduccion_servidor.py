"""Motor de deducción en el servidor: su propio cerrojo, sin retener nunca el de la recogida
horaria; unidad y temporizador; exportación con el bloque deducido. El script se prueba en Linux
con un doble de Python; lo demás, en cualquier sistema."""

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

from almacen.base import Almacen
from exportacion import semanal
from tests import ejemplos
from tests.test_exportacion_semanal import poblado

RAIZ = Path(__file__).resolve().parent.parent
SCRIPT = RAIZ / "servidor" / "deduccion.sh"
LINUX = pytest.mark.skipif(sys.platform == "win32", reason="el script es para Linux")

DOBLE_PYTHON = """#!/usr/bin/env bash
printf '%s\\n' "$*" "$EODI_DEDUCCION_DATOS" > "$PRUEBA_VISTO"
if flock --nonblock "$PRUEBA_CERROJO_RECOGIDA" true; then
  echo libre >> "$PRUEBA_VISTO"
else
  echo ocupado >> "$PRUEBA_VISTO"
fi
"""


def test_el_script_solo_usa_su_cerrojo() -> None:
    texto = SCRIPT.read_text(encoding="utf-8")
    assert '"$CERROJO_DEDUCCION"' in texto
    assert not re.search(r'"\$CERROJO"', texto)
    configuracion = (RAIZ / "servidor" / "configuracion.sh").read_text(encoding="utf-8")
    assert 'CERROJO_DEDUCCION="$SECRETOS/deduccion.lock"' in configuracion


def test_la_unidad_va_con_prioridad_baja_y_su_propio_temporizador() -> None:
    instalar = (RAIZ / "servidor" / "instalar.sh").read_text(encoding="utf-8")
    unidad = instalar.split('cat > "/etc/systemd/system/$UNIDAD_DEDUCCION.service"')[1]
    unidad = unidad.split("FIN")[1]
    assert "ExecStart=/usr/bin/env bash $CLON/servidor/deduccion.sh" in unidad
    assert "Nice=$DEDUCCION_NICE" in unidad and "IOSchedulingClass=idle" in unidad
    temporizador = instalar.split('cat > "/etc/systemd/system/$UNIDAD_DEDUCCION.timer"')[1]
    assert "OnCalendar=*-*-* *:0$MINUTO_DEDUCCION:00 UTC" in temporizador
    assert '"$UNIDAD_DEDUCCION.timer"' in (RAIZ / "servidor" / "reconstruir.sh").read_text(
        encoding="utf-8"
    )
    # estado.json recibe la última ejecución correcta del motor.
    recogida = (RAIZ / "servidor" / "recogida.sh").read_text(encoding="utf-8")
    assert '--deduccion "$DEDUCCION_REGISTRO"' in recogida


def test_los_scripts_no_llevan_saltos_de_linea_escritos_a_mano() -> None:
    # Un «\\n» literal en una orden partida en varias líneas pasa un argumento «n» de más: así
    # dejó de componerse estado.json la primera recogida tras fusionar el motor.
    for script in sorted((RAIZ / "servidor").glob("*.sh")):
        for numero, linea in enumerate(script.read_text(encoding="utf-8").splitlines(), 1):
            if linea.lstrip().startswith("#"):
                continue
            assert '" \\n' not in linea and not linea.rstrip().endswith("\\n"), (
                f"{script.name}:{numero}"
            )


def test_la_recogida_pasa_el_registro_del_motor_a_estado_json() -> None:
    recogida = (RAIZ / "servidor" / "recogida.sh").read_text(encoding="utf-8")
    orden = recogida.split("-m recogida.estado")[1].split("; then")[0]
    argumentos = orden.replace("\\\n", " ").split()
    posicion = argumentos.index("--deduccion")
    assert argumentos[posicion + 1] == '"$DEDUCCION_REGISTRO"'
    assert "n" not in argumentos


def test_el_paso_horario_no_toma_ningun_cerrojo() -> None:
    for modulo in ("recogida/deduccion.py", "proceso/deduccion/motor.py"):
        texto = (RAIZ / modulo).read_text(encoding="utf-8")
        assert "flock" not in texto and "fcntl" not in texto


def preparar(tmp_path: Path) -> tuple[dict[str, str], Path]:
    clon = tmp_path / "clon"
    (clon / "servidor").mkdir(parents=True)
    for fichero in ("deduccion.sh", "configuracion.sh"):
        (clon / "servidor" / fichero).write_text(
            (RAIZ / "servidor" / fichero).read_text(encoding="utf-8"), encoding="utf-8"
        )
    python = clon / ".venv" / "bin" / "python"
    python.parent.mkdir(parents=True)
    python.write_text(DOBLE_PYTHON, encoding="utf-8")
    python.chmod(0o755)
    secretos = tmp_path / "secretos"
    secretos.mkdir()
    (secretos / "clave_age.txt").write_text("AGE-SECRET-KEY-PRUEBA\n", encoding="utf-8")
    visto = tmp_path / "visto.txt"
    entorno = {
        **os.environ,
        "EODI_CLON": str(clon),
        "EODI_SECRETOS": str(secretos),
        "EODI_DEDUCCION_DATOS": str(tmp_path / "datos"),
        "PRUEBA_VISTO": str(visto),
        "PRUEBA_CERROJO_RECOGIDA": str(secretos / "recogida.lock"),
    }
    return entorno, visto


@LINUX
def test_calcula_sin_retener_el_cerrojo_de_la_recogida(tmp_path: Path) -> None:
    entorno, visto = preparar(tmp_path)
    cerrojo = entorno["PRUEBA_CERROJO_RECOGIDA"]
    resultado = subprocess.run(
        ["flock", cerrojo, "bash", f"{entorno['EODI_CLON']}/servidor/deduccion.sh"],
        env=entorno,
        capture_output=True,
        text=True,
        check=False,
    )
    assert resultado.returncode == 0, resultado.stderr
    orden, datos, estado_cerrojo = visto.read_text(encoding="utf-8").splitlines()
    assert orden.startswith("-m recogida.deduccion calcular --repositorio ")
    assert "--registro" in orden
    assert datos == str(tmp_path / "datos")
    # La recogida horaria lo tenía: el motor siguió sin esperarlo.
    assert estado_cerrojo == "ocupado"


@LINUX
def test_no_se_lanza_si_el_anterior_sigue_en_marcha(tmp_path: Path) -> None:
    entorno, visto = preparar(tmp_path)
    propio = Path(entorno["EODI_SECRETOS"]) / "deduccion.lock"
    resultado = subprocess.run(
        ["flock", str(propio), "bash", f"{entorno['EODI_CLON']}/servidor/deduccion.sh"],
        env=entorno,
        capture_output=True,
        text=True,
        check=False,
    )
    assert resultado.returncode == 0
    assert "sigue en marcha" in resultado.stdout
    assert not visto.exists()


# --- Exportación ------------------------------------------------------------------------


def con_deduccion() -> Almacen:
    almacen = poblado()
    id_ = ejemplos.incidente_completo()["id"]
    almacen.guardar_deduccion(id_, "incidente", ejemplos.deduccion())
    almacen.guardar_deduccion(ejemplos.ataque_completo()["id"], "ataque", ejemplos.deduccion())
    almacen.guardar_cursor(
        "deduccion",
        {
            "ultima_correcta": "2026-10-02T09:05Z",
            "version_motor": "1.0.0",
            "version_catalogo": "1.0.0",
            "validacion": {
                "casos": 28, "evaluados": 26, "aciertos": 26, "fallos_graves": 0,
                "indeterminados": 0, "en_la_base": {"acierto": 3},
            },
            "airprox": {"evaluados": 41},
            "poder_de_descarte": {"incidente": {"casos": 1, "con_descarte": 0,
                                                "compatibles_media": 7.0}},
        },
    )  # fmt: skip
    return almacen


def test_la_exportacion_lleva_lo_deducido_aparte_y_sin_cambiar_el_nivel() -> None:
    sin = {f.nombre: f for f in semanal.generar(poblado())}
    con = {f.nombre: f for f in semanal.generar(con_deduccion())}
    lineas = [json.loads(x) for x in con["incidentes.jsonl"].contenido.decode().splitlines()]
    antes = [json.loads(x) for x in sin["incidentes.jsonl"].contenido.decode().splitlines()]
    completo = next(x for x in lineas if x["id"] == ejemplos.incidente_completo()["id"])
    previo = next(x for x in antes if x["id"] == completo["id"])
    assert completo["deduccion"]["origen"] == "deducido"
    assert completo["procedencia"]["deduccion"] == {
        "origen": "deducido", "metodo": "regla", "fuentes": [],
        "regla": {"nombre": "motor_deduccion", "version": "1.0.0"},
    }  # fmt: skip
    assert completo["nivel_detalle"] == previo["nivel_detalle"]
    # Lo demás no cambia: la deducción no se mezcla con lo medido ni con lo oficial.
    for clave in previo["procedencia"]:
        assert completo["procedencia"][clave] == previo["procedencia"][clave]
    ataques = [json.loads(x) for x in con["ucrania_ataques.jsonl"].contenido.decode().splitlines()]
    assert ataques[0]["procedencia"]["deduccion"]["origen"] == "deducido"


def test_la_exportacion_lleva_el_catalogo_las_clases_las_zonas_y_la_validacion() -> None:
    ficheros = {f.nombre: f for f in semanal.generar(con_deduccion())}
    for nombre in (
        "catalogo_drones.json", "catalogo_fuentes.json", "clases_dron.json",
        "zonas_lanzamiento.json", "deduccion_validacion.json",
        "esquema/catalogo/catalogo_drones.schema.json",
        "esquema/exportacion/clases_dron.schema.json",
    ):  # fmt: skip
        assert nombre in ficheros, nombre
    clases = json.loads(ficheros["clases_dron.json"].contenido)
    assert {c["id"] for c in clases["clases"]} >= {"multirrotor_consumo_sub250", "fpv"}
    validacion = json.loads(ficheros["deduccion_validacion.json"].contenido)
    assert validacion["validacion"]["fallos_graves"] == 0
    assert ficheros["clases_dron.json"].esquema == "esquema/exportacion/clases_dron.schema.json"
    assert ficheros["catalogo_drones.json"].esquema == (
        "esquema/catalogo/catalogo_drones.schema.json"
    )
