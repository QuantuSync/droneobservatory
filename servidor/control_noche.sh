#!/usr/bin/env bash
# Revisión de madrugada del control de calidad de las fichas (recogida/control_fichas.py,
# docs/control_fichas.md): vuelve a comprobar todo lo publicado en las últimas 48 horas (llegan
# fuentes nuevas) y traduce con lo que sobra del día las citas atrasadas de la capa de Ucrania.
# La lanza eodi-control.timer cada día; también puede lanzarse a mano:
#
#   sudo systemctl start eodi-control.service
#
# Escribe en la base: toma el cerrojo de la recogida horaria (espera a la que esté en marcha) y lo
# suelta al terminar. Lo que corrige sale publicado en la recogida siguiente. Deja su pasada en
# control.json para el resumen diario y la vigilancia.
set -euo pipefail

principal() {
  local aqui codigo=0
  aqui="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  # shellcheck source=servidor/configuracion.sh
  . "$aqui/configuracion.sh"

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

  cd "$CLON"
  "$ENTORNO/bin/python" -m recogida.control_fichas noche --estado "$SECRETOS/control.json" \
    --correo "$CORREO" || codigo=$?
  echo "revisión de madrugada del control terminada con código $codigo"
  return "$codigo"
}

principal "$@"
