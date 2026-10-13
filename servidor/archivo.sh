#!/usr/bin/env bash
# Copias archivadas de las fuentes (recogida/archivo_web.py): comprueba los enlaces de las fuentes
# de los incidentes publicados, busca su copia en Internet Archive y pide archivar los que no la
# tienen, en una ronda acotada. Lo lanza eodi-archivo.timer en el minuto MINUTO_ARCHIVO de cada
# hora; también a mano:
#
#   sudo systemctl start eodi-archivo.service
#   sudo -u eodi bash /home/eodi/droneobservatory/servidor/archivo.sh resumen
#
# Toma su propio cerrojo y nunca el de la recogida: solo lee los ficheros publicados y escribe en
# su carpeta (ARCHIVO_DATOS). La recogida siguiente lleva lo encontrado a la base y lo publica. Si
# Internet Archive no responde, la ronda acaba antes y lo pendiente queda para la siguiente.
set -euo pipefail

principal() {
  local aqui codigo=0
  aqui="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  # shellcheck source=servidor/configuracion.sh
  . "$aqui/configuracion.sh"

  exec 7> "$CERROJO_ARCHIVO"
  if ! flock --nonblock 7; then
    echo "la ronda anterior del archivo sigue en marcha: esta no se lanza"
    return 0
  fi
  cd "$CLON"
  if [ "$#" -eq 0 ]; then
    set -- ronda --publicacion "$PUBLICACION_DATOS" --datos "$ARCHIVO_DATOS" --minutos "$ARCHIVO_MINUTOS"
  elif [ "$1" = "resumen" ]; then
    set -- resumen --datos "$ARCHIVO_DATOS"
  fi
  "$ENTORNO/bin/python" -m recogida.archivo_web "$@" || codigo=$?
  echo "ronda del archivo terminada con código $codigo"
  return "$codigo"
}

principal "$@"
