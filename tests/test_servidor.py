"""Script de la recogida horaria del servidor, sin red ni recogida de verdad.

El repositorio de origen es uno local recién creado y el Python del entorno virtual es
un doble que cambia (o no) un fichero publicado y sale con el código que se le pide.
"""

import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

# El script es de bash y usa flock: se prueba donde se ejecuta, que es en Linux.
pytestmark = pytest.mark.skipif(sys.platform == "win32", reason="el script es para Linux")

RAIZ = Path(__file__).resolve().parent.parent
RAMA = "main"
AUTOR = "QuantuSync <192205734+QuantuSync@users.noreply.github.com>"
MENSAJE = "Actualiza los datos publicados"
SALIDA_AVISO = 2
SALIDA_FALLO = 1
CLAVE_AGE = "# destinatario: age1falso\nAGE-SECRET-KEY-FALSA"
CABECERAS = '{"x-clave": "{clave}", "x-otra": "a b"}'
IDENTIDAD = {
    "GIT_AUTHOR_NAME": "Pruebas", "GIT_AUTHOR_EMAIL": "pruebas@example.invalid",
    "GIT_COMMITTER_NAME": "Pruebas", "GIT_COMMITTER_EMAIL": "pruebas@example.invalid",
}  # fmt: skip
# Doble de `python -m recogida.horaria`: deja anotado lo que recibe, cambia un fichero
# publicado si se le pide y sale con el código que se le pide.
DOBLE_PYTHON = """#!/usr/bin/env bash
if [ "$2" = pip ]; then
  echo instalado >> "$PRUEBA_INSTALACIONES"
  exit 0
fi
if [ "$2" = recogida.estado ]; then
  while [ $# -gt 0 ]; do
    [ "$1" = --codigo ] && codigo="$2"
    [ "$1" = --salida ] && salida="$2"
    shift
  done
  printf '{"codigo": %s}' "$codigo" > "$salida"
  exit 0
fi
printf '%s\\n' "$*" "$EODI_CLAVE_AGE" "$EODI_EXTRACTOR_CABECERAS" "$GIT_SSH_COMMAND" \\
  > "$PRUEBA_VISTO"
if [ -n "$PRUEBA_CAMBIO" ]; then
  printf '%s' "$PRUEBA_CAMBIO" > publicacion/ucrania.json
fi
exit "$PRUEBA_CODIGO"
"""


# Doble de curl: anota sus argumentos y lo que recibe por la entrada (la configuración con
# las credenciales) y sale con el código que se le pide.
DOBLE_CURL = """#!/usr/bin/env bash
printf '%s\\n' "$*" > "$PRUEBA_CURL_ARGS"
cat > "$PRUEBA_CURL_ENTRADA"
exit "${PRUEBA_CURL_CODIGO:-0}"
"""
R2 = "R2_ID=identificador\nR2_SECRETO=secreto\nR2_CUENTA=cuenta\n"


def git(*argumentos: str, directorio: Path) -> str:
    resultado = subprocess.run(
        ["git", *argumentos],
        cwd=directorio,
        env={**os.environ, **IDENTIDAD},
        capture_output=True,
        text=True,
        check=True,
    )
    return resultado.stdout.strip()


@dataclass
class Servidor:
    """Un clon como el del servidor, su repositorio de origen y su carpeta de secretos."""

    origen: Path
    clon: Path
    secretos: Path
    visto: Path
    instalaciones: Path

    def recoger(
        self, codigo: int = 0, cambio: str = "", codigo_curl: int = 0
    ) -> subprocess.CompletedProcess[str]:
        bin_ = self.secretos.parent / "bin"
        entorno = {
            **os.environ,
            "PATH": f"{bin_}:{os.environ['PATH']}",
            "PRUEBA_CURL_ARGS": str(bin_ / "curl.args"),
            "PRUEBA_CURL_ENTRADA": str(bin_ / "curl.entrada"),
            "PRUEBA_CURL_CODIGO": str(codigo_curl),
            "EODI_CLON": str(self.clon),
            "EODI_SECRETOS": str(self.secretos),
            "PRUEBA_CODIGO": str(codigo),
            "PRUEBA_CAMBIO": cambio,
            "PRUEBA_VISTO": str(self.visto),
            "PRUEBA_INSTALACIONES": str(self.instalaciones),
        }
        return subprocess.run(
            ["bash", str(self.clon / "servidor" / "recogida.sh")],
            env=entorno,
            capture_output=True,
            text=True,
            check=False,
        )

    def commits(self) -> int:
        return int(git("rev-list", "--count", RAMA, directorio=self.origen))

    def ultimo(self) -> str:
        return git("log", "-1", "--format=%an <%ae>|%s", RAMA, directorio=self.origen)

    def publicado(self) -> str:
        return git("show", f"{RAMA}:publicacion/ucrania.json", directorio=self.origen)


@pytest.fixture
def servidor(tmp_path: Path) -> Servidor:
    origen, trabajo, clon = tmp_path / "origen.git", tmp_path / "trabajo", tmp_path / "clon"
    git("init", "--quiet", "--bare", "--initial-branch", RAMA, str(origen), directorio=tmp_path)
    git("init", "--quiet", "--initial-branch", RAMA, str(trabajo), directorio=tmp_path)
    shutil.copytree(RAIZ / "servidor", trabajo / "servidor")
    (trabajo / "publicacion").mkdir()
    (trabajo / "publicacion" / "ucrania.json").write_text("{}", encoding="utf-8")
    (trabajo / "publicacion" / "incidentes.geojson").write_text("{}", encoding="utf-8")
    (trabajo / "publicacion" / "incidentes_sin_ubicacion.json").write_text("{}", encoding="utf-8")
    (trabajo / "requirements.txt").write_text("", encoding="utf-8")
    (trabajo / ".gitignore").write_text(".venv/\n", encoding="utf-8")
    git("add", ".", directorio=trabajo)
    git("commit", "--quiet", "-m", "Inicio", directorio=trabajo)
    git("push", "--quiet", str(origen), RAMA, directorio=trabajo)
    git("clone", "--quiet", str(origen), str(clon), directorio=tmp_path)
    python = clon / ".venv" / "bin" / "python"
    python.parent.mkdir(parents=True)
    python.write_text(DOBLE_PYTHON, encoding="utf-8")
    python.chmod(0o755)
    secretos = tmp_path / "secretos"
    secretos.mkdir()
    bin_ = tmp_path / "bin"
    bin_.mkdir()
    (bin_ / "curl").write_text(DOBLE_CURL, encoding="utf-8")
    (bin_ / "curl").chmod(0o755)
    (secretos / "clave_age.txt").write_text(f"{CLAVE_AGE}\n", encoding="utf-8")
    (secretos / "extractor.env").write_text(
        f"# variables del extractor\n\nEODI_EXTRACTOR_CABECERAS={CABECERAS}", encoding="utf-8"
    )
    return Servidor(origen, clon, secretos, tmp_path / "visto.txt", tmp_path / "instalaciones.txt")


def test_publica_los_ficheros_que_han_cambiado(servidor: Servidor) -> None:
    antes = servidor.commits()
    resultado = servidor.recoger(cambio='{"ataques": 1}')
    assert resultado.returncode == 0, resultado.stderr
    assert servidor.commits() == antes + 1
    assert servidor.ultimo() == f"{AUTOR}|{MENSAJE}"
    assert servidor.publicado() == '{"ataques": 1}'
    assert "ficheros publicados en main" in resultado.stdout


def test_sin_cambios_no_hay_commit(servidor: Servidor) -> None:
    antes = servidor.commits()
    resultado = servidor.recoger()
    assert resultado.returncode == 0, resultado.stderr
    assert servidor.commits() == antes
    assert "ficheros publicados sin cambios" in resultado.stdout


def test_con_avisos_publica_y_sale_con_el_codigo_de_aviso(servidor: Servidor) -> None:
    antes = servidor.commits()
    resultado = servidor.recoger(codigo=SALIDA_AVISO, cambio='{"ataques": 2}')
    assert resultado.returncode == SALIDA_AVISO
    assert servidor.commits() == antes + 1
    assert servidor.publicado() == '{"ataques": 2}'
    assert "terminó con avisos" in resultado.stdout


def test_si_la_recogida_falla_no_se_publica(servidor: Servidor) -> None:
    antes = servidor.commits()
    resultado = servidor.recoger(codigo=SALIDA_FALLO, cambio='{"ataques": 3}')
    assert resultado.returncode == SALIDA_FALLO
    assert servidor.commits() == antes
    assert "no se publica" in resultado.stdout


def test_la_recogida_recibe_los_secretos_y_la_clave_del_repositorio_de_datos(
    servidor: Servidor,
) -> None:
    assert servidor.recoger().returncode == 0
    orden, *resto = servidor.visto.read_text(encoding="utf-8").splitlines()
    assert orden.startswith("-m recogida.horaria --correo 192205734+QuantuSync@")
    assert "--repositorio git@github.com:QuantuSync/droneobservatory-datos.git --estado " in orden
    assert resto[:2] == CLAVE_AGE.splitlines()
    assert resto[2] == CABECERAS
    assert f"-i {servidor.secretos}/despliegue_datos" in resto[3]


def test_parte_de_la_ultima_version_de_main_y_descarta_lo_que_no_se_envio(
    servidor: Servidor, tmp_path: Path
) -> None:
    # Un commit local que no llegó a enviarse y un cambio nuevo en el origen.
    (servidor.clon / "publicacion" / "ucrania.json").write_text("local", encoding="utf-8")
    git("commit", "--quiet", "-am", "Sin enviar", directorio=servidor.clon)
    otro = tmp_path / "otro"
    git("clone", "--quiet", str(servidor.origen), str(otro), directorio=tmp_path)
    (otro / "nuevo.txt").write_text("nuevo", encoding="utf-8")
    git("add", "nuevo.txt", directorio=otro)
    git("commit", "--quiet", "-m", "Cambio en el origen", directorio=otro)
    git("push", "--quiet", "origin", RAMA, directorio=otro)
    antes = servidor.commits()
    assert servidor.recoger().returncode == 0
    assert (servidor.clon / "nuevo.txt").exists()
    assert servidor.commits() == antes
    assert servidor.publicado() == "{}"


def test_las_dependencias_solo_se_instalan_cuando_cambian(servidor: Servidor) -> None:
    assert servidor.recoger().returncode == 0
    assert servidor.recoger().returncode == 0
    assert servidor.instalaciones.read_text(encoding="utf-8").splitlines() == ["instalado"]


def test_no_se_lanza_si_hay_otra_en_marcha(servidor: Servidor) -> None:
    cerrojo = servidor.secretos / "recogida.lock"
    # Otro proceso tiene el cerrojo hasta que se le cierra la entrada.
    otra = subprocess.Popen(
        ["bash", "-c", f'exec 9> "{cerrojo}"; flock 9; echo listo; read -r _'],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        text=True,
    )
    assert otra.stdout is not None and otra.stdin is not None
    try:
        assert otra.stdout.readline().strip() == "listo"
        resultado = servidor.recoger(cambio='{"ataques": 4}')
    finally:
        otra.stdin.close()
        otra.wait()
        otra.stdout.close()
    assert resultado.returncode == 0
    assert "hay otra recogida en marcha" in resultado.stdout
    assert not servidor.visto.exists()


def test_sin_credenciales_de_r2_avisa_y_no_cambia_el_resultado(servidor: Servidor) -> None:
    resultado = servidor.recoger()
    assert resultado.returncode == 0
    assert "sin credenciales de R2" in resultado.stdout
    assert not (servidor.secretos.parent / "bin" / "curl.args").exists()


@pytest.mark.parametrize(("codigo", "resultado_estado"), [(0, 0), (SALIDA_AVISO, 2), (1, 1)])
def test_sube_el_estado_al_bucket_tambien_si_la_recogida_falla(
    servidor: Servidor, codigo: int, resultado_estado: int
) -> None:
    (servidor.secretos / "r2.env").write_text(R2, encoding="utf-8")
    resultado = servidor.recoger(codigo=codigo)
    assert resultado.returncode == codigo
    assert "estado.json publicado en el bucket" in resultado.stdout
    bin_ = servidor.secretos.parent / "bin"
    argumentos = (bin_ / "curl.args").read_text(encoding="utf-8")
    assert "https://cuenta.r2.cloudflarestorage.com/eodi-teselas/estado.json" in argumentos
    assert "Cache-Control: public, max-age=60" in argumentos
    assert "--aws-sigv4 aws:amz:auto:s3" in argumentos
    # Las credenciales van por la entrada de curl, nunca en sus argumentos.
    assert "secreto" not in argumentos
    assert (bin_ / "curl.entrada").read_text(encoding="utf-8") == (
        'user = "identificador:secreto"\n'
    )
    anterior = (servidor.secretos / "estado.json").read_text(encoding="utf-8")
    assert anterior == f'{{"codigo": {resultado_estado}}}'


def test_si_la_subida_falla_la_recogida_no_falla(servidor: Servidor) -> None:
    (servidor.secretos / "r2.env").write_text(R2, encoding="utf-8")
    resultado = servidor.recoger(codigo_curl=22)
    assert resultado.returncode == 0
    assert "no se pudo subir estado.json" in resultado.stdout
    assert not (servidor.secretos / "estado.json").exists()
