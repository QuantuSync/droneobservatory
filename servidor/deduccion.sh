#!/usr/bin/env bash
# Motor de deducción en el servidor (recogida/deduccion.py): para cada incidente, impacto con lugar
# y ataque, qué clases de dron son compatibles, cuáles quedan descartadas y por qué, con reglas
# físicas sobre el catálogo de prestaciones. Lo lanza eodi-deduccion.timer cada hora en el minuto
# MINUTO_DEDUCCION; también a mano:
#
#   sudo systemctl start eodi-deduccion.service
#
# Tiene su propio cerrojo y nunca toma el de la recogida horaria: solo lee la base de la rama
# estado (un clon es atómico) y deja los resultados en DEDUCCION_DATOS; la recogida horaria los
# guarda en la base con su cerrojo, en segundos. Tampoco toca el clon (lo pone al día la
# recogida). Con «--todo» recalcula todo aunque no haya cambiado nada.
set -euo pipefail

principal() {
  local aqui codigo=0
  aqui="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  # shellcheck source=servidor/configuracion.sh
  . "$aqui/configuracion.sh"

  exec 7> "$CERROJO_DEDUCCION"
  if ! flock --nonblock 7; then
    echo "el cálculo anterior sigue en marcha: este no se lanza"
    return 0
  fi

  local ssh_base="ssh -o IdentitiesOnly=yes -o StrictHostKeyChecking=yes -o UserKnownHostsFile=$HOSTS_CONOCIDOS"
  EODI_CLAVE_AGE="$(cat "$CLAVE_AGE")"
  export EODI_CLAVE_AGE
  export EODI_DEDUCCION_DATOS="$DEDUCCION_DATOS" EODI_METEO_DATOS="$METEO_DATOS"
  install -d -m 700 "$DEDUCCION_DATOS"
  cd "$CLON"
  GIT_SSH_COMMAND="$ssh_base -i $DESPLIEGUE_DATOS" \
    "$ENTORNO/bin/python" -m recogida.deduccion calcular --repositorio "$URL_DATOS" \
    --registro "$DEDUCCION_REGISTRO" "$@" || codigo=$?
  echo "motor de deducción terminado con código $codigo"
  return "$codigo"
}

principal "$@"
