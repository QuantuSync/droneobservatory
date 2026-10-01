#!/usr/bin/env bash
# Histórico de las fuentes oficiales de detalle, una sola vez y en segundo plano
# (docs/servidor.md):
#
#   sudo systemd-run --unit=eodi-detalle-historico --uid=eodi --gid=eodi \
#     /usr/bin/env bash /home/eodi/droneobservatory/servidor/detalle_historico.sh
#
# 1. recoge todo lo que cada fuente permite (recogida/detalle.py recoger --historico), con el
#    cerrojo de las fuentes de detalle: el temporizador de cada 3 horas no se solapa con él;
# 2. envía como un lote al extractor los documentos pendientes de antes de los últimos 30
#    días, dentro del presupuesto propio del histórico (3 dólares, modo de gasto «detalle»),
#    espera a que termine y deja los resultados en la carpeta de datos.
#
# No escribe en la base: la recogida horaria siguiente incorpora los resultados (y anota su
# gasto) con su cerrojo. Al diario solo van recuentos.
set -euo pipefail

principal() {
  local aqui
  aqui="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  # shellcheck source=servidor/configuracion.sh
  . "$aqui/configuracion.sh"

  exec 9> "$CERROJO_DETALLE"
  echo "esperando el cerrojo de las fuentes de detalle"
  flock --wait "$ESPERA_CERROJO_S" 9
  local python="$ENTORNO/bin/python"
  cd "$CLON"
  export EODI_DETALLE_DATOS="$DETALLE_DATOS"
  install -d -m 700 "$DETALLE_DATOS"
  "$python" -m recogida.detalle recoger --historico
  # El lote lee la base (rama estado) para saber qué falta y cuánto queda del presupuesto.
  EODI_CLAVE_AGE="$(cat "$CLAVE_AGE")"
  export EODI_CLAVE_AGE
  local linea
  while IFS= read -r linea || [ -n "$linea" ]; do
    case "$linea" in
      "" | "#"*) continue ;;
    esac
    export "${linea?}"
  done < "$EXTRACTOR"
  local ssh_base="ssh -o IdentitiesOnly=yes -o StrictHostKeyChecking=yes -o UserKnownHostsFile=$HOSTS_CONOCIDOS"
  GIT_SSH_COMMAND="$ssh_base -i $DESPLIEGUE_DATOS" \
    "$python" -m recogida.detalle historico --repositorio "$URL_DATOS"
  echo "histórico de detalle enviado y terminado"
}

principal "$@"
