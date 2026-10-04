#!/usr/bin/env bash
# Archivo del seguimiento en directo (recogida/seguimiento_archivo.py): comprime las horas ya
# cerradas, escribe el índice de cada día terminado y sube cada día a la copia de seguridad
# privada. Lo lanza eodi-seguimiento-archivo.timer en el minuto MINUTO_SEGUIMIENTO_ARCHIVO de cada
# hora; también a mano, con una orden del módulo como argumento:
#
#   sudo systemctl start eodi-seguimiento-archivo.service
#   sudo -u eodi bash /home/eodi/droneobservatory/servidor/seguimiento_archivo.sh copiar --dia AAAA-MM-DD
#
# Toma su propio cerrojo (uno solo a la vez) y nunca el de la recogida horaria: el módulo espera
# fuera de los minutos 15 a 40 y a que la recogida no esté en marcha. No toca la base ni el clon.
set -euo pipefail

principal() {
  local aqui codigo=0
  aqui="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  # shellcheck source=servidor/configuracion.sh
  . "$aqui/configuracion.sh"

  exec 7> "$CERROJO_SEGUIMIENTO_ARCHIVO"
  if ! flock --nonblock 7; then
    echo "el trabajo anterior del archivo sigue en marcha: este no se lanza"
    return 0
  fi
  if [ -r "$ALMACEN_CREDENCIALES" ]; then
    # Las credenciales van en el entorno del proceso, no en la línea de órdenes.
    # shellcheck disable=SC1090
    . "$ALMACEN_CREDENCIALES"
    export ALMACEN_ID ALMACEN_SECRETO
  else
    echo "aviso: sin $ALMACEN_CREDENCIALES, no se hace la copia de seguridad"
  fi
  export EODI_SEGUIMIENTO_DATOS="$SEGUIMIENTO_DATOS"
  cd "$CLON"
  if [ "$#" -eq 0 ]; then
    set -- ciclo
  fi
  "$ENTORNO/bin/python" -m recogida.seguimiento_archivo "$@" || codigo=$?
  echo "archivo del seguimiento terminado con código $codigo"
  return "$codigo"
}

principal "$@"
