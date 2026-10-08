// Nombres de lugar en el idioma de la página (src/i18n/nombresLugar.ts): ningún nombre de lugar se
// enseña en otra escritura ni como una descripción en otra lengua. Corre con los datos de prueba
// y, en la integración continua, con los publicados (EODI_PUBLICACION).

import { readFileSync } from "node:fs";
import { join, resolve } from "node:path";

import { describe, expect, it } from "vitest";

import { latino, NOMBRES_LUGAR, nombreDeLugar } from "../src/i18n/nombresLugar.ts";
import type { ColeccionIncidentes, PublicacionSinUbicacion } from "../src/datos/tipos.ts";

const RAIZ = join(import.meta.dirname, "..", "..");
const CARPETA = process.env.EODI_PUBLICACION ?? join(RAIZ, "tests", "fixtures", "publicacion");
const OTRA_ESCRITURA = /[Ͱ-Ͽἀ-῿Ѐ-ӿ]/;

function leer<T>(nombre: string): T {
  return JSON.parse(readFileSync(resolve(CARPETA, nombre), "utf-8")) as T;
}

describe("nombres de lugar", () => {
  it("la zona económica exclusiva de Bulgaria y los demás genéricos se escriben en cada idioma", () => {
    expect(nombreDeLugar("exclusive economic zone", "es")).toBe("Zona económica exclusiva");
    expect(nombreDeLugar("exclusive economic zone", "en")).toBe("Exclusive economic zone");
    expect(nombreDeLugar("gare de triage de Mulhouse", "es")).toBe("Estación de clasificación de Mulhouse");
    expect(nombreDeLugar("Warsaw", "es")).toBe("Varsovia");
    expect(nombreDeLugar("eastern Latvia", "es")).toBe("este de Letonia");
    expect(nombreDeLugar("Αιγαίο", "en")).toBe("Aegean");
    // Un nombre propio se deja como lo escribe la fuente.
    expect(nombreDeLugar("Portul Constanța", "es")).toBe("Portul Constanța");
  });

  it("lo que no está en la tabla: otra escritura al alfabeto latino, descripciones fuera", () => {
    expect(latino("Бургас")).toBe("Burgas");
    expect(nombreDeLugar("Пловдив", "es")).toBe("Plovdiv");
    expect(nombreDeLugar("Θεσσαλονίκη", "en")).toBe("Thessaloniki");
    expect(nombreDeLugar("north-western coast", "es")).toBeNull();
    for (const [original, escrito] of Object.entries(NOMBRES_LUGAR)) {
      expect(escrito.es.length > 0 && escrito.en.length > 0, original).toBe(true);
    }
  });

  it("en los datos publicados, ningún lugar sale en otra escritura ni como descripción en otra lengua", () => {
    const coleccion = leer<ColeccionIncidentes>("incidentes.geojson");
    const sin = leer<PublicacionSinUbicacion>("incidentes_sin_ubicacion.json");
    const lugares = [
      ...coleccion.features.map((f) => ({ lugar: f.properties.lugar as { localidad?: string; region?: string }, objetivo: f.properties.objetivo })),
      ...sin.incidentes.map((i) => ({ lugar: i.lugar as { localidad?: string; region?: string }, objetivo: i.objetivo })),
    ];
    for (const { lugar, objetivo } of lugares) {
      for (const nombre of [lugar.localidad, lugar.region, objetivo?.nombre]) {
        if (nombre === undefined) continue;
        for (const idioma of ["es", "en"] as const) {
          const escrito = nombreDeLugar(nombre, idioma);
          if (escrito === null) continue;
          expect(OTRA_ESCRITURA.test(escrito), `${nombre} en ${idioma}`).toBe(false);
        }
      }
    }
  });
});
