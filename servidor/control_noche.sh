#!/usr/bin/env bash
# Revisión de madrugada del control de calidad de las fichas (recogida/control_fichas.py,
# docs/control_fichas.md): vuelve a comprobar todo lo publicado en las últimas 48 horas (llegan
# fuentes nuevas) y traduce con lo que sobra del día las citas atrasadas, todo por lote
# (docs/modelos.md).
# La lanza eodi-control.timer cada día; también puede lanzarse a mano:
#
#   sudo systemctl start eodi-control.service
#
# Escribe en la base con el cerrojo de la recogida horaria (lo toma el propio programa: espera a
# la que esté en marcha). Las comprobaciones y las citas van por lote, a mitad de precio: mientras
# el servicio lo procesa, el cerrojo queda libre. Lo que corrige sale publicado en la recogida siguiente. Deja
# su pasada en control.json para el resumen diario y la vigilancia.
set -euo pipefail

principal() {
  local aqui codigo=0
  aqui="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  # shellcheck source=servidor/configuracion.sh
  . "$aqui/configuracion.sh"

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
    --correo "$CORREO" --cerrojo "$CERROJO" || codigo=$?
  echo "revisión de madrugada del control terminada con código $codigo"
  return "$codigo"
}

principal "$@"
