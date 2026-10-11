"""Navegadores con las notificaciones de ntfy activadas, por canal (docs/visitas.md).

ntfy no da suscriptores por canal en sus métricas. Lo único por canal que guarda son las
suscripciones de las notificaciones del navegador (Web Push), en /var/cache/ntfy/webpush.db, que
solo lee el usuario ntfy (ahí están también las direcciones de esas suscripciones). Este script lo
ejecuta la unidad eodi-visitas como root, antes de la pasada (ExecStartPre con «+»), y deja solo
los recuentos por canal en un fichero de «eodi». Sin dependencias: solo la biblioteca estándar.

Uso: python3 ntfy_suscriptores.py <webpush.db> <salida.json> <usuario>
"""

import json
import os
import pwd
import sqlite3
import sys
from datetime import UTC, datetime


def recuentos(ruta: str) -> dict[str, int]:
    if not os.path.exists(ruta):
        return {}
    conexion = sqlite3.connect(f"file:{ruta}?mode=ro", uri=True)
    try:
        filas = conexion.execute(
            "select topic, count(*) from subscription_topic group by topic"
        ).fetchall()
    finally:
        conexion.close()
    return {str(tema): int(n) for tema, n in filas}


def main(webpush: str, salida: str, usuario: str) -> None:
    datos = {
        "momento": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "temas": recuentos(webpush),
    }
    cuenta = pwd.getpwnam(usuario)
    temporal = salida + ".tmp"
    with open(temporal, "w", encoding="utf-8") as fichero:
        json.dump(datos, fichero, ensure_ascii=False)
    os.chown(temporal, cuenta.pw_uid, cuenta.pw_gid)
    os.chmod(temporal, 0o600)
    os.replace(temporal, salida)


if __name__ == "__main__":
    try:
        main(*sys.argv[1:4])
    except (OSError, sqlite3.Error) as error:
        # Sin el recuento por canal la pasada sigue: solo falta ese dato en el resumen.
        print(f"recuento por canal de ntfy sin hacer: {error}", file=sys.stderr)
