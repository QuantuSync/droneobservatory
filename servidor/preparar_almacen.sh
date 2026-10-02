#!/usr/bin/env bash
# Deja el almacén público listo con una sola orden, desde la máquina que guarda los secretos
# (en Windows, desde Git Bash y en la raíz del clon, con main al día):
#
#     bash servidor/preparar_almacen.sh
#
# Necesita %USERPROFILE%\.eodi\almacen.env con las credenciales S3 del almacén
# (ALMACEN_ID=… y ALMACEN_SECRETO=…, una por línea; se generan en la consola de Hetzner,
# docs/servidor.md). El script:
#
# 1. deja las credenciales en el servidor (/home/eodi/.eodi/almacen.env, permisos 600):
#    desde ahí la recogida sube estado.json cada hora;
# 2. en el servidor, con un entorno aparte que tiene boto3, crea el bucket, lo deja de
#    lectura pública con CORS y le copia las teselas desde R2 sin pasar por el disco
#    (servidor/preparar_almacen.py --desde-r2);
# 3. si la copia desde R2 no es posible, la hace desde este equipo con la copia local
#    (EODI_TESELAS_LOCAL, por defecto C:\dev\eodi-teselas-copia\europa-z14.pmtiles);
# 4. publica ya el último estado.json, sin esperar a la recogida siguiente;
# 5. comprueba por la dirección pública el tamaño, las peticiones Range y el CORS.
#
# Puede repetirse: lo que ya está bien se deja como está (una copia con la misma huella no
# se vuelve a subir).
set -euo pipefail

aqui="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=servidor/configuracion.sh
. "$aqui/configuracion.sh"

TESELAS_LOCAL="${EODI_TESELAS_LOCAL:-/c/dev/eodi-teselas-copia/europa-z14.pmtiles}"
REMOTO="/var/tmp/eodi-almacen"
R2_CREDENCIALES="$SECRETOS/r2.env"

[ -s "$LOCAL_ALMACEN" ] || {
  echo "falta $LOCAL_ALMACEN con ALMACEN_ID=… y ALMACEN_SECRETO=… (docs/servidor.md)" >&2
  exit 1
}
grep -q '^ALMACEN_ID=.' "$LOCAL_ALMACEN" && grep -q '^ALMACEN_SECRETO=.' "$LOCAL_ALMACEN" || {
  echo "$LOCAL_ALMACEN tiene que llevar las líneas ALMACEN_ID=… y ALMACEN_SECRETO=…" >&2
  exit 1
}
HCLOUD_TOKEN="$(tr -d '\r\n' < "$LOCAL_TOKEN")"
export HCLOUD_TOKEN
ip="$(hcloud server ip "$SERVIDOR_NOMBRE")"

conectar() {
  ssh -i "$LOCAL_CLAVE_SSH" -o IdentitiesOnly=yes -o BatchMode=yes -o ConnectTimeout=10 \
    -o StrictHostKeyChecking=yes -o UserKnownHostsFile="$LOCAL_HOSTS_CONOCIDOS" \
    "$OPERADOR@$ip" "$@"
}

# --- 1. Credenciales en el servidor ----------------------------------------------------
tr -d '\r' < "$LOCAL_ALMACEN" | conectar sudo tee "$ALMACEN_CREDENCIALES" > /dev/null
conectar sudo chown "$USUARIO:$USUARIO" "$ALMACEN_CREDENCIALES"
conectar sudo chmod 600 "$ALMACEN_CREDENCIALES"
echo "credenciales del almacén en el servidor"

# --- 2. Bucket y teselas desde el servidor -------------------------------------------------
conectar sudo install -d -o "$USUARIO" -g "$USUARIO" -m 700 "$REMOTO"
trap 'conectar sudo rm -rf "$REMOTO" || true' EXIT
tar -C "$aqui/.." -cf - servidor/preparar_almacen.py servidor/requisitos_almacen.txt \
  configuracion/almacen_publico.json | conectar sudo -u "$USUARIO" tar -C "$REMOTO" -xf -
conectar sudo -u "$USUARIO" bash -c "'
  set -e
  [ -x $REMOTO/venv/bin/python ] || $ENTORNO/bin/python -m venv $REMOTO/venv
  $REMOTO/venv/bin/python -m pip install --quiet --disable-pip-version-check \
    -r $REMOTO/servidor/requisitos_almacen.txt
'"
copiado=0
if conectar sudo -u "$USUARIO" bash -c "'
  set -e
  [ -r $R2_CREDENCIALES ]
  set -a; . $R2_CREDENCIALES; . $ALMACEN_CREDENCIALES; set +a
  cd $REMOTO && venv/bin/python servidor/preparar_almacen.py --desde-r2
'"; then
  copiado=1
fi

# --- 3. Si no, desde este equipo -------------------------------------------------------
if [ "$copiado" -eq 0 ]; then
  echo "la copia desde R2 no fue posible: se sube la copia local $TESELAS_LOCAL"
  [ -s "$TESELAS_LOCAL" ] || { echo "no está $TESELAS_LOCAL" >&2; exit 1; }
  local_venv="${TMPDIR:-/tmp}/eodi-almacen-venv"
  python_local="$(command -v py >/dev/null && echo "py -3" || echo python3)"
  [ -d "$local_venv" ] || $python_local -m venv "$local_venv"
  bin="$local_venv/bin"
  [ -d "$bin" ] || bin="$local_venv/Scripts"
  "$bin/python" -m pip install --quiet --disable-pip-version-check \
    -r "$aqui/requisitos_almacen.txt"
  (
    set -a
    # shellcheck disable=SC1090
    . <(tr -d '\r' < "$LOCAL_ALMACEN")
    set +a
    "$bin/python" "$aqui/preparar_almacen.py" --fichero "$TESELAS_LOCAL"
  )
fi

# --- 4. El último estado publicado, ya ---------------------------------------------------
conectar sudo -u "$USUARIO" bash -c "'
  set -e
  [ -r $ESTADO_ANTERIOR ] || exit 0
  set -a; . $ALMACEN_CREDENCIALES; set +a
  cd $CLON && $ENTORNO/bin/python -m recogida.almacen_publico subir \
    --fichero $ESTADO_ANTERIOR --objeto $ESTADO_OBJETO --tipo application/json \
    --cache \"$ESTADO_CACHE\"
'" || echo "aviso: estado.json se publicará en la recogida siguiente"

# --- 5. Comprobación por la dirección pública --------------------------------------------
conectar sudo -u "$USUARIO" bash -c "'cd $REMOTO && venv/bin/python servidor/preparar_almacen.py --solo-comprobar'"
echo "almacén público listo"
