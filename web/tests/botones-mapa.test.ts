// Los botones sobre el mapa llevan el fondo de los paneles: sin él, «Filtros» y «Europa ahora»
// se leían mezclados con los nombres del mapa en el escritorio.
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

const raiz = join(import.meta.dirname, "..", "src");

describe("botones sobre el mapa", () => {
  it("tienen fondo de panel, declarado después de .control", () => {
    const css = readFileSync(join(raiz, "estilos.css"), "utf-8");
    const control = css.indexOf("  .control {");
    const boton = css.indexOf(".control.boton-mapa {");
    expect(control).toBeGreaterThan(-1);
    expect(boton).toBeGreaterThan(control);
    expect(css.slice(boton, css.indexOf("}", boton))).toContain("background-color: var(--color-panel-solido)");
    const componente = readFileSync(join(raiz, "componentes", "BotonesMapa.tsx"), "utf-8");
    expect(componente).toMatch(/CLASE_BOTON = "[^"]*\bboton-mapa\b/);
  });

  it("todo lo que se abre sobre el mapa tiene fondo opaco", () => {
    const css = readFileSync(join(raiz, "estilos.css"), "utf-8");
    // Seis cifras hexadecimales: sin canal alfa.
    expect(css).toMatch(/--color-panel-solido:\s*#[0-9a-f]{6};/i);
    for (const selector of [".flotante {", ".superficie {", ".control.boton-mapa {"]) {
      const inicio = css.indexOf(selector);
      expect(inicio, selector).toBeGreaterThan(-1);
      const bloque = css.slice(inicio, css.indexOf("}", inicio));
      expect(bloque, selector).toContain("background-color: var(--color-panel-solido)");
    }
    // Ningún fondo semitransparente que se pueda poner a un panel.
    expect(css).not.toMatch(/--color-panel:/);
    expect(css).not.toMatch(/backdrop-filter/);
  });
});
