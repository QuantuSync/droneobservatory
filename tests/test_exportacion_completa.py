"""La exportación semanal completa sobre la base de prueba (tests/base_prueba.py), como la
lanza el servidor pero sin subir nada: un campo sin regla de origen la hace fallar aquí, en la
CI, antes de fusionar (docs/informe_exportacion_aegis.md, apartado 9)."""

import gzip
import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pyrage
import pytest

from almacen.cifrado import VARIABLE_CLAVE, guardar_cifrada
from esquema import DIRECTORIO
from exportacion import procedencia as origenes
from exportacion import semanal
from recogida import estado, exportacion, horaria, salud
from tests import base_prueba


def lineas(fichero: semanal.Fichero) -> list[Any]:
    return [json.loads(linea) for linea in fichero.contenido.decode("utf-8").splitlines()]


@pytest.fixture(scope="module")
def ficheros() -> dict[str, semanal.Fichero]:
    return {f.nombre: f for f in semanal.generar(base_prueba.base_prueba())}


@pytest.fixture(scope="module")
def incidentes(ficheros: dict[str, semanal.Fichero]) -> dict[str, Any]:
    return {i["id"]: i for i in lineas(ficheros["incidentes.jsonl"])}


def test_la_orden_exporta_la_base_de_prueba_en_ensayo(tmp_path: Path) -> None:
    salida = tmp_path / "version"
    clave = os.environ.get(VARIABLE_CLAVE)
    assert base_prueba.ensayo(salida) == 0
    assert os.environ.get(VARIABLE_CLAVE) == clave
    manifiesto = json.loads((salida / "manifiesto.json").read_text(encoding="utf-8"))
    assert manifiesto["version"] == "2026.01.05"
    assert (salida / "incidentes.jsonl.gz.age").exists()


def test_las_reglas_de_la_recogida_han_puesto_sus_valores(incidentes: dict[str, Any]) -> None:
    pista = incidentes["EODI-2025-00003"]
    assert pista["consecuencias"]["cierre"]["valor"] == "si"
    assert pista["tipo"] == "interrupcion_aeroportuaria"
    assert pista["presencia_dron"] == "confirmada"
    assert incidentes["EODI-2025-00004"]["ataque"]["id"] == "EODI-UA-2025-0001"


def test_el_cierre_de_pista_sale_de_la_fuente_que_lo_cuenta(incidentes: dict[str, Any]) -> None:
    procedencia = incidentes["EODI-2025-00003"]["procedencia"]
    assert procedencia["consecuencias.cierre.valor"] == {
        "origen": "prensa", "metodo": "regla", "fuentes": ["F1"],
    }  # fmt: skip
    # La presencia, por la actuación de la autoridad que cuenta esa fuente.
    assert procedencia["presencia_dron"]["metodo"] == "regla"
    assert procedencia["presencia_dron"]["fuentes"] == ["F1"]


def test_cada_campo_nuevo_lleva_su_origen(
    ficheros: dict[str, semanal.Fichero], incidentes: dict[str, Any]
) -> None:
    completo = incidentes["EODI-2025-00001"]["procedencia"]
    assert completo["atribucion"]["fuentes"] == ["F2"]
    assert completo["investigacion"] == {"origen": "oficial", "metodo": "regla", "fuentes": ["F2"]}
    assert incidentes["EODI-2025-00004"]["procedencia"]["ataque"]["origen"] == "deducido"
    ataques = {a["id"]: a for a in lineas(ficheros["ucrania_ataques.jsonl"])}
    principal = ataques["EODI-UA-2025-0001"]["procedencia"]
    assert principal["cruces.incidentes"] == {"origen": "deducido", "metodo": "regla",
                                              "fuentes": []}  # fmt: skip
    assert principal["perdida_luz"]["origen"] == "medido"
    assert ataques["EODI-UA-2025-0002"]["procedencia"]["resumen"]["metodo"] == "regla"
    tramo = ataques["EODI-UA-2025-0003"]["procedencia"]
    assert {tramo[c]["metodo"] for c in ("incluido_en", "solapado_con")} == {"regla"}
    contexto = lineas(ficheros["contexto_pais.jsonl"])
    assert contexto and all(c["procedencia"]["valor"]["origen"] for c in contexto)
    assert any(c["pais"] == "ES" for c in contexto)


def test_ningun_valor_de_la_base_de_prueba_carece_de_origen(
    ficheros: dict[str, semanal.Fichero], incidentes: dict[str, Any]
) -> None:
    for incidente in incidentes.values():
        rutas = set(origenes.valores(incidente))
        assert rutas <= set(incidente["procedencia"]), incidente["id"]
    for ataque in lineas(ficheros["ucrania_ataques.jsonl"]):
        rutas = {r.split(".")[0] for r in origenes.valores(ataque, origenes.META_ATAQUE)}
        assert rutas <= set(ataque["procedencia"]), ataque["id"]
    for impacto in lineas(ficheros["guerra_impactos.jsonl"]):
        rutas = {r for r in impacto if r not in origenes.META_IMPACTO}
        assert rutas <= set(impacto["procedencia"]), impacto["id"]


# --- Cobertura del esquema -------------------------------------------------------------------

COMUN = json.loads((DIRECTORIO / "comun.schema.json").read_text(encoding="utf-8"))
# Lo que no es un valor del suceso (se exporta tal cual, sin procedencia) o no está en la base:
# lo añade la publicación (afirmaciones_publicas del incidente, jornada del ataque) o la propia
# exportación (procedencia, nivel_detalle, indicadores).
SIN_ORIGEN = {
    "incidente": origenes.META_INCIDENTE,
    "ataque_ucrania": origenes.META_ATAQUE | {"jornada"},
    "impacto_guerra": origenes.META_IMPACTO,
}


def _resolver(nodo: Any) -> Any:
    while isinstance(nodo, dict) and "$ref" in nodo and "#/$defs/" in nodo["$ref"]:
        nodo = COMUN["$defs"][nodo["$ref"].split("#/$defs/")[1]]
    return nodo


def rutas_del_esquema(nodo: Any, prefijo: str = "", nivel: int = 3) -> set[str]:
    """Las rutas de las propiedades del esquema, hasta `nivel` de profundidad."""
    nodo = _resolver(nodo)
    if isinstance(nodo, dict) and nodo.get("type") == "array":
        nodo = _resolver(nodo.get("items"))
    propiedades = nodo.get("properties", {}) if isinstance(nodo, dict) else {}
    resultado = set()
    for clave, hijo in propiedades.items():
        ruta = f"{prefijo}.{clave}" if prefijo else clave
        resultado.add(ruta)
        if nivel > 1 and ruta not in origenes.HOJAS:
            resultado |= rutas_del_esquema(hijo, ruta, nivel - 1)
    return resultado


def rutas_presentes(valor: Any, prefijo: str = "", nivel: int = 3) -> set[str]:
    resultado: set[str] = set()
    for elemento in valor if isinstance(valor, list) else [valor]:
        if not isinstance(elemento, dict):
            continue
        for clave, hijo in elemento.items():
            ruta = f"{prefijo}.{clave}" if prefijo else clave
            resultado.add(ruta)
            if nivel > 1:
                resultado |= rutas_presentes(hijo, ruta, nivel - 1)
    return resultado


@pytest.mark.parametrize(
    ("esquema", "fichero"),
    [
        ("incidente", "incidentes.jsonl"),
        ("ataque_ucrania", "ucrania_ataques.jsonl"),
        ("impacto_guerra", "guerra_impactos.jsonl"),
    ],
)
def test_la_base_de_prueba_cubre_todo_el_esquema(
    ficheros: dict[str, semanal.Fichero], esquema: str, fichero: str
) -> None:
    """Un campo nuevo del esquema tiene que tener un ejemplo en tests/base_prueba.py: así la
    exportación de la CI pasa por él y falla si no tiene regla de origen."""
    documento = json.loads((DIRECTORIO / f"{esquema}.schema.json").read_text(encoding="utf-8"))
    rutas = {r for r in rutas_del_esquema(documento) if r.split(".")[0] not in SIN_ORIGEN[esquema]}
    presentes = set().union(*(rutas_presentes(d) for d in lineas(ficheros[fichero])))
    assert sorted(rutas - presentes) == [], "faltan ejemplos en tests/base_prueba.py"


def test_la_exportacion_cifrada_se_descifra_con_la_clave(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    salida = tmp_path / "version"
    identidad = pyrage.x25519.Identity.generate()
    monkeypatch.setenv(VARIABLE_CLAVE, str(identidad))
    base = tmp_path / "db.age"
    guardar_cifrada(base_prueba.base_prueba().conexion, base)
    argumentos = ["--base", str(base), "--sin-subir", "--salida", str(salida)]
    assert exportacion.principal(argumentos, base_prueba.EXPORTACION) == 0
    cifrado = (salida / "incidentes.jsonl.gz.age").read_bytes()
    claro = gzip.decompress(pyrage.decrypt(cifrado, [identidad])).decode("utf-8")
    assert len(claro.splitlines()) == 4


# --- Aviso inmediato de un fallo ------------------------------------------------------------


def test_un_fallo_queda_anotado_sin_perder_la_ultima_correcta(tmp_path: Path) -> None:
    registro = tmp_path / "exportacion.json"
    exportacion.escribir_registro(registro, "2026.10.04", datetime(2026, 10, 4, 3, 42, tzinfo=UTC),
                                  "a" * 64)  # fmt: skip
    argumentos = ["--registro", str(registro), "--anotar-fallo", "1"]
    assert exportacion.principal(argumentos, datetime(2026, 10, 5, 3, 48, tzinfo=UTC)) == 0
    anotado = json.loads(registro.read_text(encoding="utf-8"))
    assert anotado["fin"] == "2026-10-04T03:42Z"
    assert anotado["fallo"] == {"fin": "2026-10-05T03:48Z", "codigo": 1}
    # Una exportación correcta reescribe el registro: el fallo desaparece.
    exportacion.escribir_registro(registro, "2026.10.05", datetime(2026, 10, 5, 9, 0, tzinfo=UTC),
                                  "b" * 64)  # fmt: skip
    assert "fallo" not in json.loads(registro.read_text(encoding="utf-8"))


def test_estado_json_publica_el_fallo_solo_si_es_posterior_a_la_ultima_correcta() -> None:
    fin = datetime(2026, 10, 5, 4, 30, tzinfo=UTC)
    fallo = {"fin": "2026-10-04T03:42Z", "fallo": {"fin": "2026-10-05T03:48Z", "codigo": 1}}
    publicado = estado.componer(fin, fin, 0, None, None, 17, fallo, True)
    assert publicado["exportacion_fallida"] == "2026-10-05T03:48Z"
    assert publicado["ultima_exportacion"] == "2026-10-04T03:42Z"
    superado = {**fallo, "fin": "2026-10-05T09:00Z"}
    assert "exportacion_fallida" not in estado.componer(fin, fin, 0, None, None, 17, superado, True)
    assert "exportacion_fallida" not in estado.componer(fin, fin, 0, None, None, 17, {}, True)


def test_la_vigilancia_avisa_del_fallo_sin_esperar_a_los_8_dias() -> None:
    ahora = datetime(2026, 10, 5, 4, 41, tzinfo=UTC)
    publicado = {"ultima_exportacion": "2026-10-04T03:42Z",
                 "exportacion_fallida": "2026-10-05T03:48Z"}  # fmt: skip
    al_dia, frase = salud.diagnostico_exportacion(publicado, ahora)
    assert not al_dia and "falló el 2026-10-05 03:48 UTC" in frase
    resuelto = {**publicado, "ultima_exportacion": "2026-10-05T09:00Z"}
    assert salud.diagnostico_exportacion(resuelto, ahora)[0]


@pytest.mark.skipif(sys.platform == "win32", reason="script del servidor, solo en Linux")
def test_el_script_del_servidor_anota_el_fallo(tmp_path: Path) -> None:
    """servidor/exportacion.sh con una exportación que falla: sale con su código y deja el fallo
    anotado en el registro."""
    clon = tmp_path / "clon"
    (clon / "recogida").mkdir(parents=True)
    (clon / ".venv" / "bin").mkdir(parents=True)
    raiz = Path(__file__).resolve().parent.parent
    # El paquete recogida de verdad, salvo la exportación, que en este clon falla siempre;
    # --anotar-fallo es el del código de verdad.
    for modulo in (raiz / "recogida").glob("*.py"):
        if modulo.name != "exportacion.py":
            (clon / "recogida" / modulo.name).symlink_to(modulo)
    (clon / "recogida" / "exportacion.py").write_text(
        "import importlib.util\n"
        "import sys\n"
        f"ruta = {str(raiz / 'recogida' / 'exportacion.py')!r}\n"
        "spec = importlib.util.spec_from_file_location('exportacion_real', ruta)\n"
        "real = importlib.util.module_from_spec(spec)\n"
        "spec.loader.exec_module(real)\n"
        "sys.exit(real.principal(sys.argv[1:]) if '--anotar-fallo' in sys.argv else 1)\n",
        encoding="utf-8",
    )
    python = clon / ".venv" / "bin" / "python"
    python.symlink_to(sys.executable)
    secretos = tmp_path / "secretos"
    secretos.mkdir()
    (secretos / "clave_age.txt").write_text("x", encoding="utf-8")
    entorno = {**os.environ, "EODI_CLON": str(clon), "EODI_SECRETOS": str(secretos),
               "PYTHONPATH": str(raiz)}  # fmt: skip
    resultado = subprocess.run(
        ["bash", str(raiz / "servidor" / "exportacion.sh")], env=entorno, capture_output=True,
        text=True, check=False,
    )  # fmt: skip
    assert resultado.returncode == 1, resultado.stdout + resultado.stderr
    assert "fallo anotado" in resultado.stdout, resultado.stdout + resultado.stderr
    anotado = json.loads((secretos / "exportacion.json").read_text(encoding="utf-8"))
    assert anotado["fallo"]["codigo"] == 1


def test_el_ensayo_de_la_recogida_genera_la_exportacion_sin_subir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(VARIABLE_CLAVE, str(pyrage.x25519.Identity.generate()))
    almacen = base_prueba.base_prueba()
    destino = tmp_path / "ensayo" / "exportacion"
    assert horaria.ensayo_exportacion(almacen, base_prueba.EXPORTACION, destino)
    assert (destino / "manifiesto.json").exists()
    # Con un valor sin regla de origen, el ensayo falla.
    monkeypatch.setattr(origenes, "REGLAS", {})
    otro = tmp_path / "otro" / "exportacion"
    assert not horaria.ensayo_exportacion(almacen, base_prueba.EXPORTACION, otro)
