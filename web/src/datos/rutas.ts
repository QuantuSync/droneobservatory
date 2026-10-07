// Rutas de los drones sobre Ucrania (esquema/rutas/1.1.0): un índice con las noches publicadas y un
// fichero por noche, en el almacén público. Se piden solo al encender la subcapa «Rutas» (o al
// reproducir la guerra noche a noche): no entran en la primera carga. Se dibuja una noche cada
// vez: la última terminada o la de «Noche a noche». Cada grupo llega ya unido en un recorrido
// (una línea por rama, su franja de incertidumbre y la punta de flecha); se dibujan los
// principales por número de aparatos y la leyenda dice cuántos de cuántos.

import { urlDelAlmacen } from "../almacenPublico.ts";
import { fechaDeDia } from "../tiempo/dias.ts";
import { validarIndiceRutas, validarNocheRutas } from "./validar.ts";

export const OBJETO_INDICE_RUTAS = "rutas/indice.json";
/** Grupos que se dibujan a la vez como mucho: los de más aparatos de la noche. */
export const GRUPOS_PRINCIPALES = 40;

export type FuenteRuta = "neptun" | "fuerza_aerea";

export interface ExtremoRuta {
  t?: string;
  lat: number;
  lon: number;
  radio_km: number;
  zona?: string;
}

export interface TramoRuta {
  grupo: number;
  clase: "enlace" | "hacia_destino" | "desde_lanzamiento" | "neptun";
  tipo: "ataque" | "reaccion" | "reconocimiento";
  desde: ExtremoRuta;
  hasta: ExtremoRuta;
  precision_km: number;
  numero?: { min: number; max: number };
  kmh?: number;
  pista?: string;
  confianza?: string;
  mensajes?: number[];
  division?: boolean;
  union?: boolean;
}

export interface GrupoRuta {
  grupo: number;
  fuente: FuenteRuta;
  tramos: number;
  aparatos_max: number | null;
  kmh_mediana: number | null;
  divisiones: number;
  uniones: number;
}

/** El recorrido de un grupo en una noche, ya unido (proceso/rutas/recorridos.py). */
export interface RecorridoRuta {
  /** Su puesto en la noche: 1 es el de más aparatos. */
  grupo: number;
  tipo: "ataque" | "reaccion" | "reconocimiento";
  aparatos: number | null;
  kmh: number | null;
  inicio: string | null;
  fin: string | null;
  precision_km: { min: number; max: number };
  longitud_km: number;
  trozos: number;
  division: boolean;
  union: boolean;
  confianza?: string;
  pistas?: string[];
  /** Una línea por rama, del principio al final, (lon, lat). */
  lineas: [number, number][][];
  /** La franja de incertidumbre de cada rama. */
  franjas: [number, number][][];
  /** La punta de flecha del final de cada rama. */
  flechas: { lon: number; lat: number; rumbo: number }[];
}

export interface Atribucion {
  texto: string;
  enlace: string;
}

export interface NocheRutas {
  version: string;
  noche: string;
  fuente: FuenteRuta;
  ataques: string[];
  atribucion?: Atribucion;
  incidentes?: string[];
  version_recorridos?: string;
  recorridos?: RecorridoRuta[];
  tramos: TramoRuta[];
  grupos: GrupoRuta[];
}

export interface ResumenNocheRutas {
  noche: string;
  fuente: FuenteRuta;
  ataques: string[];
  lanzados: number | null;
  tramos: number;
  grupos: number;
  recorridos?: number;
}

export interface IndiceRutas {
  version: string;
  generado: string;
  comprobacion: {
    pasa: boolean;
    mediana_reconstruccion_km: number | null;
    mediana_recta_km: number | null;
    puntos: number;
    criterio: string;
  };
  noches_con_mensajes: number;
  noches: ResumenNocheRutas[];
  atribucion_neptun: Atribucion;
}

export async function cargarIndiceRutas(senal?: AbortSignal): Promise<IndiceRutas | null> {
  try {
    const respuesta = await fetch(urlDelAlmacen(OBJETO_INDICE_RUTAS), { signal: senal ?? null });
    if (!respuesta.ok) return null;
    const resultado = validarIndiceRutas(await respuesta.json());
    return resultado.ok ? resultado.datos : null;
  } catch {
    return null;
  }
}

export async function cargarNocheRutas(noche: string, senal?: AbortSignal): Promise<NocheRutas | null> {
  try {
    const respuesta = await fetch(urlDelAlmacen(`rutas/noches/${noche}.json`), { signal: senal ?? null });
    if (!respuesta.ok) return null;
    const resultado = validarNocheRutas(await respuesta.json());
    return resultado.ok ? resultado.datos : null;
  } catch {
    return null;
  }
}

/**
 * La noche que se dibuja: la de «Noche a noche» si se está mostrando una (null si esa no tiene
 * rutas); si no, la última noche terminada con rutas publicadas. Nunca dos a la vez.
 */
export function nocheQueSeDibuja(indice: IndiceRutas, elegida: string | null): string | null {
  if (elegida !== null) return indice.noches.some((n) => n.noche === elegida) ? elegida : null;
  const fechas = indice.noches.map((n) => n.noche).sort();
  return fechas.at(-1) ?? null;
}

/** Clave de un recorrido para encontrarlo al tocarlo: su noche y su grupo. */
export function claveRecorrido(noche: string, grupo: number): string {
  return `${noche}|${grupo}`;
}

export function recorridoDeClave(
  noches: ReadonlyMap<string, NocheRutas>,
  clave: string,
): { noche: NocheRutas; recorrido: RecorridoRuta } | null {
  const [fecha, grupo] = clave.split("|");
  const noche = noches.get(fecha ?? "");
  const recorrido = noche?.recorridos?.find((r) => r.grupo === Number(grupo));
  return noche === undefined || recorrido === undefined ? null : { noche, recorrido };
}

/** Lo que el mapa dibuja de una noche: líneas, franjas y puntas de flecha de los principales. */
export interface RutasEnMapa {
  lineas: GeoJSON.FeatureCollection<GeoJSON.LineString>;
  franjas: GeoJSON.FeatureCollection<GeoJSON.Polygon>;
  flechas: GeoJSON.FeatureCollection<GeoJSON.Point>;
  /** Grupos dibujados y grupos con recorrido de la noche. */
  mostrados: number;
  total: number;
}

/** Grosor (px) y opacidad de un recorrido según sus aparatos, del menor al mayor de la noche. */
export const GROSOR_RUTA = { minimo: 1.4, maximo: 4 } as const;
export const OPACIDAD_RUTA = { minimo: 0.5, maximo: 1 } as const;

/**
 * Los principales recorridos de una noche (los de más aparatos; los publicados ya vienen en ese
 * orden), cada uno con su grosor y su opacidad según el tamaño del grupo y su orden de dibujo:
 * los menores debajo, los mayores encima.
 */
export function rutasEnMapa(noche: NocheRutas, maximo: number = GRUPOS_PRINCIPALES): RutasEnMapa {
  const todos = noche.recorridos ?? [];
  const principales = [...todos].sort((a, b) => a.grupo - b.grupo).slice(0, maximo);
  const tope = Math.max(1, ...principales.map((r) => r.aparatos ?? 1));
  // Del menor al mayor: el último en la lista se pinta encima.
  const orden = [...principales].reverse();
  const propiedades = (r: RecorridoRuta) => {
    const peso = Math.sqrt((r.aparatos ?? 1) / tope);
    return {
      clave: claveRecorrido(noche.noche, r.grupo),
      ancho: GROSOR_RUTA.minimo + (GROSOR_RUTA.maximo - GROSOR_RUTA.minimo) * peso,
      opacidad: OPACIDAD_RUTA.minimo + (OPACIDAD_RUTA.maximo - OPACIDAD_RUTA.minimo) * peso,
      orden: r.aparatos ?? 1,
    };
  };
  return {
    lineas: {
      type: "FeatureCollection",
      features: orden.flatMap((r) =>
        r.lineas.map((linea) => ({
          type: "Feature" as const,
          geometry: { type: "LineString" as const, coordinates: linea },
          properties: propiedades(r),
        })),
      ),
    },
    franjas: {
      type: "FeatureCollection",
      features: orden.flatMap((r) =>
        r.franjas.map((anillo) => ({
          type: "Feature" as const,
          geometry: { type: "Polygon" as const, coordinates: [anillo] },
          properties: propiedades(r),
        })),
      ),
    },
    flechas: {
      type: "FeatureCollection",
      features: orden.flatMap((r) =>
        r.flechas.map((f) => ({
          type: "Feature" as const,
          geometry: { type: "Point" as const, coordinates: [f.lon, f.lat] },
          properties: { ...propiedades(r), rumbo: f.rumbo },
        })),
      ),
    },
    mostrados: principales.length,
    total: todos.length,
  };
}

/** El día (días desde 1970) como AAAA-MM-DD, la clave de una noche. */
export function nocheDeDia(dia: number): string {
  return fechaDeDia(dia).toISOString().slice(0, 10);
}

/** Recorrido de una incursión según la autoridad: la franja entre cada dos lugares que nombra. */
export interface Recorrido {
  version: string;
  fuente: string;
  cita: string;
  puntos: { nombre: string; lat: number; lon: number; radio_km: number; hora?: string }[];
  franja: [number, number][][];
}

export function recorridoEnMapa(recorrido: Recorrido | undefined): GeoJSON.FeatureCollection | null {
  if (recorrido === undefined) return null;
  return {
    type: "FeatureCollection",
    features: recorrido.franja.map((anillo) => ({
      type: "Feature" as const,
      geometry: { type: "Polygon" as const, coordinates: [anillo] },
      properties: {},
    })),
  };
}
