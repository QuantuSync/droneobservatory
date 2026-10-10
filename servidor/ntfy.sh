#!/usr/bin/env bash
# Servidor ntfy de los avisos públicos (docs/avisos.md). Se ejecuta como root en el servidor y
# puede repetirse: cada paso deja el mismo resultado.
#
# - ntfy del repositorio oficial (archive.ntfy.sh, clave comprobada por su huella) y Caddy de
#   Ubuntu delante, con el certificado de Let's Encrypt que pide y renueva solo;
# - la configuración de configuracion/ntfy/, con tope de memoria para los dos servicios;
# - los puertos 80 y 443 en el cortafuegos del servidor (el de Hetzner, en reconstruir.sh);
# - los temas públicos de configuracion/avisos.json: lectura para todos, escritura solo para
#   «observatorio» (los avisos automáticos, con su token en $NTFY_TOKEN) y «lucas»;
# - «lucas» solo si llega su contraseña por la entrada estándar (--clave-lucas): reconstruir.sh
#   la lee de %USERPROFILE%\.eodi\ntfy_lucas.txt.
set -euo pipefail

aqui="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=servidor/configuracion.sh
. "$aqui/configuracion.sh"
raiz="$(cd "$aqui/.." && pwd)"

clave_lucas=""
if [ "${1:-}" = "--clave-lucas" ]; then
  IFS= read -r clave_lucas || true
  if [ -z "$clave_lucas" ]; then
    echo "falta la contraseña de lucas en la entrada estándar" >&2
    exit 1
  fi
fi

export DEBIAN_FRONTEND=noninteractive

# --- Paquetes ------------------------------------------------------------------------
if [ ! -f /etc/apt/keyrings/ntfy.gpg ]; then
  install -d -m 755 /etc/apt/keyrings
  temporal="$(mktemp)"
  curl -fsSL -o "$temporal" "$NTFY_CLAVE_APT"
  huella="$(gpg --show-keys --with-colons "$temporal" | awk -F: '$1 == "fpr" { print $10; exit }')"
  if [ "$huella" != "$NTFY_HUELLA_APT" ]; then
    echo "la clave del repositorio de ntfy no tiene la huella esperada: $huella" >&2
    rm -f "$temporal"
    exit 1
  fi
  install -m 644 "$temporal" /etc/apt/keyrings/ntfy.gpg
  rm -f "$temporal"
fi
printf 'deb [arch=%s signed-by=/etc/apt/keyrings/ntfy.gpg] %s stable main\n' \
  "$(dpkg --print-architecture)" "$NTFY_REPOSITORIO_APT" > /etc/apt/sources.list.d/ntfy.list
if ! command -v ntfy >/dev/null || ! command -v caddy >/dev/null; then
  apt-get update -q
  apt-get install -y -q ntfy caddy
fi
# Las actualizaciones automáticas también para ntfy.
cat > /etc/apt/apt.conf.d/54eodi-ntfy <<'FIN'
Unattended-Upgrade::Origins-Pattern:: "site=archive.ntfy.sh";
FIN

# --- Configuración ---------------------------------------------------------------------
install -m 644 "$raiz/configuracion/ntfy/server.yml" /etc/ntfy/server.yml
install -m 644 "$raiz/configuracion/ntfy/Caddyfile" /etc/caddy/Caddyfile
install -d -m 750 -o ntfy -g ntfy /var/lib/ntfy /var/cache/ntfy
# Claves de las notificaciones del navegador: se crean una vez y no salen del servidor.
if [ ! -s /etc/ntfy/webpush.env ]; then
  claves="$(ntfy webpush keys 2>&1)"
  publica="$(printf '%s\n' "$claves" | awk '/web-push-public-key:/ { print $2 }')"
  privada="$(printf '%s\n' "$claves" | awk '/web-push-private-key:/ { print $2 }')"
  if [ -z "$publica" ] || [ -z "$privada" ]; then
    echo "no se pudieron crear las claves de Web Push" >&2
    exit 1
  fi
  umask 077
  printf 'NTFY_WEB_PUSH_PUBLIC_KEY=%s\nNTFY_WEB_PUSH_PRIVATE_KEY=%s\n' "$publica" "$privada" \
    > /etc/ntfy/webpush.env
  umask 022
fi
chown root:ntfy /etc/ntfy/webpush.env
chmod 640 /etc/ntfy/webpush.env

install -d -m 755 /etc/systemd/system/ntfy.service.d /etc/systemd/system/caddy.service.d
cat > /etc/systemd/system/ntfy.service.d/eodi.conf <<FIN
[Service]
EnvironmentFile=/etc/ntfy/webpush.env
MemoryMax=$NTFY_MEMORIA
Restart=always
FIN
cat > /etc/systemd/system/caddy.service.d/eodi.conf <<FIN
[Service]
MemoryMax=$CADDY_MEMORIA
FIN
systemctl daemon-reload
systemctl enable --quiet ntfy caddy
systemctl restart ntfy
systemctl reload-or-restart caddy

# --- Cortafuegos del servidor ----------------------------------------------------------
# endurecer.sh ya escribe estos puertos en una instalación nueva; aquí se añaden a la existente.
if ! grep -q "tcp dport { 80, 443 }" /etc/nftables.conf; then
  sed -i "s/^\(\s*\)tcp dport $PUERTO_SSH ct state new accept$/&\n\1tcp dport { 80, 443 } ct state new accept/" \
    /etc/nftables.conf
  nft -c -f /etc/nftables.conf
  nft -f /etc/nftables.conf
fi

# --- Usuarios y permisos ---------------------------------------------------------------
como_ntfy() { sudo --preserve-env=NTFY_PASSWORD -u ntfy ntfy "$@"; }
for _ in $(seq 1 20); do
  curl -fsS "http://$NTFY_ESCUCHA/v1/health" >/dev/null 2>&1 && break
  sleep 1
done
temas="$(python3 -c 'import json, sys
c = json.load(open(sys.argv[1], encoding="utf-8"))
print(c["general"]["tema"])
for p in c["paises"].values():
    print(p["tema"])' "$raiz/configuracion/avisos.json")"

usuarios="$(como_ntfy user list 2>&1 || true)"
if ! printf '%s\n' "$usuarios" | grep -q "^user observatorio "; then
  NTFY_PASSWORD="$(head -c 48 /dev/urandom | base64 | tr -d '/+=\n')" como_ntfy user add --role=user observatorio
fi
if [ -n "$clave_lucas" ]; then
  if printf '%s\n' "$usuarios" | grep -q "^user lucas "; then
    NTFY_PASSWORD="$clave_lucas" como_ntfy user change-pass lucas >/dev/null
  else
    NTFY_PASSWORD="$clave_lucas" como_ntfy user add --role=user lucas >/dev/null
  fi
fi
lucas_existe="$(como_ntfy user list 2>&1 | grep -c "^user lucas " || true)"

# Los permisos se rehacen enteros desde la lista de temas: un tema quitado deja de estar abierto.
como_ntfy access --reset >/dev/null
while IFS= read -r tema; do
  como_ntfy access everyone "$tema" read-only >/dev/null
  como_ntfy access observatorio "$tema" write-only >/dev/null
  if [ "$lucas_existe" -gt 0 ]; then
    como_ntfy access lucas "$tema" read-write >/dev/null
  fi
done <<< "$temas"

# Token de «observatorio» para recogida/avisos.py, solo si no hay uno.
if [ ! -s "$NTFY_TOKEN" ]; then
  salida="$(como_ntfy token add --label=recogida observatorio 2>&1)"
  token="$(printf '%s\n' "$salida" | grep -o 'tk_[A-Za-z0-9]*' | head -n 1)"
  if [ -z "$token" ]; then
    echo "no se pudo crear el token de observatorio" >&2
    exit 1
  fi
  install -d -m 700 -o "$USUARIO" -g "$USUARIO" "$SECRETOS"
  umask 077
  printf '%s' "$token" > "$NTFY_TOKEN"
  umask 022
fi
chown "$USUARIO:$USUARIO" "$NTFY_TOKEN"
chmod 600 "$NTFY_TOKEN"
install -d -m 700 -o "$USUARIO" -g "$USUARIO" "$AVISOS_DATOS"

echo "ntfy listo: $(printf '%s\n' "$temas" | wc -l) temas públicos"
