"""Paso de la recogida horaria que calcula publicacion/prevision.json (proceso/prevision).

Va después de publicar los demás ficheros y los lee de la misma carpeta: la previsión se
calcula con lo publicado. Un fallo aquí no cambia nada más: los otros ficheros ya están
escritos, prevision.json se queda como estaba (con su fecha de cálculo, que la web enseña) y
el aviso queda en el diario. Las previsiones nuevas se registran en la base (tabla
`previsiones`, sin cambios ni borrados) antes de escribir el fichero.
"""

import logging
from datetime import datetime
from pathlib import Path

from almacen.base import Almacen
from exportacion.proyeccion import escribir
from proceso import prevision
from proceso.prevision import datos as datos_prevision

registro = logging.getLogger(__name__)
FICHERO = "prevision.json"


def calcular(almacen: Almacen, ahora: datetime, directorio: Path) -> bool:
    """Calcula y escribe prevision.json en `directorio`. Devuelve si ha cambiado."""
    datos = datos_prevision.leer_publicados(directorio, ahora.date())
    documento, nuevas = prevision.calcular(datos, ahora, almacen.previsiones())
    registradas = almacen.registrar_previsiones(nuevas)
    ruta = directorio / FICHERO
    anterior = ruta.read_bytes() if ruta.exists() else None
    escribir(documento, ruta)
    registro.info(
        "previsión: %d previsiones nuevas registradas; frontera %s, semana %s, rachas %s",
        registradas,
        [p["pais"] for p in documento["frontera"]["paises"]],
        [p["pais"] for p in documento["semana"]["paises"]],
        [r["pais"] for r in documento.get("rachas", {}).get("activas", [])],
    )
    return ruta.read_bytes() != anterior


def paso_horario(almacen: Almacen, ahora: datetime, directorio: Path) -> None:
    try:
        calcular(almacen, ahora, directorio)
    except Exception as error:
        registro.warning("previsión sin calcular (queda la anterior): %s", str(error)[:300])
