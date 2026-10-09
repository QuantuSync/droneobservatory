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
if [ "$2" = pip ] || [ "$2" = playwright ]; then
  echo "instalado $2" >> "$PRUEBA_INSTALACIONES"
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
if [ "$2" = recogida.publicacion ]; then
  printf '%s\n' "$*" >> "$PRUEBA_PUBLICACION_ARGS"
  [ "$3" = comparar ] && exit "${PRUEBA_COMPARAR_CODIGO:-0}"
  exit "${PRUEBA_PUBLICACION_CODIGO:-0}"
fi
if [ "$2" = recogida.almacen_publico ]; then
  printf '%s\\n' "$*" > "$PRUEBA_SUBIDA_ARGS"
  printf '%s:%s\\n' "$ALMACEN_ID" "$ALMACEN_SECRETO" > "$PRUEBA_SUBIDA_ENTORNO"
  exit "${PRUEBA_SUBIDA_CODIGO:-0}"
fi
printf '%s\\n' "$*" "$EODI_CLAVE_AGE" "$EODI_EXTRACTOR_CABECERAS" "$GIT_SSH_COMMAND" \\
  "${EODI_DETALLE_DATOS:-}" > "$PRUEBA_VISTO"
if [ -n "$PRUEBA_CAMBIO" ]; then
  printf '%s' "$PRUEBA_CAMBIO" > "$EODI_PUBLICACION_DIRECTORIO/ucrania.json"
fi
exit "$PRUEBA_CODIGO"
"""


ALMACEN = "ALMACEN_ID=identificador\nALMACEN_SECRETO=secreto\n"


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
        self,
        codigo: int = 0,
        cambio: str = "",
        codigo_subida: int = 0,
        codigo_publicacion: int = 0,
        codigo_comparar: int = 0,
    ) -> subprocess.CompletedProcess[str]:
        bin_ = self.secretos.parent / "bin"
        entorno = {
            **os.environ,
            "EODI_PUBLICACION_DATOS": str(self.secretos.parent / "publicados"),
            "PRUEBA_PUBLICACION_ARGS": str(bin_ / "publicacion.args"),
            "PRUEBA_PUBLICACION_CODIGO": str(codigo_publicacion),
            "PRUEBA_COMPARAR_CODIGO": str(codigo_comparar),
            "PATH": f"{bin_}:{os.environ['PATH']}",
            "PRUEBA_SUBIDA_ARGS": str(bin_ / "subida.args"),
            "PRUEBA_SUBIDA_ENTORNO": str(bin_ / "subida.entorno"),
            "PRUEBA_SUBIDA_CODIGO": str(codigo_subida),
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

    def exportar(self, codigo: int = 0, cambio: str = "") -> subprocess.CompletedProcess[str]:
        entorno = {
            **os.environ,
            "EODI_CLON": str(self.clon),
            "EODI_SECRETOS": str(self.secretos),
            "PRUEBA_CODIGO": str(codigo),
            "PRUEBA_CAMBIO": cambio,
            "PRUEBA_VISTO": str(self.visto),
            "PRUEBA_INSTALACIONES": str(self.instalaciones),
        }
        return subprocess.run(
            ["bash", str(self.clon / "servidor" / "exportacion.sh")],
            env=entorno,
            capture_output=True,
            text=True,
            check=False,
        )

    def detalle(self, datos: Path) -> subprocess.CompletedProcess[str]:
        entorno = {
            **os.environ,
            "EODI_CLON": str(self.clon),
            "EODI_SECRETOS": str(self.secretos),
            "EODI_DETALLE_DATOS": str(datos),
            "PRUEBA_CODIGO": "0",
            "PRUEBA_CAMBIO": "",
            "PRUEBA_VISTO": str(self.visto),
            "PRUEBA_INSTALACIONES": str(self.instalaciones),
        }
        return subprocess.run(
            ["bash", str(self.clon / "servidor" / "detalle.sh")],
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
    (trabajo / "publicacion" / "prevision.json").write_text("{}", encoding="utf-8")
    (trabajo / "requirements.txt").write_text("", encoding="utf-8")
    (trabajo / "requirements-navegador.txt").write_text("", encoding="utf-8")
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
    assert servidor.instalaciones.read_text(encoding="utf-8").splitlines() == ["instalado pip"]


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


def test_sin_credenciales_del_almacen_avisa_y_no_cambia_el_resultado(servidor: Servidor) -> None:
    resultado = servidor.recoger()
    assert resultado.returncode == 0
    assert "sin credenciales del almacén público" in resultado.stdout
    assert not (servidor.secretos.parent / "bin" / "subida.args").exists()


@pytest.mark.parametrize(("codigo", "resultado_estado"), [(0, 0), (SALIDA_AVISO, 2), (1, 1)])
def test_sube_el_estado_al_almacen_tambien_si_la_recogida_falla(
    servidor: Servidor, codigo: int, resultado_estado: int
) -> None:
    (servidor.secretos / "almacen.env").write_text(ALMACEN, encoding="utf-8")
    resultado = servidor.recoger(codigo=codigo)
    assert resultado.returncode == codigo
    assert "estado.json publicado en el almacén" in resultado.stdout
    bin_ = servidor.secretos.parent / "bin"
    argumentos = (bin_ / "subida.args").read_text(encoding="utf-8")
    assert "subir --fichero" in argumentos
    assert "--objeto estado.json --tipo application/json" in argumentos
    assert "--cache public, max-age=60" in argumentos
    # Las credenciales van en el entorno de la subida, nunca en sus argumentos.
    assert "secreto" not in argumentos
    assert (bin_ / "subida.entorno").read_text(encoding="utf-8") == "identificador:secreto\n"
    anterior = (servidor.secretos / "estado.json").read_text(encoding="utf-8")
    assert anterior == f'{{"codigo": {resultado_estado}}}'


@pytest.mark.parametrize("codigo", [0, SALIDA_AVISO])
def test_si_la_subida_falla_la_recogida_publica_igual(servidor: Servidor, codigo: int) -> None:
    (servidor.secretos / "almacen.env").write_text(ALMACEN, encoding="utf-8")
    resultado = servidor.recoger(codigo=codigo, cambio='{"nuevo": true}', codigo_subida=1)
    assert resultado.returncode == codigo
    assert "no se pudo subir estado.json" in resultado.stdout
    # La base y los ficheros publicados no dependen del almacén: se publican igual.
    assert "ficheros publicados en main" in resultado.stdout
    assert git("show", "main:publicacion/ucrania.json", directorio=servidor.origen) == (
        '{"nuevo": true}'
    )
    assert not (servidor.secretos / "estado.json").exists()


def test_la_exportacion_recibe_la_clave_el_repositorio_de_datos_y_el_registro(
    servidor: Servidor,
) -> None:
    resultado = servidor.exportar()
    assert resultado.returncode == 0, resultado.stderr
    orden, *resto = servidor.visto.read_text(encoding="utf-8").splitlines()
    assert orden.startswith("-m recogida.exportacion --correo 192205734+QuantuSync@")
    assert "--repositorio git@github.com:QuantuSync/droneobservatory-datos.git" in orden
    assert f"--registro {servidor.secretos}/exportacion.json" in orden
    assert resto[:2] == CLAVE_AGE.splitlines()
    assert f"-i {servidor.secretos}/despliegue_datos" in resto[3]
    assert "exportación terminada con código 0" in resultado.stdout


def test_si_la_exportacion_falla_no_publica_nada_y_sale_con_su_codigo(servidor: Servidor) -> None:
    antes = servidor.commits()
    resultado = servidor.exportar(codigo=SALIDA_FALLO, cambio='{"ataques": 5}')
    assert resultado.returncode == SALIDA_FALLO
    assert servidor.commits() == antes
    # La recogida siguiente no se ve afectada: deja el clon en main y publica como siempre.
    assert servidor.recoger().returncode == 0
    assert servidor.publicado() == "{}"


def test_la_exportacion_espera_a_la_recogida_en_marcha(servidor: Servidor) -> None:
    cerrojo = servidor.secretos / "recogida.lock"
    otra = subprocess.Popen(
        ["bash", "-c", f'exec 9> "{cerrojo}"; flock 9; echo listo; sleep 2'],
        stdout=subprocess.PIPE,
        text=True,
    )
    assert otra.stdout is not None
    try:
        assert otra.stdout.readline().strip() == "listo"
        resultado = servidor.exportar()
    finally:
        otra.wait()
        otra.stdout.close()
    assert resultado.returncode == 0
    assert "esperando el cerrojo" in resultado.stdout
    assert servidor.visto.exists()


def test_detalle_recoge_en_su_carpeta_e_instala_el_navegador_una_vez(
    servidor: Servidor, tmp_path: Path
) -> None:
    datos = tmp_path / "datos" / "detalle"
    for _ in range(2):
        resultado = servidor.detalle(datos)
        assert resultado.returncode == 0, resultado.stderr
    visto = servidor.visto.read_text(encoding="utf-8").splitlines()
    assert visto[0] == "-m recogida.detalle recoger"
    assert visto[-1] == str(datos)
    assert datos.is_dir()
    assert servidor.instalaciones.read_text(encoding="utf-8").splitlines() == [
        "instalado pip",
        "instalado playwright",
    ]


def _con_cerrojo(cerrojo: Path) -> subprocess.Popen[str]:
    otra = subprocess.Popen(
        ["bash", "-c", f'exec 9> "{cerrojo}"; flock 9; echo listo; read -r _'],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True,
    )  # fmt: skip
    assert otra.stdout is not None
    assert otra.stdout.readline().strip() == "listo"
    return otra


def _soltar(otra: subprocess.Popen[str]) -> None:
    assert otra.stdin is not None and otra.stdout is not None
    otra.stdin.close()
    otra.wait()
    otra.stdout.close()


def test_detalle_tiene_su_propio_cerrojo(servidor: Servidor, tmp_path: Path) -> None:
    # El de la recogida horaria no lo frena: no toca la base.
    otra = _con_cerrojo(servidor.secretos / "recogida.lock")
    try:
        assert servidor.detalle(tmp_path / "d1").returncode == 0
        assert servidor.visto.exists()
    finally:
        _soltar(otra)
    # Con el suyo tomado, no se lanza.
    servidor.visto.unlink()
    otra = _con_cerrojo(servidor.secretos / "detalle.lock")
    try:
        resultado = servidor.detalle(tmp_path / "d2")
    finally:
        _soltar(otra)
    assert "hay otra recogida de detalle en marcha" in resultado.stdout


def leer_canales(servidor: Servidor) -> subprocess.CompletedProcess[str]:
    entorno = {
        **os.environ,
        "EODI_CLON": str(servidor.clon),
        "EODI_SECRETOS": str(servidor.secretos),
        "PRUEBA_CODIGO": "0",
        "PRUEBA_CAMBIO": "",
        "PRUEBA_VISTO": str(servidor.visto),
        "PRUEBA_INSTALACIONES": str(servidor.instalaciones),
    }
    return subprocess.run(
        ["bash", str(servidor.clon / "servidor" / "guerra.sh")],
        env=entorno,
        capture_output=True,
        text=True,
        check=False,
    )


def test_el_lector_de_canales_lee_y_sigue_el_historico(servidor: Servidor) -> None:
    resultado = leer_canales(servidor)
    assert resultado.returncode == 0, resultado.stderr
    assert "lectura de canales terminada con código 0" in resultado.stdout
    # El doble deja anotada la última llamada: la del histórico, con su fecha y su tope.
    visto = servidor.visto.read_text(encoding="utf-8").splitlines()[0]
    assert visto == "-m recogida.canales_guerra historico --desde 2025-01-01 --minutos 40"
    assert servidor.commits() == 1


def test_el_lector_de_canales_no_se_lanza_si_hay_otro(servidor: Servidor) -> None:
    cerrojo = servidor.secretos / "guerra.lock"
    with subprocess.Popen(["flock", str(cerrojo), "sleep", "5"]) as otro:
        try:
            subprocess.run(["sleep", "0.5"], check=True)
            resultado = leer_canales(servidor)
        finally:
            otro.terminate()
    assert resultado.returncode == 0
    assert "otro lector de canales en marcha" in resultado.stdout
    assert not servidor.visto.exists()


# --- Interruptor de la publicación (github, doble o almacen) ---------------------------------
def publicaciones(servidor: Servidor) -> list[str]:
    ruta = servidor.secretos.parent / "bin" / "publicacion.args"
    return ruta.read_text(encoding="utf-8").splitlines() if ruta.exists() else []


def test_en_modo_github_no_toca_el_almacen(servidor: Servidor) -> None:
    (servidor.secretos / "almacen.env").write_text(ALMACEN, encoding="utf-8")
    resultado = servidor.recoger(cambio='{"ataques": 7}')
    assert resultado.returncode == 0, resultado.stderr
    assert "publicación en modo github" in resultado.stdout
    assert publicaciones(servidor) == []
    assert servidor.publicado() == '{"ataques": 7}'


def test_en_modo_doble_publica_en_los_dos_y_compara(servidor: Servidor) -> None:
    (servidor.secretos / "almacen.env").write_text(ALMACEN, encoding="utf-8")
    (servidor.secretos / "publicacion_modo").write_text("doble\n", encoding="utf-8")
    antes = servidor.commits()
    resultado = servidor.recoger(cambio='{"ataques": 8}')
    assert resultado.returncode == 0, resultado.stderr
    assert servidor.commits() == antes + 1
    assert servidor.publicado() == '{"ataques": 8}'
    subida, comparacion = publicaciones(servidor)
    assert subida.startswith("-m recogida.publicacion subir --carpeta ")
    # En el modo doble la web se reconstruye con el commit: sin gancho.
    assert "--gancho" not in subida
    assert comparacion == f"-m recogida.publicacion comparar --carpeta {servidor.clon}/publicacion"
    assert "el almacén es idéntico" in resultado.stdout
    distinto = servidor.recoger(cambio='{"ataques": 9}', codigo_comparar=3)
    assert distinto.returncode == 0
    assert "aviso: publicación doble: el almacén no es idéntico" in distinto.stdout


def test_en_modo_almacen_no_hay_commit_y_se_pide_la_reconstruccion(servidor: Servidor) -> None:
    (servidor.secretos / "almacen.env").write_text(ALMACEN, encoding="utf-8")
    (servidor.secretos / "publicacion_modo").write_text("almacen", encoding="utf-8")
    antes = servidor.commits()
    resultado = servidor.recoger(cambio='{"ataques": 10}')
    assert resultado.returncode == 0, resultado.stderr
    assert servidor.commits() == antes
    (subida,) = publicaciones(servidor)
    assert f"--gancho {servidor.secretos}/vercel_gancho" in subida
    # Si la subida falla, la recogida no cuenta como correcta.
    fallida = servidor.recoger(cambio='{"ataques": 11}', codigo_publicacion=1)
    assert fallida.returncode == 1
    assert "los ficheros no se publicaron en el almacén" in fallida.stdout
    # Volver a doble es un solo cambio: la recogida siguiente vuelve a hacer el commit.
    (servidor.secretos / "publicacion_modo").write_text("doble", encoding="utf-8")
    assert servidor.recoger(cambio='{"ataques": 12}').returncode == 0
    assert servidor.commits() == antes + 1
    assert servidor.publicado() == '{"ataques": 12}'
