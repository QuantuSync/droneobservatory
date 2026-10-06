"""Ningún trabajo del servidor sin tope de memoria (docs/servidor.md): cada unidad de systemd que
crea servidor/instalar.sh lleva MemoryMax con un valor definido en servidor/configuracion.sh.
Desde el 6 de octubre de 2026, cuando el tráfico aéreo, sin tope, subió a 6,4 GB y dejó la
máquina sin memoria cada hora."""

import re
from pathlib import Path

SERVIDOR = Path(__file__).resolve().parent.parent / "servidor"
UNIDAD = re.compile(r'cat > "/etc/systemd/system/(\$\w+)\.service" <<FIN\n(.*?)\nFIN\n', re.S)


def _unidades() -> dict[str, str]:
    return dict(UNIDAD.findall((SERVIDOR / "instalar.sh").read_text(encoding="utf-8")))


def test_todas_las_unidades_tienen_tope_de_memoria() -> None:
    unidades = _unidades()
    assert len(unidades) >= 12
    sin_tope = [u for u, cuerpo in unidades.items() if "MemoryMax=" not in cuerpo]
    assert sin_tope == []


def test_cada_tope_esta_definido_y_cabe_en_el_servidor() -> None:
    configuracion = (SERVIDOR / "configuracion.sh").read_text(encoding="utf-8")
    valores = dict(re.findall(r'^(\w+)="?(\d+[MG])"?', configuracion, re.M))
    for unidad, cuerpo in _unidades().items():
        variable = re.search(r"MemoryMax=\$(\w+)", cuerpo)
        assert variable is not None, unidad
        valor = valores.get(variable.group(1))
        assert valor is not None, (unidad, variable.group(1))
        mb = int(valor[:-1]) * (1024 if valor.endswith("G") else 1)
        # El servidor tiene 7,7 GB: ningún trabajo solo puede quedarse con todo.
        assert mb <= 5 * 1024, (unidad, valor)
