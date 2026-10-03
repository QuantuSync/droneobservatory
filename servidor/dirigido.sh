#!/usr/bin/env bash
# Barrido dirigido desde el 1 de enero de 2025 (recogida/barrido_dirigido.py): incidentes en
# España y en puertos y presas de Europa. Se lanza una vez, a mano, como eodi y tras fusionar:
#
#   sudo systemd-run --unit=eodi-dirigido --uid=eodi --gid=eodi \
#     /usr/bin/env bash /home/eodi/droneobservatory/servidor/dirigido.sh [<rama>] [opciones]
#
# La lectura de los días de GDELT (`python -m recogida.barrido_dirigido leer`) va antes y aparte,
# sin cerrojo y con prioridad baja: no toca la base. Este script:
#
# 1. busca en los días leídos los titulares que nombran una instalación española o un puerto o
#    una presa (sin la base);
# 2. espera a que termine la recogida en marcha y toma su cerrojo;
# 3. deja un clon aparte en la rama (main por defecto), con los ficheros publicados de main;
# 4. incorpora lo hallado como artículos y candidatos, llama al extractor en un lote dentro de
#    su límite (modo «dirigida», 3 dólares una vez), rehace los incidentes, publica en el clon y
#    sube la base. La recogida siguiente publica.
#
# El informe queda en /home/eodi/dirigido-informe.json. Las opciones van a la incorporación
# (por ejemplo, --lote <id> para procesar un lote ya enviado).
set -euo pipefail

principal() {
  local aqui rama="${1:-main}" codigo=0
  shift "$(($# < 1 ? $# : 1))"
  aqui="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  # shellcheck source=servidor/configuracion.sh
  . "$aqui/configuracion.sh"

  local clon="$CASA/dirigido"
  local python="$ENTORNO/bin/python"
  local ssh_base="ssh -o IdentitiesOnly=yes -o StrictHostKeyChecking=yes -o UserKnownHostsFile=$HOSTS_CONOCIDOS"

  if [ ! -d "$clon/.git" ]; then
    git clone --quiet "$URL_LECTURA" "$clon"
  fi
  git -C "$clon" fetch --quiet origin "$rama" "$RAMA"
  git -C "$clon" checkout --quiet --force --detach "origin/$rama"
  git -C "$clon" checkout --quiet "origin/$RAMA" -- publicacion/

  export EODI_BUSQUEDA_DATOS="$BUSQUEDA_DATOS"
  (cd "$clon" && "$python" -m recogida.barrido_dirigido buscar) || return $?

  exec 9> "$CERROJO"
  echo "esperando el cerrojo de la recogida"
  flock --wait "$ESPERA_CERROJO_S" 9
  echo "cerrojo tomado"

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
    "$python" -m recogida.barrido_dirigido incorporar --correo "$CORREO" \
    --repositorio "$URL_DATOS" --informe "$DIRIGIDO_INFORME" "$@") || codigo=$?
  echo "barrido dirigido terminado con código $codigo"
  return "$codigo"
}

principal "$@"
