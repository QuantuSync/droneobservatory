// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";

import {
  CONSULTA_CON_RATON,
  MARGEN_LETRERO_PX,
  SEPARACION_LETRERO_PX,
  colocarLetrero,
  hayRaton,
} from "../src/mapa/letrero.ts";

const AREA = { ancho: 1000, alto: 700 };
const LETRERO = { ancho: 288, alto: 36 };

afterEach(() => vi.unstubAllGlobals());

describe("letrero del mapa", () => {
  it("va abajo a la derecha del cursor si cabe", () => {
    expect(colocarLetrero({ x: 100, y: 100 }, LETRERO, AREA)).toEqual({
      x: 100 + SEPARACION_LETRERO_PX,
      y: 100 + SEPARACION_LETRERO_PX,
    });
  });

  it("junto al borde derecho o al de abajo pasa al otro lado del cursor", () => {
    const { x, y } = colocarLetrero({ x: 950, y: 690 }, LETRERO, AREA);
    expect(x).toBe(950 - SEPARACION_LETRERO_PX - LETRERO.ancho);
    expect(y).toBe(690 - SEPARACION_LETRERO_PX - LETRERO.alto);
  });

  it("nunca se sale del mapa, ni con un letrero más ancho que el hueco", () => {
    for (const cursor of [
      { x: 0, y: 0 },
      { x: 999, y: 699 },
      { x: 150, y: 20 },
    ]) {
      const { x, y } = colocarLetrero(cursor, LETRERO, AREA);
      expect(x).toBeGreaterThanOrEqual(MARGEN_LETRERO_PX);
      expect(y).toBeGreaterThanOrEqual(MARGEN_LETRERO_PX);
      expect(x + LETRERO.ancho).toBeLessThanOrEqual(AREA.ancho - MARGEN_LETRERO_PX);
      expect(y + LETRERO.alto).toBeLessThanOrEqual(AREA.alto - MARGEN_LETRERO_PX);
    }
    expect(colocarLetrero({ x: 100, y: 50 }, { ancho: 400, alto: 36 }, { ancho: 300, alto: 700 }).x).toBe(
      MARGEN_LETRERO_PX,
    );
  });

  it("solo hay letrero con ratón: en una pantalla táctil no", () => {
    vi.stubGlobal("matchMedia", (consulta: string) => ({ matches: consulta !== CONSULTA_CON_RATON }));
    expect(hayRaton()).toBe(false);
    vi.stubGlobal("matchMedia", (consulta: string) => ({ matches: consulta === CONSULTA_CON_RATON }));
    expect(hayRaton()).toBe(true);
  });
});
