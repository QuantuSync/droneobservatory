#!/usr/bin/env bash
# Exportación semanal para AEGIS en el servidor (recogida/exportacion.py). La lanza
# eodi-exportacion.timer los lunes a las 03:47 UTC; también puede lanzarse a mano:
#
#   sudo systemctl start eodi-exportacion.service
#
# 1. espera a que termine la recogida horaria en marcha, si la hay, y toma su cerrojo: las
#    dos leen la rama estado y la recogida la reescribe;
# 2. ejecuta la exportación con el código del clon tal como lo dejó la última recogida (no
#    lo actualiza: eso es cosa de la recogida), que descarga la base, genera la versión del
#    día, la valida, la cifra y la sube a main del repositorio de datos con su etiqueta;
# 3. si termina bien, deja la versión y la hora en el registro de la exportación, de donde
#    estado.json saca la última exportación correcta.
#
# No escribe en la base ni en el clon, y tiene su propia unidad: si falla, la recogida
# horaria sigue igual. Al diario solo van recuentos y huellas.
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
    echo "el cerrojo sigue ocupado tras ${ESPERA_CERROJO_S} s: la exportación no se lanza"
    return 1
  fi
  echo "cerrojo tomado"

  EODI_CLAVE_AGE="$(cat "$CLAVE_AGE")"
  export EODI_CLAVE_AGE

  cd "$CLON"
  GIT_SSH_COMMAND="$ssh_base -i $DESPLIEGUE_DATOS" \
    "$python" -m recogida.exportacion --correo "$CORREO" --repositorio "$URL_DATOS" \
    --registro "$EXPORTACION_REGISTRO" || codigo=$?
  echo "exportación terminada con código $codigo"
  return "$codigo"
}

principal "$@"
