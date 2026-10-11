#!/usr/bin/env bash
# Visitas y resumen diario (recogida/visitas.py, docs/visitas.md): muestra de los suscriptores de
# ntfy, copia horaria de la base de GoatCounter al bucket privado del archivo y, a partir de las
# 08:00 de Madrid, el resumen del día anterior al tema privado lucas-resumen. Lo lanza
# eodi-visitas.timer cada 5 minutos; también a mano:
#
#   sudo systemctl start eodi-visitas.service
#   journalctl -u eodi-visitas.service -n 20
#
# No toma ningún cerrojo ni escribe en la base del observatorio: la lee, como la de GoatCounter,
# solo para leer.
set -euo pipefail

principal() {
  local aqui
  aqui="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  # shellcheck source=servidor/configuracion.sh
  . "$aqui/configuracion.sh"

  # Las credenciales van en el entorno del proceso, no en la línea de órdenes.
  # shellcheck disable=SC1090
  . "$ALMACEN_CREDENCIALES"
  export ALMACEN_ID ALMACEN_SECRETO EODI_SECRETOS="$SECRETOS" EODI_VISITAS_DATOS="$VISITAS_DATOS" \
    EODI_GOATCOUNTER_BASE="$GOATCOUNTER_BASE" EODI_AVISOS_DATOS="$AVISOS_DATOS"
  if [ "$#" -eq 0 ]; then
    set -- pasada
  fi
  cd "$CLON"
  "$ENTORNO/bin/python" -m recogida.visitas "$@"
}

principal "$@"
