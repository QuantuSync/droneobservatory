#!/usr/bin/env bash
# Prueba de restauración semanal (almacen/copias.py): baja la última copia cifrada de la base que ya
# está también en la segunda copia de Helsinki, comprueba su huella, la descifra en una carpeta
# aparte, comprueba su integridad y la borra; después baja esa misma copia de Helsinki y comprueba
# que es idéntica.
# Deja el resultado y lo que tardó en /home/eodi/.eodi/prueba_restauracion.json, que la vigilancia
# publica: si falla, o si pasan más de 8 días sin una correcta, avisa. La lanza
# eodi-prueba-restauracion.timer cada martes a las 10:55 UTC; también a mano:
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
  # La última copia horaria que ya tiene Helsinki (la réplica pasa en el minuto 47).
  objeto="$("$ENTORNO/bin/python" - <<'PY' || true
from almacen import copias, replica

credenciales = copias.Credenciales.cargar()
origen = copias.Copias(copias.cargar_destino(), credenciales)
segunda = copias.Copias(replica.destino_replica(replica.cargar()), credenciales)
en_segunda = {o.clave for o in segunda.listar(replica.PREFIJO_BASE)}
horarias = [c for c in origen.copias() if c[0] == copias.HORARIA]
for _, _, objeto in reversed(horarias):
    if replica.PREFIJO_BASE + objeto.clave.removeprefix(origen.destino.prefijo) in en_segunda:
        print(objeto.clave)
        break
PY
)"
  if [ -z "$objeto" ]; then
    echo "no hay ninguna copia horaria que esté en los dos sitios"
    codigo=1
  else
    "$ENTORNO/bin/python" -m almacen.copias restaurar --destino "$destino" --objeto "$objeto" \
      --huella || codigo=$?
  fi
  rm -f "$destino"
  if [ "$codigo" -eq 0 ]; then
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
