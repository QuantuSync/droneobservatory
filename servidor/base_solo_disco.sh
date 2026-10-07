#!/usr/bin/env bash
# Paso de la base a solo disco (almacen/solo_disco.py): comprueba que la última copia cifrada del
# almacén se restaura bien y que está también en la segunda copia de Helsinki y, si todo va bien,
# deja de subir la copia secundaria a la rama estado de GitHub. Lo lanza una sola vez
# eodi-base-solo-disco.timer (martes 13 de octubre de 2026, 10:00 UTC); también a mano:
#
#   sudo -u eodi bash /home/eodi/droneobservatory/servidor/base_solo_disco.sh --ensayo   # sin cambiar
#   sudo systemctl start eodi-base-solo-disco.service                                    # de verdad
#   journalctl -u eodi-base-solo-disco.service -n 20
#
# No toma el cerrojo de la recogida: espera fuera de los minutos 12 a 40 y a que no haya una
# recogida en marcha (el interruptor vale desde la recogida siguiente).
set -euo pipefail

principal() {
  local aqui
  aqui="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  # shellcheck source=servidor/configuracion.sh
  . "$aqui/configuracion.sh"

  local minuto
  while :; do
    minuto=$((10#$(date -u +%M)))
    if [ "$minuto" -ge 12 ] && [ "$minuto" -le 40 ]; then
      sleep 60
      continue
    fi
    if systemctl is-active --quiet "$UNIDAD.service"; then
      sleep 60
      continue
    fi
    break
  done
  # shellcheck disable=SC1090
  . "$ALMACEN_CREDENCIALES"
  export ALMACEN_ID ALMACEN_SECRETO EODI_SECRETOS="$SECRETOS"
  export EODI_BASE_DIRECTORIO="$BASE_DIRECTORIO"
  cd "$CLON"
  "$ENTORNO/bin/python" -m almacen.solo_disco "$@"
}

principal "$@"
