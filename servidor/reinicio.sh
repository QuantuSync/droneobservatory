#!/usr/bin/env bash
# Reinicio tras una actualización de seguridad que lo pide, solo cuando no corta nada
# (recogida/reinicio.py): fuera de los minutos 12 a 40, sin trabajos del observatorio en marcha y
# sin un ataque en curso sobre Ucrania según el flujo de NEPTUN. Lo lanza eodi-reinicio.timer cada
# 5 minutos de día (HORAS_REINICIO); si /run/reboot-required no existe, no hace nada. Como root: es
# quien puede reiniciar; la comprobación corre como el usuario del observatorio.
#
#   sudo systemctl start eodi-reinicio.service      # comprobar ahora (reinicia si toca)
#   journalctl -u eodi-reinicio.service -n 20
set -euo pipefail

principal() {
  local aqui
  aqui="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  # shellcheck source=servidor/configuracion.sh
  . "$aqui/configuracion.sh"

  if [ ! -e /run/reboot-required ]; then
    return 0
  fi
  echo "una actualización pide reiniciar: $(tr '\n' ' ' < /run/reboot-required.pkgs 2>/dev/null || true)"
  if runuser -u "$USUARIO" -- env EODI_SEGUIMIENTO_DATOS="$SEGUIMIENTO_DATOS" \
    sh -c "cd '$CLON' && '$ENTORNO/bin/python' -m recogida.reinicio"; then
    echo "reinicio a las $(date -u +%H:%M) UTC"
    systemctl reboot
  fi
  return 0
}

principal "$@"
