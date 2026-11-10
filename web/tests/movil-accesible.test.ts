// Lo que el teléfono y los lectores de pantalla necesitan y no se ve en una prueba de componentes:
// campos de 16 px en pantalla táctil (con menos, Safari del iPhone amplía la página al enfocarlos),
// zonas seguras con la muesca (la app instalada va con viewport-fit=cover), alturas con la barra
// del navegador a la vista, movimiento reducido y la región principal de la página.

import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

const SRC = join(import.meta.dirname, "..", "src");
const leer = (ruta: string): string => readFileSync(join(SRC, ruta), "utf8");

describe("teléfono", () => {
  it("los campos de los filtros y de los avisos miden 16 px en pantalla táctil", () => {
    expect(leer("componentes/Filtros.tsx")).toMatch(/const campo = "[^"]*\btactil:text-base\b[^"]*"/);
    expect(leer("componentes/Avisos.tsx")).toMatch(/const CAMPO = "[^"]*\btactil:text-base\b[^"]*"/);
  });

  it("la metodología, la barra y las páginas de texto respetan la muesca y la barra de gestos", () => {
    const metodologia = leer("componentes/Metodologia.tsx");
    expect(metodologia).toContain("pt-[env(safe-area-inset-top)]");
    expect(metodologia).toContain("pb-[env(safe-area-inset-bottom)]");
    const cabecera = leer("componentes/Cabecera.tsx");
    expect(cabecera).toContain("pl-[max(0.75rem,env(safe-area-inset-left))]");
    expect(cabecera).toContain("pr-[max(0.25rem,env(safe-area-inset-right))]");
    const estilos = leer("estilos.css");
    const texto = estilos.slice(estilos.indexOf("\n.texto-pagina {"));
    const regla = texto.slice(0, texto.indexOf("}"));
    for (const lado of ["right", "bottom", "left"]) expect(regla).toContain(`env(safe-area-inset-${lado})`);
  });

  it("ninguna altura máxima se mide con la barra del navegador escondida (vh)", () => {
    for (const fichero of ["componentes/Ayuda.tsx", "componentes/BotonesMapa.tsx"]) {
      expect(leer(fichero), fichero).not.toMatch(/max-h-\[\d+vh\]/);
    }
  });
});

describe("accesibilidad", () => {
  it("el mapa es la región principal de la página", () => {
    const app = leer("App.tsx");
    expect(app).toContain('<main id="mapa" tabIndex={-1}');
    expect(app.match(/<main\b/g)).toHaveLength(1);
  });

  it("ningún desplazamiento suave sin mirar si el sistema pide menos movimiento", () => {
    expect(leer("componentes/InstalarApp.tsx")).toContain('behavior: movimientoReducido() ? "auto" : "smooth"');
  });
});
