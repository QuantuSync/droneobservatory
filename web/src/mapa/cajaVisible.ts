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

/** La caja de todo lo que se ve; null si no se ve nada. */
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
      if (ataques > 0 && centro !== undefined) sumar(centro[0], centro[1], ...MEDIA_REGION_GRADOS);
    }
    for (const impacto of ucrania.impactos ?? []) sumar(impacto[3], impacto[4]);
    for (const corredor of ucrania.corredores ?? []) {
      sumar(corredor.desde[0], corredor.desde[1]);
      sumar(corredor.hasta[0], corredor.hasta[1]);
    }
  }
  for (const celda of visible.gnss ?? []) for (const [lon, lat] of celda.contorno) sumar(lon, lat);
  return caja;
}
