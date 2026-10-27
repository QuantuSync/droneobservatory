// Las imágenes de la vista previa (scripts/imagenes.ts): Europa cabe en la imagen, el PNG es válido
// y cada ficha declara la suya en la cabecera.

import { inflateSync } from "node:zlib";

import { describe, expect, it } from "vitest";

import { codificarPng, proyectar, trazoDePaises } from "../scripts/imagenes.ts";
import { etiquetasDeCabecera } from "../src/cabecera.ts";
import { IMAGEN_COMPARTIR_ALTO, IMAGEN_COMPARTIR_ANCHO, imagenDeFicha } from "../src/sitio.ts";

describe("imágenes de la vista previa", () => {
  it("Aalborg, Chipre y Helsinki caen dentro de la imagen; las Azores, en el borde izquierdo del mapa", () => {
    for (const [lon, lat] of [[9.85, 57.09], [33.4, 35.1], [24.94, 60.17]] as const) {
      const [x, y] = proyectar(lon, lat);
      expect(x).toBeGreaterThan(0);
      expect(x).toBeLessThan(IMAGEN_COMPARTIR_ANCHO);
      expect(y).toBeGreaterThan(0);
      expect(y).toBeLessThan(IMAGEN_COMPARTIR_ALTO);
    }
  });

  it("el trazo de los países salta los anillos fuera de la imagen", () => {
    const dentro = { type: "Polygon" as const, coordinates: [[[9, 56], [10, 56], [10, 57], [9, 56]]] as [number, number][][] };
    const fuera = { type: "Polygon" as const, coordinates: [[[170, 60], [171, 60], [171, 61], [170, 60]]] as [number, number][][] };
    expect(trazoDePaises([dentro])).toMatch(/^M.+Z$/u);
    expect(trazoDePaises([fuera])).toBe("");
  });

  it("el PNG lleva su firma, su tamaño y las filas que se pueden leer", () => {
    const ancho = 3;
    const alto = 2;
    const rgba = new Uint8Array(ancho * alto * 4).map((_, i) => (i * 37) % 256);
    const png = Buffer.from(codificarPng(rgba, ancho, alto));
    expect([...png.subarray(0, 8)]).toEqual([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]);
    expect(png.readUInt32BE(16)).toBe(ancho);
    expect(png.readUInt32BE(20)).toBe(alto);
    const largo = png.readUInt32BE(33);
    expect(png.subarray(37, 41).toString("ascii")).toBe("IDAT");
    expect(inflateSync(png.subarray(41, 41 + largo)).length).toBe(alto * (1 + ancho * 3));
  });

  it("la cabecera de una ficha lleva su imagen y su texto; las demás, la general", () => {
    const ficha = etiquetasDeCabecera({
      idioma: "en",
      id: "EODI-2025-00228",
      titulo: "t",
      descripcion: "d",
      imagen: { ruta: imagenDeFicha("EODI-2025-00228", "en"), alt: "Aalborg · not substantiated" },
    });
    expect(ficha).toContain('<meta property="og:image" content="https://droneobservatory.eu/compartir/EODI-2025-00228-en.png">');
    expect(ficha).toContain('<meta name="twitter:image:alt" content="Aalborg · not substantiated">');
    expect(ficha).toContain('<meta name="twitter:card" content="summary_large_image">');
    const portada = etiquetasDeCabecera({ idioma: "es", id: null, titulo: "t", descripcion: "d" });
    expect(portada).toContain('content="https://droneobservatory.eu/compartir.png"');
  });
});
