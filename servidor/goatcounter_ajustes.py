"""Ajustes de la base de GoatCounter que no tienen orden propia (servidor/visitas.sh, como el
usuario goatcounter y con el servicio parado). Sin dependencias: solo la biblioteca estándar.

- `ajustar <base>`: qué guarda el sitio (Collect) y la zona horaria del panel. Se guardan las
  páginas vistas una a una con su sesión (un número aleatorio que dura 8 horas, sin la IP), para
  contar visitas y visitantes únicos; el referente, el sistema y el navegador (sin la cabecera
  User-Agent), el tamaño de pantalla y el país. Ni la región ni el idioma.
- `sin-sesiones <base>`: al pararse, GoatCounter guarda en la tabla `store` sus sesiones abiertas,
  cuya clave lleva el User-Agent y la dirección IP del visitante, para seguirlas al volver a
  arrancar. La unidad lo borra justo después de cada parada (ExecStopPost), con borrado seguro
  (secure_delete) y vaciando el diario WAL: ninguna IP queda en el disco ni en las copias. El coste
  es que una visita en curso cuenta como nueva tras un reinicio.
"""

import json
import sqlite3
import sys

# Bits de Collect de GoatCounter 2.7 (settings.go): referente 2, User-Agent 4, pantalla 8, país 16,
# sesiones 128 y páginas vistas una a una 256. Sin región (32) ni idioma (64).
COLLECT = 2 | 4 | 8 | 16 | 128 | 256
# Zona horaria del panel en el formato de GoatCounter: país y zona.
ZONA_HORARIA_PANEL = "ES.Europe/Madrid"


def ajustar(ruta: str) -> None:
    conexion = sqlite3.connect(ruta)
    with conexion:
        for site_id, texto in conexion.execute("select site_id, settings from sites").fetchall():
            ajustes = json.loads(texto)
            ajustes.update(collect=COLLECT, collect_regions="", public="private")
            conexion.execute(
                "update sites set settings = ? where site_id = ?", (json.dumps(ajustes), site_id)
            )
        usuarios = conexion.execute(
            "select u.user_id, u.settings, s.user_defaults"
            " from users u join sites s using (site_id)"
        ).fetchall()
        for user_id, texto, por_defecto in usuarios:
            # Un usuario sin ajustes propios usa los del sitio: se parte de ellos, no de vacío.
            ajustes = json.loads(texto or "{}") or json.loads(por_defecto or "{}")
            ajustes.update(timezone=ZONA_HORARIA_PANEL, twenty_four_hours=True)
            conexion.execute(
                "update users set settings = ? where user_id = ?", (json.dumps(ajustes), user_id)
            )
    conexion.close()


def sin_sesiones(ruta: str) -> None:
    conexion = sqlite3.connect(ruta)
    conexion.execute("pragma secure_delete = on")
    with conexion:
        conexion.execute("delete from store where key = 'session'")
    conexion.execute("pragma wal_checkpoint(truncate)")
    conexion.close()


if __name__ == "__main__":
    orden, base = sys.argv[1], sys.argv[2]
    {"ajustar": ajustar, "sin-sesiones": sin_sesiones}[orden](base)
