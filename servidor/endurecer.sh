#!/usr/bin/env bash
# Endurecimiento del servidor. Se ejecuta como root en el servidor recién creado y puede
# repetirse: cada paso deja el mismo resultado.
#
# - usuario «eodi» sin privilegios para el observatorio y «operador» con sudo para
#   administrar;
# - SSH solo con clave, sin contraseña y sin root;
# - fail2ban, actualizaciones de seguridad automáticas con reinicio de madrugada,
#   zona horaria UTC, hora sincronizada y diario con rotación.
set -euo pipefail

aqui="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=servidor/configuracion.sh
. "$aqui/configuracion.sh"

export DEBIAN_FRONTEND=noninteractive
apt-get update -q
# La imagen sale con retraso: se pone al día antes de nada.
apt-get upgrade -y -q
apt-get install -y -q fail2ban unattended-upgrades git ca-certificates util-linux

# --- Usuarios ------------------------------------------------------------------------
id "$USUARIO" >/dev/null 2>&1 || adduser --disabled-password --gecos "" "$USUARIO"
id "$OPERADOR" >/dev/null 2>&1 || adduser --disabled-password --gecos "" "$OPERADOR"
# Las cuentas no tienen contraseña: no se puede entrar con ella ni por consola.
passwd --lock "$USUARIO" >/dev/null
passwd --lock "$OPERADOR" >/dev/null
passwd --lock root >/dev/null
# El operador lee el diario de la recogida sin sudo.
usermod --append --groups systemd-journal "$OPERADOR"
# El operador entra con la clave con la que se creó el servidor.
install -d -m 700 -o "$OPERADOR" -g "$OPERADOR" "/home/$OPERADOR/.ssh"
if [ -s /root/.ssh/authorized_keys ]; then
  install -m 600 -o "$OPERADOR" -g "$OPERADOR" /root/.ssh/authorized_keys \
    "/home/$OPERADOR/.ssh/authorized_keys"
fi
test -s "/home/$OPERADOR/.ssh/authorized_keys"
printf '%s ALL=(ALL) NOPASSWD:ALL\n' "$OPERADOR" > "/etc/sudoers.d/90-$OPERADOR"
chmod 440 "/etc/sudoers.d/90-$OPERADOR"
visudo -c -q

# --- SSH -----------------------------------------------------------------------------
# El primer valor que lee sshd es el que vale: el fichero va delante de los de la imagen.
cat > /etc/ssh/sshd_config.d/00-eodi.conf <<FIN
PermitRootLogin no
PubkeyAuthentication yes
PasswordAuthentication no
KbdInteractiveAuthentication no
PermitEmptyPasswords no
AllowUsers $OPERADOR
FIN
# La comprobación necesita este directorio, que solo existe mientras hay una sesión abierta.
install -d -m 755 /run/sshd
sshd -t
# Root deja de tener clave autorizada: aunque cambiara la configuración, no entra.
rm -f /root/.ssh/authorized_keys
systemctl reload ssh

# --- fail2ban ------------------------------------------------------------------------
cat > /etc/fail2ban/jail.d/eodi.local <<FIN
[sshd]
enabled = true
backend = systemd
maxretry = $VETO_INTENTOS
findtime = $VETO_VENTANA
bantime = $VETO_DURACION
FIN
systemctl enable --quiet fail2ban
systemctl restart fail2ban

# --- Actualizaciones de seguridad ----------------------------------------------------
cat > /etc/apt/apt.conf.d/20auto-upgrades <<FIN
APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Unattended-Upgrade "1";
FIN
cat > /etc/apt/apt.conf.d/52eodi-reinicio <<FIN
Unattended-Upgrade::Automatic-Reboot "true";
Unattended-Upgrade::Automatic-Reboot-Time "$HORA_REINICIO";
FIN
systemctl enable --quiet --now unattended-upgrades

# --- Hora ----------------------------------------------------------------------------
timedatectl set-timezone UTC
timedatectl set-ntp true

# --- Diario --------------------------------------------------------------------------
install -d /etc/systemd/journald.conf.d
cat > /etc/systemd/journald.conf.d/eodi.conf <<FIN
[Journal]
SystemMaxUse=$DIARIO_MAXIMO
MaxRetentionSec=$DIARIO_ANTIGUEDAD
FIN
systemctl restart systemd-journald

echo "endurecimiento hecho"
