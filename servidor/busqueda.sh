#!/usr/bin/env bash
# Búsqueda dirigida de noticias para los cierres medidos sin incidente
# (recogida/busqueda_dirigida.py). La lanza eodi-busqueda.timer cada hora; también puede
# lanzarse a mano:
#
#   sudo systemctl start eodi-busqueda.service
#
# Tiene su propio cerrojo: no espera a la recogida horaria ni la hace esperar, porque no toca
# la base ni el clon (usa el código tal como lo dejó la última recogida). Lee la lista de
# anomalías que deja la recogida horaria, descarga los GKG de GDELT de los días que faltan y
# deja lo hallado en la carpeta de datos de la búsqueda; la recogida horaria lo incorpora.
set -euo pipefail

principal() {
  local aqui codigo=0
  aqui="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  # shellcheck source=servidor/configuracion.sh
  . "$aqui/configuracion.sh"

  exec 9> "$CERROJO_BUSQUEDA"
  if ! flock --nonblock 9; then
    echo "hay otra búsqueda dirigida en marcha: esta no se lanza"
    return 0
  fi

  cd "$CLON"
  export EODI_BUSQUEDA_DATOS="$BUSQUEDA_DATOS"
  install -d -m 700 "$BUSQUEDA_DATOS"
  "$ENTORNO/bin/python" -m recogida.busqueda_dirigida buscar --tope-min "$BUSQUEDA_TOPE_MINUTOS" \
    "$@" || codigo=$?
  echo "búsqueda dirigida terminada con código $codigo"
  return "$codigo"
}

principal "$@"
