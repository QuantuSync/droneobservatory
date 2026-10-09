#!/usr/bin/env bash
# Copia pública de reserva del almacén de la web, en Helsinki (almacen/reserva.py): copia a otro
# bucket público lo nuevo o cambiado del almacén de Núremberg, con las mismas cabeceras. La lanza
# eodi-reserva.timer cada 2 minutos y la recogida justo después de publicar; también a mano:
#
#   sudo systemctl start eodi-reserva.service
#   sudo -u eodi bash /home/eodi/droneobservatory/servidor/reserva.sh comprobar
#
# Toma su propio cerrojo y nunca el de la recogida; no toca la base, los datos ni el clon.
set -euo pipefail

principal() {
  local aqui
  aqui="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  # shellcheck source=servidor/configuracion.sh
  . "$aqui/configuracion.sh"

  exec 7> "$CERROJO_RESERVA"
  if ! flock --nonblock 7; then
    echo "la pasada anterior de la reserva sigue en marcha: esta no se lanza"
    return 0
  fi
  # Las credenciales van en el entorno del proceso, no en la línea de órdenes.
  # shellcheck disable=SC1090
  . "$ALMACEN_CREDENCIALES"
  export ALMACEN_ID ALMACEN_SECRETO EODI_SECRETOS="$SECRETOS"
  cd "$CLON"
  "$ENTORNO/bin/python" -m almacen.reserva "$@"
}

principal "$@"
