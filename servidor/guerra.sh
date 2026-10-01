#!/usr/bin/env bash
# Lector de los canales de la capa de guerra con lugar (recogida/canales_guerra.py). Lo lanza
# eodi-guerra.timer en el minuto 50 de cada hora; también puede lanzarse a mano:
#
#   sudo systemctl start eodi-guerra.service
#
# 1. toma su propio cerrojo (no el de la recogida: no toca la base ni el clon); si hay otro
#    lector en marcha, no se lanza;
# 2. lee lo nuevo de todos los canales, con la comprobación de canal oficial de cada uno, y
#    lo deja en el disco del servidor ($GUERRA_DATOS);
# 3. con el tiempo que queda hasta el tope, sigue el histórico desde $GUERRA_DESDE donde lo
#    dejó (si ya está completo, no hace nada).
#
# Usa el código del clon tal como lo dejó la última recogida. Un fallo aquí no afecta a la
# recogida horaria, que solo lee lo que este lector dejó escrito. Al diario solo van nombres
# de canal y recuentos.
set -euo pipefail

principal() {
  local aqui codigo=0
  aqui="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  # shellcheck source=servidor/configuracion.sh
  . "$aqui/configuracion.sh"

  exec 8> "$CERROJO_GUERRA"
  if ! flock --nonblock 8; then
    echo "otro lector de canales en marcha: este no se lanza"
    return 0
  fi

  export EODI_GUERRA_DATOS="$GUERRA_DATOS"
  cd "$CLON"
  "$ENTORNO/bin/python" -m recogida.canales_guerra recoger || codigo=$?
  echo "lectura de canales terminada con código $codigo"
  "$ENTORNO/bin/python" -m recogida.canales_guerra historico --desde "$GUERRA_DESDE" \
    --minutos "$GUERRA_HISTORICO_MINUTOS" || codigo=$?
  echo "histórico de canales terminado con código $codigo"
  return "$codigo"
}

principal "$@"
