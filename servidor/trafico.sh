#!/usr/bin/env bash
# Procesado del archivo diario de adsb.lol (recogida/trafico.py): el día nuevo en cuanto
# adsb.lol lo publica y, mientras quede tiempo, los días del histórico (los de los incidentes
# y su línea base). Lo lanza el temporizador eodi-trafico cada hora en el minuto
# MINUTO_TRAFICO, como eodi y con prioridad baja de CPU y de disco.
#
# Tiene su propio cerrojo: nunca toma el de la recogida horaria, que sigue lanzándose a su hora
# mientras este procesa (puede tardar más de una hora). Si la ejecución anterior sigue en
# marcha, esta no se lanza. Tampoco toca el clon: lo pone al día la recogida horaria.
#
# Lo que sale de aquí son ficheros en el disco del servidor (TRAFICO_DATOS); la base la
# escribe la recogida horaria, en segundos, con su cerrojo (recogida/mediciones.py).
set -euo pipefail

principal() {
  local aqui
  aqui="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  # shellcheck source=servidor/configuracion.sh
  . "$aqui/configuracion.sh"

  exec 8> "$CERROJO_TRAFICO"
  if ! flock --nonblock 8; then
    echo "el procesado anterior sigue en marcha: este no se lanza"
    return 0
  fi
  install -d -m 700 "$TRAFICO_DATOS"
  export EODI_TRAFICO_DATOS="$TRAFICO_DATOS"
  cd "$CLON"
  "$ENTORNO/bin/python" -m recogida.trafico pendientes --tope-min "$TRAFICO_TOPE_MINUTOS"
}

principal "$@"
