// Páginas de servicio público (aviso legal, privacidad, independencia, correcciones y
// accesibilidad), la licencia dentro de los ficheros descargables y en llms.txt.

import { describe, expect, it } from "vitest";

import { conLicencia, metadatosLicencia } from "../src/datos/licencia.ts";
import type { Resumen } from "../src/datos/tipos.ts";
import { LICENCIA_DATOS_URL } from "../src/sitio.ts";
import { html } from "../src/texto/html.ts";
import { marco } from "../src/texto/paginas.ts";
import { llmsTxt } from "../src/texto/salidas.ts";
import { CONTACTO, PAGINAS_SERVICIO, RESPONSABLE, RUTAS_SERVICIO, textoServicio } from "../src/texto/servicio.ts";

const ACTUALIZADO = "2026-10-08T12:17Z";

function todoElTexto(pagina: (typeof PAGINAS_SERVICIO)[number], idioma: "es" | "en"): string {
  return JSON.stringify(textoServicio(pagina, idioma));
}

describe("páginas de servicio público", () => {
  it("existen en los dos idiomas con las mismas secciones", () => {
    for (const pagina of PAGINAS_SERVICIO) {
      const es = textoServicio(pagina, "es");
      const en = textoServicio(pagina, "en");
      expect(es.secciones.map((s) => s.id)).toEqual(en.secciones.map((s) => s.id));
      expect(RUTAS_SERVICIO[pagina].en.startsWith("/en/")).toBe(true);
      expect(RUTAS_SERVICIO[pagina].es.startsWith("/en/")).toBe(false);
    }
  });

  it("el aviso legal da el responsable y el contacto; correcciones y privacidad, el correo", () => {
    for (const idioma of ["es", "en"] as const) {
      const aviso = todoElTexto("avisoLegal", idioma);
      expect(aviso).toContain(RESPONSABLE);
      expect(aviso).toContain(CONTACTO);
      expect(todoElTexto("correcciones", idioma)).toContain(CONTACTO);
      expect(todoElTexto("privacidad", idioma)).toContain("eodi.ultima-visita");
    }
  });

  it("no hablan de límites ni nombran otros proyectos", () => {
    for (const pagina of PAGINAS_SERVICIO) {
      for (const idioma of ["es", "en"] as const) {
        expect(todoElTexto(pagina, idioma)).not.toMatch(/l[ií]mite|limitaci|limitation|\blimits?\b/i);
      }
    }
  });

  it("el pie de cada página de texto enlaza las cinco", () => {
    const pagina = {
      idioma: "en" as const,
      rutas: { es: "/ayuda", en: "/en/help" },
      titulo: "t",
      descripcion: "d",
      cuerpo: html("x"),
      estructurados: [],
      conMapa: false,
      modificada: ACTUALIZADO,
    };
    const texto = marco(pagina, ACTUALIZADO).toString();
    for (const p of PAGINAS_SERVICIO) expect(texto).toContain(`href="${RUTAS_SERVICIO[p].en}"`);
  });
});

describe("licencia de los datos abiertos", () => {
  it("va como primer miembro de cada JSON sin cambiar el resto", () => {
    const original = { type: "FeatureCollection", features: [{ id: "x" }], unidos: {} };
    const conElla = JSON.parse(conLicencia(JSON.stringify(original), ACTUALIZADO)) as Record<string, unknown>;
    expect(Object.keys(conElla)[0]).toBe("licencia");
    const { licencia, ...resto } = conElla;
    expect(resto).toEqual(original);
    expect(licencia).toEqual(metadatosLicencia(ACTUALIZADO));
    expect(metadatosLicencia(ACTUALIZADO).url).toBe(LICENCIA_DATOS_URL);
    expect(metadatosLicencia(ACTUALIZADO).alcance.es).toContain("ODbL");
  });

  it("llms.txt dice la licencia, cómo citar y enlaza las páginas nuevas", () => {
    const resumen: Resumen = { actualizado: ACTUALIZADO, incidentes: [], episodios: [], eventos: [] };
    const texto = llmsTxt(resumen);
    expect(texto).toContain(LICENCIA_DATOS_URL);
    expect(texto).toMatch(/How to cite: European Observatory of Drone Incidents/);
    expect(texto).toMatch(/Cómo citar: European Observatory of Drone Incidents/);
    for (const p of PAGINAS_SERVICIO) {
      expect(texto).toContain(RUTAS_SERVICIO[p].es);
      expect(texto).toContain(RUTAS_SERVICIO[p].en);
    }
  });
});
