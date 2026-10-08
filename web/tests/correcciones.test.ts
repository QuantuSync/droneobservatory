// Registro público de correcciones: el fichero publicado valida, la página dice su criterio, va
// de la más reciente a la más antigua, enlaza solo a fichas que existen y cada incidente
// corregido lleva su ancla; la ficha enseña «Corregido el…» con el enlace a su entrada.

import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import { anclaDeCorreccion, enlaceACorreccion, ultimasCorrecciones } from "../src/datos/correcciones.ts";
import type { RegistroCorrecciones } from "../src/datos/correcciones.ts";
import { validarCorrecciones } from "../src/datos/validar.ts";
import { cuerpoRegistro, RUTAS_REGISTRO } from "../src/texto/correcciones.ts";
import { enlacesSobre } from "../src/texto/servicio.ts";

const FIXTURE = join(import.meta.dirname, "..", "..", "tests", "fixtures", "publicacion", "correcciones.json");

function registro(): RegistroCorrecciones {
  const resultado = validarCorrecciones(JSON.parse(readFileSync(FIXTURE, "utf-8")));
  if (!resultado.ok) throw new Error(resultado.errores.join("\n"));
  return resultado.datos;
}

describe("registro de correcciones", () => {
  it("el fichero de ejemplo valida y va de la más reciente a la más antigua", () => {
    const r = registro();
    expect(r.correcciones.length).toBeGreaterThan(0);
    const fechas = r.correcciones.map((c) => c.fecha);
    expect([...fechas].sort().reverse()).toEqual(fechas);
    expect(validarCorrecciones({ ...r, correcciones: [{ ...r.correcciones[0], motivo: { es: "x" } }] }).ok).toBe(false);
  });

  it("la página dice su criterio y enlaza solo a fichas publicadas, en los dos idiomas", () => {
    const r = registro();
    const publicados = new Set(r.correcciones.flatMap((c) => (c.enlace === null ? [] : [c.enlace])).slice(0, 3));
    for (const idioma of ["es", "en"] as const) {
      const texto = cuerpoRegistro(r, idioma, publicados).valor;
      expect(texto).toContain('id="criterio"');
      expect(texto).toContain(idioma === "es" ? "No entran los datos nuevos" : "New data does not go in");
      expect(texto).not.toMatch(/l[ií]mite|limitaci|limitation|\blimits?\b/i);
      for (const c of r.correcciones) expect(texto).toContain(c.motivo[idioma].replace(/&/g, "&amp;").replace(/"/g, "&quot;").slice(1, 20));
      const fichas = [...texto.matchAll(/href="[^"#]*\/(EODI-\d{4}-\d{5})"/g)].map((m) => m[1]);
      expect(fichas.length).toBeGreaterThan(0);
      for (const id of fichas) expect(publicados.has(id ?? "")).toBe(true);
      for (const id of publicados) expect(texto).toContain(`id="${anclaDeCorreccion(id)}"`);
    }
  });

  it("la ficha lleva la fecha de la corrección más reciente y su enlace", () => {
    const r = registro();
    const ultimas = ultimasCorrecciones(r);
    for (const [id, fecha] of ultimas) {
      const suyas = r.correcciones.filter((c) => c.enlace === id).map((c) => c.fecha);
      expect(fecha).toBe(suyas.sort().at(-1));
    }
    expect(enlaceACorreccion("EODI-2025-00295", "en")).toBe("/en/corrections/log#corregido-EODI-2025-00295");
  });

  it("se enlaza desde «Sobre el observatorio», tras «Correcciones»", () => {
    for (const idioma of ["es", "en"] as const) {
      const rutas = enlacesSobre(idioma).map((s) => s.ruta);
      expect(rutas.indexOf(RUTAS_REGISTRO[idioma])).toBe(rutas.indexOf(idioma === "es" ? "/correcciones" : "/en/corrections") + 1);
    }
  });
});
