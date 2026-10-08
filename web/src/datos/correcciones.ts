// Registro público de correcciones (correcciones.json, exportacion/correcciones.py): cada
// corrección de un incidente ya publicado, con su fecha, lo que cambió y su motivo en los dos
// idiomas. De él salen la página del registro (src/texto/correcciones.ts) y la línea «Corregido
// el…» de cada ficha.

import type { Estado, PresenciaDron } from "./tipos.ts";

export interface LugarCorregido {
  pais: string | null;
  nombre?: string;
}

export type CambioCorregido =
  | { campo: "titulo"; antes: { es: string; en: string } | null; despues: { es: string; en: string } | null }
  | { campo: "estado"; antes: Estado | null; despues: Estado | null }
  | { campo: "presencia_dron"; antes: PresenciaDron | null; despues: PresenciaDron | null }
  | { campo: "lugar"; antes: LugarCorregido | null; despues: LugarCorregido | null }
  | { campo: "atribucion"; retirada: boolean }
  | { campo: "union"; destino: string }
  | { campo: "retirada" };

export interface Correccion {
  /** Cuándo se hizo (UTC, al minuto). */
  fecha: string;
  incidente: string;
  /** El incidente que se publica en su lugar (él mismo o aquel en que está unido); null si está retirado. */
  enlace: string | null;
  titulo?: { es: string; en: string };
  cambios: CambioCorregido[];
  motivo: { es: string; en: string };
  /** Revisión hecha a mano o regla de revisión aplicada a lo ya publicado. */
  revision: "a_mano" | "regla";
  a_raiz_de_un_aviso?: true;
}

export interface RegistroCorrecciones {
  version: 1;
  /** La fecha de la corrección más reciente; null si no hay ninguna. */
  actualizado: string | null;
  correcciones: Correccion[];
}

/** La página del registro de correcciones (src/texto/correcciones.ts). */
export const RUTAS_REGISTRO = {
  es: "/correcciones/registro",
  en: "/en/corrections/log",
} as const;

/** La dirección de la entrada más reciente de un incidente en el registro. */
export function enlaceACorreccion(id: string, idioma: "es" | "en"): string {
  return `${RUTAS_REGISTRO[idioma]}#${anclaDeCorreccion(id)}`;
}

/** El ancla de la entrada más reciente de cada incidente publicado en la página del registro. */
export function anclaDeCorreccion(id: string): string {
  return `corregido-${id}`;
}

/**
 * La fecha de la corrección más reciente de cada incidente publicado (el registro va de la más
 * reciente a la más antigua): la que enseña su ficha.
 */
export function ultimasCorrecciones(registro: RegistroCorrecciones): Map<string, string> {
  const ultimas = new Map<string, string>();
  for (const c of registro.correcciones) {
    if (c.enlace === null) continue;
    const anterior = ultimas.get(c.enlace);
    if (anterior === undefined || c.fecha > anterior) ultimas.set(c.enlace, c.fecha);
  }
  return ultimas;
}
