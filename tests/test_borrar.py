"""Ayudante de borrado del servidor (servidor/borrar.py): solo dentro de las carpetas de trabajo
del observatorio, nunca /dev, /etc ni lo que no es de las sesiones; y las unidades del guardián."""

import importlib.util
import os
import sys
from pathlib import Path, PurePosixPath

import pytest

RAIZ = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("borrar", RAIZ / "servidor" / "borrar.py")
assert _spec and _spec.loader
borrar = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(borrar)


@pytest.mark.parametrize(
    "ruta",
    [
        "/dev/null", "/dev", "/etc/passwd", "/usr/bin/python3", "/bin", "/boot/vmlinuz",
        "/proc/1", "/sys/kernel", "/", "/home", "/home/eodi", "/tmp", "/var/tmp",
        "/home/eodi/base", "/home/eodi/base/db.sqlite", "/home/eodi/datos/trafico",
        "/home/eodi/.eodi/almacen.env", "/home/eodi/droneobservatory/recogida",
        "/home/eodi/.cache/ms-playwright", "/home/eodi/.cache", "/var/lib/eodi-guardian",
    ],
)  # fmt: skip
def test_se_niega_fuera_de_las_carpetas_de_trabajo(ruta: str) -> None:
    assert borrar.motivo_para_negarse(Path(PurePosixPath(ruta))) is not None


@pytest.mark.parametrize(
    "ruta",
    [
        "/home/eodi/ensayo", "/home/eodi/control-repaso", "/home/eodi/publicar_rama.sh",
        "/home/eodi/.cache/pip", "/home/operador/prueba", "/tmp/eodi-prueba.json",
        "/var/tmp/sesion",
    ],
)  # fmt: skip
def test_borra_dentro_de_las_carpetas_de_trabajo(ruta: str) -> None:
    assert borrar.motivo_para_negarse(Path(PurePosixPath(ruta))) is None


def test_borra_ficheros_carpetas_y_enlaces_sin_seguirlos(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    trabajo = tmp_path / "trabajo"
    fuera = tmp_path / "fuera"
    (trabajo / "carpeta").mkdir(parents=True)
    fuera.mkdir()
    (fuera / "valioso").write_text("x")
    (trabajo / "carpeta" / "f").write_text("x")
    (trabajo / "suelto").write_text("x")
    monkeypatch.setattr(borrar, "PERMITIDAS", (Path(os.path.realpath(trabajo)),))
    monkeypatch.setattr(borrar, "PROTEGIDAS", ())
    try:
        (trabajo / "enlace").symlink_to(fuera, target_is_directory=True)
        enlace = True
    except OSError:
        enlace = False  # Windows sin permiso para enlaces
    rutas = [str(trabajo / "carpeta"), str(trabajo / "suelto")]
    rutas += [str(trabajo / "enlace")] if enlace else []
    assert borrar.principal(rutas) == 0
    assert list(trabajo.iterdir()) == []
    assert (fuera / "valioso").exists()
    assert borrar.principal([str(fuera / "valioso")]) == 1
    assert (fuera / "valioso").exists()
    assert borrar.principal([str(trabajo / ".." / "fuera" / "valioso")]) == 1
    assert borrar.principal([]) == 2


def test_el_guardian_arranca_sin_dev_null_y_tiene_tope() -> None:
    texto = (RAIZ / "servidor" / "guardian.sh").read_text(encoding="utf-8")
    assert "StandardInput=data" in texto and "MemoryMax=$GUARDIAN_MEMORIA" in texto
    assert "ExecStart=/usr/bin/python3 -I $CLON/recogida/guardian.py" in texto
    assert 'bash "$CLON/servidor/guardian.sh"' in (RAIZ / "servidor" / "instalar.sh").read_text(
        encoding="utf-8"
    )
    configuracion = (RAIZ / "servidor" / "configuracion.sh").read_text(encoding="utf-8")
    assert 'GUARDIAN_MEMORIA="300M"' in configuracion


@pytest.mark.skipif(sys.platform == "win32", reason="bash del servidor")
def test_guardian_sh_escribe_sus_unidades(tmp_path: Path) -> None:
    import os
    import subprocess

    entorno = {**os.environ, "EODI_SYSTEMD_DIR": str(tmp_path)}
    subprocess.run(["bash", str(RAIZ / "servidor" / "guardian.sh")], env=entorno, check=True)
    servicio = (tmp_path / "eodi-guardian.service").read_text(encoding="utf-8")
    assert "MemoryMax=300M" in servicio and "StateDirectory=eodi-guardian" in servicio
    assert "OnCalendar=*-*-* *:00/5:30" in (tmp_path / "eodi-guardian.timer").read_text(
        encoding="utf-8"
    )
