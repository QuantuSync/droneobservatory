"""Listas cerradas de campos que pueden salir a la web.

Se escribe a mano a propósito: añadir un campo público exige tocar esta lista.
Las rutas usan "." para objetos y "[]" para elementos de lista. La ubicación
(lugar.punto) sale como geometría, no como propiedad.
"""


def _instante(ruta: str) -> set[str]:
    return {ruta, f"{ruta}.valor", f"{ruta}.precision"}


def _rango(ruta: str) -> set[str]:
    return {ruta, f"{ruta}.min", f"{ruta}.max"}


def _estado() -> set[str]:
    return {
        "estado",
        "estado.actual",
        "estado.historial",
        "estado.historial[].estado",
        "estado.historial[].fuente_id",
        *_instante("estado.historial[].fecha"),
    }


def _fuentes() -> set[str]:
    return {
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
    }


def _control() -> set[str]:
    return {"control", *_instante("control.ultima_actualizacion"), "control.motivo_desmentido"}


CAMPOS_PUBLICOS_INCIDENTE: frozenset[str] = frozenset(
    {
        "id",
        "tipo",
        *_estado(),
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
        *_fuentes(),
        *_control(),
    }
)

# Capa de Ucrania: un ataque con sus regiones identificadas por código ISO 3166-2.
CAMPOS_PUBLICOS_ATAQUE: frozenset[str] = frozenset(
    {
        "id",
        "tipo",
        "periodo",
        *_instante("periodo.inicio"),
        *_instante("periodo.fin"),
        "sentido",
        "reivindicacion_de_parte",
        "incluido_en",
        "solapado_con",
        *_estado(),
        "lanzados",
        *_rango("lanzados.shahed_geran"),
        *_rango("lanzados.gerbera_senuelos"),
        *_rango("lanzados.otros"),
        *_rango("lanzados.total"),
        "zonas_lanzamiento",
        "tipos_dron",
        *_rango("derribados"),
        "derribados_categoria",
        *_rango("perdidos_guerra_electronica"),
        *_rango("localizaciones_impacto"),
        *_rango("localizaciones_restos"),
        "lugares_impacto",
        "lugares_restos",
        "cruces",
        "cruces[].pais",
        *_rango("cruces[].numero"),
        "regiones",
        "regiones[].region",
        *_rango("regiones[].derribados"),
        *_rango("regiones[].impactos"),
        *_rango("regiones[].caida_restos"),
        "regiones[].categorias_objetivo",
        "regiones_misiles",
        *_rango("regiones[].heridos"),
        *_rango("regiones[].fallecidos"),
        *_fuentes(),
        *_control(),
    }
)
