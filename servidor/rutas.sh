#!/usr/bin/env bash
# Rutas de los drones sobre Ucrania (recogida/rutas.py): estructura las noches nuevas del archivo
# del seguimiento en directo, calcula las rutas publicables (solo de noches terminadas) y la
# comprobación con NEPTUN, y sube al almacén público lo que cambia (rutas/indice.json y
# rutas/noches/AAAA-MM-DD.json). Lo lanza eodi-rutas.timer cada hora en el minuto MINUTO_RUTAS;
# también puede lanzarse a mano:
#
#   sudo systemctl start eodi-rutas.service
#
# Toma su propio cerrojo (nunca el de la recogida horaria), no toca la base ni el clon: lee el
# archivo del seguimiento y los ataques de cada noche que deja la recogida horaria
# (datos/rutas/ataques.json).
set -euo pipefail

principal() {
  local aqui codigo=0
  aqui="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  # shellcheck source=servidor/configuracion.sh
  . "$aqui/configuracion.sh"

  exec 7> "$CERROJO_RUTAS"
  if ! flock --nonblock 7; then
    echo "la ejecución anterior sigue en marcha: esta no se lanza"
    return 0
  fi
  if [ -r "$ALMACEN_CREDENCIALES" ]; then
    # shellcheck disable=SC1090
    . "$ALMACEN_CREDENCIALES"
    export ALMACEN_ID ALMACEN_SECRETO
  else
    echo "sin $ALMACEN_CREDENCIALES: se calcula pero no se sube nada al almacén público" >&2
  fi
  export EODI_SEGUIMIENTO_DATOS="$SEGUIMIENTO_DATOS" EODI_RUTAS_DATOS="$RUTAS_DATOS"
  install -d -m 700 "$RUTAS_DATOS"
  cd "$CLON"
  "$ENTORNO/bin/python" -m recogida.rutas estructurar || codigo=$?
  if [ "$codigo" -eq 0 ]; then
    "$ENTORNO/bin/python" -m recogida.rutas calcular || codigo=$?
  fi
  echo "rutas terminadas con código $codigo"
  return "$codigo"
}

principal "$@"
