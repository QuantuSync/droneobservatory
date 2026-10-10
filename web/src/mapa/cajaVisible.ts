// La caja que encuadra «Aplicar» en los filtros: lo que queda a la vista con los filtros puestos
// en las capas encendidas. Va aparte de Mapa.tsx para no arrastrar MapLibre al paquete inicial.

import type { CeldaGnss } from "../datos/gnss.ts";
import type { Corredor } from "../datos/guerraSatelite.ts";
import type { FilaImpacto, IncidenteResumen } from "../datos/tipos.ts";

/** [oeste, sur, este, norte]. */
export type Caja = [number, number, number, number];

/**
 * Media anchura (grados de longitud y de latitud) que se da a una región de Ucrania o de Rusia
 * alrededor de su centro: de las regiones solo se tiene el centro, y encuadrar solo los centros
 * dejaría medio contorno fuera.
 */
export const MEDIA_REGION_GRADOS: readonly [number, number] = [1.2, 0.8];

/**
 * Regiones rusas fronterizas que entran en el encuadre de la capa de Ucrania (Briansk, Kursk,
 * Bélgorod, Vorónezh, Rostov). Las regiones de Ucrania, Crimea y Sebastopol incluidas, entran
 * todas; las rusas lejanas siguen dibujadas en el mapa, pero no estiran el encuadre hasta los Urales.
 */
export const REGIONES_RUSAS_DEL_ENCUADRE: ReadonlySet<string> = new Set(["RU-BRY", "RU-KRS", "RU-BEL", "RU-VOR", "RU-ROS"]);

/**
 * Caja de Ucrania con esas regiones rusas y Crimea, [oeste, sur, este, norte]: los impactos y los
 * extremos de los corredores fuera de ella no cuentan para el encuadre.
 */
export const ZONA_DEL_ENCUADRE_UCRANIA: Caja = [22, 44.3, 44.4, 54.1];

export function regionDelEncuadre(region: string): boolean {
  return region.startsWith("UA-") || REGIONES_RUSAS_DEL_ENCUADRE.has(region);
}

function enLaZona(lon: number, lat: number): boolean {
  const [o, s, e, n] = ZONA_DEL_ENCUADRE_UCRANIA;
  return lon >= o && lon <= e && lat >= s && lat <= n;
}

export interface LoVisible {
  /** Incidentes que pasan los filtros y el periodo, si su capa (o una que sale de ellos) se ve. */
  incidentes: readonly IncidenteResumen[] | null;
  /** Capa de Ucrania: regiones con ataques en el periodo y su centro; null si está apagada. */
  ucrania: {
    intensidad: ReadonlyMap<string, number> | null;
    centros: Readonly<Record<string, [number, number]>>;
    impactos: readonly FilaImpacto[] | null;
    corredores: readonly Corredor[] | null;
  } | null;
  /** Celdas de interferencia GPS del periodo; null si la capa está apagada. */
  gnss: readonly CeldaGnss[] | null;
}

/**
 * La caja de todo lo que se ve; null si no se ve nada. De la capa de Ucrania solo cuentan Ucrania,
 * Crimea y las regiones rusas fronterizas (ver REGIONES_RUSAS_DEL_ENCUADRE).
 */
export function cajaDeLoVisible(visible: LoVisible): Caja | null {
  let caja: Caja | null = null;
  const sumar = (lon: number, lat: number, medioLon = 0, medioLat = 0) => {
    if (!Number.isFinite(lon) || !Number.isFinite(lat)) return;
    const [o, s, e, n] = [lon - medioLon, lat - medioLat, lon + medioLon, lat + medioLat];
    caja = caja === null ? [o, s, e, n] : [Math.min(caja[0], o), Math.min(caja[1], s), Math.max(caja[2], e), Math.max(caja[3], n)];
  };
  for (const incidente of visible.incidentes ?? []) {
    const punto = incidente.punto ?? incidente.aproximado;
    if (punto !== null) sumar(punto.lon, punto.lat);
  }
  const ucrania = visible.ucrania;
  if (ucrania !== null) {
    for (const [region, ataques] of ucrania.intensidad ?? []) {
      const centro = ucrania.centros[region];
      if (ataques > 0 && centro !== undefined && regionDelEncuadre(region)) sumar(centro[0], centro[1], ...MEDIA_REGION_GRADOS);
    }
    const sumarEnLaZona = (lon: number, lat: number) => {
      if (enLaZona(lon, lat)) sumar(lon, lat);
    };
    for (const impacto of ucrania.impactos ?? []) sumarEnLaZona(impacto[3], impacto[4]);
    for (const corredor of ucrania.corredores ?? []) {
      sumarEnLaZona(corredor.desde[0], corredor.desde[1]);
      sumarEnLaZona(corredor.hasta[0], corredor.hasta[1]);
    }
  }
  for (const celda of visible.gnss ?? []) for (const [lon, lat] of celda.contorno) sumar(lon, lat);
  return caja;
}
