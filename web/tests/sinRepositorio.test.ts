// La web no enlaza al repositorio del código, en ningún idioma: dice que el código es abierto,
// con la licencia Apache-2.0, sin enlace.
import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

import { en } from "../src/i18n/en.ts";
import { es } from "../src/i18n/es.ts";
import { paginaServicio } from "../src/texto/paginas.ts";
import { PAGINAS_SERVICIO } from "../src/texto/servicio.ts";
import { textosPagina } from "../src/texto/textos.ts";

const SRC = join(import.meta.dirname, "..", "src");

function ficheros(carpeta: string): string[] {
  return readdirSync(carpeta, { withFileTypes: true }).flatMap((e) =>
    e.isDirectory() ? ficheros(join(carpeta, e.name)) : [join(carpeta, e.name)],
  );
}

describe("sin enlaces al repositorio", () => {
  it("ningún fichero de la web lleva la dirección del repositorio", () => {
    for (const fichero of ficheros(SRC)) {
      expect(readFileSync(fichero, "utf-8"), fichero).not.toMatch(/github\.com\/QuantuSync/i);
    }
  });

  it("la licencia del código se dice sin enlace, en español y en inglés", () => {
    for (const [t, idioma] of [[es, "es"], [en, "en"]] as const) {
      const licencias = JSON.stringify(t.metodologia.secciones.find((s) => s.id === "licencias"));
      expect(licencias).toContain("Apache-2.0");
      expect(licencias).not.toMatch(/github\.com\/QuantuSync/i);
      const legal = PAGINAS_SERVICIO.map((nombre) => paginaServicio(nombre, idioma).cuerpo.toString()).join(" ");
      expect(legal).toContain("Apache-2.0");
      expect(legal).not.toMatch(/github\.com\/QuantuSync/i);
      expect(textosPagina(idioma).codigo).toContain("Apache-2.0");
    }
  });
});
