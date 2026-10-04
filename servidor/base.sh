#!/usr/bin/env bash
# Órdenes de la base de datos en el servidor (almacen/sitio.py y almacen/copias.py), como eodi,
# con la clave age y la clave de despliegue del repositorio de datos, igual que la recogida:
#
#   base.sh estado                    modo, fichero de la base y copias de trabajo
#   base.sh comparar                  ¿tienen el mismo contenido la base del disco y la de la rama?
#   base.sh desde-github              deja en disco la base de la rama estado
#   base.sh a-github                  sube a la rama estado la base del disco
#   base.sh huella [fichero]          huella del contenido de un fichero SQLite
#   base.sh copias listar|podar|restaurar --destino F [--objeto K] [--huella]
#
# No toma el cerrojo de la recogida: comparar y restaurar solo leen, y desde-github y a-github
# se usan con el temporizador parado o justo después de una recogida.
set -euo pipefail

aqui="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=servidor/configuracion.sh
. "$aqui/configuracion.sh"
cd "$CLON"
python="$ENTORNO/bin/python"
EODI_CLAVE_AGE="$(cat "$CLAVE_AGE")"
export EODI_CLAVE_AGE
export EODI_BASE_DIRECTORIO="$BASE_DIRECTORIO"
export GIT_SSH_COMMAND="ssh -o IdentitiesOnly=yes -o StrictHostKeyChecking=yes -o UserKnownHostsFile=$HOSTS_CONOCIDOS -i $DESPLIEGUE_DATOS"

orden="${1:-estado}"
[ "$#" -gt 0 ] && shift
case "$orden" in
  copias) exec "$python" -m almacen.copias "$@" ;;
  comparar | desde-github) exec "$python" -m almacen.sitio "$orden" --repositorio "$URL_DATOS" "$@" ;;
  a-github) exec "$python" -m almacen.sitio a-github --repositorio "$URL_DATOS" --correo "$CORREO" "$@" ;;
  *) exec "$python" -m almacen.sitio "$orden" "$@" ;;
esac
