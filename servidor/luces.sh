#!/usr/bin/env bash
# Luz nocturna tras los ataques contra la red eléctrica (recogida/luces.py, regla en
# proceso/luces.py). Lo lanza eodi-luces.timer cada hora en el minuto MINUTO_LUCES; también
# puede lanzarse a mano:
#
#   sudo systemctl start eodi-luces.service
#
# 1. toma su propio cerrojo (nunca el de la recogida horaria); si hay otra ejecución en marcha,
#    esta no se lanza;
# 2. mide en los gránulos de VIIRS de NOAA-20 del archivo abierto de NOAA el brillo de cada
#    ciudad en las noches que hacen falta (las de los ataques contra la energía y su
#    referencia, las de la validación y la última), hasta su tope de tiempo, y sigue en la
#    ejecución siguiente;
# 3. evalúa cada ataque con objetivos de energía y deja los resultados en LUCES_DATOS; la
#    recogida horaria los guarda en la base con su cerrojo;
# 4. con todas las noches medidas, las ciudades con alumbrado reducido de forma permanente, que
#    sube al almacén público (luces/alumbrado.json).
#
# Lee publicacion/ucrania.json del clon y los mensajes del lector de canales; no toca la base
# ni el clon.
set -euo pipefail

principal() {
  local aqui codigo=0
  aqui="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  # shellcheck source=servidor/configuracion.sh
  . "$aqui/configuracion.sh"

  # Si la recogida horaria sigue en marcha (una larga), esta ejecución no arranca: comprueba su
  # cerrojo sin quedárselo y la hora siguiente lo vuelve a intentar.
  if ! flock --nonblock --shared "$CERROJO" true; then
    echo "la recogida horaria sigue en marcha: esta ejecución no se lanza"
    return 0
  fi
  exec 7> "$CERROJO_LUCES"
  if ! flock --nonblock 7; then
    echo "la medida anterior sigue en marcha: esta no se lanza"
    return 0
  fi

  # Las credenciales del almacén público, para subir las ciudades con alumbrado reducido; sin
  # ellas se mide y se evalúa igual.
  if [ -r "$ALMACEN_CREDENCIALES" ]; then
    # shellcheck disable=SC1090
    . "$ALMACEN_CREDENCIALES"
    export ALMACEN_ID ALMACEN_SECRETO
  else
    echo "sin $ALMACEN_CREDENCIALES: las ciudades con alumbrado reducido no se suben" >&2
  fi
  export EODI_LUCES_DATOS="$LUCES_DATOS" EODI_GUERRA_DATOS="$GUERRA_DATOS"
  install -d -m 700 "$LUCES_DATOS"
  cd "$CLON"
  "$ENTORNO/bin/python" -m recogida.luces calcular --tope-min "$LUCES_TOPE_MINUTOS" \
    --registro "$LUCES_REGISTRO" || codigo=$?
  echo "luces nocturnas terminadas con código $codigo"
  return "$codigo"
}

principal "$@"
