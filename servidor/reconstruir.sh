#!/usr/bin/env bash
# Reconstruye el servidor de recogida desde cero con una sola orden, desde la máquina
# que guarda los secretos (en Windows, desde Git Bash):
#
#     bash servidor/reconstruir.sh
#
# Necesita hcloud, gh (con sesión de la cuenta del proyecto), ssh y los ficheros de
# secretos que se listan en docs/servidor.md. Puede repetirse: lo que ya existe se deja
# como está, salvo las claves de despliegue, que se sustituyen por las del servidor.
set -euo pipefail

aqui="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=servidor/configuracion.sh
. "$aqui/configuracion.sh"

for orden in hcloud gh ssh ssh-keygen tar; do
  command -v "$orden" >/dev/null || { echo "falta la orden $orden" >&2; exit 1; }
done
for fichero in "$LOCAL_TOKEN" "$LOCAL_CLAVE_AGE" "$LOCAL_EXTRACTOR"; do
  [ -s "$fichero" ] || { echo "falta el fichero $fichero" >&2; exit 1; }
done
HCLOUD_TOKEN="$(tr -d '\r\n' < "$LOCAL_TOKEN")"
export HCLOUD_TOKEN

# --- Clave SSH, cortafuegos y servidor -----------------------------------------------
if [ ! -f "$LOCAL_CLAVE_SSH" ]; then
  ssh-keygen -q -t ed25519 -N "" -C "$CLAVE_SSH_NOMBRE" -f "$LOCAL_CLAVE_SSH"
fi
if ! hcloud ssh-key describe "$CLAVE_SSH_NOMBRE" >/dev/null 2>&1; then
  hcloud ssh-key create --name "$CLAVE_SSH_NOMBRE" --public-key-from-file "$LOCAL_CLAVE_SSH.pub"
fi
# Solo SSH entrante. Lo que no tiene regla, incluido el ping, queda cerrado.
if ! hcloud firewall describe "$CORTAFUEGOS_NOMBRE" >/dev/null 2>&1; then
  hcloud firewall create --name "$CORTAFUEGOS_NOMBRE"
  hcloud firewall add-rule "$CORTAFUEGOS_NOMBRE" --direction in --protocol tcp \
    --port "$PUERTO_SSH" --source-ips 0.0.0.0/0 --source-ips ::/0 \
    --description "SSH"
fi
if ! hcloud server describe "$SERVIDOR_NOMBRE" >/dev/null 2>&1; then
  hcloud server create --name "$SERVIDOR_NOMBRE" --type "$SERVIDOR_TIPO" \
    --location "$SERVIDOR_LOCALIZACION" --image "$SERVIDOR_IMAGEN" \
    --ssh-key "$CLAVE_SSH_NOMBRE" --firewall "$CORTAFUEGOS_NOMBRE"
  # Servidor nuevo, clave de host nueva: la anterior ya no vale.
  rm -f "$LOCAL_HOSTS_CONOCIDOS"
fi
ip="$(hcloud server ip "$SERVIDOR_NOMBRE")"
echo "servidor $SERVIDOR_NOMBRE en $ip"

# --- Conexión ------------------------------------------------------------------------
# La clave de host se anota en la primera conexión, en un fichero solo para este servidor.
conectar() {
  local usuario="$1"
  shift
  ssh -i "$LOCAL_CLAVE_SSH" -o IdentitiesOnly=yes -o BatchMode=yes -o ConnectTimeout=10 \
    -o StrictHostKeyChecking=accept-new -o UserKnownHostsFile="$LOCAL_HOSTS_CONOCIDOS" \
    "$usuario@$ip" "$@"
}

# Un servidor recién creado solo admite a root; uno ya endurecido, solo al operador.
quien=""
for _ in $(seq "$ESPERA_SSH_INTENTOS"); do
  if conectar "$OPERADOR" true 2>/dev/null; then
    quien="$OPERADOR"
    break
  fi
  if conectar root true 2>/dev/null; then
    quien="root"
    break
  fi
  sleep "$ESPERA_SSH_PAUSA_S"
done
[ -n "$quien" ] || { echo "el servidor no acepta conexiones SSH" >&2; exit 1; }
como_root() { if [ "$quien" = root ]; then conectar root "$@"; else conectar "$OPERADOR" sudo "$@"; fi; }

# --- Endurecimiento e instalación ----------------------------------------------------
# Un servidor recién creado aún está terminando su primer arranque.
como_root cloud-init status --wait >/dev/null || true
remoto="$(conectar "$quien" mktemp -d)"
tar -C "$aqui/.." -cf - servidor | conectar "$quien" tar -C "$remoto" -xf -
como_root bash "$remoto/servidor/endurecer.sh"
# Desde aquí root ya no entra: lo demás lo hace el operador.
quien="$OPERADOR"
como_root bash "$remoto/servidor/instalar.sh"
como_root rm -rf "$remoto"

# --- Secretos ------------------------------------------------------------------------
# Viajan por la conexión SSH y quedan con permisos 600 y propiedad del usuario del
# observatorio. Los saltos de línea de Windows se quitan por el camino.
dejar_secreto() {
  # La carpeta de destino solo la puede leer su dueño: el fichero no queda a la vista
  # mientras se le ponen los permisos.
  tr -d '\r' < "$1" | conectar "$OPERADOR" sudo tee "$2" > /dev/null
  conectar "$OPERADOR" sudo chown "$USUARIO:$USUARIO" "$2"
  conectar "$OPERADOR" sudo chmod 600 "$2"
}
dejar_secreto "$LOCAL_CLAVE_AGE" "$CLAVE_AGE"
# Las variables del extractor y, en el mismo fichero, la clave de FIRMS si está en local.
variables="$(mktemp)"
trap 'rm -f "$variables"' EXIT
(
  umask 077
  grep -v "^$VARIABLE_FIRMS=" "$LOCAL_EXTRACTOR" > "$variables" || true
  if [ -s "$LOCAL_FIRMS" ]; then
    printf '%s=%s\n' "$VARIABLE_FIRMS" "$(tr -d ' \r\n' < "$LOCAL_FIRMS")" >> "$variables"
  else
    echo "aviso: sin $LOCAL_FIRMS, la recogida no descargará FIRMS" >&2
  fi
)
dejar_secreto "$variables" "$EXTRACTOR"
rm -f "$variables"

# Credenciales S3 del almacén público para subir estado.json (ALMACEN_ID y ALMACEN_SECRETO,
# una por línea). Se generan en la consola de Hetzner (docs/servidor.md). Sin ellas, la
# recogida avisa y no publica el estado.
if [ -s "$LOCAL_ALMACEN" ]; then
  dejar_secreto "$LOCAL_ALMACEN" "$ALMACEN_CREDENCIALES"
else
  echo "aviso: sin $LOCAL_ALMACEN, la recogida no publicará estado.json" >&2
fi

# --- Claves de despliegue ------------------------------------------------------------
# Las privadas se generan en el servidor y no salen de él; aquí solo llega la pública.
# Cada una da escritura en un único repositorio.
clave_despliegue() {
  local repositorio="$1" fichero="$2" id
  for id in $(gh repo deploy-key list --repo "$repositorio" --json id,title \
    --jq ".[] | select(.title == \"$TITULO_DESPLIEGUE\") | .id"); do
    gh repo deploy-key delete "$id" --repo "$repositorio"
  done
  conectar "$OPERADOR" sudo cat "$fichero.pub" \
    | gh repo deploy-key add - --repo "$repositorio" --title "$TITULO_DESPLIEGUE" --allow-write
}
clave_despliegue "$REPOSITORIO_DATOS" "$DESPLIEGUE_DATOS"
clave_despliegue "$REPOSITORIO" "$DESPLIEGUE_WEB"

# --- Temporizador --------------------------------------------------------------------
conectar "$OPERADOR" sudo systemctl enable --now "$UNIDAD.timer" "$UNIDAD_EXPORTACION.timer" \
  "$UNIDAD_DETALLE.timer" "$UNIDAD_GUERRA.timer" "$UNIDAD_TRAFICO.timer" "$UNIDAD_BUSQUEDA.timer" \
  "$UNIDAD_DEDUCCION.timer" "$UNIDAD_CATALOGO.timer" "$UNIDAD_DIRECTO.service" \
  "$UNIDAD_SATELITE.timer" "$UNIDAD_LUCES.timer" "$UNIDAD_FOCOS_VIVO.timer"   "$UNIDAD_SEGUIMIENTO.service" "$UNIDAD_SEGUIMIENTO_ARCHIVO.timer"   "$UNIDAD_RUTAS.timer"
conectar "$OPERADOR" systemctl list-timers "$UNIDAD.timer" "$UNIDAD_EXPORTACION.timer" \
  "$UNIDAD_DETALLE.timer" "$UNIDAD_GUERRA.timer" "$UNIDAD_TRAFICO.timer" \
  "$UNIDAD_BUSQUEDA.timer" "$UNIDAD_DEDUCCION.timer" "$UNIDAD_CATALOGO.timer" \
  "$UNIDAD_SATELITE.timer" "$UNIDAD_LUCES.timer" "$UNIDAD_FOCOS_VIVO.timer"   "$UNIDAD_SEGUIMIENTO_ARCHIVO.timer" "$UNIDAD_RUTAS.timer" --no-pager
echo "servidor reconstruido: $ip"
