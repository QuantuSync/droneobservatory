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
#    estado.json saca la última exportación correcta; si falla, anota allí el fallo, que
#    estado.json también publica para que la vigilancia avise en la hora siguiente.
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

  # Dónde se deja: el mismo interruptor que la publicación de los datos (configuracion.sh).
  local destinos
  case "$(modo_publicacion)" in
    almacen) destinos=almacen ;;
    doble) destinos=github,almacen ;;
    *) destinos=github ;;
  esac
  if [ -r "$ALMACEN_CREDENCIALES" ]; then
    # shellcheck disable=SC1090
    . "$ALMACEN_CREDENCIALES"
    export ALMACEN_ID ALMACEN_SECRETO
  fi
  echo "exportación hacia: $destinos"

  cd "$CLON"
  GIT_SSH_COMMAND="$ssh_base -i $DESPLIEGUE_DATOS" \
    "$python" -m recogida.exportacion --correo "$CORREO" --repositorio "$URL_DATOS" \
    --registro "$EXPORTACION_REGISTRO" --destinos "$destinos" || codigo=$?
  echo "exportación terminada con código $codigo"
  return "$codigo"
}

codigo=0
principal "$@" || codigo=$?
# Un fallo (la versión no valida, el cerrojo no se libera, la subida no sale) queda anotado en el
# registro: estado.json lo publica en la recogida siguiente y el workflow vigia-recogida abre su
# incidencia sin esperar a los 8 días.
if [ "$codigo" -ne 0 ] && [ -n "${CLON:-}" ] && [ -n "${EXPORTACION_REGISTRO:-}" ]; then
  anotar=(-m recogida.exportacion --registro "$EXPORTACION_REGISTRO" --anotar-fallo "$codigo")
  if (cd "$CLON" && "$ENTORNO/bin/python" "${anotar[@]}"); then
    echo "fallo anotado en el registro de la exportación"
  else
    echo "aviso: no se pudo anotar el fallo en el registro de la exportación"
  fi
fi
exit "$codigo"
