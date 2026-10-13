#!/usr/bin/env bash
# Reintentos de todas las unidades del servidor (docs/servidor.md, «Reintentos»), como root.
#
# Cada servicio lleva Restart=on-failure con una espera razonable y un tope de arranques: un
# fallo suelto se arregla solo con el reintento y uno que se repite no gasta sin fin. Los
# temporizadores, Persistent=true (lo que no se lanzó con el servidor apagado se lanza al
# arrancar). Se escribe como complemento (reintentos.conf en <unidad>.d/), sin tocar la unidad.
#
# Comprobado en el servidor (systemd 259) el 12 de octubre de 2026: el temporizador sigue vivo
# cuando su servicio agota el tope de arranques («Start request repeated too quickly») y lo
# vuelve a lanzar a su hora; el contador de reintentos vuelve a cero en cada arranque del
# temporizador. El tope cuenta todos los arranques, buenos o malos: en las unidades frecuentes es
# más alto que los arranques normales de su ventana.
#
# La recogida es especial: solo se repite si termina con código 1 o la corta systemd (no con el
# 2, que publica), a los 10 minutos y otra vez 15 después (a los 25 del primer fallo), y nunca más
# de dos veces por hora. El cerrojo de recogida.sh impide que se solapen dos, y mientras espera el
# reintento la unidad sigue «activating»: el temporizador de la hora siguiente no lanza otra.
#
# El paso a solo disco (una sola vez, con sus comprobaciones) no se toca.
#
# Uso: sudo bash servidor/reintentos.sh   (lo llama instalar.sh)
#      EODI_SYSTEMD_DIR=<carpeta> bash servidor/reintentos.sh   (pruebas: escribe ahí y no recarga)
set -euo pipefail

aqui="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=servidor/configuracion.sh
. "$aqui/configuracion.sh"
destino="${EODI_SYSTEMD_DIR:-/etc/systemd/system}"

# unidad | espera entre reintentos | ventana del tope | arranques en la ventana | extra
REINTENTOS=(
  "$UNIDAD|10min|50min|3|RestartPreventExitStatus=$SALIDA_AVISO RestartSteps=1 RestartMaxDelaySec=15min"
  "$UNIDAD_EXPORTACION|20min|3h|3|"
  "$UNIDAD_DETALLE|15min|170min|2|"
  "$UNIDAD_GUERRA|5min|50min|2|"
  "$UNIDAD_TRAFICO|5min|50min|2|"
  "$UNIDAD_BUSQUEDA|5min|50min|2|"
  "$UNIDAD_DEDUCCION|5min|50min|2|"
  "$UNIDAD_CATALOGO|15min|3h|3|"
  "$UNIDAD_SATELITE|10min|2h|3|"
  "$UNIDAD_LUCES|5min|50min|2|"
  "$UNIDAD_FOCOS_VIVO|5min|50min|2|"
  "$UNIDAD_RUTAS|5min|50min|2|"
  "$UNIDAD_SEGUIMIENTO_ARCHIVO|5min|50min|2|"
  "$UNIDAD_ARCHIVO|10min|50min|2|"
  "$UNIDAD_REPLICA|5min|50min|2|"
  "$UNIDAD_RESERVA|30s|10min|10|"
  "$UNIDAD_VERSIONES|10min|2h|3|"
  "$UNIDAD_PRUEBA_RESTAURACION|15min|2h|3|"
  "$UNIDAD_VIGILANCIA|60s|10min|5|"
  "$UNIDAD_VISITAS|60s|10min|5|"
  "$UNIDAD_REINICIO|60s|10min|5|"
  # Los servicios que no paran ya llevan Restart=always (que incluye on-failure); Caddy, el del
  # paquete, no: se le pone aquí.
  "caddy|10s|10min|10|"
)

# Temporizadores sin Persistent=true en su unidad.
PERSISTENTES=("$UNIDAD_RESERVA" "$UNIDAD_VISITAS" "$UNIDAD_REINICIO")

for linea in "${REINTENTOS[@]}"; do
  IFS="|" read -r unidad espera ventana arranques extra <<< "$linea"
  install -d -m 755 "$destino/$unidad.service.d"
  {
    echo "# Escrito por servidor/reintentos.sh: no editar a mano."
    echo "[Unit]"
    echo "StartLimitIntervalSec=$ventana"
    echo "StartLimitBurst=$arranques"
    echo
    echo "[Service]"
    echo "Restart=on-failure"
    echo "RestartSec=$espera"
    for ajuste in $extra; do
      echo "$ajuste"
    done
  } > "$destino/$unidad.service.d/reintentos.conf"
done

for unidad in "${PERSISTENTES[@]}"; do
  install -d -m 755 "$destino/$unidad.timer.d"
  printf '# Escrito por servidor/reintentos.sh: no editar a mano.\n[Timer]\nPersistent=true\n' \
    > "$destino/$unidad.timer.d/reintentos.conf"
done

if [ -z "${EODI_SYSTEMD_DIR:-}" ]; then
  systemctl daemon-reload
fi
echo "reintentos al día"
