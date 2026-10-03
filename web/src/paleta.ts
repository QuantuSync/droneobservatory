// Colores que necesitan el mapa y los símbolos fuera de la hoja de estilos. Un test
// comprueba que coinciden con los de estilos.css y que cumplen el contraste AA.

import type { Estado } from "./datos/tipos.ts";

export const PALETA = {
  fondo: "#060a12",
  panelSolido: "#0b111d",
  elevado: "#131c2c",
  linea: "#1f2b3f",
  texto: "#e8eef6",
  secundario: "#93a0b4",
  // Estados de un incidente: naranja lo notificado, rojo lo confirmado (y lo atribuido, que
  // es un confirmado con responsable señalado: lleva además una bandera). Se distinguen por
  // luminancia, no solo por tono, para que se separen también con daltonismo (test en
  // tests/colores.test.ts).
  notificado: "#ff9a2e",
  confirmado: "#f53a50",
  atribuido: "#f53a50",
  desmentido: "#93a0b4",
  // El verde solo dice que el sistema funciona (datos al día, en la barra de estado).
  alDia: "#56c271",
  // Capa de guerra: su propio rojo coral, distinto del rojo de los estados.
  guerra: "#f25c4f",
} as const;

/** Acento por defecto; la web usa el de la variable --acento de estilos.css. */
export const ACENTO_POR_DEFECTO = "#f4f7fb";

export const COLOR_ESTADO: Record<Estado, string> = {
  notificado: PALETA.notificado,
  confirmado: PALETA.confirmado,
  atribuido: PALETA.atribuido,
  desmentido: PALETA.desmentido,
};

/** Bandera de los atribuidos: el mismo rojo, con un borde del color del fondo que la separa
 *  de la forma del símbolo. */
export const COLOR_BANDERA = PALETA.atribuido;

/** Gravedad de cada estado para decidir el color de un grupo: manda el más grave. */
export const GRAVEDAD: Record<Estado, number> = {
  desmentido: 0,
  notificado: 1,
  confirmado: 2,
  atribuido: 3,
};

/** Relleno del color de estado a baja opacidad, con contorno del mismo color. */
export const OPACIDAD_RELLENO = 0.25;
export const GROSOR_CONTORNO = 1.2;
/** El desmentido no lleva relleno: solo contorno discontinuo. */
export const TRAZO_DESMENTIDO: readonly [number, number] = [3, 2];

/** Opacidades del relleno de las regiones de Ucrania, de menos a más ataques. */
export const ESCALA_UCRANIA: readonly number[] = [0.12, 0.27, 0.42, 0.57, 0.72];

/** El acento vigente: el de la variable CSS si hay documento, o el de por defecto. */
export function acento(): string {
  if (typeof document === "undefined") return ACENTO_POR_DEFECTO;
  const valor = getComputedStyle(document.documentElement).getPropertyValue("--acento").trim();
  return valor.length > 0 ? valor : ACENTO_POR_DEFECTO;
}

function canal(hex: string, inicio: number): number {
  const valor = parseInt(hex.slice(inicio, inicio + 2), 16) / 255;
  return valor <= 0.03928 ? valor / 12.92 : ((valor + 0.055) / 1.055) ** 2.4;
}

/** Luminancia relativa de un color #rrggbb (WCAG 2.1). */
export function luminancia(hex: string): number {
  return 0.2126 * canal(hex, 1) + 0.7152 * canal(hex, 3) + 0.0722 * canal(hex, 5);
}

/** Razón de contraste entre dos colores #rrggbb (WCAG 2.1). */
export function contraste(a: string, b: string): number {
  const [clara, oscura] = [luminancia(a), luminancia(b)].sort((x, y) => y - x) as [number, number];
  return (clara + 0.05) / (oscura + 0.05);
}
