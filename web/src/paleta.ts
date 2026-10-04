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
  // Capa de guerra: una familia violeta azulada, lejos del rojo de «confirmado», del naranja
  // de «notificado» y del verde de «al día» también con daltonismo (tests/colores.test.tsx).
  // El principal (regiones de Ucrania, impactos, corredores), uno claro para lo que se resalta
  // (focos de un impacto, focos de 24 horas que coinciden con uno, la cortinilla) y uno apagado
  // para lo secundario (regiones de Rusia, focos de 24 horas, ciudades sin luz).
  guerra: "#9d7bff",
  guerraClaro: "#cbbcff",
  guerraTenue: "#7a6cc0",
} as const;

/** Acento por defecto; la web usa el de la variable --acento de estilos.css. */
export const ACENTO_POR_DEFECTO = "#f4f7fb";

export const COLOR_ESTADO: Record<Estado, string> = {
  notificado: PALETA.notificado,
  confirmado: PALETA.confirmado,
  atribuido: PALETA.atribuido,
  desmentido: PALETA.desmentido,
};

/** Bandera de los atribuidos: el mismo rojo que el confirmado. */
export const COLOR_BANDERA = PALETA.atribuido;

/**
 * Bandera de los atribuidos (en lugar del círculo de los demás, sin nada debajo): un mástil y
 * un paño relleno que ondea, en una caja de `ancho` × `alto` píxeles del mapa. El pie del
 * mástil está en `pie`, que es el punto del incidente; el mástil sube en vertical y el paño
 * sale hacia la derecha desde arriba. La leyenda, las fichas y el pulso usan la misma forma.
 */
export interface FormaBandera {
  ancho: number;
  alto: number;
  pie: readonly [number, number];
  /** Altura del mástil, desde el pie. */
  mastil: number;
  pano: { ancho: number; alto: number; onda: number };
}

/**
 * La bandera del mapa: 28 px de mástil y un paño de 20 × 13, más grande que un círculo de
 * incidente suelto (13 px de diámetro) para que sea lo primero que se ve.
 */
export const BANDERA: FormaBandera = {
  ancho: 30,
  alto: 36,
  pie: [5, 33],
  mastil: 28,
  pano: { ancho: 20, alto: 13, onda: 2 },
};

/** Contorno claro de la bandera: la separa del fondo oscuro y de los círculos vecinos. */
export const CONTORNO_BANDERA = PALETA.texto;
/** Grosor del contorno, por fuera del trazo rojo. */
export const GROSOR_CONTORNO_BANDERA = 1.5;
/** Grosor del mástil. */
export const GROSOR_MASTIL = 2;

/** Trazado SVG del mástil. */
export function trazadoMastil(b: FormaBandera): string {
  const [x, y] = b.pie;
  return `M${x} ${y}V${y - b.mastil}`;
}

/** Trazado SVG del paño: un rectángulo con los bordes de arriba y de abajo ondulados. */
export function trazadoPano(b: FormaBandera): string {
  const x = b.pie[0];
  const arriba = b.pie[1] - b.mastil;
  const { ancho, alto, onda } = b.pano;
  const abajo = arriba + alto;
  const tercio = ancho / 3;
  return (
    `M${x} ${arriba}C${x + tercio} ${arriba - onda} ${x + 2 * tercio} ${arriba + onda} ${x + ancho} ${arriba}` +
    `V${abajo}C${x + 2 * tercio} ${abajo + onda} ${x + tercio} ${abajo - onda} ${x} ${abajo}Z`
  );
}

/** Trazado SVG de la bandera entera: mástil y paño. */
export function trazadoBandera(b: FormaBandera): string {
  return trazadoMastil(b) + trazadoPano(b);
}

/** Gravedad de cada estado para decidir el color de un grupo: manda el más grave. */
export const GRAVEDAD: Record<Estado, number> = {
  desmentido: 0,
  notificado: 1,
  confirmado: 2,
  atribuido: 3,
};

/** Grosor del contorno de los círculos (el discontinuo del desmentido y el borde del relleno). */
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
