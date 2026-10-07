"""¿Se puede reiniciar el servidor ahora? Lo pregunta servidor/reinicio.sh antes de reiniciar tras
una actualización de seguridad que lo pide (/run/reboot-required).

Las actualizaciones automáticas ya no reinician solas a hora fija: un reinicio corta la captura
del seguimiento (lo que emite NEPTUN mientras el servidor está apagado se pierde) y cualquier
trabajo en marcha. Solo se reinicia si, a la vez:

- no es entre los minutos 12 y 40 de la hora (la recogida horaria y su publicación);
- no hay en marcha ninguna unidad del observatorio con temporizador (recogida, exportación,
  tráfico, luces…): solo las que están siempre en marcha (detección en directo y captura del
  seguimiento), que vuelven solas al arrancar;
- no hay un ataque en curso sobre Ucrania según el último estado del flujo de NEPTUN del archivo
  del seguimiento: ningún misil ni balístico activo y como mucho 20 drones de largo alcance
  activos. Con el archivo del 4 al 7 de octubre de 2026, los drones activos no bajan de 4 en
  ninguna hora (hay seguimiento de drones casi siempre); 20 es la mediana del máximo horario
  durante los ataques de la noche y deja de día ventanas de varias horas;
- el estado de NEPTUN es reciente (menos de 10 minutos): si la captura no recibe, no se sabe si
  hay ataque y no se reinicia.

Sale con 0 si se puede y con 3 si no, con el motivo.

Uso: python -m recogida.reinicio [--datos <carpeta del seguimiento>]
"""

import argparse
import contextlib
import gzip
import json
import subprocess
import sys
from collections import Counter
from collections.abc import Callable, Iterable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from recogida.seguimiento import NEPTUN, directorio_datos

MINUTOS_PROHIBIDOS = range(12, 41)
SIEMPRE_EN_MARCHA = frozenset({"eodi-directo.service", "eodi-seguimiento.service"})
MAX_DRONES = 20
TIPOS_MISIL = frozenset({"missile", "ballistic"})
MAX_ANTIGUEDAD = timedelta(minutes=10)
NO_SE_PUEDE = 3


def lineas_neptun(datos: Path, ahora: datetime, horas: int = 3) -> Iterable[dict[str, Any]]:
    """Las líneas del flujo de NEPTUN de las últimas horas, en orden."""
    for atras in range(horas - 1, -1, -1):
        hora = ahora - timedelta(hours=atras)
        carpeta = datos / NEPTUN / f"{hora:%Y}" / f"{hora:%m}"
        base = f"{NEPTUN}-{hora:%Y-%m-%dT%H}"
        for ruta in sorted(carpeta.glob(f"{base}.*")):
            if not ruta.name.endswith((".jsonl", ".jsonl.gz")):
                continue
            abrir = gzip.open if ruta.name.endswith(".gz") else open
            with abrir(ruta, "rt", encoding="utf-8") as fichero:
                for linea in fichero:
                    try:
                        yield json.loads(linea)
                    except ValueError:
                        continue


def amenazas_activas(lineas: Iterable[dict[str, Any]]) -> tuple[Counter[str], datetime | None]:
    """Amenazas activas por tipo tras reproducir snapshot, upsert y remove, y la hora del último
    mensaje del flujo."""
    activas: dict[str, str] = {}
    ultimo: datetime | None = None
    for linea in lineas:
        if linea.get("via") != "ws":
            continue
        try:
            mensaje = json.loads(str(linea.get("crudo", "")))
        except ValueError:
            continue
        if not isinstance(mensaje, dict):
            continue
        with contextlib.suppress(KeyError, ValueError):
            ultimo = datetime.fromisoformat(str(linea["recibido"]).replace("Z", "+00:00"))
        tipo, datos = mensaje.get("type"), mensaje.get("data")
        if tipo == "snapshot":
            lista = datos.get("threats", []) if isinstance(datos, dict) else datos
            activas = {
                str(a["id"]): str(a.get("type", "?"))
                for a in (lista if isinstance(lista, list) else [])
                if isinstance(a, dict) and a.get("id")
            }
        elif tipo == "upsert" and isinstance(datos, dict) and datos.get("id"):
            if datos.get("status", "active") == "active":
                activas[str(datos["id"])] = str(datos.get("type", "?"))
            else:
                activas.pop(str(datos["id"]), None)
        elif tipo == "remove":
            ident = datos.get("id") if isinstance(datos, dict) else datos
            activas.pop(str(ident), None)
    return Counter(activas.values()), ultimo


def unidades_en_marcha() -> list[str]:
    salida = subprocess.run(
        ["systemctl", "list-units", "eodi-*", "--state=activating,active,deactivating",
         "--no-legend", "--plain", "--type=service"],
        capture_output=True, text=True, timeout=30, check=False,
    )  # fmt: skip
    return [linea.split()[0] for linea in salida.stdout.splitlines() if linea.strip()]


def decidir(
    ahora: datetime,
    datos: Path,
    en_marcha: Callable[[], list[str]] = unidades_en_marcha,
) -> tuple[bool, str]:
    if ahora.minute in MINUTOS_PROHIBIDOS:
        return False, f"minuto {ahora.minute}: hora de la recogida horaria"
    ocupadas = [u for u in en_marcha() if u not in SIEMPRE_EN_MARCHA]
    if ocupadas:
        return False, "trabajos en marcha: " + ", ".join(sorted(ocupadas))
    activas, ultimo = amenazas_activas(lineas_neptun(datos, ahora))
    if ultimo is None or ahora - ultimo > MAX_ANTIGUEDAD:
        return False, "sin estado reciente de NEPTUN: no se sabe si hay un ataque en curso"
    misiles = sum(activas[t] for t in TIPOS_MISIL)
    drones = activas.get("uav", 0)
    resumen = f"{drones} drones y {misiles} misiles activos"
    if misiles or drones > MAX_DRONES:
        return False, f"ataque en curso según NEPTUN: {resumen}"
    return True, f"sin ataque en curso según NEPTUN ({resumen})"


def principal(argumentos: list[str] | None = None) -> int:
    opciones = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    opciones.add_argument("--datos", type=Path)
    args = opciones.parse_args(argumentos)
    se_puede, motivo = decidir(datetime.now(UTC), args.datos or directorio_datos())
    print(("se puede reiniciar: " if se_puede else "no se reinicia: ") + motivo)
    return 0 if se_puede else NO_SE_PUEDE


if __name__ == "__main__":
    sys.exit(principal())
