"""Último recurso desde fuera: reinicia el servidor por la API de Hetzner Cloud si no se le ve.

Lo llama el workflow vigia-recogida (cada 10 minutos, también lanzado por la tarea programada de
Vercel cuando el servidor no da señales). Si salud.json (recogida/vigilancia.py, cada 5 minutos)
lleva más de 30 minutos sin renovarse, el servidor no se ha reparado solo (ni el guardián del
sistema, recogida/guardian.py, ni sus reintentos): se reinicia el servidor eodi-recogida por la
API, como mucho una vez cada 6 horas (cuentan todos los reinicios por la API, también los
manuales). Tras arrancar, el guardián lanza la recogida pendiente.

Si salud.json no se puede leer (y no solo está viejo), puede ser el almacén y no el servidor: solo
se reinicia si además sshd no saluda en el puerto 22.

La incidencia del servidor (el correo al dueño) solo se abre si esto no lo arregla: mientras el
silencio no pasa de 30 minutos, o el reinicio es de hace menos de 30, se aplaza (`aplazar=true`
en la salida del paso); con el reinicio de las 6 horas gastado y el servidor aún sin señales, se
abre.

El token (secreto EODI_HCLOUD_TOKEN del repositorio, variable HCLOUD_TOKEN) es el del proyecto
EODI de Hetzner Cloud; no se escribe nunca en el código ni en el registro.

Uso: python -m recogida.reinicio_externo [--simulacro] [--forzar]
     --simulacro: todo menos pedir el reinicio (cuenta lo que haría).
     --forzar: como si el servidor llevara más de 30 minutos sin señales (prueba real); se niega
               entre los minutos 10 y 45 de cada hora, para no pisar una recogida.
"""

import argparse
import json
import os
import socket
import sys
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from recogida import salud as salud_mod

API = "https://api.hetzner.cloud/v1"
SERVIDOR = "eodi-recogida"
MAX_SILENCIO = timedelta(minutes=30)
REINICIO_CADA = timedelta(hours=6)
# Tras pedir el reinicio, el servidor tarda unos minutos en volver y en subir salud.json.
ESPERA_TRAS_REINICIO = timedelta(minutes=30)
ORDENES_REINICIO = frozenset({"reboot_server", "reset_server", "start_server"})
MINUTOS_PROHIBIDOS_FORZAR = range(10, 46)
TOPE_S = 30.0
VARIABLE_SALIDA = "GITHUB_OUTPUT"
VARIABLE_RESUMEN = "GITHUB_STEP_SUMMARY"

Peticion = Callable[[str, str, dict[str, Any] | None], dict[str, Any]]


def _instante(texto: Any) -> datetime | None:
    if not isinstance(texto, str):
        return None
    try:
        return datetime.fromisoformat(texto.replace("Z", "+00:00")).astimezone(UTC)
    except ValueError:
        return None


def peticion_api(token: str) -> Peticion:
    def pedir(metodo: str, ruta: str, cuerpo: dict[str, Any] | None = None) -> dict[str, Any]:
        datos = json.dumps(cuerpo).encode() if cuerpo is not None else None
        p = urllib.request.Request(
            f"{API}{ruta}",
            data=datos,
            method=metodo,
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        )
        with urllib.request.urlopen(p, timeout=TOPE_S) as respuesta:
            leido: dict[str, Any] = json.loads(respuesta.read() or b"{}")
            return leido

    return pedir


def ssh_saluda(ip: str, intentos: int = 3) -> bool:
    for _ in range(intentos):
        try:
            with socket.create_connection((ip, 22), timeout=15) as conexion:
                if conexion.recv(64).startswith(b"SSH-"):
                    return True
        except OSError:
            continue
    return False


@dataclass
class Decision:
    accion: str  # nada | aplazar | reiniciar | agotado
    frase: str


def decidir(
    salud: dict[str, Any] | None,
    ahora: datetime,
    ultimo_reinicio: datetime | None,
    ssh: Callable[[], bool],
    forzar: bool = False,
) -> Decision:
    """Qué hacer con lo que dice salud.json y el último reinicio por la API."""
    generado = _instante(salud.get("generado")) if salud else None
    if forzar:
        silencio = MAX_SILENCIO + timedelta(minutes=1)
        cuando = "prueba forzada"
    elif generado is None:
        silencio = None
        cuando = "salud.json no se puede leer"
    else:
        silencio = ahora - generado
        cuando = f"último salud.json del {generado:%Y-%m-%d %H:%M} UTC"
    if silencio is not None and silencio <= MAX_SILENCIO:
        if silencio <= salud_mod.MAX_SIN_SALUD:
            return Decision("nada", f"El servidor da señales ({cuando}).")
        return Decision(
            "aplazar", f"Sin señales del servidor ({cuando}): se espera a los 30 minutos."
        )
    if silencio is None and ssh():
        return Decision("nada", f"{cuando}, pero sshd saluda: no es el servidor, no se reinicia.")
    if ultimo_reinicio is not None and ahora - ultimo_reinicio < REINICIO_CADA:
        hace = ahora - ultimo_reinicio
        if hace < ESPERA_TRAS_REINICIO:
            return Decision(
                "aplazar",
                f"Sin señales del servidor ({cuando}); reiniciado por la API hace "
                f"{hace.total_seconds() / 60:.0f} minutos: se espera a que vuelva.",
            )
        return Decision(
            "agotado",
            f"Sin señales del servidor ({cuando}) y ya se reinició por la API el "
            f"{ultimo_reinicio:%Y-%m-%d %H:%M} UTC (como mucho uno cada 6 horas): no se ha "
            "arreglado solo.",
        )
    return Decision("reiniciar", f"Sin señales del servidor ({cuando}): se reinicia por la API.")


def ultimo_reinicio(pedir: Peticion, id_: int) -> datetime | None:
    acciones = pedir("GET", f"/servers/{id_}/actions?sort=started:desc&per_page=50", None)
    momentos = [
        m
        for a in acciones.get("actions", [])
        if a.get("command") in ORDENES_REINICIO and (m := _instante(a.get("started")))
    ]
    return max(momentos) if momentos else None


def _salida(**valores: str) -> None:
    ruta = os.environ.get(VARIABLE_SALIDA)
    if ruta:
        with Path(ruta).open("a", encoding="utf-8") as fichero:
            for clave, valor in valores.items():
                fichero.write(f"{clave}={valor}\n")


def _resumen(frase: str) -> None:
    ruta = os.environ.get(VARIABLE_RESUMEN)
    if ruta:
        with Path(ruta).open("a", encoding="utf-8") as fichero:
            fichero.write(f"\n### Reinicio desde fuera\n\n{frase}\n")


def principal(
    argumentos: list[str] | None = None,
    ahora: datetime | None = None,
    pedir: Peticion | None = None,
    leer_salud: Callable[[], dict[str, Any] | None] | None = None,
    ssh: Callable[[str], bool] = ssh_saluda,
) -> int:
    opciones = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    opciones.add_argument("--simulacro", action="store_true")
    opciones.add_argument("--forzar", action="store_true")
    args = opciones.parse_args(argumentos)
    momento = ahora or datetime.now(UTC)
    if args.forzar and momento.minute in MINUTOS_PROHIBIDOS_FORZAR and not args.simulacro:
        print("::error::la prueba forzada no se lanza entre los minutos 10 y 45")
        return 1
    salud = (leer_salud or (lambda: salud_mod.leer_estado(salud_mod.URL_SALUD)))()
    token = os.environ.get("HCLOUD_TOKEN", "").strip()
    if pedir is None:
        if not token:
            frase = "Sin el secreto EODI_HCLOUD_TOKEN: no se puede reiniciar desde fuera."
            print(f"::warning::{frase}")
            _resumen(frase)
            _salida(aplazar="false", reinicio="sin_token")
            return 0
        pedir = peticion_api(token)
    try:
        servidores = pedir("GET", f"/servers?name={SERVIDOR}", None).get("servers", [])
        if not servidores:
            raise LookupError(f"no hay ningún servidor {SERVIDOR}")
        servidor = servidores[0]
        ip = servidor["public_net"]["ipv4"]["ip"]
        anterior = ultimo_reinicio(pedir, servidor["id"])
    except (OSError, ValueError, KeyError, LookupError, urllib.error.URLError) as error:
        frase = f"La API de Hetzner no responde como se espera: {type(error).__name__}."
        print(f"::warning::{frase}")
        _resumen(frase)
        _salida(aplazar="false", reinicio="error_api")
        return 0
    decision = decidir(salud, momento, anterior, lambda: ssh(ip), args.forzar)
    frase = decision.frase
    if decision.accion == "reiniciar":
        if args.simulacro:
            frase = f"SIMULACRO: {frase} (servidor {servidor['id']}, estado {servidor['status']})"
        else:
            accion = "poweron" if servidor.get("status") == "off" else "reboot"
            try:
                pedir("POST", f"/servers/{servidor['id']}/actions/{accion}", None)
                frase = f"{frase} Pedido ({accion}) a las {momento:%H:%M} UTC."
            except (OSError, urllib.error.URLError) as error:
                frase = f"{frase} La API no lo aceptó: {type(error).__name__}."
                decision = Decision("agotado", frase)
    print(frase if decision.accion == "nada" else f"::warning::{frase}")
    _resumen(frase)
    _salida(
        aplazar="true" if decision.accion in ("aplazar", "reiniciar") else "false",
        reinicio=decision.accion,
        mensaje_reinicio=frase,
    )
    return 0


if __name__ == "__main__":
    sys.exit(principal())
