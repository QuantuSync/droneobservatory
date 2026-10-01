// Letrero de ayuda al pasar el ratón por un símbolo (tipo · estado · título). Solo tiene
// sentido con un ratón: en una pantalla táctil no hay «pasar por encima», el toque abre la
// ficha directamente y el letrero no se muestra nunca.

/** Hay ratón (o algo que sabe pasar por encima con precisión). */
export const CONSULTA_CON_RATON = "(hover: hover) and (pointer: fine)";

/** Separación del letrero respecto al cursor y margen que deja con los bordes. */
export const SEPARACION_LETRERO_PX = 14;
export const MARGEN_LETRERO_PX = 8;

export function hayRaton(): boolean {
  return (
    typeof window !== "undefined" &&
    typeof window.matchMedia === "function" &&
    window.matchMedia(CONSULTA_CON_RATON).matches
  );
}

interface Medidas {
  ancho: number;
  alto: number;
}

/**
 * Dónde va el letrero: abajo a la derecha del cursor; si no cabe, al otro lado; y en todo
 * caso dentro del mapa, con un margen.
 */
export function colocarLetrero(
  cursor: { x: number; y: number },
  letrero: Medidas,
  area: Medidas,
): { x: number; y: number } {
  const eje = (posicion: number, tamano: number, limite: number) => {
    let inicio = posicion + SEPARACION_LETRERO_PX;
    if (inicio + tamano > limite - MARGEN_LETRERO_PX) inicio = posicion - SEPARACION_LETRERO_PX - tamano;
    const maximo = Math.max(MARGEN_LETRERO_PX, limite - MARGEN_LETRERO_PX - tamano);
    return Math.min(Math.max(inicio, MARGEN_LETRERO_PX), maximo);
  };
  return { x: eje(cursor.x, letrero.ancho, area.ancho), y: eje(cursor.y, letrero.alto, area.alto) };
}
