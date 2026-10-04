#!/usr/bin/env bash
# Captura del seguimiento en directo (recogida/seguimiento.py): escucha el flujo de NEPTUN y la
# vista web del canal de la Fuerza Aérea y guarda todo lo que llega, tal cual, en ficheros por
# hora. La lanza la unidad eodi-seguimiento, que está siempre en marcha (systemd la vuelve a lanzar
# si se para); también a mano:
#
#   sudo systemctl restart eodi-seguimiento.service
#
# Tiene su propio cerrojo: nunca toma el de la recogida horaria ni la hace esperar. No toca la
# base ni el clon. Solo sale cuando cambia su propio código en el clon (no con cada publicación
# de datos): systemd la vuelve a lanzar con ese código.
set -euo pipefail

principal() {
  local aqui
  aqui="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  # shellcheck source=servidor/configuracion.sh
  . "$aqui/configuracion.sh"

  exec 6> "$CERROJO_SEGUIMIENTO"
  if ! flock --nonblock 6; then
    echo "ya hay una captura del seguimiento en marcha: esta no se lanza"
    sleep 60
    return 0
  fi
  install -d -m 700 "$SEGUIMIENTO_DATOS"
  export EODI_SEGUIMIENTO_DATOS="$SEGUIMIENTO_DATOS"
  export EODI_SEGUIMIENTO_REGISTRO="$SEGUIMIENTO_REGISTRO"
  cd "$CLON"
  exec "$ENTORNO/bin/python" -m recogida.seguimiento servir
}

principal "$@"
