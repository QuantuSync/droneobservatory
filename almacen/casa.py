"""La carpeta de casa del observatorio y el aislamiento de pruebas y ensayos.

Todo lo que lee secretos, tokens o ficheros de estado parte de `casa()`: la carpeta del usuario
que ejecuta, de la base de usuarios del sistema y no de HOME (con `sudo -u <usuario>` HOME puede
seguir siendo la de quien administra). Por eso HOME no aísla nada.

EODI_CASA_AISLADA, si existe, sustituye a esa carpeta: es la única variable que hace falta para
que una prueba, un ensayo o una simulación no vean el token de ntfy, las claves ni el estado de
verdad. Con EODI_CASA_AISLADA o con EODI_SIN_AVISOS no sale ningún aviso (`envio_desactivado`, que
miran recogida/avisos.enviador y recogida/visitas.avisador_privado), aunque haya un token a mano.
Cómo se usa en el servidor: docs/pruebas_aisladas.md.
"""

import os
import sys
from pathlib import Path

# EODI_CASA ya tiene otro sentido en los scripts del servidor (la casa del observatorio, aunque se
# ejecute como otro usuario): esta es otra variable para no apagar los avisos de verdad.
VARIABLE_CASA = "EODI_CASA_AISLADA"
VARIABLE_SIN_AVISOS = "EODI_SIN_AVISOS"


def casa() -> Path:
    aislada = os.environ.get(VARIABLE_CASA)
    if aislada:
        return Path(aislada)
    if sys.platform != "win32":
        import pwd

        return Path(pwd.getpwuid(os.getuid()).pw_dir)
    return Path.home()


def envio_desactivado() -> bool:
    """Si esta ejecución tiene prohibido mandar avisos: pruebas, ensayos y simulaciones."""
    return bool(os.environ.get(VARIABLE_SIN_AVISOS) or os.environ.get(VARIABLE_CASA))


def exigir_aislamiento() -> None:
    """Para el principio de un script de ensayo o simulación: sin EODI_CASA_AISLADA no arranca."""
    if not os.environ.get(VARIABLE_CASA):
        raise SystemExit(f"falta {VARIABLE_CASA}: este script solo corre aislado")
