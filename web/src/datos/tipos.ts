// Forma de los ficheros públicos de publicacion/ (esquema 1.9.0, solo campos públicos)
// y de los resúmenes que la web deriva de ellos en el build.

export type Estado = "notificado" | "confirmado" | "atribuido" | "desmentido";
export type Tipo = "incursion" | "interrupcion_aeroportuaria" | "sobrevuelo";
export type PresenciaDron = "confirmada" | "no_confirmada" | "descartada";
export type Precision = "minuto" | "hora" | "dia" | "aproximada";
export type Fiabilidad = "A" | "B" | "C" | "D" | "E" | "F";
export type Sentido = "RU_UA" | "UA_RU";

export interface Instante {
  valor: string;
  precision: Precision;
}

export interface Rango {
  min: number;
  max: number;
}

export type RangoODesconocido = Rango | "desconocido";

export interface Titulo {
  es: string;
  en: string;
}

export interface PasoHistorial {
  estado: Estado;
  fecha: Instante;
  // Ausente cuando el cambio lo provocó una fuente que no es pública.
  fuente_id?: string;
}

export interface Fuente {
  id: string;
  enlace: string;
  medio: string;
  fecha: Instante;
  idioma: string;
  fiabilidad: Fiabilidad;
  credibilidad: number;
  frase_origen: string;
  replicas: number;
}

export type CategoriaObjetivo =
  | "aeropuerto"
  | "base_militar"
  | "puerto"
  | "energia"
  | "presa"
  | "estadio"
  | "industrial"
  | "gubernamental"
  | "otra";

export type Medida =
  | "cierre_espacio_aereo"
  | "patrulla"
  | "cazas"
  | "derribo"
  | "inhibicion"
  | "ninguna_conocida";

export type ClaseDron = "multirrotor_pequeno" | "ala_fija" | "ataque_largo_alcance" | "desconocido";

/** Lo que dice una fuente pública sobre un campo público del incidente. */
export interface AfirmacionPublica {
  /** Ruta pública del campo, con puntos: «drones.numero», «consecuencias.cierre.valor». */
  campo: string;
  fuente_id: string;
  medio: string;
  fiabilidad: Fiabilidad;
  credibilidad: number;
  fecha: Instante;
  /** Valor según esa fuente, del mismo tipo que el campo público. */
  valor: unknown;
  /** Frase literal de la fuente que justifica el valor (presencia de dron). */
  cita?: string;
}

export type SateliteFirms = "Suomi NPP" | "NOAA-20" | "NOAA-21" | "Terra" | "Aqua";
export type InstrumentoFirms = "VIIRS" | "MODIS";

/**
 * Foco térmico detectado por satélite (NASA FIRMS) en el radio y la ventana de un impacto.
 * Solo se publica el positivo: su ausencia no demuestra nada.
 */
export interface FocoTermico {
  resultado: "detectado";
  /** Hora UTC de paso del satélite en el primer foco que cuenta. */
  primer_foco: Instante;
  satelite: SateliteFirms;
  instrumento: InstrumentoFirms;
  /** Distancia del primer foco al punto del impacto. */
  distancia_km: number;
  numero_focos: number;
}

/**
 * Cierre medido con el tráfico aéreo real del archivo de adsb.lol. Solo se publica un cierre
 * medido con cobertura suficiente; la respuesta militar y la interferencia GNSS no se publican.
 */
export interface TraficoAereo {
  cierre: {
    resultado: "cierre_medido";
    aeropuerto: string;
    /** Último movimiento antes del hueco. */
    inicio: Instante;
    /** Primer movimiento después del hueco. */
    fin: Instante;
    duracion_min: number;
    vuelos_desviados: number;
    vuelos_en_espera: number;
    /** La duración o los desvíos medidos difieren de lo que declaran las fuentes. */
    difiere_de_declarado?: boolean;
  };
  /** Publicaciones diarias de adsb.lol usadas (ODbL 1.0). */
  datos?: string[];
}

/** Precisión con la que se conoce el lugar de un incidente sin punto en el mapa. */
export type NivelUbicacion = "instalacion" | "localidad" | "region" | "pais";

export interface PropiedadesIncidente {
  id: string;
  tipo: Tipo;
  estado: { actual: Estado; historial: PasoHistorial[] };
  titulo: Titulo;
  episodio?: string;
  presencia_dron?: PresenciaDron;
  tiempo: { inicio: Instante; fin?: Instante; duracion_min?: number };
  lugar: { radio_km: number; pais: string; localidad?: string };
  objetivo?: {
    categoria: CategoriaObjetivo;
    nombre?: string;
    oaci?: string;
    uso?: "civil" | "militar" | "mixto";
  };
  drones?: { numero?: RangoODesconocido; clase?: ClaseDron; modelo?: string };
  consecuencias?: {
    cierre?: { valor: "si" | "no" | "desconocido"; minutos?: RangoODesconocido };
    vuelos_desviados?: RangoODesconocido;
    vuelos_cancelados?: RangoODesconocido;
    vuelos_retrasados?: RangoODesconocido;
    danos?: { nivel: "ninguno" | "menores" | "graves" | "desconocido"; frase?: string };
    heridos?: RangoODesconocido;
    fallecidos?: RangoODesconocido;
  };
  respuesta?: { medidas?: Medida[] };
  atribucion?: { actor: string; autoridad: string; fecha: Instante };
  foco_termico?: FocoTermico;
  trafico_aereo?: TraficoAereo;
  fuentes: Fuente[];
  afirmaciones_publicas?: AfirmacionPublica[];
  control: { ultima_actualizacion: Instante; motivo_desmentido?: string };
}

export interface FeatureIncidente {
  type: "Feature";
  id: string;
  geometry: { type: "Point"; coordinates: [number, number] };
  properties: PropiedadesIncidente;
}

export interface ColeccionIncidentes {
  type: "FeatureCollection";
  features: FeatureIncidente[];
}

/**
 * Incidente cuyo lugar solo se conoce a nivel de país o región, o que la fuente nombra sin
 * que se haya podido situar con garantías (publicacion/incidentes_sin_ubicacion.json). Las
 * mismas propiedades que una feature, salvo el lugar: sin radio ni punto.
 */
export interface PropiedadesSinUbicacion extends Omit<PropiedadesIncidente, "lugar"> {
  lugar: { pais: string; nivel: NivelUbicacion; region?: string; localidad?: string };
}

export interface PublicacionSinUbicacion {
  incidentes: PropiedadesSinUbicacion[];
}

export type CategoriaObjetivoUcrania =
  | "energia"
  | "residencial"
  | "ferrocarril"
  | "puerto"
  | "industrial"
  | "otra";

export interface RegionAtaque {
  region: string;
  derribados?: RangoODesconocido;
  impactos?: RangoODesconocido;
  caida_restos?: RangoODesconocido;
  categorias_objetivo?: CategoriaObjetivoUcrania[];
  heridos?: RangoODesconocido;
  fallecidos?: RangoODesconocido;
  foco_termico?: FocoTermico;
}

export interface Ataque {
  id: string;
  tipo: "ataque_guerra";
  periodo: { inicio: Instante; fin: Instante };
  sentido: Sentido;
  reivindicacion_de_parte?: true;
  estado: { actual: Estado; historial: PasoHistorial[] };
  lanzados?: {
    shahed_geran?: RangoODesconocido;
    gerbera_senuelos?: RangoODesconocido;
    otros?: RangoODesconocido;
    total?: RangoODesconocido;
  };
  zonas_lanzamiento?: string[];
  tipos_dron?: ("ala_fija" | "multirrotor")[];
  derribados?: RangoODesconocido;
  derribados_categoria?: "derribados" | "derribados_o_neutralizados";
  perdidos_guerra_electronica?: RangoODesconocido;
  localizaciones_impacto?: RangoODesconocido;
  localizaciones_restos?: RangoODesconocido;
  lugares_impacto?: string[];
  lugares_restos?: string[];
  cruces?: { pais: string; numero: RangoODesconocido }[];
  regiones?: RegionAtaque[];
  regiones_misiles?: string[];
  incluido_en?: string;
  solapado_con?: string;
  /** Regiones y ciudades que perdieron luz nocturna tras el ataque, medido por satélite. */
  perdida_luz?: PerdidaLuz[];
  fuentes: Fuente[];
  control: { ultima_actualizacion: Instante; motivo_desmentido?: string };
}

/**
 * Pérdida de luz nocturna medida por satélite (VIIRS, banda día-noche) en una región o una
 * ciudad tras un ataque contra la red eléctrica. Las noches llevan la fecha de su tarde (UTC).
 */
export interface PerdidaLuz {
  zona: "region" | "ciudad";
  region: string;
  ciudad?: { id: string; nombre: string; punto: { lat: number; lon: number } };
  /** Pérdida de la peor noche respecto de la referencia, en %. */
  perdida_pct: number;
  noche: string;
  /** Noches con pérdida por encima del umbral de la regla. */
  noches: string[];
  referencia: { desde: string; hasta: string; noches: number; brillo: number };
  brillo: number;
  origen: "medido";
}

export type CategoriaObjetivoGuerra =
  | "energia"
  | "combustible"
  | "residencial"
  | "ferrocarril"
  | "puerto"
  | "industrial"
  | "aerodromo";

export type CategoriaInstalacion =
  | "refineria"
  | "deposito_combustible"
  | "central"
  | "subestacion"
  | "aerodromo"
  | "puerto"
  | "militar"
  | "ferrocarril"
  | "industrial";

/** Fuente de un impacto con lugar: puede ser una autoridad instalada por Rusia. */
export interface FuenteImpacto extends Fuente {
  autoridad_ocupacion?: true;
}

/** Lugar concreto (localidad o instalación) alcanzado en un ataque de la capa de guerra. */
export interface ImpactoGuerra {
  id: string;
  tipo: "impacto_guerra";
  sentido: Sentido;
  ataque?: string;
  region: string;
  lugar: {
    id: string;
    nombre: string;
    nombre_latino?: string;
    nivel: "localidad" | "instalacion";
    categoria?: CategoriaInstalacion;
    localidad?: string;
    punto: { lat: number; lon: number };
    radio_km: number;
  };
  impacto: "impacto" | "restos";
  categorias_objetivo?: CategoriaObjetivoGuerra[];
  fecha: Instante;
  /** Día del ataque (AAAA-MM-DD) si el mensaje lo nombra y no es el de su publicación. */
  dia?: string;
  /** Lo da el parte diario de la administración: las 24 horas anteriores, sin ataque. */
  parte_diario?: true;
  heridos?: RangoODesconocido;
  fallecidos?: RangoODesconocido;
  reivindicacion_de_parte?: true;
  credibilidad: number;
  foco_termico?: FocoTermico;
  fuentes: FuenteImpacto[];
  control: { ultima_actualizacion: Instante };
}

export interface PublicacionUcrania {
  ataques: Ataque[];
  impactos?: ImpactoGuerra[];
}

// ---- Resúmenes derivados ---------------------------------------------------------

/** Lo que el mapa, la línea de tiempo y los contadores necesitan de un incidente. */
export interface IncidenteResumen {
  id: string;
  /** Punto y radio de precisión; null si el lugar solo se conoce a nivel de país o región. */
  punto: { lon: number; lat: number; radio_km: number } | null;
  /** Para los incidentes sin punto, hasta dónde se conoce el lugar. */
  imprecisa: { nivel: NivelUbicacion; region: string | null } | null;
  tipo: Tipo;
  estado: Estado;
  presencia: PresenciaDron | null;
  titulo: Titulo;
  /** Día UTC del inicio, como días desde 1970-01-01. */
  dia: number;
  pais: string;
  objetivo: string | null;
  episodio: string | null;
  /** Si tiene un foco térmico detectado por satélite: el mapa le pone su marca. */
  foco: boolean;
}

export interface EpisodioResumen {
  id: string;
  incidentes: string[];
}

/** Un paso del historial de estados de un incidente, para el feed de eventos. */
export interface EventoResumen {
  id: string;
  /** Instante del paso, como lo da el historial. */
  fecha: string;
  estado: Estado;
  /** El primer paso del historial: el incidente aparece. */
  nuevo: boolean;
}

export interface Resumen {
  /** Última actualización de los datos publicados (la más reciente de los dos ficheros). */
  actualizado: string;
  incidentes: IncidenteResumen[];
  episodios: EpisodioResumen[];
  /** Eventos del historial de todos los incidentes, del más reciente al más antiguo. */
  eventos: EventoResumen[];
}

/** Ficha completa de un incidente: sus propiedades públicas más el punto. */
/** Ficha completa: con punto, o sin él y con el lugar hasta donde se conoce. */
export type IncidenteDetalle =
  | (PropiedadesIncidente & { lon: number; lat: number })
  | (PropiedadesSinUbicacion & { lon: null; lat: null });

/**
 * Ataque de la capa de Ucrania reducido a una fila:
 * [id, día, sentido, lanzados mín, lanzados máx, derribados mín, derribados máx, suma, regiones].
 * Sentido: 0 es RU_UA y 1 es UA_RU. Una cifra desconocida va como -1. «suma» es 0 cuando
 * las cifras del ataque ya están en otro parte (incluido_en o solapado_con).
 * Cada región es [índice en la tabla de regiones, derribados mín, derribados máx].
 */
export type FilaAtaque = [
  id: string,
  dia: number,
  sentido: 0 | 1,
  lanzadosMin: number,
  lanzadosMax: number,
  derribadosMin: number,
  derribadosMax: number,
  suma: 0 | 1,
  regiones: [region: number, derribadosMin: number, derribadosMax: number][],
];

/**
 * Foco térmico detectado en una región de un ataque. El parte no da el punto del impacto: la
 * marca va en el centro de la región, que sale de su contorno público.
 */
export interface FocoRegion {
  ataque: string;
  /** Día UTC del inicio del ataque, como días desde 1970-01-01. */
  dia: number;
  region: string;
  foco: FocoTermico;
  /** [lon, lat] del centro de la región. */
  centro: [number, number];
}

/**
 * Impacto con lugar reducido a una fila: identificador, día (UTC, días desde 1970-01-01),
 * sentido (0 RU_UA, 1 UA_RU), longitud, latitud, foco térmico detectado (0/1),
 * reivindicación de parte (0/1), instalación (0 localidad, 1 instalación) y región ISO 3166-2.
 */
export type FilaImpacto = [
  id: string,
  dia: number,
  sentido: 0 | 1,
  lon: number,
  lat: number,
  foco: 0 | 1,
  parte: 0 | 1,
  instalacion: 0 | 1,
  region: string,
];

/** La fuente de las cifras por región de cada sentido, con su puntuación. */
export interface FuenteSentido {
  medio: string;
  fiabilidad: Fiabilidad;
  credibilidad: number;
  reivindicacion: boolean;
}

export interface ResumenUcrania {
  /** Códigos ISO 3166-2 de las regiones (de Ucrania y de Rusia) que aparecen en los ataques. */
  regiones: string[];
  ataques: FilaAtaque[];
  /** Regiones con foco térmico detectado, por ataque. */
  focos: FocoRegion[];
  /** Impactos con lugar, por orden de día. */
  impactos: FilaImpacto[];
  /** La fuente de los partes de cada sentido; null si no hay ninguno. */
  fuentes: Record<Sentido, FuenteSentido | null>;
  /** Pérdidas de luz nocturna medidas tras los ataques, por orden de día. */
  luces: LuzResumen[];
  /** Zonas de lanzamiento con punto, una por nombre de los partes. */
  zonas: ZonaResumen[];
  /** Zonas de lanzamiento (índices en `zonas`) declaradas por cada ataque que las da. */
  origenes: Record<string, number[]>;
  /** [lon, lat] del centro de cada región de Ucrania y de Rusia. */
  centros: Record<string, [number, number]>;
  /**
   * Para los ataques contra Rusia, cuyo parte no da el origen: el punto de la frontera de
   * Ucrania más cercano al centro de cada región rusa, [lon, lat].
   */
  fronteraUcrania: Record<string, [number, number]>;
}

/** Pérdida de luz de un ataque reducida a lo que dibuja el mapa y lee la ficha. */
export interface LuzResumen {
  ataque: string;
  /** Día UTC del inicio del ataque, como días desde 1970-01-01. */
  dia: number;
  zona: "region" | "ciudad";
  region: string;
  ciudad: { nombre: string; lon: number; lat: number } | null;
  perdida: number;
  noche: string;
  noches: string[];
  referencia: { desde: string; hasta: string; noches: number };
}

/** Zona de lanzamiento con su punto: el primero de la configuración que casa con el nombre. */
export interface ZonaResumen {
  id: string;
  nombre: string;
  lon: number;
  lat: number;
}

// ---- Estado del sistema (estado.json, lo publica la recogida en el almacén público) ----

export type ResultadoRecogida = "correcta" | "con_avisos" | "fallida";
export type EstadoFuente = "leida" | "con_aviso" | "no_leida";
export type FuenteDelSistema =
  | "fuerza_aerea_ua"
  | "mindef_ru"
  | "gdelt"
  | "oficiales"
  | "extractor"
  | "firms"
  | "airprox"
  | "parlamentos"
  | "investigaciones"
  | "estadisticas_oficiales"
  | "paginas_js"
  | "ova_ua"
  | "estado_mayor_ua"
  | "gobernadores_ru"
  | "rosaviatsia"
  | "trafico_aereo"
  | "condiciones";

export interface EstadoSistema {
  version: 1;
  inicio: string;
  fin: string;
  resultado: ResultadoRecogida;
  /** Fin de la última recogida correcta; null si no ha habido ninguna. */
  ultima_correcta: string | null;
  siguiente: string;
  fuentes: { id: FuenteDelSistema; estado: EstadoFuente; ultimo_dato: string | null }[];
  /** Fin de la última exportación semanal correcta; null si no consta ninguna. */
  ultima_exportacion?: string | null;
  /** Fin de la última ejecución correcta del motor de deducción; null si no consta ninguna. */
  ultima_deduccion?: string | null;
  /** Servicio de detección en directo de cierres: su estado y su último ciclo correcto. */
  directo?: { estado: EstadoDirecto; ultimo_ciclo_correcto: string | null };
}

export type EstadoDirecto = "en_marcha" | "con_respaldo" | "parado";

/** Cifras para prerenderizar la cabecera y la barra de estado sin esperar a los datos. */
export interface Meta {
  actualizado: string;
  incidentes: number;
  confirmados: number;
  atribuidos: number;
  paises: number;
  /** Si se ha publicado el fichero de incidentes sin ubicación: la metodología lo ofrece. */
  sinUbicacion: boolean;
}
