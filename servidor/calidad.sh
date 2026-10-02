#!/usr/bin/env bash
# Tercera revisión de la calidad de los datos (recogida/calidad.py), en el servidor y con el
# mismo cerrojo que la recogida horaria: nunca escriben a la vez en la base. Se lanza una vez,
# a mano, como eodi y tras fusionar la rama que trae las reglas:
#
#   sudo systemd-run --unit=eodi-calidad --uid=eodi --gid=eodi \
#     /usr/bin/env bash /home/eodi/droneobservatory/servidor/calidad.sh [<rama>] [opciones]
#
# Las opciones van a la revisión (por ejemplo, --lote <id> para procesar un lote ya enviado).
#
# 1. espera a que termine la recogida en marcha, si la hay, y toma el cerrojo;
# 2. deja un clon aparte en la rama (main por defecto), con los ficheros publicados de main;
# 3. ejecuta la revisión, que descarga la base, separa candidatos, sitúa artículos, incorpora la
#    búsqueda dirigida, llama al extractor en un lote dentro de su límite (modo «calidad»),
#    rehace los incidentes, publica en el clon y sube la base. La recogida siguiente publica.
#
# El informe queda en /home/eodi/calidad-informe.json. Al diario solo van recuentos.
set -euo pipefail

principal() {
  local aqui rama="${1:-main}" codigo=0
  shift "$(($# < 1 ? $# : 1))"
  aqui="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  # shellcheck source=servidor/configuracion.sh
  . "$aqui/configuracion.sh"

  local clon="$CASA/calidad"
  local python="$ENTORNO/bin/python"
  local ssh_base="ssh -o IdentitiesOnly=yes -o StrictHostKeyChecking=yes -o UserKnownHostsFile=$HOSTS_CONOCIDOS"

  exec 9> "$CERROJO"
  echo "esperando el cerrojo de la recogida"
  flock --wait "$ESPERA_CERROJO_S" 9
  echo "cerrojo tomado"

  if [ ! -d "$clon/.git" ]; then
    git clone --quiet "$URL_LECTURA" "$clon"
  fi
  git -C "$clon" fetch --quiet origin "$rama" "$RAMA"
  git -C "$clon" checkout --quiet --force --detach "origin/$rama"
  git -C "$clon" checkout --quiet "origin/$RAMA" -- publicacion/

  EODI_CLAVE_AGE="$(cat "$CLAVE_AGE")"
  export EODI_CLAVE_AGE
  local linea
  while IFS= read -r linea || [ -n "$linea" ]; do
    case "$linea" in
      "" | "#"*) continue ;;
    esac
    export "${linea?}"
  done < "$EXTRACTOR"

  (cd "$clon" && GIT_SSH_COMMAND="$ssh_base -i $DESPLIEGUE_DATOS" \
    "$python" -m recogida.calidad --correo "$CORREO" --repositorio "$URL_DATOS" \
    --informe "$CALIDAD_INFORME" --busqueda "$BUSQUEDA_DATOS" "$@") || codigo=$?
  echo "revisión de la calidad terminada con código $codigo"
  return "$codigo"
}

principal "$@"
