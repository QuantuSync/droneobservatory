#!/usr/bin/env bash
# Revisión de todo lo publicado con unas reglas nuevas (recogida/revision.py), en el
# servidor y con el mismo cerrojo que la recogida horaria: nunca escriben a la vez en la
# base. Se lanza a mano, como eodi, con la rama que trae las reglas:
#
#   bash servidor/revision.sh <rama> [<fichero de aviso para soltar el cerrojo>]
#
# 1. espera a que termine la recogida en marcha, si la hay, y toma el cerrojo;
# 2. deja un clon aparte en la rama, con los ficheros publicados de main (lo que hay que
#    comparar);
# 3. ejecuta la revisión, que descarga la base, llama al extractor por lotes dentro de su
#    límite de gasto, rehace los incidentes, publica en el clon y sube la base;
# 4. si se le da un fichero de aviso, no suelta el cerrojo hasta que el fichero existe (o
#    pasa el tope): mientras la rama se fusiona, la recogida horaria no publica con el
#    código anterior sobre la base ya revisada.
#
# Los ficheros publicados quedan en el clon aparte para llevarlos al pull request; la base
# queda subida a la rama estado. Al diario solo van recuentos.
set -euo pipefail

principal() {
  local aqui rama="$1" aviso="${2:-}" codigo=0
  aqui="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  # shellcheck source=servidor/configuracion.sh
  . "$aqui/configuracion.sh"

  local clon="$CASA/revision"
  local informe="$CASA/revision-informe.json"
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
    "$python" -m recogida.revision --correo "$CORREO" --repositorio "$URL_DATOS" \
    --informe "$informe") || codigo=$?
  echo "revisión terminada con código $codigo"

  if [ "$codigo" -eq 0 ] && [ -n "$aviso" ]; then
    local esperado=0
    until [ -e "$aviso" ] || [ "$esperado" -ge "$ESPERA_FUSION_S" ]; do
      sleep "$PAUSA_AVISO_S"
      esperado=$((esperado + PAUSA_AVISO_S))
    done
    echo "cerrojo suelto"
  fi
  return "$codigo"
}

principal "$@"
