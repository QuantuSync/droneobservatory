#!/usr/bin/env bash
# Imagen de satélite de antes y después de cada instalación alcanzada (recogida/satelite.py). Lo
# lanza eodi-satelite.timer dos veces al día (HORAS_SATELITE, minuto MINUTO_SATELITE); también
# puede lanzarse a mano:
#
#   sudo systemctl start eodi-satelite.service
#
# 1. toma su propio cerrojo (nunca el de la recogida horaria); si hay otra ejecución en marcha,
#    esta no se lanza;
# 2. descarga la base de la rama estado solo para leerla (un clon es atómico: como mucho lee
#    la versión anterior) y elige los impactos con foco térmico detectado o en una instalación;
# 3. busca en el catálogo abierto de Sentinel-2 la imagen de antes y la de después sin nubes
#    sobre cada recorte, sube las nuevas al almacén público y después el índice
#    satelite/parejas.json, que lee la web.
#
# Usa el código del clon tal como lo dejó la última recogida. No toca la base ni el clon.
set -euo pipefail

principal() {
  local aqui codigo=0
  aqui="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  # shellcheck source=servidor/configuracion.sh
  . "$aqui/configuracion.sh"

  # Si la recogida horaria sigue en marcha (una larga), esta ejecución no arranca: comprueba su
  # cerrojo sin quedárselo y la hora siguiente lo vuelve a intentar.
  if ! flock --nonblock --shared "$CERROJO" true; then
    echo "la recogida horaria sigue en marcha: esta ejecución no se lanza"
    return 0
  fi
  exec 7> "$CERROJO_SATELITE"
  if ! flock --nonblock 7; then
    echo "la ejecución anterior sigue en marcha: esta no se lanza"
    return 0
  fi
  if [ ! -r "$ALMACEN_CREDENCIALES" ]; then
    echo "sin $ALMACEN_CREDENCIALES: no se puede subir nada al almacén público" >&2
    return 1
  fi

  local ssh_base="ssh -o IdentitiesOnly=yes -o StrictHostKeyChecking=yes -o UserKnownHostsFile=$HOSTS_CONOCIDOS"
  EODI_CLAVE_AGE="$(cat "$CLAVE_AGE")"
  # shellcheck disable=SC1090
  . "$ALMACEN_CREDENCIALES"
  export EODI_CLAVE_AGE ALMACEN_ID ALMACEN_SECRETO
  export EODI_SATELITE_DATOS="$SATELITE_DATOS"
  install -d -m 700 "$SATELITE_DATOS"
  cd "$CLON"
  GIT_SSH_COMMAND="$ssh_base -i $DESPLIEGUE_DATOS" \
    "$ENTORNO/bin/python" -m recogida.satelite actualizar --repositorio "$URL_DATOS" \
    --tope-min "$SATELITE_TOPE_MINUTOS" --registro "$SATELITE_REGISTRO" || codigo=$?
  echo "imágenes de satélite terminadas con código $codigo"
  return "$codigo"
}

principal "$@"
