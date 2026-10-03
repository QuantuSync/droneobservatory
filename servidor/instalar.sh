#!/usr/bin/env bash
# Instalación del observatorio. Se ejecuta como root en el servidor ya endurecido y puede
# repetirse: cada paso deja el mismo resultado.
#
# - Python, el clon del repositorio y su entorno virtual, del usuario sin privilegios;
# - la carpeta de secretos con las claves de despliegue (las privadas no salen de aquí);
# - las unidades y los temporizadores de systemd de la recogida horaria, de la exportación
#   semanal, de las fuentes de detalle, del lector de canales de la capa de guerra, del
#   procesado del archivo diario de adsb.lol, de la búsqueda dirigida de noticias y
#   del motor de deducción.
#
# La clave age y las variables del extractor las deja después reconstruir.sh, que es
# también quien da de alta las claves de despliegue y activa el temporizador.
set -euo pipefail

aqui="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=servidor/configuracion.sh
. "$aqui/configuracion.sh"

como_usuario() { sudo -u "$USUARIO" -H "$@"; }

# --- Red -----------------------------------------------------------------------------
# Desde este centro de datos la conexión por IPv6 con Telegram falla casi siempre
# (12 de 14 intentos, medido el 30 de septiembre de 2026) y por IPv4 no falla. Python
# prueba las direcciones en el orden que da el sistema y agota el tiempo límite de cada
# petición antes de pasar a la siguiente: con IPv6 delante, la lectura de un canal no
# cabe en su tope. Esta línea pone IPv4 delante; IPv6 sigue disponible como segunda opción.
if ! grep -qxF "$PREFERENCIA_IPV4" /etc/gai.conf 2>/dev/null; then
  printf '%s\n' "$PREFERENCIA_IPV4" >> /etc/gai.conf
fi

# --- Python --------------------------------------------------------------------------
# La distribución trae otra versión de Python: la del proyecto sale del archivo de
# versiones alternativas, que también recibe las actualizaciones automáticas.
export DEBIAN_FRONTEND=noninteractive
if ! command -v "python$PYTHON_VERSION" >/dev/null; then
  add-apt-repository -y ppa:deadsnakes/ppa
  apt-get update -q
  apt-get install -y -q "python$PYTHON_VERSION" "python$PYTHON_VERSION-venv"
fi
cat > /etc/apt/apt.conf.d/53eodi-python <<'FIN'
Unattended-Upgrade::Allowed-Origins:: "LP-PPA-deadsnakes:${distro_codename}";
FIN

# --- Secretos ------------------------------------------------------------------------
install -d -m 700 -o "$USUARIO" -g "$USUARIO" "$SECRETOS"
for clave in "$DESPLIEGUE_DATOS" "$DESPLIEGUE_WEB"; do
  if [ ! -f "$clave" ]; then
    como_usuario ssh-keygen -q -t ed25519 -N "" -C "$TITULO_DESPLIEGUE" -f "$clave"
  fi
  chmod 600 "$clave" "$clave.pub"
done
printf '%s\n' "$HOST_GITHUB" > "$HOSTS_CONOCIDOS"
chown "$USUARIO:$USUARIO" "$HOSTS_CONOCIDOS"
chmod 600 "$HOSTS_CONOCIDOS"

# --- Datos de FIRMS -----------------------------------------------------------------
# Los CSV diarios de anomalías térmicas: del usuario del observatorio y solo para él.
install -d -m 700 -o "$USUARIO" -g "$USUARIO" "$(dirname "$FIRMS_DATOS")" "$FIRMS_DATOS"
# Lo que guarda el lector de canales de la capa de guerra: igual, solo para el observatorio.
install -d -m 700 -o "$USUARIO" -g "$USUARIO" "$GUERRA_DATOS"

# --- Datos de las fuentes oficiales de detalle ----------------------------------------
install -d -m 700 -o "$USUARIO" -g "$USUARIO" "$(dirname "$DETALLE_DATOS")" "$DETALLE_DATOS"

# --- Datos de la búsqueda dirigida de noticias ---------------------------------------
install -d -m 700 -o "$USUARIO" -g "$USUARIO" "$(dirname "$BUSQUEDA_DATOS")" "$BUSQUEDA_DATOS"

# --- Datos del motor de deducción -----------------------------------------------------
install -d -m 700 -o "$USUARIO" -g "$USUARIO" "$DEDUCCION_DATOS"
install -d -m 700 -o "$USUARIO" -g "$USUARIO" "$CATALOGO_DATOS"
# Guerra por satélite: imágenes de Sentinel-2, luz nocturna y focos en vivo.
install -d -m 700 -o "$USUARIO" -g "$USUARIO" "$SATELITE_DATOS" "$LUCES_DATOS" \
  "$FOCOS_VIVO_DATOS"
install -d -m 700 -o "$USUARIO" -g "$USUARIO" "$DIRECTO_DATOS"

# --- Datos del tráfico aéreo y de las condiciones medidas ----------------------------
install -d -m 700 -o "$USUARIO" -g "$USUARIO" "$(dirname "$TRAFICO_DATOS")" "$TRAFICO_DATOS" \
  "$METEO_DATOS"

# --- Clon y entorno virtual ----------------------------------------------------------
# El repositorio es público: se lee sin credenciales. Solo el envío usa la clave de
# despliegue, y solo desde el script de la recogida.
if [ ! -d "$CLON/.git" ]; then
  como_usuario git clone --quiet --branch "$RAMA" "$URL_LECTURA" "$CLON"
fi
como_usuario git -C "$CLON" remote set-url origin "$URL_LECTURA"
como_usuario git -C "$CLON" remote set-url --push origin "$URL_ESCRITURA"
# Un clon que ya existía se pone al día: la unidad ejecuta el script de la recogida que
# hay en él. Con el cerrojo de la recogida, para no cambiarle el clon a una en marcha.
como_usuario flock "$CERROJO" git -C "$CLON" fetch --quiet origin "$RAMA"
como_usuario flock "$CERROJO" git -C "$CLON" reset --quiet --hard "origin/$RAMA"
if [ ! -x "$ENTORNO/bin/python" ]; then
  como_usuario "python$PYTHON_VERSION" -m venv "$ENTORNO"
fi
como_usuario "$ENTORNO/bin/python" -m pip install --quiet --disable-pip-version-check \
  -r "$CLON/requirements.txt"
como_usuario sh -c "cd '$CLON' && sha256sum requirements.txt > '$ENTORNO/requisitos.sha256'"

# --- Navegador sin interfaz ----------------------------------------------------------
# Para las listas de noticias oficiales que se cargan con JavaScript (recogida/navegador.py):
# Playwright en el entorno del observatorio, Chromium en la caché del usuario y las bibliotecas
# del sistema que pide, como root. Si la herramienta de Playwright no reconoce esta versión de
# Ubuntu, se instalan a mano las que necesita Chromium sin interfaz.
como_usuario "$ENTORNO/bin/python" -m pip install --quiet --disable-pip-version-check \
  -r "$CLON/requirements-navegador.txt"
if ! "$ENTORNO/bin/python" -m playwright install-deps chromium; then
  apt-get install -y -q libnss3 libnspr4 libatk1.0-0t64 libatk-bridge2.0-0t64 libcups2t64 \
    libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 libxfixes3 libxrandr2 libgbm1 \
    libpango-1.0-0 libcairo2 libasound2t64 libatspi2.0-0t64 fonts-liberation
fi
como_usuario "$ENTORNO/bin/python" -m playwright install chromium
como_usuario sh -c "cd '$CLON' && sha256sum requirements-navegador.txt > '$ENTORNO/navegador.sha256'"

# --- Unidad y temporizador -----------------------------------------------------------
cat > "/etc/systemd/system/$UNIDAD.service" <<FIN
[Unit]
Description=Recogida horaria del EODI
Wants=network-online.target
After=network-online.target time-sync.target

[Service]
Type=oneshot
User=$USUARIO
Group=$USUARIO
WorkingDirectory=$CLON
ExecStart=/usr/bin/env bash $CLON/servidor/recogida.sh
# Nombre con el que salen sus líneas en el diario.
SyslogIdentifier=$UNIDAD
# Tope de la ejecución entera: pasado ese tiempo systemd la corta.
TimeoutStartSec=${TOPE_MINUTOS}min
NoNewPrivileges=yes
PrivateTmp=yes
ProtectSystem=full
FIN
cat > "/etc/systemd/system/$UNIDAD.timer" <<FIN
[Unit]
Description=Recogida horaria del EODI, en el minuto $MINUTO_RECOGIDA de cada hora

[Timer]
OnCalendar=*-*-* *:$MINUTO_RECOGIDA:00 UTC
AccuracySec=1s
# Si el servidor estaba apagado a su hora, la ejecución pendiente se lanza al arrancar.
Persistent=true

[Install]
WantedBy=timers.target
FIN
cat > "/etc/systemd/system/$UNIDAD_EXPORTACION.service" <<FIN
[Unit]
Description=Exportación semanal del EODI para AEGIS
Wants=network-online.target
After=network-online.target time-sync.target

[Service]
Type=oneshot
User=$USUARIO
Group=$USUARIO
WorkingDirectory=$CLON
ExecStart=/usr/bin/env bash $CLON/servidor/exportacion.sh
SyslogIdentifier=$UNIDAD_EXPORTACION
TimeoutStartSec=${TOPE_EXPORTACION_MINUTOS}min
NoNewPrivileges=yes
PrivateTmp=yes
ProtectSystem=full
FIN
cat > "/etc/systemd/system/$UNIDAD_EXPORTACION.timer" <<FIN
[Unit]
Description=Exportación semanal del EODI para AEGIS, los lunes a las 03:47 UTC

[Timer]
OnCalendar=$CALENDARIO_EXPORTACION
AccuracySec=1s
# Si el servidor estaba apagado a su hora, la exportación pendiente se lanza al arrancar.
Persistent=true

[Install]
WantedBy=timers.target
FIN
cat > "/etc/systemd/system/$UNIDAD_DETALLE.service" <<FIN
[Unit]
Description=Fuentes oficiales de detalle del EODI (Airprox, parlamentos, investigaciones)
Wants=network-online.target
After=network-online.target time-sync.target

[Service]
Type=oneshot
User=$USUARIO
Group=$USUARIO
WorkingDirectory=$CLON
ExecStart=/usr/bin/env bash $CLON/servidor/detalle.sh
SyslogIdentifier=$UNIDAD_DETALLE
TimeoutStartSec=${TOPE_DETALLE_MINUTOS}min
# Por debajo de la recogida horaria si coinciden.
Nice=15
NoNewPrivileges=yes
PrivateTmp=yes
ProtectSystem=full
FIN
cat > "/etc/systemd/system/$UNIDAD_DETALLE.timer" <<FIN
[Unit]
Description=Fuentes oficiales de detalle del EODI, cada 3 horas

[Timer]
OnCalendar=$CALENDARIO_DETALLE
AccuracySec=1s
Persistent=true

[Install]
WantedBy=timers.target
FIN
cat > "/etc/systemd/system/$UNIDAD_GUERRA.service" <<FIN
[Unit]
Description=Lector de canales de la capa de guerra del EODI
Wants=network-online.target
After=network-online.target time-sync.target

[Service]
Type=oneshot
User=$USUARIO
Group=$USUARIO
WorkingDirectory=$CLON
ExecStart=/usr/bin/env bash $CLON/servidor/guerra.sh
SyslogIdentifier=$UNIDAD_GUERRA
TimeoutStartSec=${TOPE_GUERRA_MINUTOS}min
Nice=10
NoNewPrivileges=yes
PrivateTmp=yes
ProtectSystem=full
FIN
cat > "/etc/systemd/system/$UNIDAD_GUERRA.timer" <<FIN
[Unit]
Description=Lector de canales de la capa de guerra del EODI, en el minuto $MINUTO_GUERRA

[Timer]
OnCalendar=*-*-* *:$MINUTO_GUERRA:00 UTC
AccuracySec=1s
Persistent=true

[Install]
WantedBy=timers.target
FIN
# Procesado del archivo diario de adsb.lol (servidor/trafico.sh), con su propio cerrojo y
# prioridad baja: no retiene el cerrojo de la recogida horaria.
cat > "/etc/systemd/system/$UNIDAD_TRAFICO.service" <<FIN
[Unit]
Description=Tráfico aéreo de adsb.lol del EODI (día nuevo e histórico)
Wants=network-online.target
After=network-online.target time-sync.target

[Service]
Type=oneshot
User=$USUARIO
Group=$USUARIO
WorkingDirectory=$CLON
ExecStart=/usr/bin/env bash $CLON/servidor/trafico.sh
SyslogIdentifier=$UNIDAD_TRAFICO
TimeoutStartSec=${TRAFICO_TOPE_UNIDAD}min
Nice=$TRAFICO_NICE
IOSchedulingClass=idle
NoNewPrivileges=yes
PrivateTmp=yes
ProtectSystem=full
FIN
cat > "/etc/systemd/system/$UNIDAD_TRAFICO.timer" <<FIN
[Unit]
Description=Tráfico aéreo de adsb.lol del EODI, en el minuto $MINUTO_TRAFICO de cada hora

[Timer]
OnCalendar=*-*-* *:$MINUTO_TRAFICO:00 UTC
AccuracySec=1s
Persistent=true

[Install]
WantedBy=timers.target
FIN
# Búsqueda dirigida de noticias para los cierres medidos sin incidente
# (servidor/busqueda.sh): cerrojo propio, prioridad baja, no toca la base.
cat > "/etc/systemd/system/$UNIDAD_BUSQUEDA.service" <<FIN
[Unit]
Description=Búsqueda dirigida de noticias del EODI (cierres medidos sin incidente)
Wants=network-online.target
After=network-online.target time-sync.target

[Service]
Type=oneshot
User=$USUARIO
Group=$USUARIO
WorkingDirectory=$CLON
ExecStart=/usr/bin/env bash $CLON/servidor/busqueda.sh
SyslogIdentifier=$UNIDAD_BUSQUEDA
TimeoutStartSec=${BUSQUEDA_TOPE_UNIDAD}min
Nice=15
IOSchedulingClass=idle
NoNewPrivileges=yes
PrivateTmp=yes
ProtectSystem=full
FIN
cat > "/etc/systemd/system/$UNIDAD_BUSQUEDA.timer" <<FIN
[Unit]
Description=Búsqueda dirigida de noticias del EODI, en el minuto $MINUTO_BUSQUEDA de cada hora

[Timer]
OnCalendar=*-*-* *:0$MINUTO_BUSQUEDA:00 UTC
AccuracySec=1s
Persistent=true

[Install]
WantedBy=timers.target
FIN
# Motor de deducción (servidor/deduccion.sh): su propio cerrojo y prioridad baja; solo lee la
# base de la rama estado y deja sus resultados en DEDUCCION_DATOS, que guarda la recogida.
cat > "/etc/systemd/system/$UNIDAD_DEDUCCION.service" <<FIN
[Unit]
Description=Motor de deducción del EODI (clases de dron compatibles por reglas físicas)
Wants=network-online.target
After=network-online.target time-sync.target

[Service]
Type=oneshot
User=$USUARIO
Group=$USUARIO
WorkingDirectory=$CLON
ExecStart=/usr/bin/env bash $CLON/servidor/deduccion.sh
SyslogIdentifier=$UNIDAD_DEDUCCION
TimeoutStartSec=${TOPE_DEDUCCION_MINUTOS}min
Nice=$DEDUCCION_NICE
IOSchedulingClass=idle
NoNewPrivileges=yes
PrivateTmp=yes
ProtectSystem=full
FIN
cat > "/etc/systemd/system/$UNIDAD_DEDUCCION.timer" <<FIN
[Unit]
Description=Motor de deducción del EODI, en el minuto $MINUTO_DEDUCCION de cada hora

[Timer]
OnCalendar=*-*-* *:0$MINUTO_DEDUCCION:00 UTC
AccuracySec=1s
Persistent=true

[Install]
WantedBy=timers.target
FIN
# Barrido del catálogo vivo (servidor/catalogo.sh): su propio cerrojo y prioridad baja; solo lee
# la base de la rama estado y deja lo que encuentra en CATALOGO_DATOS, que guarda la recogida.
cat > "/etc/systemd/system/$UNIDAD_CATALOGO.service" <<FIN
[Unit]
Description=Barrido del catálogo de prestaciones del EODI (catálogo vivo)
Wants=network-online.target
After=network-online.target time-sync.target

[Service]
Type=oneshot
User=$USUARIO
Group=$USUARIO
WorkingDirectory=$CLON
ExecStart=/usr/bin/env bash $CLON/servidor/catalogo.sh
SyslogIdentifier=$UNIDAD_CATALOGO
TimeoutStartSec=${TOPE_CATALOGO_MINUTOS}min
Nice=$CATALOGO_NICE
IOSchedulingClass=idle
NoNewPrivileges=yes
PrivateTmp=yes
ProtectSystem=full
FIN
cat > "/etc/systemd/system/$UNIDAD_CATALOGO.timer" <<FIN
[Unit]
Description=Barrido del catálogo de prestaciones del EODI, una vez al día

[Timer]
OnCalendar=$CALENDARIO_CATALOGO
AccuracySec=1s
Persistent=true

[Install]
WantedBy=timers.target
FIN
# Detección en directo (servidor/directo.sh): siempre en marcha, con su propio cerrojo; systemd
# la vuelve a lanzar si se para (también cuando sale para tomar el código nuevo del clon).
cat > "/etc/systemd/system/$UNIDAD_DIRECTO.service" <<FIN
[Unit]
Description=Detección en directo de cierres de aeropuerto del EODI
Wants=network-online.target
After=network-online.target time-sync.target

[Service]
Type=simple
User=$USUARIO
Group=$USUARIO
WorkingDirectory=$CLON
ExecStart=/usr/bin/env bash $CLON/servidor/directo.sh
SyslogIdentifier=$UNIDAD_DIRECTO
Restart=always
RestartSec=30
TimeoutStopSec=60
Nice=$DIRECTO_NICE
MemoryMax=$DIRECTO_MEMORIA
NoNewPrivileges=yes
PrivateTmp=yes
ProtectSystem=full

[Install]
WantedBy=multi-user.target
FIN
# Guerra por satélite (servidor/satelite.sh, luces.sh y focos_vivo.sh): cada uno con su propio
# cerrojo y prioridad baja; ninguno toca la base ni el clon.
unidad_satelite() {
  local unidad="$1" descripcion="$2" script="$3" tope="$4" calendario="$5" cuando="$6"
  cat > "/etc/systemd/system/$unidad.service" <<FIN
[Unit]
Description=$descripcion
Wants=network-online.target
After=network-online.target time-sync.target

[Service]
Type=oneshot
User=$USUARIO
Group=$USUARIO
WorkingDirectory=$CLON
ExecStart=/usr/bin/env bash $CLON/servidor/$script
SyslogIdentifier=$unidad
TimeoutStartSec=${tope}min
Nice=$SATELITE_NICE
IOSchedulingClass=idle
MemoryMax=$SATELITE_MEMORIA_MAXIMA
NoNewPrivileges=yes
PrivateTmp=yes
ProtectSystem=full
FIN
  cat > "/etc/systemd/system/$unidad.timer" <<FIN
[Unit]
Description=$descripcion, $cuando

[Timer]
OnCalendar=$calendario
AccuracySec=1s
Persistent=true

[Install]
WantedBy=timers.target
FIN
}
unidad_satelite "$UNIDAD_SATELITE" \
  "Imágenes de satélite de antes y después de las instalaciones alcanzadas (EODI)" \
  satelite.sh "$SATELITE_TOPE_UNIDAD" "*-*-* $HORAS_SATELITE:$MINUTO_SATELITE:00 UTC" \
  "a las $HORAS_SATELITE:$MINUTO_SATELITE"
unidad_satelite "$UNIDAD_LUCES" "Luz nocturna tras los ataques contra la red eléctrica (EODI)" \
  luces.sh "$LUCES_TOPE_UNIDAD" "*-*-* *:$MINUTO_LUCES:00 UTC" \
  "en el minuto $MINUTO_LUCES de cada hora"
unidad_satelite "$UNIDAD_FOCOS_VIVO" "Focos de calor de las últimas 24 horas (EODI)" \
  focos_vivo.sh "$FOCOS_VIVO_TOPE_UNIDAD" "*-*-* *:$MINUTO_FOCOS_VIVO:00 UTC" \
  "en el minuto $MINUTO_FOCOS_VIVO de cada hora"
systemctl daemon-reload

echo "instalación hecha"
