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
  // es un confirmado con responsable señalado: su aro rojo lleva dentro la bandera del país).
  // Se distinguen por luminancia, no solo por tono, para que se separen también con
  // daltonismo (test en tests/colores.test.ts).
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

/**
 * Marcador de los atribuidos, igual en el mapa, la ficha, la lista, la leyenda y los filtros: un
 * círculo con un aro grueso en el rojo de «confirmado» y, dentro, la bandera del país al que la
 * autoridad lo atribuye recortada en círculo (relleno rojo liso si no hay país o no hay
 * bandera), separada del aro por un filo fino y oscuro. Atribuido a una persona: además, un
 * punto fijo y oscuro en el centro, con un aro rojo fino. Por fuera, un filo del color del
 * fondo lo separa de los círculos vecinos, como a ellos. Medidas en píxeles, desde el centro:
 * 23 px de diámetro (24,5 con el filo de fuera), entre el círculo suelto (13 px) y el grupo más
 * pequeño (25 px).
 */
export const MARCA_ATRIBUIDO = {
  /** Borde exterior del aro rojo. */
  radio: 11.5,
  /** Grosor del aro rojo. */
  aro: 3,
  /** Filo oscuro entre el aro y la bandera. */
  filo: 1,
  /** Filo del color del fondo por fuera del aro. */
  halo: 0.75,
  /** Radio del punto de «persona» y grosor de su aro rojo. */
  punto: 2.5,
  aroPunto: 1,
} as const;

/** Radio de la bandera recortada: lo que queda dentro del aro y del filo (15 px de diámetro). */
export const RADIO_BANDERA = MARCA_ATRIBUIDO.radio - MARCA_ATRIBUIDO.aro - MARCA_ATRIBUIDO.filo;
/** El aro, el relleno liso y el aro del punto: el rojo de «confirmado». */
export const COLOR_ARO_ATRIBUIDO = PALETA.atribuido;
/** El filo entre el aro y la bandera, el de fuera y el punto: el fondo del mapa. */
export const COLOR_FILO_ATRIBUIDO = PALETA.fondo;

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
