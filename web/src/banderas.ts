// Banderas del marcador de los atribuidos: las de web/public/banderas (flag-icons, MIT,
// versión cuadrada), servidas por la propia web. Son los países de
// configuracion/paises_atribucion.json, los únicos cuyo nombre o gentilicio se comprueba en la
// frase de la autoridad (un test lo compara). Un país sin bandera aquí lleva el marcador sin
// bandera: el aro rojo con relleno rojo liso.

import type { AtribucionResumen } from "./datos/tipos.ts";

export const BANDERAS = [
  "AD", "AL", "AT", "BA", "BE", "BG", "BY", "CH", "CY", "CZ", "DE", "DK", "EE", "ES", "FI", "FR",
  "GB", "GR", "HR", "HU", "IE", "IR", "IS", "IT", "LI", "LT", "LU", "LV", "MC", "MD", "ME", "MK",
  "MT", "NL", "NO", "PL", "PT", "RO", "RS", "RU", "SE", "SI", "SK", "SM", "TR", "UA", "VA", "XK",
] as const;

const INDICE = new Map<string, number>(BANDERAS.map((pais, i) => [pais, i]));

/** Posición de la bandera de un país en la lista, o -1 si no tiene. */
export function indiceBandera(pais: string | null | undefined): number {
  return pais === null || pais === undefined ? -1 : (INDICE.get(pais) ?? -1);
}

export function urlBandera(pais: string): string {
  return `/banderas/${pais.toLowerCase()}.svg`;
}

/** Cómo se dibuja un atribuido: con la bandera de un país (o sin bandera) y con o sin punto. */
export interface VarianteAtribuido {
  /** País cuya bandera va dentro del aro; null, relleno rojo liso. */
  bandera: string | null;
  /** Atribuido a una persona: lleva el punto fijo en el centro. */
  persona: boolean;
}

export const VARIANTE_LISA: VarianteAtribuido = { bandera: null, persona: false };

/** La variante de un atribuido. Sin tipo (datos anteriores al esquema 1.10.0), la lisa. */
export function varianteDe(atribucion: AtribucionResumen | null): VarianteAtribuido {
  const pais = atribucion?.pais ?? null;
  return {
    bandera: indiceBandera(pais) >= 0 ? pais : null,
    persona: atribucion?.tipo === "persona",
  };
}

/**
 * Varios atribuidos en un solo marcador: si todos llevan la misma bandera (o ninguna), esa,
 * con el punto solo si todos son personas; si son de países distintos, la lisa. La misma regla
 * que aplica el mapa a sus grupos (estilo.ts).
 */
export function varianteConjunta(variantes: readonly VarianteAtribuido[]): VarianteAtribuido {
  const [primera, ...resto] = variantes;
  if (primera === undefined) return VARIANTE_LISA;
  if (resto.some((v) => v.bandera !== primera.bandera)) return VARIANTE_LISA;
  return { bandera: primera.bandera, persona: variantes.every((v) => v.persona) };
}

/** Prefijo de los iconos del mapa: «atribuido-<índice de la bandera o -1>[-p]». */
export const PREFIJO_ICONO_ATRIBUIDO = "atribuido-";
export const SUFIJO_PERSONA = "-p";

export function nombreIconoAtribuido(variante: VarianteAtribuido): string {
  return `${PREFIJO_ICONO_ATRIBUIDO}${indiceBandera(variante.bandera)}${variante.persona ? SUFIJO_PERSONA : ""}`;
}
