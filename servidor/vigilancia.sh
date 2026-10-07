#!/usr/bin/env bash
# Salud del servidor para la vigilancia externa (recogida/vigilancia.py): compone salud.json con lo
# que hay en el servidor (última publicación, última recogida y sus avisos, captura del
# seguimiento, copias de la base y del archivo, disco) y lo sube al almacén público, de donde lo
# lee el workflow vigia-recogida cada 10 minutos. Lo lanza eodi-vigilancia.timer cada 5 minutos;
# también a mano:
#
#   sudo systemctl start eodi-vigilancia.service
#   journalctl -u eodi-vigilancia.service -n 20
#
# No toma ningún cerrojo, no toca la base ni el clon y no escribe más que su registro
# (vigilancia.json). Lee el diario de la recogida con el grupo systemd-journal de su unidad.
set -euo pipefail

principal() {
  local aqui
  aqui="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  # shellcheck source=servidor/configuracion.sh
  . "$aqui/configuracion.sh"

  if [ -r "$ALMACEN_CREDENCIALES" ]; then
    # Las credenciales van en el entorno del proceso, no en la línea de órdenes.
    # shellcheck disable=SC1090
    . "$ALMACEN_CREDENCIALES"
    export ALMACEN_ID ALMACEN_SECRETO
  fi
  export EODI_SECRETOS="$SECRETOS" EODI_SEGUIMIENTO_DATOS="$SEGUIMIENTO_DATOS"
  cd "$CLON"
  "$ENTORNO/bin/python" -m recogida.vigilancia
}

principal "$@"
