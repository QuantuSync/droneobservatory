#!/usr/bin/env bash
# Recogida horaria en el servidor. Hace lo mismo que el workflow recogida.yml:
#
# 1. deja el clon en la última versión de main;
# 2. ejecuta recogida.horaria, que descarga la base, recoge lo nuevo y la vuelve a subir;
# 3. publica en main los ficheros de la web si han cambiado, también cuando la recogida
#    termina con avisos (código 2) y nunca cuando falla con otro código.
#
# Sale con el código de la recogida: con avisos la unidad de systemd queda como fallida,
# igual que el workflow queda en rojo. Al diario solo van recuentos.
set -euo pipefail

# Todo dentro de una función: el script se lee entero antes de empezar, y actualizar el
# clon a mitad de ejecución no cambia lo que se está ejecutando.
principal() {
  local aqui codigo=0
  aqui="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  # shellcheck source=servidor/configuracion.sh
  . "$aqui/configuracion.sh"

  # Una sola ejecución a la vez: dos a la par se pisarían la rama estado.
  exec 9> "$CERROJO"
  if ! flock --nonblock 9; then
    echo "hay otra recogida en marcha: esta no se lanza"
    return 0
  fi

  local ssh_base="ssh -o IdentitiesOnly=yes -o StrictHostKeyChecking=yes -o UserKnownHostsFile=$HOSTS_CONOCIDOS"
  local python="$ENTORNO/bin/python"
  local instalados="$ENTORNO/requisitos.sha256"

  cd "$CLON"
  git fetch --quiet origin "$RAMA"
  git reset --quiet --hard "origin/$RAMA"
  # Las dependencias solo se reinstalan cuando cambia requirements.txt.
  if ! sha256sum --check --status "$instalados" 2>/dev/null; then
    "$python" -m pip install --quiet --disable-pip-version-check -r requirements.txt
    sha256sum requirements.txt > "$instalados"
  fi

  # La identidad age completa va en una variable; las del extractor, una por línea.
  EODI_CLAVE_AGE="$(cat "$CLAVE_AGE")"
  export EODI_CLAVE_AGE
  local linea
  while IFS= read -r linea || [ -n "$linea" ]; do
    case "$linea" in
      "" | "#"*) continue ;;
    esac
    export "${linea?}"
  done < "$EXTRACTOR"

  GIT_SSH_COMMAND="$ssh_base -i $DESPLIEGUE_DATOS" \
    "$python" -m recogida.horaria --correo "$CORREO" --repositorio "$URL_DATOS" || codigo=$?
  # Un aviso no frena la publicación. Con cualquier otro código de error no se publica.
  if [ "$codigo" -ne 0 ] && [ "$codigo" -ne "$SALIDA_AVISO" ]; then
    echo "la recogida falló con código $codigo: no se publica"
    return "$codigo"
  fi

  git add "${PUBLICADOS[@]}"
  if git diff --cached --quiet; then
    echo "ficheros publicados sin cambios"
  else
    git -c user.name="$AUTOR" -c user.email="$CORREO" commit --quiet -m "$MENSAJE_PUBLICACION"
    GIT_SSH_COMMAND="$ssh_base -i $DESPLIEGUE_WEB" git push --quiet origin "HEAD:$RAMA"
    echo "ficheros publicados en $RAMA"
  fi
  if [ "$codigo" -eq "$SALIDA_AVISO" ]; then
    echo "la recogida terminó con avisos (código $SALIDA_AVISO): están más arriba en el diario"
  fi
  return "$codigo"
}

principal "$@"
