"""Histórico de noticias de GDELT con la API DOC, por días y reanudable.

Recorre desde el 1 de enero de 2025 hasta el inicio de la recogida horaria,
día a día, con el cursor «gdelt_historico» en la base: si se corta, sigue
donde lo dejó. Con --horas se para al agotar ese tiempo (un trabajo de GitHub
Actions dura como mucho seis horas) y sube lo hecho.

La API limita mucho las peticiones, así que un recorrido largo convive con la
ejecución horaria: al terminar vuelve a descargar la base de la rama estado,
le añade los artículos, candidatos y el cursor del histórico, y la sube. Así
no pisa lo que la ejecución horaria haya guardado entretanto.

Uso: python -m recogida.historico_gdelt --correo <correo> [--hasta AAAA-MM-DD] [--horas N]
     [--sin-subir]
"""

import argparse
import logging
import sys
import time
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory

from almacen import remoto
from almacen.base import Almacen
from almacen.cifrado import abrir_cifrada, cargar_clave_local, guardar_cifrada
from proceso.noticias import titular_normalizado
from recogida import gdelt
from recogida.descarga import Descargador, DescargaFallida

registro = logging.getLogger("recogida")

DESDE = datetime(2025, 1, 1, tzinfo=UTC)
CURSOR = "gdelt_historico"
PASO = timedelta(days=1)
# Si la API no responde a un día tras los reintentos, se espera y se vuelve a
# intentar ese mismo día: 10 minutos dejan pasar un bloqueo temporal por exceso.
ESPERA_TRAS_FALLO_S = 600.0
MAX_FALLOS_SEGUIDOS = 6


def fusionar(origen: Almacen, destino: Almacen) -> None:
    """Añade a `destino` los artículos, candidatos y el cursor del histórico de `origen`."""
    for articulo in origen.articulos():
        documento = {
            **articulo,
            "titular_normalizado": titular_normalizado(articulo["titular"]),
        }
        if destino.guardar_articulo(documento):
            for _ in range(articulo["replicas"]):
                destino.sumar_replica(articulo["url"])
        if articulo["candidato"]:
            destino.asignar_candidato(articulo["url"], articulo["candidato"])
    for candidato in origen.candidatos():
        destino.guardar_candidato(candidato)
    cursor = origen.cursor(CURSOR)
    if cursor is not None:
        destino.guardar_cursor(CURSOR, cursor)


def recorrer(
    almacen: Almacen,
    descargador: Descargador,
    hasta: datetime,
    limite: float,
    reloj: Callable[[], float] = time.monotonic,
    dormir: Callable[[float], None] = time.sleep,
) -> int:
    """Días recorridos hasta `hasta` o hasta el `limite` del reloj."""
    cursor = almacen.cursor(CURSOR)
    dia = datetime.fromisoformat(cursor["hasta"]) if cursor else DESDE
    dias = fallos = 0
    while dia < hasta and reloj() < limite:
        fin = min(dia + PASO, hasta)
        try:
            recuentos = gdelt.recoger(almacen, descargador, dia, fin)
        except DescargaFallida as error:
            fallos += 1
            registro.warning("%s sin respuesta (%d seguidos): %s", dia.date(), fallos, error)
            if fallos >= MAX_FALLOS_SEGUIDOS:
                break
            dormir(ESPERA_TRAS_FALLO_S)
            continue
        fallos = 0
        almacen.guardar_cursor(CURSOR, {"hasta": fin.strftime("%Y-%m-%dT%H:%M:%SZ")})
        registro.info("%s %s", dia.date(), recuentos.resumen())
        dia, dias = fin, dias + 1
    return dias


def principal(argumentos: list[str] | None = None) -> int:
    opciones = argparse.ArgumentParser(description=__doc__)
    opciones.add_argument("--correo", required=True, help="correo del autor del commit de estado")
    opciones.add_argument("--repositorio", default=remoto.REPOSITORIO)
    opciones.add_argument(
        "--hasta", help="día final (excluido); por defecto, el inicio de la recogida horaria"
    )
    opciones.add_argument("--horas", type=float, default=float("inf"))
    opciones.add_argument("--sin-subir", action="store_true")
    args = opciones.parse_args(argumentos)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
    cargar_clave_local()
    limite = time.monotonic() + args.horas * 3600
    with TemporaryDirectory() as temporal:
        ruta = Path(temporal) / remoto.FICHERO
        if not remoto.descargar(ruta, args.repositorio):
            registro.error("no hay base en la rama %s", remoto.RAMA)
            return 1
        trabajo = Almacen(abrir_cifrada(ruta))
        horario = trabajo.cursor(gdelt.FUENTE_ID)
        if args.hasta:
            hasta = datetime.fromisoformat(args.hasta).replace(tzinfo=UTC)
        elif horario is not None:
            # Donde empezó la recogida horaria.
            hasta = datetime.fromisoformat(horario["inicio"])
        else:
            hasta = datetime.now(UTC)
        dias = recorrer(trabajo, Descargador(pausas_por_sitio=gdelt.PAUSAS), hasta, limite)
        registro.info("días recorridos: %d", dias)
        if args.sin_subir:
            guardar_cifrada(trabajo.conexion, Path.cwd() / "data" / "historico" / remoto.FICHERO)
            return 0
        # La base puede haber cambiado mientras tanto: se fusiona con la más reciente.
        remoto.descargar(ruta, args.repositorio)
        fresca = Almacen(abrir_cifrada(ruta))
        fusionar(trabajo, fresca)
        guardar_cifrada(fresca.conexion, ruta)
        remoto.subir(ruta, args.correo, args.repositorio)
        registro.info("base subida a la rama %s", remoto.RAMA)
    return 0


if __name__ == "__main__":
    sys.exit(principal())
