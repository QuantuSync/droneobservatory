#!/usr/bin/env bash
# Focos de calor en vivo (recogida/focos_vivo.py): los focos de NASA FIRMS de las últimas 24
# horas sobre Ucrania y la Rusia europea, con los mismos filtros que el cruce con los impactos.
# Lo lanza eodi-focos-vivo.timer cada hora en el minuto MINUTO_FOCOS_VIVO, después de la
# recogida horaria (que descarga FIRMS cada 3 horas); también puede lanzarse a mano:
#
#   sudo systemctl start eodi-focos-vivo.service
#
# Toma su propio cerrojo (nunca el de la recogida horaria), lee los CSV de FIRMS del disco y
# publicacion/ucrania.json del clon, y sube focos/ultimas24h.json al almacén público. No pide
# nada a FIRMS ni toca la base ni el clon.
set -euo pipefail

principal() {
  local aqui codigo=0
  aqui="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  # shellcheck source=servidor/configuracion.sh
  . "$aqui/configuracion.sh"

  exec 7> "$CERROJO_FOCOS_VIVO"
  if ! flock --nonblock 7; then
    echo "la ejecución anterior sigue en marcha: esta no se lanza"
    return 0
  fi
  if [ ! -r "$ALMACEN_CREDENCIALES" ]; then
    echo "sin $ALMACEN_CREDENCIALES: no se puede subir nada al almacén público" >&2
    return 1
  fi

  # shellcheck disable=SC1090
  . "$ALMACEN_CREDENCIALES"
  export ALMACEN_ID ALMACEN_SECRETO
  export EODI_FIRMS_DATOS="$FIRMS_DATOS" EODI_FOCOS_VIVO_DATOS="$FOCOS_VIVO_DATOS"
  install -d -m 700 "$FOCOS_VIVO_DATOS"
  cd "$CLON"
  "$ENTORNO/bin/python" -m recogida.focos_vivo generar --registro "$FOCOS_VIVO_REGISTRO" \
    || codigo=$?
  echo "focos en vivo terminados con código $codigo"
  return "$codigo"
}

principal "$@"
