// Caché del navegador para lo que no cambia con los datos (vercel.json): sin regla propia, Vercel
// manda «max-age=0, must-revalidate» y cada bandera, icono o logo se volvía a validar en cada carga.

import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

interface Regla {
  source: string;
  headers: { key: string; value: string }[];
}

const vercel = JSON.parse(readFileSync(join(import.meta.dirname, "..", "..", "vercel.json"), "utf8")) as {
  headers: Regla[];
};

function cache(ruta: string): string | null {
  let valor: string | null = null;
  for (const regla of vercel.headers) {
    if (!new RegExp(`^${regla.source}$`).test(ruta)) continue;
    for (const cabecera of regla.headers) if (cabecera.key === "Cache-Control") valor = cabecera.value;
  }
  return valor;
}

describe("caché de lo estático", () => {
  it("banderas, marca e iconos se guardan una semana, como los contornos del mapa", () => {
    for (const ruta of ["/banderas/de.svg", "/marca/logo-384.png", "/iconos/icono-192.png", "/mapa/tierra.geojson"]) {
      expect(cache(ruta), ruta).toBe("public, max-age=604800");
    }
  });

  it("el código con huella no caduca; los datos, el service worker y las páginas se siguen validando", () => {
    expect(cache("/assets/index-AbC123.js")).toBe("public, max-age=31536000, immutable");
    expect(cache("/datos/resumen.json")).toBe("public, max-age=300, must-revalidate");
    for (const ruta of ["/sw.js", "/", "/EODI-2026-00719", "/manifest.webmanifest", "/compartir.png"]) {
      const valor = cache(ruta);
      expect(valor === null || !/max-age=(?!0\b)\d+/.test(valor), ruta).toBe(true);
    }
  });
});
