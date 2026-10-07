"""Paso de la base a solo disco: deja de subirse la copia secundaria a la rama estado de GitHub.

Desde el 5 de octubre de 2026 la base manda en el disco del servidor (modo `disco`,
almacen/sitio.py) y, además de las copias cifradas del almacén privado, cada guardado sube una copia
secundaria a la rama `estado` del repositorio de datos. Esa copia se mantiene hasta el 12 de octubre
de 2026; el martes 13 a las 10:00 UTC el temporizador eodi-base-solo-disco ejecuta este paso, que
antes de cambiar nada comprueba:

1. que la última copia cifrada del almacén privado tiene menos de 2 horas, se baja, su huella
   coincide, se descifra y la base restaurada pasa la comprobación de integridad de SQLite;
2. que esa misma copia está también en la segunda copia de Helsinki (almacen/replica.py).

Si todo va bien, escribe `no` en el interruptor de la copia secundaria
(`/home/eodi/.eodi/base_secundaria`), que vale desde la recogida siguiente. Si algo falla, no cambia
nada. En los dos casos deja lo que ha hecho en `/home/eodi/.eodi/base_solo_disco.json`, que la
vigilancia publica (un fallo es un problema: llega al dueño). Con --ensayo hace las comprobaciones
sin cambiar el interruptor.

Volver atrás: `echo github > /home/eodi/.eodi/base_secundaria` (como eodi) y, para poner la rama al
día en el acto, `base.sh a-github`.

Uso: python -m almacen.solo_disco [--ensayo]
"""

import argparse
import json
import logging
import os
import sys
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from almacen import copias, replica, sitio

registro = logging.getLogger("solo_disco")

MAX_ANTIGUEDAD = timedelta(hours=2)
PRUEBA = "prueba-solo-disco.sqlite"


def comprobar(
    origen: copias.Copias,
    segunda: copias.Copias,
    trabajo: Path,
    ahora: datetime,
) -> tuple[bool, list[str]]:
    """Las dos comprobaciones; devuelve si se puede cambiar y lo comprobado."""
    hecho: list[str] = []
    horarias = [c for c in origen.copias() if c[0] == copias.HORARIA]
    if not horarias:
        return False, ["no hay copias horarias de la base en el almacén"]
    _, cuando, objeto = horarias[-1]
    if ahora - cuando > MAX_ANTIGUEDAD:
        return False, [f"la última copia ({objeto.clave}) tiene más de 2 horas"]
    destino = trabajo / PRUEBA
    destino.unlink(missing_ok=True)
    try:
        resultado = origen.restaurar(destino, objeto.clave)
        hecho.append(f"restaurada {objeto.clave}: {resultado['tamano']} bytes, íntegra")
    except (OSError, ValueError) as error:
        return False, [f"la última copia no se restaura: {error}"]
    finally:
        destino.unlink(missing_ok=True)
    en_replica = replica.PREFIJO_BASE + objeto.clave.removeprefix(origen.destino.prefijo)
    if segunda.metadato(en_replica, "x-amz-meta-sha256") is None:
        return False, [*hecho, f"{en_replica} no está en la segunda copia"]
    hecho.append(f"{en_replica} está en la segunda copia")
    return True, hecho


def principal(
    argumentos: list[str] | None = None,
    ahora: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> int:
    opciones = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    opciones.add_argument("--ensayo", action="store_true", help="comprueba sin cambiar nada")
    args = opciones.parse_args(argumentos)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    secretos = Path(os.environ.get("EODI_SECRETOS") or sitio.casa() / ".eodi")
    momento = ahora()
    if sitio.copia_secundaria() == sitio.SIN_SECUNDARIA and not args.ensayo:
        registro.info("la base ya está solo en disco: nada que hacer")
        return 0
    credenciales = copias.Credenciales.cargar()
    from almacen import cifrado

    cifrado.cargar_clave_local(secretos / "clave_age.txt")
    origen = copias.Copias(copias.cargar_destino(), credenciales)
    segunda = copias.Copias(replica.destino_replica(replica.cargar()), credenciales)
    trabajo = sitio.directorio() / sitio.TRABAJO
    try:
        correcto, hecho = comprobar(origen, segunda, trabajo, momento)
    except (OSError, ValueError) as error:
        correcto, hecho = False, [f"error al comprobar: {error}"]
    cambiado = False
    if correcto and not args.ensayo:
        sitio.fijar_copia_secundaria(sitio.SIN_SECUNDARIA)
        cambiado = True
    resultado: dict[str, Any] = {
        "fecha": momento.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "ensayo": args.ensayo,
        "correcto": correcto,
        "cambiado": cambiado,
        "comprobaciones": hecho,
    }
    for linea in hecho:
        registro.info("%s", linea)
    if not args.ensayo:
        ruta = secretos / "base_solo_disco.json"
        ruta.write_text(json.dumps(resultado, ensure_ascii=False) + "\n", encoding="utf-8")
    if correcto:
        if args.ensayo:
            registro.info("ensayo correcto: se puede pasar a solo disco")
        else:
            registro.info("la base pasa a solo disco: sin copia secundaria desde la siguiente")
        return 0
    registro.error("no se pasa a solo disco: %s", hecho[-1] if hecho else "sin comprobaciones")
    return 1


if __name__ == "__main__":
    sys.exit(principal())
