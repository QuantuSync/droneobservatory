// Los créditos del autor son los mismos en la web (src/sitio.ts) y en la configuración que los mete
// en cada fichero publicado (configuracion/licencia_datos.json, recogida/licencia.py).

import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

import { AUTOR_DATOS, metadatosLicencia } from "../src/datos/licencia.ts";
import { AUTOR_FIRMA, AUTOR_NOMBRE, CORREO_AUTOR, ORCID_URL, autorEstructurado, citaRecomendada } from "../src/sitio.ts";
import { html } from "../src/texto/html.ts";
import { marco, paginaServicio } from "../src/texto/paginas.ts";
import type { PaginaTexto } from "../src/texto/paginas.ts";
import { CONTACTO } from "../src/texto/servicio.ts";

const RAIZ = join(import.meta.dirname, "..", "..");
const configuracion = JSON.parse(readFileSync(join(RAIZ, "configuracion", "licencia_datos.json"), "utf-8")) as {
  autor: { nombre: string; firma: { es: string; en: string }; orcid: string; correo: string };
  cita: { es: string; en: string };
};

describe("créditos del autor", () => {
  it("coinciden con configuracion/licencia_datos.json", () => {
    expect(AUTOR_DATOS).toEqual(configuracion.autor);
    expect(AUTOR_NOMBRE).toBe(configuracion.autor.nombre);
    expect(AUTOR_FIRMA).toEqual(configuracion.autor.firma);
    expect(ORCID_URL).toBe(configuracion.autor.orcid);
    expect(CORREO_AUTOR).toBe(configuracion.autor.correo);
    expect(CONTACTO).toBe(CORREO_AUTOR);
    for (const idioma of ["es", "en"] as const) {
      const esperada = configuracion.cita[idioma].replace("{anio}", "2026").replace("{version}", "2026-11");
      expect(citaRecomendada("2026-11", idioma)).toBe(esperada);
    }
  });

  it("los textos exactos del autor", () => {
    expect(AUTOR_FIRMA.es).toBe("Dr. Lucas Alaniz Pintos");
    expect(AUTOR_FIRMA.en).toBe("Lucas Alaniz Pintos, PhD");
    expect(ORCID_URL).toBe("https://orcid.org/0009-0008-5179-2534");
  });

  it("la descarga lleva autor, ORCID, licencia, cita y dirección", () => {
    const m = metadatosLicencia("2026-12-31T23:30:00Z");
    expect(m.autor.orcid).toBe(ORCID_URL);
    expect(m.cita.es).toContain("Versión 2026-12.");
    expect(m.fuente).toBe("https://droneobservatory.eu/");
  });

  it("schema.org: el autor como persona con su ORCID", () => {
    const persona = autorEstructurado();
    expect(persona["@type"]).toBe("Person");
    expect(persona.sameAs).toEqual([ORCID_URL]);
    expect(persona.identifier).toEqual({ "@type": "PropertyValue", propertyID: "ORCID", value: "0009-0008-5179-2534" });
  });
});

describe("créditos en las páginas de texto (sin código)", () => {
  it("el pie de todas las páginas lleva autor, ORCID enlazado y contacto, en los dos idiomas", () => {
    for (const idioma of ["es", "en"] as const) {
      const pagina: PaginaTexto = {
        idioma,
        rutas: { es: "/ayuda", en: "/en/help" },
        titulo: "t",
        descripcion: "d",
        cuerpo: html("x"),
        estructurados: [],
        conMapa: false,
        modificada: "2026-10-09T10:17Z",
      };
      const texto = marco(pagina, "2026-10-09T10:17Z").toString();
      expect(texto).toContain(idioma === "es" ? "Autor: Dr. Lucas Alaniz Pintos" : "Author: Lucas Alaniz Pintos, PhD");
      expect(texto).toContain('href="https://orcid.org/0009-0008-5179-2534"');
      expect(texto).toContain('href="mailto:lucasalanizpintos@gmail.com"');
    }
  });

  it("el aviso legal y la independencia dicen el autor, su ORCID y la cita recomendada", () => {
    for (const nombre of ["avisoLegal", "independencia"] as const) {
      const es = paginaServicio(nombre, "es").cuerpo.toString();
      const en = paginaServicio(nombre, "en").cuerpo.toString();
      expect(es).toContain("Dr. Lucas Alaniz Pintos");
      expect(en).toContain("Lucas Alaniz Pintos, PhD");
      for (const t of [es, en]) expect(t).toContain('href="https://orcid.org/0009-0008-5179-2534"');
      expect(es).toContain("Alaniz Pintos, L. (2026). European Observatory of Drone Incidents. Versión AAAA-MM. https://droneobservatory.eu. Licencia CC BY 4.0.");
      expect(en).toContain("Alaniz Pintos, L. (2026). European Observatory of Drone Incidents. Version YYYY-MM. https://droneobservatory.eu. Licence CC BY 4.0.");
    }
  });
});
