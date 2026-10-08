// Los ficheros públicos del almacén llevan la licencia dentro (recogida/licencia.py): la web los
// valida igual y, en las descargas, pone la suya (con la fecha de la versión) en su lugar.

import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import { conLicencia } from "../src/datos/licencia.ts";
import { validarColeccion, validarPrevision, validarPublicacionUcrania, validarSinUbicacion } from "../src/datos/validar.ts";

const RAIZ = join(import.meta.dirname, "..", "..");
const FIXTURES = join(RAIZ, "tests", "fixtures", "publicacion");
const configuracion = JSON.parse(readFileSync(join(RAIZ, "configuracion", "licencia_datos.json"), "utf-8")) as Record<string, unknown>;
const licencia = Object.fromEntries(["nombre", "url", "titular", "fuente", "alcance", "cita"].map((c) => [c, configuracion[c]]));

function conLaDelAlmacen(nombre: string): Record<string, unknown> {
  const datos = JSON.parse(readFileSync(join(FIXTURES, nombre), "utf-8")) as Record<string, unknown>;
  return { licencia, ...datos };
}

describe("licencia dentro de los ficheros del almacén", () => {
  it("los ficheros con su licencia validan", () => {
    expect(validarColeccion(conLaDelAlmacen("incidentes.geojson")).ok).toBe(true);
    expect(validarSinUbicacion(conLaDelAlmacen("incidentes_sin_ubicacion.json")).ok).toBe(true);
    expect(validarPublicacionUcrania(conLaDelAlmacen("ucrania.json")).ok).toBe(true);
    expect(validarPrevision(conLaDelAlmacen("prevision.json")).ok).toBe(true);
    expect(validarColeccion({ ...conLaDelAlmacen("incidentes.geojson"), licencia: { nombre: "x" } }).ok).toBe(false);
  });

  it("la descarga lleva una sola licencia, la de la web, la primera", () => {
    const texto = conLicencia(JSON.stringify(conLaDelAlmacen("ucrania.json")), "2026-10-08T12:17Z");
    const datos = JSON.parse(texto) as Record<string, { cita: { es: string } }>;
    expect(Object.keys(datos)[0]).toBe("licencia");
    expect(datos.licencia?.cita.es).toContain("08/10/2026");
    expect(texto.match(/"licencia"/g)).toHaveLength(1);
  });
});
