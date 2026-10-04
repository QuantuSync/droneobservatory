"""Corrección de lo ya guardado con el criterio de presencia del dron, los titulares y las
noches de los cierres (una vez, dentro de la recogida horaria).

1. **Candidatos por noche** (`proceso/noticias.separar`): un candidato que juntó el cierre de
   una noche y la repetición de la noche siguiente se separa; la repetición se mide ahora desde
   el inicio del suceso (Lieja: el cierre del sábado 8 de noviembre de 2025 salió en las
   noticias del domingo por la mañana y el «opnieuw stilgelegd» del domingo por la noche es otro
   cierre). Los candidatos nuevos los extrae la recogida horaria en esta misma pasada.
2. **Rehacer** todos los incidentes con las reglas de ahora, desde las fichas y las
   declaraciones guardadas, sin descargar nada ni llamar al extractor: criterio de presencia
   (proceso/declaraciones.py, proceso/presencia.py), titulares coherentes
   (proceso/titulares.py) y fusión que nunca junta dos cierres de noches distintas
   (proceso/incidentes.cierres_de_noches_distintas).
3. **Motivo**: cada incidente que cambia de presencia, titular, estado o fecha deja su motivo
   en el historial; la base es de solo añadir y cada cambio es una versión nueva.

Se ejecuta una vez por versión (el cursor CURSOR guarda la aplicada); después la recogida
horaria aplica las mismas reglas a lo que llega.
"""

import logging
from datetime import datetime
from typing import Any

from almacen.base import Almacen
from esquema import Documento
from proceso import extraccion, incidentes, presencia
from proceso.noticias import filtro, nomenclator

registro = logging.getLogger(__name__)

CURSOR = "criterio_presencia"
PASADAS_FUSION = 5
VERSION = "presencia/2"
MOTIVO = (
    "criterio de presencia del dron (la autoridad competente que lo da por hecho lo confirma), "
    "titular coherente con la presencia y un incidente por noche de cierre"
)


def _foto(almacen: Almacen) -> dict[str, Documento]:
    return {i["id"]: i for i in almacen.incidentes()}


def aplicar(almacen: Almacen, ahora: datetime, modelos_base: frozenset[str]) -> dict[str, Any]:
    """Aplica la corrección si no se ha aplicado ya. Devuelve el resumen (vacío si no hace
    nada)."""
    hecho = almacen.cursor(CURSOR) or {}
    if hecho.get("version") == VERSION:
        return {}
    from recogida import calidad, revision

    antes = _foto(almacen)
    separados = calidad.separar_candidatos(almacen, filtro(), nomenclator())
    rehecho = revision.rehacer(almacen, ahora, modelos_base)
    # La fusión de una pasada deja sin fundir lo que solo encaja tras otra fusión (la recogida
    # horaria lo funde en las pasadas siguientes): aquí se repite hasta que no funde nada.
    vocabulario = extraccion.modelos_validos(almacen, modelos_base)
    for _ in range(PASADAS_FUSION):
        hechas = incidentes.fusionar(almacen, ahora, vocabulario)
        rehecho["fusiones"] += hechas
        if not hechas:
            break
    # Al fundir, la presencia del destino puede cambiar: la revisión deja presencia y titular
    # coherentes también en los fundidos.
    revision_presencia = presencia.revisar(
        almacen, ahora, extraccion.modelos_validos(almacen, modelos_base)
    )
    despues = _foto(almacen)
    cambios = 0
    for id_, nuevo in despues.items():
        anterior = antes.get(id_)
        if anterior is None or anterior == nuevo:
            continue
        before = {**anterior, "id": id_}
        presencia.anotar(almacen, before, nuevo, MOTIVO)
        cambios += 1
    resumen = {
        "version": VERSION,
        "fecha": ahora.strftime("%Y-%m-%dT%H:%MZ"),
        "candidatos_separados": len(separados),
        "separados": separados,
        "rehecho": rehecho,
        "presencia_revisada": len(revision_presencia[0]),
        "incidentes_con_cambios": cambios,
        "activos_antes": sum(1 for i in antes.values() if incidentes.activo(i)),
        "activos_despues": sum(1 for i in despues.values() if incidentes.activo(i)),
    }
    almacen.guardar_cursor(CURSOR, resumen)
    registro.info(
        "criterio de presencia aplicado: %s",
        {k: v for k, v in resumen.items() if k != "separados"},
    )
    return resumen
