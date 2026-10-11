#!/usr/bin/env bash
# Contador de visitas propio y resumen diario privado (docs/visitas.md). Se ejecuta como root en el
# servidor, después de servidor/ntfy.sh (usa su Caddy), y puede repetirse: cada paso deja el mismo
# resultado.
#
# - GoatCounter (versión estable oficial, binario único con SQLite, comprobado por su huella) como
#   servicio con tope de memoria, solo en local, con Caddy delante en https://stats.droneobservatory.eu;
# - un sitio y un único usuario administrador, solo si llega la contraseña por la entrada estándar
#   (--clave-lucas): reconstruir.sh la lee de %USERPROFILE%\.eodi\goatcounter_lucas.txt. Sin ella,
#   no cambia nada de lo que ya hay;
# - «eodi» puede leer la base de GoatCounter (grupo goatcounter, sin escritura) para el resumen
#   diario y para su copia de seguridad;
# - la unidad y el temporizador del resumen diario y de la copia (eodi-visitas).
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

# --- Binario ---------------------------------------------------------------------------
if [ ! -x "$GOATCOUNTER_BINARIO" ] \
  || ! "$GOATCOUNTER_BINARIO" version 2>/dev/null | grep -q "version=$GOATCOUNTER_VERSION;"; then
  temporal="$(mktemp -d)"
  curl -fsSL -o "$temporal/goatcounter.gz" "$GOATCOUNTER_URL"
  if ! printf '%s  %s\n' "$GOATCOUNTER_SHA256" "$temporal/goatcounter.gz" | sha256sum -c --quiet; then
    echo "el binario de GoatCounter no tiene la huella esperada" >&2
    rm -rf "$temporal"
    exit 1
  fi
  gunzip "$temporal/goatcounter.gz"
  install -m 755 "$temporal/goatcounter" "$GOATCOUNTER_BINARIO"
  rm -rf "$temporal"
fi

# --- Usuario y datos -------------------------------------------------------------------
if ! getent passwd "$GOATCOUNTER_USUARIO" >/dev/null; then
  useradd --system --home-dir "$GOATCOUNTER_DATOS" --shell /usr/sbin/nologin "$GOATCOUNTER_USUARIO"
fi
# La carpeta y la base se leen desde el grupo (750/640): «eodi» lee, no escribe.
install -d -m 750 -o "$GOATCOUNTER_USUARIO" -g "$GOATCOUNTER_USUARIO" "$GOATCOUNTER_DATOS"
usermod -a -G "$GOATCOUNTER_USUARIO" "$USUARIO"
install -d -m 700 -o "$USUARIO" -g "$USUARIO" "$VISITAS_DATOS"

como_goatcounter() {
  # Sin sudo: sudo anota la orden entera en el diario, y aquí puede ir la contraseña.
  setpriv --reuid="$GOATCOUNTER_USUARIO" --regid="$GOATCOUNTER_USUARIO" --init-groups \
    "$GOATCOUNTER_BINARIO" "$@"
}
bd="sqlite+$GOATCOUNTER_BASE"
(cd "$GOATCOUNTER_DATOS" && umask 027 && como_goatcounter db newdb -db "$bd" 2>/dev/null || true)
(cd "$GOATCOUNTER_DATOS" && como_goatcounter db migrate -db "$bd" all >/dev/null)
if [ -n "$clave_lucas" ]; then
  if (cd "$GOATCOUNTER_DATOS" && como_goatcounter db show site -db "$bd" \
    -find "$GOATCOUNTER_DOMINIO" >/dev/null 2>&1); then
    (cd "$GOATCOUNTER_DATOS" && como_goatcounter db update user -db "$bd" \
      -find "$GOATCOUNTER_CORREO" -password "$clave_lucas" >/dev/null)
  else
    (cd "$GOATCOUNTER_DATOS" && como_goatcounter db create site -db "$bd" \
      -vhost "$GOATCOUNTER_DOMINIO" -user.email "$GOATCOUNTER_CORREO" \
      -user.password "$clave_lucas" >/dev/null)
  fi
fi
clave_lucas=""
# Qué guarda el sitio y la zona horaria del panel, con el servicio parado (GoatCounter guarda los
# ajustes en memoria). El mismo script borra, tras cada parada, las sesiones que GoatCounter vuelca
# a la base al pararse, cuya clave lleva la IP del visitante (servidor/goatcounter_ajustes.py).
install -d -m 755 /usr/local/libexec/eodi
install -m 755 "$aqui/goatcounter_ajustes.py" "$aqui/ntfy_suscriptores.py" /usr/local/libexec/eodi/
systemctl stop goatcounter 2>/dev/null || true
setpriv --reuid="$GOATCOUNTER_USUARIO" --regid="$GOATCOUNTER_USUARIO" --init-groups   python3 /usr/local/libexec/eodi/goatcounter_ajustes.py sin-sesiones "$GOATCOUNTER_BASE"
setpriv --reuid="$GOATCOUNTER_USUARIO" --regid="$GOATCOUNTER_USUARIO" --init-groups   python3 /usr/local/libexec/eodi/goatcounter_ajustes.py ajustar "$GOATCOUNTER_BASE"
chmod 640 "$GOATCOUNTER_BASE"*

# --- Servicio --------------------------------------------------------------------------
cat > /etc/systemd/system/goatcounter.service <<FIN
[Unit]
Description=Contador de visitas de la web (GoatCounter, EODI)
Wants=network-online.target
After=network-online.target

[Service]
User=$GOATCOUNTER_USUARIO
Group=$GOATCOUNTER_USUARIO
WorkingDirectory=$GOATCOUNTER_DATOS
# Las direcciones IP no se guardan: GoatCounter usa la del visitante para el país y, en memoria y
# como mucho 8 horas, para reconocer la sesión; lo que vuelca a la base al pararse se borra al
# momento (ExecStopPost).
ExecStart=$GOATCOUNTER_BINARIO serve -listen $GOATCOUNTER_ESCUCHA -tls http -db $bd -automigrate -smtp stdout
ExecStopPost=/usr/bin/python3 /usr/local/libexec/eodi/goatcounter_ajustes.py sin-sesiones $GOATCOUNTER_BASE
UMask=0027
Restart=always
RestartSec=10
MemoryMax=$GOATCOUNTER_MEMORIA
NoNewPrivileges=yes
PrivateTmp=yes
PrivateDevices=yes
ProtectSystem=strict
ProtectHome=yes
ReadWritePaths=$GOATCOUNTER_DATOS

[Install]
WantedBy=multi-user.target
FIN

# --- Resumen diario y copia de la base de visitas ---------------------------------------
cat > "/etc/systemd/system/$UNIDAD_VISITAS.service" <<FIN
[Unit]
Description=Resumen diario privado, suscriptores de ntfy y copia de las visitas (EODI)
Wants=network-online.target
After=network-online.target time-sync.target

[Service]
Type=oneshot
User=$USUARIO
Group=$USUARIO
SupplementaryGroups=systemd-journal $GOATCOUNTER_USUARIO
WorkingDirectory=$CLON
# Los navegadores con notificaciones por canal (webpush.db solo lo lee ntfy): como root, solo los
# recuentos, a un fichero de eodi (servidor/ntfy_suscriptores.py).
ExecStartPre=+/usr/bin/python3 /usr/local/libexec/eodi/ntfy_suscriptores.py /var/cache/ntfy/webpush.db $VISITAS_DATOS/ntfy_navegador.json $USUARIO
ExecStart=/usr/bin/env bash $CLON/servidor/visitas_resumen.sh
SyslogIdentifier=$UNIDAD_VISITAS
TimeoutStartSec=${TOPE_VISITAS_MINUTOS}min
Nice=10
IOSchedulingClass=idle
MemoryMax=$VISITAS_MEMORIA
NoNewPrivileges=yes
PrivateTmp=yes
ProtectSystem=full
FIN
cat > "/etc/systemd/system/$UNIDAD_VISITAS.timer" <<FIN
[Unit]
Description=Resumen diario, suscriptores de ntfy y copia de las visitas (EODI), cada 5 minutos

[Timer]
OnCalendar=$CALENDARIO_VISITAS
AccuracySec=1s

[Install]
WantedBy=timers.target
FIN

# --- HTTPS con Caddy (el mismo Caddyfile que ntfy) ----------------------------------------
install -m 644 "$raiz/configuracion/ntfy/Caddyfile" /etc/caddy/Caddyfile

systemctl daemon-reload
systemctl enable --quiet goatcounter
systemctl restart goatcounter
systemctl reload-or-restart caddy
for _ in $(seq 1 20); do
  curl -fsS -o /dev/null "http://$GOATCOUNTER_ESCUCHA/status" -H "Host: $GOATCOUNTER_DOMINIO" 2>/dev/null && break
  sleep 1
done
# El temporizador, solo cuando el clon ya trae el script (en una instalación anterior a la fusión,
# todavía no).
if [ -f "$CLON/servidor/visitas_resumen.sh" ]; then
  systemctl enable --quiet --now "$UNIDAD_VISITAS.timer"
fi

echo "visitas listas: GoatCounter $GOATCOUNTER_VERSION en https://$GOATCOUNTER_DOMINIO"
