// Versiones citables de los datos abiertos: el índice del almacén se lee comprobando cada
// metadatos.json con su huella, la página de cada versión da sus ficheros con su huella, su
// licencia y su cita, y vercel.json sirve los ficheros desde el almacén sin tapar las páginas.

import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { validarVersiones } from "../src/datos/validar.ts";
import { rutaDeFicheroDeVersion, rutasDeVersion } from "../src/datos/versiones.ts";
import type { VersionDatos } from "../src/datos/versiones.ts";
import { destinoDeReescritura } from "../src/seguridad/despliegue.ts";
import type { ConfiguracionDespliegue } from "../src/seguridad/despliegue.ts";
import { cuerpoVersion, seccionVersiones } from "../src/texto/versiones.ts";
import { leerVersiones } from "../scripts/publicacion.ts";

const RAIZ = join(import.meta.dirname, "..", "..");
const FIXTURE = join(RAIZ, "tests", "fixtures", "publicacion", "versiones.json");
const vercel = JSON.parse(readFileSync(join(RAIZ, "vercel.json"), "utf-8")) as ConfiguracionDespliegue;

function version(): VersionDatos {
  const resultado = validarVersiones(JSON.parse(readFileSync(FIXTURE, "utf-8")));
  if (!resultado.ok) throw new Error(resultado.errores.join("\n"));
  const [v] = resultado.datos.versiones;
  if (v === undefined) throw new Error("sin versiones de ejemplo");
  return v;
}

describe("versiones citables", () => {
  it("la página de una versión da cada fichero con su huella, la licencia y la cita", () => {
    const v = version();
    for (const idioma of ["es", "en"] as const) {
      const texto = cuerpoVersion(v, idioma, "/metodologia").valor;
      for (const [nombre, f] of Object.entries(v.ficheros)) {
        expect(texto).toContain(`href="${rutaDeFicheroDeVersion(v.version, nombre)}"`);
        expect(texto).toContain(f.sha256);
      }
      expect(texto).toContain("CC BY 4.0");
      expect(texto).toContain(v.cita[idioma]);
      expect(texto).not.toMatch(/l[ií]mite|limitaci|limitation|\blimits?\b/i);
    }
    expect(v.cita.es).toBe(
      "European Observatory of Drone Incidents (2026). Datos abiertos, versión 2026-10. droneobservatory.eu/datos/versiones/2026-10/. Licencia CC BY 4.0.",
    );
    expect(rutasDeVersion("2026-10")).toEqual({ es: "/datos/versiones/2026-10", en: "/en/data/versions/2026-10" });
  });

  it("la metodología lista las versiones con la cita de la última", () => {
    const v = version();
    const texto = seccionVersiones([v], "es").valor;
    expect(texto).toContain('id="versiones"');
    expect(texto).toContain(`href="${rutasDeVersion(v.version).es}"`);
    expect(texto).toContain(`data-cita-version="${v.version}"`);
    expect(seccionVersiones([], "en").valor).toContain("first citable version");
  });

  it("vercel.json lleva los ficheros al almacén y deja las páginas a la web", () => {
    expect(destinoDeReescritura(vercel, "/datos/versiones/2026-10/incidentes.geojson")).toBe(
      "https://droneobservatory-almacen.nbg1.your-objectstorage.com/versiones/:version/:fichero",
    );
    expect(destinoDeReescritura(vercel, "/datos/versiones/2026-10/ucrania.csv")).not.toBeNull();
    expect(destinoDeReescritura(vercel, "/datos/versiones/2026-10")).toBeNull();
    expect(destinoDeReescritura(vercel, "/datos/incidentes.geojson")).toBeNull();
  });
});

describe("lectura del índice del almacén", () => {
  const anterior = process.env.EODI_PUBLICACION;
  beforeEach(() => {
    delete process.env.EODI_PUBLICACION;
  });
  afterEach(() => {
    if (anterior !== undefined) process.env.EODI_PUBLICACION = anterior;
  });

  const metadatos = new TextEncoder().encode(JSON.stringify(version()));
  const huella = createHash("sha256").update(metadatos).digest("hex");
  const indice = (sha: string) => new TextEncoder().encode(JSON.stringify({ version: 1, versiones: [{ version: "2026-10", metadatos_sha256: sha }] }));

  it("sin índice todavía (el almacén responde 403), ninguna versión", async () => {
    expect(await leerVersiones(RAIZ, () => Promise.resolve(null))).toEqual({ versiones: [] });
  });

  it("cada metadatos.json se comprueba con la huella del índice", async () => {
    const leer = (sha: string) => (url: string) =>
      Promise.resolve(url.endsWith("indice.json") ? indice(sha) : metadatos);
    const bien = (await leerVersiones(RAIZ, leer(huella))) as { versiones: VersionDatos[] };
    expect(bien.versiones.map((v) => v.version)).toEqual(["2026-10"]);
    await expect(leerVersiones(RAIZ, leer("0".repeat(64)))).rejects.toThrow(/no coincide/);
  });
});
