#!/usr/bin/env bash
# Barrido periódico del catálogo de prestaciones (recogida/catalogo_vivo.py). Lo lanza
# eodi-catalogo.timer una vez al día; también a mano:
#
#   sudo systemctl start eodi-catalogo.service
#
# Tiene su propio cerrojo y nunca toma el de la recogida horaria: solo lee la base de la rama
# estado (para los datos propios) y deja lo que encuentra en CATALOGO_DATOS; la recogida horaria
# lo guarda en la base. Tampoco toca el clon (lo pone al día la recogida). Las opciones van al
# barrido (por ejemplo, --primera para la primera pasada con su presupuesto).
set -euo pipefail

principal() {
  local aqui codigo=0
  aqui="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  # shellcheck source=servidor/configuracion.sh
  . "$aqui/configuracion.sh"

  exec 6> "$CERROJO_CATALOGO"
  if ! flock --nonblock 6; then
    echo "el barrido anterior sigue en marcha: este no se lanza"
    return 0
  fi

  local ssh_base="ssh -o IdentitiesOnly=yes -o StrictHostKeyChecking=yes -o UserKnownHostsFile=$HOSTS_CONOCIDOS"
  EODI_CLAVE_AGE="$(cat "$CLAVE_AGE")"
  export EODI_CLAVE_AGE
  local linea
  while IFS= read -r linea || [ -n "$linea" ]; do
    case "$linea" in
      "" | "#"*) continue ;;
    esac
    export "${linea?}"
  done < "$EXTRACTOR"
  export EODI_CATALOGO_DATOS="$CATALOGO_DATOS" EODI_GUERRA_DATOS="$GUERRA_DATOS"
  install -d -m 700 "$CATALOGO_DATOS"
  cd "$CLON"
  GIT_SSH_COMMAND="$ssh_base -i $DESPLIEGUE_DATOS" \
    "$ENTORNO/bin/python" -m recogida.catalogo_vivo barrer --repositorio "$URL_DATOS" "$@" \
    || codigo=$?
  echo "barrido del catálogo vivo terminado con código $codigo"
  return "$codigo"
}

principal "$@"
