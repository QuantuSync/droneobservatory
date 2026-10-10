// Lo seleccionado se ve igual en toda la web: una sola regla en estilos.css, fuera de las capas
// (ninguna utilidad de color la tapa), para todo control conmutado, y el paso del ratón solo donde
// hay ratón (en una pantalla táctil se quedaba pegado al control tocado y tapaba su estado).
import { readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

const raiz = join(import.meta.dirname, "..", "src");
const css = readFileSync(join(raiz, "estilos.css"), "utf-8");

function luminancia(hex: string): number {
  const canales = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255);
  const [r, g, b] = canales.map((c) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4)) as [number, number, number];
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}
function contraste(a: string, b: string): number {
  const [l1, l2] = [luminancia(a), luminancia(b)].sort((x, y) => y - x) as [number, number];
  return (l1 + 0.05) / (l2 + 0.05);
}
const color = (nombre: string) => css.match(new RegExp(`${nombre}:\\s*(#[0-9a-f]{6})`, "i"))?.[1] ?? "";

/** Las reglas fuera de @layer (las de nivel superior que no son @theme, @layer ni @media). */
function fueraDeCapas(): string {
  let profundidad = 0;
  let fuera = "";
  let dentroDeCapa = false;
  for (let i = 0; i < css.length; i += 1) {
    const c = css[i];
    if (profundidad === 0 && css.startsWith("@layer", i)) dentroDeCapa = true;
    if (c === "{") profundidad += 1;
    if (c === "}") {
      profundidad -= 1;
      if (profundidad === 0) dentroDeCapa = false;
    }
    if (!dentroDeCapa) fuera += c;
  }
  return fuera;
}

describe("selección común", () => {
  it("una sola regla de seleccionado, fuera de las capas, para todos los estados ARIA", () => {
    const fuera = fueraDeCapas();
    for (const estado of ['[aria-pressed="true"]', '[aria-checked="true"]', '[aria-selected="true"]', '[aria-expanded="true"]', "[data-activo]"]) {
      expect(fuera).toContain(estado);
    }
    expect(fuera).toContain("details[open] > summary.control");
    // Sin parches por componente.
    expect(css).not.toMatch(/\[data-filtros\] \.control\[/);
    expect(css).not.toContain("box-shadow: inset 0 0 0 1px var(--color-linea)");
  });

  it("el paso del ratón de los controles solo con ratón", () => {
    const sinMedia = css.replace(/@media \(hover: hover\) \{[\s\S]*?\n {0,2}\}\n/g, "");
    expect(sinMedia).not.toMatch(/\.control:hover/);
    expect(sinMedia).not.toMatch(/\.control-principal:hover/);
  });

  it("contraste: 3:1 entre activo e inactivo y 4,5:1 del texto en cada uno", () => {
    const [acento, fondo, panel, secundario, texto] = [
      color("--acento"),
      color("--color-fondo"),
      color("--color-panel-solido"),
      color("--color-secundario"),
      color("--color-texto"),
    ];
    expect(contraste(acento, panel)).toBeGreaterThanOrEqual(3);
    expect(contraste(acento, fondo)).toBeGreaterThanOrEqual(3);
    expect(contraste(fondo, acento)).toBeGreaterThanOrEqual(4.5);
    expect(contraste(fondo, texto)).toBeGreaterThanOrEqual(4.5);
    expect(contraste(secundario, panel)).toBeGreaterThanOrEqual(4.5);
  });

  it("ningún componente vuelve a pintar a mano lo seleccionado", () => {
    const componentes = join(raiz, "componentes");
    for (const fichero of readdirSync(componentes)) {
      const codigo = readFileSync(join(componentes, fichero), "utf-8");
      expect(codigo, fichero).not.toMatch(/aria-pressed=\{[^}]*\}[^>]*className=\{[^}]*\? "[^"]*bg-acento/);
      expect(codigo, fichero).not.toContain("campoActivo");
    }
  });
});
