// Las banderas del marcador de los atribuidos: los ficheros servidos, la lista de la web y la
// tabla de países de la regla de atribución (configuracion/paises_atribucion.json) son los
// mismos países.
import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import { BANDERAS, indiceBandera, urlBandera, varianteDe } from "../src/banderas.ts";
import { GENTILICIOS } from "../src/i18n/gentilicios.ts";

const WEB = join(import.meta.dirname, "..");
const DIRECTORIO = join(WEB, "public", "banderas");

describe("banderas", () => {
  it("una por país de la regla de atribución, servidas por la propia web", () => {
    const tabla = JSON.parse(
      readFileSync(join(WEB, "..", "configuracion", "paises_atribucion.json"), "utf8"),
    ) as { paises: Record<string, unknown> };
    expect([...BANDERAS]).toEqual(Object.keys(tabla.paises).sort());
    const ficheros = readdirSync(DIRECTORIO).filter((f) => f.endsWith(".svg"));
    expect(ficheros.sort()).toEqual(BANDERAS.map((p) => `${p.toLowerCase()}.svg`).sort());
    expect(Object.keys(GENTILICIOS).sort()).toEqual([...BANDERAS]);
    expect(readdirSync(DIRECTORIO)).toContain("LICENSE.txt");
  });

  it("cuadradas y con tamaño propio, para dibujarlas en el lienzo del mapa en cualquier navegador", () => {
    for (const pais of BANDERAS) {
      const svg = readFileSync(join(WEB, "public", urlBandera(pais)), "utf8");
      expect(svg, pais).toMatch(/^<svg width="512" height="512" [^>]*viewBox="0 0 512 512"/);
      // Nada que cargar de fuera.
      expect(svg, pais).not.toMatch(/(href|src)="https?:/);
    }
  });

  it("un país sin bandera en el juego, o sin país, no lleva bandera", () => {
    expect(indiceBandera("US")).toBe(-1);
    expect(indiceBandera(null)).toBe(-1);
    expect(varianteDe({ tipo: "estado", pais: "US" })).toEqual({ bandera: null, persona: false });
    expect(varianteDe({ tipo: "persona", pais: null })).toEqual({ bandera: null, persona: true });
    expect(varianteDe({ tipo: "estado", pais: "RU" })).toEqual({ bandera: "RU", persona: false });
  });
});
