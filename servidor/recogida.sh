#!/usr/bin/env bash
# Recogida horaria en el servidor. Hace lo mismo que el workflow recogida.yml:
#
# 1. deja el clon en la última versión de main;
# 2. ejecuta recogida.horaria, que descarga la base, recoge lo nuevo y la vuelve a subir;
# 3. publica en main los ficheros de la web si han cambiado, también cuando la recogida
#    termina con avisos (código 2) y nunca cuando falla con otro código;
# 4. al salir, siempre, sube estado.json al bucket de teselas (recogida/estado.py): la web
#    lo lee sin que haya commit ni reconstrucción. Si eso falla, queda como aviso y la
#    recogida no cambia de resultado.
#
# Sale con el código de la recogida: con avisos la unidad de systemd queda como fallida,
# igual que el workflow queda en rojo. Al diario solo van recuentos.
set -euo pipefail

# Estado del sistema para la web: se compone con lo que dejó la recogida y se sube a R2
# con curl, firmado con las credenciales S3 del bucket. Nada de esto cambia el código de
# salida de la recogida.
publicar_estado() {
  local codigo="$1" nuevo
  set +e
  if [ ! -r "$R2_CREDENCIALES" ]; then
    echo "aviso: sin credenciales de R2, estado.json no se publica"
    return 0
  fi
  nuevo="$(mktemp)"
  if ! "$ESTADO_PYTHON" -m recogida.estado --inicio "$ESTADO_INICIO" --codigo "$codigo" \
    --parcial "$ESTADO_PARCIAL" --anterior "$ESTADO_ANTERIOR" --salida "$nuevo" \
    --minuto "$MINUTO_RECOGIDA" --exportacion "$EXPORTACION_REGISTRO" \
    --deduccion "$DEDUCCION_REGISTRO"; then
    echo "aviso: no se pudo componer estado.json"
    rm -f "$nuevo" "$ESTADO_PARCIAL"
    return 0
  fi
  # Las credenciales van a curl por su entrada, no en la línea de órdenes.
  if (
    # shellcheck disable=SC1090
    . "$R2_CREDENCIALES"
    printf 'user = "%s:%s"\n' "$R2_ID" "$R2_SECRETO" | curl --config - --fail --silent \
      --show-error --max-time "$ESTADO_TOPE_S" --aws-sigv4 "aws:amz:auto:s3" -X PUT \
      -H "Content-Type: application/json" -H "Cache-Control: $ESTADO_CACHE" \
      --data-binary "@$nuevo" "https://$R2_CUENTA.r2.cloudflarestorage.com/$R2_BUCKET/$ESTADO_OBJETO"
  ); then
    cp "$nuevo" "$ESTADO_ANTERIOR"
    echo "estado.json publicado en el bucket"
  else
    echo "aviso: no se pudo subir estado.json al bucket"
  fi
  rm -f "$nuevo" "$ESTADO_PARCIAL"
  return 0
}

# Todo dentro de una función: el script se lee entero antes de empezar, y actualizar el
# clon a mitad de ejecución no cambia lo que se está ejecutando.
principal() {
  local aqui codigo=0
  aqui="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  # shellcheck source=servidor/configuracion.sh
  . "$aqui/configuracion.sh"

  # Una sola ejecución a la vez: dos a la par se pisarían la rama estado.
  exec 9> "$CERROJO"
  if ! flock --nonblock 9; then
    echo "hay otra recogida en marcha: esta no se lanza"
    return 0
  fi

  local ssh_base="ssh -o IdentitiesOnly=yes -o StrictHostKeyChecking=yes -o UserKnownHostsFile=$HOSTS_CONOCIDOS"
  local python="$ENTORNO/bin/python"
  local instalados="$ENTORNO/requisitos.sha256"

  # Desde aquí la recogida cuenta: al salir, con el código que sea, se publica su estado.
  ESTADO_INICIO="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  ESTADO_PARCIAL="$(mktemp)"
  ESTADO_PYTHON="$python"
  trap 'publicar_estado "$?"' EXIT

  cd "$CLON"
  git fetch --quiet origin "$RAMA"
  git reset --quiet --hard "origin/$RAMA"
  # Las dependencias solo se reinstalan cuando cambia requirements.txt.
  if ! sha256sum --check --status "$instalados" 2>/dev/null; then
    "$python" -m pip install --quiet --disable-pip-version-check -r requirements.txt
    sha256sum requirements.txt > "$instalados"
  fi

  # La identidad age completa va en una variable; las del extractor, una por línea.
  EODI_CLAVE_AGE="$(cat "$CLAVE_AGE")"
  export EODI_CLAVE_AGE
  local linea
  while IFS= read -r linea || [ -n "$linea" ]; do
    case "$linea" in
      "" | "#"*) continue ;;
    esac
    export "${linea?}"
  done < "$EXTRACTOR"
  # Los CSV de FIRMS, en el disco del servidor (recogida/firms.py).
  export EODI_FIRMS_DATOS="$FIRMS_DATOS"
  # Lo que dejan las fuentes oficiales de detalle (recogida/detalle.py), para incorporarlo.
  export EODI_DETALLE_DATOS="$DETALLE_DATOS"
  # Lo que dejó el lector de canales de la capa de guerra (servidor/guerra.sh).
  export EODI_GUERRA_DATOS="$GUERRA_DATOS"
  # Lo que deja el procesado de adsb.lol y la caché de Open-Meteo y del IEM
  # (recogida/mediciones.py).
  export EODI_TRAFICO_DATOS="$TRAFICO_DATOS" EODI_METEO_DATOS="$METEO_DATOS"

  GIT_SSH_COMMAND="$ssh_base -i $DESPLIEGUE_DATOS" \
    "$python" -m recogida.horaria --correo "$CORREO" --repositorio "$URL_DATOS" \
    --estado "$ESTADO_PARCIAL" || codigo=$?
  # Un aviso no frena la publicación. Con cualquier otro código de error no se publica.
  if [ "$codigo" -ne 0 ] && [ "$codigo" -ne "$SALIDA_AVISO" ]; then
    echo "la recogida falló con código $codigo: no se publica"
    return "$codigo"
  fi

  git add "${PUBLICADOS[@]}"
  if git diff --cached --quiet; then
    echo "ficheros publicados sin cambios"
  else
    git -c user.name="$AUTOR" -c user.email="$CORREO" commit --quiet -m "$MENSAJE_PUBLICACION"
    GIT_SSH_COMMAND="$ssh_base -i $DESPLIEGUE_WEB" git push --quiet origin "HEAD:$RAMA"
    echo "ficheros publicados en $RAMA"
  fi
  if [ "$codigo" -eq "$SALIDA_AVISO" ]; then
    echo "la recogida terminó con avisos (código $SALIDA_AVISO): están más arriba en el diario"
  fi
  return "$codigo"
}

principal "$@"
