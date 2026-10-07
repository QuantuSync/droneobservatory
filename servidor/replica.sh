#!/usr/bin/env bash
# Segunda copia en otra ubicación de Hetzner (almacen/replica.py): lleva a un bucket privado de
# Helsinki las copias cifradas de la base y el archivo del seguimiento con las rutas, este cifrado
# con la clave pública age. Lo lanza eodi-replica.timer cada hora en el minuto MINUTO_REPLICA,
# cuando ya están la copia de la base de la recogida y la del archivo; también a mano:
#
#   sudo systemctl start eodi-replica.service
#   sudo -u eodi bash /home/eodi/droneobservatory/servidor/replica.sh listar
#   sudo -u eodi bash /home/eodi/droneobservatory/servidor/replica.sh restaurar \
#     --objeto archivo/seguimiento/indices/AAAA-MM-DD.json.age --destino /home/eodi/indice.json
#
# Toma su propio cerrojo y nunca el de la recogida; no toca la base, los datos ni el clon. Para
# cifrar no necesita la identidad age; para restaurar, sí (la lleva este script).
set -euo pipefail

principal() {
  local aqui
  aqui="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  # shellcheck source=servidor/configuracion.sh
  . "$aqui/configuracion.sh"

  exec 7> "$CERROJO_REPLICA"
  if ! flock --nonblock 7; then
    echo "la réplica anterior sigue en marcha: esta no se lanza"
    return 0
  fi
  # Las credenciales van en el entorno del proceso, no en la línea de órdenes.
  # shellcheck disable=SC1090
  . "$ALMACEN_CREDENCIALES"
  export ALMACEN_ID ALMACEN_SECRETO EODI_SECRETOS="$SECRETOS"
  if [ "${1:-replicar}" = "restaurar" ]; then
    EODI_CLAVE_AGE="$(cat "$CLAVE_AGE")"
    export EODI_CLAVE_AGE
  fi
  if [ "$#" -eq 0 ]; then
    set -- replicar
  fi
  cd "$CLON"
  "$ENTORNO/bin/python" -m almacen.replica "$@"
}

principal "$@"
