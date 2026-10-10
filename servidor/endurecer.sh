#!/usr/bin/env bash
# Endurecimiento del servidor. Se ejecuta como root en el servidor recién creado y puede
# repetirse: cada paso deja el mismo resultado.
#
# - usuario «eodi» sin privilegios para el observatorio y «operador» con sudo para
#   administrar;
# - SSH solo con clave, sin contraseña, sin root y sin reenvíos;
# - cortafuegos del propio servidor (nftables): solo entran SSH, HTTP y HTTPS, además del de
#   Hetzner;
# - fail2ban con vetos crecientes, actualizaciones de seguridad automáticas sin reinicio
#   automático (lo hace eodi-reinicio cuando no corta nada), zona horaria UTC, hora
#   sincronizada y diario con rotación.
set -euo pipefail

aqui="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=servidor/configuracion.sh
. "$aqui/configuracion.sh"

export DEBIAN_FRONTEND=noninteractive
# needrestart reinicia tras cada actualización los servicios que usan bibliotecas cambiadas.
# Las unidades del observatorio son trabajos con su propio temporizador: reiniciar una corta
# su trabajo (el 2 de octubre de 2026 cortó un día del histórico de tráfico) y, como son de
# tipo oneshot, deja la actualización esperando a que terminen. Se excluyen todas las
# «eodi-»: la siguiente ejecución de su temporizador ya usa las bibliotecas nuevas.
install -d -m 755 /etc/needrestart/conf.d
cat > /etc/needrestart/conf.d/50-eodi.conf <<'FIN'
$nrconf{override_rc}{qr(^eodi-)} = 0;
FIN
apt-get update -q
# La imagen sale con retraso: se pone al día antes de nada.
apt-get upgrade -y -q
apt-get install -y -q fail2ban unattended-upgrades git ca-certificates util-linux nftables

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
MaxAuthTries 3
LoginGraceTime 30
X11Forwarding no
AllowTcpForwarding no
AllowAgentForwarding no
PermitTunnel no
FIN
# La comprobación necesita este directorio, que solo existe mientras hay una sesión abierta.
install -d -m 755 /run/sshd
sshd -t
# Root deja de tener clave autorizada: aunque cambiara la configuración, no entra.
rm -f /root/.ssh/authorized_keys
# En una imagen recién creada sshd arranca por socket (ssh.socket) y lee la configuración en cada
# conexión: solo se recarga si el servicio está en marcha (el simulacro del 7 de octubre de 2026
# se paró aquí).
if systemctl is-active --quiet ssh.service; then
  systemctl reload ssh.service
fi

# --- Cortafuegos del servidor --------------------------------------------------------
# Además del cortafuegos de Hetzner (reconstruir.sh): si un día se quitara aquel, este sigue.
# Entra SSH, HTTP y HTTPS (ntfy, servidor/ntfy.sh), lo que responde a una conexión ya abierta
# y el ICMP que hace falta (IPv6 no funciona sin él); sale todo. Tabla propia: no toca la de
# fail2ban.
cat > /etc/nftables.conf <<FIN
#!/usr/sbin/nft -f
# Cortafuegos del servidor de recogida (servidor/endurecer.sh)
table inet eodi
delete table inet eodi
table inet eodi {
  chain entrada {
    type filter hook input priority filter; policy drop;
    iif lo accept
    ct state established,related accept
    ct state invalid drop
    ip protocol icmp icmp type { echo-request, destination-unreachable, time-exceeded, parameter-problem } accept
    ip6 nexthdr icmpv6 icmpv6 type { echo-request, destination-unreachable, packet-too-big, time-exceeded, parameter-problem, nd-router-advert, nd-neighbor-solicit, nd-neighbor-advert } accept
    udp sport 67 udp dport 68 accept
    udp sport 547 udp dport 546 accept
    tcp dport $PUERTO_SSH ct state new accept
    tcp dport { 80, 443 } ct state new accept
  }
  chain reenvio {
    type filter hook forward priority filter; policy drop;
  }
}
FIN
nft -c -f /etc/nftables.conf
systemctl enable --quiet nftables
nft -f /etc/nftables.conf

# --- fail2ban ------------------------------------------------------------------------
cat > /etc/fail2ban/jail.d/eodi.local <<FIN
[DEFAULT]
bantime.increment = true
bantime.maxtime = $VETO_MAXIMO

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
# Sin reinicio automático: a hora fija podía cortar un ataque en curso (lo que emite NEPTUN con
# el servidor apagado se pierde) o un trabajo largo. Si una actualización lo pide, reinicia
# eodi-reinicio (instalar.sh) cuando no corta nada.
cat > /etc/apt/apt.conf.d/52eodi-reinicio <<FIN
Unattended-Upgrade::Automatic-Reboot "false";
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
