// Rutas de los drones sobre Ucrania (esquema/rutas/1.0.0): un índice con las noches publicadas y un
// fichero por noche, en el almacén público. Se piden solo al encender la subcapa «Rutas» (o al
// reproducir la guerra noche a noche): no entran en la primera carga. Con un periodo largo se
// enseñan solo las noches principales (las de más drones lanzados), y la leyenda dice cuántas de
// cuántas.

import { urlDelAlmacen } from "../almacenPublico.ts";
import type { Periodo } from "../tiempo/dias.ts";
import { diaDeInstante, fechaDeDia } from "../tiempo/dias.ts";
import { validarIndiceRutas, validarNocheRutas } from "./validar.ts";

export const OBJETO_INDICE_RUTAS = "rutas/indice.json";
/** Noches que se dibujan a la vez como mucho: las de más drones lanzados del periodo. */
export const NOCHES_PRINCIPALES = 10;

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
  franja: [number, number][];
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

/** Las noches del periodo y las que se dibujan: todas si caben, si no las de más drones. */
export function nochesDelPeriodo(
  indice: IndiceRutas,
  periodo: Periodo | null,
  maximo: number = NOCHES_PRINCIPALES,
): { mostradas: string[]; total: number } {
  const delPeriodo = indice.noches.filter((n) => {
    if (periodo === null) return true;
    const dia = diaDeInstante(n.noche);
    return dia >= periodo.desde - 1 && dia <= periodo.hasta;
  });
  const orden = [...delPeriodo].sort(
    (a, b) => (b.lanzados ?? -1) - (a.lanzados ?? -1) || b.tramos - a.tramos || (a.noche < b.noche ? 1 : -1),
  );
  return { mostradas: orden.slice(0, maximo).map((n) => n.noche).sort(), total: delPeriodo.length };
}

/** Clave de un tramo para encontrarlo al tocarlo: su noche y su posición. */
export function claveTramo(noche: string, indice: number): string {
  return `${noche}|${indice}`;
}

export function tramoDeClave(
  noches: ReadonlyMap<string, NocheRutas>,
  clave: string,
): { noche: NocheRutas; tramo: TramoRuta } | null {
  const [fecha, posicion] = clave.split("|");
  const noche = noches.get(fecha ?? "");
  const tramo = noche?.tramos[Number(posicion)];
  return noche === undefined || tramo === undefined ? null : { noche, tramo };
}

/** Las franjas de las noches dadas, para el mapa. */
export function rutasEnMapa(noches: readonly NocheRutas[]): GeoJSON.FeatureCollection<GeoJSON.Polygon> {
  return {
    type: "FeatureCollection",
    features: noches.flatMap((n) =>
      n.tramos.map((t, i) => ({
        type: "Feature" as const,
        geometry: { type: "Polygon" as const, coordinates: [t.franja] },
        properties: { clave: claveTramo(n.noche, i), fuente: n.fuente, tipo: t.tipo },
      })),
    ),
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
