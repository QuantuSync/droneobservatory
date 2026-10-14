// Las zonas de lanzamiento de los partes en el idioma de la página. Los partes de la Fuerza Aérea
// de Ucrania las escriben en ucraniano y la publicación da su nombre normalizado
// (proceso/zonas_lanzamiento.py); configuracion/zonas_lanzamiento_nombres.json da cómo se
// escribe cada una en español y en inglés. La ficha nunca enseña el nombre del parte en otra
// escritura (un test comprueba que todas las zonas de la tabla lo tienen).

import tabla from "../../../configuracion/zonas_lanzamiento_nombres.json" with { type: "json" };
import type { Idioma } from "../sitio.ts";

interface Entrada {
  nombre: string;
  es: string;
  en: string;
}

const NOMBRES: ReadonlyMap<string, Entrada> = new Map(
  [...(tabla.zonas as Entrada[]), ...(tabla.direcciones as Entrada[])].map((e) => [e.nombre, e]),
);

/** El nombre de la zona en el idioma de la página; el del parte solo si no está en la tabla. */
export function zonaLanzamientoEscrita(nombre: string, idioma: Idioma): string {
  return NOMBRES.get(nombre)?.[idioma] ?? nombre;
}

/** Las zonas normalizadas que conoce la tabla (para los tests). */
export function zonasConocidas(): string[] {
  return [...NOMBRES.keys()];
}
