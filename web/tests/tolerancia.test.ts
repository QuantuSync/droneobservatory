// La compilación nunca falla por el contenido de los datos (scripts/tolerancia.ts): un campo nuevo
// se ignora y se apunta, un elemento roto se quita, un fichero ilegible se toma de la web anterior.
// Como el 14 de octubre de 2026, cuando los datos publicados traían un campo que main no conocía.

import { readFileSync } from "node:fs";
import { join } from "node:path";

import { afterEach, describe, expect, it } from "vitest";

import { tolerarCamposNuevos, validarColeccion, validarPublicacionUcrania } from "../src/datos/validar.ts";
import { aceptar, depurar, patronDeRuta, resumirIgnorados } from "../scripts/tolerancia.ts";

const FIXTURES = join(__dirname, "..", "..", "tests", "fixtures", "publicacion");
const leer = (nombre: string): Record<string, unknown> =>
  JSON.parse(readFileSync(join(FIXTURES, nombre), "utf-8")) as Record<string, unknown>;

type Feature = { id: string; properties: Record<string, unknown> };

afterEach(() => tolerarCamposNuevos(false));

describe("tolerancia del build a los datos", () => {
  it("agrupa los campos ignorados por su patrón", () => {
    expect(patronDeRuta(".features[12].properties.fuentes[3].traduccion")).toBe(
      ".features[].properties.fuentes[].traduccion",
    );
    expect(resumirIgnorados([".a[1].x", ".a[2].x", ".b"])).toEqual([".a[].x (2 veces)", ".b (1 vez)"]);
  });

  it("un campo que la web no conoce se ignora y queda apuntado", () => {
    tolerarCamposNuevos(true, true);
    const coleccion = leer("incidentes.geojson");
    const features = coleccion.features as Feature[];
    for (const f of features) f.properties.campo_futuro = { es: "a", en: "b" };
    const avisos: string[] = [];
    const datos = depurar("incidentes.geojson", coleccion, validarColeccion, ["features"], avisos);
    expect(datos?.features).toHaveLength(features.length);
    expect(avisos).toEqual([
      `incidentes.geojson: campo que la web no conoce, ignorado: .features[].properties.campo_futuro (${features.length} ${features.length === 1 ? "vez" : "veces"})`,
    ]);
  });

  it("sin tolerancia, el mismo campo invalida el fichero (las pruebas validan cerrado)", () => {
    const coleccion = leer("incidentes.geojson");
    (coleccion.features as Feature[])[0]!.properties.campo_futuro = 1;
    expect(validarColeccion(coleccion).ok).toBe(false);
  });

  it("un elemento que no cumple el esquema se quita y los demás se publican", () => {
    tolerarCamposNuevos(true, true);
    const ucrania = leer("ucrania.json");
    const ataques = ucrania.ataques as Record<string, unknown>[];
    expect(ataques.length).toBeGreaterThan(1);
    ataques[0]!.id = null;
    const avisos: string[] = [];
    const datos = depurar("ucrania.json", ucrania, validarPublicacionUcrania, ["ataques", "impactos"], avisos);
    expect(datos?.ataques).toHaveLength(ataques.length - 1);
    expect(avisos[0]).toMatch(/^ucrania\.json: ataques\[0\] no cumple el esquema y no se publica en la web/);
  });

  it("un fichero ilegible se toma de la web anterior; sin ella, null", async () => {
    tolerarCamposNuevos(true, true);
    const avisos: string[] = [];
    const roto = () => Promise.reject(new SyntaxError("JSON roto"));
    const anterior = () => Promise.resolve(leer("incidentes.geojson"));
    const aceptado = await aceptar("incidentes.geojson", roto, validarColeccion, ["features"], avisos, anterior);
    expect(aceptado?.origen).toBe("anterior");
    expect(avisos).toContain("incidentes.geojson: se publica el de la compilación anterior");

    const sinWeb = () => Promise.reject(new Error("HTTP 503"));
    expect(await aceptar("incidentes.geojson", roto, validarColeccion, ["features"], [], sinWeb)).toBeNull();
  });
});
