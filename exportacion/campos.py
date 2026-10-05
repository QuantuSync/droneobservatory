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
        "estado.historial[].motivo",
        "estado.historial[].motivo.es",
        "estado.historial[].motivo.en",
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


def _afirmaciones() -> set[str]:
    """Quién dice qué: cada valor con su fuente. El valor tiene el formato de su campo: un
    texto, una lista de textos, un rango o un instante."""
    ruta = "afirmaciones_publicas[]"
    return {
        "afirmaciones_publicas",
        f"{ruta}.campo",
        f"{ruta}.fuente_id",
        f"{ruta}.medio",
        f"{ruta}.fiabilidad",
        f"{ruta}.credibilidad",
        f"{ruta}.cita",
        *_instante(f"{ruta}.fecha"),
        *_rango(f"{ruta}.valor"),
        *_instante(f"{ruta}.valor"),
    }


def _foco_termico(ruta: str) -> set[str]:
    """Foco térmico de FIRMS: solo sale si es detectado (proceso.focos_termicos.solo_detectado),
    y sin la potencia, el motivo, la ventana, la línea base ni los productos consultados."""
    return {
        ruta,
        f"{ruta}.resultado",
        *_instante(f"{ruta}.primer_foco"),
        f"{ruta}.satelite",
        f"{ruta}.instrumento",
        f"{ruta}.distancia_km",
        f"{ruta}.numero_focos",
    }


def _perdida_luz(ruta: str) -> set[str]:
    """Pérdida de luz nocturna medida por satélite (proceso/luces.py): solo se guarda la que llega
    al umbral. La región o la ciudad, la pérdida de la peor noche, las noches con pérdida, la
    referencia y el origen medido."""
    elemento = f"{ruta}[]"
    return {
        ruta,
        f"{elemento}.zona",
        f"{elemento}.region",
        f"{elemento}.ciudad",
        f"{elemento}.ciudad.id",
        f"{elemento}.ciudad.nombre",
        f"{elemento}.ciudad.punto",
        f"{elemento}.ciudad.punto.lat",
        f"{elemento}.ciudad.punto.lon",
        f"{elemento}.perdida_pct",
        f"{elemento}.noche",
        f"{elemento}.noches",
        f"{elemento}.referencia",
        f"{elemento}.referencia.desde",
        f"{elemento}.referencia.hasta",
        f"{elemento}.referencia.noches",
        f"{elemento}.referencia.brillo",
        f"{elemento}.brillo",
        f"{elemento}.origen",
    }


def _trafico_aereo(ruta: str) -> set[str]:
    """Tráfico aéreo medido: solo sale con un cierre medido válido
    (proceso.mediciones.solo_publico), con su aeropuerto, horas, duración, desvíos, esperas, si
    difiere de lo declarado y las publicaciones de adsb.lol usadas. Sin la respuesta militar,
    la interferencia GNSS, la cobertura ni la línea base."""
    cierre = f"{ruta}.cierre"
    return {
        ruta,
        cierre,
        f"{cierre}.resultado",
        f"{cierre}.aeropuerto",
        *_instante(f"{cierre}.inicio"),
        *_instante(f"{cierre}.fin"),
        f"{cierre}.duracion_min",
        f"{cierre}.vuelos_desviados",
        f"{cierre}.vuelos_en_espera",
        f"{cierre}.difiere_de_declarado",
        f"{ruta}.datos",
    }


CAMPOS_PUBLICOS_INCIDENTE: frozenset[str] = frozenset(
    {
        "id",
        "tipo",
        *_estado(),
        "titulo",
        "titulo.es",
        "titulo.en",
        "episodio",
        "presencia_dron",
        "tiempo",
        *_instante("tiempo.inicio"),
        *_instante("tiempo.fin"),
        "tiempo.duracion_min",
        "lugar",
        "lugar.radio_km",
        "lugar.pais",
        "lugar.localidad",
        # El lugar que da una autoridad: la fuente que lo nombra y los demás lugares que cita
        # (recogida/revisados.py, ubicaciones).
        "lugar.fuente_punto",
        "lugar.otros_lugares",
        "lugar.otros_lugares[].nombre",
        "lugar.otros_lugares[].punto",
        "lugar.otros_lugares[].punto.lat",
        "lugar.otros_lugares[].punto.lon",
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
        *_foco_termico("foco_termico"),
        *_trafico_aereo("trafico_aereo"),
        "respuesta",
        "respuesta.medidas",
        "ataque",
        "ataque.id",
        "ataque.jornada",
        "ataque.jornada.tipo",
        "ataque.jornada.desde",
        "ataque.jornada.hasta",
        "ataque.por",
        "atribucion",
        "atribucion.actor",
        "atribucion.autoridad",
        "atribucion.tipo",
        "atribucion.pais",
        *_instante("atribucion.fecha"),
        "investigacion",
        "investigacion[].autoridad",
        "investigacion[].cita",
        "investigacion[].fuente_id",
        *_instante("investigacion[].fecha"),
        *_fuentes(),
        *_afirmaciones(),
        *_control(),
    }
)

# Incidentes sin punto (su lugar solo se sabe a nivel de país o de región): los mismos campos
# que en el mapa, sin radio y con el nivel del lugar y la región.
CAMPOS_PUBLICOS_SIN_UBICACION: frozenset[str] = (CAMPOS_PUBLICOS_INCIDENTE - {"lugar.radio_km"}) | {
    "lugar.region",
    "lugar.nivel",
}

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
        "resumen",
        "jornada",
        "jornada.tipo",
        "jornada.desde",
        "jornada.hasta",
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
        "cruces[].incidentes",
        "cruces[].frase",
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
        *_foco_termico("regiones[].foco_termico"),
        *_perdida_luz("perdida_luz"),
        *_fuentes(),
        *_control(),
    }
)

# Capa de guerra con lugar: cada impacto con su localidad o su instalación, el ataque y la
# región a los que se enlaza, el tipo de objetivo, la fecha, las fuentes con su puntuación y
# la marca de reivindicación de parte. Sin el método de lectura, el enlace interno con el
# ataque ni la confianza del extractor.
CAMPOS_PUBLICOS_IMPACTO: frozenset[str] = frozenset(
    {
        "id",
        "tipo",
        "sentido",
        "ataque",
        "region",
        "lugar",
        "lugar.id",
        "lugar.nombre",
        "lugar.nombre_latino",
        "lugar.nivel",
        "lugar.categoria",
        "lugar.localidad",
        "lugar.punto",
        "lugar.punto.lat",
        "lugar.punto.lon",
        "lugar.radio_km",
        "impacto",
        "categorias_objetivo",
        *_instante("fecha"),
        "dia",
        "parte_diario",
        *_rango("heridos"),
        *_rango("fallecidos"),
        "reivindicacion_de_parte",
        "credibilidad",
        *_foco_termico("foco_termico"),
        *_fuentes(),
        "fuentes[].autoridad_ocupacion",
        *_control(),
    }
)

# Mapa diario de interferencia GPS (recogida/gnss_publico.py): el índice de días y meses
# publicados y, por día o mes, las celdas H3 con sus aeronaves, las degradadas, la proporción,
# el nivel y el contorno. Sin la serie por hora ni nada de las aeronaves.
CAMPOS_PUBLICOS_GNSS: frozenset[str] = frozenset(
    {
        "version",
        "generado",
        "dias",
        "meses",
        "periodo",
        "resolucion_h3",
        "resumen",
        "resumen.celdas",
        "resumen.celdas_media",
        "resumen.celdas_alta",
        "resumen.aeronaves",
        "resumen.degradadas",
        "resumen.proporcion",
        "resumen.nivel",
        "celdas",
        "celdas[].h3",
        "celdas[].aeronaves",
        "celdas[].degradadas",
        "celdas[].proporcion",
        "celdas[].nivel",
        "celdas[].contorno",
    }
)

# Detección en directo de cierres de aeropuerto (recogida/directo.py, directo.json): cada
# aviso con su aeropuerto, su estado, sus horas, la evidencia medida, la confirmación y la
# ventaja frente a la primera noticia. Sin los motivos internos, el factor de cobertura ni la
# versión de la regla.
CAMPOS_PUBLICOS_AVISO_DIRECTO: frozenset[str] = frozenset(
    {
        "id",
        "oaci",
        "nombre",
        "pais",
        "lat",
        "lon",
        "estado",
        "inicio",
        "detectado",
        "reanudado",
        "evidencia",
        "evidencia.esperados",
        "evidencia.vistos",
        "evidencia.llegadas_perdidas",
        "evidencia.salidas_perdidas",
        "evidencia.esperas",
        "evidencia.desvios",
        "confirmacion",
        "confirmacion.tipo",
        "confirmacion.incidente",
        "confirmacion.hora",
        "primera_noticia",
        "ventaja_min",
    }
)
