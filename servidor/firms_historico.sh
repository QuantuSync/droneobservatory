#!/usr/bin/env bash
# Reconstrucción del histórico de NASA FIRMS (recogida/firms.py), una sola vez, en segundo
# plano y sin solaparse con la recogida horaria. Se lanza como eodi, normalmente con
# systemd-run para que siga al cerrar la sesión (docs/servidor.md):
#
#   sudo systemd-run --unit=eodi-firms-historico --uid=eodi --gid=eodi \
#     /usr/bin/env bash /home/eodi/droneobservatory/servidor/firms_historico.sh
#
# Trabaja por tandas con el cerrojo de la recogida: cada tanda espera a que termine la
# recogida en marcha, si la hay, y acaba antes del minuto FIRMS_FIN_TANDA de la hora, unos
# minutos antes del lanzamiento horario, que encuentra el cerrojo libre. Entre ese minuto y
# el de la recogida no empieza ninguna. Es reanudable: lo ya descargado no se vuelve a pedir,
# así que si se corta basta con volver a lanzarlo. Al diario solo van recuentos.
set -euo pipefail

principal() {
  local aqui codigo fallos=0 minuto tope
  aqui="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  # shellcheck source=servidor/configuracion.sh
  . "$aqui/configuracion.sh"

  # La clave de FIRMS está con las variables del extractor; solo se toma esa línea.
  local linea
  while IFS= read -r linea || [ -n "$linea" ]; do
    case "$linea" in
      "$VARIABLE_FIRMS="*) export "${linea?}" ;;
    esac
  done < "$EXTRACTOR"
  export EODI_FIRMS_DATOS="$FIRMS_DATOS"
  install -d -m 700 "$FIRMS_DATOS"

  while :; do
    minuto="$((10#$(date -u +%M)))"
    if [ "$minuto" -ge "$FIRMS_FIN_TANDA" ] && [ "$minuto" -le "$MINUTO_RECOGIDA" ]; then
      # Turno de la recogida horaria: se espera a que la lance el temporizador.
      sleep "$(((MINUTO_RECOGIDA + 1 - minuto) * 60))"
      continue
    fi
    exec 9> "$CERROJO"
    flock --wait "$ESPERA_CERROJO_S" 9
    minuto="$((10#$(date -u +%M)))"
    if [ "$minuto" -ge "$FIRMS_FIN_TANDA" ] && [ "$minuto" -le "$MINUTO_RECOGIDA" ]; then
      exec 9>&-
      continue
    fi
    # Hasta el minuto FIRMS_FIN_TANDA de esta hora o de la siguiente.
    tope="$((((FIRMS_FIN_TANDA - minuto + 60) % 60) * 60 - 10#$(date -u +%S)))"
    if [ "$tope" -lt "$FIRMS_TANDA_MINIMA_S" ]; then
      exec 9>&-
      sleep "$FIRMS_TANDA_MINIMA_S"
      continue
    fi
    codigo=0
    (cd "$CLON" && "$ENTORNO/bin/python" -m recogida.firms historico --tope-s "$tope") \
      || codigo=$?
    exec 9>&-
    case "$codigo" in
      0)
        echo "histórico de FIRMS completo"
        (cd "$CLON" && "$ENTORNO/bin/python" -m recogida.firms resumen)
        return 0
        ;;
      3) echo "tanda terminada: quedan tramos pendientes" ;;
      *)
        fallos=$((fallos + 1))
        echo "tanda fallida con código $codigo ($fallos seguidas)"
        if [ "$fallos" -ge "$FIRMS_FALLOS_MAXIMOS" ]; then
          echo "demasiados fallos seguidos: se para; al relanzarlo sigue donde lo dejó"
          return "$codigo"
        fi
        sleep "$FIRMS_ESPERA_FALLO_S"
        continue
        ;;
    esac
    fallos=0
  done
}

principal "$@"
