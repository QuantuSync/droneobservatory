"""Vigilancia del despliegue de la web: el de producción en Vercel es el del último commit de main
y salió bien.

El 14 de octubre de 2026 a las 05:07 y a las 05:12 UTC fallaron dos compilaciones de producción
(los datos publicados traían un campo que el código de main no conocía) y nadie se enteró hasta
que otra sesión fusionó su rama. Desde entonces el workflow vigia-recogida lo comprueba en cada
pasada, por la API de Vercel (secreto EODI_VERCEL_TOKEN, token del equipo):

- si el último commit de main no tiene despliegue de producción 20 minutos después, o su último
  despliegue falló, se pide uno nuevo de main (el reintento, una sola vez por commit: cuenta los
  despliegues fallidos de ese commit desde el último bueno);
- si después de ese reintento sigue fallando (dos o más fallidos seguidos del mismo commit), es un
  problema: el vigía abre la incidencia «La web no se publica en Vercel» (y la cierra al
  arreglarse).

Un despliegue en marcha, o uno omitido a propósito (web/scripts/omitir-build.ts: el commit no toca
la web, estado CANCELED), no es problema mientras la web en producción salió de un despliegue
bueno.

Uso: python -m recogida.despliegue_web [--sha <commit>] [--sin-reintento]
Escribe `problema_web` y `mensaje_web` en la salida del paso (GITHUB_OUTPUT).
"""

import argparse
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

API = "https://api.vercel.com"
EQUIPO = "team_YuSxhC6SCSD9ei0H4F3lfukG"
PROYECTO = "prj_sOgU6PolAci3coUv91BMDriioZ2z"
NOMBRE = "droneobservatory"
# Lo que tarda como mucho en aparecer el despliegue de un commit nuevo (compilar lleva unos 5).
ESPERA_COMMIT = timedelta(minutes=20)
EN_MARCHA = frozenset({"QUEUED", "INITIALIZING", "BUILDING"})
FALLIDOS = frozenset({"ERROR"})
TOPE_S = 30.0

Peticion = Callable[[str, str, dict[str, Any] | None], dict[str, Any]]


def peticion_api(token: str) -> Peticion:
    def pedir(metodo: str, ruta: str, cuerpo: dict[str, Any] | None = None) -> dict[str, Any]:
        separador = "&" if "?" in ruta else "?"
        p = urllib.request.Request(
            f"{API}{ruta}{separador}teamId={EQUIPO}",
            data=json.dumps(cuerpo).encode() if cuerpo is not None else None,
            method=metodo,
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        )
        with urllib.request.urlopen(p, timeout=TOPE_S) as respuesta:
            leido: dict[str, Any] = json.loads(respuesta.read() or b"{}")
            return leido

    return pedir


@dataclass
class Diagnostico:
    problema: bool
    reintentar: bool
    frase: str


def _sha(despliegue: dict[str, Any]) -> str:
    return str((despliegue.get("meta") or {}).get("githubCommitSha") or "")


def _hora(despliegue: dict[str, Any]) -> datetime:
    return datetime.fromtimestamp(int(despliegue.get("created") or 0) / 1000, UTC)


def diagnosticar(
    despliegues: Sequence[dict[str, Any]], sha: str, commit: datetime, ahora: datetime
) -> Diagnostico:
    """Con los despliegues de producción (del más nuevo al más viejo) y el último commit de main."""
    corto = sha[:7]
    del_commit = [d for d in despliegues if _sha(d) == sha]
    if not del_commit:
        if ahora - commit < ESPERA_COMMIT:
            return Diagnostico(False, False, f"El commit {corto} de main aún se está desplegando.")
        return Diagnostico(
            False, True, f"El commit {corto} de main no tiene despliegue de producción."
        )
    ultimo = del_commit[0]
    estado = str(ultimo.get("state") or ultimo.get("readyState"))
    hora = f"{_hora(ultimo):%Y-%m-%d %H:%M} UTC"
    if estado == "READY":
        return Diagnostico(False, False, f"Producción en verde con el commit {corto} ({hora}).")
    if estado in EN_MARCHA:
        return Diagnostico(False, False, f"Despliegue del commit {corto} en marcha ({hora}).")
    if estado == "CANCELED":
        bueno = next((d for d in despliegues if str(d.get("state")) == "READY"), None)
        if bueno is not None:
            return Diagnostico(
                False, False,
                f"El commit {corto} no toca la web (despliegue omitido); producción en verde con "
                f"el {_sha(bueno)[:7]}.",
            )  # fmt: skip
    # Fallidos seguidos de este commit desde el último bueno.
    seguidos = 0
    for d in del_commit:
        if str(d.get("state")) in FALLIDOS:
            seguidos += 1
        elif str(d.get("state")) == "READY":
            break
    if seguidos >= 2:
        return Diagnostico(
            True, False,
            f"La compilación de producción del commit {corto} de main ha fallado {seguidos} veces "
            f"seguidas, también tras el reintento (la última, {hora}). La web publicada sigue "
            "siendo la anterior.",
        )  # fmt: skip
    return Diagnostico(
        False,
        True,
        f"La compilación de producción del commit {corto} falló ({hora}): se reintenta.",
    )


def reintentar(pedir: Peticion) -> str:
    proyecto = pedir("GET", f"/v9/projects/{PROYECTO}", None)
    repo = (proyecto.get("link") or {}).get("repoId")
    respuesta = pedir(
        "POST",
        "/v13/deployments?forceNew=1",
        {
            "name": NOMBRE,
            "project": PROYECTO,
            "target": "production",
            "gitSource": {"type": "github", "repoId": repo, "ref": "main"},
        },
    )
    return str(respuesta.get("id") or respuesta.get("uid") or "")


def _salida(problema: bool, frase: str) -> None:
    ruta = os.environ.get("GITHUB_OUTPUT")
    if ruta:
        with Path(ruta).open("a", encoding="utf-8") as fichero:
            fichero.write(f"problema_web={'true' if problema else 'false'}\nmensaje_web={frase}\n")
    resumen = os.environ.get("GITHUB_STEP_SUMMARY")
    if resumen:
        with Path(resumen).open("a", encoding="utf-8") as fichero:
            fichero.write(f"\n### Despliegue de la web\n\n{'⚠️' if problema else '✅'} {frase}\n")


def _commit_de_main(sha: str) -> datetime:
    """La hora del commit, de la copia local del repositorio (la del checkout del workflow)."""
    salida = subprocess.run(
        ["git", "show", "-s", "--format=%cI", sha], capture_output=True, text=True, check=True
    ).stdout.strip()
    return datetime.fromisoformat(salida).astimezone(UTC)


def principal(
    argumentos: list[str] | None = None,
    ahora: datetime | None = None,
    pedir: Peticion | None = None,
    hora_commit: Callable[[str], datetime] = _commit_de_main,
) -> int:
    opciones = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    opciones.add_argument("--sha", default=os.environ.get("GITHUB_SHA", ""))
    opciones.add_argument("--sin-reintento", action="store_true")
    args = opciones.parse_args(argumentos)
    momento = ahora or datetime.now(UTC)
    if pedir is None:
        token = os.environ.get("VERCEL_TOKEN", "").strip()
        if not token:
            print("::warning::sin el secreto EODI_VERCEL_TOKEN no se comprueba el despliegue")
            _salida(False, "Sin el secreto EODI_VERCEL_TOKEN: despliegue sin comprobar.")
            return 0
        pedir = peticion_api(token)
    try:
        despliegues = pedir(
            "GET", f"/v6/deployments?projectId={PROYECTO}&target=production&limit=20", None
        ).get("deployments", [])
        diagnostico = diagnosticar(despliegues, args.sha, hora_commit(args.sha), momento)
        frase = diagnostico.frase
        if diagnostico.reintentar and not args.sin_reintento:
            frase += f" Despliegue nuevo pedido: {reintentar(pedir)}."
    except (OSError, ValueError, urllib.error.URLError) as error:
        print(f"::warning::la API de Vercel no responde: {type(error).__name__}")
        _salida(False, f"La API de Vercel no responde ({type(error).__name__}).")
        return 0
    print(f"::error::{frase}" if diagnostico.problema else frase)
    _salida(diagnostico.problema, frase)
    return 0


if __name__ == "__main__":
    sys.exit(principal())
