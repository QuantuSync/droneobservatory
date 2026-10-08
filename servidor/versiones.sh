#!/usr/bin/env bash
# Versiones citables de los datos abiertos (recogida/versiones.py): el día 1 de cada mes congela en
# el almacén público (versiones/AAAA-MM/) los ficheros que se descargan de la web, con su huella,
# su licencia y su metadatos.json; cada día comprueba que ninguna versión publicada ha cambiado ni
# falta. Lo lanza eodi-versiones.timer a las 02:35 UTC; también a mano:
#
#   sudo systemctl start eodi-versiones.service
#   journalctl -u eodi-versiones.service -n 20
#   sudo -u eodi cat /home/eodi/.eodi/versiones.json
#
# No toma ningún cerrojo, no toca la base, los datos ni el clon, y nunca sobrescribe ni borra una
# versión publicada. Deja lo hecho en versiones.json, que mira la vigilancia.
set -euo pipefail

principal() {
  local aqui
  aqui="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  # shellcheck source=servidor/configuracion.sh
  . "$aqui/configuracion.sh"

  # Las credenciales van en el entorno del proceso, no en la línea de órdenes.
  # shellcheck disable=SC1090
  . "$ALMACEN_CREDENCIALES"
  export ALMACEN_ID ALMACEN_SECRETO EODI_SECRETOS="$SECRETOS"
  cd "$CLON"
  "$ENTORNO/bin/python" -m recogida.versiones "${1:-mensual}" "${@:2}"
}

principal "$@"
