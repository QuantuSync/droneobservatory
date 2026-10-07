#!/usr/bin/env bash
# Prueba de restauración semanal (almacen/copias.py): baja la última copia cifrada de la base del
# almacén privado, comprueba su huella, la descifra en una carpeta aparte, comprueba su integridad y
# la borra; después baja la misma copia de la segunda copia de Helsinki y comprueba que es idéntica.
# Deja el resultado y lo que tardó en /home/eodi/.eodi/prueba_restauracion.json, que la vigilancia
# publica: si falla, o si pasan más de 8 días sin una correcta, avisa. La lanza
# eodi-prueba-restauracion.timer cada martes a las 10:45 UTC; también a mano:
#
#   sudo systemctl start eodi-prueba-restauracion.service
#   journalctl -u eodi-prueba-restauracion.service -n 20
#
# No toma el cerrojo de la recogida ni toca la base en uso.
set -euo pipefail

principal() {
  local aqui inicio codigo=0 salida objeto
  aqui="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  # shellcheck source=servidor/configuracion.sh
  . "$aqui/configuracion.sh"

  # shellcheck disable=SC1090
  . "$ALMACEN_CREDENCIALES"
  export ALMACEN_ID ALMACEN_SECRETO EODI_SECRETOS="$SECRETOS"
  EODI_CLAVE_AGE="$(cat "$CLAVE_AGE")"
  export EODI_CLAVE_AGE EODI_BASE_DIRECTORIO="$BASE_DIRECTORIO"
  cd "$CLON"
  local destino="$BASE_DIRECTORIO/trabajo/prueba-restauracion.sqlite"
  rm -f "$destino"
  inicio=$(date +%s)
  salida="$("$ENTORNO/bin/python" -m almacen.copias restaurar --destino "$destino" --huella)" \
    || codigo=$?
  rm -f "$destino"
  objeto="$(printf '%s' "$salida" | sed -n 's/.*"objeto": "\([^"]*\)".*/\1/p')"
  if [ "$codigo" -eq 0 ] && [ -n "$objeto" ]; then
    "$ENTORNO/bin/python" - "$objeto" <<'PY' || codigo=$?
import sys

from almacen import copias, replica

objeto = sys.argv[1]
credenciales = copias.Credenciales.cargar()
origen = copias.Copias(copias.cargar_destino(), credenciales)
segunda = copias.Copias(replica.destino_replica(replica.cargar()), credenciales)
clave = replica.PREFIJO_BASE + objeto.removeprefix(origen.destino.prefijo)
if segunda.bajar(clave) != origen.bajar(objeto):
    sys.exit(f"{clave}: la segunda copia no es idéntica")
print(f"segunda copia idéntica: {clave}")
PY
  fi
  local segundos=$(($(date +%s) - inicio))
  printf '{"fecha": "%s", "correcto": %s, "objeto": "%s", "segundos": %d}\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$([ "$codigo" -eq 0 ] && echo true || echo false)" \
    "$objeto" "$segundos" > "$SECRETOS/prueba_restauracion.json"
  echo "prueba de restauración: código $codigo, $segundos s, $objeto"
  return "$codigo"
}

principal "$@"
