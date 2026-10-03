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
    expect(css.slice(boton, css.indexOf("}", boton))).toContain("background-color: var(--color-panel)");
    const componente = readFileSync(join(raiz, "componentes", "BotonesMapa.tsx"), "utf-8");
    expect(componente).toMatch(/CLASE_BOTON = "[^"]*\bboton-mapa\b/);
  });
});
