// La capa de Ucrania con el teclado: lo que está a la vista en el mapa, en el orden en que lo
// recorre el tabulador. Es la misma solución que la de los incidentes (Mapa.tsx): después del
// mapa, una lista de botones invisible que el lector de pantalla anuncia; el enfocado se señala
// en el mapa con el aro y su letrero, e Intro abre su ficha. Va aparte de Mapa.tsx para probarla
// sin MapLibre.

import type { CeldaGnss } from "../datos/gnss.ts";
import type { CiudadAlumbrado, CiudadSinLuz } from "../datos/guerraSatelite.ts";
import type { FilaImpacto } from "../datos/tipos.ts";

/**
 * Lo más que se lista de los impactos y de las celdas de GPS a la vista: con el periodo entero
 * hay miles de impactos y nadie los recorre uno a uno. La lista de la capa (en su panel) y
 * acercar el mapa dan acceso a los demás.
 */
export const MAXIMO_EN_TECLADO = 50;

/** Algo de la capa que se puede enfocar: dónde señalarlo y qué abre. */
export interface ElementoTeclado {
  clave: string;
  lon: number;
  lat: number;
}

export interface UcraniaALaVista {
  /** Regiones con ataques en el periodo cuyo centro se ve, de la más atacada a la menos. */
  regiones: (ElementoTeclado & { ataques: number })[];
  /** Los impactos más recientes de los que se ven (hasta MAXIMO_EN_TECLADO). */
  impactos: (ElementoTeclado & { fila: FilaImpacto })[];
  totalImpactos: number;
  /** Las celdas de GPS más afectadas de las que se ven (hasta MAXIMO_EN_TECLADO). */
  celdas: (ElementoTeclado & { celda: CeldaGnss })[];
  totalCeldas: number;
  /** Ciudades con pérdida de luz o alumbrado reducido («Con satélite»). */
  ciudades: (ElementoTeclado & { clase: "luz" | "alumbrado"; nombre: string; perdida: number | null })[];
}

export const NADA_A_LA_VISTA: UcraniaALaVista = {
  regiones: [],
  impactos: [],
  totalImpactos: 0,
  celdas: [],
  totalCeldas: 0,
  ciudades: [],
};

/** Centro aproximado de una celda: la media de sus vértices. */
export function centroDeCelda(celda: CeldaGnss): [number, number] {
  const n = celda.contorno.length || 1;
  const [lon, lat] = celda.contorno.reduce(([a, b], [x, y]) => [a + x, b + y], [0, 0]);
  return [lon / n, lat / n];
}

export interface CapaUcraniaEnMapa {
  /** Capa de Ucrania encendida: regiones e impactos. */
  ucrania: boolean;
  /** «Con satélite» encendido: ciudades sin luz y con alumbrado reducido. */
  satelite: boolean;
  /** Capa de GPS encendida. */
  gnss: boolean;
  intensidad: ReadonlyMap<string, number> | null;
  centros: Readonly<Record<string, [number, number]>> | null;
  impactos: readonly FilaImpacto[] | null;
  celdas: readonly CeldaGnss[] | null;
  ciudadesSinLuz: readonly CiudadSinLuz[] | null;
  alumbrado: readonly CiudadAlumbrado[] | null;
}

/** Lo que se ve de la capa, según el predicado de lo que cae dentro del mapa. */
export function ucraniaALaVista(
  capa: CapaUcraniaEnMapa,
  seVe: (lon: number, lat: number) => boolean,
): UcraniaALaVista {
  const regiones: UcraniaALaVista["regiones"] = [];
  const impactos: UcraniaALaVista["impactos"] = [];
  const ciudades: UcraniaALaVista["ciudades"] = [];
  if (capa.ucrania) {
    for (const [codigo, ataques] of capa.intensidad ?? []) {
      const centro = capa.centros?.[codigo];
      if (ataques > 0 && centro !== undefined && seVe(centro[0], centro[1])) {
        regiones.push({ clave: codigo, lon: centro[0], lat: centro[1], ataques });
      }
    }
    regiones.sort((a, b) => b.ataques - a.ataques || a.clave.localeCompare(b.clave));
    for (const fila of capa.impactos ?? []) {
      if (seVe(fila[3], fila[4])) impactos.push({ clave: fila[0], lon: fila[3], lat: fila[4], fila });
    }
    impactos.sort((a, b) => b.fila[1] - a.fila[1] || b.clave.localeCompare(a.clave));
    if (capa.satelite) {
      for (const c of capa.ciudadesSinLuz ?? []) {
        if (seVe(c.lon, c.lat)) {
          ciudades.push({ clave: `${c.region}|${c.nombre}`, lon: c.lon, lat: c.lat, clase: "luz", nombre: c.nombre, perdida: c.perdida });
        }
      }
      for (const c of capa.alumbrado ?? []) {
        const { lon, lat } = c.ciudad.punto;
        if (seVe(lon, lat)) {
          ciudades.push({ clave: c.ciudad.id, lon, lat, clase: "alumbrado", nombre: c.ciudad.nombre, perdida: null });
        }
      }
    }
  }
  const celdas: UcraniaALaVista["celdas"] = [];
  if (capa.gnss) {
    for (const celda of capa.celdas ?? []) {
      const [lon, lat] = centroDeCelda(celda);
      if (seVe(lon, lat)) celdas.push({ clave: celda.h3, lon, lat, celda });
    }
    celdas.sort((a, b) => b.celda.proporcion - a.celda.proporcion || a.clave.localeCompare(b.clave));
  }
  return {
    regiones,
    impactos: impactos.slice(0, MAXIMO_EN_TECLADO),
    totalImpactos: impactos.length,
    celdas: celdas.slice(0, MAXIMO_EN_TECLADO),
    totalCeldas: celdas.length,
    ciudades,
  };
}
