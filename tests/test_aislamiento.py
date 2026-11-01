"""El aislamiento de pruebas y ensayos (docs/pruebas_aisladas.md): con un token falso en una casa
real simulada, la suite no lo lee y no envía nada."""

import json
import os
import sqlite3
import subprocess
import sys
import textwrap
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from almacen import buckets, casa, cifrado, copias, sitio
from modelo import cliente, secundario
from proceso import nombres_lugar
from recogida import avisos, control_fichas, directo, firms, gasto_api, horaria, silencio, visitas
from tests.conftest import RUTAS_REALES

RAIZ = Path(__file__).resolve().parent.parent

# Lanza dentro de un proceso nuevo: simula al usuario del servicio (la base de usuarios devuelve la
# casa real simulada, con su token) y apunta cada fichero que se abre y cada conexión.
EXTERIOR = textwrap.dedent(
    """
    import json, os, sys
    from pathlib import Path

    casa_real, salida = sys.argv[1], sys.argv[2]
    orden = sys.argv[3:]
    if sys.platform != "win32":
        import pwd
        real = pwd.getpwuid
        class Usuario:
            pw_dir = casa_real
        pwd.getpwuid = lambda uid: Usuario
    os.environ["HOME"] = os.environ["USERPROFILE"] = casa_real
    abiertos, conexiones = [], []

    def auditar(evento, argumentos):
        if evento == "open" and isinstance(argumentos[0], (str, os.PathLike)):
            ruta = os.fspath(argumentos[0])
            if isinstance(ruta, str) and ruta.startswith(casa_real):
                abiertos.append(ruta)
        elif evento in ("socket.connect", "socket.getaddrinfo"):
            conexiones.append(
                f"connect {argumentos[1]!r}" if evento == "socket.connect" else repr(argumentos[0])
            )

    sys.addaudithook(auditar)
    import pytest
    codigo = pytest.main(orden)
    Path(salida).write_text(
        json.dumps({"codigo": int(codigo), "abiertos": abiertos, "conexiones": conexiones}),
        encoding="utf-8",
    )
    """
)


def _casa_real(tmp_path: Path) -> Path:
    real = tmp_path / "casa-real"
    (real / ".eodi").mkdir(parents=True)
    (real / ".eodi" / "ntfy_observatorio").write_text("token-falso", encoding="utf-8")
    (real / ".eodi" / "saldo_api.json").write_text(
        json.dumps({"desde": "2026-11-01T00:00:00Z", "motivo": "falso"}), encoding="utf-8"
    )
    (real / ".eodi" / "extractor.env").write_text("EODI_EXTRACTOR_CLAVE=falsa\n", encoding="utf-8")
    return real


def _exterior(tmp_path: Path, real: Path, orden: list[str]) -> dict[str, Any]:
    salida = tmp_path / "exterior.json"
    guion = tmp_path / "exterior.py"
    guion.write_text(EXTERIOR, encoding="utf-8")
    entorno = {k: v for k, v in os.environ.items() if not k.startswith("EODI_")}
    entorno["PYTHONPATH"] = str(RAIZ)
    resultado = subprocess.run(
        [sys.executable, str(guion), str(real), str(salida), *orden],
        cwd=RAIZ,
        env=entorno,
        check=True,
        capture_output=True,
        timeout=300,
    )
    datos: dict[str, Any] = json.loads(salida.read_text(encoding="utf-8"))
    datos["salida"] = resultado.stdout.decode("utf-8", "replace")[-3000:]
    return datos


def test_la_suite_no_lee_el_token_falso_de_la_casa_real_ni_envia_nada(tmp_path: Path) -> None:
    """Las pruebas que avisan de verdad si algo falla: el gasto, el silencio y el resumen."""
    real = _casa_real(tmp_path)
    datos = _exterior(
        tmp_path,
        real,
        [
            "-q",
            f"--basetemp={tmp_path / 'temporal'}",
            "tests/test_gasto_api.py",
            "tests/test_silencio.py",
            "tests/test_visitas.py",
            "tests/test_aislamiento.py::test_la_casa_de_cada_prueba_esta_vacia",
        ],
    )
    assert datos["codigo"] == 0, datos["salida"]
    assert datos["abiertos"] == []
    # La guardia corta la resolución antes de conectar: nadie llega a conectar, y a ntfy ni se
    # intenta.
    assert [c for c in datos["conexiones"] if "ntfy" in c or c.startswith("connect")] == []
    # Y la casa real simulada queda como estaba.
    assert sorted(p.name for p in (real / ".eodi").iterdir()) == [
        "extractor.env",
        "ntfy_observatorio",
        "saldo_api.json",
    ]


def test_control_negativo_sin_aislar_el_mismo_montaje_si_ve_el_token(tmp_path: Path) -> None:
    """Sin la configuración de las pruebas, el montaje de arriba delata la lectura: no pasa por no
    mirar."""
    real = _casa_real(tmp_path)
    prueba = tmp_path / "suelta" / "test_suelta.py"
    prueba.parent.mkdir()
    prueba.write_text(
        "from recogida import visitas\n"
        "def test_lee() -> None:\n"
        "    visitas.avisador_privado('x')\n",
        encoding="utf-8",
    )
    datos = _exterior(tmp_path, real, ["-q", "--noconftest", "-p", "no:cacheprovider", str(prueba)])
    assert datos["codigo"] == 0
    assert any(r.endswith("ntfy_observatorio") for r in datos["abiertos"])


def test_la_casa_de_cada_prueba_esta_vacia() -> None:
    assert os.environ[casa.VARIABLE_CASA]
    assert casa.envio_desactivado()
    assert sorted(p.name for p in (casa.casa() / ".eodi").iterdir()) == []
    assert "EODI_SECRETOS" not in os.environ


@pytest.mark.parametrize(
    "ruta",
    [
        cliente.RUTA_SALDO,
        cliente.RUTA_LOCAL,
        secundario.RUTA_LOCAL,
        gasto_api.RUTA_ESTADO,
        silencio.RUTA_ESTADO,
        control_fichas.RUTA_ESTADO_DEFECTO,
        directo.REGISTRO,
        firms.RUTA_CLAVE_LOCAL,
        cifrado.RUTA_CLAVE_LOCAL,
        copias.CREDENCIALES,
        sitio.FICHERO_MODO,
        sitio.FICHERO_SECUNDARIA,
        sitio.DIRECTORIO,
    ],
)
def test_lo_calculado_al_importar_cae_fuera_de_la_casa_real(ruta: Path) -> None:
    """Se evalúa al recoger las pruebas: ya con la casa de la sesión."""
    assert not any(ruta.is_relative_to(carpeta) for carpeta in RUTAS_REALES)


def casa_real_del_sistema() -> Path:
    if sys.platform != "win32":
        import pwd

        return Path(pwd.getpwuid(os.getuid()).pw_dir)
    return Path.home()


def test_todo_lo_que_lee_secretos_sale_de_la_misma_carpeta(tmp_path: Path) -> None:
    (tmp_path / ".eodi").mkdir()
    with pytest.MonkeyPatch.context() as parche:
        parche.setenv(casa.VARIABLE_CASA, str(tmp_path))
        assert casa.casa() == tmp_path
        assert visitas.rutas_del_entorno().secretos == tmp_path / ".eodi"
        assert nombres_lugar.ruta_cache() == tmp_path / ".eodi" / "nombres_lugar.json"
        (tmp_path / ".eodi" / "buckets.env").write_text("EODI_X=y\n", encoding="utf-8")
        assert buckets.variables() == {"EODI_X": "y"}


def test_sin_eodi_casa_manda_la_base_de_usuarios(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(casa.VARIABLE_CASA)
    monkeypatch.setenv("HOME", "/ninguna")
    if sys.platform == "win32":
        monkeypatch.setenv("USERPROFILE", "C:\\ninguna")
        assert casa.casa() == Path.home()
    else:
        assert casa.casa() == casa_real_del_sistema()
        assert str(casa.casa()) != "/ninguna"


def test_exigir_aislamiento(monkeypatch: pytest.MonkeyPatch) -> None:
    casa.exigir_aislamiento()
    monkeypatch.delenv(casa.VARIABLE_CASA)
    with pytest.raises(SystemExit):
        casa.exigir_aislamiento()


@pytest.mark.parametrize(
    "variables",
    [{casa.VARIABLE_CASA: "/x"}, {casa.VARIABLE_SIN_AVISOS: "1"}],
)
def test_aislado_el_enviador_no_llega_a_la_red(
    variables: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv(casa.VARIABLE_CASA)
    monkeypatch.delenv(casa.VARIABLE_SIN_AVISOS)
    for nombre, valor in variables.items():
        monkeypatch.setenv(nombre, valor)
    llamadas: list[object] = []
    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **k: llamadas.append(a))
    with pytest.raises(avisos.EnvioDesactivado):
        avisos.enviador("https://ntfy.invalid", "token")({"topic": "x"})
    assert llamadas == []


def test_el_envio_desactivado_no_cuenta_como_enviado(tmp_path: Path) -> None:
    enviados = avisos.Enviados(tmp_path / "avisos.sqlite")
    ahora = datetime(2026, 11, 1, tzinfo=UTC)
    enviados.activar([], ahora)
    incidente = {
        "id": "EODI-2026-00001",
        "lugar": {"pais": "RO", "nivel": "pais"},
        "estado": {"actual": "confirmado"},
        "tiempo": {"inicio": {"valor": "2026-10-31T10:00Z", "precision": "hora"}},
        "fuentes": [],
        "tipo": "incursion",
    }
    pasada = avisos.pasar(
        {"EODI-2026-00001"},
        {"EODI-2026-00001": incidente},
        enviados,
        avisos.configuracion(),
        ahora,
        avisos.enviador("https://ntfy.invalid", "token"),
    )
    assert pasada.enviados == 0
    assert pasada.fallidos > 0
    assert enviados.temas("EODI-2026-00001") == set()
    enviados.cerrar()


def test_el_avisador_privado_no_arranca_aislado(tmp_path: Path) -> None:
    (tmp_path / "ntfy_observatorio").write_text("token-falso", encoding="utf-8")
    assert visitas.avisador_privado("x", tmp_path) is None


def test_la_guardia_corta_la_red_y_la_casa_real() -> None:
    with pytest.raises(urllib.error.URLError):
        urllib.request.urlopen("http://ntfy.invalid/", timeout=1)
    with pytest.raises(PermissionError):
        Path(RUTAS_REALES[0], "ntfy_observatorio").read_text(encoding="utf-8")


def test_un_ensayo_de_la_recogida_no_arranca_sin_casa_aislada(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv(casa.VARIABLE_CASA)
    with pytest.raises(SystemExit):
        horaria.principal(["--correo", "a@b.c", "--ensayo", str(tmp_path)])


def test_el_ensayo_de_los_avisos_no_envia_ni_anota(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """recogida.avisos ensayo, la orden de ensayo.sh: dice lo que enviaría y ya."""
    base = tmp_path / "base.sqlite"
    conexion = sqlite3.connect(base)
    incidente = {
        "id": "EODI-2026-00001",
        "lugar": {"pais": "RO", "nivel": "pais"},
        "estado": {"actual": "confirmado"},
        "tiempo": {"inicio": {"valor": "2026-10-31T10:00Z", "precision": "hora"}},
        "fuentes": [],
        "tipo": "incursion",
    }
    conexion.execute("CREATE TABLE incidentes (id TEXT, documento TEXT)")
    conexion.execute(
        "INSERT INTO incidentes VALUES (?, ?)", ("EODI-2026-00001", json.dumps(incidente))
    )
    conexion.commit()
    conexion.close()
    publicacion = tmp_path / "publicacion"
    publicacion.mkdir()
    (publicacion / "incidentes_sin_ubicacion.json").write_text(
        json.dumps({"incidentes": [{"id": "EODI-2026-00001"}]}), encoding="utf-8"
    )
    datos = tmp_path / "avisos"
    ahora = datetime(2026, 11, 1, tzinfo=UTC)
    enviados = avisos.Enviados(datos / avisos.BASE_AVISOS)
    enviados.activar([], ahora)
    enviados.cerrar()
    llamadas: list[object] = []
    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **k: llamadas.append(a))
    monkeypatch.delenv(casa.VARIABLE_CASA)
    monkeypatch.delenv(casa.VARIABLE_SIN_AVISOS)
    orden = ["ensayo", "--publicacion", str(publicacion), "--base", str(base)]
    assert avisos.principal([*orden, "--datos", str(datos)], ahora) == 0
    assert llamadas == []
    enviados = avisos.Enviados(datos / avisos.BASE_AVISOS)
    assert enviados.incidentes() == set()
    enviados.cerrar()
