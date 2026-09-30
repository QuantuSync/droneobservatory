// Rutas de la web: «/» y «/en» para los dos idiomas, y una ruta propia por incidente y por
// ataque de la capa de Ucrania (/EODI-AAAA-NNNNN, /EODI-UA-AAAA-NNNN y sus versiones /en/…).

import { PATRON_ID_ATAQUE, PATRON_ID_INCIDENTE } from "./datos/vocabulario.ts";
import { PREFIJO_EN } from "./sitio.ts";
import type { Idioma } from "./sitio.ts";

export type Ficha = { clase: "incidente"; id: string } | { clase: "ataque"; id: string };

export interface Ruta {
  idioma: Idioma;
  ficha: Ficha | null;
}

export function fichaDeId(id: string): Ficha | null {
  if (PATRON_ID_INCIDENTE.test(id)) return { clase: "incidente", id };
  if (PATRON_ID_ATAQUE.test(id)) return { clase: "ataque", id };
  return null;
}

export function analizarRuta(ruta: string): Ruta {
  const segmentos = ruta.split("/").filter((s) => s.length > 0);
  const enIngles = `/${segmentos[0] ?? ""}` === PREFIJO_EN;
  const resto = enIngles ? segmentos.slice(1) : segmentos;
  const id = resto.length === 1 ? resto[0] : undefined;
  return {
    idioma: enIngles ? "en" : "es",
    ficha: id === undefined ? null : fichaDeId(id),
  };
}
