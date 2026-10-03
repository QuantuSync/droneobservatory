#!/usr/bin/env bash
# Detección en directo de cierres de aeropuerto (recogida/directo.py): cada minuto, las
# posiciones en tiempo real de los aeropuertos vigilados, los movimientos frente a su línea base
# y los avisos; publica directo.json en el almacén público y, al aparecer cada día nuevo del
# archivo de adsb.lol, el mapa diario de interferencia GPS. La lanza la unidad eodi-directo, que
# está siempre en marcha (systemd la vuelve a lanzar si se para); también a mano:
#
#   sudo systemctl restart eodi-directo.service
#
# Tiene su propio cerrojo: nunca toma el de la recogida horaria ni la hace esperar. No toca la
# base ni el clon (lo pone al día la recogida horaria; al ver código nuevo, el servicio guarda
# sus trazas y sale, y systemd lo vuelve a lanzar con ese código).
set -euo pipefail

principal() {
  local aqui
  aqui="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  # shellcheck source=servidor/configuracion.sh
  . "$aqui/configuracion.sh"

  exec 6> "$CERROJO_DIRECTO"
  if ! flock --nonblock 6; then
    echo "ya hay una detección en directo en marcha: esta no se lanza"
    sleep 60
    return 0
  fi
  install -d -m 700 "$DIRECTO_DATOS"
  export EODI_TRAFICO_DATOS="$TRAFICO_DATOS" EODI_DIRECTO_DATOS="$DIRECTO_DATOS"
  export EODI_BUSQUEDA_DATOS="$BUSQUEDA_DATOS" EODI_CERROJO_BUSQUEDA="$CERROJO_BUSQUEDA"
  if [ -r "$ALMACEN_CREDENCIALES" ]; then
    # Las credenciales van en el entorno del proceso, no en la línea de órdenes.
    # shellcheck disable=SC1090
    . "$ALMACEN_CREDENCIALES"
    export ALMACEN_ID ALMACEN_SECRETO
  else
    echo "aviso: sin credenciales del almacén público, directo.json no se publica"
  fi
  cd "$CLON"
  exec "$ENTORNO/bin/python" -m recogida.directo servir
}

principal "$@"
