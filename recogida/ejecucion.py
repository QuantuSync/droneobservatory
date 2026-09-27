"""Procesado de publicaciones de una fuente de partes y ejecución de la fuente.

El registro de ejecución solo lleva recuentos, nunca contenido.
"""

import logging
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime

from almacen.base import Almacen, DocumentoInvalido
from esquema import Documento
from proceso.ataques import incorporar
from proceso.configuracion import cargar_fuentes
from recogida.cache import CachePaginas
from recogida.descarga import Descargador
from recogida.fuente import RELECTURA, Fuente, leer_desde
from recogida.parte import ParteIlegible
from recogida.recorrido import pagina
from recogida.telegram import Publicacion

registro = logging.getLogger(__name__)


@dataclass
class Recuentos:
    publicaciones: int = 0
    partes: int = 0
    leidos: int = 0
    fallidos: int = 0
    nuevos: int = 0
    actualizados: int = 0
    motivos: Counter[str] = field(default_factory=Counter)

    def sumar(self, otros: "Recuentos") -> None:
        for nombre in ("publicaciones", "partes", "leidos", "fallidos", "nuevos", "actualizados"):
            setattr(self, nombre, getattr(self, nombre) + getattr(otros, nombre))
        self.motivos.update(otros.motivos)

    def resumen(self) -> str:
        return (
            f"publicaciones={self.publicaciones} partes={self.partes} leidos={self.leidos} "
            f"fallidos={self.fallidos} nuevos={self.nuevos} actualizados={self.actualizados}"
        )


class SinCursor(RuntimeError):
    pass


def configuracion_fuente(fuente_id: str) -> Documento:
    (config,) = [f for f in cargar_fuentes() if f["id"] == fuente_id]
    return config


def motivo_general(motivo: str) -> str:
    """Motivo sin detalles variables, para agrupar recuentos."""
    return motivo.split(":")[0]


def procesar(
    almacen: Almacen,
    publicaciones: Iterable[Publicacion],
    fuente: Fuente,
    config: Documento,
    ahora: datetime,
) -> Recuentos:
    recuentos = Recuentos()
    for publicacion in publicaciones:
        recuentos.publicaciones += 1
        if not fuente.es_parte(publicacion.texto):
            continue
        recuentos.partes += 1
        try:
            leido = fuente.leer(publicacion.texto, publicacion.fecha)
            resultado = incorporar(
                almacen, publicacion, leido, config, publicacion.texto, ahora, fuente.perfil
            )
        except (ParteIlegible, DocumentoInvalido) as error:
            motivo = str(error) if isinstance(error, ParteIlegible) else f"no valida: {error}"
            almacen.registrar_fallido(
                publicacion.enlace, config["id"], motivo, publicacion.fecha.isoformat()
            )
            recuentos.fallidos += 1
            recuentos.motivos[motivo_general(motivo)] += 1
            continue
        almacen.resolver_fallido(publicacion.enlace)
        recuentos.leidos += 1
        recuentos.nuevos += resultado.nuevo
        recuentos.actualizados += resultado.cambiado and not resultado.nuevo
    return recuentos


def ejecutar(
    almacen: Almacen,
    descargador: Descargador,
    cache: CachePaginas,
    fuente: Fuente,
    ahora: datetime | None = None,
) -> Recuentos:
    """Una ejecución de la fuente: verificar el canal, leer desde el cursor y procesar."""
    ahora = ahora or datetime.now(UTC)
    config = configuracion_fuente(fuente.id)
    cursor = almacen.cursor(fuente.id)
    if cursor is None:
        raise SinCursor(f"{fuente.id} no tiene cursor: hay que ejecutar antes el histórico")
    portada = pagina(descargador, cache, fuente.canal, None, usar_cache=False)
    fuente.verificar(descargador, portada)
    lectura = leer_desde(
        descargador, cache, portada, fuente.canal, cursor["ultimo_id"], ahora - RELECTURA
    )
    recuentos = procesar(almacen, lectura.publicaciones, fuente, config, ahora)
    if lectura.publicaciones and lectura.publicaciones[-1].id > cursor["ultimo_id"]:
        ultimo = lectura.publicaciones[-1]
        almacen.guardar_cursor(
            fuente.id, {"ultimo_id": ultimo.id, "fecha": ultimo.fecha.isoformat()}
        )
    registro.info("%s paginas=%d %s", fuente.id, lectura.paginas, recuentos.resumen())
    return recuentos
