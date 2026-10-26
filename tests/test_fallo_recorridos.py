"""El workflow «recorridos» distingue un fallo de la preparación de un fallo de la web."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

RUTA = Path(__file__).resolve().parent.parent / ".github" / "scripts" / "fallo_recorridos.py"


def _modulo() -> ModuleType:
    spec = importlib.util.spec_from_file_location("fallo_recorridos", RUTA)
    assert spec is not None and spec.loader is not None
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


fr = _modulo()


def _trabajo(nombre: str, conclusion: str, pasos: list[tuple[str, str]]) -> dict[str, Any]:
    return {
        "name": nombre,
        "conclusion": conclusion,
        "steps": [{"name": n, "conclusion": c} for n, c in pasos],
    }


BIEN = _trabajo(
    "android 1/1", "success", [("Preparación", "success"), ("Recorridos contra x", "success")]
)
WEB = _trabajo(
    "iphone 1/1", "failure", [("Preparación", "success"), ("Recorridos contra x", "failure")]
)
PREPARACION = _trabajo(
    "movil 1/3", "failure", [("Preparación", "failure"), ("Recorridos contra x", "skipped")]
)
SIN_PASOS = _trabajo("tableta 1/1", "failure", [])
TIEMPO = _trabajo(
    "escritorio 1/3",
    "cancelled",
    [("Preparación", "cancelled"), ("Recorridos contra x", "skipped")],
)


def test_sin_fallos() -> None:
    assert fr.fase([BIEN, _trabajo("destino", "success", [])]) == ""


def test_fallo_de_la_web() -> None:
    assert fr.fase([BIEN, WEB]) == "web"


def test_fallo_de_la_preparacion() -> None:
    assert fr.fase([BIEN, PREPARACION]) == "preparacion"
    assert fr.fase([SIN_PASOS]) == "preparacion"
    assert fr.fase([TIEMPO]) == "preparacion"


def test_la_web_manda_si_hay_de_los_dos() -> None:
    assert fr.fase([PREPARACION, WEB]) == "web"


def test_destino_e_incidencia_no_cuentan() -> None:
    assert fr.fase([_trabajo("incidencia", "failure", [("x", "failure")])]) == ""


def test_por_la_entrada() -> None:
    entrada = "\n".join(json.dumps(t) for t in (BIEN, PREPARACION)) + "\n"
    salida = subprocess.run(
        [sys.executable, str(RUTA)], input=entrada, capture_output=True, text=True, check=True
    )
    assert salida.stdout.strip() == "preparacion"
