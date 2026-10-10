#!/usr/bin/env bash
# Ensayo de la recogida (paso c2 de docs/fusiones.md) con el código de una rama, sobre copias
# propias de la base y de los datos: no toca la base, los datos, el clon ni el cerrojo de la
# recogida, y no sube nada. La recogida en ensayo publica en <raíz>/salida y genera también la
# exportación semanal sin subir (<raíz>/salida/exportacion); sin las variables del extractor no
# gasta. Es un trabajo de sesión (docs/servidor.md, «Trabajos de las sesiones en el servidor»):
#
#   sudo systemd-run --unit=eodi-ensayo --uid=eodi --gid=eodi -p MemoryMax=3G -p Nice=19 \
#     -p IOSchedulingClass=idle -p OOMScoreAdjust=1000 \
#     /usr/bin/env bash /home/eodi/droneobservatory/servidor/ensayo.sh <rama>
#   journalctl -u eodi-ensayo -n 40          # al final, «ensayo terminado con código N»
#
# Con ENSAYO_EXPORTACION=1 ejecuta además la exportación semanal completa como la del lunes, sobre
# la misma copia de la base y sin subir nada (<raíz>/salida/exportacion-semanal). Al terminar borra la copia de la base y
# de los datos y deja solo <raíz>/salida y el diario.
set -euo pipefail

principal() {
  local aqui rama raiz codigo=0
  aqui="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  # shellcheck source=servidor/configuracion.sh
  . "$aqui/configuracion.sh"
  rama="${1:?falta la rama}"
  raiz="${2:-$CASA/ensayo}"

  rm -rf "$raiz"
  install -d -m 700 "$raiz" "$raiz/base" "$raiz/datos" "$raiz/salida"
  git clone --quiet --depth 1 --branch "$rama" "$URL_LECTURA" "$raiz/codigo"
  echo "ensayo de $rama ($(git -C "$raiz/codigo" rev-parse --short HEAD))"

  # La base, con la API de copia de SQLite: una copia coherente aunque la recogida la sustituya.
  "$ENTORNO/bin/python" - "$BASE_DIRECTORIO/eodi.sqlite" "$raiz/base/eodi.sqlite" <<'PY'
import sqlite3
import sys

origen = sqlite3.connect(f"file:{sys.argv[1]}?mode=ro", uri=True)
destino = sqlite3.connect(sys.argv[2])
origen.backup(destino)
destino.close()
origen.close()
PY

  # Los datos pequeños se copian; los grandes que la recogida solo lee, con enlaces a sus
  # carpetas (los ficheros sueltos de su raíz, que sí escribe, se copian).
  local d f
  for d in busqueda catalogo detalle directo firms focos_vivo guerra luces meteo reintentos \
    satelite rutas; do
    if [ -d "$CASA/datos/$d" ]; then cp -a "$CASA/datos/$d" "$raiz/datos/$d"; fi
  done
  for d in trafico deduccion seguimiento; do
    install -d -m 700 "$raiz/datos/$d"
    for f in "$CASA/datos/$d"/*; do
      [ -e "$f" ] || continue
      if [ -d "$f" ]; then ln -s "$f" "$raiz/datos/$d/$(basename "$f")"
      else cp -a "$f" "$raiz/datos/$d/"; fi
    done
  done

  EODI_CLAVE_AGE="$(cat "$CLAVE_AGE")"
  export EODI_CLAVE_AGE EODI_BASE_MODO=disco EODI_BASE_DIRECTORIO="$raiz/base"
  for d in busqueda catalogo deduccion detalle directo firms focos_vivo guerra luces meteo \
    reintentos rutas satelite seguimiento trafico; do
    export "EODI_${d^^}_DATOS=$raiz/datos/$d"
  done
  cd "$raiz/codigo"
  PYTHONPATH="$raiz/codigo" "$ENTORNO/bin/python" -m recogida.horaria --correo "$CORREO" \
    --ensayo "$raiz/salida" || codigo=$?
  echo "recogida de ensayo terminada con código $codigo"
  # Avisos de ntfy en ensayo, sobre una copia de lo ya avisado: dice cuántos se enviarían, sin
  # enviar ni anotar nada (sin incidentes nuevos, 0).
  if [ "$codigo" -eq 0 ] || [ "$codigo" -eq 2 ]; then
    install -d -m 700 "$raiz/datos/avisos"
    if [ -f "$AVISOS_DATOS/avisos.sqlite" ]; then
      cp -a "$AVISOS_DATOS/avisos.sqlite" "$raiz/datos/avisos/"
    fi
    local cavi=0
    PYTHONPATH="$raiz/codigo" "$ENTORNO/bin/python" -m recogida.avisos ensayo \
      --publicacion "$raiz/salida" --base "$raiz/base/eodi.sqlite" \
      --datos "$raiz/datos/avisos" || cavi=$?
    echo "avisos de ensayo terminados con código $cavi"
    [ "$cavi" -eq 0 ] || codigo=1
    # IndexNow en ensayo, sobre una copia de lo ya enviado: dice cuántas direcciones enviaría.
    install -d -m 700 "$raiz/datos/indexnow"
    if [ -f "$INDEXNOW_DATOS/indexnow.json" ]; then
      cp -a "$INDEXNOW_DATOS/indexnow.json" "$raiz/datos/indexnow/"
    fi
    local cidx=0
    PYTHONPATH="$raiz/codigo" "$ENTORNO/bin/python" -m recogida.indexnow ensayo \
      --datos "$raiz/datos/indexnow" || cidx=$?
    echo "indexnow de ensayo terminado con código $cidx"
    [ "$cidx" -eq 0 ] || codigo=1
  fi
  if [ "${ENSAYO_EXPORTACION:-0}" = "1" ] && { [ "$codigo" -eq 0 ] || [ "$codigo" -eq 2 ]; }; then
    local cexp=0
    PYTHONPATH="$raiz/codigo" "$ENTORNO/bin/python" -m recogida.exportacion --sin-subir \
      --salida "$raiz/salida/exportacion-semanal" || cexp=$?
    echo "exportación semanal de ensayo terminada con código $cexp"
    [ "$cexp" -eq 0 ] || codigo=1
  fi
  rm -rf "$raiz/base" "$raiz/datos" "$raiz/codigo"
  echo "ensayo terminado con código $codigo"
  return "$codigo"
}

principal "$@"
