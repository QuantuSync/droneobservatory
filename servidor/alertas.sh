#!/usr/bin/env bash
# Archivo de las alertas aéreas de Ucrania de alerts.in.ua (recogida/alertas.py): consulta las
# alertas activas cada minuto y el histórico del último mes una vez al día, y guarda en crudo cada
# respuesta que cambia y la tabla de alertas, en ficheros por hora. La lanza la unidad
# eodi-alertas, que está siempre en marcha (systemd la vuelve a lanzar si se para); también a mano:
#
#   sudo systemctl restart eodi-alertas.service
#
# Tiene su propio cerrojo: nunca toma el de la recogida horaria. No toca la base ni el clon. El
# token de la API se lee de su fichero (solo legible por el usuario del servicio) y no pasa por la
# línea de órdenes. Solo sale cuando cambia su propio código en el clon.
set -euo pipefail

principal() {
  local aqui
  aqui="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  # shellcheck source=servidor/configuracion.sh
  . "$aqui/configuracion.sh"

  exec 6> "$CERROJO_ALERTAS"
  if ! flock --nonblock 6; then
    echo "ya hay una captura de alertas en marcha: esta no se lanza"
    sleep 60
    return 0
  fi
  if [ ! -s "$ALERTAS_TOKEN" ]; then
    echo "falta el token de alerts.in.ua en $ALERTAS_TOKEN: no se captura" >&2
    sleep 60
    return 1
  fi
  install -d -m 700 "$SEGUIMIENTO_DATOS"
  export EODI_SEGUIMIENTO_DATOS="$SEGUIMIENTO_DATOS"
  export EODI_ALERTAS_REGISTRO="$ALERTAS_REGISTRO"
  export EODI_ALERTAS_TOKEN_FICHERO="$ALERTAS_TOKEN"
  cd "$CLON"
  exec "$ENTORNO/bin/python" -m recogida.alertas servir
}

principal "$@"
