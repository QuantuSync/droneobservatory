#!/usr/bin/env bash
# Simulacro de desastre: levanta un servidor nuevo desde cero, como si el de verdad hubiera
# desaparecido, y comprueba que se recupera todo, sin tocar nada del de verdad. Desde la máquina
# que guarda los secretos (en Windows, Git Bash), en la raíz del clon:
#
#     bash servidor/simulacro.sh            # todo: crear, instalar, restaurar, ensayar, borrar
#     SIMULACRO_CONSERVAR=1 bash servidor/simulacro.sh   # sin borrar el servidor al final
#
# 1. crea el servidor temporal SIMULACRO_NOMBRE (mismo tipo, misma clave SSH y mismo cortafuegos
#    que el de verdad; otra IP), con su propio fichero de claves de host;
# 2. lo endurece e instala con endurecer.sh e instalar.sh, como reconstruir.sh, pero sin dar de
#    alta claves de despliegue (las del servidor de verdad no se tocan), sin las variables del
#    extractor (no gasta) y sin activar ningún temporizador ni servicio: no captura el seguimiento
#    en paralelo con el de verdad ni publica nada;
# 3. le lleva la clave age y las credenciales del almacén, restaura la última copia cifrada de la
#    base y el archivo del seguimiento entero desde la copia privada, y comprueba sus huellas;
# 4. ejecuta una recogida completa en ensayo con main (servidor/ensayo.sh, con la exportación
#    semanal), que no sube nada;
# 5. borra el servidor y comprueba que no queda nada suyo facturando.
#
# Cada paso deja su duración en el informe (SIMULACRO_INFORME, por defecto simulacro.txt en la
# carpeta temporal).
set -euo pipefail

aqui="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=servidor/configuracion.sh
. "$aqui/configuracion.sh"

NOMBRE="${SIMULACRO_NOMBRE:-eodi-simulacro}"
[ "$NOMBRE" != "$SERVIDOR_NOMBRE" ] || { echo "el simulacro no usa el servidor de verdad" >&2; exit 1; }
TEMPORAL="$(mktemp -d)"
HOSTS="$TEMPORAL/known_hosts"
INFORME="${SIMULACRO_INFORME:-$TEMPORAL/simulacro.txt}"
HCLOUD_TOKEN="$(tr -d '\r\n' < "$LOCAL_TOKEN")"
export HCLOUD_TOKEN
inicio_total=$(date +%s)
marca=$inicio_total

paso() {
  local ahora
  ahora=$(date +%s)
  printf '%s\t%5d s\t%s\n' "$(date -u +%H:%M:%S)" "$((ahora - marca))" "$1" | tee -a "$INFORME"
  marca=$ahora
}

borrar() {
  local codigo=$?
  if [ "$codigo" -ne 0 ]; then
    echo "el simulacro se paró (código $codigo); últimas líneas de los registros:" | tee -a "$INFORME"
    tail -n 5 "$TEMPORAL"/*.log 2>/dev/null | tee -a "$INFORME"
  fi
  if [ "${SIMULACRO_CONSERVAR:-0}" != "1" ]; then
    hcloud server delete "$NOMBRE" >/dev/null 2>&1 || true
    paso "servidor $NOMBRE borrado"
  fi
}
trap borrar EXIT

# --- 1. Servidor ---------------------------------------------------------------------
hcloud server create --name "$NOMBRE" --type "$SERVIDOR_TIPO" --location "$SERVIDOR_LOCALIZACION" \
  --image "$SERVIDOR_IMAGEN" --ssh-key "$CLAVE_SSH_NOMBRE" --firewall "$CORTAFUEGOS_NOMBRE" \
  --label proposito=simulacro >/dev/null
ip="$(hcloud server ip "$NOMBRE")"
paso "servidor $NOMBRE creado en $ip"

conectar() {
  local usuario="$1"
  shift
  ssh -i "$LOCAL_CLAVE_SSH" -o IdentitiesOnly=yes -o BatchMode=yes -o ConnectTimeout=10 \
    -o StrictHostKeyChecking=accept-new -o UserKnownHostsFile="$HOSTS" "$usuario@$ip" "$@"
}
quien=""
for _ in $(seq "$ESPERA_SSH_INTENTOS"); do
  if conectar root true 2>/dev/null; then quien=root; break; fi
  sleep "$ESPERA_SSH_PAUSA_S"
done
[ -n "$quien" ] || { echo "el servidor no acepta conexiones SSH" >&2; exit 1; }
conectar root cloud-init status --wait >/dev/null || true
paso "SSH disponible"

# --- 2. Endurecimiento e instalación -------------------------------------------------
remoto="$(conectar root mktemp -d)"
tar -C "$aqui/.." -cf - servidor | conectar root tar -C "$remoto" -xf -
conectar root bash "$remoto/servidor/endurecer.sh" > "$TEMPORAL/endurecer.log" 2>&1
paso "endurecer.sh terminado"
conectar "$OPERADOR" sudo bash "$remoto/servidor/instalar.sh" > "$TEMPORAL/instalar.log" 2>&1
conectar "$OPERADOR" sudo rm -rf "$remoto"
paso "instalar.sh terminado"
activos="$(conectar "$OPERADOR" systemctl list-units 'eodi-*' --state=active --no-legend | wc -l)"
paso "unidades del observatorio activas tras instalar: $activos (tienen que ser 0)"

# --- 3. Secretos y restauración ------------------------------------------------------
dejar() {
  tr -d '\r' < "$1" | conectar "$OPERADOR" sudo tee "$2" > /dev/null
  conectar "$OPERADOR" sudo chown "$USUARIO:$USUARIO" "$2"
  conectar "$OPERADOR" sudo chmod 600 "$2"
}
dejar "$LOCAL_CLAVE_AGE" "$CLAVE_AGE"
dejar "$LOCAL_ALMACEN" "$ALMACEN_CREDENCIALES"
echo disco | conectar "$OPERADOR" sudo -u "$USUARIO" tee "$BASE_INTERRUPTOR" > /dev/null
paso "clave age, credenciales del almacén e interruptor de la base"
conectar "$OPERADOR" sudo -u "$USUARIO" bash "$CLON/servidor/base.sh" copias restaurar \
  --destino "$BASE_DIRECTORIO/eodi.sqlite" --huella | tee -a "$INFORME"
paso "base restaurada desde la última copia cifrada"
conectar "$OPERADOR" sudo -u "$USUARIO" bash "$CLON/servidor/seguimiento_archivo.sh" \
  restaurar-todo | tail -n 3 | tee -a "$INFORME"
paso "archivo del seguimiento restaurado"

# --- 4. Recogida completa en ensayo --------------------------------------------------
conectar "$OPERADOR" sudo systemd-run --unit=eodi-simulacro-ensayo --uid="$USUARIO" \
  --gid="$USUARIO" -p MemoryMax=3G --setenv=ENSAYO_EXPORTACION=1 --wait --collect \
  /usr/bin/env bash "$CLON/servidor/ensayo.sh" "$RAMA" > "$TEMPORAL/ensayo.log" 2>&1 || true
conectar "$OPERADOR" journalctl -u eodi-simulacro-ensayo --no-pager -o cat \
  | grep -E "ficheros publicados|exportación semanal|terminad" | tail -n 5 | tee -a "$INFORME"
paso "recogida completa en ensayo"

# --- 5. Fin ----------------------------------------------------------------------------
trap - EXIT
borrar
# El borrado tarda unos segundos en verse en el listado.
for _ in $(seq 12); do
  restos="$(hcloud server list -o noheader -l proposito=simulacro | wc -l)"
  [ "$restos" -eq 0 ] && break
  sleep 5
done
ips="$(hcloud primary-ip list -o noheader | grep -c "$NOMBRE" || true)"
paso "quedan $restos servidores y $ips IP del simulacro"
printf 'total: %d min\n' "$((($(date +%s) - inicio_total) / 60))" | tee -a "$INFORME"
echo "informe en $INFORME"
