// Forma de los ficheros públicos de publicacion/ (esquema 1.0.0, solo campos públicos)
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
}

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
  fuentes: Fuente[];
  control: { ultima_actualizacion: Instante; motivo_desmentido?: string };
}

export interface PublicacionUcrania {
  ataques: Ataque[];
}

// ---- Resúmenes derivados ---------------------------------------------------------

/** Lo que el mapa, la línea de tiempo y los contadores necesitan de un incidente. */
export interface IncidenteResumen {
  id: string;
  lon: number;
  lat: number;
  radio_km: number;
  tipo: Tipo;
  estado: Estado;
  presencia: PresenciaDron | null;
  titulo: Titulo;
  /** Día UTC del inicio, como días desde 1970-01-01. */
  dia: number;
  pais: string;
  objetivo: string | null;
  episodio: string | null;
}

export interface EpisodioResumen {
  id: string;
  incidentes: string[];
}

export interface Resumen {
  /** Última actualización de los datos publicados (la más reciente de los dos ficheros). */
  actualizado: string;
  incidentes: IncidenteResumen[];
  episodios: EpisodioResumen[];
}

/** Ficha completa de un incidente: sus propiedades públicas más el punto. */
export interface IncidenteDetalle extends PropiedadesIncidente {
  lon: number;
  lat: number;
}

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

export interface ResumenUcrania {
  /** Códigos ISO 3166-2 de las regiones de Ucrania que aparecen en los ataques. */
  regiones: string[];
  ataques: FilaAtaque[];
}

// ---- Estado del sistema (estado.json, lo publica la recogida en el bucket de teselas) ----

export type ResultadoRecogida = "correcta" | "con_avisos" | "fallida";
export type EstadoFuente = "leida" | "con_aviso" | "no_leida";
export type FuenteDelSistema = "fuerza_aerea_ua" | "mindef_ru" | "gdelt" | "oficiales" | "extractor";

export interface EstadoSistema {
  version: 1;
  inicio: string;
  fin: string;
  resultado: ResultadoRecogida;
  /** Fin de la última recogida correcta; null si no ha habido ninguna. */
  ultima_correcta: string | null;
  siguiente: string;
  fuentes: { id: FuenteDelSistema; estado: EstadoFuente; ultimo_dato: string | null }[];
}

/** Cifras para prerenderizar la cabecera y la barra de estado sin esperar a los datos. */
export interface Meta {
  actualizado: string;
  incidentes: number;
  confirmados: number;
  paises: number;
}
