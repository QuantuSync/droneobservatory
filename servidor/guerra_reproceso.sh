#!/usr/bin/env bash
# Reproceso de la capa de guerra con lugar en el servidor: vuelve a leer todos los mensajes
# que guardó el lector de canales (tras cambiar el analizador o el nomenclátor, o al terminar
# el histórico) y, con «lote», envía ya al extractor el lote del histórico con los que el código
# no resuelve, dentro de su presupuesto único (5 dólares, modo «guerra_historico»), si no se
# envió antes. No espera al lote: lo incorpora la recogida horaria cuando termina.
#
#   sudo systemd-run --unit=eodi-guerra-reproceso --uid=eodi --gid=eodi \
#     /usr/bin/env bash /home/eodi/droneobservatory/servidor/guerra_reproceso.sh [lote]
#
# Toma el cerrojo de la recogida horaria (espera a la que esté en marcha): descarga la base de
# la rama estado, la cambia y la vuelve a subir, así que no puede coincidir con ella. La
# recogida siguiente publica el resultado. Usa el código del clon tal como lo dejó la última
# recogida.
set -euo pipefail

principal() {
  local aqui codigo=0
  aqui="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  # shellcheck source=servidor/configuracion.sh
  . "$aqui/configuracion.sh"

  local python="$ENTORNO/bin/python"
  local ssh_base="ssh -o IdentitiesOnly=yes -o StrictHostKeyChecking=yes -o UserKnownHostsFile=$HOSTS_CONOCIDOS"

  exec 9> "$CERROJO"
  echo "esperando el cerrojo de la recogida"
  if ! flock --wait "$ESPERA_CERROJO_S" 9; then
    echo "el cerrojo sigue ocupado tras ${ESPERA_CERROJO_S} s: el reproceso no se lanza"
    return 1
  fi

  EODI_CLAVE_AGE="$(cat "$CLAVE_AGE")"
  export EODI_CLAVE_AGE
  local linea
  while IFS= read -r linea || [ -n "$linea" ]; do
    case "$linea" in
      "" | "#"*) continue ;;
    esac
    export "${linea?}"
  done < "$EXTRACTOR"
  export EODI_GUERRA_DATOS="$GUERRA_DATOS"
  export GIT_SSH_COMMAND="$ssh_base -i $DESPLIEGUE_DATOS"

  cd "$CLON"
  "$python" -m recogida.guerra procesar --todo --remoto --correo "$CORREO" \
    --repositorio "$URL_DATOS" || codigo=$?
  echo "reproceso terminado con código $codigo"
  if [ "$codigo" -eq 0 ] && [ "${1:-}" = lote ]; then
    "$python" -m proceso.extraccion_guerra lote --remoto --correo "$CORREO" \
      --repositorio "$URL_DATOS" || codigo=$?
    echo "lote del extractor terminado con código $codigo"
  fi
  return "$codigo"
}

principal "$@"
