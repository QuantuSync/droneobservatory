#!/usr/bin/env bash
# Instala el guardián del sistema (recogida/guardian.py, docs/servidor.md, «Guardián del sistema»),
# como root: su servicio y su temporizador, cada 5 minutos y al minuto de arrancar. Lo llama
# instalar.sh; también se puede lanzar solo, sin reconstruir el servidor:
#
#   sudo bash /home/eodi/droneobservatory/servidor/guardian.sh
#   systemctl list-timers eodi-guardian.timer
#   journalctl -u eodi-guardian -n 20
#   cat /var/lib/eodi-guardian/estado.json
#
# Con el Python del sistema y sin el entorno del observatorio, y con la entrada de un dato y no de
# /dev/null: systemd lo puede lanzar aunque /dev/null falte (el 13 de octubre de 2026 no pudo
# lanzar ningún servicio: «Failed to set up standard input»).
#
# Uso: sudo bash servidor/guardian.sh
#      EODI_SYSTEMD_DIR=<carpeta> bash servidor/guardian.sh   (pruebas: escribe ahí y no activa)
set -euo pipefail

aqui="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=servidor/configuracion.sh
. "$aqui/configuracion.sh"
destino="${EODI_SYSTEMD_DIR:-/etc/systemd/system}"

cat > "$destino/$UNIDAD_GUARDIAN.service" <<FIN
[Unit]
Description=Guardián del sistema: dispositivos, /tmp, sshd, disco y último recurso (EODI)

[Service]
Type=oneshot
Environment=HOME=/root
Environment=EODI_GUARDIAN_ESTADO=$GUARDIAN_ESTADO
Environment=EODI_GUARDIAN_CASA=$CASA
Environment=EODI_GUARDIAN_USUARIO=$USUARIO
Environment=EODI_GUARDIAN_RECOGIDA=$UNIDAD.service
ExecStart=/usr/bin/python3 -I $CLON/recogida/guardian.py
StandardInput=data
StandardInputData=Cg==
StandardOutput=journal
StandardError=journal
StateDirectory=$UNIDAD_GUARDIAN
StateDirectoryMode=0755
SyslogIdentifier=$UNIDAD_GUARDIAN
TimeoutStartSec=4min
MemoryMax=$GUARDIAN_MEMORIA
FIN
cat > "$destino/$UNIDAD_GUARDIAN.timer" <<FIN
[Unit]
Description=Guardián del sistema (EODI), cada 5 minutos

[Timer]
OnBootSec=1min
OnCalendar=$CALENDARIO_GUARDIAN
AccuracySec=1s

[Install]
WantedBy=timers.target
FIN

if [ -z "${EODI_SYSTEMD_DIR:-}" ]; then
  systemctl daemon-reload
  systemctl enable --now "$UNIDAD_GUARDIAN.timer"
fi
echo "guardián instalado"
