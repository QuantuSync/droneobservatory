#!/usr/bin/env bash
# Recogida horaria en el servidor. Hace lo mismo que el workflow recogida.yml:
#
# 1. deja el clon en la última versión de main;
# 2. ejecuta recogida.horaria, que descarga la base, recoge lo nuevo y la vuelve a subir;
# 3. publica los ficheros de la web, también cuando la recogida termina con avisos (código 2) y
#    nunca cuando falla con otro código: según el interruptor de la publicación
#    (configuracion.sh, modo_publicacion), en main si han cambiado (github), en el almacén
#    público (almacen, y la web se reconstruye con el gancho de Vercel) o en los dos (doble,
#    comprobando después que el almacén es idéntico byte a byte a lo publicado en main);
# 4. al salir, siempre, sube estado.json al almacén público (recogida/estado.py y
#    recogida/almacen_publico.py): la web lo lee sin que haya commit ni reconstrucción. Si
#    eso falla, queda como aviso y la recogida no cambia de resultado.
#
# Sale con el código de la recogida: con avisos la unidad de systemd queda como fallida,
# igual que el workflow queda en rojo. Al diario solo van recuentos.
set -euo pipefail

# Estado del sistema para la web: se compone con lo que dejó la recogida y se sube al
# almacén público (configuracion/almacen_publico.json) con recogida.almacen_publico, que
# reintenta con espera creciente. Nada de esto cambia el código de salida de la recogida.
publicar_estado() {
  local codigo="$1" nuevo
  set +e
  if [ ! -r "$ALMACEN_CREDENCIALES" ]; then
    echo "aviso: sin credenciales del almacén público, estado.json no se publica"
    return 0
  fi
  nuevo="$(mktemp)"
  if ! "$ESTADO_PYTHON" -m recogida.estado --inicio "$ESTADO_INICIO" --codigo "$codigo"     --parcial "$ESTADO_PARCIAL" --anterior "$ESTADO_ANTERIOR" --salida "$nuevo"     --minuto "$MINUTO_RECOGIDA" --exportacion "$EXPORTACION_REGISTRO"     --deduccion "$DEDUCCION_REGISTRO" --directo "$DIRECTO_REGISTRO" --seguimiento "$SEGUIMIENTO_REGISTRO"; then
    echo "aviso: no se pudo componer estado.json"
    rm -f "$nuevo" "$ESTADO_PARCIAL"
    return 0
  fi
  # Las credenciales van en el entorno de la subida, no en la línea de órdenes.
  if (
    # shellcheck disable=SC1090
    . "$ALMACEN_CREDENCIALES"
    export ALMACEN_ID ALMACEN_SECRETO
    "$ESTADO_PYTHON" -m recogida.almacen_publico subir --fichero "$nuevo"       --objeto "$ESTADO_OBJETO" --tipo application/json --cache "$ESTADO_CACHE"
  ); then
    cp "$nuevo" "$ESTADO_ANTERIOR"
    echo "estado.json publicado en el almacén"
  else
    echo "aviso: no se pudo subir estado.json al almacén"
  fi
  rm -f "$nuevo" "$ESTADO_PARCIAL"
  return 0
}

# Sube los ficheros publicados al almacén público (recogida/publicacion.py) y, en el modo
# almacen, pide a Vercel que reconstruya la web. Con las credenciales en el entorno.
publicar_en_almacen() {
  local modo="$1" gancho=()
  [ -r "$ALMACEN_CREDENCIALES" ] || return 1
  if [ "$modo" = almacen ]; then
    gancho=(--gancho "$VERCEL_GANCHO")
  fi
  (
    # shellcheck disable=SC1090
    . "$ALMACEN_CREDENCIALES"
    export ALMACEN_ID ALMACEN_SECRETO
    "$ESTADO_PYTHON" -m recogida.publicacion subir --carpeta "$PUBLICACION_DATOS" \
      --registro "$PUBLICACION_REGISTRO" "${gancho[@]}"
  )
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

  install -d -m 700 "$PUBLICACION_DATOS"
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

  local modo_pub fichero
  modo_pub="$(modo_publicacion)"
  echo "publicación en modo $modo_pub"
  if [ "$modo_pub" != github ]; then
    # Antes que el commit: la reconstrucción que este lanza ya encuentra el almacén al día.
    if publicar_en_almacen "$modo_pub"; then
      echo "ficheros publicados en el almacén"
      # La copia de reserva de Helsinki, ya (también la lleva su temporizador cada 2 minutos), con
      # tope: un PUT colgado de Helsinki no retrasa la recogida (lo termina la pasada siguiente).
      if timeout 90 bash "$aqui/reserva.sh"; then
        echo "copia de reserva al día"
      else
        echo "aviso: la copia de reserva no quedó al día (la reintenta su temporizador)"
      fi
      # Avisos públicos de ntfy (recogida/avisos.py, docs/avisos.md): solo tras publicar bien,
      # para que el enlace del aviso funcione. Un fallo no cambia el código de la recogida: lo
      # que no salió se reintenta en la siguiente, sin repetir lo enviado.
      if timeout "$TOPE_AVISOS_SEGUNDOS" "$python" -m recogida.avisos enviar \
        --publicacion "$PUBLICACION_DATOS" --base "$BASE_DIRECTORIO/eodi.sqlite" \
        --datos "$AVISOS_DATOS" --estado "$SECRETOS/avisos.json" --token "$NTFY_TOKEN"; then
        echo "avisos de ntfy al día"
      else
        echo "aviso: no se enviaron todos los avisos de ntfy (se reintentan en la siguiente recogida)"
      fi
      # IndexNow (recogida/indexnow.py, docs/posicionamiento.md): las páginas de incidentes nuevas
      # o cambiadas que ya están en la web, para Bing y los buscadores que lo usan. Un fallo no
      # cambia el código de la recogida: lo que no salió se envía en la siguiente.
      if timeout "$TOPE_INDEXNOW_SEGUNDOS" "$python" -m recogida.indexnow enviar \
        --datos "$INDEXNOW_DATOS"; then
        echo "indexnow al día"
      else
        echo "aviso: IndexNow sin enviar del todo (se reintenta en la siguiente recogida)"
      fi
    else
      echo "aviso: los ficheros no se publicaron en el almacén"
      if [ "$modo_pub" = almacen ] && [ "$codigo" -eq 0 ]; then
        codigo=1
      fi
    fi
  fi
  if [ "$modo_pub" != almacen ]; then
    for fichero in "${PUBLICADOS[@]}"; do
      if [ -f "$PUBLICACION_DATOS/$(basename "$fichero")" ]; then
        cp "$PUBLICACION_DATOS/$(basename "$fichero")" "$fichero"
      fi
    done
    git add "${PUBLICADOS[@]}"
    if git diff --cached --quiet; then
      echo "ficheros publicados sin cambios"
    else
      git -c user.name="$AUTOR" -c user.email="$CORREO" commit --quiet -m "$MENSAJE_PUBLICACION"
      GIT_SSH_COMMAND="$ssh_base -i $DESPLIEGUE_WEB" git push --quiet origin "HEAD:$RAMA"
      echo "ficheros publicados en $RAMA"
    fi
    if [ "$modo_pub" = doble ]; then
      if "$python" -m recogida.publicacion comparar --carpeta "$CLON/publicacion"; then
        echo "publicación doble: el almacén es idéntico a $RAMA"
      else
        echo "aviso: publicación doble: el almacén no es idéntico a $RAMA"
      fi
    fi
  fi
  if [ "$codigo" -eq "$SALIDA_AVISO" ]; then
    echo "la recogida terminó con avisos (código $SALIDA_AVISO): están más arriba en el diario"
  fi
  return "$codigo"
}

principal "$@"
