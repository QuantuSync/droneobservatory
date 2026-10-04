// Listas cerradas del esquema 1.9.0 (campos públicos). Un test las compara con los
// ficheros de esquema/ para que no se separen.

export const TIPOS = ["incursion", "interrupcion_aeroportuaria", "sobrevuelo"] as const;
export const ESTADOS = ["notificado", "confirmado", "atribuido", "desmentido"] as const;
export const PRESENCIAS = ["confirmada", "no_confirmada", "descartada"] as const;
export const PRECISIONES = ["minuto", "hora", "dia", "aproximada"] as const;
export const FIABILIDADES = ["A", "B", "C", "D", "E", "F"] as const;
/** E y F nunca se publican. */
export const FIABILIDADES_PUBLICAS = ["A", "B", "C", "D"] as const;
/** Fiabilidades cuyas cifras forman el rango que muestra la ficha. */
export const FIABILIDADES_DEL_RANGO: readonly string[] = ["A", "B", "C"];
export const SENTIDOS = ["RU_UA", "UA_RU"] as const;
export const CATEGORIAS_OBJETIVO = [
  "aeropuerto",
  "base_militar",
  "puerto",
  "energia",
  "presa",
  "estadio",
  "industrial",
  "gubernamental",
  "otra",
] as const;
export const USOS = ["civil", "militar", "mixto"] as const;
export const CLASES_DRON = [
  "multirrotor_pequeno",
  "ala_fija",
  "ataque_largo_alcance",
  "desconocido",
] as const;
export const CIERRES = ["si", "no", "desconocido"] as const;
export const NIVELES_DANOS = ["ninguno", "menores", "graves", "desconocido"] as const;
export const MEDIDAS = [
  "cierre_espacio_aereo",
  "patrulla",
  "cazas",
  "derribo",
  "inhibicion",
  "ninguna_conocida",
] as const;
export const TIPOS_DRON_ATAQUE = ["ala_fija", "multirrotor"] as const;
export const CATEGORIAS_DERRIBADOS = ["derribados", "derribados_o_neutralizados"] as const;
export const CATEGORIAS_OBJETIVO_UCRANIA = [
  "energia",
  "residencial",
  "ferrocarril",
  "puerto",
  "industrial",
  "otra",
] as const;

export const NIVELES_UBICACION = ["instalacion", "localidad", "region", "pais"] as const;
export const RESULTADOS_RECOGIDA = ["correcta", "con_avisos", "fallida"] as const;
export const ESTADOS_FUENTE = ["leida", "con_aviso", "no_leida"] as const;
/** Fuentes que informa estado.json, en el orden en que se muestran. */
export const FUENTES_DEL_SISTEMA = [
  "fuerza_aerea_ua",
  "mindef_ru",
  "gdelt",
  "oficiales",
  "extractor",
  "firms",
  "airprox",
  "parlamentos",
  "investigaciones",
  "estadisticas_oficiales",
  "paginas_js",
  "ova_ua",
  "estado_mayor_ua",
  "gobernadores_ru",
  "rosaviatsia",
  "trafico_aereo",
  "condiciones",
] as const;
/** Satélites e instrumentos de los focos térmicos de NASA FIRMS. */
export const SATELITES_FIRMS = ["Suomi NPP", "NOAA-20", "NOAA-21", "Terra", "Aqua"] as const;
export const INSTRUMENTOS_FIRMS = ["VIIRS", "MODIS"] as const;
/** Lo único que se publica del cruce con FIRMS: el foco detectado. */
export const RESULTADO_FOCO_PUBLICO = "detectado";
/** El radio de búsqueda de un foco no pasa de 10 km. */
export const RADIO_FOCO_MAX_KM = 10;
/** Lo único que se publica del tráfico aéreo medido: el cierre medido. */
export const RESULTADO_TRAFICO_PUBLICO = "cierre_medido";
/** Las publicaciones diarias de adsb.lol usadas, en GitHub. */
export const PATRON_DATOS_ADSBLOL = /^https:\/\/github\.com\/adsblol\/\S+$/;
export const VERSION_ESTADO_SISTEMA = 1;
export const ESTADOS_DIRECTO = ["en_marcha", "con_respaldo", "parado"] as const;

export const PATRON_ID_INCIDENTE = /^EODI-\d{4}-\d{5}$/;
export const PATRON_ID_ATAQUE = /^EODI-UA-\d{4}-\d{4}$/;
export const PATRON_ID_IMPACTO = /^EODI-IG-\d{4}-\d{5}$/;
export const PATRON_ID_LUGAR = /^(katotth|geonames|osm):\S+$/;
export const PATRON_ID_EPISODIO =/^EODI-EP-\d{4}-\d{4}$/;
export const PATRON_INSTANTE = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2})?Z$/;
export const PATRON_PAIS = /^[A-Z]{2}$/;
export const PATRON_REGION = /^[A-Z]{2}-[A-Z0-9]{1,3}$/;
export const PATRON_IDIOMA = /^[a-z]{2}$/;
export const PATRON_OACI = /^[A-Z]{4}$/;
export const PATRON_ENLACE = /^https?:\/\/\S+$/;

export const CREDIBILIDAD_MIN = 1;
export const CREDIBILIDAD_MAX = 6;
export const RADIO_KM_MIN = 0.1;
export const RADIO_KM_MAX = 50;
export const LATITUD_MAX = 90;
export const LONGITUD_MAX = 180;

/** Impactos con lugar de la capa de guerra (canales de las administraciones regionales,
 * del Estado Mayor ucraniano y de los gobernadores rusos). */
export const CATEGORIAS_OBJETIVO_GUERRA = [
  "energia",
  "combustible",
  "residencial",
  "ferrocarril",
  "puerto",
  "industrial",
  "aerodromo",
] as const;
export const CATEGORIAS_INSTALACION = [
  "refineria",
  "deposito_combustible",
  "central",
  "subestacion",
  "aerodromo",
  "puerto",
  "militar",
  "ferrocarril",
  "industrial",
] as const;
export const NIVELES_LUGAR_GUERRA = ["localidad", "instalacion", "comunidad", "distrito"] as const;
export const TIPOS_IMPACTO = ["impacto", "restos"] as const;
/** El radio de un lugar de la capa de guerra no pasa de 50 km. */
export const RADIO_LUGAR_GUERRA_MAX_KM = 50;
