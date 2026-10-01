#!/usr/bin/env bash
# Recogida de las fuentes oficiales de detalle en el servidor (recogida/detalle.py): UK Airprox
# Board, respuestas parlamentarias, informes de investigación, cierres policiales, sentencias,
# estadísticas oficiales y las listas de noticias oficiales que se cargan con JavaScript. La
# lanza eodi-detalle.timer cada 3 horas; también puede lanzarse a mano:
#
#   sudo systemctl start eodi-detalle.service
#
# Tiene su propio cerrojo: no espera a la recogida horaria ni la hace esperar, porque no toca
# la base ni el clon (usa el código tal como lo dejó la última recogida). Deja lo descargado en
# la carpeta de datos de detalle; la recogida horaria lo incorpora a la base con su cerrojo.
# Las dependencias del navegador sin interfaz se reinstalan solo si cambia su fichero.
set -euo pipefail

principal() {
  local aqui codigo=0
  aqui="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  # shellcheck source=servidor/configuracion.sh
  . "$aqui/configuracion.sh"

  exec 9> "$CERROJO_DETALLE"
  if ! flock --nonblock 9; then
    echo "hay otra recogida de detalle en marcha: esta no se lanza"
    return 0
  fi

  local python="$ENTORNO/bin/python"
  local instalados="$ENTORNO/navegador.sha256"
  cd "$CLON"
  if ! sha256sum --check --status "$instalados" 2>/dev/null; then
    "$python" -m pip install --quiet --disable-pip-version-check -r requirements-navegador.txt
    "$python" -m playwright install chromium
    sha256sum requirements-navegador.txt > "$instalados"
  fi
  export EODI_DETALLE_DATOS="$DETALLE_DATOS"
  install -d -m 700 "$DETALLE_DATOS"
  "$python" -m recogida.detalle recoger "$@" || codigo=$?
  echo "recogida de detalle terminada con código $codigo"
  return "$codigo"
}

principal "$@"
