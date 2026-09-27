"""Lista cerrada de campos que pueden salir a la web.

Se escribe a mano a propósito: añadir un campo público exige tocar esta lista.
Las rutas usan "." para objetos y "[]" para elementos de lista. La ubicación
(lugar.punto) sale como geometría, no como propiedad.
"""


def _instante(ruta: str) -> set[str]:
    return {ruta, f"{ruta}.valor", f"{ruta}.precision"}


def _rango(ruta: str) -> set[str]:
    return {ruta, f"{ruta}.min", f"{ruta}.max"}


CAMPOS_PUBLICOS_INCIDENTE: frozenset[str] = frozenset(
    {
        "id",
        "tipo",
        "estado",
        "estado.actual",
        "estado.historial",
        "estado.historial[].estado",
        "estado.historial[].fuente_id",
        *_instante("estado.historial[].fecha"),
        "titulo",
        "titulo.es",
        "titulo.en",
        "episodio",
        "tiempo",
        *_instante("tiempo.inicio"),
        *_instante("tiempo.fin"),
        "tiempo.duracion_min",
        "lugar",
        "lugar.radio_km",
        "lugar.pais",
        "lugar.localidad",
        "objetivo",
        "objetivo.categoria",
        "objetivo.nombre",
        "objetivo.oaci",
        "objetivo.uso",
        "drones",
        *_rango("drones.numero"),
        "drones.clase",
        "drones.modelo",
        "consecuencias",
        "consecuencias.cierre",
        "consecuencias.cierre.valor",
        *_rango("consecuencias.cierre.minutos"),
        *_rango("consecuencias.vuelos_desviados"),
        *_rango("consecuencias.vuelos_cancelados"),
        *_rango("consecuencias.vuelos_retrasados"),
        "consecuencias.danos",
        "consecuencias.danos.nivel",
        "consecuencias.danos.frase",
        *_rango("consecuencias.heridos"),
        *_rango("consecuencias.fallecidos"),
        "respuesta",
        "respuesta.medidas",
        "atribucion",
        "atribucion.actor",
        "atribucion.autoridad",
        *_instante("atribucion.fecha"),
        "fuentes",
        "fuentes[].id",
        "fuentes[].enlace",
        "fuentes[].medio",
        *_instante("fuentes[].fecha"),
        "fuentes[].idioma",
        "fuentes[].fiabilidad",
        "fuentes[].credibilidad",
        "fuentes[].frase_origen",
        "fuentes[].replicas",
        "control",
        *_instante("control.ultima_actualizacion"),
        "control.motivo_desmentido",
    }
)
